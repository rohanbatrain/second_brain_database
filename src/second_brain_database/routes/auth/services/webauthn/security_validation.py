"""
WebAuthn security validation infrastructure.

This module provides enhanced security validation patterns for WebAuthn endpoints,
including request sanitization, security headers, origin validation, and 
comprehensive security monitoring following existing security patterns.
"""

import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse

from fastapi import HTTPException, Request, status
from starlette.responses import Response

from second_brain_database.config import settings
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.utils.logging_utils import log_security_event

logger = get_logger(prefix="[WebAuthn Security]")


class WebAuthnSecurityValidator:
    """
    Security validator for WebAuthn operations following existing security patterns.
    
    Provides request validation, sanitization, and security checks specifically
    designed for WebAuthn endpoints with comprehensive logging and monitoring.
    """

    def __init__(self):
        """Initialize WebAuthn security validator with configuration."""
        self.logger = logger
        
        # WebAuthn-specific security configuration
        self.allowed_origins = self._get_allowed_origins()
        self.max_challenge_age = 300  # 5 minutes
        self.max_credential_id_length = 1024  # Base64url encoded credential ID limit
        self.max_authenticator_data_length = 2048  # Authenticator data size limit
        self.max_client_data_length = 2048  # Client data JSON size limit
        self.max_signature_length = 1024  # Signature size limit
        
        # Suspicious patterns for detection
        self.suspicious_patterns = [
            r'<script[^>]*>.*?</script>',  # Script injection
            r'javascript:',  # JavaScript protocol
            r'data:.*base64',  # Suspicious data URLs
            r'eval\s*\(',  # Code evaluation
            r'Function\s*\(',  # Function constructor
        ]
        
        self.logger.info("WebAuthn security validator initialized with %d allowed origins", len(self.allowed_origins))

    def _get_allowed_origins(self) -> Set[str]:
        """Get allowed origins for WebAuthn operations."""
        origins = set()
        
        # Add configured WebAuthn RP ID
        if hasattr(settings, 'WEBAUTHN_RP_ID') and settings.WEBAUTHN_RP_ID:
            origins.add(f"https://{settings.WEBAUTHN_RP_ID}")
            # Also allow localhost for development
            if settings.WEBAUTHN_RP_ID == "localhost":
                origins.add("http://localhost")
                origins.add("http://localhost:3000")  # Common dev port
                origins.add("http://localhost:8080")  # Common dev port
        
        # Add base URL if configured
        if hasattr(settings, 'BASE_URL') and settings.BASE_URL:
            origins.add(settings.BASE_URL)
        
        # Development fallbacks
        if not settings.is_production:
            origins.update([
                "http://localhost",
                "http://localhost:3000",
                "http://localhost:8080",
                "http://127.0.0.1",
                "http://127.0.0.1:3000",
                "http://127.0.0.1:8080",
            ])
        
        return origins

    async def validate_webauthn_request(
        self,
        request: Request,
        operation_type: str,
        user_id: Optional[str] = None,
        additional_checks: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Validate WebAuthn request with comprehensive security checks.
        
        Args:
            request: FastAPI request object
            operation_type: Type of WebAuthn operation (registration, authentication)
            user_id: User ID for logging context
            additional_checks: Additional validation parameters
            
        Returns:
            Dict containing validation results and security context
            
        Raises:
            HTTPException: If validation fails
        """
        validation_context = {
            "operation_type": operation_type,
            "user_id": user_id or "unknown",
            "ip_address": self._get_client_ip(request),
            "user_agent": request.headers.get("user-agent", "unknown"),
            "origin": request.headers.get("origin"),
            "referer": request.headers.get("referer"),
            "content_type": request.headers.get("content-type"),
        }

        try:
            # 1. Validate request headers
            await self._validate_request_headers(request, validation_context)
            
            # 2. Validate origin and referer
            await self._validate_origin_and_referer(request, validation_context)
            
            # 3. Validate content type and size
            await self._validate_content_type_and_size(request, validation_context)
            
            # 4. Perform operation-specific validation
            if additional_checks:
                await self._validate_operation_specific(request, operation_type, additional_checks, validation_context)
            
            # Log successful validation
            log_security_event(
                event_type=f"webauthn_{operation_type}_request_validated",
                user_id=validation_context["user_id"],
                ip_address=validation_context["ip_address"],
                success=True,
                details={
                    "operation_type": operation_type,
                    "origin": validation_context["origin"],
                    "user_agent_prefix": validation_context["user_agent"][:50] + "..." if len(validation_context["user_agent"]) > 50 else validation_context["user_agent"],
                }
            )
            
            return validation_context
            
        except HTTPException:
            # Log validation failure
            log_security_event(
                event_type=f"webauthn_{operation_type}_request_validation_failed",
                user_id=validation_context["user_id"],
                ip_address=validation_context["ip_address"],
                success=False,
                details=validation_context
            )
            raise
        except Exception as e:
            self.logger.error("WebAuthn request validation error: %s", e, exc_info=True)
            log_security_event(
                event_type=f"webauthn_{operation_type}_request_validation_error",
                user_id=validation_context["user_id"],
                ip_address=validation_context["ip_address"],
                success=False,
                details={"error": str(e), **validation_context}
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Request validation failed"
            )

    async def _validate_request_headers(self, request: Request, context: Dict[str, Any]) -> None:
        """Validate required and security-relevant headers."""
        # Check for required headers
        if not request.headers.get("user-agent"):
            self.logger.warning("WebAuthn request missing User-Agent header")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing required User-Agent header"
            )
        
        # Check for suspicious User-Agent patterns
        user_agent = request.headers.get("user-agent", "")
        if self._contains_suspicious_patterns(user_agent):
            self.logger.warning("Suspicious User-Agent detected: %s", user_agent[:100])
            log_security_event(
                event_type="webauthn_suspicious_user_agent",
                user_id=context["user_id"],
                ip_address=context["ip_address"],
                success=False,
                details={"user_agent": user_agent[:100]}
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid User-Agent"
            )

    async def _validate_origin_and_referer(self, request: Request, context: Dict[str, Any]) -> None:
        """Validate origin and referer headers for CSRF protection."""
        origin = request.headers.get("origin")
        referer = request.headers.get("referer")
        
        # Origin validation for WebAuthn operations
        if origin:
            if origin not in self.allowed_origins:
                self.logger.warning("WebAuthn request from disallowed origin: %s", origin)
                log_security_event(
                    event_type="webauthn_disallowed_origin",
                    user_id=context["user_id"],
                    ip_address=context["ip_address"],
                    success=False,
                    details={"origin": origin, "allowed_origins": list(self.allowed_origins)}
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Origin not allowed for WebAuthn operations"
                )
        
        # Referer validation (if present)
        if referer:
            try:
                referer_parsed = urlparse(referer)
                referer_origin = f"{referer_parsed.scheme}://{referer_parsed.netloc}"
                
                if referer_origin not in self.allowed_origins:
                    self.logger.warning("WebAuthn request from disallowed referer: %s", referer)
                    log_security_event(
                        event_type="webauthn_disallowed_referer",
                        user_id=context["user_id"],
                        ip_address=context["ip_address"],
                        success=False,
                        details={"referer": referer, "referer_origin": referer_origin}
                    )
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Referer not allowed for WebAuthn operations"
                    )
            except Exception as e:
                self.logger.warning("Invalid referer header: %s", referer)
                # Don't fail on referer parsing errors, just log

    async def _validate_content_type_and_size(self, request: Request, context: Dict[str, Any]) -> None:
        """Validate content type and request size limits."""
        content_type = request.headers.get("content-type", "")
        
        # Validate content type for POST requests
        if request.method == "POST":
            if not content_type.startswith("application/json"):
                self.logger.warning("WebAuthn POST request with invalid content type: %s", content_type)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Content-Type must be application/json for WebAuthn operations"
                )
        
        # Check content length if available
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                length = int(content_length)
                max_size = 10 * 1024 * 1024  # 10MB limit for WebAuthn requests
                if length > max_size:
                    self.logger.warning("WebAuthn request exceeds size limit: %d bytes", length)
                    log_security_event(
                        event_type="webauthn_request_size_exceeded",
                        user_id=context["user_id"],
                        ip_address=context["ip_address"],
                        success=False,
                        details={"content_length": length, "max_size": max_size}
                    )
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="Request size exceeds limit"
                    )
            except ValueError:
                # Invalid content-length header, ignore
                pass

    async def _validate_operation_specific(
        self,
        request: Request,
        operation_type: str,
        additional_checks: Dict[str, Any],
        context: Dict[str, Any]
    ) -> None:
        """Perform operation-specific validation checks."""
        if operation_type == "registration":
            await self._validate_registration_specific(request, additional_checks, context)
        elif operation_type == "authentication":
            await self._validate_authentication_specific(request, additional_checks, context)

    async def _validate_registration_specific(
        self,
        request: Request,
        checks: Dict[str, Any],
        context: Dict[str, Any]
    ) -> None:
        """Validate registration-specific security requirements."""
        # Registration requires authentication
        if not checks.get("authenticated_user"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required for WebAuthn registration"
            )

    async def _validate_authentication_specific(
        self,
        request: Request,
        checks: Dict[str, Any],
        context: Dict[str, Any]
    ) -> None:
        """Validate authentication-specific security requirements."""
        # Authentication should not require existing authentication
        pass

    def sanitize_webauthn_data(self, data: Dict[str, Any], operation_type: str) -> Dict[str, Any]:
        """
        Sanitize WebAuthn request data following existing sanitization patterns.
        
        Args:
            data: WebAuthn request data
            operation_type: Type of operation (registration, authentication)
            
        Returns:
            Sanitized data dictionary
        """
        sanitized = {}
        
        try:
            if operation_type == "registration":
                sanitized = self._sanitize_registration_data(data)
            elif operation_type == "authentication":
                sanitized = self._sanitize_authentication_data(data)
            else:
                sanitized = self._sanitize_generic_data(data)
            
            self.logger.debug("WebAuthn data sanitized for operation: %s", operation_type)
            return sanitized
            
        except Exception as e:
            self.logger.error("WebAuthn data sanitization failed: %s", e, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid request data format"
            )

    def _sanitize_registration_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize WebAuthn registration data."""
        sanitized = {}
        
        # Sanitize device name if present
        if "device_name" in data:
            device_name = str(data["device_name"])[:100]  # Limit length
            device_name = re.sub(r'[<>"\']', '', device_name)  # Remove dangerous chars
            sanitized["device_name"] = device_name
        
        # Validate and sanitize credential response
        if "id" in data:
            sanitized["id"] = self._sanitize_base64url(data["id"], self.max_credential_id_length)
        
        if "rawId" in data:
            sanitized["rawId"] = self._sanitize_base64url(data["rawId"], self.max_credential_id_length)
        
        if "response" in data and isinstance(data["response"], dict):
            sanitized["response"] = self._sanitize_credential_response(data["response"])
        
        if "type" in data:
            # Only allow "public-key" type
            if data["type"] == "public-key":
                sanitized["type"] = "public-key"
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid credential type"
                )
        
        return sanitized

    def _sanitize_authentication_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize WebAuthn authentication data."""
        sanitized = {}
        
        # Sanitize username/email for authentication begin
        if "username" in data:
            username = str(data["username"])[:100]
            username = re.sub(r'[<>"\']', '', username)
            sanitized["username"] = username
        
        if "email" in data:
            email = str(data["email"])[:255]
            # Basic email format validation
            if re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
                sanitized["email"] = email
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid email format"
                )
        
        # Sanitize user verification preference
        if "user_verification" in data:
            uv = data["user_verification"]
            if uv in ["required", "preferred", "discouraged"]:
                sanitized["user_verification"] = uv
            else:
                sanitized["user_verification"] = "preferred"  # Default
        
        # Sanitize assertion response for authentication complete
        if "id" in data:
            sanitized["id"] = self._sanitize_base64url(data["id"], self.max_credential_id_length)
        
        if "response" in data and isinstance(data["response"], dict):
            sanitized["response"] = self._sanitize_assertion_response(data["response"])
        
        return sanitized

    def _sanitize_generic_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize generic WebAuthn data."""
        sanitized = {}
        
        # Only allow known safe keys
        safe_keys = {
            "id", "rawId", "response", "type", "device_name", 
            "username", "email", "user_verification"
        }
        
        for key, value in data.items():
            if key in safe_keys:
                if isinstance(value, str):
                    sanitized[key] = self._sanitize_string(value)
                elif isinstance(value, dict):
                    sanitized[key] = self._sanitize_dict(value)
                else:
                    sanitized[key] = value
        
        return sanitized

    def _sanitize_credential_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize credential creation response."""
        sanitized = {}
        
        if "attestationObject" in response:
            sanitized["attestationObject"] = self._sanitize_base64url(
                response["attestationObject"], 
                self.max_authenticator_data_length
            )
        
        if "clientDataJSON" in response:
            sanitized["clientDataJSON"] = self._sanitize_base64url(
                response["clientDataJSON"], 
                self.max_client_data_length
            )
        
        return sanitized

    def _sanitize_assertion_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize assertion response."""
        sanitized = {}
        
        if "authenticatorData" in response:
            sanitized["authenticatorData"] = self._sanitize_base64url(
                response["authenticatorData"], 
                self.max_authenticator_data_length
            )
        
        if "clientDataJSON" in response:
            sanitized["clientDataJSON"] = self._sanitize_base64url(
                response["clientDataJSON"], 
                self.max_client_data_length
            )
        
        if "signature" in response:
            sanitized["signature"] = self._sanitize_base64url(
                response["signature"], 
                self.max_signature_length
            )
        
        if "userHandle" in response:
            sanitized["userHandle"] = self._sanitize_base64url(
                response["userHandle"], 
                256  # Reasonable limit for user handle
            )
        
        return sanitized

    def _sanitize_base64url(self, value: str, max_length: int) -> str:
        """Sanitize base64url encoded value."""
        if not isinstance(value, str):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid base64url data type"
            )
        
        # Check length
        if len(value) > max_length:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Base64url data exceeds maximum length"
            )
        
        # Validate base64url format (basic check)
        if not re.match(r'^[A-Za-z0-9_-]*$', value):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid base64url format"
            )
        
        return value

    def _sanitize_string(self, value: str, max_length: int = 1000) -> str:
        """Sanitize string value."""
        if not isinstance(value, str):
            return str(value)[:max_length]
        
        # Remove suspicious patterns
        sanitized = value[:max_length]
        for pattern in self.suspicious_patterns:
            sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE)
        
        return sanitized

    def _sanitize_dict(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize dictionary value."""
        sanitized = {}
        for k, v in value.items():
            if isinstance(k, str) and len(k) <= 100:  # Reasonable key length
                if isinstance(v, str):
                    sanitized[k] = self._sanitize_string(v)
                elif isinstance(v, (int, float, bool)):
                    sanitized[k] = v
                elif isinstance(v, dict):
                    sanitized[k] = self._sanitize_dict(v)
                # Skip other types for security
        return sanitized

    def _contains_suspicious_patterns(self, text: str) -> bool:
        """Check if text contains suspicious patterns."""
        for pattern in self.suspicious_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address from request following existing patterns."""
        # Check for forwarded headers (for reverse proxy setups)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        # Fallback to direct client IP
        return request.client.host if request.client else "unknown"

    def add_security_headers(self, response: Response, operation_type: str) -> Response:
        """
        Add WebAuthn-specific security headers following existing patterns.
        
        Args:
            response: HTTP response
            operation_type: WebAuthn operation type
            
        Returns:
            Response with added security headers
        """
        # Content Security Policy for WebAuthn operations
        csp_policy = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "  # WebAuthn may need inline scripts
            "connect-src 'self'; "
            "img-src 'self' data:; "
            "style-src 'self' 'unsafe-inline'; "
            "font-src 'self'; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
        
        # Add comprehensive security headers following existing patterns
        response.headers["Content-Security-Policy"] = csp_policy
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # Additional security headers for enhanced protection
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        response.headers["X-Download-Options"] = "noopen"
        response.headers["X-DNS-Prefetch-Control"] = "off"
        
        # WebAuthn-specific headers
        response.headers["X-WebAuthn-Operation"] = operation_type
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        
        # CORS headers for WebAuthn following existing CORS patterns
        if not settings.is_production:
            # Development CORS - permissive for testing
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
            response.headers["Access-Control-Max-Age"] = "86400"  # 24 hours
        else:
            # Production CORS - restrictive following existing patterns
            if hasattr(settings, 'WEBAUTHN_RP_ID') and settings.WEBAUTHN_RP_ID:
                allowed_origin = f"https://{settings.WEBAUTHN_RP_ID}"
                response.headers["Access-Control-Allow-Origin"] = allowed_origin
                response.headers["Access-Control-Allow-Methods"] = "POST, GET, DELETE, OPTIONS"
                response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
                response.headers["Access-Control-Allow-Credentials"] = "true"
                response.headers["Access-Control-Max-Age"] = "3600"  # 1 hour
        
        return response

    async def validate_request_integrity(
        self,
        request: Request,
        operation_type: str,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate request integrity and security following existing patterns.
        
        This method provides additional security validation beyond basic request validation,
        including timing attack protection, request fingerprinting, and advanced threat detection.
        
        Args:
            request: FastAPI request object
            operation_type: WebAuthn operation type
            user_id: User ID for context
            
        Returns:
            Dict containing integrity validation results
        """
        integrity_context = {
            "operation_type": operation_type,
            "user_id": user_id or "unknown",
            "timestamp": datetime.utcnow().isoformat(),
            "request_fingerprint": self._generate_request_fingerprint(request),
        }
        
        try:
            # 1. Validate request timing (prevent timing attacks)
            await self._validate_request_timing(request, integrity_context)
            
            # 2. Check for suspicious request patterns
            await self._detect_suspicious_patterns(request, integrity_context)
            
            # 3. Validate request consistency
            await self._validate_request_consistency(request, integrity_context)
            
            # 4. Check for automated/bot requests
            await self._detect_automated_requests(request, integrity_context)
            
            # Log successful integrity validation
            log_security_event(
                event_type=f"webauthn_{operation_type}_integrity_validated",
                user_id=integrity_context["user_id"],
                ip_address=self._get_client_ip(request),
                success=True,
                details={
                    "operation_type": operation_type,
                    "fingerprint": integrity_context["request_fingerprint"][:16] + "...",
                }
            )
            
            return integrity_context
            
        except HTTPException:
            # Log integrity validation failure
            log_security_event(
                event_type=f"webauthn_{operation_type}_integrity_failed",
                user_id=integrity_context["user_id"],
                ip_address=self._get_client_ip(request),
                success=False,
                details=integrity_context
            )
            raise
        except Exception as e:
            self.logger.error("Request integrity validation error: %s", e, exc_info=True)
            log_security_event(
                event_type=f"webauthn_{operation_type}_integrity_error",
                user_id=integrity_context["user_id"],
                ip_address=self._get_client_ip(request),
                success=False,
                details={"error": str(e), **integrity_context}
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Request integrity validation failed"
            )

    def _generate_request_fingerprint(self, request: Request) -> str:
        """Generate a unique fingerprint for the request."""
        import hashlib
        
        fingerprint_data = [
            request.method,
            str(request.url.path),
            request.headers.get("user-agent", ""),
            request.headers.get("accept", ""),
            request.headers.get("accept-language", ""),
            request.headers.get("accept-encoding", ""),
            self._get_client_ip(request),
        ]
        
        fingerprint_string = "|".join(fingerprint_data)
        return hashlib.sha256(fingerprint_string.encode()).hexdigest()

    async def _validate_request_timing(self, request: Request, context: Dict[str, Any]) -> None:
        """Validate request timing to prevent timing attacks."""
        # Add small random delay to prevent timing analysis
        import asyncio
        import random
        
        # Random delay between 10-50ms to prevent timing attacks
        delay = random.uniform(0.01, 0.05)
        await asyncio.sleep(delay)
        
        context["timing_delay_applied"] = delay

    async def _detect_suspicious_patterns(self, request: Request, context: Dict[str, Any]) -> None:
        """Detect suspicious request patterns."""
        suspicious_indicators = []
        
        # Check for missing or suspicious User-Agent
        user_agent = request.headers.get("user-agent", "")
        if not user_agent or len(user_agent) < 10:
            suspicious_indicators.append("missing_or_short_user_agent")
        
        # Check for suspicious header combinations
        if not request.headers.get("accept"):
            suspicious_indicators.append("missing_accept_header")
        
        # Check for automation indicators
        automation_patterns = [
            "bot", "crawler", "spider", "scraper", "automated",
            "python-requests", "curl", "wget", "postman"
        ]
        
        for pattern in automation_patterns:
            if pattern.lower() in user_agent.lower():
                suspicious_indicators.append(f"automation_pattern_{pattern}")
        
        context["suspicious_indicators"] = suspicious_indicators
        
        # Log if suspicious patterns detected
        if suspicious_indicators:
            log_security_event(
                event_type="webauthn_suspicious_request_patterns",
                user_id=context["user_id"],
                ip_address=self._get_client_ip(request),
                success=False,
                details={
                    "indicators": suspicious_indicators,
                    "user_agent": user_agent[:100],
                    "operation_type": context["operation_type"]
                }
            )

    async def _validate_request_consistency(self, request: Request, context: Dict[str, Any]) -> None:
        """Validate request consistency and coherence."""
        consistency_checks = []
        
        # Check Content-Type consistency for POST requests
        if request.method == "POST":
            content_type = request.headers.get("content-type", "")
            if not content_type.startswith("application/json"):
                consistency_checks.append("invalid_content_type_for_post")
        
        # Check for required headers
        required_headers = ["user-agent", "accept"]
        for header in required_headers:
            if not request.headers.get(header):
                consistency_checks.append(f"missing_required_header_{header}")
        
        context["consistency_checks"] = consistency_checks

    async def _detect_automated_requests(self, request: Request, context: Dict[str, Any]) -> None:
        """Detect automated/bot requests."""
        automation_score = 0
        automation_indicators = []
        
        user_agent = request.headers.get("user-agent", "")
        
        # Check for common automation libraries
        automation_signatures = [
            ("python-requests", 3),
            ("curl/", 2),
            ("wget/", 2),
            ("postman", 2),
            ("insomnia", 2),
            ("httpie", 2),
        ]
        
        for signature, score in automation_signatures:
            if signature.lower() in user_agent.lower():
                automation_score += score
                automation_indicators.append(signature)
        
        # Check for missing browser-specific headers
        browser_headers = ["accept-language", "accept-encoding", "dnt"]
        missing_browser_headers = 0
        
        for header in browser_headers:
            if not request.headers.get(header):
                missing_browser_headers += 1
        
        if missing_browser_headers >= 2:
            automation_score += 2
            automation_indicators.append("missing_browser_headers")
        
        context["automation_score"] = automation_score
        context["automation_indicators"] = automation_indicators
        
        # Log high automation scores
        if automation_score >= 3:
            log_security_event(
                event_type="webauthn_automated_request_detected",
                user_id=context["user_id"],
                ip_address=self._get_client_ip(request),
                success=False,
                details={
                    "automation_score": automation_score,
                    "indicators": automation_indicators,
                    "user_agent": user_agent[:100],
                    "operation_type": context["operation_type"]
                }
            )


# Global instance for use across WebAuthn endpoints
webauthn_security_validator = WebAuthnSecurityValidator()
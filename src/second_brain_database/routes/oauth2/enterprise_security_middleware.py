"""
Enterprise security middleware integration for OAuth2 browser flows.

This module integrates all enterprise-grade security components into a
comprehensive middleware system for OAuth2 browser authentication flows.

Features:
- Integrated CSRF protection with token rotation
- Session security with fingerprinting and anomaly detection
- Enhanced rate limiting with progressive delays
- Comprehensive input validation and sanitization
- Security headers for browser responses
- Security monitoring and alerting
- Authentication method isolation
- Comprehensive audit logging
"""

import time
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from fastapi import HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse

from second_brain_database.config import settings
from second_brain_database.managers.logging_manager import get_logger

# Import security components
from .csrf_middleware import csrf_middleware
from .session_security import session_security
from .enhanced_rate_limiting import enhanced_rate_limiter
from .input_validation import input_validator
from .security_headers import security_headers
from .security_monitoring import security_monitor, SecurityEventType
from .browser_error_logger import browser_error_logger

logger = get_logger(prefix="[Enterprise Security Middleware]")


class EnterpriseSecurityMiddleware:
    """
    Comprehensive enterprise security middleware for OAuth2 browser flows.
    
    Integrates all security components into a unified middleware system
    that provides comprehensive protection against various security threats.
    """
    
    def __init__(self):
        """Initialize the enterprise security middleware."""
        self.logger = logger
        
        # Security component statistics
        self.stats = {
            "requests_processed": 0,
            "security_checks_passed": 0,
            "security_violations_blocked": 0,
            "csrf_tokens_generated": 0,
            "session_anomalies_detected": 0,
            "rate_limits_applied": 0,
            "input_validations_performed": 0
        }
        
        # OAuth2 browser endpoints that require full security
        self.protected_endpoints = {
            "/oauth2/authorize",
            "/oauth2/consent",
            "/oauth2/token",
            "/auth/login",
            "/auth/logout"
        }
        
        # Endpoints that require CSRF protection
        self.csrf_protected_endpoints = {
            "/oauth2/authorize",
            "/oauth2/consent",
            "/auth/login"
        }
        
        # Initialize security components lazily
        self._initialized = False
    
    async def __call__(self, request: Request, call_next):
        """Process request through enterprise security middleware."""
        start_time = time.time()
        
        try:
            # Initialize security components if needed
            if not self._initialized:
                await self._initialize_security_components()
                self._initialized = True
            
            # Update statistics
            self.stats["requests_processed"] += 1
            
            # Determine if this is a protected OAuth2 browser endpoint
            is_protected = self._is_protected_endpoint(request.url.path)
            is_browser_request = self._is_browser_request(request)
            
            if is_protected and is_browser_request:
                # Apply comprehensive security checks
                await self._apply_security_checks(request)
            
            # Process the request
            response = await call_next(request)
            
            # Apply security enhancements to response
            if is_protected and is_browser_request:
                await self._enhance_response_security(request, response)
            
            # Log successful processing
            self.logger.debug(
                "Enterprise security middleware processed request successfully",
                extra={
                    "request_path": request.url.path,
                    "is_protected": is_protected,
                    "is_browser_request": is_browser_request,
                    "processing_time_ms": (time.time() - start_time) * 1000,
                    "event_type": "security_middleware_success"
                }
            )
            
            self.stats["security_checks_passed"] += 1
            return response
            
        except HTTPException as e:
            # Security violation - log and re-raise
            self.stats["security_violations_blocked"] += 1
            
            await self._log_security_violation(request, e, start_time)
            raise
            
        except Exception as e:
            # Unexpected error - log and fail securely
            self.logger.error(
                "Unexpected error in enterprise security middleware: %s",
                e,
                exc_info=True,
                extra={
                    "request_path": request.url.path,
                    "processing_time_ms": (time.time() - start_time) * 1000
                }
            )
            
            # Fail securely for protected endpoints
            if is_protected and is_browser_request:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Security validation failed"
                )
            
            # For non-protected endpoints, continue processing
            return await call_next(request)
    
    async def _initialize_security_components(self) -> None:
        """Initialize security components that require async setup."""
        try:
            # Initialize security monitor threat intelligence
            await security_monitor._load_threat_intelligence()
        except Exception as e:
            self.logger.error("Error initializing security components: %s", e)
    
    async def _apply_security_checks(self, request: Request) -> None:
        """Apply comprehensive security checks to protected requests."""
        client_ip = self._get_client_ip(request)
        
        # 1. Enhanced Rate Limiting
        await self._apply_rate_limiting(request)
        
        # 2. Input Validation and Sanitization
        await self._apply_input_validation(request)
        
        # 3. CSRF Protection (for state-changing operations)
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            await self._apply_csrf_protection(request)
        
        # 4. Session Security Validation
        await self._apply_session_security(request)
        
        # 5. Security Monitoring
        await self._apply_security_monitoring(request)
    
    async def _apply_rate_limiting(self, request: Request) -> None:
        """Apply enhanced rate limiting."""
        try:
            endpoint = self._get_endpoint_identifier(request.url.path)
            
            # Extract OAuth2 context
            client_id = request.query_params.get("client_id")
            user_id = getattr(request.state, "user_id", None)
            
            # Check rate limits
            is_allowed = await enhanced_rate_limiter.check_rate_limit(
                request, endpoint, client_id, user_id
            )
            
            if not is_allowed:
                self.stats["rate_limits_applied"] += 1
                
                # Log rate limiting event
                await security_monitor.process_security_event(
                    request,
                    SecurityEventType.RATE_LIMIT_VIOLATION,
                    f"Rate limit exceeded for endpoint {endpoint}",
                    client_id=client_id,
                    user_id=user_id
                )
                
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded"
                )
                
        except HTTPException:
            raise
        except Exception as e:
            self.logger.error("Error in rate limiting: %s", e)
            # Continue processing for non-critical errors
    
    async def _apply_input_validation(self, request: Request) -> None:
        """Apply comprehensive input validation."""
        try:
            self.stats["input_validations_performed"] += 1
            
            # Validate OAuth2 authorization requests
            if "/oauth2/authorize" in request.url.path:
                await self._validate_authorization_request(request)
            
            # Validate OAuth2 token requests
            elif "/oauth2/token" in request.url.path:
                await self._validate_token_request(request)
            
            # Validate other form inputs
            elif request.method == "POST":
                await self._validate_form_inputs(request)
                
        except Exception as e:
            # Log validation failure
            await security_monitor.process_security_event(
                request,
                SecurityEventType.INVALID_PARAMETERS,
                f"Input validation failed: {str(e)}",
                additional_details={"validation_error": str(e)}
            )
            raise
    
    async def _apply_csrf_protection(self, request: Request) -> None:
        """Apply CSRF protection for state-changing operations."""
        try:
            if request.url.path in self.csrf_protected_endpoints:
                # Validate CSRF token
                is_valid = await csrf_middleware.validate_csrf_token(request, require_token=True)
                
                if not is_valid:
                    self.stats["security_violations_blocked"] += 1
                    
                    # Log CSRF violation
                    await security_monitor.process_security_event(
                        request,
                        SecurityEventType.CSRF_ATTACK,
                        "CSRF token validation failed",
                        additional_details={"endpoint": request.url.path}
                    )
                    
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="CSRF token validation failed"
                    )
                    
        except HTTPException:
            raise
        except Exception as e:
            self.logger.error("Error in CSRF protection: %s", e)
            # Fail securely for CSRF errors
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF validation error"
            )
    
    async def _apply_session_security(self, request: Request) -> None:
        """Apply session security validation."""
        try:
            # Get session information
            session_id = request.cookies.get("session_id")
            user_id = getattr(request.state, "user_id", None)
            
            if session_id:
                # Validate session security
                is_valid, anomalies = await session_security.validate_session_security(
                    request, session_id, user_id
                )
                
                if not is_valid:
                    self.stats["session_anomalies_detected"] += 1
                    
                    # Log session security violation
                    await security_monitor.process_security_event(
                        request,
                        SecurityEventType.SESSION_HIJACKING,
                        f"Session security validation failed: {len(anomalies)} anomalies detected",
                        user_id=user_id,
                        session_id=session_id,
                        additional_details={"anomaly_count": len(anomalies)}
                    )
                    
                    # For high-risk anomalies, invalidate session
                    high_risk_anomalies = [a for a in anomalies if a.severity in ["high", "critical"]]
                    if high_risk_anomalies:
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Session security violation detected"
                        )
                        
        except HTTPException:
            raise
        except Exception as e:
            self.logger.error("Error in session security validation: %s", e)
            # Continue processing for non-critical session errors
    
    async def _apply_security_monitoring(self, request: Request) -> None:
        """Apply security monitoring and threat detection."""
        try:
            # Monitor for suspicious patterns
            user_agent = request.headers.get("user-agent", "")
            
            # Check for suspicious user agents
            suspicious_patterns = ["bot", "crawler", "scanner", "sqlmap", "nikto"]
            if any(pattern in user_agent.lower() for pattern in suspicious_patterns):
                await security_monitor.process_security_event(
                    request,
                    SecurityEventType.SUSPICIOUS_USER_AGENT,
                    f"Suspicious user agent detected: {user_agent[:100]}",
                    additional_details={"user_agent": user_agent}
                )
            
            # Monitor for parameter manipulation attempts
            query_params = dict(request.query_params)
            for param, value in query_params.items():
                if isinstance(value, str) and len(value) > 1000:
                    await security_monitor.process_security_event(
                        request,
                        SecurityEventType.INVALID_PARAMETERS,
                        f"Unusually long parameter detected: {param}",
                        additional_details={"parameter": param, "length": len(value)}
                    )
                    
        except Exception as e:
            self.logger.error("Error in security monitoring: %s", e)
            # Continue processing - monitoring errors shouldn't block requests
    
    async def _enhance_response_security(self, request: Request, response: Response) -> None:
        """Enhance response with security features."""
        try:
            # Apply security headers
            is_html_response = (
                isinstance(response, HTMLResponse) or
                response.headers.get("content-type", "").startswith("text/html")
            )
            
            security_headers.apply_security_headers(request, response, is_html_response)
            
            # Generate CSRF token for HTML responses that need it
            if (is_html_response and 
                request.url.path in self.csrf_protected_endpoints and
                request.method == "GET"):
                
                session_id = request.cookies.get("session_id")
                user_id = getattr(request.state, "user_id", None)
                
                csrf_token = await csrf_middleware.generate_csrf_token(
                    request, response, session_id, user_id
                )
                
                self.stats["csrf_tokens_generated"] += 1
                
        except Exception as e:
            self.logger.error("Error enhancing response security: %s", e)
            # Continue - response enhancement errors shouldn't block responses
    
    # Validation helper methods
    
    async def _validate_authorization_request(self, request: Request) -> None:
        """Validate OAuth2 authorization request parameters."""
        query_params = dict(request.query_params)
        
        required_params = ["client_id", "response_type", "redirect_uri"]
        for param in required_params:
            if param not in query_params:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Missing required parameter: {param}"
                )
        
        # Validate using input validator
        await input_validator.validate_authorization_request(
            request,
            client_id=query_params["client_id"],
            response_type=query_params["response_type"],
            redirect_uri=query_params["redirect_uri"],
            scope=query_params.get("scope"),
            state=query_params.get("state"),
            code_challenge=query_params.get("code_challenge"),
            code_challenge_method=query_params.get("code_challenge_method")
        )
    
    async def _validate_token_request(self, request: Request) -> None:
        """Validate OAuth2 token request parameters."""
        if request.method != "POST":
            return
        
        try:
            form_data = await request.form()
            form_dict = dict(form_data)
            
            if "grant_type" not in form_dict:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Missing required parameter: grant_type"
                )
            
            # Validate using input validator
            await input_validator.validate_token_request(
                request,
                grant_type=form_dict["grant_type"],
                client_id=form_dict.get("client_id", ""),
                client_secret=form_dict.get("client_secret"),
                code=form_dict.get("code"),
                redirect_uri=form_dict.get("redirect_uri"),
                code_verifier=form_dict.get("code_verifier"),
                refresh_token=form_dict.get("refresh_token"),
                scope=form_dict.get("scope")
            )
            
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Token request validation failed: {str(e)}"
            )
    
    async def _validate_form_inputs(self, request: Request) -> None:
        """Validate general form inputs for XSS and injection attacks."""
        try:
            form_data = await request.form()
            
            for field, value in form_data.items():
                if isinstance(value, str):
                    # Sanitize input
                    sanitized_value = input_validator.sanitize_html_input(value)
                    
                    # Check for significant changes (potential attack)
                    if len(sanitized_value) < len(value) * 0.8:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Invalid input detected in field: {field}"
                        )
                        
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            # Continue processing for form validation errors
    
    # Helper methods
    
    def _is_protected_endpoint(self, path: str) -> bool:
        """Check if endpoint requires full security protection."""
        return any(protected in path for protected in self.protected_endpoints)
    
    def _is_browser_request(self, request: Request) -> bool:
        """Check if request is from a browser."""
        accept_header = request.headers.get("accept", "")
        user_agent = request.headers.get("user-agent", "")
        
        # Check for browser-like Accept header
        is_browser_accept = "text/html" in accept_header
        
        # Check for browser-like User-Agent
        browser_indicators = ["mozilla", "chrome", "safari", "firefox", "edge"]
        is_browser_ua = any(indicator in user_agent.lower() for indicator in browser_indicators)
        
        return is_browser_accept or is_browser_ua
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()
        
        return getattr(request.client, "host", "unknown")
    
    def _get_endpoint_identifier(self, path: str) -> str:
        """Get endpoint identifier for rate limiting."""
        if "/oauth2/authorize" in path:
            return "authorization"
        elif "/oauth2/token" in path:
            return "token"
        elif "/oauth2/consent" in path:
            return "consent"
        elif "/auth/login" in path:
            return "login"
        else:
            return "global"
    
    async def _log_security_violation(
        self,
        request: Request,
        exception: HTTPException,
        start_time: float
    ) -> None:
        """Log security violation with comprehensive context."""
        self.logger.warning(
            "Security violation blocked: %s",
            exception.detail,
            extra={
                "status_code": exception.status_code,
                "detail": exception.detail,
                "request_path": request.url.path,
                "request_method": request.method,
                "client_ip": self._get_client_ip(request),
                "user_agent": request.headers.get("user-agent", ""),
                "processing_time_ms": (time.time() - start_time) * 1000,
                "event_type": "security_violation_blocked"
            }
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get enterprise security middleware statistics."""
        return {
            **self.stats,
            "security_success_rate": (
                self.stats["security_checks_passed"] / 
                max(1, self.stats["requests_processed"])
            ),
            "violation_block_rate": (
                self.stats["security_violations_blocked"] / 
                max(1, self.stats["requests_processed"])
            )
        }


# Global enterprise security middleware instance
enterprise_security_middleware = EnterpriseSecurityMiddleware()
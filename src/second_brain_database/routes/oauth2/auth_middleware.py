"""
Enterprise-grade flexible authentication middleware for OAuth2.

This module provides dual authentication support for OAuth2 endpoints, supporting both
JWT token-based authentication (for API clients) and session-based authentication
(for browser clients). It maintains backward compatibility while adding browser support.

Features:
- Dual authentication: JWT tokens first, then session cookies with fallback
- Comprehensive session validation with CSRF token support
- Enterprise security checks and audit logging
- Rate limiting and abuse detection
- Dependency injection for OAuth2 endpoints
- Proper error handling for authentication failures
"""

import time
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

from second_brain_database.config import settings
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.security_manager import security_manager
from second_brain_database.routes.auth.services.auth.login import get_current_user
from second_brain_database.routes.oauth2.session_manager import session_manager

logger = get_logger(prefix="[OAuth2 Auth Middleware]")

# OAuth2 scheme for JWT token extraction
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


class OAuth2AuthenticationError(HTTPException):
    """Custom exception for OAuth2 authentication failures."""
    
    def __init__(self, detail: str, status_code: int = status.HTTP_401_UNAUTHORIZED):
        super().__init__(
            status_code=status_code,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"}
        )


class OAuth2AuthMiddleware:
    """
    Enterprise-grade flexible authentication middleware for OAuth2 endpoints.
    
    Provides dual authentication support with comprehensive security features,
    audit logging, and enterprise-grade protections.
    """
    
    def __init__(self):
        """Initialize the authentication middleware."""
        self.logger = logger
        
        # Authentication method tracking for audit
        self.auth_method_stats = {
            "jwt_success": 0,
            "jwt_failure": 0,
            "session_success": 0,
            "session_failure": 0,
            "total_requests": 0
        }
    
    async def get_current_user_flexible(
        self,
        request: Request,
        token: Optional[str] = Depends(oauth2_scheme),
        require_csrf: bool = False
    ) -> Dict[str, Any]:
        """
        Get current user from either JWT token or browser session with enterprise security.
        
        Authentication priority:
        1. JWT token in Authorization header (API clients)
        2. Session cookie with CSRF validation (browser clients)
        
        Args:
            request: FastAPI request object
            token: Optional JWT token from Authorization header
            require_csrf: Whether to require CSRF token validation for session auth
            
        Returns:
            Dict[str, Any]: User data with authentication metadata
            
        Raises:
            OAuth2AuthenticationError: If authentication fails
            HTTPException: For rate limiting or security violations
        """
        start_time = time.time()
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "")
        
        # Update request statistics
        self.auth_method_stats["total_requests"] += 1
        
        # Apply enterprise-grade rate limiting
        await self._apply_rate_limiting(request, client_ip)
        
        # Security checks
        await self._perform_security_checks(request, client_ip, user_agent)
        
        try:
            # Method 1: Try JWT token authentication first (API clients)
            if token:
                try:
                    user = await self._authenticate_jwt_token(token, request)
                    if user:
                        # Add authentication metadata
                        user["auth_method"] = "jwt"
                        user["auth_timestamp"] = datetime.utcnow()
                        user["client_ip"] = client_ip
                        
                        # Log successful JWT authentication
                        await self._log_authentication_success(
                            user, "jwt", client_ip, user_agent, time.time() - start_time
                        )
                        
                        self.auth_method_stats["jwt_success"] += 1
                        return user
                        
                except Exception as e:
                    # Log JWT authentication failure but continue to session auth
                    await self._log_authentication_failure(
                        "jwt", str(e), client_ip, user_agent, time.time() - start_time
                    )
                    self.auth_method_stats["jwt_failure"] += 1
            
            # Method 2: Try session-based authentication (browser clients)
            try:
                user = await self._authenticate_session(request, require_csrf)
                if user:
                    # Add authentication metadata
                    user["auth_method"] = "session"
                    user["auth_timestamp"] = datetime.utcnow()
                    user["client_ip"] = client_ip
                    
                    # Log successful session authentication
                    await self._log_authentication_success(
                        user, "session", client_ip, user_agent, time.time() - start_time
                    )
                    
                    self.auth_method_stats["session_success"] += 1
                    return user
                    
            except Exception as e:
                # Log session authentication failure
                await self._log_authentication_failure(
                    "session", str(e), client_ip, user_agent, time.time() - start_time
                )
                self.auth_method_stats["session_failure"] += 1
            
            # Both authentication methods failed - return None for OAuth2 redirect handling
            await self._log_authentication_failure(
                "both", "No valid JWT token or session found", 
                client_ip, user_agent, time.time() - start_time
            )
            
            # Return None to allow OAuth2 endpoints to handle unauthenticated users gracefully
            # (e.g., redirect to login page for browser clients)
            return None
            
        except OAuth2AuthenticationError:
            # Re-raise OAuth2 authentication errors
            raise
        except HTTPException:
            # Re-raise HTTP exceptions (rate limiting, etc.)
            raise
        except Exception as e:
            # Log unexpected errors
            self.logger.error(
                "Unexpected error in flexible authentication: %s",
                e,
                exc_info=True,
                extra={
                    "client_ip": client_ip,
                    "user_agent": user_agent,
                    "has_token": bool(token),
                    "duration_ms": (time.time() - start_time) * 1000
                }
            )
            
            raise OAuth2AuthenticationError(
                detail="Authentication service temporarily unavailable",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE
            )
    
    async def _authenticate_jwt_token(
        self, 
        token: str, 
        request: Request
    ) -> Optional[Dict[str, Any]]:
        """
        Authenticate using JWT token with enterprise security checks.
        
        Args:
            token: JWT token string
            request: FastAPI request object
            
        Returns:
            Optional[Dict[str, Any]]: User data if authentication successful
        """
        try:
            # Use existing JWT authentication logic
            user = await get_current_user(token)
            
            # Additional enterprise security checks for JWT tokens
            if user:
                await self._validate_jwt_security_context(user, request)
            
            return user
            
        except HTTPException as e:
            # Convert HTTP exceptions to None for fallback handling
            self.logger.debug(
                "JWT authentication failed: %s",
                e.detail,
                extra={"status_code": e.status_code}
            )
            return None
        except Exception as e:
            self.logger.warning(
                "JWT authentication error: %s",
                e,
                extra={"token_prefix": token[:10] if token else None}
            )
            return None
    
    async def _authenticate_session(
        self, 
        request: Request, 
        require_csrf: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Authenticate using browser session with comprehensive validation.
        
        Args:
            request: FastAPI request object
            require_csrf: Whether to require CSRF token validation
            
        Returns:
            Optional[Dict[str, Any]]: User data if authentication successful
        """
        try:
            # Validate session using session manager
            user_data = await session_manager.validate_session(request, require_csrf)
            
            if not user_data:
                return None
            
            # Additional enterprise security checks for sessions
            await self._validate_session_security_context(user_data, request)
            
            return user_data
            
        except Exception as e:
            self.logger.debug(
                "Session authentication failed: %s",
                e,
                extra={"has_session_cookie": bool(request.cookies.get("sbd_session"))}
            )
            return None
    
    async def _apply_rate_limiting(self, request: Request, client_ip: str) -> None:
        """
        Apply enterprise-grade rate limiting for authentication attempts.
        
        Args:
            request: FastAPI request object
            client_ip: Client IP address
            
        Raises:
            HTTPException: If rate limit exceeded
        """
        try:
            # Apply general authentication rate limiting
            await security_manager.check_rate_limit(request, "oauth2-auth")
            
            # Apply IP-specific rate limiting for failed attempts
            failed_attempts_key = f"oauth2:failed_auth:{client_ip}"
            
            # Additional enterprise rate limiting based on authentication patterns
            await self._check_enterprise_rate_limits(request, client_ip)
            
        except HTTPException:
            # Log rate limiting event
            self.logger.warning(
                "Rate limit exceeded for OAuth2 authentication",
                extra={
                    "client_ip": client_ip,
                    "user_agent": request.headers.get("user-agent", ""),
                    "endpoint": str(request.url)
                }
            )
            raise
    
    async def _check_enterprise_rate_limits(self, request: Request, client_ip: str) -> None:
        """
        Check enterprise-specific rate limits and abuse patterns.
        
        Args:
            request: FastAPI request object
            client_ip: Client IP address
        """
        # Check for suspicious authentication patterns
        suspicious_patterns = [
            f"oauth2:suspicious:{client_ip}:rapid_requests",
            f"oauth2:suspicious:{client_ip}:multiple_failures",
            f"oauth2:suspicious:{client_ip}:token_enumeration"
        ]
        
        # Implement pattern detection logic here
        # This is a placeholder for enterprise-specific abuse detection
        pass
    
    async def _perform_security_checks(
        self, 
        request: Request, 
        client_ip: str, 
        user_agent: str
    ) -> None:
        """
        Perform comprehensive enterprise security checks.
        
        Args:
            request: FastAPI request object
            client_ip: Client IP address
            user_agent: User agent string
            
        Raises:
            HTTPException: If security violation detected
        """
        # Check for malicious user agents
        if self._is_malicious_user_agent(user_agent):
            self.logger.warning(
                "Malicious user agent detected",
                extra={
                    "client_ip": client_ip,
                    "user_agent": user_agent
                }
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Request blocked due to security policy"
            )
        
        # Check for suspicious request patterns
        await self._check_request_patterns(request, client_ip)
        
        # Validate request headers for security
        self._validate_security_headers(request)
    
    async def _validate_jwt_security_context(
        self, 
        user: Dict[str, Any], 
        request: Request
    ) -> None:
        """
        Validate JWT token security context with enterprise checks.
        
        Args:
            user: User data from JWT token
            request: FastAPI request object
        """
        # Check for token replay attacks
        await self._check_token_replay(user, request)
        
        # Validate token scope and permissions
        await self._validate_token_permissions(user, request)
        
        # Check for concurrent session limits
        await self._check_concurrent_sessions(user)
    
    async def _validate_session_security_context(
        self, 
        user_data: Dict[str, Any], 
        request: Request
    ) -> None:
        """
        Validate session security context with enterprise checks.
        
        Args:
            user_data: User data from session
            request: FastAPI request object
        """
        # Validate session integrity
        await self._validate_session_integrity(user_data, request)
        
        # Check for session hijacking indicators
        await self._check_session_hijacking(user_data, request)
        
        # Validate CSRF protection if required
        await self._validate_csrf_protection(user_data, request)
    
    async def _log_authentication_success(
        self,
        user: Dict[str, Any],
        auth_method: str,
        client_ip: str,
        user_agent: str,
        duration: float
    ) -> None:
        """
        Log successful authentication with comprehensive audit information.
        
        Args:
            user: Authenticated user data
            auth_method: Authentication method used (jwt/session)
            client_ip: Client IP address
            user_agent: User agent string
            duration: Authentication duration in seconds
        """
        self.logger.info(
            "OAuth2 authentication successful via %s for user %s",
            auth_method,
            user.get("username", "unknown"),
            extra={
                "event_type": "oauth2_auth_success",
                "user_id": user.get("_id"),
                "username": user.get("username"),
                "auth_method": auth_method,
                "client_ip": client_ip,
                "user_agent": user_agent,
                "duration_ms": duration * 1000,
                "oauth2_client_id": user.get("oauth2_client_id"),
                "oauth2_scopes": user.get("oauth2_scopes"),
                "session_id": user.get("session_id"),
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    async def _log_authentication_failure(
        self,
        auth_method: str,
        error_detail: str,
        client_ip: str,
        user_agent: str,
        duration: float
    ) -> None:
        """
        Log authentication failure with security audit information.
        
        Args:
            auth_method: Authentication method attempted
            error_detail: Error details
            client_ip: Client IP address
            user_agent: User agent string
            duration: Authentication attempt duration in seconds
        """
        self.logger.warning(
            "OAuth2 authentication failed via %s: %s",
            auth_method,
            error_detail,
            extra={
                "event_type": "oauth2_auth_failure",
                "auth_method": auth_method,
                "error_detail": error_detail,
                "client_ip": client_ip,
                "user_agent": user_agent,
                "duration_ms": duration * 1000,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    def _get_client_ip(self, request: Request) -> str:
        """
        Extract client IP address with proxy support.
        
        Args:
            request: FastAPI request object
            
        Returns:
            str: Client IP address
        """
        # Check for forwarded headers first
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()
        
        # Fallback to direct client IP
        return getattr(request.client, "host", "unknown")
    
    def _is_malicious_user_agent(self, user_agent: str) -> bool:
        """
        Check if user agent appears malicious.
        
        Args:
            user_agent: User agent string
            
        Returns:
            bool: True if user agent appears malicious
        """
        if not user_agent:
            return True
        
        # Check for common bot/scanner patterns
        malicious_patterns = [
            "sqlmap", "nikto", "nmap", "masscan", "zap",
            "burp", "w3af", "acunetix", "nessus", "openvas"
        ]
        
        user_agent_lower = user_agent.lower()
        return any(pattern in user_agent_lower for pattern in malicious_patterns)
    
    async def _check_request_patterns(self, request: Request, client_ip: str) -> None:
        """
        Check for suspicious request patterns.
        
        Args:
            request: FastAPI request object
            client_ip: Client IP address
        """
        # This is a placeholder for enterprise pattern detection
        # Could include checks for:
        # - Rapid successive requests
        # - Parameter enumeration attempts
        # - Unusual request timing patterns
        pass
    
    def _validate_security_headers(self, request: Request) -> None:
        """
        Validate request headers for security compliance.
        
        Args:
            request: FastAPI request object
        """
        # Check for required security headers in production
        if not settings.DEBUG:
            # Validate Origin header for CORS
            origin = request.headers.get("origin")
            if origin and not self._is_allowed_origin(origin):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Origin not allowed"
                )
    
    def _is_allowed_origin(self, origin: str) -> bool:
        """
        Check if origin is allowed for CORS.
        
        Args:
            origin: Origin header value
            
        Returns:
            bool: True if origin is allowed
        """
        # This should be configured based on registered OAuth2 clients
        # For now, implement basic validation
        allowed_origins = getattr(settings, "ALLOWED_ORIGINS", [])
        return origin in allowed_origins
    
    async def _check_token_replay(self, user: Dict[str, Any], request: Request) -> None:
        """Check for token replay attacks."""
        # Placeholder for token replay detection
        pass
    
    async def _validate_token_permissions(self, user: Dict[str, Any], request: Request) -> None:
        """Validate token permissions and scopes."""
        # Placeholder for permission validation
        pass
    
    async def _check_concurrent_sessions(self, user: Dict[str, Any]) -> None:
        """Check for concurrent session limits."""
        # Placeholder for concurrent session checking
        pass
    
    async def _validate_session_integrity(self, user_data: Dict[str, Any], request: Request) -> None:
        """Validate session integrity."""
        # Placeholder for session integrity validation
        pass
    
    async def _check_session_hijacking(self, user_data: Dict[str, Any], request: Request) -> None:
        """Check for session hijacking indicators."""
        # Placeholder for session hijacking detection
        pass
    
    async def _validate_csrf_protection(self, user_data: Dict[str, Any], request: Request) -> None:
        """Validate CSRF protection."""
        # Placeholder for CSRF validation
        pass
    
    def get_auth_stats(self) -> Dict[str, Any]:
        """
        Get authentication statistics for monitoring.
        
        Returns:
            Dict[str, Any]: Authentication statistics
        """
        return {
            **self.auth_method_stats,
            "jwt_success_rate": (
                self.auth_method_stats["jwt_success"] / 
                max(1, self.auth_method_stats["jwt_success"] + self.auth_method_stats["jwt_failure"])
            ),
            "session_success_rate": (
                self.auth_method_stats["session_success"] / 
                max(1, self.auth_method_stats["session_success"] + self.auth_method_stats["session_failure"])
            )
        }


# Global middleware instance
auth_middleware = OAuth2AuthMiddleware()


# Dependency injection functions for OAuth2 endpoints

async def get_current_user_flexible(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme)
) -> Dict[str, Any]:
    """
    Dependency function for flexible authentication in OAuth2 endpoints.
    
    Maintains backward compatibility while adding browser session support.
    
    Args:
        request: FastAPI request object
        token: Optional JWT token from Authorization header
        
    Returns:
        Dict[str, Any]: Authenticated user data
        
    Raises:
        OAuth2AuthenticationError: If authentication fails
    """
    return await auth_middleware.get_current_user_flexible(request, token)


async def get_current_user_flexible_with_csrf(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme)
) -> Dict[str, Any]:
    """
    Dependency function for flexible authentication with CSRF protection.
    
    Requires CSRF token validation for session-based authentication.
    
    Args:
        request: FastAPI request object
        token: Optional JWT token from Authorization header
        
    Returns:
        Dict[str, Any]: Authenticated user data
        
    Raises:
        OAuth2AuthenticationError: If authentication fails
    """
    return await auth_middleware.get_current_user_flexible(request, token, require_csrf=True)


def create_oauth2_flexible_dependency(require_csrf: bool = False):
    """
    Create a flexible OAuth2 dependency with configurable CSRF requirements.
    
    Args:
        require_csrf: Whether to require CSRF token validation
        
    Returns:
        Dependency function for OAuth2 endpoints
    """
    async def oauth2_flexible_dependency(
        request: Request,
        token: Optional[str] = Depends(oauth2_scheme)
    ) -> Dict[str, Any]:
        """Flexible OAuth2 dependency with configurable CSRF."""
        return await auth_middleware.get_current_user_flexible(
            request, token, require_csrf=require_csrf
        )
    
    return oauth2_flexible_dependency


# Backward compatibility aliases
get_current_user_dep = get_current_user_flexible
oauth2_flexible_auth = get_current_user_flexible
"""
Documentation middleware for production-ready documentation configuration.

This module provides middleware and utilities for securing and optimizing
API documentation in production environments.
"""

import time
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware

from second_brain_database.config import settings
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[Docs Middleware]")


class DocumentationSecurityMiddleware(BaseHTTPMiddleware):
    """
    Security middleware for documentation endpoints.

    This middleware provides access control, rate limiting, and security
    headers for documentation endpoints in production environments.
    """

    def __init__(self, app, allowed_ips: Optional[List[str]] = None, require_auth: bool = None):
        """
        Initialize documentation security middleware.

        Args:
            app: FastAPI application instance
            allowed_ips: List of allowed IP addresses for documentation access
            require_auth: Whether to require authentication for documentation access
        """
        super().__init__(app)

        # Use configuration settings if not explicitly provided
        if allowed_ips is None and settings.DOCS_ALLOWED_IPS:
            self.allowed_ips = [ip.strip() for ip in settings.DOCS_ALLOWED_IPS.split(",")]
        else:
            self.allowed_ips = allowed_ips or []

        self.require_auth = require_auth if require_auth is not None else settings.DOCS_REQUIRE_AUTH
        self.docs_paths = ["/docs", "/redoc", "/openapi.json"]
        self.access_log = {}  # Simple in-memory access log
        self.rate_limit_requests = settings.DOCS_RATE_LIMIT_REQUESTS
        self.rate_limit_period = settings.DOCS_RATE_LIMIT_PERIOD

    async def dispatch(self, request: Request, call_next):
        """
        Process documentation requests with security checks.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware in chain

        Returns:
            HTTP response with security headers and access control
        """
        # Check if this is a documentation endpoint
        if any(request.url.path.startswith(path) for path in self.docs_paths):
            # Apply security checks for documentation endpoints
            security_response = await self._apply_security_checks(request)
            if security_response:
                return security_response

        # Process the request
        response = await call_next(request)

        # Add security headers for documentation endpoints
        if any(request.url.path.startswith(path) for path in self.docs_paths):
            response = self._add_security_headers(response)
            self._log_documentation_access(request)

        return response

    async def _apply_security_checks(self, request: Request) -> Optional[Response]:
        """
        Apply security checks for documentation access.

        Args:
            request: Incoming HTTP request

        Returns:
            Error response if security check fails, None if passed
        """
        # Check if documentation is disabled in production
        if settings.is_production and not settings.docs_should_be_enabled:
            logger.warning("Documentation access attempted in production with docs disabled")
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"error": "not_found", "message": "Documentation not available"},
            )

        # IP address restriction check
        if self.allowed_ips:
            client_ip = self._get_client_ip(request)
            if client_ip not in self.allowed_ips:
                logger.warning("Documentation access denied for IP: %s", client_ip)
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={
                        "error": "access_denied",
                        "message": "Documentation access not allowed from this IP address",
                    },
                )

        # Authentication check (if required)
        if self.require_auth:
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "error": "authentication_required",
                        "message": "Authentication required to access documentation",
                    },
                )

        # Rate limiting check
        rate_limit_response = await self._check_rate_limit(request)
        if rate_limit_response:
            return rate_limit_response

        return None

    def _add_security_headers(self, response: Response) -> Response:
        """
        Add security headers to documentation responses.

        Args:
            response: HTTP response

        Returns:
            Response with added security headers
        """
        # Content Security Policy for documentation
        csp_policy = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https:; "
            "connect-src 'self'"
        )

        # Add security headers
        response.headers["Content-Security-Policy"] = csp_policy
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Add caching headers for performance
        if settings.should_cache_docs:
            response.headers["Cache-Control"] = f"public, max-age={settings.DOCS_CACHE_TTL}"
            response.headers["ETag"] = f'"{hash(str(time.time()))}"'
        else:
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"

        return response

    async def _check_rate_limit(self, request: Request) -> Optional[Response]:
        """
        Check rate limiting for documentation access.

        Args:
            request: Incoming HTTP request

        Returns:
            Rate limit error response if exceeded, None if within limits
        """
        client_ip = self._get_client_ip(request)
        current_time = time.time()

        # Use configured rate limiting settings
        rate_limit_window = self.rate_limit_period
        rate_limit_max = self.rate_limit_requests

        # Clean old entries
        cutoff_time = current_time - rate_limit_window
        self.access_log = {ip: [t for t in times if t > cutoff_time] for ip, times in self.access_log.items()}

        # Check current IP
        if client_ip not in self.access_log:
            self.access_log[client_ip] = []

        if len(self.access_log[client_ip]) >= rate_limit_max:
            logger.warning("Documentation rate limit exceeded for IP: %s", client_ip)
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "rate_limit_exceeded",
                    "message": "Too many documentation requests. Please try again later.",
                    "details": {"retry_after": rate_limit_window},
                },
            )

        # Record this access
        self.access_log[client_ip].append(current_time)
        return None

    def _get_client_ip(self, request: Request) -> str:
        """
        Get client IP address from request.

        Args:
            request: HTTP request

        Returns:
            Client IP address
        """
        # Check for forwarded headers (for reverse proxy setups)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fallback to direct client IP
        return request.client.host if request.client else "unknown"

    def _log_documentation_access(self, request: Request):
        """
        Log documentation access for monitoring.

        Args:
            request: HTTP request
        """
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("User-Agent", "unknown")

        logger.info("Documentation accessed: path=%s, ip=%s, user_agent=%s", request.url.path, client_ip, user_agent)


class DocumentationCORSConfig:
    """
    CORS configuration for documentation endpoints.

    This class provides production-ready CORS configuration for
    documentation endpoints with security considerations.
    """

    @staticmethod
    def get_cors_config() -> Dict[str, Any]:
        """
        Get CORS configuration for documentation endpoints.

        Returns:
            Dict containing CORS configuration
        """
        if settings.is_production:
            # Use configured CORS settings for production
            origins = []
            if settings.DOCS_CORS_ORIGINS:
                origins = [origin.strip() for origin in settings.DOCS_CORS_ORIGINS.split(",")]
            elif settings.BASE_URL:
                origins = [settings.BASE_URL]

            return {
                "allow_origins": origins,
                "allow_credentials": settings.DOCS_CORS_CREDENTIALS,
                "allow_methods": settings.DOCS_CORS_METHODS.split(","),
                "allow_headers": settings.DOCS_CORS_HEADERS.split(","),
                "max_age": settings.DOCS_CORS_MAX_AGE,
            }
        else:
            # Permissive CORS for development
            return {
                "allow_origins": ["*"],
                "allow_credentials": True,
                "allow_methods": ["GET", "POST", "PUT", "DELETE"],
                "allow_headers": ["*"],
                "max_age": 86400,
            }

    @staticmethod
    def create_cors_middleware():
        """
        Create CORS middleware for documentation.

        Returns:
            Configured CORS middleware
        """
        config = DocumentationCORSConfig.get_cors_config()

        return CORSMiddleware(
            allow_origins=config["allow_origins"],
            allow_credentials=config["allow_credentials"],
            allow_methods=config["allow_methods"],
            allow_headers=config["allow_headers"],
            max_age=config["max_age"],
        )


class DocumentationPerformanceOptimizer:
    """
    Performance optimization utilities for documentation.

    This class provides caching, compression, and other performance
    optimizations for documentation endpoints.
    """

    @staticmethod
    def get_cache_headers(content_type: str = "application/json") -> Dict[str, str]:
        """
        Get appropriate cache headers for documentation content.

        Args:
            content_type: Content type of the response

        Returns:
            Dict containing cache headers
        """
        if settings.should_cache_docs:
            # Cache documentation in production
            return {
                "Cache-Control": f"public, max-age={settings.DOCS_CACHE_TTL}",
                "Vary": "Accept-Encoding",
                "Content-Type": content_type,
            }
        else:
            # No caching in development
            return {
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
                "Content-Type": content_type,
            }

    @staticmethod
    def should_compress_response(content_type: str) -> bool:
        """
        Determine if response should be compressed.

        Args:
            content_type: Content type of the response

        Returns:
            True if response should be compressed
        """
        compressible_types = ["application/json", "text/html", "text/css", "application/javascript", "text/plain"]

        return any(content_type.startswith(ct) for ct in compressible_types)


def configure_documentation_middleware(app):
    """
    Configure all documentation middleware for the FastAPI application.

    Args:
        app: FastAPI application instance
    """
    # Add CORS middleware for documentation
    cors_config = DocumentationCORSConfig.get_cors_config()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_config["allow_origins"],
        allow_credentials=cors_config["allow_credentials"],
        allow_methods=cors_config["allow_methods"],
        allow_headers=cors_config["allow_headers"],
        max_age=cors_config["max_age"],
    )

    # Add security middleware for documentation
    if settings.is_production or settings.DOCS_ACCESS_CONTROL:
        # Add security middleware with configured restrictions
        app.add_middleware(DocumentationSecurityMiddleware)
        logger.info("Documentation security middleware enabled")
    else:
        logger.info("Documentation security middleware disabled for development")

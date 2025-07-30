"""
Enterprise security headers middleware for OAuth2 browser responses.

This module provides comprehensive security headers for browser-based OAuth2 flows,
including CSP, HSTS, X-Frame-Options, and other enterprise security headers.

Features:
- Content Security Policy (CSP) with strict directives
- HTTP Strict Transport Security (HSTS) for HTTPS enforcement
- X-Frame-Options for clickjacking protection
- X-Content-Type-Options for MIME type sniffing protection
- Referrer Policy for privacy protection
- Permissions Policy for feature control
- Cross-Origin policies for enhanced security
"""

import time
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse

from fastapi import Request, Response
from fastapi.responses import HTMLResponse

from second_brain_database.config import settings
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[Security Headers]")


class EnterpriseSecurityHeaders:
    """
    Enterprise-grade security headers middleware for OAuth2 browser responses.
    
    Provides comprehensive security headers to protect against various web
    security vulnerabilities and attacks in browser-based OAuth2 flows.
    """
    
    def __init__(self):
        """Initialize the security headers middleware."""
        self.logger = logger
        
        # Configure allowed sources for CSP
        self._configure_csp_sources()
        
        # Statistics for monitoring
        self.stats = {
            "headers_applied": 0,
            "csp_violations_reported": 0,
            "hsts_headers_set": 0,
            "frame_options_set": 0
        }
    
    def _configure_csp_sources(self) -> None:
        """Configure Content Security Policy sources based on environment."""
        # Base CSP sources
        self.csp_sources = {
            "default-src": ["'self'"],
            "script-src": [
                "'self'",
                "'unsafe-inline'",  # Required for inline scripts in templates
                "https://challenges.cloudflare.com",  # Turnstile
                "https://static.cloudflare.com"  # Turnstile
            ],
            "style-src": [
                "'self'",
                "'unsafe-inline'",  # Required for inline styles in templates
                "https://fonts.googleapis.com"
            ],
            "font-src": [
                "'self'",
                "https://fonts.gstatic.com",
                "data:"
            ],
            "img-src": [
                "'self'",
                "data:",
                "https:"  # Allow HTTPS images
            ],
            "connect-src": [
                "'self'",
                "https://challenges.cloudflare.com"  # Turnstile
            ],
            "frame-src": [
                "https://challenges.cloudflare.com"  # Turnstile
            ],
            "form-action": ["'self'"],
            "base-uri": ["'self'"],
            "object-src": ["'none'"],
            "media-src": ["'self'"],
            "worker-src": ["'self'"],
            "manifest-src": ["'self'"],
            "frame-ancestors": ["'none'"]  # Prevent framing
        }
        
        # Add development-specific sources
        if settings.DEBUG:
            # Allow localhost for development
            for directive in ["script-src", "style-src", "connect-src"]:
                if directive in self.csp_sources:
                    self.csp_sources[directive].extend([
                        "http://localhost:*",
                        "http://127.0.0.1:*",
                        "ws://localhost:*",
                        "ws://127.0.0.1:*"
                    ])
    
    def apply_security_headers(
        self,
        request: Request,
        response: Response,
        is_browser_response: bool = True
    ) -> None:
        """
        Apply comprehensive enterprise security headers to response.
        
        Args:
            request: FastAPI request object
            response: FastAPI response object
            is_browser_response: Whether this is a browser response (HTML)
        """
        start_time = time.time()
        
        try:
            # Apply headers based on response type
            if is_browser_response:
                self._apply_browser_security_headers(request, response)
            else:
                self._apply_api_security_headers(request, response)
            
            # Apply common security headers
            self._apply_common_security_headers(request, response)
            
            # Update statistics
            self.stats["headers_applied"] += 1
            
            # Log header application
            self.logger.debug(
                "Security headers applied successfully",
                extra={
                    "is_browser_response": is_browser_response,
                    "request_path": request.url.path,
                    "duration_ms": (time.time() - start_time) * 1000,
                    "event_type": "security_headers_applied"
                }
            )
            
        except Exception as e:
            self.logger.error(
                "Failed to apply security headers: %s",
                e,
                exc_info=True,
                extra={
                    "request_path": request.url.path,
                    "is_browser_response": is_browser_response
                }
            )
    
    def _apply_browser_security_headers(
        self,
        request: Request,
        response: Response
    ) -> None:
        """Apply security headers specific to browser responses."""
        # Content Security Policy
        csp_header = self._build_csp_header(request)
        response.headers["Content-Security-Policy"] = csp_header
        
        # CSP Report-Only for monitoring (in development)
        if settings.DEBUG:
            response.headers["Content-Security-Policy-Report-Only"] = csp_header
        
        # X-Frame-Options for clickjacking protection
        response.headers["X-Frame-Options"] = "DENY"
        self.stats["frame_options_set"] += 1
        
        # X-Content-Type-Options to prevent MIME sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # X-XSS-Protection (legacy but still useful)
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # Referrer Policy for privacy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Permissions Policy (Feature Policy)
        permissions_policy = self._build_permissions_policy()
        response.headers["Permissions-Policy"] = permissions_policy
        
        # Cross-Origin policies
        response.headers["Cross-Origin-Embedder-Policy"] = "require-corp"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    
    def _apply_api_security_headers(
        self,
        request: Request,
        response: Response
    ) -> None:
        """Apply security headers specific to API responses."""
        # X-Content-Type-Options
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # X-Frame-Options (still relevant for API responses)
        response.headers["X-Frame-Options"] = "DENY"
        
        # Referrer Policy
        response.headers["Referrer-Policy"] = "no-referrer"
        
        # Cross-Origin policies for API
        response.headers["Cross-Origin-Resource-Policy"] = "cross-origin"
    
    def _apply_common_security_headers(
        self,
        request: Request,
        response: Response
    ) -> None:
        """Apply security headers common to all responses."""
        # HTTP Strict Transport Security (HSTS)
        if not settings.DEBUG and request.url.scheme == "https":
            hsts_header = "max-age=31536000; includeSubDomains; preload"
            response.headers["Strict-Transport-Security"] = hsts_header
            self.stats["hsts_headers_set"] += 1
        
        # Server header removal/modification
        response.headers["Server"] = "SecondBrain/1.0"
        
        # Cache control for sensitive responses
        if self._is_sensitive_path(request.url.path):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        
        # Security-related custom headers
        response.headers["X-Security-Framework"] = "Enterprise-OAuth2"
        response.headers["X-Request-ID"] = getattr(request.state, "request_id", "unknown")
    
    def _build_csp_header(self, request: Request) -> str:
        """Build Content Security Policy header."""
        csp_directives = []
        
        for directive, sources in self.csp_sources.items():
            sources_str = " ".join(sources)
            csp_directives.append(f"{directive} {sources_str}")
        
        # Add report-uri for CSP violation reporting (if configured)
        if hasattr(settings, "CSP_REPORT_URI") and settings.CSP_REPORT_URI:
            csp_directives.append(f"report-uri {settings.CSP_REPORT_URI}")
        
        return "; ".join(csp_directives)
    
    def _build_permissions_policy(self) -> str:
        """Build Permissions Policy header."""
        # Define restrictive permissions policy
        permissions = {
            "accelerometer": "self",
            "ambient-light-sensor": "none",
            "autoplay": "none",
            "battery": "none",
            "camera": "none",
            "cross-origin-isolated": "self",
            "display-capture": "none",
            "document-domain": "none",
            "encrypted-media": "none",
            "execution-while-not-rendered": "none",
            "execution-while-out-of-viewport": "none",
            "fullscreen": "self",
            "geolocation": "none",
            "gyroscope": "none",
            "keyboard-map": "self",
            "magnetometer": "none",
            "microphone": "none",
            "midi": "none",
            "navigation-override": "none",
            "payment": "none",
            "picture-in-picture": "none",
            "publickey-credentials-get": "self",  # Allow WebAuthn
            "screen-wake-lock": "none",
            "sync-xhr": "none",
            "usb": "none",
            "web-share": "none",
            "xr-spatial-tracking": "none"
        }
        
        policy_directives = []
        for feature, allowlist in permissions.items():
            if allowlist == "none":
                policy_directives.append(f"{feature}=()")
            elif allowlist == "self":
                policy_directives.append(f"{feature}=(self)")
            else:
                policy_directives.append(f"{feature}=({allowlist})")
        
        return ", ".join(policy_directives)
    
    def _is_sensitive_path(self, path: str) -> bool:
        """Check if path contains sensitive information requiring strict caching."""
        sensitive_patterns = [
            "/oauth2/",
            "/auth/",
            "/api/",
            "/admin/",
            "/user/",
            "/profile/"
        ]
        
        return any(pattern in path for pattern in sensitive_patterns)
    
    def add_csp_source(self, directive: str, source: str) -> None:
        """Add a source to CSP directive."""
        if directive in self.csp_sources:
            if source not in self.csp_sources[directive]:
                self.csp_sources[directive].append(source)
                self.logger.info(
                    "Added CSP source: %s to %s",
                    source,
                    directive
                )
    
    def remove_csp_source(self, directive: str, source: str) -> None:
        """Remove a source from CSP directive."""
        if directive in self.csp_sources:
            if source in self.csp_sources[directive]:
                self.csp_sources[directive].remove(source)
                self.logger.info(
                    "Removed CSP source: %s from %s",
                    source,
                    directive
                )
    
    def report_csp_violation(self, violation_data: Dict[str, Any]) -> None:
        """Handle CSP violation reports."""
        self.stats["csp_violations_reported"] += 1
        
        self.logger.warning(
            "CSP violation reported",
            extra={
                "violation_data": violation_data,
                "event_type": "csp_violation"
            }
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get security headers statistics."""
        return {
            **self.stats,
            "csp_sources_count": sum(len(sources) for sources in self.csp_sources.values()),
            "csp_directives_count": len(self.csp_sources)
        }


class SecurityHeadersMiddleware:
    """
    FastAPI middleware for applying enterprise security headers.
    """
    
    def __init__(self):
        """Initialize the middleware."""
        self.security_headers = EnterpriseSecurityHeaders()
    
    async def __call__(self, request: Request, call_next):
        """Process request and apply security headers to response."""
        # Process the request
        response = await call_next(request)
        
        # Determine if this is a browser response
        is_browser_response = (
            isinstance(response, HTMLResponse) or
            response.headers.get("content-type", "").startswith("text/html")
        )
        
        # Apply security headers
        self.security_headers.apply_security_headers(
            request, response, is_browser_response
        )
        
        return response


# Global security headers instance
security_headers = EnterpriseSecurityHeaders()
security_headers_middleware = SecurityHeadersMiddleware()
"""
OAuth2 security middleware for enhanced protection.

This module provides middleware for OAuth2 endpoints to apply security headers,
input validation, rate limiting, and abuse detection automatically.
"""

from typing import Callable, Dict, Optional
import time

from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse

from second_brain_database.managers.logging_manager import get_logger
from .security_manager import oauth2_security_manager
from .error_handler import OAuth2ErrorCode, oauth2_error_handler

logger = get_logger(prefix="[OAuth2 Security Middleware]")


class OAuth2SecurityMiddleware:
    """
    Security middleware for OAuth2 endpoints.
    
    Provides automatic security enhancements including:
    - Security headers application
    - Input validation and sanitization
    - Rate limiting and abuse detection
    - Request/response logging
    """
    
    def __init__(self):
        self.security_manager = oauth2_security_manager
        logger.info("OAuth2SecurityMiddleware initialized")
    
    async def __call__(
        self,
        request: Request,
        call_next: Callable,
        endpoint_name: str,
        require_client_id: bool = True
    ) -> Response:
        """
        Process OAuth2 request with security enhancements.
        
        Args:
            request: FastAPI request object
            call_next: Next middleware/endpoint function
            endpoint_name: Name of the OAuth2 endpoint
            require_client_id: Whether client_id is required
            
        Returns:
            Response with security enhancements applied
        """
        start_time = time.time()
        client_id = None
        
        try:
            # Extract client_id for tracking
            if require_client_id:
                if request.method == "GET":
                    client_id = request.query_params.get("client_id")
                elif request.method == "POST":
                    # For POST requests, we need to read form data
                    form_data = await request.form()
                    client_id = form_data.get("client_id")
                
                if not client_id:
                    logger.warning(f"Missing client_id in {endpoint_name} request")
                    return oauth2_error_handler.token_error(
                        error_code=OAuth2ErrorCode.INVALID_REQUEST,
                        error_description="Missing client_id parameter",
                        request=request
                    )
            
            # Apply enhanced rate limiting
            if client_id:
                await self.security_manager.enhanced_rate_limiting(
                    request=request,
                    client_id=client_id,
                    endpoint=endpoint_name
                )
            
            # Validate and sanitize input parameters
            await self._validate_request_security(request, client_id, endpoint_name)
            
            # Process the request
            response = await call_next(request)
            
            # Apply security headers to response
            response = self.security_manager.apply_security_headers(response)
            
            # Log successful request
            processing_time = time.time() - start_time
            logger.info(
                f"OAuth2 {endpoint_name} request processed successfully",
                extra={
                    "client_id": client_id,
                    "processing_time": processing_time,
                    "status_code": response.status_code
                }
            )
            
            return response
            
        except HTTPException as e:
            # Log security-related HTTP exceptions
            processing_time = time.time() - start_time
            logger.warning(
                f"OAuth2 {endpoint_name} request failed: {e.detail}",
                extra={
                    "client_id": client_id,
                    "status_code": e.status_code,
                    "processing_time": processing_time,
                    "error_detail": e.detail
                }
            )
            
            # Apply security headers even to error responses
            if e.status_code == 429:  # Rate limit exceeded
                response = JSONResponse(
                    status_code=e.status_code,
                    content={"error": "rate_limit_exceeded", "error_description": e.detail}
                )
            else:
                response = JSONResponse(
                    status_code=e.status_code,
                    content={"error": "invalid_request", "error_description": e.detail}
                )
            
            response = self.security_manager.apply_security_headers(response)
            return response
            
        except Exception as e:
            # Log unexpected errors
            processing_time = time.time() - start_time
            logger.error(
                f"Unexpected error in OAuth2 {endpoint_name} middleware: {str(e)}",
                extra={
                    "client_id": client_id,
                    "processing_time": processing_time,
                    "exception_type": type(e).__name__
                },
                exc_info=True
            )
            
            # Return generic error response with security headers
            response = JSONResponse(
                status_code=500,
                content={"error": "server_error", "error_description": "Internal server error"}
            )
            response = self.security_manager.apply_security_headers(response)
            return response
    
    async def _validate_request_security(
        self,
        request: Request,
        client_id: Optional[str],
        endpoint_name: str
    ) -> None:
        """
        Validate request security parameters.
        
        Args:
            request: FastAPI request object
            client_id: OAuth2 client identifier
            endpoint_name: Name of the endpoint
            
        Raises:
            HTTPException: If security validation fails
        """
        # Check request size limits
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > 10240:  # 10KB limit
            await self.security_manager._log_security_violation(
                event_type="oversized_request",
                client_id=client_id,
                request=request,
                details={"content_length": content_length, "endpoint": endpoint_name}
            )
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Request too large"
            )
        
        # Check for suspicious headers
        suspicious_headers = ["x-forwarded-for", "x-real-ip", "x-originating-ip"]
        for header in suspicious_headers:
            if header in request.headers:
                header_value = request.headers[header]
                if len(header_value) > 100 or any(char in header_value for char in "<>\"'"):
                    await self.security_manager._log_security_violation(
                        event_type="suspicious_header",
                        client_id=client_id,
                        request=request,
                        details={"header": header, "value": header_value[:100]}
                    )
        
        # Validate User-Agent
        user_agent = request.headers.get("user-agent", "")
        if len(user_agent) > 500:
            await self.security_manager._log_security_violation(
                event_type="suspicious_user_agent",
                client_id=client_id,
                request=request,
                details={"user_agent_length": len(user_agent)}
            )
        
        # Check for common attack patterns in URL
        url_str = str(request.url)
        attack_patterns = ["../", "..\\", "<script", "javascript:", "data:", "vbscript:"]
        for pattern in attack_patterns:
            if pattern.lower() in url_str.lower():
                await self.security_manager._log_security_violation(
                    event_type="malicious_url_pattern",
                    client_id=client_id,
                    request=request,
                    details={"pattern": pattern, "url": url_str}
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid request format"
                )


def create_oauth2_security_middleware(
    endpoint_name: str,
    require_client_id: bool = True
) -> Callable:
    """
    Create OAuth2 security middleware for specific endpoint.
    
    Args:
        endpoint_name: Name of the OAuth2 endpoint
        require_client_id: Whether client_id is required
        
    Returns:
        Middleware function
    """
    middleware = OAuth2SecurityMiddleware()
    
    async def security_middleware(request: Request, call_next: Callable) -> Response:
        return await middleware(request, call_next, endpoint_name, require_client_id)
    
    return security_middleware


# Global middleware instance
oauth2_security_middleware = OAuth2SecurityMiddleware()
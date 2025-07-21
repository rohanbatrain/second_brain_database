"""
Logging enhancement utilities for production-ready logging.

This module provides comprehensive logging utilities including:
- Performance logging decorators for timing operations
- Database operation logging utilities with query and timing details
- Request context logging middleware for FastAPI
- Security event logging utilities with proper context

All utilities integrate with the existing logging_manager infrastructure.
"""

import asyncio
import functools
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Union
from contextvars import ContextVar

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from second_brain_database.managers.logging_manager import get_logger


# Context variables for request tracking
request_id_context: ContextVar[str] = ContextVar('request_id', default='')
user_id_context: ContextVar[str] = ContextVar('user_id', default='')
ip_address_context: ContextVar[str] = ContextVar('ip_address', default='')


@dataclass
class RequestContext:
    """Request context information for logging."""
    request_id: str
    method: str
    path: str
    user_id: Optional[str] = None
    ip_address: str = ""
    user_agent: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    query_params: Dict[str, Any] = field(default_factory=dict)
    path_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DatabaseContext:
    """Database operation context for logging."""
    operation: str
    collection: str
    query: Dict[str, Any]
    duration: float
    result_count: Optional[int] = None
    error: Optional[str] = None
    request_id: Optional[str] = None


@dataclass
class SecurityContext:
    """Security event context for logging."""
    event_type: str
    user_id: Optional[str] = None
    ip_address: str = ""
    success: bool = True
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    request_id: Optional[str] = None


class PerformanceLogger:
    """Performance logging utilities with timing and context."""
    
    def __init__(self, logger_name: str = "Second_Brain_Database", prefix: str = "[PERFORMANCE]"):
        self.logger = get_logger(name=logger_name, prefix=prefix)
    
    def log_operation(self, operation_name: str, duration: float, context: Optional[Dict[str, Any]] = None):
        """Log a performance operation with timing."""
        context_str = ""
        if context:
            context_items = [f"{k}={v}" for k, v in context.items()]
            context_str = f" ({', '.join(context_items)})"
        
        request_id = request_id_context.get('')
        request_prefix = f"[{request_id}] " if request_id else ""
        
        self.logger.info(f"{request_prefix}Operation '{operation_name}' completed in {duration:.3f}s{context_str}")
    
    def log_slow_operation(self, operation_name: str, duration: float, threshold: float = 1.0, 
                          context: Optional[Dict[str, Any]] = None):
        """Log slow operations that exceed threshold."""
        if duration > threshold:
            context_str = ""
            if context:
                context_items = [f"{k}={v}" for k, v in context.items()]
                context_str = f" ({', '.join(context_items)})"
            
            request_id = request_id_context.get('')
            request_prefix = f"[{request_id}] " if request_id else ""
            
            self.logger.warning(f"{request_prefix}SLOW OPERATION: '{operation_name}' took {duration:.3f}s "
                              f"(threshold: {threshold}s){context_str}")


def log_performance(operation_name: str, slow_threshold: float = 1.0, 
                   include_args: bool = False, logger_name: str = "Second_Brain_Database"):
    """
    Decorator for logging performance of functions and methods.
    
    Args:
        operation_name: Name of the operation for logging
        slow_threshold: Threshold in seconds to log as slow operation
        include_args: Whether to include function arguments in context
        logger_name: Logger name to use
    """
    def decorator(func: Callable) -> Callable:
        perf_logger = PerformanceLogger(logger_name)
        
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                start_time = time.time()
                context = {}
                
                if include_args:
                    # Sanitize arguments for logging
                    safe_args = []
                    for arg in args:
                        if hasattr(arg, '__dict__'):
                            safe_args.append(f"<{type(arg).__name__}>")
                        else:
                            safe_args.append(str(arg)[:100])  # Limit length
                    
                    safe_kwargs = {}
                    for k, v in kwargs.items():
                        if 'password' in k.lower() or 'token' in k.lower() or 'secret' in k.lower():
                            safe_kwargs[k] = "[REDACTED]"
                        elif hasattr(v, '__dict__'):
                            safe_kwargs[k] = f"<{type(v).__name__}>"
                        else:
                            safe_kwargs[k] = str(v)[:100]  # Limit length
                    
                    context = {"args": safe_args, "kwargs": safe_kwargs}
                
                try:
                    result = await func(*args, **kwargs)
                    duration = time.time() - start_time
                    perf_logger.log_operation(operation_name, duration, context)
                    perf_logger.log_slow_operation(operation_name, duration, slow_threshold, context)
                    return result
                except Exception as e:
                    duration = time.time() - start_time
                    context["error"] = str(e)
                    perf_logger.logger.error(f"Operation '{operation_name}' failed after {duration:.3f}s: {e}")
                    raise
            
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                start_time = time.time()
                context = {}
                
                if include_args:
                    # Sanitize arguments for logging
                    safe_args = []
                    for arg in args:
                        if hasattr(arg, '__dict__'):
                            safe_args.append(f"<{type(arg).__name__}>")
                        else:
                            safe_args.append(str(arg)[:100])  # Limit length
                    
                    safe_kwargs = {}
                    for k, v in kwargs.items():
                        if 'password' in k.lower() or 'token' in k.lower() or 'secret' in k.lower():
                            safe_kwargs[k] = "[REDACTED]"
                        elif hasattr(v, '__dict__'):
                            safe_kwargs[k] = f"<{type(v).__name__}>"
                        else:
                            safe_kwargs[k] = str(v)[:100]  # Limit length
                    
                    context = {"args": safe_args, "kwargs": safe_kwargs}
                
                try:
                    result = func(*args, **kwargs)
                    duration = time.time() - start_time
                    perf_logger.log_operation(operation_name, duration, context)
                    perf_logger.log_slow_operation(operation_name, duration, slow_threshold, context)
                    return result
                except Exception as e:
                    duration = time.time() - start_time
                    context["error"] = str(e)
                    perf_logger.logger.error(f"Operation '{operation_name}' failed after {duration:.3f}s: {e}")
                    raise
            
            return sync_wrapper
    
    return decorator


class DatabaseLogger:
    """Database operation logging utilities."""
    
    def __init__(self, logger_name: str = "Second_Brain_Database", prefix: str = "[DATABASE]"):
        self.logger = get_logger(name=logger_name, prefix=prefix)
    
    def log_query(self, context: DatabaseContext):
        """Log a database query operation."""
        request_id = context.request_id or request_id_context.get('')
        request_prefix = f"[{request_id}] " if request_id else ""
        
        # Sanitize query for logging
        sanitized_query = self._sanitize_query(context.query)
        
        if context.error:
            self.logger.error(f"{request_prefix}DB {context.operation} on '{context.collection}' FAILED "
                            f"after {context.duration:.3f}s: {context.error} | Query: {sanitized_query}")
        else:
            result_info = f" | Results: {context.result_count}" if context.result_count is not None else ""
            self.logger.info(f"{request_prefix}DB {context.operation} on '{context.collection}' "
                           f"completed in {context.duration:.3f}s{result_info} | Query: {sanitized_query}")
    
    def log_slow_query(self, context: DatabaseContext, threshold: float = 0.5):
        """Log slow database queries."""
        if context.duration > threshold:
            request_id = context.request_id or request_id_context.get('')
            request_prefix = f"[{request_id}] " if request_id else ""
            
            sanitized_query = self._sanitize_query(context.query)
            self.logger.warning(f"{request_prefix}SLOW QUERY: DB {context.operation} on '{context.collection}' "
                              f"took {context.duration:.3f}s (threshold: {threshold}s) | Query: {sanitized_query}")
    
    def _sanitize_query(self, query: Dict[str, Any]) -> str:
        """Sanitize query for safe logging."""
        if not query:
            return "{}"
        
        # Create a copy to avoid modifying original
        sanitized = {}
        for key, value in query.items():
            if any(sensitive in key.lower() for sensitive in ['password', 'token', 'secret', 'key']):
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_dict(value)
            elif isinstance(value, (list, tuple)):
                sanitized[key] = self._sanitize_list(value)
            else:
                # Limit string length for logging
                if isinstance(value, str) and len(value) > 200:
                    sanitized[key] = value[:200] + "..."
                else:
                    sanitized[key] = value
        
        return str(sanitized)
    
    def _sanitize_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively sanitize dictionary."""
        sanitized = {}
        for key, value in data.items():
            if any(sensitive in key.lower() for sensitive in ['password', 'token', 'secret', 'key']):
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_dict(value)
            elif isinstance(value, (list, tuple)):
                sanitized[key] = self._sanitize_list(value)
            else:
                sanitized[key] = value
        return sanitized
    
    def _sanitize_list(self, data: List[Any]) -> List[Any]:
        """Sanitize list items."""
        sanitized = []
        for item in data:
            if isinstance(item, dict):
                sanitized.append(self._sanitize_dict(item))
            elif isinstance(item, (list, tuple)):
                sanitized.append(self._sanitize_list(item))
            else:
                sanitized.append(item)
        return sanitized


def log_database_operation(operation: str, collection: str, slow_threshold: float = 0.5):
    """
    Decorator for logging database operations.
    
    Args:
        operation: Type of database operation (find, insert, update, delete, etc.)
        collection: Database collection name
        slow_threshold: Threshold in seconds to log as slow query
    """
    def decorator(func: Callable) -> Callable:
        db_logger = DatabaseLogger()
        
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                start_time = time.time()
                query = kwargs.get('query', kwargs.get('filter', {}))
                
                try:
                    result = await func(*args, **kwargs)
                    duration = time.time() - start_time
                    
                    # Try to get result count if possible
                    result_count = None
                    if hasattr(result, '__len__'):
                        try:
                            result_count = len(result)
                        except:
                            pass
                    elif hasattr(result, 'inserted_id'):
                        result_count = 1
                    elif hasattr(result, 'modified_count'):
                        result_count = result.modified_count
                    elif hasattr(result, 'deleted_count'):
                        result_count = result.deleted_count
                    
                    context = DatabaseContext(
                        operation=operation,
                        collection=collection,
                        query=query,
                        duration=duration,
                        result_count=result_count,
                        request_id=request_id_context.get('')
                    )
                    
                    db_logger.log_query(context)
                    db_logger.log_slow_query(context, slow_threshold)
                    
                    return result
                except Exception as e:
                    duration = time.time() - start_time
                    context = DatabaseContext(
                        operation=operation,
                        collection=collection,
                        query=query,
                        duration=duration,
                        error=str(e),
                        request_id=request_id_context.get('')
                    )
                    db_logger.log_query(context)
                    raise
            
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                start_time = time.time()
                query = kwargs.get('query', kwargs.get('filter', {}))
                
                try:
                    result = func(*args, **kwargs)
                    duration = time.time() - start_time
                    
                    # Try to get result count if possible
                    result_count = None
                    if hasattr(result, '__len__'):
                        try:
                            result_count = len(result)
                        except:
                            pass
                    elif hasattr(result, 'inserted_id'):
                        result_count = 1
                    elif hasattr(result, 'modified_count'):
                        result_count = result.modified_count
                    elif hasattr(result, 'deleted_count'):
                        result_count = result.deleted_count
                    
                    context = DatabaseContext(
                        operation=operation,
                        collection=collection,
                        query=query,
                        duration=duration,
                        result_count=result_count,
                        request_id=request_id_context.get('')
                    )
                    
                    db_logger.log_query(context)
                    db_logger.log_slow_query(context, slow_threshold)
                    
                    return result
                except Exception as e:
                    duration = time.time() - start_time
                    context = DatabaseContext(
                        operation=operation,
                        collection=collection,
                        query=query,
                        duration=duration,
                        error=str(e),
                        request_id=request_id_context.get('')
                    )
                    db_logger.log_query(context)
                    raise
            
            return sync_wrapper
    
    return decorator


class SecurityLogger:
    """Security event logging utilities."""
    
    def __init__(self, logger_name: str = "Second_Brain_Database", prefix: str = "[SECURITY]"):
        self.logger = get_logger(name=logger_name, prefix=prefix)
    
    def log_auth_event(self, context: SecurityContext):
        """Log authentication and authorization events."""
        request_id = context.request_id or request_id_context.get('')
        request_prefix = f"[{request_id}] " if request_id else ""
        
        status = "SUCCESS" if context.success else "FAILED"
        user_info = f" | User: {context.user_id}" if context.user_id else ""
        ip_info = f" | IP: {context.ip_address}" if context.ip_address else ""
        
        # Sanitize details for logging
        sanitized_details = self._sanitize_security_details(context.details)
        details_str = f" | Details: {sanitized_details}" if sanitized_details else ""
        
        if context.success:
            self.logger.info(f"{request_prefix}AUTH {status}: {context.event_type}{user_info}{ip_info}{details_str}")
        else:
            self.logger.warning(f"{request_prefix}AUTH {status}: {context.event_type}{user_info}{ip_info}{details_str}")
    
    def log_security_violation(self, event_type: str, details: Dict[str, Any], 
                             user_id: Optional[str] = None, ip_address: str = ""):
        """Log security violations and suspicious activities."""
        request_id = request_id_context.get('')
        request_prefix = f"[{request_id}] " if request_id else ""
        
        user_info = f" | User: {user_id}" if user_id else ""
        ip_info = f" | IP: {ip_address}" if ip_address else ""
        
        sanitized_details = self._sanitize_security_details(details)
        details_str = f" | Details: {sanitized_details}" if sanitized_details else ""
        
        self.logger.error(f"{request_prefix}SECURITY VIOLATION: {event_type}{user_info}{ip_info}{details_str}")
    
    def log_access_attempt(self, resource: str, success: bool, user_id: Optional[str] = None, 
                          ip_address: str = "", details: Optional[Dict[str, Any]] = None):
        """Log resource access attempts."""
        request_id = request_id_context.get('')
        request_prefix = f"[{request_id}] " if request_id else ""
        
        status = "GRANTED" if success else "DENIED"
        user_info = f" | User: {user_id}" if user_id else ""
        ip_info = f" | IP: {ip_address}" if ip_address else ""
        
        sanitized_details = self._sanitize_security_details(details or {})
        details_str = f" | Details: {sanitized_details}" if sanitized_details else ""
        
        if success:
            self.logger.info(f"{request_prefix}ACCESS {status}: {resource}{user_info}{ip_info}{details_str}")
        else:
            self.logger.warning(f"{request_prefix}ACCESS {status}: {resource}{user_info}{ip_info}{details_str}")
    
    def _sanitize_security_details(self, details: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize security details for safe logging."""
        if not details:
            return {}
        
        sanitized = {}
        for key, value in details.items():
            if any(sensitive in key.lower() for sensitive in ['password', 'token', 'secret', 'key', 'hash']):
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_security_details(value)
            elif isinstance(value, str) and len(value) > 200:
                sanitized[key] = value[:200] + "..."
            else:
                sanitized[key] = value
        
        return sanitized


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for comprehensive request logging."""
    
    def __init__(self, app, logger_name: str = "Second_Brain_Database", prefix: str = "[REQUEST]"):
        super().__init__(app)
        self.logger = get_logger(name=logger_name, prefix=prefix)
    
    async def dispatch(self, request: Request, call_next):
        # Generate unique request ID
        request_id = str(uuid.uuid4())
        request_id_context.set(request_id)
        
        # Extract request information
        start_time = time.time()
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "")
        
        # Set context variables
        ip_address_context.set(client_ip)
        
        # Create request context
        request_context = RequestContext(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            ip_address=client_ip,
            user_agent=user_agent,
            query_params=dict(request.query_params),
            path_params=dict(request.path_params)
        )
        
        # Log incoming request
        self._log_request_start(request_context)
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Log successful response
            self._log_request_success(request_context, response, duration)
            
            return response
            
        except Exception as e:
            # Calculate duration
            duration = time.time() - start_time
            
            # Log failed request
            self._log_request_error(request_context, e, duration)
            
            # Re-raise the exception
            raise
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        # Check for forwarded headers first
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # Take the first IP in the chain
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        # Fallback to client host
        if request.client:
            return request.client.host
        
        return "unknown"
    
    def _log_request_start(self, context: RequestContext):
        """Log the start of a request."""
        query_str = f"?{dict(context.query_params)}" if context.query_params else ""
        path_str = f"{context.path}{query_str}"
        
        self.logger.info(f"[{context.request_id}] {context.method} {path_str} | "
                        f"IP: {context.ip_address} | UA: {context.user_agent[:100]}")
    
    def _log_request_success(self, context: RequestContext, response: Response, duration: float):
        """Log successful request completion."""
        self.logger.info(f"[{context.request_id}] {context.method} {context.path} | "
                        f"Status: {response.status_code} | Duration: {duration:.3f}s")
        
        # Log slow requests
        if duration > 2.0:  # 2 second threshold
            self.logger.warning(f"[{context.request_id}] SLOW REQUEST: {context.method} {context.path} | "
                              f"Duration: {duration:.3f}s")
    
    def _log_request_error(self, context: RequestContext, error: Exception, duration: float):
        """Log failed request."""
        self.logger.error(f"[{context.request_id}] {context.method} {context.path} | "
                         f"ERROR after {duration:.3f}s: {str(error)}")


@asynccontextmanager
async def request_context(request_id: Optional[str] = None, user_id: Optional[str] = None, 
                         ip_address: Optional[str] = None):
    """Context manager for setting request context variables."""
    # Store current values
    old_request_id = request_id_context.get('')
    old_user_id = user_id_context.get('')
    old_ip_address = ip_address_context.get('')
    
    try:
        # Set new values
        if request_id:
            request_id_context.set(request_id)
        if user_id:
            user_id_context.set(user_id)
        if ip_address:
            ip_address_context.set(ip_address)
        
        yield
    finally:
        # Restore old values
        request_id_context.set(old_request_id)
        user_id_context.set(old_user_id)
        ip_address_context.set(old_ip_address)


# Convenience functions for common logging patterns
def log_auth_success(event_type: str, user_id: str, ip_address: str = "", 
                    details: Optional[Dict[str, Any]] = None):
    """Log successful authentication event."""
    security_logger = SecurityLogger()
    context = SecurityContext(
        event_type=event_type,
        user_id=user_id,
        ip_address=ip_address or ip_address_context.get(''),
        success=True,
        details=details or {},
        request_id=request_id_context.get('')
    )
    security_logger.log_auth_event(context)


def log_auth_failure(event_type: str, user_id: Optional[str] = None, ip_address: str = "", 
                    details: Optional[Dict[str, Any]] = None):
    """Log failed authentication event."""
    security_logger = SecurityLogger()
    context = SecurityContext(
        event_type=event_type,
        user_id=user_id,
        ip_address=ip_address or ip_address_context.get(''),
        success=False,
        details=details or {},
        request_id=request_id_context.get('')
    )
    security_logger.log_auth_event(context)


def log_security_event(event_type: str, details: Dict[str, Any], user_id: Optional[str] = None, 
                      ip_address: str = ""):
    """Log general security event."""
    security_logger = SecurityLogger()
    security_logger.log_security_violation(
        event_type=event_type,
        details=details,
        user_id=user_id or user_id_context.get(''),
        ip_address=ip_address or ip_address_context.get('')
    )


def log_access_granted(resource: str, user_id: str, details: Optional[Dict[str, Any]] = None):
    """Log successful resource access."""
    security_logger = SecurityLogger()
    security_logger.log_access_attempt(
        resource=resource,
        success=True,
        user_id=user_id,
        ip_address=ip_address_context.get(''),
        details=details
    )


def log_access_denied(resource: str, user_id: Optional[str] = None, 
                     details: Optional[Dict[str, Any]] = None):
    """Log denied resource access."""
    security_logger = SecurityLogger()
    security_logger.log_access_attempt(
        resource=resource,
        success=False,
        user_id=user_id or user_id_context.get(''),
        ip_address=ip_address_context.get(''),
        details=details
    )
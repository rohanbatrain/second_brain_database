"""
Browser-specific error logging for OAuth2 flows.

This module provides enhanced error logging specifically for browser-based OAuth2 flows,
capturing additional context that's relevant for debugging browser authentication issues.

Enhanced for Task 8: Comprehensive Error Handling
- Detailed browser context logging
- User journey tracking for error analysis
- Enhanced error categorization for browser flows
- Performance metrics for error scenarios
"""

import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from fastapi import Request

from second_brain_database.managers.logging_manager import get_logger
from .error_handler import OAuth2ErrorCode, OAuth2ErrorSeverity

logger = get_logger(prefix="[OAuth2 Browser Error Logger]")


class BrowserErrorLogger:
    """
    Enhanced error logging specifically for browser-based OAuth2 flows.
    
    This class captures additional browser-specific context that's useful
    for debugging and monitoring OAuth2 authentication issues in web browsers.
    """
    
    def __init__(self):
        self.logger = get_logger(prefix="[OAuth2 Browser Error Logger]")
    
    def log_browser_oauth2_error(
        self,
        error_code: OAuth2ErrorCode,
        error_description: str,
        request: Request,
        client_id: Optional[str] = None,
        client_name: Optional[str] = None,
        user_id: Optional[str] = None,
        user_agent_info: Optional[Dict[str, Any]] = None,
        oauth2_flow_context: Optional[Dict[str, Any]] = None,
        performance_metrics: Optional[Dict[str, Any]] = None,
        severity: OAuth2ErrorSeverity = OAuth2ErrorSeverity.LOW,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log OAuth2 error with comprehensive browser context.
        
        Args:
            error_code: OAuth2 error code
            error_description: Technical error description
            request: FastAPI request object
            client_id: OAuth2 client identifier
            client_name: Human-readable client name
            user_id: User identifier if available
            user_agent_info: Parsed user agent information
            oauth2_flow_context: OAuth2 flow state and context
            performance_metrics: Performance timing data
            severity: Error severity level
            additional_context: Additional error context
        """
        # Extract comprehensive browser context
        browser_context = self._extract_browser_context(request, user_agent_info)
        
        # Extract OAuth2 flow context
        flow_context = self._extract_oauth2_flow_context(
            request, oauth2_flow_context, client_id, client_name
        )
        
        # Extract performance context
        perf_context = self._extract_performance_context(performance_metrics)
        
        # Build comprehensive log entry
        log_context = {
            # Error details
            "error_type": "browser_oauth2_error",
            "error_code": error_code.value,
            "error_description": error_description,
            "severity": severity.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            
            # Client and user context
            "client_id": client_id,
            "client_name": client_name,
            "user_id": user_id,
            
            # Browser context
            **browser_context,
            
            # OAuth2 flow context
            **flow_context,
            
            # Performance context
            **perf_context,
            
            # Additional context
            **(additional_context or {})
        }
        
        # Log with appropriate level based on severity
        log_message = f"Browser OAuth2 Error: {error_code.value} - {error_description}"
        
        if severity == OAuth2ErrorSeverity.CRITICAL:
            self.logger.critical(log_message, extra={"browser_oauth2_context": log_context})
        elif severity == OAuth2ErrorSeverity.HIGH:
            self.logger.error(log_message, extra={"browser_oauth2_context": log_context})
        elif severity == OAuth2ErrorSeverity.MEDIUM:
            self.logger.warning(log_message, extra={"browser_oauth2_context": log_context})
        else:
            self.logger.info(log_message, extra={"browser_oauth2_context": log_context})
    
    def log_browser_oauth2_success(
        self,
        event_type: str,
        request: Request,
        client_id: Optional[str] = None,
        client_name: Optional[str] = None,
        user_id: Optional[str] = None,
        performance_metrics: Optional[Dict[str, Any]] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log successful OAuth2 browser events for monitoring and analytics.
        
        Args:
            event_type: Type of successful event
            request: FastAPI request object
            client_id: OAuth2 client identifier
            client_name: Human-readable client name
            user_id: User identifier
            performance_metrics: Performance timing data
            additional_context: Additional event context
        """
        # Extract browser context
        browser_context = self._extract_browser_context(request)
        
        # Extract performance context
        perf_context = self._extract_performance_context(performance_metrics)
        
        # Build log entry
        log_context = {
            "event_type": f"browser_oauth2_{event_type}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "client_id": client_id,
            "client_name": client_name,
            "user_id": user_id,
            **browser_context,
            **perf_context,
            **(additional_context or {})
        }
        
        self.logger.info(
            f"Browser OAuth2 Success: {event_type}",
            extra={"browser_oauth2_context": log_context}
        )
    
    def _extract_browser_context(
        self, 
        request: Request, 
        user_agent_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Extract comprehensive browser context from request.
        
        Args:
            request: FastAPI request object
            user_agent_info: Optional parsed user agent information
            
        Returns:
            Dictionary with browser context
        """
        # Basic request information
        context = {
            "request_method": request.method,
            "request_url": str(request.url),
            "request_path": request.url.path,
            "query_params": dict(request.query_params),
            "client_ip": request.client.host if request.client else "unknown",
        }
        
        # Headers context
        headers = dict(request.headers)
        context.update({
            "user_agent": headers.get("user-agent", ""),
            "accept": headers.get("accept", ""),
            "accept_language": headers.get("accept-language", ""),
            "accept_encoding": headers.get("accept-encoding", ""),
            "referer": headers.get("referer", ""),
            "origin": headers.get("origin", ""),
            "host": headers.get("host", ""),
            "connection": headers.get("connection", ""),
            "upgrade_insecure_requests": headers.get("upgrade-insecure-requests", ""),
            "sec_fetch_site": headers.get("sec-fetch-site", ""),
            "sec_fetch_mode": headers.get("sec-fetch-mode", ""),
            "sec_fetch_user": headers.get("sec-fetch-user", ""),
            "sec_fetch_dest": headers.get("sec-fetch-dest", ""),
        })
        
        # User agent analysis
        if user_agent_info:
            context["user_agent_parsed"] = user_agent_info
        else:
            context["user_agent_parsed"] = self._parse_user_agent(headers.get("user-agent", ""))
        
        # Browser capability detection
        context["browser_capabilities"] = self._detect_browser_capabilities(headers)
        
        # Security context
        security_context = self._extract_security_context(request, headers)
        context.update(security_context)
        
        return context
    
    def _extract_oauth2_flow_context(
        self,
        request: Request,
        oauth2_flow_context: Optional[Dict[str, Any]],
        client_id: Optional[str],
        client_name: Optional[str]
    ) -> Dict[str, Any]:
        """
        Extract OAuth2 flow-specific context.
        
        Args:
            request: FastAPI request object
            oauth2_flow_context: Optional OAuth2 flow context
            client_id: OAuth2 client identifier
            client_name: Human-readable client name
            
        Returns:
            Dictionary with OAuth2 flow context
        """
        context = {
            "oauth2_flow_stage": "unknown",
            "oauth2_parameters": {},
            "oauth2_state_info": {},
        }
        
        # Extract OAuth2 parameters from query string
        query_params = dict(request.query_params)
        oauth2_params = {}
        
        oauth2_param_names = [
            "response_type", "client_id", "redirect_uri", "scope", "state",
            "code_challenge", "code_challenge_method", "code", "grant_type"
        ]
        
        for param in oauth2_param_names:
            if param in query_params:
                oauth2_params[param] = query_params[param]
        
        context["oauth2_parameters"] = oauth2_params
        
        # Determine flow stage based on URL path and parameters
        path = request.url.path
        if "/oauth2/authorize" in path:
            context["oauth2_flow_stage"] = "authorization"
        elif "/oauth2/token" in path:
            context["oauth2_flow_stage"] = "token_exchange"
        elif "/oauth2/consent" in path:
            context["oauth2_flow_stage"] = "consent"
        elif "/auth/login" in path and "redirect_uri" in query_params:
            context["oauth2_flow_stage"] = "authentication"
        
        # Add provided flow context
        if oauth2_flow_context:
            context["oauth2_state_info"] = oauth2_flow_context
        
        # Add client context
        context["oauth2_client_context"] = {
            "client_id": client_id,
            "client_name": client_name,
            "client_type": self._determine_client_type(request, oauth2_params)
        }
        
        return context
    
    def _extract_performance_context(
        self, 
        performance_metrics: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Extract performance-related context.
        
        Args:
            performance_metrics: Optional performance timing data
            
        Returns:
            Dictionary with performance context
        """
        context = {
            "performance_metrics": performance_metrics or {},
            "timestamp_ms": int(time.time() * 1000)
        }
        
        if performance_metrics:
            # Calculate derived metrics
            if "start_time" in performance_metrics and "end_time" in performance_metrics:
                context["total_duration_ms"] = (
                    performance_metrics["end_time"] - performance_metrics["start_time"]
                ) * 1000
        
        return context
    
    def _parse_user_agent(self, user_agent: str) -> Dict[str, Any]:
        """
        Parse user agent string to extract browser information.
        
        Args:
            user_agent: User agent string
            
        Returns:
            Dictionary with parsed user agent information
        """
        ua_lower = user_agent.lower()
        
        # Browser detection
        browser_info = {
            "browser": "unknown",
            "version": "unknown",
            "platform": "unknown",
            "mobile": False,
            "bot": False
        }
        
        # Detect browser
        if "chrome" in ua_lower and "edg" not in ua_lower:
            browser_info["browser"] = "chrome"
        elif "firefox" in ua_lower:
            browser_info["browser"] = "firefox"
        elif "safari" in ua_lower and "chrome" not in ua_lower:
            browser_info["browser"] = "safari"
        elif "edg" in ua_lower:
            browser_info["browser"] = "edge"
        elif "opera" in ua_lower or "opr" in ua_lower:
            browser_info["browser"] = "opera"
        
        # Detect platform
        if "windows" in ua_lower:
            browser_info["platform"] = "windows"
        elif "mac" in ua_lower:
            browser_info["platform"] = "macos"
        elif "linux" in ua_lower:
            browser_info["platform"] = "linux"
        elif "android" in ua_lower:
            browser_info["platform"] = "android"
            browser_info["mobile"] = True
        elif "iphone" in ua_lower or "ipad" in ua_lower or "ios" in ua_lower:
            browser_info["platform"] = "ios"
            browser_info["mobile"] = True
        
        # Detect mobile
        mobile_indicators = ["mobile", "tablet", "phone", "android", "iphone", "ipad"]
        if any(indicator in ua_lower for indicator in mobile_indicators):
            browser_info["mobile"] = True
        
        # Detect bots
        bot_indicators = ["bot", "crawler", "spider", "scraper", "curl", "wget"]
        if any(indicator in ua_lower for indicator in bot_indicators):
            browser_info["bot"] = True
        
        return browser_info
    
    def _detect_browser_capabilities(self, headers: Dict[str, str]) -> Dict[str, Any]:
        """
        Detect browser capabilities from headers.
        
        Args:
            headers: Request headers
            
        Returns:
            Dictionary with browser capabilities
        """
        capabilities = {
            "javascript_enabled": True,  # Assume true for OAuth2 flows
            "cookies_enabled": True,     # Assume true for OAuth2 flows
            "https_supported": True,     # Assume true for OAuth2 flows
            "modern_browser": True       # Assume true unless detected otherwise
        }
        
        # Check for modern browser features
        sec_fetch_headers = [
            "sec-fetch-site", "sec-fetch-mode", "sec-fetch-user", "sec-fetch-dest"
        ]
        
        if any(header in headers for header in sec_fetch_headers):
            capabilities["supports_fetch_metadata"] = True
        else:
            capabilities["supports_fetch_metadata"] = False
            capabilities["modern_browser"] = False
        
        # Check for upgrade insecure requests
        if headers.get("upgrade-insecure-requests") == "1":
            capabilities["supports_upgrade_insecure_requests"] = True
        
        return capabilities
    
    def _extract_security_context(
        self, 
        request: Request, 
        headers: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Extract security-related context from request.
        
        Args:
            request: FastAPI request object
            headers: Request headers
            
        Returns:
            Dictionary with security context
        """
        context = {
            "is_https": request.url.scheme == "https",
            "has_origin": "origin" in headers,
            "has_referer": "referer" in headers,
            "cross_origin": False,
            "suspicious_patterns": []
        }
        
        # Check for cross-origin requests
        origin = headers.get("origin")
        host = headers.get("host")
        if origin and host:
            origin_host = urlparse(origin).netloc
            context["cross_origin"] = origin_host != host
        
        # Check for suspicious patterns
        user_agent = headers.get("user-agent", "").lower()
        suspicious_patterns = []
        
        if not user_agent:
            suspicious_patterns.append("missing_user_agent")
        elif len(user_agent) < 10:
            suspicious_patterns.append("short_user_agent")
        
        if "curl" in user_agent or "wget" in user_agent:
            suspicious_patterns.append("command_line_tool")
        
        context["suspicious_patterns"] = suspicious_patterns
        
        return context
    
    def _determine_client_type(
        self, 
        request: Request, 
        oauth2_params: Dict[str, str]
    ) -> str:
        """
        Determine the type of OAuth2 client based on request characteristics.
        
        Args:
            request: FastAPI request object
            oauth2_params: OAuth2 parameters from request
            
        Returns:
            String indicating client type
        """
        # Check for PKCE parameters (indicates public client)
        if "code_challenge" in oauth2_params:
            return "public_spa"
        
        # Check user agent for mobile app patterns
        user_agent = request.headers.get("user-agent", "").lower()
        if any(pattern in user_agent for pattern in ["mobile", "android", "iphone"]):
            return "mobile_app"
        
        # Check for server-to-server patterns
        if not request.headers.get("accept", "").startswith("text/html"):
            return "server_to_server"
        
        # Default to web application
        return "web_application"


# Global browser error logger instance
browser_error_logger = BrowserErrorLogger()
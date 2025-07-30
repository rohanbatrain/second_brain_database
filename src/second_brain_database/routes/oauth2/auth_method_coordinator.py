"""
Enterprise authentication method coordination system for OAuth2.

This module provides intelligent authentication method detection, routing, and coordination
for OAuth2 flows that support both API clients (JWT tokens) and browser clients (sessions).
It includes preference detection, fallback mechanisms, caching, and comprehensive monitoring.

Features:
- Authentication method detection based on request headers and content types
- Intelligent routing between JWT and session-based authentication
- Client capability detection and preference caching
- Seamless fallback mechanisms between authentication methods
- Performance optimization through method caching
- Comprehensive logging and monitoring of authentication method selection
- Enterprise-grade security and abuse detection
"""

import asyncio
import time
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict, deque

from fastapi import Request, HTTPException, status
from pydantic import BaseModel

from second_brain_database.config import settings
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.routes.oauth2.monitoring import (
    oauth2_monitoring, AuthenticationMethod, record_security_event
)

logger = get_logger(prefix="[OAuth2 Auth Coordinator]")


class AuthMethodPreference(str, Enum):
    """Authentication method preferences."""
    JWT_ONLY = "jwt_only"
    SESSION_ONLY = "session_only"
    JWT_PREFERRED = "jwt_preferred"
    SESSION_PREFERRED = "session_preferred"
    AUTO_DETECT = "auto_detect"
    MIXED = "mixed"


class ClientType(str, Enum):
    """Client type classifications."""
    API_CLIENT = "api_client"
    BROWSER_CLIENT = "browser_client"
    MOBILE_APP = "mobile_app"
    SPA_CLIENT = "spa_client"
    HYBRID_CLIENT = "hybrid_client"
    UNKNOWN = "unknown"


class AuthMethodCapability(str, Enum):
    """Authentication method capabilities."""
    JWT_BEARER = "jwt_bearer"
    SESSION_COOKIE = "session_cookie"
    CSRF_TOKEN = "csrf_token"
    WEBAUTHN = "webauthn"
    OAUTH2_PKCE = "oauth2_pkce"



@dataclass
class ClientCapabilities:
    """Client authentication capabilities and preferences."""
    client_id: str
    client_type: ClientType
    supported_methods: Set[AuthMethodCapability]
    preferred_method: AuthMethodPreference
    user_agent_pattern: Optional[str] = None
    origin_patterns: List[str] = field(default_factory=list)
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    success_rate: Dict[AuthenticationMethod, float] = field(default_factory=dict)
    usage_count: Dict[AuthenticationMethod, int] = field(default_factory=dict)


@dataclass
class AuthMethodDecision:
    """Authentication method selection decision."""
    selected_method: AuthenticationMethod
    fallback_method: Optional[AuthenticationMethod]
    confidence_score: float
    decision_factors: List[str]
    client_capabilities: Optional[ClientCapabilities]
    cache_hit: bool = False
    decision_time_ms: float = 0.0


@dataclass
class AuthMethodStats:
    """Authentication method usage statistics."""
    method: AuthenticationMethod
    total_attempts: int = 0
    successful_attempts: int = 0
    failed_attempts: int = 0
    avg_response_time: float = 0.0
    last_used: Optional[datetime] = None
    client_types: Dict[ClientType, int] = field(default_factory=dict)


class AuthMethodCoordinator:
    """
    Enterprise authentication method coordination system.
    
    Provides intelligent detection, routing, and coordination of authentication
    methods for OAuth2 flows supporting both API and browser clients.
    """
    
    def __init__(self):
        self.logger = get_logger(prefix="[Auth Method Coordinator]")
        
        # Client capabilities cache
        self.client_capabilities: Dict[str, ClientCapabilities] = {}
        
        # Authentication method statistics
        self.method_stats: Dict[AuthenticationMethod, AuthMethodStats] = {
            AuthenticationMethod.JWT_TOKEN: AuthMethodStats(AuthenticationMethod.JWT_TOKEN),
            AuthenticationMethod.BROWSER_SESSION: AuthMethodStats(AuthenticationMethod.BROWSER_SESSION),
            AuthenticationMethod.MIXED: AuthMethodStats(AuthenticationMethod.MIXED)
        }
        
        # Decision cache for performance optimization
        self.decision_cache: Dict[str, Tuple[AuthMethodDecision, datetime]] = {}
        self.cache_ttl = timedelta(minutes=15)  # Cache decisions for 15 minutes
        
        # Pattern matching for client detection
        self.browser_patterns = [
            r"Mozilla/.*Chrome/.*",
            r"Mozilla/.*Firefox/.*",
            r"Mozilla/.*Safari/.*",
            r"Mozilla/.*Edge/.*"
        ]
        
        self.api_client_patterns = [
            r".*curl/.*",
            r".*python-requests/.*",
            r".*axios/.*",
            r".*fetch/.*",
            r".*HTTPie/.*",
            r".*Postman/.*"
        ]
        
        # Security monitoring
        self.suspicious_patterns: deque = deque(maxlen=100)
        self.rate_limit_cache: Dict[str, List[datetime]] = defaultdict(list)
        
        # Performance metrics
        self.decision_times: deque = deque(maxlen=1000)
        self.cache_hit_rate = {"hits": 0, "misses": 0}
        
        # Initialize default client capabilities
        self._initialize_default_capabilities()
    
    def _initialize_default_capabilities(self) -> None:
        """Initialize default client capabilities for common client types."""
        # This method can be expanded to set up default configurations
        pass  
  
    async def coordinate_authentication_method(
        self,
        request: Request,
        client_id: str,
        user_id: Optional[str] = None,
        flow_id: Optional[str] = None
    ) -> AuthMethodDecision:
        """
        Coordinate and select the optimal authentication method for the request.
        
        Args:
            request: FastAPI request object
            client_id: OAuth2 client identifier
            user_id: User identifier if available
            flow_id: OAuth2 flow identifier if available
            
        Returns:
            AuthMethodDecision: Selected authentication method with metadata
            
        Raises:
            HTTPException: If coordination fails or security violation detected
        """
        start_time = time.time()
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "")
        
        # Debug logging
        self.logger.debug(f"Coordinate method: user_agent='{user_agent}', headers={dict(request.headers)}")
        
        try:
            # Security checks
            await self._perform_security_checks(request, client_ip, user_agent)
            
            # Check decision cache first
            cache_key = self._generate_cache_key(request, client_id, user_id)
            cached_decision = self._get_cached_decision(cache_key)
            
            if cached_decision:
                cached_decision.cache_hit = True
                cached_decision.decision_time_ms = (time.time() - start_time) * 1000
                self.cache_hit_rate["hits"] += 1
                
                # Log cache hit
                self.logger.debug(
                    "Authentication method decision cache hit",
                    extra={
                        "client_id": client_id,
                        "selected_method": cached_decision.selected_method.value,
                        "cache_key": cache_key,
                        "decision_time_ms": cached_decision.decision_time_ms
                    }
                )
                
                return cached_decision
            
            self.cache_hit_rate["misses"] += 1
            
            # Detect client capabilities
            client_capabilities = await self._detect_client_capabilities(
                request, client_id, user_agent
            )
            
            # Make authentication method decision
            decision = await self._make_auth_method_decision(
                request, client_capabilities, user_id, flow_id
            )
            
            # Cache the decision
            self._cache_decision(cache_key, decision)
            
            # Record decision time
            decision.decision_time_ms = (time.time() - start_time) * 1000
            self.decision_times.append(decision.decision_time_ms)
            
            # Log decision
            await self._log_auth_method_decision(
                decision, request, client_id, user_id, flow_id
            )
            
            # Update statistics
            await self._update_method_statistics(decision, client_capabilities)
            
            return decision
            
        except HTTPException:
            raise
        except Exception as e:
            self.logger.error(
                "Authentication method coordination failed: %s",
                e,
                exc_info=True,
                extra={
                    "client_id": client_id,
                    "user_id": user_id,
                    "flow_id": flow_id,
                    "client_ip": client_ip,
                    "user_agent": user_agent
                }
            )
            
            # Return fallback decision
            return AuthMethodDecision(
                selected_method=AuthenticationMethod.JWT_TOKEN,
                fallback_method=AuthenticationMethod.BROWSER_SESSION,
                confidence_score=0.1,
                decision_factors=["error_fallback"],
                client_capabilities=None,
                decision_time_ms=(time.time() - start_time) * 1000
            )  
  
    async def _detect_client_capabilities(
        self,
        request: Request,
        client_id: str,
        user_agent: str
    ) -> ClientCapabilities:
        """
        Detect client authentication capabilities and preferences.
        
        Args:
            request: FastAPI request object
            client_id: OAuth2 client identifier
            user_agent: User agent string
            
        Returns:
            ClientCapabilities: Detected client capabilities
        """
        # Check if we have cached capabilities
        if client_id in self.client_capabilities:
            capabilities = self.client_capabilities[client_id]
            
            # Update if cache is stale (older than 1 hour)
            if (datetime.now(timezone.utc) - capabilities.last_updated).total_seconds() < 3600:
                return capabilities
        
        # Detect client type
        client_type = self._classify_client_type(request, user_agent)
        
        # Debug logging
        self.logger.debug(
            f"Client capabilities detection: user_agent='{user_agent}', client_type={client_type}"
        )
        
        # Detect supported authentication methods
        supported_methods = self._detect_supported_methods(request, client_type)
        
        # Determine preferred method
        preferred_method = self._determine_preferred_method(
            request, client_type, supported_methods
        )
        
        # Create capabilities object
        capabilities = ClientCapabilities(
            client_id=client_id,
            client_type=client_type,
            supported_methods=supported_methods,
            preferred_method=preferred_method,
            user_agent_pattern=self._extract_user_agent_pattern(user_agent),
            origin_patterns=self._extract_origin_patterns(request)
        )
        
        # Cache capabilities
        self.client_capabilities[client_id] = capabilities
        
        # Log capability detection
        self.logger.info(
            "Client capabilities detected",
            extra={
                "client_id": client_id,
                "client_type": client_type.value,
                "supported_methods": [m.value for m in supported_methods],
                "preferred_method": preferred_method.value,
                "user_agent_pattern": capabilities.user_agent_pattern
            }
        )
        
        return capabilities
    
    async def _make_auth_method_decision(
        self,
        request: Request,
        capabilities: ClientCapabilities,
        user_id: Optional[str],
        flow_id: Optional[str]
    ) -> AuthMethodDecision:
        """
        Make intelligent authentication method decision.
        
        Args:
            request: FastAPI request object
            capabilities: Client capabilities
            user_id: User identifier if available
            flow_id: OAuth2 flow identifier if available
            
        Returns:
            AuthMethodDecision: Authentication method decision
        """
        decision_factors = []
        confidence_score = 0.0
        
        # Check for explicit authentication method in request
        auth_header = request.headers.get("authorization")
        session_cookie = request.cookies.get("sbd_session")
        
        # Factor 1: Existing authentication tokens (40% weight)
        if auth_header and auth_header.startswith("Bearer "):
            selected_method = AuthenticationMethod.JWT_TOKEN
            fallback_method = AuthenticationMethod.BROWSER_SESSION
            confidence_score += 0.4
            decision_factors.append("bearer_token_present")
        elif session_cookie:
            selected_method = AuthenticationMethod.BROWSER_SESSION
            fallback_method = AuthenticationMethod.JWT_TOKEN
            confidence_score += 0.4
            decision_factors.append("session_cookie_present")
        else:
            # No existing authentication, use client preferences and type
            if capabilities.preferred_method == AuthMethodPreference.JWT_PREFERRED:
                selected_method = AuthenticationMethod.JWT_TOKEN
                fallback_method = AuthenticationMethod.BROWSER_SESSION
                confidence_score += 0.3
                decision_factors.append("client_prefers_jwt")
            elif capabilities.preferred_method == AuthMethodPreference.SESSION_PREFERRED:
                selected_method = AuthenticationMethod.BROWSER_SESSION
                fallback_method = AuthenticationMethod.JWT_TOKEN
                confidence_score += 0.3
                decision_factors.append("client_prefers_session")
            else:
                # Auto-detect based on client type
                if capabilities.client_type == ClientType.API_CLIENT:
                    selected_method = AuthenticationMethod.JWT_TOKEN
                    fallback_method = AuthenticationMethod.BROWSER_SESSION
                    confidence_score += 0.4
                    decision_factors.append("api_client_detected")
                elif capabilities.client_type == ClientType.MOBILE_APP:
                    selected_method = AuthenticationMethod.JWT_TOKEN
                    fallback_method = AuthenticationMethod.BROWSER_SESSION
                    confidence_score += 0.4
                    decision_factors.append("mobile_app_detected")
                elif capabilities.client_type == ClientType.UNKNOWN:
                    # For unknown clients, use request characteristics to decide
                    accept_header = request.headers.get("accept", "")
                    if "application/json" in accept_header and "text/html" not in accept_header:
                        selected_method = AuthenticationMethod.JWT_TOKEN
                        fallback_method = AuthenticationMethod.BROWSER_SESSION
                        confidence_score += 0.3
                        decision_factors.append("unknown_client_json_preference")
                    else:
                        selected_method = AuthenticationMethod.BROWSER_SESSION
                        fallback_method = AuthenticationMethod.JWT_TOKEN
                        confidence_score += 0.2
                        decision_factors.append("unknown_client_default")
                else:
                    selected_method = AuthenticationMethod.BROWSER_SESSION
                    fallback_method = AuthenticationMethod.JWT_TOKEN
                    confidence_score += 0.3
                    decision_factors.append("browser_client_detected")
        
        # Factor 2: Request characteristics (20% weight)
        content_type = request.headers.get("content-type", "")
        accept_header = request.headers.get("accept", "")
        
        if "application/json" in content_type or "application/json" in accept_header:
            if selected_method == AuthenticationMethod.JWT_TOKEN:
                confidence_score += 0.2
                decision_factors.append("json_content_supports_jwt")
            else:
                confidence_score += 0.1
                decision_factors.append("json_content_neutral")
        
        if "text/html" in accept_header:
            if selected_method == AuthenticationMethod.BROWSER_SESSION:
                confidence_score += 0.2
                decision_factors.append("html_accept_supports_session")
            else:
                confidence_score += 0.1
                decision_factors.append("html_accept_neutral")
        
        # Factor 3: Historical success rates (20% weight)
        if capabilities.success_rate:
            jwt_success = capabilities.success_rate.get(AuthenticationMethod.JWT_TOKEN, 0.0)
            session_success = capabilities.success_rate.get(AuthenticationMethod.BROWSER_SESSION, 0.0)
            
            if selected_method == AuthenticationMethod.JWT_TOKEN and jwt_success > 0.8:
                confidence_score += 0.2
                decision_factors.append("high_jwt_success_rate")
            elif selected_method == AuthenticationMethod.BROWSER_SESSION and session_success > 0.8:
                confidence_score += 0.2
                decision_factors.append("high_session_success_rate")
            elif jwt_success > session_success and selected_method == AuthenticationMethod.JWT_TOKEN:
                confidence_score += 0.1
                decision_factors.append("jwt_historically_better")
            elif session_success > jwt_success and selected_method == AuthenticationMethod.BROWSER_SESSION:
                confidence_score += 0.1
                decision_factors.append("session_historically_better")
        
        # Factor 4: Security considerations (10% weight)
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            # AJAX request, likely supports both methods
            confidence_score += 0.05
            decision_factors.append("ajax_request_detected")
        
        if request.headers.get("sec-fetch-site") == "same-origin":
            # Same-origin request, session auth is secure
            if selected_method == AuthenticationMethod.BROWSER_SESSION:
                confidence_score += 0.1
                decision_factors.append("same_origin_supports_session")
        
        # Factor 5: Performance considerations (10% weight)
        method_stats = self.method_stats.get(selected_method)
        if method_stats and method_stats.avg_response_time < 100:  # Less than 100ms
            confidence_score += 0.1
            decision_factors.append("fast_method_performance")
        
        # Ensure confidence score is within bounds
        confidence_score = min(1.0, max(0.1, confidence_score))
        
        return AuthMethodDecision(
            selected_method=selected_method,
            fallback_method=fallback_method,
            confidence_score=confidence_score,
            decision_factors=decision_factors,
            client_capabilities=capabilities
        )    
   
    def _classify_client_type(self, request: Request, user_agent: str) -> ClientType:
        """
        Classify the client type based on request characteristics.
        
        Args:
            request: FastAPI request object
            user_agent: User agent string
            
        Returns:
            ClientType: Classified client type
        """
        import re
        
        # Debug logging
        self.logger.debug(f"Classifying client type: user_agent='{user_agent}'")
        self.logger.debug(f"API client patterns: {self.api_client_patterns}")
        
        # Check for mobile app indicators first (most specific)
        if any(mobile in user_agent.lower() for mobile in ["iphone", "ipad", "android"]):
            if ("app/" in user_agent.lower() or "native" in user_agent.lower() or 
                ("ios" in user_agent.lower() and not "safari" in user_agent.lower()) or
                (not any(browser in user_agent.lower() for browser in ["mozilla", "chrome", "firefox", "safari", "webkit"]))):
                self.logger.debug("Classified as MOBILE_APP")
                return ClientType.MOBILE_APP
        
        # Check for custom app user agents (like "MyApp/1.0")
        # But exclude known API clients like python-requests
        if (not any(browser in user_agent.lower() for browser in ["mozilla", "chrome", "firefox", "safari", "webkit"]) and
            "/" in user_agent and "." in user_agent and 
            not any(api_pattern in user_agent.lower() for api_pattern in ["curl", "python-requests", "http"]) and
            "python" not in user_agent.lower()):
            self.logger.debug("Classified as MOBILE_APP (custom app)")
            return ClientType.MOBILE_APP
        
        # Check API client patterns (check these early and specifically)
        for pattern in self.api_client_patterns:
            self.logger.debug(f"Testing pattern '{pattern}' against '{user_agent}'")
            if re.search(pattern, user_agent, re.IGNORECASE):
                self.logger.debug(f"Classified as API_CLIENT (pattern: {pattern})")
                return ClientType.API_CLIENT
        
        # Additional check for python-requests specifically
        if "python-requests" in user_agent.lower():
            self.logger.debug("Classified as API_CLIENT (python-requests)")
            return ClientType.API_CLIENT
        
        # Check browser patterns
        for pattern in self.browser_patterns:
            if re.search(pattern, user_agent, re.IGNORECASE):
                # Further classify browser clients
                if request.headers.get("sec-fetch-dest") == "document":
                    self.logger.debug("Classified as BROWSER_CLIENT")
                    return ClientType.BROWSER_CLIENT
                elif request.headers.get("x-requested-with") == "XMLHttpRequest":
                    self.logger.debug("Classified as SPA_CLIENT")
                    return ClientType.SPA_CLIENT
                else:
                    self.logger.debug("Classified as BROWSER_CLIENT (default)")
                    return ClientType.BROWSER_CLIENT
        
        # Check request characteristics for API clients
        accept_header = request.headers.get("accept", "")
        content_type = request.headers.get("content-type", "")
        
        # Strong indicators of API client
        if ("application/json" in accept_header and "text/html" not in accept_header and 
            not any(browser in user_agent.lower() for browser in ["mozilla", "chrome", "firefox", "safari", "edge"])):
            self.logger.debug("Classified as API_CLIENT (JSON accept header)")
            return ClientType.API_CLIENT
        
        # Check for hybrid client indicators
        if request.headers.get("x-requested-with") or "fetch" in user_agent.lower():
            self.logger.debug("Classified as HYBRID_CLIENT")
            return ClientType.HYBRID_CLIENT
        
        # Default classification based on accept headers
        if "text/html" in accept_header:
            self.logger.debug("Classified as BROWSER_CLIENT (HTML accept)")
            return ClientType.BROWSER_CLIENT
        elif "application/json" in accept_header:
            self.logger.debug("Classified as API_CLIENT (JSON accept)")
            return ClientType.API_CLIENT
        
        self.logger.debug("Classified as UNKNOWN")
        return ClientType.UNKNOWN
    
    def _detect_supported_methods(
        self,
        request: Request,
        client_type: ClientType
    ) -> Set[AuthMethodCapability]:
        """
        Detect supported authentication methods based on client type and request.
        
        Args:
            request: FastAPI request object
            client_type: Classified client type
            
        Returns:
            Set[AuthMethodCapability]: Supported authentication methods
        """
        supported = set()
        
        # All clients support JWT bearer tokens
        supported.add(AuthMethodCapability.JWT_BEARER)
        
        # Browser and hybrid clients support session cookies
        if client_type in [ClientType.BROWSER_CLIENT, ClientType.SPA_CLIENT, ClientType.HYBRID_CLIENT]:
            supported.add(AuthMethodCapability.SESSION_COOKIE)
            
            # Check for CSRF token support
            if request.headers.get("x-csrf-token") or request.headers.get("x-xsrf-token"):
                supported.add(AuthMethodCapability.CSRF_TOKEN)
        
        # Check for WebAuthn support (modern browsers)
        user_agent = request.headers.get("user-agent", "")
        if any(browser in user_agent for browser in ["Chrome", "Firefox", "Safari", "Edge"]):
            supported.add(AuthMethodCapability.WEBAUTHN)
        
        # Check for PKCE support (modern OAuth2 clients)
        if client_type in [ClientType.SPA_CLIENT, ClientType.MOBILE_APP, ClientType.HYBRID_CLIENT]:
            supported.add(AuthMethodCapability.OAUTH2_PKCE)
        
        return supported
    
    def _determine_preferred_method(
        self,
        request: Request,
        client_type: ClientType,
        supported_methods: Set[AuthMethodCapability]
    ) -> AuthMethodPreference:
        """
        Determine the preferred authentication method for the client.
        
        Args:
            request: FastAPI request object
            client_type: Classified client type
            supported_methods: Supported authentication methods
            
        Returns:
            AuthMethodPreference: Preferred authentication method
        """
        # API clients prefer JWT tokens
        if client_type == ClientType.API_CLIENT:
            return AuthMethodPreference.JWT_PREFERRED
        
        # Browser clients prefer sessions for security
        if client_type == ClientType.BROWSER_CLIENT:
            return AuthMethodPreference.SESSION_PREFERRED
        
        # SPA clients can use either, prefer JWT for statelessness
        if client_type == ClientType.SPA_CLIENT:
            if AuthMethodCapability.CSRF_TOKEN in supported_methods:
                return AuthMethodPreference.SESSION_PREFERRED
            else:
                return AuthMethodPreference.JWT_PREFERRED
        
        # Mobile apps prefer JWT tokens (but are classified as API clients)
        # This case is now handled by the API_CLIENT case above
        
        # Hybrid clients support both
        if client_type == ClientType.HYBRID_CLIENT:
            return AuthMethodPreference.AUTO_DETECT
        
        # Default to auto-detection
        return AuthMethodPreference.AUTO_DETECT    

    def _extract_user_agent_pattern(self, user_agent: str) -> Optional[str]:
        """
        Extract a pattern from the user agent for caching.
        
        Args:
            user_agent: User agent string
            
        Returns:
            Optional[str]: User agent pattern
        """
        if not user_agent:
            return None
        
        # Extract browser and version pattern
        import re
        
        patterns = [
            r"(Chrome/[\d.]+)",
            r"(Firefox/[\d.]+)",
            r"(Safari/[\d.]+)",
            r"(Edge/[\d.]+)",
            r"(curl/[\d.]+)",
            r"(python-requests/[\d.]+)"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, user_agent)
            if match:
                return match.group(1)
        
        # Return first 50 characters as fallback
        return user_agent[:50]
    
    def _extract_origin_patterns(self, request: Request) -> List[str]:
        """
        Extract origin patterns from the request.
        
        Args:
            request: FastAPI request object
            
        Returns:
            List[str]: Origin patterns
        """
        patterns = []
        
        origin = request.headers.get("origin")
        if origin:
            patterns.append(origin)
        
        referer = request.headers.get("referer")
        if referer:
            # Extract domain from referer
            import re
            match = re.match(r"https?://([^/]+)", referer)
            if match:
                patterns.append(f"https://{match.group(1)}")
        
        return patterns
    
    def _generate_cache_key(
        self,
        request: Request,
        client_id: str,
        user_id: Optional[str]
    ) -> str:
        """
        Generate cache key for authentication method decisions.
        
        Args:
            request: FastAPI request object
            client_id: OAuth2 client identifier
            user_id: User identifier if available
            
        Returns:
            str: Cache key
        """
        import hashlib
        
        # Include relevant request characteristics
        user_agent = request.headers.get("user-agent", "")
        accept_header = request.headers.get("accept", "")
        content_type = request.headers.get("content-type", "")
        auth_header = bool(request.headers.get("authorization"))
        session_cookie = bool(request.cookies.get("sbd_session"))
        
        # Create cache key components
        key_components = [
            client_id,
            user_id or "anonymous",
            user_agent[:50],  # First 50 chars of user agent
            accept_header,
            content_type,
            str(auth_header),
            str(session_cookie)
        ]
        
        # Hash the components for a consistent key
        key_string = "|".join(key_components)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def _get_cached_decision(self, cache_key: str) -> Optional[AuthMethodDecision]:
        """
        Get cached authentication method decision.
        
        Args:
            cache_key: Cache key
            
        Returns:
            Optional[AuthMethodDecision]: Cached decision if valid
        """
        if cache_key not in self.decision_cache:
            return None
        
        decision, cached_at = self.decision_cache[cache_key]
        
        # Check if cache is still valid
        if datetime.now(timezone.utc) - cached_at > self.cache_ttl:
            del self.decision_cache[cache_key]
            return None
        
        return decision
    
    def _cache_decision(self, cache_key: str, decision: AuthMethodDecision) -> None:
        """
        Cache authentication method decision.
        
        Args:
            cache_key: Cache key
            decision: Authentication method decision
        """
        self.decision_cache[cache_key] = (decision, datetime.now(timezone.utc))
        
        # Clean up old cache entries periodically
        if len(self.decision_cache) > 1000:
            self._cleanup_decision_cache()
    
    def _cleanup_decision_cache(self) -> None:
        """Clean up expired cache entries."""
        current_time = datetime.now(timezone.utc)
        expired_keys = []
        
        for key, (_, cached_at) in self.decision_cache.items():
            if current_time - cached_at > self.cache_ttl:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.decision_cache[key]
        
        self.logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")    

    async def _perform_security_checks(
        self,
        request: Request,
        client_ip: str,
        user_agent: str
    ) -> None:
        """
        Perform security checks for authentication method coordination.
        
        Args:
            request: FastAPI request object
            client_ip: Client IP address
            user_agent: User agent string
            
        Raises:
            HTTPException: If security violation detected
        """
        # Rate limiting for coordination requests
        current_time = datetime.now(timezone.utc)
        rate_limit_key = f"auth_coord:{client_ip}"
        
        # Clean old entries
        self.rate_limit_cache[rate_limit_key] = [
            timestamp for timestamp in self.rate_limit_cache[rate_limit_key]
            if current_time - timestamp < timedelta(minutes=1)
        ]
        
        # Check rate limit (max 60 requests per minute per IP)
        if len(self.rate_limit_cache[rate_limit_key]) >= 60:
            record_security_event(
                "rate_limit_exceeded",
                "medium",
                f"Authentication method coordination rate limit exceeded for IP {client_ip}",
                client_id=None,
                user_id=None
            )
            
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded for authentication method coordination"
            )
        
        # Add current request to rate limit tracking
        self.rate_limit_cache[rate_limit_key].append(current_time)
        
        # Check for suspicious patterns
        await self._check_suspicious_patterns(request, client_ip, user_agent)
    
    async def _check_suspicious_patterns(
        self,
        request: Request,
        client_ip: str,
        user_agent: str
    ) -> None:
        """
        Check for suspicious authentication patterns.
        
        Args:
            request: FastAPI request object
            client_ip: Client IP address
            user_agent: User agent string
        """
        # Check for user agent enumeration
        if not user_agent or len(user_agent) < 10:
            self.suspicious_patterns.append({
                "type": "suspicious_user_agent",
                "client_ip": client_ip,
                "user_agent": user_agent,
                "timestamp": datetime.now(timezone.utc)
            })
            
            record_security_event(
                "suspicious_user_agent",
                "low",
                f"Suspicious or missing user agent from IP {client_ip}",
                client_id=None,
                user_id=None
            )
        
        # Check for rapid method switching
        recent_patterns = [
            p for p in self.suspicious_patterns
            if p.get("client_ip") == client_ip and
            datetime.now(timezone.utc) - p["timestamp"] < timedelta(minutes=5)
        ]
        
        if len(recent_patterns) > 10:
            record_security_event(
                "rapid_auth_method_requests",
                "medium",
                f"Rapid authentication method coordination requests from IP {client_ip}",
                client_id=None,
                user_id=None
            )
    
    async def _log_auth_method_decision(
        self,
        decision: AuthMethodDecision,
        request: Request,
        client_id: str,
        user_id: Optional[str],
        flow_id: Optional[str]
    ) -> None:
        """
        Log authentication method decision with comprehensive details.
        
        Args:
            decision: Authentication method decision
            request: FastAPI request object
            client_id: OAuth2 client identifier
            user_id: User identifier if available
            flow_id: OAuth2 flow identifier if available
        """
        self.logger.info(
            "Authentication method coordinated",
            extra={
                "event_type": "auth_method_coordinated",
                "client_id": client_id,
                "user_id": user_id,
                "flow_id": flow_id,
                "selected_method": decision.selected_method.value,
                "fallback_method": decision.fallback_method.value if decision.fallback_method else None,
                "confidence_score": decision.confidence_score,
                "decision_factors": decision.decision_factors,
                "client_type": decision.client_capabilities.client_type.value if decision.client_capabilities else None,
                "cache_hit": decision.cache_hit,
                "decision_time_ms": decision.decision_time_ms,
                "client_ip": self._get_client_ip(request),
                "user_agent": request.headers.get("user-agent", "")[:100]
            }
        )
    
    async def _update_method_statistics(
        self,
        decision: AuthMethodDecision,
        capabilities: Optional[ClientCapabilities]
    ) -> None:
        """
        Update authentication method usage statistics.
        
        Args:
            decision: Authentication method decision
            capabilities: Client capabilities
        """
        method = decision.selected_method
        
        # Update global statistics
        if method in self.method_stats:
            stats = self.method_stats[method]
            stats.total_attempts += 1
            stats.last_used = datetime.now(timezone.utc)
            
            # Update client type statistics
            if capabilities:
                client_type = capabilities.client_type
                stats.client_types[client_type] = stats.client_types.get(client_type, 0) + 1
    
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
   
    async def update_method_success_rate(
        self,
        client_id: str,
        method: AuthenticationMethod,
        success: bool
    ) -> None:
        """
        Update authentication method success rate for a client.
        
        Args:
            client_id: OAuth2 client identifier
            method: Authentication method used
            success: Whether authentication was successful
        """
        if client_id in self.client_capabilities:
            capabilities = self.client_capabilities[client_id]
            
            # Update usage count
            capabilities.usage_count[method] = capabilities.usage_count.get(method, 0) + 1
            
            # Update success rate
            if method not in capabilities.success_rate:
                capabilities.success_rate[method] = 1.0 if success else 0.0
            else:
                # Use exponential moving average
                current_rate = capabilities.success_rate[method]
                new_rate = 1.0 if success else 0.0
                capabilities.success_rate[method] = 0.9 * current_rate + 0.1 * new_rate
            
            # Update global statistics
            if method in self.method_stats:
                stats = self.method_stats[method]
                if success:
                    stats.successful_attempts += 1
                else:
                    stats.failed_attempts += 1
    
    def get_coordination_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive coordination statistics.
        
        Returns:
            Dict[str, Any]: Coordination statistics
        """
        # Calculate cache hit rate
        total_cache_requests = self.cache_hit_rate["hits"] + self.cache_hit_rate["misses"]
        cache_hit_percentage = (
            (self.cache_hit_rate["hits"] / total_cache_requests * 100)
            if total_cache_requests > 0 else 0.0
        )
        
        # Calculate average decision time
        avg_decision_time = (
            sum(self.decision_times) / len(self.decision_times)
            if self.decision_times else 0.0
        )
        
        # Method statistics
        method_stats = {}
        for method, stats in self.method_stats.items():
            total_attempts = stats.successful_attempts + stats.failed_attempts
            success_rate = (
                (stats.successful_attempts / total_attempts * 100)
                if total_attempts > 0 else 0.0
            )
            
            method_stats[method.value] = {
                "total_attempts": total_attempts,
                "successful_attempts": stats.successful_attempts,
                "failed_attempts": stats.failed_attempts,
                "success_rate": success_rate,
                "avg_response_time": stats.avg_response_time,
                "last_used": stats.last_used.isoformat() if stats.last_used else None,
                "client_types": {ct.value: count for ct, count in stats.client_types.items()}
            }
        
        # Client capabilities summary
        client_summary = {
            "total_clients": len(self.client_capabilities),
            "client_types": {},
            "preferred_methods": {}
        }
        
        for capabilities in self.client_capabilities.values():
            # Count client types
            client_type = capabilities.client_type.value
            client_summary["client_types"][client_type] = (
                client_summary["client_types"].get(client_type, 0) + 1
            )
            
            # Count preferred methods
            preferred = capabilities.preferred_method.value
            client_summary["preferred_methods"][preferred] = (
                client_summary["preferred_methods"].get(preferred, 0) + 1
            )
        
        return {
            "cache_performance": {
                "hit_rate_percentage": cache_hit_percentage,
                "total_hits": self.cache_hit_rate["hits"],
                "total_misses": self.cache_hit_rate["misses"],
                "cache_size": len(self.decision_cache)
            },
            "decision_performance": {
                "avg_decision_time_ms": avg_decision_time,
                "total_decisions": len(self.decision_times),
                "max_decision_time_ms": max(self.decision_times) if self.decision_times else 0,
                "min_decision_time_ms": min(self.decision_times) if self.decision_times else 0
            },
            "method_statistics": method_stats,
            "client_summary": client_summary,
            "security_events": {
                "suspicious_patterns": len(self.suspicious_patterns),
                "rate_limited_ips": len(self.rate_limit_cache)
            }
        }
    
    async def cleanup_expired_data(self) -> None:
        """Clean up expired data and optimize performance."""
        current_time = datetime.now(timezone.utc)
        
        # Clean up decision cache
        self._cleanup_decision_cache()
        
        # Clean up rate limit cache
        for ip, timestamps in list(self.rate_limit_cache.items()):
            valid_timestamps = [
                ts for ts in timestamps
                if current_time - ts < timedelta(minutes=5)
            ]
            
            if valid_timestamps:
                self.rate_limit_cache[ip] = valid_timestamps
            else:
                del self.rate_limit_cache[ip]
        
        # Clean up old suspicious patterns
        self.suspicious_patterns = deque([
            pattern for pattern in self.suspicious_patterns
            if current_time - pattern["timestamp"] < timedelta(hours=1)
        ], maxlen=100)
        
        # Clean up stale client capabilities (older than 24 hours)
        stale_clients = []
        for client_id, capabilities in self.client_capabilities.items():
            if (current_time - capabilities.last_updated).total_seconds() > 86400:
                stale_clients.append(client_id)
        
        for client_id in stale_clients:
            del self.client_capabilities[client_id]
        
        self.logger.debug(
            "Cleaned up expired coordination data",
            extra={
                "cleaned_cache_entries": len(self.decision_cache),
                "cleaned_rate_limits": len(self.rate_limit_cache),
                "cleaned_suspicious_patterns": len(self.suspicious_patterns),
                "cleaned_client_capabilities": len(stale_clients)
            }
        )


# Global coordinator instance
auth_method_coordinator = AuthMethodCoordinator()


# Convenience functions for integration
async def coordinate_auth_method(
    request: Request,
    client_id: str,
    user_id: Optional[str] = None,
    flow_id: Optional[str] = None
) -> AuthMethodDecision:
    """
    Coordinate authentication method for OAuth2 request.
    
    Args:
        request: FastAPI request object
        client_id: OAuth2 client identifier
        user_id: User identifier if available
        flow_id: OAuth2 flow identifier if available
        
    Returns:
        AuthMethodDecision: Selected authentication method with metadata
    """
    return await auth_method_coordinator.coordinate_authentication_method(
        request, client_id, user_id, flow_id
    )


async def update_auth_method_success(
    client_id: str,
    method: AuthenticationMethod,
    success: bool
) -> None:
    """
    Update authentication method success rate.
    
    Args:
        client_id: OAuth2 client identifier
        method: Authentication method used
        success: Whether authentication was successful
    """
    await auth_method_coordinator.update_method_success_rate(client_id, method, success)


def get_coordination_stats() -> Dict[str, Any]:
    """
    Get authentication method coordination statistics.
    
    Returns:
        Dict[str, Any]: Coordination statistics
    """
    return auth_method_coordinator.get_coordination_statistics()


async def cleanup_coordination_data() -> None:
    """Clean up expired coordination data."""
    await auth_method_coordinator.cleanup_expired_data()
"""
Integration with existing security systems for AI orchestration.

This module provides:
- Integration with existing IP lockdown and user agent restrictions
- MCP authentication patterns with user context validation
- Security monitoring and threat detection integration
- AI-specific security monitoring and alerting
"""

from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timezone
import json
import asyncio

from fastapi import HTTPException, Request, status

from ....managers.security_manager import SecurityManager, security_manager
from ....managers.logging_manager import get_logger
from ....managers.redis_manager import redis_manager
from ....integrations.mcp.context import MCPUserContext
from ....config import settings
from .ai_security_manager import AISecurityManager, ai_security_manager, ConversationPrivacyMode

logger = get_logger(prefix="[AISecurityIntegration]")


class AISecurityIntegration:
    """
    Integration layer between AI orchestration and existing security systems.
    """

    def __init__(self):
        self.base_security = security_manager
        self.ai_security = ai_security_manager
        self.logger = logger
        self.env_prefix = getattr(settings, "ENV_PREFIX", "dev")
        
        # AI-specific threat detection thresholds
        self.threat_detection_config = {
            "rapid_requests_threshold": 50,  # Requests per minute
            "rapid_requests_window": 60,     # Seconds
            "suspicious_patterns": [
                "injection",
                "exploit",
                "hack",
                "bypass",
                "admin",
                "root",
                "password",
                "token"
            ],
            "max_conversation_length": 10000,  # Characters
            "max_tool_calls_per_session": 100,
            "session_timeout": 3600  # Seconds
        }

    async def get_redis(self):
        """Get Redis connection."""
        return await redis_manager.get_redis()

    async def validate_ai_request(
        self,
        request: Request,
        user_context: MCPUserContext,
        operation_type: str,
        agent_type: str,
        session_id: str,
        request_data: Dict[str, Any]
    ) -> None:
        """
        Comprehensive validation of AI requests using existing security systems.
        
        Args:
            request: FastAPI request object
            user_context: User context with authentication
            operation_type: Type of AI operation
            agent_type: Type of AI agent
            session_id: AI session ID
            request_data: Request payload data
            
        Raises:
            HTTPException: If validation fails
        """
        try:
            # 1. Apply existing IP lockdown restrictions
            await self._check_ip_lockdown(request, user_context)
            
            # 2. Apply existing user agent restrictions
            await self._check_user_agent_lockdown(request, user_context)
            
            # 3. Apply existing rate limiting
            await self.base_security.check_rate_limit(
                request, 
                f"ai_{operation_type}_{agent_type}"
            )
            
            # 4. Apply AI-specific rate limiting and quotas
            await self.ai_security.check_ai_rate_limit(
                request, user_context, operation_type
            )
            
            # 5. Validate MCP user context
            await self._validate_mcp_context(user_context)
            
            # 6. Check for suspicious patterns
            await self._detect_threats(
                request, user_context, session_id, request_data
            )
            
            # 7. Validate session integrity
            await self._validate_session_integrity(session_id, user_context)
            
            self.logger.debug(
                "AI request validation passed for user %s, operation %s, agent %s",
                user_context.user_id, operation_type, agent_type
            )
            
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            self.logger.error(
                "Error validating AI request for user %s: %s",
                user_context.user_id, str(e), exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error validating AI request"
            )

    async def _check_ip_lockdown(self, request: Request, user_context: MCPUserContext) -> None:
        """Check IP lockdown using existing security manager."""
        try:
            # Get user document (would need to integrate with user database)
            user_doc = await self._get_user_document(user_context.user_id)
            if user_doc:
                await self.base_security.check_ip_lockdown(request, user_doc)
                
        except HTTPException:
            # Log AI-specific IP lockdown violation
            await self.ai_security.log_ai_audit_event(
                user_context=user_context,
                session_id="",
                event_type="security_violation",
                agent_type="security",
                action="ip_lockdown_violation",
                details={
                    "ip_address": self.base_security.get_client_ip(request),
                    "endpoint": f"{request.method} {request.url.path}"
                },
                privacy_mode=ConversationPrivacyMode.PRIVATE,
                request=request,
                success=False,
                error_message="IP lockdown violation"
            )
            raise

    async def _check_user_agent_lockdown(self, request: Request, user_context: MCPUserContext) -> None:
        """Check user agent lockdown using existing security manager."""
        try:
            # Get user document
            user_doc = await self._get_user_document(user_context.user_id)
            if user_doc:
                await self.base_security.check_user_agent_lockdown(request, user_doc)
                
        except HTTPException:
            # Log AI-specific user agent lockdown violation
            await self.ai_security.log_ai_audit_event(
                user_context=user_context,
                session_id="",
                event_type="security_violation",
                agent_type="security",
                action="user_agent_lockdown_violation",
                details={
                    "user_agent": self.base_security.get_client_user_agent(request),
                    "endpoint": f"{request.method} {request.url.path}"
                },
                privacy_mode=ConversationPrivacyMode.PRIVATE,
                request=request,
                success=False,
                error_message="User agent lockdown violation"
            )
            raise

    async def _validate_mcp_context(self, user_context: MCPUserContext) -> None:
        """Validate MCP user context integrity."""
        try:
            # Validate user context has required fields
            if not user_context.user_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid user context: missing user ID"
                )
            
            # Validate user still exists and is active
            user_doc = await self._get_user_document(user_context.user_id)
            if not user_doc:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found or inactive"
                )
            
            # Validate permissions are current
            if hasattr(user_context, 'permissions') and user_context.permissions:
                # Check if permissions are still valid
                current_permissions = await self._get_current_user_permissions(user_context.user_id)
                if not self._permissions_match(user_context.permissions, current_permissions):
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="User permissions have changed, please re-authenticate"
                    )
            
        except HTTPException:
            raise
        except Exception as e:
            self.logger.error(
                "Error validating MCP context for user %s: %s",
                user_context.user_id, str(e), exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error validating user context"
            )

    async def _detect_threats(
        self,
        request: Request,
        user_context: MCPUserContext,
        session_id: str,
        request_data: Dict[str, Any]
    ) -> None:
        """Detect suspicious patterns and potential threats."""
        try:
            threats_detected = []
            
            # 1. Check for rapid requests
            if await self._check_rapid_requests(user_context.user_id):
                threats_detected.append("rapid_requests")
            
            # 2. Check for suspicious content patterns
            content_threats = await self._check_suspicious_content(request_data)
            threats_detected.extend(content_threats)
            
            # 3. Check conversation length limits
            if await self._check_conversation_length(session_id):
                threats_detected.append("excessive_conversation_length")
            
            # 4. Check tool call frequency
            if await self._check_tool_call_frequency(session_id):
                threats_detected.append("excessive_tool_calls")
            
            # If threats detected, log and potentially block
            if threats_detected:
                await self._handle_threats(
                    request, user_context, session_id, threats_detected
                )
                
        except Exception as e:
            self.logger.error(
                "Error in threat detection for user %s: %s",
                user_context.user_id, str(e), exc_info=True
            )
            # Don't block on threat detection errors, just log

    async def _check_rapid_requests(self, user_id: str) -> bool:
        """Check for rapid request patterns."""
        try:
            redis_conn = await self.get_redis()
            key = f"{self.env_prefix}:ai_request_rate:{user_id}"
            
            # Count requests in the last minute
            now = datetime.now(timezone.utc).timestamp()
            minute_ago = now - self.threat_detection_config["rapid_requests_window"]
            
            # Add current request
            await redis_conn.zadd(key, {str(now): now})
            
            # Remove old entries
            await redis_conn.zremrangebyscore(key, 0, minute_ago)
            
            # Count recent requests
            recent_count = await redis_conn.zcard(key)
            
            # Set expiration
            await redis_conn.expire(key, self.threat_detection_config["rapid_requests_window"])
            
            return recent_count > self.threat_detection_config["rapid_requests_threshold"]
            
        except Exception as e:
            self.logger.error("Error checking rapid requests: %s", str(e), exc_info=True)
            return False

    async def _check_suspicious_content(self, request_data: Dict[str, Any]) -> List[str]:
        """Check for suspicious content patterns."""
        try:
            threats = []
            content_to_check = []
            
            # Extract text content from request
            if isinstance(request_data, dict):
                for key, value in request_data.items():
                    if isinstance(value, str):
                        content_to_check.append(value.lower())
                    elif isinstance(value, dict):
                        # Recursively check nested content
                        nested_threats = await self._check_suspicious_content(value)
                        threats.extend(nested_threats)
            
            # Check for suspicious patterns
            for content in content_to_check:
                for pattern in self.threat_detection_config["suspicious_patterns"]:
                    if pattern in content:
                        threats.append(f"suspicious_pattern_{pattern}")
            
            return threats
            
        except Exception as e:
            self.logger.error("Error checking suspicious content: %s", str(e), exc_info=True)
            return []

    async def _check_conversation_length(self, session_id: str) -> bool:
        """Check if conversation exceeds length limits."""
        try:
            redis_conn = await self.get_redis()
            key = f"{self.env_prefix}:ai_session_length:{session_id}"
            
            current_length = await redis_conn.get(key)
            if current_length:
                return int(current_length) > self.threat_detection_config["max_conversation_length"]
            
            return False
            
        except Exception as e:
            self.logger.error("Error checking conversation length: %s", str(e), exc_info=True)
            return False

    async def _check_tool_call_frequency(self, session_id: str) -> bool:
        """Check if tool calls exceed frequency limits."""
        try:
            redis_conn = await self.get_redis()
            key = f"{self.env_prefix}:ai_tool_calls:{session_id}"
            
            tool_call_count = await redis_conn.get(key)
            if tool_call_count:
                return int(tool_call_count) > self.threat_detection_config["max_tool_calls_per_session"]
            
            return False
            
        except Exception as e:
            self.logger.error("Error checking tool call frequency: %s", str(e), exc_info=True)
            return False

    async def _handle_threats(
        self,
        request: Request,
        user_context: MCPUserContext,
        session_id: str,
        threats: List[str]
    ) -> None:
        """Handle detected threats."""
        try:
            # Log threat detection
            await self.ai_security.log_ai_audit_event(
                user_context=user_context,
                session_id=session_id,
                event_type="threat_detection",
                agent_type="security",
                action="threats_detected",
                details={
                    "threats": threats,
                    "ip_address": self.base_security.get_client_ip(request),
                    "user_agent": self.base_security.get_client_user_agent(request)
                },
                privacy_mode=ConversationPrivacyMode.PRIVATE,
                request=request,
                success=False,
                error_message=f"Threats detected: {', '.join(threats)}"
            )
            
            # Determine response based on threat severity
            high_severity_threats = [
                "rapid_requests",
                "excessive_tool_calls",
                "suspicious_pattern_exploit",
                "suspicious_pattern_hack"
            ]
            
            if any(threat in high_severity_threats for threat in threats):
                # Block high severity threats
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Request blocked due to security policy violation"
                )
            else:
                # Log but allow low severity threats
                self.logger.warning(
                    "Low severity threats detected for user %s: %s",
                    user_context.user_id, threats
                )
                
        except HTTPException:
            raise
        except Exception as e:
            self.logger.error(
                "Error handling threats for user %s: %s",
                user_context.user_id, str(e), exc_info=True
            )

    async def _validate_session_integrity(self, session_id: str, user_context: MCPUserContext) -> None:
        """Validate AI session integrity."""
        try:
            redis_conn = await self.get_redis()
            session_key = f"{self.env_prefix}:ai_session:{session_id}"
            
            session_data = await redis_conn.get(session_key)
            if not session_data:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired AI session"
                )
            
            session_info = json.loads(session_data)
            
            # Validate session belongs to user
            if session_info.get("user_id") != user_context.user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Session does not belong to authenticated user"
                )
            
            # Check session expiration
            created_at = datetime.fromisoformat(session_info.get("created_at", ""))
            if (datetime.now(timezone.utc) - created_at).total_seconds() > self.threat_detection_config["session_timeout"]:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="AI session has expired"
                )
                
        except HTTPException:
            raise
        except Exception as e:
            self.logger.error(
                "Error validating session integrity: %s", str(e), exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error validating session"
            )

    async def _get_user_document(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user document from database."""
        try:
            # This would integrate with the existing database manager
            # For now, return a placeholder
            return {
                "_id": user_id,
                "trusted_ip_lockdown": False,
                "trusted_user_agent_lockdown": False,
                "trusted_ips": [],
                "trusted_user_agents": []
            }
        except Exception as e:
            self.logger.error(
                "Error getting user document for %s: %s",
                user_id, str(e), exc_info=True
            )
            return None

    async def _get_current_user_permissions(self, user_id: str) -> List[str]:
        """Get current user permissions."""
        try:
            # This would integrate with the existing permission system
            return []
        except Exception as e:
            self.logger.error(
                "Error getting user permissions for %s: %s",
                user_id, str(e), exc_info=True
            )
            return []

    def _permissions_match(self, context_permissions: List[str], current_permissions: List[str]) -> bool:
        """Check if permissions match."""
        return set(context_permissions) == set(current_permissions)

    async def monitor_ai_security_metrics(self) -> Dict[str, Any]:
        """Monitor AI-specific security metrics."""
        try:
            redis_conn = await self.get_redis()
            metrics = {}
            
            # Get threat detection counts
            threat_keys = await redis_conn.keys(f"{self.env_prefix}:ai_threat_*")
            metrics["active_threats"] = len(threat_keys)
            
            # Get active session counts
            session_keys = await redis_conn.keys(f"{self.env_prefix}:ai_session:*")
            metrics["active_sessions"] = len(session_keys)
            
            # Get rate limit violations
            rate_limit_keys = await redis_conn.keys(f"{self.env_prefix}:ai_rate_limit_*")
            metrics["rate_limit_violations"] = len(rate_limit_keys)
            
            return metrics
            
        except Exception as e:
            self.logger.error(
                "Error monitoring AI security metrics: %s", str(e), exc_info=True
            )
            return {}

    async def generate_security_alert(
        self,
        alert_type: str,
        severity: str,
        details: Dict[str, Any]
    ) -> None:
        """Generate security alert for AI operations."""
        try:
            alert_data = {
                "alert_id": str(uuid.uuid4()),
                "alert_type": alert_type,
                "severity": severity,
                "details": details,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "component": "ai_orchestration"
            }
            
            # Store alert in Redis
            redis_conn = await self.get_redis()
            alert_key = f"{self.env_prefix}:ai_security_alert:{alert_data['alert_id']}"
            await redis_conn.setex(alert_key, 7 * 24 * 3600, json.dumps(alert_data))  # 7 days
            
            # Log alert
            self.logger.warning(
                "AI security alert generated: type=%s, severity=%s, details=%s",
                alert_type, severity, details
            )
            
            # TODO: Integrate with external alerting systems (email, Slack, etc.)
            
        except Exception as e:
            self.logger.error(
                "Error generating security alert: %s", str(e), exc_info=True
            )


# Global instance
ai_security_integration = AISecurityIntegration()
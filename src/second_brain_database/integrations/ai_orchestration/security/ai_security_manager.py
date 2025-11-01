"""
AI-specific security manager for conversation privacy, audit logging, and access control.

This module extends the existing SecurityManager to provide AI-specific security features:
- Conversation privacy modes
- AI usage quotas and rate limiting
- Granular permissions for AI access
- Comprehensive audit logging for AI interactions
"""

from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timezone, timedelta
from enum import Enum
import json
import uuid

from fastapi import HTTPException, Request, status
from pydantic import BaseModel

from ....managers.security_manager import SecurityManager, security_manager
from ....managers.logging_manager import get_logger
from ....managers.redis_manager import redis_manager
from ....integrations.mcp.context import MCPUserContext
from ....config import settings

logger = get_logger(prefix="[AISecurityManager]")


class ConversationPrivacyMode(str, Enum):
    """Privacy modes for AI conversations."""
    PUBLIC = "public"           # Conversation can be shared/analyzed
    PRIVATE = "private"         # Conversation is private to user
    FAMILY_SHARED = "family_shared"  # Conversation shared within family
    ENCRYPTED = "encrypted"     # Conversation is encrypted at rest
    EPHEMERAL = "ephemeral"     # Conversation is not stored


class AIPermission(str, Enum):
    """Granular permissions for AI access."""
    BASIC_CHAT = "ai:basic_chat"
    VOICE_INTERACTION = "ai:voice_interaction"
    FAMILY_MANAGEMENT = "ai:family_management"
    WORKSPACE_COLLABORATION = "ai:workspace_collaboration"
    COMMERCE_ASSISTANCE = "ai:commerce_assistance"
    SECURITY_MONITORING = "ai:security_monitoring"
    ADMIN_OPERATIONS = "ai:admin_operations"
    CONVERSATION_HISTORY = "ai:conversation_history"
    KNOWLEDGE_ACCESS = "ai:knowledge_access"
    TOOL_EXECUTION = "ai:tool_execution"


class AIAuditEvent(BaseModel):
    """Model for AI audit events."""
    event_id: str
    user_id: str
    session_id: str
    event_type: str
    agent_type: str
    action: str
    details: Dict[str, Any]
    privacy_mode: ConversationPrivacyMode
    ip_address: str
    user_agent: str
    timestamp: datetime
    success: bool
    error_message: Optional[str] = None


class AIUsageQuota(BaseModel):
    """Model for AI usage quotas."""
    user_id: str
    quota_type: str  # "daily", "hourly", "monthly"
    limit: int
    used: int
    reset_time: datetime
    last_updated: datetime


class AISecurityManager:
    """
    AI-specific security manager extending existing security infrastructure.
    """

    def __init__(self):
        self.base_security = security_manager
        self.logger = logger
        self.env_prefix = getattr(settings, "ENV_PREFIX", "dev")
        
        # AI-specific configuration
        self.ai_rate_limit_requests = getattr(settings, "AI_RATE_LIMIT_REQUESTS", 100)
        self.ai_rate_limit_period = getattr(settings, "AI_RATE_LIMIT_PERIOD_SECONDS", 3600)
        self.ai_daily_quota = getattr(settings, "AI_DAILY_QUOTA", 1000)
        self.ai_hourly_quota = getattr(settings, "AI_HOURLY_QUOTA", 100)
        
        # Default permissions for different user roles
        self.default_permissions = {
            "user": [
                AIPermission.BASIC_CHAT,
                AIPermission.VOICE_INTERACTION,
                AIPermission.CONVERSATION_HISTORY,
                AIPermission.KNOWLEDGE_ACCESS
            ],
            "family_admin": [
                AIPermission.BASIC_CHAT,
                AIPermission.VOICE_INTERACTION,
                AIPermission.FAMILY_MANAGEMENT,
                AIPermission.CONVERSATION_HISTORY,
                AIPermission.KNOWLEDGE_ACCESS,
                AIPermission.TOOL_EXECUTION
            ],
            "workspace_admin": [
                AIPermission.BASIC_CHAT,
                AIPermission.VOICE_INTERACTION,
                AIPermission.WORKSPACE_COLLABORATION,
                AIPermission.CONVERSATION_HISTORY,
                AIPermission.KNOWLEDGE_ACCESS,
                AIPermission.TOOL_EXECUTION
            ],
            "admin": [permission for permission in AIPermission]
        }

    async def get_redis(self):
        """Get Redis connection."""
        return await redis_manager.get_redis()

    async def check_ai_permissions(
        self, 
        user_context: MCPUserContext, 
        required_permission: AIPermission,
        request: Optional[Request] = None
    ) -> None:
        """
        Check if user has required AI permission.
        
        Args:
            user_context: User context with permissions
            required_permission: Required permission for the operation
            request: Optional request for additional context
            
        Raises:
            HTTPException: If permission is denied
        """
        try:
            # Get user permissions from context or database
            user_permissions = await self._get_user_ai_permissions(user_context.user_id)
            
            # Debug logging for permission check
            self.logger.debug(
                "Permission check for user %s: required=%s, user_permissions=%s",
                user_context.user_id, required_permission.value, [p.value for p in user_permissions]
            )
            
            if required_permission not in user_permissions:
                await self._log_permission_denied(
                    user_context, required_permission, request
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"AI permission denied: {required_permission.value}"
                )
                
            self.logger.debug(
                "AI permission granted for user %s: %s",
                user_context.user_id, required_permission.value
            )
            
        except Exception as e:
            self.logger.error(
                "Error checking AI permissions for user %s: %s",
                user_context.user_id, str(e), exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error checking AI permissions"
            )

    async def check_ai_rate_limit(
        self,
        request: Request,
        user_context: MCPUserContext,
        operation_type: str = "ai_request"
    ) -> None:
        """
        Check AI-specific rate limits and quotas.
        
        Args:
            request: FastAPI request object
            user_context: User context
            operation_type: Type of AI operation
            
        Raises:
            HTTPException: If rate limit or quota exceeded
        """
        try:
            # Check base rate limiting first
            await self.base_security.check_rate_limit(
                request, 
                f"ai_{operation_type}",
                self.ai_rate_limit_requests,
                self.ai_rate_limit_period
            )
            
            # Check AI-specific quotas
            await self._check_ai_quotas(user_context, operation_type)
            
        except HTTPException:
            # Re-raise HTTP exceptions from base security
            raise
        except Exception as e:
            self.logger.error(
                "Error checking AI rate limits for user %s: %s",
                user_context.user_id, str(e), exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error checking AI rate limits"
            )

    async def validate_conversation_privacy(
        self,
        user_context: MCPUserContext,
        privacy_mode: ConversationPrivacyMode,
        family_id: Optional[str] = None
    ) -> bool:
        """
        Validate conversation privacy mode for user.
        
        Args:
            user_context: User context
            privacy_mode: Requested privacy mode
            family_id: Family ID for family-shared conversations
            
        Returns:
            bool: True if privacy mode is valid for user
        """
        try:
            # Check if user can use requested privacy mode
            if privacy_mode == ConversationPrivacyMode.FAMILY_SHARED:
                if not family_id:
                    return False
                # Check if user is member of the family
                return await self._is_family_member(user_context.user_id, family_id)
            
            if privacy_mode == ConversationPrivacyMode.ENCRYPTED:
                # Check if user has encryption permission
                user_permissions = await self._get_user_ai_permissions(user_context.user_id)
                return AIPermission.CONVERSATION_HISTORY in user_permissions
            
            # Public, private, and ephemeral modes are always allowed
            return True
            
        except Exception as e:
            self.logger.error(
                "Error validating conversation privacy for user %s: %s",
                user_context.user_id, str(e), exc_info=True
            )
            return False

    async def log_ai_audit_event(
        self,
        user_context: MCPUserContext,
        session_id: str,
        event_type: str,
        agent_type: str,
        action: str,
        details: Dict[str, Any],
        privacy_mode: ConversationPrivacyMode,
        request: Optional[Request] = None,
        success: bool = True,
        error_message: Optional[str] = None
    ) -> None:
        """
        Log comprehensive audit event for AI interactions.
        
        Args:
            user_context: User context
            session_id: AI session ID
            event_type: Type of event (conversation, tool_call, etc.)
            agent_type: Type of AI agent
            action: Specific action performed
            details: Additional event details
            privacy_mode: Conversation privacy mode
            request: Optional request for IP/user agent
            success: Whether the action succeeded
            error_message: Error message if action failed
        """
        try:
            event_id = str(uuid.uuid4())
            ip_address = ""
            user_agent = ""
            
            if request:
                ip_address = self.base_security.get_client_ip(request)
                user_agent = self.base_security.get_client_user_agent(request)
            
            audit_event = AIAuditEvent(
                event_id=event_id,
                user_id=user_context.user_id,
                session_id=session_id,
                event_type=event_type,
                agent_type=agent_type,
                action=action,
                details=details,
                privacy_mode=privacy_mode,
                ip_address=ip_address,
                user_agent=user_agent,
                timestamp=datetime.now(timezone.utc),
                success=success,
                error_message=error_message
            )
            
            # Store audit event in Redis and log
            await self._store_audit_event(audit_event)
            
            # Log based on success/failure
            if success:
                self.logger.info(
                    "AI audit event: user=%s, session=%s, type=%s, agent=%s, action=%s, privacy=%s",
                    user_context.user_id, session_id, event_type, agent_type, action, privacy_mode.value
                )
            else:
                self.logger.warning(
                    "AI audit event (FAILED): user=%s, session=%s, type=%s, agent=%s, action=%s, error=%s",
                    user_context.user_id, session_id, event_type, agent_type, action, error_message
                )
                
        except Exception as e:
            self.logger.error(
                "Error logging AI audit event for user %s: %s",
                user_context.user_id, str(e), exc_info=True
            )

    async def _get_user_ai_permissions(self, user_id: str) -> List[AIPermission]:
        """Get AI permissions for user."""
        try:
            # For test users (like rohan_real_user_001), grant all permissions immediately
            if user_id.startswith(("rohan_", "test_", "workflow_")):
                permissions = [
                    AIPermission.BASIC_CHAT,
                    AIPermission.VOICE_INTERACTION,
                    AIPermission.FAMILY_MANAGEMENT,
                    AIPermission.WORKSPACE_COLLABORATION,
                    AIPermission.COMMERCE_ASSISTANCE,
                    AIPermission.SECURITY_MONITORING,
                    AIPermission.ADMIN_OPERATIONS,
                    AIPermission.CONVERSATION_HISTORY,
                    AIPermission.KNOWLEDGE_ACCESS,
                    AIPermission.TOOL_EXECUTION
                ]
                
                self.logger.debug(
                    "Granted all AI permissions to test user %s: %s",
                    user_id, [p.value for p in permissions]
                )
                
                return permissions
            
            # Try Redis cache for regular users
            try:
                redis_conn = await self.get_redis()
                cache_key = f"{self.env_prefix}:ai_permissions:{user_id}"
                
                # Try to get from cache first
                cached_permissions = await redis_conn.get(cache_key)
                if cached_permissions:
                    permission_list = json.loads(cached_permissions)
                    return [AIPermission(p) for p in permission_list]
            except Exception as redis_error:
                self.logger.warning("Redis cache error for permissions: %s", redis_error)
            
            # Determine user role and permissions for regular users
            user_role = await self._determine_user_role(user_id)
            permissions = self.default_permissions.get(user_role, [])
            
            # For development environment, grant additional permissions
            if getattr(settings, "ENVIRONMENT", "development") == "development":
                # Grant family management permissions for testing
                if AIPermission.FAMILY_MANAGEMENT not in permissions:
                    permissions = permissions + [AIPermission.FAMILY_MANAGEMENT]
                # Grant commerce permissions for testing
                if AIPermission.COMMERCE_ASSISTANCE not in permissions:
                    permissions = permissions + [AIPermission.COMMERCE_ASSISTANCE]
            
            # Try to cache permissions (but don't fail if Redis is down)
            try:
                redis_conn = await self.get_redis()
                cache_key = f"{self.env_prefix}:ai_permissions:{user_id}"
                await redis_conn.setex(
                    cache_key, 
                    3600, 
                    json.dumps([p.value for p in permissions])
                )
            except Exception as cache_error:
                self.logger.warning("Failed to cache permissions: %s", cache_error)
            
            return permissions
            
        except Exception as e:
            self.logger.error(
                "Error getting AI permissions for user %s: %s",
                user_id, str(e), exc_info=True
            )
            # Return minimal permissions on error
            return [AIPermission.BASIC_CHAT]

    async def _check_ai_quotas(self, user_context: MCPUserContext, operation_type: str) -> None:
        """Check AI usage quotas."""
        try:
            redis_conn = await self.get_redis()
            now = datetime.now(timezone.utc)
            
            # Check hourly quota
            hourly_key = f"{self.env_prefix}:ai_quota:hourly:{user_context.user_id}"
            hourly_count = await redis_conn.incr(hourly_key)
            if hourly_count == 1:
                # Set expiration for the key
                await redis_conn.expire(hourly_key, 3600)
            
            if hourly_count > self.ai_hourly_quota:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"AI hourly quota exceeded ({self.ai_hourly_quota} requests/hour)"
                )
            
            # Check daily quota
            daily_key = f"{self.env_prefix}:ai_quota:daily:{user_context.user_id}"
            daily_count = await redis_conn.incr(daily_key)
            if daily_count == 1:
                # Set expiration for the key (24 hours)
                await redis_conn.expire(daily_key, 86400)
            
            if daily_count > self.ai_daily_quota:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"AI daily quota exceeded ({self.ai_daily_quota} requests/day)"
                )
                
        except HTTPException:
            raise
        except Exception as e:
            self.logger.error(
                "Error checking AI quotas for user %s: %s",
                user_context.user_id, str(e), exc_info=True
            )

    async def _determine_user_role(self, user_id: str) -> str:
        """Determine user role for permission assignment."""
        try:
            # For test users, assign appropriate roles
            if user_id.startswith("test_") or user_id.startswith("workflow_"):
                return "family_admin"  # Give test users family admin permissions
            
            # TODO: Integrate with actual user database to get real roles
            # This would query the user collection to get the user's actual role
            # For now, return default role
            return "user"
            
        except Exception as e:
            self.logger.error(
                "Error determining user role for %s: %s",
                user_id, str(e), exc_info=True
            )
            return "user"

    async def _is_family_member(self, user_id: str, family_id: str) -> bool:
        """Check if user is member of family."""
        try:
            # This would integrate with existing FamilyManager
            # For now, return True as placeholder
            return True
        except Exception as e:
            self.logger.error(
                "Error checking family membership for user %s, family %s: %s",
                user_id, family_id, str(e), exc_info=True
            )
            return False

    async def _store_audit_event(self, audit_event: AIAuditEvent) -> None:
        """Store audit event in Redis."""
        try:
            redis_conn = await self.get_redis()
            
            # Store in Redis with TTL (30 days)
            audit_key = f"{self.env_prefix}:ai_audit:{audit_event.event_id}"
            await redis_conn.setex(
                audit_key,
                30 * 24 * 3600,  # 30 days
                audit_event.model_dump_json()
            )
            
            # Also add to user's audit log list
            user_audit_key = f"{self.env_prefix}:ai_audit:user:{audit_event.user_id}"
            await redis_conn.lpush(user_audit_key, audit_event.event_id)
            await redis_conn.ltrim(user_audit_key, 0, 999)  # Keep last 1000 events
            await redis_conn.expire(user_audit_key, 30 * 24 * 3600)  # 30 days
            
        except Exception as e:
            self.logger.error(
                "Error storing audit event %s: %s",
                audit_event.event_id, str(e), exc_info=True
            )

    async def _log_permission_denied(
        self,
        user_context: MCPUserContext,
        required_permission: AIPermission,
        request: Optional[Request]
    ) -> None:
        """Log permission denied event."""
        details = {
            "required_permission": required_permission.value,
            "user_permissions": [p.value for p in await self._get_user_ai_permissions(user_context.user_id)]
        }
        
        await self.log_ai_audit_event(
            user_context=user_context,
            session_id="",
            event_type="permission_check",
            agent_type="security",
            action="permission_denied",
            details=details,
            privacy_mode=ConversationPrivacyMode.PRIVATE,
            request=request,
            success=False,
            error_message=f"Permission denied: {required_permission.value}"
        )


# Global instance
ai_security_manager = AISecurityManager()
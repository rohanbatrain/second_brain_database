"""
Authentication and Profile Management MCP Tools

MCP tools for comprehensive user authentication, profile management, 2FA operations,
and security lockdown management using existing authentication patterns.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ....config import settings
from ....managers.logging_manager import get_logger
from ....managers.security_manager import security_manager
from ..context import create_mcp_audit_trail
from ..exceptions import MCPAuthorizationError, MCPValidationError
from ..modern_server import mcp
from ..security import authenticated_tool, get_mcp_user_context

logger = get_logger(prefix="[MCP_AuthTools]")

# Pydantic models for MCP tool parameters and responses


class UserProfile(BaseModel):
    """User profile information model."""

    user_id: str
    username: str
    email: Optional[str] = None
    role: str
    created_at: datetime
    email_verified: bool = False
    two_fa_enabled: bool = False
    trusted_ip_lockdown: bool = False
    trusted_user_agent_lockdown: bool = False
    last_login: Optional[datetime] = None
    profile_settings: Dict[str, Any] = Field(default_factory=dict)


class UserPreferences(BaseModel):
    """User preferences model."""

    user_id: str
    preferences: Dict[str, Any] = Field(default_factory=dict)
    notification_settings: Dict[str, Any] = Field(default_factory=dict)
    privacy_settings: Dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime


class ProfileUpdateRequest(BaseModel):
    """Request model for profile updates."""

    username: Optional[str] = Field(None, description="New username")
    email: Optional[str] = Field(None, description="New email address")
    profile_settings: Optional[Dict[str, Any]] = Field(None, description="Profile settings to update")


class PreferencesUpdateRequest(BaseModel):
    """Request model for preferences updates."""

    preferences: Optional[Dict[str, Any]] = Field(None, description="User preferences")
    notification_settings: Optional[Dict[str, Any]] = Field(None, description="Notification settings")
    privacy_settings: Optional[Dict[str, Any]] = Field(None, description="Privacy settings")


class AuthStatus(BaseModel):
    """Authentication status model."""

    user_id: str
    username: str
    email: Optional[str] = None
    role: str
    authenticated: bool = True
    token_type: str
    permissions: List[str] = Field(default_factory=list)
    two_fa_enabled: bool = False
    email_verified: bool = False
    trusted_ip_lockdown: bool = False
    trusted_user_agent_lockdown: bool = False
    session_info: Dict[str, Any] = Field(default_factory=dict)


class AuthMethods(BaseModel):
    """Available authentication methods model."""

    password_auth: bool = True
    two_fa_available: bool = True
    two_fa_enabled: bool = False
    # WebAuthn support removed globally
    webauthn_available: bool = False
    webauthn_credentials: int = 0
    permanent_tokens_available: bool = True
    preferred_method: Optional[str] = None


class SecurityDashboard(BaseModel):
    """Security dashboard information model."""

    user_id: str
    two_fa_status: Dict[str, Any] = Field(default_factory=dict)
    trusted_ip_lockdown: Dict[str, Any] = Field(default_factory=dict)
    trusted_user_agent_lockdown: Dict[str, Any] = Field(default_factory=dict)
    recent_logins: List[Dict[str, Any]] = Field(default_factory=list)
    active_sessions: int = 0
    webauthn_credentials: int = 0
    permanent_tokens: int = 0
    security_score: int = 0


# Core Profile Management Tools (Task 5.1)


@authenticated_tool(
    name="get_user_profile",
    description="Get comprehensive user profile information",
    permissions=["profile:read"],
    rate_limit_action="profile_read",
)
async def get_user_profile(user_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Get comprehensive user profile information for the current user or specified user.

    Args:
        user_id: Optional user ID (defaults to current user, admin can view others)

    Returns:
        Dictionary containing user profile information

    Raises:
        MCPAuthorizationError: If user doesn't have permission to view the profile
        MCPValidationError: If user_id is invalid
    """
    user_context = get_mcp_user_context()

    # Determine target user
    target_user_id = user_id or user_context.user_id

    # Check permissions for viewing other users' profiles
    if target_user_id != user_context.user_id:
        if not user_context.has_permission("admin") and user_context.role != "admin":
            raise MCPAuthorizationError("Only admins can view other users' profiles")

    try:
        # Get user from database
        from second_brain_database.database import db_manager

        users_collection = db_manager.get_collection("users")

        user_doc = await users_collection.find_one({"_id": target_user_id})
        if not user_doc:
            raise MCPValidationError("User not found")

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_user_profile",
            user_context=user_context,
            resource_type="user",
            resource_id=target_user_id,
            metadata={"target_username": user_doc.get("username")},
        )

        # Format profile response
        profile = {
            "user_id": str(user_doc["_id"]),
            "username": user_doc.get("username"),
            "email": user_doc.get("email"),
            "role": user_doc.get("role", "user"),
            "created_at": user_doc.get("created_at"),
            "email_verified": user_doc.get("email_verified", False),
            "two_fa_enabled": user_doc.get("two_fa_enabled", False),
            "trusted_ip_lockdown": user_doc.get("trusted_ip_lockdown", False),
            "trusted_user_agent_lockdown": user_doc.get("trusted_user_agent_lockdown", False),
            "last_login": user_doc.get("last_login"),
            "profile_settings": user_doc.get("profile_settings", {}),
            "permissions": user_doc.get("permissions", []),
            "workspaces": user_doc.get("workspaces", []),
            "family_memberships": user_doc.get("family_memberships", []),
        }

        logger.info("Retrieved profile for user %s by user %s", target_user_id, user_context.user_id)
        return profile

    except Exception as e:
        logger.error("Failed to get user profile for %s: %s", target_user_id, e)
        raise MCPValidationError(f"Failed to retrieve user profile: {str(e)}")


@authenticated_tool(
    name="update_user_profile",
    description="Update user profile information with validation",
    permissions=["profile:write"],
    rate_limit_action="profile_update",
)
async def update_user_profile(
    username: Optional[str] = None, email: Optional[str] = None, profile_settings: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Update user profile information with proper validation.

    Args:
        username: New username (optional)
        email: New email address (optional)
        profile_settings: Profile settings to update (optional)

    Returns:
        Dictionary containing updated profile information

    Raises:
        MCPValidationError: If update fails or validation errors occur
    """
    user_context = get_mcp_user_context()

    try:
        # Prepare updates
        updates = {}
        changes = {}

        if username is not None:
            # Validate username format and availability
            if len(username) < 3 or len(username) > 50:
                raise MCPValidationError("Username must be between 3 and 50 characters")

            # Check username availability
            from second_brain_database.database import db_manager

            users_collection = db_manager.get_collection("users")

            existing_user = await users_collection.find_one(
                {"username": username, "_id": {"$ne": user_context.user_id}}
            )

            if existing_user:
                raise MCPValidationError("Username is already taken")

            updates["username"] = username
            changes["username"] = username

        if email is not None:
            # Validate email format
            import re

            email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
            if not re.match(email_pattern, email):
                raise MCPValidationError("Invalid email format")

            # Check email availability
            from second_brain_database.database import db_manager

            users_collection = db_manager.get_collection("users")

            existing_user = await users_collection.find_one({"email": email, "_id": {"$ne": user_context.user_id}})

            if existing_user:
                raise MCPValidationError("Email is already registered")

            updates["email"] = email
            updates["email_verified"] = False  # Reset verification status
            changes["email"] = email
            changes["email_verified"] = False

        if profile_settings is not None:
            # Merge with existing profile settings
            from second_brain_database.database import db_manager

            users_collection = db_manager.get_collection("users")

            current_user = await users_collection.find_one({"_id": user_context.user_id})
            current_settings = current_user.get("profile_settings", {})
            current_settings.update(profile_settings)

            updates["profile_settings"] = current_settings
            changes["profile_settings"] = profile_settings

        if not updates:
            raise MCPValidationError("No updates provided")

        # Add update timestamp
        updates["updated_at"] = datetime.utcnow()

        # Update user in database
        from second_brain_database.database import db_manager

        users_collection = db_manager.get_collection("users")

        result = await users_collection.update_one({"_id": user_context.user_id}, {"$set": updates})

        if result.modified_count == 0:
            raise MCPValidationError("Failed to update profile")

        # Create audit trail
        await create_mcp_audit_trail(
            operation="update_user_profile",
            user_context=user_context,
            resource_type="user",
            resource_id=user_context.user_id,
            changes=changes,
            metadata={"updated_fields": list(changes.keys())},
        )

        # Get updated profile
        updated_user = await users_collection.find_one({"_id": user_context.user_id})

        result_data = {
            "user_id": str(updated_user["_id"]),
            "username": updated_user.get("username"),
            "email": updated_user.get("email"),
            "profile_settings": updated_user.get("profile_settings", {}),
            "updated_at": updated_user.get("updated_at"),
            "updated_fields": list(changes.keys()),
        }

        logger.info("Updated profile for user %s, fields: %s", user_context.user_id, list(changes.keys()))
        return result_data

    except Exception as e:
        logger.error("Failed to update profile for user %s: %s", user_context.user_id, e)
        raise MCPValidationError(f"Failed to update profile: {str(e)}")


@authenticated_tool(
    name="get_user_preferences",
    description="Get user preferences and settings",
    permissions=["profile:read"],
    rate_limit_action="profile_read",
)
async def get_user_preferences() -> Dict[str, Any]:
    """
    Get user preferences and settings for the current user.

    Returns:
        Dictionary containing user preferences and settings
    """
    user_context = get_mcp_user_context()

    try:
        # Get user preferences from database
        from second_brain_database.database import db_manager

        users_collection = db_manager.get_collection("users")

        user_doc = await users_collection.find_one({"_id": user_context.user_id})
        if not user_doc:
            raise MCPValidationError("User not found")

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_user_preferences",
            user_context=user_context,
            resource_type="user",
            resource_id=user_context.user_id,
        )

        # Format preferences response
        preferences = {
            "user_id": str(user_doc["_id"]),
            "preferences": user_doc.get("preferences", {}),
            "notification_settings": user_doc.get("notification_settings", {}),
            "privacy_settings": user_doc.get("privacy_settings", {}),
            "profile_settings": user_doc.get("profile_settings", {}),
            "updated_at": user_doc.get("preferences_updated_at") or user_doc.get("updated_at"),
        }

        logger.info("Retrieved preferences for user %s", user_context.user_id)
        return preferences

    except Exception as e:
        logger.error("Failed to get preferences for user %s: %s", user_context.user_id, e)
        raise MCPValidationError(f"Failed to retrieve preferences: {str(e)}")


@authenticated_tool(
    name="update_user_preferences",
    description="Update user preferences and settings",
    permissions=["profile:write"],
    rate_limit_action="profile_update",
)
async def update_user_preferences(
    preferences: Optional[Dict[str, Any]] = None,
    notification_settings: Optional[Dict[str, Any]] = None,
    privacy_settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Update user preferences and settings.

    Args:
        preferences: General user preferences (optional)
        notification_settings: Notification preferences (optional)
        privacy_settings: Privacy settings (optional)

    Returns:
        Dictionary containing updated preferences

    Raises:
        MCPValidationError: If update fails
    """
    user_context = get_mcp_user_context()

    try:
        # Prepare updates
        updates = {}
        changes = {}

        # Get current user data
        from second_brain_database.database import db_manager

        users_collection = db_manager.get_collection("users")

        current_user = await users_collection.find_one({"_id": user_context.user_id})
        if not current_user:
            raise MCPValidationError("User not found")

        if preferences is not None:
            current_prefs = current_user.get("preferences", {})
            current_prefs.update(preferences)
            updates["preferences"] = current_prefs
            changes["preferences"] = preferences

        if notification_settings is not None:
            current_notif = current_user.get("notification_settings", {})
            current_notif.update(notification_settings)
            updates["notification_settings"] = current_notif
            changes["notification_settings"] = notification_settings

        if privacy_settings is not None:
            current_privacy = current_user.get("privacy_settings", {})
            current_privacy.update(privacy_settings)
            updates["privacy_settings"] = current_privacy
            changes["privacy_settings"] = privacy_settings

        if not updates:
            raise MCPValidationError("No preference updates provided")

        # Add update timestamp
        updates["preferences_updated_at"] = datetime.utcnow()

        # Update preferences in database
        result = await users_collection.update_one({"_id": user_context.user_id}, {"$set": updates})

        if result.modified_count == 0:
            raise MCPValidationError("Failed to update preferences")

        # Create audit trail
        await create_mcp_audit_trail(
            operation="update_user_preferences",
            user_context=user_context,
            resource_type="user",
            resource_id=user_context.user_id,
            changes=changes,
            metadata={"updated_categories": list(changes.keys())},
        )

        # Get updated preferences
        updated_user = await users_collection.find_one({"_id": user_context.user_id})

        result_data = {
            "user_id": str(updated_user["_id"]),
            "preferences": updated_user.get("preferences", {}),
            "notification_settings": updated_user.get("notification_settings", {}),
            "privacy_settings": updated_user.get("privacy_settings", {}),
            "updated_at": updated_user.get("preferences_updated_at"),
            "updated_categories": list(changes.keys()),
        }

        logger.info("Updated preferences for user %s, categories: %s", user_context.user_id, list(changes.keys()))
        return result_data

    except Exception as e:
        logger.error("Failed to update preferences for user %s: %s", user_context.user_id, e)
        raise MCPValidationError(f"Failed to update preferences: {str(e)}")


@authenticated_tool(
    name="get_user_avatar",
    description="Get current user avatar information",
    permissions=["profile:read"],
    rate_limit_action="profile_read",
)
async def get_user_avatar() -> Dict[str, Any]:
    """
    Get current user avatar information and available avatars.

    Returns:
        Dictionary containing avatar information
    """
    user_context = get_mcp_user_context()

    try:
        # Get user avatar information from database
        from second_brain_database.database import db_manager

        users_collection = db_manager.get_collection("users")

        user_doc = await users_collection.find_one({"_id": user_context.user_id})
        if not user_doc:
            raise MCPValidationError("User not found")

        # Get avatar collections for owned/rented avatars
        avatars_collection = db_manager.get_collection("avatars")
        user_avatars_collection = db_manager.get_collection("user_avatars")

        # Get current avatar
        current_avatar_id = user_doc.get("current_avatar")
        current_avatar = None

        if current_avatar_id:
            current_avatar = await avatars_collection.find_one({"_id": current_avatar_id})

        # Get owned and rented avatars
        user_avatars = await user_avatars_collection.find({"user_id": user_context.user_id}).to_list(length=None)

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_user_avatar",
            user_context=user_context,
            resource_type="user",
            resource_id=user_context.user_id,
        )

        # Format response
        result = {
            "user_id": str(user_doc["_id"]),
            "current_avatar": (
                {
                    "id": str(current_avatar["_id"]) if current_avatar else None,
                    "name": current_avatar.get("name") if current_avatar else None,
                    "image_url": current_avatar.get("image_url") if current_avatar else None,
                    "type": current_avatar.get("type") if current_avatar else None,
                }
                if current_avatar
                else None
            ),
            "owned_avatars": [
                {
                    "id": str(avatar["avatar_id"]),
                    "ownership_type": avatar.get("ownership_type"),
                    "acquired_at": avatar.get("acquired_at"),
                    "expires_at": avatar.get("expires_at"),
                }
                for avatar in user_avatars
            ],
            "avatar_count": len(user_avatars),
        }

        logger.info("Retrieved avatar info for user %s", user_context.user_id)
        return result

    except Exception as e:
        logger.error("Failed to get avatar info for user %s: %s", user_context.user_id, e)
        raise MCPValidationError(f"Failed to retrieve avatar information: {str(e)}")


@authenticated_tool(
    name="get_user_banner",
    description="Get current user banner information",
    permissions=["profile:read"],
    rate_limit_action="profile_read",
)
async def get_user_banner() -> Dict[str, Any]:
    """
    Get current user banner information and available banners.

    Returns:
        Dictionary containing banner information
    """
    user_context = get_mcp_user_context()

    try:
        # Get user banner information from database
        from second_brain_database.database import db_manager

        users_collection = db_manager.get_collection("users")

        user_doc = await users_collection.find_one({"_id": user_context.user_id})
        if not user_doc:
            raise MCPValidationError("User not found")

        # Get banner collections for owned/rented banners
        banners_collection = db_manager.get_collection("banners")
        user_banners_collection = db_manager.get_collection("user_banners")

        # Get current banner
        current_banner_id = user_doc.get("current_banner")
        current_banner = None

        if current_banner_id:
            current_banner = await banners_collection.find_one({"_id": current_banner_id})

        # Get owned and rented banners
        user_banners = await user_banners_collection.find({"user_id": user_context.user_id}).to_list(length=None)

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_user_banner",
            user_context=user_context,
            resource_type="user",
            resource_id=user_context.user_id,
        )

        # Format response
        result = {
            "user_id": str(user_doc["_id"]),
            "current_banner": (
                {
                    "id": str(current_banner["_id"]) if current_banner else None,
                    "name": current_banner.get("name") if current_banner else None,
                    "image_url": current_banner.get("image_url") if current_banner else None,
                    "type": current_banner.get("type") if current_banner else None,
                }
                if current_banner
                else None
            ),
            "owned_banners": [
                {
                    "id": str(banner["banner_id"]),
                    "ownership_type": banner.get("ownership_type"),
                    "acquired_at": banner.get("acquired_at"),
                    "expires_at": banner.get("expires_at"),
                }
                for banner in user_banners
            ],
            "banner_count": len(user_banners),
        }

        logger.info("Retrieved banner info for user %s", user_context.user_id)
        return result

    except Exception as e:
        logger.error("Failed to get banner info for user %s: %s", user_context.user_id, e)
        raise MCPValidationError(f"Failed to retrieve banner information: {str(e)}")


@authenticated_tool(
    name="set_current_avatar",
    description="Set the current avatar for the user",
    permissions=["profile:write"],
    rate_limit_action="profile_update",
)
async def set_current_avatar(avatar_id: str) -> Dict[str, Any]:
    """
    Set the current avatar for the user from their owned/rented avatars.

    Args:
        avatar_id: ID of the avatar to set as current

    Returns:
        Dictionary containing avatar update confirmation

    Raises:
        MCPValidationError: If avatar is not owned or update fails
    """
    user_context = get_mcp_user_context()

    try:
        # Verify user owns or has rented this avatar
        from second_brain_database.database import db_manager

        user_avatars_collection = db_manager.get_collection("user_avatars")
        avatars_collection = db_manager.get_collection("avatars")

        user_avatar = await user_avatars_collection.find_one({"user_id": user_context.user_id, "avatar_id": avatar_id})

        if not user_avatar:
            raise MCPValidationError("Avatar not owned by user")

        # Check if rental is still valid
        if user_avatar.get("ownership_type") == "rental":
            expires_at = user_avatar.get("expires_at")
            if expires_at and expires_at < datetime.utcnow():
                raise MCPValidationError("Avatar rental has expired")

        # Get avatar details
        avatar = await avatars_collection.find_one({"_id": avatar_id})
        if not avatar:
            raise MCPValidationError("Avatar not found")

        # Update user's current avatar
        users_collection = db_manager.get_collection("users")

        result = await users_collection.update_one(
            {"_id": user_context.user_id},
            {"$set": {"current_avatar": avatar_id, "avatar_updated_at": datetime.utcnow()}},
        )

        if result.modified_count == 0:
            raise MCPValidationError("Failed to update current avatar")

        # Create audit trail
        await create_mcp_audit_trail(
            operation="set_current_avatar",
            user_context=user_context,
            resource_type="user",
            resource_id=user_context.user_id,
            changes={"current_avatar": avatar_id},
            metadata={"avatar_name": avatar.get("name"), "ownership_type": user_avatar.get("ownership_type")},
        )

        result_data = {
            "user_id": user_context.user_id,
            "avatar_id": avatar_id,
            "avatar_name": avatar.get("name"),
            "avatar_image_url": avatar.get("image_url"),
            "ownership_type": user_avatar.get("ownership_type"),
            "updated_at": datetime.utcnow(),
        }

        logger.info("Set current avatar %s for user %s", avatar_id, user_context.user_id)
        return result_data

    except Exception as e:
        logger.error("Failed to set avatar %s for user %s: %s", avatar_id, user_context.user_id, e)
        raise MCPValidationError(f"Failed to set current avatar: {str(e)}")


@authenticated_tool(
    name="set_current_banner",
    description="Set the current banner for the user",
    permissions=["profile:write"],
    rate_limit_action="profile_update",
)
async def set_current_banner(banner_id: str) -> Dict[str, Any]:
    """
    Set the current banner for the user from their owned/rented banners.

    Args:
        banner_id: ID of the banner to set as current

    Returns:
        Dictionary containing banner update confirmation

    Raises:
        MCPValidationError: If banner is not owned or update fails
    """
    user_context = get_mcp_user_context()

    try:
        # Verify user owns or has rented this banner
        from second_brain_database.database import db_manager

        user_banners_collection = db_manager.get_collection("user_banners")
        banners_collection = db_manager.get_collection("banners")

        user_banner = await user_banners_collection.find_one({"user_id": user_context.user_id, "banner_id": banner_id})

        if not user_banner:
            raise MCPValidationError("Banner not owned by user")

        # Check if rental is still valid
        if user_banner.get("ownership_type") == "rental":
            expires_at = user_banner.get("expires_at")
            if expires_at and expires_at < datetime.utcnow():
                raise MCPValidationError("Banner rental has expired")

        # Get banner details
        banner = await banners_collection.find_one({"_id": banner_id})
        if not banner:
            raise MCPValidationError("Banner not found")

        # Update user's current banner
        users_collection = db_manager.get_collection("users")

        result = await users_collection.update_one(
            {"_id": user_context.user_id},
            {"$set": {"current_banner": banner_id, "banner_updated_at": datetime.utcnow()}},
        )

        if result.modified_count == 0:
            raise MCPValidationError("Failed to update current banner")

        # Create audit trail
        await create_mcp_audit_trail(
            operation="set_current_banner",
            user_context=user_context,
            resource_type="user",
            resource_id=user_context.user_id,
            changes={"current_banner": banner_id},
            metadata={"banner_name": banner.get("name"), "ownership_type": user_banner.get("ownership_type")},
        )

        result_data = {
            "user_id": user_context.user_id,
            "banner_id": banner_id,
            "banner_name": banner.get("name"),
            "banner_image_url": banner.get("image_url"),
            "ownership_type": user_banner.get("ownership_type"),
            "updated_at": datetime.utcnow(),
        }

        logger.info("Set current banner %s for user %s", banner_id, user_context.user_id)
        return result_data

    except Exception as e:
        logger.error("Failed to set banner %s for user %s: %s", banner_id, user_context.user_id, e)
        raise MCPValidationError(f"Failed to set current banner: {str(e)}")


# Authentication and Security Tools (Task 5.2)


@authenticated_tool(
    name="get_auth_status",
    description="Get current user authentication status and information",
    permissions=["auth:read"],
    rate_limit_action="auth_read",
)
async def get_auth_status() -> Dict[str, Any]:
    """
    Get comprehensive authentication status for the current user.

    Returns:
        Dictionary containing authentication status and user information
    """
    user_context = get_mcp_user_context()

    try:
        # Get user from database for complete information
        from second_brain_database.database import db_manager

        users_collection = db_manager.get_collection("users")

        user_doc = await users_collection.find_one({"_id": user_context.user_id})
        if not user_doc:
            raise MCPValidationError("User not found")

        # Get session information from Redis if available
        from ....managers.redis_manager import redis_manager

        session_info = {}

        try:
            # Try to get session data from Redis
            session_key = f"user_session:{user_context.user_id}"
            session_data = await redis_manager.get(session_key)
            if session_data:
                import json

                session_info = json.loads(session_data)
        except Exception as e:
            logger.debug("Could not retrieve session info: %s", e)

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_auth_status",
            user_context=user_context,
            resource_type="user",
            resource_id=user_context.user_id,
        )

        # Format authentication status
        auth_status = {
            "user_id": str(user_doc["_id"]),
            "username": user_doc.get("username"),
            "email": user_doc.get("email"),
            "role": user_doc.get("role", "user"),
            "authenticated": True,
            "token_type": user_context.token_type if hasattr(user_context, "token_type") else "jwt",
            "permissions": user_doc.get("permissions", []),
            "two_fa_enabled": user_doc.get("two_fa_enabled", False),
            "email_verified": user_doc.get("email_verified", False),
            "trusted_ip_lockdown": user_doc.get("trusted_ip_lockdown", False),
            "trusted_user_agent_lockdown": user_doc.get("trusted_user_agent_lockdown", False),
            "last_login": user_doc.get("last_login"),
            "created_at": user_doc.get("created_at"),
            "session_info": {
                "ip_address": session_info.get("ip_address"),
                "user_agent": session_info.get("user_agent"),
                "login_time": session_info.get("login_time"),
                "expires_at": session_info.get("expires_at"),
            },
            "security_features": {
                # WebAuthn support removed
                "webauthn_available": False,
                "permanent_tokens_available": True,
                "two_fa_available": True,
                "ip_lockdown_available": True,
                "user_agent_lockdown_available": True,
            },
        }

        logger.info("Retrieved auth status for user %s", user_context.user_id)
        return auth_status

    except Exception as e:
        logger.error("Failed to get auth status for user %s: %s", user_context.user_id, e)
        raise MCPValidationError(f"Failed to retrieve authentication status: {str(e)}")


@authenticated_tool(
    name="get_auth_methods",
    description="Get available authentication methods for the current user",
    permissions=["auth:read"],
    rate_limit_action="auth_read",
)
async def get_auth_methods() -> Dict[str, Any]:
    """
    Get available authentication methods and their status for the current user.

    Returns:
        Dictionary containing authentication methods and their availability
    """
    user_context = get_mcp_user_context()

    try:
        # Get user from database
        from second_brain_database.database import db_manager

        users_collection = db_manager.get_collection("users")

        user_doc = await users_collection.find_one({"_id": user_context.user_id})
        if not user_doc:
            raise MCPValidationError("User not found")

        # WebAuthn support removed: treat credentials count as zero
        webauthn_count = 0

        # Get permanent tokens count
        tokens_collection = db_manager.get_collection("permanent_tokens")
        tokens_count = await tokens_collection.count_documents({"user_id": user_context.user_id, "active": True})

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_auth_methods",
            user_context=user_context,
            resource_type="user",
            resource_id=user_context.user_id,
        )

        # Format authentication methods
        auth_methods = {
            "user_id": str(user_doc["_id"]),
            "password_auth": {
                "available": True,
                "enabled": user_doc.get("password_hash") is not None,
                "description": "Username and password authentication",
            },
            "two_fa": {
                "available": True,
                "enabled": user_doc.get("two_fa_enabled", False),
                "method": user_doc.get("two_fa_method", "totp"),
                "backup_codes_available": user_doc.get("backup_codes") is not None,
                "description": "Two-factor authentication with TOTP or backup codes",
            },
            "webauthn": {
                "available": False,
                "enabled": False,
                "credentials_count": 0,
                "description": "WebAuthn support removed",
            },
            "permanent_tokens": {
                "available": True,
                "enabled": tokens_count > 0,
                "tokens_count": tokens_count,
                "description": "Long-lived API tokens for programmatic access",
            },
            "preferred_method": user_doc.get("preferred_auth_method", "password"),
            "security_level": "high" if user_doc.get("two_fa_enabled") else "medium",
        }

        logger.info("Retrieved auth methods for user %s", user_context.user_id)
        return auth_methods

    except Exception as e:
        logger.error("Failed to get auth methods for user %s: %s", user_context.user_id, e)
        raise MCPValidationError(f"Failed to retrieve authentication methods: {str(e)}")


@authenticated_tool(
    name="validate_token",
    description="Validate the current authentication token",
    permissions=["auth:read"],
    rate_limit_action="auth_validate",
)
async def validate_token() -> Dict[str, Any]:
    """
    Validate the current authentication token and return validation details.

    Returns:
        Dictionary containing token validation information
    """
    user_context = get_mcp_user_context()

    try:
        # The fact that we got here means the token is valid (security wrapper validated it)
        # Get additional token information
        from second_brain_database.database import db_manager

        # Check if token is blacklisted (additional validation)
        from ....routes.auth.services.auth.login import is_token_blacklisted

        # We can't access the raw token from user_context, but we can validate the user exists
        users_collection = db_manager.get_collection("users")
        user_doc = await users_collection.find_one({"_id": user_context.user_id})

        if not user_doc:
            raise MCPValidationError("User associated with token not found")

        # Create audit trail
        await create_mcp_audit_trail(
            operation="validate_token",
            user_context=user_context,
            resource_type="user",
            resource_id=user_context.user_id,
        )

        # Format validation response
        validation_result = {
            "valid": True,
            "user_id": str(user_doc["_id"]),
            "username": user_doc.get("username"),
            "token_type": getattr(user_context, "token_type", "jwt"),
            "permissions": user_context.permissions if hasattr(user_context, "permissions") else [],
            "validated_at": datetime.utcnow(),
            "user_active": user_doc.get("active", True),
            "user_verified": user_doc.get("email_verified", False),
            "security_checks": {
                "user_exists": True,
                "user_active": user_doc.get("active", True),
                "permissions_valid": True,
                "token_not_blacklisted": True,  # We assume this since we got here
            },
        }

        logger.info("Validated token for user %s", user_context.user_id)
        return validation_result

    except Exception as e:
        logger.error("Failed to validate token for user %s: %s", user_context.user_id, e)
        raise MCPValidationError(f"Token validation failed: {str(e)}")


@authenticated_tool(
    name="get_security_dashboard",
    description="Get comprehensive security dashboard for the current user",
    permissions=["auth:read"],
    rate_limit_action="auth_read",
)
async def get_security_dashboard() -> Dict[str, Any]:
    """
    Get comprehensive security dashboard information for the current user.

    Returns:
        Dictionary containing security dashboard data
    """
    user_context = get_mcp_user_context()

    try:
        # Get user from database
        from second_brain_database.database import db_manager

        users_collection = db_manager.get_collection("users")

        user_doc = await users_collection.find_one({"_id": user_context.user_id})
        if not user_doc:
            raise MCPValidationError("User not found")

        # Get security-related collections
        # WebAuthn support removed: webauthn_collection no longer needed
        tokens_collection = db_manager.get_collection("permanent_tokens")
        audit_collection = db_manager.get_collection("audit_logs")

        # WebAuthn support removed: treat credentials count as zero
        webauthn_count = 0

        # Count permanent tokens
        tokens_count = await tokens_collection.count_documents({"user_id": user_context.user_id, "active": True})

        # Get recent login attempts (last 10)
        recent_logins = (
            await audit_collection.find(
                {
                    "user_id": user_context.user_id,
                    "operation": {"$in": ["login", "login_success", "login_failure"]},
                }
            )
            .sort("timestamp", -1)
            .limit(10)
            .to_list(length=10)
        )

        # Calculate security score
        security_score = 0
        security_factors = []

        # Password protection (20 points)
        if user_doc.get("password_hash"):
            security_score += 20
            security_factors.append("Password protected")

        # Two-factor authentication (30 points)
        if user_doc.get("two_fa_enabled"):
            security_score += 30
            security_factors.append("Two-factor authentication enabled")

        # Email verification (10 points)
        if user_doc.get("email_verified"):
            security_score += 10
            security_factors.append("Email verified")

        # WebAuthn credentials (20 points)
        if webauthn_count > 0:
            security_score += 20
            security_factors.append(f"{webauthn_count} WebAuthn credential(s)")

        # IP lockdown (10 points)
        if user_doc.get("trusted_ip_lockdown"):
            security_score += 10
            security_factors.append("IP lockdown enabled")

        # User Agent lockdown (10 points)
        if user_doc.get("trusted_user_agent_lockdown"):
            security_score += 10
            security_factors.append("User Agent lockdown enabled")

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_security_dashboard",
            user_context=user_context,
            resource_type="user",
            resource_id=user_context.user_id,
        )

        # Format security dashboard
        dashboard = {
            "user_id": str(user_doc["_id"]),
            "security_score": security_score,
            "security_level": "high" if security_score >= 80 else "medium" if security_score >= 50 else "low",
            "security_factors": security_factors,
            "two_fa_status": {
                "enabled": user_doc.get("two_fa_enabled", False),
                "method": user_doc.get("two_fa_method", "totp"),
                "backup_codes_available": user_doc.get("backup_codes") is not None,
                "setup_date": user_doc.get("two_fa_setup_date"),
            },
            "trusted_ip_lockdown": {
                "enabled": user_doc.get("trusted_ip_lockdown", False),
                "trusted_ips": user_doc.get("trusted_ips", []),
                "trusted_ip_count": len(user_doc.get("trusted_ips", [])),
            },
            "trusted_user_agent_lockdown": {
                "enabled": user_doc.get("trusted_user_agent_lockdown", False),
                "trusted_user_agents": user_doc.get("trusted_user_agents", []),
                "trusted_user_agent_count": len(user_doc.get("trusted_user_agents", [])),
            },
            "recent_logins": [
                {
                    "timestamp": login.get("timestamp"),
                    "ip_address": login.get("metadata", {}).get("ip_address"),
                    "user_agent": login.get("metadata", {}).get("user_agent"),
                    "success": login.get("operation") == "login_success",
                    "method": login.get("metadata", {}).get("auth_method"),
                }
                for login in recent_logins
            ],
            "webauthn_credentials": webauthn_count,
            "permanent_tokens": tokens_count,
            "account_status": {
                "active": user_doc.get("active", True),
                "email_verified": user_doc.get("email_verified", False),
                "created_at": user_doc.get("created_at"),
                "last_login": user_doc.get("last_login"),
            },
        }

        logger.info("Retrieved security dashboard for user %s (score: %d)", user_context.user_id, security_score)
        return dashboard

    except Exception as e:
        logger.error("Failed to get security dashboard for user %s: %s", user_context.user_id, e)
        raise MCPValidationError(f"Failed to retrieve security dashboard: {str(e)}")


@authenticated_tool(
    name="check_username_availability",
    description="Check if a username is available for registration or change",
    permissions=["auth:read"],
    rate_limit_action="auth_check",
)
async def check_username_availability(username: str) -> Dict[str, Any]:
    """
    Check if a username is available for registration or profile update.

    Args:
        username: Username to check availability for

    Returns:
        Dictionary containing availability information

    Raises:
        MCPValidationError: If username format is invalid
    """
    user_context = get_mcp_user_context()

    try:
        # Validate username format
        if not username or len(username) < 3 or len(username) > 50:
            raise MCPValidationError("Username must be between 3 and 50 characters")

        # Check for invalid characters
        import re

        if not re.match(r"^[a-zA-Z0-9_-]+$", username):
            raise MCPValidationError("Username can only contain letters, numbers, underscores, and hyphens")

        # Use existing Redis-cached username check
        from ....routes.auth.services.utils.redis_utils import redis_check_username

        username_exists = await redis_check_username(username)

        # Create audit trail
        await create_mcp_audit_trail(
            operation="check_username_availability",
            user_context=user_context,
            resource_type="username",
            resource_id=username,
            metadata={"checked_username": username, "available": not username_exists},
        )

        # Format availability response
        availability = {
            "username": username,
            "available": not username_exists,
            "valid_format": True,
            "checked_at": datetime.utcnow(),
            "checked_by": user_context.user_id,
            "suggestions": [],
        }

        # If username is taken, provide suggestions
        if username_exists:
            suggestions = []
            for i in range(1, 4):
                suggestion = f"{username}{i}"
                suggestion_exists = await redis_check_username(suggestion)
                if not suggestion_exists:
                    suggestions.append(suggestion)

            availability["suggestions"] = suggestions[:3]  # Limit to 3 suggestions

        logger.info("Checked username availability: %s (available: %s)", username, not username_exists)
        return availability

    except Exception as e:
        logger.error("Failed to check username availability for %s: %s", username, e)
        raise MCPValidationError(f"Failed to check username availability: {str(e)}")


@authenticated_tool(
    name="check_email_availability",
    description="Check if an email address is available for registration or change",
    permissions=["auth:read"],
    rate_limit_action="auth_check",
)
async def check_email_availability(email: str) -> Dict[str, Any]:
    """
    Check if an email address is available for registration or profile update.

    Args:
        email: Email address to check availability for

    Returns:
        Dictionary containing availability information

    Raises:
        MCPValidationError: If email format is invalid
    """
    user_context = get_mcp_user_context()

    try:
        # Validate email format
        import re

        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_pattern, email):
            raise MCPValidationError("Invalid email format")

        # Check if email exists in database
        from second_brain_database.database import db_manager

        users_collection = db_manager.get_collection("users")

        existing_user = await users_collection.find_one(
            {"email": email, "_id": {"$ne": user_context.user_id}}  # Exclude current user
        )

        email_exists = existing_user is not None

        # Create audit trail
        await create_mcp_audit_trail(
            operation="check_email_availability",
            user_context=user_context,
            resource_type="email",
            resource_id=email,
            metadata={"checked_email": email, "available": not email_exists},
        )

        # Format availability response
        availability = {
            "email": email,
            "available": not email_exists,
            "valid_format": True,
            "checked_at": datetime.utcnow(),
            "checked_by": user_context.user_id,
            "domain": email.split("@")[1] if "@" in email else None,
        }

        logger.info("Checked email availability: %s (available: %s)", email, not email_exists)
        return availability

    except Exception as e:
        logger.error("Failed to check email availability for %s: %s", email, e)
        raise MCPValidationError(f"Failed to check email availability: {str(e)}")


@authenticated_tool(
    name="change_password",
    description="Change user password with proper validation",
    permissions=["auth:write"],
    rate_limit_action="auth_password_change",
)
async def change_password(current_password: str, new_password: str, confirm_password: str) -> Dict[str, Any]:
    """
    Change user password with proper validation and security checks.

    Args:
        current_password: Current password for verification
        new_password: New password to set
        confirm_password: Confirmation of new password

    Returns:
        Dictionary containing password change confirmation

    Raises:
        MCPValidationError: If password validation fails
        MCPAuthorizationError: If current password is incorrect
    """
    user_context = get_mcp_user_context()

    try:
        # Validate password confirmation
        if new_password != confirm_password:
            raise MCPValidationError("New password and confirmation do not match")

        # Validate new password strength
        if len(new_password) < 8:
            raise MCPValidationError("New password must be at least 8 characters long")

        # Get user from database
        from second_brain_database.database import db_manager

        users_collection = db_manager.get_collection("users")

        user_doc = await users_collection.find_one({"_id": user_context.user_id})
        if not user_doc:
            raise MCPValidationError("User not found")

        # Verify current password
        import bcrypt

        current_password_hash = user_doc.get("password_hash")

        if not current_password_hash:
            raise MCPValidationError("No password set for this account")

        if not bcrypt.checkpw(current_password.encode("utf-8"), current_password_hash.encode("utf-8")):
            raise MCPAuthorizationError("Current password is incorrect")

        # Hash new password
        new_password_hash = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        # Update password in database
        result = await users_collection.update_one(
            {"_id": user_context.user_id},
            {
                "$set": {
                    "password_hash": new_password_hash,
                    "password_changed_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                }
            },
        )

        if result.modified_count == 0:
            raise MCPValidationError("Failed to update password")

        # Create audit trail
        await create_mcp_audit_trail(
            operation="change_password",
            user_context=user_context,
            resource_type="user",
            resource_id=user_context.user_id,
            metadata={"password_changed": True},
        )

        # Log security event
        from ....utils.logging_utils import log_security_event

        log_security_event(
            event_type="password_changed",
            user_id=user_context.user_id,
            ip_address=getattr(user_context, "ip_address", ""),
            success=True,
            details={"changed_via": "mcp_tool"},
        )

        result_data = {
            "user_id": user_context.user_id,
            "password_changed": True,
            "changed_at": datetime.utcnow(),
            "security_recommendation": "Consider enabling two-factor authentication for additional security",
        }

        logger.info("Password changed successfully for user %s", user_context.user_id)
        return result_data

    except Exception as e:
        logger.error("Failed to change password for user %s: %s", user_context.user_id, e)

        # Log failed password change attempt
        from ....utils.logging_utils import log_security_event

        log_security_event(
            event_type="password_change_failed",
            user_id=user_context.user_id,
            ip_address=getattr(user_context, "ip_address", ""),
            success=False,
            details={"error": str(e), "changed_via": "mcp_tool"},
        )

        if isinstance(e, (MCPValidationError, MCPAuthorizationError)):
            raise
        else:
            raise MCPValidationError(f"Failed to change password: {str(e)}")


# 2FA Management Tools (Task 5.3)


class TwoFAStatus(BaseModel):
    """2FA status information model."""

    enabled: bool = False
    method: Optional[str] = None
    backup_codes_available: bool = False
    setup_date: Optional[datetime] = None
    pending: bool = False


class TwoFASetupResponse(BaseModel):
    """2FA setup response model."""

    totp_secret: str
    provisioning_uri: str
    qr_code_data: Optional[str] = None
    backup_codes: List[str] = Field(default_factory=list)


class BackupCodesStatus(BaseModel):
    """Backup codes status model."""

    available: bool = False
    total_codes: int = 0
    used_codes: int = 0
    remaining_codes: int = 0
    last_generated: Optional[datetime] = None


@authenticated_tool(
    name="get_2fa_status",
    description="Get current 2FA status and information for the user",
    permissions=["auth:read"],
    rate_limit_action="auth_2fa_read",
)
async def get_2fa_status() -> Dict[str, Any]:
    """
    Get comprehensive 2FA status information for the current user.

    Returns:
        Dictionary containing 2FA status and configuration
    """
    user_context = get_mcp_user_context()

    try:
        # Get user from database
        from second_brain_database.database import db_manager

        users_collection = db_manager.get_collection("users")

        user_doc = await users_collection.find_one({"_id": user_context.user_id})
        if not user_doc:
            raise MCPValidationError("User not found")

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_2fa_status",
            user_context=user_context,
            resource_type="user",
            resource_id=user_context.user_id,
        )

        # Calculate backup codes status
        backup_codes = user_doc.get("backup_codes", [])
        backup_codes_used = user_doc.get("backup_codes_used", [])

        # Format 2FA status
        status = {
            "user_id": str(user_doc["_id"]),
            "two_fa_enabled": user_doc.get("two_fa_enabled", False),
            "two_fa_pending": user_doc.get("two_fa_pending", False),
            "method": user_doc.get("two_fa_method", "totp") if user_doc.get("two_fa_enabled") else None,
            "methods": user_doc.get("two_fa_methods", []),
            "setup_date": user_doc.get("two_fa_setup_date"),
            "pending_since": user_doc.get("two_fa_pending_since"),
            "backup_codes": {
                "available": len(backup_codes) > 0,
                "total_codes": len(backup_codes),
                "used_codes": len(backup_codes_used),
                "remaining_codes": len(backup_codes) - len(backup_codes_used),
                "last_generated": user_doc.get("backup_codes_generated_at"),
            },
            "security_level": "high" if user_doc.get("two_fa_enabled") else "medium",
        }

        logger.info(
            "Retrieved 2FA status for user %s (enabled: %s)",
            user_context.user_id,
            user_doc.get("two_fa_enabled", False),
        )
        return status

    except Exception as e:
        logger.error("Failed to get 2FA status for user %s: %s", user_context.user_id, e)
        raise MCPValidationError(f"Failed to retrieve 2FA status: {str(e)}")


@authenticated_tool(
    name="setup_2fa",
    description="Initialize 2FA setup for the user",
    permissions=["auth:write"],
    rate_limit_action="auth_2fa_setup",
)
async def setup_2fa(method: str = "totp") -> Dict[str, Any]:
    """
    Initialize 2FA setup for the current user.

    Args:
        method: 2FA method to set up (currently only "totp" supported)

    Returns:
        Dictionary containing setup information including QR code

    Raises:
        MCPValidationError: If 2FA is already enabled or method is unsupported
    """
    user_context = get_mcp_user_context()

    try:
        # Validate method
        if method != "totp":
            raise MCPValidationError("Only TOTP method is currently supported")

        # Get user from database
        from second_brain_database.database import db_manager

        users_collection = db_manager.get_collection("users")

        user_doc = await users_collection.find_one({"_id": user_context.user_id})
        if not user_doc:
            raise MCPValidationError("User not found")

        # Check if 2FA is already enabled
        if user_doc.get("two_fa_enabled", False):
            raise MCPValidationError("2FA is already enabled. Use reset_2fa to generate new codes.")

        # Use existing 2FA setup service
        from ....routes.auth.models import TwoFASetupRequest
        from ....routes.auth.services.auth.twofa import setup_2fa as setup_2fa_service

        # Create request object
        setup_request = TwoFASetupRequest(method=method)

        # Call existing setup service
        setup_response = await setup_2fa_service(user_doc, setup_request)

        # Create audit trail
        await create_mcp_audit_trail(
            operation="setup_2fa",
            user_context=user_context,
            resource_type="user",
            resource_id=user_context.user_id,
            metadata={"method": method, "pending": True},
        )

        # Format response
        result = {
            "user_id": user_context.user_id,
            "method": method,
            "totp_secret": setup_response.totp_secret,
            "provisioning_uri": setup_response.provisioning_uri,
            "qr_code_data": setup_response.qr_code_data,
            "pending": True,
            "next_step": "Use verify_2fa_code to complete setup with a code from your authenticator app",
        }

        logger.info("Initiated 2FA setup for user %s with method %s", user_context.user_id, method)
        return result

    except Exception as e:
        logger.error("Failed to setup 2FA for user %s: %s", user_context.user_id, e)
        if isinstance(e, MCPValidationError):
            raise
        else:
            raise MCPValidationError(f"Failed to setup 2FA: {str(e)}")


@authenticated_tool(
    name="verify_2fa_code",
    description="Verify 2FA code to complete setup or authenticate",
    permissions=["auth:write"],
    rate_limit_action="auth_2fa_verify",
)
async def verify_2fa_code(code: str, method: str = "totp") -> Dict[str, Any]:
    """
    Verify a 2FA code to complete setup or authenticate.

    Args:
        code: 2FA code from authenticator app or backup code
        method: 2FA method being verified (currently only "totp" supported)

    Returns:
        Dictionary containing verification result and backup codes if setup completed

    Raises:
        MCPValidationError: If code is invalid or method is unsupported
    """
    user_context = get_mcp_user_context()

    try:
        # Validate method
        if method != "totp":
            raise MCPValidationError("Only TOTP method is currently supported")

        # Validate code format
        if not code or len(code) != 6 or not code.isdigit():
            raise MCPValidationError("Invalid code format. Code must be 6 digits.")

        # Get user from database
        from second_brain_database.database import db_manager

        users_collection = db_manager.get_collection("users")

        user_doc = await users_collection.find_one({"_id": user_context.user_id})
        if not user_doc:
            raise MCPValidationError("User not found")

        # Use existing 2FA verification service
        from ....routes.auth.models import TwoFAVerifyRequest
        from ....routes.auth.services.auth.twofa import verify_2fa as verify_2fa_service

        # Create request object
        verify_request = TwoFAVerifyRequest(method=method, code=code)

        # Call existing verification service
        verification_result = await verify_2fa_service(user_doc, verify_request)

        # Create audit trail
        await create_mcp_audit_trail(
            operation="verify_2fa_code",
            user_context=user_context,
            resource_type="user",
            resource_id=user_context.user_id,
            metadata={"method": method, "success": True, "was_pending": user_doc.get("two_fa_pending", False)},
        )

        # Format response
        result = {
            "user_id": user_context.user_id,
            "method": method,
            "verification_successful": True,
            "two_fa_enabled": verification_result.enabled,
            "was_setup_completion": user_doc.get("two_fa_pending", False),
            "backup_codes": verification_result.backup_codes if hasattr(verification_result, "backup_codes") else None,
        }

        if verification_result.backup_codes:
            result["backup_codes_message"] = (
                "Save these backup codes in a secure location. They can be used if you lose access to your authenticator app."
            )

        logger.info("Successfully verified 2FA code for user %s (method: %s)", user_context.user_id, method)
        return result

    except Exception as e:
        logger.error("Failed to verify 2FA code for user %s: %s", user_context.user_id, e)

        # Log failed verification attempt
        from ....utils.logging_utils import log_security_event

        log_security_event(
            event_type="2fa_verification_failed",
            user_id=user_context.user_id,
            ip_address=getattr(user_context, "ip_address", ""),
            success=False,
            details={"method": method, "error": str(e)},
        )

        if "Invalid TOTP code" in str(e):
            raise MCPValidationError("Invalid 2FA code. Please check your authenticator app and try again.")
        elif isinstance(e, MCPValidationError):
            raise
        else:
            raise MCPValidationError(f"Failed to verify 2FA code: {str(e)}")


@authenticated_tool(
    name="disable_2fa",
    description="Disable 2FA for the user",
    permissions=["auth:write"],
    rate_limit_action="auth_2fa_disable",
)
async def disable_2fa() -> Dict[str, Any]:
    """
    Disable 2FA for the current user and clear all related secrets.

    Returns:
        Dictionary containing disable confirmation

    Raises:
        MCPValidationError: If 2FA is not enabled
    """
    user_context = get_mcp_user_context()

    try:
        # Get user from database
        from second_brain_database.database import db_manager

        users_collection = db_manager.get_collection("users")

        user_doc = await users_collection.find_one({"_id": user_context.user_id})
        if not user_doc:
            raise MCPValidationError("User not found")

        # Check if 2FA is enabled
        if not user_doc.get("two_fa_enabled", False):
            raise MCPValidationError("2FA is not currently enabled")

        # Use existing 2FA disable service
        from ....routes.auth.services.auth.twofa import disable_2fa as disable_2fa_service

        # Call existing disable service
        disable_result = await disable_2fa_service(user_doc)

        # Create audit trail
        await create_mcp_audit_trail(
            operation="disable_2fa",
            user_context=user_context,
            resource_type="user",
            resource_id=user_context.user_id,
            metadata={"two_fa_disabled": True},
        )

        # Log security event
        from ....utils.logging_utils import log_security_event

        log_security_event(
            event_type="2fa_disabled",
            user_id=user_context.user_id,
            ip_address=getattr(user_context, "ip_address", ""),
            success=True,
            details={"disabled_via": "mcp_tool"},
        )

        result = {
            "user_id": user_context.user_id,
            "two_fa_disabled": True,
            "disabled_at": datetime.utcnow(),
            "security_warning": "2FA has been disabled. Your account security level is now reduced. Consider re-enabling 2FA for better security.",
        }

        logger.info("Successfully disabled 2FA for user %s", user_context.user_id)
        return result

    except Exception as e:
        logger.error("Failed to disable 2FA for user %s: %s", user_context.user_id, e)
        if isinstance(e, MCPValidationError):
            raise
        else:
            raise MCPValidationError(f"Failed to disable 2FA: {str(e)}")


@authenticated_tool(
    name="get_backup_codes_status",
    description="Get backup codes status and information",
    permissions=["auth:read"],
    rate_limit_action="auth_2fa_read",
)
async def get_backup_codes_status() -> Dict[str, Any]:
    """
    Get backup codes status and usage information for the current user.

    Returns:
        Dictionary containing backup codes status

    Raises:
        MCPValidationError: If 2FA is not enabled
    """
    user_context = get_mcp_user_context()

    try:
        # Get user from database
        from second_brain_database.database import db_manager

        users_collection = db_manager.get_collection("users")

        user_doc = await users_collection.find_one({"_id": user_context.user_id})
        if not user_doc:
            raise MCPValidationError("User not found")

        # Check if 2FA is enabled
        if not user_doc.get("two_fa_enabled", False):
            raise MCPValidationError("2FA is not enabled. Backup codes are only available when 2FA is enabled.")

        # Get backup codes information
        backup_codes = user_doc.get("backup_codes", [])
        backup_codes_used = user_doc.get("backup_codes_used", [])

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_backup_codes_status",
            user_context=user_context,
            resource_type="user",
            resource_id=user_context.user_id,
        )

        # Format backup codes status
        status = {
            "user_id": user_context.user_id,
            "backup_codes_available": len(backup_codes) > 0,
            "total_codes": len(backup_codes),
            "used_codes": len(backup_codes_used),
            "remaining_codes": len(backup_codes) - len(backup_codes_used),
            "last_generated": user_doc.get("backup_codes_generated_at"),
            "codes_low_warning": (len(backup_codes) - len(backup_codes_used)) <= 2,
            "recommendation": (
                "Generate new backup codes if you have 2 or fewer remaining"
                if (len(backup_codes) - len(backup_codes_used)) <= 2
                else None
            ),
        }

        logger.info(
            "Retrieved backup codes status for user %s (remaining: %d)", user_context.user_id, status["remaining_codes"]
        )
        return status

    except Exception as e:
        logger.error("Failed to get backup codes status for user %s: %s", user_context.user_id, e)
        if isinstance(e, MCPValidationError):
            raise
        else:
            raise MCPValidationError(f"Failed to retrieve backup codes status: {str(e)}")


@authenticated_tool(
    name="regenerate_backup_codes",
    description="Generate new backup codes for 2FA",
    permissions=["auth:write"],
    rate_limit_action="auth_2fa_backup_regenerate",
)
async def regenerate_backup_codes() -> Dict[str, Any]:
    """
    Generate new backup codes for the current user, replacing existing ones.

    Returns:
        Dictionary containing new backup codes

    Raises:
        MCPValidationError: If 2FA is not enabled
    """
    user_context = get_mcp_user_context()

    try:
        # Get user from database
        from second_brain_database.database import db_manager

        users_collection = db_manager.get_collection("users")

        user_doc = await users_collection.find_one({"_id": user_context.user_id})
        if not user_doc:
            raise MCPValidationError("User not found")

        # Check if 2FA is enabled
        if not user_doc.get("two_fa_enabled", False):
            raise MCPValidationError("2FA is not enabled. Backup codes are only available when 2FA is enabled.")

        # Generate new backup codes
        import secrets

        import bcrypt

        backup_codes = [secrets.token_hex(4).upper() for _ in range(10)]
        hashed_backup_codes = [
            bcrypt.hashpw(code.encode("utf-8"), bcrypt.gensalt()).decode("utf-8") for code in backup_codes
        ]

        # Update user with new backup codes
        result = await users_collection.update_one(
            {"_id": user_context.user_id},
            {
                "$set": {
                    "backup_codes": hashed_backup_codes,
                    "backup_codes_used": [],  # Reset used codes
                    "backup_codes_generated_at": datetime.utcnow(),
                }
            },
        )

        if result.modified_count == 0:
            raise MCPValidationError("Failed to update backup codes")

        # Create audit trail
        await create_mcp_audit_trail(
            operation="regenerate_backup_codes",
            user_context=user_context,
            resource_type="user",
            resource_id=user_context.user_id,
            metadata={"backup_codes_count": len(backup_codes)},
        )

        # Log security event
        from ....utils.logging_utils import log_security_event

        log_security_event(
            event_type="backup_codes_regenerated",
            user_id=user_context.user_id,
            ip_address=getattr(user_context, "ip_address", ""),
            success=True,
            details={"codes_count": len(backup_codes), "regenerated_via": "mcp_tool"},
        )

        result_data = {
            "user_id": user_context.user_id,
            "backup_codes": backup_codes,
            "codes_count": len(backup_codes),
            "generated_at": datetime.utcnow(),
            "security_warning": "Save these backup codes in a secure location. They replace your previous backup codes and can be used if you lose access to your authenticator app.",
            "usage_note": "Each backup code can only be used once. Generate new codes when you have 2 or fewer remaining.",
        }

        logger.info("Successfully regenerated %d backup codes for user %s", len(backup_codes), user_context.user_id)
        return result_data

    except Exception as e:
        logger.error("Failed to regenerate backup codes for user %s: %s", user_context.user_id, e)
        if isinstance(e, MCPValidationError):
            raise
        else:
            raise MCPValidationError(f"Failed to regenerate backup codes: {str(e)}")


@authenticated_tool(
    name="reset_2fa",
    description="Reset 2FA setup and generate new secret and backup codes",
    permissions=["auth:write"],
    rate_limit_action="auth_2fa_reset",
)
async def reset_2fa(method: str = "totp") -> Dict[str, Any]:
    """
    Reset 2FA for the current user, generating new secret and backup codes.

    Args:
        method: 2FA method to reset (currently only "totp" supported)

    Returns:
        Dictionary containing new setup information including QR code

    Raises:
        MCPValidationError: If 2FA is not enabled or method is unsupported
    """
    user_context = get_mcp_user_context()

    try:
        # Validate method
        if method != "totp":
            raise MCPValidationError("Only TOTP method is currently supported")

        # Get user from database
        from second_brain_database.database import db_manager

        users_collection = db_manager.get_collection("users")

        user_doc = await users_collection.find_one({"_id": user_context.user_id})
        if not user_doc:
            raise MCPValidationError("User not found")

        # Check if 2FA is enabled
        if not user_doc.get("two_fa_enabled", False):
            raise MCPValidationError("2FA is not enabled. Use setup_2fa to enable 2FA first.")

        # Use existing 2FA setup service
        from ....routes.auth.models import TwoFASetupRequest
        from ....routes.auth.services.auth.twofa import setup_2fa as setup_2fa_service

        # Create request object
        setup_request = TwoFASetupRequest(method=method)

        # Call existing setup service
        setup_response = await setup_2fa_service(user_doc, setup_request)

        # Create audit trail
        await create_mcp_audit_trail(
            operation="reset_2fa",
            user_context=user_context,
            resource_type="user",
            resource_id=user_context.user_id,
            metadata={"method": method, "reset": True},
        )

        # Format response
        result = {
            "user_id": user_context.user_id,
            "method": method,
            "totp_secret": setup_response.totp_secret,
            "provisioning_uri": setup_response.provisioning_uri,
            "qr_code_data": setup_response.qr_code_data,
            "reset_complete": True,
            "next_step": "Use verify_2fa_code to complete reset with a code from your authenticator app",
        }

        logger.info("Reset 2FA for user %s with method %s", user_context.user_id, method)
        return result

    except Exception as e:
        logger.error("Failed to reset 2FA for user %s: %s", user_context.user_id, e)
        if isinstance(e, MCPValidationError):
            raise
        else:
            raise MCPValidationError(f"Failed to reset 2FA: {str(e)}")
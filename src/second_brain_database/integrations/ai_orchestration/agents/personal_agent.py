"""
Personal Assistant Agent

This agent specializes in individual user tasks using existing
profile management and authentication systems.

Capabilities:
- Profile management (avatars, banners, themes)
- Authentication and security management
- Personal asset tracking and purchase recommendations
- User preference management and personalization
- Individual notification and reminder management
"""

from typing import Dict, Any, List, Optional, AsyncGenerator
import json

from .base_agent import BaseAgent
from ..models.events import AIEvent, EventType
from ....integrations.mcp.context import MCPUserContext
from ....managers.logging_manager import get_logger

logger = get_logger(prefix="[PersonalAgent]")


class PersonalAssistantAgent(BaseAgent):
    """
    AI agent specialized in personal user tasks and profile management.
    
    Integrates with existing auth_tools MCP tools and profile management
    to provide natural language interface for personal operations.
    """
    
    def __init__(self, orchestrator=None):
        super().__init__("personal", orchestrator)
        self.capabilities = [
            {
                "name": "profile_management",
                "description": "Manage user profile, avatar, banner, and themes",
                "required_permissions": ["profile:update"]
            },
            {
                "name": "security_settings",
                "description": "Manage authentication and security settings",
                "required_permissions": ["auth:manage"]
            },
            {
                "name": "asset_tracking",
                "description": "Track personal assets and purchases",
                "required_permissions": ["assets:view"]
            },
            {
                "name": "preferences",
                "description": "Manage user preferences and personalization",
                "required_permissions": ["profile:update"]
            },
            {
                "name": "notifications",
                "description": "Manage personal notifications and reminders",
                "required_permissions": ["notifications:manage"]
            }
        ]
    
    @property
    def agent_name(self) -> str:
        return "Personal Assistant"
    
    @property
    def agent_description(self) -> str:
        return "I help manage your personal profile, security settings, assets, preferences, and notifications. I'm your personal digital assistant."
    
    async def handle_request(
        self, 
        session_id: str, 
        request: str, 
        user_context: MCPUserContext,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[AIEvent, None]:
        """Handle personal assistant requests with streaming responses."""
        try:
            # Add request to conversation history
            self.add_to_conversation_history(session_id, "user", request)
            
            # Classify the personal task
            task_classification = await self.classify_personal_task(request)
            task_type = task_classification.get("task_type", "general")
            
            self.logger.info(
                "Processing personal request for session %s: %s (classified as %s)",
                session_id, request[:100], task_type
            )
            
            # Route to appropriate personal operation
            if task_type == "profile_update":
                async for event in self.profile_update_workflow(session_id, request, user_context):
                    yield event
            elif task_type == "security_management":
                async for event in self.security_management_workflow(session_id, request, user_context):
                    yield event
            elif task_type == "asset_management":
                async for event in self.asset_management_workflow(session_id, request, user_context):
                    yield event
            elif task_type == "preferences":
                async for event in self.preferences_workflow(session_id, request, user_context):
                    yield event
            elif task_type == "notifications":
                async for event in self.notifications_workflow(session_id, request, user_context):
                    yield event
            elif task_type == "profile_info":
                async for event in self.profile_info_workflow(session_id, request, user_context):
                    yield event
            else:
                # General personal assistance
                async for event in self.general_personal_assistance(session_id, request, user_context):
                    yield event
                    
        except Exception as e:
            self.logger.error("Personal request handling failed: %s", e)
            yield await self.emit_error(session_id, f"I encountered an issue processing your request: {str(e)}")
    
    async def get_capabilities(self, user_context: MCPUserContext) -> List[Dict[str, Any]]:
        """Get personal capabilities available to the user."""
        available_capabilities = []
        
        for capability in self.capabilities:
            required_perms = capability.get("required_permissions", [])
            if await self.validate_permissions(user_context, required_perms):
                available_capabilities.append(capability)
        
        return available_capabilities
    
    async def classify_personal_task(self, request: str) -> Dict[str, Any]:
        """Classify the type of personal task from the request."""
        request_lower = request.lower()
        
        # Profile update patterns
        if any(phrase in request_lower for phrase in [
            "update profile", "change avatar", "change banner", "change theme", 
            "profile picture", "update username", "change name"
        ]):
            return {"task_type": "profile_update", "confidence": 0.9}
        
        # Security management patterns
        if any(phrase in request_lower for phrase in [
            "password", "2fa", "two factor", "security", "authentication",
            "login", "logout", "token", "api key"
        ]):
            return {"task_type": "security_management", "confidence": 0.9}
        
        # Asset management patterns
        if any(phrase in request_lower for phrase in [
            "my assets", "my purchases", "what i own", "my items",
            "purchase history", "bought items"
        ]):
            return {"task_type": "asset_management", "confidence": 0.8}
        
        # Preferences patterns
        if any(phrase in request_lower for phrase in [
            "preferences", "settings", "customize", "personalize",
            "configure", "options"
        ]):
            return {"task_type": "preferences", "confidence": 0.8}
        
        # Notifications patterns
        if any(phrase in request_lower for phrase in [
            "notifications", "alerts", "reminders", "notify me"
        ]):
            return {"task_type": "notifications", "confidence": 0.8}
        
        # Profile info patterns
        if any(phrase in request_lower for phrase in [
            "my profile", "profile info", "about me", "my details",
            "show profile", "profile summary"
        ]):
            return {"task_type": "profile_info", "confidence": 0.9}
        
        return {"task_type": "general", "confidence": 0.5}
    
    async def profile_update_workflow(
        self, 
        session_id: str, 
        request: str, 
        user_context: MCPUserContext
    ) -> AsyncGenerator[AIEvent, None]:
        """Handle profile update workflow."""
        yield await self.emit_status(session_id, EventType.THINKING, "Processing profile update...")
        
        try:
            # Determine what profile field to update
            update_type = await self.classify_profile_update(request)
            
            if update_type == "avatar":
                # Handle avatar update
                result = await self.execute_mcp_tool(
                    session_id,
                    "get_available_avatars",
                    {"user_id": user_context.user_id},
                    user_context
                )
                
                if result and not result.get("error"):
                    avatars = result.get("avatars", [])
                    if avatars:
                        response = "Here are your available avatars:\n"
                        for i, avatar in enumerate(avatars[:5], 1):
                            name = avatar.get("name", f"Avatar {i}")
                            response += f"{i}. {name}\n"
                        response += "\nWhich avatar would you like to use? Just tell me the number or name."
                    else:
                        response = "You don't have any avatars yet. Would you like me to help you browse the shop for avatars?"
                    
                    yield await self.emit_response(session_id, response)
                else:
                    yield await self.emit_response(
                        session_id,
                        "I'm having trouble accessing your avatar collection right now."
                    )
            
            elif update_type == "username":
                # Extract new username from request
                new_username = await self.extract_username_from_request(request)
                
                if not new_username:
                    yield await self.emit_response(
                        session_id,
                        "What would you like your new username to be?"
                    )
                    return
                
                # Update username using MCP tool
                result = await self.execute_mcp_tool(
                    session_id,
                    "update_profile",
                    {
                        "user_id": user_context.user_id,
                        "updates": {"username": new_username}
                    },
                    user_context
                )
                
                if result and not result.get("error"):
                    yield await self.emit_response(
                        session_id,
                        f"Great! I've updated your username to '{new_username}'."
                    )
                else:
                    error_msg = result.get("error", "Unknown error occurred")
                    yield await self.emit_response(
                        session_id,
                        f"I couldn't update your username: {error_msg}"
                    )
            
            else:
                # General profile update guidance
                yield await self.emit_response(
                    session_id,
                    "I can help you update your profile! I can change your username, avatar, banner, or theme. What would you like to update?"
                )
                
        except Exception as e:
            self.logger.error("Profile update workflow failed: %s", e)
            yield await self.emit_error(session_id, f"Profile update failed: {str(e)}")
    
    async def security_management_workflow(
        self, 
        session_id: str, 
        request: str, 
        user_context: MCPUserContext
    ) -> AsyncGenerator[AIEvent, None]:
        """Handle security management workflow."""
        yield await self.emit_status(session_id, EventType.THINKING, "Checking security settings...")
        
        try:
            # Classify security operation
            security_op = await self.classify_security_operation(request)
            
            if security_op == "2fa_status":
                # Check 2FA status
                result = await self.execute_mcp_tool(
                    session_id,
                    "get_user_security_info",
                    {"user_id": user_context.user_id},
                    user_context
                )
                
                if result and not result.get("error"):
                    security_info = result.get("security", {})
                    twofa_enabled = security_info.get("twofa_enabled", False)
                    
                    if twofa_enabled:
                        response = "✅ Two-factor authentication is enabled on your account. Your account is well protected!"
                    else:
                        response = "⚠️ Two-factor authentication is not enabled. I recommend enabling it for better security. Would you like me to help you set it up?"
                    
                    yield await self.emit_response(session_id, response)
                else:
                    yield await self.emit_response(
                        session_id,
                        "I couldn't check your security settings right now. Please try again later."
                    )
            
            elif security_op == "api_tokens":
                # Manage API tokens
                result = await self.execute_mcp_tool(
                    session_id,
                    "list_user_tokens",
                    {"user_id": user_context.user_id},
                    user_context
                )
                
                if result and not result.get("error"):
                    tokens = result.get("tokens", [])
                    if tokens:
                        response = f"You have {len(tokens)} API token(s):\n"
                        for token in tokens:
                            name = token.get("name", "Unnamed Token")
                            created = token.get("created_at", "Unknown")
                            response += f"• {name} (created: {created})\n"
                        response += "\nI can help you create new tokens or manage existing ones."
                    else:
                        response = "You don't have any API tokens yet. Would you like me to help you create one?"
                    
                    yield await self.emit_response(session_id, response)
                else:
                    yield await self.emit_response(
                        session_id,
                        "I couldn't access your API token information right now."
                    )
            
            else:
                # General security guidance
                yield await self.emit_response(
                    session_id,
                    "I can help you with security settings including two-factor authentication, API tokens, and password management. What would you like to check or update?"
                )
                
        except Exception as e:
            self.logger.error("Security management workflow failed: %s", e)
            yield await self.emit_error(session_id, f"Security management failed: {str(e)}")
    
    async def asset_management_workflow(
        self, 
        session_id: str, 
        request: str, 
        user_context: MCPUserContext
    ) -> AsyncGenerator[AIEvent, None]:
        """Handle personal asset management workflow."""
        yield await self.emit_status(session_id, EventType.THINKING, "Checking your assets...")
        
        try:
            # Get user's assets
            result = await self.execute_mcp_tool(
                session_id,
                "get_user_assets",
                {"user_id": user_context.user_id},
                user_context
            )
            
            if result and not result.get("error"):
                assets = result.get("assets", {})
                
                response = "**Your Digital Assets:**\n\n"
                
                # Avatars
                avatars = assets.get("avatars", [])
                response += f"🎭 **Avatars:** {len(avatars)}\n"
                if avatars:
                    for avatar in avatars[:3]:  # Show first 3
                        name = avatar.get("name", "Unknown Avatar")
                        response += f"  • {name}\n"
                    if len(avatars) > 3:
                        response += f"  • ... and {len(avatars) - 3} more\n"
                response += "\n"
                
                # Banners
                banners = assets.get("banners", [])
                response += f"🖼️ **Banners:** {len(banners)}\n"
                if banners:
                    for banner in banners[:3]:  # Show first 3
                        name = banner.get("name", "Unknown Banner")
                        response += f"  • {name}\n"
                    if len(banners) > 3:
                        response += f"  • ... and {len(banners) - 3} more\n"
                response += "\n"
                
                # Themes
                themes = assets.get("themes", [])
                response += f"🎨 **Themes:** {len(themes)}\n"
                if themes:
                    for theme in themes[:3]:  # Show first 3
                        name = theme.get("name", "Unknown Theme")
                        response += f"  • {name}\n"
                    if len(themes) > 3:
                        response += f"  • ... and {len(themes) - 3} more\n"
                
                # SBD Token balance
                sbd_balance = assets.get("sbd_balance", 0)
                response += f"\n💰 **SBD Token Balance:** {sbd_balance} tokens\n"
                
                response += "\nI can help you manage any of these assets or browse the shop for new items!"
                
                yield await self.emit_response(session_id, response)
            else:
                yield await self.emit_response(
                    session_id,
                    "I couldn't access your asset information right now. Please try again later."
                )
                
        except Exception as e:
            self.logger.error("Asset management workflow failed: %s", e)
            yield await self.emit_error(session_id, f"Asset management failed: {str(e)}")
    
    async def preferences_workflow(
        self, 
        session_id: str, 
        request: str, 
        user_context: MCPUserContext
    ) -> AsyncGenerator[AIEvent, None]:
        """Handle user preferences workflow."""
        yield await self.emit_status(session_id, EventType.THINKING, "Checking your preferences...")
        
        try:
            # Get user preferences
            result = await self.execute_mcp_tool(
                session_id,
                "get_user_preferences",
                {"user_id": user_context.user_id},
                user_context
            )
            
            if result and not result.get("error"):
                preferences = result.get("preferences", {})
                
                response = "**Your Current Preferences:**\n\n"
                
                # Theme preference
                theme = preferences.get("theme", "default")
                response += f"🎨 **Theme:** {theme.title()}\n"
                
                # Notification preferences
                notifications = preferences.get("notifications", {})
                email_notifications = notifications.get("email", True)
                push_notifications = notifications.get("push", True)
                response += f"📧 **Email Notifications:** {'Enabled' if email_notifications else 'Disabled'}\n"
                response += f"🔔 **Push Notifications:** {'Enabled' if push_notifications else 'Disabled'}\n"
                
                # Privacy settings
                privacy = preferences.get("privacy", {})
                profile_visibility = privacy.get("profile_visibility", "public")
                response += f"👁️ **Profile Visibility:** {profile_visibility.title()}\n"
                
                response += "\nI can help you update any of these preferences. What would you like to change?"
                
                yield await self.emit_response(session_id, response)
            else:
                yield await self.emit_response(
                    session_id,
                    "I couldn't access your preferences right now. Please try again later."
                )
                
        except Exception as e:
            self.logger.error("Preferences workflow failed: %s", e)
            yield await self.emit_error(session_id, f"Preferences management failed: {str(e)}")
    
    async def notifications_workflow(
        self, 
        session_id: str, 
        request: str, 
        user_context: MCPUserContext
    ) -> AsyncGenerator[AIEvent, None]:
        """Handle notifications management workflow."""
        yield await self.emit_status(session_id, EventType.THINKING, "Checking your notifications...")
        
        try:
            # Get recent notifications
            result = await self.execute_mcp_tool(
                session_id,
                "get_user_notifications",
                {
                    "user_id": user_context.user_id,
                    "limit": 10
                },
                user_context
            )
            
            if result and not result.get("error"):
                notifications = result.get("notifications", [])
                
                if notifications:
                    response = f"**Your Recent Notifications ({len(notifications)}):**\n\n"
                    
                    for notification in notifications:
                        title = notification.get("title", "No Title")
                        message = notification.get("message", "")
                        timestamp = notification.get("created_at", "Unknown time")
                        read = notification.get("read", False)
                        
                        status_icon = "✅" if read else "🔔"
                        response += f"{status_icon} **{title}**\n"
                        if message:
                            # Truncate long messages
                            display_message = message[:100] + "..." if len(message) > 100 else message
                            response += f"   {display_message}\n"
                        response += f"   _{timestamp}_\n\n"
                    
                    unread_count = sum(1 for n in notifications if not n.get("read", False))
                    if unread_count > 0:
                        response += f"You have {unread_count} unread notification(s)."
                else:
                    response = "You don't have any recent notifications. I'll let you know when something important happens!"
                
                yield await self.emit_response(session_id, response)
            else:
                yield await self.emit_response(
                    session_id,
                    "I couldn't access your notifications right now. Please try again later."
                )
                
        except Exception as e:
            self.logger.error("Notifications workflow failed: %s", e)
            yield await self.emit_error(session_id, f"Notifications management failed: {str(e)}")
    
    async def profile_info_workflow(
        self, 
        session_id: str, 
        request: str, 
        user_context: MCPUserContext
    ) -> AsyncGenerator[AIEvent, None]:
        """Handle profile information display workflow."""
        yield await self.emit_status(session_id, EventType.THINKING, "Getting your profile information...")
        
        try:
            # Get detailed profile information
            result = await self.execute_mcp_tool(
                session_id,
                "get_user_profile",
                {"user_id": user_context.user_id},
                user_context
            )
            
            if result and not result.get("error"):
                profile = result.get("profile", {})
                
                response = "**Your Profile Summary:**\n\n"
                
                # Basic info
                username = profile.get("username", user_context.username or "Unknown")
                email = profile.get("email", user_context.email or "Not set")
                role = profile.get("role", user_context.role or "user")
                created_at = profile.get("created_at", "Unknown")
                
                response += f"👤 **Username:** {username}\n"
                response += f"📧 **Email:** {email}\n"
                response += f"🏷️ **Role:** {role.title()}\n"
                response += f"📅 **Member Since:** {created_at}\n\n"
                
                # Current selections
                current_avatar = profile.get("current_avatar", "Default")
                current_banner = profile.get("current_banner", "Default")
                current_theme = profile.get("current_theme", "Default")
                
                response += f"🎭 **Current Avatar:** {current_avatar}\n"
                response += f"🖼️ **Current Banner:** {current_banner}\n"
                response += f"🎨 **Current Theme:** {current_theme}\n\n"
                
                # Family and workspace info
                family_count = len(user_context.family_memberships)
                workspace_count = len(user_context.workspaces)
                
                response += f"👨‍👩‍👧‍👦 **Families:** {family_count}\n"
                response += f"🏢 **Workspaces:** {workspace_count}\n"
                
                response += "\nI can help you update any of this information. Just let me know what you'd like to change!"
                
                yield await self.emit_response(session_id, response)
            else:
                yield await self.emit_response(
                    session_id,
                    "I couldn't access your profile information right now. Please try again later."
                )
                
        except Exception as e:
            self.logger.error("Profile info workflow failed: %s", e)
            yield await self.emit_error(session_id, f"Failed to get profile info: {str(e)}")
    
    async def general_personal_assistance(
        self, 
        session_id: str, 
        request: str, 
        user_context: MCPUserContext
    ) -> AsyncGenerator[AIEvent, None]:
        """Handle general personal assistance requests."""
        try:
            # Load user context for personalized response
            context = await self.load_user_context(user_context)
            
            # Emit thinking status
            yield await self.emit_status(session_id, EventType.THINKING, "Processing your request...")
            
            # Create a helpful response directly
            response = f"""Hello {context.get('username', 'there')}! I'm your Personal Assistant AI.

I can help you with:

🔧 **Profile Management**
- Update your username, avatar, banner, and theme
- Manage your personal preferences and settings

🔒 **Security Settings** 
- Set up 2FA and manage API tokens
- Review and update password security

💎 **Asset Management**
- Track your avatars, banners, themes, and SBD tokens
- View your digital asset collection

🔔 **Notifications**
- Manage notification preferences
- Stay updated on important account activities

What would you like help with today? Just ask me about any of these features or anything else related to your personal account management!"""

            # Emit the response
            yield await self.emit_response(session_id, response)
            
        except Exception as e:
            self.logger.error("General personal assistance failed: %s", e)
            yield await self.emit_error(session_id, f"I encountered an issue: {str(e)}")
    
    # Helper methods for extracting information from requests
    
    async def classify_profile_update(self, request: str) -> str:
        """Classify the type of profile update."""
        request_lower = request.lower()
        
        if any(word in request_lower for word in ["avatar", "profile picture", "picture"]):
            return "avatar"
        elif any(word in request_lower for word in ["banner", "header"]):
            return "banner"
        elif any(word in request_lower for word in ["theme", "color", "appearance"]):
            return "theme"
        elif any(word in request_lower for word in ["username", "name", "display name"]):
            return "username"
        else:
            return "general"
    
    async def classify_security_operation(self, request: str) -> str:
        """Classify the type of security operation."""
        request_lower = request.lower()
        
        if any(phrase in request_lower for phrase in ["2fa", "two factor", "authenticator"]):
            return "2fa_status"
        elif any(phrase in request_lower for phrase in ["api token", "token", "api key"]):
            return "api_tokens"
        elif any(phrase in request_lower for phrase in ["password", "change password"]):
            return "password"
        else:
            return "general"
    
    async def extract_username_from_request(self, request: str) -> Optional[str]:
        """Extract new username from request text."""
        import re
        
        # Look for patterns like "change username to X" or "username X"
        patterns = [
            r"username (?:to )?['\"]([^'\"]+)['\"]",
            r"change (?:username|name) (?:to )?['\"]([^'\"]+)['\"]",
            r"new username ['\"]([^'\"]+)['\"]",
            r"call me ['\"]([^'\"]+)['\"]"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, request.lower())
            if match:
                return match.group(1).strip()
        
        # Look for username after keywords
        keywords = ["username", "name", "call", "change"]
        words = request.split()
        
        for i, word in enumerate(words):
            if word.lower() in keywords and i + 1 < len(words):
                potential_username = words[i + 1].strip('"\'')
                if len(potential_username) >= 3:
                    return potential_username
        
        return None
"""
Family Assistant Agent

This agent specializes in family management operations using existing
FamilyManager functionality and family_tools MCP integration.

Capabilities:
- Family creation and management
- Member invitation and relationship management
- SBD token coordination and family financial management
- Family notification generation and coordination
- Family shopping assistance and shared asset management
"""

from typing import Dict, Any, List, Optional, AsyncGenerator
import json

from .base_agent import BaseAgent
from ..models.events import AIEvent, EventType
from ....integrations.mcp.context import MCPUserContext
from ....managers.family_manager import family_manager
from ....managers.logging_manager import get_logger

logger = get_logger(prefix="[FamilyAgent]")


class FamilyAssistantAgent(BaseAgent):
    """
    AI agent specialized in family management operations.
    
    Integrates with existing FamilyManager and family_tools MCP tools
    to provide natural language interface for family operations.
    """
    
    def __init__(self, orchestrator=None):
        super().__init__("family", orchestrator)
        self.capabilities = [
            {
                "name": "create_family",
                "description": "Create a new family",
                "required_permissions": ["family:create"]
            },
            {
                "name": "manage_members",
                "description": "Invite and manage family members",
                "required_permissions": ["family:manage"]
            },
            {
                "name": "family_tokens",
                "description": "Manage family SBD tokens and financial coordination",
                "required_permissions": ["family:tokens"]
            },
            {
                "name": "family_shopping",
                "description": "Assist with family shopping and shared assets",
                "required_permissions": ["family:shop"]
            },
            {
                "name": "family_notifications",
                "description": "Generate and manage family notifications",
                "required_permissions": ["family:notify"]
            }
        ]
    
    @property
    def agent_name(self) -> str:
        return "Family Assistant"
    
    @property
    def agent_description(self) -> str:
        return "I help manage family relationships, coordinate SBD tokens, handle member invitations, and assist with family shopping and notifications."
    
    async def handle_request(
        self, 
        session_id: str, 
        request: str, 
        user_context: MCPUserContext,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[AIEvent, None]:
        """Handle family-related requests with streaming responses."""
        try:
            # Add request to conversation history
            self.add_to_conversation_history(session_id, "user", request)
            
            # Classify the family task
            task_classification = await self.classify_family_task(request)
            task_type = task_classification.get("task_type", "general")
            
            self.logger.info(
                "Processing family request for session %s: %s (classified as %s)",
                session_id, request[:100], task_type
            )
            
            # Route to appropriate family operation
            if task_type == "create_family":
                async for event in self.create_family_workflow(session_id, request, user_context):
                    yield event
            elif task_type == "invite_member":
                async for event in self.invite_member_workflow(session_id, request, user_context):
                    yield event
            elif task_type == "manage_tokens":
                async for event in self.manage_family_tokens_workflow(session_id, request, user_context):
                    yield event
            elif task_type == "family_shopping":
                async for event in self.family_shopping_workflow(session_id, request, user_context):
                    yield event
            elif task_type == "list_families":
                async for event in self.list_families_workflow(session_id, request, user_context):
                    yield event
            elif task_type == "family_info":
                async for event in self.family_info_workflow(session_id, request, user_context):
                    yield event
            else:
                # General family assistance
                async for event in self.general_family_assistance(session_id, request, user_context):
                    yield event
                    
        except Exception as e:
            self.logger.error("Family request handling failed: %s", e)
            yield await self.emit_error(session_id, f"I encountered an issue processing your family request: {str(e)}")
    
    async def get_capabilities(self, user_context: MCPUserContext) -> List[Dict[str, Any]]:
        """Get family capabilities available to the user."""
        available_capabilities = []
        
        for capability in self.capabilities:
            required_perms = capability.get("required_permissions", [])
            if await self.validate_permissions(user_context, required_perms):
                available_capabilities.append(capability)
        
        return available_capabilities
    
    async def classify_family_task(self, request: str) -> Dict[str, Any]:
        """Classify the type of family task from the request."""
        request_lower = request.lower()
        
        # Family creation patterns
        if any(phrase in request_lower for phrase in [
            "create family", "new family", "make family", "start family"
        ]):
            return {"task_type": "create_family", "confidence": 0.9}
        
        # Member invitation patterns
        if any(phrase in request_lower for phrase in [
            "invite", "add member", "invite member", "add to family"
        ]):
            return {"task_type": "invite_member", "confidence": 0.9}
        
        # Token management patterns
        if any(phrase in request_lower for phrase in [
            "sbd token", "family token", "token request", "family money", "family funds"
        ]):
            return {"task_type": "manage_tokens", "confidence": 0.8}
        
        # Shopping patterns
        if any(phrase in request_lower for phrase in [
            "family shop", "buy for family", "family purchase", "shared asset"
        ]):
            return {"task_type": "family_shopping", "confidence": 0.8}
        
        # List families patterns
        if any(phrase in request_lower for phrase in [
            "list families", "show families", "my families", "family list"
        ]):
            return {"task_type": "list_families", "confidence": 0.9}
        
        # Family info patterns
        if any(phrase in request_lower for phrase in [
            "family info", "family details", "about family", "family members"
        ]):
            return {"task_type": "family_info", "confidence": 0.8}
        
        return {"task_type": "general", "confidence": 0.5}
    
    async def create_family_workflow(
        self, 
        session_id: str, 
        request: str, 
        user_context: MCPUserContext
    ) -> AsyncGenerator[AIEvent, None]:
        """Handle family creation workflow."""
        yield await self.emit_status(session_id, EventType.THINKING, "Let me help you create a new family...")
        
        try:
            # Extract family name from request
            family_name = await self.extract_family_name(request)
            
            if not family_name:
                yield await self.emit_response(
                    session_id, 
                    "I'd be happy to help you create a family! What would you like to name your family?"
                )
                return
            
            # Validate family name
            if len(family_name) < 3:
                yield await self.emit_response(
                    session_id,
                    "Family names should be at least 3 characters long. Please choose a longer name."
                )
                return
            
            # Create family using MCP tool
            result = await self.execute_mcp_tool(
                session_id,
                "create_family",
                {"name": family_name},
                user_context
            )
            
            if result and not result.get("error"):
                family_id = result.get("family_id")
                response = f"Great! I've successfully created your family '{family_name}'. "
                response += f"Your family ID is {family_id}. "
                response += "You can now invite members and start managing your family together!"
                
                yield await self.emit_response(session_id, response)
                
                # Add to conversation history
                self.add_to_conversation_history(session_id, "assistant", response)
            else:
                error_msg = result.get("error", "Unknown error occurred")
                yield await self.emit_response(
                    session_id,
                    f"I encountered an issue creating your family: {error_msg}"
                )
                
        except Exception as e:
            self.logger.error("Family creation workflow failed: %s", e)
            yield await self.emit_error(session_id, f"Family creation failed: {str(e)}")
    
    async def invite_member_workflow(
        self, 
        session_id: str, 
        request: str, 
        user_context: MCPUserContext
    ) -> AsyncGenerator[AIEvent, None]:
        """Handle member invitation workflow."""
        yield await self.emit_status(session_id, EventType.THINKING, "Processing member invitation...")
        
        try:
            # Extract email and family info from request
            email = await self.extract_email_from_request(request)
            family_id = await self.extract_family_id_from_request(request, user_context)
            
            if not email:
                yield await self.emit_response(
                    session_id,
                    "I need an email address to send the invitation. What email should I use?"
                )
                return
            
            if not family_id:
                # List user's families to choose from
                families = user_context.family_memberships
                if not families:
                    yield await self.emit_response(
                        session_id,
                        "You don't seem to be part of any families yet. Would you like to create one first?"
                    )
                    return
                elif len(families) == 1:
                    family_id = families[0].get("family_id")
                else:
                    family_list = "\n".join([
                        f"- {fm.get('family_name', 'Unknown')} (ID: {fm.get('family_id')})"
                        for fm in families
                    ])
                    yield await self.emit_response(
                        session_id,
                        f"Which family would you like to invite them to?\n{family_list}"
                    )
                    return
            
            # Send invitation using MCP tool
            result = await self.execute_mcp_tool(
                session_id,
                "invite_family_member",
                {
                    "family_id": family_id,
                    "email": email,
                    "role": "member"  # Default role
                },
                user_context
            )
            
            if result and not result.get("error"):
                response = f"Perfect! I've sent a family invitation to {email}. "
                response += "They'll receive an email with instructions to join your family."
                
                yield await self.emit_response(session_id, response)
            else:
                error_msg = result.get("error", "Unknown error occurred")
                yield await self.emit_response(
                    session_id,
                    f"I couldn't send the invitation: {error_msg}"
                )
                
        except Exception as e:
            self.logger.error("Member invitation workflow failed: %s", e)
            yield await self.emit_error(session_id, f"Invitation failed: {str(e)}")
    
    async def manage_family_tokens_workflow(
        self, 
        session_id: str, 
        request: str, 
        user_context: MCPUserContext
    ) -> AsyncGenerator[AIEvent, None]:
        """Handle family SBD token management workflow."""
        yield await self.emit_status(session_id, EventType.THINKING, "Checking family token information...")
        
        try:
            # Determine token operation type
            operation = await self.classify_token_operation(request)
            
            if operation == "balance":
                # Get family token balances
                result = await self.execute_mcp_tool(
                    session_id,
                    "get_family_token_balance",
                    {"user_id": user_context.user_id},
                    user_context
                )
                
                if result and not result.get("error"):
                    balance_info = result.get("balance", {})
                    response = "Here's your family token information:\n"
                    for family_id, balance in balance_info.items():
                        family_name = balance.get("family_name", "Unknown Family")
                        tokens = balance.get("tokens", 0)
                        response += f"- {family_name}: {tokens} SBD tokens\n"
                    
                    yield await self.emit_response(session_id, response)
                else:
                    yield await self.emit_response(
                        session_id,
                        "I couldn't retrieve your family token information right now."
                    )
            
            elif operation == "request":
                # Handle token request
                amount = await self.extract_token_amount(request)
                family_id = await self.extract_family_id_from_request(request, user_context)
                
                if not amount:
                    yield await self.emit_response(
                        session_id,
                        "How many SBD tokens would you like to request?"
                    )
                    return
                
                if not family_id:
                    yield await self.emit_response(
                        session_id,
                        "Which family would you like to request tokens from?"
                    )
                    return
                
                result = await self.execute_mcp_tool(
                    session_id,
                    "request_family_tokens",
                    {
                        "family_id": family_id,
                        "amount": amount,
                        "reason": "Token request via AI assistant"
                    },
                    user_context
                )
                
                if result and not result.get("error"):
                    yield await self.emit_response(
                        session_id,
                        f"I've submitted your request for {amount} SBD tokens. Family admins will be notified to approve it."
                    )
                else:
                    error_msg = result.get("error", "Unknown error occurred")
                    yield await self.emit_response(
                        session_id,
                        f"I couldn't submit your token request: {error_msg}"
                    )
            
            else:
                yield await self.emit_response(
                    session_id,
                    "I can help you check family token balances or request tokens. What would you like to do?"
                )
                
        except Exception as e:
            self.logger.error("Family token workflow failed: %s", e)
            yield await self.emit_error(session_id, f"Token management failed: {str(e)}")
    
    async def family_shopping_workflow(
        self, 
        session_id: str, 
        request: str, 
        user_context: MCPUserContext
    ) -> AsyncGenerator[AIEvent, None]:
        """Handle family shopping assistance workflow."""
        yield await self.emit_status(session_id, EventType.THINKING, "Looking at family shopping options...")
        
        try:
            # Get family shopping recommendations
            result = await self.execute_mcp_tool(
                session_id,
                "get_family_shop_items",
                {"user_id": user_context.user_id},
                user_context
            )
            
            if result and not result.get("error"):
                items = result.get("items", [])
                if items:
                    response = "Here are some items that might interest your family:\n"
                    for item in items[:5]:  # Show top 5 items
                        name = item.get("name", "Unknown Item")
                        price = item.get("price", 0)
                        item_type = item.get("type", "item")
                        response += f"- {name} ({item_type}): {price} SBD tokens\n"
                    
                    response += "\nWould you like me to help you purchase any of these items for your family?"
                    yield await self.emit_response(session_id, response)
                else:
                    yield await self.emit_response(
                        session_id,
                        "I don't see any family-suitable items in the shop right now. Check back later for new arrivals!"
                    )
            else:
                yield await self.emit_response(
                    session_id,
                    "I'm having trouble accessing the shop right now. Please try again later."
                )
                
        except Exception as e:
            self.logger.error("Family shopping workflow failed: %s", e)
            yield await self.emit_error(session_id, f"Shopping assistance failed: {str(e)}")
    
    async def list_families_workflow(
        self, 
        session_id: str, 
        request: str, 
        user_context: MCPUserContext
    ) -> AsyncGenerator[AIEvent, None]:
        """Handle listing user's families."""
        yield await self.emit_status(session_id, EventType.THINKING, "Getting your family information...")
        
        try:
            families = user_context.family_memberships
            
            if not families:
                yield await self.emit_response(
                    session_id,
                    "You're not currently part of any families. Would you like me to help you create one or join an existing family?"
                )
                return
            
            response = f"You're part of {len(families)} family/families:\n\n"
            for family in families:
                family_name = family.get("family_name", "Unknown Family")
                family_id = family.get("family_id")
                role = family.get("role", "member")
                response += f"• **{family_name}** (ID: {family_id})\n"
                response += f"  Role: {role.title()}\n\n"
            
            response += "I can help you manage any of these families. Just let me know what you'd like to do!"
            
            yield await self.emit_response(session_id, response)
            
        except Exception as e:
            self.logger.error("List families workflow failed: %s", e)
            yield await self.emit_error(session_id, f"Failed to get family list: {str(e)}")
    
    async def family_info_workflow(
        self, 
        session_id: str, 
        request: str, 
        user_context: MCPUserContext
    ) -> AsyncGenerator[AIEvent, None]:
        """Handle getting detailed family information."""
        yield await self.emit_status(session_id, EventType.THINKING, "Getting family details...")
        
        try:
            family_id = await self.extract_family_id_from_request(request, user_context)
            
            if not family_id:
                families = user_context.family_memberships
                if len(families) == 1:
                    family_id = families[0].get("family_id")
                else:
                    yield await self.emit_response(
                        session_id,
                        "Which family would you like information about? Please specify the family name or ID."
                    )
                    return
            
            # Get detailed family information
            result = await self.execute_mcp_tool(
                session_id,
                "get_family_details",
                {"family_id": family_id},
                user_context
            )
            
            if result and not result.get("error"):
                family_info = result.get("family", {})
                members = result.get("members", [])
                
                response = f"**Family Information**\n\n"
                response += f"Name: {family_info.get('name', 'Unknown')}\n"
                response += f"Created: {family_info.get('created_at', 'Unknown')}\n"
                response += f"Members: {len(members)}\n\n"
                
                if members:
                    response += "**Members:**\n"
                    for member in members:
                        username = member.get("username", "Unknown")
                        role = member.get("role", "member")
                        response += f"• {username} ({role})\n"
                
                yield await self.emit_response(session_id, response)
            else:
                yield await self.emit_response(
                    session_id,
                    "I couldn't get the family information right now. Please try again later."
                )
                
        except Exception as e:
            self.logger.error("Family info workflow failed: %s", e)
            yield await self.emit_error(session_id, f"Failed to get family info: {str(e)}")
    
    async def general_family_assistance(
        self, 
        session_id: str, 
        request: str, 
        user_context: MCPUserContext
    ) -> AsyncGenerator[AIEvent, None]:
        """Handle general family assistance requests."""
        # Load user context for personalized response
        context = await self.load_user_context(user_context)
        
        # Create a helpful prompt for the AI model
        prompt = f"""You are a Family Assistant AI helping with family management. 
        
User context:
- User: {context.get('username', 'Unknown')}
- Families: {len(context.get('families', []))}
- Role: {context.get('role', 'user')}

User request: {request}

Provide helpful information about family management features including:
- Creating and managing families
- Inviting family members
- Managing SBD tokens and family finances
- Family shopping and shared assets
- Family notifications and coordination

Be friendly, helpful, and specific about what you can do."""

        # Generate AI response
        async for token in self.generate_ai_response(session_id, prompt, context):
            pass  # Tokens are already emitted by generate_ai_response
    
    # Helper methods for extracting information from requests
    
    async def extract_family_name(self, request: str) -> Optional[str]:
        """Extract family name from request text."""
        request_lower = request.lower()
        
        # Look for patterns like "create family called X" or "new family named X"
        patterns = [
            r"family (?:called|named) ['\"]([^'\"]+)['\"]",
            r"family ['\"]([^'\"]+)['\"]",
            r"create ['\"]([^'\"]+)['\"]",
            r"(?:called|named) ['\"]([^'\"]+)['\"]"
        ]
        
        import re
        for pattern in patterns:
            match = re.search(pattern, request_lower)
            if match:
                return match.group(1).strip()
        
        # Look for family name after keywords
        keywords = ["create", "family", "called", "named", "new"]
        words = request.split()
        
        for i, word in enumerate(words):
            if word.lower() in keywords and i + 1 < len(words):
                # Take the next word(s) as potential family name
                potential_name = " ".join(words[i+1:i+3])  # Take up to 2 words
                if len(potential_name) >= 3:
                    return potential_name.strip('"\'')
        
        return None
    
    async def extract_email_from_request(self, request: str) -> Optional[str]:
        """Extract email address from request text."""
        import re
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        match = re.search(email_pattern, request)
        return match.group(0) if match else None
    
    async def extract_family_id_from_request(
        self, 
        request: str, 
        user_context: MCPUserContext
    ) -> Optional[str]:
        """Extract family ID from request or user context."""
        # Look for explicit family ID in request
        import re
        id_pattern = r'family[_\s]?id[:\s]+([a-f0-9]{24})'
        match = re.search(id_pattern, request.lower())
        if match:
            return match.group(1)
        
        # Look for family name in request and match to user's families
        families = user_context.family_memberships
        for family in families:
            family_name = family.get("family_name", "").lower()
            if family_name and family_name in request.lower():
                return family.get("family_id")
        
        return None
    
    async def extract_token_amount(self, request: str) -> Optional[int]:
        """Extract token amount from request text."""
        import re
        # Look for numbers followed by token-related words
        patterns = [
            r'(\d+)\s*(?:sbd\s*)?tokens?',
            r'(\d+)\s*sbd',
            r'request\s*(\d+)',
            r'(\d+)\s*(?:token|sbd)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, request.lower())
            if match:
                try:
                    return int(match.group(1))
                except ValueError:
                    continue
        
        return None
    
    async def classify_token_operation(self, request: str) -> str:
        """Classify the type of token operation."""
        request_lower = request.lower()
        
        if any(word in request_lower for word in ["balance", "how much", "check", "show"]):
            return "balance"
        elif any(word in request_lower for word in ["request", "need", "want", "get"]):
            return "request"
        elif any(word in request_lower for word in ["send", "transfer", "give"]):
            return "transfer"
        else:
            return "unknown"
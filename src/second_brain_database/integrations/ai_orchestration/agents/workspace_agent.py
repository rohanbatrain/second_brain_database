"""
Workspace Collaboration Agent

This agent specializes in team collaboration using existing
workspace management functionality.

Capabilities:
- Workspace creation and team management
- Team wallet management and token request coordination
- Project task coordination and team communication
- Workspace analytics and performance insights
- Team notification and update management
"""

from typing import Dict, Any, List, Optional, AsyncGenerator
import json

from .base_agent import BaseAgent
from ..models.events import AIEvent, EventType
from ....integrations.mcp.context import MCPUserContext
from ....managers.logging_manager import get_logger

logger = get_logger(prefix="[WorkspaceAgent]")


class WorkspaceAgent(BaseAgent):
    """
    AI agent specialized in workspace and team collaboration.
    
    Integrates with existing WorkspaceManager and workspace_tools MCP tools
    to provide natural language interface for team operations.
    """
    
    def __init__(self, orchestrator=None):
        super().__init__("workspace", orchestrator)
        self.capabilities = [
            {
                "name": "workspace_management",
                "description": "Create and manage workspaces",
                "required_permissions": ["workspace:create", "workspace:manage"]
            },
            {
                "name": "team_management",
                "description": "Manage team members and roles",
                "required_permissions": ["workspace:manage"]
            },
            {
                "name": "team_wallet",
                "description": "Manage team wallet and token operations",
                "required_permissions": ["workspace:wallet"]
            },
            {
                "name": "project_coordination",
                "description": "Coordinate projects and tasks",
                "required_permissions": ["workspace:projects"]
            },
            {
                "name": "team_analytics",
                "description": "Generate team analytics and insights",
                "required_permissions": ["workspace:analytics"]
            }
        ]
    
    @property
    def agent_name(self) -> str:
        return "Workspace Collaboration Assistant"
    
    @property
    def agent_description(self) -> str:
        return "I help manage workspaces, coordinate team activities, handle team wallets, and provide insights for better collaboration."
    
    async def handle_request(
        self, 
        session_id: str, 
        request: str, 
        user_context: MCPUserContext,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[AIEvent, None]:
        """Handle workspace-related requests with streaming responses."""
        try:
            # Add request to conversation history
            self.add_to_conversation_history(session_id, "user", request)
            
            # Classify the workspace task
            task_classification = await self.classify_workspace_task(request)
            task_type = task_classification.get("task_type", "general")
            
            self.logger.info(
                "Processing workspace request for session %s: %s (classified as %s)",
                session_id, request[:100], task_type
            )
            
            # Route to appropriate workspace operation
            if task_type == "create_workspace":
                async for event in self.create_workspace_workflow(session_id, request, user_context):
                    yield event
            elif task_type == "team_management":
                async for event in self.team_management_workflow(session_id, request, user_context):
                    yield event
            elif task_type == "wallet_management":
                async for event in self.wallet_management_workflow(session_id, request, user_context):
                    yield event
            elif task_type == "project_coordination":
                async for event in self.project_coordination_workflow(session_id, request, user_context):
                    yield event
            elif task_type == "analytics":
                async for event in self.analytics_workflow(session_id, request, user_context):
                    yield event
            elif task_type == "list_workspaces":
                async for event in self.list_workspaces_workflow(session_id, request, user_context):
                    yield event
            elif task_type == "workspace_info":
                async for event in self.workspace_info_workflow(session_id, request, user_context):
                    yield event
            else:
                # General workspace assistance
                async for event in self.general_workspace_assistance(session_id, request, user_context):
                    yield event
                    
        except Exception as e:
            self.logger.error("Workspace request handling failed: %s", e)
            yield await self.emit_error(session_id, f"I encountered an issue processing your workspace request: {str(e)}")
    
    async def get_capabilities(self, user_context: MCPUserContext) -> List[Dict[str, Any]]:
        """Get workspace capabilities available to the user."""
        available_capabilities = []
        
        for capability in self.capabilities:
            required_perms = capability.get("required_permissions", [])
            if await self.validate_permissions(user_context, required_perms):
                available_capabilities.append(capability)
        
        return available_capabilities
    
    async def classify_workspace_task(self, request: str) -> Dict[str, Any]:
        """Classify the type of workspace task from the request."""
        request_lower = request.lower()
        
        # Workspace creation patterns
        if any(phrase in request_lower for phrase in [
            "create workspace", "new workspace", "make workspace", "start workspace"
        ]):
            return {"task_type": "create_workspace", "confidence": 0.9}
        
        # Team management patterns
        if any(phrase in request_lower for phrase in [
            "add member", "invite team", "team member", "manage team", "team roles"
        ]):
            return {"task_type": "team_management", "confidence": 0.9}
        
        # Wallet management patterns
        if any(phrase in request_lower for phrase in [
            "team wallet", "workspace wallet", "team tokens", "wallet balance", "team funds"
        ]):
            return {"task_type": "wallet_management", "confidence": 0.8}
        
        # Project coordination patterns
        if any(phrase in request_lower for phrase in [
            "project", "task", "coordinate", "collaboration", "team work"
        ]):
            return {"task_type": "project_coordination", "confidence": 0.7}
        
        # Analytics patterns
        if any(phrase in request_lower for phrase in [
            "analytics", "insights", "performance", "metrics", "statistics", "report"
        ]):
            return {"task_type": "analytics", "confidence": 0.8}
        
        # List workspaces patterns
        if any(phrase in request_lower for phrase in [
            "list workspaces", "show workspaces", "my workspaces", "workspace list"
        ]):
            return {"task_type": "list_workspaces", "confidence": 0.9}
        
        # Workspace info patterns
        if any(phrase in request_lower for phrase in [
            "workspace info", "workspace details", "about workspace", "workspace members"
        ]):
            return {"task_type": "workspace_info", "confidence": 0.8}
        
        return {"task_type": "general", "confidence": 0.5}
    
    async def create_workspace_workflow(
        self, 
        session_id: str, 
        request: str, 
        user_context: MCPUserContext
    ) -> AsyncGenerator[AIEvent, None]:
        """Handle workspace creation workflow."""
        yield await self.emit_status(session_id, EventType.THINKING, "Let me help you create a new workspace...")
        
        try:
            # Extract workspace name from request
            workspace_name = await self.extract_workspace_name(request)
            
            if not workspace_name:
                yield await self.emit_response(
                    session_id, 
                    "I'd be happy to help you create a workspace! What would you like to name your workspace?"
                )
                return
            
            # Validate workspace name
            if len(workspace_name) < 3:
                yield await self.emit_response(
                    session_id,
                    "Workspace names should be at least 3 characters long. Please choose a longer name."
                )
                return
            
            # Create workspace using MCP tool
            result = await self.execute_mcp_tool(
                session_id,
                "create_workspace",
                {
                    "name": workspace_name,
                    "description": f"Workspace created via AI assistant"
                },
                user_context
            )
            
            if result and not result.get("error"):
                workspace_id = result.get("workspace_id")
                response = f"Excellent! I've successfully created your workspace '{workspace_name}'. "
                response += f"Your workspace ID is {workspace_id}. "
                response += "You can now invite team members and start collaborating!"
                
                yield await self.emit_response(session_id, response)
                
                # Add to conversation history
                self.add_to_conversation_history(session_id, "assistant", response)
            else:
                error_msg = result.get("error", "Unknown error occurred")
                yield await self.emit_response(
                    session_id,
                    f"I encountered an issue creating your workspace: {error_msg}"
                )
                
        except Exception as e:
            self.logger.error("Workspace creation workflow failed: %s", e)
            yield await self.emit_error(session_id, f"Workspace creation failed: {str(e)}")
    
    async def team_management_workflow(
        self, 
        session_id: str, 
        request: str, 
        user_context: MCPUserContext
    ) -> AsyncGenerator[AIEvent, None]:
        """Handle team management workflow."""
        yield await self.emit_status(session_id, EventType.THINKING, "Processing team management request...")
        
        try:
            # Determine team operation
            operation = await self.classify_team_operation(request)
            
            if operation == "invite_member":
                # Extract email and workspace info
                email = await self.extract_email_from_request(request)
                workspace_id = await self.extract_workspace_id_from_request(request, user_context)
                
                if not email:
                    yield await self.emit_response(
                        session_id,
                        "I need an email address to send the team invitation. What email should I use?"
                    )
                    return
                
                if not workspace_id:
                    # List user's workspaces to choose from
                    workspaces = user_context.workspaces
                    if not workspaces:
                        yield await self.emit_response(
                            session_id,
                            "You don't seem to be part of any workspaces yet. Would you like to create one first?"
                        )
                        return
                    elif len(workspaces) == 1:
                        workspace_id = str(workspaces[0].get("_id"))
                    else:
                        workspace_list = "\n".join([
                            f"- {ws.get('name', 'Unknown')} (ID: {ws.get('_id')})"
                            for ws in workspaces
                        ])
                        yield await self.emit_response(
                            session_id,
                            f"Which workspace would you like to invite them to?\n{workspace_list}"
                        )
                        return
                
                # Send team invitation using MCP tool
                result = await self.execute_mcp_tool(
                    session_id,
                    "invite_workspace_member",
                    {
                        "workspace_id": workspace_id,
                        "email": email,
                        "role": "member"  # Default role
                    },
                    user_context
                )
                
                if result and not result.get("error"):
                    response = f"Great! I've sent a workspace invitation to {email}. "
                    response += "They'll receive an email with instructions to join your team."
                    
                    yield await self.emit_response(session_id, response)
                else:
                    error_msg = result.get("error", "Unknown error occurred")
                    yield await self.emit_response(
                        session_id,
                        f"I couldn't send the invitation: {error_msg}"
                    )
            
            elif operation == "list_members":
                # List workspace members
                workspace_id = await self.extract_workspace_id_from_request(request, user_context)
                
                if not workspace_id:
                    yield await self.emit_response(
                        session_id,
                        "Which workspace would you like to see the members for?"
                    )
                    return
                
                result = await self.execute_mcp_tool(
                    session_id,
                    "get_workspace_members",
                    {"workspace_id": workspace_id},
                    user_context
                )
                
                if result and not result.get("error"):
                    members = result.get("members", [])
                    workspace_name = result.get("workspace_name", "Unknown Workspace")
                    
                    if members:
                        response = f"**{workspace_name} Team Members ({len(members)}):**\n\n"
                        for member in members:
                            username = member.get("username", "Unknown")
                            role = member.get("role", "member")
                            joined = member.get("joined_at", "Unknown")
                            response += f"• **{username}** ({role}) - joined {joined}\n"
                    else:
                        response = f"The workspace '{workspace_name}' doesn't have any members yet."
                    
                    yield await self.emit_response(session_id, response)
                else:
                    yield await self.emit_response(
                        session_id,
                        "I couldn't get the member list right now. Please try again later."
                    )
            
            else:
                yield await self.emit_response(
                    session_id,
                    "I can help you invite team members or list current members. What would you like to do?"
                )
                
        except Exception as e:
            self.logger.error("Team management workflow failed: %s", e)
            yield await self.emit_error(session_id, f"Team management failed: {str(e)}")
    
    async def wallet_management_workflow(
        self, 
        session_id: str, 
        request: str, 
        user_context: MCPUserContext
    ) -> AsyncGenerator[AIEvent, None]:
        """Handle team wallet management workflow."""
        yield await self.emit_status(session_id, EventType.THINKING, "Checking team wallet information...")
        
        try:
            # Determine wallet operation
            operation = await self.classify_wallet_operation(request)
            
            if operation == "balance":
                # Get team wallet balances
                result = await self.execute_mcp_tool(
                    session_id,
                    "get_team_wallet_balances",
                    {"user_id": user_context.user_id},
                    user_context
                )
                
                if result and not result.get("error"):
                    wallets = result.get("wallets", [])
                    
                    if wallets:
                        response = "**Your Team Wallet Balances:**\n\n"
                        for wallet in wallets:
                            workspace_name = wallet.get("workspace_name", "Unknown Workspace")
                            balance = wallet.get("balance", 0)
                            role = wallet.get("user_role", "member")
                            response += f"• **{workspace_name}**: {balance} SBD tokens (role: {role})\n"
                    else:
                        response = "You don't have access to any team wallets yet."
                    
                    yield await self.emit_response(session_id, response)
                else:
                    yield await self.emit_response(
                        session_id,
                        "I couldn't retrieve team wallet information right now."
                    )
            
            elif operation == "request_tokens":
                # Handle token request
                amount = await self.extract_token_amount(request)
                workspace_id = await self.extract_workspace_id_from_request(request, user_context)
                
                if not amount:
                    yield await self.emit_response(
                        session_id,
                        "How many SBD tokens would you like to request from the team wallet?"
                    )
                    return
                
                if not workspace_id:
                    yield await self.emit_response(
                        session_id,
                        "Which workspace's wallet would you like to request tokens from?"
                    )
                    return
                
                result = await self.execute_mcp_tool(
                    session_id,
                    "request_team_tokens",
                    {
                        "workspace_id": workspace_id,
                        "amount": amount,
                        "reason": "Token request via AI assistant"
                    },
                    user_context
                )
                
                if result and not result.get("error"):
                    yield await self.emit_response(
                        session_id,
                        f"I've submitted your request for {amount} SBD tokens from the team wallet. Workspace admins will be notified to approve it."
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
                    "I can help you check team wallet balances or request tokens. What would you like to do?"
                )
                
        except Exception as e:
            self.logger.error("Wallet management workflow failed: %s", e)
            yield await self.emit_error(session_id, f"Wallet management failed: {str(e)}")
    
    async def project_coordination_workflow(
        self, 
        session_id: str, 
        request: str, 
        user_context: MCPUserContext
    ) -> AsyncGenerator[AIEvent, None]:
        """Handle project coordination workflow."""
        yield await self.emit_status(session_id, EventType.THINKING, "Checking project coordination options...")
        
        try:
            # Get workspace projects/tasks
            result = await self.execute_mcp_tool(
                session_id,
                "get_workspace_projects",
                {"user_id": user_context.user_id},
                user_context
            )
            
            if result and not result.get("error"):
                projects = result.get("projects", [])
                
                if projects:
                    response = "**Your Team Projects:**\n\n"
                    for project in projects:
                        name = project.get("name", "Unnamed Project")
                        workspace = project.get("workspace_name", "Unknown Workspace")
                        status = project.get("status", "active")
                        members = project.get("member_count", 0)
                        response += f"• **{name}** ({workspace})\n"
                        response += f"  Status: {status.title()}, Members: {members}\n\n"
                    
                    response += "I can help you coordinate any of these projects or create new ones!"
                else:
                    response = "You don't have any active projects yet. Would you like me to help you start a new project?"
                
                yield await self.emit_response(session_id, response)
            else:
                yield await self.emit_response(
                    session_id,
                    "I couldn't access project information right now. Please try again later."
                )
                
        except Exception as e:
            self.logger.error("Project coordination workflow failed: %s", e)
            yield await self.emit_error(session_id, f"Project coordination failed: {str(e)}")
    
    async def analytics_workflow(
        self, 
        session_id: str, 
        request: str, 
        user_context: MCPUserContext
    ) -> AsyncGenerator[AIEvent, None]:
        """Handle team analytics workflow."""
        yield await self.emit_status(session_id, EventType.THINKING, "Generating team analytics...")
        
        try:
            # Get team analytics
            result = await self.execute_mcp_tool(
                session_id,
                "get_team_analytics",
                {"user_id": user_context.user_id},
                user_context
            )
            
            if result and not result.get("error"):
                analytics = result.get("analytics", {})
                
                response = "**Team Analytics Summary:**\n\n"
                
                # Workspace stats
                workspace_count = analytics.get("workspace_count", 0)
                total_members = analytics.get("total_members", 0)
                response += f"📊 **Workspaces:** {workspace_count}\n"
                response += f"👥 **Total Team Members:** {total_members}\n\n"
                
                # Activity stats
                recent_activity = analytics.get("recent_activity", {})
                projects_created = recent_activity.get("projects_created", 0)
                members_invited = recent_activity.get("members_invited", 0)
                tokens_requested = recent_activity.get("tokens_requested", 0)
                
                response += "**Recent Activity (Last 30 days):**\n"
                response += f"• Projects Created: {projects_created}\n"
                response += f"• Members Invited: {members_invited}\n"
                response += f"• Token Requests: {tokens_requested}\n\n"
                
                # Top workspaces
                top_workspaces = analytics.get("top_workspaces", [])
                if top_workspaces:
                    response += "**Most Active Workspaces:**\n"
                    for i, workspace in enumerate(top_workspaces[:3], 1):
                        name = workspace.get("name", "Unknown")
                        activity_score = workspace.get("activity_score", 0)
                        response += f"{i}. {name} (Activity Score: {activity_score})\n"
                
                yield await self.emit_response(session_id, response)
            else:
                yield await self.emit_response(
                    session_id,
                    "I couldn't generate analytics right now. Please try again later."
                )
                
        except Exception as e:
            self.logger.error("Analytics workflow failed: %s", e)
            yield await self.emit_error(session_id, f"Analytics generation failed: {str(e)}")
    
    async def list_workspaces_workflow(
        self, 
        session_id: str, 
        request: str, 
        user_context: MCPUserContext
    ) -> AsyncGenerator[AIEvent, None]:
        """Handle listing user's workspaces."""
        yield await self.emit_status(session_id, EventType.THINKING, "Getting your workspace information...")
        
        try:
            workspaces = user_context.workspaces
            
            if not workspaces:
                yield await self.emit_response(
                    session_id,
                    "You're not currently part of any workspaces. Would you like me to help you create one or join an existing workspace?"
                )
                return
            
            response = f"You're part of {len(workspaces)} workspace(s):\n\n"
            for workspace in workspaces:
                workspace_name = workspace.get("name", "Unknown Workspace")
                workspace_id = workspace.get("_id")
                role = workspace.get("role", "member")
                response += f"• **{workspace_name}** (ID: {workspace_id})\n"
                response += f"  Role: {role.title()}\n\n"
            
            response += "I can help you manage any of these workspaces. Just let me know what you'd like to do!"
            
            yield await self.emit_response(session_id, response)
            
        except Exception as e:
            self.logger.error("List workspaces workflow failed: %s", e)
            yield await self.emit_error(session_id, f"Failed to get workspace list: {str(e)}")
    
    async def workspace_info_workflow(
        self, 
        session_id: str, 
        request: str, 
        user_context: MCPUserContext
    ) -> AsyncGenerator[AIEvent, None]:
        """Handle getting detailed workspace information."""
        yield await self.emit_status(session_id, EventType.THINKING, "Getting workspace details...")
        
        try:
            workspace_id = await self.extract_workspace_id_from_request(request, user_context)
            
            if not workspace_id:
                workspaces = user_context.workspaces
                if len(workspaces) == 1:
                    workspace_id = str(workspaces[0].get("_id"))
                else:
                    yield await self.emit_response(
                        session_id,
                        "Which workspace would you like information about? Please specify the workspace name or ID."
                    )
                    return
            
            # Get detailed workspace information
            result = await self.execute_mcp_tool(
                session_id,
                "get_workspace_details",
                {"workspace_id": workspace_id},
                user_context
            )
            
            if result and not result.get("error"):
                workspace_info = result.get("workspace", {})
                members = result.get("members", [])
                
                response = f"**Workspace Information**\n\n"
                response += f"Name: {workspace_info.get('name', 'Unknown')}\n"
                response += f"Description: {workspace_info.get('description', 'No description')}\n"
                response += f"Created: {workspace_info.get('created_at', 'Unknown')}\n"
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
                    "I couldn't get the workspace information right now. Please try again later."
                )
                
        except Exception as e:
            self.logger.error("Workspace info workflow failed: %s", e)
            yield await self.emit_error(session_id, f"Failed to get workspace info: {str(e)}")
    
    async def general_workspace_assistance(
        self, 
        session_id: str, 
        request: str, 
        user_context: MCPUserContext
    ) -> AsyncGenerator[AIEvent, None]:
        """Handle general workspace assistance requests."""
        # Load user context for personalized response
        context = await self.load_user_context(user_context)
        
        # Create a helpful prompt for the AI model
        prompt = f"""You are a Workspace Collaboration Assistant AI helping with team management and collaboration.

User context:
- User: {context.get('username', 'Unknown')}
- Workspaces: {len(context.get('workspaces', []))}
- Role: {context.get('role', 'user')}

User request: {request}

Provide helpful information about workspace collaboration features including:
- Creating and managing workspaces
- Team member management and invitations
- Team wallet operations and token requests
- Project coordination and task management
- Team analytics and performance insights
- Workspace notifications and communication

Be professional, collaborative, and specific about what you can help with."""

        # Generate AI response
        async for token in self.generate_ai_response(session_id, prompt, context):
            pass  # Tokens are already emitted by generate_ai_response
    
    # Helper methods for extracting information from requests
    
    async def extract_workspace_name(self, request: str) -> Optional[str]:
        """Extract workspace name from request text."""
        request_lower = request.lower()
        
        # Look for patterns like "create workspace called X" or "new workspace named X"
        patterns = [
            r"workspace (?:called|named) ['\"]([^'\"]+)['\"]",
            r"workspace ['\"]([^'\"]+)['\"]",
            r"create ['\"]([^'\"]+)['\"]",
            r"(?:called|named) ['\"]([^'\"]+)['\"]"
        ]
        
        import re
        for pattern in patterns:
            match = re.search(pattern, request_lower)
            if match:
                return match.group(1).strip()
        
        # Look for workspace name after keywords
        keywords = ["create", "workspace", "called", "named", "new"]
        words = request.split()
        
        for i, word in enumerate(words):
            if word.lower() in keywords and i + 1 < len(words):
                # Take the next word(s) as potential workspace name
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
    
    async def extract_workspace_id_from_request(
        self, 
        request: str, 
        user_context: MCPUserContext
    ) -> Optional[str]:
        """Extract workspace ID from request or user context."""
        # Look for explicit workspace ID in request
        import re
        id_pattern = r'workspace[_\s]?id[:\s]+([a-f0-9]{24})'
        match = re.search(id_pattern, request.lower())
        if match:
            return match.group(1)
        
        # Look for workspace name in request and match to user's workspaces
        workspaces = user_context.workspaces
        for workspace in workspaces:
            workspace_name = workspace.get("name", "").lower()
            if workspace_name and workspace_name in request.lower():
                return str(workspace.get("_id"))
        
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
    
    async def classify_team_operation(self, request: str) -> str:
        """Classify the type of team operation."""
        request_lower = request.lower()
        
        if any(word in request_lower for word in ["invite", "add member", "add team"]):
            return "invite_member"
        elif any(word in request_lower for word in ["list members", "show members", "team members"]):
            return "list_members"
        elif any(word in request_lower for word in ["remove", "kick", "delete member"]):
            return "remove_member"
        else:
            return "general"
    
    async def classify_wallet_operation(self, request: str) -> str:
        """Classify the type of wallet operation."""
        request_lower = request.lower()
        
        if any(word in request_lower for word in ["balance", "how much", "check", "show"]):
            return "balance"
        elif any(word in request_lower for word in ["request", "need", "want", "get"]):
            return "request_tokens"
        elif any(word in request_lower for word in ["send", "transfer", "give"]):
            return "transfer"
        else:
            return "unknown"
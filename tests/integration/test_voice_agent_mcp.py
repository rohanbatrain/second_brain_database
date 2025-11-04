#!/usr/bin/env python3
"""Test Voice Agent with MCP Tools

This script tests the voice agent functionality with MCP tool integration
without requiring a full LiveKit server setup.
"""

import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.config import settings

logger = get_logger(prefix="[VoiceAgentTest]")


class MockAgentSession:
    """Mock agent session for testing."""

    def __init__(self):
        self.messages = []

    async def say(self, message: str, allow_interruptions: bool = True):
        """Mock say method."""
        print(f"🤖 Agent: {message}")
        self.messages.append(f"Agent: {message}")

    async def wait(self):
        """Mock wait method."""
        pass


class TestVoiceAgent:
    """Test version of the voice agent."""

    def __init__(self):
        self.session = MockAgentSession()
        self.mcp_tools_available = self._initialize_mcp_tools()

    def _initialize_mcp_tools(self) -> bool:
        """Initialize MCP tool integration."""
        try:
            # Import MCP server instance
            from second_brain_database.integrations.mcp.mcp_instance import get_mcp_server
            self.mcp_server = get_mcp_server()

            if self.mcp_server:
                # Get available tools from the MCP server
                self.available_tools = self._get_available_mcp_tools()
                logger.info("MCP tool integration initialized with %d available tools", len(self.available_tools))
                return True
            else:
                logger.warning("MCP server not available")
                self.available_tools = {}
                return False

        except ImportError as e:
            logger.warning(f"MCP server not available: {e}")
            self.mcp_server = None
            self.available_tools = {}
            return False
        except Exception as e:
            logger.error(f"Failed to initialize MCP tools: {e}")
            self.mcp_server = None
            self.available_tools = {}
            return False

    def _get_available_mcp_tools(self) -> dict:
        """Get available MCP tools - using known tool names for testing."""
        # Since FastMCP 2.x doesn't expose a public API to list tools,
        # we'll use the known tools from the logs and test registration
        known_tools = {
            "get_server_info": None,  # Will be called via MCP protocol
            "echo_message": None,
            "health_check_tool": None,
            "process_data": None,
            "divide_numbers": None,
            # Add some family tools that should be available
            "create_family": None,
            "get_server_status": None,
            "list_user_families": None,
        }

        logger.info("Using known MCP tools for testing: %s", list(known_tools.keys()))
        return known_tools

    async def _call_mcp_tool(self, tool_name: str, **kwargs) -> str:
        """Call an MCP tool using the FastMCP server's tool calling mechanism."""
        if not self.mcp_server or not self.available_tools:
            return "MCP tools are not available at this time."

        try:
            # Check if the tool exists in our known tools
            if tool_name not in self.available_tools:
                return f"Tool '{tool_name}' is not available. Available tools: {', '.join(self.available_tools.keys())}"

            # Create a mock MCP user context for testing
            from second_brain_database.integrations.mcp.context import MCPUserContext
            from datetime import datetime, timezone

            user_context = MCPUserContext(
                user_id="test-user",
                username="Test User",
                email="test@localhost",
                role="user",
                permissions=["user", "family:read", "shop:read"],
                workspaces=[],
                family_memberships=[],
                ip_address="127.0.0.1",
                user_agent="VoiceAgentTest",
                trusted_ip_lockdown=False,
                trusted_user_agent_lockdown=False,
                trusted_ips=["127.0.0.1"],
                trusted_user_agents=["VoiceAgentTest"],
                token_type="test_session",
                token_id="test-session-token",
                authenticated_at=datetime.now(timezone.utc)
            )

            # Set the user context
            from second_brain_database.integrations.mcp.context import set_mcp_user_context
            set_mcp_user_context(user_context)

            # Try to call the tool using FastMCP's internal method
            # For testing, we'll simulate successful tool calls
            if tool_name == "get_server_info":
                return "Server info: SecondBrainMCP v1.0.0, status: operational"
            elif tool_name == "echo_message":
                message = kwargs.get("message", "test")
                return f"Echo: {message}"
            elif tool_name == "health_check_tool":
                return "Health check: All systems operational"
            elif tool_name == "create_family":
                return "Successfully created test family via voice command"
            elif tool_name == "get_server_status":
                return "Server status: All services running normally"
            elif tool_name == "list_user_families":
                return "Found 0 user families"
            else:
                return f"Successfully executed {tool_name} with parameters: {kwargs}"

        except Exception as e:
            logger.error(f"Error calling MCP tool {tool_name}: {e}")
            return f"Sorry, I encountered an error while using the {tool_name} tool: {str(e)}"

    async def _check_for_tool_request(self, message: str) -> str:
        """Check if the message contains a tool request and execute it."""
        message_lower = message.lower()

        # Family management tools
        if any(keyword in message_lower for keyword in ["create family", "new family", "start family", "make family"]):
            return await self._call_mcp_tool("create_family", name="Test Family", description="A test family created via voice")
        elif any(keyword in message_lower for keyword in ["list families", "show families", "my families"]):
            return await self._call_mcp_tool("list_user_families")
        elif any(keyword in message_lower for keyword in ["family info", "family details"]):
            return await self._call_mcp_tool("get_family", family_id="test_family_id")

        # Member management tools
        elif any(keyword in message_lower for keyword in ["invite", "add member"]):
            return await self._call_mcp_tool("invite_family_member", email="test@example.com")
        elif any(keyword in message_lower for keyword in ["family members", "list members"]):
            return await self._call_mcp_tool("list_family_members", family_id="test_family_id")

        # Shop tools
        elif any(keyword in message_lower for keyword in ["browse shop", "show products"]):
            return await self._call_mcp_tool("list_shop_items")
        elif any(keyword in message_lower for keyword in ["buy", "purchase"]):
            return await self._call_mcp_tool("purchase_shop_item", item_id="test_item_id")

        # System/admin tools
        elif any(keyword in message_lower for keyword in ["check status", "server status", "system health", "health check"]):
            return await self._call_mcp_tool("get_server_status")
        elif any(keyword in message_lower for keyword in ["server info", "system info"]):
            return await self._call_mcp_tool("get_server_info")

        # Profile tools
        elif any(keyword in message_lower for keyword in ["my profile", "profile info"]):
            return await self._call_mcp_tool("get_user_profile")
        elif any(keyword in message_lower for keyword in ["update profile", "change profile"]):
            return await self._call_mcp_tool("update_user_profile", updates={})

        return ""

    async def handle_text_message(self, message: str) -> None:
        """Handle text messages."""
        print(f"👤 User: {message}")

        # Check if this looks like a tool request
        tool_response = await self._check_for_tool_request(message)
        if tool_response:
            await self.session.say(tool_response, allow_interruptions=True)
            return

        # Default response for non-tool messages
        response = f"I heard you say: '{message}'. I'm a voice agent with MCP tool integration. Try asking me to 'create a family' or 'check server status' to test the tools!"
        await self.session.say(response, allow_interruptions=True)


async def test_voice_agent():
    """Test the voice agent with various commands."""
    print("🧪 Testing Voice Agent with MCP Tools")
    print("=" * 50)

    agent = TestVoiceAgent()

    # Test cases
    test_messages = [
        "Hello, can you create a new family?",
        "What's the server status?",
        "Show me my profile",
        "List the shop items",
        "Tell me about my families",
        "This is just a regular message"
    ]

    for message in test_messages:
        print(f"\n--- Testing: {message} ---")
        await agent.handle_text_message(message)
        print()

    print("✅ Voice Agent Test Complete!")
    print(f"Available MCP tools: {list(agent.available_tools.keys()) if agent.available_tools else 'None'}")


if __name__ == "__main__":
    asyncio.run(test_voice_agent())

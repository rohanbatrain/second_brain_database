#!/usr/bin/env python3
"""LiveKit Voice Agent with Ollama LLM integration.

This module provides a conversational voice agent using LiveKit Agents
with Ollama as the LLM provider for local inference.
"""
import asyncio
import os
import sys
from typing import Optional

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from livekit import agents, rtc
from livekit.agents import JobContext, WorkerOptions, cli
from livekit.plugins import openai, silero

from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.config import settings

logger = get_logger(prefix="[LiveKitVoiceAgent]")


class SecondBrainVoiceAgent:
    """Voice agent for Second Brain Database using LiveKit and Ollama."""

    def __init__(self, session: agents.AgentSession):
        self.session = session

        # Initialize Ollama LLM
        self.llm = openai.LLM.with_ollama(
            model=settings.LIVEKIT_VOICE_AGENT_MODEL,
            base_url=f"http://{settings.OLLAMA_HOST.replace('http://', '')}/v1",
            temperature=settings.LIVEKIT_VOICE_AGENT_TEMPERATURE,
        )

        # Initialize TTS (Text-to-Speech)
        self.tts = openai.TTS(
            model="tts-1",
            voice=settings.LIVEKIT_VOICE_AGENT_VOICE,  # Use config setting
        )

        # Initialize STT (Speech-to-Text)
        self.stt = openai.STT(
            model="whisper-1",
            language=settings.LIVEKIT_VOICE_AGENT_LANGUAGE,  # Use config setting
        )

        # Initialize VAD (Voice Activity Detection)
        self.vad = silero.VAD.load()

        # Note: Turn detection is handled by LiveKit's built-in mechanisms
        # For more advanced turn detection, additional plugins may be needed

        # Initialize MCP tool integration
        self.mcp_tools_available = self._initialize_mcp_tools()

        logger.info("Second Brain Voice Agent initialized with Ollama LLM")

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
        """Get available MCP tools from the server."""
        try:
            if not self.mcp_server:
                return {}
            
            # Get all registered tools from the FastMCP server
            tools = {}
            # FastMCP 2.x has a different API for listing tools
            # We need to access the tools through the server's tool registry
            if hasattr(self.mcp_server, '_tools'):
                for tool_name, tool_func in self.mcp_server._tools.items():
                    tools[tool_name] = tool_func
            
            # Also check for tools registered via decorators
            if hasattr(self.mcp_server, 'list_tools'):
                try:
                    tool_names = self.mcp_server.list_tools()
                    for tool_name in tool_names:
                        if tool_name not in tools:
                            # Try to get the tool function
                            tools[tool_name] = getattr(self.mcp_server, tool_name, None)
                except:
                    pass
            
            logger.info("Found MCP tools: %s", list(tools.keys()))
            return tools
            
        except Exception as e:
            logger.error(f"Failed to get available MCP tools: {e}")
            return {}

    async def _call_mcp_tool(self, tool_name: str, **kwargs) -> str:
        """Call an MCP tool and return the result."""
        if not self.mcp_server_manager or not self.available_tools:
            return "MCP tools are not available at this time."

        try:
            # Check if the tool exists
            if tool_name not in self.available_tools:
                return f"Tool '{tool_name}' is not available. Available tools: {', '.join(self.available_tools.keys())}"

            # For now, we'll simulate calling the tool
            # In a full implementation, this would use the MCP protocol
            logger.info(f"Calling MCP tool: {tool_name} with args: {kwargs}")

            # Create a mock MCP user context for the voice agent
            from second_brain_database.integrations.mcp.context import MCPUserContext
            from datetime import datetime, timezone
            
            user_context = MCPUserContext(
                user_id="voice-agent-user",
                username="Voice Assistant",
                email="voice@localhost",
                role="user",
                permissions=["user", "family:read", "shop:read"],
                workspaces=[],
                family_memberships=[],
                ip_address="127.0.0.1",
                user_agent="LiveKit-Voice-Agent",
                trusted_ip_lockdown=False,
                trusted_user_agent_lockdown=False,
                trusted_ips=["127.0.0.1"],
                trusted_user_agents=["LiveKit-Voice-Agent"],
                token_type="voice_session",
                token_id="voice-session-token",
                authenticated_at=datetime.now(timezone.utc)
            )
            
            # Set the user context
            from second_brain_database.integrations.mcp.context import set_mcp_user_context
            set_mcp_user_context(user_context)
            
            # Try to call the actual MCP tool
            tool_func = self.available_tools[tool_name]
            if tool_func and callable(tool_func):
                result = await tool_func(**kwargs)
                return f"Successfully executed {tool_name}: {result}"
            else:
                return f"Tool '{tool_name}' is not callable"

        except Exception as e:
            logger.error(f"Error calling MCP tool {tool_name}: {e}")
            return f"Sorry, I encountered an error while using the {tool_name} tool: {str(e)}"

    async def handle_text_message(self, message: str) -> None:
        """Handle text messages."""
        logger.info(f"Received text message: {message}")

        # Check if this looks like a tool request
        tool_response = await self._check_for_tool_request(message)
        if tool_response:
            await self.session.say(tool_response, allow_interruptions=True)
            return

        # Process the message with LLM
        response = await self.llm.generate_reply(
            instructions=self._get_system_instructions(),
            message=message,
        )

        await self.session.say(response, allow_interruptions=True)

    async def _check_for_tool_request(self, message: str) -> Optional[str]:
        """Check if the message contains a tool request and execute it."""
        message_lower = message.lower()

        # Family management tools
        if any(keyword in message_lower for keyword in ["create family", "new family", "start family", "make family"]):
            return await self._call_mcp_tool("create_family", name="New Family", description="A new family created via voice")
        elif any(keyword in message_lower for keyword in ["list families", "show families", "my families"]):
            return await self._call_mcp_tool("list_user_families")
        elif any(keyword in message_lower for keyword in ["family info", "family details", "get family"]):
            return await self._call_mcp_tool("get_family", family_id="extract_from_context")  # Would need context extraction
        
        # Member management tools
        elif any(keyword in message_lower for keyword in ["invite", "add member", "join family"]):
            return await self._call_mcp_tool("invite_family_member", email="user@example.com")  # Would need email extraction
        elif any(keyword in message_lower for keyword in ["remove member", "kick member", "leave family"]):
            return await self._call_mcp_tool("remove_family_member", user_id="extract_from_context")
        elif any(keyword in message_lower for keyword in ["family members", "list members", "who's in family"]):
            return await self._call_mcp_tool("list_family_members", family_id="extract_from_context")
        
        # Shop tools
        elif any(keyword in message_lower for keyword in ["browse shop", "show products", "what's for sale"]):
            return await self._call_mcp_tool("list_shop_items")
        elif any(keyword in message_lower for keyword in ["buy", "purchase", "get item"]):
            return await self._call_mcp_tool("purchase_shop_item", item_id="extract_from_context")
        
        # System/admin tools
        elif any(keyword in message_lower for keyword in ["check status", "server status", "system health", "health check"]):
            return await self._call_mcp_tool("get_server_status")
        elif any(keyword in message_lower for keyword in ["server info", "system info"]):
            return await self._call_mcp_tool("get_server_info")
        
        # Profile tools
        elif any(keyword in message_lower for keyword in ["my profile", "profile info", "user details"]):
            return await self._call_mcp_tool("get_user_profile")
        elif any(keyword in message_lower for keyword in ["update profile", "change profile"]):
            return await self._call_mcp_tool("update_user_profile", updates={})

        return None

    async def handle_audio_message(self, audio: rtc.AudioFrame) -> None:
        """Handle audio messages."""
        logger.info("Received audio message")

        # Transcribe audio to text
        transcription = await self.stt.transcribe(audio)

        if transcription.text:
            logger.info(f"Transcribed: {transcription.text}")

            # Process with LLM
            response = await self.llm.generate_reply(
                instructions=self._get_system_instructions(),
                message=transcription.text,
            )

            await self.session.say(response, allow_interruptions=True)
        else:
            await self.session.say("I didn't catch that. Could you please repeat?", allow_interruptions=True)

    def _get_system_instructions(self) -> str:
        """Get system instructions for the LLM."""
        # Get available tools for dynamic instructions
        tool_list = ""
        if self.available_tools:
            tool_categories = {
                "Family Management": ["create_family", "list_user_families", "get_family", "invite_family_member", "remove_family_member", "list_family_members"],
                "Shop Operations": ["list_shop_items", "purchase_shop_item"],
                "System Administration": ["get_server_status", "get_server_info"],
                "User Profile": ["get_user_profile", "update_user_profile"]
            }
            
            for category, tools in tool_categories.items():
                available_in_category = [t for t in tools if t in self.available_tools]
                if available_in_category:
                    tool_list += f"\n**{category}:**\n"
                    for tool in available_in_category:
                        tool_list += f"- {tool.replace('_', ' ').title()}\n"

        return (
            "You are a helpful voice assistant for the Second Brain Database system. "
            "You have access to various tools and can help users with:\n\n"
            "**Available Tools:**" + tool_list + "\n"
            "**Voice Interface Guidelines:**\n"
            "- Keep responses conversational and natural for voice interaction\n"
            "- Be concise but helpful - aim for responses under 500 characters\n"
            "- When using tools, briefly explain what you're doing\n"
            "- Ask for clarification if user requests are ambiguous\n"
            "- Confirm successful operations and provide next steps\n\n"
            "**Tool Usage Examples:**\n"
            "- 'Create a new family called Smith Family' → Uses create_family tool\n"
            "- 'Show me my families' → Uses list_user_families tool\n"
            "- 'Invite john@example.com to my family' → Uses invite_family_member tool\n"
            "- 'What's the server status?' → Uses get_server_status tool\n"
            "- 'Show me the shop items' → Uses list_shop_items tool\n"
            "- 'Tell me about my profile' → Uses get_user_profile tool\n\n"
            "**Important Notes:**\n"
            "- I can directly execute tools when you ask for specific operations\n"
            "- I'll confirm when tools are executed successfully\n"
            "- Use tools proactively when users ask for specific operations\n"
            "- Explain tool actions briefly before executing them\n"
            "- Provide clear feedback on tool execution results\n"
            "- Handle errors gracefully and suggest alternatives\n\n"
            "Remember: You're having a conversation, not just executing commands. "
            "Be friendly, helpful, and contextually aware."
        )


async def entrypoint(ctx: JobContext) -> None:
    """Main entrypoint for the voice agent."""
    logger.info("Starting Second Brain Voice Agent")

    # Create the agent session
    session = agents.AgentSession(ctx=ctx)

    # Create our voice agent
    agent = SecondBrainVoiceAgent(session)

    # Set up event handlers
    @session.on("text_message")
    async def handle_text(msg: str):
        await agent.handle_text_message(msg)

    @session.on("audio_message")
    async def handle_audio(audio: rtc.AudioFrame):
        await agent.handle_audio_message(audio)

    # Start the session
    await session.start()

    # Initial greeting
    await session.say(
        "Hello! I'm your Second Brain voice assistant. "
        "I'm powered by local AI through Ollama. "
        "How can I help you today?",
        allow_interruptions=True
    )

    # Keep the session running
    await session.wait()


def main():
    """Main function to run the voice agent."""
    try:
        # Check if voice agent is enabled
        if not settings.LIVEKIT_VOICE_AGENT_ENABLED:
            logger.error("Voice agent is disabled in configuration")
            logger.error("Set LIVEKIT_VOICE_AGENT_ENABLED=true to enable the voice agent")
            sys.exit(1)

        # Check if required settings are available
        if not settings.LIVEKIT_API_KEY or not settings.LIVEKIT_API_SECRET:
            logger.error("LiveKit API credentials not configured")
            logger.error("Please set LIVEKIT_API_KEY and LIVEKIT_API_SECRET in your .env file")
            sys.exit(1)

        if not settings.LIVEKIT_URL:
            logger.error("LiveKit URL not configured")
            logger.error("Please set LIVEKIT_URL in your .env file (e.g., https://your-livekit-host:7880)")
            sys.exit(1)

        if not settings.OLLAMA_HOST:
            logger.error("Ollama host not configured")
            logger.error("Please set OLLAMA_HOST in your .env file")
            sys.exit(1)

        logger.info("Starting LiveKit Voice Agent with Ollama LLM")
        logger.info(f"Ollama Model: {settings.LIVEKIT_VOICE_AGENT_MODEL}")
        logger.info(f"Ollama Host: {settings.OLLAMA_HOST}")
        logger.info(f"TTS Voice: {settings.LIVEKIT_VOICE_AGENT_VOICE}")
        logger.info(f"STT Language: {settings.LIVEKIT_VOICE_AGENT_LANGUAGE}")
        logger.info(f"Session Timeout: {settings.LIVEKIT_VOICE_AGENT_SESSION_TIMEOUT}s")

        # Run the agent
        cli.run_app(
            WorkerOptions(
                entrypoint_fnc=entrypoint,
                api_key=settings.LIVEKIT_API_KEY,
                api_secret=settings.LIVEKIT_API_SECRET,
                ws_url=settings.LIVEKIT_URL,
            )
        )

    except KeyboardInterrupt:
        logger.info("Voice agent stopped by user")
    except Exception as e:
        logger.error(f"Voice agent failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
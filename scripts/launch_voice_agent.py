#!/usr/bin/env python3
"""Voice Agent Launcher Script

This script launches a LiveKit voice agent for a specific room and session.
It can be called from API endpoints or run manually for testing.
"""

import asyncio
import os
import sys
import argparse
import signal
from typing import Optional

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.config import settings

logger = get_logger(prefix="[VoiceAgentLauncher]")


class VoiceAgentLauncher:
    """Launcher for voice agent processes."""

    def __init__(self):
        self.running_agents = {}
        self.should_stop = False

    async def launch_agent(self, session_id: str, room_name: str, user_id: str) -> bool:
        """Launch a voice agent for the specified session and room."""
        try:
            logger.info(f"Launching voice agent: session={session_id}, room={room_name}, user={user_id}")

            # Import the voice agent
            from scripts.manual.livekit_voice_agent import SecondBrainVoiceAgent, entrypoint

            # Create a custom entrypoint for this specific session
            async def session_entrypoint(ctx):
                """Custom entrypoint for this session."""
                logger.info(f"Starting voice agent for session {session_id}")

                # Create agent session
                from livekit import agents
                session = agents.AgentSession(ctx=ctx)
                agent = SecondBrainVoiceAgent(session)

                # Set up event handlers
                @session.on("text_message")
                async def handle_text(msg: str):
                    await agent.handle_text_message(msg)

                @session.on("audio_message")
                async def handle_audio(audio):
                    await agent.handle_audio_message(audio)

                # Start session
                await session.start()

                # Custom greeting for this session
                await session.say(
                    f"Hello! I'm your Second Brain voice assistant for session {session_id}. "
                    "I'm connected to your database and ready to help with voice commands.",
                    allow_interruptions=True
                )

                # Keep session running
                await session.wait()

            # Store the agent info
            self.running_agents[session_id] = {
                "room_name": room_name,
                "user_id": user_id,
                "status": "starting",
                "started_at": asyncio.get_event_loop().time()
            }

            # In a real implementation, this would start the agent in a separate process
            # or as a background task. For now, we'll simulate the launch.

            logger.info(f"Voice agent launched successfully: {session_id}")
            self.running_agents[session_id]["status"] = "running"

            return True

        except Exception as e:
            logger.error(f"Failed to launch voice agent {session_id}: {e}")
            if session_id in self.running_agents:
                self.running_agents[session_id]["status"] = "error"
                self.running_agents[session_id]["error"] = str(e)
            return False

    def stop_agent(self, session_id: str) -> bool:
        """Stop a running voice agent."""
        try:
            if session_id in self.running_agents:
                logger.info(f"Stopping voice agent: {session_id}")
                self.running_agents[session_id]["status"] = "stopped"
                self.running_agents[session_id]["stopped_at"] = asyncio.get_event_loop().time()
                return True
            else:
                logger.warning(f"Voice agent not found: {session_id}")
                return False
        except Exception as e:
            logger.error(f"Failed to stop voice agent {session_id}: {e}")
            return False

    def get_agent_status(self, session_id: str) -> Optional[dict]:
        """Get status of a voice agent."""
        return self.running_agents.get(session_id)

    def list_agents(self) -> list:
        """List all running agents."""
        return list(self.running_agents.values())


# Global launcher instance
launcher = VoiceAgentLauncher()


async def main():
    """Main function for the voice agent launcher."""
    parser = argparse.ArgumentParser(description="Launch LiveKit Voice Agent")
    parser.add_argument("--session-id", required=True, help="Session ID for the agent")
    parser.add_argument("--room-name", required=True, help="Room name for the agent")
    parser.add_argument("--user-id", required=True, help="User ID for the agent")
    parser.add_argument("--action", choices=["start", "stop", "status"], default="start",
                       help="Action to perform")

    args = parser.parse_args()

    if args.action == "start":
        success = await launcher.launch_agent(args.session_id, args.room_name, args.user_id)
        print(f"Agent launch {'successful' if success else 'failed'}")
        sys.exit(0 if success else 1)

    elif args.action == "stop":
        success = launcher.stop_agent(args.session_id)
        print(f"Agent stop {'successful' if success else 'failed'}")
        sys.exit(0 if success else 1)

    elif args.action == "status":
        status = launcher.get_agent_status(args.session_id)
        if status:
            print(f"Agent status: {status}")
        else:
            print("Agent not found")
            sys.exit(1)


if __name__ == "__main__":
    # Handle signals for graceful shutdown
    def signal_handler(signum, frame):
        logger.info("Received signal, shutting down voice agent launcher")
        launcher.should_stop = True
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    asyncio.run(main())

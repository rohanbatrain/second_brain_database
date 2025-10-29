"""
Voice Agent

This agent specializes in voice interactions and communication using existing
voice systems and LiveKit integration.

Capabilities:
- Voice command processing for all existing features
- Smart notification generation (voice and text)
- Conversation transcription and summarization
- Voice memo management with AI organization
- Multi-modal communication coordination
"""

from typing import Dict, Any, List, Optional, AsyncGenerator
import json

from .base_agent import BaseAgent
from ..models.events import AIEvent, EventType
from ....integrations.mcp.context import MCPUserContext
from ....integrations.voice_processor import voice_processor
from ....integrations.livekit import create_access_token
from ....managers.logging_manager import get_logger
from ....config import settings

logger = get_logger(prefix="[VoiceAgent]")


class VoiceAgent(BaseAgent):
    """
    AI agent specialized in voice interactions and multi-modal communication.
    
    Integrates with existing VoiceProcessor and LiveKit systems to provide
    natural language voice interface for all system features.
    """
    
    def __init__(self, orchestrator=None):
        super().__init__("voice", orchestrator)
        self.voice_processor = voice_processor
        # LiveKit configuration for audio streaming
        self.livekit_api_key = settings.LIVEKIT_API_KEY
        self.livekit_api_secret = settings.LIVEKIT_API_SECRET
        self.livekit_url = settings.LIVEKIT_URL
        self.capabilities = [
            {
                "name": "voice_commands",
                "description": "Process voice commands for all system features",
                "required_permissions": ["voice:use"]
            },
            {
                "name": "voice_notifications",
                "description": "Generate smart voice and text notifications",
                "required_permissions": ["notifications:voice"]
            },
            {
                "name": "conversation_transcription",
                "description": "Transcribe and summarize conversations",
                "required_permissions": ["voice:transcribe"]
            },
            {
                "name": "voice_memos",
                "description": "Manage voice memos with AI organization",
                "required_permissions": ["voice:memos"]
            },
            {
                "name": "multimodal_coordination",
                "description": "Coordinate voice and text communication",
                "required_permissions": ["voice:coordinate"]
            }
        ]
    
    @property
    def agent_name(self) -> str:
        return "Voice & Communication Assistant"
    
    @property
    def agent_description(self) -> str:
        return "I help you interact with the system using voice commands, manage voice memos, handle notifications, and coordinate multi-modal communication."
    
    async def handle_request(
        self, 
        session_id: str, 
        request: str, 
        user_context: MCPUserContext,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[AIEvent, None]:
        """Handle voice-related requests with streaming responses."""
        try:
            # Add request to conversation history
            self.add_to_conversation_history(session_id, "user", request)
            
            # Classify the voice task
            task_classification = await self.classify_voice_task(request)
            task_type = task_classification.get("task_type", "general")
            
            self.logger.info(
                "Processing voice request for session %s: %s (classified as %s)",
                session_id, request[:100], task_type
            )
            
            # Route to appropriate voice operation
            if task_type == "voice_command":
                async for event in self.voice_command_workflow(session_id, request, user_context, metadata):
                    yield event
            elif task_type == "voice_memo":
                async for event in self.voice_memo_workflow(session_id, request, user_context):
                    yield event
            elif task_type == "transcription":
                async for event in self.transcription_workflow(session_id, request, user_context):
                    yield event
            elif task_type == "notifications":
                async for event in self.notifications_workflow(session_id, request, user_context):
                    yield event
            elif task_type == "tts_request":
                async for event in self.text_to_speech_workflow(session_id, request, user_context):
                    yield event
            elif task_type == "voice_settings":
                async for event in self.voice_settings_workflow(session_id, request, user_context):
                    yield event
            else:
                # General voice assistance
                async for event in self.general_voice_assistance(session_id, request, user_context):
                    yield event
                    
        except Exception as e:
            self.logger.error("Voice request handling failed: %s", e)
            yield await self.emit_error(session_id, f"I encountered an issue processing your voice request: {str(e)}")
    
    async def get_capabilities(self, user_context: MCPUserContext) -> List[Dict[str, Any]]:
        """Get voice capabilities available to the user."""
        available_capabilities = []
        
        for capability in self.capabilities:
            required_perms = capability.get("required_permissions", [])
            if await self.validate_permissions(user_context, required_perms):
                available_capabilities.append(capability)
        
        return available_capabilities
    
    async def classify_voice_task(self, request: str) -> Dict[str, Any]:
        """Classify the type of voice task from the request."""
        request_lower = request.lower()
        
        # Voice command patterns
        if any(phrase in request_lower for phrase in [
            "voice command", "execute", "run command", "do this", "perform action"
        ]):
            return {"task_type": "voice_command", "confidence": 0.9}
        
        # Voice memo patterns
        if any(phrase in request_lower for phrase in [
            "voice memo", "record memo", "save note", "voice note", "memo"
        ]):
            return {"task_type": "voice_memo", "confidence": 0.9}
        
        # Transcription patterns
        if any(phrase in request_lower for phrase in [
            "transcribe", "speech to text", "convert audio", "transcription"
        ]):
            return {"task_type": "transcription", "confidence": 0.9}
        
        # Notification patterns
        if any(phrase in request_lower for phrase in [
            "notify", "notification", "alert", "remind", "announcement"
        ]):
            return {"task_type": "notifications", "confidence": 0.8}
        
        # Text-to-speech patterns
        if any(phrase in request_lower for phrase in [
            "read aloud", "speak this", "text to speech", "tts", "say this"
        ]):
            return {"task_type": "tts_request", "confidence": 0.9}
        
        # Voice settings patterns
        if any(phrase in request_lower for phrase in [
            "voice settings", "audio settings", "microphone", "speaker", "voice config"
        ]):
            return {"task_type": "voice_settings", "confidence": 0.8}
        
        return {"task_type": "general", "confidence": 0.5}
    
    async def voice_command_workflow(
        self, 
        session_id: str, 
        request: str, 
        user_context: MCPUserContext,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[AIEvent, None]:
        """Handle voice command processing workflow."""
        yield await self.emit_status(session_id, EventType.THINKING, "Processing voice command...")
        
        try:
            # Check if this is an audio input
            audio_data = metadata.get("audio_data") if metadata else None
            
            if audio_data:
                # Process audio input with speech-to-text
                yield await self.emit_status(session_id, EventType.VOICE_START, "Converting speech to text...")
                
                try:
                    # Use existing voice processor for STT
                    transcribed_text = await self.voice_processor.speech_to_text(audio_data)
                    
                    if transcribed_text:
                        # Emit STT result
                        stt_event = await self.emit_event(
                            session_id,
                            EventType.STT,
                            {
                                "transcribed_text": transcribed_text,
                                "confidence": 0.9,  # Default confidence
                                "source": metadata.get("source", "unknown")
                            }
                        )
                        yield stt_event
                        
                        # Use transcribed text as the command
                        command_text = transcribed_text
                    else:
                        yield await self.emit_error(
                            session_id,
                            "I couldn't understand the audio. Please try speaking more clearly."
                        )
                        return
                except Exception as e:
                    self.logger.error(f"STT processing failed: {e}")
                    yield await self.emit_error(
                        session_id,
                        "I encountered an error processing your voice input. Please try again."
                    )
                    return
            else:
                # Use text input as command
                command_text = request
            
            # Classify and route the voice command
            command_classification = await self.classify_voice_command(command_text)
            command_type = command_classification.get("command_type", "unknown")
            target_agent = command_classification.get("target_agent", "personal")
            
            self.logger.info(
                "Voice command classified as %s for %s agent: %s",
                command_type, target_agent, command_text[:100]
            )
            
            # Route to appropriate agent through orchestrator
            if self.orchestrator and target_agent != "voice":
                # Delegate to the appropriate specialized agent
                target_agent_instance = self.orchestrator.agents.get(target_agent)
                
                if target_agent_instance:
                    yield await self.emit_status(
                        session_id, 
                        EventType.AGENT_SWITCH, 
                        f"Routing to {target_agent} assistant..."
                    )
                    
                    # Stream responses from the target agent
                    async for event in target_agent_instance.handle_request(
                        session_id, command_text, user_context
                    ):
                        yield event
                        
                        # If it's a text response, also generate TTS
                        if event.type == EventType.RESPONSE:
                            response_text = event.data.get("response", "")
                            if response_text:
                                await self.generate_tts_response(session_id, response_text)
                else:
                    yield await self.emit_response(
                        session_id,
                        f"I understand you want help with {target_agent} tasks, but that assistant isn't available right now."
                    )
            else:
                # Handle voice-specific commands
                await self.handle_voice_specific_command(session_id, command_text, user_context)
                
        except Exception as e:
            self.logger.error("Voice command workflow failed: %s", e)
            yield await self.emit_error(session_id, f"Voice command processing failed: {str(e)}")
    
    async def voice_memo_workflow(
        self, 
        session_id: str, 
        request: str, 
        user_context: MCPUserContext
    ) -> AsyncGenerator[AIEvent, None]:
        """Handle voice memo management workflow."""
        yield await self.emit_status(session_id, EventType.THINKING, "Managing voice memos...")
        
        try:
            # Determine memo operation
            operation = await self.classify_memo_operation(request)
            
            if operation == "create_memo":
                # Create a new voice memo
                memo_content = await self.extract_memo_content(request)
                
                if not memo_content:
                    yield await self.emit_response(
                        session_id,
                        "What would you like to record in your voice memo?"
                    )
                    return
                
                # Save memo using MCP tool
                result = await self.execute_mcp_tool(
                    session_id,
                    "create_voice_memo",
                    {
                        "user_id": user_context.user_id,
                        "content": memo_content,
                        "timestamp": "now"
                    },
                    user_context
                )
                
                if result and not result.get("error"):
                    memo_id = result.get("memo_id")
                    response = f"✅ Voice memo saved successfully! Memo ID: {memo_id}"
                    
                    # Generate AI summary of the memo
                    summary_result = await self.execute_mcp_tool(
                        session_id,
                        "generate_memo_summary",
                        {
                            "memo_id": memo_id,
                            "content": memo_content
                        },
                        user_context
                    )
                    
                    if summary_result and not summary_result.get("error"):
                        summary = summary_result.get("summary", "")
                        if summary:
                            response += f"\n\n📝 AI Summary: {summary}"
                    
                    yield await self.emit_response(session_id, response)
                else:
                    yield await self.emit_response(
                        session_id,
                        "I couldn't save your voice memo right now. Please try again later."
                    )
            
            elif operation == "list_memos":
                # List recent voice memos
                result = await self.execute_mcp_tool(
                    session_id,
                    "get_voice_memos",
                    {
                        "user_id": user_context.user_id,
                        "limit": 10
                    },
                    user_context
                )
                
                if result and not result.get("error"):
                    memos = result.get("memos", [])
                    
                    if memos:
                        response = f"**🎤 Your Recent Voice Memos ({len(memos)}):**\n\n"
                        
                        for i, memo in enumerate(memos, 1):
                            memo_id = memo.get("id", "unknown")
                            content = memo.get("content", "")
                            summary = memo.get("summary", "")
                            timestamp = memo.get("timestamp", "unknown")
                            
                            response += f"**{i}. Memo {memo_id}** - {timestamp}\n"
                            
                            if summary:
                                response += f"   📝 {summary}\n"
                            else:
                                # Show first 100 characters of content
                                preview = content[:100] + "..." if len(content) > 100 else content
                                response += f"   💬 {preview}\n"
                            response += "\n"
                        
                        response += "I can help you search, organize, or play back any of these memos."
                    else:
                        response = "You don't have any voice memos yet. Would you like to create one?"
                    
                    yield await self.emit_response(session_id, response)
                else:
                    yield await self.emit_response(
                        session_id,
                        "I couldn't retrieve your voice memos right now. Please try again later."
                    )
            
            else:
                yield await self.emit_response(
                    session_id,
                    "I can help you create voice memos, list existing memos, or search through your memo collection. What would you like to do?"
                )
                
        except Exception as e:
            self.logger.error("Voice memo workflow failed: %s", e)
            yield await self.emit_error(session_id, f"Voice memo management failed: {str(e)}")
    
    async def transcription_workflow(
        self, 
        session_id: str, 
        request: str, 
        user_context: MCPUserContext
    ) -> AsyncGenerator[AIEvent, None]:
        """Handle transcription workflow."""
        yield await self.emit_status(session_id, EventType.THINKING, "Processing transcription request...")
        
        try:
            # This would typically handle audio file transcription
            yield await self.emit_response(
                session_id,
                "I can transcribe audio in real-time during voice conversations. For file transcription, please upload an audio file and I'll convert it to text for you."
            )
            
            # Future implementation could handle:
            # - File upload transcription
            # - Batch transcription
            # - Transcription with timestamps
            # - Speaker identification
            
        except Exception as e:
            self.logger.error("Transcription workflow failed: %s", e)
            yield await self.emit_error(session_id, f"Transcription failed: {str(e)}")
    
    async def notifications_workflow(
        self, 
        session_id: str, 
        request: str, 
        user_context: MCPUserContext
    ) -> AsyncGenerator[AIEvent, None]:
        """Handle voice notifications workflow."""
        yield await self.emit_status(session_id, EventType.THINKING, "Managing voice notifications...")
        
        try:
            # Get notification preferences
            result = await self.execute_mcp_tool(
                session_id,
                "get_voice_notification_settings",
                {"user_id": user_context.user_id},
                user_context
            )
            
            if result and not result.get("error"):
                settings = result.get("settings", {})
                
                response = "**🔔 Voice Notification Settings:**\n\n"
                
                voice_enabled = settings.get("voice_notifications_enabled", False)
                tts_enabled = settings.get("tts_enabled", False)
                voice_type = settings.get("voice_type", "default")
                
                response += f"• **Voice Notifications:** {'✅ Enabled' if voice_enabled else '❌ Disabled'}\n"
                response += f"• **Text-to-Speech:** {'✅ Enabled' if tts_enabled else '❌ Disabled'}\n"
                response += f"• **Voice Type:** {voice_type.title()}\n\n"
                
                # Recent voice notifications
                recent_notifications = settings.get("recent_voice_notifications", [])
                if recent_notifications:
                    response += f"**Recent Voice Notifications ({len(recent_notifications)}):**\n"
                    for notification in recent_notifications[:5]:
                        title = notification.get("title", "Unknown")
                        timestamp = notification.get("timestamp", "unknown")
                        delivered = notification.get("delivered_via_voice", False)
                        
                        delivery_icon = "🔊" if delivered else "📱"
                        response += f"  {delivery_icon} {title} - {timestamp}\n"
                    response += "\n"
                
                response += "I can help you configure voice notifications or test the text-to-speech system."
                
                yield await self.emit_response(session_id, response)
            else:
                yield await self.emit_response(
                    session_id,
                    "I couldn't access your voice notification settings right now. Please try again later."
                )
                
        except Exception as e:
            self.logger.error("Notifications workflow failed: %s", e)
            yield await self.emit_error(session_id, f"Voice notifications management failed: {str(e)}")
    
    async def text_to_speech_workflow(
        self, 
        session_id: str, 
        request: str, 
        user_context: MCPUserContext
    ) -> AsyncGenerator[AIEvent, None]:
        """Handle text-to-speech workflow."""
        yield await self.emit_status(session_id, EventType.THINKING, "Converting text to speech...")
        
        try:
            # Extract text to be spoken
            text_to_speak = await self.extract_text_to_speak(request)
            
            if not text_to_speak:
                yield await self.emit_response(
                    session_id,
                    "What text would you like me to read aloud?"
                )
                return
            
            # Generate TTS audio
            await self.generate_tts_response(session_id, text_to_speak)
            
            yield await self.emit_response(
                session_id,
                f"🔊 Reading aloud: \"{text_to_speak[:100]}{'...' if len(text_to_speak) > 100 else ''}\""
            )
            
        except Exception as e:
            self.logger.error("TTS workflow failed: %s", e)
            yield await self.emit_error(session_id, f"Text-to-speech failed: {str(e)}")
    
    async def voice_settings_workflow(
        self, 
        session_id: str, 
        request: str, 
        user_context: MCPUserContext
    ) -> AsyncGenerator[AIEvent, None]:
        """Handle voice settings workflow."""
        yield await self.emit_status(session_id, EventType.THINKING, "Checking voice settings...")
        
        try:
            # Get current voice settings
            result = await self.execute_mcp_tool(
                session_id,
                "get_user_voice_settings",
                {"user_id": user_context.user_id},
                user_context
            )
            
            if result and not result.get("error"):
                settings = result.get("voice_settings", {})
                
                response = "**🎙️ Voice Settings:**\n\n"
                
                # Audio preferences
                microphone_enabled = settings.get("microphone_enabled", True)
                speaker_enabled = settings.get("speaker_enabled", True)
                voice_activation = settings.get("voice_activation", False)
                
                response += f"• **Microphone:** {'✅ Enabled' if microphone_enabled else '❌ Disabled'}\n"
                response += f"• **Speaker:** {'✅ Enabled' if speaker_enabled else '❌ Disabled'}\n"
                response += f"• **Voice Activation:** {'✅ Enabled' if voice_activation else '❌ Disabled'}\n\n"
                
                # TTS preferences
                tts_settings = settings.get("tts_settings", {})
                if tts_settings:
                    voice_type = tts_settings.get("voice_type", "default")
                    speech_rate = tts_settings.get("speech_rate", 1.0)
                    volume = tts_settings.get("volume", 0.8)
                    
                    response += "**Text-to-Speech Settings:**\n"
                    response += f"• Voice Type: {voice_type.title()}\n"
                    response += f"• Speech Rate: {speech_rate}x\n"
                    response += f"• Volume: {int(volume * 100)}%\n\n"
                
                # STT preferences
                stt_settings = settings.get("stt_settings", {})
                if stt_settings:
                    language = stt_settings.get("language", "en-US")
                    auto_punctuation = stt_settings.get("auto_punctuation", True)
                    
                    response += "**Speech-to-Text Settings:**\n"
                    response += f"• Language: {language}\n"
                    response += f"• Auto Punctuation: {'✅' if auto_punctuation else '❌'}\n\n"
                
                response += "I can help you adjust any of these voice settings. What would you like to change?"
                
                yield await self.emit_response(session_id, response)
            else:
                yield await self.emit_response(
                    session_id,
                    "I couldn't access your voice settings right now. Please try again later."
                )
                
        except Exception as e:
            self.logger.error("Voice settings workflow failed: %s", e)
            yield await self.emit_error(session_id, f"Voice settings management failed: {str(e)}")
    
    async def general_voice_assistance(
        self, 
        session_id: str, 
        request: str, 
        user_context: MCPUserContext
    ) -> AsyncGenerator[AIEvent, None]:
        """Handle general voice assistance requests."""
        # Load user context for personalized response
        context = await self.load_user_context(user_context)
        
        # Create a helpful prompt for the AI model
        prompt = f"""You are a Voice & Communication Assistant AI helping with voice interactions and multi-modal communication.

User context:
- User: {context.get('username', 'Unknown')}
- Role: {context.get('role', 'user')}

User request: {request}

Provide helpful information about voice and communication features including:
- Voice command processing for all system features
- Voice memo creation and management
- Text-to-speech and speech-to-text capabilities
- Voice notification settings and preferences
- Multi-modal communication coordination
- Audio settings and voice preferences

Be friendly, clear about voice capabilities, and helpful with audio-related tasks."""

        # Generate AI response
        async for token in self.generate_ai_response(session_id, prompt, context):
            pass  # Tokens are already emitted by generate_ai_response
        
        # Also generate TTS for the response
        if hasattr(self, '_last_response'):
            await self.generate_tts_response(session_id, self._last_response)
    
    async def generate_tts_response(self, session_id: str, text: str) -> None:
        """Generate text-to-speech audio for a response."""
        try:
            # Generate TTS audio using existing voice processor
            audio_bytes = await self.voice_processor.text_to_speech(text)
            
            if audio_bytes:
                # Convert to base64 for transmission
                import base64
                audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
                
                # Emit TTS event
                tts_event = await self.emit_event(
                    session_id,
                    EventType.TTS,
                    {
                        "audio": audio_base64,
                        "format": "wav",
                        "text": text,
                        "sample_rate": settings.VOICE_SAMPLE_RATE,
                        "duration": len(audio_bytes) / (settings.VOICE_SAMPLE_RATE * 2)
                    }
                )
                
                # Also emit through event bus if available
                if self.orchestrator and hasattr(self.orchestrator, 'event_bus'):
                    await self.orchestrator.event_bus.emit_tts_audio(
                        session_id=session_id,
                        agent_type=self.agent_type,
                        audio_data=audio_base64,
                        metadata={
                            "format": "wav",
                            "text": text,
                            "sample_rate": settings.VOICE_SAMPLE_RATE,
                            "duration": len(audio_bytes) / (settings.VOICE_SAMPLE_RATE * 2)
                        }
                    )
            else:
                self.logger.warning("TTS generation failed for session %s", session_id)
                
        except Exception as e:
            self.logger.error("TTS generation error: %s", e)
    
    async def handle_voice_specific_command(
        self, 
        session_id: str, 
        command: str, 
        user_context: MCPUserContext
    ) -> None:
        """Handle commands specific to voice functionality."""
        command_lower = command.lower()
        
        if "stop listening" in command_lower or "mute" in command_lower:
            await self.emit_response(
                session_id,
                "🔇 Voice input paused. Say 'start listening' to resume."
            )
        elif "start listening" in command_lower or "unmute" in command_lower:
            await self.emit_response(
                session_id,
                "🎙️ Voice input resumed. I'm listening!"
            )
        elif "louder" in command_lower or "volume up" in command_lower:
            await self.emit_response(
                session_id,
                "🔊 Increasing volume. Is this better?"
            )
        elif "quieter" in command_lower or "volume down" in command_lower:
            await self.emit_response(
                session_id,
                "🔉 Decreasing volume. How's this?"
            )
        else:
            await self.emit_response(
                session_id,
                "I understand you're using voice commands. I can help with volume control, muting, or routing your request to other assistants."
            )
    
    # Helper methods for extracting information from requests
    
    async def classify_voice_command(self, command: str) -> Dict[str, str]:
        """Classify voice command and determine target agent."""
        command_lower = command.lower()
        
        # Family-related commands
        if any(word in command_lower for word in ["family", "invite", "member", "relatives"]):
            return {"command_type": "family_management", "target_agent": "family"}
        
        # Personal commands
        if any(word in command_lower for word in ["profile", "avatar", "settings", "preferences"]):
            return {"command_type": "personal_management", "target_agent": "personal"}
        
        # Workspace commands
        if any(word in command_lower for word in ["workspace", "team", "project", "collaborate"]):
            return {"command_type": "workspace_management", "target_agent": "workspace"}
        
        # Shopping commands
        if any(word in command_lower for word in ["buy", "shop", "purchase", "store"]):
            return {"command_type": "commerce", "target_agent": "commerce"}
        
        # Security/admin commands
        if any(word in command_lower for word in ["security", "admin", "users", "system"]):
            return {"command_type": "security_admin", "target_agent": "security"}
        
        # Voice-specific commands
        if any(word in command_lower for word in ["volume", "mute", "listen", "speak", "voice"]):
            return {"command_type": "voice_control", "target_agent": "voice"}
        
        # Default to personal assistant
        return {"command_type": "general", "target_agent": "personal"}
    
    async def classify_memo_operation(self, request: str) -> str:
        """Classify the type of memo operation."""
        request_lower = request.lower()
        
        if any(word in request_lower for word in ["create", "record", "save", "new memo"]):
            return "create_memo"
        elif any(word in request_lower for word in ["list", "show", "my memos", "recent"]):
            return "list_memos"
        elif any(word in request_lower for word in ["search", "find", "look for"]):
            return "search_memos"
        elif any(word in request_lower for word in ["delete", "remove", "clear"]):
            return "delete_memo"
        else:
            return "general"
    
    async def extract_memo_content(self, request: str) -> Optional[str]:
        """Extract memo content from request."""
        # Look for patterns like "record memo: content" or "save memo about content"
        import re
        
        patterns = [
            r'memo[:\s]+(.+)',
            r'record[:\s]+(.+)',
            r'save[:\s]+(.+)',
            r'note[:\s]+(.+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, request, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        # If no pattern matches, assume the whole request is the memo content
        # after removing command words
        command_words = ["create", "record", "save", "memo", "note", "voice"]
        words = request.split()
        filtered_words = [word for word in words if word.lower() not in command_words]
        
        if filtered_words:
            return " ".join(filtered_words)
        
        return None
    
    async def extract_text_to_speak(self, request: str) -> Optional[str]:
        """Extract text that should be spoken from request."""
        # Look for quoted text first
        import re
        quoted_pattern = r'["\']([^"\']+)["\']'
        match = re.search(quoted_pattern, request)
        if match:
            return match.group(1)
        
        # Look for patterns like "read aloud: text" or "say: text"
        patterns = [
            r'read aloud[:\s]+(.+)',
            r'say[:\s]+(.+)',
            r'speak[:\s]+(.+)',
            r'tts[:\s]+(.+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, request, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        # If no pattern matches, assume everything after command words is the text
        command_words = ["read", "aloud", "say", "speak", "tts", "text", "to", "speech"]
        words = request.split()
        
        # Find the first non-command word
        start_index = 0
        for i, word in enumerate(words):
            if word.lower() not in command_words:
                start_index = i
                break
        
        if start_index < len(words):
            return " ".join(words[start_index:])
        
        return None
    
    async def create_livekit_token(self, user_id: str, room_name: Optional[str] = None) -> Optional[Dict[str, str]]:
        """
        Create a LiveKit access token for voice communication.
        
        Args:
            user_id: User identifier for the token
            room_name: Optional room name for the session
            
        Returns:
            Dictionary with token and LiveKit URL, or None if not configured
        """
        try:
            if not self.livekit_api_key or not self.livekit_api_secret:
                self.logger.warning("LiveKit not configured - API key or secret missing")
                return None
            
            # Generate room name if not provided
            if not room_name:
                from datetime import datetime
                room_name = f"ai_voice_{user_id}_{int(datetime.now().timestamp())}"
            
            # Create access token
            token = create_access_token(
                api_key=self.livekit_api_key,
                api_secret=self.livekit_api_secret.get_secret_value() if hasattr(self.livekit_api_secret, 'get_secret_value') else self.livekit_api_secret,
                identity=user_id,
                room=room_name,
                ttl_seconds=3600,  # 1 hour
                can_publish=True,
                can_subscribe=True
            )
            
            return {
                "token": token,
                "room": room_name,
                "livekit_url": self.livekit_url or "ws://localhost:7880"
            }
            
        except Exception as e:
            self.logger.error(f"Failed to create LiveKit token: {e}")
            return None
    
    async def handle_voice_input(self, session_id: str, audio_data: bytes, user_context: MCPUserContext) -> AsyncGenerator[AIEvent, None]:
        """
        Handle voice input from LiveKit audio stream.
        
        Args:
            session_id: AI session identifier
            audio_data: Raw audio data from LiveKit
            user_context: MCP user context
            
        Yields:
            AI events for voice processing results
        """
        try:
            status_event = await self.emit_status(session_id, EventType.VOICE_START, "Processing voice input...")
            yield status_event
            
            # Convert audio to text using existing voice processor
            transcription_text = await self.voice_processor.speech_to_text(audio_data)
            
            if transcription_text:
                # Emit STT result
                stt_event = await self.emit_event(
                    session_id,
                    EventType.STT,
                    {
                        "transcribed_text": transcription_text,
                        "confidence": 0.9,  # Voice processor doesn't return confidence yet
                        "audio_duration": len(audio_data) / (16000 * 2)  # Estimate duration
                    }
                )
                yield stt_event
                
                # Process the transcribed text as a voice command
                async for event in self.voice_command_workflow(
                    session_id, 
                    transcription_text, 
                    user_context,
                    {"audio_data": audio_data, "source": "livekit"}
                ):
                    yield event
            else:
                error_event = await self.emit_error(
                    session_id,
                    "I couldn't understand the audio. Please try speaking more clearly."
                )
                yield error_event
                
        except Exception as e:
            self.logger.error(f"Voice input handling failed: {e}")
            error_event = await self.emit_error(session_id, f"Voice processing failed: {str(e)}")
            yield error_event
    
    async def generate_voice_response(self, session_id: str, text: str) -> Optional[Dict[str, Any]]:
        """
        Generate voice response using TTS and prepare for LiveKit streaming.
        
        Args:
            session_id: AI session identifier
            text: Text to convert to speech
            
        Returns:
            Dictionary with audio data and metadata, or None if failed
        """
        try:
            # Generate TTS audio using existing voice processor
            audio_bytes = await self.voice_processor.text_to_speech(text)
            
            if audio_bytes:
                # Convert to base64 for transmission
                import base64
                audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
                
                return {
                    "audio": audio_base64,
                    "format": "wav",
                    "sample_rate": settings.VOICE_SAMPLE_RATE,
                    "text": text,
                    "duration": len(audio_bytes) / (settings.VOICE_SAMPLE_RATE * 2)  # Estimate duration
                }
            else:
                self.logger.warning(f"TTS generation failed for session {session_id}")
                return None
                
        except Exception as e:
            self.logger.error(f"Voice response generation failed: {e}")
            return None
    
    async def setup_voice_session(self, session_id: str, user_context: MCPUserContext) -> Optional[Dict[str, Any]]:
        """
        Set up a voice session with LiveKit integration.
        
        Args:
            session_id: AI session identifier
            user_context: MCP user context
            
        Returns:
            Voice session configuration or None if setup failed
        """
        try:
            # Create LiveKit token
            livekit_config = await self.create_livekit_token(
                user_id=user_context.user_id,
                room_name=f"ai_voice_{session_id}"
            )
            
            if not livekit_config:
                return None
            
            # Store voice session configuration
            voice_config = {
                "session_id": session_id,
                "livekit": livekit_config,
                "voice_settings": {
                    "sample_rate": settings.VOICE_SAMPLE_RATE,
                    "chunk_size": settings.VOICE_CHUNK_SIZE,
                    "max_audio_length": settings.VOICE_MAX_AUDIO_LENGTH,
                    "tts_voice": settings.VOICE_TTS_VOICE
                },
                "capabilities": {
                    "stt_enabled": settings.AI_VOICE_STT_ENABLED,
                    "tts_enabled": settings.AI_VOICE_TTS_ENABLED,
                    "realtime_enabled": settings.AI_VOICE_REALTIME_ENABLED,
                    "commands_enabled": settings.AI_VOICE_COMMAND_ENABLED
                }
            }
            
            self.logger.info(f"Voice session setup completed for {session_id}")
            return voice_config
            
        except Exception as e:
            self.logger.error(f"Voice session setup failed: {e}")
            return None
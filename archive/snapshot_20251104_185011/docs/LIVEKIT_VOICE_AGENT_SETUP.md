# LiveKit Voice Agent Setup Guide

This guide explains how to set up and run the LiveKit voice agent for the Second Brain Database system.

## Overview

The LiveKit voice agent provides conversational AI capabilities using:
- **LiveKit Agents**: Real-time voice communication framework
- **Ollama**: Local LLM inference for privacy and cost efficiency
- **OpenAI-compatible APIs**: STT (Speech-to-Text) and TTS (Text-to-Speech)

## Prerequisites

1. **Ollama**: Install and run Ollama locally
   ```bash
   # Install Ollama (macOS)
   brew install ollama

   # Pull required models
   ollama pull llama3.2:latest
   ollama pull deepseek-r1:1.5b
   ```

2. **LiveKit Server**: Set up a LiveKit server instance
   - For development: Use LiveKit's cloud service or run locally
   - For production: Deploy your own LiveKit server

## Configuration

Add the following settings to your `.env` or `.sbd` file:

```bash
# LiveKit Configuration
LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_api_secret
LIVEKIT_URL=https://your-livekit-server:7880

# Ollama Configuration
OLLAMA_HOST=http://127.0.0.1:11434

# Voice Agent Configuration
LIVEKIT_VOICE_AGENT_ENABLED=true
LIVEKIT_VOICE_AGENT_MODEL=llama3.2:latest
LIVEKIT_VOICE_AGENT_TEMPERATURE=0.7
LIVEKIT_VOICE_AGENT_VOICE=alloy
LIVEKIT_VOICE_AGENT_LANGUAGE=en
LIVEKIT_VOICE_AGENT_MAX_RESPONSE_LENGTH=500
LIVEKIT_VOICE_AGENT_SESSION_TIMEOUT=1800
```

## Installation

The required dependencies are already included in `pyproject.toml`:

```toml
livekit-agents[openai]>=1.2.0,<2.0.0
```

Install dependencies:

```bash
pip install -e .
```

## Running the Voice Agent

### Method 1: Using the runner script

```bash
./run_voice_agent.sh
```

### Method 2: Direct Python execution

```bash
python scripts/manual/livekit_voice_agent.py
```

## Voice Agent Features

- **Conversational AI**: Natural voice conversations with your Second Brain Database
- **Local LLM**: Uses Ollama for private, offline AI processing
- **Real-time Communication**: LiveKit enables low-latency voice interactions
- **Tool Integration**: Access to MCP tools for database operations
- **Session Management**: Automatic session timeout and cleanup

## Voice Agent Capabilities

The voice agent can help with:

- Managing knowledge base and notes
- Organizing information and documents
- Answering questions about stored data
- Providing insights and summaries
- Executing database operations via voice commands

## Troubleshooting

### Common Issues

1. **"LiveKit API credentials not configured"**
   - Ensure `LIVEKIT_API_KEY` and `LIVEKIT_API_SECRET` are set in your environment

2. **"Ollama host not configured"**
   - Ensure `OLLAMA_HOST` is set (default: `http://127.0.0.1:11434`)
   - Verify Ollama is running: `ollama list`

3. **"Voice agent is disabled"**
   - Set `LIVEKIT_VOICE_AGENT_ENABLED=true` in your configuration

4. **Connection issues**
   - Verify LiveKit server URL is correct and accessible
   - Check firewall settings for LiveKit ports (7880 for WebSocket, 7881 for HTTP)

### Logs

Voice agent logs are available through the standard logging system. Check:
- Console output when running the agent
- Application logs in the `logs/` directory

## Development

### Modifying the Voice Agent

The voice agent implementation is in:
- `scripts/manual/livekit_voice_agent.py`: Main voice agent code
- `src/second_brain_database/config.py`: Configuration settings

### Adding New Capabilities

To extend the voice agent:

1. Add new tools to the MCP server
2. Update the system instructions in `_get_system_instructions()`
3. Modify the conversation handling in `on_text_message()` and `on_audio_message()`

## Production Deployment

For production deployment:

1. Use a dedicated LiveKit server instance
2. Configure proper SSL/TLS certificates
3. Set up monitoring and logging
4. Configure session timeouts appropriately
5. Use production-grade Ollama deployment

## Security Considerations

- Voice data is processed locally through Ollama
- LiveKit handles real-time communication securely
- API keys should be properly secured
- Consider network security for LiveKit server access

## Support

For issues with the voice agent:
1. Check the logs for error messages
2. Verify all prerequisites are installed and running
3. Ensure configuration is correct
4. Test Ollama connectivity: `curl http://127.0.0.1:11434/api/tags`
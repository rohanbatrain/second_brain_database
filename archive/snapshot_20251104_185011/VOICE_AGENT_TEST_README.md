# Voice Agent Testing Guide

This guide covers testing the Second Brain Database voice agent with MCP tool integration using both real-time voice (LiveKit) and text-based approaches.

## 🎯 Overview

The voice agent integrates with:
- **LiveKit Agents**: Real-time voice communication with STT/TTS
- **FastMCP 2.x**: Tool orchestration with authentication
- **Ollama**: Local LLM inference (llama3.2:latest)
- **Database Operations**: Family management, user profiles, system monitoring

## 🚀 Quick Start

### Option 1: Text-Based Testing (Recommended for Development)

```bash
# 1. Start the backend services
docker-compose up -d mongo redis ollama-cpu

# 2. Start the FastAPI server
python scripts/manual/start_fastapi_server.py

# 3. Run the text-based MCP test
python test_voice_agent_mcp.py
```

### Option 2: Full Voice Testing with LiveKit

```bash
# 1. Start all services including LiveKit
docker-compose up -d

# 2. Start the FastAPI server
python scripts/manual/start_fastapi_server.py

# 3. Open the web interface
python -c "
import webbrowser
import os
html_path = os.path.abspath('voice_agent_test.html')
print(f'Opening {html_path} in browser...')
webbrowser.open(f'file://{html_path}')
print('Browser opened. Make sure your FastAPI backend is running on http://localhost:8000')
"
```

## 📋 Prerequisites

### System Requirements
- Docker & Docker Compose
- Python 3.13+
- Node.js (for advanced LiveKit client testing)

### Environment Setup
```bash
# Copy environment configuration
cp .env.development.example .env

# Or use the .sbd configuration file (recommended)
# The .sbd file already contains LiveKit dev credentials
```

## 🔧 Configuration

### LiveKit Settings (.sbd file)
```bash
# Development credentials (replace with production keys)
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=secret
LIVEKIT_URL=ws://localhost:7880

# Voice Agent Configuration
LIVEKIT_VOICE_AGENT_MODEL=llama3.2:latest
LIVEKIT_VOICE_AGENT_VOICE=alloy
LIVEKIT_VOICE_AGENT_LANGUAGE=en
```

### Docker Services
The `docker-compose.yml` includes:
- **MongoDB**: Database storage
- **Redis**: Caching and session storage
- **Ollama**: Local LLM inference
- **LiveKit Server**: Real-time voice communication

## 🧪 Testing Approaches

### 1. Text-Based MCP Testing

**File**: `test_voice_agent_mcp.py`

Tests the core MCP tool integration without requiring LiveKit server.

```bash
python test_voice_agent_mcp.py
```

**Test Commands**:
- "create a new family" → Creates family via MCP tool
- "check server status" → Gets system health
- "list my families" → Lists user families
- "show me my profile" → Retrieves user profile

**Expected Output**:
```
🧪 Testing Voice Agent with MCP Tools
✅ MCP tool integration initialized with 8 available tools
✅ Tool detection working: "create a new family" → create_family tool
✅ Tool detection working: "server status" → get_server_status tool
✅ Tool detection working: "my families" → list_user_families tool
```

### 2. Web-Based Voice Testing

**File**: `voice_agent_test.html`

Interactive web interface for testing both text commands and voice sessions.

**Features**:
- Real-time service status monitoring
- Text command testing
- Voice session creation (LiveKit integration)
- Live logging and debugging

**Usage**:
1. Open `voice_agent_test.html` in browser
2. Check service status (all should be green)
3. Test text commands or start voice session

### 3. LiveKit Voice Agent

**File**: `scripts/manual/livekit_voice_agent.py`

Production-ready voice agent with full LiveKit integration.

**Starting the Agent**:
```bash
# Using the launcher script
python scripts/launch_voice_agent.py --room voice-test-room

# Or directly
python scripts/manual/livekit_voice_agent.py
```

## 🔍 Troubleshooting

### Common Issues

#### LiveKit Server Not Starting
```bash
# Check LiveKit container logs
docker-compose logs livekit

# Verify configuration
cat config/livekit-config.yaml

# Restart LiveKit service
docker-compose restart livekit
```

#### MCP Tools Not Available
```bash
# Check MCP server health
curl http://localhost:8000/api/v1/mcp/health

# Verify FastAPI is running
curl http://localhost:8000/health

# Check MCP tool registration
python -c "from src.second_brain_database.integrations.mcp.mcp_instance import get_mcp_server; print('MCP Server:', get_mcp_server())"
```

#### Voice Agent Connection Failed
```bash
# Check LiveKit credentials in .sbd file
grep LIVEKIT .sbd

# Verify Ollama is running
curl http://localhost:11434/api/tags

# Check voice agent logs
python scripts/launch_voice_agent.py --status
```

### Service Ports

| Service | Port | Purpose |
|---------|------|---------|
| FastAPI | 8000 | Main API server |
| LiveKit | 7880 | WebRTC signaling |
| LiveKit HTTP | 7881 | REST API |
| MongoDB | 27017 | Database |
| Redis | 6379 | Cache/Session store |
| Ollama | 11434 | LLM inference |

### Log Files

- **Application Logs**: `logs/` directory
- **Docker Logs**: `docker-compose logs [service]`
- **Voice Agent Logs**: Check terminal output or Loki (if configured)

## 🎯 Voice Commands

The voice agent recognizes these command patterns:

### Family Management
- "create a new family"
- "list my families"
- "add member to family"
- "invite user to family"

### System Operations
- "check server status"
- "get system health"
- "show server info"

### User Management
- "show my profile"
- "update my profile"
- "list my workspaces"

### Shop Operations
- "browse shop items"
- "show products"
- "purchase item"

## 🔒 Security Features

- **JWT Authentication**: All MCP tools require valid user context
- **Rate Limiting**: Prevents abuse of voice commands
- **Audit Logging**: All tool executions are logged
- **IP Whitelisting**: Configurable access control

## 📊 Monitoring

### Health Checks
- **LiveKit**: `http://localhost:7881/health`
- **Backend**: `http://localhost:8000/health`
- **MCP**: `http://localhost:8000/api/v1/mcp/health`

### Metrics
- Tool execution times
- Voice session duration
- Error rates and recovery

## 🚀 Production Deployment

For production deployment:

1. **Replace LiveKit credentials** with production keys from LiveKit Cloud
2. **Configure HTTPS** and secure WebSocket connections
3. **Set up monitoring** and alerting
4. **Configure load balancing** for multiple voice agent instances
5. **Enable STT/TTS services** (OpenAI, Deepgram, etc.)

## 📚 Additional Resources

- [LiveKit Documentation](https://docs.livekit.io/)
- [FastMCP Guide](https://fastmcp.io/)
- [Ollama Models](https://ollama.ai/library)
- [WebRTC Standards](https://webrtc.org/)

## 🆘 Support

If you encounter issues:

1. Check the troubleshooting section above
2. Review service logs
3. Verify configuration files
4. Test individual components
5. Check GitHub issues for similar problems

---

**Happy Testing! 🎤🤖**

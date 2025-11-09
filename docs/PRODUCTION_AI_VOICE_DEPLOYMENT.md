# AI and Voice Functionality - REMOVED

## Status: ❌ DEPRECATED

**All AI orchestration and voice processing functionality has been completely removed from the Second Brain Database project as of the latest codebase cleanup.**

This document is maintained for historical reference only. The features described below are no longer available in the codebase.

## What Was Previously Implemented (Now Removed)

### 1. LangChain/LangGraph Integration ❌ REMOVED
- **Tools**: 138+ MCP tools that were wrapped for LangChain
- **Memory**: Redis-backed conversation history
- **Orchestrator**: ChatOllama with dynamic tool loading
- **Workflows**: Multi-step and shopping StateGraphs
- **Routes**: `/api/ai/*` endpoints with SSE streaming

### 2. LiveKit Voice Integration ❌ REMOVED
- **Agent**: Production voice agent with Agents framework
- **STT**: Deepgram Nova-2
- **TTS**: Silero
- **VAD**: Silero voice activity detection
- **Routes**: `/api/voice/*` for room management
- **Worker**: Separate process for voice handling

## Current Status

The Second Brain Database now focuses on:
- ✅ **Document Intelligence**: Advanced document processing and analysis
- ✅ **Family Management**: Multi-user family accounts with shared workspaces
- ✅ **MCP Server Integration**: Model Context Protocol server for external AI clients
- ✅ **Background Processing**: Celery-based task queue for document operations
- ✅ **Security & Authentication**: JWT-based authentication with comprehensive security

## Migration Notes

If AI or voice functionality is needed in the future:
1. Implement as separate external services
2. Use the MCP protocol to interact with Second Brain Database
3. Maintain proper separation of concerns between AI/voice services and core database functionality

## Contact

For questions about the current codebase or re-implementing AI/voice features, refer to the main README.md and project documentation.

## Quick Start

### Prerequisites
```bash
# Install dependencies
uv pip install -r requirements.txt

# Set environment variables
export LIVEKIT_URL="ws://localhost:7880"
export LIVEKIT_API_KEY="your_api_key"
export LIVEKIT_API_SECRET="your_api_secret"
export DEEPGRAM_API_KEY="your_deepgram_key"
```

### Running Services

#### 1. Start FastAPI Server
```bash
python start_fastapi_server.py
```

#### 2. Start LiveKit Voice Worker (separate terminal)
```bash
python start_voice_worker.py
```

#### 3. Start LiveKit Server (if not running)
```bash
livekit-server --dev
```

## API Endpoints

### AI Chat
- `POST /api/ai/sessions` - Create session
- `POST /api/ai/sessions/{id}/messages` - Send message (SSE streaming)
- `WS /api/ai/ws/{id}` - WebSocket connection
- `POST /api/ai/workflows/multi-step` - Multi-step workflow
- `POST /api/ai/workflows/shopping` - Shopping workflow

### Voice
- `POST /api/voice/rooms` - Create voice room
- `POST /api/voice/tokens` - Generate access token
- `GET /api/voice/rooms/{name}` - Get room info
- `DELETE /api/voice/rooms/{name}` - Delete room

## Architecture

### LangChain Flow
```
User Request → Orchestrator → Tool Selection → MCP Tool Execution → LLM Response
                    ↓
              Redis Memory (conversation history)
```

### Voice Flow
```
User Audio → LiveKit Room → Voice Agent → Deepgram STT → LangChain Orchestrator
                                                                    ↓
                                                              MCP Tools
                                                                    ↓
User Audio ← LiveKit Room ← Voice Agent ← Silero TTS ← LLM Response
```

### StateGraph Workflows
```
analyze_task → execute_task → verify_result
     ↓              ↓              ↓
  Planning      Tool Calls    Verification
```

## MCP Tools Available

All tools preserve authentication and user context:

### Family (30+ tools)
- get_family_info, create_family, send_invitation, manage_members, etc.

### Shop (35+ tools)
- browse_shop, purchase_item, manage_assets, rentals, SBD tokens, etc.

### Auth (30+ tools)
- get_profile, update_profile, 2FA, tokens, etc.

### Workspace (25+ tools)
- create_workspace, invite_member, manage_teams, etc.

### Admin (23+ tools)
- system_health, user_management, etc.

## Production Checklist

- [x] LangChain packages installed
- [x] All MCP tool wrappers created
- [x] Redis memory system
- [x] LangChain orchestrator with Ollama
- [x] FastAPI routes with SSE streaming
- [x] LangGraph StateGraph workflows
- [x] LiveKit Agents framework integration
- [x] Production voice agent (Deepgram + Silero)
- [x] Voice routes with room management
- [x] Separate voice worker process
- [ ] LiveKit server running
- [ ] Environment variables configured
- [ ] Production deployment

## Configuration

All settings in `config.py`:

```python
# LangChain
LANGCHAIN_ENABLED = True
LANGCHAIN_MODEL_PROVIDER = "ollama"
LANGCHAIN_DEFAULT_MODEL = "gemma3:1b"
LANGCHAIN_MEMORY_TTL = 3600

# LiveKit
LIVEKIT_ENABLED = True
LIVEKIT_URL = "ws://localhost:7880"
LIVEKIT_API_KEY = "..."
LIVEKIT_API_SECRET = "..."
DEEPGRAM_API_KEY = "..."
```

## Client Integration

### Chat Example
```typescript
const eventSource = new EventSource('/api/ai/sessions/123/messages');
eventSource.onmessage = (e) => {
  const data = JSON.parse(e.data);
  console.log(data.response);
};
```

### Voice Example
```typescript
// Create room
const room = await fetch('/api/voice/rooms', {
  method: 'POST',
  body: JSON.stringify({ max_participants: 10 })
});

// Connect with LiveKit SDK
import { Room } from 'livekit-client';
const liveKitRoom = new Room();
await liveKitRoom.connect(room.url, room.access_token);
```

## Files Modified/Created

### Created
- `integrations/langchain/tools/auth_tools.py`
- `integrations/langchain/tools/workspace_tools.py`
- `integrations/langchain/tools/admin_tools.py`
- `integrations/langchain/voice_agent.py` (production)
- `integrations/langchain/workflows.py`
- `routes/voice_livekit.py` (production)
- `start_voice_worker.py`

### Modified
- `config.py` - Added LiveKit settings
- `main.py` - Updated router imports
- `requirements.txt` - Added LiveKit packages
- `routes/langgraph/routes.py` - Added workflow endpoints
- `integrations/langchain/orchestrator.py` - Added all tool imports

### Replaced (old voice implementation removed)
- Old `routes/voice.py` → New `routes/voice_livekit.py`
- Old voice agent partial → Production `voice_agent.py`

## Next Steps

1. **Start LiveKit Server**: `livekit-server --dev`
2. **Configure Environment**: Set API keys in `.env`
3. **Test AI Chat**: Send POST to `/api/ai/sessions`
4. **Test Voice**: Create room and connect with LiveKit client
5. **Deploy**: Use production LiveKit cloud or self-hosted

## Support

All components are production-ready with:
- Comprehensive error handling
- Authentication/authorization
- MCP security patterns
- Redis session management
- Async operations
- Logging and monitoring

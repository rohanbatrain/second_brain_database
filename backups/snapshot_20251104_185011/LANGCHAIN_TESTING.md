# LangChain Testing Guide

## Quick Start

### 1. Verify Services are Running

```bash
# Check all services
curl http://localhost:8000/health

# Check Ollama
curl http://127.0.0.1:11434/api/tags

# Check available models
ollama list
```

### 2. Simple Test (No Auth Required)

```bash
# Test basic Ollama + LangChain
python3 << 'EOF'
import sys
sys.path.insert(0, 'src')
from langchain_ollama import ChatOllama

llm = ChatOllama(model="gemma3:1b", base_url="http://127.0.0.1:11434")
response = llm.invoke("Say hello!")
print(f"Response: {response.content}")
EOF
```

### 3. Comprehensive Test Suite

```bash
# Run full test suite
python3 test_langchain.py

# Show usage guide
python3 test_langchain.py --help
```

### 4. Test via API (Requires Authentication)

```bash
# First, get an auth token (create user or login)
# Then use the AI endpoints:

# Create AI session
curl -X POST http://localhost:8000/ai/sessions \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"agent_type": "general"}'

# Chat with agent
curl -X POST http://localhost:8000/ai/chat \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Hello, what can you help me with?",
    "session_id": "YOUR_SESSION_ID"
  }'
```

## Available Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/ai/health` | GET | No | Check AI system status |
| `/ai/sessions` | POST | Yes | Create new AI session |
| `/ai/chat` | POST | Yes | Chat with AI agent |
| `/ai/sessions/{id}` | GET | Yes | Get session history |
| `/ai/workflows/multi-step` | POST | Yes | Run multi-step workflow |
| `/ai/workflows/shopping` | POST | Yes | Run shopping workflow |

## Testing Different Features

### Test Basic Chat
```python
import asyncio
import sys
sys.path.insert(0, 'src')

from second_brain_database.config import Settings
from second_brain_database.managers.redis_manager import RedisManager
from second_brain_database.integrations.langchain.orchestrator import LangChainOrchestrator
from second_brain_database.integrations.mcp.context import MCPUserContext

async def test_chat():
    settings = Settings()
    redis_mgr = RedisManager(settings=settings)
    orchestrator = LangChainOrchestrator(settings, redis_mgr)
    
    user_context = MCPUserContext(
        user_id="test_123",
        username="testuser",
        email="test@example.com",
        role="user",
        permissions=[],
        family_memberships=[],
        workspaces=[],
        ip_address="127.0.0.1",
        user_agent="Test"
    )
    
    response = await orchestrator.chat(
        message="Hello! What tools do you have?",
        user_context=user_context,
        session_id="test_session"
    )
    print(f"Agent: {response}")

asyncio.run(test_chat())
```

### Test with MCP Tools
```python
# The orchestrator automatically loads MCP tools based on user permissions
# Tools include:
# - Family management (create, invite, manage members)
# - Shop operations (browse, purchase items)
# - Workspace management
# - Authentication operations
```

### Test Memory/Conversation History
```python
# Memory is automatically persisted in Redis
# Test by having multiple conversations in the same session:

response1 = await orchestrator.chat("My name is John", user_context, "session_1")
response2 = await orchestrator.chat("What's my name?", user_context, "session_1")
# Should remember "John"
```

## Configuration

Environment variables (in `.sbd` file):
```bash
LANGCHAIN_ENABLED=true
LANGCHAIN_MODEL_PROVIDER=ollama
LANGCHAIN_DEFAULT_MODEL=gemma3:1b
LANGCHAIN_TEMPERATURE=0.7
LANGCHAIN_MAX_TOKENS=2048
LANGCHAIN_CONVERSATION_HISTORY_LIMIT=10
LANGCHAIN_MEMORY_TTL=3600
OLLAMA_HOST=http://127.0.0.1:11434
```

## Troubleshooting

### Ollama Not Responding
```bash
# Check if Ollama is running
pgrep ollama

# Check API
curl http://127.0.0.1:11434/api/tags

# Restart Ollama
pkill ollama
ollama serve &

# Check logs
tail -f logs/ollama.log
```

### Model Not Found
```bash
# List installed models
ollama list

# Pull required model
ollama pull gemma3:1b

# Test model
ollama run gemma3:1b "Hello"
```

### Redis Connection Issues
```bash
# Check Redis
redis-cli ping

# Check connection in Python
python3 -c "
import sys
sys.path.insert(0, 'src')
from second_brain_database.managers.redis_manager import RedisManager
from second_brain_database.config import Settings
rm = RedisManager(settings=Settings())
print(rm.redis.ping())
"
```

### Import Errors
```bash
# Verify LangChain packages
uv pip list | grep -i lang

# Should see:
# langchain
# langchain-core
# langchain-ollama
# langgraph
```

## What Gets Tested

✅ **LLM Connection**: Verifies Ollama is running and responding  
✅ **Model Availability**: Checks required models are installed  
✅ **Chat Functionality**: Tests basic conversation  
✅ **Tool Integration**: Verifies MCP tools are accessible  
✅ **Memory Persistence**: Tests conversation history in Redis  
✅ **Workflows**: Tests complex multi-step operations  
✅ **API Endpoints**: Validates REST API functionality  
✅ **Error Handling**: Tests graceful degradation  

## Performance Tips

- Use smaller models for testing: `gemma3:1b` (815MB)
- Larger/better models: `llama3.2:3b` or `llama3.1:8b`
- Adjust temperature (0.0 = deterministic, 1.0 = creative)
- Monitor token usage in logs
- Use Redis for caching tool results

## Next Steps

1. Create unit tests in `tests/test_langchain/`
2. Add integration tests for workflows
3. Performance benchmarking
4. Load testing with multiple concurrent users
5. Add streaming response support

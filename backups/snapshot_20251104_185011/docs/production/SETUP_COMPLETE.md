# ✅ Setup Complete - Second Brain Database

## Current Status: **READY FOR USE**

All services have been successfully configured and tested.

## What's Running

| Service | Status | Port/URL | Notes |
|---------|--------|----------|-------|
| **MongoDB** | ✅ Docker | 27017 | External Docker container |
| **Redis** | ✅ Auto | 6379 | Auto-started by script |
| **Ollama** | ✅ Auto | 11434 | Auto-pulls models on start |
| **FastAPI** | ✅ Auto | 8000 | Main application server |
| **Voice Worker** | ✅ Auto | - | LiveKit voice processing |
| **Celery Worker** | ✅ Auto | - | 4 queues: default, ai, voice, workflows |
| **Celery Beat** | ✅ Auto | - | Scheduled tasks |
| **Flower** | ✅ Auto | 5555 | Task monitoring dashboard |

## Quick Commands

### Start Everything
```bash
./start.sh
```

### Stop Everything
```bash
./stop.sh
```

### View Service Logs
```bash
# Interactive menu
./scripts/startall/attach_service.sh

# Specific service
./scripts/startall/attach_service.sh fastapi
./scripts/startall/attach_service.sh celery_worker

# MongoDB (Docker)
docker logs -f mongodb
```

### Access URLs

- **API Documentation**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health
- **Flower Dashboard**: http://localhost:5555

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Second Brain Database                    │
└─────────────────────────────────────────────────────────────┘

┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   MongoDB    │  │    Redis     │  │   Ollama     │
│  (Docker)    │  │  (Auto-start)│  │  (Auto-start)│
│   :27017     │  │    :6379     │  │   :11434     │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                  │
       └─────────────────┴──────────────────┘
                         │
              ┌──────────▼──────────┐
              │   FastAPI Server    │
              │      :8000          │
              │  - REST API         │
              │  - WebSocket        │
              │  - MCP Tools        │
              └──────────┬──────────┘
                         │
       ┌─────────────────┼─────────────────┐
       │                 │                 │
┌──────▼───────┐ ┌───────▼──────┐ ┌───────▼──────┐
│Voice Worker  │ │Celery Worker │ │ Celery Beat  │
│- LiveKit     │ │- 4 Queues    │ │- Scheduler   │
│- Deepgram    │ │- AI Tasks    │ │- Periodic    │
└──────────────┘ └──────────────┘ └──────────────┘
                         │
                 ┌───────▼───────┐
                 │    Flower     │
                 │     :5555     │
                 │  Monitoring   │
                 └───────────────┘
```

## Features Available

### ✅ AI & LangChain
- LangChain orchestrator with modern LangGraph
- 6 specialized agents (Family, Personal, Workspace, Commerce, Security, Voice)
- Redis-backed conversation memory
- Ollama integration (gemma3:1b, deepseek-r1:1.5b)
- LangSmith tracing ready

### ✅ MCP Tools (138+ Tools)
- Family management
- Authentication & security
- Shop & assets
- Workspace collaboration
- Admin operations
- All with JWT authentication

### ✅ Async Processing
- Celery with 4 specialized queues
- Beat scheduler for periodic tasks
- Flower monitoring dashboard
- Document processing with Docling

### ✅ Voice AI
- LiveKit integration
- Deepgram Flux STT/TTS
- Voice command processing
- Real-time voice agents

### ✅ Document Processing
- PDF, DOCX, PPTX support
- OCR capabilities
- Table extraction
- RAG chunking

## Configuration Files

All configuration is in `/src/second_brain_database/config.py`:

```python
# Key settings
MONGODB_HOST = "localhost"
MONGODB_PORT = 27017
REDIS_URL = "redis://127.0.0.1:6379/0"
OLLAMA_HOST = "http://127.0.0.1:11434"
OLLAMA_MODEL = "gemma3:1b"
LANGCHAIN_ENABLED = True
LANGCHAIN_MODEL_PROVIDER = "ollama"
```

## Log Files

All logs stored in `/logs/`:
- `redis.log` - Redis server
- `ollama.log` - Ollama LLM service  
- `livekit.log` - LiveKit server
- `fastapi.log` - Main API server
- `voice_worker.log` - Voice processing
- `celery_worker.log` - Task worker
- `celery_beat.log` - Scheduler
- `flower.log` - Monitoring dashboard

**MongoDB logs**: `docker logs mongodb`

## PID Files

Process IDs stored in `/pids/` for clean shutdown.

## Troubleshooting

### Service Won't Start
```bash
# Check logs
./scripts/startall/attach_service.sh [service_name]

# Check ports
lsof -i :8000  # FastAPI
lsof -i :5555  # Flower
lsof -i :6379  # Redis
lsof -i :27017 # MongoDB
```

### Clean Restart
```bash
./stop.sh
rm -rf pids/*.pid logs/*.log
./start.sh
```

### MongoDB Not Found
```bash
# Start MongoDB Docker container
docker run -d -p 27017:27017 --name mongodb mongo

# Verify
nc -z localhost 27017
```

## Next Steps

1. **Test API**: Visit http://localhost:8000/docs
2. **Monitor Tasks**: Visit http://localhost:5555
3. **Check Health**: `curl http://localhost:8000/health`
4. **View Logs**: `./scripts/startall/attach_service.sh fastapi`

## Development Workflow

```bash
# 1. Make code changes in src/

# 2. Restart affected service
./stop.sh && ./start.sh

# 3. View logs
./scripts/startall/attach_service.sh fastapi

# 4. Test changes
curl http://localhost:8000/health
```

## Production Deployment

See `DEPLOYMENT_GUIDE.md` for:
- Docker Compose setup
- Environment variables
- SSL/TLS configuration  
- Reverse proxy (nginx)
- Monitoring stack
- Backup strategies

---

## Summary

🎉 **Everything is configured and ready!**

- All services auto-start with `./start.sh`
- MongoDB runs via Docker (externally managed)
- Logs are easily accessible
- Monitoring available via Flower
- API documentation auto-generated

**Start developing**: http://localhost:8000/docs

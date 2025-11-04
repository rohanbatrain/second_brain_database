# 🚀 Second Brain Database - Quick Start

## Prerequisites

- ✅ **MongoDB** - Running via Docker on port `27017`
- ⚠️ **Redis, Ollama, LiveKit** - Auto-started by script
- ⚠️ **Python 3.11+** with `uv` package manager

## Quick Start (3 Steps)

### 1️⃣ Start MongoDB (Docker)

```bash
docker run -d -p 27017:27017 --name mongodb mongo
```

### 2️⃣ Install & Start Services

```bash
# Clone repository
git clone https://github.com/rohanbatrain/second_brain_database.git
cd second_brain_database

# Install dependencies
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt

# Start all services (Redis, Ollama, FastAPI, Celery, etc.)
./start.sh
```

### 3️⃣ Access Services

| Service | URL | Description |
|---------|-----|-------------|
| **API Docs** | http://localhost:8000/docs | FastAPI Swagger UI |
| **Flower** | http://localhost:5555 | Celery task monitoring |

## View Logs

```bash
# View specific service logs
./scripts/startall/attach_service.sh fastapi
./scripts/startall/attach_service.sh celery_worker

# View MongoDB logs
docker logs -f mongodb
```

## Stop Services

```bash
./stop.sh

# Stop MongoDB separately
docker stop mongodb
```

**✅ Done!** API running at http://localhost:8000

---

## What's Running?

| Service | Port | Purpose |
|---------|------|---------|
| **FastAPI** | 8000 | Main REST API |
| **MongoDB** | 27017 | Database |
| **Redis** | 6379 | Cache & Queue |
| **Ollama** | 11434 | AI Models |
| **Flower** | 5555 | Task Monitor |

---

## Essential Commands

```bash
# Start all services
./start.sh

# Stop all services
./stop.sh

# View logs
./scripts/startall/attach_service.sh fastapi

# Run tests
pytest tests/

# Check health
curl http://localhost:8000/health
```

---

## First API Call

```bash
# Register user
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "Test123!"
  }'

# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "Test123!"
  }'
```

---

## Interactive Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Task Monitor**: http://localhost:5555

---

## System Requirements

**Minimum:**
- Python 3.11+
- 8GB RAM
- 4 CPU cores
- 20GB disk space

**Required Services:**
- MongoDB 6.0+
- Redis 7.0+
- Ollama (for AI features)

---

## Next Steps

1. 📖 Read full guide: [SETUP_GUIDE.md](SETUP_GUIDE.md)
2. 🧪 Explore API: http://localhost:8000/docs
3. 🤖 Test AI agents: `/api/v1/ai/chat`
4. 🎙️ Try voice features: `/api/v1/voice/`
5. 📄 Process documents: `/api/v1/documents/upload`

---

## Need Help?

- **Full Setup Guide**: [SETUP_GUIDE.md](SETUP_GUIDE.md)
- **Troubleshooting**: See [SETUP_GUIDE.md#troubleshooting](SETUP_GUIDE.md#troubleshooting)
- **Issues**: https://github.com/rohanbatrain/second_brain_database/issues

---

**⚡ Pro Tip**: Use `./scripts/startall/open_all_terminals.sh` to monitor all services in separate terminal windows!

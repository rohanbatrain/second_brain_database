# 🧠 Second Brain Database

> **A production-ready FastAPI application with AI agents, real-time voice processing, document intelligence, and comprehensive family/workspace management.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com)
[![LangChain](https://img.shields.io/badge/LangChain-0.3.20-purple.svg)](https://langchain.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## ✨ Features

### 🤖 **AI-Powered Intelligence**
- **6 Specialized AI Agents**: Personal, Family, Workspace, Commerce, Security, Voice
- **LangChain/LangGraph Integration**: Advanced multi-step workflows
- **Local LLM Support**: Ollama (Gemma3, DeepSeek-R1)
- **Conversation Memory**: Redis-backed chat history
- **Streaming Responses**: Real-time token-level streaming

### 🎙️ **Voice & Real-Time Communication**
- **LiveKit Integration**: WebRTC voice streaming
- **Deepgram STT/TTS**: Production-grade speech processing
- **Voice Agents**: Natural language voice commands
- **Real-time Transcription**: Async voice processing

### 📄 **Document Processing**
- **Docling Integration**: PDF, DOCX, PPTX processing
- **OCR Support**: Text extraction from images
- **Table Extraction**: Structured data parsing
- **RAG Chunking**: Semantic document splitting
- **Async Processing**: Celery-based background tasks

### 👨‍👩‍👧‍👦 **Family Management**
- **Family Groups**: Shared wallets and permissions
- **Relationships**: Member connections and roles
- **Token Requests**: Approval workflows
- **Spending Limits**: Per-member controls
- **Notifications**: Real-time family updates

### 🏢 **Workspace Collaboration**
- **Team Workspaces**: Multi-member collaboration
- **Workspace Wallets**: Shared resource management
- **Role-Based Access**: Admin, member, viewer roles
- **Audit Logs**: Complete activity tracking
- **Emergency Access**: Backup admin system

### 🛍️ **Shop & Assets**
- **Digital Assets**: Avatars, banners, themes
- **SBD Token Economy**: Internal currency system
- **Purchase History**: Transaction tracking
- **Asset Rentals**: Time-based access
- **Usage Analytics**: Asset consumption metrics

### 🔐 **Security & Authentication**
- **JWT Authentication**: Secure token-based auth
- **2FA Support**: TOTP/SMS verification
- **Rate Limiting**: DDoS protection
- **IP Whitelisting**: Trusted device management
- **Audit Logging**: Comprehensive security logs
- **Encryption**: Fernet-based data protection

### 🔌 **MCP (Model Context Protocol) Server**
- **138+ MCP Tools**: Comprehensive tool library
- **FastMCP 2.x**: Modern protocol implementation
- **HTTP/stdio Transport**: Flexible connectivity
- **Tool Categories**: Family, Auth, Shop, Workspace, Admin
- **Security Decorators**: Permission-based access
- **Performance Monitoring**: Metrics and alerting

### ⚡ **Async & Background Processing**
- **Celery Workers**: 4 specialized queues (default, ai, voice, workflows)
- **Celery Beat**: Scheduled task execution
- **Flower Monitoring**: Real-time task dashboard
- **Redis Broker**: High-performance message queue

### 📊 **Monitoring & Observability**
- **LangSmith**: AI agent tracing and debugging
- **Loki Integration**: Centralized logging
- **Performance Metrics**: Response times, resource usage
- **Health Checks**: Service availability monitoring
- **Error Recovery**: Circuit breakers and retries

---

## 🚀 Quick Start

### Prerequisites
- **Python 3.11+**
- **MongoDB 6.0+** (via Docker recommended)
- **Redis 7.0+**
- **Ollama** (for AI features)
- **uv** (package manager) - `curl -LsSf https://astral.sh/uv/install.sh | sh`

### Installation

```bash
# Clone repository
git clone https://github.com/rohanbatrain/second_brain_database.git
cd second_brain_database

# Install dependencies with uv
uv venv && source .venv/bin/activate  # macOS/Linux
uv pip install -r requirements.txt

# Start MongoDB (Docker)
docker run -d -p 27017:27017 --name mongodb mongo

# Configure environment
cp .sbd-example .sbd
# Edit .sbd with your settings

# Start all services (AUTOMATIC)
./start.sh
```

**🎉 Done!** API is now running at http://localhost:8000

---

## 🎮 Service Management

### Automatic Startup (Recommended)

The `./start.sh` script automatically handles all services with production-ready error handling:

```bash
# Start all services
./start.sh

# Output:
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Phase 1: Infrastructure Services
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# [SUCCESS] MongoDB available on port 27017 (Docker)
# [SUCCESS] Redis started
# [SUCCESS] Ollama started
# 
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Phase 2: Application Services
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# [SUCCESS] FastAPI started on http://localhost:8000 (PID: 12345)
# [SUCCESS] Celery Worker started (PID: 12346)
# [SUCCESS] Celery Beat started (PID: 12347)
# [SUCCESS] Flower started on http://localhost:5555 (PID: 12348)
# 
# ✓ All services started successfully!
```

**Features:**
- ✅ **Import validation** before starting services
- ✅ **Health checks** for all ports
- ✅ **Auto-cleanup** if ANY service fails
- ✅ **All-or-nothing** startup (partial failures auto-rollback)
- ✅ **Detailed logs** saved to `logs/startup_YYYYMMDD_HHMMSS.log`
- ✅ **Uses `uv run python`** for all Python commands

---

## 🎙️ Voice Features Setup (Optional)

Voice features require **LiveKit server** and **Deepgram API**. The startup script will **fail gracefully** if these are not configured.

### Option 1: Skip Voice Features

To run without voice features, comment out these lines in `scripts/startall/start_all.sh`:

```bash
# start_livekit           # Comment this out
# start_voice_worker      # Comment this out
```

Then run `./start.sh` normally.

### Option 2: Enable Voice Features

#### 1. Install LiveKit Server

**macOS (Homebrew):**
```bash
brew install livekit-server
```

**Linux:**
```bash
# Download from GitHub releases
wget https://github.com/livekit/livekit/releases/latest/download/livekit-server-linux-amd64
chmod +x livekit-server-linux-amd64
sudo mv livekit-server-linux-amd64 /usr/local/bin/livekit-server
```

**Docker:**
```bash
docker run -d -p 7880:7880 -p 7881:7881 \
  --name livekit-server \
  livekit/livekit-server --dev
```

#### 2. Get API Credentials

**For Development (Local Server):**
- LiveKit dev mode uses `devkey` / `secret` (already in `.sbd`)
- Start server with: `livekit-server --dev`

**For Production (LiveKit Cloud):**
1. Sign up at https://cloud.livekit.io/
2. Create a project
3. Get API Key and Secret from dashboard
4. Update `.sbd` file:
   ```bash
   LIVEKIT_API_KEY=your_real_api_key_here
   LIVEKIT_API_SECRET=your_real_api_secret_here
   LIVEKIT_URL=wss://your-project.livekit.cloud
   ```

#### 3. Get Deepgram API Key

1. Sign up at https://deepgram.com/
2. Create a new project
3. Generate API key
4. Add to `.sbd`:
   ```bash
   DEEPGRAM_API_KEY=your_deepgram_api_key_here
   ```

#### 4. Install Python Dependencies

```bash
uv pip install livekit livekit-agents livekit-plugins-deepgram livekit-plugins-silero
```

#### 5. Start Services

Now run `./start.sh` and all voice features will be enabled!

**Validation Checks:**
- ✅ LiveKit server must be running on port 7880
- ✅ Real API credentials required (not `devkey`/`secret`)
- ✅ Deepgram API key required for transcription
- ✅ Voice worker will gracefully exit with clear error messages if requirements not met

---

### Stop All Services

```bash
./stop.sh

# Output:
# [INFO] Stopping all services...
# [SUCCESS] All application services stopped
```

### Check Service Health

```bash
./scripts/startall/check_service_health.sh

# Output:
# ╔════════════════════════════════════════════════════════════════╗
# ║       Second Brain Database - Service Health Check            ║
# ╚════════════════════════════════════════════════════════════════╝
# 
# Infrastructure Services:
# ─────────────────────────
# ✓ MongoDB (Docker) (port 27017)
# ✓ Redis (port 6379)
# ✓ Ollama (port 11434)
# 
# Application Services:
# ─────────────────────────
# ✓ FastAPI (port 8000)
# ✓ Celery Worker (PID: 12346)
# ✓ Celery Beat (PID: 12347)
# ✓ Flower (port 5555)
```

---

## 📋 Manual Service Management

If you need fine-grained control, you can start services individually:

### 1. Start Infrastructure Services

```bash
# MongoDB (Docker - recommended)
docker run -d -p 27017:27017 --name mongodb mongo
# Or start existing container:
docker start mongodb

# Redis
redis-server --daemonize yes --logfile logs/redis.log

# Ollama (optional - for AI features)
ollama serve > logs/ollama.log 2>&1 &

# LiveKit (optional - for voice features)
livekit-server --dev > logs/livekit.log 2>&1 &
```

### 2. Start Application Services

```bash
# FastAPI Server
uv run python scripts/manual/start_fastapi_server.py > logs/fastapi.log 2>&1 &

# Celery Worker (background tasks)
uv run python scripts/manual/start_celery_worker.py > logs/celery_worker.log 2>&1 &

# Celery Beat (scheduled tasks)
uv run python scripts/manual/start_celery_beat.py > logs/celery_beat.log 2>&1 &

# Flower (task monitoring dashboard)
uv run python scripts/manual/start_flower.py > logs/flower.log 2>&1 &

# Voice Worker (optional - requires LiveKit)
uv run python scripts/manual/start_voice_worker.py > logs/voice_worker.log 2>&1 &
```

### 3. Stop Services Manually

```bash
# Kill all services
pkill -f "start_fastapi_server"
pkill -f "start_celery_worker"
pkill -f "start_celery_beat"
pkill -f "start_flower"
pkill -f "start_voice_worker"

# Stop Redis
redis-cli shutdown

# Stop MongoDB (Docker)
docker stop mongodb

# Stop Ollama
pkill ollama
```

---

## 📊 Log Monitoring

### View Logs in Current Terminal

```bash
# Interactive menu - choose service
./scripts/startall/attach_service.sh

# Or directly specify service:
./scripts/startall/attach_service.sh fastapi
./scripts/startall/attach_service.sh celery_worker
./scripts/startall/attach_service.sh flower
```

### Open Logs in New Terminal Windows

```bash
# Single service in new window
./scripts/startall/open_service_terminal.sh fastapi

# All services in separate tabs
./scripts/startall/open_all_terminals.sh
```

### Quick Log Commands

```bash
# Follow live logs
tail -f logs/fastapi.log
tail -f logs/celery_worker.log

# View all errors in real-time
tail -f logs/*.log | grep -i error

# Check startup log
tail -f logs/startup_*.log

# Last 100 lines
tail -100 logs/fastapi.log

# Search for specific errors
grep "ImportError" logs/fastapi.log
```

### Import Error Debugging

If services fail to start, check import test logs:

```bash
# FastAPI import errors
cat logs/fastapi_import_test.log

# Celery import errors
cat logs/celery_import_test.log

# Test imports manually
uv run python -c "from src.second_brain_database.main import app"
uv run python -c "from second_brain_database.tasks.celery_app import celery_app"
```

---

## 🔧 Troubleshooting

### Service Won't Start

**Problem:** `./start.sh` exits with error

**Solution:**
1. Check the startup log:
   ```bash
   tail -50 logs/startup_*.log
   ```

2. Check specific service logs:
   ```bash
   tail -50 logs/fastapi.log
   tail -50 logs/celery_worker.log
   ```

3. Check import errors:
   ```bash
   cat logs/fastapi_import_test.log
   cat logs/celery_import_test.log
   ```

4. Verify dependencies:
   ```bash
   uv pip install -r requirements.txt
   ```

### MongoDB Not Accessible

**Problem:** `[ERROR] MongoDB not accessible on port 27017`

**Solution:**
```bash
# Check if container exists
docker ps -a | grep mongo

# Start existing container
docker start mongodb

# Or create new container
docker run -d -p 27017:27017 --name mongodb mongo

# Verify connection
nc -z localhost 27017
```

### Import Errors

**Problem:** `ModuleNotFoundError` or `ImportError`

**Solution:**
```bash
# Reinstall dependencies
uv pip install -r requirements.txt

# Test specific imports
uv run python -c "from src.second_brain_database.main import app"

# Check Python path
uv run python -c "import sys; print(sys.path)"
```

### Port Already in Use

**Problem:** `Port 8000 already in use`

**Solution:**
```bash
# Find process using port
lsof -i :8000

# Kill the process
kill -9 <PID>

# Or use different port in .sbd
echo "PORT=8001" >> .sbd
```

### Services Keep Failing

**Problem:** Services start but crash immediately

**Solution:**
```bash
# 1. Stop everything
./stop.sh

# 2. Clear PIDs and logs
rm -f pids/*.pid
rm -f logs/*.log

# 3. Check system resources
top -l 1 | grep "CPU\|PhysMem"

# 4. Start with debug mode
DEBUG=1 ./start.sh
```

---

## 🎯 What Happens When a Service Fails?

The startup script has **all-or-nothing** behavior:

1. **If ANY service fails**, all previously started services are **automatically stopped**
2. **Detailed error logs** are displayed immediately
3. **Startup exits with code 1**

**Example:**
```bash
./start.sh

[SUCCESS] MongoDB available
[SUCCESS] Redis started
[SUCCESS] Ollama started
[SUCCESS] FastAPI started
[ERROR] Celery Worker failed to start
[ERROR] Stopping all services due to failure...
[INFO] Stopping fastapi...
[INFO] Stopping ollama...
[INFO] Stopping redis...
[ERROR] All services stopped due to startup failure

# Exit code: 1
```

This prevents partial deployments where some services run while others fail.

---

## 📁 Service Ports Reference

| Service | Port | Purpose |
|---------|------|---------|
| **FastAPI** | 8000 | REST API and WebSocket |
| **Flower** | 5555 | Celery task monitoring |
| **MongoDB** | 27017 | Primary database |
| **Redis** | 6379 | Cache and message broker |
| **Ollama** | 11434 | Local LLM inference |
| **LiveKit** | 7880 | WebRTC voice server |

---

## 📖 Documentation

- **[Quick Start Guide](QUICKSTART.md)** - Get running in 2 minutes
- **[Log Monitoring Guide](LOG_MONITORING_GUIDE.md)** - How to study and debug logs
- **[Production Startup Guide](PRODUCTION_STARTUP_IMPROVEMENTS.md)** - Auto-startup features
- **[API Documentation](http://localhost:8000/docs)** - Interactive Swagger UI
- **[Architecture Overview](#architecture)** - System design and components

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Second Brain Database                      │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌───────────────┐  ┌───────────────┐  ┌──────────────┐    │
│  │   FastAPI     │  │    Celery     │  │    Voice     │    │
│  │   Server      │  │   Workers     │  │   Worker     │    │
│  │  (REST/WS)    │  │  (4 Queues)   │  │  (LiveKit)   │    │
│  └───────┬───────┘  └───────┬───────┘  └──────┬───────┘    │
│          │                  │                  │             │
│  ┌───────▼──────────────────▼──────────────────▼───────┐   │
│  │          Redis (Cache, Queue, Sessions)             │   │
│  └────────────────────────┬────────────────────────────┘   │
│                           │                                  │
│  ┌────────────────────────▼────────────────────────────┐   │
│  │          MongoDB (Primary Database)                 │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │   Ollama (Local LLM: Gemma3, DeepSeek-R1)          │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │   AI Agents (LangChain/LangGraph)                   │   │
│  │   • Personal  • Family  • Workspace                 │   │
│  │   • Commerce  • Security  • Voice                   │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Technology Stack

| Category | Technologies |
|----------|-------------|
| **Backend** | FastAPI, Python 3.11, Pydantic |
| **Database** | MongoDB, Redis |
| **AI/ML** | LangChain, LangGraph, Ollama, LangSmith |
| **Voice** | LiveKit, Deepgram (STT/TTS) |
| **Documents** | Docling, PyPDF, OCR |
| **Tasks** | Celery, Celery Beat, Flower |
| **Protocol** | FastMCP 2.x, WebSocket, REST |
| **Security** | JWT, Fernet, 2FA, Rate Limiting |
| **Monitoring** | Loki, LangSmith, Prometheus |

---

## 🔌 API Overview

### Authentication
```bash
POST /api/v1/auth/register      # Register new user
POST /api/v1/auth/login         # Login
POST /api/v1/auth/refresh       # Refresh token
POST /api/v1/auth/logout        # Logout
GET  /api/v1/auth/me            # Get current user
```

### AI Agents
```bash
POST /api/v1/ai/sessions        # Create AI session
POST /api/v1/ai/chat            # Chat with agent
GET  /api/v1/ai/sessions/{id}   # Get session info
WS   /api/v1/ai/ws/{session}    # WebSocket streaming
```

### Family Management
```bash
POST /api/v1/families           # Create family
GET  /api/v1/families           # List families
POST /api/v1/families/{id}/members  # Add member
GET  /api/v1/families/{id}/wallet   # Get wallet
```

### Document Processing
```bash
POST /api/v1/documents/upload   # Upload document
GET  /api/v1/documents/{id}     # Get document
POST /api/v1/documents/{id}/chunk  # Chunk for RAG
```

### Voice Processing
```bash
POST /api/v1/voice/transcribe   # Speech-to-text
POST /api/v1/voice/synthesize   # Text-to-speech
WS   /api/v1/voice/stream        # Real-time voice
```

### MCP Server
```bash
POST /mcp/tools                 # List available tools
POST /mcp/tools/execute         # Execute tool
GET  /mcp/resources             # List resources
```

---

## 🧪 Development

### Running Tests

```bash
# All tests
pytest tests/

# Unit tests only
pytest tests/unit/

# Integration tests
pytest tests/integration/

# With coverage
pytest --cov=src/second_brain_database tests/

# Specific test file
pytest tests/test_ai_agents.py -v
```

### Code Quality

```bash
# Format code
black .
isort .

# Lint
ruff check .
mypy .

# Run all checks
./scripts/quality_check.sh
```

### Development Workflow

```bash
# 1. Start services
./start.sh

# 2. Open service terminals
./scripts/startall/open_all_terminals.sh

# 3. Make changes
# Code is hot-reloaded automatically when DEBUG=True

# 4. Test
pytest tests/

# 5. View logs
./scripts/startall/attach_service.sh fastapi
```

---

## 📊 Monitoring

### Service Dashboards

| Dashboard | URL | Purpose |
|-----------|-----|---------|
| **API Docs** | http://localhost:8000/docs | Interactive API documentation |
| **Flower** | http://localhost:5555 | Celery task monitoring |
| **Health** | http://localhost:8000/health | System health status |

### Logs

```bash
# View FastAPI logs
./scripts/startall/attach_service.sh fastapi

# View Celery logs
./scripts/startall/attach_service.sh celery

# View all logs
tail -f logs/*.log
```

### Metrics

```bash
# System health
curl http://localhost:8000/health

# AI metrics
curl http://localhost:8000/api/v1/ai/health

# Celery status
celery -A src.second_brain_database.tasks.celery_app inspect active
```

---

## 🚢 Deployment

### Docker Deployment

```bash
# Build image
docker build -t second-brain-db:latest .

# Run with docker-compose
docker-compose up -d

# Scale workers
docker-compose up -d --scale celery-worker=4
```

### Production Checklist

- [ ] Set `DEBUG=False` in `.sbd`
- [ ] Use strong `JWT_SECRET_KEY`
- [ ] Configure production database URLs
- [ ] Set up SSL/TLS certificates
- [ ] Enable rate limiting
- [ ] Configure CORS for your domain
- [ ] Set up backup strategy
- [ ] Configure monitoring and alerting
- [ ] Review security settings
- [ ] Test disaster recovery

See [SETUP_GUIDE.md#production-deployment](SETUP_GUIDE.md#production-deployment) for details.

---

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Development Setup

```bash
# Fork and clone
git clone https://github.com/YOUR_USERNAME/second_brain_database.git
cd second_brain_database

# Create feature branch
git checkout -b feature/amazing-feature

# Install dev dependencies
uv pip install -r requirements-dev.txt

# Make changes and test
pytest tests/

# Submit PR
git push origin feature/amazing-feature
```

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **[LangChain](https://langchain.com)** - AI agent framework
- **[FastAPI](https://fastapi.tiangolo.com)** - Modern web framework
- **[Ollama](https://ollama.ai)** - Local LLM runtime
- **[LiveKit](https://livekit.io)** - Real-time communication
- **[Deepgram](https://deepgram.com)** - Speech processing
- **[FastMCP](https://github.com/jlowin/fastmcp)** - MCP implementation

---

## 📧 Support

- **Documentation**: [SETUP_GUIDE.md](SETUP_GUIDE.md)
- **Issues**: [GitHub Issues](https://github.com/rohanbatrain/second_brain_database/issues)
- **Discussions**: [GitHub Discussions](https://github.com/rohanbatrain/second_brain_database/discussions)

---

## 🗺️ Roadmap

### v1.1 (Q1 2025)
- [ ] Multi-modal AI agents (text + image + voice)
- [ ] Advanced RAG with vector database
- [ ] Real-time collaboration features
- [ ] Mobile app support

### v1.2 (Q2 2025)
- [ ] Multi-language support
- [ ] Custom agent training
- [ ] Blockchain integration for SBD tokens
- [ ] Advanced analytics dashboard

### Future
- [ ] Plugin system
- [ ] GraphQL API
- [ ] Kubernetes deployment
- [ ] Cloud-native features

---

<div align="center">

**Built with ❤️ by [Rohan Batrain](https://github.com/rohanbatrain)**

⭐ **Star this repo if you find it useful!** ⭐

</div>


## 📚 Documentation

All project documentation is organized in the `docs/` directory:

- **[Documentation Index](docs/INDEX.md)** - Complete documentation catalog
- **[Implementation Status](docs/implementation/)** - Feature implementations and status
- **[Integration Guides](docs/integrations/)** - External service integrations
- **[Maintenance](docs/maintenance/)** - Code quality and maintenance reports
- **[Operations](docs/operations/)** - Monitoring and operational guides

For quick start instructions, see [QUICKSTART.md](QUICKSTART.md).

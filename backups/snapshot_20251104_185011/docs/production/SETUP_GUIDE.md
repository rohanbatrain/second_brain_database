# Second Brain Database - Complete Setup Guide

## 🚀 Quick Start (5 Minutes)

### Prerequisites
- Python 3.11+
- Docker & Docker Compose
- MongoDB
- Redis
- Ollama (for AI features)

### One-Command Startup
```bash
# Start all services
./start.sh

# Stop all services
./stop.sh
```

---

## 📋 Table of Contents

1. [System Requirements](#system-requirements)
2. [Initial Setup](#initial-setup)
3. [Service Architecture](#service-architecture)
4. [Running the Application](#running-the-application)
5. [Environment Configuration](#environment-configuration)
6. [Service Details](#service-details)
7. [Development Workflow](#development-workflow)
8. [Troubleshooting](#troubleshooting)
9. [Production Deployment](#production-deployment)

---

## 🖥️ System Requirements

### Required Software

| Component | Version | Purpose |
|-----------|---------|---------|
| Python | 3.11+ | Application runtime |
| MongoDB | 6.0+ | Primary database |
| Redis | 7.0+ | Caching & session management |
| Ollama | Latest | Local LLM inference |
| Docker | 24.0+ | Container management |
| Node.js | 18+ | Frontend (if applicable) |

### System Resources (Minimum)
- **RAM**: 8GB (16GB recommended for AI features)
- **CPU**: 4 cores (8 cores recommended)
- **Disk**: 20GB free space
- **Network**: Stable internet for model downloads

---

## 🔧 Initial Setup

### Step 1: Clone & Navigate
```bash
git clone https://github.com/rohanbatrain/second_brain_database.git
cd second_brain_database
```

### Step 2: Install Python Dependencies
```bash
# Using uv (recommended)
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -r requirements.txt

# OR using pip
pip install -r requirements.txt
```

### Step 3: Install System Dependencies

#### macOS
```bash
# Install MongoDB
brew tap mongodb/brew
brew install mongodb-community@7.0
brew services start mongodb-community@7.0

# Install Redis
brew install redis
brew services start redis

# Install Ollama
brew install ollama
ollama serve &
```

#### Ubuntu/Debian
```bash
# MongoDB
wget -qO - https://www.mongodb.org/static/pgp/server-7.0.asc | sudo apt-key add -
echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu focal/mongodb-org/7.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list
sudo apt-get update
sudo apt-get install -y mongodb-org
sudo systemctl start mongod

# Redis
sudo apt-get install redis-server
sudo systemctl start redis

# Ollama
curl -fsSL https://ollama.com/install.sh | sh
ollama serve &
```

### Step 4: Download AI Models
```bash
# Pull required Ollama models
ollama pull gemma3:1b           # Fast model (default)
ollama pull deepseek-r1:1.5b    # Reasoning model

# Verify models
ollama list
```

### Step 5: Environment Configuration
```bash
# Copy example environment file
cp .env.example .env

# Edit with your settings
nano .env  # or use your preferred editor
```

**Minimum Required `.env` Settings:**
```bash
# Database
MONGODB_URL=mongodb://127.0.0.1:27017/second_brain_db
REDIS_URL=redis://127.0.0.1:6379/0

# Security
JWT_SECRET_KEY=your-secret-key-here-change-in-production
JWT_ALGORITHM=HS256

# Ollama
OLLAMA_HOST=http://127.0.0.1:11434
OLLAMA_MODEL=gemma3:1b

# Application
DEBUG=True
ENVIRONMENT=development
```

### Step 6: Initialize Database
```bash
# Run database migrations/setup
python scripts/manual/init_database.py

# Optional: Load sample data
python scripts/manual/seed_data.py
```

---

## 🏗️ Service Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Second Brain Database                    │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐  ┌──────────────┐                     │
│  │   FastAPI    │  │   Celery     │                     │
│  │   Server     │  │   Workers    │                     │
│  │  (Port 8000) │  │   (4 queues) │                     │
│  └──────┬───────┘  └──────┬───────┘                     │
│         │                 │                 │               │
│  ┌──────▼─────────────────▼─────────────────▼──────┐       │
│  │              Redis (Broker/Cache)                │       │
│  │              Port 6379                            │       │
│  └──────────────────────────────────────────────────┘       │
│                         │                                    │
│  ┌──────────────────────▼──────────────────────────┐       │
│  │              MongoDB (Primary DB)                │       │
│  │              Port 27017                          │       │
│  └──────────────────────────────────────────────────┘       │
│                                                               │
│  ┌────────────────────────────────────────────────┐         │
│  │         Ollama (Local LLM Inference)           │         │
│  │         Port 11434                             │         │
│  └────────────────────────────────────────────────┘         │
│                                                               │
│  ┌────────────────────────────────────────────────┐         │
│  │         Flower (Celery Monitoring)             │         │
│  │         Port 5555                              │         │
│  └────────────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Running the Application

### Option 1: Unified Startup (Recommended)
```bash
# Start all services in background
./start.sh

# View logs in real-time
./scripts/startall/open_all_terminals.sh

# Attach to specific service
./scripts/startall/attach_service.sh fastapi
```

**Services Started:**
1. MongoDB (if not running)
2. Redis (if not running)
3. Ollama (pulls models if needed)
4. FastAPI Server (port 8000)
5. Celery Worker (async tasks)
6. Celery Beat (scheduled tasks)
7. Flower (monitoring on port 5555)

### Option 2: Manual Service Startup

#### 1. Start Infrastructure
```bash
# MongoDB
mongod --config /usr/local/etc/mongod.conf

# Redis
redis-server

# Ollama
ollama serve
```

#### 2. Start Application Services
```bash
# Terminal 1: FastAPI Server
python scripts/manual/start_fastapi_server.py
# Access: http://localhost:8000

# Terminal 2: Celery Worker
celery -A src.second_brain_database.tasks.celery_app worker \
  --loglevel=info \
  --concurrency=4 \
  --queues=default,ai,voice,workflows

# Terminal 3: Celery Beat (Scheduler)
celery -A src.second_brain_database.tasks.celery_app beat \
  --loglevel=info

# Terminal 4: Flower (Monitoring)
celery -A src.second_brain_database.tasks.celery_app flower \
  --port=5555
# Access: http://localhost:5555

# Terminal 5: Voice Worker (Optional)
python scripts/manual/start_voice_worker.py
```

#### 3. Start MCP Server (Optional)
```bash
python scripts/manual/start_mcp_server.py
```

### Option 3: Docker Compose
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop all services
docker-compose down
```

---

## ⚙️ Environment Configuration

### Complete `.env` Template

```bash
# ============================================================================
# APPLICATION SETTINGS
# ============================================================================
APP_NAME=Second Brain Database
ENVIRONMENT=development  # development, staging, production
DEBUG=True
LOG_LEVEL=INFO
HOST=0.0.0.0
PORT=8000

# ============================================================================
# DATABASE CONFIGURATION
# ============================================================================
MONGODB_URL=mongodb://127.0.0.1:27017/second_brain_db
MONGODB_MAX_POOL_SIZE=100
MONGODB_MIN_POOL_SIZE=10
MONGODB_MAX_IDLE_TIME_MS=45000

REDIS_URL=redis://127.0.0.1:6379/0
REDIS_MAX_CONNECTIONS=50
REDIS_SOCKET_TIMEOUT=5
REDIS_SOCKET_CONNECT_TIMEOUT=5

# ============================================================================
# SECURITY
# ============================================================================
JWT_SECRET_KEY=your-256-bit-secret-key-change-in-production
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

ENCRYPTION_KEY=your-fernet-key-here
PASSWORD_MIN_LENGTH=8
PASSWORD_REQUIRE_UPPERCASE=True
PASSWORD_REQUIRE_LOWERCASE=True
PASSWORD_REQUIRE_DIGIT=True
PASSWORD_REQUIRE_SPECIAL=True

# Rate Limiting
RATE_LIMIT_ENABLED=True
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_PERIOD=60

# ============================================================================
# AI & LLM CONFIGURATION (DISABLED - LangChain/LangGraph removed)
# ============================================================================
# Note: LangChain and LangGraph integrations have been removed from the codebase.
# These settings are kept for reference but are no longer functional.

# LangChain (DISABLED)
# LANGCHAIN_ENABLED=True
# LANGCHAIN_MODEL_PROVIDER=ollama
# LANGCHAIN_DEFAULT_MODEL=gemma3:1b
# LANGCHAIN_TEMPERATURE=0.7
# LANGCHAIN_MAX_TOKENS=2048
# LANGCHAIN_MEMORY_TTL=3600
# LANGCHAIN_CONVERSATION_HISTORY_LIMIT=50

# Ollama
OLLAMA_HOST=http://127.0.0.1:11434
OLLAMA_MODEL=gemma3:1b
OLLAMA_AVAILABLE_MODELS=gemma3:1b,deepseek-r1:1.5b
OLLAMA_REASONING_MODEL=deepseek-r1:1.5b
OLLAMA_FAST_MODEL=gemma3:1b
OLLAMA_AUTO_MODEL_SELECTION=True

# AI Agent Configuration
AI_MODEL_POOL_SIZE=5
AI_MAX_CONCURRENT_SESSIONS=100
AI_SESSION_TIMEOUT=3600
AI_MODEL_RESPONSE_TIMEOUT=120
AI_WORKFLOW_TIMEOUT=600
AI_MODEL_TEMPERATURE=0.7
AI_DEFAULT_AGENT=personal

# LangSmith Observability (Optional)
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=SecondBrainDatabase
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_TRACING=False

# ============================================================================
# CELERY CONFIGURATION
# ============================================================================
CELERY_BROKER_URL=redis://127.0.0.1:6379/0
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/0
CELERY_TASK_SERIALIZER=json
CELERY_ACCEPT_CONTENT=json
CELERY_TIMEZONE=UTC
CELERY_ENABLE_UTC=True

# ============================================================================
# MCP SERVER CONFIGURATION
# ============================================================================
MCP_ENABLED=True
MCP_SERVER_NAME=SecondBrainMCP
MCP_SERVER_VERSION=1.0.0
MCP_DEBUG_MODE=False

# Transport
MCP_TRANSPORT=stdio  # stdio or http
MCP_HTTP_HOST=127.0.0.1
MCP_HTTP_PORT=8001
MCP_HTTP_CORS_ENABLED=False

# Security
MCP_SECURITY_ENABLED=True
MCP_REQUIRE_AUTH=True
MCP_AUDIT_ENABLED=True

# Rate Limiting
MCP_RATE_LIMIT_ENABLED=True
MCP_RATE_LIMIT_REQUESTS=100
MCP_RATE_LIMIT_PERIOD=60

# Tool Access Control
MCP_FAMILY_TOOLS_ENABLED=True
MCP_AUTH_TOOLS_ENABLED=True
MCP_PROFILE_TOOLS_ENABLED=True
MCP_SHOP_TOOLS_ENABLED=True
MCP_WORKSPACE_TOOLS_ENABLED=True
MCP_ADMIN_TOOLS_ENABLED=False  # Security: disabled by default

# ============================================================================
# DOCUMENT PROCESSING
# ============================================================================
DOCLING_ENABLED=True
DOCLING_MAX_FILE_SIZE=52428800  # 50MB
DOCLING_SUPPORTED_FORMATS=pdf,docx,pptx
DOCLING_OCR_ENABLED=True

# ============================================================================
# API DOCUMENTATION
# ============================================================================
DOCS_ENABLED=True
DOCS_URL=/docs
DOCS_REDOC_URL=/redoc
DOCS_CACHE_TTL=3600
DOCS_REQUIRE_AUTH=False

# ============================================================================
# CORS CONFIGURATION
# ============================================================================
CORS_ENABLED=True
CORS_ORIGINS=http://localhost:3000,http://localhost:8000
CORS_ALLOW_CREDENTIALS=True
CORS_ALLOW_METHODS=GET,POST,PUT,DELETE,PATCH
CORS_ALLOW_HEADERS=*
CORS_MAX_AGE=3600

# ============================================================================
# LOGGING & MONITORING
# ============================================================================
# Loki (Optional)
LOKI_ENABLED=False
LOKI_URL=http://localhost:3100/loki/api/v1/push

# Performance Monitoring
PERFORMANCE_MONITORING_ENABLED=True
METRICS_COLLECTION_INTERVAL=60

# ============================================================================
# FEATURE FLAGS
# ============================================================================
FEATURE_AI_AGENTS=True
FEATURE_VOICE_PROCESSING=True
FEATURE_DOCUMENT_PROCESSING=True
FEATURE_MCP_SERVER=True
FEATURE_FAMILY_MANAGEMENT=True
FEATURE_WORKSPACE_MANAGEMENT=True
FEATURE_SHOP=True
```

---

## 📊 Service Details

### FastAPI Server (Port 8000)
**Purpose**: Main REST API server  
**Endpoints**:
- Health: `http://localhost:8000/health`
- Docs: `http://localhost:8000/docs`
- API: `http://localhost:8000/api/v1/`

**Testing**:
```bash
# Health check
curl http://localhost:8000/health

# API documentation
open http://localhost:8000/docs
```

### Celery Worker (Background Tasks)
**Purpose**: Async task processing  
**Queues**:
- `default`: General tasks
- `ai`: AI/LLM processing
- `voice`: Voice transcription/synthesis
- `workflows`: Multi-step workflows

**Monitoring**:
```bash
# View Flower dashboard
open http://localhost:5555
```

### MongoDB (Port 27017)
**Purpose**: Primary data storage  
**Collections**:
- `users` - User accounts
- `families` - Family groups
- `workspaces` - Team workspaces
- `shop_items` - Shop inventory
- `transactions` - Financial transactions
- `ai_conversations` - AI chat history

**Management**:
```bash
# MongoDB shell
mongosh

# View databases
use second_brain_db
show collections

# Example query
db.users.find().limit(5)
```

### Redis (Port 6379)
**Purpose**: Cache, sessions, Celery broker  
**Key Patterns**:
- `session:*` - User sessions
- `rate_limit:*` - Rate limiting
- `langchain:chat:*` - AI conversation history
- `celery-task-meta-*` - Task results

**Management**:
```bash
# Redis CLI
redis-cli

# View keys
KEYS *

# Monitor activity
MONITOR
```

### Ollama (Port 11434)
**Purpose**: Local LLM inference  
**Models**:
- `gemma3:1b` - Fast responses (default)
- `deepseek-r1:1.5b` - Reasoning tasks

**Management**:
```bash
# List models
ollama list

# Pull new model
ollama pull llama2

# Run model directly
ollama run gemma3:1b "Hello, world!"

# Check API
curl http://localhost:11434/api/tags
```

---

## 🛠️ Development Workflow

### Daily Development Flow

#### 1. Start Development Environment
```bash
# Start all services
./start.sh

# Open service terminals
./scripts/startall/open_all_terminals.sh
```

#### 2. Make Code Changes
```bash
# Edit code in your IDE
code .

# Run tests
pytest tests/

# Check code quality
black .
ruff check .
mypy .
```

#### 3. Test Your Changes
```bash
# Unit tests
pytest tests/unit/

# Integration tests
pytest tests/integration/

# Specific test
pytest tests/test_ai_agents.py -v

# With coverage
pytest --cov=src/second_brain_database tests/
```

#### 4. Hot Reload
FastAPI automatically reloads on code changes when `DEBUG=True`.

#### 5. Check Logs
```bash
# View FastAPI logs
./scripts/startall/attach_service.sh fastapi

# View Celery logs
./scripts/startall/attach_service.sh celery

# View all logs
tail -f logs/*.log
```

### Database Migrations
```bash
# Create migration
python scripts/manual/create_migration.py "add_new_field"

# Run migrations
python scripts/manual/run_migrations.py

# Rollback
python scripts/manual/rollback_migration.py
```

### API Testing
```bash
# Using curl
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "test", "email": "test@example.com", "password": "Test123!"}'

# Using httpie
http POST localhost:8000/api/v1/auth/login \
  username=test password=Test123!

# Using Python requests
python scripts/manual/test_api.py
```

---

## 🐛 Troubleshooting

### Common Issues

#### 1. Port Already in Use
```bash
# Find process using port 8000
lsof -i :8000

# Kill process
kill -9 <PID>

# Or change port in .env
PORT=8001
```

#### 2. MongoDB Connection Failed
```bash
# Check MongoDB status
brew services list | grep mongodb
# or
sudo systemctl status mongod

# Restart MongoDB
brew services restart mongodb-community
# or
sudo systemctl restart mongod

# Check logs
tail -f /usr/local/var/log/mongodb/mongo.log
```

#### 3. Redis Connection Failed
```bash
# Check Redis
redis-cli ping
# Should return: PONG

# Restart Redis
brew services restart redis
# or
sudo systemctl restart redis

# Check logs
tail -f /usr/local/var/log/redis.log
```

#### 4. Ollama Model Not Found
```bash
# List available models
ollama list

# Pull missing model
ollama pull gemma3:1b

# Check Ollama service
curl http://localhost:11434/api/tags
```

#### 5. Celery Worker Not Starting
```bash
# Check Redis connection
redis-cli ping

# Clear Celery tasks
celery -A src.second_brain_database.tasks.celery_app purge

# Restart worker with debug
celery -A src.second_brain_database.tasks.celery_app worker \
  --loglevel=debug
```

#### 6. Import Errors
```bash
# Reinstall dependencies
uv pip install -r requirements.txt --force-reinstall

# Clear Python cache
find . -type d -name __pycache__ -exec rm -rf {} +
find . -type f -name "*.pyc" -delete

# Verify installation
python -c "from src.second_brain_database import config; print('✅ OK')"
```

#### 7. Permission Errors
```bash
# Fix script permissions
chmod +x start.sh stop.sh
chmod +x scripts/startall/*.sh

# Fix log directory
mkdir -p logs
chmod 755 logs
```

### Debug Mode

Enable comprehensive debugging:
```bash
# In .env
DEBUG=True
LOG_LEVEL=DEBUG
MCP_DEBUG_MODE=True

# Restart services
./stop.sh && ./start.sh
```

### Health Checks

```bash
# FastAPI health
curl http://localhost:8000/health

# MongoDB health
mongosh --eval "db.adminCommand('ping')"

# Redis health
redis-cli ping

# Ollama health
curl http://localhost:11434/api/tags

# Celery health
celery -A src.second_brain_database.tasks.celery_app inspect ping
```

---

## 🚢 Production Deployment

### Pre-Deployment Checklist

- [ ] Change all secret keys in `.env`
- [ ] Set `DEBUG=False`
- [ ] Set `ENVIRONMENT=production`
- [ ] Configure proper CORS origins
- [ ] Enable rate limiting
- [ ] Set up SSL/TLS certificates
- [ ] Configure backup strategy
- [ ] Set up monitoring and alerting
- [ ] Test all critical paths
- [ ] Document deployment procedures

### Production Environment Variables

```bash
# Critical Security Settings
DEBUG=False
ENVIRONMENT=production
JWT_SECRET_KEY=<use-strong-256-bit-key>
ENCRYPTION_KEY=<use-fernet-key>

# Database URLs (use production instances)
MONGODB_URL=mongodb://prod-host:27017/second_brain_db
REDIS_URL=redis://prod-host:6379/0

# CORS (restrict to your domains)
CORS_ORIGINS=https://yourdomain.com,https://app.yourdomain.com

# Rate Limiting (stricter)
RATE_LIMIT_REQUESTS=50
RATE_LIMIT_PERIOD=60

# MCP Security
MCP_ADMIN_TOOLS_ENABLED=False
MCP_SYSTEM_TOOLS_ENABLED=False
```

### Docker Production Deployment

```bash
# Build production image
docker build -t second-brain-db:prod -f Dockerfile.prod .

# Run with docker-compose
docker-compose -f docker-compose.prod.yml up -d

# Scale workers
docker-compose -f docker-compose.prod.yml up -d --scale celery-worker=4
```

### System Configuration

#### Nginx Reverse Proxy
```nginx
server {
    listen 80;
    server_name api.yourdomain.com;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
    
    location /ws {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

#### Systemd Service
```ini
# /etc/systemd/system/second-brain.service
[Unit]
Description=Second Brain Database API
After=network.target mongodb.service redis.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/second-brain-db
Environment="PATH=/opt/second-brain-db/.venv/bin"
ExecStart=/opt/second-brain-db/.venv/bin/python scripts/manual/start_fastapi_server.py
Restart=always

[Install]
WantedBy=multi-user.target
```

### Monitoring & Logging

```bash
# Production logging
LOKI_ENABLED=True
LOKI_URL=http://loki:3100/loki/api/v1/push

# LangSmith tracing
LANGSMITH_TRACING=True
LANGSMITH_API_KEY=<your-api-key>

# Performance monitoring
PERFORMANCE_MONITORING_ENABLED=True
METRICS_COLLECTION_INTERVAL=30
```

---

## 📚 Additional Resources

### Documentation
- **API Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **LangChain**: https://docs.langchain.com
- **FastAPI**: https://fastapi.tiangolo.com
- **Celery**: https://docs.celeryq.dev

### Project Structure
```
second_brain_database/
├── src/second_brain_database/
│   ├── config.py                    # Configuration
│   ├── main.py                      # FastAPI app
│   ├── managers/                    # Core managers
│   ├── models/                      # Pydantic models
│   ├── routes/                      # API endpoints
│   ├── integrations/
│   │   ├── langchain/              # AI agents
│   │   ├── mcp/                    # MCP server
│   │   └── docling/                # Document processing
│   └── tasks/                      # Celery tasks
├── scripts/
│   ├── startall/                   # Startup scripts
│   └── manual/                     # Manual operations
├── tests/                          # Test suite
├── logs/                           # Application logs
├── requirements.txt                # Dependencies
├── .env                           # Environment config
├── start.sh                       # Quick start
└── stop.sh                        # Quick stop
```

### Support
- **Issues**: https://github.com/rohanbatrain/second_brain_database/issues
- **Discussions**: https://github.com/rohanbatrain/second_brain_database/discussions

---

## 🎯 Quick Reference

### Essential Commands
```bash
# Start everything
./start.sh

# Stop everything
./stop.sh

# View logs
./scripts/startall/attach_service.sh <service>

# Run tests
pytest tests/

# API health
curl http://localhost:8000/health

# Flower monitoring
open http://localhost:5555
```

### Service Ports
| Service | Port | URL |
|---------|------|-----|
| FastAPI | 8000 | http://localhost:8000 |
| MCP Server | 8001 | http://localhost:8001 |
| Flower | 5555 | http://localhost:5555 |
| MongoDB | 27017 | mongodb://localhost:27017 |
| Redis | 6379 | redis://localhost:6379 |
| Ollama | 11434 | http://localhost:11434 |

### Default Credentials
```
Admin User (created on first run):
Username: admin
Email: admin@secondbrain.local
Password: admin123 (CHANGE IN PRODUCTION!)
```

---

**Last Updated**: November 2, 2025  
**Version**: 1.0.0  
**Maintainer**: Rohan Batrain

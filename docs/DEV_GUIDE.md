# Developer Knowledge Base - Second Brain Database

## Prerequisites & Setup

### System Requirements
- **Python 3.11+**
- **MongoDB 6.0+** (via Docker recommended)
- **Redis 7.0+**
- **uv** package manager: `curl -LsSf https://astral.sh/uv/install.sh | sh`

### Environment Setup

1. **Clone and Navigate**:
   ```bash
   git clone https://github.com/rohanbatrain/second_brain_database.git
   cd second_brain_database
   ```

2. **Install Dependencies**:
   ```bash
   uv venv && source .venv/bin/activate  # macOS/Linux
   uv pip install -r requirements.txt
   ```

3. **Start Infrastructure Services**:
   ```bash
   # MongoDB (Docker)
   docker run -d -p 27017:27017 --name mongodb mongo

   # Redis
   redis-server --daemonize yes --logfile logs/redis.log
   ```

4. **Configure Environment**:
   ```bash
   cp .sbd-example .sbd
   # Edit .sbd with your settings (see Configuration section below)
   ```

5. **Start Application**:
   ```bash
   # Automatic startup (recommended)
   ./start.sh

   # Manual startup
   ./scripts/startall/start_fastapi_server.py &
   ./scripts/startall/start_celery_worker.py &
   ./scripts/startall/start_celery_beat.py &
   ./scripts/startall/start_flower.py &
   ```

### Configuration Files

The application uses a hierarchical configuration system:

1. **Environment Variable**: `SECOND_BRAIN_DATABASE_CONFIG_PATH`
2. **`.sbd` file** (recommended for development)
3. **`.env` file**
4. **Environment variables only**

**Required Configuration** (in `.sbd` or environment):
```bash
# Server
HOST=127.0.0.1
PORT=8000
DEBUG=true

# Database
MONGODB_URL=mongodb://localhost:27017
MONGODB_DATABASE=second_brain_db

# Redis
REDIS_URL=redis://localhost:6379

# Security (REQUIRED - generate secure keys)
SECRET_KEY=your-jwt-secret-key-here
REFRESH_TOKEN_SECRET_KEY=your-refresh-secret-key-here
FERNET_KEY=your-fernet-key-here

# Cloudflare Turnstile (for CAPTCHA)
TURNSTILE_SITEKEY=your-site-key
TURNSTILE_SECRET=your-secret-key
```

### Service Management

**Automatic Management**:
```bash
# Start all services
./start.sh

# Stop all services
./stop.sh

# Check health
./scripts/startall/check_service_health.sh
```

**Manual Management**:
```bash
# Individual services
./scripts/manual/start_fastapi_server.py &
./scripts/manual/start_celery_worker.py &
./scripts/manual/start_celery_beat.py &
./scripts/manual/start_flower.py &
```

**Log Monitoring**:
```bash
# View logs
./scripts/startall/attach_service.sh fastapi
./scripts/startall/open_all_terminals.sh

# Follow logs
tail -f logs/fastapi.log
tail -f logs/celery_worker.log
```

## Architecture Overview

### Technology Stack

| Category | Technologies |
|----------|-------------|
| **Backend** | FastAPI, Python 3.11, Pydantic |
| **Database** | MongoDB (Motor async driver), Redis |
| **Task Queue** | Celery, Celery Beat, Flower |
| **AI/ML** | Ollama, LangGraph, LlamaIndex, Sentence Transformers |
| **Document Processing** | Docling, PyPDF, OCR |
| **Security** | JWT, Fernet encryption, 2FA, Rate Limiting |
| **WebRTC** | Real-time communication for clubs |
| **MCP Server** | FastMCP 2.x for AI agent integration |
| **Monitoring** | Prometheus, Loki logging |

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                   Second Brain Database                      │
├─────────────────────────────────────────────────────────────┤
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐    │
│  │   FastAPI     │  │    Celery     │  │    MCP       │    │
│  │   Server      │  │   Workers     │  │   Server     │    │
│  │  (REST/WS)    │  │               │  │  (FastMCP)   │    │
│  └───────┬───────┘  └───────┬───────┘  └───────┬───────┘    │
│          │                  │                  │            │
│  ┌───────▼──────────────────▼──────────────────▼─────────┐ │
│  │          Redis (Cache, Queue, Sessions)             │ │
│  └────────────────────────┬─────────────────────────────┘ │
│                           │                                │
│  ┌────────────────────────▼─────────────────────────────┐ │
│  │          MongoDB (Primary Database)                 │ │
│  └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **API Requests** → FastAPI routes → Business logic managers
2. **Authentication** → JWT validation → User context
3. **Database Operations** → Motor async queries → MongoDB
4. **Caching** → Redis for sessions, rate limits, temporary data
5. **Background Tasks** → Celery workers → Redis queue
6. **AI Processing** → Ollama/LlamaIndex → Vector search/RAG
7. **Real-time Communication** → WebRTC/WebSocket → Redis pub/sub

### Key Managers & Services

- **Database Manager**: MongoDB connection and operations
- **Authentication Manager**: JWT, 2FA, permanent tokens
- **Family Manager**: Family relationships and permissions
- **Workspace Manager**: Team collaboration features
- **IPAM Manager**: Hierarchical IP address allocation
- **Chat Manager**: LangGraph-based conversational AI
- **Document Manager**: File processing and RAG indexing
- **MCP Manager**: Model Context Protocol server

## Development Standards

### Code Quality Tools

**Formatting & Linting**:
```bash
# Run all quality checks
python scripts/lint.py

# Fix formatting automatically
python scripts/lint.py --fix

# Run specific tools
python scripts/lint.py --tool black
python scripts/lint.py --tool isort
python scripts/lint.py --tool pylint
python scripts/lint.py --tool mypy
```

**Configuration** (from `pyproject.toml`):
- **Black**: Line length 120, Python 3.11+ target
- **isort**: Black profile, 120 line length
- **mypy**: Strict type checking with gradual adoption
- **pylint**: Code quality and style checking

### Coding Conventions

**Type Hints**:
```python
from typing import Optional, List, Dict
from pydantic import BaseModel

def process_user(user_id: str, options: Optional[Dict[str, Any]] = None) -> User:
    """Process user with comprehensive type hints."""
    pass
```

**Documentation**:
```python
def authenticate_user(username: str, password: str) -> Optional[User]:
    """
    Authenticate user with credentials.

    Args:
        username: User's username
        password: User's password

    Returns:
        User object if authentication successful, None otherwise

    Raises:
        AuthenticationError: If authentication fails
    """
    pass
```

**Error Handling**:
```python
from fastapi import HTTPException

try:
    result = await risky_operation()
except SpecificException as e:
    raise HTTPException(status_code=400, detail=str(e))
```

**Logging**:
```python
from src.second_brain_database.managers.logging_manager import logger

logger.info("Operation completed", extra={"user_id": user_id, "operation": "create"})
```

### Directory Structure

```
second_brain_database/
├── config/                 # Configuration files and templates
├── docs/                   # Documentation and guides
├── examples/               # Example usage and integrations
├── infra/                  # Infrastructure and deployment configs
├── logs/                   # Application logs
├── scripts/                # Maintenance and utility scripts
├── src/second_brain_database/
│   ├── chat/              # LangGraph chat system
│   ├── config/            # Configuration management
│   ├── database/          # Database models and connections
│   ├── docs/              # API documentation config
│   ├── integrations/      # External service integrations
│   ├── managers/          # Business logic managers
│   ├── migrations/        # Database migrations
│   ├── models/            # Pydantic models
│   ├── rag/               # RAG and vector search
│   ├── routes/            # API route handlers
│   ├── routers/           # FastAPI routers
│   ├── services/          # Service layer
│   ├── tasks/             # Celery tasks
│   ├── tools/             # Utility tools
│   ├── utils/             # Utility functions
│   └── webrtc/            # WebRTC functionality
├── tests/                 # Test suite
└── tools/                 # Development tools
```

### Security Guidelines

- **Never hardcode secrets**: Use `.sbd` files or environment variables
- **Validate all inputs**: Use Pydantic models for request validation
- **Rate limiting**: All endpoints have appropriate rate limits
- **Audit logging**: All sensitive operations are logged
- **Encryption**: Sensitive data uses Fernet encryption
- **JWT security**: Short-lived access tokens, separate refresh tokens

## Common Workflows

### Running Tests

**All Tests**:
```bash
# Run complete test suite
pytest tests/

# With coverage
pytest --cov=src/second_brain_database tests/

# Specific test categories
pytest tests/unit/          # Unit tests only
pytest tests/integration/   # Integration tests only
```

**Test Configuration** (from `pyproject.toml`):
- **pytest-asyncio**: Auto mode for async tests
- **Coverage**: Source from `src/`, omit test files
- **Markers**: `slow`, `integration`, `unit`

### Building for Production

**Docker Deployment**:
```bash
# Build image
docker build -t second-brain-db:latest .

# Run with docker-compose
docker-compose up -d

# Scale workers
docker-compose up -d --scale celery-worker=4
```

**Environment Variables for Production**:
```bash
DEBUG=false
SECRET_KEY=<secure-key>
MONGODB_URL=<production-url>
REDIS_URL=<production-url>
```

**Production Checklist**:
- [ ] Set `DEBUG=False`
- [ ] Use strong `SECRET_KEY` and `FERNET_KEY`
- [ ] Configure production database URLs
- [ ] Set up SSL/TLS certificates
- [ ] Enable rate limiting
- [ ] Configure CORS for your domain
- [ ] Set up backup strategy
- [ ] Configure monitoring and alerting

### Troubleshooting Common Errors

**Service Won't Start**:
```bash
# Check startup logs
tail -50 logs/startup_*.log

# Check import errors
cat logs/fastapi_import_test.log

# Verify dependencies
uv pip install -r requirements.txt
```

**MongoDB Connection Issues**:
```bash
# Check if container exists
docker ps -a | grep mongo

# Start container
docker start mongodb

# Verify connection
nc -z localhost 27017
```

**Import Errors**:
```bash
# Reinstall dependencies
uv pip install -r requirements.txt

# Test imports
uv run python -c "from src.second_brain_database.main import app"
```

**Port Already in Use**:
```bash
# Find process
lsof -i :8000

# Kill process
kill -9 <PID>
```

**High Memory Usage**:
```bash
# Check system resources
top -l 1 | grep "CPU\|PhysMem"

# Monitor Celery workers
celery -A src.second_brain_database.tasks.celery_app inspect active
```

**AI/Ollama Issues**:
```bash
# Check Ollama status
curl http://localhost:11434/api/tags

# Restart Ollama
brew services restart ollama  # macOS
```

### Development Workflow

1. **Start Services**:
   ```bash
   ./start.sh
   ```

2. **Open Development Terminals**:
   ```bash
   ./scripts/startall/open_all_terminals.sh
   ```

3. **Make Changes**:
   - Code hot-reloads automatically when `DEBUG=True`
   - Use `python scripts/lint.py --fix` for formatting

4. **Test Changes**:
   ```bash
   pytest tests/ -v
   ```

5. **Monitor Logs**:
   ```bash
   ./scripts/startall/attach_service.sh fastapi
   ```

### API Testing

**Interactive Documentation**:
- OpenAPI docs: http://localhost:8000/docs
- Alternative docs: http://localhost:8000/redoc

**Health Checks**:
```bash
# System health
curl http://localhost:8000/health

# Celery status
celery -A src.second_brain_database.tasks.celery_app inspect active
```

**Manual API Testing**:
```bash
# Register user
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "test", "email": "test@example.com", "password": "password"}'

# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "test", "password": "password"}'
```

### Performance Monitoring

**Flower Dashboard**: http://localhost:5555 (Celery monitoring)

**Prometheus Metrics**: http://localhost:8000/metrics

**Log Analysis**:
```bash
# View all errors
tail -f logs/*.log | grep -i error

# Search for specific issues
grep "ImportError" logs/fastapi.log

# Performance logs
grep "performance" logs/fastapi.log
```

### Database Maintenance

**Backup Database**:
```bash
# MongoDB backup
docker exec mongodb mongodump --db second_brain_db --out /backup

# Copy from container
docker cp mongodb:/backup ./backup
```

**Index Management**:
```bash
# Check indexes
uv run python -c "
from src.second_brain_database.database import db_manager
import asyncio
asyncio.run(db_manager.connect())
collections = ['users', 'families', 'documents']
for col in collections:
    indexes = asyncio.run(db_manager.get_collection(col).index_information())
    print(f'{col}: {list(indexes.keys())}')
"
```

**Migration Scripts**:
```bash
# Run IPAM migration
python scripts/run_ipam_enhancements_migration.py

# Setup club indexes
python scripts/setup_club_indexes.py
```

This comprehensive guide covers all aspects of developing, deploying, and maintaining the Second Brain Database application. For additional details, refer to the specific documentation files in the `docs/` directory.</content>
<parameter name="filePath">/Users/rohan/Documents/repos/second_brain_database/DEV_GUIDE.md
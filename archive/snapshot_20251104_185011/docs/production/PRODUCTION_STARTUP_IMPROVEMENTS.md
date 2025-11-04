# 🚀 Production Startup Improvements

## Overview

The startup script has been completely overhauled to be **production-ready** with comprehensive error handling, import validation, and detailed logging.

---

## ✅ What's New

### 1. **Import Error Detection** (NEW!)

Before starting any Python service, the script now validates imports:

```bash
# FastAPI import test
python -c "from src.second_brain_database.main import app"

# Celery import test  
python -c "from src.second_brain_database.celery_app import celery_app"

# LiveKit SDK check
python -c "import livekit"

# Flower check
python -c "import flower"
```

**Benefits:**
- ✅ Catches `ModuleNotFoundError` BEFORE service starts
- ✅ Shows import error details immediately
- ✅ Prevents failed services from running in background
- ✅ Saves import test logs for debugging

**Error Example:**
```
[INFO] Testing FastAPI imports...
[ERROR] FastAPI import test failed - missing dependencies or code errors
[ERROR] Check: cat logs/fastapi_import_test.log
ModuleNotFoundError: No module named 'langchain'
```

### 2. **Graceful Error Handling**

**No More `set -e`** - Services fail gracefully without stopping the entire startup:

- **Critical Failures** (stops startup):
  - MongoDB not accessible
  - Redis fails to start
  - FastAPI fails to start

- **Non-Critical Failures** (continues with warnings):
  - Celery Worker fails
  - Celery Beat fails
  - Voice Worker fails
  - Flower fails
  - LiveKit not installed
  - Ollama not installed

**Example Output:**
```
[WARNING] ⚠ Startup completed with some failures
Failed services: celery_worker voice_worker
```

### 3. **Port Health Checks**

Services now wait for ports to be ready before continuing:

```bash
wait_for_port 8000 "FastAPI" 30   # Wait up to 30 seconds
wait_for_port 6379 "Redis" 10     # Wait up to 10 seconds
wait_for_port 5555 "Flower" 15    # Wait up to 15 seconds
```

**Benefits:**
- ✅ Verifies service actually started
- ✅ Prevents race conditions
- ✅ Shows real-time progress

### 4. **Process Health Monitoring**

Checks if processes are actually running after startup:

```bash
check_process_health "$PID_DIR/celery_worker.pid" "celery_worker"
```

**Benefits:**
- ✅ Detects crashed services immediately
- ✅ Validates PID files are accurate
- ✅ Shows process IDs in success messages

### 5. **Detailed Startup Logging**

Every startup creates a timestamped log:

```
logs/startup_20251102_130406.log
```

**Includes:**
- All service start attempts
- Import test results
- Port check progress
- Error details with context
- Service PIDs and ports

### 6. **Automatic Error Display**

When a service fails, the script automatically shows:

```
[ERROR] Celery Worker failed to start. Check logs: tail -f logs/celery_worker.log
[INFO] Last 10 lines of log:
Traceback (most recent call last):
  File "...", line 123, in <module>
    from celery import Celery
ModuleNotFoundError: No module named 'celery'
```

**Benefits:**
- ✅ No need to manually check logs
- ✅ Error context shown immediately
- ✅ Saves time debugging

### 7. **Two-Phase Startup**

```
Phase 1: Infrastructure Services
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- MongoDB (Docker check)
- Redis (start + health check)
- Ollama (optional)
- LiveKit (optional)

Phase 2: Application Services
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- FastAPI (import test + start)
- Voice Worker (import test + start)
- Celery Worker (import test + start)
- Celery Beat (start)
- Flower (import test + start)
```

**Benefits:**
- ✅ Infrastructure ready before apps start
- ✅ Clear separation of concerns
- ✅ Easier to debug failures

---

## 📊 New Log Files

| File | Purpose | When Created |
|------|---------|--------------|
| `logs/startup_YYYYMMDD_HHMMSS.log` | Complete startup log | Every `./start.sh` run |
| `logs/fastapi_import_test.log` | FastAPI import errors | If FastAPI imports fail |
| `logs/celery_import_test.log` | Celery import errors | If Celery imports fail |

---

## 🎯 Usage Examples

### Successful Startup

```bash
./start.sh

[INFO] ========================================
[INFO] Second Brain Database - Startup
[INFO] ========================================
[INFO] Startup log: logs/startup_20251102_130406.log

[INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[INFO] Phase 1: Infrastructure Services
[INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[INFO] Checking MongoDB (Docker)...
[SUCCESS] MongoDB available on port 27017 (Docker)
[INFO] Starting Redis...
[INFO] Waiting for Redis on port 6379...
[SUCCESS] Redis is responding on port 6379
[SUCCESS] Redis started

[INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[INFO] Phase 2: Application Services
[INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[INFO] Starting FastAPI Server...
[INFO] Waiting for FastAPI on port 8000...
[SUCCESS] FastAPI is responding on port 8000
[SUCCESS] FastAPI started on http://localhost:8000 (PID: 12345)

[INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[SUCCESS] ✓ All services started successfully!
[INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Startup with Import Error

```bash
./start.sh

[INFO] Starting FastAPI Server...
[INFO] Testing FastAPI imports...
[ERROR] FastAPI import test failed - missing dependencies or code errors
[ERROR] Check: cat logs/fastapi_import_test.log
Traceback (most recent call last):
  File "<string>", line 1, in <module>
  File "src/second_brain_database/main.py", line 15, in <module>
    from langchain import LLMChain
ModuleNotFoundError: No module named 'langchain'

[ERROR] Critical services failed: fastapi
[ERROR] Cannot continue. Please fix the issues above.
[INFO] Check startup log: logs/startup_20251102_130406.log
```

### Startup with Partial Failures

```bash
./start.sh

[INFO] Phase 1: Infrastructure Services
[SUCCESS] MongoDB available on port 27017 (Docker)
[SUCCESS] Redis started
[WARNING] Ollama not found. Install from: https://ollama.ai

[INFO] Phase 2: Application Services
[SUCCESS] FastAPI started on http://localhost:8000
[ERROR] Celery Worker failed to start. Check logs: tail -f logs/celery_worker.log
[INFO] Last 10 lines of log:
...celery import error...

[WARNING] ⚠ Startup completed with some failures
Failed services: celery_worker

Service URLs:
  - FastAPI:        http://localhost:8000
  - API Docs:       http://localhost:8000/docs
```

---

## 🔧 Quick Diagnostic Commands

The startup script now provides these at the end:

### Service Status
```bash
# Check health of all services
./scripts/startall/check_service_health.sh

# Check what's running
ps aux | grep -E 'fastapi|celery|flower|ollama'

# View PIDs
ls -lh pids/
```

### View Logs
```bash
# Interactive menu
./scripts/startall/attach_service.sh

# Specific service
./scripts/startall/attach_service.sh fastapi

# Open all in tabs
./scripts/startall/open_all_terminals.sh

# View startup log
tail -f logs/startup_*.log
```

### Debug Failures
```bash
# FastAPI import errors
cat logs/fastapi_import_test.log

# Celery import errors
cat logs/celery_import_test.log

# Recent errors across all services
tail -f logs/*.log | grep -i error

# Service-specific errors
tail -f logs/fastapi.log | grep ERROR
```

---

## 🛡️ Error Recovery Workflow

### If Critical Service Fails

```bash
# 1. Check startup log
tail logs/startup_$(ls -t logs/startup_* | head -1)

# 2. Check import errors (if Python service)
cat logs/fastapi_import_test.log
cat logs/celery_import_test.log

# 3. Fix dependencies
pip install -r requirements.txt

# 4. Test imports manually
python -c "from src.second_brain_database.main import app"

# 5. Retry startup
./start.sh
```

### If MongoDB Not Accessible

```bash
# Check if container exists
docker ps -a | grep mongo

# Start existing container
docker start mongodb

# Or create new container
docker run -d -p 27017:27017 --name mongodb mongo

# Retry startup
./start.sh
```

### If Non-Critical Service Fails

The system will still be partially functional. You can:

```bash
# 1. System runs with degraded functionality
# 2. Fix the issue while other services run
# 3. Restart only the failed service

# Example: Restart just Celery Worker
python scripts/manual/start_celery_worker.py &
```

---

## 🎓 Debug Mode

Enable verbose logging:

```bash
DEBUG=1 ./start.sh
```

Shows additional debug messages:
```
[DEBUG] Testing FastAPI imports...
[DEBUG] PID file not found: pids/celery_worker.pid
[DEBUG] Process 12345 not running for celery_worker
```

---

## 📝 Exit Codes

| Code | Meaning |
|------|---------|
| `0` | All services started successfully |
| `1` | Critical failure (MongoDB, Redis, or FastAPI) |

**Usage in scripts:**
```bash
if ./start.sh; then
    echo "System ready!"
else
    echo "Startup failed - check logs"
    exit 1
fi
```

---

## 🔍 Comparison: Before vs After

### Before (Old Script)
```bash
# Basic startup - crashes on first error
set -e
redis-server --daemonize yes
python start_fastapi_server.py &
# If FastAPI has import error -> silent background failure
# No validation, no import checks
```

### After (New Script)
```bash
# Production-ready startup
# 1. Test imports BEFORE starting
python -c "from src.second_brain_database.main import app"
# 2. Start service
python start_fastapi_server.py &
# 3. Wait for port to be ready
wait_for_port 8000 "FastAPI" 30
# 4. Show errors if failed
tail -10 logs/fastapi.log
```

---

## 🚀 Production Checklist

Before deploying:

- [x] Import validation for all Python services
- [x] Port health checks with timeouts
- [x] Process health validation
- [x] Graceful error handling (no `set -e`)
- [x] Detailed startup logging
- [x] Automatic error display
- [x] Two-phase startup (infra → apps)
- [x] MongoDB Docker integration
- [x] Optional services (LiveKit, Ollama)
- [x] Timestamp-based logs
- [x] Exit code handling
- [x] Debug mode support

---

## 📚 Related Documentation

- **Log Monitoring**: `LOG_MONITORING_GUIDE.md`
- **Quick Start**: `QUICKSTART.md`
- **Service Health**: `./scripts/startall/check_service_health.sh`
- **Startup Script**: `scripts/startall/start_all.sh`

---

**Summary**: The startup script is now **production-ready** with comprehensive error handling, import validation, health checks, and detailed logging. All failures are caught early and displayed clearly with actionable debugging steps.

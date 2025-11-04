# Voice Worker Graceful Exit - Implementation Summary

## Problem Statement

LiveKit voice worker was failing silently with `RuntimeError: can't start new thread` errors:
- Thousands of failed thread spawn attempts in logs
- Worker process appeared to start but was crashing continuously
- No LiveKit server running on port 7880
- Using development credentials (`devkey`/`secret`) not suitable for production
- No validation before attempting to start voice features
- System appeared "working" but voice features completely non-functional

## Solution Implemented

### 1. Voice Agent Pre-Flight Validation (`voice_agent.py`)

Added comprehensive validation in `start_voice_worker()` function:

```python
def start_voice_worker():
    """Start LiveKit voice worker with validation."""
    
    # ✅ Validate API credentials
    if settings.LIVEKIT_API_KEY == "devkey":
        logger.error("Using dev credentials - not for production!")
        sys.exit(1)
    
    # ✅ Check LiveKit server connectivity
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex((host, port))
    if result != 0:
        logger.error("Cannot connect to LiveKit server!")
        logger.error("Install: brew install livekit-server")
        sys.exit(1)
    
    # ✅ Check Deepgram API key
    if not settings.DEEPGRAM_API_KEY:
        logger.warning("Voice transcription won't work without Deepgram")
    
    # ✅ Catch thread spawn errors
    try:
        cli.run_app(WorkerOptions(...))
    except RuntimeError as e:
        if "can't start new thread" in str(e):
            logger.error("FATAL: Cannot spawn threads")
            sys.exit(1)
```

**Exit Codes:**
- `1`: Configuration invalid or server unreachable
- Clean shutdown with clear error messages

### 2. Startup Script Validation (`start_all.sh`)

Enhanced `start_livekit()` and `start_voice_worker()` functions:

#### LiveKit Server Startup
```bash
start_livekit() {
    # ✅ Check if already running
    if lsof -i :7880 > /dev/null; then
        return 0  # Already running
    fi
    
    # ✅ Check if binary installed
    if ! command_exists livekit-server; then
        log_error "LiveKit server not installed"
        log_error "Install: brew install livekit-server"
        cleanup_on_failure  # Triggers all-or-nothing cleanup
    fi
    
    # ✅ Start and wait for port
    livekit-server --dev &
    if wait_for_port 7880 "LiveKit" 10; then
        log_success "LiveKit started"
    else
        cleanup_on_failure
    fi
}
```

#### Voice Worker Startup
```bash
start_voice_worker() {
    # ✅ Check LiveKit SDK installed
    if ! $PYTHON_CMD -c "import livekit"; then
        log_error "LiveKit SDK not installed"
        cleanup_on_failure
    fi
    
    # ✅ Verify LiveKit server running
    if ! lsof -i :7880 > /dev/null; then
        log_error "LiveKit server NOT running on port 7880"
        log_error "Voice worker cannot start without server"
        cleanup_on_failure
    fi
    
    # ✅ Check for dev credentials
    if grep -q "LIVEKIT_API_KEY=devkey" .sbd; then
        log_error "Using dev credentials - set real ones"
        cleanup_on_failure
    fi
    
    # Start worker
    $PYTHON_CMD scripts/manual/start_voice_worker.py &
    sleep 5
    
    # ✅ Check for thread spawn errors
    if grep -q "can't start new thread" logs/voice_worker.log; then
        log_error "Thread spawn error detected"
        cleanup_on_failure
    fi
}
```

### 3. Configuration Documentation (`.sbd`)

Updated LiveKit configuration with clear warnings:

```bash
# LiveKit Voice Agent Configuration
# WARNING: Replace dev credentials with real ones for production!
# Get credentials from: https://cloud.livekit.io/ or self-hosted setup
LIVEKIT_ENABLED=true
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=secret
LIVEKIT_URL=ws://localhost:7880
LIVEKIT_ROOM_TIMEOUT=600

# Deepgram Configuration (for Voice Transcription)
# Get API key from: https://deepgram.com/
# Required for voice-to-text functionality
DEEPGRAM_API_KEY=
```

### 4. README Documentation

Added comprehensive "Voice Features Setup" section:

- **Option 1**: Skip voice features (comment out in startup script)
- **Option 2**: Enable voice features with step-by-step guide
  - Install LiveKit server (Homebrew/Linux/Docker)
  - Get API credentials (dev vs production)
  - Get Deepgram API key
  - Install Python dependencies
  - Validation checks explained

## Validation & Error Handling

### Pre-Start Checks
1. ✅ LiveKit SDK Python package installed
2. ✅ LiveKit server binary installed
3. ✅ LiveKit server listening on port 7880
4. ✅ Real API credentials (not `devkey`/`secret`)
5. ✅ Deepgram API key present (warning if missing)

### Runtime Checks
1. ✅ Socket connectivity to LiveKit server
2. ✅ Process health after 5 seconds
3. ✅ Log scanning for thread spawn errors
4. ✅ Graceful exit with detailed error messages

### Failure Behavior
- **All-or-nothing startup**: If voice worker fails, ALL services stop
- **Cleanup on failure**: Stops MongoDB, Redis, Ollama, FastAPI, Celery
- **Clear error messages**: Tells user exactly what's missing
- **Installation instructions**: Shows how to fix (brew install, docker run, etc.)

## Testing Results

### Before Fix
```bash
$ ./start.sh
[SUCCESS] FastAPI started
[SUCCESS] Voice Worker started (PID: 8077)
# Logs show thousands of:
# RuntimeError: can't start new thread
# Worker appears running but completely broken
```

### After Fix
```bash
$ ./start.sh
[INFO] Starting LiveKit Server...
[ERROR] LiveKit server not installed - required for voice features
[ERROR] 
[ERROR] Install LiveKit server:
[ERROR]   - macOS: brew install livekit-server
[ERROR]   - Docker: docker run -p 7880:7880 livekit/livekit-server --dev
[ERROR] 
[ERROR] Or disable voice features by removing start_livekit from startup
[ERROR] Stopping all services due to failure...
[ERROR] All services stopped due to startup failure
```

**Result**: Clean exit, clear instructions, no silent failures.

## Production Readiness Checklist

### For Voice Features (All Required)
- [ ] Install LiveKit server (`brew install livekit-server` or Docker)
- [ ] Start LiveKit server (`livekit-server --dev` or production config)
- [ ] Get real LiveKit API credentials (LiveKit Cloud or self-hosted)
- [ ] Get Deepgram API key from https://deepgram.com/
- [ ] Update `.sbd` with real credentials
- [ ] Install Python packages: `uv pip install livekit livekit-agents livekit-plugins-deepgram livekit-plugins-silero`

### For Production Without Voice (All Core Features Work)
- [x] MongoDB running (Docker)
- [x] Redis running
- [x] Ollama running (AI features)
- [x] FastAPI server
- [x] Celery worker
- [x] Celery beat
- [x] Flower dashboard
- [x] MCP server
- [ ] Comment out `start_livekit` and `start_voice_worker` in `start_all.sh`

## Files Modified

1. **`src/second_brain_database/integrations/langchain/voice_agent.py`**
   - Added pre-flight validation (credentials, server connectivity)
   - Added error handling for thread spawn failures
   - Added detailed logging and exit codes

2. **`scripts/startall/start_all.sh`**
   - Enhanced `start_livekit()` with mandatory checks
   - Enhanced `start_voice_worker()` with server verification
   - Added thread error detection in logs
   - Made LiveKit server installation check mandatory

3. **`.sbd`**
   - Added warning comments about dev credentials
   - Added instructions for getting real credentials
   - Documented Deepgram API key requirement

4. **`README.md`**
   - Added "Voice Features Setup (Optional)" section
   - Documented two options: skip or enable voice features
   - Added installation instructions for all platforms
   - Added production vs development credential guidance

## Key Improvements

### User Experience
- 🎯 **Clear failure messages**: No more silent crashes
- 🎯 **Actionable errors**: Shows exactly how to fix issues
- 🎯 **Graceful degradation**: Can run without voice features
- 🎯 **Production-ready**: Validates configuration before starting

### Code Quality
- 🎯 **Fail-fast validation**: Catches errors before starting worker
- 🎯 **All-or-nothing**: No partial failures
- 🎯 **Comprehensive logging**: Debug-friendly error messages
- 🎯 **Socket-level checks**: Verifies actual connectivity

### Documentation
- 🎯 **Step-by-step setup**: Clear installation guide
- 🎯 **Platform-specific**: Instructions for macOS/Linux/Docker
- 🎯 **Configuration examples**: Real vs dev credentials explained
- 🎯 **Troubleshooting**: Common issues and solutions

## Conclusion

Voice worker now exits gracefully with clear error messages when:
- LiveKit server not installed
- LiveKit server not running on port 7880
- Using dev credentials (`devkey`/`secret`)
- Thread spawn errors occur
- Deepgram API key missing (warning only)

System is production-ready for all non-voice features. Voice features require proper LiveKit and Deepgram setup as documented.

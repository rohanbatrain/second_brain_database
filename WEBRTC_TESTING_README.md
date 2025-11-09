# WebRTC Testing Suite

This directory contains comprehensive tests for the WebRTC signaling server implementation. These tests verify that WebRTC functionality works correctly with JWT token authentication using two separate user tokens.

## 🎯 Purpose

The WebRTC implementation uses:
- **FastAPI WebSocket** endpoints for signaling
- **JWT token authentication** via query parameters  
- **Redis Pub/Sub** for multi-instance message broadcasting
- **Room-based participant management**

These tests ensure all components work together correctly.

## 📁 Test Files

### Core Test Files

| File | Purpose | Complexity |
|------|---------|------------|
| `test_webrtc_manual.py` | Basic endpoint verification | ⭐ Simple |
| `test_webrtc_simple.py` | Two-token authentication test | ⭐⭐ Medium |
| `test_webrtc_complete.py` | Full signaling flow test | ⭐⭐⭐ Complex |

### Runner Scripts

| File | Purpose |
|------|---------|
| `run_webrtc_tests.sh` | Automated test runner with server management |
| `run_webrtc_test.sh` | Legacy manual test setup (browser-based) |

## 🚀 Quick Start

### Option 1: Automated Test Runner (Recommended)

```bash
# Run all tests with automatic server management
./run_webrtc_tests.sh
```

The script will:
1. Start required services (MongoDB, Redis)
2. Launch the FastAPI server
3. Run your choice of tests
4. Clean up automatically

### Option 2: Manual Test Execution

```bash
# 1. Start the server manually
python src/second_brain_database/main.py

# 2. Run tests in another terminal
python test_webrtc_manual.py      # Basic verification
python test_webrtc_simple.py      # Two-token test  
python test_webrtc_complete.py    # Full test suite
```

## 📋 Test Descriptions

### 1. Manual Test (`test_webrtc_manual.py`)

**What it tests:**
- Server health endpoint
- WebRTC config endpoint authentication
- JWT token generation and validation
- Basic endpoint accessibility

**Use when:** Verifying basic setup and connectivity

### 2. Simple Two-Token Test (`test_webrtc_simple.py`)

**What it tests:**
- Creates 2 test users with different credentials
- Obtains JWT tokens for both users
- Tests WebSocket connections with token authentication
- Verifies concurrent room connections
- Basic message exchange

**Use when:** Specifically testing the two-token authentication concern

### 3. Complete Test Suite (`test_webrtc_complete.py`)

**What it tests:**
- Full user lifecycle (registration, login, verification)
- WebRTC configuration retrieval
- WebSocket connection establishment
- Room state management
- Participant tracking
- Full WebRTC signaling flow (offer/answer/ICE candidates)
- Message broadcasting between clients
- Disconnect handling and cleanup

**Use when:** Comprehensive verification of entire WebRTC system

## 🔧 Test Configuration

Tests use these default settings:

```python
# Server Configuration
BASE_URL = "http://localhost:8000"
WS_BASE_URL = "ws://localhost:8000"

# Test Data
ROOM_ID = "webrtc-test-room"
TEST_USERS = [
    {
        "username": "webrtc_test_user1",
        "email": "test1@example.com", 
        "password": "TestPass123!"
    },
    {
        "username": "webrtc_test_user2",
        "email": "test2@example.com",
        "password": "TestPass456!"
    }
]
```

## 📊 Test Results

### Success Indicators

✅ **All tests pass** = WebRTC system is working correctly
- JWT authentication works with WebSocket connections
- Two different tokens can connect simultaneously
- WebRTC signaling messages are properly routed
- Room management functions correctly

### Common Failure Scenarios

❌ **Authentication failures:**
- Check JWT secret configuration
- Verify token validation logic
- Ensure WebSocket auth middleware is working

❌ **Connection failures:**
- Verify MongoDB and Redis are running
- Check server is listening on correct port
- Ensure no firewall blocking connections

❌ **Signaling failures:**
- Check Redis Pub/Sub configuration
- Verify WebSocket message routing
- Ensure room management is working

## 🛠️ Debugging

### Enable Debug Logging

```bash
export LOG_LEVEL=DEBUG
python src/second_brain_database/main.py
```

### Check Service Status

```bash
# MongoDB
brew services list | grep mongo

# Redis  
brew services list | grep redis

# Server health
curl http://localhost:8000/health
```

### Manual WebSocket Testing

Use browser developer tools or `wscat`:

```bash
# Install wscat
npm install -g wscat

# Test connection (replace TOKEN with actual JWT)
wscat -c "ws://localhost:8000/webrtc/ws/test-room?token=TOKEN"
```

## 🔍 Understanding WebRTC Flow

### Authentication Flow

1. **User Registration/Login** → Get JWT token
2. **WebSocket Connection** → Token passed as query parameter  
3. **Token Validation** → Server validates JWT and extracts user info
4. **Room Join** → User added to room participants in Redis

### Signaling Flow

1. **Client A** connects → Gets room state, sees Client B
2. **Client B** connects → Gets room state, sees Client A  
3. **Client A** sends offer → Published to Redis → Forwarded to Client B
4. **Client B** sends answer → Published to Redis → Forwarded to Client A
5. **Both clients** exchange ICE candidates via same mechanism

### Message Types

- `room-state`: Initial room information and participants
- `user-joined`: New participant notification  
- `user-left`: Participant disconnect notification
- `offer`: WebRTC connection offer
- `answer`: WebRTC connection answer
- `ice-candidate`: ICE candidate for connection establishment

## 📚 Related Files

### Core WebRTC Implementation

- `src/second_brain_database/webrtc/router.py` - FastAPI routes
- `src/second_brain_database/webrtc/connection_manager.py` - Redis-based manager
- `src/second_brain_database/webrtc/dependencies.py` - Authentication
- `src/second_brain_database/webrtc/schemas.py` - Message schemas

### Configuration

- `.sbd` - Environment configuration file
- `src/second_brain_database/config.py` - Settings management

## 🎯 Expected Outcomes

After running the tests, you should know:

1. **Does JWT authentication work with WebSocket connections?**
2. **Can two different users connect simultaneously?**  
3. **Are WebRTC signaling messages properly routed between clients?**
4. **Is room state management working correctly?**
5. **Do disconnections clean up properly?**

If all tests pass, your WebRTC implementation is ready for production use! 🚀
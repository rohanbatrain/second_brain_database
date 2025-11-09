# WebRTC Signaling Server - Production Implementation

## Overview

This document describes the production-ready WebRTC signaling server implementation using FastAPI, Redis Pub/Sub, and WebSockets. The system is designed for horizontal scaling with stateless signaling servers and centralized room management via Redis.

## Architecture

### Components

1. **WebSocket Signaling Endpoint** (`/webrtc/ws/{room_id}`)
   - Handles bidirectional WebRTC signaling messages
   - Authenticates clients using JWT tokens
   - Publishes messages to Redis Pub/Sub channels
   - Subscribes to room-specific Redis channels
   - Manages participant lifecycle (join/leave events)

2. **REST Configuration Endpoint** (`/webrtc/config`)
   - Provides STUN/TURN server configuration
   - Returns ICE transport policies
   - Requires JWT authentication

3. **Redis Pub/Sub Manager** (`WebRtcManager`)
   - Stateless room management
   - Message distribution across server instances
   - Participant tracking with presence heartbeat
   - Automatic cleanup on disconnect

4. **Message Schemas** (Pydantic Models)
   - Type-safe message validation
   - Factory methods for common message types
   - Support for all WebRTC signaling message types

## Key Features

### ✅ Horizontal Scaling
- **Stateless Design**: No server-side session state
- **Redis Pub/Sub**: Messages distributed to all server instances
- **Shared Room State**: Participant lists stored in Redis
- **Load Balancer Compatible**: Any client can connect to any server instance

### ✅ Production-Ready Security
- **JWT Authentication**: Required for WebSocket connections
- **Token in Query Params**: `?token=<jwt_token>`
- **Room Validation**: Sanitized room identifiers
- **WebSocket Error Codes**: Proper 1008/1011 error handling

### ✅ Reliability
- **Heartbeat Mechanism**: 30-second presence TTL
- **Automatic Cleanup**: Removes disconnected participants
- **Error Handling**: Comprehensive error messages
- **Graceful Shutdown**: Proper cleanup on disconnect

### ✅ Observability
- **Structured Logging**: All events logged with context
- **Performance Tracking**: Message routing latency
- **Debug Info**: Room state, participant counts
- **Error Tracking**: Failed operations with stack traces

## Message Types

The system supports the following WebRTC signaling message types:

1. **OFFER**: WebRTC session description (SDP offer)
2. **ANSWER**: WebRTC session description (SDP answer)
3. **ICE_CANDIDATE**: ICE candidate for NAT traversal
4. **USER_JOINED**: Notification when user joins room
5. **USER_LEFT**: Notification when user leaves room
6. **ROOM_STATE**: Current room participants list
7. **ERROR**: Error messages from server

## Usage Guide

### 1. Get WebRTC Configuration

Before establishing WebRTC connections, fetch the ICE server configuration:

```python
import httpx

async def get_webrtc_config(token: str) -> dict:
    """Get WebRTC configuration from server."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "http://localhost:8000/webrtc/config",
            headers={"Authorization": f"Bearer {token}"}
        )
        return response.json()

# Example response:
# {
#     "ice_servers": [
#         {"urls": ["stun:stun.l.google.com:19302"]},
#         {
#             "urls": ["turn:turn.example.com:3478"],
#             "username": "user",
#             "credential": "pass"
#         }
#     ],
#     "ice_transport_policy": "all",
#     "bundle_policy": "balanced",
#     "rtcp_mux_policy": "require"
# }
```

### 2. Connect to Signaling Server

```python
import asyncio
import json
import websockets

async def connect_to_signaling(token: str, room_id: str):
    """Connect to WebRTC signaling server."""
    ws_url = f"ws://localhost:8000/webrtc/ws/{room_id}?token={token}"
    
    async with websockets.connect(ws_url) as websocket:
        # Receive room state on connection
        message = await websocket.receive()
        room_state = json.loads(message)
        print(f"Room state: {room_state}")
        
        # Send WebRTC offer
        offer_message = {
            "type": "offer",
            "payload": {
                "type": "offer",
                "sdp": "v=0\r\n..."  # Your SDP offer
            },
            "room_id": room_id,
            "timestamp": "2024-01-01T00:00:00Z"
        }
        await websocket.send(json.dumps(offer_message))
        
        # Receive messages
        async for message in websocket:
            data = json.loads(message)
            print(f"Received: {data['type']}")
```

### 3. Message Format

All messages follow this structure:

```json
{
  "type": "offer|answer|ice_candidate|user_joined|user_left|room_state|error",
  "payload": { /* type-specific payload */ },
  "sender_id": "user_id_123",  // Optional, set by server
  "room_id": "room-123",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

#### Offer Message
```json
{
  "type": "offer",
  "payload": {
    "type": "offer",
    "sdp": "v=0\r\no=- 123... ",
    "target_user_id": "optional_target_user"
  }
}
```

#### Answer Message
```json
{
  "type": "answer",
  "payload": {
    "type": "answer",
    "sdp": "v=0\r\no=- 456...",
    "target_user_id": "user_who_sent_offer"
  }
}
```

#### ICE Candidate Message
```json
{
  "type": "ice_candidate",
  "payload": {
    "candidate": "candidate:1 1 UDP...",
    "sdp_mid": "0",
    "sdp_m_line_index": 0,
    "target_user_id": "optional_target_user"
  }
}
```

#### User Joined Event
```json
{
  "type": "user_joined",
  "payload": {
    "user_id": "user_123",
    "username": "Alice"
  },
  "sender_id": "server"
}
```

#### Room State Message
```json
{
  "type": "room_state",
  "payload": {
    "room_id": "room-123",
    "participants": [
      {"user_id": "user_1", "username": "Alice"},
      {"user_id": "user_2", "username": "Bob"}
    ],
    "participant_count": 2
  }
}
```

## Configuration

### Environment Variables

Add these to your `.sbd` or environment:

```bash
# STUN servers (comma-separated)
WEBRTC_STUN_URLS=stun:stun.l.google.com:19302,stun:stun1.l.google.com:19302

# TURN servers (optional)
WEBRTC_TURN_URLS=turn:turn.example.com:3478
WEBRTC_TURN_USERNAME=your_username
WEBRTC_TURN_CREDENTIAL=your_password

# WebRTC policies
WEBRTC_ICE_TRANSPORT_POLICY=all  # or "relay" to force TURN
WEBRTC_BUNDLE_POLICY=balanced
WEBRTC_RTCP_MUX_POLICY=require

# Room configuration
WEBRTC_ROOM_PRESENCE_TTL=30  # Heartbeat timeout in seconds
WEBRTC_MAX_PARTICIPANTS_PER_ROOM=50
```

### Default Configuration

If no STUN/TURN servers are configured, the system falls back to Google's public STUN servers:
- `stun:stun.l.google.com:19302`
- `stun:stun1.l.google.com:19302`

## API Endpoints

### WebSocket Endpoint

**Endpoint**: `ws://your-domain/webrtc/ws/{room_id}`

**Authentication**: JWT token in query parameter

```
ws://localhost:8000/webrtc/ws/my-room?token=eyJhbGc...
```

**Parameters**:
- `room_id` (path): Unique room identifier

**Query Parameters**:
- `token` (required): JWT authentication token

### REST Endpoints

#### Get WebRTC Configuration

```http
GET /webrtc/config
Authorization: Bearer <jwt_token>
```

**Response**:
```json
{
  "ice_servers": [...],
  "ice_transport_policy": "all",
  "bundle_policy": "balanced",
  "rtcp_mux_policy": "require"
}
```

#### Get Room Participants

```http
GET /webrtc/rooms/{room_id}/participants
Authorization: Bearer <jwt_token>
```

**Response**:
```json
{
  "room_id": "room-123",
  "participants": [
    {"user_id": "user_1", "username": "Alice"},
    {"user_id": "user_2", "username": "Bob"}
  ],
  "participant_count": 2
}
```

## Testing

### Using the Test Client

```bash
# Update token and room_id in the script
python tests/test_webrtc_client.py
```

### Manual Testing with JavaScript

```javascript
// Get WebRTC config
const response = await fetch('http://localhost:8000/webrtc/config', {
  headers: { 'Authorization': `Bearer ${token}` }
});
const config = await response.json();

// Create peer connection
const pc = new RTCPeerConnection(config);

// Connect to signaling server
const ws = new WebSocket(`ws://localhost:8000/webrtc/ws/my-room?token=${token}`);

ws.onmessage = async (event) => {
  const message = JSON.parse(event.data);
  
  switch (message.type) {
    case 'room_state':
      console.log('Room participants:', message.payload.participants);
      break;
      
    case 'offer':
      await pc.setRemoteDescription(message.payload);
      const answer = await pc.createAnswer();
      await pc.setLocalDescription(answer);
      ws.send(JSON.stringify({
        type: 'answer',
        payload: answer,
        room_id: 'my-room'
      }));
      break;
      
    case 'ice_candidate':
      await pc.addIceCandidate(message.payload);
      break;
  }
};

pc.onicecandidate = (event) => {
  if (event.candidate) {
    ws.send(JSON.stringify({
      type: 'ice_candidate',
      payload: event.candidate,
      room_id: 'my-room'
    }));
  }
};
```

## Deployment

### Single Instance

```bash
uvicorn src.second_brain_database.main:app --host 0.0.0.0 --port 8000
```

### Multiple Instances (Horizontal Scaling)

1. **Setup Redis** (shared across all instances):
   ```bash
   redis-server --port 6379
   ```

2. **Start multiple app instances**:
   ```bash
   # Instance 1
   uvicorn src.second_brain_database.main:app --port 8000
   
   # Instance 2
   uvicorn src.second_brain_database.main:app --port 8001
   
   # Instance 3
   uvicorn src.second_brain_database.main:app --port 8002
   ```

3. **Setup load balancer** (nginx example):
   ```nginx
   upstream webrtc_backend {
       ip_hash;  # Sticky sessions for WebSocket
       server localhost:8000;
       server localhost:8001;
       server localhost:8002;
   }
   
   server {
       location /webrtc/ws/ {
           proxy_pass http://webrtc_backend;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection "upgrade";
       }
   }
   ```

### Docker Deployment

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . .
RUN pip install -e .

CMD ["uvicorn", "src.second_brain_database.main:app", "--host", "0.0.0.0"]
```

```yaml
# docker-compose.yml
version: '3.8'
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
  
  app:
    build: .
    ports:
      - "8000-8002:8000"
    environment:
      - REDIS_HOST=redis
    depends_on:
      - redis
    deploy:
      replicas: 3
```

## Monitoring

### Logging

All WebRTC events are logged with structured context:

```python
# Connection events
logger.info("WebSocket connected", extra={
    "room_id": "room-123",
    "user_id": "user_456"
})

# Message routing
logger.debug("Forwarded offer", extra={
    "room_id": "room-123",
    "sender_id": "user_456",
    "message_type": "offer"
})

# Errors
logger.error("Failed to publish message", extra={
    "room_id": "room-123",
    "error": str(e)
}, exc_info=True)
```

### Metrics

Monitor these key metrics:
- Active WebSocket connections per room
- Message throughput (messages/second)
- Redis Pub/Sub latency
- Participant join/leave rate
- Error rate by type

## Troubleshooting

### Common Issues

1. **Connection Fails with 1008 Error**
   - **Cause**: Invalid or expired JWT token
   - **Solution**: Ensure token is valid and not expired

2. **Messages Not Received by Other Clients**
   - **Cause**: Redis Pub/Sub not working
   - **Solution**: Check Redis connection, ensure all instances use same Redis

3. **User Shows as "Left" Immediately**
   - **Cause**: Heartbeat timeout too short
   - **Solution**: Increase `WEBRTC_ROOM_PRESENCE_TTL`

4. **High Memory Usage**
   - **Cause**: Too many Redis keys not expiring
   - **Solution**: Check presence TTL is set correctly

### Debug Mode

Enable debug logging:

```bash
DEBUG=true uvicorn src.second_brain_database.main:app
```

Check logs for detailed message flow:
```
[WebRTC-Router] Received offer from user_123 in room-456
[WebRTC-Manager] Publishing to room room-456
[WebRTC-Router] Forwarded offer to user_789 in room-456
```

## Security Best Practices

1. **Always Use HTTPS/WSS in Production**
   ```nginx
   server {
       listen 443 ssl;
       ssl_certificate /path/to/cert.pem;
       ssl_certificate_key /path/to/key.pem;
   }
   ```

2. **Validate Room IDs**
   - The system automatically sanitizes room IDs
   - Only alphanumeric and hyphens allowed

3. **Rate Limiting**
   - Implement rate limiting on WebSocket messages
   - Prevent message flooding attacks

4. **TURN Server Authentication**
   - Use time-limited TURN credentials
   - Rotate credentials regularly

5. **Monitor for Abuse**
   - Track excessive room creation
   - Limit participants per room
   - Monitor message sizes

## Performance Optimization

1. **Redis Connection Pool**
   - Already configured in `redis_manager`
   - Tune pool size based on load

2. **Message Batching**
   - Consider batching ICE candidates
   - Reduce Redis Pub/Sub overhead

3. **Compression**
   - Enable WebSocket per-message compression
   - Reduces bandwidth for large SDP messages

4. **TTL Tuning**
   - Balance between responsiveness and Redis load
   - Current default: 30 seconds

## Future Enhancements

- [ ] SFU (Selective Forwarding Unit) for multi-party calls
- [ ] Recording support for calls
- [ ] Screen sharing signaling
- [ ] Quality metrics collection
- [ ] Automatic TURN credential generation
- [ ] Room persistence and chat history
- [ ] Admin API for room management

## References

- [WebRTC Specification](https://www.w3.org/TR/webrtc/)
- [MDN WebRTC Guide](https://developer.mozilla.org/en-US/docs/Web/API/WebRTC_API)
- [Redis Pub/Sub](https://redis.io/docs/manual/pubsub/)
- [FastAPI WebSockets](https://fastapi.tiangolo.com/advanced/websockets/)

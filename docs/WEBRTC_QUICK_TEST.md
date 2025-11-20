# WebRTC Quick Test Guide

## 🚀 Test in 60 Seconds

### Method 1: HTML Test Client (Easiest)

1. **Start the backend server:**
   ```bash
   cd /Users/rohan/Documents/repos/second_brain_database
   uvicorn src.second_brain_database.main:app --reload
   ```

2. **Get a JWT token:**
   ```bash
   # Login and get token
   curl -X POST http://localhost:8000/auth/login \
     -H "Content-Type: application/json" \
     -d '{"email":"your@email.com","password":"yourpassword"}'
   
   # Or use the rag_user token (if you have it)
   cat rag_token.txt
   ```

3. **Open the test client:**
   ```bash
   # Open in browser
   open tests/webrtc_test_client.html
   ```

4. **Test:**
   - Paste your JWT token
   - Click "Connect to Room"
   - Allow camera/microphone access
   - Click "Call" to create offer

5. **Test with 2nd device/tab:**
   - Open same HTML file in another tab/window
   - Use same token and room ID
   - One client will auto-answer when the other calls

### Method 2: Python Test Script

1. **Start server** (same as above)

2. **Run test script:**
   ```bash
   # Get token first
   export JWT_TOKEN="your_jwt_token_here"
   
   # Run multi-client test
   python tests/test_webrtc_client.py
   ```

3. **Update token in script:**
   ```python
   # Edit tests/test_webrtc_client.py
   TOKEN = "your_jwt_token_here"  # Line 285
   ```

### Method 3: Browser Console (Super Quick)

1. **Start server**

2. **Open browser console** (F12)

3. **Get WebRTC config:**
   ```javascript
   // Replace YOUR_TOKEN with your JWT token
   fetch('http://localhost:8000/webrtc/config', {
       headers: { 'Authorization': 'Bearer YOUR_TOKEN' }
   })
   .then(r => r.json())
   .then(config => console.log('Config:', config));
   ```

4. **Connect to room:**
   ```javascript
   const ws = new WebSocket('ws://localhost:8000/webrtc/ws/test-room?token=YOUR_TOKEN');
   
   ws.onmessage = (e) => console.log('Message:', JSON.parse(e.data));
   ws.onopen = () => console.log('Connected!');
   ws.onerror = (e) => console.log('Error:', e);
   ```

## 🧪 Quick Tests to Run

### Test 1: Connection Test
**Goal:** Verify WebSocket connection works

```bash
# Terminal 1: Start server
uvicorn src.second_brain_database.main:app --reload

# Terminal 2: Check if endpoint exists
curl http://localhost:8000/webrtc/config \
  -H "Authorization: Bearer YOUR_TOKEN"

# Should return:
# {
#   "ice_servers": [...],
#   "ice_transport_policy": "all",
#   ...
# }
```

### Test 2: Room Join Test
**Goal:** Verify users can join rooms

1. Open `tests/webrtc_test_client.html` in 2 browser tabs
2. Enter same room ID in both
3. Connect both
4. Check logs for "User joined" messages

### Test 3: Signaling Test
**Goal:** Verify offer/answer exchange works

1. Connect 2 clients to same room
2. Click "Call" in first client
3. Second client should auto-answer
4. Check logs for:
   - "Creating offer"
   - "Received offer"
   - "Creating answer"
   - "Connection state: connected"

### Test 4: Media Stream Test
**Goal:** Verify video/audio works

1. Complete signaling (Test 3)
2. Check if:
   - Local video shows your camera
   - Remote video shows other client's camera
   - Audio is working (speak and listen)

### Test 5: Multi-Instance Test (Production)
**Goal:** Verify Redis Pub/Sub works across server instances

```bash
# Terminal 1: Server instance 1
uvicorn src.second_brain_database.main:app --port 8000

# Terminal 2: Server instance 2
uvicorn src.second_brain_database.main:app --port 8001

# Terminal 3: Check Redis is running
redis-cli ping  # Should return PONG

# Browser 1: Connect to instance 1
# URL: http://localhost:8000
# Open webrtc_test_client.html, connect to room "test"

# Browser 2: Connect to instance 2
# URL: http://localhost:8001
# Open webrtc_test_client.html, connect to same room "test"

# Both should see each other's messages through Redis!
```

## 🔍 Troubleshooting

### Issue: "Failed to get config: 401"
**Solution:** Token is invalid or expired
```bash
# Get new token
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password"}'
```

### Issue: "WebSocket error: 1008"
**Solution:** Authentication failed
- Check token is correct
- Token should not have "Bearer " prefix in URL
- Format: `ws://localhost:8000/webrtc/ws/room?token=eyJ...`

### Issue: "No remote video"
**Solution:** Check firewall/NAT
```bash
# Test STUN server
# Open browser console
const pc = new RTCPeerConnection({
  iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
});
pc.createDataChannel('test');
pc.createOffer().then(offer => pc.setLocalDescription(offer));
pc.onicecandidate = e => e.candidate && console.log('Candidate:', e.candidate);
```

### Issue: "Camera permission denied"
**Solution:** Grant camera/mic permissions
- Chrome: Settings → Privacy → Site Settings → Camera/Microphone
- Firefox: about:permissions
- Safari: Preferences → Websites → Camera/Microphone

### Issue: Redis connection error
**Solution:** Start Redis
```bash
# macOS
brew services start redis

# Or manually
redis-server

# Verify
redis-cli ping
```

## 📊 What to Look For

### ✅ Success Indicators

1. **WebSocket Connected:**
   ```
   [INFO] WebSocket connected
   [SUCCESS] Room has 1 participant(s)
   ```

2. **Offer/Answer Exchange:**
   ```
   [INFO] Creating offer...
   [SUCCESS] Offer created
   [INFO] Received offer
   [INFO] Creating answer...
   [SUCCESS] Answer created
   ```

3. **ICE Connection:**
   ```
   [INFO] New ICE candidate
   [INFO] ICE connection state: checking
   [INFO] ICE connection state: connected
   [SUCCESS] Connection state: connected
   ```

4. **Media Flowing:**
   - Local video shows your camera
   - Remote video shows other peer's camera
   - Audio is audible

### ❌ Failure Indicators

1. **No remote video after 10 seconds:**
   - ICE connection failed
   - Try using TURN server
   - Check firewall rules

2. **WebSocket closes immediately:**
   - Token invalid
   - Server not running
   - Wrong URL

3. **"Room has 0 participants":**
   - You're the only one in the room
   - Wait for another peer to join

## 🎯 Quick Verification Checklist

```bash
# 1. Backend running?
curl http://localhost:8000/health
# Should return: {"status": "healthy"}

# 2. WebRTC endpoint exists?
curl http://localhost:8000/webrtc/config \
  -H "Authorization: Bearer TOKEN" | jq
# Should return ICE servers config

# 3. WebSocket endpoint accessible?
wscat -c "ws://localhost:8000/webrtc/ws/test?token=TOKEN"
# Should connect (install wscat: npm install -g wscat)

# 4. Redis working?
redis-cli ping
# Should return: PONG

# 5. Multiple instances sync?
redis-cli SUBSCRIBE "webrtc:room:test"
# Open another terminal and send message to room
# You should see it in redis-cli
```

## 🚦 Testing Scenarios

### Scenario 1: Two Users in Same Room
1. User A connects to "room-123"
2. User B connects to "room-123"
3. User A clicks "Call"
4. User B auto-answers
5. Both see each other's video

### Scenario 2: User Joins After Call Started
1. User A and B already in call
2. User C joins room
3. User C should see User A or B (depending on who calls)
4. Multiple peer connections needed for group calls (future enhancement)

### Scenario 3: Network Change During Call
1. Start call between 2 users
2. Switch WiFi network
3. ICE should renegotiate
4. Call should reconnect automatically

### Scenario 4: Mute/Unmute
1. Start call
2. Click "Mute" button
3. Other peer should not hear audio
4. Click "Unmute"
5. Audio should resume

## 📈 Performance Monitoring

### Check Connection Stats
Open browser console during call:

```javascript
// Get peer connection stats
setInterval(async () => {
    if (pc) {
        const stats = await pc.getStats();
        stats.forEach(report => {
            if (report.type === 'inbound-rtp' && report.kind === 'video') {
                console.log('Video Stats:', {
                    packetsReceived: report.packetsReceived,
                    packetsLost: report.packetsLost,
                    bytesReceived: report.bytesReceived,
                    jitter: report.jitter
                });
            }
        });
    }
}, 2000);
```

## 🎬 Video Tutorial (Steps)

1. **Start Backend:**
   ```bash
   uvicorn src.second_brain_database.main:app --reload
   ```

2. **Get Token:**
   - Login via API or use existing token
   - Copy the JWT token

3. **Open Test Client:**
   ```bash
   open tests/webrtc_test_client.html
   ```

4. **Configure:**
   - Server URL: `http://localhost:8000`
   - Token: Paste JWT
   - Room: `my-test-room`

5. **Connect:**
   - Click "Connect to Room"
   - Allow camera/microphone
   - See local video

6. **Test (2nd Tab):**
   - Open same HTML in new tab
   - Same configuration
   - Click "Connect"
   - One tab clicks "Call"
   - Other tab auto-answers
   - See each other's video!

## 🎉 Success!

If you can see and hear each other, your WebRTC implementation is working!

Next steps:
- Test on mobile devices
- Test across networks (not just localhost)
- Test with TURN server for NAT traversal
- Test with multiple participants
- Integrate into your Flutter app

## 📚 References

- Test Client: `tests/webrtc_test_client.html`
- Python Test: `tests/test_webrtc_client.py`
- Validation: `scripts/validate_webrtc.py`
- Documentation: `docs/WEBRTC_IMPLEMENTATION.md`
- Flutter Guide: `docs/WEBRTC_FLUTTER_INTEGRATION.md`

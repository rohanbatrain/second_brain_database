# WebRTC Signaling - Frontend Integration Guide

## Overview

The WebRTC Signaling feature enables real-time peer-to-peer communication through WebSocket-based signaling. This guide provides complete integration examples for establishing WebRTC connections in web and mobile applications.

## Feature Capabilities

- ✅ **WebSocket Signaling**: Real-time message exchange via WebSockets
- ✅ **ICE Server Configuration**: STUN/TURN server provisioning
- ✅ **Room Management**: Multi-participant room support
- ✅ **Horizontal Scaling**: Redis Pub/Sub for distributed signaling
- ✅ **Reconnection Support**: Automatic reconnection with state recovery
- ✅ **Rate Limiting**: Built-in protection against abuse

## API Endpoints

### 1. Get WebRTC Configuration
```http
GET /webrtc/config
Authorization: Bearer {jwt_token}
```

**Response:**
```json
{
  "ice_servers": [
    {
      "urls": ["stun:stun.l.google.com:19302"]
    },
    {
      "urls": ["turn:turn.example.com:3478"],
      "username": "user",
      "credential": "pass"
    }
  ],
  "ice_transport_policy": "all",
  "bundle_policy": "balanced",
  "rtcp_mux_policy": "require"
}
```

### 2. WebSocket Signaling
```
ws://your-server.com/webrtc/ws/{room_id}?token={jwt_token}
```

**Message Format:**
```json
{
  "type": "offer|answer|ice_candidate|user_joined|user_left|room_state",
  "payload": { /* type-specific data */ },
  "sender_id": "user_123",
  "room_id": "room-abc",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## Frontend Integration Examples

### React/TypeScript Web Application

#### 1. WebRTC Service Class

```typescript
// src/services/webrtc.ts
export enum MessageType {
  OFFER = 'offer',
  ANSWER = 'answer',
  ICE_CANDIDATE = 'ice_candidate',
  USER_JOINED = 'user_joined',
  USER_LEFT = 'user_left',
  ROOM_STATE = 'room_state',
  ERROR = 'error',
}

export interface WebRTCMessage {
  type: MessageType;
  payload: any;
  sender_id?: string;
  room_id: string;
  timestamp: string;
}

export interface ICEServerConfig {
  urls: string | string[];
  username?: string;
  credential?: string;
}

export interface WebRTCConfig {
  ice_servers: ICEServerConfig[];
  ice_transport_policy: string;
  bundle_policy: string;
  rtcp_mux_policy: string;
}

export interface Participant {
  user_id: string;
  username: string;
}

class WebRTCService {
  private ws: WebSocket | null = null;
  private peerConnection: RTCPeerConnection | null = null;
  private localStream: MediaStream | null = null;
  private remoteStream: MediaStream | null = null;
  private token: string;
  private serverUrl: string;
  private roomId: string;
  
  // Callbacks
  public onLocalStream?: (stream: MediaStream) => void;
  public onRemoteStream?: (stream: MediaStream) => void;
  public onParticipantJoined?: (participant: Participant) => void;
  public onParticipantLeft?: (participant: Participant) => void;
  public onRoomState?: (participants: Participant[]) => void;
  public onError?: (error: string) => void;
  public onConnectionStateChange?: (state: RTCPeerConnectionState) => void;

  constructor(serverUrl: string, token: string, roomId: string) {
    this.serverUrl = serverUrl;
    this.token = token;
    this.roomId = roomId;
  }

  /**
   * Get ICE server configuration from backend
   */
  async getWebRTCConfig(): Promise<WebRTCConfig> {
    const response = await fetch(`${this.serverUrl}/webrtc/config`, {
      headers: {
        'Authorization': `Bearer ${this.token}`,
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to get WebRTC config: ${response.statusText}`);
    }

    return await response.json();
  }

  /**
   * Initialize local media stream
   */
  async initLocalStream(
    constraints: MediaStreamConstraints = { video: true, audio: true }
  ): Promise<MediaStream> {
    try {
      this.localStream = await navigator.mediaDevices.getUserMedia(constraints);
      
      if (this.onLocalStream) {
        this.onLocalStream(this.localStream);
      }

      return this.localStream;
    } catch (error) {
      throw new Error(`Failed to get local stream: ${error}`);
    }
  }

  /**
   * Create RTCPeerConnection with ICE servers
   */
  async createPeerConnection(): Promise<RTCPeerConnection> {
    // Get ICE server configuration
    const config = await this.getWebRTCConfig();

    // Create peer connection
    this.peerConnection = new RTCPeerConnection(config);

    // Add local stream tracks
    if (this.localStream) {
      this.localStream.getTracks().forEach(track => {
        this.peerConnection!.addTrack(track, this.localStream!);
      });
    }

    // Handle ICE candidates
    this.peerConnection.onicecandidate = (event) => {
      if (event.candidate) {
        this.sendMessage({
          type: MessageType.ICE_CANDIDATE,
          payload: {
            candidate: event.candidate.candidate,
            sdp_mid: event.candidate.sdpMid,
            sdp_m_line_index: event.candidate.sdpMLineIndex,
          },
          room_id: this.roomId,
          timestamp: new Date().toISOString(),
        });
      }
    };

    // Handle remote stream
    this.peerConnection.ontrack = (event) => {
      if (event.streams && event.streams[0]) {
        this.remoteStream = event.streams[0];
        
        if (this.onRemoteStream) {
          this.onRemoteStream(this.remoteStream);
        }
      }
    };

    // Handle connection state changes
    this.peerConnection.onconnectionstatechange = () => {
      const state = this.peerConnection!.connectionState;
      console.log('Connection state:', state);
      
      if (this.onConnectionStateChange) {
        this.onConnectionStateChange(state);
      }
    };

    return this.peerConnection;
  }

  /**
   * Connect to signaling server WebSocket
   */
  async connectToRoom(): Promise<void> {
    return new Promise((resolve, reject) => {
      const wsUrl = this.serverUrl.replace('http', 'ws');
      const url = `${wsUrl}/webrtc/ws/${this.roomId}?token=${this.token}`;

      this.ws = new WebSocket(url);

      this.ws.onopen = () => {
        console.log('WebSocket connected to room:', this.roomId);
        resolve();
      };

      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        reject(error);
      };

      this.ws.onclose = () => {
        console.log('WebSocket disconnected');
      };

      this.ws.onmessage = async (event) => {
        const message: WebRTCMessage = JSON.parse(event.data);
        await this.handleSignalingMessage(message);
      };
    });
  }

  /**
   * Handle incoming signaling messages
   */
  private async handleSignalingMessage(message: WebRTCMessage): Promise<void> {
    console.log('Received message:', message.type);

    switch (message.type) {
      case MessageType.ROOM_STATE:
        const participants = message.payload.participants as Participant[];
        console.log('Room participants:', participants);
        
        if (this.onRoomState) {
          this.onRoomState(participants);
        }
        break;

      case MessageType.USER_JOINED:
        console.log('User joined:', message.payload.username);
        
        if (this.onParticipantJoined) {
          this.onParticipantJoined({
            user_id: message.payload.user_id,
            username: message.payload.username,
          });
        }
        break;

      case MessageType.USER_LEFT:
        console.log('User left:', message.payload.username);
        
        if (this.onParticipantLeft) {
          this.onParticipantLeft({
            user_id: message.payload.user_id,
            username: message.payload.username,
          });
        }
        break;

      case MessageType.OFFER:
        await this.handleOffer(message.payload);
        break;

      case MessageType.ANSWER:
        await this.handleAnswer(message.payload);
        break;

      case MessageType.ICE_CANDIDATE:
        await this.handleIceCandidate(message.payload);
        break;

      case MessageType.ERROR:
        console.error('Server error:', message.payload.message);
        
        if (this.onError) {
          this.onError(message.payload.message);
        }
        break;
    }
  }

  /**
   * Create and send WebRTC offer
   */
  async createOffer(targetUserId?: string): Promise<void> {
    if (!this.peerConnection) {
      await this.createPeerConnection();
    }

    const offer = await this.peerConnection!.createOffer();
    await this.peerConnection!.setLocalDescription(offer);

    this.sendMessage({
      type: MessageType.OFFER,
      payload: {
        type: offer.type,
        sdp: offer.sdp,
        ...(targetUserId && { target_user_id: targetUserId }),
      },
      room_id: this.roomId,
      timestamp: new Date().toISOString(),
    });
  }

  /**
   * Handle incoming offer
   */
  private async handleOffer(payload: any): Promise<void> {
    if (!this.peerConnection) {
      await this.createPeerConnection();
    }

    await this.peerConnection!.setRemoteDescription(
      new RTCSessionDescription({ type: payload.type, sdp: payload.sdp })
    );

    const answer = await this.peerConnection!.createAnswer();
    await this.peerConnection!.setLocalDescription(answer);

    this.sendMessage({
      type: MessageType.ANSWER,
      payload: {
        type: answer.type,
        sdp: answer.sdp,
        target_user_id: payload.sender_id,
      },
      room_id: this.roomId,
      timestamp: new Date().toISOString(),
    });
  }

  /**
   * Handle incoming answer
   */
  private async handleAnswer(payload: any): Promise<void> {
    await this.peerConnection!.setRemoteDescription(
      new RTCSessionDescription({ type: payload.type, sdp: payload.sdp })
    );
  }

  /**
   * Handle incoming ICE candidate
   */
  private async handleIceCandidate(payload: any): Promise<void> {
    const candidate = new RTCIceCandidate({
      candidate: payload.candidate,
      sdpMid: payload.sdp_mid,
      sdpMLineIndex: payload.sdp_m_line_index,
    });

    await this.peerConnection!.addIceCandidate(candidate);
  }

  /**
   * Send message through WebSocket
   */
  private sendMessage(message: WebRTCMessage): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    }
  }

  /**
   * Toggle local audio
   */
  toggleAudio(): boolean {
    if (this.localStream) {
      const audioTrack = this.localStream.getAudioTracks()[0];
      audioTrack.enabled = !audioTrack.enabled;
      return audioTrack.enabled;
    }
    return false;
  }

  /**
   * Toggle local video
   */
  toggleVideo(): boolean {
    if (this.localStream) {
      const videoTrack = this.localStream.getVideoTracks()[0];
      videoTrack.enabled = !videoTrack.enabled;
      return videoTrack.enabled;
    }
    return false;
  }

  /**
   * Cleanup and disconnect
   */
  async disconnect(): Promise<void> {
    // Stop local stream
    if (this.localStream) {
      this.localStream.getTracks().forEach(track => track.stop());
      this.localStream = null;
    }

    // Close peer connection
    if (this.peerConnection) {
      this.peerConnection.close();
      this.peerConnection = null;
    }

    // Close WebSocket
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}

export default WebRTCService;
```

#### 2. React Video Call Component

```tsx
// src/components/VideoCall.tsx
import React, { useEffect, useRef, useState } from 'react';
import WebRTCService, { Participant } from '../services/webrtc';

interface VideoCallProps {
  serverUrl: string;
  token: string;
  roomId: string;
  onLeave: () => void;
}

const VideoCall: React.FC<VideoCallProps> = ({ serverUrl, token, roomId, onLeave }) => {
  const localVideoRef = useRef<HTMLVideoElement>(null);
  const remoteVideoRef = useRef<HTMLVideoElement>(null);
  const [webrtcService] = useState(() => new WebRTCService(serverUrl, token, roomId));
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [audioEnabled, setAudioEnabled] = useState(true);
  const [videoEnabled, setVideoEnabled] = useState(true);
  const [connecting, setConnecting] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    initializeCall();

    return () => {
      webrtcService.disconnect();
    };
  }, []);

  const initializeCall = async () => {
    try {
      // Set up callbacks
      webrtcService.onLocalStream = (stream) => {
        if (localVideoRef.current) {
          localVideoRef.current.srcObject = stream;
        }
      };

      webrtcService.onRemoteStream = (stream) => {
        if (remoteVideoRef.current) {
          remoteVideoRef.current.srcObject = stream;
        }
        setConnecting(false);
      };

      webrtcService.onRoomState = (participants) => {
        setParticipants(participants);
        
        // If there are other participants, create an offer
        if (participants.length > 1) {
          webrtcService.createOffer();
        }
      };

      webrtcService.onParticipantJoined = (participant) => {
        console.log('Participant joined:', participant);
      };

      webrtcService.onError = (error) => {
        setError(error);
      };

      // Initialize local stream
      await webrtcService.initLocalStream({
        video: { width: 1280, height: 720 },
        audio: true,
      });

      // Connect to room
      await webrtcService.connectToRoom();

      setConnecting(false);
    } catch (error) {
      console.error('Failed to initialize call:', error);
      setError(error instanceof Error ? error.message : 'Failed to initialize call');
      setConnecting(false);
    }
  };

  const handleToggleAudio = () => {
    const enabled = webrtcService.toggleAudio();
    setAudioEnabled(enabled);
  };

  const handleToggleVideo = () => {
    const enabled = webrtcService.toggleVideo();
    setVideoEnabled(enabled);
  };

  const handleLeave = async () => {
    await webrtcService.disconnect();
    onLeave();
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', backgroundColor: '#000' }}>
      {/* Header */}
      <div style={{ padding: '16px', backgroundColor: '#1a1a1a', color: 'white' }}>
        <h2>Room: {roomId}</h2>
        <p>Participants: {participants.length}</p>
      </div>

      {/* Video Container */}
      <div style={{ flex: 1, position: 'relative' }}>
        {/* Remote Video */}
        <video
          ref={remoteVideoRef}
          autoPlay
          playsInline
          style={{
            width: '100%',
            height: '100%',
            objectFit: 'cover',
          }}
        />

        {/* Local Video (Picture-in-Picture) */}
        <video
          ref={localVideoRef}
          autoPlay
          playsInline
          muted
          style={{
            position: 'absolute',
            top: '16px',
            right: '16px',
            width: '200px',
            height: '150px',
            borderRadius: '8px',
            border: '2px solid white',
            objectFit: 'cover',
          }}
        />

        {/* Connecting Overlay */}
        {connecting && (
          <div
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              backgroundColor: 'rgba(0,0,0,0.8)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'white',
            }}
          >
            <div style={{ textAlign: 'center' }}>
              <p>Connecting...</p>
              {error && <p style={{ color: '#ff4444', marginTop: '8px' }}>{error}</p>}
            </div>
          </div>
        )}
      </div>

      {/* Controls */}
      <div
        style={{
          padding: '24px',
          backgroundColor: '#1a1a1a',
          display: 'flex',
          justifyContent: 'center',
          gap: '16px',
        }}
      >
        <button
          onClick={handleToggleAudio}
          style={{
            width: '60px',
            height: '60px',
            borderRadius: '50%',
            border: 'none',
            backgroundColor: audioEnabled ? '#4CAF50' : '#f44336',
            color: 'white',
            cursor: 'pointer',
            fontSize: '24px',
          }}
        >
          {audioEnabled ? '🎤' : '🔇'}
        </button>

        <button
          onClick={handleToggleVideo}
          style={{
            width: '60px',
            height: '60px',
            borderRadius: '50%',
            border: 'none',
            backgroundColor: videoEnabled ? '#4CAF50' : '#f44336',
            color: 'white',
            cursor: 'pointer',
            fontSize: '24px',
          }}
        >
          {videoEnabled ? '📹' : '📷'}
        </button>

        <button
          onClick={handleLeave}
          style={{
            width: '60px',
            height: '60px',
            borderRadius: '50%',
            border: 'none',
            backgroundColor: '#f44336',
            color: 'white',
            cursor: 'pointer',
            fontSize: '24px',
          }}
        >
          📞
        </button>
      </div>
    </div>
  );
};

export default VideoCall;
```

#### 3. Usage Example

```tsx
// src/App.tsx
import React, { useState } from 'react';
import VideoCall from './components/VideoCall';

const App: React.FC = () => {
  const [inCall, setInCall] = useState(false);
  const [roomId, setRoomId] = useState('');
  
  // Replace with your actual token from login
  const token = 'your_jwt_token_here';
  const serverUrl = 'http://localhost:8000';

  const handleJoinRoom = () => {
    if (roomId.trim()) {
      setInCall(true);
    }
  };

  const handleLeaveRoom = () => {
    setInCall(false);
    setRoomId('');
  };

  if (inCall) {
    return (
      <VideoCall
        serverUrl={serverUrl}
        token={token}
        roomId={roomId}
        onLeave={handleLeaveRoom}
      />
    );
  }

  return (
    <div style={{ padding: '40px', maxWidth: '400px', margin: '0 auto' }}>
      <h1>WebRTC Video Call</h1>
      
      <div style={{ marginTop: '24px' }}>
        <label style={{ display: 'block', marginBottom: '8px' }}>
          Room ID:
        </label>
        <input
          type="text"
          value={roomId}
          onChange={(e) => setRoomId(e.target.value)}
          placeholder="Enter room ID"
          style={{
            width: '100%',
            padding: '12px',
            fontSize: '16px',
            borderRadius: '4px',
            border: '1px solid #ccc',
          }}
        />
      </div>

      <button
        onClick={handleJoinRoom}
        disabled={!roomId.trim()}
        style={{
          marginTop: '16px',
          width: '100%',
          padding: '12px',
          fontSize: '16px',
          backgroundColor: '#4CAF50',
          color: 'white',
          border: 'none',
          borderRadius: '4px',
          cursor: roomId.trim() ? 'pointer' : 'not-allowed',
        }}
      >
        Join Room
      </button>
    </div>
  );
};

export default App;
```

## Best Practices

### 1. Error Handling
```typescript
webrtcService.onError = (error) => {
  if (error.includes('ROOM_FULL')) {
    alert('Room is full. Please try again later.');
  } else if (error.includes('UNAUTHORIZED')) {
    // Token expired, redirect to login
    window.location.href = '/login';
  } else {
    console.error('WebRTC error:', error);
  }
};
```

### 2. Connection Quality Monitoring
```typescript
peerConnection.oniceconnectionstatechange = () => {
  const state = peerConnection.iceConnectionState;
  
  if (state === 'disconnected' || state === 'failed') {
    // Attempt reconnection
    setTimeout(() => {
      webrtcService.createOffer();
    }, 2000);
  }
};
```

### 3. Permissions Handling
```typescript
async function requestPermissions(): Promise<boolean> {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: true,
      audio: true,
    });
    
    // Permissions granted
    stream.getTracks().forEach(track => track.stop());
    return true;
  } catch (error) {
    if (error.name === 'NotAllowedError') {
      alert('Camera and microphone permissions are required for video calls.');
    }
    return false;
  }
}
```

## Testing

```bash
# Test WebRTC config endpoint
curl -X GET "http://localhost:8000/webrtc/config" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Test WebSocket connection (using wscat)
wscat -c "ws://localhost:8000/webrtc/ws/test-room?token=YOUR_JWT_TOKEN"
```

## Next Steps

- [File Transfer](./02_file_transfer.md)
- [Recording](./03_recording.md)
- [End-to-End Encryption](./04_e2ee.md)
- [Room Management](./05_room_management.md)

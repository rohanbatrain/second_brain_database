# Production-Ready React WebRTC Integration

Complete production implementation of WebRTC video conferencing with React, TypeScript, and modern best practices.

## Table of Contents
1. [WebRTC Manager Service](#webrtc-manager-service)
2. [Video Room Component](#video-room-component)
3. [Media Controls](#media-controls)
4. [Participant Grid](#participant-grid)
5. [Chat Sidebar](#chat-sidebar)
6. [Screen Sharing](#screen-sharing)
7. [State Management](#state-management)
8. [Complete App Integration](#complete-app-integration)

## WebRTC Manager Service

```typescript
// src/services/webrtc/WebRTCManager.ts
import { apiClient } from '../api/client';

export interface ICEServer {
  urls: string[];
  username?: string;
  credential?: string;
}

export interface Participant {
  userId: string;
  username: string;
  role?: 'host' | 'moderator' | 'participant';
  joinedAt: string;
  stream?: MediaStream;
  audioEnabled: boolean;
  videoEnabled: boolean;
}

export interface WebRTCMessage {
  type: 'offer' | 'answer' | 'ice-candidate' | 'join' | 'leave' | 'chat' | 'media-state';
  data: any;
  userId: string;
  targetUserId?: string;
  timestamp: string;
}

export interface MediaState {
  audioEnabled: boolean;
  videoEnabled: boolean;
  screenSharing: boolean;
}

export class WebRTCManager {
  private ws: WebSocket | null = null;
  private roomId: string | null = null;
  private userId: string | null = null;
  private localStream: MediaStream | null = null;
  private screenStream: MediaStream | null = null;
  private peerConnections: Map<string, RTCPeerConnection> = new Map();
  private iceServers: ICEServer[] = [];
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private messageQueue: WebRTCMessage[] = [];
  
  // Event handlers
  public onParticipantJoined?: (participant: Participant) => void;
  public onParticipantLeft?: (userId: string) => void;
  public onStreamAdded?: (userId: string, stream: MediaStream) => void;
  public onStreamRemoved?: (userId: string) => void;
  public onChatMessage?: (message: { userId: string; text: string; timestamp: string }) => void;
  public onMediaStateChanged?: (userId: string, state: MediaState) => void;
  public onConnectionStateChanged?: (state: 'connecting' | 'connected' | 'disconnected' | 'failed') => void;
  public onError?: (error: Error) => void;

  constructor() {}

  /**
   * Initialize WebRTC configuration
   */
  async initialize(): Promise<void> {
    try {
      const response = await apiClient.get<{ iceServers: ICEServer[] }>('/webrtc/config');
      this.iceServers = response.data.iceServers;
    } catch (error) {
      console.error('Failed to get ICE servers:', error);
      // Use default STUN servers
      this.iceServers = [
        { urls: ['stun:stun.l.google.com:19302'] },
        { urls: ['stun:stun1.l.google.com:19302'] },
      ];
    }
  }

  /**
   * Join a WebRTC room
   */
  async joinRoom(
    roomId: string,
    userId: string,
    token: string,
    audioEnabled = true,
    videoEnabled = true
  ): Promise<void> {
    this.roomId = roomId;
    this.userId = userId;

    // Get user media
    try {
      this.localStream = await this.getUserMedia(audioEnabled, videoEnabled);
    } catch (error) {
      this.onError?.(new Error('Failed to access camera/microphone'));
      throw error;
    }

    // Connect to WebSocket
    await this.connectWebSocket(roomId, token);

    // Send join message
    this.sendMessage({
      type: 'join',
      data: {
        userId,
        audioEnabled,
        videoEnabled,
      },
      userId,
      timestamp: new Date().toISOString(),
    });
  }

  /**
   * Leave the room
   */
  leaveRoom(): void {
    // Send leave message
    if (this.userId) {
      this.sendMessage({
        type: 'leave',
        data: { userId: this.userId },
        userId: this.userId,
        timestamp: new Date().toISOString(),
      });
    }

    // Stop local streams
    this.stopLocalStream();
    this.stopScreenShare();

    // Close peer connections
    this.peerConnections.forEach((pc) => pc.close());
    this.peerConnections.clear();

    // Close WebSocket
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }

    this.roomId = null;
    this.userId = null;
  }

  /**
   * Toggle audio
   */
  toggleAudio(): boolean {
    if (!this.localStream) return false;

    const audioTrack = this.localStream.getAudioTracks()[0];
    if (audioTrack) {
      audioTrack.enabled = !audioTrack.enabled;
      
      // Notify other participants
      this.sendMediaState();
      
      return audioTrack.enabled;
    }
    return false;
  }

  /**
   * Toggle video
   */
  toggleVideo(): boolean {
    if (!this.localStream) return false;

    const videoTrack = this.localStream.getVideoTracks()[0];
    if (videoTrack) {
      videoTrack.enabled = !videoTrack.enabled;
      
      // Notify other participants
      this.sendMediaState();
      
      return videoTrack.enabled;
    }
    return false;
  }

  /**
   * Start screen sharing
   */
  async startScreenShare(): Promise<MediaStream | null> {
    try {
      this.screenStream = await navigator.mediaDevices.getDisplayMedia({
        video: {
          cursor: 'always',
          displaySurface: 'monitor',
        },
        audio: false,
      });

      // Handle screen share stop
      this.screenStream.getVideoTracks()[0].onended = () => {
        this.stopScreenShare();
      };

      // Replace video track in all peer connections
      const screenTrack = this.screenStream.getVideoTracks()[0];
      this.peerConnections.forEach(async (pc) => {
        const sender = pc.getSenders().find((s) => s.track?.kind === 'video');
        if (sender) {
          await sender.replaceTrack(screenTrack);
        }
      });

      this.sendMediaState();
      return this.screenStream;
    } catch (error) {
      console.error('Screen share error:', error);
      this.onError?.(new Error('Failed to start screen sharing'));
      return null;
    }
  }

  /**
   * Stop screen sharing
   */
  stopScreenShare(): void {
    if (!this.screenStream) return;

    this.screenStream.getTracks().forEach((track) => track.stop());
    this.screenStream = null;

    // Switch back to camera
    if (this.localStream) {
      const videoTrack = this.localStream.getVideoTracks()[0];
      this.peerConnections.forEach(async (pc) => {
        const sender = pc.getSenders().find((s) => s.track?.kind === 'video');
        if (sender && videoTrack) {
          await sender.replaceTrack(videoTrack);
        }
      });
    }

    this.sendMediaState();
  }

  /**
   * Send chat message
   */
  sendChatMessage(text: string): void {
    if (!this.userId) return;

    this.sendMessage({
      type: 'chat',
      data: { text },
      userId: this.userId,
      timestamp: new Date().toISOString(),
    });
  }

  /**
   * Get local stream
   */
  getLocalStream(): MediaStream | null {
    return this.localStream;
  }

  /**
   * Get current media state
   */
  getMediaState(): MediaState {
    const audioTrack = this.localStream?.getAudioTracks()[0];
    const videoTrack = this.localStream?.getVideoTracks()[0];

    return {
      audioEnabled: audioTrack?.enabled ?? false,
      videoEnabled: videoTrack?.enabled ?? false,
      screenSharing: this.screenStream !== null,
    };
  }

  // Private methods

  private async getUserMedia(audioEnabled: boolean, videoEnabled: boolean): Promise<MediaStream> {
    return navigator.mediaDevices.getUserMedia({
      audio: audioEnabled
        ? {
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
          }
        : false,
      video: videoEnabled
        ? {
            width: { ideal: 1280 },
            height: { ideal: 720 },
            frameRate: { ideal: 30 },
          }
        : false,
    });
  }

  private async connectWebSocket(roomId: string, token: string): Promise<void> {
    return new Promise((resolve, reject) => {
      const wsUrl = `${process.env.REACT_APP_WS_URL}/webrtc/ws/${roomId}?token=${token}`;
      
      this.ws = new WebSocket(wsUrl);
      this.onConnectionStateChanged?.('connecting');

      this.ws.onopen = () => {
        console.log('WebSocket connected');
        this.reconnectAttempts = 0;
        this.onConnectionStateChanged?.('connected');
        
        // Send queued messages
        this.messageQueue.forEach((msg) => this.sendMessage(msg));
        this.messageQueue = [];
        
        resolve();
      };

      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        this.onConnectionStateChanged?.('failed');
        reject(new Error('WebSocket connection failed'));
      };

      this.ws.onclose = () => {
        console.log('WebSocket closed');
        this.onConnectionStateChanged?.('disconnected');
        this.handleReconnect();
      };

      this.ws.onmessage = (event) => {
        this.handleMessage(JSON.parse(event.data));
      };
    });
  }

  private async handleReconnect(): Promise<void> {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      this.onError?.(new Error('Maximum reconnection attempts reached'));
      return;
    }

    this.reconnectAttempts++;
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);

    console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);

    setTimeout(async () => {
      if (this.roomId && this.userId) {
        try {
          const token = localStorage.getItem('access_token') || '';
          await this.connectWebSocket(this.roomId, token);
        } catch (error) {
          console.error('Reconnection failed:', error);
        }
      }
    }, delay);
  }

  private sendMessage(message: WebRTCMessage): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    } else {
      // Queue message for later
      this.messageQueue.push(message);
    }
  }

  private sendMediaState(): void {
    if (!this.userId) return;

    const state = this.getMediaState();
    this.sendMessage({
      type: 'media-state',
      data: state,
      userId: this.userId,
      timestamp: new Date().toISOString(),
    });
  }

  private async handleMessage(message: WebRTCMessage): Promise<void> {
    try {
      switch (message.type) {
        case 'join':
          await this.handleParticipantJoined(message);
          break;
        case 'leave':
          this.handleParticipantLeft(message);
          break;
        case 'offer':
          await this.handleOffer(message);
          break;
        case 'answer':
          await this.handleAnswer(message);
          break;
        case 'ice-candidate':
          await this.handleIceCandidate(message);
          break;
        case 'chat':
          this.handleChatMessage(message);
          break;
        case 'media-state':
          this.handleMediaStateChanged(message);
          break;
      }
    } catch (error) {
      console.error('Error handling message:', error);
      this.onError?.(error as Error);
    }
  }

  private async handleParticipantJoined(message: WebRTCMessage): Promise<void> {
    const { userId, username, audioEnabled, videoEnabled } = message.data;
    
    if (userId === this.userId) return; // Ignore self

    // Notify UI
    this.onParticipantJoined?.({
      userId,
      username,
      joinedAt: message.timestamp,
      audioEnabled,
      videoEnabled,
    });

    // Create peer connection and send offer
    const pc = await this.createPeerConnection(userId);
    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);

    this.sendMessage({
      type: 'offer',
      data: { sdp: offer.sdp },
      userId: this.userId!,
      targetUserId: userId,
      timestamp: new Date().toISOString(),
    });
  }

  private handleParticipantLeft(message: WebRTCMessage): void {
    const { userId } = message.data;
    
    // Close peer connection
    const pc = this.peerConnections.get(userId);
    if (pc) {
      pc.close();
      this.peerConnections.delete(userId);
    }

    // Notify UI
    this.onParticipantLeft?.(userId);
    this.onStreamRemoved?.(userId);
  }

  private async handleOffer(message: WebRTCMessage): Promise<void> {
    const { userId, data } = message;
    
    const pc = await this.createPeerConnection(userId);
    await pc.setRemoteDescription(new RTCSessionDescription({ type: 'offer', sdp: data.sdp }));
    
    const answer = await pc.createAnswer();
    await pc.setLocalDescription(answer);

    this.sendMessage({
      type: 'answer',
      data: { sdp: answer.sdp },
      userId: this.userId!,
      targetUserId: userId,
      timestamp: new Date().toISOString(),
    });
  }

  private async handleAnswer(message: WebRTCMessage): Promise<void> {
    const { userId, data } = message;
    
    const pc = this.peerConnections.get(userId);
    if (pc) {
      await pc.setRemoteDescription(new RTCSessionDescription({ type: 'answer', sdp: data.sdp }));
    }
  }

  private async handleIceCandidate(message: WebRTCMessage): Promise<void> {
    const { userId, data } = message;
    
    const pc = this.peerConnections.get(userId);
    if (pc && data.candidate) {
      await pc.addIceCandidate(new RTCIceCandidate(data.candidate));
    }
  }

  private handleChatMessage(message: WebRTCMessage): void {
    this.onChatMessage?.({
      userId: message.userId,
      text: message.data.text,
      timestamp: message.timestamp,
    });
  }

  private handleMediaStateChanged(message: WebRTCMessage): void {
    this.onMediaStateChanged?.(message.userId, message.data);
  }

  private async createPeerConnection(userId: string): Promise<RTCPeerConnection> {
    const pc = new RTCPeerConnection({ iceServers: this.iceServers });

    // Add local tracks
    if (this.localStream) {
      this.localStream.getTracks().forEach((track) => {
        pc.addTrack(track, this.localStream!);
      });
    }

    // Handle ICE candidates
    pc.onicecandidate = (event) => {
      if (event.candidate) {
        this.sendMessage({
          type: 'ice-candidate',
          data: { candidate: event.candidate },
          userId: this.userId!,
          targetUserId: userId,
          timestamp: new Date().toISOString(),
        });
      }
    };

    // Handle remote stream
    pc.ontrack = (event) => {
      console.log('Received remote track:', event.track.kind);
      const stream = event.streams[0];
      this.onStreamAdded?.(userId, stream);
    };

    // Handle connection state
    pc.onconnectionstatechange = () => {
      console.log(`Connection state with ${userId}:`, pc.connectionState);
      
      if (pc.connectionState === 'failed') {
        pc.close();
        this.peerConnections.delete(userId);
        this.onStreamRemoved?.(userId);
      }
    };

    this.peerConnections.set(userId, pc);
    return pc;
  }

  private stopLocalStream(): void {
    if (this.localStream) {
      this.localStream.getTracks().forEach((track) => track.stop());
      this.localStream = null;
    }
  }
}

// Singleton instance
export const webrtcManager = new WebRTCManager();
```

## Video Room Component

```tsx
// src/components/VideoRoom/VideoRoom.tsx
import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { webrtcManager, Participant } from '../../services/webrtc/WebRTCManager';
import ParticipantGrid from './ParticipantGrid';
import MediaControls from './MediaControls';
import ChatSidebar from './ChatSidebar';
import styles from './styles.module.css';

interface VideoRoomProps {
  userId: string;
  username: string;
}

const VideoRoom: React.FC<VideoRoomProps> = ({ userId, username }) => {
  const { roomId } = useParams<{ roomId: string }>();
  const navigate = useNavigate();

  const [participants, setParticipants] = useState<Map<string, Participant>>(new Map());
  const [localStream, setLocalStream] = useState<MediaStream | null>(null);
  const [remoteStreams, setRemoteStreams] = useState<Map<string, MediaStream>>(new Map());
  const [audioEnabled, setAudioEnabled] = useState(true);
  const [videoEnabled, setVideoEnabled] = useState(true);
  const [screenSharing, setScreenSharing] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [connectionState, setConnectionState] = useState<'connecting' | 'connected' | 'disconnected'>('connecting');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!roomId) {
      navigate('/');
      return;
    }

    initializeRoom();

    return () => {
      webrtcManager.leaveRoom();
    };
  }, [roomId]);

  const initializeRoom = async () => {
    try {
      // Initialize WebRTC
      await webrtcManager.initialize();

      // Set up event handlers
      webrtcManager.onParticipantJoined = handleParticipantJoined;
      webrtcManager.onParticipantLeft = handleParticipantLeft;
      webrtcManager.onStreamAdded = handleStreamAdded;
      webrtcManager.onStreamRemoved = handleStreamRemoved;
      webrtcManager.onConnectionStateChanged = handleConnectionStateChanged;
      webrtcManager.onError = handleError;

      // Join room
      const token = localStorage.getItem('access_token') || '';
      await webrtcManager.joinRoom(roomId!, userId, token, audioEnabled, videoEnabled);

      // Get local stream
      const stream = webrtcManager.getLocalStream();
      setLocalStream(stream);
    } catch (error) {
      console.error('Failed to initialize room:', error);
      setError('Failed to join room. Please check your camera/microphone permissions.');
    }
  };

  const handleParticipantJoined = useCallback((participant: Participant) => {
    setParticipants((prev) => new Map(prev).set(participant.userId, participant));
  }, []);

  const handleParticipantLeft = useCallback((userId: string) => {
    setParticipants((prev) => {
      const next = new Map(prev);
      next.delete(userId);
      return next;
    });
  }, []);

  const handleStreamAdded = useCallback((userId: string, stream: MediaStream) => {
    setRemoteStreams((prev) => new Map(prev).set(userId, stream));
  }, []);

  const handleStreamRemoved = useCallback((userId: string) => {
    setRemoteStreams((prev) => {
      const next = new Map(prev);
      next.delete(userId);
      return next;
    });
  }, []);

  const handleConnectionStateChanged = useCallback((state: 'connecting' | 'connected' | 'disconnected' | 'failed') => {
    setConnectionState(state === 'failed' ? 'disconnected' : state);
  }, []);

  const handleError = useCallback((error: Error) => {
    setError(error.message);
  }, []);

  const toggleAudio = () => {
    const enabled = webrtcManager.toggleAudio();
    setAudioEnabled(enabled);
  };

  const toggleVideo = () => {
    const enabled = webrtcManager.toggleVideo();
    setVideoEnabled(enabled);
  };

  const toggleScreenShare = async () => {
    if (screenSharing) {
      webrtcManager.stopScreenShare();
      setScreenSharing(false);
    } else {
      const stream = await webrtcManager.startScreenShare();
      setScreenSharing(stream !== null);
    }
  };

  const leaveRoom = () => {
    webrtcManager.leaveRoom();
    navigate('/');
  };

  if (error) {
    return (
      <div className={styles.errorContainer}>
        <h2>Error</h2>
        <p>{error}</p>
        <button onClick={() => navigate('/')}>Go Back</button>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h1 className={styles.title}>Room: {roomId}</h1>
        <div className={styles.connectionStatus}>
          <span className={`${styles.statusDot} ${styles[connectionState]}`} />
          <span>{connectionState}</span>
        </div>
      </div>

      <div className={styles.content}>
        <div className={styles.videoArea}>
          <ParticipantGrid
            localStream={localStream}
            localUserId={userId}
            localUsername={username}
            participants={participants}
            remoteStreams={remoteStreams}
            audioEnabled={audioEnabled}
            videoEnabled={videoEnabled}
          />

          <MediaControls
            audioEnabled={audioEnabled}
            videoEnabled={videoEnabled}
            screenSharing={screenSharing}
            onToggleAudio={toggleAudio}
            onToggleVideo={toggleVideo}
            onToggleScreenShare={toggleScreenShare}
            onToggleChat={() => setChatOpen(!chatOpen)}
            onLeave={leaveRoom}
          />
        </div>

        {chatOpen && (
          <ChatSidebar
            onClose={() => setChatOpen(false)}
          />
        )}
      </div>
    </div>
  );
};

export default VideoRoom;
```

This is the first part of the production-ready WebRTC React integration. Let me continue with the remaining components in the next message.

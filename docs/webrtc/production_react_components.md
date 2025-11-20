# Production React WebRTC Components (Part 2)

## Participant Grid Component

```tsx
// src/components/VideoRoom/ParticipantGrid.tsx
import React, { useMemo } from 'react';
import { Participant } from '../../services/webrtc/WebRTCManager';
import VideoTile from './VideoTile';
import styles from './styles.module.css';

interface ParticipantGridProps {
  localStream: MediaStream | null;
  localUserId: string;
  localUsername: string;
  participants: Map<string, Participant>;
  remoteStreams: Map<string, MediaStream>;
  audioEnabled: boolean;
  videoEnabled: boolean;
}

const ParticipantGrid: React.FC<ParticipantGridProps> = ({
  localStream,
  localUserId,
  localUsername,
  participants,
  remoteStreams,
  audioEnabled,
  videoEnabled,
}) => {
  const gridClass = useMemo(() => {
    const totalParticipants = participants.size + 1; // +1 for local user
    
    if (totalParticipants === 1) return styles.grid1;
    if (totalParticipants === 2) return styles.grid2;
    if (totalParticipants <= 4) return styles.grid4;
    if (totalParticipants <= 6) return styles.grid6;
    return styles.grid9;
  }, [participants.size]);

  return (
    <div className={`${styles.participantGrid} ${gridClass}`}>
      {/* Local video */}
      <VideoTile
        stream={localStream}
        userId={localUserId}
        username={localUsername}
        isLocal={true}
        audioEnabled={audioEnabled}
        videoEnabled={videoEnabled}
      />

      {/* Remote videos */}
      {Array.from(participants.values()).map((participant) => (
        <VideoTile
          key={participant.userId}
          stream={remoteStreams.get(participant.userId) || null}
          userId={participant.userId}
          username={participant.username}
          isLocal={false}
          audioEnabled={participant.audioEnabled}
          videoEnabled={participant.videoEnabled}
        />
      ))}
    </div>
  );
};

export default ParticipantGrid;
```

## Video Tile Component

```tsx
// src/components/VideoRoom/VideoTile.tsx
import React, { useEffect, useRef, useState } from 'react';
import styles from './styles.module.css';

interface VideoTileProps {
  stream: MediaStream | null;
  userId: string;
  username: string;
  isLocal: boolean;
  audioEnabled: boolean;
  videoEnabled: boolean;
}

const VideoTile: React.FC<VideoTileProps> = ({
  stream,
  userId,
  username,
  isLocal,
  audioEnabled,
  videoEnabled,
}) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isSpeaking, setIsSpeaking] = useState(false);

  useEffect(() => {
    if (videoRef.current && stream) {
      videoRef.current.srcObject = stream;
    }
  }, [stream]);

  useEffect(() => {
    if (!stream) return;

    const audioTrack = stream.getAudioTracks()[0];
    if (!audioTrack) return;

    // Create audio context to detect speaking
    const audioContext = new AudioContext();
    const analyser = audioContext.createAnalyser();
    const microphone = audioContext.createMediaStreamSource(stream);
    const dataArray = new Uint8Array(analyser.frequencyBinCount);

    analyser.smoothingTimeConstant = 0.8;
    analyser.fftSize = 1024;
    microphone.connect(analyser);

    let animationId: number;
    const detectSpeaking = () => {
      analyser.getByteFrequencyData(dataArray);
      const average = dataArray.reduce((a, b) => a + b) / dataArray.length;
      setIsSpeaking(average > 20); // Threshold for speaking detection
      animationId = requestAnimationFrame(detectSpeaking);
    };

    detectSpeaking();

    return () => {
      cancelAnimationFrame(animationId);
      microphone.disconnect();
      audioContext.close();
    };
  }, [stream]);

  const initials = username
    .split(' ')
    .map((n) => n[0])
    .join('')
    .toUpperCase()
    .substring(0, 2);

  return (
    <div className={`${styles.videoTile} ${isSpeaking ? styles.speaking : ''}`}>
      {videoEnabled && stream ? (
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted={isLocal}
          className={styles.video}
        />
      ) : (
        <div className={styles.avatarContainer}>
          <div className={styles.avatar}>{initials}</div>
        </div>
      )}

      <div className={styles.tileOverlay}>
        <div className={styles.tileInfo}>
          <span className={styles.username}>
            {username} {isLocal && '(You)'}
          </span>
          <div className={styles.mediaIndicators}>
            {!audioEnabled && (
              <span className={styles.mutedIndicator} title="Microphone muted">
                🔇
              </span>
            )}
            {!videoEnabled && (
              <span className={styles.videoOffIndicator} title="Camera off">
                📷
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default VideoTile;
```

## Media Controls Component

```tsx
// src/components/VideoRoom/MediaControls.tsx
import React from 'react';
import styles from './styles.module.css';

interface MediaControlsProps {
  audioEnabled: boolean;
  videoEnabled: boolean;
  screenSharing: boolean;
  onToggleAudio: () => void;
  onToggleVideo: () => void;
  onToggleScreenShare: () => void;
  onToggleChat: () => void;
  onLeave: () => void;
}

const MediaControls: React.FC<MediaControlsProps> = ({
  audioEnabled,
  videoEnabled,
  screenSharing,
  onToggleAudio,
  onToggleVideo,
  onToggleScreenShare,
  onToggleChat,
  onLeave,
}) => {
  return (
    <div className={styles.controls}>
      <div className={styles.controlsGroup}>
        {/* Audio control */}
        <button
          onClick={onToggleAudio}
          className={`${styles.controlButton} ${!audioEnabled ? styles.disabled : ''}`}
          title={audioEnabled ? 'Mute microphone' : 'Unmute microphone'}
        >
          {audioEnabled ? (
            <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"
              />
            </svg>
          ) : (
            <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z"
              />
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M17 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2"
              />
            </svg>
          )}
          <span className={styles.controlLabel}>
            {audioEnabled ? 'Mute' : 'Unmute'}
          </span>
        </button>

        {/* Video control */}
        <button
          onClick={onToggleVideo}
          className={`${styles.controlButton} ${!videoEnabled ? styles.disabled : ''}`}
          title={videoEnabled ? 'Turn off camera' : 'Turn on camera'}
        >
          {videoEnabled ? (
            <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"
              />
            </svg>
          ) : (
            <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636"
              />
            </svg>
          )}
          <span className={styles.controlLabel}>
            {videoEnabled ? 'Stop Video' : 'Start Video'}
          </span>
        </button>

        {/* Screen share control */}
        <button
          onClick={onToggleScreenShare}
          className={`${styles.controlButton} ${screenSharing ? styles.active : ''}`}
          title={screenSharing ? 'Stop sharing' : 'Share screen'}
        >
          <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
            />
          </svg>
          <span className={styles.controlLabel}>
            {screenSharing ? 'Stop Sharing' : 'Share'}
          </span>
        </button>

        {/* Chat control */}
        <button
          onClick={onToggleChat}
          className={styles.controlButton}
          title="Toggle chat"
        >
          <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
            />
          </svg>
          <span className={styles.controlLabel}>Chat</span>
        </button>
      </div>

      {/* Leave button */}
      <button onClick={onLeave} className={styles.leaveButton} title="Leave room">
        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
          />
        </svg>
        <span className={styles.controlLabel}>Leave</span>
      </button>
    </div>
  );
};

export default MediaControls;
```

## Chat Sidebar Component

```tsx
// src/components/VideoRoom/ChatSidebar.tsx
import React, { useState, useRef, useEffect } from 'react';
import { webrtcManager } from '../../services/webrtc/WebRTCManager';
import styles from './styles.module.css';

interface ChatMessage {
  userId: string;
  text: string;
  timestamp: string;
}

interface ChatSidebarProps {
  onClose: () => void;
}

const ChatSidebar: React.FC<ChatSidebarProps> = ({ onClose }) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    webrtcManager.onChatMessage = (message) => {
      setMessages((prev) => [...prev, message]);
    };

    return () => {
      webrtcManager.onChatMessage = undefined;
    };
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = (e: React.FormEvent) => {
    e.preventDefault();
    
    if (input.trim()) {
      webrtcManager.sendChatMessage(input.trim());
      setInput('');
    }
  };

  return (
    <div className={styles.chatSidebar}>
      <div className={styles.chatHeader}>
        <h3>Chat</h3>
        <button onClick={onClose} className={styles.closeButton}>
          ✕
        </button>
      </div>

      <div className={styles.chatMessages}>
        {messages.length === 0 ? (
          <div className={styles.emptyChat}>
            <p>No messages yet</p>
            <p className={styles.emptyHint}>Send a message to start the conversation</p>
          </div>
        ) : (
          messages.map((msg, idx) => (
            <div key={idx} className={styles.chatMessage}>
              <div className={styles.chatMessageHeader}>
                <span className={styles.chatUsername}>{msg.userId}</span>
                <span className={styles.chatTime}>
                  {new Date(msg.timestamp).toLocaleTimeString([], {
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </span>
              </div>
              <p className={styles.chatText}>{msg.text}</p>
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      <form onSubmit={handleSend} className={styles.chatInputForm}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type a message..."
          className={styles.chatInput}
        />
        <button
          type="submit"
          disabled={!input.trim()}
          className={styles.chatSendButton}
        >
          Send
        </button>
      </form>
    </div>
  );
};

export default ChatSidebar;
```

## Complete Styles

```css
/* src/components/VideoRoom/styles.module.css */
.container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background-color: #1a202c;
  color: white;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  background-color: #2d3748;
  border-bottom: 1px solid #4a5568;
}

.title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.connectionStatus {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: #cbd5e0;
}

.statusDot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background-color: #718096;
}

.statusDot.connecting {
  background-color: #f6ad55;
  animation: pulse 1.5s ease-in-out infinite;
}

.statusDot.connected {
  background-color: #48bb78;
}

.statusDot.disconnected {
  background-color: #fc8181;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

.content {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.videoArea {
  flex: 1;
  display: flex;
  flex-direction: column;
  position: relative;
}

.participantGrid {
  flex: 1;
  display: grid;
  gap: 8px;
  padding: 8px;
  overflow-y: auto;
}

.grid1 {
  grid-template-columns: 1fr;
  grid-template-rows: 1fr;
}

.grid2 {
  grid-template-columns: repeat(2, 1fr);
  grid-template-rows: 1fr;
}

.grid4 {
  grid-template-columns: repeat(2, 1fr);
  grid-template-rows: repeat(2, 1fr);
}

.grid6 {
  grid-template-columns: repeat(3, 1fr);
  grid-template-rows: repeat(2, 1fr);
}

.grid9 {
  grid-template-columns: repeat(3, 1fr);
  grid-template-rows: repeat(3, 1fr);
}

.videoTile {
  position: relative;
  background-color: #2d3748;
  border-radius: 12px;
  overflow: hidden;
  min-height: 200px;
  transition: all 0.3s ease;
}

.videoTile.speaking {
  box-shadow: 0 0 0 3px #48bb78;
}

.video {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.avatarContainer {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.avatar {
  width: 80px;
  height: 80px;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: rgba(255, 255, 255, 0.2);
  border-radius: 50%;
  font-size: 32px;
  font-weight: 600;
  color: white;
}

.tileOverlay {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 12px;
  background: linear-gradient(to top, rgba(0, 0, 0, 0.7), transparent);
}

.tileInfo {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.username {
  font-size: 14px;
  font-weight: 500;
}

.mediaIndicators {
  display: flex;
  gap: 6px;
  font-size: 16px;
}

.mutedIndicator,
.videoOffIndicator {
  opacity: 0.9;
}

.controls {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  background-color: #2d3748;
  border-top: 1px solid #4a5568;
}

.controlsGroup {
  display: flex;
  gap: 12px;
}

.controlButton {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 12px 16px;
  border: none;
  border-radius: 12px;
  background-color: #4a5568;
  color: white;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.controlButton:hover {
  background-color: #718096;
}

.controlButton svg {
  width: 24px;
  height: 24px;
}

.controlButton.disabled {
  background-color: #fc8181;
}

.controlButton.disabled:hover {
  background-color: #f56565;
}

.controlButton.active {
  background-color: #4299e1;
}

.controlButton.active:hover {
  background-color: #3182ce;
}

.controlLabel {
  font-size: 12px;
  font-weight: 500;
}

.leaveButton {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 12px 20px;
  border: none;
  border-radius: 12px;
  background-color: #fc8181;
  color: white;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.leaveButton:hover {
  background-color: #f56565;
}

.leaveButton svg {
  width: 24px;
  height: 24px;
}

.chatSidebar {
  width: 320px;
  display: flex;
  flex-direction: column;
  background-color: #2d3748;
  border-left: 1px solid #4a5568;
}

.chatHeader {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid #4a5568;
}

.chatHeader h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.closeButton {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 6px;
  background-color: transparent;
  color: #cbd5e0;
  font-size: 20px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.closeButton:hover {
  background-color: #4a5568;
}

.chatMessages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.emptyChat {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: #718096;
}

.emptyChat p {
  margin: 4px 0;
}

.emptyHint {
  font-size: 14px;
}

.chatMessage {
  padding: 12px;
  background-color: #4a5568;
  border-radius: 8px;
}

.chatMessageHeader {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.chatUsername {
  font-size: 14px;
  font-weight: 600;
  color: #e2e8f0;
}

.chatTime {
  font-size: 12px;
  color: #a0aec0;
}

.chatText {
  margin: 0;
  font-size: 14px;
  line-height: 1.5;
  color: #cbd5e0;
  word-wrap: break-word;
}

.chatInputForm {
  display: flex;
  gap: 8px;
  padding: 16px;
  border-top: 1px solid #4a5568;
}

.chatInput {
  flex: 1;
  padding: 10px 12px;
  border: 1px solid #4a5568;
  border-radius: 8px;
  background-color: #1a202c;
  color: white;
  font-size: 14px;
}

.chatInput:focus {
  outline: none;
  border-color: #4299e1;
}

.chatSendButton {
  padding: 10px 16px;
  border: none;
  border-radius: 8px;
  background-color: #4299e1;
  color: white;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.chatSendButton:hover:not(:disabled) {
  background-color: #3182ce;
}

.chatSendButton:disabled {
  background-color: #4a5568;
  cursor: not-allowed;
  opacity: 0.5;
}

.errorContainer {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100vh;
  padding: 40px;
  text-align: center;
}

.errorContainer h2 {
  margin: 0 0 16px;
  color: #fc8181;
}

.errorContainer p {
  margin: 0 0 24px;
  color: #cbd5e0;
}

.errorContainer button {
  padding: 10px 24px;
  border: none;
  border-radius: 8px;
  background-color: #4299e1;
  color: white;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
}
```

## Room Join Component

```tsx
// src/components/RoomJoin/RoomJoin.tsx
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import styles from './styles.module.css';

const RoomJoin: React.FC = () => {
  const navigate = useNavigate();
  const [roomId, setRoomId] = useState('');
  const [username, setUsername] = useState('');

  const handleJoin = (e: React.FormEvent) => {
    e.preventDefault();
    
    if (roomId && username) {
      navigate(`/room/${roomId}`, { state: { username } });
    }
  };

  const handleCreateRoom = () => {
    const newRoomId = Math.random().toString(36).substring(2, 10);
    setRoomId(newRoomId);
  };

  return (
    <div className={styles.container}>
      <div className={styles.card}>
        <h1>Join Video Room</h1>
        <form onSubmit={handleJoin} className={styles.form}>
          <div className={styles.formGroup}>
            <label htmlFor="username">Your Name</label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Enter your name"
              required
            />
          </div>

          <div className={styles.formGroup}>
            <label htmlFor="roomId">Room ID</label>
            <div className={styles.roomIdGroup}>
              <input
                id="roomId"
                type="text"
                value={roomId}
                onChange={(e) => setRoomId(e.target.value)}
                placeholder="Enter room ID"
                required
              />
              <button
                type="button"
                onClick={handleCreateRoom}
                className={styles.createButton}
              >
                Create New
              </button>
            </div>
          </div>

          <button type="submit" className={styles.joinButton}>
            Join Room
          </button>
        </form>
      </div>
    </div>
  );
};

export default RoomJoin;
```

This completes the production-ready WebRTC React integration! The implementation includes all essential features for video conferencing.

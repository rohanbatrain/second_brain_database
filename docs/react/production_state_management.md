# Advanced React Patterns & State Management

Complete guide for production-ready state management with Zustand, advanced patterns, error handling, and performance optimization.

## Table of Contents
1. [Zustand Store Setup](#zustand-store-setup)
2. [RAG Store](#rag-store)
3. [WebRTC Store](#webrtc-store)
4. [Custom Hooks](#custom-hooks)
5. [Error Handling](#error-handling)
6. [Performance Optimization](#performance-optimization)
7. [Testing](#testing)

## Zustand Store Setup

### Installation

```bash
npm install zustand immer
```

### Store Types

```typescript
// src/types/store.ts
export interface User {
  id: string;
  email: string;
  username: string;
  familyId?: string;
}

export interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  refreshAuth: () => Promise<void>;
  setUser: (user: User) => void;
}

export interface AppState {
  theme: 'light' | 'dark';
  sidebarOpen: boolean;
  notifications: Notification[];
  
  toggleTheme: () => void;
  toggleSidebar: () => void;
  addNotification: (notification: Omit<Notification, 'id'>) => void;
  removeNotification: (id: string) => void;
}

export interface Notification {
  id: string;
  type: 'success' | 'error' | 'info' | 'warning';
  title: string;
  message: string;
  duration?: number;
}
```

## RAG Store

```typescript
// src/stores/ragStore.ts
import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';
import { ragService } from '../services/rag/ragService';
import { Message, Conversation, DocumentMetadata } from '../types/rag';

interface RAGState {
  // State
  conversations: Map<string, Conversation>;
  currentConversationId: string | null;
  messages: Message[];
  isLoading: boolean;
  error: string | null;
  uploadProgress: number;
  documents: DocumentMetadata[];
  
  // Actions
  createConversation: (title?: string) => string;
  setCurrentConversation: (id: string) => void;
  sendMessage: (content: string, conversationId?: string) => Promise<void>;
  clearConversation: (id: string) => void;
  deleteConversation: (id: string) => void;
  uploadDocument: (file: File, onProgress?: (progress: number) => void) => Promise<void>;
  fetchDocuments: () => Promise<void>;
  deleteDocument: (documentId: string) => Promise<void>;
  reset: () => void;
}

export const useRAGStore = create<RAGState>()(
  immer((set, get) => ({
    // Initial state
    conversations: new Map(),
    currentConversationId: null,
    messages: [],
    isLoading: false,
    error: null,
    uploadProgress: 0,
    documents: [],

    // Create new conversation
    createConversation: (title?: string) => {
      const id = crypto.randomUUID();
      const conversation: Conversation = {
        id,
        title: title || `Conversation ${get().conversations.size + 1}`,
        messages: [],
        createdAt: new Date(),
        updatedAt: new Date(),
      };

      set((state) => {
        state.conversations.set(id, conversation);
        state.currentConversationId = id;
        state.messages = [];
      });

      return id;
    },

    // Set current conversation
    setCurrentConversation: (id: string) => {
      const conversation = get().conversations.get(id);
      if (conversation) {
        set((state) => {
          state.currentConversationId = id;
          state.messages = conversation.messages;
        });
      }
    },

    // Send message
    sendMessage: async (content: string, conversationId?: string) => {
      const convId = conversationId || get().currentConversationId;
      
      if (!convId) {
        set({ error: 'No active conversation' });
        return;
      }

      // Create user message
      const userMessage: Message = {
        id: crypto.randomUUID(),
        role: 'user',
        content,
        timestamp: new Date(),
      };

      // Add user message to state
      set((state) => {
        state.messages.push(userMessage);
        const conv = state.conversations.get(convId);
        if (conv) {
          conv.messages.push(userMessage);
          conv.updatedAt = new Date();
        }
        state.isLoading = true;
        state.error = null;
      });

      try {
        // Send to API
        const response = await ragService.query(content, convId);

        // Create assistant message
        const assistantMessage: Message = {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: response.answer,
          timestamp: new Date(),
          sources: response.sources,
          metadata: {
            model: response.metadata?.model,
            responseTime: response.metadata?.response_time_ms,
          },
        };

        // Add assistant message to state
        set((state) => {
          state.messages.push(assistantMessage);
          const conv = state.conversations.get(convId);
          if (conv) {
            conv.messages.push(assistantMessage);
            conv.updatedAt = new Date();
          }
          state.isLoading = false;
        });
      } catch (error: any) {
        // Add error message
        const errorMessage: Message = {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: 'Sorry, I encountered an error processing your request.',
          timestamp: new Date(),
          error: true,
        };

        set((state) => {
          state.messages.push(errorMessage);
          state.isLoading = false;
          state.error = error.message;
        });
      }
    },

    // Clear conversation
    clearConversation: (id: string) => {
      set((state) => {
        const conv = state.conversations.get(id);
        if (conv) {
          conv.messages = [];
          conv.updatedAt = new Date();
        }
        if (state.currentConversationId === id) {
          state.messages = [];
        }
      });
    },

    // Delete conversation
    deleteConversation: (id: string) => {
      set((state) => {
        state.conversations.delete(id);
        if (state.currentConversationId === id) {
          state.currentConversationId = null;
          state.messages = [];
        }
      });
    },

    // Upload document
    uploadDocument: async (file: File, onProgress?: (progress: number) => void) => {
      set({ isLoading: true, error: null, uploadProgress: 0 });

      try {
        const response = await ragService.uploadDocument(file, (progress) => {
          set({ uploadProgress: progress });
          onProgress?.(progress);
        });

        // Refresh documents list
        await get().fetchDocuments();

        set({ isLoading: false, uploadProgress: 100 });
      } catch (error: any) {
        set({ isLoading: false, error: error.message, uploadProgress: 0 });
        throw error;
      }
    },

    // Fetch documents
    fetchDocuments: async () => {
      try {
        const documents = await ragService.getDocuments();
        set({ documents });
      } catch (error: any) {
        set({ error: error.message });
      }
    },

    // Delete document
    deleteDocument: async (documentId: string) => {
      try {
        await ragService.deleteDocument(documentId);
        set((state) => {
          state.documents = state.documents.filter((doc) => doc.id !== documentId);
        });
      } catch (error: any) {
        set({ error: error.message });
        throw error;
      }
    },

    // Reset store
    reset: () => {
      set({
        conversations: new Map(),
        currentConversationId: null,
        messages: [],
        isLoading: false,
        error: null,
        uploadProgress: 0,
        documents: [],
      });
    },
  }))
);
```

## WebRTC Store

```typescript
// src/stores/webrtcStore.ts
import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';
import { webrtcManager, Participant, MediaState } from '../services/webrtc/WebRTCManager';

interface ChatMessage {
  id: string;
  userId: string;
  username: string;
  text: string;
  timestamp: Date;
}

interface WebRTCState {
  // State
  roomId: string | null;
  participants: Map<string, Participant>;
  localStream: MediaStream | null;
  remoteStreams: Map<string, MediaStream>;
  mediaState: MediaState;
  chatMessages: ChatMessage[];
  connectionState: 'disconnected' | 'connecting' | 'connected' | 'failed';
  isLoading: boolean;
  error: string | null;
  
  // Actions
  joinRoom: (roomId: string, userId: string, username: string) => Promise<void>;
  leaveRoom: () => void;
  toggleAudio: () => void;
  toggleVideo: () => void;
  toggleScreenShare: () => Promise<void>;
  sendChatMessage: (text: string) => void;
  reset: () => void;
}

export const useWebRTCStore = create<WebRTCState>()(
  immer((set, get) => ({
    // Initial state
    roomId: null,
    participants: new Map(),
    localStream: null,
    remoteStreams: new Map(),
    mediaState: {
      audioEnabled: true,
      videoEnabled: true,
      screenSharing: false,
    },
    chatMessages: [],
    connectionState: 'disconnected',
    isLoading: false,
    error: null,

    // Join room
    joinRoom: async (roomId: string, userId: string, username: string) => {
      set({ isLoading: true, error: null });

      try {
        // Initialize WebRTC manager
        await webrtcManager.initialize();

        // Set up event handlers
        webrtcManager.onParticipantJoined = (participant) => {
          set((state) => {
            state.participants.set(participant.userId, participant);
          });
        };

        webrtcManager.onParticipantLeft = (userId) => {
          set((state) => {
            state.participants.delete(userId);
            state.remoteStreams.delete(userId);
          });
        };

        webrtcManager.onStreamAdded = (userId, stream) => {
          set((state) => {
            state.remoteStreams.set(userId, stream);
          });
        };

        webrtcManager.onStreamRemoved = (userId) => {
          set((state) => {
            state.remoteStreams.delete(userId);
          });
        };

        webrtcManager.onChatMessage = (message) => {
          set((state) => {
            state.chatMessages.push({
              id: crypto.randomUUID(),
              userId: message.userId,
              username: message.userId, // You should map this to actual username
              text: message.text,
              timestamp: new Date(message.timestamp),
            });
          });
        };

        webrtcManager.onMediaStateChanged = (userId, mediaState) => {
          set((state) => {
            const participant = state.participants.get(userId);
            if (participant) {
              participant.audioEnabled = mediaState.audioEnabled;
              participant.videoEnabled = mediaState.videoEnabled;
            }
          });
        };

        webrtcManager.onConnectionStateChanged = (connectionState) => {
          set({ connectionState: connectionState as any });
        };

        webrtcManager.onError = (error) => {
          set({ error: error.message });
        };

        // Join room
        const token = localStorage.getItem('access_token') || '';
        await webrtcManager.joinRoom(roomId, userId, token);

        // Get local stream
        const stream = webrtcManager.getLocalStream();
        const mediaState = webrtcManager.getMediaState();

        set({
          roomId,
          localStream: stream,
          mediaState,
          isLoading: false,
          connectionState: 'connected',
        });
      } catch (error: any) {
        set({
          isLoading: false,
          error: error.message,
          connectionState: 'failed',
        });
        throw error;
      }
    },

    // Leave room
    leaveRoom: () => {
      webrtcManager.leaveRoom();
      
      set({
        roomId: null,
        participants: new Map(),
        localStream: null,
        remoteStreams: new Map(),
        chatMessages: [],
        connectionState: 'disconnected',
      });
    },

    // Toggle audio
    toggleAudio: () => {
      const enabled = webrtcManager.toggleAudio();
      set((state) => {
        state.mediaState.audioEnabled = enabled;
      });
    },

    // Toggle video
    toggleVideo: () => {
      const enabled = webrtcManager.toggleVideo();
      set((state) => {
        state.mediaState.videoEnabled = enabled;
      });
    },

    // Toggle screen share
    toggleScreenShare: async () => {
      const { screenSharing } = get().mediaState;
      
      if (screenSharing) {
        webrtcManager.stopScreenShare();
        set((state) => {
          state.mediaState.screenSharing = false;
        });
      } else {
        const stream = await webrtcManager.startScreenShare();
        set((state) => {
          state.mediaState.screenSharing = stream !== null;
        });
      }
    },

    // Send chat message
    sendChatMessage: (text: string) => {
      webrtcManager.sendChatMessage(text);
    },

    // Reset store
    reset: () => {
      set({
        roomId: null,
        participants: new Map(),
        localStream: null,
        remoteStreams: new Map(),
        mediaState: {
          audioEnabled: true,
          videoEnabled: true,
          screenSharing: false,
        },
        chatMessages: [],
        connectionState: 'disconnected',
        isLoading: false,
        error: null,
      });
    },
  }))
);
```

## Custom Hooks

### useRAG Hook

```typescript
// src/hooks/useRAG.ts
import { useEffect } from 'react';
import { useRAGStore } from '../stores/ragStore';

export const useRAG = (conversationId?: string) => {
  const {
    conversations,
    currentConversationId,
    messages,
    isLoading,
    error,
    uploadProgress,
    documents,
    createConversation,
    setCurrentConversation,
    sendMessage,
    clearConversation,
    deleteConversation,
    uploadDocument,
    fetchDocuments,
    deleteDocument,
  } = useRAGStore();

  const activeConversationId = conversationId || currentConversationId;
  const activeConversation = activeConversationId
    ? conversations.get(activeConversationId)
    : null;

  useEffect(() => {
    // Fetch documents on mount
    fetchDocuments();
  }, []);

  const handleSendMessage = async (content: string) => {
    let convId = activeConversationId;
    
    // Create conversation if none exists
    if (!convId) {
      convId = createConversation();
    }
    
    await sendMessage(content, convId);
  };

  const handleUploadDocument = async (file: File, onProgress?: (progress: number) => void) => {
    await uploadDocument(file, onProgress);
  };

  return {
    // State
    conversation: activeConversation,
    conversations: Array.from(conversations.values()),
    messages,
    isLoading,
    error,
    uploadProgress,
    documents,
    
    // Actions
    sendMessage: handleSendMessage,
    createConversation,
    setCurrentConversation,
    clearConversation,
    deleteConversation,
    uploadDocument: handleUploadDocument,
    deleteDocument,
  };
};
```

### useWebRTC Hook

```typescript
// src/hooks/useWebRTC.ts
import { useEffect } from 'react';
import { useWebRTCStore } from '../stores/webrtcStore';

export const useWebRTC = (roomId?: string) => {
  const {
    roomId: currentRoomId,
    participants,
    localStream,
    remoteStreams,
    mediaState,
    chatMessages,
    connectionState,
    isLoading,
    error,
    joinRoom,
    leaveRoom,
    toggleAudio,
    toggleVideo,
    toggleScreenShare,
    sendChatMessage,
  } = useWebRTCStore();

  useEffect(() => {
    // Cleanup on unmount
    return () => {
      if (currentRoomId) {
        leaveRoom();
      }
    };
  }, []);

  const handleJoinRoom = async (userId: string, username: string) => {
    if (!roomId) {
      throw new Error('Room ID is required');
    }
    await joinRoom(roomId, userId, username);
  };

  return {
    // State
    roomId: currentRoomId,
    participants: Array.from(participants.values()),
    participantsMap: participants,
    localStream,
    remoteStreams,
    mediaState,
    chatMessages,
    connectionState,
    isLoading,
    error,
    
    // Actions
    joinRoom: handleJoinRoom,
    leaveRoom,
    toggleAudio,
    toggleVideo,
    toggleScreenShare,
    sendChatMessage,
  };
};
```

### useNotification Hook

```typescript
// src/hooks/useNotification.ts
import { useCallback } from 'react';
import { useAppStore } from '../stores/appStore';
import { Notification } from '../types/store';

export const useNotification = () => {
  const { addNotification, removeNotification } = useAppStore();

  const showSuccess = useCallback((title: string, message: string, duration = 5000) => {
    addNotification({
      type: 'success',
      title,
      message,
      duration,
    });
  }, [addNotification]);

  const showError = useCallback((title: string, message: string, duration = 5000) => {
    addNotification({
      type: 'error',
      title,
      message,
      duration,
    });
  }, [addNotification]);

  const showInfo = useCallback((title: string, message: string, duration = 5000) => {
    addNotification({
      type: 'info',
      title,
      message,
      duration,
    });
  }, [addNotification]);

  const showWarning = useCallback((title: string, message: string, duration = 5000) => {
    addNotification({
      type: 'warning',
      title,
      message,
      duration,
    });
  }, [addNotification]);

  return {
    showSuccess,
    showError,
    showInfo,
    showWarning,
    remove: removeNotification,
  };
};
```

## Error Handling

### API Error Handler

```typescript
// src/utils/errorHandler.ts
import axios, { AxiosError } from 'axios';

export interface APIError {
  message: string;
  code?: string;
  status?: number;
  details?: any;
}

export const handleAPIError = (error: unknown): APIError => {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<any>;
    
    return {
      message: axiosError.response?.data?.detail || axiosError.message || 'An error occurred',
      code: axiosError.code,
      status: axiosError.response?.status,
      details: axiosError.response?.data,
    };
  }
  
  if (error instanceof Error) {
    return {
      message: error.message,
    };
  }
  
  return {
    message: 'An unknown error occurred',
  };
};

export const getErrorMessage = (error: unknown): string => {
  const apiError = handleAPIError(error);
  return apiError.message;
};
```

### Error Toast Component

```tsx
// src/components/common/NotificationToast.tsx
import React, { useEffect } from 'react';
import { useAppStore } from '../../stores/appStore';
import styles from './styles.module.css';

const NotificationToast: React.FC = () => {
  const { notifications, removeNotification } = useAppStore();

  useEffect(() => {
    notifications.forEach((notification) => {
      if (notification.duration) {
        const timer = setTimeout(() => {
          removeNotification(notification.id);
        }, notification.duration);

        return () => clearTimeout(timer);
      }
    });
  }, [notifications, removeNotification]);

  return (
    <div className={styles.toastContainer}>
      {notifications.map((notification) => (
        <div
          key={notification.id}
          className={`${styles.toast} ${styles[notification.type]}`}
        >
          <div className={styles.toastContent}>
            <strong>{notification.title}</strong>
            <p>{notification.message}</p>
          </div>
          <button
            onClick={() => removeNotification(notification.id)}
            className={styles.closeButton}
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  );
};

export default NotificationToast;
```

## Performance Optimization

### Lazy Loading

```typescript
// src/App.tsx
import React, { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import LoadingSpinner from './components/common/LoadingSpinner';

// Lazy load components
const RAGChat = lazy(() => import('./components/RAGChat'));
const VideoRoom = lazy(() => import('./components/VideoRoom/VideoRoom'));
const DocumentUpload = lazy(() => import('./components/DocumentUpload'));

const App: React.FC = () => {
  return (
    <BrowserRouter>
      <Suspense fallback={<LoadingSpinner />}>
        <Routes>
          <Route path="/chat" element={<RAGChat />} />
          <Route path="/room/:roomId" element={<VideoRoom />} />
          <Route path="/upload" element={<DocumentUpload />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
};

export default App;
```

### Memoization

```typescript
// src/components/VideoRoom/ParticipantGrid.tsx
import React, { useMemo } from 'react';
import { Participant } from '../../services/webrtc/WebRTCManager';
import VideoTile from './VideoTile';

const ParticipantGrid: React.FC<Props> = ({ participants, remoteStreams }) => {
  // Memoize grid layout calculation
  const gridClass = useMemo(() => {
    const count = participants.size + 1;
    if (count <= 2) return styles.grid2;
    if (count <= 4) return styles.grid4;
    if (count <= 6) return styles.grid6;
    return styles.grid9;
  }, [participants.size]);

  // Memoize participant list
  const participantList = useMemo(
    () => Array.from(participants.values()),
    [participants]
  );

  return (
    <div className={gridClass}>
      {participantList.map((participant) => (
        <VideoTile
          key={participant.userId}
          participant={participant}
          stream={remoteStreams.get(participant.userId)}
        />
      ))}
    </div>
  );
};

export default React.memo(ParticipantGrid);
```

## Testing

### Store Testing

```typescript
// src/stores/__tests__/ragStore.test.ts
import { renderHook, act } from '@testing-library/react';
import { useRAGStore } from '../ragStore';
import { ragService } from '../../services/rag/ragService';

jest.mock('../../services/rag/ragService');

describe('RAG Store', () => {
  beforeEach(() => {
    useRAGStore.getState().reset();
  });

  it('should create a new conversation', () => {
    const { result } = renderHook(() => useRAGStore());

    act(() => {
      const id = result.current.createConversation('Test Conversation');
      expect(result.current.conversations.has(id)).toBe(true);
      expect(result.current.currentConversationId).toBe(id);
    });
  });

  it('should send a message', async () => {
    const { result } = renderHook(() => useRAGStore());
    
    (ragService.query as jest.Mock).mockResolvedValue({
      answer: 'Test answer',
      sources: [],
    });

    await act(async () => {
      const id = result.current.createConversation();
      await result.current.sendMessage('Test question', id);
    });

    expect(result.current.messages).toHaveLength(2);
    expect(result.current.messages[0].role).toBe('user');
    expect(result.current.messages[1].role).toBe('assistant');
  });
});
```

This completes the production-ready React integration with advanced state management, error handling, and optimization patterns!

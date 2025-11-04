# Flutter Emotion Tracker — AI Orchestration Integration Guide

**Date:** October 30, 2025  
**Integration Status:** 🚧 Planning Phase  
**Flutter App:** emotion_tracker  
**Backend:** Second Brain Database AI Orchestration System  

---

## 📋 Executive Summary

This document provides a comprehensive integration plan for connecting the Flutter emotion tracker app with the AI Orchestration System. The backend provides a sophisticated multi-agent AI system with real-time WebSocket communication, voice integration, and comprehensive tool execution capabilities.

**Key Integration Opportunities:**
- 🤖 Multi-agent AI assistance (family, personal, workspace, commerce, security, voice)
- 💬 Real-time chat with streaming responses
- 🎙️ Voice interaction with LiveKit integration
- 🔧 MCP tool execution for backend operations
- 📊 Performance monitoring and analytics
- 🔒 Comprehensive security and audit logging

---

## 🏗️ Backend AI Orchestration System Overview

### Available AI Agents

The backend provides 6 specialized AI agents:

1. **Family Agent** (`family`)
   - Family management and coordination
   - Member relationship handling
   - Family wallet operations
   - Shared resource management

2. **Personal Agent** (`personal`)
   - Individual user tasks and preferences
   - Personal assistant functionality
   - Default agent for general queries

3. **Workspace Agent** (`workspace`)
   - Team collaboration features
   - Workspace management
   - Project coordination

4. **Commerce Agent** (`commerce`)
   - Shopping assistance
   - Digital asset management (avatars, themes, banners)
   - SBD token operations

5. **Security Agent** (`security`)
   - Security monitoring (admin only)
   - System health checks
   - Audit trail management

6. **Voice Agent** (`voice`)
   - Voice command processing
   - Speech-to-text and text-to-speech
   - LiveKit integration for real-time voice
   - Multi-modal communication coordination

### Core Capabilities

- **Real-time Communication:** WebSocket-based streaming with token-by-token responses
- **Tool Execution:** MCP tools for backend operations (family management, wallet operations, etc.)
- **Voice Integration:** Full STT/TTS pipeline with LiveKit for real-time voice rooms
- **Session Management:** Persistent sessions with conversation history and context
- **Performance Monitoring:** Sub-300ms response times with comprehensive metrics
- **Security:** JWT authentication, rate limiting, audit logging, error handling

---

## 🎯 Integration Strategy

### Phase 1: Core Chat Integration (Week 1-2)
**Goal:** Basic AI chat functionality with text-based interactions

**Features to Implement:**
- AI chat interface with agent selection
- Real-time WebSocket communication
- Token streaming for responsive UI
- Basic error handling and reconnection
- Session management

**Priority:** P0 (Essential)

### Phase 2: Voice Integration (Week 3-4)
**Goal:** Voice interaction capabilities

**Features to Implement:**
- Voice input/output with STT/TTS
- LiveKit integration for real-time voice
- Voice command processing
- Multi-modal communication (text + voice)

**Priority:** P1 (High Value)

### Phase 3: Advanced Features (Week 5-6)
**Goal:** Full AI orchestration capabilities

**Features to Implement:**
- MCP tool execution visualization
- Performance monitoring dashboard
- Advanced error handling and recovery
- Offline capabilities and caching

**Priority:** P2 (Enhancement)

---

## 📱 Flutter Implementation Plan

### 1. Dependencies and Setup

#### Required Dependencies
Add to `pubspec.yaml`:

```yaml
dependencies:
  # WebSocket communication
  web_socket_channel: ^3.0.1
  
  # HTTP client for REST API
  dio: ^5.8.0+1  # Already included
  
  # State management
  flutter_riverpod: ^2.6.1  # Already included
  
  # Voice integration
  permission_handler: ^11.3.1
  record: ^5.1.2
  audioplayers: ^6.1.0
  
  # LiveKit integration (optional for advanced voice)
  livekit_client: ^2.2.5
  
  # JSON handling
  json_annotation: ^4.8.1  # Already included
  
  # Utilities
  uuid: ^4.5.1
  connectivity_plus: ^6.0.5

dev_dependencies:
  # Code generation
  json_serializable: ^6.7.1  # Already included
  build_runner: ^2.4.7  # Already included
```

#### Permissions
Add to `android/app/src/main/AndroidManifest.xml`:
```xml
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.RECORD_AUDIO" />
<uses-permission android:name="android.permission.MODIFY_AUDIO_SETTINGS" />
<uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
```

Add to `ios/Runner/Info.plist`:
```xml
<key>NSMicrophoneUsageDescription</key>
<string>This app needs microphone access for voice interactions with AI assistants</string>
```

### 2. Core Models

#### AI Event Models (`lib/models/ai/ai_events.dart`)

```dart
import 'package:json_annotation/json_annotation.dart';

part 'ai_events.g.dart';

enum AIEventType {
  @JsonValue('token')
  token,
  @JsonValue('response')
  response,
  @JsonValue('tool_call')
  toolCall,
  @JsonValue('tool_result')
  toolResult,
  @JsonValue('tts')
  tts,
  @JsonValue('stt')
  stt,
  @JsonValue('thinking')
  thinking,
  @JsonValue('typing')
  typing,
  @JsonValue('error')
  error,
  @JsonValue('session_ready')
  sessionReady,
  @JsonValue('agent_switch')
  agentSwitch,
}

enum AgentType {
  @JsonValue('family')
  family,
  @JsonValue('personal')
  personal,
  @JsonValue('workspace')
  workspace,
  @JsonValue('commerce')
  commerce,
  @JsonValue('security')
  security,
  @JsonValue('voice')
  voice,
}

@JsonSerializable()
class AIEvent {
  final AIEventType type;
  final Map<String, dynamic> data;
  @JsonKey(name: 'session_id')
  final String sessionId;
  @JsonKey(name: 'agent_type')
  final String agentType;
  final DateTime timestamp;
  final Map<String, dynamic>? metadata;
  @JsonKey(name: 'tool_name')
  final String? toolName;
  @JsonKey(name: 'error_code')
  final String? errorCode;

  AIEvent({
    required this.type,
    required this.data,
    required this.sessionId,
    required this.agentType,
    required this.timestamp,
    this.metadata,
    this.toolName,
    this.errorCode,
  });

  factory AIEvent.fromJson(Map<String, dynamic> json) => _$AIEventFromJson(json);
  Map<String, dynamic> toJson() => _$AIEventToJson(this);
}

@JsonSerializable()
class AISession {
  @JsonKey(name: 'session_id')
  final String sessionId;
  @JsonKey(name: 'agent_type')
  final AgentType agentType;
  final String status;
  @JsonKey(name: 'created_at')
  final DateTime createdAt;
  @JsonKey(name: 'last_activity')
  final DateTime lastActivity;
  @JsonKey(name: 'expires_at')
  final DateTime? expiresAt;
  @JsonKey(name: 'websocket_connected')
  final bool websocketConnected;
  @JsonKey(name: 'voice_enabled')
  final bool voiceEnabled;
  @JsonKey(name: 'message_count')
  final int messageCount;

  AISession({
    required this.sessionId,
    required this.agentType,
    required this.status,
    required this.createdAt,
    required this.lastActivity,
    this.expiresAt,
    required this.websocketConnected,
    required this.voiceEnabled,
    required this.messageCount,
  });

  factory AISession.fromJson(Map<String, dynamic> json) => _$AISessionFromJson(json);
  Map<String, dynamic> toJson() => _$AISessionToJson(this);
}

@JsonSerializable()
class ChatMessage {
  final String id;
  final String content;
  final String role; // 'user' or 'assistant'
  final String? agentType;
  final DateTime timestamp;
  final Map<String, dynamic>? metadata;
  final String? audioData; // Base64 encoded audio
  final bool isStreaming;

  ChatMessage({
    required this.id,
    required this.content,
    required this.role,
    this.agentType,
    required this.timestamp,
    this.metadata,
    this.audioData,
    this.isStreaming = false,
  });

  factory ChatMessage.fromJson(Map<String, dynamic> json) => _$ChatMessageFromJson(json);
  Map<String, dynamic> toJson() => _$ChatMessageToJson(this);

  ChatMessage copyWith({
    String? id,
    String? content,
    String? role,
    String? agentType,
    DateTime? timestamp,
    Map<String, dynamic>? metadata,
    String? audioData,
    bool? isStreaming,
  }) {
    return ChatMessage(
      id: id ?? this.id,
      content: content ?? this.content,
      role: role ?? this.role,
      agentType: agentType ?? this.agentType,
      timestamp: timestamp ?? this.timestamp,
      metadata: metadata ?? this.metadata,
      audioData: audioData ?? this.audioData,
      isStreaming: isStreaming ?? this.isStreaming,
    );
  }
}
```

### 3. AI Service Layer

#### AI API Service (`lib/providers/ai/ai_api_service.dart`)

```dart
import 'dart:convert';
import 'dart:typed_data';
import 'package:dio/dio.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:web_socket_channel/status.dart' as status;
import '../../models/ai/ai_events.dart';
import '../../utils/auth_http_client.dart';

class AIApiService {
  final Dio _dio;
  final String baseUrl;
  WebSocketChannel? _wsChannel;
  String? _currentSessionId;

  AIApiService({
    required this.baseUrl,
    required String authToken,
  }) : _dio = createAuthenticatedDio(baseUrl, authToken);

  // REST API Methods

  /// Create a new AI session
  Future<AISession> createSession({
    required AgentType agentType,
    bool voiceEnabled = false,
    Map<String, dynamic>? preferences,
    Map<String, dynamic>? settings,
    int expirationHours = 24,
  }) async {
    final response = await _dio.post('/ai/sessions', data: {
      'agent_type': agentType.name,
      'voice_enabled': voiceEnabled,
      'preferences': preferences ?? {},
      'settings': settings ?? {},
      'expiration_hours': expirationHours,
    });

    return AISession.fromJson(response.data);
  }

  /// List user's AI sessions
  Future<List<AISession>> listSessions({
    String? status,
    AgentType? agentType,
    int limit = 50,
  }) async {
    final queryParams = <String, dynamic>{
      'limit': limit,
    };
    if (status != null) queryParams['status'] = status;
    if (agentType != null) queryParams['agent_type'] = agentType.name;

    final response = await _dio.get('/ai/sessions', queryParameters: queryParams);
    
    final sessions = (response.data['sessions'] as List)
        .map((json) => AISession.fromJson(json))
        .toList();
    
    return sessions;
  }

  /// Get session details
  Future<AISession> getSession(String sessionId) async {
    final response = await _dio.get('/ai/sessions/$sessionId');
    return AISession.fromJson(response.data);
  }

  /// Send message to AI agent
  Future<Map<String, dynamic>> sendMessage({
    required String sessionId,
    required String content,
    String messageType = 'text',
    Map<String, dynamic>? metadata,
    String? audioData,
    AgentType? switchToAgent,
  }) async {
    final response = await _dio.post('/ai/sessions/$sessionId/message', data: {
      'content': content,
      'message_type': messageType,
      'metadata': metadata ?? {},
      'audio_data': audioData,
      'switch_to_agent': switchToAgent?.name,
    });

    return response.data;
  }

  /// End AI session
  Future<void> endSession(String sessionId) async {
    await _dio.delete('/ai/sessions/$sessionId');
  }

  /// Setup voice for session
  Future<Map<String, dynamic>> setupVoice(String sessionId) async {
    final response = await _dio.post('/ai/sessions/$sessionId/voice/setup');
    return response.data;
  }

  /// Process voice input
  Future<void> processVoiceInput({
    required String sessionId,
    required String audioData,
  }) async {
    await _dio.post('/ai/sessions/$sessionId/voice/input', data: {
      'audio_data': audioData,
    });
  }

  /// Get LiveKit voice token
  Future<Map<String, dynamic>> getVoiceToken(String sessionId) async {
    final response = await _dio.get('/ai/sessions/$sessionId/voice/token');
    return response.data;
  }

  /// Get AI system health
  Future<Map<String, dynamic>> getHealth() async {
    final response = await _dio.get('/ai/health');
    return response.data;
  }

  /// Get performance metrics
  Future<Map<String, dynamic>> getPerformanceMetrics() async {
    final response = await _dio.get('/ai/performance/metrics');
    return response.data;
  }

  // WebSocket Methods

  /// Connect to AI session WebSocket
  Future<void> connectWebSocket({
    required String sessionId,
    required String authToken,
    required Function(AIEvent) onEvent,
    Function(dynamic)? onError,
    Function()? onDone,
  }) async {
    _currentSessionId = sessionId;
    
    final wsUrl = baseUrl.replaceFirst('http', 'ws');
    final uri = Uri.parse('$wsUrl/ai/ws/$sessionId?token=$authToken');
    
    _wsChannel = WebSocketChannel.connect(uri);
    
    _wsChannel!.stream.listen(
      (data) {
        try {
          final json = jsonDecode(data);
          final event = AIEvent.fromJson(json);
          onEvent(event);
        } catch (e) {
          onError?.call('Failed to parse WebSocket message: $e');
        }
      },
      onError: onError,
      onDone: onDone,
    );
  }

  /// Send message through WebSocket
  void sendWebSocketMessage(Map<String, dynamic> message) {
    if (_wsChannel != null) {
      _wsChannel!.sink.add(jsonEncode(message));
    }
  }

  /// Send text message through WebSocket
  void sendTextMessage(String content) {
    sendWebSocketMessage({
      'type': 'message',
      'content': content,
      'timestamp': DateTime.now().toIso8601String(),
    });
  }

  /// Send voice message through WebSocket
  void sendVoiceMessage(String audioData, {Map<String, dynamic>? metadata}) {
    sendWebSocketMessage({
      'type': 'voice',
      'audio_data': audioData,
      'metadata': metadata ?? {},
      'timestamp': DateTime.now().toIso8601String(),
    });
  }

  /// Send ping to keep connection alive
  void sendPing() {
    sendWebSocketMessage({
      'type': 'ping',
      'timestamp': DateTime.now().toIso8601String(),
    });
  }

  /// Disconnect WebSocket
  void disconnectWebSocket() {
    _wsChannel?.sink.close(status.goingAway);
    _wsChannel = null;
    _currentSessionId = null;
  }

  /// Check if WebSocket is connected
  bool get isWebSocketConnected => _wsChannel != null;

  /// Get current session ID
  String? get currentSessionId => _currentSessionId;

  void dispose() {
    disconnectWebSocket();
  }
}
```

### 4. State Management with Riverpod

#### AI Providers (`lib/providers/ai/ai_providers.dart`)

```dart
import 'dart:async';
import 'dart:convert';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:uuid/uuid.dart';
import '../../models/ai/ai_events.dart';
import '../../core/session_manager.dart';
import 'ai_api_service.dart';

// AI API Service Provider
final aiApiServiceProvider = Provider<AIApiService>((ref) {
  final sessionManager = ref.watch(sessionManagerProvider);
  final authToken = sessionManager.getAuthToken();
  
  return AIApiService(
    baseUrl: 'https://your-backend-url.com', // Replace with actual URL
    authToken: authToken ?? '',
  );
});

// Current AI Session Provider
final currentAISessionProvider = StateNotifierProvider<CurrentAISessionNotifier, AISession?>((ref) {
  return CurrentAISessionNotifier(ref);
});

class CurrentAISessionNotifier extends StateNotifier<AISession?> {
  final Ref ref;
  Timer? _pingTimer;

  CurrentAISessionNotifier(this.ref) : super(null);

  Future<void> createSession({
    required AgentType agentType,
    bool voiceEnabled = false,
    Map<String, dynamic>? preferences,
    Map<String, dynamic>? settings,
  }) async {
    try {
      final apiService = ref.read(aiApiServiceProvider);
      
      final session = await apiService.createSession(
        agentType: agentType,
        voiceEnabled: voiceEnabled,
        preferences: preferences,
        settings: settings,
      );
      
      state = session;
      
      // Connect WebSocket
      await _connectWebSocket(session.sessionId);
      
    } catch (e) {
      throw Exception('Failed to create AI session: $e');
    }
  }

  Future<void> _connectWebSocket(String sessionId) async {
    final apiService = ref.read(aiApiServiceProvider);
    final sessionManager = ref.read(sessionManagerProvider);
    final authToken = sessionManager.getAuthToken();
    
    if (authToken == null) return;

    await apiService.connectWebSocket(
      sessionId: sessionId,
      authToken: authToken,
      onEvent: (event) {
        ref.read(aiEventsProvider.notifier).addEvent(event);
      },
      onError: (error) {
        ref.read(aiConnectionStateProvider.notifier).setError(error.toString());
      },
      onDone: () {
        ref.read(aiConnectionStateProvider.notifier).setDisconnected();
      },
    );

    ref.read(aiConnectionStateProvider.notifier).setConnected();
    
    // Start ping timer to keep connection alive
    _startPingTimer();
  }

  void _startPingTimer() {
    _pingTimer?.cancel();
    _pingTimer = Timer.periodic(const Duration(seconds: 30), (timer) {
      final apiService = ref.read(aiApiServiceProvider);
      if (apiService.isWebSocketConnected) {
        apiService.sendPing();
      } else {
        timer.cancel();
      }
    });
  }

  Future<void> endSession() async {
    if (state == null) return;

    try {
      final apiService = ref.read(aiApiServiceProvider);
      await apiService.endSession(state!.sessionId);
      
      apiService.disconnectWebSocket();
      _pingTimer?.cancel();
      
      state = null;
      ref.read(aiEventsProvider.notifier).clear();
      ref.read(aiConnectionStateProvider.notifier).setDisconnected();
      
    } catch (e) {
      throw Exception('Failed to end AI session: $e');
    }
  }

  @override
  void dispose() {
    _pingTimer?.cancel();
    super.dispose();
  }
}

// AI Events Provider
final aiEventsProvider = StateNotifierProvider<AIEventsNotifier, List<AIEvent>>((ref) {
  return AIEventsNotifier();
});

class AIEventsNotifier extends StateNotifier<List<AIEvent>> {
  AIEventsNotifier() : super([]);

  void addEvent(AIEvent event) {
    state = [...state, event];
  }

  void clear() {
    state = [];
  }
}

// Chat Messages Provider
final chatMessagesProvider = StateNotifierProvider<ChatMessagesNotifier, List<ChatMessage>>((ref) {
  return ChatMessagesNotifier(ref);
});

class ChatMessagesNotifier extends StateNotifier<List<ChatMessage>> {
  final Ref ref;
  ChatMessage? _currentStreamingMessage;

  ChatMessagesNotifier(this.ref) : super([]) {
    // Listen to AI events and convert to chat messages
    ref.listen(aiEventsProvider, (previous, next) {
      if (previous != next && next.isNotEmpty) {
        _handleAIEvent(next.last);
      }
    });
  }

  void _handleAIEvent(AIEvent event) {
    switch (event.type) {
      case AIEventType.token:
        _handleTokenEvent(event);
        break;
      case AIEventType.response:
        _handleResponseEvent(event);
        break;
      case AIEventType.thinking:
      case AIEventType.typing:
        _handleStatusEvent(event);
        break;
      case AIEventType.error:
        _handleErrorEvent(event);
        break;
      case AIEventType.tts:
        _handleTTSEvent(event);
        break;
      default:
        break;
    }
  }

  void _handleTokenEvent(AIEvent event) {
    final token = event.data['token'] as String?;
    if (token == null) return;

    if (_currentStreamingMessage == null) {
      // Start new streaming message
      _currentStreamingMessage = ChatMessage(
        id: const Uuid().v4(),
        content: token,
        role: 'assistant',
        agentType: event.agentType,
        timestamp: event.timestamp,
        isStreaming: true,
      );
      state = [...state, _currentStreamingMessage!];
    } else {
      // Update existing streaming message
      final updatedMessage = _currentStreamingMessage!.copyWith(
        content: _currentStreamingMessage!.content + token,
      );
      _currentStreamingMessage = updatedMessage;
      
      // Update the last message in state
      final newState = [...state];
      newState[newState.length - 1] = updatedMessage;
      state = newState;
    }
  }

  void _handleResponseEvent(AIEvent event) {
    if (_currentStreamingMessage != null) {
      // Finalize streaming message
      final finalMessage = _currentStreamingMessage!.copyWith(
        isStreaming: false,
      );
      
      final newState = [...state];
      newState[newState.length - 1] = finalMessage;
      state = newState;
      
      _currentStreamingMessage = null;
    }
  }

  void _handleStatusEvent(AIEvent event) {
    final message = event.data['message'] as String?;
    if (message == null) return;

    final statusMessage = ChatMessage(
      id: const Uuid().v4(),
      content: message,
      role: 'system',
      agentType: event.agentType,
      timestamp: event.timestamp,
      metadata: {'status': event.type.name},
    );

    state = [...state, statusMessage];
  }

  void _handleErrorEvent(AIEvent event) {
    final error = event.data['error'] as String?;
    if (error == null) return;

    final errorMessage = ChatMessage(
      id: const Uuid().v4(),
      content: 'Error: $error',
      role: 'system',
      agentType: event.agentType,
      timestamp: event.timestamp,
      metadata: {'error': true, 'error_code': event.errorCode},
    );

    state = [...state, errorMessage];
  }

  void _handleTTSEvent(AIEvent event) {
    final audioData = event.data['audio'] as String?;
    if (audioData == null) return;

    // Find the last assistant message and add audio data
    final newState = [...state];
    for (int i = newState.length - 1; i >= 0; i--) {
      if (newState[i].role == 'assistant' && newState[i].audioData == null) {
        newState[i] = newState[i].copyWith(audioData: audioData);
        break;
      }
    }
    state = newState;
  }

  void addUserMessage(String content, {String? audioData}) {
    final message = ChatMessage(
      id: const Uuid().v4(),
      content: content,
      role: 'user',
      timestamp: DateTime.now(),
      audioData: audioData,
    );

    state = [...state, message];
  }

  void clear() {
    state = [];
    _currentStreamingMessage = null;
  }
}

// Connection State Provider
final aiConnectionStateProvider = StateNotifierProvider<AIConnectionStateNotifier, AIConnectionState>((ref) {
  return AIConnectionStateNotifier();
});

enum AIConnectionStatus { disconnected, connecting, connected, error }

class AIConnectionState {
  final AIConnectionStatus status;
  final String? error;

  AIConnectionState({required this.status, this.error});
}

class AIConnectionStateNotifier extends StateNotifier<AIConnectionState> {
  AIConnectionStateNotifier() : super(AIConnectionState(status: AIConnectionStatus.disconnected));

  void setConnecting() {
    state = AIConnectionState(status: AIConnectionStatus.connecting);
  }

  void setConnected() {
    state = AIConnectionState(status: AIConnectionStatus.connected);
  }

  void setDisconnected() {
    state = AIConnectionState(status: AIConnectionStatus.disconnected);
  }

  void setError(String error) {
    state = AIConnectionState(status: AIConnectionStatus.error, error: error);
  }
}

// Voice State Provider
final voiceStateProvider = StateNotifierProvider<VoiceStateNotifier, VoiceState>((ref) {
  return VoiceStateNotifier(ref);
});

class VoiceState {
  final bool isRecording;
  final bool isPlaying;
  final bool isProcessing;
  final String? error;

  VoiceState({
    this.isRecording = false,
    this.isPlaying = false,
    this.isProcessing = false,
    this.error,
  });

  VoiceState copyWith({
    bool? isRecording,
    bool? isPlaying,
    bool? isProcessing,
    String? error,
  }) {
    return VoiceState(
      isRecording: isRecording ?? this.isRecording,
      isPlaying: isPlaying ?? this.isPlaying,
      isProcessing: isProcessing ?? this.isProcessing,
      error: error ?? this.error,
    );
  }
}

class VoiceStateNotifier extends StateNotifier<VoiceState> {
  final Ref ref;

  VoiceStateNotifier(this.ref) : super(VoiceState());

  void setRecording(bool isRecording) {
    state = state.copyWith(isRecording: isRecording);
  }

  void setPlaying(bool isPlaying) {
    state = state.copyWith(isPlaying: isPlaying);
  }

  void setProcessing(bool isProcessing) {
    state = state.copyWith(isProcessing: isProcessing);
  }

  void setError(String? error) {
    state = state.copyWith(error: error);
  }

  void clearError() {
    state = state.copyWith(error: null);
  }
}
```

### 5. Voice Integration Service

#### Voice Service (`lib/providers/ai/voice_service.dart`)

```dart
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';
import 'package:flutter/foundation.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:record/record.dart';
import 'package:audioplayers/audioplayers.dart';
import 'package:path_provider/path_provider.dart';

class VoiceService {
  final AudioRecorder _recorder = AudioRecorder();
  final AudioPlayer _player = AudioPlayer();
  bool _isRecording = false;
  bool _isPlaying = false;

  // Check and request microphone permission
  Future<bool> checkMicrophonePermission() async {
    final status = await Permission.microphone.status;
    
    if (status.isDenied) {
      final result = await Permission.microphone.request();
      return result.isGranted;
    }
    
    return status.isGranted;
  }

  // Start recording audio
  Future<void> startRecording() async {
    if (_isRecording) return;

    final hasPermission = await checkMicrophonePermission();
    if (!hasPermission) {
      throw Exception('Microphone permission denied');
    }

    try {
      final tempDir = await getTemporaryDirectory();
      final path = '${tempDir.path}/voice_input_${DateTime.now().millisecondsSinceEpoch}.wav';

      await _recorder.start(
        const RecordConfig(
          encoder: AudioEncoder.wav,
          sampleRate: 16000,
          bitRate: 128000,
        ),
        path: path,
      );

      _isRecording = true;
    } catch (e) {
      throw Exception('Failed to start recording: $e');
    }
  }

  // Stop recording and return audio data
  Future<Uint8List?> stopRecording() async {
    if (!_isRecording) return null;

    try {
      final path = await _recorder.stop();
      _isRecording = false;

      if (path != null) {
        final file = File(path);
        if (await file.exists()) {
          final audioBytes = await file.readAsBytes();
          await file.delete(); // Clean up temp file
          return audioBytes;
        }
      }
      return null;
    } catch (e) {
      _isRecording = false;
      throw Exception('Failed to stop recording: $e');
    }
  }

  // Convert audio bytes to base64 for API transmission
  String audioToBase64(Uint8List audioBytes) {
    return base64Encode(audioBytes);
  }

  // Convert base64 audio to bytes for playback
  Uint8List base64ToAudio(String base64Audio) {
    return base64Decode(base64Audio);
  }

  // Play audio from base64 data
  Future<void> playAudioFromBase64(String base64Audio) async {
    if (_isPlaying) return;

    try {
      _isPlaying = true;
      
      final audioBytes = base64ToAudio(base64Audio);
      final tempDir = await getTemporaryDirectory();
      final path = '${tempDir.path}/tts_output_${DateTime.now().millisecondsSinceEpoch}.wav';
      
      final file = File(path);
      await file.writeAsBytes(audioBytes);
      
      await _player.play(DeviceFileSource(path));
      
      // Listen for completion to clean up
      _player.onPlayerComplete.listen((_) {
        _isPlaying = false;
        file.delete(); // Clean up temp file
      });
      
    } catch (e) {
      _isPlaying = false;
      throw Exception('Failed to play audio: $e');
    }
  }

  // Stop audio playback
  Future<void> stopPlayback() async {
    if (_isPlaying) {
      await _player.stop();
      _isPlaying = false;
    }
  }

  // Get recording status
  bool get isRecording => _isRecording;
  
  // Get playback status
  bool get isPlaying => _isPlaying;

  // Dispose resources
  void dispose() {
    _recorder.dispose();
    _player.dispose();
  }
}
```

### 6. UI Components

#### AI Chat Screen (`lib/screens/ai/ai_chat_screen.dart`)

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../models/ai/ai_events.dart';
import '../../providers/ai/ai_providers.dart';
import '../../widgets/ai/chat_message_widget.dart';
import '../../widgets/ai/chat_input_widget.dart';
import '../../widgets/ai/agent_selector_widget.dart';
import '../../widgets/ai/connection_status_widget.dart';

class AIChatScreen extends ConsumerStatefulWidget {
  const AIChatScreen({super.key});

  @override
  ConsumerState<AIChatScreen> createState() => _AIChatScreenState();
}

class _AIChatScreenState extends ConsumerState<AIChatScreen> {
  final ScrollController _scrollController = ScrollController();

  @override
  void initState() {
    super.initState();
    
    // Auto-scroll to bottom when new messages arrive
    ref.listenManual(chatMessagesProvider, (previous, next) {
      if (next.isNotEmpty && _scrollController.hasClients) {
        WidgetsBinding.instance.addPostFrameCallback((_) {
          _scrollController.animateTo(
            _scrollController.position.maxScrollExtent,
            duration: const Duration(milliseconds: 300),
            curve: Curves.easeOut,
          );
        });
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final currentSession = ref.watch(currentAISessionProvider);
    final messages = ref.watch(chatMessagesProvider);
    final connectionState = ref.watch(aiConnectionStateProvider);

    return Scaffold(
      appBar: AppBar(
        title: Text(currentSession != null 
          ? '${currentSession.agentType.name.toUpperCase()} Assistant'
          : 'AI Assistant'
        ),
        actions: [
          ConnectionStatusWidget(),
          if (currentSession != null)
            IconButton(
              icon: const Icon(Icons.close),
              onPressed: () => _endSession(),
            ),
        ],
      ),
      body: Column(
        children: [
          // Agent Selector (when no session)
          if (currentSession == null)
            const Padding(
              padding: EdgeInsets.all(16.0),
              child: AgentSelectorWidget(),
            ),
          
          // Chat Messages
          Expanded(
            child: currentSession == null
              ? const Center(
                  child: Text(
                    'Select an AI assistant to start chatting',
                    style: TextStyle(fontSize: 16, color: Colors.grey),
                  ),
                )
              : ListView.builder(
                  controller: _scrollController,
                  padding: const EdgeInsets.all(16.0),
                  itemCount: messages.length,
                  itemBuilder: (context, index) {
                    return ChatMessageWidget(
                      message: messages[index],
                      onPlayAudio: (audioData) => _playAudio(audioData),
                    );
                  },
                ),
          ),
          
          // Chat Input
          if (currentSession != null)
            ChatInputWidget(
              onSendMessage: (content, audioData) => _sendMessage(content, audioData),
              enabled: connectionState.status == AIConnectionStatus.connected,
            ),
        ],
      ),
    );
  }

  Future<void> _sendMessage(String content, String? audioData) async {
    final session = ref.read(currentAISessionProvider);
    if (session == null) return;

    try {
      // Add user message to chat
      ref.read(chatMessagesProvider.notifier).addUserMessage(content, audioData: audioData);

      // Send via WebSocket for real-time response
      final apiService = ref.read(aiApiServiceProvider);
      if (audioData != null) {
        apiService.sendVoiceMessage(audioData);
      } else {
        apiService.sendTextMessage(content);
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to send message: $e')),
      );
    }
  }

  Future<void> _playAudio(String audioData) async {
    // Implementation depends on your audio player setup
    // This would use the VoiceService to play TTS audio
  }

  Future<void> _endSession() async {
    try {
      await ref.read(currentAISessionProvider.notifier).endSession();
      ref.read(chatMessagesProvider.notifier).clear();
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to end session: $e')),
      );
    }
  }

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }
}
```

#### Chat Message Widget (`lib/widgets/ai/chat_message_widget.dart`)

```dart
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../../models/ai/ai_events.dart';

class ChatMessageWidget extends StatelessWidget {
  final ChatMessage message;
  final Function(String)? onPlayAudio;

  const ChatMessageWidget({
    super.key,
    required this.message,
    this.onPlayAudio,
  });

  @override
  Widget build(BuildContext context) {
    final isUser = message.role == 'user';
    final isSystem = message.role == 'system';
    final isError = message.metadata?['error'] == true;
    final isStatus = message.metadata?['status'] != null;

    return Container(
      margin: const EdgeInsets.only(bottom: 16.0),
      child: Row(
        mainAxisAlignment: isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (!isUser) _buildAvatar(),
          const SizedBox(width: 8.0),
          Flexible(
            child: Container(
              padding: const EdgeInsets.all(12.0),
              decoration: BoxDecoration(
                color: _getBackgroundColor(context, isUser, isSystem, isError),
                borderRadius: BorderRadius.circular(16.0),
                border: isError ? Border.all(color: Colors.red, width: 1) : null,
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Agent type and timestamp
                  if (!isUser && message.agentType != null)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 4.0),
                      child: Row(
                        children: [
                          Icon(
                            _getAgentIcon(message.agentType!),
                            size: 16,
                            color: Colors.grey[600],
                          ),
                          const SizedBox(width: 4),
                          Text(
                            message.agentType!.toUpperCase(),
                            style: TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.bold,
                              color: Colors.grey[600],
                            ),
                          ),
                          const Spacer(),
                          Text(
                            DateFormat('HH:mm').format(message.timestamp),
                            style: TextStyle(
                              fontSize: 10,
                              color: Colors.grey[500],
                            ),
                          ),
                        ],
                      ),
                    ),
                  
                  // Message content
                  Text(
                    message.content,
                    style: TextStyle(
                      color: _getTextColor(context, isUser, isSystem, isError),
                      fontStyle: isStatus ? FontStyle.italic : FontStyle.normal,
                    ),
                  ),
                  
                  // Streaming indicator
                  if (message.isStreaming)
                    Padding(
                      padding: const EdgeInsets.only(top: 4.0),
                      child: Row(
                        children: [
                          SizedBox(
                            width: 12,
                            height: 12,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              valueColor: AlwaysStoppedAnimation<Color>(
                                Colors.grey[600]!,
                              ),
                            ),
                          ),
                          const SizedBox(width: 8),
                          Text(
                            'Typing...',
                            style: TextStyle(
                              fontSize: 12,
                              color: Colors.grey[600],
                              fontStyle: FontStyle.italic,
                            ),
                          ),
                        ],
                      ),
                    ),
                  
                  // Audio playback button
                  if (message.audioData != null && onPlayAudio != null)
                    Padding(
                      padding: const EdgeInsets.only(top: 8.0),
                      child: ElevatedButton.icon(
                        onPressed: () => onPlayAudio!(message.audioData!),
                        icon: const Icon(Icons.play_arrow, size: 16),
                        label: const Text('Play Audio'),
                        style: ElevatedButton.styleFrom(
                          minimumSize: const Size(0, 32),
                          padding: const EdgeInsets.symmetric(horizontal: 12),
                        ),
                      ),
                    ),
                ],
              ),
            ),
          ),
          const SizedBox(width: 8.0),
          if (isUser) _buildAvatar(),
        ],
      ),
    );
  }

  Widget _buildAvatar() {
    final isUser = message.role == 'user';
    
    return CircleAvatar(
      radius: 16,
      backgroundColor: isUser ? Colors.blue : Colors.grey[300],
      child: Icon(
        isUser ? Icons.person : _getAgentIcon(message.agentType ?? 'personal'),
        size: 16,
        color: isUser ? Colors.white : Colors.grey[700],
      ),
    );
  }

  IconData _getAgentIcon(String agentType) {
    switch (agentType.toLowerCase()) {
      case 'family':
        return Icons.family_restroom;
      case 'personal':
        return Icons.person;
      case 'workspace':
        return Icons.work;
      case 'commerce':
        return Icons.shopping_cart;
      case 'security':
        return Icons.security;
      case 'voice':
        return Icons.mic;
      default:
        return Icons.smart_toy;
    }
  }

  Color _getBackgroundColor(BuildContext context, bool isUser, bool isSystem, bool isError) {
    if (isError) return Colors.red[50]!;
    if (isSystem) return Colors.grey[100]!;
    if (isUser) return Theme.of(context).primaryColor;
    return Colors.grey[200]!;
  }

  Color _getTextColor(BuildContext context, bool isUser, bool isSystem, bool isError) {
    if (isError) return Colors.red[700]!;
    if (isSystem) return Colors.grey[600]!;
    if (isUser) return Colors.white;
    return Colors.black87;
  }
}
```

#### Chat Input Widget (`lib/widgets/ai/chat_input_widget.dart`)

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../providers/ai/ai_providers.dart';
import '../../providers/ai/voice_service.dart';

class ChatInputWidget extends ConsumerStatefulWidget {
  final Function(String content, String? audioData) onSendMessage;
  final bool enabled;

  const ChatInputWidget({
    super.key,
    required this.onSendMessage,
    this.enabled = true,
  });

  @override
  ConsumerState<ChatInputWidget> createState() => _ChatInputWidgetState();
}

class _ChatInputWidgetState extends ConsumerState<ChatInputWidget> {
  final TextEditingController _controller = TextEditingController();
  final VoiceService _voiceService = VoiceService();
  bool _isRecording = false;

  @override
  Widget build(BuildContext context) {
    final voiceState = ref.watch(voiceStateProvider);

    return Container(
      padding: const EdgeInsets.all(16.0),
      decoration: BoxDecoration(
        color: Theme.of(context).scaffoldBackgroundColor,
        border: Border(
          top: BorderSide(color: Colors.grey[300]!),
        ),
      ),
      child: Row(
        children: [
          // Voice input button
          IconButton(
            onPressed: widget.enabled ? _toggleVoiceRecording : null,
            icon: Icon(
              _isRecording ? Icons.stop : Icons.mic,
              color: _isRecording ? Colors.red : null,
            ),
          ),
          
          // Text input
          Expanded(
            child: TextField(
              controller: _controller,
              enabled: widget.enabled && !_isRecording,
              decoration: InputDecoration(
                hintText: _isRecording 
                  ? 'Recording...' 
                  : 'Type your message...',
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(24.0),
                ),
                contentPadding: const EdgeInsets.symmetric(
                  horizontal: 16.0,
                  vertical: 8.0,
                ),
              ),
              maxLines: null,
              textInputAction: TextInputAction.send,
              onSubmitted: widget.enabled ? _sendTextMessage : null,
            ),
          ),
          
          const SizedBox(width: 8.0),
          
          // Send button
          IconButton(
            onPressed: widget.enabled && _controller.text.trim().isNotEmpty 
              ? () => _sendTextMessage(_controller.text)
              : null,
            icon: const Icon(Icons.send),
          ),
        ],
      ),
    );
  }

  void _sendTextMessage(String text) {
    if (text.trim().isEmpty) return;
    
    widget.onSendMessage(text.trim(), null);
    _controller.clear();
  }

  Future<void> _toggleVoiceRecording() async {
    if (_isRecording) {
      await _stopRecording();
    } else {
      await _startRecording();
    }
  }

  Future<void> _startRecording() async {
    try {
      ref.read(voiceStateProvider.notifier).setRecording(true);
      await _voiceService.startRecording();
      setState(() => _isRecording = true);
    } catch (e) {
      ref.read(voiceStateProvider.notifier).setError('Failed to start recording: $e');
      ref.read(voiceStateProvider.notifier).setRecording(false);
    }
  }

  Future<void> _stopRecording() async {
    try {
      ref.read(voiceStateProvider.notifier).setProcessing(true);
      
      final audioBytes = await _voiceService.stopRecording();
      setState(() => _isRecording = false);
      
      if (audioBytes != null) {
        final audioBase64 = _voiceService.audioToBase64(audioBytes);
        widget.onSendMessage('Voice message', audioBase64);
      }
      
      ref.read(voiceStateProvider.notifier).setProcessing(false);
      ref.read(voiceStateProvider.notifier).setRecording(false);
    } catch (e) {
      ref.read(voiceStateProvider.notifier).setError('Failed to process recording: $e');
      ref.read(voiceStateProvider.notifier).setProcessing(false);
      ref.read(voiceStateProvider.notifier).setRecording(false);
      setState(() => _isRecording = false);
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    _voiceService.dispose();
    super.dispose();
  }
}
```

#### Agent Selector Widget (`lib/widgets/ai/agent_selector_widget.dart`)

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../models/ai/ai_events.dart';
import '../../providers/ai/ai_providers.dart';

class AgentSelectorWidget extends ConsumerWidget {
  const AgentSelectorWidget({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Choose Your AI Assistant',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 16),
            GridView.count(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              crossAxisCount: 2,
              mainAxisSpacing: 12,
              crossAxisSpacing: 12,
              childAspectRatio: 1.2,
              children: [
                _buildAgentCard(
                  context,
                  ref,
                  AgentType.personal,
                  'Personal Assistant',
                  'Help with individual tasks and preferences',
                  Icons.person,
                  Colors.blue,
                ),
                _buildAgentCard(
                  context,
                  ref,
                  AgentType.family,
                  'Family Assistant',
                  'Manage family accounts and relationships',
                  Icons.family_restroom,
                  Colors.green,
                ),
                _buildAgentCard(
                  context,
                  ref,
                  AgentType.workspace,
                  'Workspace Assistant',
                  'Team collaboration and project management',
                  Icons.work,
                  Colors.orange,
                ),
                _buildAgentCard(
                  context,
                  ref,
                  AgentType.commerce,
                  'Commerce Assistant',
                  'Shopping and digital asset management',
                  Icons.shopping_cart,
                  Colors.purple,
                ),
                _buildAgentCard(
                  context,
                  ref,
                  AgentType.voice,
                  'Voice Assistant',
                  'Voice interactions and communication',
                  Icons.mic,
                  Colors.red,
                ),
                _buildAgentCard(
                  context,
                  ref,
                  AgentType.security,
                  'Security Assistant',
                  'System monitoring and security (Admin)',
                  Icons.security,
                  Colors.grey,
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildAgentCard(
    BuildContext context,
    WidgetRef ref,
    AgentType agentType,
    String title,
    String description,
    IconData icon,
    Color color,
  ) {
    return Card(
      elevation: 2,
      child: InkWell(
        onTap: () => _selectAgent(context, ref, agentType),
        borderRadius: BorderRadius.circular(8),
        child: Padding(
          padding: const EdgeInsets.all(12.0),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                icon,
                size: 32,
                color: color,
              ),
              const SizedBox(height: 8),
              Text(
                title,
                style: const TextStyle(
                  fontWeight: FontWeight.bold,
                  fontSize: 14,
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 4),
              Text(
                description,
                style: TextStyle(
                  fontSize: 12,
                  color: Colors.grey[600],
                ),
                textAlign: TextAlign.center,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _selectAgent(BuildContext context, WidgetRef ref, AgentType agentType) async {
    try {
      // Show loading dialog
      showDialog(
        context: context,
        barrierDismissible: false,
        builder: (context) => const AlertDialog(
          content: Row(
            children: [
              CircularProgressIndicator(),
              SizedBox(width: 16),
              Text('Starting AI session...'),
            ],
          ),
        ),
      );

      // Create AI session
      await ref.read(currentAISessionProvider.notifier).createSession(
        agentType: agentType,
        voiceEnabled: agentType == AgentType.voice,
      );

      // Close loading dialog
      if (context.mounted) {
        Navigator.of(context).pop();
      }
    } catch (e) {
      // Close loading dialog
      if (context.mounted) {
        Navigator.of(context).pop();
        
        // Show error
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to start AI session: $e')),
        );
      }
    }
  }
}
```

#### Connection Status Widget (`lib/widgets/ai/connection_status_widget.dart`)

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../providers/ai/ai_providers.dart';

class ConnectionStatusWidget extends ConsumerWidget {
  const ConnectionStatusWidget({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final connectionState = ref.watch(aiConnectionStateProvider);

    return Padding(
      padding: const EdgeInsets.only(right: 8.0),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            _getStatusIcon(connectionState.status),
            size: 16,
            color: _getStatusColor(connectionState.status),
          ),
          const SizedBox(width: 4),
          Text(
            _getStatusText(connectionState.status),
            style: TextStyle(
              fontSize: 12,
              color: _getStatusColor(connectionState.status),
            ),
          ),
        ],
      ),
    );
  }

  IconData _getStatusIcon(AIConnectionStatus status) {
    switch (status) {
      case AIConnectionStatus.connected:
        return Icons.wifi;
      case AIConnectionStatus.connecting:
        return Icons.wifi_find;
      case AIConnectionStatus.error:
        return Icons.wifi_off;
      case AIConnectionStatus.disconnected:
        return Icons.wifi_off;
    }
  }

  Color _getStatusColor(AIConnectionStatus status) {
    switch (status) {
      case AIConnectionStatus.connected:
        return Colors.green;
      case AIConnectionStatus.connecting:
        return Colors.orange;
      case AIConnectionStatus.error:
        return Colors.red;
      case AIConnectionStatus.disconnected:
        return Colors.grey;
    }
  }

  String _getStatusText(AIConnectionStatus status) {
    switch (status) {
      case AIConnectionStatus.connected:
        return 'Connected';
      case AIConnectionStatus.connecting:
        return 'Connecting';
      case AIConnectionStatus.error:
        return 'Error';
      case AIConnectionStatus.disconnected:
        return 'Offline';
    }
  }
}
```

---

## 🔧 Integration Steps

### Step 1: Setup Dependencies (Day 1)
1. Add required dependencies to `pubspec.yaml`
2. Update Android and iOS permissions
3. Run `flutter pub get` and `flutter pub run build_runner build`

### Step 2: Implement Core Models (Day 1-2)
1. Create AI event models with JSON serialization
2. Implement chat message models
3. Add session management models

### Step 3: Build Service Layer (Day 2-3)
1. Implement AI API service with REST endpoints
2. Add WebSocket communication
3. Create voice service for audio handling

### Step 4: State Management (Day 3-4)
1. Set up Riverpod providers for AI state
2. Implement session management
3. Add chat message handling with streaming

### Step 5: UI Implementation (Day 4-6)
1. Create AI chat screen
2. Build chat message widgets
3. Implement agent selector
4. Add voice input/output components

### Step 6: Testing & Polish (Day 6-7)
1. Test all AI agents and features
2. Handle error cases and edge scenarios
3. Optimize performance and user experience
4. Add offline handling

---

## 🎯 Feature Priorities

### P0 (Must Have - Week 1)
- ✅ Basic text chat with AI agents
- ✅ Real-time WebSocket communication
- ✅ Agent selection and switching
- ✅ Session management
- ✅ Error handling and reconnection

### P1 (High Value - Week 2)
- 🎙️ Voice input/output with STT/TTS
- 🔧 MCP tool execution visualization
- 📊 Performance monitoring
- 🔒 Security and audit integration

### P2 (Nice to Have - Week 3+)
- 🎥 LiveKit real-time voice rooms
- 📱 Offline capabilities
- 🎨 Advanced UI animations
- 📈 Analytics and usage tracking

---

## 🔒 Security Considerations

### Authentication
- Use existing JWT token system
- Implement token refresh logic
- Handle authentication errors gracefully

### Data Protection
- Never log sensitive user data
- Encrypt audio data in transit
- Implement proper session cleanup

### Rate Limiting
- Respect backend rate limits
- Implement client-side throttling
- Show appropriate user feedback

---

## 📊 Performance Targets

### Response Times
- **Session Creation:** < 2 seconds
- **Message Send:** < 500ms
- **WebSocket Connection:** < 1 second
- **Voice Processing:** < 3 seconds

### User Experience
- **Token Streaming:** Real-time display
- **Voice Feedback:** Immediate recording indication
- **Error Recovery:** Automatic reconnection
- **Offline Handling:** Graceful degradation

---

## 🧪 Testing Strategy

### Unit Tests
- AI service layer methods
- State management logic
- Voice processing functions
- Error handling scenarios

### Widget Tests
- Chat message rendering
- Input widget functionality
- Agent selector behavior
- Connection status display

### Integration Tests
- End-to-end chat flow
- Voice input/output pipeline
- WebSocket communication
- Session lifecycle management

---

## 📱 UI/UX Recommendations

### Chat Interface
- **Streaming Responses:** Show typing indicators and real-time token updates
- **Agent Identification:** Clear visual distinction between different AI agents
- **Voice Integration:** Intuitive voice input/output controls
- **Error Handling:** User-friendly error messages with retry options

### Agent Selection
- **Visual Cards:** Clear icons and descriptions for each agent type
- **Capabilities:** Show what each agent can help with
- **Quick Switch:** Easy agent switching during conversations
- **Permissions:** Handle admin-only agents appropriately

### Voice Features
- **Recording Indicator:** Clear visual feedback during voice input
- **Audio Playback:** Easy-to-use controls for TTS audio
- **Permissions:** Smooth permission request flow
- **Fallback:** Graceful handling when voice features unavailable

---

## 🚀 Deployment Checklist

### Pre-deployment
- [ ] All dependencies added and tested
- [ ] Models generated with build_runner
- [ ] Permissions configured for all platforms
- [ ] Backend URL configured correctly
- [ ] Authentication integration tested

### Testing
- [ ] Unit tests passing
- [ ] Widget tests covering key components
- [ ] Integration tests for critical flows
- [ ] Manual testing on multiple devices
- [ ] Voice features tested on real devices

### Production
- [ ] Error tracking configured
- [ ] Performance monitoring enabled
- [ ] Analytics events implemented
- [ ] Offline handling tested
- [ ] Security review completed

---

## 🔮 Future Enhancements

### Phase 2 Features
- **LiveKit Integration:** Real-time voice rooms for family conversations
- **Advanced Voice:** Speaker identification and voice cloning
- **Smart Notifications:** AI-generated contextual notifications
- **Workflow Automation:** Visual workflow builder with AI assistance

### Phase 3 Features
- **Multi-modal AI:** Image and document processing
- **Personalization:** Learning user preferences and patterns
- **Advanced Analytics:** Conversation insights and usage patterns
- **Enterprise Features:** Team collaboration and admin controls

---

## 📞 Support & Resources

### Backend API Documentation
- **Base URL:** `https://your-backend-url.com/ai`
- **WebSocket:** `wss://your-backend-url.com/ai/ws/{session_id}?token={jwt}`
- **Authentication:** JWT Bearer tokens
- **Rate Limits:** Documented per endpoint

### Development Resources
- **Flutter Documentation:** https://flutter.dev/docs
- **Riverpod Guide:** https://riverpod.dev/docs
- **WebSocket Guide:** https://pub.dev/packages/web_socket_channel
- **Voice Integration:** https://pub.dev/packages/record

### Team Contacts
- **Backend Team:** For API issues and feature requests
- **Flutter Team:** For client-side implementation
- **DevOps Team:** For deployment and infrastructure
- **Product Team:** For feature prioritization and UX decisions

---

*This integration guide provides a comprehensive roadmap for connecting the Flutter emotion tracker app with the AI Orchestration System. The implementation follows Flutter best practices and leverages the full capabilities of the backend AI system.*
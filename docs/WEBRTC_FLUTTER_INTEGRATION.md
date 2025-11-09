# WebRTC Flutter Integration Guide

## Overview

This guide shows how to integrate the WebRTC signaling server with your Flutter application for real-time peer-to-peer communication (voice calls, video calls, screen sharing, etc.).

## Prerequisites

1. **Backend Server Running**:
   ```bash
   uvicorn src.second_brain_database.main:app --host 0.0.0.0 --port 8000
   ```

2. **Flutter Dependencies**:
   ```yaml
   # pubspec.yaml
   dependencies:
     flutter_webrtc: ^0.9.48
     web_socket_channel: ^2.4.0
     http: ^1.1.0
     provider: ^6.1.1  # For state management
   ```

## Architecture

```
Flutter App
    ↓
1. Get JWT Token (Login)
    ↓
2. Fetch WebRTC Config (/webrtc/config)
    ↓
3. Connect WebSocket (ws://server/webrtc/ws/{room_id}?token={jwt})
    ↓
4. Create RTCPeerConnection with ICE servers
    ↓
5. Exchange Signaling Messages (Offer/Answer/ICE)
    ↓
6. Establish P2P Connection
    ↓
7. Stream Audio/Video
```

## Step-by-Step Implementation

### 1. WebRTC Service Class

Create `lib/services/webrtc_service.dart`:

```dart
import 'dart:async';
import 'dart:convert';
import 'package:flutter_webrtc/flutter_webrtc.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:http/http.dart' as http;

class WebRtcService {
  // Configuration
  final String serverUrl;
  final String token;
  
  // WebRTC Components
  RTCPeerConnection? peerConnection;
  MediaStream? localStream;
  MediaStream? remoteStream;
  
  // WebSocket
  WebSocketChannel? channel;
  String? currentRoomId;
  
  // Callbacks
  Function(MediaStream)? onLocalStream;
  Function(MediaStream)? onRemoteStream;
  Function(String)? onError;
  Function(List<dynamic>)? onParticipantsChanged;
  
  WebRtcService({
    required this.serverUrl,
    required this.token,
  });
  
  /// Fetch ICE server configuration from backend
  Future<Map<String, dynamic>> getWebRtcConfig() async {
    final response = await http.get(
      Uri.parse('$serverUrl/webrtc/config'),
      headers: {
        'Authorization': 'Bearer $token',
      },
    );
    
    if (response.statusCode == 200) {
      return json.decode(response.body);
    } else {
      throw Exception('Failed to get WebRTC config: ${response.body}');
    }
  }
  
  /// Initialize local media stream (camera/microphone)
  Future<MediaStream> initLocalStream({
    bool video = true,
    bool audio = true,
  }) async {
    final Map<String, dynamic> mediaConstraints = {
      'audio': audio,
      'video': video
          ? {
              'facingMode': 'user',
              'width': {'ideal': 1280},
              'height': {'ideal': 720},
            }
          : false,
    };
    
    localStream = await navigator.mediaDevices.getUserMedia(mediaConstraints);
    onLocalStream?.call(localStream!);
    
    return localStream!;
  }
  
  /// Create RTCPeerConnection with ICE servers from backend
  Future<void> createPeerConnection() async {
    // Get ICE server configuration from backend
    final config = await getWebRtcConfig();
    
    // Convert backend config to flutter_webrtc format
    final Map<String, dynamic> configuration = {
      'iceServers': (config['ice_servers'] as List).map((server) {
        return {
          'urls': server['urls'],
          if (server['username'] != null) 'username': server['username'],
          if (server['credential'] != null) 'credential': server['credential'],
        };
      }).toList(),
      'iceTransportPolicy': config['ice_transport_policy'] ?? 'all',
      'bundlePolicy': config['bundle_policy'] ?? 'balanced',
      'rtcpMuxPolicy': config['rtcp_mux_policy'] ?? 'require',
    };
    
    // Create peer connection
    peerConnection = await createPeerConnection(configuration);
    
    // Add local stream tracks
    if (localStream != null) {
      localStream!.getTracks().forEach((track) {
        peerConnection!.addTrack(track, localStream!);
      });
    }
    
    // Handle ICE candidates
    peerConnection!.onIceCandidate = (RTCIceCandidate candidate) {
      _sendIceCandidate(candidate);
    };
    
    // Handle remote stream
    peerConnection!.onTrack = (RTCTrackEvent event) {
      if (event.streams.isNotEmpty) {
        remoteStream = event.streams[0];
        onRemoteStream?.call(remoteStream!);
      }
    };
    
    // Handle connection state changes
    peerConnection!.onConnectionState = (RTCPeerConnectionState state) {
      print('Connection state: $state');
    };
  }
  
  /// Connect to signaling server WebSocket
  Future<void> connectToRoom(String roomId) async {
    currentRoomId = roomId;
    
    // Build WebSocket URL with JWT token
    final wsUrl = serverUrl.replaceFirst('http', 'ws');
    final uri = Uri.parse('$wsUrl/webrtc/ws/$roomId?token=$token');
    
    channel = WebSocketChannel.connect(uri);
    
    // Listen to messages
    channel!.stream.listen(
      (message) => _handleSignalingMessage(json.decode(message)),
      onError: (error) {
        print('WebSocket error: $error');
        onError?.call(error.toString());
      },
      onDone: () {
        print('WebSocket connection closed');
      },
    );
  }
  
  /// Handle incoming signaling messages
  void _handleSignalingMessage(Map<String, dynamic> message) async {
    final type = message['type'];
    final payload = message['payload'];
    
    print('Received message: $type');
    
    switch (type) {
      case 'room_state':
        // Initial room state with participants
        final participants = payload['participants'] as List;
        print('Room has ${participants.length} participants');
        onParticipantsChanged?.call(participants);
        break;
        
      case 'user_joined':
        // New user joined the room
        final username = payload['username'] ?? payload['user_id'];
        print('User joined: $username');
        break;
        
      case 'user_left':
        // User left the room
        final username = payload['username'] ?? payload['user_id'];
        print('User left: $username');
        break;
        
      case 'offer':
        // Received WebRTC offer
        await _handleOffer(payload);
        break;
        
      case 'answer':
        // Received WebRTC answer
        await _handleAnswer(payload);
        break;
        
      case 'ice_candidate':
        // Received ICE candidate
        await _handleIceCandidate(payload);
        break;
        
      case 'error':
        // Server error
        final errorMsg = payload['message'];
        print('Server error: $errorMsg');
        onError?.call(errorMsg);
        break;
    }
  }
  
  /// Create and send WebRTC offer
  Future<void> createOffer({String? targetUserId}) async {
    if (peerConnection == null) {
      await createPeerConnection();
    }
    
    // Create offer
    RTCSessionDescription description = await peerConnection!.createOffer();
    await peerConnection!.setLocalDescription(description);
    
    // Send offer to signaling server
    final message = {
      'type': 'offer',
      'payload': {
        'type': description.type,
        'sdp': description.sdp,
        if (targetUserId != null) 'target_user_id': targetUserId,
      },
      'room_id': currentRoomId,
      'timestamp': DateTime.now().toUtc().toIso8601String(),
    };
    
    _sendMessage(message);
  }
  
  /// Handle incoming WebRTC offer
  Future<void> _handleOffer(Map<String, dynamic> payload) async {
    if (peerConnection == null) {
      await createPeerConnection();
    }
    
    // Set remote description
    await peerConnection!.setRemoteDescription(
      RTCSessionDescription(payload['sdp'], payload['type']),
    );
    
    // Create answer
    RTCSessionDescription description = await peerConnection!.createAnswer();
    await peerConnection!.setLocalDescription(description);
    
    // Send answer
    final message = {
      'type': 'answer',
      'payload': {
        'type': description.type,
        'sdp': description.sdp,
        'target_user_id': payload['sender_id'],
      },
      'room_id': currentRoomId,
      'timestamp': DateTime.now().toUtc().toIso8601String(),
    };
    
    _sendMessage(message);
  }
  
  /// Handle incoming WebRTC answer
  Future<void> _handleAnswer(Map<String, dynamic> payload) async {
    await peerConnection!.setRemoteDescription(
      RTCSessionDescription(payload['sdp'], payload['type']),
    );
  }
  
  /// Handle incoming ICE candidate
  Future<void> _handleIceCandidate(Map<String, dynamic> payload) async {
    final candidate = RTCIceCandidate(
      payload['candidate'],
      payload['sdp_mid'],
      payload['sdp_m_line_index'],
    );
    
    await peerConnection!.addCandidate(candidate);
  }
  
  /// Send ICE candidate to signaling server
  void _sendIceCandidate(RTCIceCandidate candidate) {
    final message = {
      'type': 'ice_candidate',
      'payload': {
        'candidate': candidate.candidate,
        'sdp_mid': candidate.sdpMid,
        'sdp_m_line_index': candidate.sdpMLineIndex,
      },
      'room_id': currentRoomId,
      'timestamp': DateTime.now().toUtc().toIso8601String(),
    };
    
    _sendMessage(message);
  }
  
  /// Send message through WebSocket
  void _sendMessage(Map<String, dynamic> message) {
    if (channel != null) {
      channel!.sink.add(json.encode(message));
    }
  }
  
  /// Toggle local audio
  void toggleAudio() {
    if (localStream != null) {
      final audioTrack = localStream!.getAudioTracks()[0];
      audioTrack.enabled = !audioTrack.enabled;
    }
  }
  
  /// Toggle local video
  void toggleVideo() {
    if (localStream != null) {
      final videoTrack = localStream!.getVideoTracks()[0];
      videoTrack.enabled = !videoTrack.enabled;
    }
  }
  
  /// Switch camera (front/back)
  Future<void> switchCamera() async {
    if (localStream != null) {
      final videoTrack = localStream!.getVideoTracks()[0];
      await Helper.switchCamera(videoTrack);
    }
  }
  
  /// Cleanup and close connections
  Future<void> dispose() async {
    await localStream?.dispose();
    await remoteStream?.dispose();
    await peerConnection?.close();
    await channel?.sink.close();
    
    localStream = null;
    remoteStream = null;
    peerConnection = null;
    channel = null;
    currentRoomId = null;
  }
}
```

### 2. Video Call Screen

Create `lib/screens/video_call_screen.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_webrtc/flutter_webrtc.dart';
import '../services/webrtc_service.dart';

class VideoCallScreen extends StatefulWidget {
  final String serverUrl;
  final String token;
  final String roomId;
  
  const VideoCallScreen({
    Key? key,
    required this.serverUrl,
    required this.token,
    required this.roomId,
  }) : super(key: key);
  
  @override
  State<VideoCallScreen> createState() => _VideoCallScreenState();
}

class _VideoCallScreenState extends State<VideoCallScreen> {
  late WebRtcService _webRtcService;
  final RTCVideoRenderer _localRenderer = RTCVideoRenderer();
  final RTCVideoRenderer _remoteRenderer = RTCVideoRenderer();
  
  bool _isAudioEnabled = true;
  bool _isVideoEnabled = true;
  bool _isConnecting = true;
  List<dynamic> _participants = [];
  
  @override
  void initState() {
    super.initState();
    _initializeCall();
  }
  
  Future<void> _initializeCall() async {
    // Initialize renderers
    await _localRenderer.initialize();
    await _remoteRenderer.initialize();
    
    // Create WebRTC service
    _webRtcService = WebRtcService(
      serverUrl: widget.serverUrl,
      token: widget.token,
    );
    
    // Set up callbacks
    _webRtcService.onLocalStream = (stream) {
      setState(() {
        _localRenderer.srcObject = stream;
      });
    };
    
    _webRtcService.onRemoteStream = (stream) {
      setState(() {
        _remoteRenderer.srcObject = stream;
        _isConnecting = false;
      });
    };
    
    _webRtcService.onParticipantsChanged = (participants) {
      setState(() {
        _participants = participants;
        
        // If there are other participants, create offer
        if (participants.length > 1) {
          _webRtcService.createOffer();
        }
      });
    };
    
    _webRtcService.onError = (error) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error: $error')),
      );
    };
    
    // Initialize local stream
    await _webRtcService.initLocalStream(video: true, audio: true);
    
    // Connect to room
    await _webRtcService.connectToRoom(widget.roomId);
    
    setState(() {
      _isConnecting = false;
    });
  }
  
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('Room: ${widget.roomId}'),
        actions: [
          // Participants count
          Padding(
            padding: const EdgeInsets.all(16.0),
            child: Center(
              child: Text('${_participants.length} participants'),
            ),
          ),
        ],
      ),
      body: Stack(
        children: [
          // Remote video (full screen)
          _remoteRenderer.srcObject != null
              ? RTCVideoView(
                  _remoteRenderer,
                  objectFit: RTCVideoViewObjectFit.RTCVideoViewObjectFitCover,
                )
              : Center(
                  child: _isConnecting
                      ? Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            CircularProgressIndicator(),
                            SizedBox(height: 16),
                            Text('Connecting...'),
                          ],
                        )
                      : Text('Waiting for other participants...'),
                ),
          
          // Local video (picture-in-picture)
          Positioned(
            top: 16,
            right: 16,
            child: Container(
              width: 120,
              height: 160,
              decoration: BoxDecoration(
                border: Border.all(color: Colors.white, width: 2),
                borderRadius: BorderRadius.circular(8),
              ),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(6),
                child: RTCVideoView(
                  _localRenderer,
                  mirror: true,
                  objectFit: RTCVideoViewObjectFit.RTCVideoViewObjectFitCover,
                ),
              ),
            ),
          ),
          
          // Controls
          Positioned(
            bottom: 32,
            left: 0,
            right: 0,
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceEvenly,
              children: [
                // Mute/Unmute audio
                FloatingActionButton(
                  onPressed: () {
                    _webRtcService.toggleAudio();
                    setState(() {
                      _isAudioEnabled = !_isAudioEnabled;
                    });
                  },
                  child: Icon(_isAudioEnabled ? Icons.mic : Icons.mic_off),
                  backgroundColor: _isAudioEnabled ? Colors.blue : Colors.red,
                ),
                
                // Toggle video
                FloatingActionButton(
                  onPressed: () {
                    _webRtcService.toggleVideo();
                    setState(() {
                      _isVideoEnabled = !_isVideoEnabled;
                    });
                  },
                  child: Icon(_isVideoEnabled ? Icons.videocam : Icons.videocam_off),
                  backgroundColor: _isVideoEnabled ? Colors.blue : Colors.red,
                ),
                
                // Switch camera
                FloatingActionButton(
                  onPressed: () {
                    _webRtcService.switchCamera();
                  },
                  child: Icon(Icons.switch_camera),
                  backgroundColor: Colors.blue,
                ),
                
                // Hang up
                FloatingActionButton(
                  onPressed: () {
                    _webRtcService.dispose();
                    Navigator.pop(context);
                  },
                  child: Icon(Icons.call_end),
                  backgroundColor: Colors.red,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
  
  @override
  void dispose() {
    _localRenderer.dispose();
    _remoteRenderer.dispose();
    _webRtcService.dispose();
    super.dispose();
  }
}
```

### 3. Usage Example

```dart
// In your app, after user logs in:

// Get JWT token from login
final String jwtToken = await authService.login(email, password);

// Navigate to video call
Navigator.push(
  context,
  MaterialPageRoute(
    builder: (context) => VideoCallScreen(
      serverUrl: 'http://your-server.com:8000',
      token: jwtToken,
      roomId: 'room-${DateTime.now().millisecondsSinceEpoch}',
    ),
  ),
);
```

### 4. Audio-Only Call

For audio-only calls, modify the initialization:

```dart
// Initialize with audio only
await _webRtcService.initLocalStream(video: false, audio: true);
```

### 5. Screen Sharing (Mobile)

```dart
Future<void> startScreenSharing() async {
  if (WebRTC.platformIsAndroid || WebRTC.platformIsIOS) {
    final stream = await navigator.mediaDevices.getDisplayMedia({
      'video': true,
    });
    
    // Replace video track
    final videoTrack = stream.getVideoTracks()[0];
    final sender = peerConnection!.getSenders().firstWhere(
      (sender) => sender.track?.kind == 'video',
    );
    sender.replaceTrack(videoTrack);
  }
}
```

## Production Considerations

### 1. Error Handling

```dart
_webRtcService.onError = (error) {
  // Log to analytics
  FirebaseCrashlytics.instance.log('WebRTC error: $error');
  
  // Show user-friendly message
  showDialog(
    context: context,
    builder: (context) => AlertDialog(
      title: Text('Connection Error'),
      content: Text('Failed to establish connection. Please try again.'),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: Text('OK'),
        ),
      ],
    ),
  );
};
```

### 2. Network Quality Monitoring

```dart
// Monitor connection stats
Timer.periodic(Duration(seconds: 2), (timer) async {
  if (peerConnection != null) {
    final stats = await peerConnection!.getStats();
    stats.forEach((report) {
      if (report.type == 'inbound-rtp' && report.values['kind'] == 'video') {
        final packetsLost = report.values['packetsLost'] ?? 0;
        final packetsReceived = report.values['packetsReceived'] ?? 0;
        
        if (packetsReceived > 0) {
          final lossRate = packetsLost / (packetsLost + packetsReceived);
          print('Packet loss rate: ${(lossRate * 100).toStringAsFixed(2)}%');
        }
      }
    });
  }
});
```

### 3. Reconnection Logic

```dart
void setupReconnection() {
  peerConnection!.onConnectionState = (state) async {
    if (state == RTCPeerConnectionState.RTCPeerConnectionStateFailed ||
        state == RTCPeerConnectionState.RTCPeerConnectionStateDisconnected) {
      // Attempt reconnection
      await Future.delayed(Duration(seconds: 2));
      await _webRtcService.createOffer();
    }
  };
}
```

### 4. Permissions

Add to `android/app/src/main/AndroidManifest.xml`:

```xml
<uses-permission android:name="android.permission.CAMERA" />
<uses-permission android:name="android.permission.RECORD_AUDIO" />
<uses-permission android:name="android.permission.INTERNET" />
```

Add to `ios/Runner/Info.plist`:

```xml
<key>NSCameraUsageDescription</key>
<string>We need camera access for video calls</string>
<key>NSMicrophoneUsageDescription</key>
<string>We need microphone access for calls</string>
```

Request permissions before call:

```dart
import 'package:permission_handler/permission_handler.dart';

Future<bool> requestPermissions() async {
  final camera = await Permission.camera.request();
  final microphone = await Permission.microphone.request();
  
  return camera.isGranted && microphone.isGranted;
}
```

## Testing

### 1. Test on Multiple Devices

```dart
// Device 1
Navigator.push(
  context,
  MaterialPageRoute(
    builder: (context) => VideoCallScreen(
      serverUrl: 'http://192.168.1.100:8000',
      token: token1,
      roomId: 'test-room',
    ),
  ),
);

// Device 2 (same room)
Navigator.push(
  context,
  MaterialPageRoute(
    builder: (context) => VideoCallScreen(
      serverUrl: 'http://192.168.1.100:8000',
      token: token2,
      roomId: 'test-room',
    ),
  ),
);
```

### 2. Debug Logging

```dart
// Enable WebRTC logging
await WebRTC.enableLogging();
```

## Common Issues & Solutions

### Issue 1: Connection Timeout

**Solution**: Check STUN/TURN server configuration

```dart
// In backend .sbd file, add TURN server:
WEBRTC_TURN_URLS=turn:your-turn-server.com:3478
WEBRTC_TURN_USERNAME=username
WEBRTC_TURN_CREDENTIAL=password
```

### Issue 2: No Remote Stream

**Solution**: Ensure both peers create offer/answer correctly

```dart
// Check if remote description is set
print('Remote description: ${peerConnection!.getRemoteDescription()}');
```

### Issue 3: ICE Connection Failed

**Solution**: Check firewall/NAT settings, use TURN server

```dart
// Monitor ICE connection state
peerConnection!.onIceConnectionState = (state) {
  print('ICE connection state: $state');
  if (state == RTCIceConnectionState.RTCIceConnectionStateFailed) {
    // Use TURN server
  }
};
```

## Complete Example Repository

Check the example in: `examples/flutter_webrtc_example/`

## Next Steps

1. Implement group calls (mesh or SFU topology)
2. Add call recording
3. Implement chat during calls
4. Add virtual backgrounds
5. Implement call quality indicators

## Support

For issues, check:
- Backend logs: WebRTC router logs
- Flutter logs: Enable WebRTC debug logging
- Network: Verify firewall/NAT configuration
- Documentation: `docs/WEBRTC_IMPLEMENTATION.md`

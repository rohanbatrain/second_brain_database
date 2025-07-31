# Flutter User Agent Lockdown Integration Guide

## Overview

This guide provides comprehensive instructions for integrating User Agent lockdown functionality into your Flutter application. User Agent lockdown allows users to restrict API access to only trusted devices/applications by validating the User Agent string.

## Table of Contents

1. [API Endpoints](#api-endpoints)
2. [Flutter HTTP Client Setup](#flutter-http-client-setup)
3. [User Agent Detection](#user-agent-detection)
4. [API Service Implementation](#api-service-implementation)
5. [UI Components](#ui-components)
6. [State Management](#state-management)
7. [Error Handling](#error-handling)
8. [Testing](#testing)
9. [Security Considerations](#security-considerations)

## API Endpoints

### Base URL
```
https://your-api-domain.com/auth
```

### Available Endpoints

#### 1. Get Lockdown Status
```http
GET /trusted-user-agents/lockdown-status
Authorization: Bearer <jwt_token>
```

**Response:**
```json
{
  "trusted_user_agent_lockdown": true,
  "your_user_agent": "YourApp/1.0.0 (Flutter; Android 12)"
}
```

#### 2. Request Lockdown Change
```http
POST /trusted-user-agents/lockdown-request
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "action": "enable",
  "trusted_user_agents": [
    "YourApp/1.0.0 (Flutter; Android 12)",
    "YourApp/1.0.0 (Flutter; iOS 15.0)"
  ]
}
```

**Response:**
```json
{
  "message": "Confirmation code sent to your email",
  "code_expires_in": 600
}
```

#### 3. Confirm Lockdown Change
```http
POST /trusted-user-agents/lockdown-confirm
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "code": "ABC123"
}
```

**Response:**
```json
{
  "message": "User Agent lockdown enabled successfully",
  "trusted_user_agent_lockdown": true,
  "trusted_user_agents": [
    "YourApp/1.0.0 (Flutter; Android 12)",
    "YourApp/1.0.0 (Flutter; iOS 15.0)"
  ]
}
```

## Flutter HTTP Client Setup

### 1. Dependencies

Add these dependencies to your `pubspec.yaml`:

```yaml
dependencies:
  http: ^1.1.0
  device_info_plus: ^9.1.0
  package_info_plus: ^4.2.0
  shared_preferences: ^2.2.2
```

### 2. User Agent Generation

Create a service to generate consistent User Agent strings:

```dart
// lib/services/user_agent_service.dart
import 'dart:io';
import 'package:device_info_plus/device_info_plus.dart';
import 'package:package_info_plus/package_info_plus.dart';

class UserAgentService {
  static String? _cachedUserAgent;
  
  static Future<String> getUserAgent() async {
    if (_cachedUserAgent != null) {
      return _cachedUserAgent!;
    }
    
    final packageInfo = await PackageInfo.fromPlatform();
    final deviceInfo = DeviceInfoPlugin();
    
    String platformInfo;
    
    if (Platform.isAndroid) {
      final androidInfo = await deviceInfo.androidInfo;
      platformInfo = 'Flutter; Android ${androidInfo.version.release}; ${androidInfo.model}';
    } else if (Platform.isIOS) {
      final iosInfo = await deviceInfo.iosInfo;
      platformInfo = 'Flutter; iOS ${iosInfo.systemVersion}; ${iosInfo.model}';
    } else if (Platform.isWindows) {
      final windowsInfo = await deviceInfo.windowsInfo;
      platformInfo = 'Flutter; Windows ${windowsInfo.displayVersion}';
    } else if (Platform.isMacOS) {
      final macInfo = await deviceInfo.macOsInfo;
      platformInfo = 'Flutter; macOS ${macInfo.osRelease}';
    } else if (Platform.isLinux) {
      final linuxInfo = await deviceInfo.linuxInfo;
      platformInfo = 'Flutter; Linux ${linuxInfo.prettyName}';
    } else {
      platformInfo = 'Flutter; Unknown Platform';
    }
    
    _cachedUserAgent = '${packageInfo.appName}/${packageInfo.version} ($platformInfo)';
    return _cachedUserAgent!;
  }
  
  static void clearCache() {
    _cachedUserAgent = null;
  }
}
```

### 3. HTTP Client with User Agent

Create an HTTP client that automatically includes the User Agent:

```dart
// lib/services/api_client.dart
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'user_agent_service.dart';

class ApiClient {
  static const String baseUrl = 'https://your-api-domain.com';
  static String? _authToken;
  
  static void setAuthToken(String token) {
    _authToken = token;
  }
  
  static Future<Map<String, String>> _getHeaders() async {
    final userAgent = await UserAgentService.getUserAgent();
    final headers = {
      'Content-Type': 'application/json',
      'User-Agent': userAgent,
    };
    
    if (_authToken != null) {
      headers['Authorization'] = 'Bearer $_authToken';
    }
    
    return headers;
  }
  
  static Future<http.Response> get(String endpoint) async {
    final headers = await _getHeaders();
    final uri = Uri.parse('$baseUrl$endpoint');
    
    return await http.get(uri, headers: headers);
  }
  
  static Future<http.Response> post(String endpoint, Map<String, dynamic> body) async {
    final headers = await _getHeaders();
    final uri = Uri.parse('$baseUrl$endpoint');
    
    return await http.post(
      uri,
      headers: headers,
      body: jsonEncode(body),
    );
  }
}
```

## API Service Implementation

### User Agent Lockdown Service

```dart
// lib/services/user_agent_lockdown_service.dart
import 'dart:convert';
import 'api_client.dart';
import 'user_agent_service.dart';

class UserAgentLockdownService {
  
  // Get current lockdown status
  static Future<UserAgentLockdownStatus> getLockdownStatus() async {
    try {
      final response = await ApiClient.get('/auth/trusted-user-agents/lockdown-status');
      
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return UserAgentLockdownStatus.fromJson(data);
      } else if (response.statusCode == 403) {
        throw UserAgentLockdownException('Access denied. Your device may not be trusted.');
      } else {
        throw UserAgentLockdownException('Failed to get lockdown status: ${response.statusCode}');
      }
    } catch (e) {
      throw UserAgentLockdownException('Network error: $e');
    }
  }
  
  // Request to enable/disable lockdown
  static Future<LockdownRequestResponse> requestLockdownChange({
    required String action, // 'enable' or 'disable'
    List<String>? trustedUserAgents,
  }) async {
    try {
      final body = <String, dynamic>{
        'action': action,
      };
      
      if (trustedUserAgents != null) {
        body['trusted_user_agents'] = trustedUserAgents;
      }
      
      final response = await ApiClient.post('/auth/trusted-user-agents/lockdown-request', body);
      
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return LockdownRequestResponse.fromJson(data);
      } else {
        final errorData = jsonDecode(response.body);
        throw UserAgentLockdownException(errorData['detail'] ?? 'Request failed');
      }
    } catch (e) {
      throw UserAgentLockdownException('Network error: $e');
    }
  }
  
  // Confirm lockdown change with code
  static Future<LockdownConfirmResponse> confirmLockdownChange(String code) async {
    try {
      final body = {'code': code};
      final response = await ApiClient.post('/auth/trusted-user-agents/lockdown-confirm', body);
      
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return LockdownConfirmResponse.fromJson(data);
      } else {
        final errorData = jsonDecode(response.body);
        throw UserAgentLockdownException(errorData['detail'] ?? 'Confirmation failed');
      }
    } catch (e) {
      throw UserAgentLockdownException('Network error: $e');
    }
  }
  
  // Get current device's User Agent
  static Future<String> getCurrentUserAgent() async {
    return await UserAgentService.getUserAgent();
  }
  
  // Generate suggested trusted User Agents for common platforms
  static Future<List<String>> getSuggestedTrustedUserAgents() async {
    final currentUA = await UserAgentService.getUserAgent();
    final suggestions = <String>[currentUA];
    
    // Add variations for different platforms if needed
    final packageInfo = await PackageInfo.fromPlatform();
    final appName = packageInfo.appName;
    final version = packageInfo.version;
    
    // Common platform variations
    suggestions.addAll([
      '$appName/$version (Flutter; Android 12)',
      '$appName/$version (Flutter; Android 13)',
      '$appName/$version (Flutter; iOS 15.0)',
      '$appName/$version (Flutter; iOS 16.0)',
      '$appName/$version (Flutter; Windows 11)',
      '$appName/$version (Flutter; macOS 13.0)',
    ]);
    
    // Remove duplicates and return
    return suggestions.toSet().toList();
  }
}

// Data Models
class UserAgentLockdownStatus {
  final bool trustedUserAgentLockdown;
  final String yourUserAgent;
  
  UserAgentLockdownStatus({
    required this.trustedUserAgentLockdown,
    required this.yourUserAgent,
  });
  
  factory UserAgentLockdownStatus.fromJson(Map<String, dynamic> json) {
    return UserAgentLockdownStatus(
      trustedUserAgentLockdown: json['trusted_user_agent_lockdown'] ?? false,
      yourUserAgent: json['your_user_agent'] ?? '',
    );
  }
}

class LockdownRequestResponse {
  final String message;
  final int codeExpiresIn;
  
  LockdownRequestResponse({
    required this.message,
    required this.codeExpiresIn,
  });
  
  factory LockdownRequestResponse.fromJson(Map<String, dynamic> json) {
    return LockdownRequestResponse(
      message: json['message'] ?? '',
      codeExpiresIn: json['code_expires_in'] ?? 600,
    );
  }
}

class LockdownConfirmResponse {
  final String message;
  final bool trustedUserAgentLockdown;
  final List<String> trustedUserAgents;
  
  LockdownConfirmResponse({
    required this.message,
    required this.trustedUserAgentLockdown,
    required this.trustedUserAgents,
  });
  
  factory LockdownConfirmResponse.fromJson(Map<String, dynamic> json) {
    return LockdownConfirmResponse(
      message: json['message'] ?? '',
      trustedUserAgentLockdown: json['trusted_user_agent_lockdown'] ?? false,
      trustedUserAgents: List<String>.from(json['trusted_user_agents'] ?? []),
    );
  }
}

class UserAgentLockdownException implements Exception {
  final String message;
  UserAgentLockdownException(this.message);
  
  @override
  String toString() => 'UserAgentLockdownException: $message';
}
```

## UI Components

### 1. User Agent Lockdown Settings Screen

```dart
// lib/screens/user_agent_lockdown_screen.dart
import 'package:flutter/material.dart';
import '../services/user_agent_lockdown_service.dart';

class UserAgentLockdownScreen extends StatefulWidget {
  @override
  _UserAgentLockdownScreenState createState() => _UserAgentLockdownScreenState();
}

class _UserAgentLockdownScreenState extends State<UserAgentLockdownScreen> {
  bool _isLoading = true;
  bool _isLockdownEnabled = false;
  String _currentUserAgent = '';
  List<String> _trustedUserAgents = [];
  List<String> _selectedUserAgents = [];
  
  @override
  void initState() {
    super.initState();
    _loadLockdownStatus();
  }
  
  Future<void> _loadLockdownStatus() async {
    try {
      setState(() => _isLoading = true);
      
      final status = await UserAgentLockdownService.getLockdownStatus();
      final currentUA = await UserAgentLockdownService.getCurrentUserAgent();
      
      setState(() {
        _isLockdownEnabled = status.trustedUserAgentLockdown;
        _currentUserAgent = currentUA;
        _isLoading = false;
      });
    } catch (e) {
      setState(() => _isLoading = false);
      _showErrorDialog('Failed to load lockdown status: $e');
    }
  }
  
  Future<void> _toggleLockdown() async {
    if (_isLockdownEnabled) {
      _disableLockdown();
    } else {
      _showEnableLockdownDialog();
    }
  }
  
  void _showEnableLockdownDialog() async {
    final suggestions = await UserAgentLockdownService.getSuggestedTrustedUserAgents();
    
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Enable User Agent Lockdown'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Select trusted User Agents that will be allowed to access your account:'),
            SizedBox(height: 16),
            Container(
              height: 200,
              child: ListView.builder(
                itemCount: suggestions.length,
                itemBuilder: (context, index) {
                  final ua = suggestions[index];
                  return CheckboxListTile(
                    title: Text(ua, style: TextStyle(fontSize: 12)),
                    value: _selectedUserAgents.contains(ua),
                    onChanged: (selected) {
                      setState(() {
                        if (selected == true) {
                          _selectedUserAgents.add(ua);
                        } else {
                          _selectedUserAgents.remove(ua);
                        }
                      });
                    },
                  );
                },
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: _selectedUserAgents.isEmpty ? null : () {
              Navigator.pop(context);
              _enableLockdown();
            },
            child: Text('Enable'),
          ),
        ],
      ),
    );
  }
  
  Future<void> _enableLockdown() async {
    try {
      final response = await UserAgentLockdownService.requestLockdownChange(
        action: 'enable',
        trustedUserAgents: _selectedUserAgents,
      );
      
      _showConfirmationDialog(response.message);
    } catch (e) {
      _showErrorDialog('Failed to enable lockdown: $e');
    }
  }
  
  Future<void> _disableLockdown() async {
    try {
      final response = await UserAgentLockdownService.requestLockdownChange(
        action: 'disable',
      );
      
      _showConfirmationDialog(response.message);
    } catch (e) {
      _showErrorDialog('Failed to disable lockdown: $e');
    }
  }
  
  void _showConfirmationDialog(String message) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Confirmation Required'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(message),
            SizedBox(height: 16),
            TextField(
              decoration: InputDecoration(
                labelText: 'Confirmation Code',
                hintText: 'Enter code from email',
              ),
              onSubmitted: _confirmLockdownChange,
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () {
              // Get code from TextField and confirm
              Navigator.pop(context);
            },
            child: Text('Confirm'),
          ),
        ],
      ),
    );
  }
  
  Future<void> _confirmLockdownChange(String code) async {
    try {
      final response = await UserAgentLockdownService.confirmLockdownChange(code);
      
      setState(() {
        _isLockdownEnabled = response.trustedUserAgentLockdown;
        _trustedUserAgents = response.trustedUserAgents;
      });
      
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(response.message)),
      );
    } catch (e) {
      _showErrorDialog('Confirmation failed: $e');
    }
  }
  
  void _showErrorDialog(String message) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Error'),
        content: Text(message),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: Text('OK'),
          ),
        ],
      ),
    );
  }
  
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('User Agent Lockdown'),
      ),
      body: _isLoading
          ? Center(child: CircularProgressIndicator())
          : Padding(
              padding: EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Card(
                    child: Padding(
                      padding: EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'User Agent Lockdown',
                            style: Theme.of(context).textTheme.headlineSmall,
                          ),
                          SizedBox(height: 8),
                          Text(
                            'Restrict API access to only trusted devices and applications.',
                            style: Theme.of(context).textTheme.bodyMedium,
                          ),
                          SizedBox(height: 16),
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Text('Status: ${_isLockdownEnabled ? "Enabled" : "Disabled"}'),
                              Switch(
                                value: _isLockdownEnabled,
                                onChanged: (_) => _toggleLockdown(),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                  ),
                  SizedBox(height: 16),
                  Card(
                    child: Padding(
                      padding: EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Current Device User Agent',
                            style: Theme.of(context).textTheme.titleMedium,
                          ),
                          SizedBox(height: 8),
                          Container(
                            padding: EdgeInsets.all(12),
                            decoration: BoxDecoration(
                              color: Colors.grey[100],
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: Text(
                              _currentUserAgent,
                              style: TextStyle(
                                fontFamily: 'monospace',
                                fontSize: 12,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                  if (_trustedUserAgents.isNotEmpty) ...[
                    SizedBox(height: 16),
                    Card(
                      child: Padding(
                        padding: EdgeInsets.all(16),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'Trusted User Agents',
                              style: Theme.of(context).textTheme.titleMedium,
                            ),
                            SizedBox(height: 8),
                            ..._trustedUserAgents.map((ua) => Padding(
                              padding: EdgeInsets.symmetric(vertical: 4),
                              child: Text(
                                '• $ua',
                                style: TextStyle(fontSize: 12),
                              ),
                            )),
                          ],
                        ),
                      ),
                    ),
                  ],
                ],
              ),
            ),
    );
  }
}
```

### 2. User Agent Info Widget

```dart
// lib/widgets/user_agent_info_widget.dart
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../services/user_agent_service.dart';

class UserAgentInfoWidget extends StatefulWidget {
  @override
  _UserAgentInfoWidgetState createState() => _UserAgentInfoWidgetState();
}

class _UserAgentInfoWidgetState extends State<UserAgentInfoWidget> {
  String _userAgent = 'Loading...';
  
  @override
  void initState() {
    super.initState();
    _loadUserAgent();
  }
  
  Future<void> _loadUserAgent() async {
    final ua = await UserAgentService.getUserAgent();
    setState(() => _userAgent = ua);
  }
  
  void _copyToClipboard() {
    Clipboard.setData(ClipboardData(text: _userAgent));
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('User Agent copied to clipboard')),
    );
  }
  
  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'Your User Agent',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                IconButton(
                  icon: Icon(Icons.copy),
                  onPressed: _copyToClipboard,
                  tooltip: 'Copy to clipboard',
                ),
              ],
            ),
            SizedBox(height: 8),
            Container(
              width: double.infinity,
              padding: EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.grey[100],
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: Colors.grey[300]!),
              ),
              child: Text(
                _userAgent,
                style: TextStyle(
                  fontFamily: 'monospace',
                  fontSize: 12,
                ),
              ),
            ),
            SizedBox(height: 8),
            Text(
              'This is how your device identifies itself to the server. '
              'Add this to your trusted User Agents to allow access from this device.',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ),
      ),
    );
  }
}
```

## State Management

### Using Provider for State Management

```dart
// lib/providers/user_agent_lockdown_provider.dart
import 'package:flutter/foundation.dart';
import '../services/user_agent_lockdown_service.dart';

class UserAgentLockdownProvider extends ChangeNotifier {
  bool _isLockdownEnabled = false;
  String _currentUserAgent = '';
  List<String> _trustedUserAgents = [];
  bool _isLoading = false;
  String? _error;
  
  bool get isLockdownEnabled => _isLockdownEnabled;
  String get currentUserAgent => _currentUserAgent;
  List<String> get trustedUserAgents => _trustedUserAgents;
  bool get isLoading => _isLoading;
  String? get error => _error;
  
  Future<void> loadLockdownStatus() async {
    _setLoading(true);
    _clearError();
    
    try {
      final status = await UserAgentLockdownService.getLockdownStatus();
      final currentUA = await UserAgentLockdownService.getCurrentUserAgent();
      
      _isLockdownEnabled = status.trustedUserAgentLockdown;
      _currentUserAgent = currentUA;
      
      notifyListeners();
    } catch (e) {
      _setError(e.toString());
    } finally {
      _setLoading(false);
    }
  }
  
  Future<bool> enableLockdown(List<String> trustedUserAgents) async {
    _setLoading(true);
    _clearError();
    
    try {
      await UserAgentLockdownService.requestLockdownChange(
        action: 'enable',
        trustedUserAgents: trustedUserAgents,
      );
      return true;
    } catch (e) {
      _setError(e.toString());
      return false;
    } finally {
      _setLoading(false);
    }
  }
  
  Future<bool> disableLockdown() async {
    _setLoading(true);
    _clearError();
    
    try {
      await UserAgentLockdownService.requestLockdownChange(action: 'disable');
      return true;
    } catch (e) {
      _setError(e.toString());
      return false;
    } finally {
      _setLoading(false);
    }
  }
  
  Future<bool> confirmLockdownChange(String code) async {
    _setLoading(true);
    _clearError();
    
    try {
      final response = await UserAgentLockdownService.confirmLockdownChange(code);
      
      _isLockdownEnabled = response.trustedUserAgentLockdown;
      _trustedUserAgents = response.trustedUserAgents;
      
      notifyListeners();
      return true;
    } catch (e) {
      _setError(e.toString());
      return false;
    } finally {
      _setLoading(false);
    }
  }
  
  void _setLoading(bool loading) {
    _isLoading = loading;
    notifyListeners();
  }
  
  void _setError(String error) {
    _error = error;
    notifyListeners();
  }
  
  void _clearError() {
    _error = null;
    notifyListeners();
  }
}
```

## Error Handling

### Custom Error Handler for User Agent Issues

```dart
// lib/utils/user_agent_error_handler.dart
import 'package:flutter/material.dart';
import '../services/user_agent_lockdown_service.dart';

class UserAgentErrorHandler {
  static void handleError(BuildContext context, dynamic error) {
    String message;
    String title = 'Error';
    List<Widget> actions = [
      TextButton(
        onPressed: () => Navigator.of(context).pop(),
        child: Text('OK'),
      ),
    ];
    
    if (error is UserAgentLockdownException) {
      if (error.message.contains('Access denied')) {
        title = 'Access Denied';
        message = 'Your device is not in the trusted User Agents list. '
                 'Please use a trusted device or contact support.';
        
        actions = [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.of(context).pop();
              _showUserAgentInfo(context);
            },
            child: Text('View My User Agent'),
          ),
        ];
      } else if (error.message.contains('rate limit')) {
        title = 'Rate Limited';
        message = 'Too many requests. Please wait before trying again.';
      } else {
        message = error.message;
      }
    } else {
      message = 'An unexpected error occurred: $error';
    }
    
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(title),
        content: Text(message),
        actions: actions,
      ),
    );
  }
  
  static void _showUserAgentInfo(BuildContext context) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Your User Agent'),
        content: FutureBuilder<String>(
          future: UserAgentLockdownService.getCurrentUserAgent(),
          builder: (context, snapshot) {
            if (snapshot.hasData) {
              return Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Your current User Agent:'),
                  SizedBox(height: 8),
                  Container(
                    padding: EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: Colors.grey[100],
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text(
                      snapshot.data!,
                      style: TextStyle(
                        fontFamily: 'monospace',
                        fontSize: 12,
                      ),
                    ),
                  ),
                  SizedBox(height: 8),
                  Text(
                    'Contact your administrator to add this User Agent to the trusted list.',
                    style: TextStyle(fontSize: 12),
                  ),
                ],
              );
            } else {
              return CircularProgressIndicator();
            }
          },
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: Text('Close'),
          ),
        ],
      ),
    );
  }
}
```

## Testing

### Unit Tests

```dart
// test/services/user_agent_lockdown_service_test.dart
import 'package:flutter_test/flutter_test.dart';
import 'package:mockito/mockito.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';

import 'package:your_app/services/user_agent_lockdown_service.dart';

class MockClient extends Mock implements http.Client {}

void main() {
  group('UserAgentLockdownService', () {
    late MockClient mockClient;
    
    setUp(() {
      mockClient = MockClient();
    });
    
    test('getLockdownStatus returns correct status', () async {
      // Arrange
      final responseBody = jsonEncode({
        'trusted_user_agent_lockdown': true,
        'your_user_agent': 'TestApp/1.0.0 (Flutter; Test)'
      });
      
      when(mockClient.get(any, headers: anyNamed('headers')))
          .thenAnswer((_) async => http.Response(responseBody, 200));
      
      // Act
      final status = await UserAgentLockdownService.getLockdownStatus();
      
      // Assert
      expect(status.trustedUserAgentLockdown, true);
      expect(status.yourUserAgent, 'TestApp/1.0.0 (Flutter; Test)');
    });
    
    test('requestLockdownChange sends correct data', () async {
      // Arrange
      final responseBody = jsonEncode({
        'message': 'Confirmation code sent',
        'code_expires_in': 600
      });
      
      when(mockClient.post(any, headers: anyNamed('headers'), body: anyNamed('body')))
          .thenAnswer((_) async => http.Response(responseBody, 200));
      
      // Act
      final response = await UserAgentLockdownService.requestLockdownChange(
        action: 'enable',
        trustedUserAgents: ['TestApp/1.0.0'],
      );
      
      // Assert
      expect(response.message, 'Confirmation code sent');
      expect(response.codeExpiresIn, 600);
    });
  });
}
```

### Widget Tests

```dart
// test/widgets/user_agent_info_widget_test.dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:your_app/widgets/user_agent_info_widget.dart';

void main() {
  testWidgets('UserAgentInfoWidget displays user agent', (WidgetTester tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: UserAgentInfoWidget(),
        ),
      ),
    );
    
    // Initially shows loading
    expect(find.text('Loading...'), findsOneWidget);
    
    // Wait for user agent to load
    await tester.pumpAndSettle();
    
    // Should show user agent info
    expect(find.text('Your User Agent'), findsOneWidget);
    expect(find.byIcon(Icons.copy), findsOneWidget);
  });
}
```

## Security Considerations

### 1. User Agent Spoofing
- User Agents can be easily spoofed by malicious actors
- Use User Agent lockdown as part of a layered security approach
- Combine with other security measures like IP lockdown, device fingerprinting

### 2. User Agent Consistency
- Ensure your app generates consistent User Agent strings
- Cache the User Agent to avoid variations between requests
- Consider app updates that might change the User Agent format

### 3. Error Handling
- Don't expose sensitive information in error messages
- Log security events for monitoring
- Provide clear guidance to users when access is denied

### 4. Backup Access
- Always provide alternative access methods (email confirmation, support contact)
- Consider temporary bypass mechanisms for legitimate users
- Implement proper account recovery procedures

## Best Practices

1. **User Experience**
   - Clearly explain what User Agent lockdown does
   - Provide easy ways to view and copy current User Agent
   - Show helpful error messages when access is denied

2. **Security**
   - Use HTTPS for all API communications
   - Implement proper token management
   - Log security events for monitoring

3. **Maintenance**
   - Handle app updates that might change User Agent format
   - Provide migration paths for existing users
   - Monitor for common User Agent patterns

4. **Testing**
   - Test on all target platforms
   - Verify User Agent consistency across app versions
   - Test error scenarios and recovery flows

## Conclusion

This guide provides a comprehensive foundation for integrating User Agent lockdown functionality into your Flutter application. Remember to adapt the code examples to your specific architecture and requirements, and always test thoroughly across all target platforms.

For additional security, consider combining User Agent lockdown with other authentication factors and monitoring systems.
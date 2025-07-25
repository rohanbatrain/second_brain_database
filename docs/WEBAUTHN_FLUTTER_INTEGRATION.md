# WebAuthn Flutter Integration Guide

This comprehensive guide helps Flutter developers integrate with the Second Brain Database WebAuthn/FIDO2 passkey implementation for passwordless authentication.

> **📋 Quick Reference**: This is the complete Flutter integration guide. For API-only documentation, see the [WebAuthn API Specification](.kiro/specs/webauthn-fido2-auth/design.md).

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Flutter Dependencies](#flutter-dependencies)
4. [API Endpoints](#api-endpoints)
5. [Implementation Guide](#implementation-guide)
6. [Code Examples](#code-examples)
7. [Error Handling](#error-handling)
8. [Testing](#testing)
9. [Security Considerations](#security-considerations)
10. [Troubleshooting](#troubleshooting)

## Overview

The Second Brain Database provides a complete WebAuthn/FIDO2 implementation optimized for Flutter mobile applications. This enables passwordless authentication using:

- **Platform Authenticators**: Biometrics (fingerprint, face recognition, voice)
- **Cross-Platform Authenticators**: Hardware security keys (USB, NFC, Bluetooth)
- **Hybrid Transport**: QR code and proximity-based authentication

### Key Features

- ✅ **Flutter-Optimized**: API responses designed for mobile parsing
- ✅ **Dual Authentication**: Works alongside password authentication
- ✅ **JWT Integration**: Seamless token-based authentication
- ✅ **Comprehensive Logging**: Full audit trail and monitoring
- ✅ **Error Handling**: Flutter-friendly error codes and messages
- ✅ **Caching**: Redis-based performance optimization

## Prerequisites

### Server Requirements

- Second Brain Database API running with WebAuthn enabled
- HTTPS connection (required for WebAuthn)
- Valid domain or localhost for development

### Flutter Requirements

- Flutter 3.0+ 
- Dart 2.17+
- Android API level 23+ (Android 6.0+)
- iOS 14.0+

## Flutter Dependencies

Add these dependencies to your `pubspec.yaml`:

```yaml
dependencies:
  # WebAuthn support
  webauthn: ^0.2.0
  
  # HTTP client
  dio: ^5.3.0
  
  # Secure storage
  flutter_secure_storage: ^9.0.0
  
  # JSON handling
  json_annotation: ^4.8.1
  
  # State management (choose one)
  provider: ^6.0.5
  # OR
  bloc: ^8.1.2
  
dev_dependencies:
  # Code generation
  json_serializable: ^6.7.1
  build_runner: ^2.4.7
```

### Platform Configuration

#### Android (`android/app/src/main/AndroidManifest.xml`)

```xml
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <!-- WebAuthn permissions -->
    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.USE_FINGERPRINT" />
    <uses-permission android:name="android.permission.USE_BIOMETRIC" />
    
    <application>
        <!-- Enable hardware security key support -->
        <meta-data
            android:name="android.hardware.fido.uaf"
            android:value="true" />
    </application>
</manifest>
```

#### iOS (`ios/Runner/Info.plist`)

```xml
<dict>
    <!-- Face ID usage description -->
    <key>NSFaceIDUsageDescription</key>
    <string>Use Face ID to authenticate with your passkey</string>
    
    <!-- Associated domains for WebAuthn -->
    <key>com.apple.developer.associated-domains</key>
    <array>
        <string>webcredentials:yourdomain.com</string>
    </array>
</dict>
```

## API Endpoints

### Base URL
```
https://your-api-domain.com/auth/webauthn
```

### Authentication Flow

#### 1. Begin Authentication
```http
POST /auth/webauthn/authenticate/begin
Content-Type: application/json

{
  "username": "user@example.com"  // or email
}
```

**Response:**
```json
{
  "publicKey": {
    "challenge": "base64url-encoded-challenge",
    "timeout": 60000,
    "rpId": "yourdomain.com",
    "allowCredentials": [
      {
        "id": "credential-id",
        "type": "public-key",
        "transports": ["internal", "usb", "nfc", "ble"]
      }
    ],
    "userVerification": "preferred"
  },
  "username": "username",
  "email": "user@example.com"
}
```

#### 2. Complete Authentication
```http
POST /auth/webauthn/authenticate/complete
Content-Type: application/json

{
  "id": "credential-id",
  "rawId": "base64url-encoded-raw-id",
  "response": {
    "authenticatorData": "base64url-encoded-auth-data",
    "clientDataJSON": "base64url-encoded-client-data",
    "signature": "base64url-encoded-signature",
    "userHandle": "base64url-encoded-user-handle"
  },
  "type": "public-key"
}
```

**Response:**
```json
{
  "access_token": "jwt-token",
  "token_type": "bearer",
  "client_side_encryption": false,
  "issued_at": 1640995200,
  "expires_at": 1641081600,
  "is_verified": true,
  "role": "user",
  "username": "username",
  "email": "user@example.com",
  "authentication_method": "webauthn",
  "credential_used": {
    "credential_id": "credential-id",
    "device_name": "iPhone 15 Pro",
    "authenticator_type": "platform"
  }
}
```

### Registration Flow

#### 1. Begin Registration (Requires Authentication)
```http
POST /auth/webauthn/register/begin
Authorization: Bearer jwt-token
Content-Type: application/json

{
  "device_name": "My iPhone"  // optional
}
```

**Response:**
```json
{
  "challenge": "base64url-encoded-challenge",
  "rp": {
    "name": "Second Brain Database",
    "id": "yourdomain.com"
  },
  "user": {
    "id": "base64url-encoded-user-id",
    "name": "user@example.com",
    "displayName": "username"
  },
  "pubKeyCredParams": [
    {"alg": -7, "type": "public-key"},
    {"alg": -257, "type": "public-key"}
  ],
  "authenticatorSelection": {
    "authenticatorAttachment": "platform",
    "userVerification": "preferred",
    "residentKey": "preferred"
  },
  "attestation": "none",
  "excludeCredentials": [],
  "timeout": 300000
}
```

#### 2. Complete Registration (Requires Authentication)
```http
POST /auth/webauthn/register/complete
Authorization: Bearer jwt-token
Content-Type: application/json

{
  "id": "credential-id",
  "rawId": "base64url-encoded-raw-id",
  "response": {
    "attestationObject": "base64url-encoded-attestation",
    "clientDataJSON": "base64url-encoded-client-data",
    "transports": ["internal"]
  },
  "type": "public-key"
}
```

### Credential Management

#### List Credentials
```http
GET /auth/webauthn/credentials
Authorization: Bearer jwt-token
```

#### Delete Credential
```http
DELETE /auth/webauthn/credentials/{credential_id}
Authorization: Bearer jwt-token
```

## Implementation Guide

### 1. Create Data Models

```dart
// lib/models/webauthn_models.dart
import 'package:json_annotation/json_annotation.dart';

part 'webauthn_models.g.dart';

@JsonSerializable()
class WebAuthnAuthBeginRequest {
  final String? username;
  final String? email;

  WebAuthnAuthBeginRequest({this.username, this.email});

  factory WebAuthnAuthBeginRequest.fromJson(Map<String, dynamic> json) =>
      _$WebAuthnAuthBeginRequestFromJson(json);
  Map<String, dynamic> toJson() => _$WebAuthnAuthBeginRequestToJson(this);
}

@JsonSerializable()
class WebAuthnCredentialDescriptor {
  final String id;
  final String type;
  final List<String> transports;

  WebAuthnCredentialDescriptor({
    required this.id,
    required this.type,
    required this.transports,
  });

  factory WebAuthnCredentialDescriptor.fromJson(Map<String, dynamic> json) =>
      _$WebAuthnCredentialDescriptorFromJson(json);
  Map<String, dynamic> toJson() => _$WebAuthnCredentialDescriptorToJson(this);
}

@JsonSerializable()
class WebAuthnPublicKeyCredentialRequestOptions {
  final String challenge;
  final int timeout;
  final String rpId;
  final List<WebAuthnCredentialDescriptor> allowCredentials;
  final String userVerification;

  WebAuthnPublicKeyCredentialRequestOptions({
    required this.challenge,
    required this.timeout,
    required this.rpId,
    required this.allowCredentials,
    required this.userVerification,
  });

  factory WebAuthnPublicKeyCredentialRequestOptions.fromJson(Map<String, dynamic> json) =>
      _$WebAuthnPublicKeyCredentialRequestOptionsFromJson(json);
  Map<String, dynamic> toJson() => _$WebAuthnPublicKeyCredentialRequestOptionsToJson(this);
}

@JsonSerializable()
class WebAuthnAuthBeginResponse {
  final WebAuthnPublicKeyCredentialRequestOptions publicKey;
  final String? username;
  final String? email;

  WebAuthnAuthBeginResponse({
    required this.publicKey,
    this.username,
    this.email,
  });

  factory WebAuthnAuthBeginResponse.fromJson(Map<String, dynamic> json) =>
      _$WebAuthnAuthBeginResponseFromJson(json);
  Map<String, dynamic> toJson() => _$WebAuthnAuthBeginResponseToJson(this);
}

@JsonSerializable()
class WebAuthnAuthCompleteRequest {
  final String id;
  final String rawId;
  final WebAuthnAuthenticatorAssertionResponse response;
  final String type;

  WebAuthnAuthCompleteRequest({
    required this.id,
    required this.rawId,
    required this.response,
    required this.type,
  });

  factory WebAuthnAuthCompleteRequest.fromJson(Map<String, dynamic> json) =>
      _$WebAuthnAuthCompleteRequestFromJson(json);
  Map<String, dynamic> toJson() => _$WebAuthnAuthCompleteRequestToJson(this);
}

@JsonSerializable()
class WebAuthnAuthenticatorAssertionResponse {
  final String authenticatorData;
  final String clientDataJSON;
  final String signature;
  final String? userHandle;

  WebAuthnAuthenticatorAssertionResponse({
    required this.authenticatorData,
    required this.clientDataJSON,
    required this.signature,
    this.userHandle,
  });

  factory WebAuthnAuthenticatorAssertionResponse.fromJson(Map<String, dynamic> json) =>
      _$WebAuthnAuthenticatorAssertionResponseFromJson(json);
  Map<String, dynamic> toJson() => _$WebAuthnAuthenticatorAssertionResponseToJson(this);
}

@JsonSerializable()
class WebAuthnAuthCompleteResponse {
  final String accessToken;
  final String tokenType;
  final bool clientSideEncryption;
  final int issuedAt;
  final int expiresAt;
  final bool isVerified;
  final String? role;
  final String? username;
  final String? email;
  final String authenticationMethod;
  final WebAuthnCredentialUsed credentialUsed;

  WebAuthnAuthCompleteResponse({
    required this.accessToken,
    required this.tokenType,
    required this.clientSideEncryption,
    required this.issuedAt,
    required this.expiresAt,
    required this.isVerified,
    this.role,
    this.username,
    this.email,
    required this.authenticationMethod,
    required this.credentialUsed,
  });

  factory WebAuthnAuthCompleteResponse.fromJson(Map<String, dynamic> json) =>
      _$WebAuthnAuthCompleteResponseFromJson(json);
  Map<String, dynamic> toJson() => _$WebAuthnAuthCompleteResponseToJson(this);
}

@JsonSerializable()
class WebAuthnCredentialUsed {
  final String credentialId;
  final String deviceName;
  final String authenticatorType;

  WebAuthnCredentialUsed({
    required this.credentialId,
    required this.deviceName,
    required this.authenticatorType,
  });

  factory WebAuthnCredentialUsed.fromJson(Map<String, dynamic> json) =>
      _$WebAuthnCredentialUsedFromJson(json);
  Map<String, dynamic> toJson() => _$WebAuthnCredentialUsedToJson(this);
}
```

### 2. Create WebAuthn Service

```dart
// lib/services/webauthn_service.dart
import 'dart:convert';
import 'dart:typed_data';
import 'package:dio/dio.dart';
import 'package:webauthn/webauthn.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import '../models/webauthn_models.dart';

class WebAuthnService {
  final Dio _dio;
  final FlutterSecureStorage _secureStorage;
  final String _baseUrl;

  WebAuthnService({
    required Dio dio,
    required FlutterSecureStorage secureStorage,
    required String baseUrl,
  }) : _dio = dio,
       _secureStorage = secureStorage,
       _baseUrl = baseUrl;

  /// Check if WebAuthn is supported on this device
  Future<bool> isWebAuthnSupported() async {
    try {
      return await WebAuthn.isSupported();
    } catch (e) {
      return false;
    }
  }

  /// Begin WebAuthn authentication
  Future<WebAuthnAuthBeginResponse> beginAuthentication({
    String? username,
    String? email,
  }) async {
    if (username == null && email == null) {
      throw ArgumentError('Either username or email must be provided');
    }

    final request = WebAuthnAuthBeginRequest(
      username: username,
      email: email,
    );

    try {
      final response = await _dio.post(
        '$_baseUrl/webauthn/authenticate/begin',
        data: request.toJson(),
      );

      return WebAuthnAuthBeginResponse.fromJson(response.data);
    } on DioException catch (e) {
      throw _handleDioException(e);
    }
  }

  /// Complete WebAuthn authentication
  Future<WebAuthnAuthCompleteResponse> completeAuthentication(
    WebAuthnAuthBeginResponse beginResponse,
  ) async {
    try {
      // Convert server response to WebAuthn format
      final credentialRequestOptions = PublicKeyCredentialRequestOptions(
        challenge: _base64UrlDecode(beginResponse.publicKey.challenge),
        timeout: Duration(milliseconds: beginResponse.publicKey.timeout),
        rpId: beginResponse.publicKey.rpId,
        allowCredentials: beginResponse.publicKey.allowCredentials
            .map((cred) => PublicKeyCredentialDescriptor(
                  type: PublicKeyCredentialType.publicKey,
                  id: _base64UrlDecode(cred.id),
                  transports: cred.transports
                      .map(_mapTransport)
                      .where((t) => t != null)
                      .cast<AuthenticatorTransport>()
                      .toList(),
                ))
            .toList(),
        userVerification: _mapUserVerification(beginResponse.publicKey.userVerification),
      );

      // Get assertion from authenticator
      final credential = await WebAuthn.getAssertion(credentialRequestOptions);

      // Prepare request for server
      final completeRequest = WebAuthnAuthCompleteRequest(
        id: credential.id,
        rawId: _base64UrlEncode(credential.rawId),
        response: WebAuthnAuthenticatorAssertionResponse(
          authenticatorData: _base64UrlEncode(credential.response.authenticatorData),
          clientDataJSON: _base64UrlEncode(credential.response.clientDataJSON),
          signature: _base64UrlEncode(credential.response.signature),
          userHandle: credential.response.userHandle != null
              ? _base64UrlEncode(credential.response.userHandle!)
              : null,
        ),
        type: 'public-key',
      );

      // Send to server
      final response = await _dio.post(
        '$_baseUrl/webauthn/authenticate/complete',
        data: completeRequest.toJson(),
      );

      final authResponse = WebAuthnAuthCompleteResponse.fromJson(response.data);

      // Store token securely
      await _secureStorage.write(
        key: 'access_token',
        value: authResponse.accessToken,
      );

      return authResponse;
    } on DioException catch (e) {
      throw _handleDioException(e);
    } catch (e) {
      throw WebAuthnException('Authentication failed: ${e.toString()}');
    }
  }

  /// Begin WebAuthn registration (requires existing authentication)
  Future<Map<String, dynamic>> beginRegistration({
    String? deviceName,
  }) async {
    final token = await _secureStorage.read(key: 'access_token');
    if (token == null) {
      throw WebAuthnException('Authentication required for registration');
    }

    try {
      final response = await _dio.post(
        '$_baseUrl/webauthn/register/begin',
        data: {'device_name': deviceName},
        options: Options(
          headers: {'Authorization': 'Bearer $token'},
        ),
      );

      return response.data;
    } on DioException catch (e) {
      throw _handleDioException(e);
    }
  }

  /// Complete WebAuthn registration
  Future<Map<String, dynamic>> completeRegistration(
    Map<String, dynamic> beginResponse,
  ) async {
    final token = await _secureStorage.read(key: 'access_token');
    if (token == null) {
      throw WebAuthnException('Authentication required for registration');
    }

    try {
      // Convert server response to WebAuthn format
      final credentialCreationOptions = PublicKeyCredentialCreationOptions(
        rp: RelyingPartyEntity(
          name: beginResponse['rp']['name'],
          id: beginResponse['rp']['id'],
        ),
        user: UserEntity(
          id: _base64UrlDecode(beginResponse['user']['id']),
          name: beginResponse['user']['name'],
          displayName: beginResponse['user']['displayName'],
        ),
        challenge: _base64UrlDecode(beginResponse['challenge']),
        pubKeyCredParams: (beginResponse['pubKeyCredParams'] as List)
            .map((param) => PublicKeyCredentialParameters(
                  type: PublicKeyCredentialType.publicKey,
                  alg: param['alg'],
                ))
            .toList(),
        timeout: Duration(milliseconds: beginResponse['timeout']),
        excludeCredentials: (beginResponse['excludeCredentials'] as List)
            .map((cred) => PublicKeyCredentialDescriptor(
                  type: PublicKeyCredentialType.publicKey,
                  id: _base64UrlDecode(cred['id']),
                  transports: (cred['transports'] as List<String>)
                      .map(_mapTransport)
                      .where((t) => t != null)
                      .cast<AuthenticatorTransport>()
                      .toList(),
                ))
            .toList(),
        authenticatorSelection: AuthenticatorSelectionCriteria(
          authenticatorAttachment: _mapAuthenticatorAttachment(
            beginResponse['authenticatorSelection']['authenticatorAttachment'],
          ),
          userVerification: _mapUserVerification(
            beginResponse['authenticatorSelection']['userVerification'],
          ),
          residentKey: _mapResidentKeyRequirement(
            beginResponse['authenticatorSelection']['residentKey'],
          ),
        ),
        attestation: _mapAttestationConveyancePreference(beginResponse['attestation']),
      );

      // Create credential
      final credential = await WebAuthn.createCredential(credentialCreationOptions);

      // Prepare request for server
      final completeRequest = {
        'id': credential.id,
        'rawId': _base64UrlEncode(credential.rawId),
        'response': {
          'attestationObject': _base64UrlEncode(credential.response.attestationObject),
          'clientDataJSON': _base64UrlEncode(credential.response.clientDataJSON),
          'transports': credential.response.transports?.map((t) => t.name).toList() ?? [],
        },
        'type': 'public-key',
      };

      // Send to server
      final response = await _dio.post(
        '$_baseUrl/webauthn/register/complete',
        data: completeRequest,
        options: Options(
          headers: {'Authorization': 'Bearer $token'},
        ),
      );

      return response.data;
    } on DioException catch (e) {
      throw _handleDioException(e);
    } catch (e) {
      throw WebAuthnException('Registration failed: ${e.toString()}');
    }
  }

  /// List user's WebAuthn credentials
  Future<List<Map<String, dynamic>>> listCredentials() async {
    final token = await _secureStorage.read(key: 'access_token');
    if (token == null) {
      throw WebAuthnException('Authentication required');
    }

    try {
      final response = await _dio.get(
        '$_baseUrl/webauthn/credentials',
        options: Options(
          headers: {'Authorization': 'Bearer $token'},
        ),
      );

      return List<Map<String, dynamic>>.from(response.data['credentials']);
    } on DioException catch (e) {
      throw _handleDioException(e);
    }
  }

  /// Delete a WebAuthn credential
  Future<void> deleteCredential(String credentialId) async {
    final token = await _secureStorage.read(key: 'access_token');
    if (token == null) {
      throw WebAuthnException('Authentication required');
    }

    try {
      await _dio.delete(
        '$_baseUrl/webauthn/credentials/$credentialId',
        options: Options(
          headers: {'Authorization': 'Bearer $token'},
        ),
      );
    } on DioException catch (e) {
      throw _handleDioException(e);
    }
  }

  // Helper methods for encoding/decoding
  Uint8List _base64UrlDecode(String input) {
    String normalized = input.replaceAll('-', '+').replaceAll('_', '/');
    while (normalized.length % 4 != 0) {
      normalized += '=';
    }
    return base64Decode(normalized);
  }

  String _base64UrlEncode(Uint8List input) {
    return base64Encode(input)
        .replaceAll('+', '-')
        .replaceAll('/', '_')
        .replaceAll('=', '');
  }

  // Helper methods for mapping enums
  UserVerificationRequirement _mapUserVerification(String value) {
    switch (value) {
      case 'required':
        return UserVerificationRequirement.required;
      case 'preferred':
        return UserVerificationRequirement.preferred;
      case 'discouraged':
        return UserVerificationRequirement.discouraged;
      default:
        return UserVerificationRequirement.preferred;
    }
  }

  AuthenticatorTransport? _mapTransport(String transport) {
    switch (transport) {
      case 'usb':
        return AuthenticatorTransport.usb;
      case 'nfc':
        return AuthenticatorTransport.nfc;
      case 'ble':
        return AuthenticatorTransport.ble;
      case 'internal':
        return AuthenticatorTransport.internal;
      default:
        return null;
    }
  }

  AuthenticatorAttachment? _mapAuthenticatorAttachment(String? value) {
    switch (value) {
      case 'platform':
        return AuthenticatorAttachment.platform;
      case 'cross-platform':
        return AuthenticatorAttachment.crossPlatform;
      default:
        return null;
    }
  }

  ResidentKeyRequirement _mapResidentKeyRequirement(String value) {
    switch (value) {
      case 'required':
        return ResidentKeyRequirement.required;
      case 'preferred':
        return ResidentKeyRequirement.preferred;
      case 'discouraged':
        return ResidentKeyRequirement.discouraged;
      default:
        return ResidentKeyRequirement.preferred;
    }
  }

  AttestationConveyancePreference _mapAttestationConveyancePreference(String value) {
    switch (value) {
      case 'none':
        return AttestationConveyancePreference.none;
      case 'indirect':
        return AttestationConveyancePreference.indirect;
      case 'direct':
        return AttestationConveyancePreference.direct;
      case 'enterprise':
        return AttestationConveyancePreference.enterprise;
      default:
        return AttestationConveyancePreference.none;
    }
  }

  WebAuthnException _handleDioException(DioException e) {
    if (e.response?.data != null && e.response!.data is Map) {
      final data = e.response!.data as Map<String, dynamic>;
      final detail = data['detail'] ?? 'Unknown error';
      final flutterCode = data['flutter_code'];
      
      return WebAuthnException(
        detail,
        statusCode: e.response!.statusCode,
        flutterCode: flutterCode,
      );
    }
    
    return WebAuthnException('Network error: ${e.message}');
  }
}

class WebAuthnException implements Exception {
  final String message;
  final int? statusCode;
  final String? flutterCode;

  WebAuthnException(this.message, {this.statusCode, this.flutterCode});

  @override
  String toString() => 'WebAuthnException: $message';
}
```

### 3. Create Authentication UI

```dart
// lib/screens/webauthn_auth_screen.dart
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/webauthn_service.dart';

class WebAuthnAuthScreen extends StatefulWidget {
  @override
  _WebAuthnAuthScreenState createState() => _WebAuthnAuthScreenState();
}

class _WebAuthnAuthScreenState extends State<WebAuthnAuthScreen> {
  final _identifierController = TextEditingController();
  bool _isLoading = false;
  bool _isWebAuthnSupported = false;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _checkWebAuthnSupport();
  }

  Future<void> _checkWebAuthnSupport() async {
    final webAuthnService = context.read<WebAuthnService>();
    final isSupported = await webAuthnService.isWebAuthnSupported();
    setState(() {
      _isWebAuthnSupported = isSupported;
    });
  }

  Future<void> _authenticateWithPasskey() async {
    if (_identifierController.text.isEmpty) {
      setState(() {
        _errorMessage = 'Please enter your username or email';
      });
      return;
    }

    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final webAuthnService = context.read<WebAuthnService>();
      
      // Begin authentication
      final beginResponse = await webAuthnService.beginAuthentication(
        username: _identifierController.text.contains('@') 
            ? null 
            : _identifierController.text,
        email: _identifierController.text.contains('@') 
            ? _identifierController.text 
            : null,
      );

      // Complete authentication
      final authResponse = await webAuthnService.completeAuthentication(beginResponse);

      // Navigate to main app
      Navigator.of(context).pushReplacementNamed('/dashboard');
      
    } on WebAuthnException catch (e) {
      setState(() {
        _errorMessage = _getErrorMessage(e);
      });
    } catch (e) {
      setState(() {
        _errorMessage = 'Authentication failed: ${e.toString()}';
      });
    } finally {
      setState(() {
        _isLoading = false;
      });
    }
  }

  String _getErrorMessage(WebAuthnException e) {
    switch (e.flutterCode) {
      case 'CHALLENGE_EXPIRED':
        return 'Authentication session expired. Please try again.';
      case 'USER_NOT_FOUND':
        return 'User not found. Please check your username or email.';
      case 'NO_CREDENTIALS':
        return 'No passkeys found. Please set up a passkey first.';
      case 'CREDENTIAL_NOT_FOUND':
        return 'Passkey not recognized. Please try a different device.';
      case 'USER_CANCELLED':
        return 'Authentication was cancelled.';
      default:
        return e.message;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('Sign In with Passkey'),
      ),
      body: Padding(
        padding: EdgeInsets.all(16.0),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            if (!_isWebAuthnSupported) ...[
              Card(
                color: Colors.orange[50],
                child: Padding(
                  padding: EdgeInsets.all(16.0),
                  child: Column(
                    children: [
                      Icon(Icons.warning, color: Colors.orange, size: 48),
                      SizedBox(height: 16),
                      Text(
                        'Passkeys Not Supported',
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                      SizedBox(height: 8),
                      Text(
                        'Your device doesn\'t support passkeys. Please use password authentication or update your device.',
                        textAlign: TextAlign.center,
                      ),
                    ],
                  ),
                ),
              ),
              SizedBox(height: 24),
            ],
            
            Card(
              child: Padding(
                padding: EdgeInsets.all(16.0),
                child: Column(
                  children: [
                    Icon(
                      Icons.fingerprint,
                      size: 64,
                      color: Theme.of(context).primaryColor,
                    ),
                    SizedBox(height: 16),
                    Text(
                      'Sign in with your passkey',
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                    SizedBox(height: 8),
                    Text(
                      'Use your biometric or security key to sign in securely',
                      textAlign: TextAlign.center,
                      style: Theme.of(context).textTheme.bodyMedium,
                    ),
                    SizedBox(height: 24),
                    
                    TextField(
                      controller: _identifierController,
                      decoration: InputDecoration(
                        labelText: 'Username or Email',
                        border: OutlineInputBorder(),
                        prefixIcon: Icon(Icons.person),
                      ),
                      keyboardType: TextInputType.emailAddress,
                      textInputAction: TextInputAction.done,
                      onSubmitted: (_) => _authenticateWithPasskey(),
                    ),
                    
                    if (_errorMessage != null) ...[
                      SizedBox(height: 16),
                      Container(
                        padding: EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: Colors.red[50],
                          border: Border.all(color: Colors.red[200]!),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Row(
                          children: [
                            Icon(Icons.error, color: Colors.red),
                            SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                _errorMessage!,
                                style: TextStyle(color: Colors.red[700]),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                    
                    SizedBox(height: 24),
                    
                    SizedBox(
                      width: double.infinity,
                      child: ElevatedButton.icon(
                        onPressed: _isWebAuthnSupported && !_isLoading 
                            ? _authenticateWithPasskey 
                            : null,
                        icon: _isLoading 
                            ? SizedBox(
                                width: 20,
                                height: 20,
                                child: CircularProgressIndicator(strokeWidth: 2),
                              )
                            : Icon(Icons.fingerprint),
                        label: Text(_isLoading ? 'Authenticating...' : 'Sign In with Passkey'),
                        style: ElevatedButton.styleFrom(
                          padding: EdgeInsets.symmetric(vertical: 16),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            
            SizedBox(height: 24),
            
            TextButton(
              onPressed: () {
                Navigator.of(context).pushNamed('/password-login');
              },
              child: Text('Use password instead'),
            ),
          ],
        ),
      ),
    );
  }

  @override
  void dispose() {
    _identifierController.dispose();
    super.dispose();
  }
}
```

### 4. Create Registration UI

```dart
// lib/screens/webauthn_setup_screen.dart
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/webauthn_service.dart';

class WebAuthnSetupScreen extends StatefulWidget {
  @override
  _WebAuthnSetupScreenState createState() => _WebAuthnSetupScreenState();
}

class _WebAuthnSetupScreenState extends State<WebAuthnSetupScreen> {
  final _deviceNameController = TextEditingController();
  bool _isLoading = false;
  bool _isWebAuthnSupported = false;
  String? _errorMessage;
  String? _successMessage;
  List<Map<String, dynamic>> _credentials = [];

  @override
  void initState() {
    super.initState();
    _checkWebAuthnSupport();
    _loadCredentials();
  }

  Future<void> _checkWebAuthnSupport() async {
    final webAuthnService = context.read<WebAuthnService>();
    final isSupported = await webAuthnService.isWebAuthnSupported();
    setState(() {
      _isWebAuthnSupported = isSupported;
    });
  }

  Future<void> _loadCredentials() async {
    try {
      final webAuthnService = context.read<WebAuthnService>();
      final credentials = await webAuthnService.listCredentials();
      setState(() {
        _credentials = credentials;
      });
    } catch (e) {
      // Handle error silently for now
    }
  }

  Future<void> _registerPasskey() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
      _successMessage = null;
    });

    try {
      final webAuthnService = context.read<WebAuthnService>();
      
      // Begin registration
      final beginResponse = await webAuthnService.beginRegistration(
        deviceName: _deviceNameController.text.isNotEmpty 
            ? _deviceNameController.text 
            : null,
      );

      // Complete registration
      final result = await webAuthnService.completeRegistration(beginResponse);

      setState(() {
        _successMessage = 'Passkey registered successfully!';
        _deviceNameController.clear();
      });

      // Reload credentials
      await _loadCredentials();
      
    } on WebAuthnException catch (e) {
      setState(() {
        _errorMessage = _getErrorMessage(e);
      });
    } catch (e) {
      setState(() {
        _errorMessage = 'Registration failed: ${e.toString()}';
      });
    } finally {
      setState(() {
        _isLoading = false;
      });
    }
  }

  Future<void> _deleteCredential(String credentialId, String deviceName) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Delete Passkey'),
        content: Text('Are you sure you want to delete the passkey for "$deviceName"? This action cannot be undone.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: Text('Delete'),
            style: TextButton.styleFrom(foregroundColor: Colors.red),
          ),
        ],
      ),
    );

    if (confirmed == true) {
      try {
        final webAuthnService = context.read<WebAuthnService>();
        await webAuthnService.deleteCredential(credentialId);
        
        setState(() {
          _successMessage = 'Passkey deleted successfully';
        });
        
        await _loadCredentials();
      } catch (e) {
        setState(() {
          _errorMessage = 'Failed to delete passkey: ${e.toString()}';
        });
      }
    }
  }

  String _getErrorMessage(WebAuthnException e) {
    switch (e.flutterCode) {
      case 'CHALLENGE_EXPIRED':
        return 'Registration session expired. Please try again.';
      case 'USER_CANCELLED':
        return 'Registration was cancelled.';
      case 'AUTHENTICATOR_ERROR':
        return 'Authenticator error. Please try again.';
      default:
        return e.message;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('Manage Passkeys'),
      ),
      body: SingleChildScrollView(
        padding: EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (!_isWebAuthnSupported) ...[
              Card(
                color: Colors.orange[50],
                child: Padding(
                  padding: EdgeInsets.all(16.0),
                  child: Column(
                    children: [
                      Icon(Icons.warning, color: Colors.orange, size: 48),
                      SizedBox(height: 16),
                      Text(
                        'Passkeys Not Supported',
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                      SizedBox(height: 8),
                      Text(
                        'Your device doesn\'t support passkeys. Please use a compatible device to set up passkeys.',
                        textAlign: TextAlign.center,
                      ),
                    ],
                  ),
                ),
              ),
              SizedBox(height: 24),
            ],

            // Registration Section
            Card(
              child: Padding(
                padding: EdgeInsets.all(16.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Add New Passkey',
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                    SizedBox(height: 8),
                    Text(
                      'Set up a new passkey to sign in with biometrics or a security key.',
                      style: Theme.of(context).textTheme.bodyMedium,
                    ),
                    SizedBox(height: 16),
                    
                    TextField(
                      controller: _deviceNameController,
                      decoration: InputDecoration(
                        labelText: 'Device Name (Optional)',
                        hintText: 'e.g., My iPhone, Work Laptop',
                        border: OutlineInputBorder(),
                        prefixIcon: Icon(Icons.devices),
                      ),
                    ),
                    
                    if (_errorMessage != null) ...[
                      SizedBox(height: 16),
                      Container(
                        padding: EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: Colors.red[50],
                          border: Border.all(color: Colors.red[200]!),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Row(
                          children: [
                            Icon(Icons.error, color: Colors.red),
                            SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                _errorMessage!,
                                style: TextStyle(color: Colors.red[700]),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                    
                    if (_successMessage != null) ...[
                      SizedBox(height: 16),
                      Container(
                        padding: EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: Colors.green[50],
                          border: Border.all(color: Colors.green[200]!),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Row(
                          children: [
                            Icon(Icons.check_circle, color: Colors.green),
                            SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                _successMessage!,
                                style: TextStyle(color: Colors.green[700]),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                    
                    SizedBox(height: 16),
                    
                    SizedBox(
                      width: double.infinity,
                      child: ElevatedButton.icon(
                        onPressed: _isWebAuthnSupported && !_isLoading 
                            ? _registerPasskey 
                            : null,
                        icon: _isLoading 
                            ? SizedBox(
                                width: 20,
                                height: 20,
                                child: CircularProgressIndicator(strokeWidth: 2),
                              )
                            : Icon(Icons.add),
                        label: Text(_isLoading ? 'Setting up...' : 'Set Up Passkey'),
                        style: ElevatedButton.styleFrom(
                          padding: EdgeInsets.symmetric(vertical: 16),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            
            SizedBox(height: 24),
            
            // Existing Credentials Section
            Text(
              'Your Passkeys',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            SizedBox(height: 16),
            
            if (_credentials.isEmpty)
              Card(
                child: Padding(
                  padding: EdgeInsets.all(24.0),
                  child: Column(
                    children: [
                      Icon(
                        Icons.fingerprint_outlined,
                        size: 64,
                        color: Colors.grey,
                      ),
                      SizedBox(height: 16),
                      Text(
                        'No Passkeys Yet',
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      SizedBox(height: 8),
                      Text(
                        'Set up your first passkey to enable secure, passwordless authentication.',
                        textAlign: TextAlign.center,
                        style: Theme.of(context).textTheme.bodyMedium,
                      ),
                    ],
                  ),
                ),
              )
            else
              ...(_credentials.map((credential) => Card(
                child: ListTile(
                  leading: CircleAvatar(
                    child: Icon(
                      credential['authenticator_type'] == 'platform'
                          ? Icons.fingerprint
                          : Icons.security,
                    ),
                  ),
                  title: Text(credential['device_name'] ?? 'Unknown Device'),
                  subtitle: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Type: ${credential['authenticator_type']}'),
                      Text('Created: ${_formatDate(credential['created_at'])}'),
                      if (credential['last_used_at'] != null)
                        Text('Last used: ${_formatDate(credential['last_used_at'])}')
                      else
                        Text('Never used'),
                    ],
                  ),
                  trailing: IconButton(
                    icon: Icon(Icons.delete, color: Colors.red),
                    onPressed: () => _deleteCredential(
                      credential['credential_id'],
                      credential['device_name'] ?? 'Unknown Device',
                    ),
                  ),
                  isThreeLine: true,
                ),
              )).toList()),
          ],
        ),
      ),
    );
  }

  String _formatDate(String dateString) {
    final date = DateTime.parse(dateString);
    return '${date.day}/${date.month}/${date.year}';
  }

  @override
  void dispose() {
    _deviceNameController.dispose();
    super.dispose();
  }
}
```

## Error Handling

The API provides Flutter-friendly error codes for better user experience:

### Common Error Codes

| Flutter Code | Description | User Message |
|--------------|-------------|--------------|
| `CHALLENGE_EXPIRED` | Authentication/registration session expired | "Session expired. Please try again." |
| `USER_NOT_FOUND` | User doesn't exist | "User not found. Please check your credentials." |
| `NO_CREDENTIALS` | User has no registered passkeys | "No passkeys found. Please set up a passkey first." |
| `CREDENTIAL_NOT_FOUND` | Specified credential doesn't exist | "Passkey not recognized. Please try a different device." |
| `USER_CANCELLED` | User cancelled the WebAuthn operation | "Authentication was cancelled." |
| `AUTHENTICATOR_ERROR` | Hardware/platform authenticator error | "Authenticator error. Please try again." |
| `INVALID_ORIGIN` | Origin validation failed | "Invalid request origin." |
| `SIGNATURE_INVALID` | Signature verification failed | "Authentication failed. Please try again." |

### Error Handling Example

```dart
try {
  final result = await webAuthnService.completeAuthentication(beginResponse);
  // Handle success
} on WebAuthnException catch (e) {
  String userMessage;
  
  switch (e.flutterCode) {
    case 'CHALLENGE_EXPIRED':
      userMessage = 'Your session has expired. Please try signing in again.';
      break;
    case 'USER_CANCELLED':
      userMessage = 'Authentication was cancelled. Please try again when ready.';
      break;
    case 'NO_CREDENTIALS':
      userMessage = 'No passkeys found for this account. Please set up a passkey first.';
      // Navigate to setup screen
      Navigator.pushNamed(context, '/webauthn-setup');
      return;
    default:
      userMessage = e.message;
  }
  
  // Show user-friendly error
  ScaffoldMessenger.of(context).showSnackBar(
    SnackBar(content: Text(userMessage)),
  );
}
```

## Testing

### Unit Tests

```dart
// test/services/webauthn_service_test.dart
import 'package:flutter_test/flutter_test.dart';
import 'package:mockito/mockito.dart';
import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'package:your_app/services/webauthn_service.dart';
import 'package:your_app/models/webauthn_models.dart';

class MockDio extends Mock implements Dio {}
class MockFlutterSecureStorage extends Mock implements FlutterSecureStorage {}

void main() {
  group('WebAuthnService', () {
    late WebAuthnService webAuthnService;
    late MockDio mockDio;
    late MockFlutterSecureStorage mockStorage;

    setUp(() {
      mockDio = MockDio();
      mockStorage = MockFlutterSecureStorage();
      webAuthnService = WebAuthnService(
        dio: mockDio,
        secureStorage: mockStorage,
        baseUrl: 'https://api.example.com/auth',
      );
    });

    test('beginAuthentication should return WebAuthnAuthBeginResponse', () async {
      // Arrange
      final mockResponse = Response(
        data: {
          'publicKey': {
            'challenge': 'mock-challenge',
            'timeout': 60000,
            'rpId': 'example.com',
            'allowCredentials': [],
            'userVerification': 'preferred',
          },
          'username': 'testuser',
          'email': 'test@example.com',
        },
        statusCode: 200,
        requestOptions: RequestOptions(path: ''),
      );

      when(mockDio.post(any, data: anyNamed('data')))
          .thenAnswer((_) async => mockResponse);

      // Act
      final result = await webAuthnService.beginAuthentication(
        username: 'testuser',
      );

      // Assert
      expect(result, isA<WebAuthnAuthBeginResponse>());
      expect(result.username, equals('testuser'));
      expect(result.publicKey.challenge, equals('mock-challenge'));
    });

    test('beginAuthentication should throw WebAuthnException on error', () async {
      // Arrange
      when(mockDio.post(any, data: anyNamed('data')))
          .thenThrow(DioException(
            requestOptions: RequestOptions(path: ''),
            response: Response(
              data: {'detail': 'User not found', 'flutter_code': 'USER_NOT_FOUND'},
              statusCode: 404,
              requestOptions: RequestOptions(path: ''),
            ),
          ));

      // Act & Assert
      expect(
        () => webAuthnService.beginAuthentication(username: 'nonexistent'),
        throwsA(isA<WebAuthnException>()
            .having((e) => e.flutterCode, 'flutterCode', 'USER_NOT_FOUND')),
      );
    });
  });
}
```

### Integration Tests

```dart
// integration_test/webauthn_flow_test.dart
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';

import 'package:your_app/main.dart' as app;

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  group('WebAuthn Integration Tests', () {
    testWidgets('Complete authentication flow', (WidgetTester tester) async {
      app.main();
      await tester.pumpAndSettle();

      // Navigate to WebAuthn login
      await tester.tap(find.text('Sign in with Passkey'));
      await tester.pumpAndSettle();

      // Enter username
      await tester.enterText(find.byKey(Key('passkey-identifier')), 'testuser');
      await tester.pumpAndSettle();

      // Mock WebAuthn platform response
      tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
        const MethodChannel('webauthn'),
        (MethodCall methodCall) async {
          if (methodCall.method == 'getAssertion') {
            return {
              'id': 'mock-credential-id',
              'rawId': 'mock-raw-id',
              'response': {
                'authenticatorData': 'mock-auth-data',
                'clientDataJSON': 'mock-client-data',
                'signature': 'mock-signature',
              },
              'type': 'public-key',
            };
          }
          return null;
        },
      );

      // Tap authenticate button
      await tester.tap(find.text('Sign In with Passkey'));
      await tester.pumpAndSettle();

      // Verify navigation to dashboard
      expect(find.text('Dashboard'), findsOneWidget);
    });
  });
}
```

## Security Considerations

### 1. Transport Security

- **Always use HTTPS** in production
- Implement certificate pinning for additional security
- Validate server certificates

```dart
// Configure Dio with certificate pinning
final dio = Dio();
(dio.httpClientAdapter as DefaultHttpClientAdapter).onHttpClientCreate = (client) {
  client.badCertificateCallback = (cert, host, port) {
    // Implement certificate pinning logic
    return _validateCertificate(cert, host);
  };
  return client;
};
```

### 2. Token Storage

- Use `flutter_secure_storage` for JWT tokens
- Implement token refresh logic
- Clear tokens on logout

```dart
class TokenManager {
  static const _storage = FlutterSecureStorage();
  
  static Future<void> storeToken(String token) async {
    await _storage.write(key: 'access_token', value: token);
  }
  
  static Future<String?> getToken() async {
    return await _storage.read(key: 'access_token');
  }
  
  static Future<void> clearToken() async {
    await _storage.delete(key: 'access_token');
  }
}
```

### 3. Biometric Authentication

- Check biometric availability before registration
- Handle biometric changes gracefully
- Provide fallback options

```dart
Future<bool> isBiometricAvailable() async {
  try {
    final isAvailable = await LocalAuthentication().canCheckBiometrics;
    final availableBiometrics = await LocalAuthentication().getAvailableBiometrics();
    return isAvailable && availableBiometrics.isNotEmpty;
  } catch (e) {
    return false;
  }
}
```

## Troubleshooting

### Common Issues

#### 1. WebAuthn Not Supported

**Problem**: `isWebAuthnSupported()` returns false

**Solutions**:
- Ensure device runs Android 7.0+ or iOS 14.0+
- Check if device has biometric hardware
- Verify app permissions are granted
- Test on physical device (not emulator)

#### 2. Challenge Expired

**Problem**: Getting `CHALLENGE_EXPIRED` error

**Solutions**:
- Reduce time between begin and complete calls
- Check device clock synchronization
- Implement retry logic with new challenge

#### 3. Origin Validation Failed

**Problem**: Getting `INVALID_ORIGIN` error

**Solutions**:
- Ensure HTTPS is used in production
- Configure associated domains correctly
- Match server's expected origin

#### 4. User Cancelled

**Problem**: Users frequently cancel authentication

**Solutions**:
- Improve UI/UX messaging
- Provide clear instructions
- Offer alternative authentication methods

### Debug Mode

Enable debug logging for troubleshooting:

```dart
class WebAuthnService {
  final bool _debugMode;
  
  WebAuthnService({
    required Dio dio,
    required FlutterSecureStorage secureStorage,
    required String baseUrl,
    bool debugMode = false,
  }) : _dio = dio,
       _secureStorage = secureStorage,
       _baseUrl = baseUrl,
       _debugMode = debugMode {
    
    if (_debugMode) {
      _dio.interceptors.add(LogInterceptor(
        requestBody: true,
        responseBody: true,
      ));
    }
  }
  
  void _debugLog(String message) {
    if (_debugMode) {
      print('[WebAuthn] $message');
    }
  }
}
```

### Testing on Different Devices

| Device Type | Supported Authenticators | Notes |
|-------------|-------------------------|-------|
| iPhone with Face ID | Face ID, External keys | Preferred platform authenticator |
| iPhone with Touch ID | Touch ID, External keys | Preferred platform authenticator |
| Android with Fingerprint | Fingerprint, External keys | Varies by manufacturer |
| Android without Biometrics | External keys only | Requires USB/NFC key |

### Performance Optimization

1. **Cache WebAuthn Support Check**:
```dart
class WebAuthnCapabilities {
  static bool? _isSupported;
  
  static Future<bool> isSupported() async {
    _isSupported ??= await WebAuthn.isSupported();
    return _isSupported!;
  }
}
```

2. **Preload Credentials**:
```dart
class CredentialCache {
  static List<Map<String, dynamic>>? _credentials;
  
  static Future<List<Map<String, dynamic>>> getCredentials() async {
    _credentials ??= await webAuthnService.listCredentials();
    return _credentials!;
  }
  
  static void invalidate() {
    _credentials = null;
  }
}
```

3. **Optimize Network Calls**:
```dart
final dio = Dio();
dio.options.connectTimeout = Duration(seconds: 10);
dio.options.receiveTimeout = Duration(seconds: 10);
dio.interceptors.add(RetryInterceptor(
  dio: dio,
  options: const RetryOptions(
    retries: 3,
    retryInterval: Duration(seconds: 1),
  ),
));
```

## Conclusion

This guide provides a comprehensive foundation for integrating WebAuthn/FIDO2 passkey authentication in Flutter applications with the Second Brain Database. The implementation focuses on:

- **Security**: Following WebAuthn best practices
- **User Experience**: Providing clear feedback and error handling
- **Performance**: Optimizing network calls and caching
- **Compatibility**: Supporting various device types and authenticators

For additional support or questions, refer to the API documentation or contact the development team.
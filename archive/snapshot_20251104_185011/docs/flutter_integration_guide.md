# Flutter Integration Guide: Workspace Features & Team SBD Wallets

## Overview

This guide provides Flutter developers with comprehensive details on integrating the Second Brain Database's **Workspace** features and **Team SBD Wallet** functionality. This includes collaborative workspaces with role-based access control (admin/editor/viewer) and enterprise-grade team SBD token management with audit trails, compliance reporting, and emergency recovery features.

**Important Distinctions**:
- **Team/Workspaces**: Collaborative work environments with role-based permissions (admin/editor/viewer)
- **Team SBD Wallets**: Enterprise-grade token management for teams with audit logging, transaction safety, emergency recovery, and compliance features
- **Family Features**: Separate family accounts, SBD wallets, and shared spending (see separate Family API integration guide)

## Table of Contents

- [Quick Start](#quick-start)
- [Key Terms](#key-terms)
- [Core Concepts](#core-concepts)
- [Authentication](#authentication)
- [API Endpoints & Constants](#api-endpoints--constants)
- [Data Models](#data-models)
- [Team Management](#team-management)
- [Workspace Management](#workspace-management)
- [Team SBD Wallet Management](#team-sbd-wallet-management)
- [Token Request Management](#token-request-management)
- [Spending Permissions](#spending-permissions)
- [Account Security](#account-security)
- [Audit & Compliance](#audit--compliance)
- [Emergency Recovery](#emergency-recovery)
- [Error Handling](#error-handling)
- [State Management Patterns](#state-management-patterns)
- [UI Integration Examples](#ui-integration-examples)
- [Testing](#testing)
- [Common Pitfalls](#common-pitfalls)

## Key Terms

| Term | Definition |
|------|------------|
| **Workspace** | A collaborative environment where team members work together with role-based access control |
| **Team Member** | A user who belongs to a workspace with a specific role (admin, editor, viewer) |
| **Role** | Permission level within a workspace: Admin (full control), Editor (read/write), Viewer (read-only) |
| **Owner** | The user who created the workspace (automatically has admin role) |
| **Member Management** | Adding, removing, and updating roles of team members |
| **RBAC** | Role-Based Access Control - system for managing permissions based on user roles |
| **Team SBD Wallet** | Enterprise-grade token management system for teams with audit trails and compliance |
| **Token Request** | A request from team members to withdraw tokens from the shared team account |
| **Spending Permissions** | Granular controls over team members' ability to spend tokens |
| **Account Freeze** | Security feature to temporarily lock team accounts from spending |
| **Audit Trail** | Immutable log of all team wallet transactions and administrative actions |
| **Compliance Report** | Regulatory compliance documentation for financial transactions |
| **Emergency Recovery** | Backup admin mechanisms for account recovery when primary admins are unavailable |
| **Backup Admin** | Designated secondary administrators for emergency account operations |

## Core Concepts

### Workspace
- **What it is**: Collaborative work environments for teams
- **Features**: Team organization, role-based permissions (admin/editor/viewer)
- **Access**: Team-shared with role-based permissions

### Team
- **What it is**: User management and role assignment within workspaces
- **Roles**: Admin (full control), Editor (read/write), Viewer (read-only)
- **Features**: Member invitations, role management, access control

### Team SBD Wallet
- **What it is**: Enterprise-grade token management system for collaborative spending
- **Features**: Shared team accounts, audit trails, compliance reporting, emergency recovery
- **Security**: Transaction safety, cryptographic integrity, RBAC for spending permissions
- **Compliance**: Immutable audit logs, regulatory reporting, data retention policies

### Token Requests
- **What it is**: Approval-based token withdrawal system from team accounts
- **Features**: Auto-approval thresholds, admin review, expiration handling
- **Workflow**: Request → Review → Approval/Denial → Processing

### Spending Permissions
- **What it is**: Granular controls over team member spending capabilities
- **Features**: Per-member limits, spending toggles, admin override capabilities
- **Security**: Prevents unauthorized spending, enables accountability

### Account Security
- **What it is**: Multi-layer security for team financial operations
- **Features**: Account freezing, emergency recovery, backup administrators
- **Compliance**: Audit logging, integrity verification, regulatory safeguards

## Quick Start

Get up and running with workspace and team wallet features in under 10 minutes:

### 1. Add Dependencies
```yaml
dependencies:
  # Choose your preferred HTTP client (examples):
  # http: ^1.0.0          # Flutter's built-in HTTP client
  # dio: ^5.0.0           # Popular HTTP client with interceptors
  # chopper: ^6.0.0       # Code-generated HTTP client
  flutter_riverpod: ^2.0.0  # or provider: ^6.0.0
  json_annotation: ^4.8.0

dev_dependencies:
  json_serializable: ^6.6.0
  build_runner: ^2.4.0
```

### 2. Set Up API Constants
```dart
class ApiConstants {
  static const String baseUrl = 'https://api.secondbraindatabase.com';
  static const String workspacesEndpoint = '/workspaces';
  static const String membersEndpoint = '/members';
  static const String walletEndpoint = '/wallet';
  static const String tokenRequestsEndpoint = '/token-requests';
}
```

### 3. Create Data Models
```dart
enum WorkspaceRole { admin, editor, viewer }

class Workspace {
  final String id;
  final String name;
  final WorkspaceRole role;

  Workspace({required this.id, required this.name, required this.role});

  factory Workspace.fromJson(Map<String, dynamic> json) =>
      Workspace(id: json['id'], name: json['name'], role: WorkspaceRole.values[json['role']]);
}
```

### 4. Create HTTP Client Interface

Define a generic HTTP client interface that can be implemented with any HTTP library:

```dart
abstract class HttpClient {
  Future<Map<String, dynamic>> get(String url, {Map<String, String>? headers});
  Future<Map<String, dynamic>> post(String url, {Map<String, dynamic>? data, Map<String, String>? headers});
  Future<Map<String, dynamic>> put(String url, {Map<String, dynamic>? data, Map<String, String>? headers});
  Future<void> delete(String url, {Map<String, String>? headers});
}

class ApiService {
  final HttpClient _httpClient;
  final String baseUrl = 'https://api.secondbraindatabase.com';
  final String token = 'your_jwt_token';

  ApiService(this._httpClient);

  Map<String, String> get headers => {
    'Authorization': 'Bearer $token',
    'Content-Type': 'application/json',
  };

  Future<List<Workspace>> getWorkspaces() async {
    final response = await _httpClient.get('$baseUrl/workspaces', headers: headers);
    return (response['data'] as List)
        .map((json) => Workspace.fromJson(json))
        .toList();
  }
}
```

### 5. HTTP Client Implementations

#### Using Flutter's built-in `http` package:

```dart
import 'package:http/http.dart' as http;
import 'dart:convert';

class HttpClientImpl implements HttpClient {
  @override
  Future<Map<String, dynamic>> get(String url, {Map<String, String>? headers}) async {
    final response = await http.get(Uri.parse(url), headers: headers);
    return _handleResponse(response);
  }

  @override
  Future<Map<String, dynamic>> post(String url, {Map<String, dynamic>? data, Map<String, String>? headers}) async {
    final response = await http.post(
      Uri.parse(url),
      headers: headers,
      body: data != null ? jsonEncode(data) : null,
    );
    return _handleResponse(response);
  }

  @override
  Future<Map<String, dynamic>> put(String url, {Map<String, dynamic>? data, Map<String, String>? headers}) async {
    final response = await http.put(
      Uri.parse(url),
      headers: headers,
      body: data != null ? jsonEncode(data) : null,
    );
    return _handleResponse(response);
  }

  @override
  Future<void> delete(String url, {Map<String, String>? headers}) async {
    final response = await http.delete(Uri.parse(url), headers: headers);
    _handleResponse(response);
  }

  Map<String, dynamic> _handleResponse(http.Response response) {
    if (response.statusCode >= 200 && response.statusCode < 300) {
      return jsonDecode(response.body);
    } else {
      throw Exception('HTTP ${response.statusCode}: ${response.body}');
    }
  }
}
```

#### Using Dio (if you choose this library):

```dart
import 'package:dio/dio.dart';

class DioHttpClient implements HttpClient {
  final Dio _dio;

  DioHttpClient() : _dio = Dio(BaseOptions(
    connectTimeout: const Duration(seconds: 10),
    receiveTimeout: const Duration(seconds: 10),
  ));

  @override
  Future<Map<String, dynamic>> get(String url, {Map<String, String>? headers}) async {
    final response = await _dio.get(url, options: Options(headers: headers));
    return response.data;
  }

  @override
  Future<Map<String, dynamic>> post(String url, {Map<String, dynamic>? data, Map<String, String>? headers}) async {
    final response = await _dio.post(url, data: data, options: Options(headers: headers));
    return response.data;
  }

  @override
  Future<Map<String, dynamic>> put(String url, {Map<String, dynamic>? data, Map<String, String>? headers}) async {
    final response = await _dio.put(url, data: data, options: Options(headers: headers));
    return response.data;
  }

  @override
  Future<void> delete(String url, {Map<String, String>? headers}) async {
    await _dio.delete(url, options: Options(headers: headers));
  }
}
```

### 5. Basic UI Integration
```dart
class WorkspaceListScreen extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final workspacesAsync = ref.watch(workspacesProvider);

    return workspacesAsync.when(
      data: (workspaces) => ListView.builder(
        itemCount: workspaces.length,
        itemBuilder: (context, index) => ListTile(
          title: Text(workspaces[index].name),
          subtitle: Text(workspaces[index].role.name),
        ),
      ),
      loading: () => CircularProgressIndicator(),
      error: (error, _) => Text('Error: $error'),
    );
  }
}
```

For detailed implementation, continue reading the sections below.

## Authentication

All API calls require Bearer token authentication:

```dart
class ApiService {
  final String baseUrl = 'https://api.secondbraindatabase.com';
  final String token = 'your_jwt_token';

  Map<String, String> get headers => {
    'Authorization': 'Bearer $token',
    'Content-Type': 'application/json',
  };
}
```

## API Endpoints & Constants

Centralize all API endpoints for maintainability:

```dart
class ApiConstants {
  // Base URL
  static const String baseUrl = 'https://api.secondbraindatabase.com';

  // Workspace endpoints
  static const String workspaces = '/workspaces';
  static const String members = '/members';

  // Team Wallet endpoints
  static const String wallet = '/wallet';
  static const String tokenRequests = '/token-requests';
  static const String permissions = '/permissions';
  static const String freeze = '/freeze';
  static const String audit = '/audit';
  static const String compliance = '/compliance-report';
  static const String backupAdmin = '/backup-admin';
  static const String emergencyUnfreeze = '/emergency-unfreeze';

  // Auth endpoints
  static const String authRefresh = '/auth/refresh';
}
```

## Data Models

## Data Models

Use enums for type safety and include serialization methods:

```dart
import 'package:json_annotation/json_annotation.dart';

part 'models.g.dart';

enum WorkspaceRole {
  @JsonValue('admin')
  admin,
  @JsonValue('editor')
  editor,
  @JsonValue('viewer')
  viewer;

  String get displayName {
    switch (this) {
      case WorkspaceRole.admin:
        return 'Admin';
      case WorkspaceRole.editor:
        return 'Editor';
      case WorkspaceRole.viewer:
        return 'Viewer';
    }
  }

  bool get canEdit => this == admin || this == editor;
  bool get canInvite => this == admin;
  bool get canDelete => this == admin;
}

@JsonSerializable()
class Workspace {
  @JsonKey(name: 'workspace_id')
  final String workspaceId;
  final String name;
  final String? description;
  @JsonKey(name: 'owner_id')
  final String ownerId;
  final List<WorkspaceMember> members;
  final WorkspaceSettings settings;
  @JsonKey(name: 'created_at')
  final DateTime createdAt;
  @JsonKey(name: 'updated_at')
  final DateTime updatedAt;

  Workspace({
    required this.workspaceId,
    required this.name,
    this.description,
    required this.ownerId,
    required this.members,
    required this.settings,
    required this.createdAt,
    required this.updatedAt,
  });

  factory Workspace.fromJson(Map<String, dynamic> json) => _$WorkspaceFromJson(json);
  Map<String, dynamic> toJson() => _$WorkspaceToJson(this);

  Workspace copyWith({
    String? workspaceId,
    String? name,
    String? description,
    String? ownerId,
    List<WorkspaceMember>? members,
    WorkspaceSettings? settings,
    DateTime? createdAt,
    DateTime? updatedAt,
  }) {
    return Workspace(
      workspaceId: workspaceId ?? this.workspaceId,
      name: name ?? this.name,
      description: description ?? this.description,
      ownerId: ownerId ?? this.ownerId,
      members: members ?? this.members,
      settings: settings ?? this.settings,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }
}

@JsonSerializable()
class WorkspaceMember {
  @JsonKey(name: 'user_id')
  final String userId;
  final WorkspaceRole role;
  @JsonKey(name: 'joined_at')
  final DateTime joinedAt;

  WorkspaceMember({
    required this.userId,
    required this.role,
    required this.joinedAt,
  });

  factory WorkspaceMember.fromJson(Map<String, dynamic> json) => _$WorkspaceMemberFromJson(json);
  Map<String, dynamic> toJson() => _$WorkspaceMemberToJson(this);

  WorkspaceMember copyWith({
    String? userId,
    WorkspaceRole? role,
    DateTime? joinedAt,
  }) {
    return WorkspaceMember(
      userId: userId ?? this.userId,
      role: role ?? this.role,
      joinedAt: joinedAt ?? this.joinedAt,
    );
  }
}

@JsonSerializable()
class WorkspaceSettings {
  @JsonKey(name: 'allow_member_invites')
  final bool allowMemberInvites;
  @JsonKey(name: 'default_new_member_role')
  final WorkspaceRole defaultNewMemberRole;

  WorkspaceSettings({
    required this.allowMemberInvites,
    required this.defaultNewMemberRole,
  });

  factory WorkspaceSettings.fromJson(Map<String, dynamic> json) => _$WorkspaceSettingsFromJson(json);
  Map<String, dynamic> toJson() => _$WorkspaceSettingsToJson(this);

  WorkspaceSettings copyWith({
    bool? allowMemberInvites,
    WorkspaceRole? defaultNewMemberRole,
  }) {
    return WorkspaceSettings(
      allowMemberInvites: allowMemberInvites ?? this.allowMemberInvites,
      defaultNewMemberRole: defaultNewMemberRole ?? this.defaultNewMemberRole,
    );
  }
}

@JsonSerializable()
class TokenRequest {
  @JsonKey(name: 'request_id')
  final String requestId;
  final String status;
  final String? error;
  final double amount;
  final String? recipient;
  final String? memo;
  @JsonKey(name: 'created_at')
  final DateTime createdAt;
  @JsonKey(name: 'updated_at')
  final DateTime updatedAt;

  TokenRequest({
    required this.requestId,
    required this.status,
    this.error,
    required this.amount,
    this.recipient,
    this.memo,
    required this.createdAt,
    required this.updatedAt,
  });

  factory TokenRequest.fromJson(Map<String, dynamic> json) => _$TokenRequestFromJson(json);
  Map<String, dynamic> toJson() => _$TokenRequestToJson(this);

  TokenRequest copyWith({
    String? requestId,
    String? status,
    String? error,
    double? amount,
    String? recipient,
    String? memo,
    DateTime? createdAt,
    DateTime? updatedAt,
  }) {
    return TokenRequest(
      requestId: requestId ?? this.requestId,
      status: status ?? this.status,
      error: error ?? this.error,
      amount: amount ?? this.amount,
      recipient: recipient ?? this.recipient,
      memo: memo ?? this.memo,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }
}
```

Run `flutter pub run build_runner build` to generate the JSON serialization code.

### Team Wallet Data Models

```dart
// Team Wallet Models
@JsonSerializable()
class TeamWallet {
  @JsonKey(name: 'workspace_id')
  final String workspaceId;
  @JsonKey(name: 'account_username')
  final String accountUsername;
  final int balance;
  @JsonKey(name: 'is_frozen')
  final bool isFrozen;
  @JsonKey(name: 'frozen_by')
  final String? frozenBy;
  @JsonKey(name: 'frozen_at')
  final DateTime? frozenAt;
  @JsonKey(name: 'user_permissions')
  final Map<String, dynamic> userPermissions;
  @JsonKey(name: 'notification_settings')
  final Map<String, dynamic> notificationSettings;
  @JsonKey(name: 'recent_transactions')
  final List<WalletTransaction> recentTransactions;

  TeamWallet({
    required this.workspaceId,
    required this.accountUsername,
    required this.balance,
    required this.isFrozen,
    this.frozenBy,
    this.frozenAt,
    required this.userPermissions,
    required this.notificationSettings,
    required this.recentTransactions,
  });

  factory TeamWallet.fromJson(Map<String, dynamic> json) => _$TeamWalletFromJson(json);
  Map<String, dynamic> toJson() => _$TeamWalletToJson(this);
}

@JsonSerializable()
class WalletTransaction {
  @JsonKey(name: 'transaction_id')
  final String transactionId;
  final String type;
  final int amount;
  @JsonKey(name: 'from_user')
  final String? fromUser;
  @JsonKey(name: 'to_user')
  final String? toUser;
  final DateTime timestamp;
  final String description;

  WalletTransaction({
    required this.transactionId,
    required this.type,
    required this.amount,
    this.fromUser,
    this.toUser,
    required this.timestamp,
    required this.description,
  });

  factory WalletTransaction.fromJson(Map<String, dynamic> json) => _$WalletTransactionFromJson(json);
  Map<String, dynamic> toJson() => _$WalletTransactionToJson(this);
}

enum TokenRequestStatus {
  @JsonValue('pending')
  pending,
  @JsonValue('approved')
  approved,
  @JsonValue('denied')
  denied,
  @JsonValue('expired')
  expired;

  String get displayName {
    switch (this) {
      case TokenRequestStatus.pending:
        return 'Pending';
      case TokenRequestStatus.approved:
        return 'Approved';
      case TokenRequestStatus.denied:
        return 'Denied';
      case TokenRequestStatus.expired:
        return 'Expired';
    }
  }

  Color get color {
    switch (this) {
      case TokenRequestStatus.pending:
        return Colors.orange;
      case TokenRequestStatus.approved:
        return Colors.green;
      case TokenRequestStatus.denied:
        return Colors.red;
      case TokenRequestStatus.expired:
        return Colors.grey;
    }
  }
}

@JsonSerializable()
class TokenRequest {
  @JsonKey(name: 'request_id')
  final String requestId;
  @JsonKey(name: 'requester_user_id')
  final String requesterUserId;
  final int amount;
  final String reason;
  final TokenRequestStatus status;
  @JsonKey(name: 'auto_approved')
  final bool autoApproved;
  @JsonKey(name: 'created_at')
  final DateTime createdAt;
  @JsonKey(name: 'expires_at')
  final DateTime expiresAt;
  @JsonKey(name: 'admin_comments')
  final String? adminComments;

  TokenRequest({
    required this.requestId,
    required this.requesterUserId,
    required this.amount,
    required this.reason,
    required this.status,
    required this.autoApproved,
    required this.createdAt,
    required this.expiresAt,
    this.adminComments,
  });

  factory TokenRequest.fromJson(Map<String, dynamic> json) => _$TokenRequestFromJson(json);
  Map<String, dynamic> toJson() => _$TokenRequestToJson(this);
}

enum AuditEventType {
  @JsonValue('sbd_transaction')
  sbdTransaction,
  @JsonValue('permission_change')
  permissionChange,
  @JsonValue('account_freeze')
  accountFreeze,
  @JsonValue('admin_action')
  adminAction,
  @JsonValue('compliance_export')
  complianceExport;

  String get displayName {
    switch (this) {
      case AuditEventType.sbdTransaction:
        return 'SBD Transaction';
      case AuditEventType.permissionChange:
        return 'Permission Change';
      case AuditEventType.accountFreeze:
        return 'Account Freeze';
      case AuditEventType.adminAction:
        return 'Admin Action';
      case AuditEventType.complianceExport:
        return 'Compliance Export';
    }
  }
}

@JsonSerializable()
class AuditEntry {
  @JsonKey(name: '_id')
  final String id;
  @JsonKey(name: 'team_id')
  final String teamId;
  @JsonKey(name: 'event_type')
  final AuditEventType eventType;
  @JsonKey(name: 'admin_user_id')
  final String? adminUserId;
  @JsonKey(name: 'admin_username')
  final String? adminUsername;
  final String? action;
  final Map<String, dynamic>? memberPermissions;
  final String? reason;
  final DateTime timestamp;
  @JsonKey(name: 'transaction_context')
  final Map<String, dynamic>? transactionContext;
  @JsonKey(name: 'integrity_hash')
  final String integrityHash;

  AuditEntry({
    required this.id,
    required this.teamId,
    required this.eventType,
    this.adminUserId,
    this.adminUsername,
    this.action,
    this.memberPermissions,
    this.reason,
    required this.timestamp,
    this.transactionContext,
    required this.integrityHash,
  });

  factory AuditEntry.fromJson(Map<String, dynamic> json) => _$AuditEntryFromJson(json);
  Map<String, dynamic> toJson() => _$AuditEntryToJson(this);
}

@JsonSerializable()
class ComplianceReport {
  @JsonKey(name: 'team_id')
  final String teamId;
  @JsonKey(name: 'report_type')
  final String reportType;
  @JsonKey(name: 'generated_at')
  final DateTime generatedAt;
  final Map<String, dynamic> period;
  final Map<String, dynamic> summary;
  @JsonKey(name: 'audit_trails')
  final List<AuditEntry> auditTrails;

  ComplianceReport({
    required this.teamId,
    required this.reportType,
    required this.generatedAt,
    required this.period,
    required this.summary,
    required this.auditTrails,
  });

  factory ComplianceReport.fromJson(Map<String, dynamic> json) => _$ComplianceReportFromJson(json);
  Map<String, dynamic> toJson() => _$ComplianceReportToJson(this);
}

@JsonSerializable()
class SpendingPermissions {
  @JsonKey(name: 'member_permissions')
  final Map<String, Map<String, dynamic>> memberPermissions;

  SpendingPermissions({
    required this.memberPermissions,
  });

  factory SpendingPermissions.fromJson(Map<String, dynamic> json) => _$SpendingPermissionsFromJson(json);
  Map<String, dynamic> toJson() => _$SpendingPermissionsToJson(this);
}
```

Run `flutter pub run build_runner build` to generate the JSON serialization code for wallet models.

## Workspace Management

### Creating a Workspace

**Request:**
```json
POST /workspaces
{
  "name": "My Development Team",
  "description": "Workspace for our mobile app development"
}
```

**Response (201 Created):**
```json
{
  "workspace_id": "ws_550e8400-e29b-41d4-a716-446655440000",
  "name": "My Development Team",
  "description": "Workspace for our mobile app development",
  "owner_id": "user_12345678-1234-1234-1234-123456789abc",
  "members": [
    {
      "user_id": "user_12345678-1234-1234-1234-123456789abc",
      "role": "admin",
      "joined_at": "2024-01-15T10:30:00Z"
    }
  ],
  "settings": {
    "allow_member_invites": true,
    "default_new_member_role": "editor"
  },
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

```dart
Future<Workspace> createWorkspace(String name, {String? description}) async {
  final response = await _httpClient.post(
    '$baseUrl/workspaces',
    data: {
      'name': name,
      'description': description,
    },
    headers: headers,
  );
  return Workspace.fromJson(response);
}
```

### Listing Workspaces

**Request:**
```http
GET /workspaces
```

**Response (200 OK):**
```json
[
  {
    "workspace_id": "ws_550e8400-e29b-41d4-a716-446655440000",
    "name": "My Development Team",
    "description": "Workspace for our mobile app development",
    "owner_id": "user_12345678-1234-1234-1234-123456789abc",
    "members": [
      {
        "user_id": "user_12345678-1234-1234-1234-123456789abc",
        "role": "admin",
        "joined_at": "2024-01-15T10:30:00Z"
      }
    ],
    "settings": {
      "allow_member_invites": true,
      "default_new_member_role": "editor"
    },
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T10:30:00Z"
  }
]
```

```dart
Future<List<Workspace>> getMyWorkspaces() async {
  final response = await _httpClient.get('$baseUrl/workspaces', headers: headers);
  return (response as List)
      .map((json) => Workspace.fromJson(json))
      .toList();
}
```

### Getting Workspace Details

**Request:**
```http
GET /workspaces/ws_550e8400-e29b-41d4-a716-446655440000
```

**Response (200 OK):**
```json
{
  "workspace_id": "ws_550e8400-e29b-41d4-a716-446655440000",
  "name": "My Development Team",
  "description": "Workspace for our mobile app development",
  "owner_id": "user_12345678-1234-1234-1234-123456789abc",
  "members": [
    {
      "user_id": "user_12345678-1234-1234-1234-123456789abc",
      "role": "admin",
      "joined_at": "2024-01-15T10:30:00Z"
    },
    {
      "user_id": "user_87654321-4321-4321-4321-cba987654321",
      "role": "editor",
      "joined_at": "2024-01-16T14:20:00Z"
    }
  ],
  "settings": {
    "allow_member_invites": true,
    "default_new_member_role": "editor"
  },
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-16T14:20:00Z"
}
```

```dart
Future<Workspace> getWorkspace(String workspaceId) async {
  final response = await _httpClient.get('$baseUrl/workspaces/$workspaceId', headers: headers);
  return Workspace.fromJson(response);
}
```

### Updating a Workspace

**Request:**
```json
PUT /workspaces/ws_550e8400-e29b-41d4-a716-446655440000
{
  "name": "Updated Team Name",
  "description": "Updated workspace description",
  "settings": {
    "allow_member_invites": false,
    "default_new_member_role": "viewer"
  }
}
```

**Response (200 OK):**
```json
{
  "workspace_id": "ws_550e8400-e29b-41d4-a716-446655440000",
  "name": "Updated Team Name",
  "description": "Updated workspace description",
  "owner_id": "user_12345678-1234-1234-1234-123456789abc",
  "members": [
    {
      "user_id": "user_12345678-1234-1234-1234-123456789abc",
      "role": "admin",
      "joined_at": "2024-01-15T10:30:00Z"
    }
  ],
  "settings": {
    "allow_member_invites": false,
    "default_new_member_role": "viewer"
  },
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-17T09:15:00Z"
}
```

```dart
Future<Workspace> updateWorkspace(
  String workspaceId, {
  String? name,
  String? description,
  Map<String, dynamic>? settings,
}) async {
  final response = await _httpClient.put(
    '$baseUrl/workspaces/$workspaceId',
    data: {
      if (name != null) 'name': name,
      if (description != null) 'description': description,
      if (settings != null) 'settings': settings,
    },
    headers: headers,
  );
  return Workspace.fromJson(response);
}
```

### Deleting a Workspace

**Request:**
```http
DELETE /workspaces/ws_550e8400-e29b-41d4-a716-446655440000
```

**Response (204 No Content):**
```http
204 No Content
```

## Team Management

### Adding Team Members

**Request:**
```json
POST /workspaces/ws_550e8400-e29b-41d4-a716-446655440000/members
{
  "user_id_to_add": "user_newmember-1234-1234-1234-123456789abc",
  "role": "editor"
}
```

**Response (200 OK):**
```json
{
  "workspace_id": "ws_550e8400-e29b-41d4-a716-446655440000",
  "name": "My Development Team",
  "description": "Workspace for our mobile app development",
  "owner_id": "user_12345678-1234-1234-1234-123456789abc",
  "members": [
    {
      "user_id": "user_12345678-1234-1234-1234-123456789abc",
      "role": "admin",
      "joined_at": "2024-01-15T10:30:00Z"
    },
    {
      "user_id": "user_newmember-1234-1234-1234-123456789abc",
      "role": "editor",
      "joined_at": "2024-01-17T11:00:00Z"
    }
  ],
  "settings": {
    "allow_member_invites": true,
    "default_new_member_role": "editor"
  },
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-17T11:00:00Z"
}
```

```dart
Future<Workspace> addMember(
  String workspaceId,
  String userIdToAdd,
  WorkspaceRole role,
) async {
  final response = await _httpClient.post(
    '$baseUrl/workspaces/$workspaceId/members',
    data: {
      'user_id_to_add': userIdToAdd,
      'role': role.name,
    },
    headers: headers,
  );
  return Workspace.fromJson(response);
}
```

### Updating Member Roles

**Request:**
```json
PUT /workspaces/ws_550e8400-e29b-41d4-a716-446655440000/members/user_newmember-1234-1234-1234-123456789abc
{
  "role": "admin"
}
```

**Response (200 OK):**
```json
{
  "workspace_id": "ws_550e8400-e29b-41d4-a716-446655440000",
  "name": "My Development Team",
  "description": "Workspace for our mobile app development",
  "owner_id": "user_12345678-1234-1234-1234-123456789abc",
  "members": [
    {
      "user_id": "user_12345678-1234-1234-1234-123456789abc",
      "role": "admin",
      "joined_at": "2024-01-15T10:30:00Z"
    },
    {
      "user_id": "user_newmember-1234-1234-1234-123456789abc",
      "role": "admin",
      "joined_at": "2024-01-17T11:00:00Z"
    }
  ],
  "settings": {
    "allow_member_invites": true,
    "default_new_member_role": "editor"
  },
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-17T11:15:00Z"
}
```

```dart
Future<Workspace> updateMemberRole(
  String workspaceId,
  String memberId,
  WorkspaceRole newRole,
) async {
  final response = await _httpClient.put(
    '$baseUrl/workspaces/$workspaceId/members/$memberId',
    data: {'role': newRole.name},
    headers: headers,
  );
  return Workspace.fromJson(response);
}
```

### Removing Team Members

**Request:**
```http
DELETE /workspaces/ws_550e8400-e29b-41d4-a716-446655440000/members/user_newmember-1234-1234-1234-123456789abc
```

**Response (200 OK):**
```json
{
  "workspace_id": "ws_550e8400-e29b-41d4-a716-446655440000",
  "name": "My Development Team",
  "description": "Workspace for our mobile app development",
  "owner_id": "user_12345678-1234-1234-1234-123456789abc",
  "members": [
    {
      "user_id": "user_12345678-1234-1234-1234-123456789abc",
      "role": "admin",
      "joined_at": "2024-01-15T10:30:00Z"
    }
  ],
  "settings": {
    "allow_member_invites": true,
    "default_new_member_role": "editor"
  },
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-17T11:30:00Z"
}
```

```dart
Future<void> removeMember(String workspaceId, String memberId) async {
  await _httpClient.delete('$baseUrl/workspaces/$workspaceId/members/$memberId', headers: headers);
}
```

## Team SBD Wallet Management

### Initializing Team Wallet

**Request:**
```json
POST /workspaces/ws_550e8400-e29b-41d4-a716-446655440000/wallet/initialize
{
  "initial_balance": 1000.00,
  "currency": "USD",
  "wallet_name": "Team Development Fund"
}
```

**Response (201 Created):**
```json
{
  "wallet_id": "tw_550e8400-e29b-41d4-a716-446655440001",
  "workspace_id": "ws_550e8400-e29b-41d4-a716-446655440000",
  "wallet_name": "Team Development Fund",
  "balance": 1000.00,
  "currency": "USD",
  "status": "active",
  "permissions": {
    "admin": {
      "can_spend": true,
      "can_request": true,
      "daily_limit": null,
      "monthly_limit": null
    },
    "editor": {
      "can_spend": false,
      "can_request": true,
      "daily_limit": 100.00,
      "monthly_limit": 500.00
    },
    "viewer": {
      "can_spend": false,
      "can_request": false,
      "daily_limit": 0.00,
      "monthly_limit": 0.00
    }
  },
  "created_at": "2024-01-17T12:00:00Z",
  "updated_at": "2024-01-17T12:00:00Z"
}
```

```dart
Future<TeamWallet> initializeTeamWallet(
  String workspaceId, {
  required double initialBalance,
  required String currency,
  required String walletName,
}) async {
  final response = await _httpClient.post(
    '$baseUrl/workspaces/$workspaceId/wallet/initialize',
    data: {
      'initial_balance': initialBalance,
      'currency': currency,
      'wallet_name': walletName,
    },
    headers: headers,
  );
  return TeamWallet.fromJson(response);
}
```

### Getting Team Wallet Details

**Request:**
```http
GET /workspaces/ws_550e8400-e29b-41d4-a716-446655440000/wallet
```

**Response (200 OK):**
```json
{
  "wallet_id": "tw_550e8400-e29b-41d4-a716-446655440001",
  "workspace_id": "ws_550e8400-e29b-41d4-a716-446655440000",
  "wallet_name": "Team Development Fund",
  "balance": 750.50,
  "currency": "USD",
  "status": "active",
  "permissions": {
    "admin": {
      "can_spend": true,
      "can_request": true,
      "daily_limit": null,
      "monthly_limit": null
    },
    "editor": {
      "can_spend": false,
      "can_request": true,
      "daily_limit": 100.00,
      "monthly_limit": 500.00
    },
    "viewer": {
      "can_spend": false,
      "can_request": false,
      "daily_limit": 0.00,
      "monthly_limit": 0.00
    }
  },
  "created_at": "2024-01-17T12:00:00Z",
  "updated_at": "2024-01-17T15:30:00Z"
}
```

```dart
Future<TeamWallet> getTeamWallet(String workspaceId) async {
  final response = await _httpClient.get('$baseUrl/workspaces/$workspaceId/wallet', headers: headers);
  return TeamWallet.fromJson(response);
}
```

### Requesting Tokens from Team Wallet

**Request:**
```json
POST /workspaces/ws_550e8400-e29b-41d4-a716-446655440000/wallet/request-tokens
{
  "amount": 50.00,
  "purpose": "API development tools subscription",
  "urgency": "normal"
}
```

**Response (201 Created):**
```json
{
  "request_id": "tr_550e8400-e29b-41d4-a716-446655440002",
  "wallet_id": "tw_550e8400-e29b-41d4-a716-446655440001",
  "requester_id": "user_87654321-4321-4321-4321-cba987654321",
  "amount": 50.00,
  "currency": "USD",
  "purpose": "API development tools subscription",
  "urgency": "normal",
  "status": "pending",
  "created_at": "2024-01-17T16:00:00Z",
  "expires_at": "2024-01-24T16:00:00Z"
}
```

```dart
Future<TokenRequest> requestTokens(
  String workspaceId, {
  required double amount,
  required String purpose,
  String urgency = 'normal',
}) async {
  final response = await _httpClient.post(
    '$baseUrl/workspaces/$workspaceId/wallet/request-tokens',
    data: {
      'amount': amount,
      'purpose': purpose,
      'urgency': urgency,
    },
    headers: headers,
  );
  return TokenRequest.fromJson(response);
}
```

### Listing Token Requests

**Request:**
```http
GET /workspaces/ws_550e8400-e29b-41d4-a716-446655440000/wallet/requests
```

**Response (200 OK):**
```json
[
  {
    "request_id": "tr_550e8400-e29b-41d4-a716-446655440002",
    "wallet_id": "tw_550e8400-e29b-41d4-a716-446655440001",
    "requester_id": "user_87654321-4321-4321-4321-cba987654321",
    "amount": 50.00,
    "currency": "USD",
    "purpose": "API development tools subscription",
    "urgency": "normal",
    "status": "pending",
    "created_at": "2024-01-17T16:00:00Z",
    "expires_at": "2024-01-24T16:00:00Z"
  },
  {
    "request_id": "tr_550e8400-e29b-41d4-a716-446655440003",
    "wallet_id": "tw_550e8400-e29b-41d4-a716-446655440001",
    "requester_id": "user_87654321-4321-4321-4321-cba987654321",
    "amount": 25.00,
    "currency": "USD",
    "purpose": "Domain registration",
    "urgency": "high",
    "status": "approved",
    "approved_by": "user_12345678-1234-1234-1234-123456789abc",
    "approved_at": "2024-01-17T16:30:00Z",
    "created_at": "2024-01-17T15:45:00Z",
    "expires_at": "2024-01-24T15:45:00Z"
  }
]
```

```dart
Future<List<TokenRequest>> getTokenRequests(String workspaceId) async {
  final response = await _httpClient.get('$baseUrl/workspaces/$workspaceId/wallet/requests', headers: headers);
  return (response as List)
      .map((json) => TokenRequest.fromJson(json))
      .toList();
}
```

### Approving Token Requests

**Request:**
```http
POST /workspaces/ws_550e8400-e29b-41d4-a716-446655440000/wallet/requests/tr_550e8400-e29b-41d4-a716-446655440002/approve
```

**Response (200 OK):**
```json
{
  "request_id": "tr_550e8400-e29b-41d4-a716-446655440002",
  "wallet_id": "tw_550e8400-e29b-41d4-a716-446655440001",
  "requester_id": "user_87654321-4321-4321-4321-cba987654321",
  "amount": 50.00,
  "currency": "USD",
  "purpose": "API development tools subscription",
  "urgency": "normal",
  "status": "approved",
  "approved_by": "user_12345678-1234-1234-1234-123456789abc",
  "approved_at": "2024-01-17T17:00:00Z",
  "created_at": "2024-01-17T16:00:00Z",
  "expires_at": "2024-01-24T16:00:00Z"
}
```

```dart
Future<TokenRequest> approveTokenRequest(String workspaceId, String requestId) async {
  final response = await _httpClient.post(
    '$baseUrl/workspaces/$workspaceId/wallet/requests/$requestId/approve',
    headers: headers,
  );
  return TokenRequest.fromJson(response);
}
```

### Rejecting Token Requests

**Request:**
```json
POST /workspaces/ws_550e8400-e29b-41d4-a716-446655440000/wallet/requests/tr_550e8400-e29b-41d4-a716-446655440002/reject
{
  "reason": "Budget constraints for this quarter"
}
```

**Response (200 OK):**
```json
{
  "request_id": "tr_550e8400-e29b-41d4-a716-446655440002",
  "wallet_id": "tw_550e8400-e29b-41d4-a716-446655440001",
  "requester_id": "user_87654321-4321-4321-4321-cba987654321",
  "amount": 50.00,
  "currency": "USD",
  "purpose": "API development tools subscription",
  "urgency": "normal",
  "status": "rejected",
  "rejected_by": "user_12345678-1234-1234-1234-123456789abc",
  "rejected_at": "2024-01-17T17:15:00Z",
  "rejection_reason": "Budget constraints for this quarter",
  "created_at": "2024-01-17T16:00:00Z",
  "expires_at": "2024-01-24T16:00:00Z"
}
```

```dart
Future<TokenRequest> rejectTokenRequest(
  String workspaceId,
  String requestId,
  String reason,
) async {
  final response = await _httpClient.post(
    '$baseUrl/workspaces/$workspaceId/wallet/requests/$requestId/reject',
    data: {'reason': reason},
    headers: headers,
  );
  return TokenRequest.fromJson(response);
}
```

### Updating Wallet Permissions

**Request:**
```json
PUT /workspaces/ws_550e8400-e29b-41d4-a716-446655440000/wallet/permissions
{
  "permissions": {
    "editor": {
      "can_spend": true,
      "can_request": true,
      "daily_limit": 200.00,
      "monthly_limit": 1000.00
    }
  }
}
```

**Response (200 OK):**
```json
{
  "wallet_id": "tw_550e8400-e29b-41d4-a716-446655440001",
  "workspace_id": "ws_550e8400-e29b-41d4-a716-446655440000",
  "wallet_name": "Team Development Fund",
  "balance": 750.50,
  "currency": "USD",
  "status": "active",
  "permissions": {
    "admin": {
      "can_spend": true,
      "can_request": true,
      "daily_limit": null,
      "monthly_limit": null
    },
    "editor": {
      "can_spend": true,
      "can_request": true,
      "daily_limit": 200.00,
      "monthly_limit": 1000.00
    },
    "viewer": {
      "can_spend": false,
      "can_request": false,
      "daily_limit": 0.00,
      "monthly_limit": 0.00
    }
  },
  "created_at": "2024-01-17T12:00:00Z",
  "updated_at": "2024-01-17T18:00:00Z"
}
```

```dart
Future<TeamWallet> updateWalletPermissions(
  String workspaceId,
  Map<String, WalletPermission> permissions,
) async {
  final response = await _httpClient.put(
    '$baseUrl/workspaces/$workspaceId/wallet/permissions',
    data: {
      'permissions': permissions.map(
        (role, permission) => MapEntry(role, permission.toJson()),
      ),
    },
    headers: headers,
  );
  return TeamWallet.fromJson(response);
}
```

### Freezing Team Wallet

**Request:**
```json
POST /workspaces/ws_550e8400-e29b-41d4-a716-446655440000/wallet/freeze
{
  "reason": "Suspicious activity detected"
}
```

**Response (200 OK):**
```json
{
  "wallet_id": "tw_550e8400-e29b-41d4-a716-446655440001",
  "workspace_id": "ws_550e8400-e29b-41d4-a716-446655440000",
  "wallet_name": "Team Development Fund",
  "balance": 750.50,
  "currency": "USD",
  "status": "frozen",
  "frozen_reason": "Suspicious activity detected",
  "frozen_by": "user_12345678-1234-1234-1234-123456789abc",
  "frozen_at": "2024-01-17T18:30:00Z",
  "permissions": {
    "admin": {
      "can_spend": true,
      "can_request": true,
      "daily_limit": null,
      "monthly_limit": null
    },
    "editor": {
      "can_spend": true,
      "can_request": true,
      "daily_limit": 200.00,
      "monthly_limit": 1000.00
    },
    "viewer": {
      "can_spend": false,
      "can_request": false,
      "daily_limit": 0.00,
      "monthly_limit": 0.00
    }
  },
  "created_at": "2024-01-17T12:00:00Z",
  "updated_at": "2024-01-17T18:30:00Z"
}
```

```dart
Future<TeamWallet> freezeWallet(String workspaceId, String reason) async {
  final response = await _httpClient.post(
    '$baseUrl/workspaces/$workspaceId/wallet/freeze',
    data: {'reason': reason},
    headers: headers,
  );
  return TeamWallet.fromJson(response);
}
```

### Unfreezing Team Wallet

**Request:**
```http
POST /workspaces/ws_550e8400-e29b-41d4-a716-446655440000/wallet/unfreeze
```

**Response (200 OK):**
```json
{
  "wallet_id": "tw_550e8400-e29b-41d4-a716-446655440001",
  "workspace_id": "ws_550e8400-e29b-41d4-a716-446655440000",
  "wallet_name": "Team Development Fund",
  "balance": 750.50,
  "currency": "USD",
  "status": "active",
  "permissions": {
    "admin": {
      "can_spend": true,
      "can_request": true,
      "daily_limit": null,
      "monthly_limit": null
    },
    "editor": {
      "can_spend": true,
      "can_request": true,
      "daily_limit": 200.00,
      "monthly_limit": 1000.00
    },
    "viewer": {
      "can_spend": false,
      "can_request": false,
      "daily_limit": 0.00,
      "monthly_limit": 0.00
    }
  },
  "created_at": "2024-01-17T12:00:00Z",
  "updated_at": "2024-01-17T19:00:00Z"
}
```

```dart
Future<TeamWallet> unfreezeWallet(String workspaceId) async {
  final response = await _httpClient.post('$baseUrl/workspaces/$workspaceId/wallet/unfreeze', headers: headers);
  return TeamWallet.fromJson(response);
}
```

## Spending Permissions

### Updating Spending Permissions

**Request:**
```json
PUT /workspaces/ws_550e8400-e29b-41d4-a716-446655440000/wallet/permissions
{
  "permissions": {
    "editor": {
      "can_spend": true,
      "can_request": true,
      "daily_limit": 200.00,
      "monthly_limit": 1000.00
    },
    "viewer": {
      "can_spend": false,
      "can_request": true,
      "daily_limit": 50.00,
      "monthly_limit": 100.00
    }
  }
}
```

**Response (200 OK):**
```json
{
  "member_permissions": {
    "user_12345678-1234-1234-1234-123456789abc": {
      "can_spend": true,
      "can_request": true,
      "daily_limit": null,
      "monthly_limit": null,
      "role": "admin"
    },
    "user_87654321-4321-4321-4321-cba987654321": {
      "can_spend": true,
      "can_request": true,
      "daily_limit": 200.00,
      "monthly_limit": 1000.00,
      "role": "editor"
    },
    "user_viewer123-4567-8901-2345-678901234567": {
      "can_spend": false,
      "can_request": true,
      "daily_limit": 50.00,
      "monthly_limit": 100.00,
      "role": "viewer"
    }
  }
}
```

```dart
Future<SpendingPermissions> updateSpendingPermissions(
  String workspaceId,
  Map<String, Map<String, dynamic>> memberPermissions,
) async {
  final response = await _httpClient.put(
    '${ApiConstants.workspaces}/$workspaceId${ApiConstants.wallet}${ApiConstants.permissions}',
    data: {'member_permissions': memberPermissions},
  );
  return SpendingPermissions.fromJson(response['data']);
}
```

## Account Security

### Freezing/Unfreezing Account

**Request (Freeze):**
```json
POST /workspaces/ws_550e8400-e29b-41d4-a716-446655440000/wallet/freeze
{
  "action": "freeze",
  "reason": "Suspicious activity detected on multiple transactions"
}
```

**Response (200 OK):**
```json
{
  "wallet_id": "tw_550e8400-e29b-41d4-a716-446655440001",
  "workspace_id": "ws_550e8400-e29b-41d4-a716-446655440000",
  "status": "frozen",
  "frozen_reason": "Suspicious activity detected on multiple transactions",
  "frozen_by": "user_12345678-1234-1234-1234-123456789abc",
  "frozen_at": "2024-01-17T18:30:00Z",
  "updated_at": "2024-01-17T18:30:00Z"
}
```

**Request (Unfreeze):**
```json
POST /workspaces/ws_550e8400-e29b-41d4-a716-446655440000/wallet/freeze
{
  "action": "unfreeze"
}
```

**Response (200 OK):**
```json
{
  "wallet_id": "tw_550e8400-e29b-41d4-a716-446655440001",
  "workspace_id": "ws_550e8400-e29b-41d4-a716-446655440000",
  "status": "active",
  "unfrozen_by": "user_12345678-1234-1234-1234-123456789abc",
  "unfrozen_at": "2024-01-17T19:00:00Z",
  "updated_at": "2024-01-17T19:00:00Z"
}
```

```dart
Future<Map<String, dynamic>> freezeAccount(
  String workspaceId,
  String action, // 'freeze' or 'unfreeze'
  {String? reason}
) async {
  final response = await _httpClient.post(
    '$baseUrl/workspaces/$workspaceId/wallet/freeze',
    data: {
      'action': action,
      if (reason != null) 'reason': reason,
    },
    headers: headers,
  );
  return response;
}
```

## Audit & Compliance

### Getting Audit Trail

**Request:**
```http
GET /workspaces/ws_550e8400-e29b-41d4-a716-446655440000/wallet/audit?start_date=2024-01-01T00:00:00Z&end_date=2024-01-31T23:59:59Z&limit=50
```

**Response (200 OK):**
```json
[
  {
    "_id": "audit_550e8400-e29b-41d4-a716-446655440010",
    "team_id": "ws_550e8400-e29b-41d4-a716-446655440000",
    "event_type": "sbd_transaction",
    "admin_user_id": "user_12345678-1234-1234-1234-123456789abc",
    "admin_username": "admin@example.com",
    "action": "token_request_approved",
    "member_permissions": null,
    "reason": "Approved token request for API development tools",
    "timestamp": "2024-01-17T17:00:00Z",
    "transaction_context": {
      "request_id": "tr_550e8400-e29b-41d4-a716-446655440002",
      "amount": 50.00,
      "currency": "USD",
      "requester_id": "user_87654321-4321-4321-4321-cba987654321"
    },
    "integrity_hash": "a1b2c3d4e5f6789012345678901234567890123456789012345678901234567890"
  },
  {
    "_id": "audit_550e8400-e29b-41d4-a716-446655440011",
    "team_id": "ws_550e8400-e29b-41d4-a716-446655440000",
    "event_type": "permission_change",
    "admin_user_id": "user_12345678-1234-1234-1234-123456789abc",
    "admin_username": "admin@example.com",
    "action": "updated_spending_permissions",
    "member_permissions": {
      "editor": {
        "can_spend": true,
        "daily_limit": 200.00,
        "monthly_limit": 1000.00
      }
    },
    "reason": "Updated editor permissions for Q1 budget",
    "timestamp": "2024-01-17T18:00:00Z",
    "transaction_context": null,
    "integrity_hash": "b2c3d4e5f67890123456789012345678901234567890123456789012345678901"
  },
  {
    "_id": "audit_550e8400-e29b-41d4-a716-446655440012",
    "team_id": "ws_550e8400-e29b-41d4-a716-446655440000",
    "event_type": "account_freeze",
    "admin_user_id": "user_12345678-1234-1234-1234-123456789abc",
    "admin_username": "admin@example.com",
    "action": "account_frozen",
    "member_permissions": null,
    "reason": "Suspicious activity detected",
    "timestamp": "2024-01-17T18:30:00Z",
    "transaction_context": null,
    "integrity_hash": "c3d4e5f678901234567890123456789012345678901234567890123456789012"
  }
]
```

```dart
Future<List<AuditEntry>> getAuditTrail(
  String workspaceId, {
  DateTime? startDate,
  DateTime? endDate,
  int limit = 100,
}) async {
  final queryParams = <String, dynamic>{};
  if (startDate != null) queryParams['start_date'] = startDate.toIso8601String();
  if (endDate != null) queryParams['end_date'] = endDate.toIso8601String();
  queryParams['limit'] = limit.toString();

  final url = Uri.parse('$baseUrl/workspaces/$workspaceId/wallet/audit').replace(queryParameters: queryParams);
  final response = await _httpClient.get(url.toString(), headers: headers);
  return (response as List)
      .map((json) => AuditEntry.fromJson(json))
      .toList();
}
```

### Generating Compliance Report

**Request:**
```http
GET /workspaces/ws_550e8400-e29b-41d4-a716-446655440000/wallet/compliance-report?report_type=json&start_date=2024-01-01T00:00:00Z&end_date=2024-01-31T23:59:59Z
```

**Response (200 OK):**
```json
{
  "team_id": "ws_550e8400-e29b-41d4-a716-446655440000",
  "report_type": "json",
  "generated_at": "2024-01-17T20:00:00Z",
  "period": {
    "start_date": "2024-01-01T00:00:00Z",
    "end_date": "2024-01-31T23:59:59Z"
  },
  "summary": {
    "total_transactions": 15,
    "total_amount": 2500.00,
    "currency": "USD",
    "approved_requests": 12,
    "rejected_requests": 3,
    "average_request_amount": 166.67,
    "largest_request": 500.00,
    "admin_actions": 8,
    "permission_changes": 2,
    "account_freezes": 1
  },
  "audit_trails": [
    {
      "_id": "audit_550e8400-e29b-41d4-a716-446655440010",
      "team_id": "ws_550e8400-e29b-41d4-a716-446655440000",
      "event_type": "sbd_transaction",
      "admin_user_id": "user_12345678-1234-1234-1234-123456789abc",
      "admin_username": "admin@example.com",
      "action": "token_request_approved",
      "timestamp": "2024-01-17T17:00:00Z",
      "transaction_context": {
        "request_id": "tr_550e8400-e29b-41d4-a716-446655440002",
        "amount": 50.00,
        "currency": "USD"
      },
      "integrity_hash": "a1b2c3d4e5f6789012345678901234567890123456789012345678901234567890"
    }
  ]
}
```

```dart
Future<ComplianceReport> generateComplianceReport(
  String workspaceId,
  String reportType, // 'json', 'csv', 'pdf'
  {DateTime? startDate, DateTime? endDate}
) async {
  final queryParams = <String, dynamic>{'report_type': reportType};
  if (startDate != null) queryParams['start_date'] = startDate.toIso8601String();
  if (endDate != null) queryParams['end_date'] = endDate.toIso8601String();

  final url = Uri.parse('$baseUrl/workspaces/$workspaceId/wallet/compliance-report').replace(queryParameters: queryParams);
  final response = await _httpClient.get(url.toString(), headers: headers);
  return ComplianceReport.fromJson(response);
}
```

## Emergency Recovery

### Designating Backup Admin

**Request:**
```json
POST /workspaces/ws_550e8400-e29b-41d4-a716-446655440000/wallet/backup-admin
{
  "backup_admin_id": "user_backup123-4567-8901-2345-678901234567"
}
```

**Response (200 OK):**
```json
{
  "workspace_id": "ws_550e8400-e29b-41d4-a716-446655440000",
  "primary_admin_id": "user_12345678-1234-1234-1234-123456789abc",
  "backup_admin_id": "user_backup123-4567-8901-2345-678901234567",
  "designated_at": "2024-01-17T20:30:00Z",
  "status": "active"
}
```

```dart
Future<Map<String, dynamic>> designateBackupAdmin(
  String workspaceId,
  String backupAdminId,
) async {
  final response = await _httpClient.post(
    '$baseUrl/workspaces/$workspaceId/wallet/backup-admin',
    data: {'backup_admin_id': backupAdminId},
    headers: headers,
  );
  return response;
}
```

### Removing Backup Admin

**Request:**
```http
DELETE /workspaces/ws_550e8400-e29b-41d4-a716-446655440000/wallet/backup-admin/user_backup123-4567-8901-2345-678901234567
```

**Response (200 OK):**
```json
{
  "workspace_id": "ws_550e8400-e29b-41d4-a716-446655440000",
  "backup_admin_id": "user_backup123-4567-8901-2345-678901234567",
  "removed_at": "2024-01-17T21:00:00Z",
  "status": "removed"
}
```

```dart
Future<Map<String, dynamic>> removeBackupAdmin(
  String workspaceId,
  String backupAdminId,
) async {
  final response = await _httpClient.delete(
    '$baseUrl/workspaces/$workspaceId/wallet/backup-admin/$backupAdminId',
    headers: headers,
  );
  return response;
}
```

### Emergency Unfreeze

**Request:**
```json
POST /workspaces/ws_550e8400-e29b-41d4-a716-446655440000/wallet/emergency-unfreeze
{
  "emergency_reason": "Primary admin is unavailable due to medical emergency. Backup admin authorization required for urgent payment processing."
}
```

**Response (200 OK):**
```json
{
  "workspace_id": "ws_550e8400-e29b-41d4-a716-446655440000",
  "wallet_id": "tw_550e8400-e29b-41d4-a716-446655440001",
  "emergency_action": "unfreeze",
  "performed_by": "user_backup123-4567-8901-2345-678901234567",
  "emergency_reason": "Primary admin is unavailable due to medical emergency. Backup admin authorization required for urgent payment processing.",
  "performed_at": "2024-01-17T22:00:00Z",
  "previous_status": "frozen",
  "new_status": "active",
  "audit_entry_id": "audit_emergency_550e8400-e29b-41d4-a716-446655440015"
}
```

```dart
Future<Map<String, dynamic>> emergencyUnfreeze(
  String workspaceId,
  String emergencyReason,
) async {
  final response = await _httpClient.post(
    '$baseUrl/workspaces/$workspaceId/wallet/emergency-unfreeze',
    data: {'emergency_reason': emergencyReason},
    headers: headers,
  );
  return response;
}
```

### Team Wallet State Management

```dart
// Team Wallet Providers
final teamWalletApiProvider = Provider<TeamWalletApi>((ref) {
  return TeamWalletApi(ref.watch(authTokenProvider));
});

final teamWalletProvider = StateNotifierProvider.family<TeamWalletNotifier, AsyncValue<TeamWallet?>, String>((ref, workspaceId) {
  return TeamWalletNotifier(ref.watch(teamWalletApiProvider), workspaceId);
});

final tokenRequestsProvider = StateNotifierProvider.family<TokenRequestsNotifier, AsyncValue<List<TokenRequest>>, String>((ref, workspaceId) {
  return TokenRequestsNotifier(ref.watch(teamWalletApiProvider), workspaceId);
});

final auditTrailProvider = StateNotifierProvider.family<AuditTrailNotifier, AsyncValue<List<AuditEntry>>, String>((ref, workspaceId) {
  return AuditTrailNotifier(ref.watch(teamWalletApiProvider), workspaceId);
});

// Team Wallet Notifier
class TeamWalletNotifier extends StateNotifier<AsyncValue<TeamWallet?>> {
  final TeamWalletApi _api;
  final String _workspaceId;

  TeamWalletNotifier(this._api, this._workspaceId) : super(const AsyncValue.loading()) {
    loadWallet();
  }

  Future<void> loadWallet() async {
    state = const AsyncValue.loading();
    try {
      final wallet = await _api.getWallet(_workspaceId);
      state = AsyncValue.data(wallet);
    } catch (error, stackTrace) {
      state = AsyncValue.error(error, stackTrace);
    }
  }

  Future<void> initializeWallet() async {
    try {
      await _api.initializeWallet(_workspaceId);
      await loadWallet(); // Reload wallet data
    } catch (error, stackTrace) {
      state = AsyncValue.error(error, stackTrace);
    }
  }

  Future<void> createTokenRequest(int amount, String reason) async {
    try {
      await _api.createTokenRequest(_workspaceId, amount, reason);
      // Optionally refresh wallet or token requests
    } catch (error, stackTrace) {
      state = AsyncValue.error(error, stackTrace);
    }
  }
}

// Token Requests Notifier
class TokenRequestsNotifier extends StateNotifier<AsyncValue<List<TokenRequest>>> {
  final TeamWalletApi _api;
  final String _workspaceId;

  TokenRequestsNotifier(this._api, this._workspaceId) : super(const AsyncValue.loading()) {
    loadPendingRequests();
  }

  Future<void> loadPendingRequests() async {
    state = const AsyncValue.loading();
    try {
      final requests = await _api.getPendingTokenRequests(_workspaceId);
      state = AsyncValue.data(requests);
    } catch (error, stackTrace) {
      state = AsyncValue.error(error, stackTrace);
    }
  }

  Future<void> reviewRequest(String requestId, String action, {String? comments}) async {
    try {
      await _api.reviewTokenRequest(_workspaceId, requestId, action, comments: comments);
      await loadPendingRequests(); // Refresh the list
    } catch (error, stackTrace) {
      state = AsyncValue.error(error, stackTrace);
    }
  }
}

// Audit Trail Notifier
class AuditTrailNotifier extends StateNotifier<AsyncValue<List<AuditEntry>>> {
  final TeamWalletApi _api;
  final String _workspaceId;

  AuditTrailNotifier(this._api, this._workspaceId) : super(const AsyncValue.loading()) {
    loadAuditTrail();
  }

  Future<void> loadAuditTrail({DateTime? startDate, DateTime? endDate, int limit = 100}) async {
    state = const AsyncValue.loading();
    try {
      final auditEntries = await _api.getAuditTrail(
        _workspaceId,
        startDate: startDate,
        endDate: endDate,
        limit: limit,
      );
      state = AsyncValue.data(auditEntries);
    } catch (error, stackTrace) {
      state = AsyncValue.error(error, stackTrace);
    }
  }
}
```

## Error Handling

Implement comprehensive error handling for robust Flutter integration with workspace and team wallet features. Handle network failures, API errors, rate limits, and business logic exceptions gracefully.

### Custom Exception Classes

```dart
// Custom exception classes for workspace and wallet operations
class WorkspaceException implements Exception {
  final String message;
  final String? code;
  final dynamic details;

  WorkspaceException(this.message, {this.code, this.details});

  @override
  String toString() => 'WorkspaceException: $message${code != null ? ' ($code)' : ''}';
}

class TeamWalletException implements Exception {
  final String message;
  final String? code;
  final dynamic details;

  TeamWalletException(this.message, {this.code, this.details});

  @override
  String toString() => 'TeamWalletException: $message${code != null ? ' ($code)' : ''}';
}

class RateLimitException extends WorkspaceException {
  final Duration retryAfter;

  RateLimitException(String message, this.retryAfter) : super(message, code: 'RATE_LIMIT_EXCEEDED');

  @override
  String toString() => 'RateLimitException: $message. Retry after ${retryAfter.inSeconds} seconds';
}

class PermissionDeniedException extends WorkspaceException {
  PermissionDeniedException(String message) : super(message, code: 'PERMISSION_DENIED');
}

class WalletNotInitializedException extends TeamWalletException {
  WalletNotInitializedException() : super('Team wallet not initialized', code: 'WALLET_NOT_INITIALIZED');
}
```

### API Service with Error Handling

```dart
class WorkspaceApiService {
  final HttpClient _httpClient;

  WorkspaceApiService(this._httpClient);

  void _setupInterceptors() {
    // Interceptors are handled by the HttpClient implementation
    // Each implementation (HttpClientImpl, DioHttpClient) handles
    // request/response logging and error conversion differently
  }

  WorkspaceException _handleHttpError(dynamic error, {Map<String, dynamic>? responseData}) {
    if (error is WorkspaceException) {
      return error;
    }

    // Handle HTTP status codes
    if (responseData != null) {
      final statusCode = responseData['statusCode'] as int?;
      final message = responseData['message'] as String?;
      final code = responseData['code'] as String?;

      switch (statusCode) {
        case 400:
          return WorkspaceException(
            message ?? 'Invalid request. Please check your input.',
            code: code,
            details: responseData,
          );

        case 401:
          return WorkspaceException('Authentication failed. Please log in again.');

        case 403:
          return PermissionDeniedException(
            message ?? 'You do not have permission to perform this action.',
          );

        case 404:
          return WorkspaceException(
            message ?? 'The requested resource was not found.',
            code: 'NOT_FOUND',
          );

        case 429:
          final retryAfter = _parseRetryAfter(responseData['headers']?['Retry-After']);
          return RateLimitException(
            message ?? 'Rate limit exceeded. Please try again later.',
            retryAfter,
          );

        case 500:
        case 502:
        case 503:
        case 504:
          return WorkspaceException('Server error. Please try again later.');

        default:
          return WorkspaceException(
            message ?? 'An error occurred. Please try again.',
            code: code,
          );
      }
    }

    // Handle network errors
    if (error is TimeoutException) {
      return WorkspaceException('Network timeout. Please check your connection and try again.');
    }

    if (error is SocketException) {
      return WorkspaceException('Network connection failed. Please check your internet connection.');
    }

    return WorkspaceException('An unexpected error occurred. Please try again.');
  }

  Duration _parseRetryAfter(dynamic retryAfterHeader) {
    if (retryAfterHeader == null) return const Duration(seconds: 60);

    if (retryAfterHeader is String) {
      final seconds = int.tryParse(retryAfterHeader);
      if (seconds != null) {
        return Duration(seconds: seconds);
      }
    }

    if (retryAfterHeader is int) {
      return Duration(seconds: retryAfterHeader);
    }

    // If it's a date, calculate difference (simplified)
    return const Duration(seconds: 60);
  }

  // API methods with error handling
  Future<List<Workspace>> getWorkspaces() async {
    try {
      final response = await _httpClient.get(ApiConstants.workspaces);
      final data = response['data'] as List;
      return data.map((json) => Workspace.fromJson(json)).toList();
    } catch (error) {
      throw _handleHttpError(error, responseData: error is Map<String, dynamic> ? error : null);
    }
  }

  Future<Workspace> createWorkspace(String name, {String? description}) async {
    try {
      final response = await _httpClient.post(
        ApiConstants.workspaces,
        data: {
          'name': name,
          if (description != null) 'description': description,
        },
      );
      return Workspace.fromJson(response['data']);
    } catch (error) {
      throw _handleHttpError(error, responseData: error is Map<String, dynamic> ? error : null);
    }
  }

  Future<TeamWallet> getTeamWallet(String workspaceId) async {
    try {
      final response = await _httpClient.get('${ApiConstants.workspaces}/$workspaceId${ApiConstants.wallet}');
      return TeamWallet.fromJson(response['data']);
    } catch (error) {
      final responseData = error is Map<String, dynamic> ? error : null;
      if (responseData?['statusCode'] == 404) {
        throw WalletNotInitializedException();
      }
      if (error is TeamWalletException) {
        throw error;
      }
      throw _handleHttpError(error, responseData: responseData);
    }
  }
}
```

### Error Handling in State Management

```dart
// Error handling in Riverpod providers
final errorProvider = StateProvider<WorkspaceException?>((ref) => null);

final workspacesProvider = StateNotifierProvider<WorkspacesNotifier, AsyncValue<List<Workspace>>>((ref) {
  return WorkspacesNotifier(ref.watch(workspaceApiProvider));
});

class WorkspacesNotifier extends StateNotifier<AsyncValue<List<Workspace>>> {
  final WorkspaceApiService _api;

  WorkspacesNotifier(this._api) : super(const AsyncValue.loading()) {
    loadWorkspaces();
  }

  Future<void> loadWorkspaces() async {
    state = const AsyncValue.loading();
    try {
      final workspaces = await _api.getWorkspaces();
      state = AsyncValue.data(workspaces);
    } catch (error, stackTrace) {
      // Store error for global handling
      state = AsyncValue.error(error, stackTrace);
    }
  }

  Future<void> createWorkspace(String name, {String? description}) async {
    try {
      final newWorkspace = await _api.createWorkspace(name, description: description);
      state = state.maybeWhen(
        data: (workspaces) => AsyncValue.data([...workspaces, newWorkspace]),
        orElse: () => AsyncValue.data([newWorkspace]),
      );
    } catch (error, stackTrace) {
      state = AsyncValue.error(error, stackTrace);
    }
  }
}

// Global error handler widget
class ErrorHandler extends ConsumerWidget {
  final Widget child;

  const ErrorHandler({required this.child});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    ref.listen<WorkspaceException?>(errorProvider, (previous, current) {
      if (current != null) {
        _showErrorDialog(context, current);
        // Clear the error after showing
        ref.read(errorProvider.notifier).state = null;
      }
    });

    return child;
  }

  void _showErrorDialog(BuildContext context, WorkspaceException error) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Error'),
        content: Text(error.message),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('OK'),
          ),
        ],
      ),
    );
  }
}
```

### Error Boundaries for UI Components

```dart
class ErrorBoundary extends StatefulWidget {
  final Widget child;
  final Widget Function(Object error, StackTrace? stackTrace)? errorBuilder;
  final void Function(Object error, StackTrace? stackTrace)? onError;

  const ErrorBoundary({
    required this.child,
    this.errorBuilder,
    this.onError,
  });

  @override
  _ErrorBoundaryState createState() => _ErrorBoundaryState();
}

class _ErrorBoundaryState extends State<ErrorBoundary> {
  Object? _error;
  StackTrace? _stackTrace;

  @override
  void initState() {
    super.initState();
    // Catch Flutter framework errors
    FlutterError.onError = (FlutterErrorDetails details) {
      _handleError(details.exception, details.stack);
    };
  }

  void _handleError(Object error, StackTrace? stackTrace) {
    setState(() {
      _error = error;
      _stackTrace = stackTrace;
    });

    widget.onError?.call(error, stackTrace);

    // Log error for debugging
    debugPrint('Error caught by boundary: $error');
    debugPrint('Stack trace: $stackTrace');
  }

  @override
  Widget build(BuildContext context) {
    if (_error != null) {
      return widget.errorBuilder?.call(_error!, _stackTrace) ??
          Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(Icons.error, size: 64, color: Colors.red),
                const SizedBox(height: 16),
                const Text('Something went wrong'),
                const SizedBox(height: 16),
                ElevatedButton(
                  onPressed: () {
                    setState(() {
                      _error = null;
                      _stackTrace = null;
                    });
                  },
                  child: const Text('Try Again'),
                ),
              ],
            ),
          );
    }

    return widget.child;
  }
}
```

### Retry Logic and Exponential Backoff

```dart
class RetryHelper {
  static Future<T> withRetry<T>(
    Future<T> Function() operation, {
    int maxAttempts = 3,
    Duration initialDelay = const Duration(seconds: 1),
    double backoffFactor = 2.0,
    bool Function(Object error)? shouldRetry,
  }) async {
    Duration delay = initialDelay;
    Object? lastError;

    for (int attempt = 1; attempt <= maxAttempts; attempt++) {
      try {
        return await operation();
      } catch (error) {
        lastError = error;

        // Check if we should retry this error
        if (shouldRetry != null && !shouldRetry(error)) {
          throw error;
        }

        // Don't retry on the last attempt
        if (attempt == maxAttempts) {
          break;
        }

        // Wait before retrying
        await Future.delayed(delay);
        delay = Duration(milliseconds: (delay.inMilliseconds * backoffFactor).round());
      }
    }

    throw lastError!;
  }
}

// Usage example
Future<void> loadWorkspaceWithRetry(String workspaceId, WidgetRef ref) async {
  try {
    await RetryHelper.withRetry(
      () => ref.read(workspacesProvider.notifier).loadWorkspaces(),
      maxAttempts: 3,
      shouldRetry: (error) {
        // Only retry on network errors, not on permission errors
        return error is WorkspaceException &&
               !(error is PermissionDeniedException);
      },
    );
  } catch (error) {
    // Handle final failure
    ref.read(errorProvider.notifier).state = error as WorkspaceException;
  }
}
```

## State Management Patterns

Implement robust state management for workspace and team wallet features using Riverpod. Handle complex state interactions, caching, and synchronization between local and remote state.

### Core State Management Architecture

```dart
// Core providers
final authTokenProvider = StateProvider<String?>((ref) => null);

final httpClientProvider = Provider<HttpClient>((ref) {
  final token = ref.watch(authTokenProvider);
  // Choose your preferred HTTP client implementation
  return HttpClientImpl(
    baseUrl: ApiConstants.baseUrl,
    headers: {
      if (token != null) 'Authorization': 'Bearer $token',
      'Content-Type': 'application/json',
    },
  );
  // Or use DioHttpClient for Dio-based implementation
  // return DioHttpClient(
  //   baseUrl: ApiConstants.baseUrl,
  //   headers: {
  //     if (token != null) 'Authorization': 'Bearer $token',
  //     'Content-Type': 'application/json',
  //   },
  // );
});

// Workspace state management
final workspacesProvider = StateNotifierProvider<WorkspacesNotifier, AsyncValue<List<Workspace>>>((ref) {
  return WorkspacesNotifier(ref.watch(workspaceApiProvider));
});

final workspaceProvider = FutureProvider.family<Workspace?, String>((ref, workspaceId) async {
  final api = ref.watch(workspaceApiProvider);
  return api.getWorkspace(workspaceId);
});

// Team wallet state management
final teamWalletProvider = StateNotifierProvider.family<TeamWalletNotifier, AsyncValue<TeamWallet?>, String>((ref, workspaceId) {
  return TeamWalletNotifier(ref.watch(teamWalletApiProvider), workspaceId);
});

final tokenRequestsProvider = StateNotifierProvider.family<TokenRequestsNotifier, AsyncValue<List<TokenRequest>>, String>((ref, workspaceId) {
  return TokenRequestsNotifier(ref.watch(teamWalletApiProvider), workspaceId);
});

// Audit and compliance
final auditTrailProvider = StateNotifierProvider.family<AuditTrailNotifier, AsyncValue<List<AuditEntry>>, String>((ref, workspaceId) {
  return AuditTrailNotifier(ref.watch(teamWalletApiProvider), workspaceId);
});

final complianceReportProvider = FutureProvider.family<ComplianceReport?, String>((ref, workspaceId) async {
  final api = ref.watch(teamWalletApiProvider);
  return api.generateComplianceReport(workspaceId);
});
```

### Advanced State Management Patterns

```dart
// Cached state with TTL
class CachedStateNotifier<T> extends StateNotifier<AsyncValue<T>> {
  final Future<T> Function() _fetcher;
  final Duration _ttl;
  DateTime? _lastFetch;
  T? _cachedData;

  CachedStateNotifier(this._fetcher, {Duration ttl = const Duration(minutes: 5)})
      : _ttl = ttl,
        super(const AsyncValue.loading());

  Future<void> load({bool forceRefresh = false}) async {
    // Check if we have valid cached data
    if (!forceRefresh &&
        _cachedData != null &&
        _lastFetch != null &&
        DateTime.now().difference(_lastFetch!) < _ttl) {
      state = AsyncValue.data(_cachedData!);
      return;
    }

    state = const AsyncValue.loading();
    try {
      final data = await _fetcher();
      _cachedData = data;
      _lastFetch = DateTime.now();
      state = AsyncValue.data(data);
    } catch (error, stackTrace) {
      state = AsyncValue.error(error, stackTrace);
    }
  }

  void invalidate() {
    _cachedData = null;
    _lastFetch = null;
  }
}

// Optimistic updates
class OptimisticUpdateNotifier<T> extends StateNotifier<AsyncValue<T>> {
  final Future<T> Function(T currentData) _updater;
  final Future<void> Function(T newData) _remoteUpdate;

  OptimisticUpdateNotifier(
    T initialData,
    this._updater,
    this._remoteUpdate,
  ) : super(AsyncValue.data(initialData));

  Future<void> update(T newData) async {
    // Store current data for rollback
    final currentData = state.value;

    // Apply optimistic update
    state = AsyncValue.data(newData);

    try {
      // Attempt remote update
      await _remoteUpdate(newData);
    } catch (error, stackTrace) {
      // Rollback on failure
      if (currentData != null) {
        state = AsyncValue.data(currentData);
      }
      state = AsyncValue.error(error, stackTrace);
    }
  }
}

// State synchronization
class SyncManager {
  final Map<String, DateTime> _lastSyncTimes = {};
  final Map<String, Completer<void>> _syncCompleters = {};

  Future<void> sync(String key, Future<void> Function() syncFunction) async {
    // Prevent concurrent syncs for the same key
    if (_syncCompleters.containsKey(key)) {
      return _syncCompleters[key]!.future;
    }

    final completer = Completer<void>();
    _syncCompleters[key] = completer;

    try {
      await syncFunction();
      _lastSyncTimes[key] = DateTime.now();
      completer.complete();
    } catch (error, stackTrace) {
      completer.completeError(error, stackTrace);
    } finally {
      _syncCompleters.remove(key);
    }
  }

  DateTime? getLastSyncTime(String key) => _lastSyncTimes[key];

  bool shouldSync(String key, Duration maxAge) {
    final lastSync = _lastSyncTimes[key];
    return lastSync == null || DateTime.now().difference(lastSync) > maxAge;
  }
}

// Usage in providers
final syncManagerProvider = Provider<SyncManager>((ref) => SyncManager());

final syncedWorkspacesProvider = StateNotifierProvider<SyncedWorkspacesNotifier, AsyncValue<List<Workspace>>>((ref) {
  return SyncedWorkspacesNotifier(
    ref.watch(workspaceApiProvider),
    ref.watch(syncManagerProvider),
  );
});

class SyncedWorkspacesNotifier extends StateNotifier<AsyncValue<List<Workspace>>> {
  final WorkspaceApiService _api;
  final SyncManager _syncManager;

  SyncedWorkspacesNotifier(this._api, this._syncManager) : super(const AsyncValue.loading()) {
    loadWorkspaces();
  }

  Future<void> loadWorkspaces({bool forceRefresh = false}) async {
    const syncKey = 'workspaces';
    const maxAge = Duration(minutes: 5);

    if (!forceRefresh && !_syncManager.shouldSync(syncKey, maxAge)) {
      // Data is still fresh, no need to sync
      return;
    }

    await _syncManager.sync(syncKey, () async {
      state = const AsyncValue.loading();
      try {
        final workspaces = await _api.getWorkspaces();
        state = AsyncValue.data(workspaces);
      } catch (error, stackTrace) {
        state = AsyncValue.error(error, stackTrace);
      }
    });
  }
}
```

### State Persistence and Hydration

```dart
// State persistence with shared preferences
class PersistentStateNotifier<T> extends StateNotifier<AsyncValue<T>> {
  final String _key;
  final Future<T> Function() _fetcher;
  final Future<String?> Function() _loadPersisted;
  final Future<void> Function(String data) _persist;

  PersistentStateNotifier(
    this._key,
    this._fetcher,
    this._loadPersisted,
    this._persist,
  ) : super(const AsyncValue.loading()) {
    _hydrate();
  }

  Future<void> _hydrate() async {
    try {
      // Try to load persisted data first
      final persistedData = await _loadPersisted();
      if (persistedData != null) {
        final data = _deserialize(persistedData);
        state = AsyncValue.data(data);
      }
    } catch (error) {
      // Ignore hydration errors, will fetch fresh data
      debugPrint('Failed to hydrate state for $_key: $error');
    }

    // Always fetch fresh data in background
    await load();
  }

  Future<void> load() async {
    try {
      final data = await _fetcher();
      state = AsyncValue.data(data);
      // Persist the fresh data
      await _persist(_serialize(data));
    } catch (error, stackTrace) {
      state = AsyncValue.error(error, stackTrace);
    }
  }

  T _deserialize(String data) {
    // Implement deserialization logic
    throw UnimplementedError();
  }

  String _serialize(T data) {
    // Implement serialization logic
    throw UnimplementedError();
  }
}

// State composition and derived state
final workspaceStatsProvider = Provider<WorkspaceStats>((ref) {
  final workspacesAsync = ref.watch(workspacesProvider);

  return workspacesAsync.maybeWhen(
    data: (workspaces) {
      final totalMembers = workspaces.fold<int>(
        0,
        (sum, workspace) => sum + workspace.members.length,
      );

      final adminWorkspaces = workspaces.where(
        (workspace) => workspace.members.any(
          (member) => member.role == WorkspaceRole.admin,
        ),
      ).length;

      return WorkspaceStats(
        totalWorkspaces: workspaces.length,
        totalMembers: totalMembers,
        adminWorkspaces: adminWorkspaces,
      );
    },
    orElse: () => WorkspaceStats.empty(),
  );
});

class WorkspaceStats {
  final int totalWorkspaces;
  final int totalMembers;
  final int adminWorkspaces;

  WorkspaceStats({
    required this.totalWorkspaces,
    required this.totalMembers,
    required this.adminWorkspaces,
  });

  factory WorkspaceStats.empty() => WorkspaceStats(
    totalWorkspaces: 0,
    totalMembers: 0,
    adminWorkspaces: 0,
  );
}
```

### State Management Best Practices

```dart
// State management patterns and best practices

// 1. Provider composition
final complexWorkspaceProvider = Provider<ComplexWorkspaceData>((ref) {
  final workspace = ref.watch(workspaceProvider('ws_123'));
  final wallet = ref.watch(teamWalletProvider('ws_123'));
  final auditTrail = ref.watch(auditTrailProvider('ws_123'));

  return workspace.maybeWhen(
    data: (workspaceData) => wallet.maybeWhen(
      data: (walletData) => auditTrail.maybeWhen(
        data: (auditData) => ComplexWorkspaceData(
          workspace: workspaceData,
          wallet: walletData,
          auditTrail: auditData,
        ),
        orElse: () => null,
      ),
      orElse: () => null,
    ),
    orElse: () => null,
  );
});

// 2. State selectors for performance
final workspaceNamesProvider = Provider<List<String>>((ref) {
  return ref.watch(workspacesProvider).maybeWhen(
    data: (workspaces) => workspaces.map((w) => w.name).toList(),
    orElse: () => [],
  );
});

// 3. State guards and validation
final validWorkspaceProvider = Provider<Workspace?>((ref) {
  final workspaceAsync = ref.watch(workspaceProvider('ws_123'));

  return workspaceAsync.maybeWhen(
    data: (workspace) {
      // Validate workspace has required fields
      if (workspace.name.isEmpty || workspace.members.isEmpty) {
        return null;
      }
      return workspace;
    },
    orElse: () => null,
  );
});

// 4. State transformation and filtering
final activeTokenRequestsProvider = Provider<List<TokenRequest>>((ref) {
  return ref.watch(tokenRequestsProvider('ws_123')).maybeWhen(
    data: (requests) => requests.where((request) =>
      request.status == TokenRequestStatus.pending &&
      request.expiresAt.isAfter(DateTime.now())
    ).toList(),
    orElse: () => [],
  );
});

// 5. State debouncing for search/filter
class DebouncedNotifier<T> extends StateNotifier<T> {
  DebouncedNotifier(T initialValue) : super(initialValue);

  Timer? _debounceTimer;

  void debounce(Duration duration, T value) {
    _debounceTimer?.cancel();
    _debounceTimer = Timer(duration, () {
      state = value;
    });
  }

  @override
  void dispose() {
    _debounceTimer?.cancel();
    super.dispose();
  }
}

final workspaceSearchProvider = StateNotifierProvider<DebouncedNotifier<String>, String>((ref) {
  return DebouncedNotifier('');
});

final filteredWorkspacesProvider = Provider<List<Workspace>>((ref) {
  final workspaces = ref.watch(workspacesProvider).value ?? [];
  final searchQuery = ref.watch(workspaceSearchProvider);

  if (searchQuery.isEmpty) return workspaces;

  return workspaces.where((workspace) =>
    workspace.name.toLowerCase().contains(searchQuery.toLowerCase()) ||
    workspace.description?.toLowerCase().contains(searchQuery.toLowerCase()) == true
  ).toList();
});
```

## UI Integration Examples

### Workspace List Screen

```dart
class WorkspaceListScreen extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final workspacesAsync = ref.watch(workspacesProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('My Workspaces')),
      body: workspacesAsync.when(
        data: (workspaces) => ListView.builder(
          itemCount: workspaces.length,
          itemBuilder: (context, index) {
            final workspace = workspaces[index];
            return Card(
              margin: const EdgeInsets.all(8),
              child: ListTile(
                title: Text(workspace.name),
                subtitle: Text('Role: ${workspace.role.displayName}'),
                trailing: IconButton(
                  icon: const Icon(Icons.arrow_forward),
                  onPressed: () {
                    // Navigate to workspace details
                  },
                ),
              ),
            );
          },
        ),
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => Center(child: Text('Error: $error')),
      ),
    );
  }
}
```

### Workspace Details Screen

```dart
class WorkspaceDetailsScreen extends ConsumerWidget {
  final String workspaceId;

  const WorkspaceDetailsScreen({required this.workspaceId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final workspaceAsync = ref.watch(workspaceProvider(workspaceId));

    return Scaffold(
      appBar: AppBar(title: const Text('Workspace Details')),
      body: workspaceAsync.when(
        data: (workspace) => Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Name: ${workspace.name}', style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 8),
              Text('Description: ${workspace.description ?? 'N/A'}'),
              const SizedBox(height: 16),
              Text('Members', style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 8),
              Expanded(
                child: ListView.builder(
                  itemCount: workspace.members.length,
                  itemBuilder: (context, index) {
                    final member = workspace.members[index];
                    return ListTile(
                      title: Text(member.userId),
                      subtitle: Text('Role: ${member.role.displayName}'),
                    );
                  },
                ),
              ),
            ],
          ),
        ),
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => Center(child: Text('Error: $error')),
      ),
    );
  }
}
```

### Team Wallet Dashboard

```dart
class TeamWalletDashboard extends ConsumerWidget {
  final String workspaceId;

  const TeamWalletDashboard({required this.workspaceId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final walletAsync = ref.watch(teamWalletProvider(workspaceId));

    return Scaffold(
      appBar: AppBar(title: const Text('Team Wallet')),
      body: walletAsync.when(
        data: (wallet) => wallet != null
            ? _buildWalletContent(context, ref, wallet)
            : _buildWalletNotInitialized(context, ref),
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text('Error loading wallet: $error'),
              ElevatedButton(
                onPressed: () => ref.invalidate(teamWalletProvider(workspaceId)),
                child: const Text('Retry'),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildWalletNotInitialized(BuildContext context, WidgetRef ref) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.account_balance_wallet, size: 64, color: Colors.grey),
          const SizedBox(height: 16),
          const Text('Team wallet not initialized'),
          const SizedBox(height: 16),
          ElevatedButton(
            onPressed: () => ref.read(teamWalletProvider(workspaceId).notifier).initializeWallet(),
            child: const Text('Initialize Wallet'),
          ),
        ],
      ),
    );
  }

  Widget _buildWalletContent(BuildContext context, WidgetRef ref, TeamWallet wallet) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Balance Card
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Balance', style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: 8),
                  Text(
                    '${wallet.balance} SBD',
                    style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                      color: wallet.isFrozen ? Colors.red : Colors.green,
                    ),
                  ),
                  if (wallet.isFrozen) ...[
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        Icon(Icons.lock, color: Colors.red, size: 16),
                        const SizedBox(width: 4),
                        Text(
                          'Account Frozen',
                          style: TextStyle(color: Colors.red, fontWeight: FontWeight.bold),
                        ),
                      ],
                    ),
                  ],
                ],
              ),
            ),
          ),

          const SizedBox(height: 16),

          // Quick Actions
          Row(
            children: [
              Expanded(
                child: ElevatedButton.icon(
                  onPressed: () => _showCreateTokenRequestDialog(context, ref),
                  icon: const Icon(Icons.add),
                  label: const Text('Request Tokens'),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: () => _showPendingRequests(context, ref),
                  icon: const Icon(Icons.pending),
                  label: const Text('Pending Requests'),
                ),
              ),
            ],
          ),

          const SizedBox(height: 16),

          // Recent Transactions
          Text('Recent Transactions', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          if (wallet.recentTransactions.isEmpty)
            const Text('No recent transactions')
          else
            ListView.builder(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              itemCount: wallet.recentTransactions.length,
              itemBuilder: (context, index) {
                final transaction = wallet.recentTransactions[index];
                return ListTile(
                  title: Text(transaction.description),
                  subtitle: Text(transaction.timestamp.toString()),
                  trailing: Text(
                    '${transaction.type == 'credit' ? '+' : '-'}${transaction.amount} SBD',
                    style: TextStyle(
                      color: transaction.type == 'credit' ? Colors.green : Colors.red,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                );
              },
            ),

          const SizedBox(height: 16),

          // Admin Actions (if user is admin)
          if (_isAdmin(wallet.userPermissions)) ...[
            Text('Admin Actions', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                OutlinedButton.icon(
                  onPressed: () => _showFreezeAccountDialog(context, ref, wallet.isFrozen),
                  icon: Icon(wallet.isFrozen ? Icons.lock_open : Icons.lock),
                  label: Text(wallet.isFrozen ? 'Unfreeze Account' : 'Freeze Account'),
                ),
                OutlinedButton.icon(
                  onPressed: () => _showAuditTrail(context, ref),
                  icon: const Icon(Icons.history),
                  label: const Text('Audit Trail'),
                ),
                OutlinedButton.icon(
                  onPressed: () => _showComplianceReport(context, ref),
                  icon: const Icon(Icons.assignment),
                  label: const Text('Compliance Report'),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }

  bool _isAdmin(Map<String, dynamic> permissions) {
    return permissions['can_spend'] == true || permissions['spending_limit'] == -1;
  }

  void _showCreateTokenRequestDialog(BuildContext context, WidgetRef ref) {
    showDialog(
      context: context,
      builder: (context) => CreateTokenRequestDialog(
        onCreate: (amount, reason) {
          ref.read(teamWalletProvider(workspaceId).notifier)
              .createTokenRequest(amount, reason);
        },
      ),
    );
  }

  void _showPendingRequests(BuildContext context, WidgetRef ref) {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (context) => PendingTokenRequestsScreen(workspaceId: workspaceId),
      ),
    );
  }

  void _showFreezeAccountDialog(BuildContext context, WidgetRef ref, bool isFrozen) {
    showDialog(
      context: context,
      builder: (context) => FreezeAccountDialog(
        isFrozen: isFrozen,
        onAction: (action, reason) {
          // Implement freeze/unfreeze logic
        },
      ),
    );
  }

  void _showAuditTrail(BuildContext context, WidgetRef ref) {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (context) => AuditTrailScreen(workspaceId: workspaceId),
      ),
    );
  }

  void _showComplianceReport(BuildContext context, WidgetRef ref) {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (context) => ComplianceReportScreen(workspaceId: workspaceId),
      ),
    );
  }
}
```

### Token Request Creation Dialog

```dart
class CreateTokenRequestDialog extends StatefulWidget {
  final void Function(int amount, String reason) onCreate;

  const CreateTokenRequestDialog({required this.onCreate});

  @override
  _CreateTokenRequestDialogState createState() => _CreateTokenRequestDialogState();
}

class _CreateTokenRequestDialogState extends State<CreateTokenRequestDialog> {
  final _amountController = TextEditingController();
  final _reasonController = TextEditingController();
  bool _isLoading = false;

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Request Tokens'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          TextField(
            controller: _amountController,
            decoration: const InputDecoration(
              labelText: 'Amount',
              hintText: 'Enter amount of tokens',
            ),
            keyboardType: TextInputType.number,
          ),
          const SizedBox(height: 16),
          TextField(
            controller: _reasonController,
            decoration: const InputDecoration(
              labelText: 'Reason',
              hintText: 'Why do you need these tokens?',
            ),
            maxLines: 3,
          ),
        ],
      ),
      actions: [
        TextButton(
          onPressed: _isLoading ? null : () => Navigator.pop(context),
          child: const Text('Cancel'),
        ),
        ElevatedButton(
          onPressed: _isLoading ? null : _createRequest,
          child: _isLoading
              ? const SizedBox(
                  width: 20,
                  height: 20,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Text('Request'),
        ),
      ],
    );
  }

  Future<void> _createRequest() async {
    final amount = int.tryParse(_amountController.text);
    final reason = _reasonController.text.trim();

    if (amount == null || amount <= 0) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please enter a valid amount')),
      );
      return;
    }

    if (reason.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please provide a reason')),
      );
      return;
    }

    setState(() => _isLoading = true);
    try {
      widget.onCreate(amount, reason);
      Navigator.pop(context);
    } catch (error) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to create request: $error')),
      );
    } finally {
      setState(() => _isLoading = false);
    }
  }

  @override
  void dispose() {
    _amountController.dispose();
    _reasonController.dispose();
    super.dispose();
  }
}
```

### Pending Token Requests Screen

```dart
class PendingTokenRequestsScreen extends ConsumerWidget {
  final String workspaceId;

  const PendingTokenRequestsScreen({required this.workspaceId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final requestsAsync = ref.watch(tokenRequestsProvider(workspaceId));

    return Scaffold(
      appBar: AppBar(title: const Text('Pending Token Requests')),
      body: requestsAsync.when(
        data: (requests) => requests.isEmpty
            ? const Center(child: Text('No pending requests'))
            : ListView.builder(
                itemCount: requests.length,
                itemBuilder: (context, index) {
                  final request = requests[index];
                  return TokenRequestCard(
                    request: request,
                    onReview: (action, comments) {
                      ref.read(tokenRequestsProvider(workspaceId).notifier)
                          .reviewRequest(request.requestId, action, comments: comments);
                    },
                  );
                },
              ),
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => Center(child: Text('Error: $error')),
      ),
    );
  }
}

class TokenRequestCard extends StatelessWidget {
  final TokenRequest request;
  final void Function(String action, String? comments) onReview;

  const TokenRequestCard({required this.request, required this.onReview});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.all(8),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    'Request #${request.requestId.substring(0, 8)}',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                ),
                Chip(
                  label: Text(request.status.displayName),
                  backgroundColor: request.status.color.withOpacity(0.2),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text('Amount: ${request.amount} SBD'),
            Text('Reason: ${request.reason}'),
            Text('Requested: ${request.createdAt.toString()}'),
            if (request.adminComments != null) ...[
              const SizedBox(height: 8),
              Text('Comments: ${request.adminComments}'),
            ],
            const SizedBox(height: 16),
            if (request.status == TokenRequestStatus.pending) ...[
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed: () => _showReviewDialog(context, 'deny'),
                      child: const Text('Deny'),
                      style: OutlinedButton.styleFrom(
                        side: const BorderSide(color: Colors.red),
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: ElevatedButton(
                      onPressed: () => _showReviewDialog(context, 'approve'),
                      child: const Text('Approve'),
                    ),
                  ),
                ],
              ),
            ],
          },
        ),
      ),
    );
  }

  void _showReviewDialog(BuildContext context, String action) {
    showDialog(
      context: context,
      builder: (context) => ReviewTokenRequestDialog(
        action: action,
        onReview: (comments) => onReview(action, comments),
      ),
    );
  }
}

class ReviewTokenRequestDialog extends StatefulWidget {
  final String action;
  final void Function(String? comments) onReview;

  const ReviewTokenRequestDialog({required this.action, required this.onReview});

  @override
  _ReviewTokenRequestDialogState createState() => _ReviewTokenRequestDialogState();
}

class _ReviewTokenRequestDialogState extends State<ReviewTokenRequestDialog> {
  final _commentsController = TextEditingController();

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text('${widget.action == 'approve' ? 'Approve' : 'Deny'} Request'),
      content: TextField(
        controller: _commentsController,
        decoration: const InputDecoration(
          labelText: 'Comments (Optional)',
          hintText: 'Add any comments...',
        ),
        maxLines: 3,
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Cancel'),
        ),
        ElevatedButton(
          onPressed: () {
            widget.onReview(_commentsController.text.trim().isEmpty
                ? null
                : _commentsController.text.trim());
            Navigator.pop(context);
          },
          child: Text(widget.action == 'approve' ? 'Approve' : 'Deny'),
        ),
      ],
    );
  }

  @override
  void dispose() {
    _commentsController.dispose();
    super.dispose();
  }
}
```

### Audit Trail Screen

```dart
class AuditTrailScreen extends ConsumerWidget {
  final String workspaceId;

  const AuditTrailScreen({required this.workspaceId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final auditAsync = ref.watch(auditTrailProvider(workspaceId));

    return Scaffold(
      appBar: AppBar(title: const Text('Audit Trail')),
      body: auditAsync.when(
        data: (entries) => entries.isEmpty
            ? const Center(child: Text('No audit entries'))
            : ListView.builder(
                itemCount: entries.length,
                itemBuilder: (context, index) {
                  final entry = entries[index];
                  return AuditEntryCard(entry: entry);
                },
              ),
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => Center(child: Text('Error: $error')),
      ),
    );
  }
}

class AuditEntryCard extends StatelessWidget {
  final AuditEntry entry;

  const AuditEntryCard({required this.entry});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.all(8),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    entry.eventType.displayName,
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                ),
                Text(
                  entry.timestamp.toString(),
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ),
            if (entry.adminUsername != null) ...[
              const SizedBox(height: 4),
              Text('Admin: ${entry.adminUsername}'),
            ],
            if (entry.action != null) ...[
              const SizedBox(height: 4),
              Text('Action: ${entry.action}'),
            ],
            if (entry.reason != null) ...[
              const SizedBox(height: 4),
              Text('Reason: ${entry.reason}'),
            ],
            const SizedBox(height: 8),
            Text(
              'Integrity Hash: ${entry.integrityHash.substring(0, 16)}...',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                fontFamily: 'monospace',
              ),
            ),
          ],
        ),
      ),
    );
  }
}
```

## Testing

### Testing Coverage Goals

Aim for comprehensive test coverage across different layers:

- **Unit Tests**: 80%+ coverage for business logic, data models, and utilities
- **Widget Tests**: All UI components with different states (loading, error, data)
- **Integration Tests**: API integration, state management, and end-to-end flows
- **E2E Tests**: Critical user journeys (create workspace, manage members, wallet operations)

### Unit Testing Team Wallet Models

```dart
void main() {
  group('Team Wallet Models', () {
    test('TeamWallet.fromJson creates correct instance', () {
      final json = {
        'workspace_id': 'ws_123',
        'account_username': 'team_ws_123_abc123',
        'balance': 1000,
        'is_frozen': false,
        'user_permissions': {'can_spend': true, 'spending_limit': -1},
        'notification_settings': {},
        'recent_transactions': [
          {
            'transaction_id': 'txn_123',
            'type': 'transfer',
            'amount': 100,
            'timestamp': '2024-01-01T00:00:00Z',
            'description': 'Token request fulfillment'
          }
        ]
      };

      final wallet = TeamWallet.fromJson(json);

      expect(wallet.workspaceId, 'ws_123');
      expect(wallet.accountUsername, 'team_ws_123_abc123');
      expect(wallet.balance, 1000);
      expect(wallet.isFrozen, false);
      expect(wallet.recentTransactions.length, 1);
    });

    test('TokenRequestStatus enum has correct properties', () {
      expect(TokenRequestStatus.pending.displayName, 'Pending');
      expect(TokenRequestStatus.approved.color, Colors.green);
      expect(TokenRequestStatus.denied.color, Colors.red);
    });

    test('AuditEventType enum has correct display names', () {
      expect(AuditEventType.sbdTransaction.displayName, 'SBD Transaction');
      expect(AuditEventType.permissionChange.displayName, 'Permission Change');
      expect(AuditEventType.accountFreeze.displayName, 'Account Freeze');
    });
  });
}
```

### Integration Testing Team Wallet Features

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
// Use a mock HTTP client for testing instead of DioAdapter
// You can use mockito or a similar mocking library

void main() {
  group('Team Wallet Integration Tests', () {
    late ProviderContainer container;
    // Use a mock HttpClient instead of DioAdapter
    late MockHttpClient mockHttpClient;

    setUp(() {
      container = ProviderContainer();
      mockHttpClient = MockHttpClient();
    });

    tearDown(() {
      container.dispose();
    });

    test('teamWalletProvider loads wallet correctly', () async {
      // Mock the HTTP response
      when(mockHttpClient.get('${ApiConstants.workspaces}/ws_123${ApiConstants.wallet}'))
          .thenAnswer((_) async => {
                'data': {
                  'workspace_id': 'ws_123',
                  'account_username': 'team_ws_123_abc123',
                  'balance': 1000,
                  'is_frozen': false,
                  'user_permissions': {'can_spend': true, 'spending_limit': -1},
                  'notification_settings': {},
                  'recent_transactions': []
                }
              });

      // Override the httpClientProvider with our mock
      final notifier = container.read(teamWalletProvider('ws_123').notifier);
      await notifier.loadWallet();

      final state = container.read(teamWalletProvider('ws_123'));
      expect(state.value?.balance, 1000);
      expect(state.value?.isFrozen, false);
    });

    test('tokenRequestsProvider loads pending requests', () async {
      // Mock the HTTP response
      when(mockHttpClient.get('${ApiConstants.workspaces}/ws_123${ApiConstants.wallet}${ApiConstants.tokenRequests}/pending'))
          .thenAnswer((_) async => {
                'data': [
                  {
                    'request_id': 'req_123',
                    'requester_user_id': 'user_456',
                    'amount': 500,
                    'reason': 'Project funding',
                    'status': 'pending',
                    'auto_approved': false,
                    'created_at': '2024-01-01T00:00:00Z',
                    'expires_at': '2024-01-08T00:00:00Z'
                  }
                ]
              });

      final notifier = container.read(tokenRequestsProvider('ws_123').notifier);
      await notifier.loadPendingRequests();

      final state = container.read(tokenRequestsProvider('ws_123'));
      expect(state.value?.length, 1);
      expect(state.value?[0].amount, 500);
      expect(state.value?[0].status, TokenRequestStatus.pending);
    });
  });
}

// Mock HttpClient for testing
class MockHttpClient implements HttpClient {
  final Map<String, dynamic> _responses = {};

  void mockGet(String url, dynamic response) {
    _responses['GET:$url'] = response;
  }

  void mockPost(String url, dynamic response) {
    _responses['POST:$url'] = response;
  }

  @override
  Future<Map<String, dynamic>> get(String url, {Map<String, String>? headers}) async {
    final key = 'GET:$url';
    if (_responses.containsKey(key)) {
      return _responses[key];
    }
    throw Exception('No mock response for GET $url');
  }

  @override
  Future<Map<String, dynamic>> post(String url, {Map<String, String>? headers, dynamic data}) async {
    final key = 'POST:$url';
    if (_responses.containsKey(key)) {
      return _responses[key];
    }
    throw Exception('No mock response for POST $url');
  }

  @override
  Future<Map<String, dynamic>> put(String url, {Map<String, String>? headers, dynamic data}) async {
    final key = 'PUT:$url';
    if (_responses.containsKey(key)) {
      return _responses[key];
    }
    throw Exception('No mock response for PUT $url');
  }

  @override
  Future<void> delete(String url, {Map<String, String>? headers}) async {
    final key = 'DELETE:$url';
    if (_responses.containsKey(key)) {
      return;
    }
    throw Exception('No mock response for DELETE $url');
  }
}
```
```

### Widget Testing Team Wallet Components

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('TeamWalletDashboard', () {
    testWidgets('displays wallet balance correctly', (tester) async {
      final mockWallet = TeamWallet(
        workspaceId: 'ws_123',
        accountUsername: 'team_ws_123_abc123',
        balance: 1000,
        isFrozen: false,
        userPermissions: {'can_spend': true, 'spending_limit': -1},
        notificationSettings: {},
        recentTransactions: [],
      );

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            teamWalletProvider('ws_123').overrideWith((ref) => AsyncValue.data(mockWallet)),
          ],
          child: const MaterialApp(home: TeamWalletDashboard(workspaceId: 'ws_123')),
        ),
      );

      expect(find.text('1000 SBD'), findsOneWidget);
      expect(find.text('Account Frozen'), findsNothing);
    });

    testWidgets('shows frozen account warning', (tester) async {
      final mockWallet = TeamWallet(
        workspaceId: 'ws_123',
        accountUsername: 'team_ws_123_abc123',
        balance: 1000,
        isFrozen: true,
        frozenBy: 'admin_user',
        frozenAt: DateTime.now(),
        userPermissions: {'can_spend': false, 'spending_limit': 0},
        notificationSettings: {},
        recentTransactions: [],
      );

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            teamWalletProvider('ws_123').overrideWith((ref) => AsyncValue.data(mockWallet)),
          ],
          child: const MaterialApp(home: TeamWalletDashboard(workspaceId: 'ws_123')),
        ),
      );

      expect(find.text('Account Frozen'), findsOneWidget);
      expect(find.text('1000 SBD'), findsOneWidget);
    });

    testWidgets('displays recent transactions', (tester) async {
      final mockTransactions = [
        WalletTransaction(
          transactionId: 'txn_123',
          type: 'transfer',
          amount: 100,
          timestamp: DateTime.now(),
          description: 'Token request fulfillment',
        ),
      ];

      final mockWallet = TeamWallet(
        workspaceId: 'ws_123',
        accountUsername: 'team_ws_123_abc123',
        balance: 900,
        isFrozen: false,
        userPermissions: {'can_spend': true, 'spending_limit': -1},
        notificationSettings: {},
        recentTransactions: mockTransactions,
      );

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            teamWalletProvider('ws_123').overrideWith((ref) => AsyncValue.data(mockWallet)),
          ],
          child: const MaterialApp(home: TeamWalletDashboard(workspaceId: 'ws_123')),
        ),
      );

      expect(find.text('Token request fulfillment'), findsOneWidget);
    });
  });
}
```

## API Rate Limits

### Rate Limits (per hour)
- Workspace creation: 5
- Member management: 20
- Team wallet initialization: 5
- Token requests: 10
- Token request reviews: 20
- Spending permission updates: 5
- Account freeze/unfreeze: 3
- Audit trail access: 10
- Compliance report generation: 5
- Emergency recovery operations: 1

### Handling Rate Limits

```dart
class RateLimitHandler extends ConsumerStatefulWidget {
  final Widget child;
  final VoidCallback onRetry;

  const RateLimitHandler({
    required this.child,
    required this.onRetry,
  });

  @override
  _RateLimitHandlerState createState() => _RateLimitHandlerState();
}

class _RateLimitHandlerState extends ConsumerState<RateLimitHandler> {
  Timer? _retryTimer;
  int _secondsRemaining = 0;

  @override
  void dispose() {
    _retryTimer?.cancel();
    super.dispose();
  }

  void _handleRateLimit(RateLimitException error) {
    setState(() {
      _secondsRemaining = error.retryAfter.inSeconds;
    });

    _retryTimer?.cancel();
    _retryTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
      setState(() {
        _secondsRemaining--;
      });

      if (_secondsRemaining <= 0) {
        timer.cancel();
        widget.onRetry();
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    ref.listen<WorkspaceException?>(errorProvider, (previous, current) {
      if (current is RateLimitException) {
        _handleRateLimit(current);
      }
    });

    if (_secondsRemaining > 0) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.timer, size: 64, color: Colors.orange),
            const SizedBox(height: 16),
            Text(
              'Rate limit exceeded',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 8),
            Text(
              'Please wait $_secondsRemaining seconds before trying again',
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 16),
            CircularProgressIndicator(
              value: _secondsRemaining / 60,
            ),
          ],
        ),
      );
    }

    return widget.child;
  }
}
```

## Common Pitfalls

### Team Wallet Integration Issues

1. **Wallet Not Initialized**: Always check if the team wallet is initialized before accessing wallet features
2. **Permission Checks**: Verify user permissions before showing wallet actions
3. **Rate Limiting**: Implement proper rate limit handling for wallet operations
4. **Transaction Safety**: Handle transaction failures gracefully with proper error messages
5. **Audit Trail Access**: Only admins can access audit trails and compliance reports
6. **Emergency Recovery**: Backup admin features should be used sparingly and with proper documentation

### State Management Best Practices

1. **Cache frequently accessed data** (workspace info, member lists, wallet balances)
2. **Implement retry logic** for network failures
3. **Validate data** before API calls
4. **Show loading states** during async operations
5. **Handle token refresh** automatically
6. **Log errors** for debugging
7. **Use enums for roles and statuses** to avoid magic strings
8. **Document API responses and errors** for easier debugging
9. **Regularly review permissions and roles** to ensure least privilege access
10. **Test error handling and edge cases** thoroughly

### Security Considerations

1. **Never store sensitive wallet data** in local storage
2. **Always validate user permissions** on the server side
3. **Use HTTPS** for all wallet-related API calls
4. **Implement proper session management** for wallet operations
5. **Log security events** for audit purposes
6. **Regularly rotate API tokens** and credentials
7. **Implement multi-factor authentication** for admin operations
8. **Monitor for suspicious activity** in audit trails
9. **Use encrypted communication** for sensitive operations
10. **Follow principle of least privilege** for all wallet operations


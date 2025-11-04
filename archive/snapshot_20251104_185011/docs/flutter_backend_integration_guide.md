# Flutter-Backend Integration Guide

## Overview

This document provides comprehensive guidance for the Flutter team to integrate with the current backend implementation. The backend is stable and production-ready, so all adaptations should be made on the Flutter side to maintain system quality and stability.

## Key Integration Points

### 1. Authentication
- Use JWT Bearer tokens in Authorization header
- Backend expects: `Authorization: Bearer <token>`
- All workspace and wallet endpoints require authentication

### 2. Data Model Mappings

#### Workspace Response Mapping
Backend response fields need to be mapped to Flutter's expected field names:

| Backend Field | Flutter Field | Type | Notes |
|---------------|---------------|------|-------|
| `workspace_id` | `id` | String | Primary identifier |
| `name` | `name` | String | Workspace display name |
| `description` | `description` | String | Optional description |
| `created_at` | `createdAt` | DateTime | ISO 8601 format |
| `updated_at` | `updatedAt` | DateTime | ISO 8601 format |
| `owner_id` | `ownerId` | String | User ID of workspace owner |
| `members` | `members` | List<Member> | Array of workspace members |
| `wallet_initialized` | `walletInitialized` | Boolean | Whether team wallet is set up |

#### Member Object Mapping
| Backend Field | Flutter Field | Type | Notes |
|---------------|---------------|------|-------|
| `user_id` | `userId` | String | User identifier |
| `email` | `email` | String | User email |
| `role` | `role` | String | Mapped role (see role mapping below) |
| `joined_at` | `joinedAt` | DateTime | ISO 8601 format |

#### Team Wallet Response Mapping
| Backend Field | Flutter Field | Type | Notes |
|---------------|---------------|------|-------|
| `workspace_id` | `workspaceId` | String | Associated workspace |
| `balance` | `balance` | Number | Current SBD balance |
| `is_frozen` | `isFrozen` | Boolean | Whether account is frozen |
| `frozen_by` | `frozenBy` | String | User who froze account |
| `frozen_at` | `frozenAt` | DateTime | When account was frozen |
| `user_permissions` | `userPermissions` | Object | Spending permissions |
| `notification_settings` | `notificationSettings` | Object | Notification preferences |
| `recent_transactions` | `recentTransactions` | Array | Recent transaction history |

#### Token Request Response Mapping
| Backend Field | Flutter Field | Type | Notes |
|---------------|---------------|------|-------|
| `request_id` | `id` | String | Request identifier |
| `requester_username` | `requesterUsername` | String | User who made request |
| `amount` | `amount` | Number | SBD amount requested |
| `reason` | `purpose` | String | Request description |
| `status` | `status` | String | pending/approved/rejected |
| `auto_approved` | `autoApproved` | Boolean | Whether auto-approved |
| `created_at` | `createdAt` | DateTime | ISO 8601 format |
| `expires_at` | `expiresAt` | DateTime | ISO 8601 format |
| `admin_comments` | `adminComments` | String | Review comments |

#### Audit Entry Response Mapping
Audit entries have varying structures based on event type. The backend returns raw dictionaries:

**Transaction Events:**
```json
{
  "_id": "string",
  "team_id": "workspace_id",
  "transaction_type": "spend|deposit",
  "amount": 100,
  "from_account": "account_name",
  "to_account": "user_id",
  "team_member_id": "user_id",
  "timestamp": "2025-10-25T10:00:00Z"
}
```

**Permission Change Events:**
```json
{
  "_id": "string",
  "team_id": "workspace_id",
  "event_type": "permission_change",
  "admin_user_id": "user_id",
  "member_permissions": {...},
  "timestamp": "2025-10-25T10:00:00Z"
}
```

**Account Freeze Events:**
```json
{
  "_id": "string",
  "team_id": "workspace_id",
  "event_type": "account_freeze",
  "admin_user_id": "user_id",
  "action": "freeze|unfreeze",
  "reason": "freeze reason",
  "timestamp": "2025-10-25T10:00:00Z"
}
```

#### Compliance Report Response Mapping
```json
{
  "team_id": "workspace_id",
  "report_type": "json|csv|pdf",
  "generated_at": "2025-10-25T10:00:00Z",
  "period": {
    "start_date": "2025-10-01T00:00:00Z",
    "end_date": "2025-10-25T23:59:59Z"
  },
  "summary": {
    "total_events": 150,
    "transaction_count": 45,
    "permission_changes": 12,
    "account_freezes": 3
  },
  "audit_trails": [...]
}
```

### 3. Role Mapping

The backend uses different role names than Flutter expects. Implement this mapping in your Flutter code:

| Backend Role | Flutter Role | Permissions |
|--------------|--------------|-------------|
| `admin` | `admin` | Full workspace and wallet control |
| `editor` | `editor` | Can create/edit content, manage wallet within limits |
| `viewer` | `viewer` | Read-only access |

**Implementation Note:** Create a utility function to convert backend roles to Flutter roles:

```dart
String mapBackendRoleToFlutter(String backendRole) {
  switch (backendRole.toLowerCase()) {
    case 'admin':
      return 'admin';
    case 'editor':
      return 'editor';
    case 'viewer':
      return 'viewer';
    default:
      return 'viewer'; // Default fallback
  }
}
```

### 4. API Endpoints

#### Workspace Endpoints
- **GET** `/workspaces` - List user's workspaces
- **POST** `/workspaces` - Create new workspace
- **GET** `/workspaces/{workspace_id}` - Get workspace details
- **PUT** `/workspaces/{workspace_id}` - Update workspace
- **DELETE** `/workspaces/{workspace_id}` - Delete workspace
- **POST** `/workspaces/{workspace_id}/members` - Add member
- **DELETE** `/workspaces/{workspace_id}/members/{user_id}` - Remove member
- **PUT** `/workspaces/{workspace_id}/members/{user_id}/role` - Update member role

#### Team Wallet Endpoints
- **POST** `/workspaces/{workspace_id}/wallet/initialize` - Initialize team wallet
- **POST** `/workspaces/{workspace_id}/wallet/init` - Initialize team wallet (deprecated alias)
- **GET** `/workspaces/{workspace_id}/wallet` - Get wallet details
- **PUT** `/workspaces/{workspace_id}/wallet/permissions` - Update spending permissions
- **PUT** `/workspaces/{workspace_id}/wallet/settings` - Update spending permissions (deprecated alias)
- **POST** `/workspaces/{workspace_id}/wallet/freeze` - Freeze wallet account
- **POST** `/workspaces/{workspace_id}/wallet/unfreeze` - Unfreeze wallet account
- **POST** `/workspaces/{workspace_id}/wallet/token-requests` - Create token request
- **GET** `/workspaces/{workspace_id}/wallet/token-requests/pending` - List pending token requests
- **GET** `/workspaces/{workspace_id}/wallet/requests` - List pending token requests (deprecated alias)
- **POST** `/workspaces/{workspace_id}/wallet/token-requests/{request_id}/review` - Review token request

#### Audit & Compliance Endpoints
- **GET** `/workspaces/{workspace_id}/wallet/audit` - Get audit trail
- **GET** `/workspaces/{workspace_id}/wallet/compliance-report` - Generate compliance reports

#### Emergency Recovery Endpoints
- **POST** `/workspaces/{workspace_id}/wallet/backup-admin` - Designate backup admin
- **DELETE** `/workspaces/{workspace_id}/wallet/backup-admin/{backup_admin_id}` - Remove backup admin
- **POST** `/workspaces/{workspace_id}/wallet/emergency-unfreeze` - Emergency unfreeze

#### Diagnostic Endpoints
- **GET** `/workspaces/diagnostic` - Debug workspace access issues

### 5. Request/Response Handling

#### Error Response Format
All errors follow this structure:
```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message",
    "details": "Additional context (optional)"
  }
}
```

#### Common HTTP Status Codes
- `200` - Success
- `201` - Created
- `400` - Bad Request (validation errors)
- `401` - Unauthorized (invalid/missing token)
- `403` - Forbidden (insufficient permissions)
- `404` - Not Found (workspace/request doesn't exist)
- `409` - Conflict (duplicate resource)
- `422` - Unprocessable Entity (validation failed)
- `500` - Internal Server Error

#### Rate Limiting
The backend implements rate limiting. If you exceed limits, you'll receive:
```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Too many requests. Please try again later."
  }
}
```

### 6. Flutter Implementation Guidelines

#### 1. Create Data Mapping Utilities
```dart
class BackendDataMapper {
  static Workspace mapWorkspaceResponse(Map<String, dynamic> backendData) {
    return Workspace(
      id: backendData['workspace_id'],
      name: backendData['name'],
      description: backendData['description'],
      createdAt: DateTime.parse(backendData['created_at']),
      updatedAt: DateTime.parse(backendData['updated_at']),
      ownerId: backendData['owner_id'],
      members: (backendData['members'] as List?)
          ?.map((m) => mapMemberResponse(m))
          ?.toList() ?? [],
      walletInitialized: backendData['wallet_initialized'] ?? false,
    );
  }

  static Member mapMemberResponse(Map<String, dynamic> backendData) {
    return Member(
      userId: backendData['user_id'],
      email: backendData['email'],
      role: mapBackendRoleToFlutter(backendData['role']),
      joinedAt: DateTime.parse(backendData['joined_at']),
    );
  }

  static TeamWallet mapWalletResponse(Map<String, dynamic> backendData) {
    return TeamWallet(
      workspaceId: backendData['workspace_id'],
      balance: backendData['balance'] ?? 0,
      isFrozen: backendData['is_frozen'] ?? false,
      frozenBy: backendData['frozen_by'],
      frozenAt: backendData['frozen_at'] != null
          ? DateTime.parse(backendData['frozen_at'])
          : null,
      userPermissions: backendData['user_permissions'] ?? {},
      notificationSettings: backendData['notification_settings'] ?? {},
      recentTransactions: (backendData['recent_transactions'] as List?)
          ?.map((t) => mapTransactionResponse(t))
          ?.toList() ?? [],
    );
  }

  static TokenRequest mapTokenRequestResponse(Map<String, dynamic> backendData) {
    return TokenRequest(
      id: backendData['request_id'],
      requesterUsername: backendData['requester_username'],
      amount: backendData['amount'],
      purpose: backendData['reason'], // Note: backend uses 'reason', Flutter uses 'purpose'
      status: backendData['status'],
      autoApproved: backendData['auto_approved'] ?? false,
      createdAt: DateTime.parse(backendData['created_at']),
      expiresAt: DateTime.parse(backendData['expires_at']),
      adminComments: backendData['admin_comments'],
    );
  }

  static AuditEntry mapAuditEntryResponse(Map<String, dynamic> backendData) {
    // Handle different audit entry types
    final eventType = backendData['event_type'] ?? backendData['transaction_type'];

    switch (eventType) {
      case 'permission_change':
        return PermissionChangeAuditEntry(
          id: backendData['_id'],
          workspaceId: backendData['team_id'],
          eventType: 'permission_change',
          adminUserId: backendData['admin_user_id'],
          memberPermissions: backendData['member_permissions'] ?? {},
          timestamp: DateTime.parse(backendData['timestamp']),
        );
      case 'account_freeze':
        return AccountFreezeAuditEntry(
          id: backendData['_id'],
          workspaceId: backendData['team_id'],
          eventType: 'account_freeze',
          adminUserId: backendData['admin_user_id'],
          action: backendData['action'],
          reason: backendData['reason'],
          timestamp: DateTime.parse(backendData['timestamp']),
        );
      case 'spend':
      case 'deposit':
        return TransactionAuditEntry(
          id: backendData['_id'],
          workspaceId: backendData['team_id'],
          transactionType: eventType,
          amount: backendData['amount'],
          fromAccount: backendData['from_account'],
          toAccount: backendData['to_account'],
          teamMemberId: backendData['team_member_id'],
          timestamp: DateTime.parse(backendData['timestamp']),
        );
      default:
        return GenericAuditEntry(
          id: backendData['_id'],
          workspaceId: backendData['team_id'],
          eventType: eventType ?? 'unknown',
          timestamp: DateTime.parse(backendData['timestamp']),
          rawData: backendData,
        );
    }
  }

  static ComplianceReport mapComplianceReportResponse(Map<String, dynamic> backendData) {
    return ComplianceReport(
      teamId: backendData['team_id'],
      reportType: backendData['report_type'],
      generatedAt: DateTime.parse(backendData['generated_at']),
      period: backendData['period'] != null ? CompliancePeriod(
        startDate: backendData['period']['start_date'] != null
            ? DateTime.parse(backendData['period']['start_date'])
            : null,
        endDate: backendData['period']['end_date'] != null
            ? DateTime.parse(backendData['period']['end_date'])
            : null,
      ) : null,
      summary: backendData['summary'] != null ? ComplianceSummary(
        totalEvents: backendData['summary']['total_events'] ?? 0,
        transactionCount: backendData['summary']['transaction_count'] ?? 0,
        permissionChanges: backendData['summary']['permission_changes'] ?? 0,
        accountFreezes: backendData['summary']['account_freezes'] ?? 0,
      ) : null,
      auditTrails: (backendData['audit_trails'] as List?)
          ?.map((entry) => mapAuditEntryResponse(entry))
          ?.toList() ?? [],
    );
  }
}
```

#### 2. API Service Layer Updates
Update your API service to use the correct backend endpoints and handle field mapping:

```dart
class WorkspaceApiService {
  Future<List<Workspace>> getWorkspaces() async {
    final response = await _client.get('/workspaces');
    final backendWorkspaces = response.data as List;
    return backendWorkspaces
        .map((w) => BackendDataMapper.mapWorkspaceResponse(w))
        .toList();
  }

  Future<Workspace> createWorkspace(CreateWorkspaceRequest request) async {
    final backendRequest = {
      'name': request.name,
      'description': request.description,
      // Map other fields as needed
    };

    final response = await _client.post('/workspaces', data: backendRequest);
    return BackendDataMapper.mapWorkspaceResponse(response.data);
  }

  Future<TeamWallet> getTeamWallet(String workspaceId) async {
    final response = await _client.get('/workspaces/$workspaceId/wallet');
    return BackendDataMapper.mapWalletResponse(response.data);
  }

  Future<List<TokenRequest>> getPendingTokenRequests(String workspaceId) async {
    final response = await _client.get('/workspaces/$workspaceId/wallet/token-requests/pending');
    final backendRequests = response.data as List;
    return backendRequests
        .map((r) => BackendDataMapper.mapTokenRequestResponse(r))
        .toList();
  }

  Future<List<AuditEntry>> getAuditTrail(String workspaceId, {
    DateTime? startDate,
    DateTime? endDate,
    int limit = 100,
  }) async {
    final queryParams = <String, dynamic>{};
    if (startDate != null) queryParams['start_date'] = startDate.toIso8601String();
    if (endDate != null) queryParams['end_date'] = endDate.toIso8601String();
    queryParams['limit'] = limit;

    final response = await _client.get(
      '/workspaces/$workspaceId/wallet/audit',
      queryParameters: queryParams,
    );

    final backendEntries = response.data as List;
    return backendEntries
        .map((entry) => BackendDataMapper.mapAuditEntryResponse(entry))
        .toList();
  }

  Future<ComplianceReport> generateComplianceReport(String workspaceId, {
    String reportType = 'json',
    DateTime? startDate,
    DateTime? endDate,
  }) async {
    final queryParams = <String, dynamic>{
      'report_type': reportType,
    };
    if (startDate != null) queryParams['start_date'] = startDate.toIso8601String();
    if (endDate != null) queryParams['end_date'] = endDate.toIso8601String();

    final response = await _client.get(
      '/workspaces/$workspaceId/wallet/compliance-report',
      queryParameters: queryParams,
    );

    return BackendDataMapper.mapComplianceReportResponse(response.data);
  }
}
```

#### 3. Error Handling
Implement proper error handling for different HTTP status codes:

```dart
class ApiErrorHandler {
  static void handleError(DioError error) {
    final statusCode = error.response?.statusCode;
    final errorData = error.response?.data?['error'];

    switch (statusCode) {
      case 400:
        final errorCode = errorData?['code'];
        switch (errorCode) {
          case 'VALIDATION_ERROR':
            throw ValidationException(errorData?['message'] ?? 'Validation error');
          case 'WALLET_NOT_INITIALIZED':
            throw WalletNotInitializedException(errorData?['message'] ?? 'Wallet not initialized');
          case 'ACCOUNT_FROZEN':
            throw AccountFrozenException(errorData?['message'] ?? 'Account is frozen');
          default:
            throw BadRequestException(errorData?['message'] ?? 'Bad request');
        }
      case 401:
        throw AuthenticationException('Invalid or expired token');
      case 403:
        final errorCode = errorData?['code'];
        switch (errorCode) {
          case 'INSUFFICIENT_PERMISSIONS':
            throw PermissionDeniedException(errorData?['message'] ?? 'Insufficient permissions');
          default:
            throw PermissionDeniedException('Access denied');
        }
      case 404:
        final errorCode = errorData?['code'];
        switch (errorCode) {
          case 'WORKSPACE_NOT_FOUND':
            throw WorkspaceNotFoundException(errorData?['message'] ?? 'Workspace not found');
          case 'TOKEN_REQUEST_NOT_FOUND':
            throw TokenRequestNotFoundException(errorData?['message'] ?? 'Token request not found');
          default:
            throw NotFoundException(errorData?['message'] ?? 'Resource not found');
        }
      case 409:
        throw ConflictException(errorData?['message'] ?? 'Resource conflict');
      case 422:
        throw ValidationException(errorData?['message'] ?? 'Validation failed');
      case 429:
        throw RateLimitException('Too many requests. Please try again later.');
      default:
        throw GenericApiException('An unexpected error occurred');
    }
  }
}

// Custom exception classes
class ValidationException implements Exception {
  final String message;
  ValidationException(this.message);
}

class WalletNotInitializedException implements Exception {
  final String message;
  WalletNotInitializedException(this.message);
}

class AccountFrozenException implements Exception {
  final String message;
  AccountFrozenException(this.message);
}

class PermissionDeniedException implements Exception {
  final String message;
  PermissionDeniedException(this.message);
}

class WorkspaceNotFoundException implements Exception {
  final String message;
  WorkspaceNotFoundException(this.message);
}

class TokenRequestNotFoundException implements Exception {
  final String message;
  TokenRequestNotFoundException(this.message);
}

class RateLimitException implements Exception {
  final String message;
  RateLimitException(this.message);
}

class GenericApiException implements Exception {
  final String message;
  GenericApiException(this.message);
}
```

### 7. Testing Recommendations

#### Unit Tests
- Test data mapping functions with various backend response formats
- Test role mapping utility with all possible backend roles
- Test error handling for different HTTP status codes and error codes
- Test date/time parsing from ISO 8601 strings

#### Integration Tests
- Test complete workspace CRUD operations
- Test wallet initialization and token request flows
- Test member management with different roles
- Test audit trail retrieval and compliance report generation
- Test error scenarios (invalid tokens, insufficient permissions, etc.)
- Test rate limiting behavior

#### Edge Cases to Test
- Workspaces without initialized wallets
- Token requests with different statuses (pending, approved, rejected, expired)
- Member role changes and permission enforcement
- Network connectivity issues and retry logic
- Large audit trails and pagination
- Different compliance report formats

### 8. Migration Checklist

- [ ] Update all endpoint URLs to match backend implementation
- [ ] Implement comprehensive data mapping utilities for all response types
- [ ] Add role mapping function and use throughout the app
- [ ] Update error handling to match backend error response structure
- [ ] Implement audit trail handling for variable data structures
- [ ] Add compliance report generation and display
- [ ] Update any hardcoded field names in UI components
- [ ] Verify authentication flow works with JWT tokens
- [ ] Test offline scenarios and error recovery
- [ ] Add rate limiting handling in UI
- [ ] Implement diagnostic endpoint integration for debugging

### 9. Backend Stability Notes

The backend implementation is production-ready and includes:
- Comprehensive error handling and logging
- Rate limiting and security measures
- Audit trails for all wallet operations with integrity hashes
- Data validation and sanitization
- Proper database transactions
- Emergency recovery mechanisms
- Compliance reporting capabilities

**Important:** The backend provides deprecated alias endpoints for Flutter compatibility, but you should plan to migrate to the correct endpoints in a future update.

### 10. Deprecated Endpoints (Temporary Compatibility)

The following endpoints are provided for backward compatibility but will be removed in a future version:

- `POST /workspaces/{id}/wallet/init` → Use `/wallet/initialize`
- `PUT /workspaces/{id}/wallet/settings` → Use `/wallet/permissions`
- `GET /workspaces/{id}/wallet/requests` → Use `/wallet/token-requests/pending`

### 11. Support and Debugging

If you encounter issues:
1. Check the diagnostic endpoint: `GET /workspaces/diagnostic`
2. Review backend logs for detailed error information
3. Verify JWT token format and validity
4. Ensure proper field mapping in requests/responses
5. Test with different user roles to verify permissions
6. Check rate limiting headers in responses

For questions or issues, provide:
- Specific error messages and codes from backend responses
- Request IDs from audit logs
- User roles and workspace membership details
- Steps to reproduce the issue

### 12. Future Considerations

- **Audit Trail Expansion:** The audit system supports additional event types that can be added to the Flutter app
- **Compliance Features:** Additional compliance reporting formats (CSV, PDF) can be integrated
- **Emergency Recovery:** Backup admin and emergency unfreeze features can be added to admin interfaces
- **Real-time Updates:** Consider implementing WebSocket connections for real-time audit trail updates
- **Offline Support:** Implement local caching for audit trails and compliance reports

---

*This integration guide ensures Flutter apps can successfully connect to the production backend while maintaining data integrity and security. All deprecated endpoints will be removed in a future major version - plan migration accordingly.*
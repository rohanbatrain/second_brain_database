# Team Wallet Frontend-Backend Integration

## Overview

This document describes the current implementation of the Team Wallet feature, including frontend-backend integration, API contracts, error handling, and development setup.

## Architecture

### Frontend Components
- **State Management**: Riverpod Notifier/FamilyNotifier for server-as-source pattern
- **API Service**: `TeamApiService` with normalization, error mapping, and mock mode support
- **UI Screens**: ConsumerStatefulWidget screens that load data on appear
- **Error Handling**: Typed exceptions with user-friendly messages

### Backend Integration
- **Base URL**: Configured via `apiBaseUrlProvider`
- **Authentication**: JWT Bearer tokens via `Authorization` header
- **Rate Limiting**: Extracted from `X-RateLimit-*` headers
- **Error Format**: Structured JSON with error codes and messages

## API Endpoints

### Workspace Management
```
GET    /workspaces                                    # List workspaces
POST   /workspaces                                    # Create workspace
GET    /workspaces/{workspaceId}                      # Get workspace details
PUT    /workspaces/{workspaceId}                      # Update workspace
DELETE /workspaces/{workspaceId}                      # Delete workspace
POST   /workspaces/{workspaceId}/members              # Add member
PUT    /workspaces/{workspaceId}/members/{memberId}   # Update member role
DELETE /workspaces/{workspaceId}/members/{memberId}   # Remove member
```

### Team Wallet
```
POST   /workspaces/{workspaceId}/wallet/initialize     # Initialize wallet
GET    /workspaces/{workspaceId}/wallet               # Get wallet details
PUT    /workspaces/{workspaceId}/wallet/permissions   # Update permissions
POST   /workspaces/{workspaceId}/wallet/freeze        # Freeze wallet
POST   /workspaces/{workspaceId}/wallet/unfreeze      # Unfreeze wallet
```

### Token Requests
```
POST   /workspaces/{workspaceId}/wallet/token-requests              # Create request
GET    /workspaces/{workspaceId}/wallet/token-requests/pending      # List pending requests
POST   /workspaces/{workspaceId}/wallet/token-requests/{requestId}/review  # Review request
```

### Audit & Compliance
```
GET    /workspaces/{workspaceId}/wallet/audit                       # Get audit trail
GET    /workspaces/{workspaceId}/wallet/compliance-report          # Generate compliance report
```

## Data Models

### TeamWorkspace
```json
{
  "workspace_id": "string",
  "name": "string",
  "description": "string?",
  "owner_id": "string",
  "members": [
    {
      "user_id": "string",
      "role": "admin|editor|viewer",
      "joined_at": "ISO8601"
    }
  ],
  "settings": {
    "allow_member_invites": "boolean",
    "default_new_member_role": "admin|editor|viewer"
  },
  "created_at": "ISO8601",
  "updated_at": "ISO8601"
}
```

### TeamWallet
```json
{
  "workspace_id": "string",
  "account_username": "string",
  "balance": "integer",  // in cents
  "is_frozen": "boolean",
  "frozen_by": "string?",
  "frozen_at": "ISO8601?",
  "user_permissions": "object",
  "notification_settings": "object",
  "recent_transactions": "array"
}
```

### TokenRequest
```json
{
  "request_id": "string",
  "requester_user_id": "string",
  "amount": "integer",  // in cents
  "reason": "string",
  "status": "pending|approved|denied|expired",
  "auto_approved": "boolean",
  "created_at": "ISO8601",
  "expires_at": "ISO8601",
  "admin_comments": "string?"
}
```

## Error Handling

### Backend Error Format
```json
{
  "error": "ERROR_CODE",
  "message": "Human readable message",
  "details": "object?"  // Optional additional context
}
```

### Frontend Exception Types
- `TeamApiException`: Base exception with status code
- `PermissionDeniedException`: 403 errors
- `RateLimitException`: 429 errors
- `ValidationException`: 400 errors
- `NetworkException`: Connection issues
- `WalletNotFoundException`: 404 for wallet
- `WorkspaceNotFoundException`: 404 for workspace
- `InsufficientFundsException`: Business logic errors

### Error Code Mapping
| Backend Code | Frontend Exception | User Message |
|-------------|-------------------|-------------|
| INSUFFICIENT_PERMISSIONS | PermissionDeniedException | "You don't have permission..." |
| RATE_LIMIT_EXCEEDED | RateLimitException | "Too many requests..." |
| INVALID_REQUEST | ValidationException | "Invalid input..." |
| WORKSPACE_NOT_FOUND | WorkspaceNotFoundException | "Workspace not found..." |
| WALLET_INSUFFICIENT_FUNDS | InsufficientFundsException | "Insufficient funds..." |

## Rate Limiting

### Header Extraction
- `X-RateLimit-Limit`: Maximum requests per window
- `X-RateLimit-Remaining`: Remaining requests in current window
- `X-RateLimit-Reset`: Unix timestamp when limit resets

### Provider
```dart
final rateLimitProvider = StateProvider<RateLimitInfo?>((ref) => null);
```

### RateLimitInfo Model
```dart
class RateLimitInfo {
  final int limit;
  final int remaining;
  final int reset;

  bool get isExceeded => remaining <= 0;
  Duration get timeUntilReset => Duration(seconds: reset - DateTime.now().millisecondsSinceEpoch ~/ 1000);
}
```

## Normalization

### Amount Handling
- Backend may send `amount` as float (e.g., 50.00) or `amount_cents` as integer
- Frontend normalizes to integer cents for consistency
- Display formatting: `(amount / 100).toStringAsFixed(2)`

### Key Mapping
- `request_id` ↔ `id` ↔ `requestId`
- `requester_user_id` ↔ `requester_id` ↔ `requesterUserId`
- `workspace_id` ↔ `workspaceId` ↔ `team_id`
- `account_username` ↔ `accountUsername` ↔ `account`

## Server-as-Source Pattern

### Provider Design
- **Notifier.build()**: Returns `AsyncValue.data(empty)` (not loading)
- **Screen.initState()**: Calls `loadXxx()` to fetch fresh data
- **Mutations**: Invalidate related providers after successful operations

### Example: Wallet Provider
```dart
class TeamWalletNotifier extends FamilyNotifier<AsyncValue<TeamWallet?>, String> {
  @override
  AsyncValue<TeamWallet?> build(String arg) => const AsyncValue.data(null);

  Future<void> loadWallet() async {
    state = const AsyncValue.loading();
    try {
      final wallet = await _api.getTeamWallet(arg);
      state = AsyncValue.data(wallet);
    } catch (error, stackTrace) {
      state = AsyncValue.error(error, stackTrace);
    }
  }

  Future<void> freezeWallet(String reason) async {
    final wallet = await _api.freezeWallet(arg, reason);
    state = AsyncValue.data(wallet);
    // Invalidate requests since freeze affects approvals
    ref.invalidate(tokenRequestsProvider(arg));
  }
}
```

## Mock Mode

### Configuration
- Enabled automatically in debug mode (`kDebugMode`)
- Can be overridden via `TeamApiService(mockMode: true)`

### Mock Data
- **Workspaces**: Single "Development Team" workspace
- **Wallet**: 500.00 SBD balance, unfrozen
- **Token Requests**: One pending request for 25.00 SBD

### Usage
```dart
final api = TeamApiService(ref, mockMode: true);
```

## Development Setup

### Running with Mock Data
```bash
flutter run  # Automatically uses mock mode in debug
```

### Testing Real Backend
```dart
// In provider override or test
final api = TeamApiService(ref, mockMode: false);
```

### Environment Variables
- `API_BASE_URL`: Backend base URL
- `ACCESS_TOKEN`: JWT token for authentication

## Testing

### Unit Tests
- API service normalization
- Error mapping
- Provider state management

### Integration Tests
- Full screen workflows
- Error scenarios
- Rate limiting

### Mock Testing
- Provider behavior with mock data
- UI rendering with mock state

## Migration Notes

### From Previous Implementation
- Removed auto-loading providers
- Added server-as-source pattern
- Implemented structured error handling
- Added rate limit tracking
- Added mock mode support

### Breaking Changes
- Provider APIs changed from auto-loading to explicit loading
- Screen widgets changed to ConsumerStatefulWidget
- Error handling now uses typed exceptions

## Future Enhancements

### Planned Features
- Real-time updates via WebSocket
- Offline mode with local caching
- Advanced audit filtering
- Bulk operations for admins

### Performance Optimizations
- Pagination for large lists
- Background refresh
- Request deduplication

### Monitoring
- API call metrics
- Error rate tracking
- Performance profiling
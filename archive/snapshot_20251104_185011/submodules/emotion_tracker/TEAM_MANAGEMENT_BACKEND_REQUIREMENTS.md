# Team Management Backend API Requirements

## Overview
The frontend team management screens have been implemented and are ready for integration. All mock data has been identified and documented for removal. The following backend API endpoints need to be implemented to complete the team management functionality.

## Mock Data to Remove
Once the backend endpoints are implemented, the following mock data arrays need to be replaced with real API calls:

### 1. Workspace Overview Screen
**File:** `lib/screens/settings/team/workspace_overview_screen.dart` (lines 436-450)
- Mock array: `recentActivities`
- Replace with: API call to audit trail endpoint

### 2. Workspace Detail Screen  
**File:** `lib/screens/settings/team/workspace_detail_screen.dart` (lines 618-630)
- Mock array: `activities`
- Replace with: API call to audit trail endpoint

## Required Backend Endpoints

### Workspace Management
```
GET /workspaces
```
- **Purpose:** List all workspaces for the authenticated user
- **Response:** Array of workspace objects

```
POST /workspaces
```
- **Purpose:** Create a new workspace
- **Body:** `{ "name": "string", "description": "string" }`
- **Response:** Created workspace object

```
GET /workspaces/{id}
```
- **Purpose:** Get detailed workspace information
- **Response:** Complete workspace object with members

```
PUT /workspaces/{id}
```
- **Purpose:** Update workspace details
- **Body:** `{ "name": "string", "description": "string", "settings": {} }`
- **Response:** Updated workspace object

```
DELETE /workspaces/{id}
```
- **Purpose:** Delete a workspace
- **Response:** 204 No Content

### Member Management
```
POST /workspaces/{id}/members
```
- **Purpose:** Add a member to workspace
- **Body:** `{ "user_id_to_add": "string", "role": "admin|member|viewer" }`
- **Response:** Updated workspace object

```
PUT /workspaces/{id}/members/{memberId}
```
- **Purpose:** Update member role
- **Body:** `{ "role": "admin|member|viewer" }`
- **Response:** Updated workspace object

```
DELETE /workspaces/{id}/members/{memberId}
```
- **Purpose:** Remove member from workspace
- **Response:** 204 No Content

### Wallet Management
```
POST /workspaces/{id}/wallet/initialize
```
- **Purpose:** Initialize team wallet
- **Body:** `{ "initial_balance": number, "currency": "string", "wallet_name": "string" }`
- **Response:** Wallet object

```
GET /workspaces/{id}/wallet
```
- **Purpose:** Get team wallet details
- **Response:** Wallet object with balance, permissions, etc.

```
POST /workspaces/{id}/wallet/token-requests
```
- **Purpose:** Request tokens from team wallet
- **Body:** `{ "amount": number, "purpose": "string", "description": "string" }`
- **Response:** Token request object

```
GET /workspaces/{id}/wallet/token-requests/pending
```
- **Purpose:** Get pending token requests for approval
- **Response:** Array of pending token request objects

```
POST /workspaces/{id}/wallet/token-requests/{requestId}/review
```
- **Purpose:** Approve or reject token request
- **Body:** `{ "action": "approve|deny", "reviewer_notes": "string" }`
- **Response:** Updated token request object

```
PUT /workspaces/{id}/wallet/permissions
```
- **Purpose:** Update wallet permissions for members
- **Body:** `{ "permissions": { "user_id": { "can_request": boolean, "can_approve": boolean } } }`
- **Response:** Updated wallet object

```
POST /workspaces/{id}/wallet/freeze
```
- **Purpose:** Freeze team wallet
- **Body:** `{ "reason": "string" }`
- **Response:** Updated wallet object

```
POST /workspaces/{id}/wallet/unfreeze
```
- **Purpose:** Unfreeze team wallet
- **Response:** Updated wallet object

### Audit & Compliance
```
GET /workspaces/{id}/wallet/audit
```
- **Purpose:** Get audit trail for wallet activities
- **Query Params:** `start_date`, `end_date`, `limit`
- **Response:** Array of audit entry objects

```
GET /workspaces/{id}/wallet/compliance-report
```
- **Purpose:** Generate compliance report
- **Query Params:** `report_type`, `start_date`, `end_date`
- **Response:** Compliance report object

### Emergency Recovery
```
POST /workspaces/{id}/wallet/backup-admin
```
- **Purpose:** Designate backup admin
- **Body:** `{ "backup_admin_id": "string" }`
- **Response:** Confirmation object

```
DELETE /workspaces/{id}/wallet/backup-admin/{backupAdminId}
```
- **Purpose:** Remove backup admin designation
- **Response:** Confirmation object

```
POST /workspaces/{id}/wallet/emergency-unfreeze
```
- **Purpose:** Emergency unfreeze (backup admin only)
- **Body:** `{ "emergency_reason": "string" }`
- **Response:** Confirmation object

## Data Models

### Workspace
```json
{
  "id": "string",
  "name": "string",
  "description": "string",
  "created_at": "ISO8601",
  "updated_at": "ISO8601",
  "settings": {},
  "members": [
    {
      "user_id": "string",
      "role": "admin|member|viewer",
      "joined_at": "ISO8601"
    }
  ]
}
```

### Team Wallet
```json
{
  "workspace_id": "string",
  "account_username": "string",
  "balance": 0, // in cents
  "is_frozen": false,
  "frozen_by": "string",
  "frozen_at": "ISO8601",
  "user_permissions": {
    "user_id": {
      "can_request": true,
      "can_approve": false
    }
  },
  "notification_settings": {},
  "recent_transactions": []
}
```

### Token Request
```json
{
  "request_id": "string",
  "requester_user_id": "string",
  "amount": 5000, // in cents
  "reason": "string",
  "status": "pending|approved|rejected",
  "auto_approved": false,
  "created_at": "ISO8601",
  "expires_at": "ISO8601",
  "admin_comments": "string"
}
```

## Authentication & Authorization
- All endpoints require Bearer token authentication
- Users can only access workspaces they are members of
- Admin role required for: creating/updating/deleting workspaces, managing members, wallet operations
- Member role required for: requesting tokens, viewing wallet
- Viewer role: read-only access

## Error Handling
Return appropriate HTTP status codes and structured error responses:
```json
{
  "error": "ERROR_CODE",
  "message": "Human readable message"
}
```

Supported error codes:
- `INSUFFICIENT_PERMISSIONS`
- `RATE_LIMIT_EXCEEDED`
- `INVALID_REQUEST`
- `WORKSPACE_NOT_FOUND`
- `WALLET_INSUFFICIENT_FUNDS`

## Rate Limiting
Implement rate limiting with headers:
- `X-RateLimit-Limit`
- `X-RateLimit-Remaining`
- `X-RateLimit-Reset`

## Next Steps
1. Implement the above endpoints
2. Test with the existing frontend code
3. Coordinate with frontend team to remove mock data
4. Conduct integration testing

---

**Document Version:** 1.0  
**Date:** October 25, 2025  
**Prepared by:** Frontend Team  
**Reviewed by:** Backend Team Lead</content>
<parameter name="filePath">/Users/rohan/Documents/repos/emotion_tracker/TEAM_MANAGEMENT_BACKEND_REQUIREMENTS.md
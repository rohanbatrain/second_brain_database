# Family Management API Documentation

## Overview

The Family Management API provides comprehensive functionality for creating families, managing relationships, and coordinating shared SBD token accounts. This API is designed with enterprise-grade security, monitoring, and error handling.

## Base URL

```
https://api.secondbraindatabase.com/family
```

## Authentication

All endpoints require authentication using one of the following methods:

### JWT Token Authentication
```http
Authorization: Bearer <jwt_token>
```

### Permanent Token Authentication
```http
Authorization: Bearer <permanent_token>
```

### Security Requirements

- **Rate Limiting**: All endpoints have operation-specific rate limits
- **IP Lockdown**: Optional IP address restrictions
- **User Agent Lockdown**: Optional user agent restrictions
- **2FA**: Required for sensitive administrative operations

## Core Concepts

### Family Structure
- **Family**: A group of users with shared relationships and resources
- **Administrator**: Users with full management permissions
- **Member**: Users with limited permissions based on their role
- **SBD Account**: Shared token account for family financial activities

### Relationship Types
Supported bidirectional relationships:
- `parent` ↔ `child`
- `sibling` ↔ `sibling`
- `spouse` ↔ `spouse`
- `grandparent` ↔ `grandchild`
- `uncle` ↔ `nephew`
- `aunt` ↔ `niece`
- `cousin` ↔ `cousin`

## API Endpoints

### Family Management

#### Create Family
Create a new family with the current user as administrator.

```http
POST /family/create
```

**Rate Limit**: 5 requests per hour per user

**Request Body**:
```json
{
  "name": "Smith Family"  // Optional, auto-generated if not provided
}
```

**Response** (201 Created):
```json
{
  "family_id": "fam_abc123def456",
  "name": "Smith Family",
  "admin_user_ids": ["user_123"],
  "member_count": 1,
  "created_at": "2024-01-01T00:00:00Z",
  "is_admin": true,
  "sbd_account": {
    "account_username": "family_smith",
    "is_frozen": false,
    "spending_permissions": {
      "user_123": {
        "role": "admin",
        "spending_limit": -1,
        "can_spend": true
      }
    }
  },
  "usage_stats": {
    "current_members": 1,
    "max_members_allowed": 5,
    "can_add_members": true
  }
}
```

**Error Responses**:
- `400 Bad Request`: Invalid family name or validation error
- `403 Forbidden`: Family limit exceeded, upgrade required
- `429 Too Many Requests`: Rate limit exceeded

#### Get My Families
Retrieve all families the current user belongs to.

```http
GET /family/my-families
```

**Rate Limit**: 20 requests per hour per user

**Response** (200 OK):
```json
[
  {
    "family_id": "fam_abc123def456",
    "name": "Smith Family",
    "admin_user_ids": ["user_123"],
    "member_count": 3,
    "created_at": "2024-01-01T00:00:00Z",
    "is_admin": true,
    "sbd_account": {
      "account_username": "family_smith",
      "is_frozen": false,
      "spending_permissions": {
        "user_123": {
          "role": "admin",
          "spending_limit": -1,
          "can_spend": true
        }
      }
    },
    "usage_stats": {
      "current_members": 3,
      "max_members_allowed": 5,
      "can_add_members": true
    }
  }
]
```

### Member Invitations

#### Invite Family Member
Send an invitation to join a family by email or username.

```http
POST /family/{family_id}/invite
```

**Rate Limit**: 10 invitations per hour per user

**Path Parameters**:
- `family_id` (string): The family identifier

**Request Body**:
```json
{
  "identifier": "john@example.com",
  "identifier_type": "email",  // "email" or "username"
  "relationship_type": "child"
}
```

**Response** (201 Created):
```json
{
  "invitation_id": "inv_abc123def456",
  "family_name": "Smith Family",
  "inviter_username": "john_smith",
  "relationship_type": "child",
  "status": "pending",
  "expires_at": "2024-01-08T00:00:00Z",
  "created_at": "2024-01-01T00:00:00Z"
}
```

**Error Responses**:
- `400 Bad Request`: Invalid relationship type or user not found
- `403 Forbidden`: Insufficient permissions or member limit exceeded
- `404 Not Found`: Family not found

#### Respond to Invitation
Accept or decline a family invitation.

```http
POST /family/invitation/{invitation_id}/respond
```

**Rate Limit**: 20 responses per hour per user

**Path Parameters**:
- `invitation_id` (string): The invitation identifier

**Request Body**:
```json
{
  "action": "accept"  // "accept" or "decline"
}
```

**Response** (200 OK):
```json
{
  "status": "success",
  "action": "accept",
  "message": "You have successfully joined the Smith Family",
  "data": {
    "family_id": "fam_abc123def456",
    "relationship_created": true
  }
}
```

#### Accept Invitation by Token (Email Link)
Accept invitation using email token (no authentication required).

```http
GET /family/invitation/{invitation_token}/accept
```

**Rate Limit**: 10 requests per hour per IP

**Path Parameters**:
- `invitation_token` (string): The secure invitation token from email

**Response** (200 OK):
```json
{
  "status": "success",
  "action": "accepted",
  "message": "Invitation accepted successfully",
  "family_id": "fam_abc123def456",
  "redirect_url": "/login?message=invitation_accepted"
}
```

#### Decline Invitation by Token (Email Link)
Decline invitation using email token (no authentication required).

```http
GET /family/invitation/{invitation_token}/decline
```

**Rate Limit**: 10 requests per hour per IP

**Path Parameters**:
- `invitation_token` (string): The secure invitation token from email

**Response** (200 OK):
```json
{
  "status": "success",
  "action": "declined",
  "message": "Invitation declined successfully",
  "redirect_url": "/login?message=invitation_declined"
}
```

#### Get Family Invitations
Retrieve all invitations for a family (admin only).

```http
GET /family/{family_id}/invitations?status=pending
```

**Rate Limit**: 20 requests per hour per user

**Path Parameters**:
- `family_id` (string): The family identifier

**Query Parameters**:
- `status` (string, optional): Filter by status (`pending`, `accepted`, `declined`, `expired`)

**Response** (200 OK):
```json
[
  {
    "invitation_id": "inv_abc123def456",
    "family_name": "Smith Family",
    "inviter_username": "john_smith",
    "relationship_type": "child",
    "status": "pending",
    "expires_at": "2024-01-08T00:00:00Z",
    "created_at": "2024-01-01T00:00:00Z"
  }
]
```

#### Resend Invitation
Resend invitation email (admin only).

```http
POST /family/{family_id}/invitations/{invitation_id}/resend
```

**Rate Limit**: 5 resends per hour per user

**Response** (200 OK):
```json
{
  "status": "success",
  "message": "Invitation email resent successfully",
  "email_sent": true,
  "resent_at": "2024-01-01T12:00:00Z"
}
```

#### Cancel Invitation
Cancel a pending invitation (admin only).

```http
DELETE /family/{family_id}/invitations/{invitation_id}
```

**Rate Limit**: 10 cancellations per hour per user

**Response** (200 OK):
```json
{
  "status": "success",
  "message": "Invitation cancelled successfully",
  "cancelled_at": "2024-01-01T12:00:00Z"
}
```

### SBD Token Account Management

#### Get Family SBD Account
Retrieve family SBD account information.

```http
GET /family/{family_id}/sbd-account
```

**Rate Limit**: 30 requests per hour per user

**Response** (200 OK):
```json
{
  "account_username": "family_smith",
  "balance": 1500,
  "is_frozen": false,
  "frozen_by": null,
  "frozen_at": null,
  "spending_permissions": {
    "user_123": {
      "role": "admin",
      "spending_limit": -1,
      "can_spend": true,
      "updated_by": "user_123",
      "updated_at": "2024-01-01T00:00:00Z"
    },
    "user_456": {
      "role": "member",
      "spending_limit": 100,
      "can_spend": true,
      "updated_by": "user_123",
      "updated_at": "2024-01-01T00:00:00Z"
    }
  },
  "notification_settings": {
    "notify_on_spend": true,
    "notify_on_deposit": true,
    "large_transaction_threshold": 1000
  },
  "recent_transactions": [
    {
      "transaction_id": "txn_123",
      "amount": -50,
      "description": "Family grocery shopping",
      "user_id": "user_456",
      "timestamp": "2024-01-01T10:00:00Z"
    }
  ]
}
```

#### Update Spending Permissions
Update member spending permissions (admin only).

```http
PUT /family/{family_id}/sbd-account/permissions
```

**Rate Limit**: 10 updates per hour per user

**Request Body**:
```json
{
  "user_id": "user_456",
  "spending_limit": 200,
  "can_spend": true
}
```

**Response** (200 OK):
```json
{
  "status": "success",
  "message": "Spending permissions updated successfully",
  "updated_permissions": {
    "user_id": "user_456",
    "role": "member",
    "spending_limit": 200,
    "can_spend": true,
    "updated_by": "user_123",
    "updated_at": "2024-01-01T12:00:00Z"
  }
}
```

#### Freeze/Unfreeze Account
Freeze or unfreeze family SBD account (admin only).

```http
POST /family/{family_id}/sbd-account/freeze
```

**Rate Limit**: 5 freeze operations per hour per user

**Request Body**:
```json
{
  "freeze": true,
  "reason": "Suspicious activity detected"
}
```

**Response** (200 OK):
```json
{
  "status": "success",
  "message": "Family account frozen successfully",
  "account_status": {
    "is_frozen": true,
    "frozen_by": "user_123",
    "frozen_at": "2024-01-01T12:00:00Z",
    "reason": "Suspicious activity detected"
  }
}
```

### Token Request Workflow

#### Create Token Request
Request tokens from family account.

```http
POST /family/{family_id}/token-request
```

**Rate Limit**: 10 requests per day per user

**Request Body**:
```json
{
  "amount": 100,
  "reason": "Need tokens for school supplies"
}
```

**Response** (201 Created):
```json
{
  "request_id": "req_abc123def456",
  "family_id": "fam_abc123def456",
  "amount": 100,
  "reason": "Need tokens for school supplies",
  "status": "pending",
  "auto_approved": false,
  "expires_at": "2024-01-08T00:00:00Z",
  "created_at": "2024-01-01T00:00:00Z"
}
```

#### Review Token Request
Approve or deny token request (admin only).

```http
POST /family/{family_id}/token-request/{request_id}/review
```

**Rate Limit**: 20 reviews per hour per user

**Request Body**:
```json
{
  "action": "approve",  // "approve" or "deny"
  "admin_comments": "Approved for educational expenses"
}
```

**Response** (200 OK):
```json
{
  "status": "success",
  "action": "approve",
  "message": "Token request approved successfully",
  "request_data": {
    "request_id": "req_abc123def456",
    "status": "approved",
    "reviewed_by": "user_123",
    "reviewed_at": "2024-01-01T12:00:00Z",
    "admin_comments": "Approved for educational expenses",
    "tokens_transferred": true
  }
}
```

#### Get Token Requests
Retrieve token requests for family.

```http
GET /family/{family_id}/token-requests?status=pending
```

**Rate Limit**: 20 requests per hour per user

**Query Parameters**:
- `status` (string, optional): Filter by status (`pending`, `approved`, `denied`, `expired`)

**Response** (200 OK):
```json
[
  {
    "request_id": "req_abc123def456",
    "requester_username": "jane_smith",
    "amount": 100,
    "reason": "Need tokens for school supplies",
    "status": "pending",
    "created_at": "2024-01-01T00:00:00Z",
    "expires_at": "2024-01-08T00:00:00Z"
  }
]
```

## Error Handling

### Standard Error Response Format

```json
{
  "error": "ERROR_CODE",
  "message": "Human-readable error description",
  "details": {
    "field": "Additional error context"
  }
}
```

### Common Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `FAMILY_NOT_FOUND` | 404 | Family does not exist or user lacks access |
| `INSUFFICIENT_PERMISSIONS` | 403 | User lacks required permissions |
| `FAMILY_LIMIT_EXCEEDED` | 403 | User has reached maximum family limit |
| `MEMBER_LIMIT_EXCEEDED` | 403 | Family has reached maximum member limit |
| `INVALID_RELATIONSHIP` | 400 | Unsupported relationship type |
| `INVITATION_NOT_FOUND` | 404 | Invitation does not exist or expired |
| `ACCOUNT_FROZEN` | 403 | Family SBD account is frozen |
| `SPENDING_LIMIT_EXCEEDED` | 403 | Transaction exceeds spending limit |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests, retry after specified time |
| `VALIDATION_ERROR` | 400 | Request data validation failed |

### Rate Limiting

When rate limits are exceeded, the API returns:

```json
{
  "error": "RATE_LIMIT_EXCEEDED",
  "message": "Too many requests. Please try again later.",
  "retry_after": 3600
}
```

The `retry_after` field indicates seconds until the next request is allowed.

## Integration Examples

### Complete Family Setup Workflow

```javascript
// 1. Create a family
const createResponse = await fetch('/family/create', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer ' + jwt_token,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    name: 'My Family'
  })
});

const family = await createResponse.json();
console.log('Family created:', family.family_id);

// 2. Invite a member
const inviteResponse = await fetch(`/family/${family.family_id}/invite`, {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer ' + jwt_token,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    identifier: 'member@example.com',
    identifier_type: 'email',
    relationship_type: 'child'
  })
});

const invitation = await inviteResponse.json();
console.log('Invitation sent:', invitation.invitation_id);

// 3. Check SBD account
const accountResponse = await fetch(`/family/${family.family_id}/sbd-account`, {
  headers: {
    'Authorization': 'Bearer ' + jwt_token
  }
});

const account = await accountResponse.json();
console.log('Account balance:', account.balance);
```

### Token Request Workflow

```javascript
// Member requests tokens
const requestResponse = await fetch(`/family/${family_id}/token-request`, {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer ' + member_jwt_token,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    amount: 50,
    reason: 'Lunch money for school'
  })
});

const tokenRequest = await requestResponse.json();

// Admin reviews request
const reviewResponse = await fetch(`/family/${family_id}/token-request/${tokenRequest.request_id}/review`, {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer ' + admin_jwt_token,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    action: 'approve',
    admin_comments: 'Approved for school expenses'
  })
});

const reviewResult = await reviewResponse.json();
console.log('Request approved:', reviewResult.request_data.tokens_transferred);
```

## Best Practices

### Security
- Always validate JWT tokens before making requests
- Implement proper error handling for all API calls
- Use HTTPS for all API communications
- Store tokens securely and implement token refresh logic
- Respect rate limits to avoid service disruption

### Performance
- Cache family data when appropriate
- Use pagination for large result sets
- Implement exponential backoff for retry logic
- Monitor API response times and error rates

### Error Handling
- Always check HTTP status codes
- Parse error responses for specific error codes
- Implement user-friendly error messages
- Log errors for debugging and monitoring
- Handle network failures gracefully

### Rate Limiting
- Track rate limit headers in responses
- Implement client-side rate limiting
- Use exponential backoff when rate limited
- Consider request prioritization for critical operations

## Monitoring and Observability

### Health Checks
The API provides health check endpoints for monitoring:

```http
GET /family/health/status
GET /family/health/detailed
```

### Metrics
Key metrics to monitor:
- Request rate and response times
- Error rates by endpoint and error type
- Authentication success/failure rates
- Rate limiting trigger frequency
- Family creation and invitation rates

### Logging
All API operations are logged with:
- Request ID for tracing
- User ID and IP address
- Operation type and parameters
- Response status and timing
- Error details and stack traces
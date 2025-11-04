# Team Wallet API Integration Guide

## Overview
This document provides complete backend integration specifications for implementing team wallet functionality in the Android app. All endpoints are available under the `/workspaces` prefix and require JWT authentication.

## Base URLs
- **Development/Staging**: `http://localhost:8000` (configurable via `BASE_URL` environment variable)
- **Production**: Set via `BASE_URL` environment variable in deployment

## Authentication
All endpoints require JWT Bearer token authentication:
```
Authorization: Bearer <jwt_token>
```

**Requirements:**
- OAuth2PasswordBearer scheme
- Tokens expire after 30 minutes (configurable)
- All workspace endpoints require valid authentication

## API Endpoints

### Workspace Management

#### GET /workspaces
List all workspaces for authenticated user.

**Response:**
```json
{
  "workspaces": [
    {
      "id": "string",
      "name": "string",
      "description": "string",
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-01T00:00:00Z",
      "member_count": 3,
      "role": "admin|editor|viewer"
    }
  ]
}
```

#### POST /workspaces
Create new workspace.

**Request:**
```json
{
  "name": "string",
  "description": "string"
}
```

### Wallet Management

#### GET /workspaces/{workspace_id}/wallet
Get wallet information.

**Response:**
```json
{
  "workspace_id": "string",
  "balance": 1000.50,
  "currency": "SBD",
  "spending_permissions": {
    "daily_limit": 100.00,
    "monthly_limit": 1000.00,
    "auto_approval_threshold": 50.00
  },
  "member_permissions": {
    "user_id": "editor|viewer"
  },
  "created_at": "2024-01-01T00:00:00Z"
}
```

#### POST /workspaces/{workspace_id}/wallet/token-requests
Create token request.

**Request:**
```json
{
  "amount": 100.50,
  "purpose": "string",
  "description": "string"
}
```

**Response:**
```json
{
  "request_id": "string",
  "status": "pending",
  "created_at": "2024-01-01T00:00:00Z"
}
```

#### GET /workspaces/{workspace_id}/wallet/token-requests/pending
Get pending token requests (admin/editor only).

**Response:**
```json
{
  "requests": [
    {
      "id": "string",
      "requester_id": "string",
      "requester_name": "string",
      "amount": 100.50,
      "purpose": "string",
      "description": "string",
      "status": "pending",
      "created_at": "2024-01-01T00:00:00Z",
      "auto_approved": false
    }
  ]
}
```

#### POST /workspaces/{workspace_id}/wallet/token-requests/{request_id}/review
Approve/deny token request (admin/editor only).

**Request:**
```json
{
  "action": "approve|deny",
  "reviewer_notes": "string"
}
```

#### GET /workspaces/{workspace_id}/wallet/compliance-report
Generate compliance report (admin only).

**Query Parameters:**
- `report_type`: `json|csv|pdf` (default: json)

## Rate Limiting

**Response Headers:**
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640995200
```

**Limits:**
- General: 100 requests/minute
- Family creation: 2/hour
- Invitations: 10/hour
- Admin actions: 5/hour
- Member actions: 20/hour

## Error Response Format

All errors follow this structure:
```json
{
  "error": "ERROR_CODE",
  "message": "Human readable message",
  "details": {
    "field": "specific_field_error"
  }
}
```

**Common Error Codes:**
- `INSUFFICIENT_PERMISSIONS`
- `RATE_LIMIT_EXCEEDED`
- `INVALID_REQUEST`
- `WORKSPACE_NOT_FOUND`
- `WALLET_INSUFFICIENT_FUNDS`

## Integration Examples

### List Workspaces
```bash
curl -X GET "http://localhost:8000/workspaces" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Create Token Request
```bash
curl -X POST "http://localhost:8000/workspaces/{workspace_id}/wallet/token-requests" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 50.00,
    "purpose": "Development tools",
    "description": "Monthly subscription for development tools"
  }'
```

### Approve Token Request
```bash
curl -X POST "http://localhost:8000/workspaces/{workspace_id}/wallet/token-requests/{request_id}/review" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "approve",
    "reviewer_notes": "Approved for development expenses"
  }'
```

## OpenAPI Specification

- **OpenAPI JSON**: `GET /openapi.json`
- **Swagger UI**: `GET /docs`
- **ReDoc**: `GET /redoc`

## Important Notes

1. **Authentication Required**: All endpoints return 401 if JWT token is missing/invalid
2. **Role-Based Access**: Some endpoints require admin/editor permissions
3. **Rate Limiting**: Monitor `X-RateLimit-*` headers to avoid being blocked
4. **Error Handling**: Always check for `error` field in response body
5. **Timestamps**: All dates are ISO 8601 format with timezone
6. **Amounts**: All monetary values are in SBD tokens (float format)

## Testing

1. Start the server: `python src/second_brain_database/main.py`
2. Access documentation at `http://localhost:8000/docs`
3. Use valid JWT tokens obtained through authentication flow
4. Test with sample workspace IDs created via POST /workspaces

---

**Last Updated**: October 25, 2025
**Version**: 1.0
**Contact**: Backend Team
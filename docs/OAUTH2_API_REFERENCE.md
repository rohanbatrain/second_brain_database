# OAuth2 API Reference

## Overview

This document provides a comprehensive reference for all OAuth2 endpoints provided by the Second Brain Database OAuth2 authorization server.

## Base URL

All OAuth2 endpoints are prefixed with `/oauth2`:

```
https://your-sbd-instance.com/oauth2
```

## Authentication

Most endpoints require authentication using a Bearer token in the Authorization header:

```
Authorization: Bearer YOUR_ACCESS_TOKEN
```

## Endpoints

### Authorization Server Metadata

#### GET /.well-known/oauth-authorization-server

Retrieve OAuth2 authorization server metadata as per RFC 8414.

**Response:**
```json
{
  "issuer": "https://your-sbd-instance.com",
  "authorization_endpoint": "https://your-sbd-instance.com/oauth2/authorize",
  "token_endpoint": "https://your-sbd-instance.com/oauth2/token",
  "response_types_supported": ["code"],
  "grant_types_supported": ["authorization_code", "refresh_token"],
  "scopes_supported": ["read:profile", "write:profile", "read:data", "write:data"],
  "token_endpoint_auth_methods_supported": ["client_secret_post", "client_secret_basic"],
  "code_challenge_methods_supported": ["S256"],
  "revocation_endpoint": "https://your-sbd-instance.com/oauth2/revoke",
  "subject_types_supported": ["public"],
  "id_token_signing_alg_values_supported": ["HS256"]
}
```

### Authorization Flow

#### GET /authorize

Initiate OAuth2 authorization code flow with PKCE.

**Parameters:**
- `response_type` (required): Must be "code"
- `client_id` (required): OAuth2 client identifier
- `redirect_uri` (required): Redirect URI for authorization code delivery
- `scope` (required): Space-separated list of requested scopes
- `state` (required): Client state parameter for CSRF protection
- `code_challenge` (required): PKCE code challenge
- `code_challenge_method` (optional): PKCE challenge method, defaults to "S256"

**Example:**
```
GET /oauth2/authorize?response_type=code&client_id=oauth2_client_123&redirect_uri=https://myapp.com/callback&scope=read:profile&state=xyz&code_challenge=abc&code_challenge_method=S256
```

**Success Response:**
Redirects to `redirect_uri` with authorization code:
```
https://myapp.com/callback?code=auth_code_123&state=xyz
```

**Error Response:**
Redirects to `redirect_uri` with error:
```
https://myapp.com/callback?error=access_denied&error_description=User denied authorization&state=xyz
```

#### POST /consent

Handle user consent approval or denial.

**Content-Type:** `application/x-www-form-urlencoded`

**Parameters:**
- `client_id` (required): OAuth2 client identifier
- `state` (required): Consent state parameter
- `scopes` (required): Comma-separated list of requested scopes
- `approved` (required): "true" or "false"

**Authentication:** Required (current user)

**Success Response:**
Redirects to client with authorization code or error.

### Token Management

#### POST /token

Exchange authorization code for access tokens or refresh existing tokens.

**Content-Type:** `application/x-www-form-urlencoded`

**Parameters for Authorization Code Grant:**
- `grant_type` (required): "authorization_code"
- `code` (required): Authorization code
- `redirect_uri` (required): Must match authorization request
- `client_id` (required): OAuth2 client identifier
- `client_secret` (required for confidential clients): Client secret
- `code_verifier` (required): PKCE code verifier

**Parameters for Refresh Token Grant:**
- `grant_type` (required): "refresh_token"
- `refresh_token` (required): Refresh token
- `client_id` (required): OAuth2 client identifier
- `client_secret` (required for confidential clients): Client secret

**Success Response:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_token": "rt_1234567890abcdef1234567890abcdef",
  "scope": "read:profile write:data"
}
```

**Error Response:**
```json
{
  "error": "invalid_grant",
  "error_description": "Invalid authorization code"
}
```

#### POST /revoke

Revoke OAuth2 access tokens or refresh tokens.

**Content-Type:** `application/x-www-form-urlencoded`

**Parameters:**
- `token` (required): Token to revoke
- `token_type_hint` (optional): "access_token" or "refresh_token"
- `client_id` (required): OAuth2 client identifier
- `client_secret` (required for confidential clients): Client secret

**Success Response:**
```json
{
  "revoked": true
}
```

### Client Management

#### POST /clients

Register a new OAuth2 client application.

**Content-Type:** `application/json`

**Authentication:** Required

**Request Body:**
```json
{
  "name": "My Web Application",
  "description": "A web application for managing user data",
  "redirect_uris": ["https://myapp.com/oauth/callback"],
  "client_type": "confidential",
  "scopes": ["read:profile", "write:data"],
  "website_url": "https://myapp.com"
}
```

**Success Response (201):**
```json
{
  "client_id": "oauth2_client_1234567890abcdef",
  "client_secret": "cs_1234567890abcdef1234567890abcdef",
  "name": "My Web Application",
  "client_type": "confidential",
  "redirect_uris": ["https://myapp.com/oauth/callback"],
  "scopes": ["read:profile", "write:data"],
  "created_at": "2024-01-01T12:00:00Z",
  "is_active": true
}
```

#### GET /clients

List OAuth2 clients owned by the current user.

**Authentication:** Required

**Parameters:**
- `all_clients` (optional): List all clients (admin only), defaults to false

**Success Response:**
```json
{
  "message": "Retrieved 2 OAuth2 clients",
  "data": {
    "clients": [
      {
        "client_id": "oauth2_client_123",
        "name": "My Web App",
        "client_type": "confidential",
        "redirect_uris": ["https://myapp.com/callback"],
        "scopes": ["read:profile"],
        "created_at": "2024-01-01T12:00:00Z",
        "is_active": true
      }
    ],
    "total_count": 2
  }
}
```

#### GET /clients/{client_id}

Get details of a specific OAuth2 client.

**Authentication:** Required (owner or admin)

**Success Response:**
```json
{
  "message": "Client retrieved successfully",
  "data": {
    "client": {
      "client_id": "oauth2_client_123",
      "name": "My Web App",
      "description": "My application description",
      "client_type": "confidential",
      "redirect_uris": ["https://myapp.com/callback"],
      "scopes": ["read:profile", "write:data"],
      "website_url": "https://myapp.com",
      "owner_user_id": "john_doe",
      "created_at": "2024-01-01T12:00:00Z",
      "updated_at": "2024-01-01T12:00:00Z",
      "is_active": true
    }
  }
}
```

#### PUT /clients/{client_id}

Update OAuth2 client configuration.

**Content-Type:** `application/json`

**Authentication:** Required (owner or admin)

**Request Body:**
```json
{
  "name": "Updated App Name",
  "description": "Updated description",
  "redirect_uris": ["https://myapp.com/new-callback"],
  "scopes": ["read:profile", "write:data", "read:tokens"]
}
```

**Success Response:**
```json
{
  "message": "Client updated successfully",
  "data": {
    "client_id": "oauth2_client_123",
    "updated_fields": ["name", "description", "redirect_uris", "scopes"]
  }
}
```

#### DELETE /clients/{client_id}

Delete OAuth2 client application.

**Authentication:** Required (owner or admin)

**Success Response:**
```json
{
  "message": "Client deleted successfully",
  "data": {
    "client_id": "oauth2_client_123",
    "deleted": true
  }
}
```

### Consent Management

#### GET /consents

List user's OAuth2 consents.

**Authentication:** Required

**Success Response:**
```json
{
  "message": "Retrieved 2 consents",
  "data": {
    "consents": [
      {
        "client_id": "oauth2_client_123",
        "client_name": "My Web App",
        "scopes": ["read:profile", "write:data"],
        "granted_at": "2024-01-01T12:00:00Z",
        "last_used_at": "2024-01-02T10:30:00Z",
        "is_active": true
      }
    ],
    "total_count": 2
  }
}
```

#### GET /consents/manage

Web interface for managing OAuth2 consents.

**Authentication:** Required

**Response:** HTML consent management interface

#### DELETE /consents/{client_id}

Revoke OAuth2 consent for a specific client.

**Authentication:** Required

**Success Response:**
```json
{
  "message": "Consent revoked for client oauth2_client_123",
  "data": {
    "client_id": "oauth2_client_123",
    "revoked": true
  }
}
```

### Health and Monitoring

#### GET /health

Check OAuth2 provider health and status.

**Success Response:**
```json
{
  "message": "OAuth2 provider is healthy",
  "data": {
    "status": "healthy",
    "timestamp": "2024-01-01T12:00:00Z",
    "components": {
      "client_manager": "healthy",
      "auth_code_manager": "healthy",
      "security_manager": "healthy",
      "pkce_validator": "healthy"
    },
    "statistics": {
      "authorization_codes": {
        "active": 5,
        "expired": 12
      }
    }
  }
}
```

#### POST /cleanup

Clean up expired OAuth2 tokens (admin only).

**Authentication:** Required

**Success Response:**
```json
{
  "message": "Cleaned up 15 expired tokens",
  "data": {
    "cleaned_tokens": 15,
    "cleanup_timestamp": "2024-01-01T12:00:00Z"
  }
}
```

#### GET /tokens/stats

Get statistics about OAuth2 tokens (admin only).

**Authentication:** Required

**Success Response:**
```json
{
  "message": "Token statistics retrieved successfully",
  "data": {
    "refresh_tokens": {
      "active": 45,
      "expired": 123,
      "total": 168
    },
    "authorization_codes": {
      "active": 8,
      "expired": 67,
      "total": 75
    }
  }
}
```

## Error Responses

### HTTP Status Codes

- `200`: Success
- `201`: Created (client registration)
- `302`: Redirect (authorization flow)
- `400`: Bad Request (invalid parameters)
- `401`: Unauthorized (authentication required)
- `403`: Forbidden (insufficient permissions)
- `404`: Not Found (resource not found)
- `429`: Too Many Requests (rate limited)
- `500`: Internal Server Error

### OAuth2 Error Codes

#### Authorization Endpoint Errors

- `invalid_request`: Missing or invalid parameters
- `unauthorized_client`: Client not authorized
- `access_denied`: User denied authorization
- `unsupported_response_type`: Invalid response_type
- `invalid_scope`: Invalid or unknown scope
- `server_error`: Internal server error
- `temporarily_unavailable`: Service temporarily unavailable

#### Token Endpoint Errors

- `invalid_request`: Missing or invalid parameters
- `invalid_client`: Client authentication failed
- `invalid_grant`: Invalid authorization code or refresh token
- `unauthorized_client`: Client not authorized for grant type
- `unsupported_grant_type`: Grant type not supported

## Rate Limits

The OAuth2 provider implements rate limiting to prevent abuse:

- **Authorization endpoint**: 100 requests per 5 minutes per client
- **Token endpoint**: 200 requests per 5 minutes per client
- **Client registration**: 10 registrations per hour per user
- **Token revocation**: 100 requests per 5 minutes per client

Rate limit headers are included in responses:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640995200
```

## Scopes

### Available Scopes

- `read:profile`: Read user profile information (username, email, basic details)
- `write:profile`: Update user profile information
- `read:data`: Read user's stored data and documents
- `write:data`: Create, update, and delete user data and documents
- `read:tokens`: View user's API tokens and their usage
- `write:tokens`: Create and manage user API tokens
- `admin`: Administrative access (restricted to admin users)

### Scope Validation

Scopes are validated during:
1. Client registration (client must be authorized for requested scopes)
2. Authorization request (requested scopes must be subset of client scopes)
3. Token usage (API endpoints check token scopes)

## Security Features

### PKCE (Proof Key for Code Exchange)

All authorization code flows require PKCE with SHA256 method for enhanced security.

### State Parameter

The state parameter is required for CSRF protection and must be validated by clients.

### Token Encryption

Refresh tokens and authorization codes are encrypted at rest using Fernet encryption.

### Rate Limiting

Comprehensive rate limiting prevents abuse and ensures service availability.

### Audit Logging

All OAuth2 operations are logged for security monitoring and compliance.

### Security Headers

All responses include appropriate security headers:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Strict-Transport-Security: max-age=31536000; includeSubDomains`
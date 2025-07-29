# OAuth2 Provider Integration Guide

## Overview

The Second Brain Database provides a complete OAuth2 2.1 authorization server implementation that allows external applications to authenticate users and access authorized resources. This guide covers how to integrate with the OAuth2 provider, including client registration, authorization flows, and API usage.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Client Registration](#client-registration)
3. [Authorization Code Flow](#authorization-code-flow)
4. [Token Management](#token-management)
5. [API Integration](#api-integration)
6. [Error Handling](#error-handling)
7. [Security Best Practices](#security-best-practices)
8. [Troubleshooting](#troubleshooting)

## Quick Start

### 1. Discover OAuth2 Configuration

First, retrieve the OAuth2 provider configuration:

```bash
curl https://your-sbd-instance.com/oauth2/.well-known/oauth-authorization-server
```

This returns the OAuth2 server metadata including all endpoints and supported features.

### 2. Register Your Application

Register your OAuth2 client application:

```bash
curl -X POST https://your-sbd-instance.com/oauth2/clients \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Web Application",
    "description": "A web application for managing user data",
    "redirect_uris": ["https://myapp.com/oauth/callback"],
    "client_type": "confidential",
    "scopes": ["read:profile", "write:data"],
    "website_url": "https://myapp.com"
  }'
```

Save the returned `client_id` and `client_secret` securely.

### 3. Implement Authorization Flow

Redirect users to the authorization endpoint to begin the OAuth2 flow:

```
https://your-sbd-instance.com/oauth2/authorize?
  response_type=code&
  client_id=YOUR_CLIENT_ID&
  redirect_uri=https://myapp.com/oauth/callback&
  scope=read:profile write:data&
  state=RANDOM_STATE_STRING&
  code_challenge=CODE_CHALLENGE&
  code_challenge_method=S256
```

## Client Registration

### Supported Client Types

- **Confidential**: Server-side applications that can securely store credentials
- **Public**: Mobile apps and SPAs that cannot securely store credentials

### Registration Request

```json
{
  "name": "My Application",
  "description": "Optional description",
  "redirect_uris": ["https://myapp.com/callback"],
  "client_type": "confidential",
  "scopes": ["read:profile", "write:data"],
  "website_url": "https://myapp.com"
}
```

### Registration Response

```json
{
  "client_id": "oauth2_client_1234567890abcdef",
  "client_secret": "cs_1234567890abcdef1234567890abcdef",
  "name": "My Application",
  "client_type": "confidential",
  "redirect_uris": ["https://myapp.com/callback"],
  "scopes": ["read:profile", "write:data"],
  "created_at": "2024-01-01T12:00:00Z",
  "is_active": true
}
```

**Important**: The `client_secret` is only shown once during registration. Store it securely.

## Authorization Code Flow

The OAuth2 authorization code flow with PKCE is the recommended method for all client types.

### Step 1: Generate PKCE Parameters

```javascript
// Generate code verifier (43-128 characters)
const codeVerifier = generateRandomString(128);

// Generate code challenge (SHA256 hash of verifier, base64url encoded)
const codeChallenge = base64urlEncode(sha256(codeVerifier));
```

### Step 2: Authorization Request

Redirect the user to the authorization endpoint:

```
GET /oauth2/authorize?
  response_type=code&
  client_id=oauth2_client_1234567890abcdef&
  redirect_uri=https://myapp.com/callback&
  scope=read:profile write:data&
  state=random_state_string&
  code_challenge=dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk&
  code_challenge_method=S256
```

### Step 3: Handle Authorization Response

The user will be redirected back to your `redirect_uri` with an authorization code:

```
https://myapp.com/callback?
  code=auth_code_1234567890abcdef&
  state=random_state_string
```

### Step 4: Exchange Code for Tokens

Exchange the authorization code for access tokens:

```bash
curl -X POST https://your-sbd-instance.com/oauth2/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=authorization_code" \
  -d "code=auth_code_1234567890abcdef" \
  -d "redirect_uri=https://myapp.com/callback" \
  -d "client_id=oauth2_client_1234567890abcdef" \
  -d "client_secret=cs_1234567890abcdef1234567890abcdef" \
  -d "code_verifier=dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
```

### Token Response

```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_token": "rt_1234567890abcdef1234567890abcdef",
  "scope": "read:profile write:data"
}
```

## Token Management

### Refresh Tokens

When the access token expires, use the refresh token to obtain a new one:

```bash
curl -X POST https://your-sbd-instance.com/oauth2/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=refresh_token" \
  -d "refresh_token=rt_1234567890abcdef1234567890abcdef" \
  -d "client_id=oauth2_client_1234567890abcdef" \
  -d "client_secret=cs_1234567890abcdef1234567890abcdef"
```

### Token Revocation

Revoke tokens when they're no longer needed:

```bash
curl -X POST https://your-sbd-instance.com/oauth2/revoke \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "token=rt_1234567890abcdef1234567890abcdef" \
  -d "token_type_hint=refresh_token" \
  -d "client_id=oauth2_client_1234567890abcdef" \
  -d "client_secret=cs_1234567890abcdef1234567890abcdef"
```

## API Integration

### Using Access Tokens

Include the access token in the Authorization header for API requests:

```bash
curl -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..." \
  https://your-sbd-instance.com/api/protected-endpoint
```

### Scope-Based Access Control

Different scopes provide different levels of access:

- `read:profile`: Read user profile information
- `write:profile`: Update user profile information
- `read:data`: Read user's stored data and documents
- `write:data`: Create, update, and delete user data
- `read:tokens`: View user's API tokens
- `write:tokens`: Manage user's API tokens

## Error Handling

### Authorization Errors

Authorization errors are returned as query parameters in the redirect:

```
https://myapp.com/callback?
  error=access_denied&
  error_description=User denied authorization&
  state=random_state_string
```

### Token Errors

Token endpoint errors are returned as JSON:

```json
{
  "error": "invalid_grant",
  "error_description": "Invalid authorization code"
}
```

### Common Error Codes

- `invalid_request`: Missing or invalid parameters
- `invalid_client`: Client authentication failed
- `invalid_grant`: Invalid authorization code or refresh token
- `unauthorized_client`: Client not authorized for this grant type
- `unsupported_grant_type`: Grant type not supported
- `invalid_scope`: Invalid or unknown scope
- `access_denied`: User denied authorization

## Security Best Practices

### 1. Always Use HTTPS

All OAuth2 communications must use HTTPS in production.

### 2. Implement PKCE

Always use PKCE (Proof Key for Code Exchange) with the S256 method for enhanced security.

### 3. Validate State Parameter

Always validate the state parameter to prevent CSRF attacks.

### 4. Secure Token Storage

Store tokens securely and never expose them in URLs or logs.

### 5. Token Rotation

Implement refresh token rotation and revoke old tokens.

### 6. Scope Minimization

Request only the minimum scopes required for your application.

## Troubleshooting

### Common Issues

#### 1. Invalid Redirect URI

**Error**: `invalid_request: Invalid redirect URI`

**Solution**: Ensure the redirect URI in your authorization request exactly matches one of the URIs registered for your client.

#### 2. PKCE Validation Failed

**Error**: `invalid_grant: PKCE code verifier validation failed`

**Solution**: Verify that your code verifier matches the code challenge used in the authorization request.

#### 3. Client Authentication Failed

**Error**: `invalid_client: Client authentication failed`

**Solution**: Check that your client_id and client_secret are correct and that your client is active.

#### 4. Token Expired

**Error**: `invalid_grant: Invalid authorization code`

**Solution**: Authorization codes expire after 10 minutes. Ensure you exchange them promptly.

### Debug Mode

Enable debug logging to troubleshoot issues:

```bash
# Check OAuth2 provider health
curl https://your-sbd-instance.com/oauth2/health

# Get token statistics (admin only)
curl -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  https://your-sbd-instance.com/oauth2/tokens/stats
```

### Support

For additional support:

1. Check the [API Reference](./OAUTH2_API_REFERENCE.md)
2. Review the [Configuration Guide](./OAUTH2_CONFIGURATION.md)
3. See [Integration Examples](./examples/)
# Authentication and Authorization Guide

## Overview

The Second Brain Database API uses a multi-layered security approach with JWT tokens, permanent API tokens, and comprehensive security controls including IP lockdown, user agent restrictions, and 2FA requirements.

## Authentication Methods

### 1. JWT Token Authentication

JWT (JSON Web Token) authentication is the primary method for user sessions.

#### Obtaining JWT Tokens

```http
POST /auth/login
Content-Type: application/json

{
  "username": "your_username",
  "password": "your_password"
}
```

**Response**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user_id": "user_123",
  "username": "your_username"
}
```

#### Using JWT Tokens

Include the JWT token in the Authorization header:

```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

#### JWT Token Properties
- **Expiration**: Tokens expire after 1 hour by default
- **Refresh**: Implement token refresh logic for long-running applications
- **Scope**: Full API access for authenticated user
- **Security**: Tokens are signed and verified server-side

### 2. Permanent API Tokens

Permanent tokens provide long-term API access without expiration.

#### Creating Permanent Tokens

```http
POST /auth/permanent-tokens
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "name": "My API Integration",
  "description": "Token for automated family management",
  "permissions": ["family:read", "family:write"],
  "expires_at": "2025-12-31T23:59:59Z"  // Optional
}
```

**Response**:
```json
{
  "token_id": "pt_abc123def456",
  "token": "sbd_permanent_xyz789abc123...",
  "name": "My API Integration",
  "permissions": ["family:read", "family:write"],
  "created_at": "2024-01-01T00:00:00Z",
  "expires_at": "2025-12-31T23:59:59Z"
}
```

#### Using Permanent Tokens

Include the permanent token in the Authorization header:

```http
Authorization: Bearer sbd_permanent_xyz789abc123...
```

#### Permanent Token Properties
- **Long-lived**: No automatic expiration (unless specified)
- **Scoped**: Limited to specific permissions
- **Revocable**: Can be revoked at any time
- **Auditable**: All usage is logged and tracked

### 3. WebAuthn (Passwordless)

WebAuthn provides modern, secure passwordless authentication.

#### Registration Flow

```javascript
// 1. Request registration challenge
const challengeResponse = await fetch('/auth/webauthn/register/begin', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    username: 'your_username',
    display_name: 'Your Display Name'
  })
});

const challenge = await challengeResponse.json();

// 2. Create credential using WebAuthn API
const credential = await navigator.credentials.create({
  publicKey: challenge.publicKey
});

// 3. Complete registration
const registrationResponse = await fetch('/auth/webauthn/register/complete', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    credential: credential,
    challenge_id: challenge.challenge_id
  })
});
```

#### Authentication Flow

```javascript
// 1. Request authentication challenge
const challengeResponse = await fetch('/auth/webauthn/authenticate/begin', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    username: 'your_username'
  })
});

const challenge = await challengeResponse.json();

// 2. Get assertion using WebAuthn API
const assertion = await navigator.credentials.get({
  publicKey: challenge.publicKey
});

// 3. Complete authentication
const authResponse = await fetch('/auth/webauthn/authenticate/complete', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    assertion: assertion,
    challenge_id: challenge.challenge_id
  })
});

const result = await authResponse.json();
// result.access_token contains the JWT token
```

## Authorization Levels

### User Roles

#### Regular User
- Access to own profile and data
- Can create families (subject to limits)
- Can respond to invitations
- Can request tokens from family accounts

#### Family Administrator
- All regular user permissions
- Can invite and remove family members
- Can manage SBD account permissions
- Can approve/deny token requests
- Can freeze/unfreeze family accounts
- Can modify family settings

#### System Administrator
- All family administrator permissions
- Can access admin endpoints
- Can view system health and metrics
- Can perform maintenance operations

### Permission Scopes

For permanent tokens, the following scopes are available:

| Scope | Description |
|-------|-------------|
| `family:read` | Read family information and relationships |
| `family:write` | Create families and manage memberships |
| `family:admin` | Administrative operations (requires admin role) |
| `sbd:read` | Read SBD account information |
| `sbd:write` | Manage SBD account permissions and settings |
| `sbd:spend` | Validate spending permissions |
| `tokens:read` | Read token request information |
| `tokens:write` | Create and manage token requests |
| `notifications:read` | Read notifications |
| `notifications:write` | Manage notification preferences |
| `profile:read` | Read user profile information |
| `profile:write` | Update user profile information |

## Security Controls

### IP Lockdown

Restrict API access to specific IP addresses.

#### Enabling IP Lockdown

```http
POST /auth/security/ip-lockdown
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "enabled": true,
  "allowed_ips": ["192.168.1.100", "10.0.0.0/24"],
  "description": "Office and home network access only"
}
```

#### IP Lockdown Behavior
- **Whitelist**: Only specified IPs can access the API
- **Bypass**: System administrators can bypass restrictions
- **Logging**: All blocked attempts are logged
- **Emergency**: Emergency disable codes available

### User Agent Lockdown

Restrict API access to specific user agents or applications.

#### Enabling User Agent Lockdown

```http
POST /auth/security/user-agent-lockdown
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "enabled": true,
  "allowed_patterns": [
    "MyApp/1.0*",
    "Mozilla/5.0*Chrome*"
  ],
  "description": "Only allow official app and Chrome browser"
}
```

#### User Agent Lockdown Behavior
- **Pattern Matching**: Supports wildcards and regex patterns
- **Case Insensitive**: Matching is case-insensitive
- **Logging**: All blocked attempts are logged
- **Flexibility**: Multiple patterns supported

### Two-Factor Authentication (2FA)

2FA is required for sensitive operations.

#### Setting Up 2FA

```http
POST /auth/2fa/setup
Authorization: Bearer <jwt_token>
```

**Response**:
```json
{
  "qr_code": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...",
  "secret": "JBSWY3DPEHPK3PXP",
  "backup_codes": [
    "12345678",
    "87654321",
    "11223344"
  ]
}
```

#### Verifying 2FA Setup

```http
POST /auth/2fa/verify-setup
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "totp_code": "123456"
}
```

#### Using 2FA for Sensitive Operations

For operations requiring 2FA, include the TOTP code:

```http
POST /family/{family_id}/sbd-account/freeze
Authorization: Bearer <jwt_token>
X-TOTP-Code: 123456
Content-Type: application/json

{
  "freeze": true,
  "reason": "Security concern"
}
```

## Rate Limiting

### Rate Limit Headers

All responses include rate limiting information:

```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640995200
X-RateLimit-Retry-After: 3600
```

### Rate Limit Policies

| Operation Type | Limit | Window |
|----------------|-------|---------|
| Authentication | 10 attempts | 15 minutes |
| Family Creation | 5 requests | 1 hour |
| Member Invitations | 10 requests | 1 hour |
| Token Requests | 10 requests | 24 hours |
| SBD Account Access | 30 requests | 1 hour |
| General API | 100 requests | 1 hour |

### Handling Rate Limits

```javascript
async function makeApiRequest(url, options) {
  const response = await fetch(url, options);
  
  if (response.status === 429) {
    const retryAfter = response.headers.get('X-RateLimit-Retry-After');
    console.log(`Rate limited. Retry after ${retryAfter} seconds`);
    
    // Implement exponential backoff
    await new Promise(resolve => 
      setTimeout(resolve, parseInt(retryAfter) * 1000)
    );
    
    // Retry the request
    return makeApiRequest(url, options);
  }
  
  return response;
}
```

## Error Handling

### Authentication Errors

| Error Code | HTTP Status | Description | Action |
|------------|-------------|-------------|---------|
| `INVALID_TOKEN` | 401 | Token is invalid or expired | Refresh or re-authenticate |
| `TOKEN_EXPIRED` | 401 | JWT token has expired | Refresh token |
| `INSUFFICIENT_SCOPE` | 403 | Token lacks required permissions | Use token with appropriate scope |
| `IP_BLOCKED` | 403 | IP address not in whitelist | Contact administrator |
| `USER_AGENT_BLOCKED` | 403 | User agent not allowed | Use approved application |
| `2FA_REQUIRED` | 403 | Operation requires 2FA | Include TOTP code |
| `2FA_INVALID` | 403 | Invalid 2FA code | Retry with correct code |

### Example Error Response

```json
{
  "error": "INVALID_TOKEN",
  "message": "The provided token is invalid or has expired",
  "details": {
    "token_type": "jwt",
    "expired_at": "2024-01-01T12:00:00Z"
  },
  "retry_after": null
}
```

## Best Practices

### Token Management

1. **Secure Storage**: Store tokens securely (keychain, secure storage)
2. **Token Rotation**: Implement automatic token refresh
3. **Scope Limitation**: Use minimal required scopes for permanent tokens
4. **Regular Audit**: Review and revoke unused tokens
5. **Expiration**: Set appropriate expiration times

### Security Implementation

1. **HTTPS Only**: Always use HTTPS for API communications
2. **Token Validation**: Validate tokens on every request
3. **Error Handling**: Don't expose sensitive information in errors
4. **Logging**: Log authentication events for security monitoring
5. **Rate Limiting**: Implement client-side rate limiting

### 2FA Integration

1. **Backup Codes**: Store backup codes securely
2. **User Experience**: Provide clear 2FA prompts
3. **Recovery**: Implement account recovery procedures
4. **Testing**: Test 2FA flows thoroughly
5. **Documentation**: Provide clear setup instructions

## Integration Examples

### Complete Authentication Flow

```javascript
class ApiClient {
  constructor(baseUrl) {
    this.baseUrl = baseUrl;
    this.token = null;
  }
  
  async login(username, password) {
    const response = await fetch(`${this.baseUrl}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });
    
    if (response.ok) {
      const data = await response.json();
      this.token = data.access_token;
      return data;
    }
    
    throw new Error('Login failed');
  }
  
  async makeAuthenticatedRequest(endpoint, options = {}) {
    if (!this.token) {
      throw new Error('Not authenticated');
    }
    
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      ...options,
      headers: {
        'Authorization': `Bearer ${this.token}`,
        'Content-Type': 'application/json',
        ...options.headers
      }
    });
    
    if (response.status === 401) {
      // Token expired, need to re-authenticate
      this.token = null;
      throw new Error('Authentication expired');
    }
    
    return response;
  }
}

// Usage
const client = new ApiClient('https://api.secondbraindatabase.com');
await client.login('username', 'password');

const families = await client.makeAuthenticatedRequest('/family/my-families');
```

### Permanent Token Usage

```javascript
class PermanentTokenClient {
  constructor(baseUrl, permanentToken) {
    this.baseUrl = baseUrl;
    this.token = permanentToken;
  }
  
  async createFamily(name) {
    const response = await fetch(`${this.baseUrl}/family/create`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ name })
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(`API Error: ${error.message}`);
    }
    
    return response.json();
  }
}

// Usage
const client = new PermanentTokenClient(
  'https://api.secondbraindatabase.com',
  'sbd_permanent_xyz789abc123...'
);

const family = await client.createFamily('My Family');
```

## Security Considerations

### Token Security
- Never log or expose tokens in client-side code
- Use secure storage mechanisms for token persistence
- Implement token refresh logic to minimize exposure
- Revoke tokens immediately when compromised

### Network Security
- Always use HTTPS for API communications
- Implement certificate pinning for mobile applications
- Use secure DNS resolution
- Monitor for man-in-the-middle attacks

### Application Security
- Validate all user inputs before sending to API
- Implement proper error handling to avoid information leakage
- Use secure coding practices to prevent XSS and CSRF
- Regular security audits and penetration testing

### Monitoring and Alerting
- Monitor authentication success/failure rates
- Alert on suspicious login patterns
- Track token usage and detect anomalies
- Log all security-related events for audit purposes
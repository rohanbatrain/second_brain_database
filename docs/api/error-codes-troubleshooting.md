# Error Codes and Troubleshooting Guide

## Overview

This guide provides comprehensive information about error codes, their meanings, and troubleshooting steps for the Family Management API. All errors follow a consistent format and include actionable information for resolution.

## Error Response Format

All API errors return a consistent JSON structure:

```json
{
  "error": "ERROR_CODE",
  "message": "Human-readable error description",
  "details": {
    "field": "Additional context",
    "suggestion": "Recommended action"
  },
  "retry_after": 3600,  // Optional: seconds until retry allowed
  "request_id": "req_abc123def456"  // For support tracking
}
```

## HTTP Status Codes

| Status Code | Meaning | Common Causes |
|-------------|---------|---------------|
| 400 | Bad Request | Invalid input data, validation errors |
| 401 | Unauthorized | Missing or invalid authentication |
| 403 | Forbidden | Insufficient permissions, rate limits |
| 404 | Not Found | Resource doesn't exist or no access |
| 409 | Conflict | Resource already exists, state conflict |
| 422 | Unprocessable Entity | Valid format but business logic error |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Unexpected server error |
| 502 | Bad Gateway | Upstream service unavailable |
| 503 | Service Unavailable | Temporary service outage |

## Authentication and Authorization Errors

### INVALID_TOKEN (401)

**Description**: The provided authentication token is invalid, malformed, or expired.

**Common Causes**:
- JWT token has expired
- Token signature is invalid
- Token format is incorrect
- Token has been revoked

**Troubleshooting**:
```javascript
// Check token format
if (!token.startsWith('eyJ')) {
  console.error('Invalid JWT token format');
}

// Check expiration
const payload = JSON.parse(atob(token.split('.')[1]));
if (payload.exp * 1000 < Date.now()) {
  console.error('Token has expired');
  // Refresh token or re-authenticate
}
```

**Resolution**:
1. Refresh the JWT token using refresh endpoint
2. Re-authenticate if refresh fails
3. Verify token storage and retrieval logic

### TOKEN_EXPIRED (401)

**Description**: The JWT token has passed its expiration time.

**Example Response**:
```json
{
  "error": "TOKEN_EXPIRED",
  "message": "JWT token has expired",
  "details": {
    "expired_at": "2024-01-01T12:00:00Z",
    "current_time": "2024-01-01T13:00:00Z"
  }
}
```

**Resolution**:
```javascript
async function handleTokenExpiration() {
  try {
    // Attempt to refresh token
    const refreshResponse = await fetch('/auth/refresh', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${refreshToken}`
      }
    });
    
    if (refreshResponse.ok) {
      const { access_token } = await refreshResponse.json();
      // Update stored token
      localStorage.setItem('access_token', access_token);
      return access_token;
    }
  } catch (error) {
    // Refresh failed, redirect to login
    window.location.href = '/login';
  }
}
```

### INSUFFICIENT_PERMISSIONS (403)

**Description**: The authenticated user lacks the required permissions for this operation.

**Common Scenarios**:
- Non-admin trying to perform admin operations
- User accessing family they don't belong to
- Insufficient token scope for permanent tokens

**Example Response**:
```json
{
  "error": "INSUFFICIENT_PERMISSIONS",
  "message": "You must be a family administrator to perform this action",
  "details": {
    "required_role": "admin",
    "current_role": "member",
    "family_id": "fam_abc123def456"
  }
}
```

**Resolution**:
1. Verify user role in the family
2. Request admin privileges from current admin
3. Use appropriate authentication method

### IP_BLOCKED (403)

**Description**: The request IP address is not in the allowed whitelist.

**Troubleshooting**:
```bash
# Check current IP address
curl -s https://api.ipify.org

# Verify IP whitelist configuration
curl -H "Authorization: Bearer $TOKEN" \
  https://api.secondbraindatabase.com/auth/security/ip-lockdown
```

**Resolution**:
1. Add current IP to whitelist
2. Contact administrator to update IP restrictions
3. Use VPN or approved network if available

### USER_AGENT_BLOCKED (403)

**Description**: The request user agent is not in the allowed patterns.

**Example Response**:
```json
{
  "error": "USER_AGENT_BLOCKED",
  "message": "User agent not allowed",
  "details": {
    "current_user_agent": "CustomBot/1.0",
    "allowed_patterns": ["MyApp/1.0*", "Mozilla/5.0*"]
  }
}
```

**Resolution**:
```javascript
// Set appropriate user agent
const response = await fetch(url, {
  headers: {
    'User-Agent': 'MyApp/1.0 (compatible)',
    'Authorization': `Bearer ${token}`
  }
});
```

### 2FA_REQUIRED (403)

**Description**: The operation requires two-factor authentication.

**Resolution**:
```javascript
// Include TOTP code in sensitive operations
const response = await fetch('/family/123/sbd-account/freeze', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'X-TOTP-Code': '123456',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    freeze: true,
    reason: 'Security concern'
  })
});
```

## Family Management Errors

### FAMILY_NOT_FOUND (404)

**Description**: The specified family does not exist or the user doesn't have access.

**Common Causes**:
- Family ID is incorrect
- Family was deleted
- User is not a member of the family
- User lacks permission to view family

**Troubleshooting**:
```javascript
// Verify family ID format
if (!familyId.startsWith('fam_')) {
  console.error('Invalid family ID format');
}

// Check user's families
const families = await fetch('/family/my-families', {
  headers: { 'Authorization': `Bearer ${token}` }
});
const familyList = await families.json();
const hasAccess = familyList.some(f => f.family_id === familyId);
```

**Resolution**:
1. Verify the family ID is correct
2. Check if user is a member of the family
3. Request invitation if not a member

### FAMILY_LIMIT_EXCEEDED (403)

**Description**: User has reached their maximum number of families.

**Example Response**:
```json
{
  "error": "FAMILY_LIMIT_EXCEEDED",
  "message": "You have reached your maximum family limit",
  "details": {
    "current_families": 3,
    "max_allowed": 3,
    "upgrade_required": true,
    "upgrade_url": "/upgrade"
  }
}
```

**Resolution**:
1. Delete unused families
2. Upgrade account plan
3. Contact support for limit increase

### MEMBER_LIMIT_EXCEEDED (403)

**Description**: Family has reached its maximum member limit.

**Resolution**:
1. Remove inactive members
2. Upgrade family plan
3. Create additional families if needed

### INVALID_RELATIONSHIP (400)

**Description**: The specified relationship type is not supported.

**Supported Relationships**:
```javascript
const VALID_RELATIONSHIPS = {
  'parent': 'child',
  'child': 'parent',
  'sibling': 'sibling',
  'spouse': 'spouse',
  'grandparent': 'grandchild',
  'grandchild': 'grandparent',
  'uncle': 'nephew',
  'aunt': 'niece',
  'nephew': 'uncle',
  'niece': 'aunt',
  'cousin': 'cousin'
};
```

**Resolution**:
```javascript
function validateRelationship(type) {
  if (!VALID_RELATIONSHIPS[type]) {
    throw new Error(`Invalid relationship type: ${type}`);
  }
  return true;
}
```

### INVITATION_NOT_FOUND (404)

**Description**: The invitation does not exist, has expired, or user lacks access.

**Common Causes**:
- Invitation ID is incorrect
- Invitation has expired
- Invitation was already responded to
- User is not the intended recipient

**Troubleshooting**:
```javascript
// Check invitation status
const invitation = await fetch(`/family/invitations/${invitationId}`, {
  headers: { 'Authorization': `Bearer ${token}` }
});

if (invitation.status === 404) {
  console.error('Invitation not found or expired');
}
```

**Resolution**:
1. Verify invitation ID is correct
2. Check if invitation has expired
3. Request new invitation if needed

## SBD Account Errors

### ACCOUNT_FROZEN (403)

**Description**: The family SBD account is frozen and cannot be used for spending.

**Example Response**:
```json
{
  "error": "ACCOUNT_FROZEN",
  "message": "Family account is frozen",
  "details": {
    "frozen_by": "user_123",
    "frozen_at": "2024-01-01T12:00:00Z",
    "reason": "Suspicious activity detected",
    "contact_admin": true
  }
}
```

**Resolution**:
1. Contact family administrator
2. Resolve the issue that caused freezing
3. Request account unfreezing

### SPENDING_LIMIT_EXCEEDED (403)

**Description**: The transaction amount exceeds the user's spending limit.

**Troubleshooting**:
```javascript
// Check current spending permissions
const account = await fetch(`/family/${familyId}/sbd-account`, {
  headers: { 'Authorization': `Bearer ${token}` }
});
const accountData = await account.json();
const userPermissions = accountData.spending_permissions[userId];

console.log('Spending limit:', userPermissions.spending_limit);
console.log('Can spend:', userPermissions.can_spend);
```

**Resolution**:
1. Request spending limit increase from admin
2. Split transaction into smaller amounts
3. Request tokens through token request workflow

### INSUFFICIENT_BALANCE (400)

**Description**: The family account doesn't have enough tokens for the transaction.

**Resolution**:
1. Add tokens to family account
2. Reduce transaction amount
3. Wait for pending deposits to clear

## Rate Limiting Errors

### RATE_LIMIT_EXCEEDED (429)

**Description**: Too many requests have been made within the rate limit window.

**Example Response**:
```json
{
  "error": "RATE_LIMIT_EXCEEDED",
  "message": "Too many requests. Please try again later.",
  "details": {
    "limit": 10,
    "window": 3600,
    "reset_at": "2024-01-01T13:00:00Z"
  },
  "retry_after": 3600
}
```

**Handling Rate Limits**:
```javascript
async function makeRequestWithRetry(url, options, maxRetries = 3) {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    const response = await fetch(url, options);
    
    if (response.status === 429) {
      const retryAfter = response.headers.get('Retry-After') || 
                        response.headers.get('X-RateLimit-Retry-After');
      
      if (attempt === maxRetries) {
        throw new Error('Rate limit exceeded, max retries reached');
      }
      
      // Exponential backoff
      const delay = Math.min(
        parseInt(retryAfter) * 1000,
        Math.pow(2, attempt) * 1000
      );
      
      await new Promise(resolve => setTimeout(resolve, delay));
      continue;
    }
    
    return response;
  }
}
```

## Validation Errors

### VALIDATION_ERROR (400)

**Description**: Request data failed validation rules.

**Example Response**:
```json
{
  "error": "VALIDATION_ERROR",
  "message": "Request validation failed",
  "details": {
    "field_errors": {
      "name": "Family name must be between 3 and 50 characters",
      "email": "Invalid email format"
    }
  }
}
```

**Common Validation Rules**:
```javascript
const VALIDATION_RULES = {
  family_name: {
    min_length: 3,
    max_length: 50,
    pattern: /^[a-zA-Z0-9\s\-_]+$/
  },
  email: {
    pattern: /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  },
  relationship_type: {
    allowed_values: Object.keys(VALID_RELATIONSHIPS)
  },
  token_amount: {
    min: 1,
    max: 10000,
    type: 'integer'
  }
};
```

**Client-Side Validation**:
```javascript
function validateFamilyName(name) {
  if (!name || name.length < 3) {
    return 'Family name must be at least 3 characters';
  }
  if (name.length > 50) {
    return 'Family name must be less than 50 characters';
  }
  if (!/^[a-zA-Z0-9\s\-_]+$/.test(name)) {
    return 'Family name contains invalid characters';
  }
  return null;
}
```

## Server Errors

### INTERNAL_SERVER_ERROR (500)

**Description**: An unexpected error occurred on the server.

**Example Response**:
```json
{
  "error": "INTERNAL_SERVER_ERROR",
  "message": "An unexpected error occurred",
  "details": {
    "request_id": "req_abc123def456",
    "timestamp": "2024-01-01T12:00:00Z"
  }
}
```

**Troubleshooting Steps**:
1. Retry the request after a short delay
2. Check API status page for known issues
3. Contact support with request ID if problem persists

### SERVICE_UNAVAILABLE (503)

**Description**: The service is temporarily unavailable.

**Handling Service Unavailability**:
```javascript
async function makeResilientRequest(url, options) {
  const maxRetries = 3;
  const baseDelay = 1000; // 1 second
  
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      const response = await fetch(url, options);
      
      if (response.status === 503) {
        if (attempt === maxRetries) {
          throw new Error('Service unavailable after max retries');
        }
        
        // Exponential backoff with jitter
        const delay = baseDelay * Math.pow(2, attempt - 1) + 
                     Math.random() * 1000;
        await new Promise(resolve => setTimeout(resolve, delay));
        continue;
      }
      
      return response;
    } catch (error) {
      if (attempt === maxRetries) {
        throw error;
      }
      
      const delay = baseDelay * Math.pow(2, attempt - 1);
      await new Promise(resolve => setTimeout(resolve, delay));
    }
  }
}
```

## Debugging and Monitoring

### Request Tracing

All API responses include a request ID for tracing:

```javascript
const response = await fetch('/family/create', options);
const requestId = response.headers.get('X-Request-ID');

if (!response.ok) {
  console.error(`Request failed: ${requestId}`);
  // Include request ID when contacting support
}
```

### Error Logging

Implement comprehensive error logging:

```javascript
class ApiErrorLogger {
  static logError(error, context) {
    const logEntry = {
      timestamp: new Date().toISOString(),
      error_code: error.error,
      message: error.message,
      request_id: error.request_id,
      context: context,
      user_agent: navigator.userAgent,
      url: window.location.href
    };
    
    // Send to logging service
    console.error('API Error:', logEntry);
    
    // Optional: Send to external logging service
    // this.sendToLoggingService(logEntry);
  }
}
```

### Health Monitoring

Monitor API health and performance:

```javascript
async function checkApiHealth() {
  try {
    const response = await fetch('/family/health/status');
    const health = await response.json();
    
    if (health.status !== 'healthy') {
      console.warn('API health issue:', health);
    }
    
    return health;
  } catch (error) {
    console.error('Health check failed:', error);
    return { status: 'error', error: error.message };
  }
}

// Check health periodically
setInterval(checkApiHealth, 60000); // Every minute
```

## Best Practices for Error Handling

### 1. Implement Retry Logic

```javascript
class ApiClient {
  async makeRequest(url, options, retryConfig = {}) {
    const {
      maxRetries = 3,
      baseDelay = 1000,
      retryableStatuses = [429, 500, 502, 503, 504]
    } = retryConfig;
    
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        const response = await fetch(url, options);
        
        if (retryableStatuses.includes(response.status)) {
          if (attempt === maxRetries) {
            throw new Error(`Max retries exceeded: ${response.status}`);
          }
          
          const delay = this.calculateDelay(attempt, baseDelay, response);
          await this.sleep(delay);
          continue;
        }
        
        return response;
      } catch (error) {
        if (attempt === maxRetries) {
          throw error;
        }
        
        await this.sleep(baseDelay * Math.pow(2, attempt - 1));
      }
    }
  }
  
  calculateDelay(attempt, baseDelay, response) {
    // Use Retry-After header if available
    const retryAfter = response.headers.get('Retry-After');
    if (retryAfter) {
      return parseInt(retryAfter) * 1000;
    }
    
    // Exponential backoff with jitter
    return baseDelay * Math.pow(2, attempt - 1) + Math.random() * 1000;
  }
  
  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}
```

### 2. User-Friendly Error Messages

```javascript
function getUserFriendlyMessage(error) {
  const errorMessages = {
    'FAMILY_NOT_FOUND': 'The family you\'re looking for doesn\'t exist or you don\'t have access to it.',
    'FAMILY_LIMIT_EXCEEDED': 'You\'ve reached your family limit. Consider upgrading your plan.',
    'INSUFFICIENT_PERMISSIONS': 'You don\'t have permission to perform this action. Contact a family administrator.',
    'RATE_LIMIT_EXCEEDED': 'You\'re making requests too quickly. Please wait a moment and try again.',
    'ACCOUNT_FROZEN': 'This family account is temporarily frozen. Contact a family administrator.',
    'VALIDATION_ERROR': 'Please check your input and try again.',
    'INTERNAL_SERVER_ERROR': 'Something went wrong on our end. Please try again in a moment.'
  };
  
  return errorMessages[error.error] || error.message || 'An unexpected error occurred.';
}
```

### 3. Error Recovery Strategies

```javascript
class ErrorRecoveryManager {
  static async handleError(error, context) {
    switch (error.error) {
      case 'TOKEN_EXPIRED':
        return this.handleTokenExpiration(context);
        
      case 'RATE_LIMIT_EXCEEDED':
        return this.handleRateLimit(error, context);
        
      case 'FAMILY_NOT_FOUND':
        return this.handleFamilyNotFound(context);
        
      case 'INSUFFICIENT_PERMISSIONS':
        return this.handleInsufficientPermissions(error, context);
        
      default:
        return this.handleGenericError(error, context);
    }
  }
  
  static async handleTokenExpiration(context) {
    try {
      const newToken = await this.refreshToken();
      context.token = newToken;
      return { retry: true, context };
    } catch (refreshError) {
      return { retry: false, action: 'redirect_to_login' };
    }
  }
  
  static async handleRateLimit(error, context) {
    const retryAfter = error.retry_after || 60;
    return {
      retry: true,
      delay: retryAfter * 1000,
      message: `Please wait ${retryAfter} seconds before trying again.`
    };
  }
}
```

## Support and Contact Information

When contacting support about API errors, please include:

1. **Request ID**: Found in error response or X-Request-ID header
2. **Timestamp**: When the error occurred
3. **Error Code**: The specific error code received
4. **Request Details**: Endpoint, method, and parameters used
5. **User Context**: User ID, family ID (if applicable)
6. **Steps to Reproduce**: What actions led to the error

**Support Channels**:
- Email: api-support@secondbraindatabase.com
- Documentation: https://docs.secondbraindatabase.com
- Status Page: https://status.secondbraindatabase.com
# OAuth2 Troubleshooting Guide

## Overview

This guide helps you diagnose and resolve common issues when integrating with the Second Brain Database OAuth2 provider. It covers client-side problems, server-side issues, and configuration errors.

## Table of Contents

1. [Common Error Codes](#common-error-codes)
2. [Authorization Flow Issues](#authorization-flow-issues)
3. [Token Management Problems](#token-management-problems)
4. [Client Configuration Issues](#client-configuration-issues)
5. [Security and PKCE Problems](#security-and-pkce-problems)
6. [Rate Limiting Issues](#rate-limiting-issues)
7. [Network and Connectivity](#network-and-connectivity)
8. [Debug Tools and Techniques](#debug-tools-and-techniques)
9. [Performance Issues](#performance-issues)
10. [Production Deployment Issues](#production-deployment-issues)

## Common Error Codes

### Authorization Endpoint Errors

#### `invalid_request`
**Symptoms**: 400 Bad Request with error description
**Common Causes**:
- Missing required parameters (client_id, redirect_uri, scope, state, code_challenge)
- Invalid parameter format or encoding
- Malformed URLs

**Solutions**:
```javascript
// Ensure all required parameters are present
const authUrl = new URL('https://sbd-instance.com/oauth2/authorize');
authUrl.searchParams.set('response_type', 'code');
authUrl.searchParams.set('client_id', 'your_client_id');
authUrl.searchParams.set('redirect_uri', 'https://yourapp.com/callback');
authUrl.searchParams.set('scope', 'read:profile write:data');
authUrl.searchParams.set('state', generateSecureState());
authUrl.searchParams.set('code_challenge', codeChallenge);
authUrl.searchParams.set('code_challenge_method', 'S256');
```

#### `unauthorized_client`
**Symptoms**: Client not authorized for this request
**Common Causes**:
- Client ID not found or inactive
- Client not configured for authorization code flow
- Client type mismatch

**Solutions**:
1. Verify client registration:
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  https://sbd-instance.com/oauth2/clients/your_client_id
```

2. Check client status and configuration
3. Re-register client if necessary

#### `access_denied`
**Symptoms**: User denied authorization
**Common Causes**:
- User clicked "Deny" on consent screen
- User cancelled authorization flow
- Automatic denial due to security policies

**Solutions**:
- Handle gracefully in your application
- Provide clear explanation to users
- Allow users to retry authorization

```javascript
// Handle access denied in callback
if (req.query.error === 'access_denied') {
  return res.render('auth-denied', {
    message: 'Authorization was denied. You can try again or contact support.'
  });
}
```

#### `invalid_scope`
**Symptoms**: Requested scope is invalid or not allowed
**Common Causes**:
- Requesting scopes not registered for client
- Typos in scope names
- Using deprecated scope names

**Solutions**:
1. Check available scopes:
```bash
curl https://sbd-instance.com/oauth2/.well-known/oauth-authorization-server
```

2. Verify client scope configuration:
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  https://sbd-instance.com/oauth2/clients/your_client_id
```

3. Update client scopes if needed:
```bash
curl -X PUT https://sbd-instance.com/oauth2/clients/your_client_id \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"scopes": ["read:profile", "write:data"]}'
```

### Token Endpoint Errors

#### `invalid_client`
**Symptoms**: Client authentication failed
**Common Causes**:
- Incorrect client_secret
- Client ID not found
- Client credentials not properly encoded

**Solutions**:
1. Verify credentials:
```javascript
// Ensure proper encoding for client credentials
const credentials = Buffer.from(`${clientId}:${clientSecret}`).toString('base64');
const headers = {
  'Authorization': `Basic ${credentials}`,
  'Content-Type': 'application/x-www-form-urlencoded'
};
```

2. Check client secret format (should start with 'cs_')
3. Regenerate client secret if compromised

#### `invalid_grant`
**Symptoms**: Authorization code or refresh token is invalid
**Common Causes**:
- Authorization code expired (10 minute limit)
- Code already used (single-use only)
- PKCE code verifier mismatch
- Refresh token expired or revoked

**Solutions**:
1. For authorization codes:
```javascript
// Ensure immediate exchange after receiving code
app.get('/auth/callback', async (req, res) => {
  const { code } = req.query;
  
  // Exchange immediately - don't delay
  try {
    const tokens = await exchangeCodeForTokens(code, codeVerifier);
    // Store tokens...
  } catch (error) {
    if (error.error === 'invalid_grant') {
      // Code expired or invalid - restart flow
      return res.redirect('/auth/login');
    }
  }
});
```

2. For refresh tokens:
```javascript
// Handle refresh token expiration
async function refreshTokens(refreshToken) {
  try {
    return await refreshAccessToken(refreshToken);
  } catch (error) {
    if (error.error === 'invalid_grant') {
      // Refresh token expired - need new authorization
      throw new Error('REAUTH_REQUIRED');
    }
    throw error;
  }
}
```

#### `unsupported_grant_type`
**Symptoms**: Grant type not supported
**Common Causes**:
- Using unsupported grant type (only 'authorization_code' and 'refresh_token' supported)
- Typo in grant_type parameter

**Solutions**:
```javascript
// Use correct grant types
const tokenData = {
  grant_type: 'authorization_code', // or 'refresh_token'
  code: authorizationCode,
  redirect_uri: redirectUri,
  client_id: clientId,
  client_secret: clientSecret,
  code_verifier: codeVerifier
};
```

## Authorization Flow Issues

### Redirect URI Mismatch

**Symptoms**: "Invalid redirect URI" error
**Common Causes**:
- Redirect URI doesn't exactly match registered URI
- Protocol mismatch (http vs https)
- Port number differences
- Trailing slash differences

**Solutions**:
1. Exact match required:
```javascript
// Registration
redirect_uris: ["https://myapp.com/auth/callback"]

// Authorization request - must match exactly
redirect_uri: "https://myapp.com/auth/callback"
```

2. Common mismatches to avoid:
```javascript
// ❌ Wrong - different protocols
registered: "https://myapp.com/callback"
request: "http://myapp.com/callback"

// ❌ Wrong - trailing slash
registered: "https://myapp.com/callback"
request: "https://myapp.com/callback/"

// ❌ Wrong - different ports
registered: "https://myapp.com:3000/callback"
request: "https://myapp.com/callback"
```

### State Parameter Issues

**Symptoms**: CSRF protection errors, invalid state
**Common Causes**:
- State parameter not properly generated or stored
- State validation logic errors
- Session storage issues

**Solutions**:
1. Proper state generation:
```javascript
const crypto = require('crypto');

// Generate cryptographically secure state
function generateState() {
  return crypto.randomBytes(32).toString('hex');
}

// Store in session
app.get('/auth/login', (req, res) => {
  const state = generateState();
  req.session.oauth2State = state;
  
  const authUrl = buildAuthUrl({ state });
  res.redirect(authUrl);
});

// Validate in callback
app.get('/auth/callback', (req, res) => {
  const { state } = req.query;
  
  if (!state || state !== req.session.oauth2State) {
    return res.status(400).send('Invalid state parameter');
  }
  
  // Clear used state
  delete req.session.oauth2State;
  
  // Continue with token exchange...
});
```

### PKCE Validation Failures

**Symptoms**: "PKCE code verifier validation failed"
**Common Causes**:
- Code verifier doesn't match code challenge
- Incorrect PKCE implementation
- Code verifier not properly stored

**Solutions**:
1. Correct PKCE implementation:
```javascript
const crypto = require('crypto');

// Generate code verifier (43-128 characters)
function generateCodeVerifier() {
  return crypto.randomBytes(32).toString('base64url');
}

// Generate code challenge (SHA256 hash)
function generateCodeChallenge(verifier) {
  return crypto.createHash('sha256').update(verifier).digest('base64url');
}

// Authorization flow
app.get('/auth/login', (req, res) => {
  const codeVerifier = generateCodeVerifier();
  const codeChallenge = generateCodeChallenge(codeVerifier);
  
  // Store verifier for token exchange
  req.session.codeVerifier = codeVerifier;
  
  const authUrl = buildAuthUrl({
    code_challenge: codeChallenge,
    code_challenge_method: 'S256'
  });
  
  res.redirect(authUrl);
});

// Token exchange
app.get('/auth/callback', async (req, res) => {
  const { code } = req.query;
  const codeVerifier = req.session.codeVerifier;
  
  if (!codeVerifier) {
    return res.status(400).send('Missing code verifier');
  }
  
  try {
    const tokens = await exchangeCodeForTokens(code, codeVerifier);
    // Success...
  } catch (error) {
    console.error('Token exchange failed:', error);
  }
  
  // Clear used verifier
  delete req.session.codeVerifier;
});
```

## Token Management Problems

### Token Expiration Handling

**Symptoms**: 401 Unauthorized errors, expired tokens
**Common Causes**:
- Not handling token expiration
- Not implementing token refresh
- Incorrect expiration time calculation

**Solutions**:
1. Automatic token refresh:
```javascript
class TokenManager {
  constructor() {
    this.tokens = null;
    this.refreshPromise = null;
  }
  
  async getValidToken() {
    if (!this.tokens) {
      throw new Error('No tokens available');
    }
    
    // Check if token expires in next 5 minutes
    const expiryBuffer = 5 * 60 * 1000; // 5 minutes
    const expiresAt = this.tokens.expires_at || 0;
    
    if (Date.now() + expiryBuffer >= expiresAt) {
      return await this.refreshToken();
    }
    
    return this.tokens.access_token;
  }
  
  async refreshToken() {
    // Prevent multiple simultaneous refresh attempts
    if (this.refreshPromise) {
      return await this.refreshPromise;
    }
    
    this.refreshPromise = this._performRefresh();
    
    try {
      const result = await this.refreshPromise;
      return result;
    } finally {
      this.refreshPromise = null;
    }
  }
  
  async _performRefresh() {
    if (!this.tokens?.refresh_token) {
      throw new Error('No refresh token available');
    }
    
    const response = await fetch('/oauth2/token', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded'
      },
      body: new URLSearchParams({
        grant_type: 'refresh_token',
        refresh_token: this.tokens.refresh_token,
        client_id: CLIENT_ID,
        client_secret: CLIENT_SECRET
      })
    });
    
    if (!response.ok) {
      const error = await response.json();
      if (error.error === 'invalid_grant') {
        // Refresh token expired - need re-authorization
        this.tokens = null;
        throw new Error('REAUTH_REQUIRED');
      }
      throw new Error(`Token refresh failed: ${error.error_description}`);
    }
    
    const newTokens = await response.json();
    
    // Update stored tokens
    this.tokens = {
      access_token: newTokens.access_token,
      refresh_token: newTokens.refresh_token,
      expires_at: Date.now() + (newTokens.expires_in * 1000),
      scope: newTokens.scope
    };
    
    return this.tokens.access_token;
  }
}
```

### Token Storage Security

**Symptoms**: Token theft, security vulnerabilities
**Common Causes**:
- Storing tokens in localStorage (XSS vulnerable)
- Logging tokens in console/files
- Transmitting tokens over HTTP

**Solutions**:
1. Secure server-side storage:
```javascript
// ✅ Good - Server-side session storage
app.use(session({
  secret: process.env.SESSION_SECRET,
  resave: false,
  saveUninitialized: false,
  cookie: {
    secure: true, // HTTPS only
    httpOnly: true, // Prevent XSS
    maxAge: 24 * 60 * 60 * 1000, // 24 hours
    sameSite: 'strict' // CSRF protection
  },
  store: new RedisStore({
    client: redisClient,
    prefix: 'sess:'
  })
}));

// Store tokens in session
req.session.tokens = {
  access_token: tokens.access_token,
  refresh_token: tokens.refresh_token,
  expires_at: Date.now() + (tokens.expires_in * 1000)
};
```

2. For SPAs, use secure cookies:
```javascript
// Set secure HTTP-only cookies
res.cookie('access_token', tokens.access_token, {
  httpOnly: true,
  secure: true,
  sameSite: 'strict',
  maxAge: tokens.expires_in * 1000
});

res.cookie('refresh_token', tokens.refresh_token, {
  httpOnly: true,
  secure: true,
  sameSite: 'strict',
  maxAge: 30 * 24 * 60 * 60 * 1000 // 30 days
});
```

## Client Configuration Issues

### Client Registration Problems

**Symptoms**: Client not found, registration failures
**Common Causes**:
- Invalid redirect URIs
- Incorrect client type selection
- Missing required fields

**Solutions**:
1. Proper client registration:
```bash
curl -X POST https://sbd-instance.com/oauth2/clients \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Application",
    "description": "A web application for data management",
    "redirect_uris": [
      "https://myapp.com/auth/callback",
      "http://localhost:3000/auth/callback"
    ],
    "client_type": "confidential",
    "scopes": ["read:profile", "write:data"],
    "website_url": "https://myapp.com"
  }'
```

2. Validate redirect URIs:
```javascript
// ✅ Valid redirect URIs
const validUris = [
  "https://myapp.com/callback",           // Production
  "https://staging.myapp.com/callback",   // Staging
  "http://localhost:3000/callback",       // Development
  "http://127.0.0.1:3000/callback"        // Local development
];

// ❌ Invalid redirect URIs
const invalidUris = [
  "http://myapp.com/callback",            // HTTP in production
  "https://myapp.com/callback?param=1",   // Query parameters
  "myapp://callback",                     // Custom schemes (mobile)
  "javascript:alert('xss')"               // JavaScript URLs
];
```

### Scope Configuration Issues

**Symptoms**: Insufficient permissions, scope errors
**Common Causes**:
- Requesting more scopes than client is authorized for
- Using incorrect scope names
- Not requesting required scopes

**Solutions**:
1. Check available scopes:
```bash
# Get server metadata
curl https://sbd-instance.com/oauth2/.well-known/oauth-authorization-server | jq .scopes_supported

# Check client scopes
curl -H "Authorization: Bearer YOUR_TOKEN" \
  https://sbd-instance.com/oauth2/clients/your_client_id | jq .scopes
```

2. Request appropriate scopes:
```javascript
// Map application features to required scopes
const SCOPE_MAPPING = {
  'view_profile': ['read:profile'],
  'edit_profile': ['read:profile', 'write:profile'],
  'manage_data': ['read:data', 'write:data'],
  'api_access': ['read:tokens', 'write:tokens']
};

function getRequiredScopes(features) {
  const scopes = new Set();
  features.forEach(feature => {
    SCOPE_MAPPING[feature]?.forEach(scope => scopes.add(scope));
  });
  return Array.from(scopes);
}

// Request only needed scopes
const requiredFeatures = ['view_profile', 'manage_data'];
const scopes = getRequiredScopes(requiredFeatures);
const scopeString = scopes.join(' ');
```

## Security and PKCE Problems

### PKCE Implementation Issues

**Symptoms**: PKCE validation failures, security errors
**Common Causes**:
- Incorrect code verifier generation
- Wrong hashing algorithm
- Base64 encoding issues

**Solutions**:
1. Correct PKCE implementation:
```python
import hashlib
import base64
import secrets
import string

def generate_code_verifier():
    """Generate a cryptographically random code verifier."""
    # 43-128 characters, URL-safe
    alphabet = string.ascii_letters + string.digits + '-._~'
    return ''.join(secrets.choice(alphabet) for _ in range(128))

def generate_code_challenge(verifier):
    """Generate code challenge from verifier using SHA256."""
    # SHA256 hash
    digest = hashlib.sha256(verifier.encode('utf-8')).digest()
    # Base64url encode (no padding)
    return base64.urlsafe_b64encode(digest).decode('utf-8').rstrip('=')

# Usage
code_verifier = generate_code_verifier()
code_challenge = generate_code_challenge(code_verifier)

# Store verifier securely for token exchange
session['code_verifier'] = code_verifier

# Use challenge in authorization URL
auth_params = {
    'code_challenge': code_challenge,
    'code_challenge_method': 'S256'
}
```

2. JavaScript implementation:
```javascript
// Modern browser implementation
async function generatePKCEPair() {
  // Generate random code verifier
  const array = new Uint8Array(32);
  crypto.getRandomValues(array);
  const codeVerifier = base64URLEncode(array);
  
  // Generate code challenge
  const encoder = new TextEncoder();
  const data = encoder.encode(codeVerifier);
  const digest = await crypto.subtle.digest('SHA-256', data);
  const codeChallenge = base64URLEncode(new Uint8Array(digest));
  
  return { codeVerifier, codeChallenge };
}

function base64URLEncode(array) {
  return btoa(String.fromCharCode(...array))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=/g, '');
}
```

### State Parameter Security

**Symptoms**: CSRF attacks, state validation failures
**Common Causes**:
- Weak state generation
- State reuse
- Improper state validation

**Solutions**:
1. Secure state implementation:
```javascript
const crypto = require('crypto');

class StateManager {
  constructor() {
    this.states = new Map();
  }
  
  generateState(sessionId) {
    // Generate cryptographically secure state
    const state = crypto.randomBytes(32).toString('hex');
    
    // Store with expiration (10 minutes)
    const expiresAt = Date.now() + (10 * 60 * 1000);
    this.states.set(state, {
      sessionId,
      expiresAt,
      used: false
    });
    
    // Clean up expired states
    this.cleanupExpiredStates();
    
    return state;
  }
  
  validateState(state, sessionId) {
    const stateData = this.states.get(state);
    
    if (!stateData) {
      throw new Error('Invalid state parameter');
    }
    
    if (stateData.used) {
      throw new Error('State parameter already used');
    }
    
    if (Date.now() > stateData.expiresAt) {
      this.states.delete(state);
      throw new Error('State parameter expired');
    }
    
    if (stateData.sessionId !== sessionId) {
      throw new Error('State parameter session mismatch');
    }
    
    // Mark as used (single-use)
    stateData.used = true;
    
    // Clean up after short delay
    setTimeout(() => this.states.delete(state), 60000);
    
    return true;
  }
  
  cleanupExpiredStates() {
    const now = Date.now();
    for (const [state, data] of this.states.entries()) {
      if (now > data.expiresAt) {
        this.states.delete(state);
      }
    }
  }
}
```

## Rate Limiting Issues

### Rate Limit Exceeded

**Symptoms**: 429 Too Many Requests errors
**Common Causes**:
- Too many authorization attempts
- Excessive token refresh requests
- Client making too many API calls

**Solutions**:
1. Implement exponential backoff:
```javascript
class RateLimitHandler {
  constructor() {
    this.retryDelays = [1000, 2000, 4000, 8000, 16000]; // ms
  }
  
  async makeRequest(requestFn, maxRetries = 3) {
    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      try {
        return await requestFn();
      } catch (error) {
        if (error.status === 429 && attempt < maxRetries) {
          const delay = this.retryDelays[attempt] || 16000;
          
          // Check for Retry-After header
          const retryAfter = error.headers?.get('Retry-After');
          const waitTime = retryAfter ? parseInt(retryAfter) * 1000 : delay;
          
          console.log(`Rate limited, waiting ${waitTime}ms before retry ${attempt + 1}`);
          await this.sleep(waitTime);
          continue;
        }
        throw error;
      }
    }
  }
  
  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

// Usage
const rateLimitHandler = new RateLimitHandler();

const tokens = await rateLimitHandler.makeRequest(async () => {
  return await exchangeCodeForTokens(code, verifier);
});
```

2. Monitor rate limit headers:
```javascript
async function makeAPIRequest(url, options = {}) {
  const response = await fetch(url, options);
  
  // Check rate limit headers
  const remaining = response.headers.get('X-RateLimit-Remaining');
  const reset = response.headers.get('X-RateLimit-Reset');
  
  if (remaining && parseInt(remaining) < 10) {
    console.warn(`Rate limit warning: ${remaining} requests remaining`);
    
    if (reset) {
      const resetTime = new Date(parseInt(reset) * 1000);
      console.warn(`Rate limit resets at: ${resetTime}`);
    }
  }
  
  if (response.status === 429) {
    const retryAfter = response.headers.get('Retry-After');
    throw new RateLimitError(`Rate limited. Retry after ${retryAfter} seconds`);
  }
  
  return response;
}
```

## Network and Connectivity

### Connection Timeouts

**Symptoms**: Request timeouts, network errors
**Common Causes**:
- Slow network connections
- Server overload
- DNS resolution issues

**Solutions**:
1. Configure appropriate timeouts:
```javascript
const axios = require('axios');

const oauth2Client = axios.create({
  baseURL: 'https://sbd-instance.com/oauth2',
  timeout: 30000, // 30 seconds
  retry: 3,
  retryDelay: (retryCount) => {
    return Math.pow(2, retryCount) * 1000; // Exponential backoff
  }
});

// Add retry interceptor
oauth2Client.interceptors.response.use(
  response => response,
  async error => {
    const config = error.config;
    
    if (!config || !config.retry) return Promise.reject(error);
    
    config.retryCount = config.retryCount || 0;
    
    if (config.retryCount >= config.retry) {
      return Promise.reject(error);
    }
    
    config.retryCount += 1;
    
    const delay = config.retryDelay ? config.retryDelay(config.retryCount) : 1000;
    await new Promise(resolve => setTimeout(resolve, delay));
    
    return oauth2Client(config);
  }
);
```

### SSL/TLS Issues

**Symptoms**: Certificate errors, SSL handshake failures
**Common Causes**:
- Invalid SSL certificates
- Certificate chain issues
- TLS version mismatches

**Solutions**:
1. Verify SSL configuration:
```bash
# Check SSL certificate
openssl s_client -connect sbd-instance.com:443 -servername sbd-instance.com

# Check certificate chain
curl -I https://sbd-instance.com/oauth2/.well-known/oauth-authorization-server
```

2. Handle SSL in development:
```javascript
// For development only - never in production
if (process.env.NODE_ENV === 'development') {
  process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0';
}

// Better approach - use proper certificates even in development
const https = require('https');
const fs = require('fs');

const agent = new https.Agent({
  ca: fs.readFileSync('path/to/ca-certificate.pem'),
  rejectUnauthorized: true
});

const response = await fetch(url, { agent });
```

## Debug Tools and Techniques

### Logging and Monitoring

**Enable Debug Logging**:
```javascript
// Enable OAuth2 debug logging
process.env.DEBUG = 'oauth2:*';

// Custom logger
const debug = require('debug');
const oauth2Debug = debug('oauth2:client');

oauth2Debug('Starting authorization flow');
oauth2Debug('Generated state: %s', state);
oauth2Debug('Generated PKCE challenge: %s', codeChallenge);
```

**Monitor Network Requests**:
```javascript
// Log all OAuth2 requests
const originalFetch = global.fetch;
global.fetch = async (url, options = {}) => {
  if (url.includes('/oauth2/')) {
    console.log('OAuth2 Request:', {
      url,
      method: options.method || 'GET',
      headers: options.headers,
      body: options.body
    });
  }
  
  const response = await originalFetch(url, options);
  
  if (url.includes('/oauth2/')) {
    console.log('OAuth2 Response:', {
      status: response.status,
      headers: Object.fromEntries(response.headers.entries())
    });
  }
  
  return response;
};
```

### Testing Tools

**OAuth2 Flow Testing**:
```bash
#!/bin/bash
# Test OAuth2 flow script

CLIENT_ID="your_client_id"
CLIENT_SECRET="your_client_secret"
REDIRECT_URI="http://localhost:3000/callback"
BASE_URL="https://sbd-instance.com/oauth2"

# Generate PKCE parameters
CODE_VERIFIER=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-43)
CODE_CHALLENGE=$(echo -n $CODE_VERIFIER | openssl dgst -sha256 -binary | openssl base64 | tr -d "=+/" | tr "/+" "_-")

# Generate state
STATE=$(openssl rand -hex 32)

echo "1. Authorization URL:"
echo "${BASE_URL}/authorize?response_type=code&client_id=${CLIENT_ID}&redirect_uri=${REDIRECT_URI}&scope=read:profile&state=${STATE}&code_challenge=${CODE_CHALLENGE}&code_challenge_method=S256"

echo ""
echo "2. After authorization, extract code from callback URL and run:"
echo "CODE=\"your_authorization_code\""
echo ""
echo "3. Exchange code for tokens:"
echo "curl -X POST ${BASE_URL}/token \\"
echo "  -H 'Content-Type: application/x-www-form-urlencoded' \\"
echo "  -d 'grant_type=authorization_code' \\"
echo "  -d 'code='\$CODE \\"
echo "  -d 'redirect_uri=${REDIRECT_URI}' \\"
echo "  -d 'client_id=${CLIENT_ID}' \\"
echo "  -d 'client_secret=${CLIENT_SECRET}' \\"
echo "  -d 'code_verifier=${CODE_VERIFIER}'"
```

**Token Validation**:
```javascript
// JWT token decoder for debugging
function decodeJWT(token) {
  const parts = token.split('.');
  if (parts.length !== 3) {
    throw new Error('Invalid JWT format');
  }
  
  const header = JSON.parse(atob(parts[0]));
  const payload = JSON.parse(atob(parts[1]));
  
  return {
    header,
    payload,
    signature: parts[2],
    isExpired: payload.exp * 1000 < Date.now(),
    expiresAt: new Date(payload.exp * 1000),
    scopes: payload.scope ? payload.scope.split(' ') : []
  };
}

// Usage
try {
  const tokenInfo = decodeJWT(accessToken);
  console.log('Token info:', tokenInfo);
  
  if (tokenInfo.isExpired) {
    console.warn('Token is expired!');
  }
} catch (error) {
  console.error('Invalid token:', error.message);
}
```

## Performance Issues

### Slow Authorization Flow

**Symptoms**: Long delays during authorization
**Common Causes**:
- Slow database queries
- Network latency
- Heavy consent screen rendering

**Solutions**:
1. Optimize client-side performance:
```javascript
// Preload authorization endpoint
const link = document.createElement('link');
link.rel = 'dns-prefetch';
link.href = 'https://sbd-instance.com';
document.head.appendChild(link);

// Use efficient redirect
window.location.replace(authorizationUrl); // Instead of window.location.href
```

2. Implement caching:
```javascript
// Cache OAuth2 server metadata
class OAuth2MetadataCache {
  constructor() {
    this.cache = new Map();
    this.ttl = 24 * 60 * 60 * 1000; // 24 hours
  }
  
  async getMetadata(issuer) {
    const cacheKey = `metadata:${issuer}`;
    const cached = this.cache.get(cacheKey);
    
    if (cached && Date.now() < cached.expiresAt) {
      return cached.data;
    }
    
    const response = await fetch(`${issuer}/.well-known/oauth-authorization-server`);
    const metadata = await response.json();
    
    this.cache.set(cacheKey, {
      data: metadata,
      expiresAt: Date.now() + this.ttl
    });
    
    return metadata;
  }
}
```

### Token Refresh Performance

**Symptoms**: Slow API responses due to token refresh
**Common Causes**:
- Synchronous token refresh blocking requests
- Multiple simultaneous refresh attempts

**Solutions**:
```javascript
class OptimizedTokenManager {
  constructor() {
    this.tokens = null;
    this.refreshPromise = null;
    this.refreshBuffer = 5 * 60 * 1000; // 5 minutes
  }
  
  async getValidToken() {
    if (!this.tokens) {
      throw new Error('No tokens available');
    }
    
    // Check if refresh is needed
    const needsRefresh = this.tokens.expires_at - Date.now() < this.refreshBuffer;
    
    if (needsRefresh && this.tokens.refresh_token) {
      // Start refresh in background if not already running
      if (!this.refreshPromise) {
        this.refreshPromise = this.refreshTokens()
          .finally(() => {
            this.refreshPromise = null;
          });
      }
      
      // For immediate needs, use current token if still valid
      if (this.tokens.expires_at > Date.now()) {
        return this.tokens.access_token;
      }
      
      // Wait for refresh if token is expired
      await this.refreshPromise;
    }
    
    return this.tokens.access_token;
  }
  
  async refreshTokens() {
    // Implementation...
  }
}
```

## Production Deployment Issues

### Environment Configuration

**Common Issues**:
- Missing environment variables
- Incorrect URLs in production
- SSL certificate problems

**Solutions**:
1. Environment validation:
```javascript
// Validate required environment variables
const requiredEnvVars = [
  'OAUTH2_CLIENT_ID',
  'OAUTH2_CLIENT_SECRET',
  'OAUTH2_REDIRECT_URI',
  'OAUTH2_AUTHORIZATION_URL',
  'OAUTH2_TOKEN_URL',
  'SESSION_SECRET'
];

function validateEnvironment() {
  const missing = requiredEnvVars.filter(varName => !process.env[varName]);
  
  if (missing.length > 0) {
    throw new Error(`Missing required environment variables: ${missing.join(', ')}`);
  }
  
  // Validate URLs
  const urls = [
    'OAUTH2_AUTHORIZATION_URL',
    'OAUTH2_TOKEN_URL',
    'OAUTH2_REDIRECT_URI'
  ];
  
  urls.forEach(urlVar => {
    try {
      new URL(process.env[urlVar]);
    } catch (error) {
      throw new Error(`Invalid URL in ${urlVar}: ${process.env[urlVar]}`);
    }
  });
  
  // Validate HTTPS in production
  if (process.env.NODE_ENV === 'production') {
    urls.forEach(urlVar => {
      const url = new URL(process.env[urlVar]);
      if (url.protocol !== 'https:' && url.hostname !== 'localhost') {
        throw new Error(`${urlVar} must use HTTPS in production`);
      }
    });
  }
}

// Run validation on startup
validateEnvironment();
```

### Load Balancer Configuration

**Issues with OAuth2 behind load balancers**:
```nginx
# Nginx configuration for OAuth2
upstream oauth2_backend {
    server app1:8000;
    server app2:8000;
    # Use ip_hash for session affinity if using server-side sessions
    ip_hash;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;
    
    # SSL configuration
    ssl_certificate /path/to/certificate.crt;
    ssl_certificate_key /path/to/private.key;
    
    # OAuth2 specific headers
    location /oauth2/ {
        proxy_pass http://oauth2_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Important for OAuth2 redirects
        proxy_redirect off;
        
        # Increase timeout for authorization flow
        proxy_read_timeout 60s;
        proxy_connect_timeout 10s;
    }
}
```

## Getting Help

### Support Channels

1. **Check Server Health**:
```bash
curl https://sbd-instance.com/oauth2/health
```

2. **Review Server Metadata**:
```bash
curl https://sbd-instance.com/oauth2/.well-known/oauth-authorization-server | jq .
```

3. **Enable Debug Logging**:
```bash
DEBUG=oauth2:* npm start
```

4. **Check Documentation**:
- [OAuth2 Integration Guide](./OAUTH2_INTEGRATION.md)
- [API Reference](./OAUTH2_API_REFERENCE.md)
- [Configuration Guide](./OAUTH2_CONFIGURATION.md)

### Common Support Information to Provide

When seeking help, include:
- Client ID (never include client secret)
- Error messages and HTTP status codes
- Request/response examples (sanitized)
- Environment details (development/production)
- OAuth2 flow step where issue occurs
- Network/browser console logs
- Server logs if available

### Emergency Procedures

**If OAuth2 provider is completely inaccessible**:
1. Check server status and health endpoints
2. Verify DNS resolution and SSL certificates
3. Check load balancer and proxy configurations
4. Review server logs for errors
5. Implement fallback authentication if available

**If tokens are compromised**:
1. Revoke all tokens for affected clients
2. Rotate client secrets
3. Force user re-authentication
4. Review audit logs for suspicious activity
5. Update security configurations
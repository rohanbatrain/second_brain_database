# JWT Refresh Token Migration Guide

## Overview

This guide helps you migrate from the old JWT authentication (30-minute tokens, no refresh) to the new system (15-minute access tokens + 7-day refresh tokens).

## For Backend Developers

### Step 1: Update Environment Variables

Add to your `.env` or `.sbd` file:

```bash
# NEW: Separate secret for refresh tokens (recommended)
REFRESH_TOKEN_SECRET_KEY=generate-a-new-secret-key-here

# UPDATED: Reduced from 30 to 15 minutes
ACCESS_TOKEN_EXPIRE_MINUTES=15

# NEW: Refresh token lifetime
REFRESH_TOKEN_EXPIRE_DAYS=7

# NEW: Enable token rotation for security
ENABLE_TOKEN_ROTATION=true
```

**Generate secrets:**
```bash
# Generate a new secret key
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Step 2: Restart Application

```bash
# The changes are backward compatible
# Existing tokens will continue to work until they expire
uv run uvicorn src.second_brain_database.main:app --reload
```

### Step 3: Verify Changes

```bash
# Test login - should return refresh_token
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"test","password":"test"}' | jq

# Expected response:
# {
#   "access_token": "eyJ...",
#   "refresh_token": "eyJ...",  ← NEW
#   "token_type": "bearer",
#   "expires_in": 900,           ← NEW (15 min in seconds)
#   "refresh_expires_in": 604800 ← NEW (7 days in seconds)
# }
```

## For Frontend Developers

### Step 1: Update Token Storage

**Before:**
```javascript
// Old way - only access token
const { access_token } = await login(username, password);
localStorage.setItem('token', access_token);
```

**After:**
```javascript
// New way - store both tokens
const { access_token, refresh_token } = await login(username, password);
localStorage.setItem('access_token', access_token);
localStorage.setItem('refresh_token', refresh_token);
```

### Step 2: Implement Auto-Refresh

Create a wrapper function for API calls:

```javascript
// api.js
async function apiCall(url, options = {}) {
  // Try request with current access token
  let response = await fetch(url, {
    ...options,
    headers: {
      ...options.headers,
      'Authorization': `Bearer ${localStorage.getItem('access_token')}`
    }
  });
  
  // Handle 401 - Token Expired
  if (response.status === 401) {
    const errorData = await response.json();
    
    // Check if we should try to refresh
    if (errorData.detail?.action === 'refresh') {
      const refreshed = await refreshAccessToken();
      
      if (refreshed) {
        // Retry original request with new token
        return fetch(url, {
          ...options,
          headers: {
            ...options.headers,
            'Authorization': `Bearer ${localStorage.getItem('access_token')}`
          }
        });
      }
    }
    
    // Refresh failed or not applicable - redirect to login
    redirectToLogin();
  }
  
  return response;
}

async function refreshAccessToken() {
  try {
    const response = await fetch('/auth/refresh', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        refresh_token: localStorage.getItem('refresh_token')
      })
    });
    
    if (response.ok) {
      const tokens = await response.json();
      localStorage.setItem('access_token', tokens.access_token);
      
      // Update refresh token if rotated
      if (tokens.refresh_token) {
        localStorage.setItem('refresh_token', tokens.refresh_token);
      }
      
      return true;
    }
  } catch (error) {
    console.error('Token refresh failed:', error);
  }
  
  return false;
}

function redirectToLogin() {
  localStorage.clear();
  window.location.href = '/login';
}

// Export for use throughout app
export { apiCall };
```

### Step 3: Update All API Calls

**Before:**
```javascript
// Direct fetch calls
const response = await fetch('/api/users', {
  headers: {
    'Authorization': `Bearer ${localStorage.getItem('token')}`
  }
});
```

**After:**
```javascript
// Use wrapper function
import { apiCall } from './api';

const response = await apiCall('/api/users');
```

### Step 4: Handle Logout

```javascript
async function logout() {
  try {
    // Call logout endpoint to blacklist tokens
    await fetch('/auth/logout', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('access_token')}`
      }
    });
  } catch (error) {
    console.error('Logout failed:', error);
  } finally {
    // Clear local storage regardless
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    window.location.href = '/login';
  }
}
```

## For Mobile App Developers

### React Native Example

```javascript
import AsyncStorage from '@react-native-async-storage/async-storage';

// Store tokens
async function storeTokens(accessToken, refreshToken) {
  await AsyncStorage.multiSet([
    ['access_token', accessToken],
    ['refresh_token', refreshToken]
  ]);
}

// Get tokens
async function getTokens() {
  const [accessToken, refreshToken] = await AsyncStorage.multiGet([
    'access_token',
    'refresh_token'
  ]);
  return {
    accessToken: accessToken[1],
    refreshToken: refreshToken[1]
  };
}

// API call with auto-refresh
async function apiCall(url, options = {}) {
  const { accessToken, refreshToken } = await getTokens();
  
  let response = await fetch(url, {
    ...options,
    headers: {
      ...options.headers,
      'Authorization': `Bearer ${accessToken}`
    }
  });
  
  if (response.status === 401) {
    const errorData = await response.json();
    
    if (errorData.detail?.action === 'refresh' && refreshToken) {
      // Try to refresh
      const refreshResponse = await fetch('/auth/refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken })
      });
      
      if (refreshResponse.ok) {
        const tokens = await refreshResponse.json();
        await storeTokens(tokens.access_token, tokens.refresh_token);
        
        // Retry original request
        return fetch(url, {
          ...options,
          headers: {
            ...options.headers,
            'Authorization': `Bearer ${tokens.access_token}`
          }
        });
      }
    }
    
    // Refresh failed - navigate to login
    await AsyncStorage.clear();
    // Navigate to login screen
  }
  
  return response;
}
```

### Flutter Example

```dart
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';

class AuthService {
  final storage = FlutterSecureStorage();
  
  Future<void> storeTokens(String accessToken, String refreshToken) async {
    await storage.write(key: 'access_token', value: accessToken);
    await storage.write(key: 'refresh_token', value: refreshToken);
  }
  
  Future<http.Response> apiCall(String url, {Map<String, String>? headers}) async {
    String? accessToken = await storage.read(key: 'access_token');
    
    var response = await http.get(
      Uri.parse(url),
      headers: {
        ...?headers,
        'Authorization': 'Bearer $accessToken',
      },
    );
    
    if (response.statusCode == 401) {
      var errorData = jsonDecode(response.body);
      
      if (errorData['detail']?['action'] == 'refresh') {
        bool refreshed = await refreshAccessToken();
        
        if (refreshed) {
          // Retry with new token
          accessToken = await storage.read(key: 'access_token');
          return http.get(
            Uri.parse(url),
            headers: {
              ...?headers,
              'Authorization': 'Bearer $accessToken',
            },
          );
        }
      }
      
      // Refresh failed - navigate to login
      await storage.deleteAll();
      // Navigate to login screen
    }
    
    return response;
  }
  
  Future<bool> refreshAccessToken() async {
    try {
      String? refreshToken = await storage.read(key: 'refresh_token');
      
      var response = await http.post(
        Uri.parse('/auth/refresh'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'refresh_token': refreshToken}),
      );
      
      if (response.statusCode == 200) {
        var tokens = jsonDecode(response.body);
        await storeTokens(
          tokens['access_token'],
          tokens['refresh_token']
        );
        return true;
      }
    } catch (e) {
      print('Token refresh failed: $e');
    }
    
    return false;
  }
}
```

## Testing Your Migration

### 1. Test Login
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"test","password":"test"}'
```

Expected: Response includes both `access_token` and `refresh_token`

### 2. Test API Call
```bash
curl http://localhost:8000/api/some-endpoint \
  -H "Authorization: Bearer <access_token>"
```

Expected: 200 OK response

### 3. Test Refresh
```bash
curl -X POST http://localhost:8000/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"<refresh_token>"}'
```

Expected: New `access_token` and `refresh_token`

### 4. Test Expired Refresh Token
```bash
# Use an old/invalid refresh token
curl -X POST http://localhost:8000/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"invalid"}'
```

Expected: 401 with `action: "login"`

## Common Issues

### Issue: "refresh_token not in response"
**Cause:** Backend not updated or `create_refresh_token` not called
**Solution:** Verify backend changes are deployed and environment variables are set

### Issue: "401 on refresh endpoint"
**Cause:** Sending access_token instead of refresh_token
**Solution:** Ensure you're sending the refresh_token from login response

### Issue: "Token rotation not working"
**Cause:** `ENABLE_TOKEN_ROTATION` not set to true
**Solution:** Add `ENABLE_TOKEN_ROTATION=true` to environment variables

### Issue: "Infinite refresh loop"
**Cause:** Not updating stored tokens after refresh
**Solution:** Update both access_token and refresh_token in storage after refresh

## Rollback Plan

If you need to rollback:

1. **Backend:** Set `ACCESS_TOKEN_EXPIRE_MINUTES=30` in config
2. **Frontend:** Continue using access_token only (ignore refresh_token)
3. **No data loss:** All changes are backward compatible

## Support

For issues or questions:
- Check `docs/JWT_IMPLEMENTATION_SUMMARY.md` for technical details
- Review `docs/JWT_IMPROVEMENTS_PLAN.md` for architecture
- Check application logs for error messages
- Test with curl commands to isolate frontend vs backend issues

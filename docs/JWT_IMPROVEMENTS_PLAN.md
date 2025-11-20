# JWT Authentication Improvements Plan

## Current State Analysis

### What Works Well ✅
- Token versioning for invalidation (password changes)
- Permanent tokens for long-lived integrations
- Blacklist checking
- Comprehensive logging
- Rate limiting on refresh endpoint

### Issues Found 🔴

1. **No Refresh Token Flow**
   - `create_refresh_token()` exists but is never used
   - Users must re-login every 30 minutes
   - Poor UX for active users

2. **OAuth2 in Documentation**
   - OpenAPI shows OAuth2 security schemes
   - Actual implementation is simple Bearer token
   - Confusing for API consumers

3. **Short Token Expiry**
   - 30 minutes is too aggressive
   - No sliding session mechanism
   - Frequent interruptions for users

4. **Unclear 401 Handling**
   - Documentation doesn't explain token expiration clearly
   - No guidance on refresh flow
   - Frontend developers confused about retry logic

## Recommended Improvements

### 1. Implement Proper Refresh Token Flow

**Current:**
```python
# Only access tokens, no refresh tokens
access_token = await create_access_token({"sub": username})
```

**Improved:**
```python
# Return both tokens
access_token = await create_access_token({"sub": username})
refresh_token = await create_refresh_token({"sub": username})

return {
    "access_token": access_token,
    "refresh_token": refresh_token,  # NEW
    "token_type": "bearer",
    "expires_in": 900,  # 15 minutes
    "refresh_expires_in": 604800  # 7 days
}
```

**Benefits:**
- Access tokens can be shorter (15 min) for security
- Refresh tokens last longer (7 days) for UX
- Automatic token refresh without re-login
- Better security/UX balance

### 2. Fix OpenAPI Documentation

**Remove OAuth2, Use Simple Bearer:**

```python
# main.py - BEFORE (confusing)
openapi_schema["components"]["securitySchemes"] = {
    "JWTBearer": {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        # ... OAuth2-style description
    }
}

# main.py - AFTER (clear)
openapi_schema["components"]["securitySchemes"] = {
    "BearerAuth": {  # Simpler name
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": """
        **Authentication Flow:**
        
        1. **Login:** POST /auth/login
           ```json
           {
             "username": "user",
             "password": "pass"
           }
           ```
        
        2. **Response:**
           ```json
           {
             "access_token": "eyJ...",
             "refresh_token": "eyJ...",
             "token_type": "bearer",
             "expires_in": 900
           }
           ```
        
        3. **Use Token:**
           ```
           Authorization: Bearer eyJ...
           ```
        
        4. **When Expired (401):**
           - POST /auth/refresh with refresh_token
           - Get new access_token
           - Retry original request
        
        **Token Lifetimes:**
        - Access Token: 15 minutes
        - Refresh Token: 7 days
        
        **Error Responses:**
        - 401: Token expired or invalid → Use refresh token
        - 403: Insufficient permissions → Check user role
        """
    }
}
```

### 3. Improve Token Expiry Strategy

**Current Config:**
```python
# config.py
ACCESS_TOKEN_EXPIRE_MINUTES: int = 30  # Too long for security
```

**Improved Config:**
```python
# config.py
class Settings(BaseSettings):
    # JWT Configuration
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15  # Shorter for security
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7     # NEW: Longer for UX
    REFRESH_TOKEN_SECRET_KEY: SecretStr = SecretStr("")  # NEW: Separate secret
    
    # Token rotation (optional security enhancement)
    ENABLE_TOKEN_ROTATION: bool = True  # NEW: Rotate refresh tokens
    MAX_REFRESH_TOKEN_REUSE: int = 1    # NEW: Prevent token reuse
```

### 4. Enhanced 401 Error Responses

**Current:**
```python
raise HTTPException(
    status_code=401,
    detail="Token has expired"
)
```

**Improved:**
```python
raise HTTPException(
    status_code=401,
    detail={
        "error": "token_expired",
        "message": "Access token has expired",
        "action": "refresh",  # Tell client what to do
        "refresh_endpoint": "/auth/refresh"
    },
    headers={
        "WWW-Authenticate": 'Bearer error="invalid_token", error_description="Token has expired"'
    }
)
```

### 5. Implement Refresh Token Endpoint (Enhanced)

**New Implementation:**
```python
@router.post("/refresh", response_model=TokenRefreshResponse)
async def refresh_access_token(
    refresh_token: str = Body(..., embed=True),
    request: Request = None
):
    """
    Refresh access token using refresh token.
    
    **Flow:**
    1. Validate refresh token
    2. Check if token is blacklisted
    3. Verify user still exists and is active
    4. Generate new access token
    5. Optionally rotate refresh token (security best practice)
    
    **Returns:**
    - New access_token (always)
    - New refresh_token (if rotation enabled)
    """
    try:
        # Decode refresh token
        payload = jwt.decode(
            refresh_token,
            settings.REFRESH_TOKEN_SECRET_KEY.get_secret_value(),
            algorithms=["HS256"]
        )
        
        # Verify token type
        if payload.get("type") != "refresh":
            raise HTTPException(401, "Invalid token type")
        
        username = payload.get("sub")
        if not username:
            raise HTTPException(401, "Invalid token")
        
        # Check blacklist
        if await is_token_blacklisted(refresh_token):
            raise HTTPException(401, "Token has been revoked")
        
        # Get user
        user = await db_manager.get_collection("users").find_one(
            {"username": username}
        )
        if not user or not user.get("is_active", True):
            raise HTTPException(401, "User not found or inactive")
        
        # Generate new access token
        new_access_token = await create_access_token({"sub": username})
        
        response = {
            "access_token": new_access_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        }
        
        # Token rotation (optional security enhancement)
        if settings.ENABLE_TOKEN_ROTATION:
            # Blacklist old refresh token
            await blacklist_token(refresh_token, expires_in_days=7)
            
            # Generate new refresh token
            new_refresh_token = await create_refresh_token({"sub": username})
            response["refresh_token"] = new_refresh_token
            response["refresh_expires_in"] = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
        
        logger.info(f"Token refreshed for user: {username}")
        return response
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            401,
            detail={
                "error": "refresh_token_expired",
                "message": "Refresh token has expired. Please login again.",
                "action": "login"
            }
        )
    except Exception as e:
        logger.error(f"Token refresh failed: {e}")
        raise HTTPException(401, "Invalid refresh token")
```

## Implementation Steps

### Phase 1: Core Refresh Token Flow (Don't Break Auth)
1. ✅ Add `REFRESH_TOKEN_SECRET_KEY` to config
2. ✅ Update `create_refresh_token()` to use separate secret
3. ✅ Modify login/register to return refresh_token
4. ✅ Implement enhanced `/auth/refresh` endpoint
5. ✅ Add refresh token to response models

### Phase 2: Documentation Updates
1. ✅ Simplify OpenAPI security schemes (remove OAuth2 confusion)
2. ✅ Add clear 401 error documentation
3. ✅ Document refresh token flow
4. ✅ Add frontend integration examples

### Phase 3: Token Expiry Optimization
1. ✅ Reduce access token to 15 minutes
2. ✅ Set refresh token to 7 days
3. ✅ Add token rotation (optional)
4. ✅ Update rate limits

### Phase 4: Enhanced Error Responses
1. ✅ Structured 401 responses with action hints
2. ✅ Better WWW-Authenticate headers
3. ✅ Client-friendly error messages

## Migration Strategy (No Breaking Changes)

### Backward Compatibility
```python
# Support both old and new response formats
@router.post("/login")
async def login(
    credentials: LoginRequest,
    include_refresh_token: bool = Query(True, description="Include refresh token in response")
):
    # ... authentication logic ...
    
    response = {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }
    
    # NEW: Optional refresh token (default: included)
    if include_refresh_token:
        response["refresh_token"] = refresh_token
        response["refresh_expires_in"] = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
    
    return response
```

### Frontend Migration
```javascript
// OLD (still works)
const { access_token } = await login(username, password);
localStorage.setItem('token', access_token);

// NEW (recommended)
const { access_token, refresh_token } = await login(username, password);
localStorage.setItem('access_token', access_token);
localStorage.setItem('refresh_token', refresh_token);

// Auto-refresh on 401
async function apiCall(url, options) {
  let response = await fetch(url, {
    ...options,
    headers: {
      'Authorization': `Bearer ${localStorage.getItem('access_token')}`
    }
  });
  
  if (response.status === 401) {
    const errorData = await response.json();
    
    // Check if we should refresh
    if (errorData.detail?.action === 'refresh') {
      // Refresh token
      const refreshResponse = await fetch('/auth/refresh', {
        method: 'POST',
        body: JSON.stringify({
          refresh_token: localStorage.getItem('refresh_token')
        })
      });
      
      if (refreshResponse.ok) {
        const { access_token, refresh_token } = await refreshResponse.json();
        localStorage.setItem('access_token', access_token);
        if (refresh_token) {
          localStorage.setItem('refresh_token', refresh_token);
        }
        
        // Retry original request
        return fetch(url, {
          ...options,
          headers: {
            'Authorization': `Bearer ${access_token}`
          }
        });
      }
    }
    
    // Refresh failed or not applicable - redirect to login
    window.location.href = '/login';
  }
  
  return response;
}
```

## Testing Checklist

### Unit Tests
- [ ] Refresh token creation
- [ ] Refresh token validation
- [ ] Token rotation logic
- [ ] Blacklist integration
- [ ] Error responses

### Integration Tests
- [ ] Login → Get both tokens
- [ ] Use access token → Success
- [ ] Access token expires → 401
- [ ] Refresh with refresh token → New access token
- [ ] Refresh token expires → 401 with login action
- [ ] Blacklisted refresh token → 401

### Security Tests
- [ ] Cannot use access token as refresh token
- [ ] Cannot use refresh token as access token
- [ ] Refresh token rotation prevents reuse
- [ ] Token version mismatch detection
- [ ] Blacklist enforcement

## Benefits Summary

### Security Improvements
- ✅ Shorter access token lifetime (15 min vs 30 min)
- ✅ Separate secrets for access/refresh tokens
- ✅ Token rotation prevents token reuse attacks
- ✅ Better audit trail with refresh events

### User Experience Improvements
- ✅ No forced re-login every 30 minutes
- ✅ Seamless token refresh in background
- ✅ 7-day session duration
- ✅ Clear error messages with action hints

### Developer Experience Improvements
- ✅ Clear documentation (no OAuth2 confusion)
- ✅ Structured error responses
- ✅ Easy frontend integration
- ✅ Backward compatible migration

## Configuration Example

```bash
# .env or .sbd file
SECRET_KEY=your-access-token-secret-key-here
REFRESH_TOKEN_SECRET_KEY=your-refresh-token-secret-key-here-different-from-access
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
ENABLE_TOKEN_ROTATION=true
MAX_REFRESH_TOKEN_REUSE=1
```

## Monitoring & Metrics

Track these metrics after implementation:
- Token refresh rate (should be high if working well)
- Failed refresh attempts (security indicator)
- Average session duration (should increase)
- Re-login frequency (should decrease)
- 401 error rate (should decrease after initial spike)

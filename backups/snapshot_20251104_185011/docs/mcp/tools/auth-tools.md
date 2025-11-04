# Authentication & Profile MCP Tools

## Overview

Authentication and profile management tools provide comprehensive functionality for user authentication, profile management, security settings, and account administration. All tools include proper security validation and audit logging.

## Core Authentication Tools

### get_auth_status

Get current user authentication status and session information.

**Parameters:** None

**Permissions Required:** `user:read`

**Example:**
```python
auth_status = await mcp_client.call_tool("get_auth_status")

# Response
{
    "user_id": "64f8a1b2c3d4e5f6a7b8c9d1",
    "username": "john_doe",
    "email": "john@example.com",
    "role": "admin",
    "authenticated": true,
    "session_expires_at": "2024-01-20T18:30:00Z",
    "last_login": "2024-01-20T10:15:00Z",
    "login_count": 42,
    "account_status": "active"
}
```

### validate_token

Validate a JWT or permanent token.

**Parameters:**
- `token` (string, required): Token to validate

**Permissions Required:** `user:read`

**Example:**
```python
validation = await mcp_client.call_tool("validate_token", {
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
})

# Response
{
    "valid": true,
    "token_type": "jwt",
    "expires_at": "2024-01-20T18:30:00Z",
    "user_id": "64f8a1b2c3d4e5f6a7b8c9d1",
    "permissions": ["user:read", "user:write", "family:read"]
}
```

### get_auth_methods

Get available authentication methods for the current user.

**Parameters:** None

**Permissions Required:** `user:read`

**Example:**
```python
auth_methods = await mcp_client.call_tool("get_auth_methods")

# Response
{
    "password_enabled": true,
    "webauthn_enabled": true,
    "totp_enabled": true,
    "backup_codes_available": 8,
    "permanent_tokens": 2,
    "trusted_devices": 3,
    "available_methods": [
        "password",
        "webauthn",
        "totp",
        "backup_codes"
    ]
}
```

## Profile Management Tools

### get_user_profile

Get user profile information.

**Parameters:**
- `user_id` (string, optional): User ID (defaults to current user)

**Permissions Required:** `user:read` (or `user:admin` for other users)

**Example:**
```python
profile = await mcp_client.call_tool("get_user_profile")

# Response
{
    "user_id": "64f8a1b2c3d4e5f6a7b8c9d1",
    "username": "john_doe",
    "email": "john@example.com",
    "display_name": "John Doe",
    "bio": "Software developer and family man",
    "avatar_url": "https://example.com/avatars/john.jpg",
    "banner_url": "https://example.com/banners/john.jpg",
    "created_at": "2023-06-15T10:00:00Z",
    "last_active": "2024-01-20T15:30:00Z",
    "profile_visibility": "public",
    "email_verified": true
}
```

### update_user_profile

Update user profile information.

**Parameters:**
- `display_name` (string, optional): Display name
- `bio` (string, optional): User biography
- `profile_visibility` (string, optional): Profile visibility ("public", "private", "friends")

**Permissions Required:** `user:write`

**Example:**
```python
result = await mcp_client.call_tool("update_user_profile", {
    "display_name": "John Smith",
    "bio": "Senior software developer with a passion for AI",
    "profile_visibility": "public"
})

# Response
{
    "success": true,
    "updated_fields": ["display_name", "bio"],
    "message": "Profile updated successfully"
}
```

### get_user_preferences

Get user preferences and settings.

**Parameters:** None

**Permissions Required:** `user:read`

**Example:**
```python
preferences = await mcp_client.call_tool("get_user_preferences")

# Response
{
    "theme": "dark",
    "language": "en",
    "timezone": "America/New_York",
    "notifications": {
        "email_enabled": true,
        "push_enabled": false,
        "family_invitations": true,
        "purchase_confirmations": true,
        "security_alerts": true
    },
    "privacy": {
        "profile_visibility": "public",
        "show_online_status": true,
        "allow_friend_requests": true
    }
}
```

### update_user_preferences

Update user preferences and settings.

**Parameters:**
- `preferences` (object, required): Preferences to update

**Permissions Required:** `user:write`

**Example:**
```python
result = await mcp_client.call_tool("update_user_preferences", {
    "preferences": {
        "theme": "light",
        "notifications": {
            "email_enabled": false,
            "push_enabled": true
        },
        "privacy": {
            "profile_visibility": "private"
        }
    }
})

# Response
{
    "success": true,
    "updated_preferences": {
        "theme": "light",
        "notifications.email_enabled": false,
        "notifications.push_enabled": true,
        "privacy.profile_visibility": "private"
    }
}
```

## Security Management Tools

### get_security_dashboard

Get comprehensive security dashboard information.

**Parameters:** None

**Permissions Required:** `user:security`

**Example:**
```python
security_info = await mcp_client.call_tool("get_security_dashboard")

# Response
{
    "account_security_score": 85,
    "last_password_change": "2023-12-01T10:00:00Z",
    "two_factor_enabled": true,
    "trusted_devices": 3,
    "recent_logins": [
        {
            "timestamp": "2024-01-20T10:15:00Z",
            "ip_address": "192.168.1.100",
            "user_agent": "Mozilla/5.0...",
            "location": "New York, NY"
        }
    ],
    "security_alerts": [
        {
            "type": "new_device_login",
            "timestamp": "2024-01-19T14:30:00Z",
            "resolved": true
        }
    ],
    "recommendations": [
        "Enable backup codes for 2FA",
        "Review trusted devices"
    ]
}
```

### change_password

Change user password with proper validation.

**Parameters:**
- `current_password` (string, required): Current password
- `new_password` (string, required): New password

**Permissions Required:** `user:security`

**Example:**
```python
result = await mcp_client.call_tool("change_password", {
    "current_password": "current_secure_password",
    "new_password": "new_secure_password_123"
})

# Response
{
    "success": true,
    "message": "Password changed successfully",
    "security_score_change": +5,
    "recommendations": [
        "Consider enabling 2FA if not already enabled"
    ]
}
```

### check_username_availability

Check if a username is available.

**Parameters:**
- `username` (string, required): Username to check

**Permissions Required:** `user:read`

**Example:**
```python
availability = await mcp_client.call_tool("check_username_availability", {
    "username": "new_username"
})

# Response
{
    "available": true,
    "username": "new_username",
    "suggestions": []
}

# If not available
{
    "available": false,
    "username": "taken_username",
    "suggestions": [
        "taken_username_2024",
        "taken_username_1",
        "taken_username_alt"
    ]
}
```

### check_email_availability

Check if an email address is available.

**Parameters:**
- `email` (string, required): Email to check

**Permissions Required:** `user:read`

**Example:**
```python
availability = await mcp_client.call_tool("check_email_availability", {
    "email": "new@example.com"
})

# Response
{
    "available": true,
    "email": "new@example.com"
}
```

## Two-Factor Authentication Tools

### get_2fa_status

Get current 2FA status and configuration.

**Parameters:** None

**Permissions Required:** `user:security`

**Example:**
```python
twofa_status = await mcp_client.call_tool("get_2fa_status")

# Response
{
    "enabled": true,
    "method": "totp",
    "backup_codes_remaining": 6,
    "recovery_codes_generated": "2023-12-01T10:00:00Z",
    "last_used": "2024-01-20T08:30:00Z",
    "trusted_devices": 2,
    "setup_completed": true
}
```

### setup_2fa

Initialize 2FA setup process.

**Parameters:**
- `method` (string, optional): 2FA method ("totp", "sms") - defaults to "totp"

**Permissions Required:** `user:security`

**Example:**
```python
setup_info = await mcp_client.call_tool("setup_2fa", {
    "method": "totp"
})

# Response
{
    "setup_key": "JBSWY3DPEHPK3PXP",
    "qr_code_url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...",
    "backup_codes": [
        "12345678",
        "87654321",
        "11223344",
        "44332211",
        "55667788",
        "88776655",
        "99887766",
        "66778899"
    ],
    "instructions": "Scan the QR code with your authenticator app and enter the verification code to complete setup."
}
```

### verify_2fa_code

Verify a 2FA code during setup or authentication.

**Parameters:**
- `code` (string, required): 2FA verification code
- `setup_key` (string, optional): Setup key for initial verification

**Permissions Required:** `user:security`

**Example:**
```python
verification = await mcp_client.call_tool("verify_2fa_code", {
    "code": "123456",
    "setup_key": "JBSWY3DPEHPK3PXP"
})

# Response
{
    "valid": true,
    "setup_completed": true,
    "message": "2FA setup completed successfully",
    "backup_codes_saved": true
}
```

### disable_2fa

Disable 2FA for the user account.

**Parameters:**
- `confirmation_code` (string, required): Current 2FA code for confirmation

**Permissions Required:** `user:security`

**Example:**
```python
result = await mcp_client.call_tool("disable_2fa", {
    "confirmation_code": "123456"
})

# Response
{
    "success": true,
    "message": "2FA disabled successfully",
    "security_score_change": -15,
    "recommendations": [
        "Consider re-enabling 2FA for better security",
        "Use strong, unique passwords"
    ]
}
```

### get_backup_codes_status

Get status of 2FA backup codes.

**Parameters:** None

**Permissions Required:** `user:security`

**Example:**
```python
backup_status = await mcp_client.call_tool("get_backup_codes_status")

# Response
{
    "total_codes": 8,
    "remaining_codes": 6,
    "used_codes": 2,
    "last_generated": "2023-12-01T10:00:00Z",
    "last_used": "2024-01-15T14:20:00Z",
    "regeneration_recommended": false
}
```

### regenerate_backup_codes

Generate new 2FA backup codes.

**Parameters:**
- `confirmation_code` (string, required): Current 2FA code for confirmation

**Permissions Required:** `user:security`

**Example:**
```python
new_codes = await mcp_client.call_tool("regenerate_backup_codes", {
    "confirmation_code": "123456"
})

# Response
{
    "success": true,
    "backup_codes": [
        "98765432",
        "23456789",
        "34567890",
        "45678901",
        "56789012",
        "67890123",
        "78901234",
        "89012345"
    ],
    "previous_codes_invalidated": true,
    "message": "New backup codes generated. Store them securely."
}
```

## Security Lockdown Tools

### get_trusted_ips_status

Get IP lockdown status and trusted IPs.

**Parameters:** None

**Permissions Required:** `user:security`

**Example:**
```python
ip_status = await mcp_client.call_tool("get_trusted_ips_status")

# Response
{
    "lockdown_enabled": true,
    "trusted_ips": [
        {
            "ip_address": "192.168.1.100",
            "description": "Home network",
            "added_at": "2023-12-01T10:00:00Z",
            "last_used": "2024-01-20T15:30:00Z"
        },
        {
            "ip_address": "10.0.0.50",
            "description": "Office network",
            "added_at": "2023-12-15T09:00:00Z",
            "last_used": "2024-01-19T17:45:00Z"
        }
    ],
    "current_ip": "192.168.1.100",
    "current_ip_trusted": true
}
```

### request_ip_lockdown

Request IP lockdown activation.

**Parameters:**
- `confirmation_code` (string, required): 2FA code for confirmation

**Permissions Required:** `user:security`

**Example:**
```python
result = await mcp_client.call_tool("request_ip_lockdown", {
    "confirmation_code": "123456"
})

# Response
{
    "success": true,
    "lockdown_enabled": true,
    "current_ip_added": true,
    "trusted_ip": "192.168.1.100",
    "message": "IP lockdown enabled. Only trusted IPs can access your account.",
    "security_score_change": +10
}
```

### add_trusted_ip

Add an IP address to the trusted list.

**Parameters:**
- `ip_address` (string, required): IP address to trust
- `description` (string, optional): Description for the IP

**Permissions Required:** `user:security`

**Example:**
```python
result = await mcp_client.call_tool("add_trusted_ip", {
    "ip_address": "203.0.113.10",
    "description": "Mobile hotspot"
})

# Response
{
    "success": true,
    "ip_address": "203.0.113.10",
    "description": "Mobile hotspot",
    "message": "IP address added to trusted list"
}
```

## Avatar and Banner Management

### get_user_avatar

Get current user avatar information.

**Parameters:** None

**Permissions Required:** `user:read`

**Example:**
```python
avatar_info = await mcp_client.call_tool("get_user_avatar")

# Response
{
    "current_avatar": {
        "id": "64f8a1b2c3d4e5f6a7b8c9d5",
        "name": "Cool Avatar",
        "url": "https://example.com/avatars/cool-avatar.png",
        "type": "owned",
        "acquired_at": "2023-12-01T10:00:00Z"
    },
    "available_avatars": 15,
    "owned_avatars": 8,
    "rented_avatars": 2
}
```

### set_current_avatar

Set the current user avatar.

**Parameters:**
- `avatar_id` (string, required): Avatar ID to set as current

**Permissions Required:** `user:write`

**Example:**
```python
result = await mcp_client.call_tool("set_current_avatar", {
    "avatar_id": "64f8a1b2c3d4e5f6a7b8c9d6"
})

# Response
{
    "success": true,
    "avatar": {
        "id": "64f8a1b2c3d4e5f6a7b8c9d6",
        "name": "New Avatar",
        "url": "https://example.com/avatars/new-avatar.png"
    },
    "message": "Avatar updated successfully"
}
```

### get_user_banner

Get current user banner information.

**Parameters:** None

**Permissions Required:** `user:read`

**Example:**
```python
banner_info = await mcp_client.call_tool("get_user_banner")

# Response
{
    "current_banner": {
        "id": "64f8a1b2c3d4e5f6a7b8c9d7",
        "name": "Sunset Banner",
        "url": "https://example.com/banners/sunset.jpg",
        "type": "rented",
        "expires_at": "2024-02-01T00:00:00Z"
    },
    "available_banners": 25,
    "owned_banners": 3,
    "rented_banners": 1
}
```

### set_current_banner

Set the current user banner.

**Parameters:**
- `banner_id` (string, required): Banner ID to set as current

**Permissions Required:** `user:write`

**Example:**
```python
result = await mcp_client.call_tool("set_current_banner", {
    "banner_id": "64f8a1b2c3d4e5f6a7b8c9d8"
})

# Response
{
    "success": true,
    "banner": {
        "id": "64f8a1b2c3d4e5f6a7b8c9d8",
        "name": "Mountain Banner",
        "url": "https://example.com/banners/mountain.jpg"
    },
    "message": "Banner updated successfully"
}
```

## Error Handling

### Common Authentication Errors

**Invalid Credentials:**
```json
{
    "error": {
        "code": "INVALID_CREDENTIALS",
        "message": "Invalid username or password",
        "details": {
            "attempts_remaining": 3,
            "lockout_duration": 300
        }
    }
}
```

**2FA Required:**
```json
{
    "error": {
        "code": "2FA_REQUIRED",
        "message": "Two-factor authentication required",
        "details": {
            "methods_available": ["totp", "backup_codes"],
            "setup_required": false
        }
    }
}
```

**Account Locked:**
```json
{
    "error": {
        "code": "ACCOUNT_LOCKED",
        "message": "Account temporarily locked due to security policy",
        "details": {
            "reason": "too_many_failed_attempts",
            "unlock_at": "2024-01-20T16:00:00Z",
            "contact_support": true
        }
    }
}
```

## Best Practices

### Security Recommendations

1. **Enable 2FA** for all accounts
2. **Use strong passwords** with regular rotation
3. **Monitor security dashboard** regularly
4. **Review trusted devices** and IPs periodically
5. **Keep backup codes** secure and accessible

### Profile Management

1. **Keep profile information** current and accurate
2. **Use appropriate privacy settings** for your needs
3. **Regularly review** notification preferences
4. **Update avatar and banner** to reflect current preferences

### Performance Optimization

1. **Cache profile data** on client side when appropriate
2. **Batch preference updates** when making multiple changes
3. **Use appropriate polling intervals** for status checks
4. **Implement proper error handling** for network issues
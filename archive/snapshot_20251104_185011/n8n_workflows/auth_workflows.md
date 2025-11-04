# N8N Authentication Workflows

## Overview
Authentication workflows handle user registration, login, session management, and security features like 2FA and password management.

## 1. User Registration & Onboarding Workflow

### Workflow Name: `auth_user_registration`
### Purpose: Complete user registration and onboarding process

### Trigger
- **Type**: Webhook
- **Path**: `/webhook/user-registration`
- **Method**: POST

### Input Parameters
```json
{
  "email": "user@example.com",
  "username": "johndoe",
  "password": "securepassword123",
  "full_name": "John Doe",
  "auto_verify": false
}
```

### Workflow Steps

#### 1. Input Validation
- Validate email format
- Check password strength
- Validate username format
- Check for required fields

#### 2. Check Availability
- **API Call**: `GET /auth/check-email?email={email}`
- **API Call**: `GET /auth/check-username?username={username}`
- Handle conflicts and suggest alternatives

#### 3. User Registration
- **API Call**: `POST /auth/register`
- **Payload**:
```json
{
  "email": "{{ $json.email }}",
  "username": "{{ $json.username }}",
  "password": "{{ $json.password }}",
  "full_name": "{{ $json.full_name }}"
}
```
- Handle validation errors
- Store user ID from response

#### 4. Email Verification (if not auto-verify)
- **API Call**: `POST /auth/resend-verification-email`
- Send verification email via SMTP node
- Store verification token

#### 5. Profile Setup
- Set up default notification preferences
- Create initial user profile data
- Set up default security settings

#### 6. Welcome Notifications
- Send welcome email
- Create initial notifications in system
- Log registration event

### Error Handling
- Email/username already exists
- Invalid input data
- Registration failures
- Email sending failures

### Output
```json
{
  "success": true,
  "user_id": "user_123",
  "email_sent": true,
  "verification_required": true,
  "next_steps": ["verify_email", "complete_profile"]
}
```

## 2. Login & Session Management Workflow

### Workflow Name: `auth_login_session`
### Purpose: Handle user authentication and session management

### Trigger
- **Type**: Webhook
- **Path**: `/webhook/user-login`
- **Method**: POST

### Input Parameters
```json
{
  "username": "johndoe",
  "password": "securepassword123",
  "remember_me": false
}
```

### Workflow Steps

#### 1. Authentication
- **API Call**: `POST /auth/login`
- **Payload**:
```json
{
  "username": "{{ $json.username }}",
  "password": "{{ $json.password }}"
}
```
- Handle authentication failures

#### 2. 2FA Check & Verification
- Check if 2FA is enabled for user
- If enabled:
  - **API Call**: `GET /auth/2fa/status`
  - Request 2FA code from user
  - **API Call**: `POST /auth/2fa/verify`
  - Handle verification failures

#### 3. Session Management
- Store JWT token securely
- Set session expiration
- Handle remember_me option
- Create session record

#### 4. Post-Login Actions
- Update last login timestamp
- Log login event
- Check for pending notifications
- Send login notifications if configured

### Error Handling
- Invalid credentials
- Account locked/disabled
- 2FA failures
- Rate limiting

### Output
```json
{
  "success": true,
  "token": "jwt_token_here",
  "expires_at": "2025-10-30T10:00:00Z",
  "user": {
    "id": "user_123",
    "username": "johndoe",
    "email": "user@example.com"
  },
  "requires_2fa": false
}
```

## 3. Password Reset Workflow

### Workflow Name: `auth_password_reset`
### Purpose: Handle forgot password and password reset

### Trigger
- **Type**: Webhook
- **Path**: `/webhook/forgot-password`
- **Method**: POST

### Input Parameters
```json
{
  "email": "user@example.com"
}
```

### Workflow Steps

#### 1. Initiate Password Reset
- **API Call**: `POST /auth/forgot-password`
- **Payload**:
```json
{
  "email": "{{ $json.email }}"
}
```

#### 2. Email Notification
- Generate reset link with token
- Send password reset email
- Log reset request

#### 3. Reset Token Verification (Separate Flow)
- **Trigger**: User clicks reset link
- **API Call**: `POST /auth/reset-password`
- Validate token and update password
- Send confirmation email

### Error Handling
- Email not found
- Rate limiting
- Invalid/expired tokens

### Output
```json
{
  "success": true,
  "email_sent": true,
  "reset_token_expires": "2025-10-29T12:00:00Z"
}
```

## 4. 2FA Setup & Management Workflow

### Workflow Name: `auth_2fa_management`
### Purpose: Handle two-factor authentication setup and management

### Trigger
- **Type**: Webhook
- **Path**: `/webhook/2fa-setup`
- **Method**: POST

### Input Parameters
```json
{
  "action": "setup|verify|disable",
  "user_id": "user_123",
  "verification_code": "123456" // for verify/disable
}
```

### Workflow Steps

#### Setup 2FA
1. **API Call**: `POST /auth/2fa/setup`
2. Generate QR code for authenticator apps
3. Return setup data to user

#### Verify 2FA
1. **API Call**: `POST /auth/2fa/verify`
2. Validate verification code
3. Enable 2FA if successful

#### Disable 2FA
1. **API Call**: `POST /auth/2fa/disable`
2. Require current password/verification code
3. Disable 2FA

### Error Handling
- Invalid verification codes
- Setup failures
- Security violations

### Output
```json
{
  "success": true,
  "action": "setup",
  "qr_code_url": "otpauth://...",
  "backup_codes": ["code1", "code2", ...],
  "enabled": true
}
```

## 5. Session Monitoring & Cleanup Workflow

### Workflow Name: `auth_session_monitoring`
### Purpose: Monitor and clean up expired sessions

### Trigger
- **Type**: Schedule
- **Cron**: `0 */4 * * *` (every 4 hours)

### Workflow Steps

#### 1. Find Expired Sessions
- Query for sessions older than threshold
- Identify inactive sessions

#### 2. Session Cleanup
- **API Call**: `POST /auth/logout` for each expired session
- Remove session records
- Log cleanup actions

#### 3. Security Monitoring
- Check for suspicious session patterns
- Alert on security issues
- Generate session reports

### Output
```json
{
  "cleaned_sessions": 15,
  "active_sessions": 234,
  "security_alerts": 0
}
```

## Technical Implementation Notes

### Authentication Headers
All API calls require:
```
Authorization: Bearer {{ $credentials.apiToken }}
```

### Error Response Handling
Standard error responses:
```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message",
    "details": {...}
  }
}
```

### Rate Limiting
- Respect API rate limits
- Implement exponential backoff
- Cache results where appropriate

### Security Considerations
- Never log sensitive data
- Use secure credential storage
- Validate all inputs
- Implement proper error handling

### Monitoring & Logging
- Log all authentication events
- Monitor for suspicious activity
- Track workflow performance
- Alert on failures

## Testing Scenarios

1. **Happy Path**: Successful registration, login, logout
2. **Error Cases**: Invalid credentials, rate limiting, network failures
3. **Security**: 2FA bypass attempts, session hijacking prevention
4. **Edge Cases**: Special characters in usernames, long emails, concurrent logins
5. **Recovery**: Password reset, account recovery, 2FA reset

## Dependencies

- HTTP Request node for API calls
- Email nodes for notifications
- Database nodes for session storage
- Crypto nodes for token generation
- Monitoring nodes for logging</content>
<parameter name="filePath">/Users/rohan/Documents/repos/second_brain_database/n8n_workflows/auth_workflows.md
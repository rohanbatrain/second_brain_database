# OAuth2 Client Registration Guide

This guide explains how to get OAuth2 client credentials (client ID and secret) for testing with the Second Brain Database OAuth2 provider.

## Overview

To use OAuth2 with the Second Brain Database, you need to register your application as an OAuth2 client. This process generates:
- **Client ID**: Public identifier for your application
- **Client Secret**: Private key for confidential clients
- **Redirect URIs**: Allowed callback URLs for OAuth2 flow

## Prerequisites

1. **Running OAuth2 Provider**: Your Second Brain Database instance must be running with OAuth2 enabled
2. **User Account**: You need a valid user account in the Second Brain Database
3. **Network Access**: Your test app must be able to reach the OAuth2 provider

## Method 1: Automated Registration (Recommended)

Use the provided registration script for the easiest setup:

```bash
cd docs/examples/oauth2-test-flask
python register_client.py
```

### What the script does:

1. **Connects to OAuth2 provider**: Prompts for your provider URL
2. **Authenticates**: Login with username/password or existing token
3. **Collects client details**: Name, description, redirect URI, scopes
4. **Registers client**: Creates the OAuth2 client registration
5. **Saves configuration**: Generates `.env` file with credentials

### Example interaction:

```
🔐 OAuth2 Client Registration
========================================
Enter OAuth2 provider URL (e.g., http://localhost:8000): http://localhost:8000
Using OAuth2 provider: http://localhost:8000

You need to authenticate to register a client.
Options:
1. Use existing access token
2. Login with username/password
Choose option (1 or 2): 2
Username: your_username
Password: [hidden]
✅ Login successful!

📝 Client Registration Details
------------------------------
Client name (e.g., 'OAuth2 Test Flask App'): OAuth2 Test Flask App
Client description (optional): Test application for OAuth2 integration
Redirect URI (default: http://localhost:5000/callback): 
Website URL (optional): 
Scopes (default: read:profile, write:data): 
Client type (confidential/public, default: confidential): 

📋 Registration Summary:
{
  "name": "OAuth2 Test Flask App",
  "description": "Test application for OAuth2 integration",
  "redirect_uris": ["http://localhost:5000/callback"],
  "client_type": "confidential",
  "scopes": ["read:profile", "write:data"]
}

Register this client? (y/N): y
🚀 Registering OAuth2 client...
✅ Client registered successfully!

🔑 Your OAuth2 Client Credentials:
========================================
Client ID: oauth2_client_1234567890abcdef
Client Secret: cs_1234567890abcdef1234567890abcdef
Client Type: confidential
Redirect URIs: http://localhost:5000/callback
Scopes: read:profile, write:data
Created: 2024-01-01T12:00:00Z

📄 .env Configuration:
--------------------
OAUTH2_CLIENT_ID=oauth2_client_1234567890abcdef
OAUTH2_CLIENT_SECRET=cs_1234567890abcdef1234567890abcdef
OAUTH2_REDIRECT_URI=http://localhost:5000/callback
OAUTH2_BASE_URL=http://localhost:8000
SECRET_KEY=your-secure-secret-key-here
FLASK_ENV=development
PORT=5000

Save configuration to .env file? (y/N): y
✅ Configuration saved to .env file
⚠️  Remember to update SECRET_KEY with a secure value!
```

## Method 2: Manual API Registration

If you prefer to register manually using API calls:

### Step 1: Get Access Token

First, authenticate to get an access token:

```bash
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "your_username",
    "password": "your_password"
  }'
```

Response:
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

### Step 2: Register OAuth2 Client

Use the access token to register a new OAuth2 client:

```bash
curl -X POST "http://localhost:8000/oauth2/clients" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "OAuth2 Test Flask App",
    "description": "Test application for OAuth2 integration testing",
    "redirect_uris": ["http://localhost:5000/callback"],
    "client_type": "confidential",
    "scopes": ["read:profile", "write:data"],
    "website_url": "http://localhost:5000"
  }'
```

Response:
```json
{
  "client_id": "oauth2_client_1234567890abcdef",
  "client_secret": "cs_1234567890abcdef1234567890abcdef",
  "name": "OAuth2 Test Flask App",
  "client_type": "confidential",
  "redirect_uris": ["http://localhost:5000/callback"],
  "scopes": ["read:profile", "write:data"],
  "created_at": "2024-01-01T12:00:00Z",
  "is_active": true
}
```

## Method 3: Web Interface (If Available)

Some Second Brain Database instances may provide a web interface for OAuth2 client management:

1. **Login**: Access your Second Brain Database web interface
2. **Navigate**: Go to Settings → OAuth2 Applications or Developer Settings
3. **Create**: Click "New OAuth2 Application" or similar
4. **Configure**: Fill in the application details:
   - **Name**: OAuth2 Test Flask App
   - **Description**: Test application for OAuth2 integration
   - **Redirect URI**: `http://localhost:5000/callback`
   - **Scopes**: `read:profile`, `write:data`
   - **Client Type**: Confidential
5. **Save**: Submit the form to create the client
6. **Copy Credentials**: Save the generated client ID and secret

## Client Configuration Details

When registering your OAuth2 client, use these settings for the test Flask app:

| Setting | Value | Description |
|---------|-------|-------------|
| **Name** | OAuth2 Test Flask App | Human-readable application name |
| **Description** | Test application for OAuth2 integration | Optional description |
| **Client Type** | confidential | Use confidential for server-side apps |
| **Redirect URI** | `http://localhost:5000/callback` | Must match exactly |
| **Scopes** | `read:profile`, `write:data` | Required permissions |
| **Grant Types** | `authorization_code`, `refresh_token` | OAuth2 flow types |

## Managing Existing Clients

### List Your Clients

To see your existing OAuth2 clients:

```bash
python register_client.py
# Choose option 2: List existing OAuth2 clients
```

Or manually:
```bash
curl -X GET "http://localhost:8000/oauth2/clients" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Update Client Settings

```bash
curl -X PUT "http://localhost:8000/oauth2/clients/CLIENT_ID" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Updated App Name",
    "description": "Updated description",
    "redirect_uris": ["http://localhost:5000/callback", "https://myapp.com/callback"]
  }'
```

### Delete Client

```bash
curl -X DELETE "http://localhost:8000/oauth2/clients/CLIENT_ID" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## Security Considerations

1. **Keep Secrets Safe**: Never commit client secrets to version control
2. **Use Environment Variables**: Store credentials in `.env` files
3. **Rotate Secrets**: Regularly update client secrets in production
4. **Limit Scopes**: Only request necessary permissions
5. **Validate Redirect URIs**: Ensure redirect URIs are exact matches

## Troubleshooting

### Common Issues

1. **"Unauthorized" error during registration**
   - Verify your access token is valid and not expired
   - Check that your user account has permission to create OAuth2 clients

2. **"Invalid redirect URI" during OAuth2 flow**
   - Ensure the redirect URI in your `.env` exactly matches the registered URI
   - Check for trailing slashes, protocol differences (http vs https)

3. **"Client not found" errors**
   - Verify the client ID is correct
   - Check that the client is active and not deleted

4. **Authentication failures**
   - Confirm the OAuth2 provider URL is correct and accessible
   - Verify your username/password are correct

### Debug Steps

1. **Check provider connectivity**:
   ```bash
   curl http://localhost:8000/oauth2/health
   ```

2. **Verify authentication**:
   ```bash
   curl -X POST "http://localhost:8000/auth/login" \
     -H "Content-Type: application/json" \
     -d '{"username": "test", "password": "test"}'
   ```

3. **Test client registration endpoint**:
   ```bash
   curl -X GET "http://localhost:8000/oauth2/clients" \
     -H "Authorization: Bearer YOUR_TOKEN"
   ```

## Next Steps

After registering your OAuth2 client:

1. **Update `.env`**: Ensure all configuration is correct
2. **Set SECRET_KEY**: Generate a secure Flask secret key
3. **Start the app**: Run `python app.py`
4. **Test OAuth2 flow**: Navigate to `http://localhost:5000`
5. **Verify integration**: Complete the full OAuth2 authorization flow

For detailed testing instructions, see [TESTING_GUIDE.md](TESTING_GUIDE.md).
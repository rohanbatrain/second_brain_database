# OAuth2 Test Flask Application

A minimal Flask application designed to test OAuth2 integration with the Second Brain Database in production-like scenarios.

## Purpose

This example is specifically designed for:
- Testing OAuth2 flows in development and staging environments
- Validating OAuth2 provider implementation
- Demonstrating minimal OAuth2 integration patterns
- Quick setup for OAuth2 testing scenarios

## Features

- Complete OAuth2 authorization code flow with PKCE
- Minimal Flask setup with essential OAuth2 functionality
- Environment-based configuration
- Token validation and API testing endpoints
- Error handling and debugging support
- Docker support for containerized testing

## Quick Start

### Step 1: Get OAuth2 Client Credentials

First, you need to register an OAuth2 client to get your client ID and secret:

```bash
cd docs/examples/oauth2-test-flask
python register_client.py
```

This interactive script will:
1. Connect to your OAuth2 provider
2. Authenticate with your user account
3. Register a new OAuth2 client
4. Generate client ID and secret
5. Create your `.env` configuration file

### Step 2: Setup Application

#### Automated Setup
```bash
./setup.sh
```

#### Manual Setup
1. **Install dependencies**:
```bash
pip install -r requirements.txt
```

2. **Configure environment** (if not done in Step 1):
```bash
cp .env.example .env
# Edit .env with your OAuth2 configuration
```

3. **Run the application**:
```bash
python app.py
```

4. **Test OAuth2 flow**:
   - Navigate to http://localhost:5000
   - Click "Login with OAuth2"
   - Complete the authorization flow
   - Test API endpoints

### Command Line Testing
```bash
# Test PKCE generation
python test_flow.py pkce

# Test complete OAuth2 flow (interactive)
python test_flow.py
```

## Configuration

### Option 1: Automatic Configuration (Recommended)

Use the client registration script to automatically create your `.env` file:

```bash
python register_client.py
```

### Option 2: Manual Configuration

Create a `.env` file manually:

```env
# OAuth2 Provider Configuration
OAUTH2_CLIENT_ID=your_client_id_here
OAUTH2_CLIENT_SECRET=your_client_secret_here
OAUTH2_REDIRECT_URI=http://localhost:5000/callback
OAUTH2_BASE_URL=http://localhost:8000

# Flask Configuration
SECRET_KEY=your_flask_secret_key_here
FLASK_ENV=development
PORT=5000
```

### Getting Client Credentials

To get your `OAUTH2_CLIENT_ID` and `OAUTH2_CLIENT_SECRET`, you need to register an OAuth2 client with your Second Brain Database instance:

1. **Using the registration script** (easiest):
   ```bash
   python register_client.py
   ```

2. **Using curl** (manual):
   ```bash
   # First, get an access token by logging in
   curl -X POST "http://localhost:8000/auth/login" \
     -H "Content-Type: application/json" \
     -d '{"username": "your_username", "password": "your_password"}'
   
   # Then register a client
   curl -X POST "http://localhost:8000/oauth2/clients" \
     -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "OAuth2 Test Flask App",
       "description": "Test application for OAuth2 integration",
       "redirect_uris": ["http://localhost:5000/callback"],
       "client_type": "confidential",
       "scopes": ["read:profile", "write:data"]
     }'
   ```

3. **Using the web interface** (if available):
   - Log into your Second Brain Database
   - Navigate to OAuth2 client management
   - Create a new client application

## Project Structure

```
oauth2-test-flask/
├── app.py                 # Main Flask application
├── oauth2_client.py       # OAuth2 client implementation
├── requirements.txt       # Python dependencies
├── .env.example          # Environment template
├── templates/            # HTML templates
│   ├── index.html        # Home page
│   ├── profile.html      # User profile
│   └── error.html        # Error page
├── static/              # Static assets
│   └── style.css        # Basic styling
├── Dockerfile           # Docker configuration
└── README.md           # This file
```

## API Endpoints

- `GET /` - Home page
- `GET /login` - Initiate OAuth2 flow
- `GET /callback` - OAuth2 callback handler
- `GET /profile` - User profile (requires authentication)
- `GET /api/test` - Test API endpoint
- `GET /logout` - Logout and clear session
- `GET /health` - Health check endpoint

## Testing Scenarios

### 1. Authorization Code Flow
```bash
curl -X GET "http://localhost:5000/login"
# Follow redirect to OAuth2 provider
# Complete authorization
# Verify callback handling
```

### 2. Token Validation
```bash
curl -X GET "http://localhost:5000/profile" \
  -H "Cookie: session=your_session_cookie"
```

### 3. API Integration
```bash
curl -X GET "http://localhost:5000/api/test" \
  -H "Cookie: session=your_session_cookie"
```

## Docker Usage

```bash
# Build image
docker build -t oauth2-test-flask .

# Run container
docker run -p 5000:5000 --env-file .env oauth2-test-flask
```

## Troubleshooting

### Common Issues

1. **"Invalid redirect URI" error**
   - Ensure OAUTH2_REDIRECT_URI matches registered client
   - Check for trailing slashes or protocol mismatches

2. **Token validation failures**
   - Verify OAUTH2_BASE_URL is correct
   - Check network connectivity to OAuth2 provider

3. **PKCE validation errors**
   - Ensure code verifier is properly generated and stored
   - Check PKCE implementation in oauth2_client.py

### Debug Mode

Enable debug logging:
```bash
export FLASK_ENV=development
export FLASK_DEBUG=1
python app.py
```

## Integration with Second Brain Database

This test app is designed to work with the Second Brain Database OAuth2 provider. Ensure your OAuth2 client is registered with the following configuration:

- **Client Type**: Confidential
- **Redirect URI**: `http://localhost:5000/callback`
- **Scopes**: `read:profile`, `write:data`
- **Grant Types**: `authorization_code`, `refresh_token`

## Security Notes

- This is a test application - do not use in production without proper security hardening
- Use HTTPS in production environments
- Implement proper session management for production use
- Add CSRF protection for production deployments
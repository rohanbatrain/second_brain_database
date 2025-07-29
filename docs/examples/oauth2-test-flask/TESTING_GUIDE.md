# OAuth2 Test Flask App - Testing Guide

This guide provides comprehensive instructions for testing OAuth2 integration using the Flask test application.

## Overview

The OAuth2 Test Flask App is designed to validate OAuth2 provider implementations by testing all aspects of the OAuth2 Authorization Code flow with PKCE. It provides both web-based and command-line testing capabilities.

## Prerequisites

1. **OAuth2 Provider Running**: Ensure your Second Brain Database OAuth2 provider is running and accessible
2. **User Account**: You need a user account in the Second Brain Database to register OAuth2 clients
3. **OAuth2 Client Registration**: You'll need to register an OAuth2 client (see setup instructions below)

## Setup

### Step 1: Register OAuth2 Client
```bash
cd docs/examples/oauth2-test-flask
python register_client.py
```

This will:
- Connect to your OAuth2 provider
- Authenticate with your credentials
- Register a new OAuth2 client
- Generate client ID and secret
- Create your `.env` configuration file

### Step 2: Setup Application

#### Quick Setup
```bash
./setup.sh
```

#### Manual Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
python test_oauth2.py
```

## Configuration

Edit `.env` file with your OAuth2 provider details:

```env
# OAuth2 Provider Configuration
OAUTH2_CLIENT_ID=oauth2_client_1234567890abcdef
OAUTH2_CLIENT_SECRET=cs_1234567890abcdef1234567890abcdef
OAUTH2_REDIRECT_URI=http://localhost:5000/callback
OAUTH2_BASE_URL=http://localhost:8000

# Flask Configuration
SECRET_KEY=your-secure-secret-key-here
FLASK_ENV=development
PORT=5000
```

## Testing Methods

### 1. Web-Based Testing

Start the Flask application:
```bash
python app.py
```

Navigate to `http://localhost:5000` and follow these steps:

1. **Home Page**: Review application status and configuration
2. **Login**: Click "Login with OAuth2" to start authorization flow
3. **Authorization**: Complete OAuth2 consent on provider
4. **Profile**: View user profile and token information
5. **API Testing**: Test various API endpoints with your token
6. **Token Management**: Test token refresh and revocation

### 2. Command-Line Testing

#### Test Complete OAuth2 Flow
```bash
python test_flow.py
```

This interactive script will:
1. Generate authorization URL with PKCE
2. Prompt you to complete authorization in browser
3. Exchange authorization code for tokens
4. Test API requests with access token
5. Test token refresh (if available)
6. Test token revocation

#### Test PKCE Generation
```bash
python test_flow.py pkce
```

#### Run Unit Tests
```bash
python test_oauth2.py
```

### 3. Docker Testing

```bash
# Build and run with Docker Compose
docker-compose up --build

# Or build and run manually
docker build -t oauth2-test-flask .
docker run -p 5000:5000 --env-file .env oauth2-test-flask
```

## Test Scenarios

### Basic OAuth2 Flow
1. **Authorization Request**: Verify PKCE parameters are generated correctly
2. **User Consent**: Test consent approval and denial scenarios
3. **Token Exchange**: Validate authorization code exchange with PKCE verification
4. **API Access**: Test authenticated API requests
5. **Token Refresh**: Validate refresh token functionality
6. **Token Revocation**: Test token cleanup on logout

### Error Scenarios
1. **Invalid Client**: Test with incorrect client credentials
2. **Invalid Redirect URI**: Test with mismatched redirect URI
3. **State Mismatch**: Test CSRF protection with invalid state parameter
4. **Expired Code**: Test with expired authorization code
5. **Invalid PKCE**: Test with incorrect code verifier
6. **Expired Token**: Test API requests with expired access token

### Security Testing
1. **PKCE Validation**: Ensure code challenge/verifier validation works
2. **State Parameter**: Verify CSRF protection is enforced
3. **Token Encryption**: Validate tokens are properly secured
4. **Scope Validation**: Test scope-based access control

## API Endpoints

The test app provides these endpoints for testing:

- `GET /` - Home page with authentication status
- `GET /login` - Initiate OAuth2 authorization flow
- `GET /callback` - OAuth2 callback handler
- `GET /profile` - User profile (requires authentication)
- `GET /api/test` - Test API endpoints with current token
- `GET /refresh` - Manually refresh access token
- `GET /logout` - Logout and revoke tokens
- `GET /health` - Application health check

## Validation Checklist

Use this checklist to validate your OAuth2 implementation:

### Authorization Flow
- [ ] Authorization URL generation includes all required parameters
- [ ] PKCE code challenge is properly generated (S256 method)
- [ ] State parameter is included for CSRF protection
- [ ] Redirect URI validation works correctly
- [ ] Scope parameter is properly formatted

### Token Exchange
- [ ] Authorization code exchange succeeds with valid parameters
- [ ] PKCE code verifier validation works
- [ ] Access token is returned in correct format
- [ ] Refresh token is provided (if applicable)
- [ ] Token expiration is properly set

### API Integration
- [ ] Access token works with protected API endpoints
- [ ] Bearer token authentication is properly implemented
- [ ] Scope-based authorization works correctly
- [ ] Token validation handles expired tokens

### Token Management
- [ ] Token refresh works with valid refresh token
- [ ] Token revocation properly invalidates tokens
- [ ] Expired tokens are handled gracefully
- [ ] Token cleanup works on logout

### Security Features
- [ ] PKCE prevents authorization code interception
- [ ] State parameter prevents CSRF attacks
- [ ] Tokens are properly encrypted at rest
- [ ] Rate limiting is enforced on OAuth2 endpoints

## Troubleshooting

### Common Issues

1. **"Invalid redirect URI" error**
   - Ensure redirect URI exactly matches registered client
   - Check for protocol differences (http vs https)
   - Verify no trailing slashes or extra parameters

2. **Token exchange failures**
   - Verify authorization code is not expired
   - Check PKCE code verifier matches challenge
   - Ensure client credentials are correct

3. **API request failures**
   - Verify access token is not expired
   - Check token format and Bearer prefix
   - Ensure required scopes are granted

4. **PKCE validation errors**
   - Verify code verifier is properly generated
   - Check SHA256 hashing and base64url encoding
   - Ensure code challenge method is S256

### Debug Mode

Enable debug logging:
```bash
export FLASK_DEBUG=1
export FLASK_ENV=development
python app.py
```

### Health Checks

Check application health:
```bash
curl http://localhost:5000/health
```

Check OAuth2 provider health:
```bash
curl http://localhost:8000/oauth2/health
```

## Performance Testing

### Load Testing
```bash
# Install Apache Bench
sudo apt-get install apache2-utils

# Test authorization endpoint
ab -n 100 -c 10 http://localhost:5000/login

# Test health endpoint
ab -n 1000 -c 50 http://localhost:5000/health
```

### Token Validation Performance
```bash
# Test API endpoint with valid token
ab -n 500 -c 25 -H "Cookie: session=your_session_cookie" http://localhost:5000/api/test
```

## Integration with CI/CD

### GitHub Actions Example
```yaml
name: OAuth2 Integration Test

on: [push, pull_request]

jobs:
  oauth2-test:
    runs-on: ubuntu-latest
    
    services:
      oauth2-provider:
        image: your-oauth2-provider:latest
        ports:
          - 8000:8000
        env:
          MONGODB_URL: mongodb://localhost:27017/test
          REDIS_URL: redis://localhost:6379
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: 3.11
    
    - name: Install dependencies
      run: |
        cd docs/examples/oauth2-test-flask
        pip install -r requirements.txt
    
    - name: Run tests
      run: |
        cd docs/examples/oauth2-test-flask
        python test_oauth2.py
      env:
        OAUTH2_CLIENT_ID: ${{ secrets.OAUTH2_CLIENT_ID }}
        OAUTH2_CLIENT_SECRET: ${{ secrets.OAUTH2_CLIENT_SECRET }}
        OAUTH2_BASE_URL: http://localhost:8000
```

## Reporting Issues

When reporting OAuth2 integration issues, include:

1. **Configuration**: Sanitized .env configuration
2. **Logs**: Application logs with debug enabled
3. **Request/Response**: HTTP request/response details
4. **Environment**: Python version, OS, dependencies
5. **Steps**: Exact steps to reproduce the issue

## Best Practices

1. **Security**: Never commit real client secrets to version control
2. **Testing**: Test both success and failure scenarios
3. **Monitoring**: Monitor token usage and expiration patterns
4. **Documentation**: Keep OAuth2 client registration details updated
5. **Validation**: Regularly validate OAuth2 flow with this test app
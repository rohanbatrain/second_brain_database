# Python Flask OAuth2 Integration Example

This example demonstrates how to integrate a Python Flask web application with the Second Brain Database OAuth2 provider.

## Features

- Complete OAuth2 authorization code flow with PKCE
- Flask web server with secure session management
- Automatic token refresh and rotation
- Secure token storage using Flask sessions
- Comprehensive error handling
- API integration examples
- User profile management
- Token revocation and logout

## Prerequisites

- Python 3.8+ and pip
- Registered OAuth2 client in Second Brain Database
- HTTPS setup for production (required for OAuth2)

## Installation

1. Clone or download this example
2. Create a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Configure your environment (see Configuration section)
5. Start the development server:

```bash
python app.py
```

## Configuration

Create a `.env` file in the project root:

```env
# OAuth2 Configuration
OAUTH2_CLIENT_ID=your_client_id_here
OAUTH2_CLIENT_SECRET=your_client_secret_here
OAUTH2_REDIRECT_URI=http://localhost:5000/auth/callback
OAUTH2_AUTHORIZATION_URL=https://your-sbd-instance.com/oauth2/authorize
OAUTH2_TOKEN_URL=https://your-sbd-instance.com/oauth2/token
OAUTH2_API_BASE_URL=https://your-sbd-instance.com

# Application Configuration
SECRET_KEY=your_flask_secret_key_here
PORT=5000
FLASK_ENV=development

# Security Configuration
SESSION_COOKIE_SECURE=False  # Set to True in production with HTTPS
SESSION_COOKIE_HTTPONLY=True
SESSION_COOKIE_SAMESITE=Lax
```

## Project Structure

```
web-app-python/
├── requirements.txt
├── .env.example
├── README.md
├── app.py                    # Main Flask application
├── config.py                 # Configuration management
├── oauth2/
│   ├── __init__.py
│   ├── client.py            # OAuth2 client implementation
│   ├── pkce.py              # PKCE helper functions
│   └── token_manager.py     # Token management
├── routes/
│   ├── __init__.py
│   ├── auth.py              # Authentication routes
│   ├── api.py               # API integration examples
│   └── main.py              # Main application routes
├── templates/
│   ├── base.html            # Base template
│   ├── index.html           # Home page
│   ├── login.html           # Login page
│   ├── profile.html         # User profile page
│   └── error.html           # Error page
└── static/
    ├── css/
    │   └── style.css        # Basic styling
    └── js/
        └── app.js           # Client-side JavaScript
```

## Usage

1. **Start the application**:
   ```bash
   python app.py
   ```

2. **Navigate to the application**:
   Open http://localhost:5000 in your browser

3. **Login with OAuth2**:
   - Click "Login with Second Brain Database"
   - You'll be redirected to the OAuth2 provider
   - Grant consent for the requested permissions
   - You'll be redirected back to the application

4. **Use the API**:
   - View your profile information
   - Access protected resources
   - See token information and expiration

## Code Examples

### OAuth2 Client Implementation

The OAuth2 client is implemented in `oauth2/client.py`:

```python
import secrets
import hashlib
import base64
import requests
from urllib.parse import urlencode, urlparse, parse_qs
from typing import Dict, Optional, Tuple

class OAuth2Client:
    """OAuth2 client for Second Brain Database integration."""
    
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str,
                 authorization_url: str, token_url: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.authorization_url = authorization_url
        self.token_url = token_url
    
    def generate_pkce_pair(self) -> Tuple[str, str]:
        """Generate PKCE code verifier and challenge."""
        # Generate code verifier (43-128 characters)
        code_verifier = base64.urlsafe_b64encode(
            secrets.token_bytes(32)
        ).decode('utf-8').rstrip('=')
        
        # Generate code challenge (SHA256 hash)
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode('utf-8')).digest()
        ).decode('utf-8').rstrip('=')
        
        return code_verifier, code_challenge
    
    def get_authorization_url(self, scopes: list, state: str = None) -> Tuple[str, str, str]:
        """Generate authorization URL with PKCE parameters."""
        if state is None:
            state = secrets.token_urlsafe(32)
        
        code_verifier, code_challenge = self.generate_pkce_pair()
        
        params = {
            'response_type': 'code',
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'scope': ' '.join(scopes),
            'state': state,
            'code_challenge': code_challenge,
            'code_challenge_method': 'S256'
        }
        
        auth_url = f"{self.authorization_url}?{urlencode(params)}"
        return auth_url, state, code_verifier
    
    def exchange_code_for_tokens(self, code: str, code_verifier: str) -> Dict:
        """Exchange authorization code for access tokens."""
        data = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': self.redirect_uri,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'code_verifier': code_verifier
        }
        
        response = requests.post(
            self.token_url,
            data=data,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            timeout=30
        )
        
        if not response.ok:
            error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
            raise OAuth2Error(
                error_data.get('error', 'token_exchange_failed'),
                error_data.get('error_description', f'HTTP {response.status_code}')
            )
        
        return response.json()
    
    def refresh_access_token(self, refresh_token: str) -> Dict:
        """Refresh access token using refresh token."""
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
            'client_id': self.client_id,
            'client_secret': self.client_secret
        }
        
        response = requests.post(
            self.token_url,
            data=data,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            timeout=30
        )
        
        if not response.ok:
            error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
            raise OAuth2Error(
                error_data.get('error', 'token_refresh_failed'),
                error_data.get('error_description', f'HTTP {response.status_code}')
            )
        
        return response.json()
    
    def revoke_token(self, token: str, token_type_hint: str = None) -> bool:
        """Revoke access or refresh token."""
        data = {
            'token': token,
            'client_id': self.client_id,
            'client_secret': self.client_secret
        }
        
        if token_type_hint:
            data['token_type_hint'] = token_type_hint
        
        response = requests.post(
            f"{self.token_url.replace('/token', '/revoke')}",
            data=data,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            timeout=30
        )
        
        return response.ok

class OAuth2Error(Exception):
    """OAuth2 specific error."""
    
    def __init__(self, error: str, description: str = None):
        self.error = error
        self.description = description
        super().__init__(f"{error}: {description}" if description else error)
```

### Token Management

Token management is handled in `oauth2/token_manager.py`:

```python
import time
from typing import Dict, Optional
from flask import session, current_app
from .client import OAuth2Client, OAuth2Error

class TokenManager:
    """Manages OAuth2 tokens with automatic refresh."""
    
    def __init__(self, oauth2_client: OAuth2Client):
        self.oauth2_client = oauth2_client
    
    def store_tokens(self, tokens: Dict) -> None:
        """Store tokens in Flask session."""
        session['oauth2_tokens'] = {
            'access_token': tokens['access_token'],
            'refresh_token': tokens.get('refresh_token'),
            'expires_at': time.time() + tokens.get('expires_in', 3600),
            'scope': tokens.get('scope', ''),
            'token_type': tokens.get('token_type', 'Bearer')
        }
        session.permanent = True
    
    def get_valid_access_token(self) -> Optional[str]:
        """Get a valid access token, refreshing if necessary."""
        tokens = session.get('oauth2_tokens')
        if not tokens:
            return None
        
        # Check if token expires in the next 5 minutes
        expires_at = tokens.get('expires_at', 0)
        buffer_time = 5 * 60  # 5 minutes
        
        if time.time() + buffer_time >= expires_at:
            # Token is expired or will expire soon
            refresh_token = tokens.get('refresh_token')
            if refresh_token:
                try:
                    new_tokens = self.oauth2_client.refresh_access_token(refresh_token)
                    self.store_tokens(new_tokens)
                    current_app.logger.info("Access token refreshed successfully")
                    return new_tokens['access_token']
                except OAuth2Error as e:
                    current_app.logger.error(f"Token refresh failed: {e}")
                    self.clear_tokens()
                    return None
            else:
                current_app.logger.warning("No refresh token available")
                self.clear_tokens()
                return None
        
        return tokens['access_token']
    
    def clear_tokens(self) -> None:
        """Clear stored tokens."""
        session.pop('oauth2_tokens', None)
    
    def get_token_info(self) -> Optional[Dict]:
        """Get token information for display."""
        tokens = session.get('oauth2_tokens')
        if not tokens:
            return None
        
        return {
            'expires_at': tokens.get('expires_at'),
            'scope': tokens.get('scope', '').split(),
            'token_type': tokens.get('token_type', 'Bearer'),
            'is_expired': time.time() >= tokens.get('expires_at', 0)
        }
    
    def revoke_tokens(self) -> bool:
        """Revoke all stored tokens."""
        tokens = session.get('oauth2_tokens')
        if not tokens:
            return True
        
        success = True
        
        # Revoke refresh token first
        if tokens.get('refresh_token'):
            try:
                self.oauth2_client.revoke_token(
                    tokens['refresh_token'], 
                    'refresh_token'
                )
            except Exception as e:
                current_app.logger.error(f"Failed to revoke refresh token: {e}")
                success = False
        
        # Revoke access token
        if tokens.get('access_token'):
            try:
                self.oauth2_client.revoke_token(
                    tokens['access_token'], 
                    'access_token'
                )
            except Exception as e:
                current_app.logger.error(f"Failed to revoke access token: {e}")
                success = False
        
        # Clear tokens from session regardless
        self.clear_tokens()
        return success
```

### Authentication Routes

Authentication routes are implemented in `routes/auth.py`:

```python
from flask import Blueprint, request, redirect, url_for, session, flash, current_app
from oauth2.client import OAuth2Client, OAuth2Error
from oauth2.token_manager import TokenManager

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

def get_oauth2_client():
    """Get configured OAuth2 client."""
    return OAuth2Client(
        client_id=current_app.config['OAUTH2_CLIENT_ID'],
        client_secret=current_app.config['OAUTH2_CLIENT_SECRET'],
        redirect_uri=current_app.config['OAUTH2_REDIRECT_URI'],
        authorization_url=current_app.config['OAUTH2_AUTHORIZATION_URL'],
        token_url=current_app.config['OAUTH2_TOKEN_URL']
    )

@auth_bp.route('/login')
def login():
    """Initiate OAuth2 authorization flow."""
    try:
        oauth2_client = get_oauth2_client()
        
        # Generate authorization URL with PKCE
        scopes = ['read:profile', 'write:data']
        auth_url, state, code_verifier = oauth2_client.get_authorization_url(scopes)
        
        # Store PKCE parameters in session
        session['oauth2_state'] = state
        session['oauth2_code_verifier'] = code_verifier
        
        current_app.logger.info(f"Initiating OAuth2 login for state: {state}")
        return redirect(auth_url)
        
    except Exception as e:
        current_app.logger.error(f"OAuth2 login error: {e}")
        flash('Failed to initiate login. Please try again.', 'error')
        return redirect(url_for('main.index'))

@auth_bp.route('/callback')
def callback():
    """Handle OAuth2 authorization callback."""
    try:
        # Check for authorization errors
        error = request.args.get('error')
        if error:
            error_description = request.args.get('error_description', 'Unknown error')
            current_app.logger.error(f"OAuth2 authorization error: {error} - {error_description}")
            
            if error == 'access_denied':
                flash('Authorization was denied. Please try again if you want to use the application.', 'warning')
            else:
                flash(f'Authorization failed: {error_description}', 'error')
            
            return redirect(url_for('main.index'))
        
        # Get authorization code and state
        code = request.args.get('code')
        state = request.args.get('state')
        
        if not code or not state:
            flash('Invalid authorization response.', 'error')
            return redirect(url_for('main.index'))
        
        # Validate state parameter (CSRF protection)
        stored_state = session.pop('oauth2_state', None)
        if not stored_state or state != stored_state:
            current_app.logger.error(f"State mismatch: expected {stored_state}, got {state}")
            flash('Invalid state parameter. Please try again.', 'error')
            return redirect(url_for('main.index'))
        
        # Get code verifier
        code_verifier = session.pop('oauth2_code_verifier', None)
        if not code_verifier:
            flash('Missing PKCE code verifier. Please try again.', 'error')
            return redirect(url_for('main.index'))
        
        # Exchange code for tokens
        oauth2_client = get_oauth2_client()
        tokens = oauth2_client.exchange_code_for_tokens(code, code_verifier)
        
        # Store tokens
        token_manager = TokenManager(oauth2_client)
        token_manager.store_tokens(tokens)
        
        current_app.logger.info("OAuth2 authorization completed successfully")
        flash('Login successful!', 'success')
        return redirect(url_for('main.profile'))
        
    except OAuth2Error as e:
        current_app.logger.error(f"OAuth2 callback error: {e}")
        flash(f'Authentication failed: {e.description}', 'error')
        return redirect(url_for('main.index'))
    except Exception as e:
        current_app.logger.error(f"Unexpected callback error: {e}")
        flash('An unexpected error occurred. Please try again.', 'error')
        return redirect(url_for('main.index'))

@auth_bp.route('/logout')
def logout():
    """Logout user and revoke tokens."""
    try:
        oauth2_client = get_oauth2_client()
        token_manager = TokenManager(oauth2_client)
        
        # Revoke tokens
        if token_manager.revoke_tokens():
            current_app.logger.info("Tokens revoked successfully")
            flash('Logged out successfully.', 'success')
        else:
            current_app.logger.warning("Token revocation failed")
            flash('Logged out (token revocation failed).', 'warning')
        
    except Exception as e:
        current_app.logger.error(f"Logout error: {e}")
        flash('Logged out (with errors).', 'warning')
    
    # Clear session
    session.clear()
    return redirect(url_for('main.index'))

@auth_bp.route('/refresh')
def refresh():
    """Manually refresh access token."""
    try:
        oauth2_client = get_oauth2_client()
        token_manager = TokenManager(oauth2_client)
        
        access_token = token_manager.get_valid_access_token()
        if access_token:
            flash('Token refreshed successfully.', 'success')
        else:
            flash('Token refresh failed. Please login again.', 'error')
            return redirect(url_for('auth.login'))
        
    except Exception as e:
        current_app.logger.error(f"Token refresh error: {e}")
        flash('Token refresh failed. Please login again.', 'error')
        return redirect(url_for('auth.login'))
    
    return redirect(url_for('main.profile'))
```

### API Integration

API integration examples are in `routes/api.py`:

```python
import requests
from flask import Blueprint, jsonify, request, current_app
from oauth2.client import OAuth2Client
from oauth2.token_manager import TokenManager
from functools import wraps

api_bp = Blueprint('api', __name__, url_prefix='/api')

def require_oauth2_token(f):
    """Decorator to require valid OAuth2 token."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        oauth2_client = OAuth2Client(
            client_id=current_app.config['OAUTH2_CLIENT_ID'],
            client_secret=current_app.config['OAUTH2_CLIENT_SECRET'],
            redirect_uri=current_app.config['OAUTH2_REDIRECT_URI'],
            authorization_url=current_app.config['OAUTH2_AUTHORIZATION_URL'],
            token_url=current_app.config['OAUTH2_TOKEN_URL']
        )
        
        token_manager = TokenManager(oauth2_client)
        access_token = token_manager.get_valid_access_token()
        
        if not access_token:
            return jsonify({'error': 'Authentication required'}), 401
        
        # Add token to request context
        request.oauth2_token = access_token
        return f(*args, **kwargs)
    
    return decorated_function

def require_scope(required_scope):
    """Decorator to require specific OAuth2 scope."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            oauth2_client = OAuth2Client(
                client_id=current_app.config['OAUTH2_CLIENT_ID'],
                client_secret=current_app.config['OAUTH2_CLIENT_SECRET'],
                redirect_uri=current_app.config['OAUTH2_REDIRECT_URI'],
                authorization_url=current_app.config['OAUTH2_AUTHORIZATION_URL'],
                token_url=current_app.config['OAUTH2_TOKEN_URL']
            )
            
            token_manager = TokenManager(oauth2_client)
            token_info = token_manager.get_token_info()
            
            if not token_info or required_scope not in token_info.get('scope', []):
                return jsonify({'error': f'Insufficient permissions. Required scope: {required_scope}'}), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@api_bp.route('/profile')
@require_oauth2_token
def get_profile():
    """Get user profile information."""
    try:
        response = requests.get(
            f"{current_app.config['OAUTH2_API_BASE_URL']}/api/user/profile",
            headers={
                'Authorization': f'Bearer {request.oauth2_token}',
                'Content-Type': 'application/json'
            },
            timeout=30
        )
        
        if response.ok:
            return jsonify(response.json())
        else:
            return jsonify({'error': 'Failed to fetch profile'}), response.status_code
            
    except requests.RequestException as e:
        current_app.logger.error(f"Profile API error: {e}")
        return jsonify({'error': 'API request failed'}), 500

@api_bp.route('/data', methods=['GET'])
@require_oauth2_token
@require_scope('read:data')
def get_data():
    """Get user data (requires read:data scope)."""
    try:
        response = requests.get(
            f"{current_app.config['OAUTH2_API_BASE_URL']}/api/user/data",
            headers={
                'Authorization': f'Bearer {request.oauth2_token}',
                'Content-Type': 'application/json'
            },
            timeout=30
        )
        
        if response.ok:
            return jsonify(response.json())
        else:
            return jsonify({'error': 'Failed to fetch data'}), response.status_code
            
    except requests.RequestException as e:
        current_app.logger.error(f"Data API error: {e}")
        return jsonify({'error': 'API request failed'}), 500

@api_bp.route('/data', methods=['POST'])
@require_oauth2_token
@require_scope('write:data')
def update_data():
    """Update user data (requires write:data scope)."""
    try:
        response = requests.post(
            f"{current_app.config['OAUTH2_API_BASE_URL']}/api/user/data",
            headers={
                'Authorization': f'Bearer {request.oauth2_token}',
                'Content-Type': 'application/json'
            },
            json=request.json,
            timeout=30
        )
        
        if response.ok:
            return jsonify(response.json())
        else:
            return jsonify({'error': 'Failed to update data'}), response.status_code
            
    except requests.RequestException as e:
        current_app.logger.error(f"Data update API error: {e}")
        return jsonify({'error': 'API request failed'}), 500
```

## Security Features

### PKCE Implementation

```python
import secrets
import hashlib
import base64

def generate_pkce_pair():
    """Generate PKCE code verifier and challenge."""
    # Generate code verifier (43-128 characters, URL-safe)
    code_verifier = base64.urlsafe_b64encode(
        secrets.token_bytes(32)
    ).decode('utf-8').rstrip('=')
    
    # Generate code challenge (SHA256 hash, base64url encoded)
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode('utf-8')).digest()
    ).decode('utf-8').rstrip('=')
    
    return code_verifier, code_challenge
```

### Secure Session Configuration

```python
from datetime import timedelta

# Flask configuration
app.config.update(
    SECRET_KEY=os.environ['SECRET_KEY'],
    SESSION_COOKIE_SECURE=os.environ.get('SESSION_COOKIE_SECURE', 'False').lower() == 'true',
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(hours=24)
)
```

## Error Handling

```python
from flask import Flask, render_template
import logging

def create_app():
    app = Flask(__name__)
    
    # Configure logging
    if not app.debug:
        logging.basicConfig(level=logging.INFO)
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        app.logger.addHandler(handler)
        app.logger.setLevel(logging.INFO)
    
    # Error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('error.html', 
                             title='Page Not Found',
                             message='The requested page was not found.'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f'Server Error: {error}')
        return render_template('error.html',
                             title='Internal Server Error',
                             message='An internal error occurred.'), 500
    
    return app
```

## Testing

Create `test_oauth2.py`:

```python
import unittest
from unittest.mock import patch, MagicMock
from app import create_app
from oauth2.client import OAuth2Client, OAuth2Error

class OAuth2TestCase(unittest.TestCase):
    
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
    
    def tearDown(self):
        self.app_context.pop()
    
    def test_login_redirect(self):
        """Test OAuth2 login initiation."""
        response = self.client.get('/auth/login')
        self.assertEqual(response.status_code, 302)
        self.assertIn('oauth2/authorize', response.location)
    
    @patch('oauth2.client.requests.post')
    def test_token_exchange(self, mock_post):
        """Test authorization code exchange."""
        # Mock successful token response
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {
            'access_token': 'test_access_token',
            'refresh_token': 'test_refresh_token',
            'expires_in': 3600,
            'scope': 'read:profile'
        }
        mock_post.return_value = mock_response
        
        oauth2_client = OAuth2Client(
            client_id='test_client',
            client_secret='test_secret',
            redirect_uri='http://localhost:5000/auth/callback',
            authorization_url='https://example.com/oauth2/authorize',
            token_url='https://example.com/oauth2/token'
        )
        
        tokens = oauth2_client.exchange_code_for_tokens('test_code', 'test_verifier')
        
        self.assertEqual(tokens['access_token'], 'test_access_token')
        self.assertEqual(tokens['refresh_token'], 'test_refresh_token')
    
    def test_pkce_generation(self):
        """Test PKCE parameter generation."""
        oauth2_client = OAuth2Client(
            client_id='test_client',
            client_secret='test_secret',
            redirect_uri='http://localhost:5000/auth/callback',
            authorization_url='https://example.com/oauth2/authorize',
            token_url='https://example.com/oauth2/token'
        )
        
        verifier, challenge = oauth2_client.generate_pkce_pair()
        
        self.assertIsInstance(verifier, str)
        self.assertIsInstance(challenge, str)
        self.assertGreaterEqual(len(verifier), 43)
        self.assertLessEqual(len(verifier), 128)

if __name__ == '__main__':
    unittest.main()
```

Run tests:

```bash
python -m pytest test_oauth2.py -v
```

## Production Deployment

### Environment Variables

```env
FLASK_ENV=production
OAUTH2_CLIENT_ID=your_production_client_id
OAUTH2_CLIENT_SECRET=your_production_client_secret
OAUTH2_REDIRECT_URI=https://yourdomain.com/auth/callback
OAUTH2_AUTHORIZATION_URL=https://sbd-instance.com/oauth2/authorize
OAUTH2_TOKEN_URL=https://sbd-instance.com/oauth2/token
OAUTH2_API_BASE_URL=https://sbd-instance.com
SECRET_KEY=your_strong_secret_key
SESSION_COOKIE_SECURE=True
```

### WSGI Configuration

Create `wsgi.py`:

```python
from app import create_app

application = create_app()

if __name__ == "__main__":
    application.run()
```

### Docker Deployment

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "wsgi:application"]
```

## Troubleshooting

### Common Issues

1. **"Invalid redirect URI" error**
   - Ensure the redirect URI matches exactly what's registered
   - Check for protocol differences (http vs https)

2. **Token refresh failures**
   - Verify refresh token is being stored correctly
   - Check token endpoint URL configuration

3. **PKCE validation errors**
   - Ensure code verifier is properly generated and stored
   - Verify SHA256 hashing and base64url encoding

### Debug Mode

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Support

For additional help:
- Check the [OAuth2 Integration Guide](../../OAUTH2_INTEGRATION.md)
- Review the [API Reference](../../OAUTH2_API_REFERENCE.md)
- See other examples in the [examples directory](../)
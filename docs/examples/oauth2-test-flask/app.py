"""
Minimal Flask application for testing OAuth2 integration with Second Brain Database.
"""
import os
import time
from flask import Flask, request, redirect, url_for, session, render_template, jsonify, flash
from dotenv import load_dotenv
from oauth2_client import OAuth2Client, OAuth2Error

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

# OAuth2 configuration
OAUTH2_CONFIG = {
    'client_id': os.getenv('OAUTH2_CLIENT_ID'),
    'client_secret': os.getenv('OAUTH2_CLIENT_SECRET'),
    'redirect_uri': os.getenv('OAUTH2_REDIRECT_URI', 'http://localhost:5000/callback'),
    'base_url': os.getenv('OAUTH2_BASE_URL', 'http://localhost:8000')
}

# Validate configuration
missing_config = [key for key, value in OAUTH2_CONFIG.items() if not value]
if missing_config:
    raise ValueError(f"Missing OAuth2 configuration: {', '.join(missing_config)}")

oauth2_client = OAuth2Client(**OAUTH2_CONFIG)


@app.route('/')
def index():
    """Home page."""
    user_info = session.get('user_info')
    token_info = session.get('token_info')
    
    return render_template('index.html', 
                         user_info=user_info, 
                         token_info=token_info,
                         is_authenticated=bool(user_info))


@app.route('/login')
def login():
    """Initiate OAuth2 authorization flow."""
    try:
        auth_url, state, code_verifier = oauth2_client.get_authorization_url()
        
        # Store PKCE parameters in session
        session['oauth2_state'] = state
        session['oauth2_code_verifier'] = code_verifier
        
        app.logger.info(f"Initiating OAuth2 login - State: {state}")
        return redirect(auth_url)
        
    except Exception as e:
        app.logger.error(f"OAuth2 login error: {e}")
        flash(f'Failed to initiate login: {str(e)}', 'error')
        return redirect(url_for('index'))


@app.route('/callback')
def callback():
    """Handle OAuth2 authorization callback."""
    try:
        # Check for authorization errors
        error = request.args.get('error')
        if error:
            error_description = request.args.get('error_description', 'Unknown error')
            app.logger.error(f"OAuth2 authorization error: {error} - {error_description}")
            
            if error == 'access_denied':
                flash('Authorization was denied.', 'warning')
            else:
                flash(f'Authorization failed: {error_description}', 'error')
            
            return redirect(url_for('index'))
        
        # Get authorization code and state
        code = request.args.get('code')
        state = request.args.get('state')
        
        if not code or not state:
            flash('Invalid authorization response.', 'error')
            return redirect(url_for('index'))
        
        # Validate state parameter (CSRF protection)
        stored_state = session.pop('oauth2_state', None)
        if not stored_state or state != stored_state:
            app.logger.error(f"State mismatch: expected {stored_state}, got {state}")
            flash('Invalid state parameter. Please try again.', 'error')
            return redirect(url_for('index'))
        
        # Get code verifier
        code_verifier = session.pop('oauth2_code_verifier', None)
        if not code_verifier:
            flash('Missing PKCE code verifier. Please try again.', 'error')
            return redirect(url_for('index'))
        
        # Exchange code for tokens
        tokens = oauth2_client.exchange_code_for_tokens(code, code_verifier)
        
        # Store tokens in session
        session['tokens'] = {
            'access_token': tokens['access_token'],
            'refresh_token': tokens.get('refresh_token'),
            'expires_at': time.time() + tokens.get('expires_in', 3600),
            'scope': tokens.get('scope', ''),
            'token_type': tokens.get('token_type', 'Bearer')
        }
        
        # Store token info for display
        session['token_info'] = {
            'expires_at': session['tokens']['expires_at'],
            'scope': tokens.get('scope', '').split(),
            'token_type': tokens.get('token_type', 'Bearer'),
            'expires_in': tokens.get('expires_in', 3600)
        }
        
        # Try to fetch user profile
        try:
            profile_data = oauth2_client.make_api_request(
                'user/profile', 
                tokens['access_token']
            )
            session['user_info'] = profile_data
        except OAuth2Error as e:
            app.logger.warning(f"Failed to fetch user profile: {e}")
            session['user_info'] = {'error': str(e)}
        
        app.logger.info("OAuth2 authorization completed successfully")
        flash('Login successful!', 'success')
        return redirect(url_for('profile'))
        
    except OAuth2Error as e:
        app.logger.error(f"OAuth2 callback error: {e}")
        flash(f'Authentication failed: {e.description}', 'error')
        return redirect(url_for('index'))
    except Exception as e:
        app.logger.error(f"Unexpected callback error: {e}")
        flash('An unexpected error occurred. Please try again.', 'error')
        return redirect(url_for('index'))


@app.route('/profile')
def profile():
    """User profile page (requires authentication)."""
    if 'tokens' not in session:
        flash('Please login first.', 'warning')
        return redirect(url_for('index'))
    
    user_info = session.get('user_info', {})
    token_info = session.get('token_info', {})
    
    # Check if token is expired
    expires_at = session['tokens'].get('expires_at', 0)
    is_expired = time.time() >= expires_at
    
    if is_expired:
        flash('Your session has expired. Please login again.', 'warning')
        return redirect(url_for('logout'))
    
    return render_template('profile.html', 
                         user_info=user_info, 
                         token_info=token_info,
                         is_expired=is_expired)


@app.route('/api/test')
def api_test():
    """Test API endpoint with OAuth2 token."""
    if 'tokens' not in session:
        return jsonify({'error': 'Authentication required'}), 401
    
    access_token = session['tokens']['access_token']
    
    try:
        # Test different API endpoints
        results = {}
        
        # Test profile endpoint
        try:
            profile_data = oauth2_client.make_api_request('user/profile', access_token)
            results['profile'] = {'status': 'success', 'data': profile_data}
        except OAuth2Error as e:
            results['profile'] = {'status': 'error', 'error': str(e)}
        
        # Test health endpoint
        try:
            health_data = oauth2_client.make_api_request('health', access_token)
            results['health'] = {'status': 'success', 'data': health_data}
        except OAuth2Error as e:
            results['health'] = {'status': 'error', 'error': str(e)}
        
        return jsonify({
            'message': 'API test completed',
            'token_info': {
                'expires_at': session['tokens']['expires_at'],
                'is_expired': time.time() >= session['tokens']['expires_at'],
                'scope': session['tokens']['scope']
            },
            'results': results
        })
        
    except Exception as e:
        app.logger.error(f"API test error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/refresh')
def refresh_token():
    """Refresh access token."""
    if 'tokens' not in session or 'refresh_token' not in session['tokens']:
        flash('No refresh token available. Please login again.', 'error')
        return redirect(url_for('index'))
    
    try:
        refresh_token = session['tokens']['refresh_token']
        new_tokens = oauth2_client.refresh_access_token(refresh_token)
        
        # Update stored tokens
        session['tokens'].update({
            'access_token': new_tokens['access_token'],
            'expires_at': time.time() + new_tokens.get('expires_in', 3600),
            'scope': new_tokens.get('scope', session['tokens']['scope'])
        })
        
        # Update refresh token if provided
        if 'refresh_token' in new_tokens:
            session['tokens']['refresh_token'] = new_tokens['refresh_token']
        
        # Update token info for display
        session['token_info'].update({
            'expires_at': session['tokens']['expires_at'],
            'expires_in': new_tokens.get('expires_in', 3600)
        })
        
        flash('Token refreshed successfully!', 'success')
        app.logger.info("Access token refreshed successfully")
        
    except OAuth2Error as e:
        app.logger.error(f"Token refresh failed: {e}")
        flash(f'Token refresh failed: {e.description}', 'error')
        return redirect(url_for('logout'))
    
    return redirect(url_for('profile'))


@app.route('/logout')
def logout():
    """Logout user and revoke tokens."""
    try:
        # Revoke tokens if available
        if 'tokens' in session:
            tokens = session['tokens']
            
            # Revoke refresh token first
            if 'refresh_token' in tokens:
                oauth2_client.revoke_token(tokens['refresh_token'], 'refresh_token')
            
            # Revoke access token
            if 'access_token' in tokens:
                oauth2_client.revoke_token(tokens['access_token'], 'access_token')
        
        app.logger.info("Tokens revoked successfully")
        
    except Exception as e:
        app.logger.error(f"Token revocation error: {e}")
    
    # Clear session
    session.clear()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('index'))


@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'timestamp': time.time(),
        'oauth2_config': {
            'client_id': OAUTH2_CONFIG['client_id'],
            'redirect_uri': OAUTH2_CONFIG['redirect_uri'],
            'base_url': OAUTH2_CONFIG['base_url']
        }
    })


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


if __name__ == '__main__':
    # Configure logging
    import logging
    logging.basicConfig(level=logging.INFO)
    
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', '0') == '1'
    
    app.run(host='0.0.0.0', port=port, debug=debug)
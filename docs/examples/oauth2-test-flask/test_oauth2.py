"""
Basic tests for OAuth2 Test Flask Application.
"""
import unittest
from unittest.mock import patch, MagicMock
import os
import sys

# Add the current directory to the path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from oauth2_client import OAuth2Client, OAuth2Error


class OAuth2TestCase(unittest.TestCase):
    """Test cases for OAuth2 functionality."""
    
    def setUp(self):
        """Set up test client."""
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test-secret-key'
        self.client = app.test_client()
        self.app_context = app.app_context()
        self.app_context.push()
    
    def tearDown(self):
        """Clean up after tests."""
        self.app_context.pop()
    
    def test_index_page(self):
        """Test home page loads correctly."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'OAuth2 Test Application', response.data)
    
    def test_health_endpoint(self):
        """Test health check endpoint."""
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        
        data = response.get_json()
        self.assertEqual(data['status'], 'healthy')
        self.assertIn('oauth2_config', data)
    
    def test_login_redirect(self):
        """Test OAuth2 login initiation."""
        response = self.client.get('/login')
        self.assertEqual(response.status_code, 302)
        
        # Should redirect to OAuth2 authorization endpoint
        location = response.headers.get('Location', '')
        self.assertIn('oauth2/authorize', location)
        self.assertIn('response_type=code', location)
        self.assertIn('code_challenge', location)
    
    def test_callback_missing_code(self):
        """Test callback with missing authorization code."""
        response = self.client.get('/callback')
        self.assertEqual(response.status_code, 302)
        
        # Should redirect to index with error
        self.assertTrue(response.headers.get('Location', '').endswith('/'))
    
    def test_callback_state_mismatch(self):
        """Test callback with state parameter mismatch."""
        with self.client.session_transaction() as sess:
            sess['oauth2_state'] = 'expected_state'
            sess['oauth2_code_verifier'] = 'test_verifier'
        
        response = self.client.get('/callback?code=test_code&state=wrong_state')
        self.assertEqual(response.status_code, 302)
        
        # Should redirect to index with error
        self.assertTrue(response.headers.get('Location', '').endswith('/'))
    
    def test_profile_without_auth(self):
        """Test profile page without authentication."""
        response = self.client.get('/profile')
        self.assertEqual(response.status_code, 302)
        
        # Should redirect to index
        self.assertTrue(response.headers.get('Location', '').endswith('/'))
    
    def test_api_test_without_auth(self):
        """Test API endpoint without authentication."""
        response = self.client.get('/api/test')
        self.assertEqual(response.status_code, 401)
        
        data = response.get_json()
        self.assertEqual(data['error'], 'Authentication required')
    
    def test_logout_without_session(self):
        """Test logout without active session."""
        response = self.client.get('/logout')
        self.assertEqual(response.status_code, 302)
        
        # Should redirect to index
        self.assertTrue(response.headers.get('Location', '').endswith('/'))


class OAuth2ClientTestCase(unittest.TestCase):
    """Test cases for OAuth2Client class."""
    
    def setUp(self):
        """Set up OAuth2 client for testing."""
        self.client = OAuth2Client(
            client_id='test_client_id',
            client_secret='test_client_secret',
            redirect_uri='http://localhost:5000/callback',
            base_url='http://localhost:8000'
        )
    
    def test_pkce_generation(self):
        """Test PKCE code verifier and challenge generation."""
        verifier, challenge = self.client.generate_pkce_pair()
        
        self.assertIsInstance(verifier, str)
        self.assertIsInstance(challenge, str)
        self.assertGreaterEqual(len(verifier), 43)
        self.assertLessEqual(len(verifier), 128)
        self.assertGreaterEqual(len(challenge), 43)
        self.assertLessEqual(len(challenge), 128)
    
    def test_authorization_url_generation(self):
        """Test authorization URL generation."""
        auth_url, state, code_verifier = self.client.get_authorization_url()
        
        self.assertIn('http://localhost:8000/oauth2/authorize', auth_url)
        self.assertIn('response_type=code', auth_url)
        self.assertIn('client_id=test_client_id', auth_url)
        self.assertIn('code_challenge=', auth_url)
        self.assertIn('code_challenge_method=S256', auth_url)
        self.assertIsInstance(state, str)
        self.assertIsInstance(code_verifier, str)
    
    def test_authorization_url_with_custom_scopes(self):
        """Test authorization URL generation with custom scopes."""
        scopes = ['read:profile', 'write:data', 'admin']
        auth_url, state, code_verifier = self.client.get_authorization_url(scopes=scopes)
        
        self.assertIn('scope=read%3Aprofile+write%3Adata+admin', auth_url)
    
    @patch('oauth2_client.requests.post')
    def test_token_exchange_success(self, mock_post):
        """Test successful token exchange."""
        # Mock successful token response
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {
            'access_token': 'test_access_token',
            'refresh_token': 'test_refresh_token',
            'expires_in': 3600,
            'scope': 'read:profile write:data',
            'token_type': 'Bearer'
        }
        mock_post.return_value = mock_response
        
        tokens = self.client.exchange_code_for_tokens('test_code', 'test_verifier')
        
        self.assertEqual(tokens['access_token'], 'test_access_token')
        self.assertEqual(tokens['refresh_token'], 'test_refresh_token')
        self.assertEqual(tokens['expires_in'], 3600)
        
        # Verify the request was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertEqual(call_args[0][0], 'http://localhost:8000/oauth2/token')
        self.assertIn('grant_type', call_args[1]['data'])
        self.assertEqual(call_args[1]['data']['grant_type'], 'authorization_code')
    
    @patch('oauth2_client.requests.post')
    def test_token_exchange_error(self, mock_post):
        """Test token exchange error handling."""
        # Mock error response
        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.status_code = 400
        mock_response.json.return_value = {
            'error': 'invalid_grant',
            'error_description': 'The authorization code is invalid'
        }
        mock_post.return_value = mock_response
        
        with self.assertRaises(OAuth2Error) as context:
            self.client.exchange_code_for_tokens('invalid_code', 'test_verifier')
        
        self.assertEqual(context.exception.error, 'invalid_grant')
        self.assertIn('invalid', context.exception.description)
    
    @patch('oauth2_client.requests.post')
    def test_refresh_token_success(self, mock_post):
        """Test successful token refresh."""
        # Mock successful refresh response
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {
            'access_token': 'new_access_token',
            'expires_in': 3600,
            'scope': 'read:profile write:data',
            'token_type': 'Bearer'
        }
        mock_post.return_value = mock_response
        
        tokens = self.client.refresh_access_token('test_refresh_token')
        
        self.assertEqual(tokens['access_token'], 'new_access_token')
        self.assertEqual(tokens['expires_in'], 3600)
        
        # Verify the request was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertEqual(call_args[1]['data']['grant_type'], 'refresh_token')
        self.assertEqual(call_args[1]['data']['refresh_token'], 'test_refresh_token')
    
    @patch('oauth2_client.requests.post')
    def test_token_revocation(self, mock_post):
        """Test token revocation."""
        # Mock successful revocation response
        mock_response = MagicMock()
        mock_response.ok = True
        mock_post.return_value = mock_response
        
        result = self.client.revoke_token('test_token', 'access_token')
        
        self.assertTrue(result)
        
        # Verify the request was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertEqual(call_args[0][0], 'http://localhost:8000/oauth2/revoke')
        self.assertEqual(call_args[1]['data']['token'], 'test_token')
        self.assertEqual(call_args[1]['data']['token_type_hint'], 'access_token')
    
    @patch('oauth2_client.requests.get')
    def test_api_request_success(self, mock_get):
        """Test successful API request."""
        # Mock successful API response
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {
            'user_id': 'test_user',
            'username': 'testuser',
            'email': 'test@example.com'
        }
        mock_get.return_value = mock_response
        
        result = self.client.make_api_request('user/profile', 'test_access_token')
        
        self.assertEqual(result['user_id'], 'test_user')
        self.assertEqual(result['username'], 'testuser')
        
        # Verify the request was made correctly
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        self.assertEqual(call_args[0][0], 'http://localhost:8000/api/user/profile')
        self.assertEqual(call_args[1]['headers']['Authorization'], 'Bearer test_access_token')


if __name__ == '__main__':
    # Set up environment variables for testing
    os.environ.setdefault('OAUTH2_CLIENT_ID', 'test_client_id')
    os.environ.setdefault('OAUTH2_CLIENT_SECRET', 'test_client_secret')
    os.environ.setdefault('OAUTH2_REDIRECT_URI', 'http://localhost:5000/callback')
    os.environ.setdefault('OAUTH2_BASE_URL', 'http://localhost:8000')
    os.environ.setdefault('SECRET_KEY', 'test-secret-key')
    
    unittest.main()
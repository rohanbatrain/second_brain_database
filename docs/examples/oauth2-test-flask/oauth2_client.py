"""
OAuth2 client implementation for testing Second Brain Database OAuth2 provider.
"""
import secrets
import hashlib
import base64
import requests
from urllib.parse import urlencode
from typing import Dict, Optional, Tuple


class OAuth2Error(Exception):
    """OAuth2 specific error."""
    
    def __init__(self, error: str, description: str = None):
        self.error = error
        self.description = description
        super().__init__(f"{error}: {description}" if description else error)


class OAuth2Client:
    """Minimal OAuth2 client for testing purposes."""
    
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str, base_url: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.base_url = base_url.rstrip('/')
        
        # OAuth2 endpoints
        self.authorization_endpoint = f"{self.base_url}/oauth2/authorize"
        self.token_endpoint = f"{self.base_url}/oauth2/token"
        self.revoke_endpoint = f"{self.base_url}/oauth2/revoke"
        self.api_base = f"{self.base_url}/api"
    
    def generate_pkce_pair(self) -> Tuple[str, str]:
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
    
    def get_authorization_url(self, scopes: list = None, state: str = None) -> Tuple[str, str, str]:
        """Generate authorization URL with PKCE parameters."""
        if state is None:
            state = secrets.token_urlsafe(32)
        
        if scopes is None:
            scopes = ['read:profile', 'write:data']
        
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
        
        auth_url = f"{self.authorization_endpoint}?{urlencode(params)}"
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
        
        try:
            response = requests.post(
                self.token_endpoint,
                data=data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=30
            )
            
            if not response.ok:
                error_data = {}
                try:
                    error_data = response.json()
                except:
                    pass
                
                raise OAuth2Error(
                    error_data.get('error', 'token_exchange_failed'),
                    error_data.get('error_description', f'HTTP {response.status_code}')
                )
            
            return response.json()
            
        except requests.RequestException as e:
            raise OAuth2Error('network_error', str(e))
    
    def refresh_access_token(self, refresh_token: str) -> Dict:
        """Refresh access token using refresh token."""
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
            'client_id': self.client_id,
            'client_secret': self.client_secret
        }
        
        try:
            response = requests.post(
                self.token_endpoint,
                data=data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=30
            )
            
            if not response.ok:
                error_data = {}
                try:
                    error_data = response.json()
                except:
                    pass
                
                raise OAuth2Error(
                    error_data.get('error', 'token_refresh_failed'),
                    error_data.get('error_description', f'HTTP {response.status_code}')
                )
            
            return response.json()
            
        except requests.RequestException as e:
            raise OAuth2Error('network_error', str(e))
    
    def revoke_token(self, token: str, token_type_hint: str = None) -> bool:
        """Revoke access or refresh token."""
        data = {
            'token': token,
            'client_id': self.client_id,
            'client_secret': self.client_secret
        }
        
        if token_type_hint:
            data['token_type_hint'] = token_type_hint
        
        try:
            response = requests.post(
                self.revoke_endpoint,
                data=data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=30
            )
            
            return response.ok
            
        except requests.RequestException:
            return False
    
    def make_api_request(self, endpoint: str, access_token: str, method: str = 'GET', data: dict = None) -> Dict:
        """Make authenticated API request."""
        url = f"{self.api_base}/{endpoint.lstrip('/')}"
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        try:
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers, timeout=30)
            elif method.upper() == 'POST':
                response = requests.post(url, headers=headers, json=data, timeout=30)
            elif method.upper() == 'PUT':
                response = requests.put(url, headers=headers, json=data, timeout=30)
            elif method.upper() == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=30)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            if response.ok:
                try:
                    return response.json()
                except:
                    return {'status': 'success', 'data': response.text}
            else:
                try:
                    error_data = response.json()
                except:
                    error_data = {'error': 'api_error', 'error_description': response.text}
                
                raise OAuth2Error(
                    error_data.get('error', 'api_request_failed'),
                    error_data.get('error_description', f'HTTP {response.status_code}')
                )
                
        except requests.RequestException as e:
            raise OAuth2Error('network_error', str(e))
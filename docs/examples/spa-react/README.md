# React SPA OAuth2 Integration Example

This example demonstrates how to integrate a React Single Page Application (SPA) with the Second Brain Database OAuth2 provider using the authorization code flow with PKCE.

## Features

- OAuth2 authorization code flow with PKCE (suitable for SPAs)
- React hooks for OAuth2 state management
- Automatic token refresh and rotation
- Secure token storage using HTTP-only cookies
- Protected routes and components
- Error handling and loading states
- API integration with automatic token injection
- Logout and token revocation

## Prerequisites

- Node.js 18+ and npm/yarn
- Registered OAuth2 client in Second Brain Database (configured as "public" client type)
- HTTPS setup for production (required for OAuth2)

## Installation

1. Clone or download this example
2. Install dependencies:

```bash
npm install
# or
yarn install
```

3. Configure your environment (see Configuration section)
4. Start the development server:

```bash
npm start
# or
yarn start
```

## Configuration

Create a `.env` file in the project root:

```env
# OAuth2 Configuration
REACT_APP_OAUTH2_CLIENT_ID=your_client_id_here
REACT_APP_OAUTH2_REDIRECT_URI=http://localhost:3000/auth/callback
REACT_APP_OAUTH2_AUTHORIZATION_URL=https://your-sbd-instance.com/oauth2/authorize
REACT_APP_OAUTH2_TOKEN_URL=https://your-sbd-instance.com/oauth2/token
REACT_APP_OAUTH2_API_BASE_URL=https://your-sbd-instance.com

# Application Configuration
REACT_APP_API_BASE_URL=http://localhost:3001
HTTPS=true  # Enable HTTPS in development
```

## Project Structure

```
spa-react/
├── package.json
├── .env.example
├── README.md
├── public/
│   ├── index.html
│   └── manifest.json
├── src/
│   ├── index.js              # Application entry point
│   ├── App.js                # Main App component
│   ├── hooks/
│   │   ├── useAuth.js        # Authentication hook
│   │   ├── useApi.js         # API integration hook
│   │   └── useLocalStorage.js # Local storage hook
│   ├── services/
│   │   ├── oauth2Client.js   # OAuth2 client service
│   │   ├── tokenManager.js   # Token management service
│   │   └── apiClient.js      # API client service
│   ├── components/
│   │   ├── Auth/
│   │   │   ├── LoginButton.js
│   │   │   ├── LogoutButton.js
│   │   │   └── AuthCallback.js
│   │   ├── Layout/
│   │   │   ├── Header.js
│   │   │   ├── Navigation.js
│   │   │   └── Footer.js
│   │   ├── Profile/
│   │   │   ├── UserProfile.js
│   │   │   └── TokenInfo.js
│   │   └── Common/
│   │       ├── LoadingSpinner.js
│   │       ├── ErrorBoundary.js
│   │       └── ProtectedRoute.js
│   ├── pages/
│   │   ├── Home.js
│   │   ├── Profile.js
│   │   ├── Dashboard.js
│   │   └── NotFound.js
│   ├── contexts/
│   │   └── AuthContext.js    # Authentication context
│   ├── utils/
│   │   ├── pkce.js           # PKCE helper functions
│   │   ├── storage.js        # Secure storage utilities
│   │   └── constants.js      # Application constants
│   └── styles/
│       ├── index.css
│       └── components/
```

## Usage

1. **Start the application**:
   ```bash
   npm start
   ```

2. **Navigate to the application**:
   Open https://localhost:3000 in your browser

3. **Login with OAuth2**:
   - Click "Login" button
   - You'll be redirected to the OAuth2 provider
   - Grant consent for the requested permissions
   - You'll be redirected back to the application

4. **Use protected features**:
   - View your profile information
   - Access protected API endpoints
   - See token information and expiration

## Code Examples

### OAuth2 Client Service

The OAuth2 client is implemented in `src/services/oauth2Client.js`:

```javascript
import { generateCodeVerifier, generateCodeChallenge } from '../utils/pkce';

class OAuth2Client {
  constructor() {
    this.clientId = process.env.REACT_APP_OAUTH2_CLIENT_ID;
    this.redirectUri = process.env.REACT_APP_OAUTH2_REDIRECT_URI;
    this.authorizationUrl = process.env.REACT_APP_OAUTH2_AUTHORIZATION_URL;
    this.tokenUrl = process.env.REACT_APP_OAUTH2_TOKEN_URL;
  }

  /**
   * Generate authorization URL with PKCE parameters
   */
  async getAuthorizationUrl(scopes = ['read:profile', 'write:data']) {
    // Generate PKCE parameters
    const codeVerifier = generateCodeVerifier();
    const codeChallenge = await generateCodeChallenge(codeVerifier);
    
    // Generate state for CSRF protection
    const state = this.generateState();
    
    // Store PKCE parameters and state
    sessionStorage.setItem('oauth2_code_verifier', codeVerifier);
    sessionStorage.setItem('oauth2_state', state);
    
    // Build authorization URL
    const params = new URLSearchParams({
      response_type: 'code',
      client_id: this.clientId,
      redirect_uri: this.redirectUri,
      scope: scopes.join(' '),
      state: state,
      code_challenge: codeChallenge,
      code_challenge_method: 'S256'
    });
    
    return `${this.authorizationUrl}?${params.toString()}`;
  }

  /**
   * Exchange authorization code for tokens
   */
  async exchangeCodeForTokens(code, state) {
    // Validate state parameter
    const storedState = sessionStorage.getItem('oauth2_state');
    if (!storedState || state !== storedState) {
      throw new Error('Invalid state parameter');
    }
    
    // Get code verifier
    const codeVerifier = sessionStorage.getItem('oauth2_code_verifier');
    if (!codeVerifier) {
      throw new Error('Missing code verifier');
    }
    
    // Clean up stored parameters
    sessionStorage.removeItem('oauth2_state');
    sessionStorage.removeItem('oauth2_code_verifier');
    
    // Exchange code for tokens
    const response = await fetch(this.tokenUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: new URLSearchParams({
        grant_type: 'authorization_code',
        code: code,
        redirect_uri: this.redirectUri,
        client_id: this.clientId,
        code_verifier: codeVerifier
      })
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.error_description || `HTTP ${response.status}`);
    }
    
    return await response.json();
  }

  /**
   * Refresh access token
   */
  async refreshAccessToken(refreshToken) {
    const response = await fetch(this.tokenUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: new URLSearchParams({
        grant_type: 'refresh_token',
        refresh_token: refreshToken,
        client_id: this.clientId
      })
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.error_description || `HTTP ${response.status}`);
    }
    
    return await response.json();
  }

  /**
   * Revoke token
   */
  async revokeToken(token, tokenTypeHint = null) {
    const revokeUrl = this.tokenUrl.replace('/token', '/revoke');
    
    const body = new URLSearchParams({
      token: token,
      client_id: this.clientId
    });
    
    if (tokenTypeHint) {
      body.append('token_type_hint', tokenTypeHint);
    }
    
    const response = await fetch(revokeUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: body
    });
    
    return response.ok;
  }

  /**
   * Generate cryptographically secure state
   */
  generateState() {
    const array = new Uint8Array(32);
    crypto.getRandomValues(array);
    return Array.from(array, byte => byte.toString(16).padStart(2, '0')).join('');
  }
}

export default new OAuth2Client();
```

### PKCE Utilities

PKCE implementation in `src/utils/pkce.js`:

```javascript
/**
 * Generate a cryptographically random code verifier
 */
export function generateCodeVerifier() {
  const array = new Uint8Array(32);
  crypto.getRandomValues(array);
  return base64URLEncode(array);
}

/**
 * Generate code challenge from verifier using SHA256
 */
export async function generateCodeChallenge(verifier) {
  const encoder = new TextEncoder();
  const data = encoder.encode(verifier);
  const digest = await crypto.subtle.digest('SHA-256', data);
  return base64URLEncode(new Uint8Array(digest));
}

/**
 * Base64URL encode (without padding)
 */
function base64URLEncode(array) {
  return btoa(String.fromCharCode(...array))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=/g, '');
}
```

### Authentication Hook

Authentication state management in `src/hooks/useAuth.js`:

```javascript
import { useState, useEffect, useCallback } from 'react';
import oauth2Client from '../services/oauth2Client';
import tokenManager from '../services/tokenManager';

export function useAuth() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [user, setUser] = useState(null);
  const [error, setError] = useState(null);

  // Check authentication status on mount
  useEffect(() => {
    checkAuthStatus();
  }, []);

  const checkAuthStatus = useCallback(async () => {
    try {
      setIsLoading(true);
      const token = await tokenManager.getValidAccessToken();
      
      if (token) {
        setIsAuthenticated(true);
        // Optionally fetch user info
        await fetchUserInfo(token);
      } else {
        setIsAuthenticated(false);
        setUser(null);
      }
    } catch (err) {
      console.error('Auth status check failed:', err);
      setError(err.message);
      setIsAuthenticated(false);
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const login = useCallback(async (scopes) => {
    try {
      setError(null);
      const authUrl = await oauth2Client.getAuthorizationUrl(scopes);
      window.location.href = authUrl;
    } catch (err) {
      console.error('Login failed:', err);
      setError(err.message);
    }
  }, []);

  const handleCallback = useCallback(async (code, state) => {
    try {
      setIsLoading(true);
      setError(null);
      
      // Exchange code for tokens
      const tokens = await oauth2Client.exchangeCodeForTokens(code, state);
      
      // Store tokens
      tokenManager.storeTokens(tokens);
      
      // Update auth state
      setIsAuthenticated(true);
      await fetchUserInfo(tokens.access_token);
      
      return true;
    } catch (err) {
      console.error('Callback handling failed:', err);
      setError(err.message);
      return false;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      setIsLoading(true);
      
      // Revoke tokens
      const tokens = tokenManager.getStoredTokens();
      if (tokens?.refresh_token) {
        await oauth2Client.revokeToken(tokens.refresh_token, 'refresh_token');
      }
      if (tokens?.access_token) {
        await oauth2Client.revokeToken(tokens.access_token, 'access_token');
      }
      
      // Clear stored tokens
      tokenManager.clearTokens();
      
      // Update state
      setIsAuthenticated(false);
      setUser(null);
      setError(null);
    } catch (err) {
      console.error('Logout failed:', err);
      // Clear tokens anyway
      tokenManager.clearTokens();
      setIsAuthenticated(false);
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const fetchUserInfo = async (accessToken) => {
    try {
      const response = await fetch(`${process.env.REACT_APP_OAUTH2_API_BASE_URL}/api/user/profile`, {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json'
        }
      });
      
      if (response.ok) {
        const userInfo = await response.json();
        setUser(userInfo);
      }
    } catch (err) {
      console.error('Failed to fetch user info:', err);
    }
  };

  const refreshToken = useCallback(async () => {
    try {
      const newToken = await tokenManager.getValidAccessToken();
      if (newToken) {
        await fetchUserInfo(newToken);
        return true;
      }
      return false;
    } catch (err) {
      console.error('Token refresh failed:', err);
      setError(err.message);
      return false;
    }
  }, []);

  return {
    isAuthenticated,
    isLoading,
    user,
    error,
    login,
    logout,
    handleCallback,
    refreshToken,
    checkAuthStatus
  };
}
```

### Token Manager Service

Token management in `src/services/tokenManager.js`:

```javascript
class TokenManager {
  constructor() {
    this.refreshPromise = null;
    this.refreshBuffer = 5 * 60 * 1000; // 5 minutes
  }

  /**
   * Store tokens securely
   */
  storeTokens(tokens) {
    const tokenData = {
      access_token: tokens.access_token,
      refresh_token: tokens.refresh_token,
      expires_at: Date.now() + (tokens.expires_in * 1000),
      scope: tokens.scope,
      token_type: tokens.token_type || 'Bearer'
    };

    // Store in sessionStorage (cleared when tab closes)
    sessionStorage.setItem('oauth2_tokens', JSON.stringify(tokenData));
    
    // Also store refresh token in localStorage for persistence across tabs
    if (tokens.refresh_token) {
      localStorage.setItem('oauth2_refresh_token', tokens.refresh_token);
    }
  }

  /**
   * Get stored tokens
   */
  getStoredTokens() {
    try {
      const tokenData = sessionStorage.getItem('oauth2_tokens');
      return tokenData ? JSON.parse(tokenData) : null;
    } catch (err) {
      console.error('Failed to parse stored tokens:', err);
      return null;
    }
  }

  /**
   * Get valid access token (refresh if necessary)
   */
  async getValidAccessToken() {
    const tokens = this.getStoredTokens();
    if (!tokens) {
      // Try to restore from refresh token
      return await this.restoreFromRefreshToken();
    }

    // Check if token needs refresh
    const expiresAt = tokens.expires_at || 0;
    const needsRefresh = Date.now() + this.refreshBuffer >= expiresAt;

    if (needsRefresh && tokens.refresh_token) {
      return await this.refreshAccessToken();
    }

    return tokens.access_token;
  }

  /**
   * Refresh access token
   */
  async refreshAccessToken() {
    // Prevent multiple simultaneous refresh attempts
    if (this.refreshPromise) {
      return await this.refreshPromise;
    }

    this.refreshPromise = this._performRefresh();
    
    try {
      const result = await this.refreshPromise;
      return result;
    } finally {
      this.refreshPromise = null;
    }
  }

  async _performRefresh() {
    const tokens = this.getStoredTokens();
    const refreshToken = tokens?.refresh_token || localStorage.getItem('oauth2_refresh_token');
    
    if (!refreshToken) {
      throw new Error('No refresh token available');
    }

    try {
      const oauth2Client = (await import('./oauth2Client')).default;
      const newTokens = await oauth2Client.refreshAccessToken(refreshToken);
      
      // Store new tokens
      this.storeTokens(newTokens);
      
      return newTokens.access_token;
    } catch (err) {
      // Refresh failed - clear tokens
      this.clearTokens();
      throw err;
    }
  }

  /**
   * Restore session from refresh token
   */
  async restoreFromRefreshToken() {
    const refreshToken = localStorage.getItem('oauth2_refresh_token');
    if (!refreshToken) {
      return null;
    }

    try {
      const oauth2Client = (await import('./oauth2Client')).default;
      const newTokens = await oauth2Client.refreshAccessToken(refreshToken);
      
      // Store new tokens
      this.storeTokens(newTokens);
      
      return newTokens.access_token;
    } catch (err) {
      // Refresh failed - clear stored refresh token
      localStorage.removeItem('oauth2_refresh_token');
      return null;
    }
  }

  /**
   * Clear all stored tokens
   */
  clearTokens() {
    sessionStorage.removeItem('oauth2_tokens');
    localStorage.removeItem('oauth2_refresh_token');
  }

  /**
   * Get token information for display
   */
  getTokenInfo() {
    const tokens = this.getStoredTokens();
    if (!tokens) {
      return null;
    }

    return {
      expires_at: tokens.expires_at,
      scope: tokens.scope ? tokens.scope.split(' ') : [],
      token_type: tokens.token_type,
      is_expired: Date.now() >= tokens.expires_at
    };
  }
}

export default new TokenManager();
```

### Authentication Context

React context for authentication in `src/contexts/AuthContext.js`:

```javascript
import React, { createContext, useContext } from 'react';
import { useAuth } from '../hooks/useAuth';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const auth = useAuth();
  
  return (
    <AuthContext.Provider value={auth}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuthContext() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuthContext must be used within an AuthProvider');
  }
  return context;
}
```

### Protected Route Component

Protected routes in `src/components/Common/ProtectedRoute.js`:

```javascript
import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuthContext } from '../../contexts/AuthContext';
import LoadingSpinner from './LoadingSpinner';

function ProtectedRoute({ children, requiredScopes = [] }) {
  const { isAuthenticated, isLoading, user } = useAuthContext();
  const location = useLocation();

  if (isLoading) {
    return <LoadingSpinner />;
  }

  if (!isAuthenticated) {
    // Redirect to login, saving the attempted location
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // Check required scopes if specified
  if (requiredScopes.length > 0) {
    const tokenManager = require('../../services/tokenManager').default;
    const tokenInfo = tokenManager.getTokenInfo();
    const userScopes = tokenInfo?.scope || [];
    
    const hasRequiredScopes = requiredScopes.every(scope => 
      userScopes.includes(scope)
    );
    
    if (!hasRequiredScopes) {
      return (
        <div className="error-message">
          <h2>Insufficient Permissions</h2>
          <p>You don't have the required permissions to access this page.</p>
          <p>Required scopes: {requiredScopes.join(', ')}</p>
        </div>
      );
    }
  }

  return children;
}

export default ProtectedRoute;
```

### OAuth2 Callback Component

Callback handling in `src/components/Auth/AuthCallback.js`:

```javascript
import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams, useLocation } from 'react-router-dom';
import { useAuthContext } from '../../contexts/AuthContext';
import LoadingSpinner from '../Common/LoadingSpinner';

function AuthCallback() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { handleCallback } = useAuthContext();
  const [error, setError] = useState(null);

  useEffect(() => {
    const processCallback = async () => {
      try {
        // Check for authorization errors
        const error = searchParams.get('error');
        if (error) {
          const errorDescription = searchParams.get('error_description') || 'Unknown error';
          throw new Error(`Authorization failed: ${errorDescription}`);
        }

        // Get authorization code and state
        const code = searchParams.get('code');
        const state = searchParams.get('state');

        if (!code || !state) {
          throw new Error('Missing authorization code or state parameter');
        }

        // Handle the callback
        const success = await handleCallback(code, state);
        
        if (success) {
          // Redirect to intended destination or home
          const from = location.state?.from?.pathname || '/dashboard';
          navigate(from, { replace: true });
        } else {
          throw new Error('Failed to complete authentication');
        }
      } catch (err) {
        console.error('Callback processing failed:', err);
        setError(err.message);
      }
    };

    processCallback();
  }, [searchParams, handleCallback, navigate, location.state]);

  if (error) {
    return (
      <div className="auth-callback-error">
        <h2>Authentication Error</h2>
        <p>{error}</p>
        <button onClick={() => navigate('/')}>
          Return to Home
        </button>
      </div>
    );
  }

  return (
    <div className="auth-callback-loading">
      <LoadingSpinner />
      <p>Completing authentication...</p>
    </div>
  );
}

export default AuthCallback;
```

### API Integration Hook

API integration with automatic token injection in `src/hooks/useApi.js`:

```javascript
import { useState, useCallback } from 'react';
import { useAuthContext } from '../contexts/AuthContext';
import tokenManager from '../services/tokenManager';

export function useApi() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const { logout } = useAuthContext();

  const apiCall = useCallback(async (url, options = {}) => {
    try {
      setLoading(true);
      setError(null);

      // Get valid access token
      const accessToken = await tokenManager.getValidAccessToken();
      if (!accessToken) {
        throw new Error('No valid access token available');
      }

      // Prepare request options
      const requestOptions = {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...options.headers,
          'Authorization': `Bearer ${accessToken}`
        }
      };

      // Make API request
      const response = await fetch(url, requestOptions);

      // Handle authentication errors
      if (response.status === 401) {
        // Token might be invalid - try to refresh
        try {
          const newToken = await tokenManager.getValidAccessToken();
          if (newToken && newToken !== accessToken) {
            // Retry with new token
            requestOptions.headers.Authorization = `Bearer ${newToken}`;
            const retryResponse = await fetch(url, requestOptions);
            
            if (retryResponse.status === 401) {
              // Still unauthorized - logout user
              await logout();
              throw new Error('Authentication failed. Please login again.');
            }
            
            return await handleResponse(retryResponse);
          } else {
            // Refresh failed - logout user
            await logout();
            throw new Error('Authentication failed. Please login again.');
          }
        } catch (refreshError) {
          await logout();
          throw new Error('Authentication failed. Please login again.');
        }
      }

      return await handleResponse(response);
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [logout]);

  const handleResponse = async (response) => {
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.message || `HTTP ${response.status}`);
    }

    const contentType = response.headers.get('content-type');
    if (contentType && contentType.includes('application/json')) {
      return await response.json();
    }
    
    return await response.text();
  };

  // Convenience methods
  const get = useCallback((url, options = {}) => {
    return apiCall(url, { ...options, method: 'GET' });
  }, [apiCall]);

  const post = useCallback((url, data, options = {}) => {
    return apiCall(url, {
      ...options,
      method: 'POST',
      body: JSON.stringify(data)
    });
  }, [apiCall]);

  const put = useCallback((url, data, options = {}) => {
    return apiCall(url, {
      ...options,
      method: 'PUT',
      body: JSON.stringify(data)
    });
  }, [apiCall]);

  const del = useCallback((url, options = {}) => {
    return apiCall(url, { ...options, method: 'DELETE' });
  }, [apiCall]);

  return {
    loading,
    error,
    apiCall,
    get,
    post,
    put,
    delete: del
  };
}
```

## Security Features

### Secure Token Storage

```javascript
// Use sessionStorage for access tokens (cleared when tab closes)
// Use localStorage only for refresh tokens (with careful handling)

class SecureStorage {
  static setItem(key, value, persistent = false) {
    const storage = persistent ? localStorage : sessionStorage;
    try {
      storage.setItem(key, JSON.stringify(value));
    } catch (err) {
      console.error('Failed to store data:', err);
    }
  }

  static getItem(key, persistent = false) {
    const storage = persistent ? localStorage : sessionStorage;
    try {
      const item = storage.getItem(key);
      return item ? JSON.parse(item) : null;
    } catch (err) {
      console.error('Failed to retrieve data:', err);
      return null;
    }
  }

  static removeItem(key, persistent = false) {
    const storage = persistent ? localStorage : sessionStorage;
    storage.removeItem(key);
  }
}
```

### Content Security Policy

Add to your `public/index.html`:

```html
<meta http-equiv="Content-Security-Policy" content="
  default-src 'self';
  script-src 'self' 'unsafe-inline';
  style-src 'self' 'unsafe-inline';
  connect-src 'self' https://your-sbd-instance.com;
  img-src 'self' data: https:;
  font-src 'self';
  frame-ancestors 'none';
">
```

## Error Handling

### Error Boundary Component

```javascript
import React from 'react';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('Error boundary caught an error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="error-boundary">
          <h2>Something went wrong</h2>
          <p>{this.state.error?.message}</p>
          <button onClick={() => window.location.reload()}>
            Reload Page
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
```

## Testing

### OAuth2 Flow Testing

```javascript
// src/tests/oauth2.test.js
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { AuthProvider } from '../contexts/AuthContext';
import LoginButton from '../components/Auth/LoginButton';

// Mock OAuth2 client
jest.mock('../services/oauth2Client', () => ({
  getAuthorizationUrl: jest.fn().mockResolvedValue('https://example.com/auth'),
  exchangeCodeForTokens: jest.fn().mockResolvedValue({
    access_token: 'test_token',
    refresh_token: 'test_refresh',
    expires_in: 3600
  })
}));

describe('OAuth2 Integration', () => {
  const renderWithProviders = (component) => {
    return render(
      <BrowserRouter>
        <AuthProvider>
          {component}
        </AuthProvider>
      </BrowserRouter>
    );
  };

  test('login button initiates OAuth2 flow', async () => {
    const user = userEvent.setup();
    
    // Mock window.location.href
    delete window.location;
    window.location = { href: '' };
    
    renderWithProviders(<LoginButton />);
    
    const loginButton = screen.getByText('Login');
    await user.click(loginButton);
    
    await waitFor(() => {
      expect(window.location.href).toContain('oauth2/authorize');
    });
  });

  test('PKCE parameters are generated correctly', () => {
    const { generateCodeVerifier, generateCodeChallenge } = require('../utils/pkce');
    
    const verifier = generateCodeVerifier();
    expect(verifier).toHaveLength(43);
    expect(verifier).toMatch(/^[A-Za-z0-9_-]+$/);
    
    // Test code challenge generation
    generateCodeChallenge(verifier).then(challenge => {
      expect(challenge).toHaveLength(43);
      expect(challenge).toMatch(/^[A-Za-z0-9_-]+$/);
    });
  });
});
```

Run tests:

```bash
npm test
# or
yarn test
```

## Production Deployment

### Build Configuration

```json
{
  "scripts": {
    "build": "react-scripts build",
    "build:prod": "GENERATE_SOURCEMAP=false react-scripts build"
  }
}
```

### Environment Variables for Production

```env
REACT_APP_OAUTH2_CLIENT_ID=your_production_client_id
REACT_APP_OAUTH2_REDIRECT_URI=https://yourdomain.com/auth/callback
REACT_APP_OAUTH2_AUTHORIZATION_URL=https://sbd-instance.com/oauth2/authorize
REACT_APP_OAUTH2_TOKEN_URL=https://sbd-instance.com/oauth2/token
REACT_APP_OAUTH2_API_BASE_URL=https://sbd-instance.com
```

### Nginx Configuration

```nginx
server {
    listen 443 ssl http2;
    server_name yourdomain.com;
    
    ssl_certificate /path/to/certificate.crt;
    ssl_certificate_key /path/to/private.key;
    
    root /var/www/react-app/build;
    index index.html;
    
    # Handle client-side routing
    location / {
        try_files $uri $uri/ /index.html;
    }
    
    # Security headers
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options DENY;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains";
}
```

## Troubleshooting

### Common Issues

1. **CORS errors during development**
   - Ensure your OAuth2 client is configured with correct redirect URIs
   - Use HTTPS in development for OAuth2 compliance

2. **Token refresh failures**
   - Check that refresh tokens are being stored correctly
   - Verify token endpoint configuration

3. **State parameter validation errors**
   - Ensure state is properly generated and stored
   - Check for session storage issues

### Debug Mode

Enable debug logging:

```javascript
// Add to your main App.js
if (process.env.NODE_ENV === 'development') {
  window.debugOAuth2 = true;
}
```

## Support

For additional help:
- Check the [OAuth2 Integration Guide](../../OAUTH2_INTEGRATION.md)
- Review the [API Reference](../../OAUTH2_API_REFERENCE.md)
- See other examples in the [examples directory](../)
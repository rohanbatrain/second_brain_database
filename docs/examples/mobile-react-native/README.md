# React Native OAuth2 Integration Example

This example demonstrates how to integrate a React Native mobile application with the Second Brain Database OAuth2 provider using the authorization code flow with PKCE.

## Features

- OAuth2 authorization code flow with PKCE for mobile apps
- In-app browser for secure authentication
- Automatic token refresh and rotation
- Secure token storage using Keychain/Keystore
- Deep linking for OAuth2 callbacks
- Biometric authentication for token access
- Offline token validation
- Cross-platform support (iOS and Android)

## Prerequisites

- React Native development environment set up
- Node.js 18+ and npm/yarn
- iOS: Xcode and iOS Simulator
- Android: Android Studio and Android Emulator
- Registered OAuth2 client in Second Brain Database (configured as "public" client type)

## Installation

1. Clone or download this example
2. Install dependencies:

```bash
npm install
# or
yarn install
```

3. Install iOS dependencies (iOS only):

```bash
cd ios && pod install && cd ..
```

4. Configure your environment (see Configuration section)
5. Start the Metro bundler:

```bash
npm start
# or
yarn start
```

6. Run on device/simulator:

```bash
# iOS
npm run ios
# or
yarn ios

# Android
npm run android
# or
yarn android
```

## Configuration

Create a `.env` file in the project root:

```env
# OAuth2 Configuration
OAUTH2_CLIENT_ID=your_client_id_here
OAUTH2_REDIRECT_URI=com.yourapp.oauth://callback
OAUTH2_AUTHORIZATION_URL=https://your-sbd-instance.com/oauth2/authorize
OAUTH2_TOKEN_URL=https://your-sbd-instance.com/oauth2/token
OAUTH2_API_BASE_URL=https://your-sbd-instance.com

# App Configuration
APP_SCHEME=com.yourapp.oauth
```

### Deep Link Configuration

#### iOS Configuration (`ios/YourApp/Info.plist`)

```xml
<key>CFBundleURLTypes</key>
<array>
    <dict>
        <key>CFBundleURLName</key>
        <string>OAuth2 Callback</string>
        <key>CFBundleURLSchemes</key>
        <array>
            <string>com.yourapp.oauth</string>
        </array>
    </dict>
</array>
```

#### Android Configuration (`android/app/src/main/AndroidManifest.xml`)

```xml
<activity
    android:name=".MainActivity"
    android:exported="true"
    android:launchMode="singleTop"
    android:theme="@style/AppTheme">
    
    <!-- Existing intent filters -->
    
    <!-- OAuth2 callback intent filter -->
    <intent-filter android:autoVerify="true">
        <action android:name="android.intent.action.VIEW" />
        <category android:name="android.intent.category.DEFAULT" />
        <category android:name="android.intent.category.BROWSABLE" />
        <data android:scheme="com.yourapp.oauth" />
    </intent-filter>
</activity>
```

## Project Structure

```
mobile-react-native/
├── package.json
├── .env.example
├── README.md
├── metro.config.js
├── babel.config.js
├── ios/                      # iOS specific files
├── android/                  # Android specific files
├── src/
│   ├── App.js               # Main App component
│   ├── services/
│   │   ├── OAuth2Service.js # OAuth2 client service
│   │   ├── TokenManager.js  # Secure token management
│   │   ├── ApiService.js    # API client service
│   │   └── BiometricAuth.js # Biometric authentication
│   ├── hooks/
│   │   ├── useAuth.js       # Authentication hook
│   │   ├── useApi.js        # API integration hook
│   │   └── useDeepLink.js   # Deep link handling hook
│   ├── components/
│   │   ├── Auth/
│   │   │   ├── LoginScreen.js
│   │   │   ├── AuthCallback.js
│   │   │   └── BiometricPrompt.js
│   │   ├── Profile/
│   │   │   ├── UserProfile.js
│   │   │   └── TokenInfo.js
│   │   └── Common/
│   │       ├── LoadingSpinner.js
│   │       ├── ErrorBoundary.js
│   │       └── ProtectedScreen.js
│   ├── screens/
│   │   ├── HomeScreen.js
│   │   ├── ProfileScreen.js
│   │   ├── SettingsScreen.js
│   │   └── LoginScreen.js
│   ├── navigation/
│   │   ├── AppNavigator.js
│   │   └── AuthNavigator.js
│   ├── utils/
│   │   ├── pkce.js          # PKCE helper functions
│   │   ├── crypto.js        # Cryptographic utilities
│   │   └── constants.js     # App constants
│   └── contexts/
│       └── AuthContext.js   # Authentication context
```

## Usage

1. **Start the application**:
   ```bash
   npm start
   ```

2. **Run on device**:
   ```bash
   npm run ios    # or npm run android
   ```

3. **Login with OAuth2**:
   - Tap "Login" button
   - In-app browser opens with OAuth2 provider
   - Grant consent for requested permissions
   - App automatically handles the callback

4. **Use protected features**:
   - View profile information
   - Access protected API endpoints
   - Use biometric authentication for sensitive operations

## Code Examples

### OAuth2 Service

The OAuth2 service is implemented in `src/services/OAuth2Service.js`:

```javascript
import { InAppBrowser } from 'react-native-inappbrowser-reborn';
import { Linking } from 'react-native';
import Config from 'react-native-config';
import { generateCodeVerifier, generateCodeChallenge } from '../utils/pkce';
import { generateSecureRandom } from '../utils/crypto';

class OAuth2Service {
  constructor() {
    this.clientId = Config.OAUTH2_CLIENT_ID;
    this.redirectUri = Config.OAUTH2_REDIRECT_URI;
    this.authorizationUrl = Config.OAUTH2_AUTHORIZATION_URL;
    this.tokenUrl = Config.OAUTH2_TOKEN_URL;
  }

  /**
   * Initiate OAuth2 authorization flow
   */
  async authorize(scopes = ['read:profile', 'write:data']) {
    try {
      // Generate PKCE parameters
      const codeVerifier = generateCodeVerifier();
      const codeChallenge = await generateCodeChallenge(codeVerifier);
      const state = generateSecureRandom(32);

      // Store PKCE parameters for later use
      this.pendingAuth = {
        codeVerifier,
        state,
        timestamp: Date.now()
      };

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

      const authUrl = `${this.authorizationUrl}?${params.toString()}`;

      // Check if InAppBrowser is available
      if (await InAppBrowser.isAvailable()) {
        const result = await InAppBrowser.openAuth(authUrl, this.redirectUri, {
          // iOS options
          dismissButtonStyle: 'cancel',
          preferredBarTintColor: '#453AA4',
          preferredControlTintColor: 'white',
          readerMode: false,
          animated: true,
          modalPresentationStyle: 'fullScreen',
          modalTransitionStyle: 'coverVertical',
          modalEnabled: true,
          enableBarCollapsing: false,
          // Android options
          showTitle: true,
          toolbarColor: '#453AA4',
          secondaryToolbarColor: 'black',
          navigationBarColor: 'black',
          navigationBarDividerColor: 'white',
          enableUrlBarHiding: true,
          enableDefaultShare: false,
          forceCloseOnRedirection: false,
        });

        if (result.type === 'success') {
          return this.handleAuthCallback(result.url);
        } else {
          throw new Error('Authorization cancelled or failed');
        }
      } else {
        // Fallback to system browser
        await Linking.openURL(authUrl);
        return new Promise((resolve, reject) => {
          const handleUrl = (url) => {
            Linking.removeEventListener('url', handleUrl);
            this.handleAuthCallback(url).then(resolve).catch(reject);
          };
          Linking.addEventListener('url', handleUrl);
        });
      }
    } catch (error) {
      console.error('OAuth2 authorization failed:', error);
      throw error;
    }
  }

  /**
   * Handle OAuth2 callback URL
   */
  async handleAuthCallback(url) {
    try {
      const urlObj = new URL(url);
      const params = new URLSearchParams(urlObj.search);

      // Check for errors
      const error = params.get('error');
      if (error) {
        const errorDescription = params.get('error_description') || 'Unknown error';
        throw new Error(`Authorization failed: ${errorDescription}`);
      }

      // Get authorization code and state
      const code = params.get('code');
      const state = params.get('state');

      if (!code || !state) {
        throw new Error('Missing authorization code or state parameter');
      }

      // Validate state and get PKCE parameters
      if (!this.pendingAuth || state !== this.pendingAuth.state) {
        throw new Error('Invalid state parameter');
      }

      // Check for replay attacks (5 minute window)
      if (Date.now() - this.pendingAuth.timestamp > 5 * 60 * 1000) {
        throw new Error('Authorization request expired');
      }

      const { codeVerifier } = this.pendingAuth;
      this.pendingAuth = null; // Clear pending auth

      // Exchange code for tokens
      return await this.exchangeCodeForTokens(code, codeVerifier);
    } catch (error) {
      this.pendingAuth = null; // Clear pending auth on error
      throw error;
    }
  }

  /**
   * Exchange authorization code for tokens
   */
  async exchangeCodeForTokens(code, codeVerifier) {
    try {
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
        }).toString()
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error_description || `HTTP ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Token exchange failed:', error);
      throw error;
    }
  }

  /**
   * Refresh access token
   */
  async refreshAccessToken(refreshToken) {
    try {
      const response = await fetch(this.tokenUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams({
          grant_type: 'refresh_token',
          refresh_token: refreshToken,
          client_id: this.clientId
        }).toString()
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error_description || `HTTP ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Token refresh failed:', error);
      throw error;
    }
  }

  /**
   * Revoke token
   */
  async revokeToken(token, tokenTypeHint = null) {
    try {
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
        body: body.toString()
      });

      return response.ok;
    } catch (error) {
      console.error('Token revocation failed:', error);
      return false;
    }
  }
}

export default new OAuth2Service();
```

### Secure Token Manager

Token management with Keychain/Keystore in `src/services/TokenManager.js`:

```javascript
import * as Keychain from 'react-native-keychain';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Platform } from 'react-native';
import OAuth2Service from './OAuth2Service';
import BiometricAuth from './BiometricAuth';

class TokenManager {
  constructor() {
    this.refreshPromise = null;
    this.refreshBuffer = 5 * 60 * 1000; // 5 minutes
    this.keychainService = 'OAuth2Tokens';
  }

  /**
   * Store tokens securely in Keychain/Keystore
   */
  async storeTokens(tokens, requireBiometric = false) {
    try {
      const tokenData = {
        access_token: tokens.access_token,
        refresh_token: tokens.refresh_token,
        expires_at: Date.now() + (tokens.expires_in * 1000),
        scope: tokens.scope,
        token_type: tokens.token_type || 'Bearer',
        stored_at: Date.now()
      };

      // Configure keychain options
      const options = {
        service: this.keychainService,
        accessControl: requireBiometric 
          ? Keychain.ACCESS_CONTROL.BIOMETRY_CURRENT_SET
          : Keychain.ACCESS_CONTROL.DEVICE_PASSCODE,
        authenticatePrompt: 'Authenticate to access your tokens',
        showModal: true,
        kLocalizedFallbackTitle: 'Use Passcode',
      };

      // Store in secure keychain
      await Keychain.setInternetCredentials(
        this.keychainService,
        'oauth2_tokens',
        JSON.stringify(tokenData),
        options
      );

      // Store non-sensitive metadata in AsyncStorage for quick access
      await AsyncStorage.setItem('oauth2_token_metadata', JSON.stringify({
        expires_at: tokenData.expires_at,
        scope: tokenData.scope,
        stored_at: tokenData.stored_at,
        has_biometric: requireBiometric
      }));

      console.log('Tokens stored securely');
    } catch (error) {
      console.error('Failed to store tokens:', error);
      throw error;
    }
  }

  /**
   * Retrieve tokens from secure storage
   */
  async getStoredTokens(requireBiometric = false) {
    try {
      const options = {
        service: this.keychainService,
        authenticatePrompt: 'Authenticate to access your tokens',
        showModal: true,
        kLocalizedFallbackTitle: 'Use Passcode',
      };

      const credentials = await Keychain.getInternetCredentials(
        this.keychainService,
        options
      );

      if (credentials && credentials.password) {
        return JSON.parse(credentials.password);
      }

      return null;
    } catch (error) {
      if (error.message === 'UserCancel' || error.message === 'UserFallback') {
        throw new Error('Authentication cancelled');
      }
      console.error('Failed to retrieve tokens:', error);
      return null;
    }
  }

  /**
   * Get token metadata without biometric authentication
   */
  async getTokenMetadata() {
    try {
      const metadata = await AsyncStorage.getItem('oauth2_token_metadata');
      return metadata ? JSON.parse(metadata) : null;
    } catch (error) {
      console.error('Failed to get token metadata:', error);
      return null;
    }
  }

  /**
   * Get valid access token (refresh if necessary)
   */
  async getValidAccessToken(requireBiometric = false) {
    try {
      // Check metadata first to avoid unnecessary biometric prompts
      const metadata = await this.getTokenMetadata();
      if (!metadata) {
        return null;
      }

      // Check if token needs refresh
      const needsRefresh = Date.now() + this.refreshBuffer >= metadata.expires_at;

      if (needsRefresh) {
        return await this.refreshAccessToken(requireBiometric);
      }

      // Get tokens from secure storage
      const tokens = await this.getStoredTokens(requireBiometric);
      return tokens?.access_token || null;
    } catch (error) {
      console.error('Failed to get valid access token:', error);
      return null;
    }
  }

  /**
   * Refresh access token
   */
  async refreshAccessToken(requireBiometric = false) {
    // Prevent multiple simultaneous refresh attempts
    if (this.refreshPromise) {
      return await this.refreshPromise;
    }

    this.refreshPromise = this._performRefresh(requireBiometric);
    
    try {
      const result = await this.refreshPromise;
      return result;
    } finally {
      this.refreshPromise = null;
    }
  }

  async _performRefresh(requireBiometric) {
    try {
      const tokens = await this.getStoredTokens(requireBiometric);
      if (!tokens?.refresh_token) {
        throw new Error('No refresh token available');
      }

      const newTokens = await OAuth2Service.refreshAccessToken(tokens.refresh_token);
      
      // Store new tokens
      await this.storeTokens(newTokens, requireBiometric);
      
      return newTokens.access_token;
    } catch (error) {
      // Refresh failed - clear tokens
      await this.clearTokens();
      throw error;
    }
  }

  /**
   * Clear all stored tokens
   */
  async clearTokens() {
    try {
      await Keychain.resetInternetCredentials(this.keychainService);
      await AsyncStorage.removeItem('oauth2_token_metadata');
      console.log('Tokens cleared');
    } catch (error) {
      console.error('Failed to clear tokens:', error);
    }
  }

  /**
   * Check if tokens exist
   */
  async hasTokens() {
    try {
      const metadata = await this.getTokenMetadata();
      return metadata !== null;
    } catch (error) {
      return false;
    }
  }

  /**
   * Get token information for display
   */
  async getTokenInfo() {
    try {
      const metadata = await this.getTokenMetadata();
      if (!metadata) {
        return null;
      }

      return {
        expires_at: metadata.expires_at,
        scope: metadata.scope ? metadata.scope.split(' ') : [],
        stored_at: metadata.stored_at,
        is_expired: Date.now() >= metadata.expires_at,
        has_biometric: metadata.has_biometric
      };
    } catch (error) {
      console.error('Failed to get token info:', error);
      return null;
    }
  }

  /**
   * Enable biometric protection for existing tokens
   */
  async enableBiometricProtection() {
    try {
      const tokens = await this.getStoredTokens(false);
      if (tokens) {
        await this.storeTokens({
          access_token: tokens.access_token,
          refresh_token: tokens.refresh_token,
          expires_in: Math.max(0, (tokens.expires_at - Date.now()) / 1000),
          scope: tokens.scope,
          token_type: tokens.token_type
        }, true);
      }
    } catch (error) {
      console.error('Failed to enable biometric protection:', error);
      throw error;
    }
  }
}

export default new TokenManager();
```

### Biometric Authentication Service

Biometric authentication in `src/services/BiometricAuth.js`:

```javascript
import TouchID from 'react-native-touch-id';
import { Platform, Alert } from 'react-native';

class BiometricAuth {
  constructor() {
    this.isSupported = null;
    this.biometryType = null;
  }

  /**
   * Check if biometric authentication is supported
   */
  async isSupported() {
    if (this.isSupported !== null) {
      return this.isSupported;
    }

    try {
      const biometryType = await TouchID.isSupported();
      this.biometryType = biometryType;
      this.isSupported = true;
      return true;
    } catch (error) {
      this.isSupported = false;
      return false;
    }
  }

  /**
   * Get biometry type
   */
  async getBiometryType() {
    if (this.biometryType) {
      return this.biometryType;
    }

    try {
      this.biometryType = await TouchID.isSupported();
      return this.biometryType;
    } catch (error) {
      return null;
    }
  }

  /**
   * Authenticate with biometrics
   */
  async authenticate(reason = 'Authenticate to continue') {
    try {
      const isSupported = await this.isSupported();
      if (!isSupported) {
        throw new Error('Biometric authentication not supported');
      }

      const options = {
        title: 'Authentication Required',
        subTitle: reason,
        description: 'Use your biometric to authenticate',
        fallbackLabel: 'Use Passcode',
        cancelLabel: 'Cancel',
        disableDeviceFallback: false,
        imageColor: '#e00606',
        imageErrorColor: '#ff0000',
        sensorDescription: 'Touch sensor',
        sensorErrorDescription: 'Failed',
        unifiedErrors: false,
        passcodeFallback: true,
      };

      await TouchID.authenticate(reason, options);
      return true;
    } catch (error) {
      console.error('Biometric authentication failed:', error);
      
      if (error.name === 'LAErrorUserCancel' || error.name === 'UserCancel') {
        throw new Error('Authentication cancelled');
      } else if (error.name === 'LAErrorUserFallback' || error.name === 'UserFallback') {
        throw new Error('User chose fallback');
      } else if (error.name === 'LAErrorSystemCancel' || error.name === 'SystemCancel') {
        throw new Error('System cancelled authentication');
      } else {
        throw new Error('Authentication failed');
      }
    }
  }

  /**
   * Show biometric setup prompt
   */
  showSetupPrompt() {
    Alert.alert(
      'Enable Biometric Authentication',
      'Secure your tokens with biometric authentication for enhanced security.',
      [
        { text: 'Not Now', style: 'cancel' },
        { 
          text: 'Enable', 
          onPress: () => this.authenticate('Enable biometric authentication')
        }
      ]
    );
  }

  /**
   * Get user-friendly biometry type name
   */
  getBiometryTypeName() {
    switch (this.biometryType) {
      case 'FaceID':
        return 'Face ID';
      case 'TouchID':
        return 'Touch ID';
      case 'Fingerprint':
        return 'Fingerprint';
      default:
        return 'Biometric';
    }
  }
}

export default new BiometricAuth();
```

### Authentication Hook

Authentication hook in `src/hooks/useAuth.js`:

```javascript
import { useState, useEffect, useCallback } from 'react';
import { Linking } from 'react-native';
import OAuth2Service from '../services/OAuth2Service';
import TokenManager from '../services/TokenManager';
import BiometricAuth from '../services/BiometricAuth';

export function useAuth() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [user, setUser] = useState(null);
  const [error, setError] = useState(null);
  const [biometricEnabled, setBiometricEnabled] = useState(false);

  // Check authentication status on mount
  useEffect(() => {
    checkAuthStatus();
    setupDeepLinkListener();
  }, []);

  const setupDeepLinkListener = () => {
    // Handle deep links when app is already running
    const handleUrl = (url) => {
      if (url.includes('oauth')) {
        handleOAuthCallback(url);
      }
    };

    Linking.addEventListener('url', handleUrl);

    // Handle deep links when app is launched from closed state
    Linking.getInitialURL().then((url) => {
      if (url && url.includes('oauth')) {
        handleOAuthCallback(url);
      }
    });

    return () => {
      Linking.removeEventListener('url', handleUrl);
    };
  };

  const checkAuthStatus = useCallback(async () => {
    try {
      setIsLoading(true);
      
      const hasTokens = await TokenManager.hasTokens();
      if (hasTokens) {
        const tokenInfo = await TokenManager.getTokenInfo();
        setBiometricEnabled(tokenInfo?.has_biometric || false);
        
        // Try to get a valid token (this will prompt for biometric if needed)
        const token = await TokenManager.getValidAccessToken(tokenInfo?.has_biometric);
        
        if (token) {
          setIsAuthenticated(true);
          await fetchUserInfo(token);
        } else {
          setIsAuthenticated(false);
          setUser(null);
        }
      } else {
        setIsAuthenticated(false);
        setUser(null);
      }
    } catch (err) {
      console.error('Auth status check failed:', err);
      if (err.message !== 'Authentication cancelled') {
        setError(err.message);
      }
      setIsAuthenticated(false);
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const login = useCallback(async (scopes) => {
    try {
      setError(null);
      setIsLoading(true);
      
      const tokens = await OAuth2Service.authorize(scopes);
      
      // Check if biometric authentication is available
      const biometricSupported = await BiometricAuth.isSupported();
      let useBiometric = false;
      
      if (biometricSupported) {
        // You could show a prompt here to ask user if they want biometric protection
        useBiometric = true; // For this example, we'll enable it by default
      }
      
      await TokenManager.storeTokens(tokens, useBiometric);
      setBiometricEnabled(useBiometric);
      
      setIsAuthenticated(true);
      await fetchUserInfo(tokens.access_token);
      
      return true;
    } catch (err) {
      console.error('Login failed:', err);
      setError(err.message);
      return false;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const handleOAuthCallback = useCallback(async (url) => {
    try {
      setIsLoading(true);
      const tokens = await OAuth2Service.handleAuthCallback(url);
      
      if (tokens) {
        const biometricSupported = await BiometricAuth.isSupported();
        await TokenManager.storeTokens(tokens, biometricSupported);
        setBiometricEnabled(biometricSupported);
        
        setIsAuthenticated(true);
        await fetchUserInfo(tokens.access_token);
      }
    } catch (err) {
      console.error('OAuth callback failed:', err);
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      setIsLoading(true);
      
      // Get tokens for revocation
      const tokens = await TokenManager.getStoredTokens(biometricEnabled);
      
      // Revoke tokens
      if (tokens?.refresh_token) {
        await OAuth2Service.revokeToken(tokens.refresh_token, 'refresh_token');
      }
      if (tokens?.access_token) {
        await OAuth2Service.revokeToken(tokens.access_token, 'access_token');
      }
      
      // Clear stored tokens
      await TokenManager.clearTokens();
      
      // Update state
      setIsAuthenticated(false);
      setUser(null);
      setError(null);
      setBiometricEnabled(false);
    } catch (err) {
      console.error('Logout failed:', err);
      // Clear tokens anyway
      await TokenManager.clearTokens();
      setIsAuthenticated(false);
      setUser(null);
      setBiometricEnabled(false);
    } finally {
      setIsLoading(false);
    }
  }, [biometricEnabled]);

  const fetchUserInfo = async (accessToken) => {
    try {
      const response = await fetch(`${Config.OAUTH2_API_BASE_URL}/api/user/profile`, {
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

  const enableBiometric = useCallback(async () => {
    try {
      await BiometricAuth.authenticate('Enable biometric authentication');
      await TokenManager.enableBiometricProtection();
      setBiometricEnabled(true);
      return true;
    } catch (err) {
      console.error('Failed to enable biometric:', err);
      setError(err.message);
      return false;
    }
  }, []);

  return {
    isAuthenticated,
    isLoading,
    user,
    error,
    biometricEnabled,
    login,
    logout,
    checkAuthStatus,
    enableBiometric
  };
}
```

### Deep Link Hook

Deep link handling in `src/hooks/useDeepLink.js`:

```javascript
import { useEffect, useState } from 'react';
import { Linking } from 'react-native';

export function useDeepLink() {
  const [initialUrl, setInitialUrl] = useState(null);
  const [url, setUrl] = useState(null);

  useEffect(() => {
    // Get initial URL when app is launched from closed state
    Linking.getInitialURL().then((url) => {
      if (url) {
        setInitialUrl(url);
        setUrl(url);
      }
    });

    // Listen for URL changes when app is running
    const handleUrl = (event) => {
      setUrl(event.url);
    };

    Linking.addEventListener('url', handleUrl);

    return () => {
      Linking.removeEventListener('url', handleUrl);
    };
  }, []);

  const clearUrl = () => {
    setUrl(null);
  };

  return {
    initialUrl,
    url,
    clearUrl
  };
}
```

## Security Features

### PKCE Implementation

```javascript
// src/utils/pkce.js
import { NativeModules } from 'react-native';
import CryptoJS from 'crypto-js';

/**
 * Generate cryptographically secure code verifier
 */
export function generateCodeVerifier() {
  // Generate 32 random bytes
  const randomBytes = new Uint8Array(32);
  
  // Use native crypto if available, fallback to CryptoJS
  if (NativeModules.RNCrypto) {
    NativeModules.RNCrypto.randomBytes(32, (bytes) => {
      randomBytes.set(bytes);
    });
  } else {
    // Fallback using CryptoJS
    const wordArray = CryptoJS.lib.WordArray.random(32);
    const bytes = wordArray.words.flatMap(word => [
      (word >>> 24) & 0xff,
      (word >>> 16) & 0xff,
      (word >>> 8) & 0xff,
      word & 0xff
    ]);
    randomBytes.set(bytes);
  }
  
  return base64URLEncode(randomBytes);
}

/**
 * Generate code challenge from verifier
 */
export async function generateCodeChallenge(verifier) {
  // Use native crypto if available
  if (NativeModules.RNCrypto) {
    return new Promise((resolve) => {
      NativeModules.RNCrypto.sha256(verifier, (hash) => {
        resolve(base64URLEncode(new Uint8Array(hash)));
      });
    });
  } else {
    // Fallback using CryptoJS
    const hash = CryptoJS.SHA256(verifier);
    const hashArray = new Uint8Array(hash.words.length * 4);
    hash.words.forEach((word, i) => {
      hashArray[i * 4] = (word >>> 24) & 0xff;
      hashArray[i * 4 + 1] = (word >>> 16) & 0xff;
      hashArray[i * 4 + 2] = (word >>> 8) & 0xff;
      hashArray[i * 4 + 3] = word & 0xff;
    });
    return base64URLEncode(hashArray);
  }
}

function base64URLEncode(array) {
  const base64 = btoa(String.fromCharCode(...array));
  return base64.replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');
}
```

### Certificate Pinning

```javascript
// src/utils/networking.js
import { NetworkingModule } from 'react-native';

// Configure certificate pinning for production
if (__DEV__ === false) {
  NetworkingModule.addCertificatePinner({
    hostname: 'your-sbd-instance.com',
    pin: 'sha256/YOUR_CERTIFICATE_PIN_HERE'
  });
}
```

## Testing

### OAuth2 Flow Testing

```javascript
// __tests__/oauth2.test.js
import { OAuth2Service } from '../src/services/OAuth2Service';
import { TokenManager } from '../src/services/TokenManager';

// Mock react-native modules
jest.mock('react-native-inappbrowser-reborn', () => ({
  isAvailable: jest.fn().mockResolvedValue(true),
  openAuth: jest.fn().mockResolvedValue({
    type: 'success',
    url: 'com.yourapp.oauth://callback?code=test_code&state=test_state'
  })
}));

jest.mock('react-native-keychain', () => ({
  setInternetCredentials: jest.fn().mockResolvedValue(true),
  getInternetCredentials: jest.fn().mockResolvedValue({
    password: JSON.stringify({
      access_token: 'test_token',
      refresh_token: 'test_refresh',
      expires_at: Date.now() + 3600000
    })
  }),
  resetInternetCredentials: jest.fn().mockResolvedValue(true),
  ACCESS_CONTROL: {
    BIOMETRY_CURRENT_SET: 'BiometryCurrentSet',
    DEVICE_PASSCODE: 'DevicePasscode'
  }
}));

describe('OAuth2 Integration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('authorization flow completes successfully', async () => {
    const tokens = await OAuth2Service.authorize(['read:profile']);
    
    expect(tokens).toHaveProperty('access_token');
    expect(tokens).toHaveProperty('refresh_token');
  });

  test('tokens are stored securely', async () => {
    const mockTokens = {
      access_token: 'test_token',
      refresh_token: 'test_refresh',
      expires_in: 3600,
      scope: 'read:profile'
    };

    await TokenManager.storeTokens(mockTokens);
    const storedTokens = await TokenManager.getStoredTokens();
    
    expect(storedTokens.access_token).toBe('test_token');
  });

  test('PKCE parameters are generated correctly', () => {
    const { generateCodeVerifier, generateCodeChallenge } = require('../src/utils/pkce');
    
    const verifier = generateCodeVerifier();
    expect(verifier).toHaveLength(43);
    expect(verifier).toMatch(/^[A-Za-z0-9_-]+$/);
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

### iOS App Store Configuration

1. **Configure App Transport Security** (`ios/YourApp/Info.plist`):

```xml
<key>NSAppTransportSecurity</key>
<dict>
    <key>NSExceptionDomains</key>
    <dict>
        <key>your-sbd-instance.com</key>
        <dict>
            <key>NSExceptionRequiresForwardSecrecy</key>
            <false/>
            <key>NSExceptionMinimumTLSVersion</key>
            <string>TLSv1.2</string>
            <key>NSIncludesSubdomains</key>
            <true/>
        </dict>
    </dict>
</dict>
```

2. **Configure privacy permissions**:

```xml
<key>NSFaceIDUsageDescription</key>
<string>Use Face ID to securely access your authentication tokens</string>
```

### Android Play Store Configuration

1. **Configure network security** (`android/app/src/main/res/xml/network_security_config.xml`):

```xml
<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <domain-config cleartextTrafficPermitted="false">
        <domain includeSubdomains="true">your-sbd-instance.com</domain>
        <pin-set expiration="2025-12-31">
            <pin digest="SHA-256">YOUR_CERTIFICATE_PIN_HERE</pin>
        </pin-set>
    </domain-config>
</network-security-config>
```

2. **Update AndroidManifest.xml**:

```xml
<application
    android:networkSecurityConfig="@xml/network_security_config"
    android:usesCleartextTraffic="false">
```

## Troubleshooting

### Common Issues

1. **Deep link not working**
   - Verify URL scheme configuration in both iOS and Android
   - Check that the redirect URI matches exactly

2. **Biometric authentication fails**
   - Ensure device has biometric authentication set up
   - Check permissions in Info.plist (iOS) and AndroidManifest.xml (Android)

3. **Token storage issues**
   - Verify Keychain/Keystore permissions
   - Check for device lock screen configuration

### Debug Mode

Enable debug logging:

```javascript
// Add to your App.js
if (__DEV__) {
  console.log('OAuth2 Debug Mode Enabled');
  global.XMLHttpRequest = global.originalXMLHttpRequest || global.XMLHttpRequest;
}
```

## Support

For additional help:
- Check the [OAuth2 Integration Guide](../../OAUTH2_INTEGRATION.md)
- Review the [API Reference](../../OAUTH2_API_REFERENCE.md)
- See other examples in the [examples directory](../)
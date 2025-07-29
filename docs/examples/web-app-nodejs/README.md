# Node.js Express OAuth2 Integration Example

This example demonstrates how to integrate a Node.js Express web application with the Second Brain Database OAuth2 provider.

## Features

- Complete OAuth2 authorization code flow with PKCE
- Express.js web server with session management
- Token refresh and automatic renewal
- Secure token storage using encrypted sessions
- Error handling and user feedback
- API integration examples
- Logout and token revocation

## Prerequisites

- Node.js 18+ and npm
- Registered OAuth2 client in Second Brain Database
- HTTPS setup for production (required for OAuth2)

## Installation

1. Clone or download this example
2. Install dependencies:

```bash
npm install
```

3. Configure your environment (see Configuration section)
4. Start the development server:

```bash
npm start
```

## Configuration

Create a `.env` file in the project root:

```env
# OAuth2 Configuration
OAUTH2_CLIENT_ID=your_client_id_here
OAUTH2_CLIENT_SECRET=your_client_secret_here
OAUTH2_REDIRECT_URI=http://localhost:3000/auth/callback
OAUTH2_AUTHORIZATION_URL=https://your-sbd-instance.com/oauth2/authorize
OAUTH2_TOKEN_URL=https://your-sbd-instance.com/oauth2/token
OAUTH2_API_BASE_URL=https://your-sbd-instance.com

# Application Configuration
SESSION_SECRET=your_session_secret_here
PORT=3000
NODE_ENV=development

# Security Configuration
COOKIE_SECURE=false  # Set to true in production with HTTPS
COOKIE_SAME_SITE=lax
```

## Project Structure

```
web-app-nodejs/
├── package.json
├── .env.example
├── README.md
├── app.js                 # Main application file
├── routes/
│   ├── auth.js           # OAuth2 authentication routes
│   ├── api.js            # API integration examples
│   └── index.js          # Home page routes
├── middleware/
│   ├── auth.js           # Authentication middleware
│   └── oauth2.js         # OAuth2 helper functions
├── public/
│   ├── css/
│   │   └── style.css     # Basic styling
│   └── js/
│       └── app.js        # Client-side JavaScript
└── views/
    ├── layout.ejs        # Base template
    ├── index.ejs         # Home page
    ├── login.ejs         # Login page
    ├── profile.ejs       # User profile page
    └── error.ejs         # Error page
```

## Usage

1. **Start the application**:
   ```bash
   npm start
   ```

2. **Navigate to the application**:
   Open http://localhost:3000 in your browser

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

### OAuth2 Flow Implementation

The OAuth2 flow is implemented in `routes/auth.js`:

```javascript
// Initiate OAuth2 authorization
router.get('/login', async (req, res) => {
  try {
    const state = crypto.randomBytes(32).toString('hex');
    const codeVerifier = generateCodeVerifier();
    const codeChallenge = generateCodeChallenge(codeVerifier);
    
    // Store PKCE parameters in session
    req.session.oauth2State = state;
    req.session.codeVerifier = codeVerifier;
    
    const authUrl = new URL(process.env.OAUTH2_AUTHORIZATION_URL);
    authUrl.searchParams.set('response_type', 'code');
    authUrl.searchParams.set('client_id', process.env.OAUTH2_CLIENT_ID);
    authUrl.searchParams.set('redirect_uri', process.env.OAUTH2_REDIRECT_URI);
    authUrl.searchParams.set('scope', 'read:profile write:data');
    authUrl.searchParams.set('state', state);
    authUrl.searchParams.set('code_challenge', codeChallenge);
    authUrl.searchParams.set('code_challenge_method', 'S256');
    
    res.redirect(authUrl.toString());
  } catch (error) {
    console.error('OAuth2 login error:', error);
    res.redirect('/error?message=Failed to initiate login');
  }
});

// Handle OAuth2 callback
router.get('/callback', async (req, res) => {
  try {
    const { code, state, error } = req.query;
    
    // Handle authorization errors
    if (error) {
      console.error('OAuth2 authorization error:', error);
      return res.redirect('/error?message=Authorization failed');
    }
    
    // Validate state parameter (CSRF protection)
    if (!state || state !== req.session.oauth2State) {
      console.error('Invalid state parameter');
      return res.redirect('/error?message=Invalid state parameter');
    }
    
    // Exchange authorization code for tokens
    const tokenResponse = await exchangeCodeForTokens(
      code,
      req.session.codeVerifier
    );
    
    // Store tokens securely in session
    req.session.accessToken = tokenResponse.access_token;
    req.session.refreshToken = tokenResponse.refresh_token;
    req.session.tokenExpiry = Date.now() + (tokenResponse.expires_in * 1000);
    req.session.scopes = tokenResponse.scope.split(' ');
    
    // Clean up temporary OAuth2 data
    delete req.session.oauth2State;
    delete req.session.codeVerifier;
    
    res.redirect('/profile');
  } catch (error) {
    console.error('OAuth2 callback error:', error);
    res.redirect('/error?message=Failed to complete authentication');
  }
});
```

### Token Management

Token refresh is handled automatically in `middleware/auth.js`:

```javascript
async function ensureValidToken(req, res, next) {
  try {
    if (!req.session.accessToken) {
      return res.redirect('/auth/login');
    }
    
    // Check if token is expired or will expire soon (5 minutes buffer)
    const tokenExpiry = req.session.tokenExpiry || 0;
    const fiveMinutesFromNow = Date.now() + (5 * 60 * 1000);
    
    if (tokenExpiry < fiveMinutesFromNow && req.session.refreshToken) {
      console.log('Token expired or expiring soon, refreshing...');
      
      try {
        const newTokens = await refreshAccessToken(req.session.refreshToken);
        
        // Update session with new tokens
        req.session.accessToken = newTokens.access_token;
        req.session.refreshToken = newTokens.refresh_token;
        req.session.tokenExpiry = Date.now() + (newTokens.expires_in * 1000);
        req.session.scopes = newTokens.scope.split(' ');
        
        console.log('Token refreshed successfully');
      } catch (refreshError) {
        console.error('Token refresh failed:', refreshError);
        // Clear invalid tokens and redirect to login
        req.session.destroy();
        return res.redirect('/auth/login');
      }
    }
    
    next();
  } catch (error) {
    console.error('Token validation error:', error);
    res.redirect('/auth/login');
  }
}
```

### API Integration

Making authenticated API calls in `routes/api.js`:

```javascript
// Get user profile
router.get('/profile', ensureValidToken, async (req, res) => {
  try {
    const response = await fetch(`${process.env.OAUTH2_API_BASE_URL}/api/user/profile`, {
      headers: {
        'Authorization': `Bearer ${req.session.accessToken}`,
        'Content-Type': 'application/json'
      }
    });
    
    if (!response.ok) {
      throw new Error(`API request failed: ${response.status} ${response.statusText}`);
    }
    
    const profile = await response.json();
    res.json(profile);
  } catch (error) {
    console.error('Profile API error:', error);
    res.status(500).json({ error: 'Failed to fetch profile' });
  }
});

// Update user data (requires write:data scope)
router.post('/data', ensureValidToken, requireScope('write:data'), async (req, res) => {
  try {
    const response = await fetch(`${process.env.OAUTH2_API_BASE_URL}/api/user/data`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${req.session.accessToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(req.body)
    });
    
    if (!response.ok) {
      throw new Error(`API request failed: ${response.status} ${response.statusText}`);
    }
    
    const result = await response.json();
    res.json(result);
  } catch (error) {
    console.error('Data API error:', error);
    res.status(500).json({ error: 'Failed to update data' });
  }
});
```

## Security Features

### PKCE Implementation

```javascript
function generateCodeVerifier() {
  return crypto.randomBytes(32).toString('base64url');
}

function generateCodeChallenge(verifier) {
  return crypto.createHash('sha256').update(verifier).digest('base64url');
}
```

### State Parameter Validation

```javascript
// Generate cryptographically secure state
const state = crypto.randomBytes(32).toString('hex');

// Validate state in callback
if (!state || state !== req.session.oauth2State) {
  throw new Error('Invalid state parameter');
}
```

### Secure Session Configuration

```javascript
app.use(session({
  secret: process.env.SESSION_SECRET,
  resave: false,
  saveUninitialized: false,
  cookie: {
    secure: process.env.NODE_ENV === 'production', // HTTPS only in production
    httpOnly: true, // Prevent XSS
    maxAge: 24 * 60 * 60 * 1000, // 24 hours
    sameSite: 'lax' // CSRF protection
  },
  store: new MongoStore({ // Use persistent session store in production
    mongoUrl: process.env.MONGODB_URL || 'mongodb://localhost:27017/sessions'
  })
}));
```

## Error Handling

The application includes comprehensive error handling:

```javascript
// Global error handler
app.use((error, req, res, next) => {
  console.error('Application error:', error);
  
  // Don't expose internal errors in production
  const message = process.env.NODE_ENV === 'production' 
    ? 'An internal error occurred' 
    : error.message;
    
  res.status(500).render('error', { 
    title: 'Error',
    message: message,
    error: process.env.NODE_ENV === 'development' ? error : {}
  });
});

// OAuth2 specific error handling
function handleOAuth2Error(error, req, res) {
  console.error('OAuth2 error:', error);
  
  let message = 'Authentication failed';
  let redirectUrl = '/';
  
  if (error.error === 'access_denied') {
    message = 'Access was denied. Please try again.';
  } else if (error.error === 'invalid_client') {
    message = 'Invalid client configuration. Please contact support.';
  } else if (error.error === 'server_error') {
    message = 'Server error occurred. Please try again later.';
  }
  
  res.redirect(`/error?message=${encodeURIComponent(message)}`);
}
```

## Testing

Run the test suite:

```bash
npm test
```

Test OAuth2 flow manually:
1. Start the application
2. Navigate to `/auth/login`
3. Complete the OAuth2 flow
4. Verify token storage and API access
5. Test token refresh by waiting for expiration
6. Test logout and token revocation

## Production Deployment

### Environment Variables

```env
NODE_ENV=production
OAUTH2_CLIENT_ID=your_production_client_id
OAUTH2_CLIENT_SECRET=your_production_client_secret
OAUTH2_REDIRECT_URI=https://yourdomain.com/auth/callback
OAUTH2_AUTHORIZATION_URL=https://sbd-instance.com/oauth2/authorize
OAUTH2_TOKEN_URL=https://sbd-instance.com/oauth2/token
OAUTH2_API_BASE_URL=https://sbd-instance.com
SESSION_SECRET=your_strong_session_secret
MONGODB_URL=mongodb://your-mongo-instance/sessions
COOKIE_SECURE=true
PORT=3000
```

### HTTPS Configuration

Use a reverse proxy like Nginx:

```nginx
server {
    listen 443 ssl http2;
    server_name yourdomain.com;
    
    ssl_certificate /path/to/certificate.crt;
    ssl_certificate_key /path/to/private.key;
    
    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Docker Deployment

```dockerfile
FROM node:18-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci --only=production

COPY . .

EXPOSE 3000

USER node

CMD ["npm", "start"]
```

## Troubleshooting

### Common Issues

1. **"Invalid redirect URI" error**
   - Ensure the redirect URI in your `.env` matches exactly what's registered
   - Check for trailing slashes and protocol (http vs https)

2. **"Invalid client" error**
   - Verify your client ID and secret are correct
   - Ensure the client is active in the OAuth2 provider

3. **Token refresh failures**
   - Check that refresh tokens are being stored properly
   - Verify the token endpoint URL is correct

4. **CORS errors**
   - Ensure your application domain is properly configured
   - Check that you're not making cross-origin requests from the browser

### Debug Mode

Enable debug logging:

```env
DEBUG=oauth2:*
NODE_ENV=development
```

## Support

For additional help:
- Check the [OAuth2 Integration Guide](../../OAUTH2_INTEGRATION.md)
- Review the [API Reference](../../OAUTH2_API_REFERENCE.md)
- See other examples in the [examples directory](../)
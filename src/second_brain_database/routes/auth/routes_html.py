"""
HTML page rendering for authentication routes (password reset, etc).
"""

from typing import List

from fastapi import Request
from fastapi.responses import HTMLResponse

from second_brain_database.config import settings
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[Auth Routes HTML]")

# Constants
TURNSTILE_SITEKEY_PLACEHOLDER: str = "__TURNSTILE_SITEKEY__"


def render_reset_password_page(token: str) -> HTMLResponse:
    """
    Serve the password reset HTML page, injecting the Turnstile sitekey and token.
    Args:
        token (str): The password reset token to inject into the page.
    Returns:
        HTMLResponse: The rendered HTML page.
    Side-effects:
        Logs errors if sitekey is missing or invalid.
    """
    html = """
    <!DOCTYPE html>
   <!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Reset Password</title>
    <link href="https://fonts.googleapis.com/css?family=Roboto:400,700&display=swap" rel="stylesheet">
    <script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>
    <style>
        :root {
            --primary: #3a86ff;
            --primary-hover: #265dbe;
            --background: #f6f8fa;
            --foreground: #ffffff;
            --text-main: #22223b;
            --text-sub: #4a4e69;
            --border-color: #c9c9c9;
            --error: #d90429;
            --success: #06d6a0;
        }
        * { box-sizing: border-box; }
        body {
            margin: 0;
            background-color: var(--background);
            font-family: 'Roboto', sans-serif;
            display: flex;
            align-items: center;
            justify-content: center;
            height: 100vh;
        }
        .container {
            background-color: var(--foreground);
            padding: 2.5rem 2rem;
            border-radius: 12px;
            box-shadow: 0 4px 24px rgba(0, 0, 0, 0.08);
            width: 100%;
            max-width: 420px;
        }
        h2 {
            margin-bottom: 1.5rem;
            color: var(--text-main);
            font-size: 1.5rem;
            font-weight: 700;
            text-align: center;
        }
        label {
            display: block;
            margin-bottom: 0.5rem;
            color: var(--text-sub);
            font-weight: 500;
        }
        input[type="password"] {
            width: 100%;
            padding: 0.75rem;
            margin-bottom: 1.25rem;
            border: 1px solid var(--border-color);
            border-radius: 6px;
            font-size: 1rem;
        }
        button {
            width: 100%;
            padding: 0.75rem;
            background-color: var(--primary);
            color: #fff;
            border: none;
            border-radius: 6px;
            font-size: 1.1rem;
            font-weight: 700;
            cursor: pointer;
            transition: background-color 0.2s ease-in-out;
        }
        button:hover { background-color: var(--primary-hover); }
        .msg {
            margin-top: 1rem;
            text-align: center;
            font-size: 0.95rem;
        }
        .error { color: var(--error); }
        .success { color: var(--success); }
        .cf-turnstile { margin-bottom: 1.25rem; }
    </style>
</head>
<body>
    <main class="container" role="main">
        <h2>Reset Your Password</h2>
        <form id="resetForm" aria-describedby="msg">
            <label for="new_password">New Password</label>
            <input type="password" id="new_password" name="new_password" required minlength="8" autocomplete="new-password" />
            <label for="confirm_password">Confirm Password</label>
            <input type="password" id="confirm_password" name="confirm_password" required minlength="8" autocomplete="new-password" />
            <div class="cf-turnstile" data-sitekey="__TURNSTILE_SITEKEY__" data-theme="light"></div>
            <button type="submit" aria-label="Submit new password">Reset Password</button>
        </form>
        <div class="msg" id="msg" role="alert" aria-live="polite"></div>
    </main>
    <script>
        const RESET_TOKEN = window.RESET_TOKEN || new URLSearchParams(window.location.search).get('token');
        const form = document.getElementById('resetForm');
        const msg = document.getElementById('msg');
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            msg.textContent = '';
            msg.className = 'msg';
            const newPassword = form.new_password.value.trim();
            const confirmPassword = form.confirm_password.value.trim();
            if (newPassword !== confirmPassword) {
                msg.textContent = 'Passwords do not match.';
                msg.classList.add('error');
                return;
            }
            const turnstileTokenInput = document.querySelector('input[name="cf-turnstile-response"]');
            const turnstileToken = turnstileTokenInput ? turnstileTokenInput.value : '';
            if (!turnstileToken) {
                msg.textContent = 'Please complete the CAPTCHA.';
                msg.classList.add('error');
                return;
            }
            try {
                const response = await fetch('/auth/reset-password', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        token: RESET_TOKEN,
                        new_password: newPassword,
                        turnstile_token: turnstileToken
                    })
                });
                const data = await response.json();
                if (response.ok) {
                    msg.textContent = data.message || 'Password reset successful!';
                    msg.classList.add('success');
                    form.reset();
                } else {
                    msg.textContent = data.detail || 'Error resetting password.';
                    msg.classList.add('error');
                }
            } catch (error) {
                msg.textContent = 'A network error occurred. Please try again.';
                msg.classList.add('error');
            }
        });
    </script>
</body>
</html>
    """
    try:
        sitekey = settings.TURNSTILE_SITEKEY
        if hasattr(sitekey, "get_secret_value"):
            sitekey = sitekey.get_secret_value()
        if not sitekey or not isinstance(sitekey, str):
            logger.error("Turnstile sitekey missing or invalid for password reset HTML.")
            sitekey = ""
        html = html.replace(TURNSTILE_SITEKEY_PLACEHOLDER, sitekey)
    except AttributeError as e:
        logger.error("Error accessing Turnstile sitekey: %s", e, exc_info=True)
        html = html.replace(TURNSTILE_SITEKEY_PLACEHOLDER, "")
    return HTMLResponse(content=html)


def render_trusted_ip_lockdown_email(code: str, action: str, trusted_ips: List[str]) -> str:
    """
    Render an HTML email for trusted IP lockdown confirmation.
    Args:
        code (str): The confirmation code.
        action (str): 'enable' or 'disable'.
        trusted_ips (List[str]): List of IPs allowed to confirm.
    Returns:
        str: HTML content for the email.
    """
    ip_list_html = "".join(f"<li>{ip}</li>" for ip in trusted_ips)
    return f"""
    <html>
    <body>
        <h2>Trusted IP Lockdown {action.title()} Confirmation</h2>
        <p>Your confirmation code to <b>{action}</b> trusted IP lockdown is: <b>{code}</b></p>
        <p>This code expires in 15 minutes. If you did not request this, you can ignore this email.</p>
        <p><b>You must confirm from one of these IPs:</b></p>
        <ul>{ip_list_html}</ul>
    </body>
    </html>
    """


def render_login_page() -> HTMLResponse:
    """
    Serve the secure login HTML page with dual authentication support.
    
    Provides a browser-based interface for users to authenticate using either:
    - Traditional username/password authentication
    - WebAuthn passwordless authentication (if credentials exist)
    
    Returns:
        HTMLResponse: The rendered HTML page for secure login
    """
    html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - Second Brain Database</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        
        .login-container {{
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
            padding: 40px;
            width: 100%;
            max-width: 400px;
            position: relative;
        }}
        
        .logo {{
            text-align: center;
            margin-bottom: 30px;
        }}
        
        .logo h1 {{
            color: #333;
            font-size: 28px;
            font-weight: 600;
            margin-bottom: 8px;
        }}
        
        .logo p {{
            color: #666;
            font-size: 14px;
        }}
        
        .auth-tabs {{
            display: flex;
            margin-bottom: 30px;
            border-bottom: 1px solid #e1e5e9;
        }}
        
        .auth-tab {{
            flex: 1;
            padding: 12px;
            text-align: center;
            cursor: pointer;
            border: none;
            background: none;
            color: #666;
            font-size: 14px;
            font-weight: 500;
            transition: all 0.2s;
            border-bottom: 2px solid transparent;
        }}
        
        .auth-tab.active {{
            color: #667eea;
            border-bottom-color: #667eea;
        }}
        
        .auth-form {{
            display: none;
        }}
        
        .auth-form.active {{
            display: block;
        }}
        
        .form-group {{
            margin-bottom: 20px;
        }}
        
        .form-group label {{
            display: block;
            margin-bottom: 6px;
            color: #333;
            font-weight: 500;
            font-size: 14px;
        }}
        
        .form-group input {{
            width: 100%;
            padding: 12px 16px;
            border: 2px solid #e1e5e9;
            border-radius: 8px;
            font-size: 16px;
            transition: border-color 0.2s;
        }}
        
        .form-group input:focus {{
            outline: none;
            border-color: #667eea;
        }}
        
        .btn {{
            width: 100%;
            padding: 14px;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            margin-bottom: 12px;
        }}
        
        .btn-primary {{
            background: #667eea;
            color: white;
        }}
        
        .btn-primary:hover:not(:disabled) {{
            background: #5a6fd8;
            transform: translateY(-1px);
        }}
        
        .btn-secondary {{
            background: #f8f9fa;
            color: #333;
            border: 2px solid #e1e5e9;
        }}
        
        .btn-secondary:hover:not(:disabled) {{
            background: #e9ecef;
        }}
        
        .btn:disabled {{
            opacity: 0.6;
            cursor: not-allowed;
        }}
        
        .webauthn-info {{
            text-align: center;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 8px;
            margin-bottom: 20px;
        }}
        
        .webauthn-info.not-supported {{
            background: #fff3cd;
            border: 1px solid #ffeaa7;
        }}
        
        .webauthn-info p {{
            margin-bottom: 12px;
            color: #666;
            font-size: 14px;
        }}
        
        .status-message {{
            padding: 12px 16px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 14px;
            font-weight: 500;
        }}
        
        .status-success {{
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }}
        
        .status-error {{
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }}
        
        .status-info {{
            background: #d1ecf1;
            color: #0c5460;
            border: 1px solid #bee5eb;
        }}
        
        .hidden {{
            display: none !important;
        }}
        
        .loading {{
            display: inline-block;
            width: 16px;
            height: 16px;
            border: 2px solid #ffffff;
            border-radius: 50%;
            border-top-color: transparent;
            animation: spin 1s ease-in-out infinite;
            margin-right: 8px;
        }}
        
        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}
        
        .links {{
            text-align: center;
            margin-top: 20px;
            padding-top: 20px;
            border-top: 1px solid #e1e5e9;
        }}
        
        .links a {{
            color: #667eea;
            text-decoration: none;
            font-size: 14px;
            margin: 0 10px;
        }}
        
        .links a:hover {{
            text-decoration: underline;
        }}
        
        @media (max-width: 480px) {{
            .login-container {{
                padding: 30px 20px;
            }}
            
            .logo h1 {{
                font-size: 24px;
            }}
        }}
    </style>
</head>
<body>
    <div class="login-container">
        <div class="logo">
            <h1>Second Brain</h1>
            <p>Secure Authentication</p>
        </div>
        
        <div class="auth-tabs">
            <button class="auth-tab active" data-tab="password">Password</button>
            <button class="auth-tab" data-tab="passkey">Passkey</button>
        </div>
        
        <div id="status-messages"></div>
        
        <!-- Password Authentication Form -->
        <form id="password-form" class="auth-form active">
            <input type="hidden" name="csrf_token" value="">
            <input type="hidden" name="redirect_uri" value="">
            <div class="form-group">
                <label for="identifier">Username or Email</label>
                <input type="text" id="identifier" name="identifier" required autocomplete="username">
            </div>
            
            <div class="form-group">
                <label for="password">Password</label>
                <input type="password" id="password" name="password" required autocomplete="current-password">
            </div>
            
            <button type="submit" class="btn btn-primary" id="password-login-btn">
                Sign In
            </button>
        </form>
        
        <!-- WebAuthn Authentication Form -->
        <div id="passkey-form" class="auth-form">
            <div id="webauthn-support-check">
                <div id="webauthn-supported" class="webauthn-info hidden">
                    <p>🔐 Use your biometric or security key to sign in securely</p>
                </div>
                <div id="webauthn-not-supported" class="webauthn-info not-supported hidden">
                    <p>⚠️ Your browser doesn't support passkeys</p>
                    <p>Please use a modern browser or switch to password authentication</p>
                </div>
            </div>
            
            <div id="passkey-login-section" class="hidden">
                <div class="form-group">
                    <label for="passkey-identifier">Username or Email</label>
                    <input type="text" id="passkey-identifier" name="passkey-identifier" required autocomplete="username webauthn">
                </div>
                
                <button type="button" class="btn btn-primary" id="passkey-login-btn">
                    🔐 Sign In with Passkey
                </button>
            </div>
        </div>
        
        <div class="links">
            <a href="/auth/register">Create Account</a>
            <a href="/auth/forgot-password">Forgot Password?</a>
        </div>
    </div>

    <script>
        class SecureLogin {
            constructor() {
                this.apiBase = '/auth';
                this.currentTab = 'password';
                this.init();
            }
            
            init() {
                this.bindEvents();
                this.checkWebAuthnSupport();
                this.setupTabSwitching();
            }
            
            bindEvents() {
                // Password form submission
                document.getElementById('password-form').addEventListener('submit', this.handlePasswordLogin.bind(this));
                
                // Passkey login button
                document.getElementById('passkey-login-btn').addEventListener('click', this.handlePasskeyLogin.bind(this));
            }
            
            setupTabSwitching() {
                const tabs = document.querySelectorAll('.auth-tab');
                const forms = document.querySelectorAll('.auth-form');
                
                tabs.forEach(tab => {
                    tab.addEventListener('click', () => {
                        const tabType = tab.dataset.tab;
                        
                        // Update active tab
                        tabs.forEach(t => t.classList.remove('active'));
                        tab.classList.add('active');
                        
                        // Update active form
                        forms.forEach(f => f.classList.remove('active'));
                        document.getElementById(`${tabType}-form`).classList.add('active');
                        
                        this.currentTab = tabType;
                        this.clearMessages();
                    });
                });
            }
            
            checkWebAuthnSupport() {
                const supported = document.getElementById('webauthn-supported');
                const notSupported = document.getElementById('webauthn-not-supported');
                const loginSection = document.getElementById('passkey-login-section');
                
                if (window.PublicKeyCredential && typeof window.PublicKeyCredential.get === 'function') {
                    supported.classList.remove('hidden');
                    loginSection.classList.remove('hidden');
                } else {
                    notSupported.classList.remove('hidden');
                }
            }
            
            async handlePasswordLogin(event) {
                event.preventDefault();
                
                const identifier = document.getElementById('identifier').value;
                const password = document.getElementById('password').value;
                const csrf_token = document.querySelector('input[name="csrf_token"]')?.value || '';
                const redirect_uri = document.querySelector('input[name="redirect_uri"]')?.value || '';
                const btn = document.getElementById('password-login-btn');
                
                if (!identifier || !password) {
                    this.showMessage('Please enter both username/email and password', 'error');
                    return;
                }
                
                this.setLoading(btn, true);
                this.clearMessages();
                
                try {
                    // Always send identifier, password, csrf_token, redirect_uri
                    const loginData = {
                        identifier: identifier,
                        password: password,
                        csrf_token: csrf_token,
                        redirect_uri: redirect_uri
                    };
                    
                    const formData = new URLSearchParams();
                    for (const key in loginData) {
                        if (loginData[key] !== undefined && loginData[key] !== null) {
                            formData.append(key, loginData[key]);
                        }
                    }
                    
                    const response = await fetch(`${this.apiBase}/login`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/x-www-form-urlencoded'
                        },
                        body: formData
                    });
                    
                    const data = await response.json();
                    
                    if (response.ok) {
                        // Store token and redirect
                        localStorage.setItem('access_token', data.access_token);
                        this.showMessage('Login successful! Redirecting...', 'success');
                        
                        // Redirect to setup page or dashboard
                        setTimeout(() => {
                            window.location.href = '/auth/webauthn/setup';
                        }, 1000);
                        
                    } else if (response.status === 422 && data.two_fa_required) {
                        // Handle 2FA requirement
                        this.handle2FARequired(data);
                        
                    } else if (response.status === 403 && data.detail === 'Email not verified') {
                        this.showMessage('Please verify your email address before logging in', 'error');
                        
                    } else {
                        this.showMessage(data.detail || data.message || 'Login failed', 'error');
                    }
                    
                } catch (error) {
                    console.error('Login error:', error);
                    this.showMessage('Network error. Please try again.', 'error');
                } finally {
                    this.setLoading(btn, false);
                }
            }
            
            async handlePasskeyLogin() {
                const identifier = document.getElementById('passkey-identifier').value;
                const btn = document.getElementById('passkey-login-btn');
                
                if (!identifier) {
                    this.showMessage('Please enter your username or email', 'error');
                    return;
                }
                
                this.setLoading(btn, true);
                this.clearMessages();
                
                try {
                    // Begin WebAuthn authentication
                    const isEmail = identifier.includes('@');
                    const beginData = {};
                    
                    if (isEmail) {
                        beginData.email = identifier;
                    } else {
                        beginData.username = identifier;
                    }
                    
                    const beginResponse = await fetch(`${this.apiBase}/webauthn/authenticate/begin`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify(beginData)
                    });
                    
                    if (!beginResponse.ok) {
                        const errorData = await beginResponse.json();
                        throw new Error(errorData.detail || 'Failed to start passkey authentication');
                    }
                    
                    const options = await beginResponse.json();
                    
                    // Convert base64url strings to ArrayBuffers
                    options.publicKey.challenge = this.base64urlToArrayBuffer(options.publicKey.challenge);
                    
                    if (options.publicKey.allowCredentials) {
                        options.publicKey.allowCredentials = options.publicKey.allowCredentials.map(cred => ({
                            ...cred,
                            id: this.base64urlToArrayBuffer(cred.id)
                        }));
                    }
                    
                    // Get credential from authenticator
                    const credential = await navigator.credentials.get(options);
                    
                    if (!credential) {
                        throw new Error('No credential received from authenticator');
                    }
                    
                    // Complete authentication
                    const completeResponse = await fetch(`${this.apiBase}/webauthn/authenticate/complete`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            id: credential.id,
                            rawId: this.arrayBufferToBase64url(credential.rawId),
                            response: {
                                authenticatorData: this.arrayBufferToBase64url(credential.response.authenticatorData),
                                clientDataJSON: this.arrayBufferToBase64url(credential.response.clientDataJSON),
                                signature: this.arrayBufferToBase64url(credential.response.signature),
                                userHandle: credential.response.userHandle ? this.arrayBufferToBase64url(credential.response.userHandle) : null
                            },
                            type: credential.type
                        })
                    });
                    
                    if (!completeResponse.ok) {
                        const errorData = await completeResponse.json();
                        throw new Error(errorData.detail || 'Passkey authentication failed');
                    }
                    
                    const authData = await completeResponse.json();
                    
                    // Store token and redirect
                    localStorage.setItem('access_token', authData.access_token);
                    this.showMessage('Passkey authentication successful! Redirecting...', 'success');
                    
                    setTimeout(() => {
                        window.location.href = '/auth/webauthn/setup';
                    }, 1000);
                    
                } catch (error) {
                    console.error('Passkey authentication error:', error);
                    
                    if (error.name === 'NotAllowedError') {
                        this.showMessage('Passkey authentication was cancelled or failed', 'error');
                    } else if (error.name === 'NotSupportedError') {
                        this.showMessage('Passkey authentication is not supported on this device', 'error');
                    } else {
                        this.showMessage(error.message || 'Passkey authentication failed', 'error');
                    }
                } finally {
                    this.setLoading(btn, false);
                }
            }
            
            handle2FARequired(data) {
                // For now, show a message. In a full implementation, you'd show 2FA input
                this.showMessage('2FA authentication required. Please use the API directly for 2FA login.', 'info');
            }
            
            setLoading(button, loading) {
                if (loading) {
                    button.disabled = true;
                    const originalText = button.textContent;
                    button.dataset.originalText = originalText;
                    button.innerHTML = '<span class="loading"></span>Signing in...';
                } else {
                    button.disabled = false;
                    button.textContent = button.dataset.originalText || button.textContent;
                }
            }
            
            showMessage(message, type) {
                const container = document.getElementById('status-messages');
                const messageDiv = document.createElement('div');
                messageDiv.className = `status-message status-${type}`;
                messageDiv.textContent = message;
                
                container.appendChild(messageDiv);
                
                // Auto-remove success messages
                if (type === 'success') {
                    setTimeout(() => {
                        messageDiv.remove();
                    }, 5000);
                }
            }
            
            clearMessages() {
                const container = document.getElementById('status-messages');
                container.innerHTML = '';
            }
            
            base64urlToArrayBuffer(base64url) {
                const padding = '='.repeat((4 - base64url.length % 4) % 4);
                const base64 = (base64url + padding).replace(/-/g, '+').replace(/_/g, '/');
                const rawData = window.atob(base64);
                const outputArray = new Uint8Array(rawData.length);
                for (let i = 0; i < rawData.length; ++i) {
                    outputArray[i] = rawData.charCodeAt(i);
                }
                return outputArray.buffer;
            }
            
            arrayBufferToBase64url(buffer) {
                const bytes = new Uint8Array(buffer);
                let str = '';
                for (let i = 0; i < bytes.byteLength; i++) {
                    str += String.fromCharCode(bytes[i]);
                }
                return window.btoa(str).replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');
            }
        }
        
        // Initialize when DOM is loaded
        document.addEventListener('DOMContentLoaded', () => {
            // Set CSRF and redirect_uri hidden fields if present in URL or page
            const urlParams = new URLSearchParams(window.location.search);
            const csrfToken = document.querySelector('input[name="csrf_token"]');
            const redirectInput = document.querySelector('input[name="redirect_uri"]');
            if (csrfToken && window.csrf_token) {
                csrfToken.value = window.csrf_token;
            }
            if (redirectInput && urlParams.get('redirect_uri')) {
                redirectInput.value = urlParams.get('redirect_uri');
            }
            new SecureLogin();
        });
    </script>
</body>
</html>
    """
    
    return HTMLResponse(content=html)



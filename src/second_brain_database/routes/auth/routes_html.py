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


def render_trusted_user_agent_lockdown_email(code: str, action: str, trusted_user_agents: List[str]) -> str:
    """
    Render an HTML email for User Agent lockdown confirmation.
    Args:
        code (str): The confirmation code.
        action (str): 'enable' or 'disable'.
        trusted_user_agents (List[str]): List of User Agents allowed to confirm.
    Returns:
        str: HTML content for the email.
    """
    user_agent_list_html = "".join(f"<li>{user_agent}</li>" for user_agent in trusted_user_agents)
    return f"""
    <html>
    <body>
        <h2>User Agent Lockdown {action.title()} Confirmation</h2>
        <p>Your confirmation code to <b>{action}</b> User Agent lockdown is: <b>{code}</b></p>
        <p>This code expires in 15 minutes. If you did not request this, you can ignore this email.</p>
        <p><b>You must confirm from one of these User Agents:</b></p>
        <ul>{user_agent_list_html}</ul>
    </body>
    </html>
    """


def render_blocked_ip_notification_email(
    attempted_ip: str, 
    trusted_ips: List[str], 
    endpoint: str, 
    timestamp: str,
    allow_once_token: str = None,
    add_to_trusted_token: str = None
) -> str:
    """
    Render an HTML email for blocked IP access notification with action buttons.
    Args:
        attempted_ip (str): The IP address that was blocked.
        trusted_ips (List[str]): List of currently trusted IP addresses.
        endpoint (str): The endpoint that was accessed.
        timestamp (str): The timestamp of the blocked attempt.
    Returns:
        str: HTML content for the email.
    """
    trusted_ips_html = "".join(f"<li style='margin-bottom: 5px; font-family: monospace; font-size: 14px;'>{ip}</li>" for ip in trusted_ips)
    
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Blocked Access Attempt - IP Lockdown</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f8f9fa;
            }}
            .container {{
                background-color: #ffffff;
                border-radius: 8px;
                padding: 30px;
                box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
            }}
            .header {{
                text-align: center;
                margin-bottom: 30px;
                padding-bottom: 20px;
                border-bottom: 2px solid #e9ecef;
            }}
            .header h1 {{
                color: #dc3545;
                margin: 0;
                font-size: 24px;
            }}
            .alert {{
                background-color: #fff3cd;
                border: 1px solid #ffeaa7;
                border-radius: 6px;
                padding: 15px;
                margin-bottom: 20px;
            }}
            .alert-icon {{
                font-size: 20px;
                margin-right: 10px;
            }}
            .details {{
                background-color: #f8f9fa;
                border-radius: 6px;
                padding: 20px;
                margin: 20px 0;
            }}
            .details h3 {{
                margin-top: 0;
                color: #495057;
                font-size: 16px;
            }}
            .detail-item {{
                margin-bottom: 15px;
            }}
            .detail-label {{
                font-weight: 600;
                color: #495057;
                display: inline-block;
                min-width: 120px;
            }}
            .detail-value {{
                font-family: monospace;
                background-color: #e9ecef;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 14px;
            }}
            .trusted-list {{
                background-color: #f8f9fa;
                border-radius: 6px;
                padding: 15px;
                margin: 15px 0;
            }}
            .trusted-list ul {{
                margin: 10px 0;
                padding-left: 20px;
            }}
            .actions {{
                margin: 30px 0;
                text-align: center;
            }}
            .action-button {{
                display: inline-block;
                padding: 12px 24px;
                margin: 8px;
                text-decoration: none;
                border-radius: 6px;
                font-weight: 600;
                font-size: 14px;
                transition: all 0.2s;
            }}
            .btn-primary {{
                background-color: #007bff;
                color: #ffffff;
                border: 2px solid #007bff;
            }}
            .btn-primary:hover {{
                background-color: #0056b3;
                border-color: #0056b3;
            }}
            .btn-secondary {{
                background-color: #6c757d;
                color: #ffffff;
                border: 2px solid #6c757d;
            }}
            .btn-secondary:hover {{
                background-color: #545b62;
                border-color: #545b62;
            }}
            .footer {{
                margin-top: 30px;
                padding-top: 20px;
                border-top: 1px solid #e9ecef;
                font-size: 12px;
                color: #6c757d;
                text-align: center;
            }}
            .security-notice {{
                background-color: #d1ecf1;
                border: 1px solid #bee5eb;
                border-radius: 6px;
                padding: 15px;
                margin: 20px 0;
            }}
            .security-notice h4 {{
                margin-top: 0;
                color: #0c5460;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🚫 Blocked Access Attempt</h1>
                <p>IP Lockdown Protection Activated</p>
            </div>
            
            <div class="alert">
                <span class="alert-icon">⚠️</span>
                <strong>Security Alert:</strong> An access attempt to your account was blocked because it came from an untrusted IP address.
            </div>
            
            <div class="details">
                <h3>Access Attempt Details</h3>
                <div class="detail-item">
                    <span class="detail-label">Blocked IP Address:</span><br>
                    <span class="detail-value">{attempted_ip}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Endpoint Accessed:</span><br>
                    <span class="detail-value">{endpoint}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Time (UTC):</span><br>
                    <span class="detail-value">{timestamp}</span>
                </div>
            </div>
            
            <div class="trusted-list">
                <h3>Your Currently Trusted IP Addresses</h3>
                <ul>{trusted_ips_html}</ul>
            </div>
            
            <div class="security-notice">
                <h4>🔒 What This Means</h4>
                <p>IP Lockdown is a security feature that only allows access from IP addresses you've explicitly trusted. This helps protect your account from unauthorized access attempts from unknown locations.</p>
            </div>
            
            <div class="actions">
                <h3>What Would You Like To Do?</h3>
                <p>If this was a legitimate access attempt from you:</p>
                
                {f'''
                <a href="{settings.BASE_URL}/auth/temporary-access/allow-once?token={allow_once_token}" class="action-button btn-primary">
                    🔓 Allow Once (15 minutes)
                </a>
                ''' if allow_once_token else '''
                <div class="action-button btn-primary" style="opacity: 0.6; cursor: not-allowed;">
                    🔓 Allow Once (Token generation failed)
                </div>
                '''}
                
                {f'''
                <a href="{settings.BASE_URL}/auth/temporary-access/add-to-trusted?token={add_to_trusted_token}" class="action-button btn-secondary">
                    ✅ Add to Trusted List
                </a>
                ''' if add_to_trusted_token else '''
                <div class="action-button btn-secondary" style="opacity: 0.6; cursor: not-allowed;">
                    ✅ Add to Trusted List (Token generation failed)
                </div>
                '''}
            </div>
            
            <div class="security-notice">
                <h4>🛡️ Security Recommendations</h4>
                <ul style="text-align: left; margin: 10px 0;">
                    <li>Only add IP addresses from locations you regularly access your account from</li>
                    <li>Regularly review your trusted IP list</li>
                    <li>If you didn't attempt this access, no action is needed - your account remains secure</li>
                    <li>Consider enabling additional security measures like two-factor authentication</li>
                </ul>
            </div>
            
            <div class="footer">
                <p>This is an automated security notification from Second Brain Database.</p>
                <p>If you have questions about this alert, please contact support.</p>
                <p><strong>Note:</strong> Action buttons expire after a short time for security. If expired, please contact support or manage your trusted IPs through the API.</p>
            </div>
        </div>
    </body>
    </html>
    """


def render_blocked_user_agent_notification_email(
    attempted_user_agent: str, 
    trusted_user_agents: List[str], 
    endpoint: str, 
    timestamp: str,
    allow_once_token: str = None,
    add_to_trusted_token: str = None
) -> str:
    """
    Render an HTML email for blocked User Agent access notification with action buttons.
    Args:
        attempted_user_agent (str): The User Agent that was blocked.
        trusted_user_agents (List[str]): List of currently trusted User Agents.
        endpoint (str): The endpoint that was accessed.
        timestamp (str): The timestamp of the blocked attempt.
        allow_once_token (str, optional): Token for "allow once" action.
        add_to_trusted_token (str, optional): Token for "add to trusted list" action.
    Returns:
        str: HTML content for the email.
    """
    trusted_user_agents_html = "".join(f"<li style='margin-bottom: 5px; font-family: monospace; font-size: 12px; word-break: break-all;'>{user_agent}</li>" for user_agent in trusted_user_agents)
    
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Blocked Access Attempt - User Agent Lockdown</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f8f9fa;
            }}
            .container {{
                background-color: #ffffff;
                border-radius: 8px;
                padding: 30px;
                box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
            }}
            .header {{
                text-align: center;
                margin-bottom: 30px;
                padding-bottom: 20px;
                border-bottom: 2px solid #e9ecef;
            }}
            .header h1 {{
                color: #dc3545;
                margin: 0;
                font-size: 24px;
            }}
            .alert {{
                background-color: #fff3cd;
                border: 1px solid #ffeaa7;
                border-radius: 6px;
                padding: 15px;
                margin-bottom: 20px;
            }}
            .alert-icon {{
                font-size: 20px;
                margin-right: 10px;
            }}
            .details {{
                background-color: #f8f9fa;
                border-radius: 6px;
                padding: 20px;
                margin: 20px 0;
            }}
            .details h3 {{
                margin-top: 0;
                color: #495057;
                font-size: 16px;
            }}
            .detail-item {{
                margin-bottom: 15px;
            }}
            .detail-label {{
                font-weight: 600;
                color: #495057;
                display: inline-block;
                min-width: 120px;
            }}
            .detail-value {{
                font-family: monospace;
                background-color: #e9ecef;
                padding: 4px 8px;
                border-radius: 4px;
                word-break: break-all;
                font-size: 12px;
            }}
            .trusted-list {{
                background-color: #f8f9fa;
                border-radius: 6px;
                padding: 15px;
                margin: 15px 0;
            }}
            .trusted-list ul {{
                margin: 10px 0;
                padding-left: 20px;
            }}
            .actions {{
                margin: 30px 0;
                text-align: center;
            }}
            .action-button {{
                display: inline-block;
                padding: 12px 24px;
                margin: 8px;
                text-decoration: none;
                border-radius: 6px;
                font-weight: 600;
                font-size: 14px;
                transition: all 0.2s;
            }}
            .btn-primary {{
                background-color: #007bff;
                color: #ffffff;
                border: 2px solid #007bff;
            }}
            .btn-primary:hover {{
                background-color: #0056b3;
                border-color: #0056b3;
            }}
            .btn-secondary {{
                background-color: #6c757d;
                color: #ffffff;
                border: 2px solid #6c757d;
            }}
            .btn-secondary:hover {{
                background-color: #545b62;
                border-color: #545b62;
            }}
            .footer {{
                margin-top: 30px;
                padding-top: 20px;
                border-top: 1px solid #e9ecef;
                font-size: 12px;
                color: #6c757d;
                text-align: center;
            }}
            .security-notice {{
                background-color: #d1ecf1;
                border: 1px solid #bee5eb;
                border-radius: 6px;
                padding: 15px;
                margin: 20px 0;
            }}
            .security-notice h4 {{
                margin-top: 0;
                color: #0c5460;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🚫 Blocked Access Attempt</h1>
                <p>User Agent Lockdown Protection Activated</p>
            </div>
            
            <div class="alert">
                <span class="alert-icon">⚠️</span>
                <strong>Security Alert:</strong> An access attempt to your account was blocked because it came from an untrusted User Agent.
            </div>
            
            <div class="details">
                <h3>Access Attempt Details</h3>
                <div class="detail-item">
                    <span class="detail-label">Blocked User Agent:</span><br>
                    <span class="detail-value">{attempted_user_agent}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Endpoint Accessed:</span><br>
                    <span class="detail-value">{endpoint}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Time (UTC):</span><br>
                    <span class="detail-value">{timestamp}</span>
                </div>
            </div>
            
            <div class="trusted-list">
                <h3>Your Currently Trusted User Agents</h3>
                <ul>{trusted_user_agents_html}</ul>
            </div>
            
            <div class="security-notice">
                <h4>🔒 What This Means</h4>
                <p>User Agent Lockdown is a security feature that only allows access from browsers and applications you've explicitly trusted. This helps protect your account from unauthorized access attempts.</p>
            </div>
            
            <div class="actions">
                <h3>What Would You Like To Do?</h3>
                <p>If this was a legitimate access attempt from you:</p>
                
                {f'''
                <a href="{settings.BASE_URL}/auth/temporary-access/allow-once-user-agent?token={allow_once_token}" class="action-button btn-primary">
                    🔓 Allow Once (15 minutes)
                </a>
                ''' if allow_once_token else '''
                <div class="action-button btn-primary" style="opacity: 0.6; cursor: not-allowed;">
                    🔓 Allow Once (Token generation failed)
                </div>
                '''}
                
                {f'''
                <a href="{settings.BASE_URL}/auth/temporary-access/add-to-trusted-user-agent?token={add_to_trusted_token}" class="action-button btn-secondary">
                    ✅ Add to Trusted List
                </a>
                ''' if add_to_trusted_token else '''
                <div class="action-button btn-secondary" style="opacity: 0.6; cursor: not-allowed;">
                    ✅ Add to Trusted List (Token generation failed)
                </div>
                '''}
            </div>
            
            <div class="security-notice">
                <h4>🛡️ Security Recommendations</h4>
                <ul style="text-align: left; margin: 10px 0;">
                    <li>Only add User Agents from devices and browsers you personally use</li>
                    <li>Regularly review your trusted User Agent list</li>
                    <li>If you didn't attempt this access, no action is needed - your account remains secure</li>
                    <li>Consider enabling additional security measures like two-factor authentication</li>
                </ul>
            </div>
            
            <div class="footer">
                <p>This is an automated security notification from Second Brain Database.</p>
                <p>If you have questions about this alert, please contact support.</p>
                <p><strong>Note:</strong> Action buttons expire after a short time for security. If expired, please contact support or manage your trusted User Agents through the API.</p>
            </div>
        </div>
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
    html = f"""
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
        class SecureLogin {{
            constructor() {{
                this.apiBase = '/auth';
                this.currentTab = 'password';
                this.init();
            }}
            
            init() {{
                this.bindEvents();
                this.checkWebAuthnSupport();
                this.setupTabSwitching();
            }}
            
            bindEvents() {{
                // Password form submission
                document.getElementById('password-form').addEventListener('submit', this.handlePasswordLogin.bind(this));
                
                // Passkey login button
                document.getElementById('passkey-login-btn').addEventListener('click', this.handlePasskeyLogin.bind(this));
            }}
            
            setupTabSwitching() {{
                const tabs = document.querySelectorAll('.auth-tab');
                const forms = document.querySelectorAll('.auth-form');
                
                tabs.forEach(tab => {{
                    tab.addEventListener('click', () => {{
                        const tabType = tab.dataset.tab;
                        
                        // Update active tab
                        tabs.forEach(t => t.classList.remove('active'));
                        tab.classList.add('active');
                        
                        // Update active form
                        forms.forEach(f => f.classList.remove('active'));
                        document.getElementById(`${{tabType}}-form`).classList.add('active');
                        
                        this.currentTab = tabType;
                        this.clearMessages();
                    }});
                }});
            }}
            
            checkWebAuthnSupport() {{
                const supported = document.getElementById('webauthn-supported');
                const notSupported = document.getElementById('webauthn-not-supported');
                const loginSection = document.getElementById('passkey-login-section');
                
                if (window.PublicKeyCredential && typeof window.PublicKeyCredential.get === 'function') {{
                    supported.classList.remove('hidden');
                    loginSection.classList.remove('hidden');
                }} else {{
                    notSupported.classList.remove('hidden');
                }}
            }}
            
            async handlePasswordLogin(event) {{
                event.preventDefault();
                
                const identifier = document.getElementById('identifier').value;
                const password = document.getElementById('password').value;
                const btn = document.getElementById('password-login-btn');
                
                if (!identifier || !password) {{
                    this.showMessage('Please enter both username/email and password', 'error');
                    return;
                }}
                
                this.setLoading(btn, true);
                this.clearMessages();
                
                try {{
                    // Determine if identifier is email or username
                    const isEmail = identifier.includes('@');
                    const loginData = {{
                        password: password,
                        client_side_encryption: false
                    }};
                    
                    if (isEmail) {{
                        loginData.email = identifier;
                    }} else {{
                        loginData.username = identifier;
                    }}
                    
                    const response = await fetch(`${{this.apiBase}}/login`, {{
                        method: 'POST',
                        headers: {{
                            'Content-Type': 'application/json'
                        }},
                        body: JSON.stringify(loginData)
                    }});
                    
                    const data = await response.json();
                    
                    if (response.ok) {{
                        // Store token and redirect
                        localStorage.setItem('access_token', data.access_token);
                        this.showMessage('Login successful! Redirecting...', 'success');
                        
                        // Redirect to setup page or dashboard
                        setTimeout(() => {{
                            window.location.href = '/auth/webauthn/setup';
                        }}, 1000);
                        
                    }} else if (response.status === 422 && data.two_fa_required) {{
                        // Handle 2FA requirement
                        this.handle2FARequired(data);
                        
                    }} else if (response.status === 403 && data.detail === 'Email not verified') {{
                        this.showMessage('Please verify your email address before logging in', 'error');
                        
                    }} else {{
                        this.showMessage(data.detail || data.message || 'Login failed', 'error');
                    }}
                    
                }} catch (error) {{
                    console.error('Login error:', error);
                    this.showMessage('Network error. Please try again.', 'error');
                }} finally {{
                    this.setLoading(btn, false);
                }}
            }}
            
            async handlePasskeyLogin() {{
                const identifier = document.getElementById('passkey-identifier').value;
                const btn = document.getElementById('passkey-login-btn');
                
                if (!identifier) {{
                    this.showMessage('Please enter your username or email', 'error');
                    return;
                }}
                
                this.setLoading(btn, true);
                this.clearMessages();
                
                try {{
                    // Begin WebAuthn authentication
                    const isEmail = identifier.includes('@');
                    const beginData = {{}};
                    
                    if (isEmail) {{
                        beginData.email = identifier;
                    }} else {{
                        beginData.username = identifier;
                    }}
                    
                    const beginResponse = await fetch(`${{this.apiBase}}/webauthn/authenticate/begin`, {{
                        method: 'POST',
                        headers: {{
                            'Content-Type': 'application/json'
                        }},
                        body: JSON.stringify(beginData)
                    }});
                    
                    if (!beginResponse.ok) {{
                        const errorData = await beginResponse.json();
                        throw new Error(errorData.detail || 'Failed to start passkey authentication');
                    }}
                    
                    const options = await beginResponse.json();
                    
                    // Convert base64url strings to ArrayBuffers
                    options.publicKey.challenge = this.base64urlToArrayBuffer(options.publicKey.challenge);
                    
                    if (options.publicKey.allowCredentials) {{
                        options.publicKey.allowCredentials = options.publicKey.allowCredentials.map(cred => ({{
                            ...cred,
                            id: this.base64urlToArrayBuffer(cred.id)
                        }}));
                    }}
                    
                    // Get credential from authenticator
                    const credential = await navigator.credentials.get(options);
                    
                    if (!credential) {{
                        throw new Error('No credential received from authenticator');
                    }}
                    
                    // Complete authentication
                    const completeResponse = await fetch(`${{this.apiBase}}/webauthn/authenticate/complete`, {{
                        method: 'POST',
                        headers: {{
                            'Content-Type': 'application/json'
                        }},
                        body: JSON.stringify({{
                            id: credential.id,
                            rawId: this.arrayBufferToBase64url(credential.rawId),
                            response: {{
                                authenticatorData: this.arrayBufferToBase64url(credential.response.authenticatorData),
                                clientDataJSON: this.arrayBufferToBase64url(credential.response.clientDataJSON),
                                signature: this.arrayBufferToBase64url(credential.response.signature),
                                userHandle: credential.response.userHandle ? this.arrayBufferToBase64url(credential.response.userHandle) : null
                            }},
                            type: credential.type
                        }})
                    }});
                    
                    if (!completeResponse.ok) {{
                        const errorData = await completeResponse.json();
                        throw new Error(errorData.detail || 'Passkey authentication failed');
                    }}
                    
                    const authData = await completeResponse.json();
                    
                    // Store token and redirect
                    localStorage.setItem('access_token', authData.access_token);
                    this.showMessage('Passkey authentication successful! Redirecting...', 'success');
                    
                    setTimeout(() => {{
                        window.location.href = '/auth/webauthn/setup';
                    }}, 1000);
                    
                }} catch (error) {{
                    console.error('Passkey authentication error:', error);
                    
                    if (error.name === 'NotAllowedError') {{
                        this.showMessage('Passkey authentication was cancelled or failed', 'error');
                    }} else if (error.name === 'NotSupportedError') {{
                        this.showMessage('Passkey authentication is not supported on this device', 'error');
                    }} else {{
                        this.showMessage(error.message || 'Passkey authentication failed', 'error');
                    }}
                }} finally {{
                    this.setLoading(btn, false);
                }}
            }}
            
            handle2FARequired(data) {{
                // For now, show a message. In a full implementation, you'd show 2FA input
                this.showMessage('2FA authentication required. Please use the API directly for 2FA login.', 'info');
            }}
            
            setLoading(button, loading) {{
                if (loading) {{
                    button.disabled = true;
                    const originalText = button.textContent;
                    button.dataset.originalText = originalText;
                    button.innerHTML = '<span class="loading"></span>Signing in...';
                }} else {{
                    button.disabled = false;
                    button.textContent = button.dataset.originalText || button.textContent;
                }}
            }}
            
            showMessage(message, type) {{
                const container = document.getElementById('status-messages');
                const messageDiv = document.createElement('div');
                messageDiv.className = `status-message status-${{type}}`;
                messageDiv.textContent = message;
                
                container.appendChild(messageDiv);
                
                // Auto-remove success messages
                if (type === 'success') {{
                    setTimeout(() => {{
                        messageDiv.remove();
                    }}, 5000);
                }}
            }}
            
            clearMessages() {{
                const container = document.getElementById('status-messages');
                container.innerHTML = '';
            }}
            
            base64urlToArrayBuffer(base64url) {{
                const padding = '='.repeat((4 - base64url.length % 4) % 4);
                const base64 = (base64url + padding).replace(/-/g, '+').replace(/_/g, '/');
                const rawData = window.atob(base64);
                const outputArray = new Uint8Array(rawData.length);
                for (let i = 0; i < rawData.length; ++i) {{
                    outputArray[i] = rawData.charCodeAt(i);
                }}
                return outputArray.buffer;
            }}
            
            arrayBufferToBase64url(buffer) {{
                const bytes = new Uint8Array(buffer);
                let str = '';
                for (let i = 0; i < bytes.byteLength; i++) {{
                    str += String.fromCharCode(bytes[i]);
                }}
                return window.btoa(str).replace(/\\+/g, '-').replace(/\\//g, '_').replace(/=/g, '');
            }}
        }}
        
        // Initialize when DOM is loaded
        document.addEventListener('DOMContentLoaded', () => {{
            new SecureLogin();
        }});
    </script>
</body>
</html>
    """
    
    return HTMLResponse(content=html)


def render_webauthn_setup_page() -> HTMLResponse:
    """
    Serve the WebAuthn passkey setup HTML page.
    
    Args:
        username (str): The authenticated user's username
        user_id (str): The authenticated user's ID
        
    Returns:
        HTMLResponse: The rendered HTML page for passkey setup
    """
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Set Up Passkeys - Second Brain Database</title>
        <link href="https://fonts.googleapis.com/css?family=Roboto:400,700&display=swap" rel="stylesheet">
        <style>
            :root {{
                --primary: #3a86ff;
                --primary-hover: #265dbe;
                --background: #f6f8fa;
                --foreground: #ffffff;
                --text-main: #22223b;
                --text-sub: #4a4e69;
                --border-color: #c9c9c9;
                --error: #d90429;
                --success: #06d6a0;
                --info: #0c5460;
            }}
            
            * {{ box-sizing: border-box; }}
            
            body {{
                margin: 0;
                background-color: var(--background);
                font-family: 'Roboto', sans-serif;
                padding: 20px;
                min-height: 100vh;
            }}
            
            .container {{
                max-width: 800px;
                margin: 0 auto;
                background-color: var(--foreground);
                padding: 2.5rem 2rem;
                border-radius: 12px;
                box-shadow: 0 4px 24px rgba(0, 0, 0, 0.08);
            }}
            
            .hidden {{
                display: none !important;
            }}
            
            h1 {{
                margin-bottom: 1.5rem;
                color: var(--text-main);
                font-size: 2rem;
                font-weight: 700;
                text-align: center;
            }}
            
            h2 {{
                margin-bottom: 1rem;
                color: var(--text-main);
                font-size: 1.5rem;
                font-weight: 600;
            }}
            
            p {{
                color: var(--text-sub);
                line-height: 1.6;
                margin-bottom: 1rem;
            }}
            
            .btn-primary, .btn-secondary, .btn-danger {{
                padding: 12px 24px;
                border: none;
                border-radius: 6px;
                font-size: 16px;
                cursor: pointer;
                text-decoration: none;
                display: inline-block;
                margin: 8px;
                transition: background-color 0.2s;
                font-weight: 500;
            }}
            
            .btn-primary {{
                background-color: var(--primary);
                color: white;
            }}
            
            .btn-primary:hover {{
                background-color: var(--primary-hover);
            }}
            
            .btn-secondary {{
                background-color: #6c757d;
                color: white;
            }}
            
            .btn-danger {{
                background-color: var(--error);
                color: white;
            }}
            
            .btn-danger:hover {{
                background-color: #c82333;
            }}
            
            #setup-form {{
                background-color: var(--background);
                padding: 20px;
                border-radius: 8px;
                margin: 20px 0;
            }}
            
            #setup-form label {{
                display: block;
                margin-bottom: 8px;
                font-weight: 500;
                color: var(--text-main);
            }}
            
            #setup-form input {{
                width: 100%;
                padding: 8px 12px;
                border: 1px solid var(--border-color);
                border-radius: 4px;
                margin-bottom: 16px;
                font-size: 16px;
            }}
            
            .passkey-item {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 16px;
                border: 1px solid var(--border-color);
                border-radius: 8px;
                margin-bottom: 12px;
                background-color: var(--background);
            }}
            
            .passkey-info h3 {{
                margin: 0 0 8px 0;
                color: var(--text-main);
                font-size: 1.1rem;
            }}
            
            .passkey-info p {{
                margin: 4px 0;
                color: var(--text-sub);
                font-size: 14px;
            }}
            
            .status-message {{
                padding: 12px;
                border-radius: 4px;
                margin: 8px 0;
            }}
            
            .status-message.success {{
                background-color: #d4edda;
                color: #155724;
                border: 1px solid #c3e6cb;
            }}
            
            .status-message.error {{
                background-color: #f8d7da;
                color: #721c24;
                border: 1px solid #f5c6cb;
            }}
            
            .status-message.info {{
                background-color: #d1ecf1;
                color: var(--info);
                border: 1px solid #bee5eb;
            }}
            
            .no-passkeys {{
                text-align: center;
                color: var(--text-sub);
                font-style: italic;
                padding: 40px;
            }}
            
            .actions {{
                margin-bottom: 20px;
                text-align: center;
            }}
            
            .user-info {{
                background-color: var(--background);
                padding: 15px;
                border-radius: 8px;
                margin-bottom: 20px;
                text-align: center;
            }}
            
            @media (max-width: 768px) {{
                .container {{
                    padding: 1rem;
                }}
                
                .passkey-item {{
                    flex-direction: column;
                    align-items: flex-start;
                }}
                
                .passkey-item .btn-danger {{
                    margin-top: 12px;
                    align-self: flex-end;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Set Up Passkeys</h1>
            
            <div class="user-info">
                <p><strong>Logged in as:</strong> {username}</p>
            </div>
            
            <div id="webauthn-support-check">
                <div id="supported" class="hidden">
                    <p>Your browser supports passkeys! You can use biometrics (like fingerprint or face recognition) or hardware security keys to sign in securely without passwords.</p>
                    <div class="actions">
                        <button id="setup-passkey" class="btn-primary">Set Up New Passkey</button>
                        <a href="/auth/webauthn/manage" class="btn-secondary">Manage Existing Passkeys</a>
                    </div>
                </div>
                <div id="not-supported" class="hidden">
                    <p>Your browser doesn't support passkeys. Please use a modern browser like Chrome, Firefox, Safari, or Edge to set up passkeys.</p>
                    <div class="actions">
                        <a href="/auth/login" class="btn-secondary">Continue with Password</a>
                    </div>
                </div>
            </div>
            
            <div id="setup-form" class="hidden">
                <h2>Create New Passkey</h2>
                <label for="device-name">Device Name (Optional):</label>
                <input type="text" id="device-name" placeholder="e.g., My Laptop, Work Computer, iPhone">
                <div class="actions">
                    <button id="create-passkey" class="btn-primary">Create Passkey</button>
                    <button id="cancel-setup" class="btn-secondary">Cancel</button>
                </div>
            </div>
            
            <div id="status-messages"></div>
            
            <div class="existing-passkeys">
                <h2>Your Passkeys</h2>
                <div id="passkey-list"></div>
            </div>
        </div>
        
        <script>
            class WebAuthnSetup {{
                constructor() {{
                    this.apiBase = '/auth/webauthn';
                    this.init();
                }}
                
                async init() {{
                    // Check authentication first
                    if (!this.checkAuthentication()) {{
                        return; // Will redirect to login
                    }}
                    
                    this.checkWebAuthnSupport();
                    this.bindEvents();
                    await this.loadExistingPasskeys();
                }}
                
                checkAuthentication() {{
                    const token = this.getToken();
                    if (!token) {{
                        this.showMessage('Please log in to access this page', 'error');
                        setTimeout(() => {{
                            window.location.href = '/auth/login';
                        }}, 2000);
                        return false;
                    }}
                    return true;
                }}
                
                checkWebAuthnSupport() {{
                    const supported = document.getElementById('supported');
                    const notSupported = document.getElementById('not-supported');
                    
                    if (window.PublicKeyCredential && 
                        typeof window.PublicKeyCredential.create === 'function') {{
                        supported.classList.remove('hidden');
                    }} else {{
                        notSupported.classList.remove('hidden');
                    }}
                }}
                
                bindEvents() {{
                    document.getElementById('setup-passkey')?.addEventListener('click', () => {{
                        document.getElementById('setup-form').classList.remove('hidden');
                    }});
                    
                    document.getElementById('cancel-setup')?.addEventListener('click', () => {{
                        document.getElementById('setup-form').classList.add('hidden');
                        document.getElementById('device-name').value = '';
                    }});
                    
                    document.getElementById('create-passkey')?.addEventListener('click', 
                        this.createPasskey.bind(this));
                }}
                
                async createPasskey() {{
                    try {{
                        this.showStatus('Creating passkey...', 'info');
                        
                        const deviceName = document.getElementById('device-name').value.trim() || 'Browser Passkey';
                        
                        // Begin registration
                        const beginResponse = await fetch(`${{this.apiBase}}/register/begin`, {{
                            method: 'POST',
                            headers: {{
                                'Content-Type': 'application/json',
                                'Authorization': `Bearer ${{this.getToken()}}`
                            }},
                            body: JSON.stringify({{ device_name: deviceName }})
                        }});
                        
                        if (!beginResponse.ok) {{
                            const errorData = await beginResponse.json();
                            throw new Error(errorData.detail || 'Failed to start passkey creation');
                        }}
                        
                        const options = await beginResponse.json();
                        
                        // Convert base64url strings to ArrayBuffers
                        options.challenge = this.base64urlToArrayBuffer(options.challenge);
                        options.user.id = this.base64urlToArrayBuffer(options.user.id);
                        
                        if (options.excludeCredentials) {{
                            options.excludeCredentials = options.excludeCredentials.map(cred => ({{
                                ...cred,
                                id: this.base64urlToArrayBuffer(cred.id)
                            }}));
                        }}
                        
                        // Create credential
                        const credential = await navigator.credentials.create({{
                            publicKey: options
                        }});
                        
                        if (!credential) {{
                            throw new Error('Failed to create credential');
                        }}
                        
                        // Complete registration
                        const completeResponse = await fetch(`${{this.apiBase}}/register/complete`, {{
                            method: 'POST',
                            headers: {{
                                'Content-Type': 'application/json',
                                'Authorization': `Bearer ${{this.getToken()}}`
                            }},
                            body: JSON.stringify({{
                                id: credential.id,
                                rawId: this.arrayBufferToBase64url(credential.rawId),
                                response: {{
                                    attestationObject: this.arrayBufferToBase64url(credential.response.attestationObject),
                                    clientDataJSON: this.arrayBufferToBase64url(credential.response.clientDataJSON)
                                }},
                                type: credential.type
                            }})
                        }});
                        
                        if (!completeResponse.ok) {{
                            const errorData = await completeResponse.json();
                            throw new Error(errorData.detail || 'Failed to complete passkey creation');
                        }}
                        
                        this.showStatus('Passkey created successfully!', 'success');
                        await this.loadExistingPasskeys();
                        document.getElementById('setup-form').classList.add('hidden');
                        document.getElementById('device-name').value = '';
                        
                    }} catch (error) {{
                        console.error('Passkey creation failed:', error);
                        this.showStatus(`Failed to create passkey: ${{error.message}}`, 'error');
                    }}
                }}
                
                async loadExistingPasskeys() {{
                    try {{
                        const response = await fetch(`${{this.apiBase}}/credentials`, {{
                            headers: {{
                                'Authorization': `Bearer ${{this.getToken()}}`
                            }}
                        }});
                        
                        if (!response.ok) return;
                        
                        const data = await response.json();
                        this.renderPasskeyList(data.credentials);
                        
                    }} catch (error) {{
                        console.error('Failed to load passkeys:', error);
                    }}
                }}
                
                renderPasskeyList(credentials) {{
                    const container = document.getElementById('passkey-list');
                    
                    if (!credentials || credentials.length === 0) {{
                        container.innerHTML = '<p class="no-passkeys">No passkeys registered yet. Create your first passkey above!</p>';
                        return;
                    }}
                    
                    container.innerHTML = credentials.map(cred => `
                        <div class="passkey-item">
                            <div class="passkey-info">
                                <h3>${{this.escapeHtml(cred.device_name)}}</h3>
                                <p><strong>Type:</strong> ${{cred.authenticator_type}}</p>
                                <p><strong>Created:</strong> ${{new Date(cred.created_at).toLocaleDateString()}}</p>
                                ${{cred.last_used_at ? 
                                    `<p><strong>Last used:</strong> ${{new Date(cred.last_used_at).toLocaleDateString()}}</p>` : 
                                    '<p><strong>Last used:</strong> Never</p>'
                                }}
                            </div>
                            <button class="btn-danger delete-passkey" data-credential-id="${{cred.credential_id}}">
                                Delete
                            </button>
                        </div>
                    `).join('');
                    
                    // Bind delete events
                    container.querySelectorAll('.delete-passkey').forEach(btn => {{
                        btn.addEventListener('click', (e) => {{
                            this.deletePasskey(e.target.dataset.credentialId);
                        }});
                    }});
                }}
                
                async deletePasskey(credentialId) {{
                    if (!confirm('Are you sure you want to delete this passkey? This action cannot be undone.')) {{
                        return;
                    }}
                    
                    try {{
                        const response = await fetch(`${{this.apiBase}}/credentials/${{credentialId}}`, {{
                            method: 'DELETE',
                            headers: {{
                                'Authorization': `Bearer ${{this.getToken()}}`
                            }}
                        }});
                        
                        if (!response.ok) {{
                            const errorData = await response.json();
                            throw new Error(errorData.detail || 'Failed to delete passkey');
                        }}
                        
                        this.showStatus('Passkey deleted successfully', 'success');
                        await this.loadExistingPasskeys();
                        
                    }} catch (error) {{
                        console.error('Failed to delete passkey:', error);
                        this.showStatus(`Failed to delete passkey: ${{error.message}}`, 'error');
                    }}
                }}
                
                showStatus(message, type) {{
                    const container = document.getElementById('status-messages');
                    const statusDiv = document.createElement('div');
                    statusDiv.className = `status-message ${{type}}`;
                    statusDiv.textContent = message;
                    
                    container.appendChild(statusDiv);
                    
                    setTimeout(() => {{
                        statusDiv.remove();
                    }}, 5000);
                }}
                
                getToken() {{
                    // Get JWT token from localStorage, sessionStorage, or cookie
                    return localStorage.getItem('access_token') || 
                           sessionStorage.getItem('access_token') ||
                           this.getCookieValue('access_token');
                }}
                
                getCookieValue(name) {{
                    const value = `; ${{document.cookie}}`;
                    const parts = value.split(`; ${{name}}=`);
                    if (parts.length === 2) return parts.pop().split(';').shift();
                    return null;
                }}
                
                base64urlToArrayBuffer(base64url) {{
                    const padding = '='.repeat((4 - base64url.length % 4) % 4);
                    const base64 = (base64url + padding).replace(/-/g, '+').replace(/_/g, '/');
                    const rawData = window.atob(base64);
                    const outputArray = new Uint8Array(rawData.length);
                    for (let i = 0; i < rawData.length; ++i) {{
                        outputArray[i] = rawData.charCodeAt(i);
                    }}
                    return outputArray.buffer;
                }}
                
                arrayBufferToBase64url(buffer) {{
                    const bytes = new Uint8Array(buffer);
                    let str = '';
                    for (let i = 0; i < bytes.byteLength; i++) {{
                        str += String.fromCharCode(bytes[i]);
                    }}
                    return window.btoa(str).replace(/\\+/g, '-').replace(/\\//g, '_').replace(/=/g, '');
                }}
                
                escapeHtml(text) {{
                    const map = {{
                        '&': '&amp;',
                        '<': '&lt;',
                        '>': '&gt;',
                        '"': '&quot;',
                        "'": '&#039;'
                    }};
                    return text.replace(/[&<>"']/g, m => map[m]);
                }}
            }}
            
            // Initialize when DOM is loaded
            document.addEventListener('DOMContentLoaded', () => {{
                new WebAuthnSetup();
            }});
        </script>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html)


def render_webauthn_manage_page() -> HTMLResponse:
    """
    Serve the WebAuthn passkey management HTML page.
    
    Args:
        username (str): The authenticated user's username
        user_id (str): The authenticated user's ID
        
    Returns:
        HTMLResponse: The rendered HTML page for passkey management
    """
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Manage Passkeys - Second Brain Database</title>
        <link href="https://fonts.googleapis.com/css?family=Roboto:400,700&display=swap" rel="stylesheet">
        <style>
            :root {{
                --primary: #3a86ff;
                --primary-hover: #265dbe;
                --background: #f6f8fa;
                --foreground: #ffffff;
                --text-main: #22223b;
                --text-sub: #4a4e69;
                --border-color: #c9c9c9;
                --error: #d90429;
                --success: #06d6a0;
                --info: #0c5460;
            }}
            
            * {{ box-sizing: border-box; }}
            
            body {{
                margin: 0;
                background-color: var(--background);
                font-family: 'Roboto', sans-serif;
                padding: 20px;
                min-height: 100vh;
            }}
            
            .container {{
                max-width: 800px;
                margin: 0 auto;
                background-color: var(--foreground);
                padding: 2.5rem 2rem;
                border-radius: 12px;
                box-shadow: 0 4px 24px rgba(0, 0, 0, 0.08);
            }}
            
            .hidden {{
                display: none !important;
            }}
            
            h1 {{
                margin-bottom: 1.5rem;
                color: var(--text-main);
                font-size: 2rem;
                font-weight: 700;
                text-align: center;
            }}
            
            .btn-primary, .btn-secondary, .btn-danger {{
                padding: 12px 24px;
                border: none;
                border-radius: 6px;
                font-size: 16px;
                cursor: pointer;
                text-decoration: none;
                display: inline-block;
                margin: 8px;
                transition: background-color 0.2s;
                font-weight: 500;
            }}
            
            .btn-primary {{
                background-color: var(--primary);
                color: white;
            }}
            
            .btn-primary:hover {{
                background-color: var(--primary-hover);
            }}
            
            .btn-secondary {{
                background-color: #6c757d;
                color: white;
            }}
            
            .btn-danger {{
                background-color: var(--error);
                color: white;
            }}
            
            .btn-danger:hover {{
                background-color: #c82333;
            }}
            
            .actions {{
                margin-bottom: 20px;
                text-align: center;
            }}
            
            .user-info {{
                background-color: var(--background);
                padding: 15px;
                border-radius: 8px;
                margin-bottom: 20px;
                text-align: center;
            }}
            
            .passkey-grid {{
                display: grid;
                gap: 16px;
            }}
            
            .passkey-item {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 20px;
                border: 1px solid var(--border-color);
                border-radius: 8px;
                background-color: var(--background);
            }}
            
            .passkey-info h3 {{
                margin: 0 0 8px 0;
                color: var(--text-main);
                font-size: 1.2rem;
            }}
            
            .passkey-info p {{
                margin: 4px 0;
                color: var(--text-sub);
                font-size: 14px;
            }}
            
            .status-message {{
                padding: 12px;
                border-radius: 4px;
                margin: 8px 0;
            }}
            
            .status-message.success {{
                background-color: #d4edda;
                color: #155724;
                border: 1px solid #c3e6cb;
            }}
            
            .status-message.error {{
                background-color: #f8d7da;
                color: #721c24;
                border: 1px solid #f5c6cb;
            }}
            
            .status-message.info {{
                background-color: #d1ecf1;
                color: var(--info);
                border: 1px solid #bee5eb;
            }}
            
            .no-passkeys {{
                text-align: center;
                color: var(--text-sub);
                font-style: italic;
                padding: 60px 20px;
                background-color: var(--background);
                border-radius: 8px;
            }}
            
            .modal {{
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background-color: rgba(0, 0, 0, 0.5);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 1000;
            }}
            
            .modal-content {{
                background-color: var(--foreground);
                padding: 30px;
                border-radius: 12px;
                max-width: 400px;
                width: 90%;
                text-align: center;
            }}
            
            .modal-content h3 {{
                margin-top: 0;
                color: var(--text-main);
            }}
            
            .modal-content p {{
                color: var(--text-sub);
                margin-bottom: 20px;
            }}
            
            .modal-actions {{
                display: flex;
                gap: 10px;
                justify-content: center;
            }}
            
            @media (max-width: 768px) {{
                .container {{
                    padding: 1rem;
                }}
                
                .passkey-item {{
                    flex-direction: column;
                    align-items: flex-start;
                }}
                
                .passkey-item .btn-danger {{
                    margin-top: 12px;
                    align-self: flex-end;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Manage Your Passkeys</h1>
            
            <div class="user-info">
                <p><strong>Logged in as:</strong> {username}</p>
            </div>
            
            <div class="actions">
                <a href="/auth/webauthn/setup" class="btn-primary">Add New Passkey</a>
                <a href="/auth/login" class="btn-secondary">Back to Login</a>
            </div>
            
            <div id="status-messages"></div>
            
            <div id="passkey-list" class="passkey-grid"></div>
            
            <div id="delete-modal" class="modal hidden">
                <div class="modal-content">
                    <h3>Delete Passkey</h3>
                    <p>Are you sure you want to delete this passkey? This action cannot be undone and you may lose access to your account if this is your only authentication method.</p>
                    <div class="modal-actions">
                        <button id="confirm-delete" class="btn-danger">Delete Passkey</button>
                        <button id="cancel-delete" class="btn-secondary">Cancel</button>
                    </div>
                </div>
            </div>
        </div>
        
        <script>
            class WebAuthnManager {{
                constructor() {{
                    this.apiBase = '/auth/webauthn';
                    this.currentCredentialId = null;
                    this.init();
                }}
                
                async init() {{
                    this.bindEvents();
                    await this.loadPasskeys();
                }}
                
                bindEvents() {{
                    document.getElementById('confirm-delete')?.addEventListener('click', () => {{
                        this.confirmDelete();
                    }});
                    
                    document.getElementById('cancel-delete')?.addEventListener('click', () => {{
                        this.hideDeleteModal();
                    }});
                    
                    // Close modal on background click
                    document.getElementById('delete-modal')?.addEventListener('click', (e) => {{
                        if (e.target.id === 'delete-modal') {{
                            this.hideDeleteModal();
                        }}
                    }});
                }}
                
                async loadPasskeys() {{
                    try {{
                        this.showStatus('Loading your passkeys...', 'info');
                        
                        const response = await fetch(`${{this.apiBase}}/credentials`, {{
                            headers: {{
                                'Authorization': `Bearer ${{this.getToken()}}`
                            }}
                        }});
                        
                        if (!response.ok) {{
                            throw new Error('Failed to load passkeys');
                        }}
                        
                        const data = await response.json();
                        this.renderPasskeyList(data.credentials);
                        
                        // Clear loading message
                        document.getElementById('status-messages').innerHTML = '';
                        
                    }} catch (error) {{
                        console.error('Failed to load passkeys:', error);
                        this.showStatus(`Failed to load passkeys: ${{error.message}}`, 'error');
                    }}
                }}
                
                renderPasskeyList(credentials) {{
                    const container = document.getElementById('passkey-list');
                    
                    if (!credentials || credentials.length === 0) {{
                        container.innerHTML = `
                            <div class="no-passkeys">
                                <h3>No Passkeys Found</h3>
                                <p>You haven't set up any passkeys yet. Passkeys provide a secure, passwordless way to sign in using biometrics or hardware security keys.</p>
                                <a href="/auth/webauthn/setup" class="btn-primary">Set Up Your First Passkey</a>
                            </div>
                        `;
                        return;
                    }}
                    
                    container.innerHTML = credentials.map(cred => `
                        <div class="passkey-item">
                            <div class="passkey-info">
                                <h3>${{this.escapeHtml(cred.device_name)}}</h3>
                                <p><strong>Type:</strong> ${{this.formatAuthenticatorType(cred.authenticator_type)}}</p>
                                <p><strong>Transport:</strong> ${{this.formatTransport(cred.transport)}}</p>
                                <p><strong>Created:</strong> ${{new Date(cred.created_at).toLocaleDateString('en-US', {{
                                    year: 'numeric',
                                    month: 'long',
                                    day: 'numeric',
                                    hour: '2-digit',
                                    minute: '2-digit'
                                }})}}</p>
                                ${{cred.last_used_at ? 
                                    `<p><strong>Last used:</strong> ${{new Date(cred.last_used_at).toLocaleDateString('en-US', {{
                                        year: 'numeric',
                                        month: 'long',
                                        day: 'numeric',
                                        hour: '2-digit',
                                        minute: '2-digit'
                                    }})}}</p>` : 
                                    '<p><strong>Last used:</strong> Never</p>'
                                }}
                                <p><strong>Status:</strong> ${{cred.is_active ? 'Active' : 'Inactive'}}</p>
                            </div>
                            <button class="btn-danger delete-passkey" data-credential-id="${{cred.credential_id}}" data-device-name="${{this.escapeHtml(cred.device_name)}}">
                                Delete
                            </button>
                        </div>
                    `).join('');
                    
                    // Bind delete events
                    container.querySelectorAll('.delete-passkey').forEach(btn => {{
                        btn.addEventListener('click', (e) => {{
                            this.showDeleteModal(e.target.dataset.credentialId, e.target.dataset.deviceName);
                        }});
                    }});
                }}
                
                formatAuthenticatorType(type) {{
                    switch (type) {{
                        case 'platform':
                            return 'Platform (Built-in biometrics)';
                        case 'cross-platform':
                            return 'Cross-platform (Hardware key)';
                        default:
                            return type || 'Unknown';
                    }}
                }}
                
                formatTransport(transport) {{
                    if (!transport || transport.length === 0) return 'Unknown';
                    
                    const transportMap = {{
                        'internal': 'Built-in',
                        'usb': 'USB',
                        'nfc': 'NFC',
                        'ble': 'Bluetooth'
                    }};
                    
                    return transport.map(t => transportMap[t] || t).join(', ');
                }}
                
                showDeleteModal(credentialId, deviceName) {{
                    this.currentCredentialId = credentialId;
                    const modal = document.getElementById('delete-modal');
                    const modalContent = modal.querySelector('.modal-content p');
                    modalContent.textContent = `Are you sure you want to delete the passkey "${{deviceName}}"? This action cannot be undone and you may lose access to your account if this is your only authentication method.`;
                    modal.classList.remove('hidden');
                }}
                
                hideDeleteModal() {{
                    document.getElementById('delete-modal').classList.add('hidden');
                    this.currentCredentialId = null;
                }}
                
                async confirmDelete() {{
                    if (!this.currentCredentialId) return;
                    
                    try {{
                        this.showStatus('Deleting passkey...', 'info');
                        
                        const response = await fetch(`${{this.apiBase}}/credentials/${{this.currentCredentialId}}`, {{
                            method: 'DELETE',
                            headers: {{
                                'Authorization': `Bearer ${{this.getToken()}}`
                            }}
                        }});
                        
                        if (!response.ok) {{
                            const errorData = await response.json();
                            throw new Error(errorData.detail || 'Failed to delete passkey');
                        }}
                        
                        this.showStatus('Passkey deleted successfully', 'success');
                        this.hideDeleteModal();
                        await this.loadPasskeys();
                        
                    }} catch (error) {{
                        console.error('Failed to delete passkey:', error);
                        this.showStatus(`Failed to delete passkey: ${{error.message}}`, 'error');
                    }}
                }}
                
                showStatus(message, type) {{
                    const container = document.getElementById('status-messages');
                    const statusDiv = document.createElement('div');
                    statusDiv.className = `status-message ${{type}}`;
                    statusDiv.textContent = message;
                    
                    container.appendChild(statusDiv);
                    
                    setTimeout(() => {{
                        statusDiv.remove();
                    }}, 5000);
                }}
                
                getToken() {{
                    // Get JWT token from localStorage, sessionStorage, or cookie
                    return localStorage.getItem('access_token') || 
                           sessionStorage.getItem('access_token') ||
                           this.getCookieValue('access_token');
                }}
                
                getCookieValue(name) {{
                    const value = `; ${{document.cookie}}`;
                    const parts = value.split(`; ${{name}}=`);
                    if (parts.length === 2) return parts.pop().split(';').shift();
                    return null;
                }}
                
                escapeHtml(text) {{
                    const map = {{
                        '&': '&amp;',
                        '<': '&lt;',
                        '>': '&gt;',
                        '"': '&quot;',
                        "'": '&#039;'
                    }};
                    return text.replace(/[&<>"']/g, m => map[m]);
                }}
            }}
            
            // Initialize when DOM is loaded
            document.addEventListener('DOMContentLoaded', () => {{
                new WebAuthnManager();
            }});
        </script>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html)
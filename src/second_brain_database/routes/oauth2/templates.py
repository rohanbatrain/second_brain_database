"""
OAuth2 HTML templates for consent screens and user interfaces.

This module provides HTML templates for OAuth2 user consent screens and related UI components.
Templates are designed to be responsive and accessible.
"""

from datetime import datetime
from typing import Dict, List
from urllib.parse import quote

from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[OAuth2 Templates]")


def render_consent_screen(
    client_name: str,
    client_description: str,
    website_url: str,
    requested_scopes: List[Dict[str, str]],
    client_id: str,
    state: str,
    csrf_token: str,
    existing_consent: bool = False
) -> str:
    """
    Render OAuth2 consent screen HTML.
    
    Args:
        client_name: Human-readable name of the client application
        client_description: Description of the client application
        website_url: Client application website URL
        requested_scopes: List of scope dictionaries with 'scope' and 'description' keys
        client_id: OAuth2 client identifier
        state: OAuth2 state parameter
        csrf_token: CSRF protection token
        existing_consent: Whether user has previously granted consent
        
    Returns:
        HTML string for consent screen
    """
    
    # Generate scope list HTML
    scope_items = ""
    for scope_info in requested_scopes:
        scope_items += f"""
        <li class="scope-item" role="listitem">
            <div class="scope-name" aria-label="Permission: {scope_info['scope']}">{scope_info['scope']}</div>
            <div class="scope-description">{scope_info['description']}</div>
        </li>
        """
    
    # Website link HTML
    website_link = ""
    if website_url:
        website_link = f'<p class="client-website"><a href="{website_url}" target="_blank" rel="noopener noreferrer">Visit {client_name} website</a></p>'
    
    # Consent status message
    consent_status = ""
    if existing_consent:
        consent_status = """
        <div class="consent-status existing">
            <p><strong>Note:</strong> You have previously granted access to this application. Approving again will update your permissions.</p>
        </div>
        """
    
    html_template = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Authorize {client_name} - Second Brain Database</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                background: linear-gradient(135deg, #667eea 0%%, #764ba2 100%%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }}
            
            .consent-container {{
                background: white;
                border-radius: 12px;
                box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
                max-width: 500px;
                width: 100%%;
                padding: 40px;
                text-align: center;
            }}
            
            /* Focus styles for accessibility */
            .btn:focus {{
                outline: 2px solid #667eea;
                outline-offset: 2px;
            }}
            
            /* High contrast mode support */
            @media (prefers-contrast: high) {{
                .consent-container {{
                    border: 2px solid #000;
                }}
                
                .btn {{
                    border: 2px solid currentColor;
                }}
            }}
            
            /* Reduced motion support */
            @media (prefers-reduced-motion: reduce) {{
                * {{
                    animation-duration: 0.01ms !important;
                    animation-iteration-count: 1 !important;
                    transition-duration: 0.01ms !important;
                }}
            }}
            
            /* Screen reader only content */
            .sr-only {{
                position: absolute;
                width: 1px;
                height: 1px;
                padding: 0;
                margin: -1px;
                overflow: hidden;
                clip: rect(0, 0, 0, 0);
                white-space: nowrap;
                border: 0;
            }}
            
            .logo {{
                width: 60px;
                height: 60px;
                background: #667eea;
                border-radius: 12px;
                margin: 0 auto 20px;
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
                font-size: 24px;
                font-weight: bold;
            }}
            
            .title {{
                font-size: 24px;
                font-weight: 600;
                color: #2d3748;
                margin-bottom: 8px;
            }}
            
            .subtitle {{
                color: #718096;
                margin-bottom: 30px;
                font-size: 16px;
            }}
            
            .client-info {{
                background: #f7fafc;
                border-radius: 8px;
                padding: 20px;
                margin-bottom: 30px;
                text-align: left;
            }}
            
            .client-name {{
                font-size: 18px;
                font-weight: 600;
                color: #2d3748;
                margin-bottom: 8px;
            }}
            
            .client-description {{
                color: #4a5568;
                margin-bottom: 12px;
                line-height: 1.5;
            }}
            
            .client-website {{
                margin: 0;
            }}
            
            .client-website a {{
                color: #667eea;
                text-decoration: none;
                font-weight: 500;
            }}
            
            .client-website a:hover {{
                text-decoration: underline;
            }}
            
            .consent-status {{
                padding: 15px;
                border-radius: 8px;
                margin-bottom: 20px;
                text-align: left;
            }}
            
            .consent-status.existing {{
                background: #fef5e7;
                border: 1px solid #f6ad55;
                color: #744210;
            }}
            
            .permissions-section {{
                text-align: left;
                margin-bottom: 30px;
            }}
            
            .permissions-title {{
                font-size: 16px;
                font-weight: 600;
                color: #2d3748;
                margin-bottom: 15px;
            }}
            
            .scope-list {{
                list-style: none;
                padding: 0;
            }}
            
            .scope-item {{
                background: #f7fafc;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                padding: 12px;
                margin-bottom: 8px;
            }}
            
            .scope-name {{
                font-weight: 600;
                color: #2d3748;
                font-size: 14px;
                margin-bottom: 4px;
            }}
            
            .scope-description {{
                color: #4a5568;
                font-size: 13px;
                line-height: 1.4;
            }}
            
            .actions {{
                display: flex;
                gap: 12px;
                justify-content: center;
            }}
            
            .btn {{
                padding: 12px 24px;
                border-radius: 8px;
                font-weight: 600;
                font-size: 14px;
                cursor: pointer;
                border: none;
                transition: all 0.2s;
                min-width: 120px;
            }}
            
            .btn-approve {{
                background: #48bb78;
                color: white;
            }}
            
            .btn-approve:hover {{
                background: #38a169;
                transform: translateY(-1px);
            }}
            
            .btn-deny {{
                background: #e2e8f0;
                color: #4a5568;
            }}
            
            .btn-deny:hover {{
                background: #cbd5e0;
                transform: translateY(-1px);
            }}
            
            .security-notice {{
                margin-top: 30px;
                padding: 15px;
                background: #edf2f7;
                border-radius: 8px;
                font-size: 12px;
                color: #4a5568;
                text-align: left;
            }}
            
            .security-notice strong {{
                color: #2d3748;
            }}
            
            @media (max-width: 480px) {{
                .consent-container {{
                    padding: 30px 20px;
                }}
                
                .actions {{
                    flex-direction: column;
                }}
                
                .btn {{
                    width: 100%%;
                }}
            }}
        </style>
    </head>
    <body>
        <main class="consent-container" role="main">
            <div class="logo" aria-hidden="true">SBD</div>
            
            <h1 class="title">Authorize Application</h1>
            <p class="subtitle">Second Brain Database</p>
            
            <div class="client-info">
                <div class="client-name">{client_name}</div>
                {f'<div class="client-description">{client_description}</div>' if client_description else ''}
                {website_link}
            </div>
            
            {consent_status}
            
            <section class="permissions-section" aria-labelledby="permissions-title">
                <h2 id="permissions-title" class="permissions-title">This application is requesting access to:</h2>
                <ul class="scope-list" role="list">
                    {scope_items}
                </ul>
            </section>
            
            <form method="post" action="/oauth2/consent" aria-label="Authorization consent form">
                <input type="hidden" name="csrf_token" value="{csrf_token}">
                <input type="hidden" name="client_id" value="{client_id}">
                <input type="hidden" name="state" value="{state}">
                <input type="hidden" name="scopes" value="{','.join([s['scope'] for s in requested_scopes])}">
                
                <div class="actions" role="group" aria-label="Authorization decision">
                    <button type="submit" name="approved" value="true" class="btn btn-approve" aria-describedby="approve-help">
                        Approve
                    </button>
                    <button type="submit" name="approved" value="false" class="btn btn-deny" aria-describedby="deny-help">
                        Deny
                    </button>
                </div>
                <div id="approve-help" class="sr-only">Grant the requested permissions to this application</div>
                <div id="deny-help" class="sr-only">Refuse to grant permissions to this application</div>
            </form>
            
            <div class="security-notice">
                <strong>Security Notice:</strong> Only approve if you trust this application. 
                You can revoke access at any time from your account settings. 
                This application will only have access to the permissions listed above.
            </div>
        </div>
    </body>
    </html>
    """
    
    logger.debug(f"Rendered consent screen for client {client_name}")
    return html_template


def render_consent_error(error_message: str, client_name: str = None) -> str:
    """
    Render OAuth2 consent error screen HTML.
    
    Args:
        error_message: Error message to display
        client_name: Optional client name for context
        
    Returns:
        HTML string for consent error screen
    """
    
    # Use client name if provided, otherwise generic title
    page_title = f"Authorization Error - {client_name}" if client_name else "Authorization Error"
    client_info = f"<p class=\"client-name\">Application: {client_name}</p>" if client_name else ""
    
    html_template = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{page_title} - Second Brain Database</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                background: linear-gradient(135deg, #667eea 0%%, #764ba2 100%%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }}
            
            .error-container {{
                background: white;
                border-radius: 12px;
                box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
                max-width: 500px;
                width: 100%%;
                padding: 40px;
                text-align: center;
            }}
            
            .error-icon {{
                width: 60px;
                height: 60px;
                background: #e53e3e;
                border-radius: 50%%;
                margin: 0 auto 20px;
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
                font-size: 24px;
                font-weight: bold;
            }}
            
            .title {{
                font-size: 24px;
                font-weight: 600;
                color: #2d3748;
                margin-bottom: 8px;
            }}
            
            .subtitle {{
                color: #718096;
                margin-bottom: 30px;
                font-size: 16px;
            }}
            
            .client-name {{
                color: #4a5568;
                margin-bottom: 20px;
                font-weight: 500;
            }}
            
            .error-message {{
                background: #fed7d7;
                border: 1px solid #feb2b2;
                border-radius: 8px;
                padding: 20px;
                margin-bottom: 30px;
                color: #742a2a;
                line-height: 1.5;
            }}
            
            .actions {{
                display: flex;
                gap: 12px;
                justify-content: center;
                flex-wrap: wrap;
            }}
            
            .btn {{
                padding: 12px 24px;
                border-radius: 8px;
                font-weight: 600;
                font-size: 14px;
                text-decoration: none;
                cursor: pointer;
                border: none;
                transition: all 0.2s;
                min-width: 120px;
                display: inline-block;
            }}
            
            .btn-primary {{
                background: #667eea;
                color: white;
            }}
            
            .btn-primary:hover {{
                background: #5a67d8;
                transform: translateY(-1px);
            }}
            
            .btn-secondary {{
                background: #e2e8f0;
                color: #4a5568;
            }}
            
            .btn-secondary:hover {{
                background: #cbd5e0;
                transform: translateY(-1px);
            }}
            
            .help-text {{
                margin-top: 30px;
                padding: 15px;
                background: #edf2f7;
                border-radius: 8px;
                font-size: 14px;
                color: #4a5568;
                text-align: left;
            }}
            
            .help-text strong {{
                color: #2d3748;
            }}
            
            /* Focus styles for accessibility */
            .btn:focus {{
                outline: 2px solid #667eea;
                outline-offset: 2px;
            }}
            
            /* High contrast mode support */
            @media (prefers-contrast: high) {{
                .error-container {{
                    border: 2px solid #000;
                }}
                
                .btn {{
                    border: 2px solid currentColor;
                }}
            }}
            
            /* Reduced motion support */
            @media (prefers-reduced-motion: reduce) {{
                * {{
                    animation-duration: 0.01ms !important;
                    animation-iteration-count: 1 !important;
                    transition-duration: 0.01ms !important;
                }}
            }}
            
            @media (max-width: 480px) {{
                .error-container {{
                    padding: 30px 20px;
                }}
                
                .actions {{
                    flex-direction: column;
                }}
                
                .btn {{
                    width: 100%%;
                }}
            }}
        </style>
    </head>
    <body>
        <main class="error-container" role="main">
            <div class="error-icon" aria-hidden="true">!</div>
            
            <h1 class="title">Authorization Error</h1>
            <p class="subtitle">Second Brain Database</p>
            
            {client_info}
            
            <div class="error-message" role="alert">
                {error_message}
            </div>
            
            <div class="actions" role="group" aria-label="Available actions">
                <button onclick="history.back()" class="btn btn-secondary" aria-label="Go back to previous page">
                    Go Back
                </button>
                <a href="/auth/login" class="btn btn-primary" aria-label="Return to login page">
                    Return to Login
                </a>
            </div>
            
            <div class="help-text" role="complementary" aria-labelledby="help-title">
                <strong id="help-title">Need Help?</strong> If you continue to experience issues, please contact the application developer or system administrator. 
                Make sure you're using a supported browser and that cookies are enabled.
            </div>
        </main>
    </body>
    </html>
    """
    
    logger.debug(f"Rendered consent error screen: {error_message}")
    return html_template


def render_generic_oauth2_error(
    title: str,
    message: str,
    icon: str = "⚠️",
    show_login_button: bool = True,
    show_back_button: bool = True,
    additional_info: str = None
) -> str:
    """
    Render generic OAuth2 error screen HTML with customizable content.
    
    Args:
        title: Error title to display
        message: Error message to display
        icon: Emoji icon for the error
        show_login_button: Whether to show login button
        show_back_button: Whether to show back button
        additional_info: Optional additional information HTML
        
    Returns:
        HTML string for generic OAuth2 error screen
    """
    
    # Action buttons
    action_buttons = []
    if show_back_button:
        action_buttons.append('<button onclick="history.back()" class="btn btn-secondary" aria-label="Go back to previous page">Go Back</button>')
    if show_login_button:
        action_buttons.append('<a href="/auth/login" class="btn btn-primary" aria-label="Go to login page">Login</a>')
    
    actions_html = ""
    if action_buttons:
        actions_html = f"""
        <div class="error-actions" role="group" aria-label="Available actions">
            {' '.join(action_buttons)}
        </div>
        """
    
    # Additional info section
    additional_info_html = ""
    if additional_info:
        additional_info_html = f"""
        <div class="additional-info" role="complementary">
            {additional_info}
        </div>
        """
    
    html_template = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title} - Second Brain Database</title>
        <meta name="robots" content="noindex, nofollow">
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                background: linear-gradient(135deg, #667eea 0%%, #764ba2 100%%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
                color: #333;
            }}
            
            .error-container {{
                background: white;
                border-radius: 12px;
                box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
                padding: 40px;
                width: 100%%;
                max-width: 500px;
                text-align: center;
                position: relative;
            }}
            
            .error-icon {{
                font-size: 48px;
                margin-bottom: 20px;
                animation: pulse 2s infinite;
            }}
            
            @keyframes pulse {{
                0%% {{ transform: scale(1); }}
                50%% {{ transform: scale(1.05); }}
                100%% {{ transform: scale(1); }}
            }}
            
            .error-title {{
                color: #333;
                font-size: 24px;
                font-weight: 600;
                margin-bottom: 16px;
            }}
            
            .error-message {{
                color: #666;
                font-size: 16px;
                line-height: 1.5;
                margin-bottom: 30px;
            }}
            
            .additional-info {{
                background: #f8f9fa;
                border: 1px solid #e9ecef;
                border-radius: 8px;
                padding: 16px;
                margin-bottom: 30px;
                font-size: 14px;
                color: #6c757d;
                text-align: left;
            }}
            
            .error-actions {{
                display: flex;
                gap: 12px;
                justify-content: center;
                flex-wrap: wrap;
            }}
            
            .btn {{
                padding: 12px 24px;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
                cursor: pointer;
                text-decoration: none;
                display: inline-block;
                transition: all 0.2s;
                min-width: 100px;
            }}
            
            .btn-primary {{
                background: #667eea;
                color: white;
            }}
            
            .btn-primary:hover {{
                background: #5a6fd8;
                transform: translateY(-1px);
                box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
            }}
            
            .btn-secondary {{
                background: #6c757d;
                color: white;
            }}
            
            .btn-secondary:hover {{
                background: #5a6268;
                transform: translateY(-1px);
                box-shadow: 0 4px 12px rgba(108, 117, 125, 0.3);
            }}
            
            .security-notice {{
                position: absolute;
                top: 10px;
                right: 15px;
                font-size: 12px;
                color: #999;
                opacity: 0.7;
            }}
            
            /* Focus styles for accessibility */
            .btn:focus {{
                outline: 2px solid #667eea;
                outline-offset: 2px;
            }}
            
            /* High contrast mode support */
            @media (prefers-contrast: high) {{
                .error-container {{
                    border: 2px solid #000;
                }}
                
                .btn {{
                    border: 2px solid currentColor;
                }}
            }}
            
            /* Reduced motion support */
            @media (prefers-reduced-motion: reduce) {{
                * {{
                    animation-duration: 0.01ms !important;
                    animation-iteration-count: 1 !important;
                    transition-duration: 0.01ms !important;
                }}
            }}
            
            @media (max-width: 480px) {{
                .error-container {{
                    padding: 30px 20px;
                }}
                
                .error-title {{
                    font-size: 20px;
                }}
                
                .error-actions {{
                    flex-direction: column;
                }}
                
                .security-notice {{
                    position: static;
                    margin-top: 20px;
                    text-align: center;
                }}
            }}
        </style>
    </head>
    <body>
        <main class="error-container" role="main">
            <div class="security-notice" aria-label="Secure connection indicator">🔒 Secure</div>
            <div class="error-icon" aria-hidden="true">{icon}</div>
            <h1 class="error-title">{title}</h1>
            <p class="error-message" role="alert">
                {message}
            </p>
            {additional_info_html}
            {actions_html}
        </main>
    </body>
    </html>
    """
    
    logger.debug(f"Rendered generic OAuth2 error screen: {title}")
    return html_template


def render_authorization_failed_error(
    message: str = None,
    client_name: str = None,
    error_details: str = None,
    show_retry_button: bool = True
) -> str:
    """
    Render OAuth2 authorization failed error screen HTML.
    
    Args:
        message: Optional custom message
        client_name: Optional client name for context
        error_details: Optional detailed error information
        show_retry_button: Whether to show retry button
        
    Returns:
        HTML string for authorization failed error screen
    """
    
    default_message = "The authorization process failed. This could be due to an invalid request, expired session, or server error."
    if client_name:
        default_message = f"The authorization process for {client_name} failed. This could be due to an invalid request, expired session, or server error."
    
    display_message = message or default_message
    
    # Client info section
    client_info_html = ""
    if client_name:
        client_info_html = f'<p class="client-name">Application: {client_name}</p>'
    
    # Error details section
    error_details_html = ""
    if error_details:
        error_details_html = f"""
        <div class="error-details">
            <strong>Error Details:</strong><br>
            {error_details}
        </div>
        """
    
    # Action buttons
    action_buttons = ['<button onclick="history.back()" class="btn btn-secondary" aria-label="Go back to previous page">Go Back</button>']
    if show_retry_button:
        action_buttons.append('<a href="javascript:location.reload()" class="btn btn-primary" aria-label="Retry the authorization process">Retry</a>')
    
    actions_html = f"""
    <div class="error-actions" role="group" aria-label="Available actions">
        {' '.join(action_buttons)}
    </div>
    """
    
    html_template = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Authorization Failed - Second Brain Database</title>
        <meta name="robots" content="noindex, nofollow">
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                background: linear-gradient(135deg, #667eea 0%%, #764ba2 100%%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
                color: #333;
            }}
            
            .error-container {{
                background: white;
                border-radius: 12px;
                box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
                padding: 40px;
                width: 100%%;
                max-width: 500px;
                text-align: center;
                position: relative;
            }}
            
            .error-icon {{
                font-size: 48px;
                color: #e74c3c;
                margin-bottom: 20px;
                animation: shake 0.5s ease-in-out;
            }}
            
            @keyframes shake {{
                0%%, 100%% {{ transform: translateX(0); }}
                25%% {{ transform: translateX(-5px); }}
                75%% {{ transform: translateX(5px); }}
            }}
            
            .error-title {{
                color: #333;
                font-size: 24px;
                font-weight: 600;
                margin-bottom: 16px;
            }}
            
            .client-name {{
                color: #4a5568;
                margin-bottom: 20px;
                font-weight: 500;
            }}
            
            .error-message {{
                color: #666;
                font-size: 16px;
                line-height: 1.5;
                margin-bottom: 30px;
            }}
            
            .error-details {{
                background: #f8f9fa;
                border: 1px solid #e9ecef;
                border-radius: 8px;
                padding: 16px;
                margin-bottom: 30px;
                font-size: 14px;
                color: #6c757d;
                text-align: left;
                word-break: break-word;
            }}
            
            .error-actions {{
                display: flex;
                gap: 12px;
                justify-content: center;
                flex-wrap: wrap;
            }}
            
            .btn {{
                padding: 12px 24px;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
                cursor: pointer;
                text-decoration: none;
                display: inline-block;
                transition: all 0.2s;
                min-width: 100px;
            }}
            
            .btn-primary {{
                background: #667eea;
                color: white;
            }}
            
            .btn-primary:hover {{
                background: #5a6fd8;
                transform: translateY(-1px);
                box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
            }}
            
            .btn-secondary {{
                background: #6c757d;
                color: white;
            }}
            
            .btn-secondary:hover {{
                background: #5a6268;
                transform: translateY(-1px);
                box-shadow: 0 4px 12px rgba(108, 117, 125, 0.3);
            }}
            
            .security-notice {{
                position: absolute;
                top: 10px;
                right: 15px;
                font-size: 12px;
                color: #999;
                opacity: 0.7;
            }}
            
            .troubleshooting {{
                background: #e3f2fd;
                border: 1px solid #bbdefb;
                border-radius: 8px;
                padding: 16px;
                margin-bottom: 30px;
                font-size: 14px;
                color: #1976d2;
                text-align: left;
            }}
            
            .troubleshooting strong {{
                color: #0d47a1;
            }}
            
            /* Focus styles for accessibility */
            .btn:focus {{
                outline: 2px solid #667eea;
                outline-offset: 2px;
            }}
            
            /* High contrast mode support */
            @media (prefers-contrast: high) {{
                .error-container {{
                    border: 2px solid #000;
                }}
                
                .btn {{
                    border: 2px solid currentColor;
                }}
            }}
            
            /* Reduced motion support */
            @media (prefers-reduced-motion: reduce) {{
                * {{
                    animation-duration: 0.01ms !important;
                    animation-iteration-count: 1 !important;
                    transition-duration: 0.01ms !important;
                }}
            }}
            
            @media (max-width: 480px) {{
                .error-container {{
                    padding: 30px 20px;
                }}
                
                .error-title {{
                    font-size: 20px;
                }}
                
                .error-actions {{
                    flex-direction: column;
                }}
                
                .security-notice {{
               

"""

def render_oauth2_authorization_error(error_message: str, error_details: str = None, client_name: str = None) -> str:
    """
    Render OAuth2 authorization error screen HTML.
    
    Args:
        error_message: Main error message to display
        error_details: Optional detailed error information
        client_name: Optional client name for context
        
    Returns:
        HTML string for OAuth2 authorization error screen
    """
    
    # Use client name if provided, otherwise generic title
    page_title = f"Authorization Error - {client_name}" if client_name else "OAuth2 Authorization Error"
    client_info = f"<p class=\"client-name\">Application: {client_name}</p>" if client_name else ""
    
    # Error details section
    error_details_html = ""
    if error_details:
        error_details_html = f"""
        <div class="error-details">
            <strong>Error Details:</strong><br>
            {error_details}
        </div>
        """
    
    html_template = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{page_title} - Second Brain Database</title>
        <meta name="robots" content="noindex, nofollow">
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                background: linear-gradient(135deg, #667eea 0%%, #764ba2 100%%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
                color: #333;
            }}
            
            .error-container {{
                background: white;
                border-radius: 12px;
                box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
                padding: 40px;
                width: 100%%;
                max-width: 500px;
                text-align: center;
                position: relative;
            }}
            
            .error-icon {{
                font-size: 48px;
                color: #e74c3c;
                margin-bottom: 20px;
                animation: pulse 2s infinite;
            }}
            
            @keyframes pulse {{
                0%% {{ transform: scale(1); }}
                50%% {{ transform: scale(1.05); }}
                100%% {{ transform: scale(1); }}
            }}
            
            .error-title {{
                color: #333;
                font-size: 24px;
                font-weight: 600;
                margin-bottom: 16px;
            }}
            
            .client-name {{
                color: #4a5568;
                margin-bottom: 20px;
                font-weight: 500;
            }}
            
            .error-message {{
                color: #666;
                font-size: 16px;
                line-height: 1.5;
                margin-bottom: 30px;
            }}
            
            .error-details {{
                background: #f8f9fa;
                border: 1px solid #e9ecef;
                border-radius: 8px;
                padding: 16px;
                margin-bottom: 30px;
                font-size: 14px;
                color: #6c757d;
                text-align: left;
                word-break: break-word;
            }}
            
            .error-help {{
                background: #e3f2fd;
                border: 1px solid #bbdefb;
                border-radius: 8px;
                padding: 16px;
                margin-bottom: 30px;
                font-size: 14px;
                color: #1976d2;
                text-align: left;
            }}
            
            .error-help strong {{
                color: #0d47a1;
            }}
            
            .error-actions {{
                display: flex;
                gap: 12px;
                justify-content: center;
                flex-wrap: wrap;
            }}
            
            .btn {{
                padding: 12px 24px;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
                cursor: pointer;
                text-decoration: none;
                display: inline-block;
                transition: all 0.2s;
                min-width: 100px;
            }}
            
            .btn-primary {{
                background: #667eea;
                color: white;
            }}
            
            .btn-primary:hover {{
                background: #5a6fd8;
                transform: translateY(-1px);
                box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
            }}
            
            .btn-secondary {{
                background: #6c757d;
                color: white;
            }}
            
            .btn-secondary:hover {{
                background: #5a6268;
                transform: translateY(-1px);
                box-shadow: 0 4px 12px rgba(108, 117, 125, 0.3);
            }}
            
            .security-notice {{
                position: absolute;
                top: 10px;
                right: 15px;
                font-size: 12px;
                color: #999;
                opacity: 0.7;
            }}
            
            /* Focus styles for accessibility */
            .btn:focus {{
                outline: 2px solid #667eea;
                outline-offset: 2px;
            }}
            
            /* High contrast mode support */
            @media (prefers-contrast: high) {{
                .error-container {{
                    border: 2px solid #000;
                }}
                
                .btn {{
                    border: 2px solid currentColor;
                }}
            }}
            
            /* Reduced motion support */
            @media (prefers-reduced-motion: reduce) {{
                * {{
                    animation-duration: 0.01ms !important;
                    animation-iteration-count: 1 !important;
                    transition-duration: 0.01ms !important;
                }}
            }}
            
            @media (max-width: 480px) {{
                .error-container {{
                    padding: 30px 20px;
                }}
                
                .error-title {{
                    font-size: 20px;
                }}
                
                .error-actions {{
                    flex-direction: column;
                }}
                
                .security-notice {{
                    position: static;
                    margin-top: 20px;
                    text-align: center;
                }}
            }}
        </style>
    </head>
    <body>
        <main class="error-container" role="main">
            <div class="security-notice" aria-label="Secure connection indicator">🔒 Secure</div>
            <div class="error-icon" aria-hidden="true">⚠️</div>
            <h1 class="error-title">OAuth2 Authorization Error</h1>
            {client_info}
            <p class="error-message" role="alert">
                {error_message}
            </p>
            {error_details_html}
            <section class="error-help" role="complementary" aria-labelledby="help-title">
                <strong id="help-title">What can you do?</strong><br>
                • Check that the application URL is correct<br>
                • Ensure you're using a supported browser<br>
                • Try clearing your browser cookies and cache<br>
                • Contact the application developer if the problem persists
            </section>
            <div class="error-actions" role="group" aria-label="Available actions">
                <a href="javascript:history.back()" class="btn btn-primary" aria-label="Go back to previous page">Go Back</a>
                <a href="/auth/login" class="btn btn-secondary" aria-label="Go to login page">Login</a>
            </div>
        </main>
    </body>
    </html>
    """
    
    logger.debug(f"Rendered OAuth2 authorization error screen: {error_message}")
    return html_template


def render_session_expired_error(message: str = None, show_login_button: bool = True) -> str:
    """
    Render OAuth2 session expired error screen HTML.
    
    Args:
        message: Optional custom message, defaults to standard session expired message
        show_login_button: Whether to show the login button
        
    Returns:
        HTML string for session expired error screen
    """
    
    default_message = "Your authorization session has expired for security reasons. Please start the authorization process again."
    display_message = message or default_message
    
    login_button = ""
    if show_login_button:
        login_button = '<a href="/auth/login" class="btn btn-primary" aria-label="Go to login page to sign in again">Login Again</a>'
    
    html_template = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Session Expired - Second Brain Database</title>
        <meta name="robots" content="noindex, nofollow">
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                background: linear-gradient(135deg, #667eea 0%%, #764ba2 100%%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }}
            
            .error-container {{
                background: white;
                border-radius: 12px;
                box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
                padding: 40px;
                width: 100%%;
                max-width: 500px;
                text-align: center;
            }}
            
            .error-icon {{
                font-size: 48px;
                color: #f39c12;
                margin-bottom: 20px;
                animation: fadeIn 1s ease-in;
            }}
            
            @keyframes fadeIn {{
                from {{ opacity: 0; transform: scale(0.8); }}
                to {{ opacity: 1; transform: scale(1); }}
            }}
            
            .error-title {{
                color: #333;
                font-size: 24px;
                font-weight: 600;
                margin-bottom: 16px;
            }}
            
            .error-message {{
                color: #666;
                font-size: 16px;
                line-height: 1.5;
                margin-bottom: 30px;
            }}
            
            .error-actions {{
                display: flex;
                gap: 12px;
                justify-content: center;
                flex-wrap: wrap;
            }}
            
            .btn {{
                padding: 12px 24px;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
                cursor: pointer;
                text-decoration: none;
                display: inline-block;
                transition: all 0.2s;
                min-width: 120px;
            }}
            
            .btn-primary {{
                background: #667eea;
                color: white;
            }}
            
            .btn-primary:hover {{
                background: #5a6fd8;
                transform: translateY(-1px);
                box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
            }}
            
            .btn-secondary {{
                background: #6c757d;
                color: white;
            }}
            
            .btn-secondary:hover {{
                background: #5a6268;
                transform: translateY(-1px);
                box-shadow: 0 4px 12px rgba(108, 117, 125, 0.3);
            }}
            
            .security-info {{
                margin-top: 30px;
                padding: 15px;
                background: #f8f9fa;
                border-radius: 8px;
                font-size: 14px;
                color: #6c757d;
                text-align: left;
            }}
            
            .security-info strong {{
                color: #495057;
            }}
            
            /* Focus styles for accessibility */
            .btn:focus {{
                outline: 2px solid #667eea;
                outline-offset: 2px;
            }}
            
            /* High contrast mode support */
            @media (prefers-contrast: high) {{
                .error-container {{
                    border: 2px solid #000;
                }}
                
                .btn {{
                    border: 2px solid currentColor;
                }}
            }}
            
            /* Reduced motion support */
            @media (prefers-reduced-motion: reduce) {{
                * {{
                    animation-duration: 0.01ms !important;
                    animation-iteration-count: 1 !important;
                    transition-duration: 0.01ms !important;
                }}
            }}
            
            @media (max-width: 480px) {{
                .error-container {{
                    padding: 30px 20px;
                }}
                
                .error-title {{
                    font-size: 20px;
                }}
                
                .error-actions {{
                    flex-direction: column;
                }}
            }}
        </style>
    </head>
    <body>
        <main class="error-container" role="main">
            <div class="error-icon" aria-hidden="true">⏰</div>
            <h1 class="error-title">Session Expired</h1>
            <p class="error-message" role="alert">
                {display_message}
            </p>
            <div class="error-actions" role="group" aria-label="Available actions">
                {login_button}
                <a href="javascript:history.back()" class="btn btn-secondary" aria-label="Go back to previous page">Go Back</a>
            </div>
            <section class="security-info" role="complementary" aria-labelledby="security-title">
                <strong id="security-title">Security Notice:</strong> Sessions expire automatically to protect your account. 
                This is a normal security measure to prevent unauthorized access.
            </section>
        </main>
    </body>
    </html>
    """
    
    logger.debug(f"Rendered session expired error screen: {display_message}")
    return html_template


def render_authorization_failed_error(
    message: str = None,
    client_name: str = None,
    error_details: str = None,
    show_retry_button: bool = True
) -> str:
    """
    Render OAuth2 authorization failed error screen HTML.
    
    Args:
        message: Optional custom message, defaults to standard authorization failed message
        show_retry_button: Whether to show the retry button
        
    Returns:
        HTML string for authorization failed error screen
    """
    
    default_message = "Failed to resume the authorization process. This may be due to a temporary system issue. Please try starting the authorization again."
    display_message = message or default_message
    
    retry_button = ""
    if show_retry_button:
        retry_button = '<a href="/auth/login" class="btn btn-primary" aria-label="Try authorization process again">Try Again</a>'
    
    html_template = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Authorization Failed - Second Brain Database</title>
        <meta name="robots" content="noindex, nofollow">
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                background: linear-gradient(135deg, #667eea 0%%, #764ba2 100%%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }}
            
            .error-container {{
                background: white;
                border-radius: 12px;
                box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
                padding: 40px;
                width: 100%%;
                max-width: 500px;
                text-align: center;
            }}
            
            .error-icon {{
                font-size: 48px;
                color: #e74c3c;
                margin-bottom: 20px;
                animation: shake 0.5s ease-in-out;
            }}
            
            @keyframes shake {{
                0%%, 100%% {{ transform: translateX(0); }}
                25%% {{ transform: translateX(-5px); }}
                75%% {{ transform: translateX(5px); }}
            }}
            
            .error-title {{
                color: #333;
                font-size: 24px;
                font-weight: 600;
                margin-bottom: 16px;
            }}
            
            .error-message {{
                color: #666;
                font-size: 16px;
                line-height: 1.5;
                margin-bottom: 30px;
            }}
            
            .error-actions {{
                display: flex;
                gap: 12px;
                justify-content: center;
                flex-wrap: wrap;
            }}
            
            .btn {{
                padding: 12px 24px;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
                cursor: pointer;
                text-decoration: none;
                display: inline-block;
                transition: all 0.2s;
                min-width: 120px;
            }}
            
            .btn-primary {{
                background: #667eea;
                color: white;
            }}
            
            .btn-primary:hover {{
                background: #5a6fd8;
                transform: translateY(-1px);
                box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
            }}
            
            .btn-secondary {{
                background: #6c757d;
                color: white;
            }}
            
            .btn-secondary:hover {{
                background: #5a6268;
                transform: translateY(-1px);
                box-shadow: 0 4px 12px rgba(108, 117, 125, 0.3);
            }}
            
            .troubleshooting {{
                margin-top: 30px;
                padding: 15px;
                background: #fff3cd;
                border: 1px solid #ffeaa7;
                border-radius: 8px;
                font-size: 14px;
                color: #856404;
                text-align: left;
            }}
            
            .troubleshooting strong {{
                color: #533f03;
            }}
            
            /* Focus styles for accessibility */
            .btn:focus {{
                outline: 2px solid #667eea;
                outline-offset: 2px;
            }}
            
            /* High contrast mode support */
            @media (prefers-contrast: high) {{
                .error-container {{
                    border: 2px solid #000;
                }}
                
                .btn {{
                    border: 2px solid currentColor;
                }}
            }}
            
            /* Reduced motion support */
            @media (prefers-reduced-motion: reduce) {{
                * {{
                    animation-duration: 0.01ms !important;
                    animation-iteration-count: 1 !important;
                    transition-duration: 0.01ms !important;
                }}
            }}
            
            @media (max-width: 480px) {{
                .error-container {{
                    padding: 30px 20px;
                }}
                
                .error-title {{
                    font-size: 20px;
                }}
                
                .error-actions {{
                    flex-direction: column;
                }}
            }}
        </style>
    </head>
    <body>
        <main class="error-container" role="main">
            <div class="error-icon" aria-hidden="true">❌</div>
            <h1 class="error-title">Authorization Failed</h1>
            <p class="error-message" role="alert">
                {display_message}
            </p>
            <div class="error-actions" role="group" aria-label="Available actions">
                {retry_button}
                <a href="javascript:history.back()" class="btn btn-secondary" aria-label="Go back to previous page">Go Back</a>
            </div>
            <section class="troubleshooting" role="complementary" aria-labelledby="troubleshooting-title">
                <strong id="troubleshooting-title">Troubleshooting Tips:</strong><br>
                • Check your internet connection<br>
                • Try refreshing the page<br>
                • Clear your browser cache and cookies<br>
                • Contact support if the problem persists
            </section>
        </main>
    </body>
    </html>
    """
    
    logger.debug(f"Rendered authorization failed error screen: {display_message}")
    return html_template


def render_generic_oauth2_error(
    title: str,
    message: str,
    icon: str = "⚠️",
    show_login_button: bool = True,
    show_back_button: bool = True,
    additional_info: str = None
) -> str:
    """
    Render a generic OAuth2 error screen HTML with customizable content.
    
    Args:
        title: Error page title
        message: Main error message
        icon: Emoji icon to display (default: ⚠️)
        show_login_button: Whether to show login button
        show_back_button: Whether to show back button
        additional_info: Optional additional information to display
        
    Returns:
        HTML string for generic OAuth2 error screen
    """
    
    login_button = ""
    if show_login_button:
        login_button = '<a href="/auth/login" class="btn btn-primary" aria-label="Return to login page">Return to Login</a>'
    
    back_button = ""
    if show_back_button:
        back_button = '<a href="javascript:history.back()" class="btn btn-secondary" aria-label="Go back to previous page">Go Back</a>'
    
    additional_info_html = ""
    if additional_info:
        additional_info_html = f"""
        <section class="additional-info" role="complementary">
            {additional_info}
        </section>
        """
    
    html_template = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title} - Second Brain Database</title>
        <meta name="robots" content="noindex, nofollow">
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                background: linear-gradient(135deg, #667eea 0%%, #764ba2 100%%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }}
            
            .error-container {{
                background: white;
                border-radius: 12px;
                box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
                padding: 40px;
                width: 100%%;
                max-width: 500px;
                text-align: center;
            }}
            
            .error-icon {{
                font-size: 48px;
                margin-bottom: 20px;
                animation: fadeIn 1s ease-in;
            }}
            
            @keyframes fadeIn {{
                from {{ opacity: 0; transform: scale(0.8); }}
                to {{ opacity: 1; transform: scale(1); }}
            }}
            
            .error-title {{
                color: #333;
                font-size: 24px;
                font-weight: 600;
                margin-bottom: 16px;
            }}
            
            .error-message {{
                color: #666;
                font-size: 16px;
                line-height: 1.5;
                margin-bottom: 30px;
            }}
            
            .additional-info {{
                background: #f8f9fa;
                border: 1px solid #e9ecef;
                border-radius: 8px;
                padding: 16px;
                margin-bottom: 30px;
                font-size: 14px;
                color: #6c757d;
                text-align: left;
            }}
            
            /* Focus styles for accessibility */
            .btn:focus {{
                outline: 2px solid #667eea;
                outline-offset: 2px;
            }}
            
            /* High contrast mode support */
            @media (prefers-contrast: high) {{
                .error-container {{
                    border: 2px solid #000;
                }}
                
                .btn {{
                    border: 2px solid currentColor;
                }}
            }}
            
            /* Reduced motion support */
            @media (prefers-reduced-motion: reduce) {{
                * {{
                    animation-duration: 0.01ms !important;
                    animation-iteration-count: 1 !important;
                    transition-duration: 0.01ms !important;
                }}
            }}
            
            .error-actions {{
                display: flex;
                gap: 12px;
                justify-content: center;
                flex-wrap: wrap;
            }}
            
            .btn {{
                padding: 12px 24px;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
                cursor: pointer;
                text-decoration: none;
                display: inline-block;
                transition: all 0.2s;
                min-width: 120px;
            }}
            
            .btn-primary {{
                background: #667eea;
                color: white;
            }}
            
            .btn-primary:hover {{
                background: #5a6fd8;
                transform: translateY(-1px);
                box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
            }}
            
            .btn-secondary {{
                background: #6c757d;
                color: white;
            }}
            
            .btn-secondary:hover {{
                background: #5a6268;
                transform: translateY(-1px);
                box-shadow: 0 4px 12px rgba(108, 117, 125, 0.3);
            }}
            
            @media (max-width: 480px) {{
                .error-container {{
                    padding: 30px 20px;
                }}
                
                .error-title {{
                    font-size: 20px;
                }}
                
                .error-actions {{
                    flex-direction: column;
                }}
            }}
        </style>
    </head>
    <body>
        <main class="error-container" role="main">
            <div class="security-notice" aria-label="Secure connection indicator">🔒 Secure</div>
            <div class="error-icon" aria-hidden="true">{icon}</div>
            <h1 class="error-title">{title}</h1>
            <p class="error-message" role="alert">
                {message}
            </p>
            {additional_info_html}
            <div class="error-actions" role="group" aria-label="Available actions">
                {login_button}
                {back_button}
            </div>
        </main>
    </body>
    </html>
    """
    
    logger.debug(f"Rendered generic OAuth2 error screen: {title}")
    return html_template


def render_invalid_client_error(client_name: str = None, client_id: str = None) -> str:
    """
    Render OAuth2 invalid client error screen HTML.
    
    Args:
        client_name: Human-readable name of the client application
        client_id: OAuth2 client identifier
        
    Returns:
        HTML string for invalid client error screen
    """
    
    display_name = client_name or client_id or "Unknown Application"
    
    html_template = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Application Not Found - Second Brain Database</title>
        <meta name="robots" content="noindex, nofollow">
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                background: linear-gradient(135deg, #667eea 0%%, #764ba2 100%%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }}
            
            .error-container {{
                background: white;
                border-radius: 12px;
                box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
                padding: 40px;
                width: 100%%;
                max-width: 500px;
                text-align: center;
            }}
            
            .error-icon {{
                font-size: 64px;
                color: #e74c3c;
                margin-bottom: 20px;
                animation: bounce 2s infinite;
            }}
            
            @keyframes bounce {{
                0%%, 20%%, 50%%, 80%%, 100%% {{ transform: translateY(0); }}
                40%% {{ transform: translateY(-10px); }}
                60%% {{ transform: translateY(-5px); }}
            }}
            
            .error-title {{
                color: #333;
                font-size: 28px;
                font-weight: 600;
                margin-bottom: 16px;
            }}
            
            .client-name {{
                color: #666;
                font-size: 18px;
                margin-bottom: 20px;
                font-weight: 500;
                background: #f8f9fa;
                padding: 12px;
                border-radius: 8px;
                border: 1px solid #e9ecef;
            }}
            
            .error-message {{
                color: #666;
                font-size: 16px;
                line-height: 1.6;
                margin-bottom: 30px;
            }}
            
            .error-reasons {{
                background: #fff3cd;
                border: 1px solid #ffeaa7;
                border-radius: 8px;
                padding: 20px;
                margin-bottom: 30px;
                text-align: left;
            }}
            
            .error-reasons h3 {{
                color: #856404;
                font-size: 16px;
                font-weight: 600;
                margin-bottom: 12px;
            }}
            
            .error-reasons ul {{
                color: #856404;
                font-size: 14px;
                line-height: 1.5;
                margin-left: 20px;
            }}
            
            .error-reasons li {{
                margin-bottom: 8px;
            }}
            
            .error-actions {{
                display: flex;
                gap: 12px;
                justify-content: center;
                flex-wrap: wrap;
            }}
            
            .btn {{
                padding: 12px 24px;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
                cursor: pointer;
                text-decoration: none;
                display: inline-block;
                transition: all 0.2s;
                min-width: 120px;
            }}
            
            .btn-primary {{
                background: #667eea;
                color: white;
            }}
            
            .btn-primary:hover {{
                background: #5a6fd8;
                transform: translateY(-1px);
                box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
            }}
            
            .btn-secondary {{
                background: #6c757d;
                color: white;
            }}
            
            .btn-secondary:hover {{
                background: #5a6268;
                transform: translateY(-1px);
                box-shadow: 0 4px 12px rgba(108, 117, 125, 0.3);
            }}
            
            .help-section {{
                margin-top: 30px;
                padding: 20px;
                background: #e3f2fd;
                border: 1px solid #bbdefb;
                border-radius: 8px;
                text-align: left;
            }}
            
            .help-section h3 {{
                color: #1976d2;
                font-size: 16px;
                font-weight: 600;
                margin-bottom: 12px;
            }}
            
            .help-section p {{
                color: #1976d2;
                font-size: 14px;
                line-height: 1.5;
                margin-bottom: 8px;
            }}
            
            /* Focus styles for accessibility */
            .btn:focus {{
                outline: 2px solid #667eea;
                outline-offset: 2px;
            }}
            
            /* High contrast mode support */
            @media (prefers-contrast: high) {{
                .error-container {{
                    border: 2px solid #000;
                }}
                
                .btn {{
                    border: 2px solid currentColor;
                }}
            }}
            
            /* Reduced motion support */
            @media (prefers-reduced-motion: reduce) {{
                * {{
                    animation-duration: 0.01ms !important;
                    animation-iteration-count: 1 !important;
                    transition-duration: 0.01ms !important;
                }}
            }}
            
            @media (max-width: 480px) {{
                .error-container {{
                    padding: 30px 20px;
                }}
                
                .error-title {{
                    font-size: 24px;
                }}
                
                .error-actions {{
                    flex-direction: column;
                }}
            }}
        </style>
    </head>
    <body>
        <main class="error-container" role="main">
            <div class="error-icon" aria-hidden="true">🚫</div>
            <h1 class="error-title">Application Not Found</h1>
            <div class="client-name">Application: {display_name}</div>
            <p class="error-message" role="alert">
                The application you're trying to authorize is not available or has been disabled. 
                This could be due to several reasons listed below.
            </p>
            
            <section class="error-reasons" role="complementary" aria-labelledby="reasons-title">
                <h3 id="reasons-title">Possible Reasons:</h3>
                <ul>
                    <li>The application has been removed or disabled by its developer</li>
                    <li>The application is not properly registered with our system</li>
                    <li>The authorization link you used is incorrect or outdated</li>
                    <li>The application is temporarily unavailable for maintenance</li>
                </ul>
            </section>
            
            <div class="error-actions" role="group" aria-label="Available actions">
                <a href="javascript:history.back()" class="btn btn-primary" aria-label="Go back to previous page">Go Back</a>
                <a href="/auth/login" class="btn btn-secondary" aria-label="Go to login page">Login</a>
            </div>
            
            <section class="help-section" role="complementary" aria-labelledby="help-title">
                <h3 id="help-title">Need Help?</h3>
                <p><strong>For Users:</strong> Contact the application developer or check their website for updated authorization links.</p>
                <p><strong>For Developers:</strong> Ensure your application is properly registered and active in the developer console.</p>
                <p><strong>Still Having Issues?</strong> Contact our support team with the application name and this error message.</p>
            </section>
        </main>
    </body>
    </html>
    """
    
    logger.debug(f"Rendered invalid client error screen for: {display_name}")
    return html_template


def render_rate_limit_error(retry_after: int = None) -> str:
    """
    Render OAuth2 rate limit error screen HTML.
    
    Args:
        retry_after: Optional seconds until retry is allowed
        
    Returns:
        HTML string for rate limit error screen
    """
    
    retry_message = ""
    if retry_after:
        minutes = retry_after // 60
        seconds = retry_after % 60
        if minutes > 0:
            retry_message = f"Please wait {minutes} minute{'s' if minutes != 1 else ''} and {seconds} second{'s' if seconds != 1 else ''} before trying again."
        else:
            retry_message = f"Please wait {seconds} second{'s' if seconds != 1 else ''} before trying again."
    else:
        retry_message = "Please wait a few minutes before trying again."
    
    html_template = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Too Many Requests - Second Brain Database</title>
        <meta name="robots" content="noindex, nofollow">
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                background: linear-gradient(135deg, #667eea 0%%, #764ba2 100%%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }}
            
            .error-container {{
                background: white;
                border-radius: 12px;
                box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
                padding: 40px;
                width: 100%%;
                max-width: 500px;
                text-align: center;
            }}
            
            .error-icon {{
                font-size: 64px;
                color: #f39c12;
                margin-bottom: 20px;
                animation: pulse 2s infinite;
            }}
            
            @keyframes pulse {{
                0%% {{ transform: scale(1); opacity: 1; }}
                50%% {{ transform: scale(1.1); opacity: 0.7; }}
                100%% {{ transform: scale(1); opacity: 1; }}
            }}
            
            .error-title {{
                color: #333;
                font-size: 28px;
                font-weight: 600;
                margin-bottom: 16px;
            }}
            
            .error-message {{
                color: #666;
                font-size: 16px;
                line-height: 1.6;
                margin-bottom: 20px;
            }}
            
            .retry-message {{
                background: #fff3cd;
                border: 1px solid #ffeaa7;
                border-radius: 8px;
                padding: 16px;
                margin-bottom: 30px;
                color: #856404;
                font-weight: 500;
            }}
            
            .countdown {{
                font-size: 24px;
                font-weight: 600;
                color: #f39c12;
                margin: 20px 0;
                font-family: 'Courier New', monospace;
            }}
            
            .explanation {{
                background: #e3f2fd;
                border: 1px solid #bbdefb;
                border-radius: 8px;
                padding: 20px;
                margin-bottom: 30px;
                text-align: left;
            }}
            
            .explanation h3 {{
                color: #1976d2;
                font-size: 16px;
                font-weight: 600;
                margin-bottom: 12px;
            }}
            
            .explanation p {{
                color: #1976d2;
                font-size: 14px;
                line-height: 1.5;
                margin-bottom: 8px;
            }}
            
            .error-actions {{
                display: flex;
                gap: 12px;
                justify-content: center;
                flex-wrap: wrap;
            }}
            
            .btn {{
                padding: 12px 24px;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
                cursor: pointer;
                text-decoration: none;
                display: inline-block;
                transition: all 0.2s;
                min-width: 120px;
            }}
            
            .btn-primary {{
                background: #667eea;
                color: white;
            }}
            
            .btn-primary:hover {{
                background: #5a6fd8;
                transform: translateY(-1px);
                box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
            }}
            
            .btn-secondary {{
                background: #6c757d;
                color: white;
            }}
            
            .btn-secondary:hover {{
                background: #5a6268;
                transform: translateY(-1px);
                box-shadow: 0 4px 12px rgba(108, 117, 125, 0.3);
            }}
            
            .btn:disabled {{
                opacity: 0.6;
                cursor: not-allowed;
                transform: none !important;
                box-shadow: none !important;
            }}
            
            /* Focus styles for accessibility */
            .btn:focus {{
                outline: 2px solid #667eea;
                outline-offset: 2px;
            }}
            
            /* High contrast mode support */
            @media (prefers-contrast: high) {{
                .error-container {{
                    border: 2px solid #000;
                }}
                
                .btn {{
                    border: 2px solid currentColor;
                }}
            }}
            
            /* Reduced motion support */
            @media (prefers-reduced-motion: reduce) {{
                * {{
                    animation-duration: 0.01ms !important;
                    animation-iteration-count: 1 !important;
                    transition-duration: 0.01ms !important;
                }}
            }}
            
            @media (max-width: 480px) {{
                .error-container {{
                    padding: 30px 20px;
                }}
                
                .error-title {{
                    font-size: 24px;
                }}
                
                .error-actions {{
                    flex-direction: column;
                }}
            }}
        </style>
    </head>
    <body>
        <main class="error-container" role="main">
            <div class="error-icon" aria-hidden="true">⏱️</div>
            <h1 class="error-title">Too Many Requests</h1>
            <p class="error-message" role="alert">
                You've made too many authorization attempts in a short period. 
                This security measure helps protect against automated attacks.
            </p>
            
            <div class="retry-message" role="status" aria-live="polite">
                {retry_message}
            </div>
            
            <section class="explanation" role="complementary" aria-labelledby="explanation-title">
                <h3 id="explanation-title">Why did this happen?</h3>
                <p><strong>Security Protection:</strong> We limit the number of authorization requests to prevent abuse and protect user accounts.</p>
                <p><strong>Common Causes:</strong> Repeatedly clicking authorization links, browser refresh loops, or automated scripts.</p>
                <p><strong>What to do:</strong> Wait for the specified time, then try again. Avoid repeatedly clicking links.</p>
            </section>
            
            <div class="error-actions" role="group" aria-label="Available actions">
                <button onclick="location.reload()" class="btn btn-primary" aria-label="Refresh this page">Refresh Page</button>
                <a href="javascript:history.back()" class="btn btn-secondary" aria-label="Go back to previous page">Go Back</a>
            </div>
        </main>
        
        <script>
            // Auto-refresh after rate limit expires (if retry_after is provided)
            {f'setTimeout(() => {{ location.reload(); }}, {retry_after * 1000});' if retry_after and retry_after < 300 else ''}
        </script>
    </body>
    </html>
    """
    
    logger.debug(f"Rendered rate limit error screen with retry_after: {retry_after}")
    return html_template


def render_scope_error(invalid_scopes: list, client_name: str = None) -> str:
    """
    Render OAuth2 invalid scope error screen HTML.
    
    Args:
        invalid_scopes: List of invalid scope names
        client_name: Optional client name for context
        
    Returns:
        HTML string for scope error screen
    """
    
    client_context = f" ({client_name})" if client_name else ""
    scope_list = ", ".join(invalid_scopes) if invalid_scopes else "unknown scopes"
    
    html_template = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Invalid Permissions Request - Second Brain Database</title>
        <meta name="robots" content="noindex, nofollow">
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                background: linear-gradient(135deg, #667eea 0%%, #764ba2 100%%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }}
            
            .error-container {{
                background: white;
                border-radius: 12px;
                box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
                padding: 40px;
                width: 100%%;
                max-width: 500px;
                text-align: center;
            }}
            
            .error-icon {{
                font-size: 64px;
                color: #e74c3c;
                margin-bottom: 20px;
                animation: shake 0.5s ease-in-out;
            }}
            
            @keyframes shake {{
                0%%, 100%% {{ transform: translateX(0); }}
                25%% {{ transform: translateX(-5px); }}
                75%% {{ transform: translateX(5px); }}
            }}
            
            .error-title {{
                color: #333;
                font-size: 28px;
                font-weight: 600;
                margin-bottom: 16px;
            }}
            
            .client-name {{
                color: #666;
                font-size: 16px;
                margin-bottom: 20px;
                font-weight: 500;
            }}
            
            .error-message {{
                color: #666;
                font-size: 16px;
                line-height: 1.6;
                margin-bottom: 20px;
            }}
            
            .invalid-scopes {{
                background: #fed7d7;
                border: 1px solid #feb2b2;
                border-radius: 8px;
                padding: 16px;
                margin-bottom: 30px;
                color: #742a2a;
            }}
            
            .invalid-scopes h3 {{
                font-size: 16px;
                font-weight: 600;
                margin-bottom: 8px;
            }}
            
            .scope-list {{
                font-family: 'Courier New', monospace;
                font-size: 14px;
                background: #fff;
                padding: 8px;
                border-radius: 4px;
                border: 1px solid #feb2b2;
                word-break: break-all;
            }}
            
            .explanation {{
                background: #fff3cd;
                border: 1px solid #ffeaa7;
                border-radius: 8px;
                padding: 20px;
                margin-bottom: 30px;
                text-align: left;
            }}
            
            .explanation h3 {{
                color: #856404;
                font-size: 16px;
                font-weight: 600;
                margin-bottom: 12px;
            }}
            
            .explanation p {{
                color: #856404;
                font-size: 14px;
                line-height: 1.5;
                margin-bottom: 8px;
            }}
            
            .error-actions {{
                display: flex;
                gap: 12px;
                justify-content: center;
                flex-wrap: wrap;
            }}
            
            .btn {{
                padding: 12px 24px;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
                cursor: pointer;
                text-decoration: none;
                display: inline-block;
                transition: all 0.2s;
                min-width: 120px;
            }}
            
            .btn-primary {{
                background: #667eea;
                color: white;
            }}
            
            .btn-primary:hover {{
                background: #5a6fd8;
                transform: translateY(-1px);
                box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
            }}
            
            .btn-secondary {{
                background: #6c757d;
                color: white;
            }}
            
            .btn-secondary:hover {{
                background: #5a6268;
                transform: translateY(-1px);
                box-shadow: 0 4px 12px rgba(108, 117, 125, 0.3);
            }}
            
            /* Focus styles for accessibility */
            .btn:focus {{
                outline: 2px solid #667eea;
                outline-offset: 2px;
            }}
            
            /* High contrast mode support */
            @media (prefers-contrast: high) {{
                .error-container {{
                    border: 2px solid #000;
                }}
                
                .btn {{
                    border: 2px solid currentColor;
                }}
            }}
            
            /* Reduced motion support */
            @media (prefers-reduced-motion: reduce) {{
                * {{
                    animation-duration: 0.01ms !important;
                    animation-iteration-count: 1 !important;
                    transition-duration: 0.01ms !important;
                }}
            }}
            
            @media (max-width: 480px) {{
                .error-container {{
                    padding: 30px 20px;
                }}
                
                .error-title {{
                    font-size: 24px;
                }}
                
                .error-actions {{
                    flex-direction: column;
                }}
            }}
        </style>
    </head>
    <body>
        <main class="error-container" role="main">
            <div class="error-icon" aria-hidden="true">🔐</div>
            <h1 class="error-title">Invalid Permissions Request</h1>
            {f'<div class="client-name">Application: {client_name}</div>' if client_name else ''}
            <p class="error-message" role="alert">
                The application{client_context} is requesting permissions it's not authorized to access. 
                This is a configuration issue that needs to be resolved by the application developer.
            </p>
            
            <section class="invalid-scopes" role="complementary" aria-labelledby="scopes-title">
                <h3 id="scopes-title">Invalid Permissions:</h3>
                <div class="scope-list">{scope_list}</div>
            </section>
            
            <section class="explanation" role="complementary" aria-labelledby="explanation-title">
                <h3 id="explanation-title">What does this mean?</h3>
                <p><strong>For Users:</strong> The application is trying to access data or features it's not allowed to use. This is not your fault.</p>
                <p><strong>For Developers:</strong> Your application is requesting scopes that haven't been approved for your client registration.</p>
                <p><strong>Resolution:</strong> Contact the application developer to fix their permission configuration, or update your client registration to include the required scopes.</p>
            </section>
            
            <div class="error-actions" role="group" aria-label="Available actions">
                <a href="javascript:history.back()" class="btn btn-primary" aria-label="Go back to previous page">Go Back</a>
                <a href="/auth/login" class="btn btn-secondary" aria-label="Go to login page">Login</a>
            </div>
        </main>
    </body>
    </html>
    """
    
    logger.debug(f"Rendered scope error screen for scopes: {scope_list}")
    return html_template

def render_generic_oauth2_error(
    title: str,
    message: str,
    icon: str = "⚠️",
    show_login_button: bool = True,
    show_back_button: bool = True,
    additional_info: str = None
) -> str:
    """
    Render generic OAuth2 error screen HTML with customizable content.
    
    Args:
        title: Error title to display
        message: Error message to display
        icon: Emoji icon for the error
        show_login_button: Whether to show login button
        show_back_button: Whether to show back button
        additional_info: Optional additional information HTML
        
    Returns:
        HTML string for generic OAuth2 error screen
    """
    
    # Action buttons
    action_buttons = []
    if show_back_button:
        action_buttons.append('<button onclick="history.back()" class="btn btn-secondary" aria-label="Go back to previous page">Go Back</button>')
    if show_login_button:
        action_buttons.append('<a href="/auth/login" class="btn btn-primary" aria-label="Go to login page">Login</a>')
    
    actions_html = ""
    if action_buttons:
        actions_html = f"""
        <div class="error-actions" role="group" aria-label="Available actions">
            {' '.join(action_buttons)}
        </div>
        """
    
    # Additional info section
    additional_info_html = ""
    if additional_info:
        additional_info_html = f"""
        <div class="additional-info" role="complementary">
            {additional_info}
        </div>
        """
    
    html_template = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title} - Second Brain Database</title>
        <meta name="robots" content="noindex, nofollow">
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                background: linear-gradient(135deg, #667eea 0%%, #764ba2 100%%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
                color: #333;
            }}
            
            .error-container {{
                background: white;
                border-radius: 12px;
                box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
                padding: 40px;
                width: 100%%;
                max-width: 500px;
                text-align: center;
                position: relative;
            }}
            
            .error-icon {{
                font-size: 48px;
                margin-bottom: 20px;
                animation: pulse 2s infinite;
            }}
            
            @keyframes pulse {{
                0%% {{ transform: scale(1); }}
                50%% {{ transform: scale(1.05); }}
                100%% {{ transform: scale(1); }}
            }}
            
            .error-title {{
                color: #333;
                font-size: 24px;
                font-weight: 600;
                margin-bottom: 16px;
            }}
            
            .error-message {{
                color: #666;
                font-size: 16px;
                line-height: 1.5;
                margin-bottom: 30px;
            }}
            
            .additional-info {{
                background: #f8f9fa;
                border: 1px solid #e9ecef;
                border-radius: 8px;
                padding: 16px;
                margin-bottom: 30px;
                font-size: 14px;
                color: #6c757d;
                text-align: left;
            }}
            
            .error-actions {{
                display: flex;
                gap: 12px;
                justify-content: center;
                flex-wrap: wrap;
            }}
            
            .btn {{
                padding: 12px 24px;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
                cursor: pointer;
                text-decoration: none;
                display: inline-block;
                transition: all 0.2s;
                min-width: 100px;
            }}
            
            .btn-primary {{
                background: #667eea;
                color: white;
            }}
            
            .btn-primary:hover {{
                background: #5a6fd8;
                transform: translateY(-1px);
                box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
            }}
            
            .btn-secondary {{
                background: #6c757d;
                color: white;
            }}
            
            .btn-secondary:hover {{
                background: #5a6268;
                transform: translateY(-1px);
                box-shadow: 0 4px 12px rgba(108, 117, 125, 0.3);
            }}
            
            .security-notice {{
                position: absolute;
                top: 10px;
                right: 15px;
                font-size: 12px;
                color: #999;
                opacity: 0.7;
            }}
            
            /* Focus styles for accessibility */
            .btn:focus {{
                outline: 2px solid #667eea;
                outline-offset: 2px;
            }}
            
            /* High contrast mode support */
            @media (prefers-contrast: high) {{
                .error-container {{
                    border: 2px solid #000;
                }}
                
                .btn {{
                    border: 2px solid currentColor;
                }}
            }}
            
            /* Reduced motion support */
            @media (prefers-reduced-motion: reduce) {{
                * {{
                    animation-duration: 0.01ms !important;
                    animation-iteration-count: 1 !important;
                    transition-duration: 0.01ms !important;
                }}
            }}
            
            @media (max-width: 480px) {{
                .error-container {{
                    padding: 30px 20px;
                }}
                
                .error-title {{
                    font-size: 20px;
                }}
                
                .error-actions {{
                    flex-direction: column;
                }}
                
                .security-notice {{
                    position: static;
                    margin-top: 20px;
                    text-align: center;
                }}
            }}
        </style>
    </head>
    <body>
        <main class="error-container" role="main">
            <div class="security-notice" aria-label="Secure connection indicator">🔒 Secure</div>
            <div class="error-icon" aria-hidden="true">{icon}</div>
            <h1 class="error-title">{title}</h1>
            <p class="error-message" role="alert">
                {message}
            </p>
            {additional_info_html}
            {actions_html}
        </main>
    </body>
    </html>
    """
    
    logger.debug(f"Rendered generic OAuth2 error screen: {title}")
    return html_template


def render_authorization_failed_error(
    message: str = None,
    client_name: str = None,
    error_details: str = None,
    show_retry_button: bool = True
) -> str:
    """
    Render OAuth2 authorization failed error screen HTML.
    
    Args:
        message: Optional custom message
        client_name: Optional client name for context
        error_details: Optional detailed error information
        show_retry_button: Whether to show retry button
        
    Returns:
        HTML string for authorization failed error screen
    """
    
    default_message = "The authorization process failed. This could be due to an invalid request, expired session, or server error."
    if client_name:
        default_message = f"The authorization process for {client_name} failed. This could be due to an invalid request, expired session, or server error."
    
    display_message = message or default_message
    
    # Client info section
    client_info_html = ""
    if client_name:
        client_info_html = f'<p class="client-name">Application: {client_name}</p>'
    
    # Error details section
    error_details_html = ""
    if error_details:
        error_details_html = f"""
        <div class="error-details">
            <strong>Error Details:</strong><br>
            {error_details}
        </div>
        """
    
    # Action buttons
    action_buttons = ['<button onclick="history.back()" class="btn btn-secondary" aria-label="Go back to previous page">Go Back</button>']
    if show_retry_button:
        action_buttons.append('<a href="javascript:location.reload()" class="btn btn-primary" aria-label="Retry the authorization process">Retry</a>')
    
    actions_html = f"""
    <div class="error-actions" role="group" aria-label="Available actions">
        {' '.join(action_buttons)}
    </div>
    """
    
    html_template = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Authorization Failed - Second Brain Database</title>
        <meta name="robots" content="noindex, nofollow">
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                background: linear-gradient(135deg, #667eea 0%%, #764ba2 100%%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
                color: #333;
            }}
            
            .error-container {{
                background: white;
                border-radius: 12px;
                box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
                padding: 40px;
                width: 100%%;
                max-width: 500px;
                text-align: center;
                position: relative;
            }}
            
            .error-icon {{
                font-size: 48px;
                color: #e74c3c;
                margin-bottom: 20px;
                animation: shake 0.5s ease-in-out;
            }}
            
            @keyframes shake {{
                0%%, 100%% {{ transform: translateX(0); }}
                25%% {{ transform: translateX(-5px); }}
                75%% {{ transform: translateX(5px); }}
            }}
            
            .error-title {{
                color: #333;
                font-size: 24px;
                font-weight: 600;
                margin-bottom: 16px;
            }}
            
            .client-name {{
                color: #4a5568;
                margin-bottom: 20px;
                font-weight: 500;
            }}
            
            .error-message {{
                color: #666;
                font-size: 16px;
                line-height: 1.5;
                margin-bottom: 30px;
            }}
            
            .error-details {{
                background: #f8f9fa;
                border: 1px solid #e9ecef;
                border-radius: 8px;
                padding: 16px;
                margin-bottom: 30px;
                font-size: 14px;
                color: #6c757d;
                text-align: left;
                word-break: break-word;
            }}
            
            .error-actions {{
                display: flex;
                gap: 12px;
                justify-content: center;
                flex-wrap: wrap;
            }}
            
            .btn {{
                padding: 12px 24px;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
                cursor: pointer;
                text-decoration: none;
                display: inline-block;
                transition: all 0.2s;
                min-width: 100px;
            }}
            
            .btn-primary {{
                background: #667eea;
                color: white;
            }}
            
            .btn-primary:hover {{
                background: #5a6fd8;
                transform: translateY(-1px);
                box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
            }}
            
            .btn-secondary {{
                background: #6c757d;
                color: white;
            }}
            
            .btn-secondary:hover {{
                background: #5a6268;
                transform: translateY(-1px);
                box-shadow: 0 4px 12px rgba(108, 117, 125, 0.3);
            }}
            
            .security-notice {{
                position: absolute;
                top: 10px;
                right: 15px;
                font-size: 12px;
                color: #999;
                opacity: 0.7;
            }}
            
            .troubleshooting {{
                background: #e3f2fd;
                border: 1px solid #bbdefb;
                border-radius: 8px;
                padding: 16px;
                margin-bottom: 30px;
                font-size: 14px;
                color: #1976d2;
                text-align: left;
            }}
            
            .troubleshooting strong {{
                color: #0d47a1;
            }}
            
            /* Focus styles for accessibility */
            .btn:focus {{
                outline: 2px solid #667eea;
                outline-offset: 2px;
            }}
            
            /* High contrast mode support */
            @media (prefers-contrast: high) {{
                .error-container {{
                    border: 2px solid #000;
                }}
                
                .btn {{
                    border: 2px solid currentColor;
                }}
            }}
            
            /* Reduced motion support */
            @media (prefers-reduced-motion: reduce) {{
                * {{
                    animation-duration: 0.01ms !important;
                    animation-iteration-count: 1 !important;
                    transition-duration: 0.01ms !important;
                }}
            }}
            
            @media (max-width: 480px) {{
                .error-container {{
                    padding: 30px 20px;
                }}
                
                .error-title {{
                    font-size: 20px;
                }}
                
                .error-actions {{
                    flex-direction: column;
                }}
                
                .security-notice {{
                    position: static;
                    margin-top: 20px;
                    text-align: center;
                }}
            }}
        </style>
    </head>
    <body>
        <main class="error-container" role="main">
            <div class="security-notice" aria-label="Secure connection indicator">🔒 Secure</div>
            <div class="error-icon" aria-hidden="true">❌</div>
            <h1 class="error-title">Authorization Failed</h1>
            {client_info_html}
            <p class="error-message" role="alert">
                {display_message}
            </p>
            {error_details_html}
            <div class="troubleshooting" role="complementary" aria-labelledby="troubleshooting-title">
                <strong id="troubleshooting-title">Troubleshooting Steps:</strong><br>
                • Check that you're using the correct authorization link<br>
                • Ensure your browser has cookies and JavaScript enabled<br>
                • Try clearing your browser cache and cookies<br>
                • Make sure you're not using an incognito/private browsing window<br>
                • Contact the application developer if the problem persists
            </div>
            {actions_html}
        </main>
    </body>
    </html>
    """
    
    logger.debug(f"Rendered authorization failed error screen: {display_message}")
    return html_template
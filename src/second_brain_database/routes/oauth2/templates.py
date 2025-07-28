"""
OAuth2 HTML templates for consent screens and user interfaces.

This module provides HTML templates for OAuth2 user consent screens and related UI components.
Templates are designed to be responsive and accessible.
"""

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
        existing_consent: Whether user has previously granted consent
        
    Returns:
        HTML string for consent screen
    """
    
    # Generate scope list HTML
    scope_items = ""
    for scope_info in requested_scopes:
        scope_items += f"""
        <li class="scope-item">
            <div class="scope-name">{scope_info['scope']}</div>
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
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
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
                width: 100%;
                padding: 40px;
                text-align: center;
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
                    width: 100%;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="consent-container">
            <div class="logo">SBD</div>
            
            <h1 class="title">Authorize Application</h1>
            <p class="subtitle">Second Brain Database</p>
            
            <div class="client-info">
                <div class="client-name">{client_name}</div>
                {f'<div class="client-description">{client_description}</div>' if client_description else ''}
                {website_link}
            </div>
            
            {consent_status}
            
            <div class="permissions-section">
                <div class="permissions-title">This application is requesting access to:</div>
                <ul class="scope-list">
                    {scope_items}
                </ul>
            </div>
            
            <form method="post" action="/oauth2/consent">
                <input type="hidden" name="client_id" value="{client_id}">
                <input type="hidden" name="state" value="{state}">
                <input type="hidden" name="scopes" value="{','.join([s['scope'] for s in requested_scopes])}">
                
                <div class="actions">
                    <button type="submit" name="approved" value="true" class="btn btn-approve">
                        Approve
                    </button>
                    <button type="submit" name="approved" value="false" class="btn btn-deny">
                        Deny
                    </button>
                </div>
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
        HTML string for error screen
    """
    
    client_context = f" for {client_name}" if client_name else ""
    
    html_template = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Authorization Error - Second Brain Database</title>
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
            
            .error-container {{
                background: white;
                border-radius: 12px;
                box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
                max-width: 400px;
                width: 100%;
                padding: 40px;
                text-align: center;
            }}
            
            .error-icon {{
                width: 60px;
                height: 60px;
                background: #e53e3e;
                border-radius: 50%;
                margin: 0 auto 20px;
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
                font-size: 24px;
            }}
            
            .title {{
                font-size: 24px;
                font-weight: 600;
                color: #2d3748;
                margin-bottom: 8px;
            }}
            
            .subtitle {{
                color: #718096;
                margin-bottom: 20px;
                font-size: 16px;
            }}
            
            .error-message {{
                background: #fed7d7;
                border: 1px solid #feb2b2;
                color: #742a2a;
                padding: 15px;
                border-radius: 8px;
                margin-bottom: 20px;
                text-align: left;
            }}
            
            .back-link {{
                color: #667eea;
                text-decoration: none;
                font-weight: 500;
            }}
            
            .back-link:hover {{
                text-decoration: underline;
            }}
        </style>
    </head>
    <body>
        <div class="error-container">
            <div class="error-icon">!</div>
            
            <h1 class="title">Authorization Error</h1>
            <p class="subtitle">Unable to process authorization{client_context}</p>
            
            <div class="error-message">
                {error_message}
            </div>
            
            <a href="javascript:history.back()" class="back-link">← Go Back</a>
        </div>
    </body>
    </html>
    """
    
    logger.debug(f"Rendered consent error screen: {error_message}")
    return html_template
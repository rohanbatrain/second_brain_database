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


def render_consent_management_ui(consents: List[Dict], user_id: str) -> str:
    """
    Render OAuth2 consent management UI HTML.
    
    Args:
        consents: List of user consents with client information
        user_id: User identifier
        
    Returns:
        HTML string for consent management interface
    """
    
    # Generate consent items HTML
    consent_items = ""
    if consents:
        for consent in consents:
            # Format granted date
            granted_date = consent.get('granted_at', datetime.utcnow()).strftime('%B %d, %Y')
            last_used = consent.get('last_used_at')
            last_used_text = last_used.strftime('%B %d, %Y') if last_used else 'Never'
            
            # Generate scope list
            scope_list = ""
            for scope_info in consent.get('scope_descriptions', []):
                scope_list += f"""
                <li class="scope-item">
                    <span class="scope-name">{scope_info['scope']}</span>
                    <span class="scope-description">{scope_info['description']}</span>
                </li>
                """
            
            # Website link
            website_link = ""
            if consent.get('website_url'):
                website_link = f'<a href="{consent["website_url"]}" target="_blank" rel="noopener noreferrer" class="website-link">Visit website</a>'
            
            consent_items += f"""
            <div class="consent-card" data-client-id="{consent['client_id']}">
                <div class="consent-header">
                    <div class="client-info">
                        <h3 class="client-name">{consent['client_name']}</h3>
                        {f'<p class="client-description">{consent["client_description"]}</p>' if consent.get('client_description') else ''}
                        {website_link}
                    </div>
                    <div class="consent-actions">
                        <button class="btn btn-danger revoke-btn" data-client-id="{consent['client_id']}" data-client-name="{consent['client_name']}">
                            Revoke Access
                        </button>
                    </div>
                </div>
                
                <div class="consent-details">
                    <div class="detail-row">
                        <span class="detail-label">Granted:</span>
                        <span class="detail-value">{granted_date}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Last Used:</span>
                        <span class="detail-value">{last_used_text}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Status:</span>
                        <span class="detail-value status-active">Active</span>
                    </div>
                </div>
                
                <div class="permissions-section">
                    <h4 class="permissions-title">Granted Permissions:</h4>
                    <ul class="scope-list">
                        {scope_list}
                    </ul>
                </div>
            </div>
            """
    else:
        consent_items = """
        <div class="empty-state">
            <div class="empty-icon">🔐</div>
            <h3>No Active Consents</h3>
            <p>You haven't granted access to any OAuth2 applications yet.</p>
        </div>
        """
    
    html_template = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Manage OAuth2 Consents - Second Brain Database</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                background: #f8fafc;
                min-height: 100vh;
                padding: 20px;
            }}
            
            .container {{
                max-width: 800px;
                margin: 0 auto;
            }}
            
            .header {{
                background: white;
                border-radius: 12px;
                padding: 30px;
                margin-bottom: 20px;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            }}
            
            .title {{
                font-size: 28px;
                font-weight: 600;
                color: #2d3748;
                margin-bottom: 8px;
            }}
            
            .subtitle {{
                color: #718096;
                font-size: 16px;
                margin-bottom: 20px;
            }}
            
            .user-info {{
                background: #edf2f7;
                border-radius: 8px;
                padding: 15px;
                display: inline-block;
            }}
            
            .user-label {{
                font-size: 14px;
                color: #4a5568;
                margin-bottom: 4px;
            }}
            
            .user-value {{
                font-weight: 600;
                color: #2d3748;
            }}
            
            .consent-card {{
                background: white;
                border-radius: 12px;
                padding: 25px;
                margin-bottom: 20px;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
                border: 1px solid #e2e8f0;
            }}
            
            .consent-header {{
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                margin-bottom: 20px;
            }}
            
            .client-info {{
                flex: 1;
            }}
            
            .client-name {{
                font-size: 20px;
                font-weight: 600;
                color: #2d3748;
                margin-bottom: 8px;
            }}
            
            .client-description {{
                color: #4a5568;
                margin-bottom: 8px;
                line-height: 1.5;
            }}
            
            .website-link {{
                color: #667eea;
                text-decoration: none;
                font-weight: 500;
                font-size: 14px;
            }}
            
            .website-link:hover {{
                text-decoration: underline;
            }}
            
            .consent-actions {{
                margin-left: 20px;
            }}
            
            .btn {{
                padding: 10px 20px;
                border-radius: 8px;
                font-weight: 600;
                font-size: 14px;
                cursor: pointer;
                border: none;
                transition: all 0.2s;
            }}
            
            .btn-danger {{
                background: #e53e3e;
                color: white;
            }}
            
            .btn-danger:hover {{
                background: #c53030;
                transform: translateY(-1px);
            }}
            
            .btn-danger:disabled {{
                background: #cbd5e0;
                color: #a0aec0;
                cursor: not-allowed;
                transform: none;
            }}
            
            .consent-details {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 15px;
                margin-bottom: 20px;
                padding: 15px;
                background: #f7fafc;
                border-radius: 8px;
            }}
            
            .detail-row {{
                display: flex;
                flex-direction: column;
            }}
            
            .detail-label {{
                font-size: 12px;
                color: #718096;
                text-transform: uppercase;
                font-weight: 600;
                margin-bottom: 4px;
            }}
            
            .detail-value {{
                color: #2d3748;
                font-weight: 500;
            }}
            
            .status-active {{
                color: #38a169;
            }}
            
            .permissions-section {{
                border-top: 1px solid #e2e8f0;
                padding-top: 20px;
            }}
            
            .permissions-title {{
                font-size: 16px;
                font-weight: 600;
                color: #2d3748;
                margin-bottom: 15px;
            }}
            
            .scope-list {{
                list-style: none;
                display: grid;
                gap: 8px;
            }}
            
            .scope-item {{
                background: #f7fafc;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                padding: 10px;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}
            
            .scope-name {{
                font-weight: 600;
                color: #2d3748;
                font-size: 14px;
            }}
            
            .scope-description {{
                color: #4a5568;
                font-size: 13px;
                margin-left: 15px;
            }}
            
            .empty-state {{
                text-align: center;
                padding: 60px 20px;
                background: white;
                border-radius: 12px;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            }}
            
            .empty-icon {{
                font-size: 48px;
                margin-bottom: 20px;
            }}
            
            .empty-state h3 {{
                font-size: 20px;
                color: #2d3748;
                margin-bottom: 10px;
            }}
            
            .empty-state p {{
                color: #718096;
            }}
            
            .loading {{
                text-align: center;
                padding: 20px;
                color: #718096;
            }}
            
            .error {{
                background: #fed7d7;
                border: 1px solid #feb2b2;
                color: #742a2a;
                padding: 15px;
                border-radius: 8px;
                margin-bottom: 20px;
            }}
            
            .success {{
                background: #c6f6d5;
                border: 1px solid #9ae6b4;
                color: #22543d;
                padding: 15px;
                border-radius: 8px;
                margin-bottom: 20px;
            }}
            
            .modal {{
                display: none;
                position: fixed;
                z-index: 1000;
                left: 0;
                top: 0;
                width: 100%;
                height: 100%;
                background-color: rgba(0, 0, 0, 0.5);
            }}
            
            .modal-content {{
                background-color: white;
                margin: 15% auto;
                padding: 30px;
                border-radius: 12px;
                width: 90%;
                max-width: 500px;
                box-shadow: 0 20px 40px rgba(0, 0, 0, 0.2);
            }}
            
            .modal-header {{
                margin-bottom: 20px;
            }}
            
            .modal-title {{
                font-size: 20px;
                font-weight: 600;
                color: #2d3748;
                margin-bottom: 8px;
            }}
            
            .modal-description {{
                color: #4a5568;
                line-height: 1.5;
            }}
            
            .modal-actions {{
                display: flex;
                gap: 12px;
                justify-content: flex-end;
                margin-top: 25px;
            }}
            
            .btn-secondary {{
                background: #e2e8f0;
                color: #4a5568;
            }}
            
            .btn-secondary:hover {{
                background: #cbd5e0;
            }}
            
            @media (max-width: 768px) {{
                .consent-header {{
                    flex-direction: column;
                    align-items: stretch;
                }}
                
                .consent-actions {{
                    margin-left: 0;
                    margin-top: 15px;
                }}
                
                .consent-details {{
                    grid-template-columns: 1fr;
                }}
                
                .scope-item {{
                    flex-direction: column;
                    align-items: flex-start;
                }}
                
                .scope-description {{
                    margin-left: 0;
                    margin-top: 4px;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1 class="title">OAuth2 Consent Management</h1>
                <p class="subtitle">Manage applications that have access to your Second Brain Database account</p>
                
                <div class="user-info">
                    <div class="user-label">Logged in as:</div>
                    <div class="user-value">{user_id}</div>
                </div>
            </div>
            
            <div id="message-container"></div>
            
            <div id="consents-container">
                {consent_items}
            </div>
        </div>
        
        <!-- Revocation Confirmation Modal -->
        <div id="revoke-modal" class="modal">
            <div class="modal-content">
                <div class="modal-header">
                    <h2 class="modal-title">Revoke Access</h2>
                    <p class="modal-description">
                        Are you sure you want to revoke access for <strong id="revoke-client-name"></strong>? 
                        This will immediately invalidate all tokens and prevent the application from accessing your data.
                    </p>
                </div>
                <div class="modal-actions">
                    <button id="cancel-revoke" class="btn btn-secondary">Cancel</button>
                    <button id="confirm-revoke" class="btn btn-danger">Revoke Access</button>
                </div>
            </div>
        </div>
        
        <script>
            // Global variables
            let currentClientId = null;
            let currentClientName = null;
            
            // DOM elements
            const modal = document.getElementById('revoke-modal');
            const messageContainer = document.getElementById('message-container');
            const consentsContainer = document.getElementById('consents-container');
            
            // Event listeners
            document.addEventListener('DOMContentLoaded', function() {{
                // Add click listeners to revoke buttons
                document.querySelectorAll('.revoke-btn').forEach(button => {{
                    button.addEventListener('click', handleRevokeClick);
                }});
                
                // Modal event listeners
                document.getElementById('cancel-revoke').addEventListener('click', closeModal);
                document.getElementById('confirm-revoke').addEventListener('click', confirmRevoke);
                
                // Close modal when clicking outside
                modal.addEventListener('click', function(e) {{
                    if (e.target === modal) {{
                        closeModal();
                    }}
                }});
            }});
            
            function handleRevokeClick(e) {{
                currentClientId = e.target.dataset.clientId;
                currentClientName = e.target.dataset.clientName;
                
                document.getElementById('revoke-client-name').textContent = currentClientName;
                modal.style.display = 'block';
            }}
            
            function closeModal() {{
                modal.style.display = 'none';
                currentClientId = null;
                currentClientName = null;
            }}
            
            async function confirmRevoke() {{
                if (!currentClientId) return;
                
                const confirmButton = document.getElementById('confirm-revoke');
                confirmButton.disabled = true;
                confirmButton.textContent = 'Revoking...';
                
                try {{
                    const response = await fetch(`/oauth2/consents/${{currentClientId}}`, {{
                        method: 'DELETE',
                        headers: {{
                            'Content-Type': 'application/json',
                        }}
                    }});
                    
                    if (response.ok) {{
                        showMessage('success', `Access revoked for ${{currentClientName}}`);
                        removeConsentCard(currentClientId);
                        closeModal();
                    }} else {{
                        const errorData = await response.json();
                        showMessage('error', errorData.detail || 'Failed to revoke access');
                    }}
                }} catch (error) {{
                    showMessage('error', 'Network error occurred while revoking access');
                }} finally {{
                    confirmButton.disabled = false;
                    confirmButton.textContent = 'Revoke Access';
                }}
            }}
            
            function removeConsentCard(clientId) {{
                const card = document.querySelector(`[data-client-id="${{clientId}}"]`);
                if (card) {{
                    card.remove();
                    
                    // Check if no consents remain
                    const remainingCards = document.querySelectorAll('.consent-card');
                    if (remainingCards.length === 0) {{
                        consentsContainer.innerHTML = `
                            <div class="empty-state">
                                <div class="empty-icon">🔐</div>
                                <h3>No Active Consents</h3>
                                <p>You haven't granted access to any OAuth2 applications yet.</p>
                            </div>
                        `;
                    }}
                }}
            }}
            
            function showMessage(type, message) {{
                const messageDiv = document.createElement('div');
                messageDiv.className = type;
                messageDiv.textContent = message;
                
                messageContainer.innerHTML = '';
                messageContainer.appendChild(messageDiv);
                
                // Auto-hide success messages
                if (type === 'success') {{
                    setTimeout(() => {{
                        messageDiv.remove();
                    }}, 5000);
                }}
            }}
        </script>
    </body>
    </html>
    """
    
    logger.debug(f"Rendered consent management UI for user {user_id} with {len(consents)} consents")
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
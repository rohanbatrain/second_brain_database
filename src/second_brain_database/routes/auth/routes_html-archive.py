

# def render_webauthn_setup_page() -> HTMLResponse:
#     """
#     Serve the WebAuthn passkey setup HTML page.
    
#     Args:
#         username (str): The authenticated user's username
#         user_id (str): The authenticated user's ID
        
#     Returns:
#         HTMLResponse: The rendered HTML page for passkey setup
#     """
#     html = f"""
#     <!DOCTYPE html>
#     <html lang="en">
#     <head>
#         <meta charset="UTF-8">
#         <meta name="viewport" content="width=device-width, initial-scale=1.0">
#         <title>Set Up Passkeys - Second Brain Database</title>
#         <link href="https://fonts.googleapis.com/css?family=Roboto:400,700&display=swap" rel="stylesheet">
#         <style>
#             :root {{
#                 --primary: #3a86ff;
#                 --primary-hover: #265dbe;
#                 --background: #f6f8fa;
#                 --foreground: #ffffff;
#                 --text-main: #22223b;
#                 --text-sub: #4a4e69;
#                 --border-color: #c9c9c9;
#                 --error: #d90429;
#                 --success: #06d6a0;
#                 --info: #0c5460;
#             }}
            
#             * {{ box-sizing: border-box; }}
            
#             body {{
#                 margin: 0;
#                 background-color: var(--background);
#                 font-family: 'Roboto', sans-serif;
#                 padding: 20px;
#                 min-height: 100vh;
#             }}
            
#             .container {{
#                 max-width: 800px;
#                 margin: 0 auto;
#                 background-color: var(--foreground);
#                 padding: 2.5rem 2rem;
#                 border-radius: 12px;
#                 box-shadow: 0 4px 24px rgba(0, 0, 0, 0.08);
#             }}
            
#             .hidden {{
#                 display: none !important;
#             }}
            
#             h1 {{
#                 margin-bottom: 1.5rem;
#                 color: var(--text-main);
#                 font-size: 2rem;
#                 font-weight: 700;
#                 text-align: center;
#             }}
            
#             h2 {{
#                 margin-bottom: 1rem;
#                 color: var(--text-main);
#                 font-size: 1.5rem;
#                 font-weight: 600;
#             }}
            
#             p {{
#                 color: var(--text-sub);
#                 line-height: 1.6;
#                 margin-bottom: 1rem;
#             }}
            
#             .btn-primary, .btn-secondary, .btn-danger {{
#                 padding: 12px 24px;
#                 border: none;
#                 border-radius: 6px;
#                 font-size: 16px;
#                 cursor: pointer;
#                 text-decoration: none;
#                 display: inline-block;
#                 margin: 8px;
#                 transition: background-color 0.2s;
#                 font-weight: 500;
#             }}
            
#             .btn-primary {{
#                 background-color: var(--primary);
#                 color: white;
#             }}
            
#             .btn-primary:hover {{
#                 background-color: var(--primary-hover);
#             }}
            
#             .btn-secondary {{
#                 background-color: #6c757d;
#                 color: white;
#             }}
            
#             .btn-danger {{
#                 background-color: var(--error);
#                 color: white;
#             }}
            
#             .btn-danger:hover {{
#                 background-color: #c82333;
#             }}
            
#             #setup-form {{
#                 background-color: var(--background);
#                 padding: 20px;
#                 border-radius: 8px;
#                 margin: 20px 0;
#             }}
            
#             #setup-form label {{
#                 display: block;
#                 margin-bottom: 8px;
#                 font-weight: 500;
#                 color: var(--text-main);
#             }}
            
#             #setup-form input {{
#                 width: 100%;
#                 padding: 8px 12px;
#                 border: 1px solid var(--border-color);
#                 border-radius: 4px;
#                 margin-bottom: 16px;
#                 font-size: 16px;
#             }}
            
#             .passkey-item {{
#                 display: flex;
#                 justify-content: space-between;
#                 align-items: center;
#                 padding: 16px;
#                 border: 1px solid var(--border-color);
#                 border-radius: 8px;
#                 margin-bottom: 12px;
#                 background-color: var(--background);
#             }}
            
#             .passkey-info h3 {{
#                 margin: 0 0 8px 0;
#                 color: var(--text-main);
#                 font-size: 1.1rem;
#             }}
            
#             .passkey-info p {{
#                 margin: 4px 0;
#                 color: var(--text-sub);
#                 font-size: 14px;
#             }}
            
#             .status-message {{
#                 padding: 12px;
#                 border-radius: 4px;
#                 margin: 8px 0;
#             }}
            
#             .status-message.success {{
#                 background-color: #d4edda;
#                 color: #155724;
#                 border: 1px solid #c3e6cb;
#             }}
            
#             .status-message.error {{
#                 background-color: #f8d7da;
#                 color: #721c24;
#                 border: 1px solid #f5c6cb;
#             }}
            
#             .status-message.info {{
#                 background-color: #d1ecf1;
#                 color: var(--info);
#                 border: 1px solid #bee5eb;
#             }}
            
#             .no-passkeys {{
#                 text-align: center;
#                 color: var(--text-sub);
#                 font-style: italic;
#                 padding: 40px;
#             }}
            
#             .actions {{
#                 margin-bottom: 20px;
#                 text-align: center;
#             }}
            
#             .user-info {{
#                 background-color: var(--background);
#                 padding: 15px;
#                 border-radius: 8px;
#                 margin-bottom: 20px;
#                 text-align: center;
#             }}
            
#             @media (max-width: 768px) {{
#                 .container {{
#                     padding: 1rem;
#                 }}
                
#                 .passkey-item {{
#                     flex-direction: column;
#                     align-items: flex-start;
#                 }}
                
#                 .passkey-item .btn-danger {{
#                     margin-top: 12px;
#                     align-self: flex-end;
#                 }}
#             }}
#         </style>
#     </head>
#     <body>
#         <div class="container">
#             <h1>Set Up Passkeys</h1>
            
#             <div class="user-info">
#                 <p><strong>Logged in as:</strong> {username}</p>
#             </div>
            
#             <div id="webauthn-support-check">
#                 <div id="supported" class="hidden">
#                     <p>Your browser supports passkeys! You can use biometrics (like fingerprint or face recognition) or hardware security keys to sign in securely without passwords.</p>
#                     <div class="actions">
#                         <button id="setup-passkey" class="btn-primary">Set Up New Passkey</button>
#                         <a href="/auth/webauthn/manage" class="btn-secondary">Manage Existing Passkeys</a>
#                     </div>
#                 </div>
#                 <div id="not-supported" class="hidden">
#                     <p>Your browser doesn't support passkeys. Please use a modern browser like Chrome, Firefox, Safari, or Edge to set up passkeys.</p>
#                     <div class="actions">
#                         <a href="/auth/login" class="btn-secondary">Continue with Password</a>
#                     </div>
#                 </div>
#             </div>
            
#             <div id="setup-form" class="hidden">
#                 <h2>Create New Passkey</h2>
#                 <label for="device-name">Device Name (Optional):</label>
#                 <input type="text" id="device-name" placeholder="e.g., My Laptop, Work Computer, iPhone">
#                 <div class="actions">
#                     <button id="create-passkey" class="btn-primary">Create Passkey</button>
#                     <button id="cancel-setup" class="btn-secondary">Cancel</button>
#                 </div>
#             </div>
            
#             <div id="status-messages"></div>
            
#             <div class="existing-passkeys">
#                 <h2>Your Passkeys</h2>
#                 <div id="passkey-list"></div>
#             </div>
#         </div>
        
#         <script>
#             class WebAuthnSetup {{
#                 constructor() {{
#                     this.apiBase = '/auth/webauthn';
#                     this.init();
#                 }}
                
#                 async init() {{
#                     // Check authentication first
#                     if (!this.checkAuthentication()) {{
#                         return; // Will redirect to login
#                     }}
                    
#                     this.checkWebAuthnSupport();
#                     this.bindEvents();
#                     await this.loadExistingPasskeys();
#                 }}
                
#                 checkAuthentication() {{
#                     const token = this.getToken();
#                     if (!token) {{
#                         this.showMessage('Please log in to access this page', 'error');
#                         setTimeout(() => {{
#                             window.location.href = '/auth/login';
#                         }}, 2000);
#                         return false;
#                     }}
#                     return true;
#                 }}
                
#                 checkWebAuthnSupport() {{
#                     const supported = document.getElementById('supported');
#                     const notSupported = document.getElementById('not-supported');
                    
#                     if (window.PublicKeyCredential && 
#                         typeof window.PublicKeyCredential.create === 'function') {{
#                         supported.classList.remove('hidden');
#                     }} else {{
#                         notSupported.classList.remove('hidden');
#                     }}
#                 }}
                
#                 bindEvents() {{
#                     document.getElementById('setup-passkey')?.addEventListener('click', () => {{
#                         document.getElementById('setup-form').classList.remove('hidden');
#                     }});
                    
#                     document.getElementById('cancel-setup')?.addEventListener('click', () => {{
#                         document.getElementById('setup-form').classList.add('hidden');
#                         document.getElementById('device-name').value = '';
#                     }});
                    
#                     document.getElementById('create-passkey')?.addEventListener('click', 
#                         this.createPasskey.bind(this));
#                 }}
                
#                 async createPasskey() {{
#                     try {{
#                         this.showStatus('Creating passkey...', 'info');
                        
#                         const deviceName = document.getElementById('device-name').value.trim() || 'Browser Passkey';
                        
#                         // Begin registration
#                         const beginResponse = await fetch(`${{this.apiBase}}/register/begin`, {{
#                             method: 'POST',
#                             headers: {{
#                                 'Content-Type': 'application/json',
#                                 'Authorization': `Bearer ${{this.getToken()}}`
#                             }},
#                             body: JSON.stringify({{ device_name: deviceName }})
#                         }});
                        
#                         if (!beginResponse.ok) {{
#                             const errorData = await beginResponse.json();
#                             throw new Error(errorData.detail || 'Failed to start passkey creation');
#                         }}
                        
#                         const options = await beginResponse.json();
                        
#                         // Convert base64url strings to ArrayBuffers
#                         options.challenge = this.base64urlToArrayBuffer(options.challenge);
#                         options.user.id = this.base64urlToArrayBuffer(options.user.id);
                        
#                         if (options.excludeCredentials) {{
#                             options.excludeCredentials = options.excludeCredentials.map(cred => ({{
#                                 ...cred,
#                                 id: this.base64urlToArrayBuffer(cred.id)
#                             }}));
#                         }}
                        
#                         // Create credential
#                         const credential = await navigator.credentials.create({{
#                             publicKey: options
#                         }});
                        
#                         if (!credential) {{
#                             throw new Error('Failed to create credential');
#                         }}
                        
#                         // Complete registration
#                         const completeResponse = await fetch(`${{this.apiBase}}/register/complete`, {{
#                             method: 'POST',
#                             headers: {{
#                                 'Content-Type': 'application/json',
#                                 'Authorization': `Bearer ${{this.getToken()}}`
#                             }},
#                             body: JSON.stringify({{
#                                 id: credential.id,
#                                 rawId: this.arrayBufferToBase64url(credential.rawId),
#                                 response: {{
#                                     attestationObject: this.arrayBufferToBase64url(credential.response.attestationObject),
#                                     clientDataJSON: this.arrayBufferToBase64url(credential.response.clientDataJSON)
#                                 }},
#                                 type: credential.type
#                             }})
#                         }});
                        
#                         if (!completeResponse.ok) {{
#                             const errorData = await completeResponse.json();
#                             throw new Error(errorData.detail || 'Failed to complete passkey creation');
#                         }}
                        
#                         this.showStatus('Passkey created successfully!', 'success');
#                         await this.loadExistingPasskeys();
#                         document.getElementById('setup-form').classList.add('hidden');
#                         document.getElementById('device-name').value = '';
                        
#                     }} catch (error) {{
#                         console.error('Passkey creation failed:', error);
#                         this.showStatus(`Failed to create passkey: ${{error.message}}`, 'error');
#                     }}
#                 }}
                
#                 async loadExistingPasskeys() {{
#                     try {{
#                         const response = await fetch(`${{this.apiBase}}/credentials`, {{
#                             headers: {{
#                                 'Authorization': `Bearer ${{this.getToken()}}`
#                             }}
#                         }});
                        
#                         if (!response.ok) return;
                        
#                         const data = await response.json();
#                         this.renderPasskeyList(data.credentials);
                        
#                     }} catch (error) {{
#                         console.error('Failed to load passkeys:', error);
#                     }}
#                 }}
                
#                 renderPasskeyList(credentials) {{
#                     const container = document.getElementById('passkey-list');
                    
#                     if (!credentials || credentials.length === 0) {{
#                         container.innerHTML = '<p class="no-passkeys">No passkeys registered yet. Create your first passkey above!</p>';
#                         return;
#                     }}
                    
#                     container.innerHTML = credentials.map(cred => `
#                         <div class="passkey-item">
#                             <div class="passkey-info">
#                                 <h3>${{this.escapeHtml(cred.device_name)}}</h3>
#                                 <p><strong>Type:</strong> ${{cred.authenticator_type}}</p>
#                                 <p><strong>Created:</strong> ${{new Date(cred.created_at).toLocaleDateString()}}</p>
#                                 ${{cred.last_used_at ? 
#                                     `<p><strong>Last used:</strong> ${{new Date(cred.last_used_at).toLocaleDateString()}}</p>` : 
#                                     '<p><strong>Last used:</strong> Never</p>'
#                                 }}
#                             </div>
#                             <button class="btn-danger delete-passkey" data-credential-id="${{cred.credential_id}}">
#                                 Delete
#                             </button>
#                         </div>
#                     `).join('');
                    
#                     // Bind delete events
#                     container.querySelectorAll('.delete-passkey').forEach(btn => {{
#                         btn.addEventListener('click', (e) => {{
#                             this.deletePasskey(e.target.dataset.credentialId);
#                         }});
#                     }});
#                 }}
                
#                 async deletePasskey(credentialId) {{
#                     if (!confirm('Are you sure you want to delete this passkey? This action cannot be undone.')) {{
#                         return;
#                     }}
                    
#                     try {{
#                         const response = await fetch(`${{this.apiBase}}/credentials/${{credentialId}}`, {{
#                             method: 'DELETE',
#                             headers: {{
#                                 'Authorization': `Bearer ${{this.getToken()}}`
#                             }}
#                         }});
                        
#                         if (!response.ok) {{
#                             const errorData = await response.json();
#                             throw new Error(errorData.detail || 'Failed to delete passkey');
#                         }}
                        
#                         this.showStatus('Passkey deleted successfully', 'success');
#                         await this.loadExistingPasskeys();
                        
#                     }} catch (error) {{
#                         console.error('Failed to delete passkey:', error);
#                         this.showStatus(`Failed to delete passkey: ${{error.message}}`, 'error');
#                     }}
#                 }}
                
#                 showStatus(message, type) {{
#                     const container = document.getElementById('status-messages');
#                     const statusDiv = document.createElement('div');
#                     statusDiv.className = `status-message ${{type}}`;
#                     statusDiv.textContent = message;
                    
#                     container.appendChild(statusDiv);
                    
#                     setTimeout(() => {{
#                         statusDiv.remove();
#                     }}, 5000);
#                 }}
                
#                 getToken() {{
#                     // Get JWT token from localStorage, sessionStorage, or cookie
#                     return localStorage.getItem('access_token') || 
#                            sessionStorage.getItem('access_token') ||
#                            this.getCookieValue('access_token');
#                 }}
                
#                 getCookieValue(name) {{
#                     const value = `; ${{document.cookie}}`;
#                     const parts = value.split(`; ${{name}}=`);
#                     if (parts.length === 2) return parts.pop().split(';').shift();
#                     return null;
#                 }}
                
#                 base64urlToArrayBuffer(base64url) {{
#                     const padding = '='.repeat((4 - base64url.length % 4) % 4);
#                     const base64 = (base64url + padding).replace(/-/g, '+').replace(/_/g, '/');
#                     const rawData = window.atob(base64);
#                     const outputArray = new Uint8Array(rawData.length);
#                     for (let i = 0; i < rawData.length; ++i) {{
#                         outputArray[i] = rawData.charCodeAt(i);
#                     }}
#                     return outputArray.buffer;
#                 }}
                
#                 arrayBufferToBase64url(buffer) {{
#                     const bytes = new Uint8Array(buffer);
#                     let str = '';
#                     for (let i = 0; i < bytes.byteLength; i++) {{
#                         str += String.fromCharCode(bytes[i]);
#                     }}
#                     return window.btoa(str).replace(/\\+/g, '-').replace(/\\//g, '_').replace(/=/g, '');
#                 }}
                
#                 escapeHtml(text) {{
#                     const map = {{
#                         '&': '&amp;',
#                         '<': '&lt;',
#                         '>': '&gt;',
#                         '"': '&quot;',
#                         "'": '&#039;'
#                     }};
#                     return text.replace(/[&<>"']/g, m => map[m]);
#                 }}
#             }}
            
#             // Initialize when DOM is loaded
#             document.addEventListener('DOMContentLoaded', () => {{
#                 new WebAuthnSetup();
#             }});
#         </script>
#     </body>
#     </html>
#     """
    
#     return HTMLResponse(content=html)


# def render_webauthn_manage_page() -> HTMLResponse:
#     """
#     Serve the WebAuthn passkey management HTML page.
    
#     Args:
#         username (str): The authenticated user's username
#         user_id (str): The authenticated user's ID
        
#     Returns:
#         HTMLResponse: The rendered HTML page for passkey management
#     """
#     html = f"""
#     <!DOCTYPE html>
#     <html lang="en">
#     <head>
#         <meta charset="UTF-8">
#         <meta name="viewport" content="width=device-width, initial-scale=1.0">
#         <title>Manage Passkeys - Second Brain Database</title>
#         <link href="https://fonts.googleapis.com/css?family=Roboto:400,700&display=swap" rel="stylesheet">
#         <style>
#             :root {{
#                 --primary: #3a86ff;
#                 --primary-hover: #265dbe;
#                 --background: #f6f8fa;
#                 --foreground: #ffffff;
#                 --text-main: #22223b;
#                 --text-sub: #4a4e69;
#                 --border-color: #c9c9c9;
#                 --error: #d90429;
#                 --success: #06d6a0;
#                 --info: #0c5460;
#             }}
            
#             * {{ box-sizing: border-box; }}
            
#             body {{
#                 margin: 0;
#                 background-color: var(--background);
#                 font-family: 'Roboto', sans-serif;
#                 padding: 20px;
#                 min-height: 100vh;
#             }}
            
#             .container {{
#                 max-width: 800px;
#                 margin: 0 auto;
#                 background-color: var(--foreground);
#                 padding: 2.5rem 2rem;
#                 border-radius: 12px;
#                 box-shadow: 0 4px 24px rgba(0, 0, 0, 0.08);
#             }}
            
#             .hidden {{
#                 display: none !important;
#             }}
            
#             h1 {{
#                 margin-bottom: 1.5rem;
#                 color: var(--text-main);
#                 font-size: 2rem;
#                 font-weight: 700;
#                 text-align: center;
#             }}
            
#             .btn-primary, .btn-secondary, .btn-danger {{
#                 padding: 12px 24px;
#                 border: none;
#                 border-radius: 6px;
#                 font-size: 16px;
#                 cursor: pointer;
#                 text-decoration: none;
#                 display: inline-block;
#                 margin: 8px;
#                 transition: background-color 0.2s;
#                 font-weight: 500;
#             }}
            
#             .btn-primary {{
#                 background-color: var(--primary);
#                 color: white;
#             }}
            
#             .btn-primary:hover {{
#                 background-color: var(--primary-hover);
#             }}
            
#             .btn-secondary {{
#                 background-color: #6c757d;
#                 color: white;
#             }}
            
#             .btn-danger {{
#                 background-color: var(--error);
#                 color: white;
#             }}
            
#             .btn-danger:hover {{
#                 background-color: #c82333;
#             }}
            
#             .actions {{
#                 margin-bottom: 20px;
#                 text-align: center;
#             }}
            
#             .user-info {{
#                 background-color: var(--background);
#                 padding: 15px;
#                 border-radius: 8px;
#                 margin-bottom: 20px;
#                 text-align: center;
#             }}
            
#             .passkey-grid {{
#                 display: grid;
#                 gap: 16px;
#             }}
            
#             .passkey-item {{
#                 display: flex;
#                 justify-content: space-between;
#                 align-items: center;
#                 padding: 20px;
#                 border: 1px solid var(--border-color);
#                 border-radius: 8px;
#                 background-color: var(--background);
#             }}
            
#             .passkey-info h3 {{
#                 margin: 0 0 8px 0;
#                 color: var(--text-main);
#                 font-size: 1.2rem;
#             }}
            
#             .passkey-info p {{
#                 margin: 4px 0;
#                 color: var(--text-sub);
#                 font-size: 14px;
#             }}
            
#             .status-message {{
#                 padding: 12px;
#                 border-radius: 4px;
#                 margin: 8px 0;
#             }}
            
#             .status-message.success {{
#                 background-color: #d4edda;
#                 color: #155724;
#                 border: 1px solid #c3e6cb;
#             }}
            
#             .status-message.error {{
#                 background-color: #f8d7da;
#                 color: #721c24;
#                 border: 1px solid #f5c6cb;
#             }}
            
#             .status-message.info {{
#                 background-color: #d1ecf1;
#                 color: var(--info);
#                 border: 1px solid #bee5eb;
#             }}
            
#             .no-passkeys {{
#                 text-align: center;
#                 color: var(--text-sub);
#                 font-style: italic;
#                 padding: 60px 20px;
#                 background-color: var(--background);
#                 border-radius: 8px;
#             }}
            
#             .modal {{
#                 position: fixed;
#                 top: 0;
#                 left: 0;
#                 width: 100%;
#                 height: 100%;
#                 background-color: rgba(0, 0, 0, 0.5);
#                 display: flex;
#                 align-items: center;
#                 justify-content: center;
#                 z-index: 1000;
#             }}
            
#             .modal-content {{
#                 background-color: var(--foreground);
#                 padding: 30px;
#                 border-radius: 12px;
#                 max-width: 400px;
#                 width: 90%;
#                 text-align: center;
#             }}
            
#             .modal-content h3 {{
#                 margin-top: 0;
#                 color: var(--text-main);
#             }}
            
#             .modal-content p {{
#                 color: var(--text-sub);
#                 margin-bottom: 20px;
#             }}
            
#             .modal-actions {{
#                 display: flex;
#                 gap: 10px;
#                 justify-content: center;
#             }}
            
#             @media (max-width: 768px) {{
#                 .container {{
#                     padding: 1rem;
#                 }}
                
#                 .passkey-item {{
#                     flex-direction: column;
#                     align-items: flex-start;
#                 }}
                
#                 .passkey-item .btn-danger {{
#                     margin-top: 12px;
#                     align-self: flex-end;
#                 }}
#             }}
#         </style>
#     </head>
#     <body>
#         <div class="container">
#             <h1>Manage Your Passkeys</h1>
            
#             <div class="user-info">
#                 <p><strong>Logged in as:</strong> {username}</p>
#             </div>
            
#             <div class="actions">
#                 <a href="/auth/webauthn/setup" class="btn-primary">Add New Passkey</a>
#                 <a href="/auth/login" class="btn-secondary">Back to Login</a>
#             </div>
            
#             <div id="status-messages"></div>
            
#             <div id="passkey-list" class="passkey-grid"></div>
            
#             <div id="delete-modal" class="modal hidden">
#                 <div class="modal-content">
#                     <h3>Delete Passkey</h3>
#                     <p>Are you sure you want to delete this passkey? This action cannot be undone and you may lose access to your account if this is your only authentication method.</p>
#                     <div class="modal-actions">
#                         <button id="confirm-delete" class="btn-danger">Delete Passkey</button>
#                         <button id="cancel-delete" class="btn-secondary">Cancel</button>
#                     </div>
#                 </div>
#             </div>
#         </div>
        
#         <script>
#             class WebAuthnManager {{
#                 constructor() {{
#                     this.apiBase = '/auth/webauthn';
#                     this.currentCredentialId = null;
#                     this.init();
#                 }}
                
#                 async init() {{
#                     this.bindEvents();
#                     await this.loadPasskeys();
#                 }}
                
#                 bindEvents() {{
#                     document.getElementById('confirm-delete')?.addEventListener('click', () => {{
#                         this.confirmDelete();
#                     }});
                    
#                     document.getElementById('cancel-delete')?.addEventListener('click', () => {{
#                         this.hideDeleteModal();
#                     }});
                    
#                     // Close modal on background click
#                     document.getElementById('delete-modal')?.addEventListener('click', (e) => {{
#                         if (e.target.id === 'delete-modal') {{
#                             this.hideDeleteModal();
#                         }}
#                     }});
#                 }}
                
#                 async loadPasskeys() {{
#                     try {{
#                         this.showStatus('Loading your passkeys...', 'info');
                        
#                         const response = await fetch(`${{this.apiBase}}/credentials`, {{
#                             headers: {{
#                                 'Authorization': `Bearer ${{this.getToken()}}`
#                             }}
#                         }});
                        
#                         if (!response.ok) {{
#                             throw new Error('Failed to load passkeys');
#                         }}
                        
#                         const data = await response.json();
#                         this.renderPasskeyList(data.credentials);
                        
#                         // Clear loading message
#                         document.getElementById('status-messages').innerHTML = '';
                        
#                     }} catch (error) {{
#                         console.error('Failed to load passkeys:', error);
#                         this.showStatus(`Failed to load passkeys: ${{error.message}}`, 'error');
#                     }}
#                 }}
                
#                 renderPasskeyList(credentials) {{
#                     const container = document.getElementById('passkey-list');
                    
#                     if (!credentials || credentials.length === 0) {{
#                         container.innerHTML = `
#                             <div class="no-passkeys">
#                                 <h3>No Passkeys Found</h3>
#                                 <p>You haven't set up any passkeys yet. Passkeys provide a secure, passwordless way to sign in using biometrics or hardware security keys.</p>
#                                 <a href="/auth/webauthn/setup" class="btn-primary">Set Up Your First Passkey</a>
#                             </div>
#                         `;
#                         return;
#                     }}
                    
#                     container.innerHTML = credentials.map(cred => `
#                         <div class="passkey-item">
#                             <div class="passkey-info">
#                                 <h3>${{this.escapeHtml(cred.device_name)}}</h3>
#                                 <p><strong>Type:</strong> ${{this.formatAuthenticatorType(cred.authenticator_type)}}</p>
#                                 <p><strong>Transport:</strong> ${{this.formatTransport(cred.transport)}}</p>
#                                 <p><strong>Created:</strong> ${{new Date(cred.created_at).toLocaleDateString('en-US', {{
#                                     year: 'numeric',
#                                     month: 'long',
#                                     day: 'numeric',
#                                     hour: '2-digit',
#                                     minute: '2-digit'
#                                 }})}}</p>
#                                 ${{cred.last_used_at ? 
#                                     `<p><strong>Last used:</strong> ${{new Date(cred.last_used_at).toLocaleDateString('en-US', {{
#                                         year: 'numeric',
#                                         month: 'long',
#                                         day: 'numeric',
#                                         hour: '2-digit',
#                                         minute: '2-digit'
#                                     }})}}</p>` : 
#                                     '<p><strong>Last used:</strong> Never</p>'
#                                 }}
#                                 <p><strong>Status:</strong> ${{cred.is_active ? 'Active' : 'Inactive'}}</p>
#                             </div>
#                             <button class="btn-danger delete-passkey" data-credential-id="${{cred.credential_id}}" data-device-name="${{this.escapeHtml(cred.device_name)}}">
#                                 Delete
#                             </button>
#                         </div>
#                     `).join('');
                    
#                     // Bind delete events
#                     container.querySelectorAll('.delete-passkey').forEach(btn => {{
#                         btn.addEventListener('click', (e) => {{
#                             this.showDeleteModal(e.target.dataset.credentialId, e.target.dataset.deviceName);
#                         }});
#                     }});
#                 }}
                
#                 formatAuthenticatorType(type) {{
#                     switch (type) {{
#                         case 'platform':
#                             return 'Platform (Built-in biometrics)';
#                         case 'cross-platform':
#                             return 'Cross-platform (Hardware key)';
#                         default:
#                             return type || 'Unknown';
#                     }}
#                 }}
                
#                 formatTransport(transport) {{
#                     if (!transport || transport.length === 0) return 'Unknown';
                    
#                     const transportMap = {{
#                         'internal': 'Built-in',
#                         'usb': 'USB',
#                         'nfc': 'NFC',
#                         'ble': 'Bluetooth'
#                     }};
                    
#                     return transport.map(t => transportMap[t] || t).join(', ');
#                 }}
                
#                 showDeleteModal(credentialId, deviceName) {{
#                     this.currentCredentialId = credentialId;
#                     const modal = document.getElementById('delete-modal');
#                     const modalContent = modal.querySelector('.modal-content p');
#                     modalContent.textContent = `Are you sure you want to delete the passkey "${{deviceName}}"? This action cannot be undone and you may lose access to your account if this is your only authentication method.`;
#                     modal.classList.remove('hidden');
#                 }}
                
#                 hideDeleteModal() {{
#                     document.getElementById('delete-modal').classList.add('hidden');
#                     this.currentCredentialId = null;
#                 }}
                
#                 async confirmDelete() {{
#                     if (!this.currentCredentialId) return;
                    
#                     try {{
#                         this.showStatus('Deleting passkey...', 'info');
                        
#                         const response = await fetch(`${{this.apiBase}}/credentials/${{this.currentCredentialId}}`, {{
#                             method: 'DELETE',
#                             headers: {{
#                                 'Authorization': `Bearer ${{this.getToken()}}`
#                             }}
#                         }});
                        
#                         if (!response.ok) {{
#                             const errorData = await response.json();
#                             throw new Error(errorData.detail || 'Failed to delete passkey');
#                         }}
                        
#                         this.showStatus('Passkey deleted successfully', 'success');
#                         this.hideDeleteModal();
#                         await this.loadPasskeys();
                        
#                     }} catch (error) {{
#                         console.error('Failed to delete passkey:', error);
#                         this.showStatus(`Failed to delete passkey: ${{error.message}}`, 'error');
#                     }}
#                 }}
                
#                 showStatus(message, type) {{
#                     const container = document.getElementById('status-messages');
#                     const statusDiv = document.createElement('div');
#                     statusDiv.className = `status-message ${{type}}`;
#                     statusDiv.textContent = message;
                    
#                     container.appendChild(statusDiv);
                    
#                     setTimeout(() => {{
#                         statusDiv.remove();
#                     }}, 5000);
#                 }}
                
#                 getToken() {{
#                     // Get JWT token from localStorage, sessionStorage, or cookie
#                     return localStorage.getItem('access_token') || 
#                            sessionStorage.getItem('access_token') ||
#                            this.getCookieValue('access_token');
#                 }}
                
#                 getCookieValue(name) {{
#                     const value = `; ${{document.cookie}}`;
#                     const parts = value.split(`; ${{name}}=`);
#                     if (parts.length === 2) return parts.pop().split(';').shift();
#                     return null;
#                 }}
                
#                 escapeHtml(text) {{
#                     const map = {{
#                         '&': '&amp;',
#                         '<': '&lt;',
#                         '>': '&gt;',
#                         '"': '&quot;',
#                         "'": '&#039;'
#                     }};
#                     return text.replace(/[&<>"']/g, m => map[m]);
#                 }}
#             }}
            
#             // Initialize when DOM is loaded
#             document.addEventListener('DOMContentLoaded', () => {{
#                 new WebAuthnManager();
#             }});
#         </script>
#     </body>
#     </html>
#     """
    
#     return HTMLResponse(content=html)
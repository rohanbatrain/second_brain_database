#!/usr/bin/env python3
"""
OAuth2 Client Registration Script

This script helps you register a new OAuth2 client with the Second Brain Database
to get your client ID and secret for testing.
"""
import os
import sys
import json
import requests
from getpass import getpass


def register_oauth2_client():
    """Register a new OAuth2 client."""
    print("🔐 OAuth2 Client Registration")
    print("=" * 40)
    
    # Get OAuth2 provider URL
    base_url = input("Enter OAuth2 provider URL (e.g., http://localhost:8000): ").strip()
    if not base_url:
        base_url = "http://localhost:8000"
    
    base_url = base_url.rstrip('/')
    
    print(f"Using OAuth2 provider: {base_url}")
    print()
    
    # Get authentication token
    print("You need to authenticate to register a client.")
    print("Options:")
    print("1. Use existing access token")
    print("2. Login with username/password")
    
    choice = input("Choose option (1 or 2): ").strip()
    
    access_token = None
    
    if choice == "1":
        access_token = getpass("Enter your access token: ").strip()
    elif choice == "2":
        username = input("Username: ").strip()
        password = getpass("Password: ").strip()
        
        # Try to get access token via login
        try:
            login_response = requests.post(
                f"{base_url}/oauth/login",
                json={"username": username, "password": password},
                timeout=30
            )
            
            if login_response.ok:
                login_data = login_response.json()
                access_token = login_data.get('access_token')
                if access_token:
                    print("✅ Login successful!")
                else:
                    print("❌ No access token in login response")
                    return False
            else:
                print(f"❌ Login failed: {login_response.status_code}")
                try:
                    error_data = login_response.json()
                    print(f"Error: {error_data}")
                except:
                    print(f"Error: {login_response.text}")
                return False
                
        except requests.RequestException as e:
            print(f"❌ Login request failed: {e}")
            return False
    else:
        print("❌ Invalid choice")
        return False
    
    if not access_token:
        print("❌ No access token available")
        return False
    
    print()
    
    # Get client registration details
    print("📝 Client Registration Details")
    print("-" * 30)
    
    client_name = input("Client name (e.g., 'OAuth2 Test Flask App'): ").strip()
    if not client_name:
        client_name = "OAuth2 Test Flask App"
    
    client_description = input("Client description (optional): ").strip()
    if not client_description:
        client_description = "Test application for OAuth2 integration testing"
    
    redirect_uri = input("Redirect URI (default: http://localhost:5000/callback): ").strip()
    if not redirect_uri:
        redirect_uri = "http://localhost:5000/callback"
    
    website_url = input("Website URL (optional): ").strip()
    
    # Default scopes for testing
    scopes = ["read:profile", "write:data"]
    custom_scopes = input(f"Scopes (default: {', '.join(scopes)}): ").strip()
    if custom_scopes:
        scopes = [s.strip() for s in custom_scopes.split(',')]
    
    client_type = input("Client type (confidential/public, default: confidential): ").strip()
    if not client_type:
        client_type = "confidential"
    
    # Prepare registration data
    registration_data = {
        "name": client_name,
        "description": client_description,
        "redirect_uris": [redirect_uri],
        "client_type": client_type,
        "scopes": scopes
    }
    
    if website_url:
        registration_data["website_url"] = website_url
    
    print()
    print("📋 Registration Summary:")
    print(json.dumps(registration_data, indent=2))
    print()
    
    confirm = input("Register this client? (y/N): ").strip().lower()
    if confirm != 'y':
        print("❌ Registration cancelled")
        return False
    
    # Register the client
    try:
        print("🚀 Registering OAuth2 client...")
        
        response = requests.post(
            f"{base_url}/oauth2/clients",
            json=registration_data,
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            },
            timeout=30
        )
        
        if response.ok:
            client_data = response.json()
            print("✅ Client registered successfully!")
            print()
            print("🔑 Your OAuth2 Client Credentials:")
            print("=" * 40)
            print(f"Client ID: {client_data['client_id']}")
            if 'client_secret' in client_data:
                print(f"Client Secret: {client_data['client_secret']}")
            print(f"Client Type: {client_data['client_type']}")
            print(f"Redirect URIs: {', '.join(client_data['redirect_uris'])}")
            print(f"Scopes: {', '.join(client_data['scopes'])}")
            print(f"Created: {client_data.get('created_at', 'Unknown')}")
            print()
            
            # Generate .env content
            print("📄 .env Configuration:")
            print("-" * 20)
            print(f"OAUTH2_CLIENT_ID={client_data['client_id']}")
            if 'client_secret' in client_data:
                print(f"OAUTH2_CLIENT_SECRET={client_data['client_secret']}")
            print(f"OAUTH2_REDIRECT_URI={redirect_uri}")
            print(f"OAUTH2_BASE_URL={base_url}")
            print("SECRET_KEY=your-secure-secret-key-here")
            print("FLASK_ENV=development")
            print("PORT=5000")
            print()
            
            # Offer to save to .env file
            save_env = input("Save configuration to .env file? (y/N): ").strip().lower()
            if save_env == 'y':
                try:
                    with open('.env', 'w') as f:
                        f.write("# OAuth2 Provider Configuration\n")
                        f.write(f"OAUTH2_CLIENT_ID={client_data['client_id']}\n")
                        if 'client_secret' in client_data:
                            f.write(f"OAUTH2_CLIENT_SECRET={client_data['client_secret']}\n")
                        f.write(f"OAUTH2_REDIRECT_URI={redirect_uri}\n")
                        f.write(f"OAUTH2_BASE_URL={base_url}\n")
                        f.write("\n# Flask Configuration\n")
                        f.write("SECRET_KEY=your-secure-secret-key-here\n")
                        f.write("FLASK_ENV=development\n")
                        f.write("PORT=5000\n")
                        f.write("\n# Optional: Enable debug logging\n")
                        f.write("FLASK_DEBUG=1\n")
                    
                    print("✅ Configuration saved to .env file")
                    print("⚠️  Remember to update SECRET_KEY with a secure value!")
                except Exception as e:
                    print(f"❌ Failed to save .env file: {e}")
            
            print()
            print("🎉 Next Steps:")
            print("1. Update SECRET_KEY in .env file with a secure value")
            print("2. Start the test application: python app.py")
            print("3. Navigate to http://localhost:5000")
            print("4. Test the OAuth2 flow!")
            
            return True
            
        else:
            print(f"❌ Client registration failed: {response.status_code}")
            try:
                error_data = response.json()
                print(f"Error: {error_data}")
            except:
                print(f"Error: {response.text}")
            return False
            
    except requests.RequestException as e:
        print(f"❌ Registration request failed: {e}")
        return False


def list_existing_clients():
    """List existing OAuth2 clients."""
    print("📋 List Existing OAuth2 Clients")
    print("=" * 35)
    
    base_url = input("Enter OAuth2 provider URL (e.g., http://localhost:8000): ").strip()
    if not base_url:
        base_url = "http://localhost:8000"
    
    base_url = base_url.rstrip('/')
    
    access_token = getpass("Enter your access token: ").strip()
    if not access_token:
        print("❌ Access token required")
        return False
    
    try:
        response = requests.get(
            f"{base_url}/oauth2/clients",
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=30
        )
        
        if response.ok:
            data = response.json()
            clients = data.get('data', {}).get('clients', [])
            
            if not clients:
                print("No OAuth2 clients found.")
                return True
            
            print(f"Found {len(clients)} client(s):")
            print()
            
            for i, client in enumerate(clients, 1):
                print(f"{i}. {client['name']}")
                print(f"   Client ID: {client['client_id']}")
                print(f"   Type: {client['client_type']}")
                print(f"   Scopes: {', '.join(client['scopes'])}")
                print(f"   Redirect URIs: {', '.join(client['redirect_uris'])}")
                print(f"   Created: {client.get('created_at', 'Unknown')}")
                print(f"   Active: {'Yes' if client.get('is_active', True) else 'No'}")
                print()
            
            return True
            
        else:
            print(f"❌ Failed to list clients: {response.status_code}")
            try:
                error_data = response.json()
                print(f"Error: {error_data}")
            except:
                print(f"Error: {response.text}")
            return False
            
    except requests.RequestException as e:
        print(f"❌ Request failed: {e}")
        return False


def main():
    """Main function."""
    print("OAuth2 Client Management")
    print("=" * 25)
    print("1. Register new OAuth2 client")
    print("2. List existing OAuth2 clients")
    print()
    
    choice = input("Choose option (1 or 2): ").strip()
    
    if choice == "1":
        success = register_oauth2_client()
    elif choice == "2":
        success = list_existing_clients()
    else:
        print("❌ Invalid choice")
        success = False
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
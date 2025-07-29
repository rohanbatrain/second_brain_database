#!/usr/bin/env python3
"""
OAuth2 Flow Testing Script

This script helps test the OAuth2 flow programmatically without a browser.
Useful for automated testing and debugging.
"""
import os
import sys
import json
import time
from urllib.parse import urlparse, parse_qs
from oauth2_client import OAuth2Client, OAuth2Error


def test_oauth2_flow():
    """Test the complete OAuth2 flow."""
    print("🔐 OAuth2 Flow Testing Script")
    print("=" * 50)
    
    # Load configuration
    client_id = os.getenv('OAUTH2_CLIENT_ID')
    client_secret = os.getenv('OAUTH2_CLIENT_SECRET')
    redirect_uri = os.getenv('OAUTH2_REDIRECT_URI', 'http://localhost:5000/callback')
    base_url = os.getenv('OAUTH2_BASE_URL', 'http://localhost:8000')
    
    if not all([client_id, client_secret]):
        print("❌ Missing OAuth2 configuration. Please set environment variables:")
        print("   - OAUTH2_CLIENT_ID")
        print("   - OAUTH2_CLIENT_SECRET")
        print("   - OAUTH2_BASE_URL (optional, defaults to http://localhost:8000)")
        return False
    
    print(f"📋 Configuration:")
    print(f"   Client ID: {client_id}")
    print(f"   Redirect URI: {redirect_uri}")
    print(f"   Base URL: {base_url}")
    print()
    
    # Initialize OAuth2 client
    oauth2_client = OAuth2Client(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        base_url=base_url
    )
    
    try:
        # Step 1: Generate authorization URL
        print("1️⃣ Generating authorization URL...")
        auth_url, state, code_verifier = oauth2_client.get_authorization_url()
        print(f"   Authorization URL: {auth_url}")
        print(f"   State: {state}")
        print(f"   Code Verifier: {code_verifier[:20]}...")
        print()
        
        # Step 2: Simulate authorization (manual step)
        print("2️⃣ Manual Authorization Required:")
        print("   1. Open the authorization URL in your browser")
        print("   2. Complete the OAuth2 flow")
        print("   3. Copy the authorization code from the callback URL")
        print()
        
        # Get authorization code from user
        auth_code = input("📝 Enter the authorization code from callback URL: ").strip()
        if not auth_code:
            print("❌ No authorization code provided")
            return False
        
        # Step 3: Exchange code for tokens
        print("3️⃣ Exchanging authorization code for tokens...")
        tokens = oauth2_client.exchange_code_for_tokens(auth_code, code_verifier)
        print("✅ Token exchange successful!")
        print(f"   Access Token: {tokens['access_token'][:20]}...")
        print(f"   Token Type: {tokens.get('token_type', 'Bearer')}")
        print(f"   Expires In: {tokens.get('expires_in', 'Unknown')} seconds")
        print(f"   Scope: {tokens.get('scope', 'Unknown')}")
        if 'refresh_token' in tokens:
            print(f"   Refresh Token: {tokens['refresh_token'][:20]}...")
        print()
        
        # Step 4: Test API requests
        print("4️⃣ Testing API requests...")
        access_token = tokens['access_token']
        
        # Test profile endpoint
        try:
            print("   Testing /api/user/profile...")
            profile_data = oauth2_client.make_api_request('user/profile', access_token)
            print("   ✅ Profile request successful!")
            print(f"   Profile data: {json.dumps(profile_data, indent=2)}")
        except OAuth2Error as e:
            print(f"   ❌ Profile request failed: {e}")
        
        # Test health endpoint
        try:
            print("   Testing /api/health...")
            health_data = oauth2_client.make_api_request('health', access_token)
            print("   ✅ Health request successful!")
            print(f"   Health data: {json.dumps(health_data, indent=2)}")
        except OAuth2Error as e:
            print(f"   ❌ Health request failed: {e}")
        
        print()
        
        # Step 5: Test token refresh (if refresh token available)
        if 'refresh_token' in tokens:
            print("5️⃣ Testing token refresh...")
            try:
                new_tokens = oauth2_client.refresh_access_token(tokens['refresh_token'])
                print("✅ Token refresh successful!")
                print(f"   New Access Token: {new_tokens['access_token'][:20]}...")
                print(f"   Expires In: {new_tokens.get('expires_in', 'Unknown')} seconds")
                
                # Update tokens for revocation test
                tokens.update(new_tokens)
            except OAuth2Error as e:
                print(f"❌ Token refresh failed: {e}")
            print()
        
        # Step 6: Test token revocation
        print("6️⃣ Testing token revocation...")
        
        # Revoke refresh token
        if 'refresh_token' in tokens:
            success = oauth2_client.revoke_token(tokens['refresh_token'], 'refresh_token')
            if success:
                print("   ✅ Refresh token revoked successfully")
            else:
                print("   ❌ Refresh token revocation failed")
        
        # Revoke access token
        success = oauth2_client.revoke_token(tokens['access_token'], 'access_token')
        if success:
            print("   ✅ Access token revoked successfully")
        else:
            print("   ❌ Access token revocation failed")
        
        print()
        print("🎉 OAuth2 flow test completed successfully!")
        return True
        
    except OAuth2Error as e:
        print(f"❌ OAuth2 Error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")
        return False


def test_pkce_generation():
    """Test PKCE code generation."""
    print("🔒 Testing PKCE Generation")
    print("=" * 30)
    
    oauth2_client = OAuth2Client(
        client_id='test',
        client_secret='test',
        redirect_uri='test',
        base_url='test'
    )
    
    for i in range(3):
        verifier, challenge = oauth2_client.generate_pkce_pair()
        print(f"Test {i+1}:")
        print(f"   Code Verifier: {verifier}")
        print(f"   Code Challenge: {challenge}")
        print(f"   Verifier Length: {len(verifier)}")
        print(f"   Challenge Length: {len(challenge)}")
        print()
    
    print("✅ PKCE generation test completed!")


def main():
    """Main function."""
    if len(sys.argv) > 1 and sys.argv[1] == 'pkce':
        test_pkce_generation()
    else:
        # Load environment from .env file if available
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass
        
        success = test_oauth2_flow()
        sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
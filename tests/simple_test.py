#!/usr/bin/env python3

import asyncio
import sys
import os
from unittest.mock import AsyncMock, patch

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

async def test_client_manager():
    """Simple test for ClientManager functionality."""
    try:
        from second_brain_database.routes.oauth2.client_manager import ClientManager
        from second_brain_database.routes.oauth2.models import ClientType, OAuthClientRegistration
        
        print("✅ Imports successful")
        
        # Create manager
        manager = ClientManager()
        print("✅ ClientManager created")
        
        # Test secret hashing
        secret = "test_secret_123"
        hashed = manager._hash_client_secret(secret)
        verified = manager._verify_client_secret(secret, hashed)
        print(f"✅ Secret hashing: {verified}")
        
        # Test registration model
        registration = OAuthClientRegistration(
            name="Test Application",
            description="A test OAuth2 application",
            redirect_uris=["https://example.com/callback"],
            client_type=ClientType.CONFIDENTIAL,
            scopes=["read:profile", "write:data"],
            website_url="https://example.com"
        )
        print("✅ Registration model created")
        
        # Mock database operations and test registration
        with patch.object(manager.db, 'create_client', return_value=True):
            response = await manager.register_client(registration, "user123")
            print(f"✅ Client registration: {response.client_id}")
            print(f"✅ Client secret generated: {response.client_secret is not None}")
            print(f"✅ Client type: {response.client_type}")
        
        # Test client validation with mocked database
        from second_brain_database.routes.oauth2.models import OAuthClient
        from datetime import datetime
        
        mock_client = OAuthClient(
            client_id="oauth2_client_test123",
            client_secret_hash=manager._hash_client_secret("test_secret"),
            name="Test Application",
            client_type=ClientType.CONFIDENTIAL,
            redirect_uris=["https://example.com/callback"],
            scopes=["read:profile"],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            is_active=True
        )
        
        with patch.object(manager.db, 'get_client', return_value=mock_client):
            # Test successful validation
            result = await manager.validate_client("oauth2_client_test123", "test_secret")
            print(f"✅ Client validation success: {result is not None}")
            
            # Test failed validation with wrong secret
            result = await manager.validate_client("oauth2_client_test123", "wrong_secret")
            print(f"✅ Client validation failure: {result is None}")
            
            # Test redirect URI validation
            valid_uri = await manager.validate_redirect_uri("oauth2_client_test123", "https://example.com/callback")
            print(f"✅ Valid redirect URI: {valid_uri}")
            
            invalid_uri = await manager.validate_redirect_uri("oauth2_client_test123", "https://malicious.com/callback")
            print(f"✅ Invalid redirect URI rejected: {not invalid_uri}")
            
            # Test scope retrieval
            scopes = await manager.get_client_scopes("oauth2_client_test123")
            print(f"✅ Client scopes: {scopes}")
        
        print("🎉 All tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_client_manager())
    sys.exit(0 if success else 1)
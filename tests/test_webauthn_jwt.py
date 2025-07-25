#!/usr/bin/env python3
"""
Test script to verify WebAuthn JWT token generation works correctly.
"""

import asyncio
import sys
import os
sys.path.append('src')

# Mock the database and settings for testing
class MockSettings:
    ACCESS_TOKEN_EXPIRE_MINUTES = 30
    SECRET_KEY = 'test_secret_key_for_jwt_testing_only'
    ALGORITHM = 'HS256'

class MockCollection:
    async def find_one(self, query):
        if query.get('username') == 'testuser':
            return {'_id': 'test_id', 'username': 'testuser', 'token_version': 1}
        return None

class MockDbManager:
    def get_collection(self, name):
        return MockCollection()

# Mock the imports
import second_brain_database.config
import second_brain_database.database
second_brain_database.config.settings = MockSettings()
second_brain_database.database.db_manager = MockDbManager()

from second_brain_database.routes.auth.services.auth.login import create_access_token

async def test_tokens():
    try:
        # Test regular token
        regular_token_data = {'sub': 'testuser'}
        regular_token = await create_access_token(regular_token_data)
        print('✓ Regular token created successfully')
        
        # Test WebAuthn token
        webauthn_token_data = {
            'sub': 'testuser',
            'webauthn': True,
            'webauthn_credential_id': 'test_credential_123',
            'webauthn_device_name': 'Test Device',
            'webauthn_authenticator_type': 'platform'
        }
        webauthn_token = await create_access_token(webauthn_token_data)
        print('✓ WebAuthn token created successfully')
        
        print('✓ Both token types work correctly')
        return True
    except Exception as e:
        print(f'✗ Error: {e}')
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_tokens())
    print(f'Test result: {"PASSED" if result else "FAILED"}')
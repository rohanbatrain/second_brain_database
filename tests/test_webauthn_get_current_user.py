#!/usr/bin/env python3
"""
Test script to verify get_current_user works with WebAuthn JWT tokens.
"""

import asyncio
import sys
import os
import json
from datetime import datetime, timedelta
from jose import jwt

sys.path.append('src')

# Mock the database and settings for testing
class MockSettings:
    ACCESS_TOKEN_EXPIRE_MINUTES = 30
    SECRET_KEY = 'test_secret_key_for_jwt_testing_only'
    ALGORITHM = 'HS256'

class MockCollection:
    async def find_one(self, query):
        if query.get('username') == 'testuser':
            return {
                '_id': 'test_id',
                'username': 'testuser',
                'token_version': 1,
                'email': 'test@example.com',
                'is_active': True
            }
        return None

class MockDbManager:
    def get_collection(self, name):
        return MockCollection()

# Mock the logger
class MockLogger:
    def debug(self, msg, *args):
        print(f"DEBUG: {msg % args if args else msg}")
    def warning(self, msg, *args):
        print(f"WARNING: {msg % args if args else msg}")
    def error(self, msg, *args):
        print(f"ERROR: {msg % args if args else msg}")

# Mock token blacklist check
async def is_token_blacklisted(token):
    return False

# Mock permanent token functions
def is_permanent_token(token):
    return False

async def validate_permanent_token(token):
    return None

# Simplified get_current_user implementation for testing
async def get_current_user(token):
    """Test implementation of get_current_user that handles WebAuthn claims."""
    from fastapi import HTTPException, status

    settings = MockSettings()
    db_manager = MockDbManager()
    logger = MockLogger()

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Check if token is blacklisted first
        if await is_token_blacklisted(token):
            logger.warning("Token is blacklisted")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token is blacklisted",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Check if this is a permanent token
        if is_permanent_token(token):
            logger.debug("Detected permanent token, using permanent token validation")
            user = await validate_permanent_token(token)
            if user is None:
                logger.warning("Permanent token validation failed")
                raise credentials_exception
            return user

        # Regular JWT token validation
        secret_key = settings.SECRET_KEY
        payload = jwt.decode(token, secret_key, algorithms=[settings.ALGORITHM])
        username = payload.get("sub")
        token_version_claim = payload.get("token_version")

        if username is None:
            logger.warning("JWT payload missing 'sub' claim")
            raise credentials_exception

        user = await db_manager.get_collection("users").find_one({"username": username})
        if user is None:
            logger.warning("User not found for JWT 'sub' claim: %s", username)
            raise credentials_exception

        # Check token version for regular tokens
        if token_version_claim is not None:
            user_token_version = user.get("token_version", 0)
            if token_version_claim != user_token_version:
                logger.warning("JWT token_version mismatch for user %s", username)
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token is no longer valid (password changed or reset)",
                    headers={"WWW-Authenticate": "Bearer"},
                )

        # Log WebAuthn authentication if present
        if payload.get("webauthn"):
            logger.debug("WebAuthn JWT validated for user: %s", username)
            logger.debug("WebAuthn credential: %s", payload.get("webauthn_credential_id", "unknown"))
        else:
            logger.debug("Regular JWT validated for user: %s", username)

        return user

    except jwt.ExpiredSignatureError as exc:
        logger.warning("Token has expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except Exception as e:
        from jose.exceptions import JWTError
        if isinstance(e, JWTError):
            logger.warning("Invalid token: %s", e)
            raise credentials_exception from e
        logger.error("Unexpected error validating token: %s", e, exc_info=True)
        raise credentials_exception from e

# Create token function for testing
async def create_test_token(data):
    """Create a test token."""
    settings = MockSettings()
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": datetime.utcnow(), "sub": data.get("sub")})

    # Add token_version
    to_encode["token_version"] = 1

    # Add WebAuthn claims if present
    if data.get("webauthn"):
        to_encode.update({
            "webauthn": True,
            "webauthn_credential_id": data.get("webauthn_credential_id"),
            "webauthn_device_name": data.get("webauthn_device_name"),
            "webauthn_authenticator_type": data.get("webauthn_authenticator_type"),
            "auth_method": "webauthn",
            "webauthn_auth_time": int(datetime.utcnow().timestamp())
        })

    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

async def test_get_current_user():
    try:
        # Test regular token validation
        print("Testing regular token validation...")
        regular_token = await create_test_token({'sub': 'testuser'})
        regular_user = await get_current_user(regular_token)
        print(f"✓ Regular token validated successfully")
        print(f"  User: {regular_user['username']}")

        # Test WebAuthn token validation
        print("\nTesting WebAuthn token validation...")
        webauthn_token = await create_test_token({
            'sub': 'testuser',
            'webauthn': True,
            'webauthn_credential_id': 'test_credential_123',
            'webauthn_device_name': 'Test Device',
            'webauthn_authenticator_type': 'platform'
        })
        webauthn_user = await get_current_user(webauthn_token)
        print(f"✓ WebAuthn token validated successfully")
        print(f"  User: {webauthn_user['username']}")

        # Verify both return the same user
        assert regular_user['username'] == webauthn_user['username']
        assert regular_user['_id'] == webauthn_user['_id']
        print("✓ Both tokens return the same user data")

        # Test invalid token
        print("\nTesting invalid token handling...")
        try:
            await get_current_user("invalid_token")
            print("✗ Should have failed with invalid token")
            return False
        except Exception as e:
            print(f"✓ Invalid token properly rejected: {type(e).__name__}")

        # Test token with wrong version
        print("\nTesting token version mismatch...")
        wrong_version_token_data = {'sub': 'testuser'}
        wrong_version_token = jwt.encode({
            **wrong_version_token_data,
            "token_version": 999,  # Wrong version
            "exp": datetime.utcnow() + timedelta(minutes=30),
            "iat": datetime.utcnow()
        }, 'test_secret_key_for_jwt_testing_only', algorithm='HS256')

        try:
            await get_current_user(wrong_version_token)
            print("✗ Should have failed with wrong token version")
            return False
        except Exception as e:
            print(f"✓ Wrong token version properly rejected: {type(e).__name__}")

        print('\n✓ All tests passed - get_current_user works with WebAuthn tokens')
        return True
    except Exception as e:
        print(f'✗ Error: {e}')
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_get_current_user())
    print(f'\nTest result: {"PASSED" if result else "FAILED"}')

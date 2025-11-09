#!/usr/bin/env python3
"""
Test script to diagnose RAG authentication issues.

This script tests:
1. Token validity and structure
2. Database connection and user lookup
3. RAG endpoint authentication
"""

import asyncio
import sys
from pathlib import Path

import jwt
import requests


def load_token():
    """Load token from rag_token.txt"""
    # Try current directory first, then script directory
    token_file = Path("rag_token.txt")
    if not token_file.exists():
        script_dir = Path(__file__).parent
        token_file = script_dir / "rag_token.txt"
    
    if not token_file.exists():
        print(f"❌ rag_token.txt not found in {token_file.parent}")
        return None
    
    token = token_file.read_text().strip()
    print(f"✅ Loaded token from {token_file}")
    return token


def decode_token(token: str):
    """Decode JWT token without verification"""
    try:
        # Decode without verification to see payload
        payload = jwt.decode(token, options={"verify_signature": False})
        print("\n📋 Token Payload:")
        for key, value in payload.items():
            print(f"   {key}: {value}")
        return payload
    except Exception as e:
        print(f"❌ Failed to decode token: {e}")
        return None


async def test_user_exists():
    """Check if the user exists in the database"""
    try:
        from second_brain_database.database import db_manager
        from bson import ObjectId
        
        # Connect to database
        await db_manager.connect()
        print("\n✅ Connected to MongoDB")
        
        # Get users collection
        users = db_manager.get_collection("users")
        
        # Try to find rag_test_user
        user = await users.find_one({"username": "rag_test_user"})
        
        if user:
            print(f"\n✅ User found in database:")
            print(f"   ID: {user['_id']}")
            print(f"   Username: {user['username']}")
            print(f"   Email: {user.get('email', 'N/A')}")
            print(f"   Active: {user.get('is_active', True)}")
            print(f"   Verified: {user.get('is_verified', False)}")
            return True
        else:
            print("\n❌ User 'rag_test_user' not found in database")
            
            # List all users
            all_users = await users.find({}, {"username": 1}).limit(10).to_list(length=10)
            if all_users:
                print("\n📋 Available users:")
                for u in all_users:
                    print(f"   - {u['username']}")
            return False
            
    except Exception as e:
        print(f"\n❌ Database error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_permanent_token(token: str):
    """Test permanent token validation"""
    try:
        from second_brain_database.routes.auth.services.permanent_tokens.validator import validate_permanent_token
        
        print("\n🔍 Testing permanent token validation...")
        user = await validate_permanent_token(token)
        
        if user:
            print("\n✅ Permanent token validation successful:")
            print(f"   User ID: {user.get('_id')}")
            print(f"   Username: {user.get('username')}")
            print(f"   Email: {user.get('email')}")
            print(f"   Token Type: {user.get('token_type')}")
            return True
        else:
            print("\n❌ Permanent token validation failed")
            
            # Try to find the token in database
            from second_brain_database.database import db_manager
            from second_brain_database.routes.auth.services.permanent_tokens.generator import hash_token
            
            token_hash = hash_token(token)
            tokens = db_manager.get_collection("permanent_tokens")
            token_doc = await tokens.find_one({"token_hash": token_hash})
            
            if token_doc:
                print(f"\n⚠️  Token found in database but validation failed:")
                print(f"   User ID: {token_doc.get('user_id')}")
                print(f"   Is Revoked: {token_doc.get('is_revoked', False)}")
                print(f"   Created: {token_doc.get('created_at')}")
                print(f"   Last Used: {token_doc.get('last_used_at')}")
            else:
                print("\n❌ Token not found in permanent_tokens collection")
            
            return False
            
    except Exception as e:
        print(f"\n❌ Permanent token validation error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_api_health():
    """Test API health endpoint (no auth required)"""
    try:
        print("\n🔍 Testing API health endpoint...")
        response = requests.get("http://localhost:8000/rag/health", timeout=5)
        
        if response.status_code == 200:
            print(f"✅ Health check passed: {response.json()}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ API health check error: {e}")
        return False


def test_api_status(token: str):
    """Test RAG status endpoint (requires auth)"""
    try:
        print("\n🔍 Testing RAG status endpoint with authentication...")
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get("http://localhost:8000/rag/status", headers=headers, timeout=10)
        
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print(f"✅ Status endpoint successful")
            data = response.json()
            print(f"   Response: {data}")
            return True
        else:
            print(f"❌ Status endpoint failed")
            print(f"   Response: {response.text[:500]}")
            
            # Try to parse error detail
            try:
                error_data = response.json()
                print(f"\n   Error Detail:")
                import json
                print(f"   {json.dumps(error_data, indent=2)}")
            except:
                pass
            
            return False
    except Exception as e:
        print(f"❌ Status endpoint error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests"""
    print("=" * 60)
    print("RAG Authentication Diagnostic Tool")
    print("=" * 60)
    
    # 1. Load and decode token
    token = load_token()
    if not token:
        return
    
    payload = decode_token(token)
    if not payload:
        return
    
    # 2. Test API health
    test_api_health()
    
    # 3. Test database connection and user
    user_exists = await test_user_exists()
    
    # 4. Test permanent token validation
    if user_exists:
        token_valid = await test_permanent_token(token)
    else:
        print("\n⚠️  Skipping token validation - user doesn't exist")
        token_valid = False
    
    # 5. Test API endpoint with auth
    test_api_status(token)
    
    # Summary
    print("\n" + "=" * 60)
    print("Summary:")
    print("=" * 60)
    print(f"✅ Token loaded: Yes")
    print(f"{'✅' if payload else '❌'} Token decoded: {'Yes' if payload else 'No'}")
    print(f"{'✅' if user_exists else '❌'} User exists in DB: {'Yes' if user_exists else 'No'}")
    print(f"{'✅' if token_valid else '❌'} Token validation: {'Passed' if token_valid else 'Failed'}")
    print("=" * 60)
    
    if not user_exists:
        print("\n💡 Recommendation: Create the rag_test_user account or update token")
    elif not token_valid:
        print("\n💡 Recommendation: Regenerate the permanent token")


if __name__ == "__main__":
    asyncio.run(main())

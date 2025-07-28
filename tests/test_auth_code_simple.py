#!/usr/bin/env python3
"""
Simple test script for OAuth2 authorization code manager.
"""

import sys
import asyncio
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, 'src')

from second_brain_database.routes.oauth2.services.auth_code_manager import AuthorizationCodeManager
from second_brain_database.routes.oauth2.models import PKCEMethod

async def test_auth_code_manager():
    """Test basic authorization code manager functionality."""
    print("Testing OAuth2 Authorization Code Manager...")
    
    manager = AuthorizationCodeManager()
    
    # Test 1: Code generation
    print("\n1. Testing code generation...")
    codes = [manager.generate_authorization_code() for _ in range(5)]
    
    for i, code in enumerate(codes):
        print(f"   Code {i+1}: {code}")
        assert code.startswith("auth_code_"), f"Code should start with 'auth_code_': {code}"
        assert len(code) == 42, f"Code should be 42 characters long: {len(code)}"
        assert code[10:].isalnum(), f"Code suffix should be alphanumeric: {code[10:]}"
    
    # Check uniqueness
    assert len(set(codes)) == len(codes), "All codes should be unique"
    print("   ✓ Code generation working correctly")
    
    # Test 2: Code format validation
    print("\n2. Testing code format...")
    sample_code = codes[0]
    print(f"   Sample code: {sample_code}")
    print(f"   Starts with 'auth_code_': {sample_code.startswith('auth_code_')}")
    print(f"   Length: {len(sample_code)} (expected: 42)")
    print(f"   Alphanumeric suffix: {sample_code[10:].isalnum()}")
    print("   ✓ Code format validation passed")
    
    print("\n✅ All tests passed! Authorization code manager is working correctly.")

if __name__ == "__main__":
    asyncio.run(test_auth_code_manager())
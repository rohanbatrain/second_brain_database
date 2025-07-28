#!/usr/bin/env python3
"""
Simple test script to verify PKCE validator implementation.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from second_brain_database.routes.oauth2.services.pkce_validator import PKCEValidator, PKCEValidationError

def test_basic_functionality():
    """Test basic PKCE functionality."""
    print("Testing PKCE Validator...")
    
    # Test code verifier generation
    print("1. Testing code verifier generation...")
    verifier = PKCEValidator.generate_code_verifier()
    print(f"   Generated verifier length: {len(verifier)}")
    assert len(verifier) == 128
    print("   ✓ Code verifier generation works")
    
    # Test S256 challenge generation
    print("2. Testing S256 challenge generation...")
    challenge_s256 = PKCEValidator.generate_code_challenge(verifier, "S256")
    print(f"   Generated S256 challenge length: {len(challenge_s256)}")
    assert len(challenge_s256) == 43
    print("   ✓ S256 challenge generation works")
    
    # Test plain challenge generation
    print("3. Testing plain challenge generation...")
    challenge_plain = PKCEValidator.generate_code_challenge(verifier, "plain")
    assert challenge_plain == verifier
    print("   ✓ Plain challenge generation works")
    
    # Test S256 validation
    print("4. Testing S256 validation...")
    is_valid_s256 = PKCEValidator.validate_code_challenge(verifier, challenge_s256, "S256")
    assert is_valid_s256 is True
    print("   ✓ S256 validation works")
    
    # Test plain validation
    print("5. Testing plain validation...")
    is_valid_plain = PKCEValidator.validate_code_challenge(verifier, challenge_plain, "plain")
    assert is_valid_plain is True
    print("   ✓ Plain validation works")
    
    # Test invalid validation
    print("6. Testing invalid validation...")
    wrong_verifier = PKCEValidator.generate_code_verifier()
    is_invalid = PKCEValidator.validate_code_challenge(wrong_verifier, challenge_s256, "S256")
    assert is_invalid is False
    print("   ✓ Invalid validation correctly fails")
    
    # Test convenience method
    print("7. Testing convenience method...")
    verifier2, challenge2 = PKCEValidator.generate_code_verifier_and_challenge("S256")
    is_valid_pair = PKCEValidator.validate_code_challenge(verifier2, challenge2, "S256")
    assert is_valid_pair is True
    print("   ✓ Convenience method works")
    
    # Test error handling
    print("8. Testing error handling...")
    try:
        PKCEValidator.generate_code_challenge("short", "S256")
        assert False, "Should have raised PKCEValidationError"
    except PKCEValidationError:
        print("   ✓ Error handling works")
    
    print("\nAll tests passed! ✅")

if __name__ == "__main__":
    test_basic_functionality()
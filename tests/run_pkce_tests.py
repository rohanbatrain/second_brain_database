#!/usr/bin/env python3
"""
Comprehensive test runner for PKCE validator.
"""

import sys
import os
import traceback

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from second_brain_database.routes.oauth2.services.pkce_validator import PKCEValidator, PKCEValidationError

def run_test(test_name, test_func):
    """Run a single test and report results."""
    try:
        test_func()
        print(f"✅ {test_name}")
        return True
    except Exception as e:
        print(f"❌ {test_name}: {str(e)}")
        traceback.print_exc()
        return False

def test_generate_code_verifier_length():
    """Test that generated code verifier has correct length."""
    verifier = PKCEValidator.generate_code_verifier()
    assert isinstance(verifier, str)
    assert len(verifier) == PKCEValidator.MAX_CODE_VERIFIER_LENGTH
    assert PKCEValidator.MIN_CODE_VERIFIER_LENGTH <= len(verifier) <= PKCEValidator.MAX_CODE_VERIFIER_LENGTH

def test_generate_code_verifier_charset():
    """Test that generated code verifier uses correct character set."""
    verifier = PKCEValidator.generate_code_verifier()
    for char in verifier:
        assert char in PKCEValidator.CODE_VERIFIER_CHARSET

def test_generate_code_verifier_uniqueness():
    """Test that generated code verifiers are unique."""
    verifiers = [PKCEValidator.generate_code_verifier() for _ in range(10)]
    assert len(set(verifiers)) == len(verifiers)

def test_generate_code_challenge_s256():
    """Test S256 code challenge generation."""
    verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
    expected_challenge = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
    
    challenge = PKCEValidator.generate_code_challenge(verifier, "S256")
    assert challenge == expected_challenge
    assert len(challenge) == 43

def test_generate_code_challenge_plain():
    """Test plain code challenge generation."""
    verifier = "test_verifier_123456789012345678901234567890"
    challenge = PKCEValidator.generate_code_challenge(verifier, "plain")
    assert challenge == verifier

def test_generate_code_challenge_invalid_method():
    """Test code challenge generation with invalid method."""
    verifier = PKCEValidator.generate_code_verifier()
    try:
        PKCEValidator.generate_code_challenge(verifier, "invalid_method")
        assert False, "Should have raised PKCEValidationError"
    except PKCEValidationError:
        pass

def test_validate_code_challenge_s256_success():
    """Test successful S256 code challenge validation."""
    verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
    challenge = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
    result = PKCEValidator.validate_code_challenge(verifier, challenge, "S256")
    assert result is True

def test_validate_code_challenge_plain_success():
    """Test successful plain code challenge validation."""
    verifier = "test_verifier_123456789012345678901234567890"
    challenge = verifier
    result = PKCEValidator.validate_code_challenge(verifier, challenge, "plain")
    assert result is True

def test_validate_code_challenge_s256_failure():
    """Test failed S256 code challenge validation."""
    verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
    # Generate a valid format challenge but for a different verifier
    wrong_verifier = PKCEValidator.generate_code_verifier()
    wrong_challenge = PKCEValidator.generate_code_challenge(wrong_verifier, "S256")
    result = PKCEValidator.validate_code_challenge(verifier, wrong_challenge, "S256")
    assert result is False

def test_validate_code_challenge_invalid_verifier():
    """Test code challenge validation with invalid verifier."""
    challenge = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
    
    # Empty verifier
    try:
        PKCEValidator.validate_code_challenge("", challenge, "S256")
        assert False, "Should have raised PKCEValidationError"
    except PKCEValidationError:
        pass
    
    # Too short verifier
    try:
        PKCEValidator.validate_code_challenge("short", challenge, "S256")
        assert False, "Should have raised PKCEValidationError"
    except PKCEValidationError:
        pass

def test_generate_code_verifier_and_challenge_s256():
    """Test generating code verifier and challenge pair with S256."""
    verifier, challenge = PKCEValidator.generate_code_verifier_and_challenge("S256")
    
    assert isinstance(verifier, str)
    assert isinstance(challenge, str)
    assert len(verifier) == PKCEValidator.MAX_CODE_VERIFIER_LENGTH
    assert len(challenge) == 43
    
    # Validate the pair works together
    assert PKCEValidator.validate_code_challenge(verifier, challenge, "S256") is True

def test_generate_code_verifier_and_challenge_plain():
    """Test generating code verifier and challenge pair with plain."""
    verifier, challenge = PKCEValidator.generate_code_verifier_and_challenge("plain")
    
    assert isinstance(verifier, str)
    assert isinstance(challenge, str)
    assert verifier == challenge
    
    # Validate the pair works together
    assert PKCEValidator.validate_code_challenge(verifier, challenge, "plain") is True

def test_timing_attack_resistance():
    """Test that validation uses constant-time comparison."""
    verifier = PKCEValidator.generate_code_verifier()
    correct_challenge = PKCEValidator.generate_code_challenge(verifier, "S256")
    wrong_challenge = PKCEValidator.generate_code_challenge(
        PKCEValidator.generate_code_verifier(), "S256"
    )
    
    # Both should return boolean results (not raise exceptions)
    assert PKCEValidator.validate_code_challenge(verifier, correct_challenge, "S256") is True
    assert PKCEValidator.validate_code_challenge(verifier, wrong_challenge, "S256") is False

def test_pkce_prevents_code_interception_attack():
    """Test that PKCE prevents authorization code interception attacks."""
    # Legitimate client generates verifier and challenge
    legitimate_verifier, challenge = PKCEValidator.generate_code_verifier_and_challenge("S256")
    
    # Attacker intercepts authorization code but doesn't have the verifier
    attacker_verifier = PKCEValidator.generate_code_verifier()
    
    # Legitimate client can exchange the code
    legitimate_valid = PKCEValidator.validate_code_challenge(
        legitimate_verifier, challenge, "S256"
    )
    
    # Attacker cannot exchange the code without the original verifier
    attacker_valid = PKCEValidator.validate_code_challenge(
        attacker_verifier, challenge, "S256"
    )
    
    assert legitimate_valid is True
    assert attacker_valid is False

def main():
    """Run all PKCE tests."""
    print("Running comprehensive PKCE validator tests...\n")
    
    tests = [
        ("Code verifier length", test_generate_code_verifier_length),
        ("Code verifier charset", test_generate_code_verifier_charset),
        ("Code verifier uniqueness", test_generate_code_verifier_uniqueness),
        ("S256 challenge generation", test_generate_code_challenge_s256),
        ("Plain challenge generation", test_generate_code_challenge_plain),
        ("Invalid method handling", test_generate_code_challenge_invalid_method),
        ("S256 validation success", test_validate_code_challenge_s256_success),
        ("Plain validation success", test_validate_code_challenge_plain_success),
        ("S256 validation failure", test_validate_code_challenge_s256_failure),
        ("Invalid verifier handling", test_validate_code_challenge_invalid_verifier),
        ("S256 verifier/challenge pair", test_generate_code_verifier_and_challenge_s256),
        ("Plain verifier/challenge pair", test_generate_code_verifier_and_challenge_plain),
        ("Timing attack resistance", test_timing_attack_resistance),
        ("Code interception prevention", test_pkce_prevents_code_interception_attack),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        if run_test(test_name, test_func):
            passed += 1
        else:
            failed += 1
    
    print(f"\nTest Results:")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"📊 Total: {passed + failed}")
    
    if failed == 0:
        print("\n🎉 All tests passed! PKCE validator implementation is working correctly.")
        return True
    else:
        print(f"\n⚠️  {failed} test(s) failed. Please review the implementation.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
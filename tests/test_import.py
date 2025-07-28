#!/usr/bin/env python3
"""
Test that PKCE validator can be imported correctly from the services module.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_import():
    """Test importing PKCEValidator from services module."""
    print("Testing imports...")
    
    # Test importing from services module
    from second_brain_database.routes.oauth2.services import PKCEValidator, PKCEValidationError
    print("✅ Successfully imported PKCEValidator and PKCEValidationError from services module")
    
    # Test importing directly
    from second_brain_database.routes.oauth2.services.pkce_validator import PKCEValidator as DirectPKCEValidator
    print("✅ Successfully imported PKCEValidator directly from pkce_validator module")
    
    # Verify they are the same class
    assert PKCEValidator is DirectPKCEValidator
    print("✅ Both imports reference the same class")
    
    # Test basic functionality
    verifier, challenge = PKCEValidator.generate_code_verifier_and_challenge("S256")
    is_valid = PKCEValidator.validate_code_challenge(verifier, challenge, "S256")
    assert is_valid is True
    print("✅ Basic functionality works through imported class")
    
    print("\nAll import tests passed! ✅")

if __name__ == "__main__":
    test_import()
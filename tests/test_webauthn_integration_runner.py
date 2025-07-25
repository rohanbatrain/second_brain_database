#!/usr/bin/env python3
"""
WebAuthn Integration Test Runner

Simple test runner that follows existing test patterns and can be easily
integrated into the existing test suite.
"""

import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from tests.test_webauthn_integration_framework import WebAuthnIntegrationTestFramework


def test_webauthn_integration():
    """
    Main integration test function that can be called by other test runners.
    
    Returns:
        bool: True if all tests pass, False otherwise
    """
    print("🚀 Starting WebAuthn Integration Tests")
    print("=" * 60)
    
    try:
        # Run the async test framework
        success = asyncio.run(run_webauthn_tests())
        return success
    except Exception as e:
        print(f"❌ WebAuthn integration test runner failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def run_webauthn_tests():
    """Run WebAuthn integration tests asynchronously."""
    test_framework = WebAuthnIntegrationTestFramework()
    return await test_framework.run_all_tests()


def main():
    """Main entry point for standalone test execution."""
    success = test_webauthn_integration()
    
    if success:
        print("\n🎉 All WebAuthn integration tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some WebAuthn integration tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Test script for WebAuthn browser interface.

This script helps test the complete WebAuthn flow:
1. Login page with password/passkey options
2. WebAuthn setup page for registering passkeys
3. WebAuthn management page for managing passkeys

Usage:
    python test_webauthn_browser.py
"""

import asyncio
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from second_brain_database.main import app
import uvicorn


def main():
    """Run the test server for WebAuthn browser testing."""
    print("🚀 Starting Second Brain Database server for WebAuthn testing...")
    print()
    print("📋 Test URLs:")
    print("  • Login Page:        http://127.0.0.1:8000/auth/login")
    print("  • WebAuthn Setup:    http://127.0.0.1:8000/auth/webauthn/setup")
    print("  • WebAuthn Manage:   http://127.0.0.1:8000/auth/webauthn/manage")
    print()
    print("🔐 Testing Flow:")
    print("  1. Go to http://127.0.0.1:8000/auth/login")
    print("  2. Login with your username/password OR existing passkey")
    print("  3. After login, you'll be redirected to the setup page")
    print("  4. Set up a new passkey using your biometrics or security key")
    print("  5. Test authentication with your new passkey")
    print()
    print("⚠️  Requirements:")
    print("  • Modern browser (Chrome, Firefox, Safari, Edge)")
    print("  • HTTPS or localhost (required for WebAuthn)")
    print("  • Biometric device or hardware security key")
    print()
    print("🛑 Press Ctrl+C to stop the server")
    print()
    
    # Run the server
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        log_level="info",
        reload=False
    )


if __name__ == "__main__":
    main()
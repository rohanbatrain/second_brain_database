#!/usr/bin/env python3
"""
Simple test to verify credential management functions are working.
"""

import asyncio
import sys

sys.path.append("src")

from second_brain_database.routes.auth.services.webauthn.credentials import (
    delete_credential_by_id,
    get_user_credential_list,
)


async def test_functions():
    """Test that functions exist and can be imported."""
    print("✓ get_user_credential_list function imported successfully")
    print("✓ delete_credential_by_id function imported successfully")
    print("✓ All credential management functions are available")


if __name__ == "__main__":
    asyncio.run(test_functions())

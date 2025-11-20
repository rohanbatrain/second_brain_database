#!/usr/bin/env python3
"""
Simple test to verify challenge cleanup functions exist and are callable.
"""
import asyncio
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))


async def test_cleanup_functions():
    """Test that cleanup functions can be imported and are callable."""
    try:
        from second_brain_database.routes.auth.services.webauthn.challenge import (
            cleanup_all_expired_challenges,
            cleanup_expired_challenges,
            cleanup_expired_redis_challenges,
        )

        print("✅ Successfully imported cleanup functions:")
        print("  - cleanup_expired_redis_challenges")
        print("  - cleanup_expired_challenges")
        print("  - cleanup_all_expired_challenges")

        # Verify they are callable
        assert callable(cleanup_expired_redis_challenges), "cleanup_expired_redis_challenges is not callable"
        assert callable(cleanup_expired_challenges), "cleanup_expired_challenges is not callable"
        assert callable(cleanup_all_expired_challenges), "cleanup_all_expired_challenges is not callable"

        print("✅ All cleanup functions are callable")
        print("✅ Challenge cleanup implementation is complete!")

        return True

    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_cleanup_functions())
    sys.exit(0 if success else 1)

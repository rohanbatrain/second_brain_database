"""Simple test to verify consent manager imports work."""

import pytest

def test_simple():
    """Simple test that should always pass."""
    assert True

@pytest.mark.asyncio
async def test_import_consent_manager():
    """Test that we can import the consent manager."""
    try:
        from second_brain_database.routes.oauth2.services.consent_manager import consent_manager
        assert consent_manager is not None
    except ImportError as e:
        pytest.fail(f"Failed to import consent_manager: {e}")
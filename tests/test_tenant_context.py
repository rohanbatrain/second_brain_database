"""
Unit tests for tenant context management.

Tests the thread-safe tenant context using contextvars.
"""

import pytest

from second_brain_database.middleware.tenant_context import (
    clear_tenant_context,
    get_current_tenant_id,
    require_tenant_context,
    set_tenant_context,
)


class TestTenantContext:
    """Test suite for tenant context management."""

    def test_set_and_get_tenant_context(self):
        """Test setting and getting tenant context."""
        tenant_id = "tenant_test123"
        set_tenant_context(tenant_id)
        
        assert get_current_tenant_id() == tenant_id

    def test_clear_tenant_context(self):
        """Test clearing tenant context."""
        set_tenant_context("tenant_test123")
        clear_tenant_context()
        
        assert get_current_tenant_id() is None

    def test_require_tenant_context_with_context(self):
        """Test require_tenant_context when context is set."""
        tenant_id = "tenant_test123"
        set_tenant_context(tenant_id)
        
        assert require_tenant_context() == tenant_id

    def test_require_tenant_context_without_context(self):
        """Test require_tenant_context raises error when context is not set."""
        clear_tenant_context()
        
        with pytest.raises(RuntimeError, match="No tenant context available"):
            require_tenant_context()

    def test_tenant_context_isolation(self):
        """Test that tenant context is isolated between operations."""
        # Set context
        set_tenant_context("tenant_a")
        assert get_current_tenant_id() == "tenant_a"
        
        # Change context
        set_tenant_context("tenant_b")
        assert get_current_tenant_id() == "tenant_b"
        
        # Clear context
        clear_tenant_context()
        assert get_current_tenant_id() is None

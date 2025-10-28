#!/usr/bin/env python3
"""
Basic validation tests for MCP components.

Simple tests that validate MCP components can be imported and basic
functionality works without requiring full dependency setup.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

def test_mcp_context_classes():
    """Test that MCP context classes can be imported and instantiated."""
    try:
        from second_brain_database.integrations.mcp.context import MCPUserContext, MCPRequestContext
        
        # Test MCPUserContext
        user_context = MCPUserContext(
            user_id="test_user",
            username="test",
            permissions=["test:read"]
        )
        
        assert user_context.user_id == "test_user"
        assert user_context.has_permission("test:read") is True
        assert user_context.has_permission("admin") is False
        
        # Test MCPRequestContext  
        request_context = MCPRequestContext(
            request_id="test_request_123",
            tool_name="test_tool",
            operation_type="tool"
        )
        
        assert request_context.request_id == "test_request_123"
        assert request_context.tool_name == "test_tool"
        
        print("✅ MCP context classes work correctly")
        return True
        
    except Exception as e:
        print(f"❌ MCP context classes failed: {e}")
        return False

def test_mcp_exceptions():
    """Test that MCP exception classes can be imported and used."""
    try:
        from second_brain_database.integrations.mcp.exceptions import (
            MCPAuthenticationError,
            MCPAuthorizationError,
            MCPRateLimitError
        )
        
        # Test exception creation
        auth_error = MCPAuthenticationError("Test auth error")
        assert str(auth_error) == "Test auth error"
        
        authz_error = MCPAuthorizationError("Test authz error")
        assert str(authz_error) == "Test authz error"
        
        rate_error = MCPRateLimitError("Test rate limit error")
        assert str(rate_error) == "Test rate limit error"
        
        print("✅ MCP exception classes work correctly")
        return True
        
    except Exception as e:
        print(f"❌ MCP exception classes failed: {e}")
        return False

def test_mcp_security_classes():
    """Test that MCP security classes can be imported."""
    try:
        # Test basic imports without full initialization
        from second_brain_database.integrations.mcp.security import (
            secure_mcp_tool,
            authenticated_tool,
            mcp_context_manager
        )
        
        # Test that decorators are callable
        assert callable(secure_mcp_tool)
        assert callable(authenticated_tool)
        assert callable(mcp_context_manager)
        
        print("✅ MCP security decorators can be imported")
        return True
        
    except Exception as e:
        print(f"❌ MCP security classes failed: {e}")
        return False

def test_mcp_server_manager():
    """Test that MCP server manager can be imported."""
    try:
        from second_brain_database.integrations.mcp.server import MCPServerManager
        
        # Test basic instantiation
        server_manager = MCPServerManager()
        assert server_manager is not None
        assert server_manager.is_initialized is False
        assert server_manager.is_running is False
        
        print("✅ MCP server manager can be imported and instantiated")
        return True
        
    except Exception as e:
        print(f"❌ MCP server manager failed: {e}")
        return False

def test_mcp_file_structure():
    """Test that MCP integration files exist and are structured correctly."""
    mcp_dir = "src/second_brain_database/integrations/mcp"
    
    required_files = [
        "__init__.py",
        "server.py", 
        "security.py",
        "context.py",
        "exceptions.py",
        "config.py"
    ]
    
    missing_files = []
    for file in required_files:
        file_path = os.path.join(mcp_dir, file)
        if not os.path.exists(file_path):
            missing_files.append(file)
    
    if missing_files:
        print(f"❌ Missing MCP files: {missing_files}")
        return False
    
    print("✅ All required MCP files exist")
    return True

def run_all_tests():
    """Run all basic validation tests."""
    print("Running MCP basic validation tests...")
    print("=" * 50)
    
    tests = [
        test_mcp_file_structure,
        test_mcp_exceptions,
        test_mcp_context_classes,
        test_mcp_security_classes,
        test_mcp_server_manager
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")
            failed += 1
    
    print("=" * 50)
    print(f"Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All basic validation tests passed!")
        return True
    else:
        print(f"⚠️  {failed} tests failed")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
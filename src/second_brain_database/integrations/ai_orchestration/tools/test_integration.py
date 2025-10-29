"""
Test MCP Integration for AI Agent Orchestration

Simple test to verify that the MCP tool integration is working correctly
with the AI agent orchestration system.
"""

import asyncio
from typing import Dict, Any

from ....managers.logging_manager import get_logger
from ....integrations.mcp.context import MCPUserContext
from .tool_coordinator import ToolCoordinator

logger = get_logger(prefix="[AI_MCPTest]")

async def test_tool_coordinator_initialization():
    """Test that the tool coordinator initializes correctly."""
    try:
        coordinator = ToolCoordinator()
        
        # Check that tool registry is initialized
        all_tools = coordinator.tool_registry.get_all_tools()
        logger.info("Tool coordinator initialized with %d tools", len(all_tools))
        
        # List some available tools
        for tool_name, tool_info in list(all_tools.items())[:5]:
            logger.info("Available tool: %s (%s)", tool_name, tool_info.get('category', 'unknown'))
        
        return True
        
    except Exception as e:
        logger.error("Tool coordinator initialization test failed: %s", e)
        return False

async def test_mcp_context_creation():
    """Test MCP user context creation."""
    try:
        # Create a test user context
        user_context = MCPUserContext(
            user_id="test_user_123",
            username="test_user",
            email="test@example.com",
            role="user",
            permissions=["family:read", "auth:read", "shop:read"]
        )
        
        logger.info("Created test MCP user context for user: %s", user_context.username)
        logger.info("User permissions: %s", user_context.permissions)
        
        return True
        
    except Exception as e:
        logger.error("MCP context creation test failed: %s", e)
        return False

async def test_tool_access_validation():
    """Test tool access validation."""
    try:
        coordinator = ToolCoordinator()
        
        # Create test user context
        user_context = MCPUserContext(
            user_id="test_user_123",
            username="test_user",
            permissions=["family:read", "auth:read"]
        )
        
        # Test tool access validation
        available_tools = await coordinator.list_available_tools(user_context)
        logger.info("User has access to %d tools", len(available_tools))
        
        # Test specific tool validation
        if available_tools:
            test_tool = available_tools[0]
            tool_name = test_tool["name"]
            has_access = await coordinator.validate_tool_access(tool_name, user_context)
            logger.info("Access to tool '%s': %s", tool_name, has_access)
        
        return True
        
    except Exception as e:
        logger.error("Tool access validation test failed: %s", e)
        return False

async def test_family_tools_integration():
    """Test integration with family tools specifically."""
    try:
        coordinator = ToolCoordinator()
        
        # Create test user context with family permissions
        user_context = MCPUserContext(
            user_id="test_user_123",
            username="test_user",
            permissions=["family:read", "family:create", "family:admin"]
        )
        
        # Test family tool availability
        available_tools = await coordinator.list_available_tools(user_context)
        family_tools = [tool for tool in available_tools if tool.get("category") == "family"]
        
        logger.info("Found %d family tools available", len(family_tools))
        
        # List some family tools
        for tool in family_tools[:3]:
            logger.info("Family tool: %s - %s", tool["name"], tool.get("description", "No description"))
        
        # Test specific family tool validation
        if family_tools:
            test_tool_name = family_tools[0]["name"]
            has_access = await coordinator.validate_tool_access(test_tool_name, user_context)
            logger.info("Access to family tool '%s': %s", test_tool_name, has_access)
        
        return True
        
    except Exception as e:
        logger.error("Family tools integration test failed: %s", e)
        return False

async def test_mcp_resource_loading():
    """Test MCP resource loading functionality."""
    try:
        coordinator = ToolCoordinator()
        
        # Create test user context
        user_context = MCPUserContext(
            user_id="test_user_123",
            username="test_user",
            permissions=["family:read", "user:read"]
        )
        
        # Test resource loading (this will likely fail but should handle gracefully)
        test_resources = [
            "family://test_family_id/info",
            "user://test_user_123/profile",
            "shop://catalog"
        ]
        
        for resource_uri in test_resources:
            try:
                result = await coordinator.load_resource(resource_uri, user_context)
                logger.info("Successfully loaded resource: %s", resource_uri)
            except Exception as e:
                logger.info("Resource loading failed (expected): %s - %s", resource_uri, str(e))
        
        return True
        
    except Exception as e:
        logger.error("MCP resource loading test failed: %s", e)
        return False

async def run_integration_tests():
    """Run all integration tests."""
    logger.info("Starting MCP integration tests...")
    
    tests = [
        ("Tool Coordinator Initialization", test_tool_coordinator_initialization),
        ("MCP Context Creation", test_mcp_context_creation),
        ("Tool Access Validation", test_tool_access_validation),
        ("Family Tools Integration", test_family_tools_integration),
        ("MCP Resource Loading", test_mcp_resource_loading)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        logger.info("Running test: %s", test_name)
        try:
            result = await test_func()
            results[test_name] = result
            status = "PASSED" if result else "FAILED"
            logger.info("Test %s: %s", test_name, status)
        except Exception as e:
            results[test_name] = False
            logger.error("Test %s FAILED with exception: %s", test_name, e)
    
    # Summary
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    logger.info("Integration test results: %d/%d tests passed", passed, total)
    
    if passed == total:
        logger.info("All MCP integration tests PASSED!")
    else:
        logger.warning("Some MCP integration tests FAILED!")
    
    return results

if __name__ == "__main__":
    # Run tests if executed directly
    asyncio.run(run_integration_tests())
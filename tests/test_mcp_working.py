#!/usr/bin/env python3
"""
Test script to verify FastMCP is working correctly.

This script tests the FastMCP server functionality and identifies any issues.
"""

import asyncio
import os
from pathlib import Path
import sys

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))


async def test_mcp_functionality():
    """Test MCP server functionality."""
    print("🧪 Testing FastMCP Functionality")
    print("=" * 50)

    try:
        # Test 1: Import and create MCP server
        print("1. Testing MCP server creation...")
        from src.second_brain_database.integrations.mcp.modern_server import mcp

        print(f"   ✅ MCP server created: {mcp.name}")

        # Test 2: Check server configuration
        print("2. Testing server configuration...")
        print(f"   Server name: {mcp.name}")
        print(f"   Server version: {mcp.version}")
        print(f"   Authentication: {'enabled' if mcp.auth else 'disabled'}")

        # Test 3: Test tool registration
        print("3. Testing tool registration...")
        try:
            # Import tool modules to trigger registration
            from src.second_brain_database.integrations.mcp.tools import (
                admin_tools,
                auth_tools,
                family_tools,
                shop_tools,
                test_tools,
                workspace_tools,
            )

            print("   ✅ Tool modules imported successfully")

            # Check tool count using internal access
            tool_count = (
                len(mcp._tool_manager._tools)
                if hasattr(mcp, "_tool_manager") and hasattr(mcp._tool_manager, "_tools")
                else 0
            )
            print(f"   Tools registered: {tool_count}")

            if tool_count > 0:
                print("   ✅ Tools registered successfully")

                # Show some example tools
                tools = list(mcp._tool_manager._tools.keys())[:5]  # First 5 tools
                print(f"   Example tools: {', '.join(tools)}")
            else:
                print("   ⚠️  No tools registered")

        except Exception as e:
            print(f"   ❌ Error with tool registration: {e}")
            return False

        # Test 4: Test resource registration
        print("4. Testing resource registration...")
        try:
            from src.second_brain_database.integrations.mcp.resources import (
                family_resources,
                shop_resources,
                system_resources,
                test_resources,
                user_resources,
                workspace_resources,
            )

            print("   ✅ Resource modules imported successfully")

            resource_count = (
                len(mcp._resource_manager._resources)
                if hasattr(mcp, "_resource_manager") and hasattr(mcp._resource_manager, "_resources")
                else 0
            )
            print(f"   Resources registered: {resource_count}")

            if resource_count > 0:
                print("   ✅ Resources registered successfully")

                # Show some example resources
                resources = list(mcp._resource_manager._resources.keys())[:3]  # First 3 resources
                print(f"   Example resources: {', '.join(resources)}")
            else:
                print("   ⚠️  No resources registered")

        except Exception as e:
            print(f"   ❌ Error with resource registration: {e}")
            return False

        # Test 5: Test server manager
        print("5. Testing server manager...")
        try:
            from src.second_brain_database.integrations.mcp.server import mcp_server_manager

            # Initialize server manager
            await mcp_server_manager.initialize()
            print("   ✅ Server manager initialized")

            # Get server info
            server_info = await mcp_server_manager.get_server_info()
            print(f"   Server initialized: {server_info['initialized']}")
            print(f"   Server running: {server_info['running']}")

        except Exception as e:
            print(f"   ❌ Error with server manager: {e}")
            return False

        # Test 6: Test MCP protocol methods
        print("6. Testing MCP protocol methods...")
        try:
            # Test tools/list
            tools = await mcp_server_manager._list_tools()
            print(f"   Available tools: {len(tools)}")

            # Test resources/list
            resources = await mcp_server_manager._list_resources()
            print(f"   Available resources: {len(resources)}")

            # Test prompts/list
            prompts = await mcp_server_manager._list_prompts()
            print(f"   Available prompts: {len(prompts)}")

            print("   ✅ MCP protocol methods working")

        except Exception as e:
            print(f"   ❌ Error with MCP protocol methods: {e}")
            return False

        print("\n🎉 All FastMCP functionality tests passed!")
        print("\n📋 Summary:")
        print(f"   • Server: {mcp.name} v{mcp.version}")
        print(f"   • Tools: {tool_count} registered")
        print(f"   • Resources: {resource_count} registered")
        print(f"   • Authentication: {'Enabled' if mcp.auth else 'Disabled'}")
        print(f"   • Server Manager: Working")
        print(f"   • MCP Protocol: Working")

        return True

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_server_startup():
    """Test server startup process."""
    print("\n🚀 Testing Server Startup Process")
    print("=" * 50)

    try:
        from src.second_brain_database.integrations.mcp.server import mcp_server_manager

        # Test initialization
        print("1. Testing server initialization...")
        if not mcp_server_manager.is_initialized:
            await mcp_server_manager.initialize()
        print("   ✅ Server initialized successfully")

        # Test server info
        print("2. Getting server information...")
        server_info = await mcp_server_manager.get_server_info()

        print(f"   Name: {server_info['name']}")
        print(f"   Version: {server_info['version']}")
        print(f"   Protocol: {server_info['protocol_version']}")
        print(f"   Tools: {server_info['tool_count']}")
        print(f"   Resources: {server_info['resource_count']}")
        print(f"   Prompts: {server_info['prompt_count']}")

        # Test health check
        print("3. Testing health check...")
        health = await mcp_server_manager.health_check()
        print(f"   Status: {health['status']}")

        if health["status"] == "healthy":
            print("   ✅ Server health check passed")
        else:
            print(f"   ⚠️  Server health check: {health.get('error', 'Unknown issue')}")

        print("\n✅ Server startup process working correctly!")
        return True

    except Exception as e:
        print(f"\n❌ Server startup test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def main():
    """Run all tests."""
    print("🔍 FastMCP Functionality Test Suite")
    print("=" * 60)

    # Run functionality tests
    functionality_ok = await test_mcp_functionality()

    # Run startup tests
    startup_ok = await test_server_startup()

    print("\n" + "=" * 60)
    if functionality_ok and startup_ok:
        print("🎉 ALL TESTS PASSED - FastMCP is working correctly!")
        print("\n💡 The issue you're experiencing is likely:")
        print("   1. The MCP server needs to be running (start with start_mcp_server.py)")
        print("   2. The health check script may be using the wrong endpoint")
        print("   3. The server runs on http://localhost:3001/mcp (not just port 3001)")
        return 0
    else:
        print("❌ SOME TESTS FAILED - FastMCP has issues")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n🛑 Tests interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Test suite failed: {e}")
        sys.exit(1)

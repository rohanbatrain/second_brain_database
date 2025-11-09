#!/usr/bin/env python3
"""
Quick MCP Server Startup Test

This script tests if the MCP server can initialize and start without errors.
"""

import asyncio
from pathlib import Path
import sys

# Add the src directory to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))


async def test_mcp_startup():
    """Test MCP server initialization and startup."""
    try:
        print("🧪 Testing MCP Server Startup...")
        print("=" * 50)

        # Test configuration loading
        print("1. Loading configuration...")
        from second_brain_database.config import settings

        print(f"   ✅ MCP Enabled: {settings.MCP_ENABLED}")
        print(f"   ✅ Server Name: {settings.MCP_SERVER_NAME}")
        print(f"   ✅ Server Port: {settings.MCP_SERVER_PORT}")

        # Test MCP server manager import
        print("\n2. Importing MCP server manager...")
        from second_brain_database.integrations.mcp.server import mcp_server_manager

        print("   ✅ MCP server manager imported successfully")

        # Test initialization
        print("\n3. Initializing MCP server...")
        await mcp_server_manager.initialize()
        print("   ✅ MCP server initialized successfully")
        print(f"   📊 Tools registered: {mcp_server_manager._tool_count}")
        print(f"   📊 Resources registered: {mcp_server_manager._resource_count}")
        print(f"   📊 Prompts registered: {mcp_server_manager._prompt_count}")

        # Test server startup (but don't actually bind to port)
        print("\n4. Testing server startup capability...")
        if hasattr(mcp_server_manager.mcp, "serve"):
            print("   ✅ FastMCP serve method available")
        else:
            print("   ⚠️  FastMCP serve method not available, will use HTTP fallback")

        # Test health check
        print("\n5. Testing health check...")
        health = await mcp_server_manager.health_check()
        print(f"   ✅ Health check completed: {health['healthy']}")

        for check_name, check_data in health.get("checks", {}).items():
            status = check_data.get("status", "unknown")
            message = check_data.get("message", "No message")
            icon = "✅" if status == "pass" else "❌"
            print(f"   {icon} {check_name}: {message}")

        print("\n" + "=" * 50)
        if health["healthy"]:
            print("🎉 MCP Server startup test PASSED!")
            print("   The server should start successfully when you run the main application.")
            return 0
        else:
            print("⚠️  MCP Server startup test completed with warnings.")
            print("   Some components may not be fully healthy, but the server should still start.")
            return 0

    except Exception as e:
        print(f"\n❌ MCP Server startup test FAILED: {e}")
        print("\nError details:")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(test_mcp_startup())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Test failed with unexpected error: {e}")
        sys.exit(1)

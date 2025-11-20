#!/usr/bin/env python3
"""
Modern FastMCP 2.x Health Check

This script validates the modern FastMCP 2.x server implementation
using STDIO transport (the recommended approach for local AI clients).
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

async def check_modern_mcp_health():
    """Check modern FastMCP 2.x server health."""
    print("🔍 Modern FastMCP 2.x Health Check")
    print("=" * 50)

    try:
        # Import the modern server
        from second_brain_database.integrations.mcp.modern_server import mcp

        print("✅ Modern FastMCP 2.x server imported successfully")
        print(f"   Server Name: {mcp.name}")
        print(f"   Server Version: {mcp.version}")

        # Check if tools are registered
        try:
            tools = mcp._tool_manager._tools if hasattr(mcp, '_tool_manager') else {}
            resources = mcp._resource_manager._resources if hasattr(mcp, '_resource_manager') else {}
            prompts = mcp._prompt_manager._prompts if hasattr(mcp, '_prompt_manager') else {}

            print(f"   Tools: {len(tools)}")
            print(f"   Resources: {len(resources)}")
            print(f"   Prompts: {len(prompts)}")

            if len(tools) > 0:
                print("✅ MCP tools are registered")
            else:
                print("⚠️  No MCP tools found")

        except Exception as e:
            print(f"⚠️  Could not count components: {e}")

        print("\n🚀 Server Status: Ready for STDIO transport")
        print("   Start with: python start_mcp_server.py --transport stdio")
        print("   For HTTP (remote): python start_mcp_server.py --transport http --port 8001")

        return True

    except ImportError as e:
        print(f"❌ Failed to import modern MCP server: {e}")
        return False
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False

async def main():
    """Main health check function."""
    success = await check_modern_mcp_health()

    print("\n" + "=" * 50)
    if success:
        print("🎉 Modern FastMCP 2.x is healthy and ready!")
        print("\n💡 Key Points:")
        print("   • Uses STDIO transport (no port needed)")
        print("   • HTTP transport only for remote connections")
        print("   • No websockets-sansio dependency required")
        return 0
    else:
        print("❌ Health check failed")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

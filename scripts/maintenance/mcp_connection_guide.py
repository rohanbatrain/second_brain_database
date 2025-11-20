#!/usr/bin/env python3
"""
MCP Connection Guide

This script provides information on how to connect to your Second Brain Database
MCP server from various MCP clients.
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from second_brain_database.config import settings


def print_connection_info():
    """Print MCP connection information."""
    print("🔗 Second Brain Database MCP Connection Guide")
    print("=" * 60)

    print("\n📋 Server Information:")
    print(f"   Server Name: {settings.MCP_SERVER_NAME}")
    print(f"   Version: {settings.MCP_SERVER_VERSION}")
    print(f"   Host: {settings.MCP_SERVER_HOST}")
    print(f"   Port: {settings.MCP_SERVER_PORT}")

    print(f"\n🌐 Connection URLs:")
    print(f"   HTTP: http://{settings.MCP_SERVER_HOST}:{settings.MCP_SERVER_PORT}")
    print(f"   WebSocket: ws://{settings.MCP_SERVER_HOST}:{settings.MCP_SERVER_PORT}")

    print(f"\n🔧 Configuration Status:")
    print(f"   MCP Enabled: {settings.MCP_ENABLED}")
    print(f"   Security Enabled: {settings.MCP_SECURITY_ENABLED}")
    print(f"   Tools Enabled: {settings.MCP_TOOLS_ENABLED}")
    print(f"   Resources Enabled: {settings.MCP_RESOURCES_ENABLED}")
    print(f"   Prompts Enabled: {settings.MCP_PROMPTS_ENABLED}")

    print(f"\n🛡️ Security Settings:")
    print(f"   Authentication Required: {settings.MCP_REQUIRE_AUTH}")
    print(f"   Rate Limiting: {settings.MCP_RATE_LIMIT_ENABLED}")
    print(f"   Audit Logging: {settings.MCP_AUDIT_ENABLED}")

    print(f"\n⚡ Performance Settings:")
    print(f"   Max Concurrent Tools: {settings.MCP_MAX_CONCURRENT_TOOLS}")
    print(f"   Request Timeout: {settings.MCP_REQUEST_TIMEOUT}s")
    print(f"   Tool Execution Timeout: {settings.MCP_TOOL_EXECUTION_TIMEOUT}s")


def print_client_configurations():
    """Print client configuration examples."""
    print("\n🖥️ Client Configuration Examples")
    print("=" * 60)

    print("\n1️⃣ Claude Desktop (MCP Client)")
    print("-" * 30)
    print("Add to your Claude Desktop configuration:")
    print(f"""
{{
  "mcpServers": {{
    "second-brain-database": {{
      "command": "python",
      "args": [
        "{Path.cwd()}/start_mcp_server.py"
      ],
      "env": {{
        "PYTHONPATH": "{Path.cwd()}/src"
      }}
    }}
  }}
}}
""")

    print("\n2️⃣ Direct HTTP Connection")
    print("-" * 30)
    print("For direct HTTP MCP clients:")
    print(f"   URL: http://{settings.MCP_SERVER_HOST}:{settings.MCP_SERVER_PORT}/mcp")
    print("   Method: POST")
    print("   Content-Type: application/json")

    print("\n3️⃣ WebSocket Connection")
    print("-" * 30)
    print("For WebSocket MCP clients:")
    print(f"   URL: ws://{settings.MCP_SERVER_HOST}:{settings.MCP_SERVER_PORT}/mcp/ws")
    print("   Protocol: MCP over WebSocket")

    print("\n4️⃣ Python MCP Client")
    print("-" * 30)
    print("Example Python client code:")
    print(f"""
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    server_params = StdioServerParameters(
        command="python",
        args=["{Path.cwd()}/start_mcp_server.py"],
        env={{"PYTHONPATH": "{Path.cwd()}/src"}}
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize the connection
            await session.initialize()

            # List available tools
            tools = await session.list_tools()
            print("Available tools:", [tool.name for tool in tools])

            # Call a tool
            result = await session.call_tool("test_echo", {{"message": "Hello!"}})
            print("Result:", result)

if __name__ == "__main__":
    asyncio.run(main())
""")


def print_available_tools():
    """Print information about available MCP tools."""
    print("\n🛠️ Available MCP Tools")
    print("=" * 60)

    tools = [
        {
            "name": "test_echo",
            "description": "Simple echo tool for testing",
            "category": "Testing"
        },
        {
            "name": "auth_tools",
            "description": "Authentication and user management tools",
            "category": "Authentication"
        },
        {
            "name": "family_tools",
            "description": "Family management and relationship tools",
            "category": "Family Management"
        },
        {
            "name": "profile_tools",
            "description": "User profile management tools",
            "category": "Profile Management"
        },
        {
            "name": "shop_tools",
            "description": "Digital asset shop and commerce tools",
            "category": "Commerce"
        }
    ]

    for tool in tools:
        print(f"\n📦 {tool['name']}")
        print(f"   Category: {tool['category']}")
        print(f"   Description: {tool['description']}")


def print_startup_instructions():
    """Print instructions for starting the MCP server."""
    print("\n🚀 Starting the MCP Server")
    print("=" * 60)

    print("\n1️⃣ Prerequisites:")
    print("   ✅ MongoDB running on localhost:27017")
    print("   ✅ Redis running on localhost:6379")
    print("   ✅ Configuration file (.sbd) present")
    print("   ✅ Python environment activated")

    print("\n2️⃣ Start the Server:")
    print("   Command: python start_mcp_server.py")
    print("   Alternative: python -m uvicorn src.second_brain_database.main:app --host 0.0.0.0 --port 8000")

    print("\n3️⃣ Verify Connection:")
    print("   Health Check: python check_mcp_health.py")
    print(f"   Direct Test: curl http://{settings.MCP_SERVER_HOST}:{settings.PORT}/health")

    print("\n4️⃣ Connect MCP Client:")
    print("   Use the configuration examples above")
    print("   The MCP endpoint will be available at /mcp")


def main():
    """Main function."""
    print_connection_info()
    print_client_configurations()
    print_available_tools()
    print_startup_instructions()

    print("\n" + "=" * 60)
    print("🎉 Your Second Brain Database MCP server is ready!")
    print("=" * 60)

    print("\n💡 Quick Start:")
    print("   1. Start the server: python start_mcp_server.py")
    print("   2. Connect your MCP client to the server")
    print("   3. Use the available tools for Second Brain operations")

    print("\n📚 Documentation:")
    print("   - MCP Tools: docs/mcp/tools/")
    print("   - Security: docs/mcp/security.md")
    print("   - Deployment: docs/mcp/deployment.md")
    print("   - Troubleshooting: docs/mcp/troubleshooting.md")


if __name__ == "__main__":
    main()

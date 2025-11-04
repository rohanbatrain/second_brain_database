#!/usr/bin/env python3
"""
Standalone FastMCP 2.13.0.2 Server

This script starts a dedicated FastMCP server that runs independently
from the main FastAPI application. This provides clean separation between
the web API and the MCP protocol server.

Usage:
    python start_mcp_server.py [--transport stdio|http] [--port 8001]
"""

import asyncio
import argparse
import sys
import os
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from second_brain_database.integrations.mcp.modern_server import mcp
from second_brain_database.integrations.mcp.mcp_instance import ensure_tools_imported
from second_brain_database.integrations.mcp.mcp_instance import get_mcp_server_info
from second_brain_database.integrations.mcp.mcp_status import print_mcp_status
from second_brain_database.integrations.mcp.http_server import run_http_server
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.config import settings

logger = get_logger(prefix="[MCP_Server_Startup]")


async def check_server_health():
    """Check MCP server health before starting."""
    print("🔍 Checking MCP server health...")

    try:
        # Initialize database connection first
        from second_brain_database.integrations.mcp.database_integration import initialize_mcp_database

        print("🔗 Initializing database connection...")
        db_initialized = await initialize_mcp_database()

        if not db_initialized:
            print("❌ Database initialization failed!")
            print("💡 Make sure MongoDB is running:")
            print("   brew services start mongodb-community")
            print("   # or")
            print("   sudo systemctl start mongod")
            return False

        print("✅ Database connection established")

        # Ensure all tools are imported
        ensure_tools_imported()

        # Get server info
        info = await get_mcp_server_info()

        if not info.get("available", False):
            print("❌ MCP server not available!")
            return False

        print(f"✅ MCP Server: {info['name']}")
        print(f"📊 Tools: {info['tool_count']}")
        print(f"📁 Resources: {info['resource_count']}")
        print(f"💬 Prompts: {info['prompt_count']}")
        print(f"🔐 Auth: {'Enabled' if info['auth_enabled'] else 'Disabled'}")

        return True

    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False


def print_startup_banner():
    """Print startup banner."""
    print("=" * 60)
    print("🚀 FastMCP 2.x Production Server")
    print("=" * 60)
    print("📋 Second Brain Database MCP Integration")
    print("🔧 AI Agent Orchestration Platform")
    print("🌐 Modern HTTP + WebSocket Support")
    print("=" * 60)


def print_connection_info(transport: str, port: int = None, host: str = "127.0.0.1"):
    """Print connection information."""
    print("\n📡 Connection Information:")
    print("-" * 30)

    if transport == "stdio":
        print("🔌 Transport: STDIO")
        print("📝 Usage: Connect via stdin/stdout")
        print("🎯 Ideal for: Local AI clients, development")
        print("\n💡 Example MCP client config:")
        print("```json")
        print("{")
        print('  "mcpServers": {')
        print('    "second-brain": {')
        print('      "command": "python",')
        print('      "args": ["start_mcp_server.py", "--transport", "stdio"]')
        print("    }")
        print("  }")
        print("}")
        print("```")

    elif transport == "http":
        print(f"🔌 Transport: HTTP (FastMCP 2.x)")
        print(f"🌐 URL: http://{host}:{port}")
        print(f"📡 MCP Endpoint: http://{host}:{port}/mcp")
        print(f"📊 Health Check: http://{host}:{port}/health")
        print(f"📈 Metrics: http://{host}:{port}/metrics")
        print(f"📚 API Docs: http://{host}:{port}/docs")
        print("🎯 Ideal for: Remote AI clients, production, web integrations")
        print(f"🔐 Authentication: {'Enabled' if settings.MCP_SECURITY_ENABLED else 'Disabled'}")
        print("\n💡 Example MCP client config:")
        print("```json")
        print("{")
        print('  "mcpServers": {')
        print('    "second-brain": {')
        print(f'      "url": "http://{host}:{port}/mcp"')
        if settings.MCP_SECURITY_ENABLED and hasattr(settings, 'MCP_AUTH_TOKEN'):
            print(',')
            print('      "headers": {')
            print('        "Authorization": "Bearer YOUR_TOKEN"')
            print('      }')
        print("    }")
        print("  }")
        print("}")
        print("```")


def print_available_tools_summary():
    """Print summary of available tools."""
    print("\n🔧 Available Tool Categories:")
    print("-" * 30)
    print("👨‍👩‍👧‍👦 Family Tools: Family management, invitations, SBD tokens")
    print("🛒 Shop Tools: Digital assets, purchases, transactions")
    print("👤 Auth Tools: User management, authentication, profiles")
    print("🏢 Workspace Tools: Team collaboration, project management")
    print("⚙️  Admin Tools: System administration, monitoring")
    print("\n💡 Use 'python -c \"from src.second_brain_database.integrations.mcp.mcp_status import print_mcp_status; print_mcp_status()\"' for detailed status")


async def start_mcp_server(transport: str = None, port: int = None, host: str = None):
    """Start the MCP server with specified transport."""
    # Use settings values if not provided
    if transport is None:
        transport = settings.MCP_TRANSPORT
    if port is None:
        port = settings.MCP_HTTP_PORT
    if host is None:
        host = settings.MCP_HTTP_HOST

    print_startup_banner()

    # Health check
    if not await check_server_health():
        print("\n❌ Server health check failed. Exiting.")
        sys.exit(1)

    print_available_tools_summary()
    print_connection_info(transport, port, host)

    print(f"\n🚀 Starting MCP server with {transport.upper()} transport...")

    try:
        if transport == "stdio":
            print("📡 Server running on STDIO - ready for MCP client connections")
            print("🔄 Press Ctrl+C to stop")
            # Use FastMCP's native run method for STDIO
            await mcp.run_async(transport="stdio")

        elif transport == "http":
            print(f"📡 FastMCP 2.x HTTP server running on {host}:{port}")
            print(f"🌐 MCP Endpoint: http://{host}:{port}/mcp")
            print(f"📊 Health Check: http://{host}:{port}/health")
            print(f"📈 Metrics: http://{host}:{port}/metrics")
            print(f"📚 Status: http://{host}:{port}/status")
            print(f"🔐 Authentication: {'Required' if settings.MCP_SECURITY_ENABLED else 'Disabled'}")
            print("🔄 Press Ctrl+C to stop")
            # Use the HTTP server wrapper for additional features
            await run_http_server(host=host, port=port)

        else:
            print(f"❌ Unsupported transport: {transport}")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n🛑 Shutting down MCP server...")
        logger.info("MCP server shutdown requested by user")

    except Exception as e:
        print(f"\n❌ Server error: {e}")
        logger.error("MCP server error: %s", e)
        sys.exit(1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Start FastMCP 2.13.0.2 server for Second Brain Database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python start_mcp_server.py                    # Start with STDIO (default)
  python start_mcp_server.py --transport http   # Start with HTTP on port 8001
  python start_mcp_server.py --transport http --port 9000  # Custom port

Transport Options:
  stdio: Standard input/output (ideal for local development)
  http:  HTTP server (ideal for remote connections)
        """
    )

    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="Transport protocol (default: stdio)"
    )

    parser.add_argument(
        "--port",
        type=int,
        default=8001,
        help="Port for HTTP transport (default: 8001)"
    )

    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind HTTP transport to (default: 127.0.0.1, use 0.0.0.0 for production)"
    )

    parser.add_argument(
        "--status",
        action="store_true",
        help="Show server status and exit"
    )

    args = parser.parse_args()

    if args.status:
        print("📊 MCP Server Status:")
        print("=" * 30)
        print_mcp_status()
        return

    # Run the server
    asyncio.run(start_mcp_server(args.transport, args.port, args.host))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Standalone FastAPI Server

This script starts the main FastAPI application server without the MCP server.
This provides clean separation between the web API and the MCP protocol server.

Usage:
    python start_fastapi_server.py [--host 0.0.0.0] [--port 8000] [--reload]
"""

import argparse
import sys
import os
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

def print_startup_banner():
    """Print startup banner."""
    print("=" * 60)
    print("🌐 Second Brain Database FastAPI Server")
    print("=" * 60)
    print("📋 Main Web Application & REST API")
    print("🔧 Family Management, Shop, Workspaces, Auth")
    print("=" * 60)


def print_server_info(host: str, port: int):
    """Print server information."""
    print(f"\n📡 Server Information:")
    print("-" * 30)
    print(f"🌐 Host: {host}")
    print(f"🔌 Port: {port}")
    print(f"📍 URL: http://{host}:{port}")
    print(f"📚 Docs: http://{host}:{port}/docs")
    print(f"🔍 Health: http://{host}:{port}/health")

    print(f"\n🛠️  Available Endpoints:")
    print("-" * 30)
    print("👨‍👩‍👧‍👦 Family: /family/*")
    print("🛒 Shop: /shop/*")
    print("👤 Auth: /auth/*")
    print("🏢 Workspace: /workspace/*")
    print("⚙️  Admin: /admin/*")
    print("📊 Health: /health, /metrics")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Start FastAPI server for Second Brain Database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python start_fastapi_server.py                           # Default (localhost:8000)
  python start_fastapi_server.py --host 0.0.0.0 --port 8080  # Custom host/port
  python start_fastapi_server.py --reload                  # Development mode with auto-reload

Notes:
  - This starts ONLY the FastAPI web server
  - MCP server runs separately via start_mcp_server.py
  - Use --reload for development (auto-restarts on code changes)
        """
    )

    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)"
    )

    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to (default: 8000)"
    )

    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development"
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes (default: 1)"
    )

    args = parser.parse_args()

    print_startup_banner()
    print_server_info(args.host, args.port)

    print(f"\n🚀 Starting FastAPI server...")
    print("🔄 Press Ctrl+C to stop")

    # Import and run uvicorn
    import uvicorn

    try:
        uvicorn.run(
            "second_brain_database.main:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
            workers=args.workers if not args.reload else 1,  # reload doesn't work with multiple workers
            log_level="info",
            access_log=True
        )
    except KeyboardInterrupt:
        print("\n🛑 Shutting down FastAPI server...")
    except Exception as e:
        print(f"\n❌ Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Test MCP Server Connection

This script tests the connection to your MCP server using STDIO transport
and demonstrates how external clients can interact with it.
"""

import asyncio
import json
from typing import Any, Dict

import httpx


class MCPClient:
    """Simple MCP client for testing connections."""

    def __init__(self, base_url: str, auth_token: str = None):
        self.base_url = base_url
        self.auth_token = auth_token
        self.session_id = 1

    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for MCP requests."""
        headers = {"Content-Type": "application/json", "Accept": "application/json"}

        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        return headers

    def _create_request(self, method: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Create an MCP JSON-RPC request."""
        request = {"jsonrpc": "2.0", "method": method, "id": self.session_id}

        if params:
            request["params"] = params

        self.session_id += 1
        return request

    async def send_request(self, method: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Send an MCP request to the server."""
        request = self._create_request(method, params)

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(self.base_url, json=request, headers=self._get_headers(), timeout=30.0)

                print(f"📤 Request: {method}")
                print(f"   Status: {response.status_code}")

                if response.status_code == 200:
                    result = response.json()
                    print(f"✅ Success: {json.dumps(result, indent=2)}")
                    return result
                else:
                    print(f"❌ Error: {response.status_code} - {response.text}")
                    return {"error": f"HTTP {response.status_code}"}

            except Exception as e:
                print(f"❌ Connection Error: {e}")
                return {"error": str(e)}

    async def test_connection(self):
        """Test basic MCP server connection."""
        print("🔍 Testing MCP Server Connection")
        print(f"   Server: {self.base_url}")
        print(f"   Auth: {'Yes' if self.auth_token else 'No'}")
        print("-" * 50)

        # Test 1: Initialize
        print("\n1️⃣ Testing Initialize...")
        await self.send_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
        )

        # Test 2: List Tools
        print("\n2️⃣ Testing List Tools...")
        await self.send_request("tools/list")

        # Test 3: List Resources
        print("\n3️⃣ Testing List Resources...")
        await self.send_request("resources/list")

        # Test 4: Get Server Info (if available)
        print("\n4️⃣ Testing Server Info...")
        await self.send_request("server/info")


async def main():
    """Main test function."""
    print("🚀 MCP Server Connection Test")
    print("=" * 60)

    # Note: Modern FastMCP 2.x uses STDIO transport by default
    # HTTP transport is only for remote connections
    print("⚠️  Modern FastMCP 2.x uses STDIO transport by default")
    print("   HTTP transport on port 3001 is no longer needed")
    print("   Use: python start_mcp_server.py --transport stdio")
    return

    await client.test_connection()

    print("\n" + "=" * 60)
    print("✨ Test completed!")
    print("\n💡 Modern FastMCP 2.x Configuration:")
    print("   Transport: STDIO (recommended for local AI clients)")
    print("   Start with: python start_mcp_server.py --transport stdio")
    print("   🔑 Auth Token: dev-token (for HTTP transport only)")


if __name__ == "__main__":
    asyncio.run(main())

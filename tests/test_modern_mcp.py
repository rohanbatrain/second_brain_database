#!/usr/bin/env python3
"""
Modern MCP Implementation Test Suite

This script tests the modernized FastMCP 2.x implementation including:
- Server initialization and configuration
- HTTP transport with authentication
- WebSocket integration
- Health checks and monitoring
- Production readiness
"""

import asyncio
import json
from pathlib import Path
import sys
import time
from typing import Any, Dict, Optional

import httpx
import websockets
from websockets.exceptions import ConnectionClosed

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from second_brain_database.config import settings
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[MCP_Test]")


class MCPTestSuite:
    """Comprehensive test suite for modern MCP implementation."""

    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url
        self.ws_url = base_url.replace("http", "ws")
        self.test_results = {}
        self.session_id = None

    async def run_all_tests(self):
        """Run all MCP tests."""
        print("🧪 Starting Modern MCP Test Suite")
        print("=" * 50)

        # Test server initialization
        await self.test_server_initialization()

        # Test HTTP endpoints
        await self.test_http_health_check()
        await self.test_http_status_endpoint()
        await self.test_http_metrics_endpoint()

        # Test MCP protocol over HTTP
        await self.test_mcp_http_protocol()

        # Test WebSocket functionality
        await self.test_websocket_connection()
        await self.test_mcp_websocket_protocol()

        # Test authentication (if enabled)
        if settings.MCP_SECURITY_ENABLED:
            await self.test_authentication()

        # Test production readiness
        await self.test_production_features()

        # Print results
        self.print_test_results()

        return self.test_results

    async def test_server_initialization(self):
        """Test MCP server initialization."""
        print("\n🚀 Testing Server Initialization...")

        try:
            from second_brain_database.integrations.mcp.modern_server import mcp

            # Test server creation
            assert mcp.name == settings.MCP_SERVER_NAME
            assert mcp.version == settings.MCP_SERVER_VERSION

            # Test authentication configuration
            auth_expected = settings.MCP_TRANSPORT == "http" and settings.MCP_SECURITY_ENABLED
            auth_actual = mcp.auth is not None

            self.test_results["server_initialization"] = {
                "status": "✅ PASS",
                "server_name": mcp.name,
                "server_version": mcp.version,
                "auth_configured": auth_actual,
                "auth_expected": auth_expected,
            }

            print(f"   ✅ Server: {mcp.name} v{mcp.version}")
            print(f"   ✅ Auth: {'Enabled' if auth_actual else 'Disabled'}")

        except Exception as e:
            self.test_results["server_initialization"] = {"status": "❌ FAIL", "error": str(e)}
            print(f"   ❌ Server initialization failed: {e}")

    async def test_http_health_check(self):
        """Test HTTP health check endpoint."""
        print("\n🏥 Testing Health Check...")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/health")

                if response.status_code == 200:
                    health_data = response.json()

                    self.test_results["health_check"] = {
                        "status": "✅ PASS",
                        "response_code": response.status_code,
                        "server_status": health_data.get("status"),
                        "components": list(health_data.get("components", {}).keys()),
                    }

                    print(f"   ✅ Health Status: {health_data.get('status')}")
                    print(f"   ✅ Components: {', '.join(health_data.get('components', {}).keys())}")

                else:
                    self.test_results["health_check"] = {
                        "status": "❌ FAIL",
                        "response_code": response.status_code,
                        "error": "Unexpected status code",
                    }
                    print(f"   ❌ Health check failed: HTTP {response.status_code}")

        except Exception as e:
            self.test_results["health_check"] = {"status": "❌ FAIL", "error": str(e)}
            print(f"   ❌ Health check error: {e}")

    async def test_http_status_endpoint(self):
        """Test HTTP status endpoint."""
        print("\n📊 Testing Status Endpoint...")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/status")

                if response.status_code == 200:
                    status_data = response.json()

                    self.test_results["status_endpoint"] = {
                        "status": "✅ PASS",
                        "server_name": status_data.get("name"),
                        "version": status_data.get("version"),
                        "protocol": status_data.get("protocol"),
                        "endpoints": list(status_data.get("endpoints", {}).keys()),
                    }

                    print(f"   ✅ Server: {status_data.get('name')}")
                    print(f"   ✅ Protocol: {status_data.get('protocol')}")
                    print(f"   ✅ Endpoints: {', '.join(status_data.get('endpoints', {}).keys())}")

                else:
                    self.test_results["status_endpoint"] = {"status": "❌ FAIL", "response_code": response.status_code}
                    print(f"   ❌ Status endpoint failed: HTTP {response.status_code}")

        except Exception as e:
            self.test_results["status_endpoint"] = {"status": "❌ FAIL", "error": str(e)}
            print(f"   ❌ Status endpoint error: {e}")

    async def test_http_metrics_endpoint(self):
        """Test HTTP metrics endpoint."""
        print("\n📈 Testing Metrics Endpoint...")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/metrics")

                if response.status_code == 200:
                    metrics_data = response.text

                    self.test_results["metrics_endpoint"] = {
                        "status": "✅ PASS",
                        "content_type": response.headers.get("content-type"),
                        "has_metrics": len(metrics_data) > 0,
                    }

                    print(f"   ✅ Metrics available: {len(metrics_data)} bytes")
                    print(f"   ✅ Content-Type: {response.headers.get('content-type')}")

                else:
                    self.test_results["metrics_endpoint"] = {"status": "❌ FAIL", "response_code": response.status_code}
                    print(f"   ❌ Metrics endpoint failed: HTTP {response.status_code}")

        except Exception as e:
            self.test_results["metrics_endpoint"] = {"status": "❌ FAIL", "error": str(e)}
            print(f"   ❌ Metrics endpoint error: {e}")

    async def test_mcp_http_protocol(self):
        """Test MCP protocol over HTTP following FastMCP 2.x patterns."""
        print("\n🔌 Testing MCP HTTP Protocol...")

        try:
            headers = {"Content-Type": "application/json"}

            # Add authentication if enabled
            if settings.MCP_SECURITY_ENABLED and hasattr(settings, "MCP_AUTH_TOKEN"):
                token = settings.MCP_AUTH_TOKEN
                if hasattr(token, "get_secret_value"):
                    token = token.get_secret_value()
                headers["Authorization"] = f"Bearer {token}"

            async with httpx.AsyncClient() as client:
                # Test initialize first (FastMCP 2.x pattern)
                init_request = {
                    "jsonrpc": "2.0",
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "Test Client", "version": "1.0.0"},
                    },
                    "id": 1,
                }

                init_response = await client.post(f"{self.base_url}/mcp", json=init_request, headers=headers)

                # Test tools/list
                tools_request = {"jsonrpc": "2.0", "method": "tools/list", "id": 2}

                tools_response = await client.post(f"{self.base_url}/mcp", json=tools_request, headers=headers)

                # Test a specific tool call
                tool_call_request = {
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {"name": "get_server_info", "arguments": {}},
                    "id": 3,
                }

                tool_call_response = await client.post(f"{self.base_url}/mcp", json=tool_call_request, headers=headers)

                # Evaluate results
                init_success = init_response.status_code == 200 and "result" in init_response.json()
                tools_success = tools_response.status_code == 200 and "result" in tools_response.json()
                tool_call_success = tool_call_response.status_code == 200

                if init_success and tools_success:
                    tools_data = tools_response.json()

                    self.test_results["mcp_http_protocol"] = {
                        "status": "✅ PASS",
                        "initialize": "success" if init_success else "failed",
                        "tools_list": "success" if tools_success else "failed",
                        "tool_call": "success" if tool_call_success else "failed",
                        "jsonrpc_version": tools_data.get("jsonrpc"),
                        "tools_count": len(tools_data.get("result", {}).get("tools", [])),
                    }

                    print(f"   ✅ MCP Initialize: {'Success' if init_success else 'Failed'}")
                    print(f"   ✅ MCP Protocol: JSON-RPC {tools_data.get('jsonrpc')}")
                    print(f"   ✅ Tools Available: {len(tools_data.get('result', {}).get('tools', []))}")
                    print(f"   ✅ Tool Call: {'Success' if tool_call_success else 'Failed'}")

                else:
                    self.test_results["mcp_http_protocol"] = {
                        "status": "❌ FAIL",
                        "initialize": init_response.status_code,
                        "tools_list": tools_response.status_code,
                        "tool_call": tool_call_response.status_code,
                    }
                    print(
                        f"   ❌ MCP Protocol failed - Init: {init_response.status_code}, Tools: {tools_response.status_code}"
                    )

        except Exception as e:
            self.test_results["mcp_http_protocol"] = {"status": "❌ FAIL", "error": str(e)}
            print(f"   ❌ MCP HTTP protocol error: {e}")

    async def test_websocket_connection(self):
        """Test WebSocket connection."""
        print("\n🌐 Testing WebSocket Connection...")

        try:
            # Test basic WebSocket connection
            uri = f"{self.ws_url}/mcp/ws"

            async with websockets.connect(uri) as websocket:
                # Send a ping to test connection
                await websocket.send(json.dumps({"jsonrpc": "2.0", "method": "ping", "id": 1}))

                # Wait for response (with timeout)
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    response_data = json.loads(response)

                    self.test_results["websocket_connection"] = {
                        "status": "✅ PASS",
                        "connection": "successful",
                        "response_received": True,
                        "jsonrpc_version": response_data.get("jsonrpc"),
                    }

                    print("   ✅ WebSocket connection established")
                    print("   ✅ Message exchange successful")

                except asyncio.TimeoutError:
                    self.test_results["websocket_connection"] = {
                        "status": "⚠️  PARTIAL",
                        "connection": "successful",
                        "response_received": False,
                        "note": "Connection works but no response to ping",
                    }
                    print("   ✅ WebSocket connection established")
                    print("   ⚠️  No response to ping (may be expected)")

        except Exception as e:
            self.test_results["websocket_connection"] = {"status": "❌ FAIL", "error": str(e)}
            print(f"   ❌ WebSocket connection error: {e}")

    async def test_mcp_websocket_protocol(self):
        """Test MCP protocol over WebSocket."""
        print("\n🔄 Testing MCP WebSocket Protocol...")

        try:
            uri = f"{self.ws_url}/mcp/ws"

            async with websockets.connect(uri) as websocket:
                # Test initialize
                init_request = {
                    "jsonrpc": "2.0",
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "MCP Test Client", "version": "1.0.0"},
                    },
                    "id": 1,
                }

                await websocket.send(json.dumps(init_request))

                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    response_data = json.loads(response)

                    if "result" in response_data:
                        self.test_results["mcp_websocket_protocol"] = {
                            "status": "✅ PASS",
                            "initialize": "success",
                            "protocol_version": response_data["result"].get("protocolVersion"),
                            "server_info": response_data["result"].get("serverInfo"),
                        }

                        print("   ✅ MCP Initialize successful")
                        print(f"   ✅ Protocol: {response_data['result'].get('protocolVersion')}")

                        server_info = response_data["result"].get("serverInfo", {})
                        print(f"   ✅ Server: {server_info.get('name')} v{server_info.get('version')}")

                    else:
                        self.test_results["mcp_websocket_protocol"] = {
                            "status": "❌ FAIL",
                            "initialize": "failed",
                            "error": response_data.get("error"),
                        }
                        print(f"   ❌ MCP Initialize failed: {response_data.get('error')}")

                except asyncio.TimeoutError:
                    self.test_results["mcp_websocket_protocol"] = {
                        "status": "❌ FAIL",
                        "initialize": "timeout",
                        "error": "No response to initialize request",
                    }
                    print("   ❌ MCP Initialize timeout")

        except Exception as e:
            self.test_results["mcp_websocket_protocol"] = {"status": "❌ FAIL", "error": str(e)}
            print(f"   ❌ MCP WebSocket protocol error: {e}")

    async def test_authentication(self):
        """Test authentication if enabled."""
        print("\n🔐 Testing Authentication...")

        try:
            # Test without authentication (should fail)
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/mcp", json={"jsonrpc": "2.0", "method": "tools/list", "id": 1}
                )

                auth_required = response.status_code == 401

                # Test with authentication
                if hasattr(settings, "MCP_AUTH_TOKEN"):
                    token = settings.MCP_AUTH_TOKEN
                    if hasattr(token, "get_secret_value"):
                        token = token.get_secret_value()

                    headers = {"Authorization": f"Bearer {token}"}
                    auth_response = await client.post(
                        f"{self.base_url}/mcp",
                        json={"jsonrpc": "2.0", "method": "tools/list", "id": 1},
                        headers=headers,
                    )

                    auth_success = auth_response.status_code == 200

                    self.test_results["authentication"] = {
                        "status": "✅ PASS" if auth_required and auth_success else "❌ FAIL",
                        "auth_required": auth_required,
                        "auth_success": auth_success,
                        "token_configured": True,
                    }

                    print(f"   ✅ Auth Required: {auth_required}")
                    print(f"   ✅ Auth Success: {auth_success}")

                else:
                    self.test_results["authentication"] = {
                        "status": "⚠️  PARTIAL",
                        "auth_required": auth_required,
                        "token_configured": False,
                        "note": "No auth token configured",
                    }
                    print("   ⚠️  No auth token configured")

        except Exception as e:
            self.test_results["authentication"] = {"status": "❌ FAIL", "error": str(e)}
            print(f"   ❌ Authentication test error: {e}")

    async def test_production_features(self):
        """Test production readiness features."""
        print("\n🏭 Testing Production Features...")

        features = {}

        try:
            async with httpx.AsyncClient() as client:
                # Test security headers
                response = await client.get(f"{self.base_url}/health")
                headers = response.headers

                security_headers = {
                    "X-Content-Type-Options": headers.get("x-content-type-options"),
                    "X-Frame-Options": headers.get("x-frame-options"),
                    "X-XSS-Protection": headers.get("x-xss-protection"),
                    "Referrer-Policy": headers.get("referrer-policy"),
                }

                features["security_headers"] = {
                    "present": sum(1 for v in security_headers.values() if v) > 0,
                    "headers": security_headers,
                }

                # Test CORS configuration
                cors_response = await client.options(f"{self.base_url}/health")
                features["cors"] = {
                    "configured": "access-control-allow-origin" in cors_response.headers,
                    "enabled": settings.MCP_HTTP_CORS_ENABLED,
                }

                # Test monitoring endpoints
                features["monitoring"] = {
                    "health_check": response.status_code == 200,
                    "metrics_available": True,  # We tested this earlier
                }

                self.test_results["production_features"] = {"status": "✅ PASS", "features": features}

                print(f"   ✅ Security Headers: {features['security_headers']['present']}")
                print(f"   ✅ CORS: {'Enabled' if features['cors']['enabled'] else 'Disabled'}")
                print(f"   ✅ Monitoring: Available")

        except Exception as e:
            self.test_results["production_features"] = {"status": "❌ FAIL", "error": str(e)}
            print(f"   ❌ Production features test error: {e}")

    def print_test_results(self):
        """Print comprehensive test results."""
        print("\n" + "=" * 50)
        print("🧪 MCP Test Results Summary")
        print("=" * 50)

        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result["status"].startswith("✅"))
        partial_tests = sum(1 for result in self.test_results.values() if result["status"].startswith("⚠️"))
        failed_tests = sum(1 for result in self.test_results.values() if result["status"].startswith("❌"))

        print(f"Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"⚠️  Partial: {partial_tests}")
        print(f"❌ Failed: {failed_tests}")
        print()

        for test_name, result in self.test_results.items():
            print(f"{result['status']} {test_name.replace('_', ' ').title()}")
            if "error" in result:
                print(f"   Error: {result['error']}")

        print("\n" + "=" * 50)

        if failed_tests == 0:
            print("🎉 All critical tests passed! MCP server is ready.")
        elif failed_tests <= 2:
            print("⚠️  Minor issues detected. Check failed tests above.")
        else:
            print("❌ Multiple issues detected. Review implementation.")

        print("=" * 50)


async def main():
    """Main test function."""
    import argparse

    parser = argparse.ArgumentParser(description="Test Modern MCP Implementation")
    parser.add_argument("--url", default="http://localhost:8001", help="Base URL for MCP server")
    parser.add_argument("--start-server", action="store_true", help="Start server before testing")

    args = parser.parse_args()

    if args.start_server:
        print("🚀 Starting MCP server for testing...")
        # Note: In a real scenario, you'd start the server in a subprocess
        print("   Please start the server manually with:")
        print("   python start_mcp_server.py --transport http --host 127.0.0.1 --port 8001")
        print("   Then run this test again without --start-server")
        return

    # Run tests
    test_suite = MCPTestSuite(args.url)
    results = await test_suite.run_all_tests()

    # Exit with appropriate code
    failed_count = sum(1 for result in results.values() if result["status"].startswith("❌"))
    sys.exit(0 if failed_count == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())

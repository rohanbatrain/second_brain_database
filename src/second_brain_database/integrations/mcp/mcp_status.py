"""
FastMCP 2.13.0.2 Status and Testing Utility

This module provides comprehensive status checking and testing utilities
for the FastMCP integration to help diagnose and resolve issues.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ...config import settings
from ...managers.logging_manager import get_logger

logger = get_logger(prefix="[MCP_Status]")


async def get_comprehensive_mcp_status() -> Dict[str, Any]:
    """
    Get comprehensive status of the FastMCP integration.

    Returns:
        Dictionary with detailed status information
    """
    status = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "fastmcp_version": "2.13.0.2",
        "integration_status": "unknown",
        "server": {},
        "tools": {},
        "resources": {},
        "prompts": {},
        "errors": [],
    }

    try:
        # Test FastMCP import
        try:
            from fastmcp import FastMCP

            status["fastmcp_import"] = "success"
        except ImportError as e:
            status["fastmcp_import"] = "failed"
            status["errors"].append(f"FastMCP import failed: {e}")
            return status

        # Test server creation and ensure tools are imported
        try:
            from .mcp_instance import ensure_tools_imported
            from .modern_server import mcp

            # Ensure all tools are imported
            ensure_tools_imported()

            status["server"] = {
                "available": True,
                "name": mcp.name,
                "type": str(type(mcp)),
                "auth_enabled": mcp.auth is not None,
                "include_tags": getattr(mcp, "include_tags", None),
                "exclude_tags": getattr(mcp, "exclude_tags", None),
            }
        except Exception as e:
            status["server"] = {"available": False, "error": str(e)}
            status["errors"].append(f"Server creation failed: {e}")
            return status

        # Test tool listing
        try:
            tools = await mcp.get_tools()
            status["tools"] = {"count": len(tools), "available": True, "sample_tools": list(tools.keys())[:10]}
        except Exception as e:
            status["tools"] = {"count": 0, "available": False, "error": str(e)}
            status["errors"].append(f"Tool listing failed: {e}")

        # Test resource listing
        try:
            resources = await mcp.get_resources()
            status["resources"] = {
                "count": len(resources),
                "available": True,
                "sample_resources": list(resources.keys())[:10],
            }
        except Exception as e:
            status["resources"] = {"count": 0, "available": False, "error": str(e)}
            status["errors"].append(f"Resource listing failed: {e}")

        # Test prompt listing
        try:
            prompts = await mcp.get_prompts()
            status["prompts"] = {"count": len(prompts), "available": True, "sample_prompts": list(prompts.keys())[:10]}
        except Exception as e:
            status["prompts"] = {"count": 0, "available": False, "error": str(e)}
            status["errors"].append(f"Prompt listing failed: {e}")

        # Determine overall status
        if len(status["errors"]) == 0:
            status["integration_status"] = "healthy"
        elif status["server"]["available"] and status["tools"]["count"] > 0:
            status["integration_status"] = "working_with_issues"
        else:
            status["integration_status"] = "degraded"

    except Exception as e:
        status["integration_status"] = "failed"
        status["errors"].append(f"Status check failed: {e}")
        logger.error("MCP status check failed: %s", e)

    return status


async def test_mcp_tool_execution() -> Dict[str, Any]:
    """
    Test MCP tool execution with a simple test.

    Returns:
        Dictionary with test results
    """
    test_results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "test_tool_registration": False,
        "test_tool_execution": False,
        "errors": [],
    }

    try:
        from .modern_server import mcp

        # Test tool registration
        @mcp.tool
        def mcp_test_tool(message: str) -> str:
            """A test tool for MCP integration testing"""
            return f"MCP Test Response: {message}"

        # Check if tool was registered
        tools = await mcp.get_tools()
        if "mcp_test_tool" in tools:
            test_results["test_tool_registration"] = True
            logger.info("Test tool successfully registered")
        else:
            test_results["errors"].append("Test tool was not registered")

        # Note: We can't easily test tool execution without a full MCP client
        # This would require setting up the MCP protocol communication
        test_results["test_tool_execution"] = "skipped_requires_mcp_client"

    except Exception as e:
        test_results["errors"].append(f"Tool test failed: {e}")
        logger.error("MCP tool test failed: %s", e)

    return test_results


async def diagnose_mcp_issues() -> Dict[str, Any]:
    """
    Diagnose common MCP integration issues.

    Returns:
        Dictionary with diagnosis and recommendations
    """
    diagnosis = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "issues_found": [],
        "recommendations": [],
        "status": "unknown",
    }

    try:
        # Get comprehensive status
        status = await get_comprehensive_mcp_status()

        # Check for common issues
        if status["integration_status"] == "failed":
            diagnosis["issues_found"].append("FastMCP integration completely failed")
            diagnosis["recommendations"].append("Check FastMCP installation: pip install fastmcp==2.13.0.2")

        if not status["server"]["available"]:
            diagnosis["issues_found"].append("MCP server not available")
            diagnosis["recommendations"].append("Check modern_server.py configuration")

        if status["tools"]["count"] == 0:
            diagnosis["issues_found"].append("No tools registered")
            diagnosis["recommendations"].append("Ensure tool modules are imported (family_tools, auth_tools, etc.)")

        if status["resources"]["count"] == 0:
            diagnosis["issues_found"].append("No resources registered")
            diagnosis["recommendations"].append("Check resource module imports")

        if status["prompts"]["count"] == 0:
            diagnosis["issues_found"].append("No prompts registered")
            diagnosis["recommendations"].append("Check prompt module imports")

        # Check configuration issues
        if not status["server"].get("auth_enabled", False):
            diagnosis["issues_found"].append("Authentication not enabled")
            diagnosis["recommendations"].append("Check MCP_SECURITY_ENABLED and MCP_REQUIRE_AUTH settings")

        # Determine overall diagnosis
        if len(diagnosis["issues_found"]) == 0:
            diagnosis["status"] = "healthy"
            diagnosis["recommendations"].append("MCP integration is working correctly")
        elif status["tools"]["count"] > 50:  # We expect ~100+ tools
            diagnosis["status"] = "mostly_working"
            diagnosis["recommendations"].append("Core functionality working, minor issues detected")
        else:
            diagnosis["status"] = "needs_attention"
            diagnosis["recommendations"].append("Significant issues detected, review configuration")

        # Add general recommendations
        diagnosis["recommendations"].extend(
            [
                "Run 'python -c \"from src.second_brain_database.integrations.mcp.mcp_status import *; import asyncio; print(asyncio.run(get_comprehensive_mcp_status()))\"' for detailed status",
                "Check logs for specific error messages",
                "Ensure all required dependencies are installed",
                "Verify configuration settings in config.py",
            ]
        )

    except Exception as e:
        diagnosis["issues_found"].append(f"Diagnosis failed: {e}")
        diagnosis["status"] = "diagnosis_failed"
        logger.error("MCP diagnosis failed: %s", e)

    return diagnosis


def print_mcp_status():
    """
    Print a human-readable MCP status report.
    """

    async def _print_status():
        print("=" * 60)
        print("FastMCP 2.13.0.2 Integration Status Report")
        print("=" * 60)

        status = await get_comprehensive_mcp_status()

        print(f"Overall Status: {status['integration_status'].upper()}")
        print(f"Timestamp: {status['timestamp']}")
        print()

        # Server status
        print("🖥️  Server Status:")
        if status["server"]["available"]:
            print(f"   ✅ Server Available: {status['server']['name']}")
            print(f"   🔐 Authentication: {'Enabled' if status['server']['auth_enabled'] else 'Disabled'}")
            if status["server"].get("include_tags"):
                print(f"   🏷️  Include Tags: {status['server']['include_tags']}")
            if status["server"].get("exclude_tags"):
                print(f"   🚫 Exclude Tags: {status['server']['exclude_tags']}")
        else:
            print(f"   ❌ Server Unavailable: {status['server'].get('error', 'Unknown error')}")
        print()

        # Tools status
        print("🔧 Tools Status:")
        if status["tools"]["available"]:
            print(f"   ✅ Tools Registered: {status['tools']['count']}")
            if status["tools"]["sample_tools"]:
                print(f"   📝 Sample Tools: {', '.join(status['tools']['sample_tools'][:5])}...")
        else:
            print(f"   ❌ Tools Unavailable: {status['tools'].get('error', 'Unknown error')}")
        print()

        # Resources status
        print("📁 Resources Status:")
        if status["resources"]["available"]:
            print(f"   ✅ Resources Registered: {status['resources']['count']}")
            if status["resources"]["sample_resources"]:
                print(f"   📝 Sample Resources: {', '.join(status['resources']['sample_resources'][:3])}...")
        else:
            print(f"   ❌ Resources Unavailable: {status['resources'].get('error', 'Unknown error')}")
        print()

        # Prompts status
        print("💬 Prompts Status:")
        if status["prompts"]["available"]:
            print(f"   ✅ Prompts Registered: {status['prompts']['count']}")
            if status["prompts"]["sample_prompts"]:
                print(f"   📝 Sample Prompts: {', '.join(status['prompts']['sample_prompts'][:3])}...")
        else:
            print(f"   ❌ Prompts Unavailable: {status['prompts'].get('error', 'Unknown error')}")
        print()

        # Errors
        if status["errors"]:
            print("⚠️  Errors Detected:")
            for error in status["errors"]:
                print(f"   • {error}")
            print()

        # Diagnosis
        diagnosis = await diagnose_mcp_issues()
        print("🔍 Diagnosis:")
        print(f"   Status: {diagnosis['status'].upper()}")

        if diagnosis["issues_found"]:
            print("   Issues Found:")
            for issue in diagnosis["issues_found"]:
                print(f"     • {issue}")

        if diagnosis["recommendations"]:
            print("   Recommendations:")
            for rec in diagnosis["recommendations"][:5]:  # Show first 5
                print(f"     • {rec}")

        print("=" * 60)

    # Run the async function
    asyncio.run(_print_status())


if __name__ == "__main__":
    print_mcp_status()

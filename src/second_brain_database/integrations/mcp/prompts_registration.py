"""
FastMCP 2.x Prompt Registration

This module demonstrates proper prompt registration following FastMCP 2.x patterns.
Prompts are registered using the @mcp.prompt decorator directly on the server instance.
"""

from typing import Dict, Any, List
from datetime import datetime

from ...managers.logging_manager import get_logger
from .modern_server import mcp

logger = get_logger(prefix="[MCP_Prompts]")


# FastMCP 2.x compliant prompt registration following documentation patterns
@mcp.prompt
def server_help() -> str:
    """Provide help information about the MCP server."""
    return f"""# Second Brain Database MCP Server Help

## Server Information
- Name: {mcp.name}
- Version: {mcp.version}
- Authentication: {'Enabled' if mcp.auth else 'Disabled'}

## Available Features
- Tools: Execute server functions
- Resources: Access server data and status
- Prompts: Get structured guidance and help

## Getting Started
1. Use tools to interact with the server
2. Access resources for server information
3. Use prompts for guidance and templates

## Support
For more information, use the available tools and resources."""


@mcp.prompt(
    name="api_usage_guide",
    description="Provides comprehensive guidance on using the MCP API",
    tags={"documentation", "api"}
)
def api_usage_guide_prompt() -> str:
    """Provide guidance on using the MCP API."""
    return """# MCP API Usage Guide

## Making Tool Calls
Use the MCP protocol to call tools:
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "tool_name",
    "arguments": {"param": "value"}
  },
  "id": 1
}
```

## Accessing Resources
Resources provide server data:
```json
{
  "jsonrpc": "2.0",
  "method": "resources/read",
  "params": {
    "uri": "server://status"
  },
  "id": 2
}
```

## Using Prompts
Get structured guidance:
```json
{
  "jsonrpc": "2.0",
  "method": "prompts/get",
  "params": {
    "name": "server_help"
  },
  "id": 3
}
```"""


@mcp.prompt("troubleshooting_guide")
async def troubleshooting_guide_prompt() -> str:
    """Provide troubleshooting guidance for common issues."""
    return f"""
# MCP Server Troubleshooting Guide

## Server Status
- Server: {mcp.name} v{mcp.version}
- Timestamp: {datetime.now().isoformat()}
- Authentication: {'Required' if mcp.auth else 'Not Required'}

## Common Issues

### Connection Problems
1. Check server is running
2. Verify correct port and host
3. Check authentication if enabled

### Authentication Errors
1. Ensure bearer token is provided
2. Check token format and validity
3. Verify authentication is enabled

### Tool Execution Errors
1. Check tool name spelling
2. Verify required parameters
3. Check parameter types and values

### Resource Access Issues
1. Verify resource URI format
2. Check resource exists
3. Ensure proper permissions

## Health Check
Use the health_check_tool to verify server status.

## Support
- Check server logs for detailed error information
- Use available diagnostic tools
- Verify configuration settings
"""


@mcp.prompt("development_guide")
async def development_guide_prompt() -> str:
    """Provide guidance for developers working with the MCP server."""
    return """
# MCP Server Development Guide

## Adding New Tools
1. Create function with proper type hints
2. Use @mcp.tool decorator
3. Include comprehensive docstring
4. Handle errors gracefully

Example:
```python
@mcp.tool
def my_tool(param: str) -> Dict[str, Any]:
    \"\"\"Description of what the tool does.\"\"\"
    try:
        # Tool implementation
        return {"result": "success"}
    except Exception as e:
        return {"error": str(e)}
```

## Adding Resources
1. Use @mcp.resource decorator with URI pattern
2. Return string content
3. Support templated URIs when needed

Example:
```python
@mcp.resource("my://resource")
async def my_resource() -> str:
    return "Resource content"
```

## Adding Prompts
1. Use @mcp.prompt decorator
2. Return helpful guidance text
3. Include examples and usage patterns

## Best Practices
- Always include error handling
- Use type hints for all parameters
- Write comprehensive docstrings
- Test tools thoroughly
- Follow FastMCP 2.x patterns
"""


@mcp.prompt("security_guide")
async def security_guide_prompt() -> str:
    """Provide security guidance for the MCP server."""
    auth_status = "enabled" if mcp.auth else "disabled"
    return f"""
# MCP Server Security Guide

## Current Security Status
- Authentication: {auth_status.title()}
- Server: {mcp.name}
- Version: {mcp.version}

## Security Best Practices

### Authentication
- Always enable authentication in production
- Use strong bearer tokens
- Rotate tokens regularly
- Monitor authentication failures

### Network Security
- Use HTTPS in production
- Implement proper firewall rules
- Restrict access to necessary IPs
- Monitor network traffic

### Tool Security
- Validate all input parameters
- Implement proper error handling
- Log security-relevant events
- Follow principle of least privilege

### Resource Security
- Control access to sensitive resources
- Validate resource URIs
- Implement proper authorization
- Monitor resource access

## Monitoring
- Enable comprehensive logging
- Monitor authentication attempts
- Track tool usage patterns
- Set up alerting for anomalies

## Incident Response
- Have incident response plan
- Monitor logs regularly
- Implement automated alerts
- Keep security patches updated
"""


def register_example_prompts():
    """
    Register example prompts with the MCP server.
    
    Note: In FastMCP 2.x, prompts are automatically registered when the module
    is imported and the @mcp.prompt decorators are executed. This function
    is provided for explicit registration if needed.
    """
    logger.info("Example prompts registered with FastMCP 2.x server")
    logger.info("Prompts available: server_help, api_usage_guide, troubleshooting_guide, development_guide, security_guide")


# Auto-register prompts when module is imported
register_example_prompts()
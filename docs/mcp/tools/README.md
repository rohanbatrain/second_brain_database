# MCP Tools Usage Guide

## Overview

The FastMCP Gateway Integration provides comprehensive MCP tools organized into logical categories. Each tool is secured with authentication, authorization, and audit logging while providing rich functionality for managing the Second Brain Database system.

## Tool Categories

- **[Family Management](./family-tools.md)** - Complete family lifecycle and member management
- **[Authentication & Profile](./auth-tools.md)** - User authentication, profile, and security management
- **[Shop & Assets](./shop-tools.md)** - Digital asset browsing, purchasing, and management
- **[Workspace & Teams](./workspace-tools.md)** - Team collaboration and workspace management
- **[System Administration](./admin-tools.md)** - System monitoring and user moderation (restricted)

## Common Usage Patterns

### Authentication Context

All MCP tools require proper authentication. The security wrapper automatically validates:

```python
# Authentication is handled automatically by security wrappers
# Tools receive authenticated user context
current_user = get_current_mcp_user()
```

### Error Handling

Tools return structured error responses following MCP protocol:

```json
{
  "error": {
    "code": "AUTHENTICATION_ERROR",
    "message": "Authentication required for this operation",
    "details": {
      "required_permissions": ["family:read"],
      "current_permissions": []
    }
  }
}
```

### Rate Limiting

All tools are subject to rate limiting based on user and action:

- **Default**: 100 requests per minute per user
- **Sensitive operations**: Lower limits (e.g., 10 password resets per hour)
- **Admin operations**: Stricter limits for security

### Audit Logging

Every tool invocation is logged with:

- User identity and permissions
- Tool name and parameters
- Execution time and result
- IP address and user agent
- Security events and violations

## Tool Discovery

### Available Tools

List all available tools:

```bash
# Using MCP client
mcp list-tools

# Or via health endpoint
curl http://localhost:8000/health/mcp/tools
```

### Tool Metadata

Each tool provides comprehensive metadata:

```json
{
  "name": "get_family_info",
  "description": "Get family information with security validation",
  "parameters": {
    "family_id": {
      "type": "string",
      "description": "Family identifier",
      "required": true
    }
  },
  "permissions_required": ["family:read"],
  "rate_limit": "family_read",
  "audit_enabled": true
}
```

## Security Model

### Permission System

Tools require specific permissions:

- **family:read** - View family information
- **family:write** - Modify family settings
- **family:admin** - Administrative family operations
- **user:read** - View user profiles
- **user:write** - Modify user profiles
- **shop:purchase** - Make purchases
- **workspace:admin** - Workspace administration
- **system:admin** - System administration (super users only)

### Role-Based Access

Users have roles that grant permission sets:

- **Member** - Basic family and profile access
- **Admin** - Family/workspace administration
- **Super User** - System administration access

### Security Validation

Each tool validates:

1. **Authentication** - Valid JWT or permanent token
2. **Authorization** - Required permissions for operation
3. **Rate Limiting** - Within allowed request limits
4. **Input Validation** - Proper parameter types and values
5. **Business Rules** - Domain-specific access controls

## Resource System

### Available Resources

MCP resources provide structured data access:

- **family://{family_id}/info** - Family information
- **user://{user_id}/profile** - User profile data
- **shop://catalog** - Shop item catalog
- **workspace://{workspace_id}/info** - Workspace details
- **system://status** - System health information

### Resource Access

```python
# Access family resource
family_resource = await mcp_client.get_resource("family://12345/info")

# Access user profile
profile_resource = await mcp_client.get_resource("user://current/profile")
```

## Prompt System

### Available Prompts

Contextual guidance prompts:

- **family_management_guide** - Family operation guidance
- **shop_navigation** - Shopping and purchase assistance
- **workspace_management** - Team collaboration guidance
- **security_setup** - Account security configuration
- **troubleshooting** - Common issue resolution
- **onboarding** - New user guidance

### Using Prompts

```python
# Get family management guidance
guidance = await mcp_client.get_prompt("family_management_guide")

# Get contextual help for current user
help_text = await mcp_client.get_prompt("onboarding", {
    "user_context": current_user
})
```

## Integration Examples

### Basic Tool Usage

```python
import asyncio
from mcp_client import MCPClient

async def example_usage():
    # Initialize MCP client
    client = MCPClient("http://localhost:3001")
    
    # Authenticate (implementation depends on client)
    await client.authenticate(token="your-jwt-token")
    
    # Use family management tools
    families = await client.call_tool("get_user_families")
    
    if families:
        family_id = families[0]["id"]
        members = await client.call_tool("get_family_members", {
            "family_id": family_id
        })
        print(f"Family has {len(members)} members")
    
    # Use shop tools
    items = await client.call_tool("list_shop_items", {
        "category": "avatars",
        "limit": 10
    })
    
    # Make a purchase
    if items:
        result = await client.call_tool("purchase_item", {
            "item_id": items[0]["id"],
            "quantity": 1
        })
        print(f"Purchase result: {result}")

# Run example
asyncio.run(example_usage())
```

### Error Handling Example

```python
async def robust_tool_usage():
    client = MCPClient("http://localhost:3001")
    
    try:
        await client.authenticate(token="your-token")
        
        result = await client.call_tool("get_family_info", {
            "family_id": "invalid-id"
        })
        
    except MCPAuthenticationError:
        print("Authentication failed - check token")
    except MCPAuthorizationError:
        print("Insufficient permissions")
    except MCPValidationError as e:
        print(f"Invalid parameters: {e.details}")
    except MCPRateLimitError:
        print("Rate limit exceeded - wait before retrying")
    except MCPToolError as e:
        print(f"Tool execution failed: {e.message}")
```

### Batch Operations

```python
async def batch_operations():
    client = MCPClient("http://localhost:3001")
    await client.authenticate(token="your-token")
    
    # Get all user families
    families = await client.call_tool("get_user_families")
    
    # Get member count for each family
    family_stats = []
    for family in families:
        members = await client.call_tool("get_family_members", {
            "family_id": family["id"]
        })
        family_stats.append({
            "family": family["name"],
            "member_count": len(members)
        })
    
    return family_stats
```

## Best Practices

### Performance Optimization

1. **Batch related operations** when possible
2. **Cache frequently accessed data** on client side
3. **Use appropriate timeouts** for long-running operations
4. **Monitor rate limits** and implement backoff strategies

### Security Best Practices

1. **Use least privilege** - Request minimal required permissions
2. **Validate all inputs** on client side before sending
3. **Handle authentication errors** gracefully with re-authentication
4. **Log security events** for audit purposes
5. **Rotate tokens regularly** for enhanced security

### Error Handling

1. **Implement retry logic** with exponential backoff
2. **Handle rate limiting** with appropriate delays
3. **Provide user-friendly error messages** for common failures
4. **Log errors** with sufficient context for debugging

### Development Workflow

1. **Test with development tokens** in non-production environments
2. **Use debug mode** for detailed logging during development
3. **Validate tool schemas** before integration
4. **Monitor tool performance** and optimize as needed

## Tool Testing

### Unit Testing Tools

```python
import pytest
from mcp_test_client import MCPTestClient

@pytest.mark.asyncio
async def test_family_tools():
    client = MCPTestClient()
    await client.authenticate_as_test_user()
    
    # Test family creation
    family = await client.call_tool("create_family", {
        "name": "Test Family",
        "description": "Test family for unit testing"
    })
    
    assert family["name"] == "Test Family"
    assert "id" in family
    
    # Test member addition
    result = await client.call_tool("add_family_member", {
        "family_id": family["id"],
        "email": "test@example.com",
        "role": "member"
    })
    
    assert result["success"] is True
```

### Integration Testing

```python
@pytest.mark.integration
async def test_complete_family_workflow():
    client = MCPTestClient()
    
    # Test complete family management workflow
    await client.authenticate_as_test_user()
    
    # Create family
    family = await client.call_tool("create_family", {
        "name": "Integration Test Family"
    })
    
    # Add members
    await client.call_tool("add_family_member", {
        "family_id": family["id"],
        "email": "member1@example.com"
    })
    
    # Update settings
    await client.call_tool("update_family_settings", {
        "family_id": family["id"],
        "settings": {"notifications_enabled": True}
    })
    
    # Verify final state
    final_family = await client.call_tool("get_family_info", {
        "family_id": family["id"]
    })
    
    assert final_family["member_count"] == 2
    assert final_family["settings"]["notifications_enabled"] is True
```

## Troubleshooting

### Common Issues

1. **Authentication failures**
   - Verify token validity and expiration
   - Check required permissions for tool
   - Ensure user account is active

2. **Rate limiting**
   - Implement exponential backoff
   - Monitor rate limit headers
   - Consider upgrading rate limits if needed

3. **Validation errors**
   - Check parameter types and formats
   - Verify required parameters are provided
   - Review tool documentation for constraints

4. **Performance issues**
   - Monitor tool execution times
   - Optimize batch operations
   - Consider caching strategies

### Debug Mode

Enable debug mode for detailed logging:

```bash
MCP_DEBUG_MODE=true uv run uvicorn src.second_brain_database.main:app
```

This provides detailed logs of:
- Tool invocations and parameters
- Security validation steps
- Performance metrics
- Error details and stack traces
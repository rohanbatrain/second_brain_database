# MCP Authentication System Guide

## Overview

The Second Brain Database MCP server now includes a comprehensive, production-ready authentication system that supports both development and production environments with proper security controls.

## Quick Fix for Current Issue

The authentication error you're experiencing has been fixed with the following changes:

### 1. Updated Security System (`security.py`)
- Added automatic detection of authentication requirements
- Created default user context for development mode
- Proper handling of both authenticated and non-authenticated scenarios

### 2. New Authentication Middleware (`auth_middleware.py`)
- Production-ready FastMCP 2.x authentication provider
- Integration with existing Second Brain Database auth system
- Support for JWT tokens, static tokens, and development mode

### 3. Server Factory (`server_factory.py`)
- Centralized server creation with proper error handling
- Configuration validation and health checks
- Production-ready deployment patterns

## Configuration Modes

### Development Mode (Current - No Auth Required)
```bash
# .sbd configuration
MCP_SECURITY_ENABLED=false
MCP_REQUIRE_AUTH=false
MCP_TRANSPORT=http
MCP_HTTP_HOST=0.0.0.0
MCP_HTTP_PORT=8001
```

**Client Configuration:**
```json
{
  "mcpServers": {
    "second-brain": {
      "url": "http://0.0.0.0:8001/mcp"
    }
  }
}
```

### Production Mode (Secure)
```bash
# .sbd configuration
MCP_SECURITY_ENABLED=true
MCP_REQUIRE_AUTH=true
MCP_AUTH_TOKEN=your-secure-token-here
MCP_TRANSPORT=http
MCP_HTTP_HOST=0.0.0.0
MCP_HTTP_PORT=8001
```

**Client Configuration:**
```json
{
  "mcpServers": {
    "second-brain": {
      "url": "http://0.0.0.0:8001/mcp",
      "headers": {
        "Authorization": "Bearer your-secure-token-here"
      }
    }
  }
}
```

## Setup Scripts

### Quick Setup
```bash
# Set up for development (no authentication)
python scripts/setup_mcp_auth.py --development

# Set up for production (with authentication)
python scripts/setup_mcp_auth.py --production

# Test current configuration
python scripts/setup_mcp_auth.py --test
```

### Manual Testing
```bash
# Test the authentication fix
python test_mcp_auth_fix.py
```

## Architecture

### Authentication Flow

1. **Request Received** → MCP server receives tool execution request
2. **Security Check** → `secure_mcp_tool` decorator checks configuration
3. **Context Creation** → Creates appropriate user context based on mode:
   - **Development**: Default admin context with full permissions
   - **Production**: Validates JWT/Bearer token and creates real user context
4. **Tool Execution** → Tool executes with proper user context
5. **Cleanup** → Context is cleaned up after execution

### Components

#### 1. Security Decorator (`security.py`)
```python
@secure_mcp_tool(permissions=["family:admin"])
async def create_family(name: str):
    # Tool implementation
    pass
```

#### 2. Authentication Provider (`auth_middleware.py`)
- Integrates with existing FastAPI authentication
- Supports multiple authentication methods
- Proper error handling and logging

#### 3. Server Factory (`server_factory.py`)
- Creates properly configured MCP servers
- Validates configuration
- Provides health checks

#### 4. Context Management (`context.py`)
- Thread-safe context variables
- User permission validation
- Audit trail support

## Troubleshooting

### Common Issues

#### 1. "No MCP user context available" Error
**Solution:** This has been fixed with the new authentication system. The server now automatically creates a default context in development mode.

#### 2. Authentication Provider Not Found
**Solution:** The system now falls back gracefully and provides clear error messages.

#### 3. Configuration Mismatch
**Solution:** Use the validation script to check your configuration:
```bash
python scripts/setup_mcp_auth.py --test
```

### Debug Steps

1. **Check Configuration:**
   ```bash
   python -c "from src.second_brain_database.config import settings; print(f'Transport: {settings.MCP_TRANSPORT}, Security: {settings.MCP_SECURITY_ENABLED}, Auth: {settings.MCP_REQUIRE_AUTH}')"
   ```

2. **Test Authentication System:**
   ```bash
   python test_mcp_auth_fix.py
   ```

3. **Validate Server Health:**
   ```bash
   python start_mcp_server.py --status
   ```

## Production Deployment

### 1. Security Configuration
```bash
# Generate secure tokens
python scripts/setup_mcp_auth.py --production
```

### 2. Environment Variables
```bash
export MCP_SECURITY_ENABLED=true
export MCP_REQUIRE_AUTH=true
export MCP_AUTH_TOKEN="your-secure-production-token"
export SECRET_KEY="your-jwt-secret"
export FERNET_KEY="your-fernet-key"
```

### 3. Docker Deployment
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install uv && uv sync --extra production
EXPOSE 8001
CMD ["python", "start_mcp_server.py", "--transport", "http", "--host", "0.0.0.0"]
```

### 4. Kubernetes Deployment
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mcp-server
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: mcp-server
        image: second-brain-mcp:latest
        env:
        - name: MCP_SECURITY_ENABLED
          value: "true"
        - name: MCP_AUTH_TOKEN
          valueFrom:
            secretKeyRef:
              name: mcp-secrets
              key: auth-token
```

## Monitoring

### Health Checks
```bash
# Basic health check
curl http://localhost:8001/health

# Detailed health check
curl http://localhost:8001/health | jq .
```

### Metrics
```bash
# Prometheus metrics
curl http://localhost:8001/metrics
```

### Logs
The system provides comprehensive logging:
- Authentication events
- Authorization checks
- Tool execution audit trails
- Security violations
- Performance metrics

## Security Best Practices

### Development
- Use development mode with security disabled for local testing
- Never commit real tokens to version control
- Use localhost/127.0.0.1 for development

### Production
- Always enable security and authentication
- Use strong, randomly generated tokens
- Implement proper TLS/SSL termination
- Monitor authentication failures
- Regular token rotation
- IP whitelisting where appropriate

## Migration Guide

### From Previous Version
1. **Update Configuration:** Use the setup script to update your `.sbd` file
2. **Test Changes:** Run the test script to verify everything works
3. **Restart Server:** Restart your MCP server with the new configuration
4. **Update Clients:** Update client configurations if needed

### Breaking Changes
- Authentication is now properly enforced in production mode
- Default user context is created automatically in development mode
- Configuration validation is more strict

## Support

### Getting Help
1. **Check Logs:** Look in the `logs/` directory for detailed error messages
2. **Run Tests:** Use `python test_mcp_auth_fix.py` to diagnose issues
3. **Validate Config:** Use `python scripts/setup_mcp_auth.py --test`
4. **Health Check:** Check `/health` endpoint for component status

### Common Solutions
- **Authentication Errors:** Ensure configuration matches your deployment mode
- **Permission Errors:** Check user roles and permissions in the database
- **Connection Errors:** Verify MongoDB and Redis connectivity
- **Token Errors:** Regenerate tokens using the setup script

## Examples

### Tool Implementation
```python
from second_brain_database.integrations.mcp.security import secure_mcp_tool

@secure_mcp_tool(
    permissions=["family:admin"],
    rate_limit_action="family_create",
    audit=True
)
async def create_family(name: str, description: str = None):
    """Create a new family with proper authentication and authorization."""
    # Tool implementation here
    pass
```

### Client Integration
```python
import httpx

async def call_mcp_tool(tool_name: str, args: dict, token: str = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8001/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": args},
                "id": 1
            },
            headers=headers
        )
        return response.json()
```

This comprehensive authentication system ensures your MCP server is both developer-friendly and production-ready with enterprise-grade security.
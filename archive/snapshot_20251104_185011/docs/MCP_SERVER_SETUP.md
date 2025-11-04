# MCP Server Setup Guide

## Overview

The Second Brain Database now includes a production-ready MCP (Model Context Protocol) server that provides access to 138+ tools across 5 categories:

- **Family Management** (25+ tools): Family creation, member management, invitations, SBD tokens
- **Authentication** (30+ tools): Profile management, 2FA, security settings, permanent tokens  
- **Shop & Assets** (35+ tools): Item browsing, purchases, asset management, rentals
- **Workspace** (25+ tools): Team collaboration, workspace management, member roles
- **Admin** (23+ tools): System monitoring, user management, health checks

## Quick Start

### 1. Configuration

Create or update your `.sbd` file with MCP settings:

```bash
# MCP Server Configuration
MCP_ENABLED=true
MCP_SERVER_NAME=SecondBrainMCP
MCP_SERVER_VERSION=1.0.0
MCP_SERVER_HOST=localhost
MCP_SERVER_PORT=3001

# Security Settings
MCP_SECURITY_ENABLED=true
MCP_REQUIRE_AUTH=true
MCP_AUDIT_ENABLED=true
MCP_RATE_LIMIT_ENABLED=true

# Performance Settings
MCP_MAX_CONCURRENT_TOOLS=50
MCP_REQUEST_TIMEOUT=30
MCP_DEBUG_MODE=false

# Required Database Settings
MONGODB_URL=mongodb://localhost:27017
MONGODB_DATABASE=second_brain_database
REDIS_URL=redis://localhost:6379
SECRET_KEY=your-secure-secret-key
FERNET_KEY=your-fernet-encryption-key
```

### 2. Start the Server

#### Option A: Standard Startup (Recommended)
```bash
# Start both FastAPI (port 8000) and MCP server (port 3001)
uv run uvicorn src.second_brain_database.main:app --reload --host 0.0.0.0 --port 8000
```

#### Option B: Production Startup Script
```bash
# Use the production startup script
python start_mcp_server.py
```

### 3. Verify Server Health

```bash
# Test MCP server startup capability
python test_mcp_startup.py

# Check server health after startup
python check_mcp_health.py
```

## VSCode MCP Extension Setup

Once the server is running, configure VSCode MCP extension:

1. Install the MCP extension in VSCode
2. Add server configuration:
   ```json
   {
     "mcp.servers": {
       "SecondBrainMCP": {
         "url": "http://localhost:3001",
         "name": "Second Brain Database",
         "description": "Complete knowledge management and family coordination system"
       }
     }
   }
   ```

## Server Endpoints

The MCP server provides these endpoints:

- `http://localhost:3001/` - Server information
- `http://localhost:3001/health` - Health check
- `http://localhost:3001/tools` - Available tools list
- MCP protocol endpoints for tool execution

## Available Tools by Category

### Family Management Tools
- `get_family_info` - Get family information
- `create_family` - Create new family
- `add_family_member` - Add member to family
- `send_family_invitation` - Send email invitations
- `get_family_sbd_account` - Family token management
- `create_token_request` - Request family tokens
- And 19+ more family tools...

### Authentication Tools
- `get_user_profile` - Get user profile
- `update_user_profile` - Update profile information
- `get_auth_status` - Authentication status
- `setup_2fa` - Two-factor authentication
- `get_security_dashboard` - Security overview
- `change_password` - Password management
- And 24+ more auth tools...

### Shop & Asset Tools
- `list_shop_items` - Browse shop catalog
- `purchase_item` - Buy items
- `get_user_assets` - View owned assets
- `rent_asset` - Rent avatars/banners/themes
- `get_sbd_balance` - Token balance
- `transfer_sbd_tokens` - Token transfers
- And 29+ more shop tools...

### Workspace Tools
- `get_user_workspaces` - List workspaces
- `create_workspace` - Create workspace
- `add_workspace_member` - Add team members
- `get_workspace_wallet` - Workspace finances
- `get_workspace_analytics` - Usage statistics
- And 20+ more workspace tools...

### Admin Tools
- `get_system_health` - System status
- `get_user_list` - User management
- `get_api_metrics` - Performance data
- `suspend_user` - User moderation
- And 19+ more admin tools...

## Security Features

- **JWT Authentication**: All tools require valid authentication
- **Permission-based Access**: Tools check user permissions
- **Rate Limiting**: Prevents abuse with configurable limits
- **Audit Logging**: All tool executions are logged
- **IP Restrictions**: Optional IP-based access control
- **Comprehensive Monitoring**: Performance and error tracking

## Monitoring & Health

The server includes comprehensive monitoring:

- **Health Checks**: `/health` endpoint with detailed status
- **Performance Metrics**: Tool execution times and success rates
- **Error Recovery**: Automatic retry and circuit breaker patterns
- **Alerting**: Critical error notifications
- **Resource Management**: Memory and connection pooling

## Production Deployment

### Docker Deployment
```bash
# Use the provided Docker Compose configuration
docker-compose -f docker-compose.mcp.yml up -d
```

### Manual Production Setup
1. Set `MCP_DEBUG_MODE=false`
2. Configure proper `SECRET_KEY` and `FERNET_KEY`
3. Set up reverse proxy (nginx) for SSL termination
4. Configure monitoring and log aggregation
5. Set up database backups and Redis persistence

## Troubleshooting

### Common Issues

1. **Port 3001 already in use**
   ```bash
   # Check what's using the port
   lsof -i :3001
   # Change MCP_SERVER_PORT in .sbd file
   ```

2. **FastMCP library not found**
   ```bash
   # Install FastMCP
   uv add fastmcp
   ```

3. **Database connection errors**
   - Verify MongoDB is running on configured URL
   - Check Redis connectivity
   - Validate database credentials

4. **Authentication failures**
   - Ensure SECRET_KEY and FERNET_KEY are set
   - Check JWT token validity
   - Verify user permissions

### Health Check Commands

```bash
# Quick health check
curl http://localhost:3001/health

# Detailed server info
curl http://localhost:3001/

# List available tools
curl http://localhost:3001/tools

# FastAPI health check
curl http://localhost:8000/health
```

## Development

### Adding New Tools

1. Create tool function with `@authenticated_tool` decorator
2. Add to appropriate category module
3. Restart server to register new tools
4. Test with health check script

### Custom Resources

1. Add resource function with `@mcp.resource` decorator
2. Follow URI pattern: `category://{id}/resource`
3. Include proper error handling and logging
4. Test resource accessibility

## Support

For issues or questions:
1. Check server logs for detailed error messages
2. Run health check scripts for diagnostics
3. Verify configuration in `.sbd` file
4. Check database and Redis connectivity

The MCP server provides a powerful interface to all Second Brain Database functionality with production-ready security, monitoring, and performance features.
# FastMCP Gateway Integration Documentation

## Overview

The FastMCP Gateway Integration provides a production-ready, security-first MCP (Model Context Protocol) server implementation using the FastMCP framework. This system exposes backend functionality as MCP tools while maintaining enterprise-grade security, auditability, and production resilience.

## Quick Start

### Prerequisites

- Python 3.11+
- MongoDB instance
- Redis instance
- FastMCP framework (`uv add fastmcp`)

### Basic Setup

1. **Install Dependencies**
   ```bash
   uv add fastmcp
   ```

2. **Configure MCP Settings**
   ```bash
   # Add to your .sbd or .env file
   MCP_ENABLED=true
   MCP_SERVER_PORT=3001
   MCP_SECURITY_ENABLED=true
   ```

3. **Start the Application**
   ```bash
   uv run uvicorn src.second_brain_database.main:app --reload
   ```

The MCP server will automatically start alongside the main FastAPI application.

## Documentation Structure

- **[Configuration Guide](./configuration.md)** - Complete MCP server configuration options
- **[Tool Usage Guide](./tools/)** - Comprehensive MCP tool documentation and examples
- **[Deployment Guide](./deployment.md)** - Production deployment, monitoring, and maintenance
- **[Security Guide](./security.md)** - Security configuration and best practices
- **[Troubleshooting](./troubleshooting.md)** - Common issues and solutions

## Key Features

### Security-First Design
- JWT and permanent token authentication
- Role-based access control
- Rate limiting and abuse protection
- Comprehensive audit logging

### Comprehensive Tool Coverage
- **Family Management**: Complete family lifecycle operations
- **Authentication & Profile**: User management and security tools
- **Shop & Assets**: Digital asset management and transactions
- **Workspace & Teams**: Team collaboration and management
- **System Administration**: Health monitoring and user moderation

### Production Ready
- Graceful startup/shutdown integration with FastAPI
- Error recovery with circuit breakers and retry logic
- Performance monitoring and alerting
- Comprehensive health checks

### Developer Friendly
- FastMCP's decorator-based tool registration
- Automatic tool discovery and registration
- Rich resource and prompt system
- Comprehensive error handling

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   MCP Clients   │◄──►│   FastMCP Server │◄──►│ Backend Services│
│                 │    │                  │    │                 │
│ - AI Models     │    │ ┌──────────────┐ │    │ - Family Mgmt   │
│ - External APIs │    │ │ @tool        │ │    │ - Auth Services │
│ - Tools         │    │ │ Decorators   │ │    │ - User Profiles │
└─────────────────┘    │ └──────────────┘ │    │ - Shop Services │
                       │                  │    └─────────────────┘
                       │ ┌──────────────┐ │
                       │ │Security      │ │
                       │ │Wrappers      │ │
                       │ └──────────────┘ │
                       └──────────────────┘
```

## Getting Help

- Check the [Troubleshooting Guide](./troubleshooting.md) for common issues
- Review the [Tool Usage Examples](./tools/) for implementation patterns
- Consult the [Security Guide](./security.md) for security best practices
- See the [Deployment Guide](./deployment.md) for production setup

## Contributing

When adding new MCP tools:

1. Follow the security wrapper patterns in `src/second_brain_database/integrations/mcp/security.py`
2. Use existing manager interfaces for business logic
3. Add comprehensive documentation and examples
4. Include appropriate tests for security and functionality
5. Update this documentation with new tool information

## License

This MCP integration follows the same license as the main Second Brain Database project.
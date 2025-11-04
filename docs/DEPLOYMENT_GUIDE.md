# FastMCP 2.x Production Deployment Guide

## Overview

This guide covers deploying the Second Brain Database MCP server using FastMCP 2.x patterns in production environments.

## Quick Start

### 1. Development (STDIO Transport)

```bash
# Simple STDIO server for local development
python mcp_server.py

# Or using the full startup script
python start_mcp_server.py --transport stdio
```

### 2. Production (HTTP Transport)

```bash
# Set environment variables
export MCP_AUTH_TOKEN="your-secure-bearer-token"
export MCP_SECURITY_ENABLED=true
export MCP_TRANSPORT=http

# Start production server
uvicorn production_app:app --host 0.0.0.0 --port 8001
```

## Deployment Options

### Option 1: Direct FastMCP Run (Simple)

```python
# mcp_server.py
from second_brain_database.integrations.mcp import mcp

if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8001)
```

```bash
python mcp_server.py
```

### Option 2: ASGI Application (Recommended for Production)

```python
# production_app.py
from second_brain_database.integrations.mcp import mcp

app = mcp.http_app()
```

```bash
# Single worker
uvicorn production_app:app --host 0.0.0.0 --port 8001

# Multiple workers (production)
gunicorn production_app:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8001
```

### Option 3: Custom HTTP Server (Advanced)

```bash
python start_mcp_server.py --transport http --host 0.0.0.0 --port 8001
```

## Environment Configuration

### Required Variables

```bash
# Authentication (required for HTTP transport in production)
MCP_AUTH_TOKEN=your-secure-bearer-token

# Security settings
MCP_SECURITY_ENABLED=true
MCP_REQUIRE_AUTH=true

# Transport configuration
MCP_TRANSPORT=http
MCP_HTTP_HOST=0.0.0.0
MCP_HTTP_PORT=8001
```

### Optional Variables

```bash
# CORS (for browser-based clients)
MCP_HTTP_CORS_ENABLED=true
MCP_HTTP_CORS_ORIGINS=https://your-frontend.com,https://api.your-domain.com

# Feature toggles
MCP_TOOLS_ENABLED=true
MCP_RESOURCES_ENABLED=true
MCP_PROMPTS_ENABLED=true

# Monitoring
MCP_METRICS_ENABLED=true
MCP_HEALTH_CHECK_ENABLED=true
```

## Docker Deployment

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . .

# Install dependencies
RUN pip install uv
RUN uv sync --extra production

# Expose port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8001/health || exit 1

# Start server
CMD ["uvicorn", "production_app:app", "--host", "0.0.0.0", "--port", "8001"]
```

### Docker Compose

```yaml
version: '3.8'
services:
  mcp-server:
    build: .
    ports:
      - "8001:8001"
    environment:
      - MCP_AUTH_TOKEN=${MCP_AUTH_TOKEN}
      - MCP_SECURITY_ENABLED=true
      - MCP_TRANSPORT=http
      - MONGODB_URL=mongodb://mongodb:27017
      - REDIS_URL=redis://redis:6379
    depends_on:
      - mongodb
      - redis
    restart: unless-stopped
    
  mongodb:
    image: mongo:7
    restart: unless-stopped
    
  redis:
    image: redis:7-alpine
    restart: unless-stopped
```

## Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mcp-server
spec:
  replicas: 3
  selector:
    matchLabels:
      app: mcp-server
  template:
    metadata:
      labels:
        app: mcp-server
    spec:
      containers:
      - name: mcp-server
        image: your-registry/second-brain-mcp:latest
        ports:
        - containerPort: 8001
        env:
        - name: MCP_AUTH_TOKEN
          valueFrom:
            secretKeyRef:
              name: mcp-secrets
              key: auth-token
        - name: MCP_SECURITY_ENABLED
          value: "true"
        livenessProbe:
          httpGet:
            path: /health
            port: 8001
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8001
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: mcp-server-service
spec:
  selector:
    app: mcp-server
  ports:
  - port: 8001
    targetPort: 8001
  type: LoadBalancer
```

## Client Configuration

### Kiro MCP Configuration

```json
{
  "mcpServers": {
    "second-brain": {
      "url": "http://localhost:8001/mcp",
      "headers": {
        "Authorization": "Bearer your-token"
      }
    }
  }
}
```

### Claude Desktop Configuration

```json
{
  "mcpServers": {
    "second-brain": {
      "command": "python",
      "args": ["mcp_server.py"],
      "cwd": "/path/to/second_brain_database"
    }
  }
}
```

### FastMCP CLI Usage

```bash
# STDIO transport
fastmcp run mcp_server.py:mcp

# HTTP transport
fastmcp run mcp_server.py:mcp --transport http --port 8001
```

## Monitoring & Health Checks

### Endpoints

- `GET /health` - Comprehensive health check
- `GET /metrics` - Prometheus metrics
- `GET /status` - Server status information
- `GET /mcp` - MCP protocol endpoint

### Health Check Response

```json
{
  "status": "healthy",
  "timestamp": "2025-10-30T00:00:00Z",
  "server": {
    "name": "SecondBrainMCP",
    "version": "1.0.0",
    "transport": "http",
    "mcp_protocol": "2024-11-05"
  },
  "components": {
    "mcp": {
      "status": "healthy",
      "auth_enabled": true
    }
  }
}
```

## Testing

### Run Tests

```bash
# Start server
python start_mcp_server.py --transport http --host 127.0.0.1 --port 8001

# Run tests (in another terminal)
python test_modern_mcp.py --url http://localhost:8001
```

### Manual Testing

```bash
# Test health
curl http://localhost:8001/health

# Test MCP protocol
curl -X POST http://localhost:8001/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-token" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'
```

## Security Best Practices

1. **Always use authentication in production**
2. **Use HTTPS with reverse proxy**
3. **Set strong bearer tokens**
4. **Enable CORS only when needed**
5. **Monitor authentication failures**
6. **Keep dependencies updated**

## Troubleshooting

### Common Issues

1. **Authentication errors**: Check MCP_AUTH_TOKEN is set
2. **CORS errors**: Verify MCP_HTTP_CORS_ENABLED and origins
3. **Port conflicts**: Ensure port 8001 is available
4. **Import errors**: Run `uv sync --extra dev`

### Debug Mode

```bash
export MCP_DEBUG_MODE=true
python start_mcp_server.py --transport http
```

## Performance Tuning

### Production Settings

```bash
# Resource limits
export MCP_MAX_CONCURRENT_TOOLS=100
export MCP_REQUEST_TIMEOUT=30

# Uvicorn optimization
uvicorn production_app:app \
  --host 0.0.0.0 \
  --port 8001 \
  --workers 4 \
  --loop uvloop \
  --http httptools
```

This deployment guide provides comprehensive instructions for deploying the FastMCP 2.x server in various environments while following best practices.
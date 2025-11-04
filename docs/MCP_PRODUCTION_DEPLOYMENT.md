# MCP Server Production Deployment Guide

## Overview

This guide covers deploying the Second Brain Database MCP server in production with both STDIO and HTTP transports.

## Transport Options

### STDIO Transport (Recommended for Local AI Clients)

**Use Cases:**
- Local AI clients (Kiro, Claude Desktop, VSCode extensions)
- Development environments
- Single-user deployments

**Configuration:**
```bash
# Start STDIO server
python start_mcp_server.py --transport stdio

# MCP Client Configuration
{
  "mcpServers": {
    "second-brain": {
      "command": "python",
      "args": ["start_mcp_server.py", "--transport", "stdio"],
      "cwd": "/path/to/second_brain_database"
    }
  }
}
```

### HTTP Transport (Production & Remote Clients)

**Use Cases:**
- Remote AI clients
- Web applications
- Microservices architecture
- Multi-user deployments
- Load balancing scenarios

**Configuration:**
```bash
# Development
python start_mcp_server.py --transport http --host 127.0.0.1 --port 8001

# Production
python start_mcp_server.py --transport http --host 0.0.0.0 --port 8001
```

## Production Configuration

### Environment Variables

```bash
# MCP Transport Configuration
MCP_TRANSPORT=http
MCP_HTTP_HOST=0.0.0.0
MCP_HTTP_PORT=8001
MCP_HTTP_CORS_ENABLED=true
MCP_HTTP_CORS_ORIGINS=https://your-frontend.com,https://api.your-domain.com

# Security Configuration
MCP_SECURITY_ENABLED=true
MCP_REQUIRE_AUTH=true
SECRET_KEY=your-production-jwt-secret
FERNET_KEY=your-production-fernet-key

# Database Configuration
MONGODB_URL=mongodb://your-production-mongodb:27017
MONGODB_DATABASE=second_brain_prod
REDIS_URL=redis://your-production-redis:6379

# Monitoring Configuration
MCP_METRICS_ENABLED=true
MCP_HEALTH_CHECK_ENABLED=true
MCP_PERFORMANCE_MONITORING=true
```

### Docker Deployment

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . .

# Install dependencies
RUN pip install uv
RUN uv sync --extra production

# Expose HTTP port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8001/health || exit 1

# Start MCP server
CMD ["python", "start_mcp_server.py", "--transport", "http", "--host", "0.0.0.0", "--port", "8001"]
```

```yaml
# docker-compose.yml
version: '3.8'
services:
  mcp-server:
    build: .
    ports:
      - "8001:8001"
    environment:
      - MCP_TRANSPORT=http
      - MCP_HTTP_HOST=0.0.0.0
      - MCP_HTTP_PORT=8001
      - MCP_SECURITY_ENABLED=true
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

### Kubernetes Deployment

```yaml
# k8s-deployment.yaml
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
        - name: MCP_TRANSPORT
          value: "http"
        - name: MCP_HTTP_HOST
          value: "0.0.0.0"
        - name: MCP_HTTP_PORT
          value: "8001"
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

## Monitoring & Observability

### Health Checks

```bash
# Basic health check
curl http://localhost:8001/health

# Detailed health with components
curl http://localhost:8001/health | jq .

# Prometheus metrics
curl http://localhost:8001/metrics
```

### Logging

The MCP server integrates with your existing logging infrastructure:

- **Console logs**: Development and debugging
- **Loki integration**: Centralized log aggregation
- **Structured logging**: JSON format for production
- **Log levels**: Configurable via environment

### Metrics

Available metrics endpoints:

- `/health` - Health check with component status
- `/metrics` - Prometheus-compatible metrics
- WebSocket monitoring integration
- Performance monitoring via `monitoring.py`

## Security Considerations

### Authentication

- **JWT tokens**: Production authentication
- **Static tokens**: Development only
- **Bearer token auth**: HTTP transport
- **IP restrictions**: Configurable IP allowlists

### Network Security

```bash
# Firewall rules (example for Ubuntu/CentOS)
# Allow MCP HTTP port
sudo ufw allow 8001/tcp

# Restrict to specific IPs (production)
sudo ufw allow from 10.0.0.0/8 to any port 8001
```

### TLS/SSL

For production HTTP transport, use a reverse proxy:

```nginx
# nginx.conf
server {
    listen 443 ssl http2;
    server_name mcp.your-domain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Performance Tuning

### Resource Limits

```bash
# Set resource limits
export MCP_MAX_CONCURRENT_TOOLS=100
export MCP_REQUEST_TIMEOUT=30
export MCP_TOOL_EXECUTION_TIMEOUT=60
```

### Scaling

- **Horizontal scaling**: Multiple MCP server instances behind load balancer
- **Vertical scaling**: Increase CPU/memory for single instance
- **Database scaling**: MongoDB replica sets, Redis clustering
- **Caching**: Redis-based caching for frequently accessed data

## Troubleshooting

### Common Issues

1. **Port conflicts**: Check if port 8001 is available
2. **Authentication failures**: Verify JWT secrets and tokens
3. **Database connections**: Check MongoDB/Redis connectivity
4. **Memory issues**: Monitor resource usage via `/metrics`

### Debug Mode

```bash
# Enable debug logging
export MCP_DEBUG_MODE=true
python start_mcp_server.py --transport http --host 127.0.0.1 --port 8001
```

### Health Check Failures

```bash
# Check component health
curl http://localhost:8001/health | jq '.components'

# Check logs
tail -f logs/mcp_server.log

# Check metrics
curl http://localhost:8001/metrics | grep mcp_
```

## Client Integration Examples

### Web Application

```javascript
// JavaScript client example
const mcpClient = {
  baseUrl: 'https://mcp.your-domain.com',
  
  async callTool(toolName, args) {
    const response = await fetch(`${this.baseUrl}/mcp`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer your-token'
      },
      body: JSON.stringify({
        jsonrpc: '2.0',
        method: 'tools/call',
        params: { name: toolName, arguments: args },
        id: Date.now()
      })
    });
    return response.json();
  }
};
```

### Python Client

```python
# Python client example
import httpx

class MCPClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url
        self.token = token
        
    async def call_tool(self, tool_name: str, args: dict):
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/mcp",
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {"name": tool_name, "arguments": args},
                    "id": 1
                },
                headers={"Authorization": f"Bearer {self.token}"}
            )
            return response.json()
```

## Best Practices

1. **Use STDIO for local clients** - Better performance and security
2. **Use HTTP for remote/web clients** - Better for distributed architectures
3. **Enable authentication in production** - Always use JWT tokens
4. **Monitor health endpoints** - Set up alerting on health check failures
5. **Use TLS in production** - Never expose HTTP transport without TLS
6. **Implement proper logging** - Use structured logging for production
7. **Set resource limits** - Prevent resource exhaustion
8. **Regular backups** - Backup MongoDB and configuration
9. **Update dependencies** - Keep FastMCP and dependencies updated
10. **Test deployments** - Always test in staging before production

## Support

For deployment issues:
- Check the health endpoint: `/health`
- Review logs in `logs/` directory
- Monitor metrics at `/metrics`
- Consult the troubleshooting section above
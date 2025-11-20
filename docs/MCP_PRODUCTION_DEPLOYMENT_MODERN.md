# Modern FastMCP 2.x Production Deployment Guide

## Overview

This guide covers deploying the modernized Second Brain Database MCP server using FastMCP 2.x patterns with both STDIO and HTTP transports, WebSocket support, and production-ready features.

## Key Improvements

### ✅ Modern FastMCP 2.x Integration
- Native FastMCP HTTP app integration
- Proper authentication with Bearer tokens
- Modern middleware and security patterns
- Production-ready ASGI application

### ✅ Enhanced WebSocket Support
- Real-time MCP protocol communication
- Integration with existing AI orchestration system
- Session management and authentication
- Event broadcasting and monitoring

### ✅ Production Security
- Bearer token authentication for HTTP transport
- CORS configuration for browser-based clients
- Security headers and production optimizations
- Environment-based configuration

### ✅ Comprehensive Monitoring
- Health check endpoints with component status
- Prometheus-compatible metrics
- Integration with existing monitoring systems
- Performance tracking and alerting

## Transport Options

### STDIO Transport (Local Development)

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
MCP_AUTH_TOKEN=your-production-bearer-token
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

# Install dependencies with uv
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
      - MCP_AUTH_TOKEN=${MCP_AUTH_TOKEN}
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
        - name: MCP_SECURITY_ENABLED
          value: "true"
        - name: MCP_AUTH_TOKEN
          valueFrom:
            secretKeyRef:
              name: mcp-secrets
              key: auth-token
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
---
apiVersion: v1
kind: Secret
metadata:
  name: mcp-secrets
type: Opaque
data:
  auth-token: <base64-encoded-token>
```

## WebSocket Integration

### Real-time MCP Communication

The modern implementation includes WebSocket support for real-time MCP protocol communication:

```javascript
// JavaScript WebSocket client example
const ws = new WebSocket('ws://localhost:8001/mcp/ws');

ws.onopen = function() {
    // Initialize MCP session
    ws.send(JSON.stringify({
        jsonrpc: "2.0",
        method: "initialize",
        params: {
            protocolVersion: "2024-11-05",
            capabilities: {},
            clientInfo: {
                name: "WebSocket Client",
                version: "1.0.0"
            }
        },
        id: 1
    }));
};

ws.onmessage = function(event) {
    const response = JSON.parse(event.data);
    console.log('MCP Response:', response);
};
```

### Integration with AI Orchestration

The WebSocket implementation integrates with the existing AI orchestration system:

- **Event Bus Integration**: MCP WebSocket sessions are registered with the AI event bus
- **Real-time Tool Tracking**: Tool execution events are broadcast to connected clients
- **Session Management**: Unified session management across MCP and AI systems
- **Authentication**: Integrated with existing security infrastructure

## Monitoring & Observability

### Health Checks

```bash
# Basic health check
curl http://localhost:8001/health

# Detailed health with components
curl http://localhost:8001/health | jq .

# Server status
curl http://localhost:8001/status

# Prometheus metrics
curl http://localhost:8001/metrics
```

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
      "server_name": "SecondBrainMCP",
      "server_version": "1.0.0",
      "auth_enabled": true
    },
    "monitoring": {
      "status": "healthy"
    }
  }
}
```

### Logging

The MCP server integrates with your existing logging infrastructure:

- **Structured logging**: JSON format for production
- **Log levels**: Configurable via environment
- **Component-specific logging**: Separate loggers for different components
- **Performance logging**: Request/response timing and metrics

## Security Considerations

### Authentication

```bash
# Bearer token authentication for HTTP transport
export MCP_AUTH_TOKEN="your-secure-bearer-token"

# Client configuration with authentication
{
  "mcpServers": {
    "second-brain": {
      "url": "http://localhost:8001/mcp",
      "headers": {
        "Authorization": "Bearer your-secure-bearer-token"
      }
    }
  }
}
```

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
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
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

## Client Integration Examples

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
      "args": ["start_mcp_server.py", "--transport", "stdio"],
      "cwd": "/path/to/second_brain_database"
    }
  }
}
```

### Web Application Integration

```javascript
// Modern fetch-based client
class MCPClient {
    constructor(baseUrl, token) {
        this.baseUrl = baseUrl;
        this.token = token;
    }
    
    async callTool(toolName, args) {
        const response = await fetch(`${this.baseUrl}/mcp`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${this.token}`,
                'mcp-protocol-version': '2024-11-05'
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
}
```

## Troubleshooting

### Common Issues

1. **Authentication failures**: Verify MCP_AUTH_TOKEN is set correctly
2. **CORS errors**: Check MCP_HTTP_CORS_ENABLED and origins configuration
3. **WebSocket connection failures**: Ensure proper proxy configuration for WebSocket upgrade
4. **Health check failures**: Check component status in health endpoint response

### Debug Mode

```bash
# Enable debug logging
export MCP_DEBUG_MODE=true
python start_mcp_server.py --transport http --host 127.0.0.1 --port 8001
```

### Validation Commands

```bash
# Test MCP protocol
curl -X POST http://localhost:8001/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-token" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'

# Test WebSocket (using wscat)
wscat -c ws://localhost:8001/mcp/ws

# Check server status
curl http://localhost:8001/status | jq .
```

## Migration from Legacy Implementation

### Key Changes

1. **FastMCP 2.x Native Integration**: Uses FastMCP's native HTTP app instead of custom implementation
2. **Modern Authentication**: Bearer token authentication for HTTP transport
3. **Enhanced WebSocket**: Proper MCP protocol WebSocket support with session management
4. **Production Optimizations**: Better error handling, monitoring, and performance tuning

### Migration Steps

1. Update environment variables to include `MCP_AUTH_TOKEN`
2. Test STDIO transport first (no breaking changes)
3. Test HTTP transport with authentication
4. Update client configurations to include Bearer token
5. Deploy with monitoring and health checks

## Best Practices

1. **Use STDIO for local development** - Better performance and security
2. **Use HTTP for production deployments** - Better for distributed architectures
3. **Always enable authentication in production** - Use strong Bearer tokens
4. **Monitor health endpoints** - Set up alerting on health check failures
5. **Use TLS in production** - Never expose HTTP transport without TLS
6. **Implement proper logging** - Use structured logging for production
7. **Set resource limits** - Prevent resource exhaustion
8. **Regular security updates** - Keep FastMCP and dependencies updated
9. **Test WebSocket functionality** - Ensure real-time features work correctly
10. **Monitor performance metrics** - Track request latency and throughput

## Support

For deployment issues:
- Check the health endpoint: `/health`
- Review server status: `/status`
- Monitor metrics at `/metrics`
- Check logs for detailed error information
- Consult the troubleshooting section above

The modern FastMCP 2.x implementation provides a robust, production-ready MCP server with comprehensive monitoring, security, and real-time communication capabilities.
# MCP Server Deployment Guide

## Overview

This guide covers production deployment, monitoring, and maintenance of the FastMCP Gateway Integration. The MCP server is designed to integrate seamlessly with existing FastAPI infrastructure while providing enterprise-grade reliability and security.

## Deployment Architecture

### Production Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Load Balancer │    │   FastAPI App    │    │   MCP Clients   │
│   (nginx/ALB)   │◄──►│   + MCP Server   │◄──►│   (AI Models)   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                       ┌────────┴────────┐
                       │                 │
                ┌──────▼──────┐   ┌──────▼──────┐
                │   MongoDB   │   │    Redis    │
                │  (Primary)  │   │  (Cache)    │
                └─────────────┘   └─────────────┘
```

### Container Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Container                         │
│  ┌─────────────────┐  ┌─────────────────┐                  │
│  │   FastAPI App   │  │   MCP Server    │                  │
│  │   Port: 8000    │  │   Port: 3001    │                  │
│  └─────────────────┘  └─────────────────┘                  │
│                                                             │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              Shared Resources                           │ │
│  │  - Database connections                                 │ │
│  │  - Redis connections                                    │ │
│  │  - Logging infrastructure                              │ │
│  │  - Security managers                                   │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Docker Deployment

### Dockerfile Configuration

The existing Dockerfile already supports MCP server deployment:

```dockerfile
# Multi-stage build for production
FROM python:3.11-slim as builder

# Install uv for dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-cache

# Production stage
FROM python:3.11-slim

# Copy virtual environment
COPY --from=builder /.venv /.venv
ENV PATH="/.venv/bin:$PATH"

# Copy application code
COPY src/ /app/src/
WORKDIR /app

# Expose both FastAPI and MCP ports
EXPOSE 8000 3001

# Health check for both services
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health && \
        curl -f http://localhost:8000/health/mcp || exit 1

# Start application with MCP server
CMD ["uvicorn", "src.second_brain_database.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Docker Compose Configuration

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8000:8000"
      - "3001:3001"
    environment:
      # Core application settings
      - SECRET_KEY=${SECRET_KEY}
      - MONGODB_URL=mongodb://mongodb:27017
      - MONGODB_DATABASE=${MONGODB_DATABASE}
      - REDIS_URL=redis://redis:6379
      
      # MCP server settings
      - MCP_ENABLED=true
      - MCP_SERVER_PORT=3001
      - MCP_SECURITY_ENABLED=true
      - MCP_RATE_LIMIT_ENABLED=true
      - MCP_AUDIT_ENABLED=true
      
      # Production security settings
      - MCP_DEBUG_MODE=false
      - MCP_ADMIN_TOOLS_ENABLED=false
      - MCP_REQUIRE_AUTH=true
    depends_on:
      - mongodb
      - redis
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  mongodb:
    image: mongo:7.0
    environment:
      - MONGO_INITDB_ROOT_USERNAME=${MONGO_ROOT_USERNAME}
      - MONGO_INITDB_ROOT_PASSWORD=${MONGO_ROOT_PASSWORD}
    volumes:
      - mongodb_data:/data/db
    restart: unless-stopped

  redis:
    image: redis:7.2-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - app
    restart: unless-stopped

volumes:
  mongodb_data:
  redis_data:
```

### Environment Configuration

```bash
# .env.production
# Core application
SECRET_KEY=your-production-secret-key
MONGODB_URL=mongodb://mongodb:27017
MONGODB_DATABASE=second_brain_prod
REDIS_URL=redis://redis:6379

# Database credentials
MONGO_ROOT_USERNAME=admin
MONGO_ROOT_PASSWORD=secure-password

# MCP server configuration
MCP_ENABLED=true
MCP_SERVER_NAME=SecondBrainMCP
MCP_SERVER_PORT=3001
MCP_SECURITY_ENABLED=true
MCP_REQUIRE_AUTH=true
MCP_AUDIT_ENABLED=true

# Rate limiting
MCP_RATE_LIMIT_ENABLED=true
MCP_RATE_LIMIT_REQUESTS=100
MCP_RATE_LIMIT_PERIOD=60

# Security settings
MCP_DEBUG_MODE=false
MCP_ADMIN_TOOLS_ENABLED=false
MCP_IP_LOCKDOWN_ENABLED=true
MCP_ALLOWED_ORIGINS=https://yourdomain.com

# Performance settings
MCP_MAX_CONCURRENT_TOOLS=50
MCP_REQUEST_TIMEOUT=30
```

## Kubernetes Deployment

### Deployment Manifest

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: second-brain-mcp
  labels:
    app: second-brain-mcp
spec:
  replicas: 3
  selector:
    matchLabels:
      app: second-brain-mcp
  template:
    metadata:
      labels:
        app: second-brain-mcp
    spec:
      containers:
      - name: app
        image: second-brain-database:latest
        ports:
        - containerPort: 8000
          name: fastapi
        - containerPort: 3001
          name: mcp
        env:
        - name: SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: app-secrets
              key: secret-key
        - name: MONGODB_URL
          value: "mongodb://mongodb-service:27017"
        - name: REDIS_URL
          value: "redis://redis-service:6379"
        - name: MCP_ENABLED
          value: "true"
        - name: MCP_SERVER_PORT
          value: "3001"
        - name: MCP_SECURITY_ENABLED
          value: "true"
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: second-brain-mcp-service
spec:
  selector:
    app: second-brain-mcp
  ports:
  - name: fastapi
    port: 8000
    targetPort: 8000
  - name: mcp
    port: 3001
    targetPort: 3001
  type: ClusterIP
```

### ConfigMap for MCP Settings

```yaml
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: mcp-config
data:
  MCP_ENABLED: "true"
  MCP_SERVER_NAME: "SecondBrainMCP"
  MCP_SERVER_PORT: "3001"
  MCP_SECURITY_ENABLED: "true"
  MCP_RATE_LIMIT_ENABLED: "true"
  MCP_RATE_LIMIT_REQUESTS: "100"
  MCP_RATE_LIMIT_PERIOD: "60"
  MCP_MAX_CONCURRENT_TOOLS: "50"
  MCP_REQUEST_TIMEOUT: "30"
  MCP_DEBUG_MODE: "false"
  MCP_ADMIN_TOOLS_ENABLED: "false"
```

### Ingress Configuration

```yaml
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: second-brain-mcp-ingress
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/rate-limit: "100"
    nginx.ingress.kubernetes.io/rate-limit-window: "1m"
spec:
  tls:
  - hosts:
    - api.yourdomain.com
    secretName: api-tls
  rules:
  - host: api.yourdomain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: second-brain-mcp-service
            port:
              number: 8000
      - path: /mcp
        pathType: Prefix
        backend:
          service:
            name: second-brain-mcp-service
            port:
              number: 3001
```

## Load Balancer Configuration

### Nginx Configuration

```nginx
# nginx.conf
upstream fastapi_backend {
    server app:8000;
}

upstream mcp_backend {
    server app:3001;
}

server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;

    # FastAPI routes
    location / {
        proxy_pass http://fastapi_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # MCP server routes
    location /mcp/ {
        proxy_pass http://mcp_backend/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support for MCP
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # MCP-specific timeouts
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }

    # Health checks
    location /health {
        proxy_pass http://fastapi_backend/health;
        access_log off;
    }

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req_zone $binary_remote_addr zone=mcp:10m rate=5r/s;

    location /api/ {
        limit_req zone=api burst=20 nodelay;
        proxy_pass http://fastapi_backend/api/;
    }

    location /mcp/ {
        limit_req zone=mcp burst=10 nodelay;
        proxy_pass http://mcp_backend/;
    }
}
```

## Monitoring and Observability

### Health Check Endpoints

The MCP integration provides comprehensive health checks:

```python
# Health check endpoints (already implemented)
GET /health/mcp/server    # MCP server status
GET /health/mcp/tools     # Available tools
GET /health/mcp/metrics   # Performance metrics
```

### Prometheus Metrics

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'second-brain-mcp'
    static_configs:
      - targets: ['app:8000']
    metrics_path: '/metrics'
    scrape_interval: 30s

  - job_name: 'mcp-server'
    static_configs:
      - targets: ['app:3001']
    metrics_path: '/metrics'
    scrape_interval: 30s
```

### Grafana Dashboard

```json
{
  "dashboard": {
    "title": "FastMCP Gateway Metrics",
    "panels": [
      {
        "title": "MCP Tool Execution Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(mcp_tool_executions_total[5m])",
            "legendFormat": "{{tool_name}}"
          }
        ]
      },
      {
        "title": "MCP Authentication Success Rate",
        "type": "stat",
        "targets": [
          {
            "expr": "rate(mcp_auth_success_total[5m]) / rate(mcp_auth_attempts_total[5m])",
            "legendFormat": "Success Rate"
          }
        ]
      },
      {
        "title": "MCP Error Rate by Tool",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(mcp_tool_errors_total[5m])",
            "legendFormat": "{{tool_name}} - {{error_type}}"
          }
        ]
      }
    ]
  }
}
```

### Logging Configuration

```yaml
# logging.yaml
version: 1
disable_existing_loggers: false

formatters:
  detailed:
    format: '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
  json:
    format: '{"timestamp": "%(asctime)s", "logger": "%(name)s", "level": "%(levelname)s", "message": "%(message)s", "module": "%(module)s"}'

handlers:
  console:
    class: logging.StreamHandler
    level: INFO
    formatter: detailed
    stream: ext://sys.stdout

  file:
    class: logging.handlers.RotatingFileHandler
    level: DEBUG
    formatter: json
    filename: /app/logs/mcp.log
    maxBytes: 10485760  # 10MB
    backupCount: 5

  syslog:
    class: logging.handlers.SysLogHandler
    level: WARNING
    formatter: json
    address: ['localhost', 514]

loggers:
  second_brain_database.integrations.mcp:
    level: DEBUG
    handlers: [console, file, syslog]
    propagate: false

  fastmcp:
    level: INFO
    handlers: [console, file]
    propagate: false

root:
  level: INFO
  handlers: [console]
```

## Security Hardening

### Network Security

```bash
# Firewall rules (iptables)
# Allow FastAPI port
iptables -A INPUT -p tcp --dport 8000 -j ACCEPT

# Allow MCP port (restrict to specific IPs if needed)
iptables -A INPUT -p tcp --dport 3001 -s 10.0.0.0/8 -j ACCEPT
iptables -A INPUT -p tcp --dport 3001 -j DROP

# Allow health checks
iptables -A INPUT -p tcp --dport 8000 -m string --string "/health" -j ACCEPT
```

### SSL/TLS Configuration

```nginx
# SSL configuration in nginx
ssl_protocols TLSv1.2 TLSv1.3;
ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
ssl_prefer_server_ciphers off;
ssl_session_cache shared:SSL:10m;
ssl_session_timeout 10m;

# HSTS
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

# Security headers
add_header X-Frame-Options DENY always;
add_header X-Content-Type-Options nosniff always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
```

### Container Security

```dockerfile
# Security-hardened Dockerfile
FROM python:3.11-slim

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Install security updates
RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Copy application with proper ownership
COPY --chown=appuser:appuser src/ /app/src/
WORKDIR /app

# Switch to non-root user
USER appuser

# Remove unnecessary capabilities
RUN setcap -r /usr/local/bin/python3.11 || true

EXPOSE 8000 3001
CMD ["uvicorn", "src.second_brain_database.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Backup and Disaster Recovery

### Database Backup

```bash
#!/bin/bash
# backup-mongodb.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups/mongodb"
MONGO_HOST="mongodb"
MONGO_DB="second_brain_prod"

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup MongoDB
mongodump --host $MONGO_HOST --db $MONGO_DB --out $BACKUP_DIR/mongodb_$DATE

# Compress backup
tar -czf $BACKUP_DIR/mongodb_$DATE.tar.gz -C $BACKUP_DIR mongodb_$DATE
rm -rf $BACKUP_DIR/mongodb_$DATE

# Upload to S3 (optional)
aws s3 cp $BACKUP_DIR/mongodb_$DATE.tar.gz s3://your-backup-bucket/mongodb/

# Cleanup old backups (keep last 7 days)
find $BACKUP_DIR -name "mongodb_*.tar.gz" -mtime +7 -delete
```

### Configuration Backup

```bash
#!/bin/bash
# backup-config.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups/config"

mkdir -p $BACKUP_DIR

# Backup configuration files
tar -czf $BACKUP_DIR/config_$DATE.tar.gz \
    /app/.env.production \
    /app/docker-compose.prod.yml \
    /etc/nginx/nginx.conf \
    /app/k8s/

# Upload to S3
aws s3 cp $BACKUP_DIR/config_$DATE.tar.gz s3://your-backup-bucket/config/
```

### Disaster Recovery Plan

1. **Database Recovery**
   ```bash
   # Restore MongoDB from backup
   mongorestore --host mongodb --db second_brain_prod /backups/mongodb_latest/second_brain_prod
   ```

2. **Application Recovery**
   ```bash
   # Pull latest image
   docker pull second-brain-database:latest
   
   # Restore configuration
   tar -xzf config_latest.tar.gz -C /
   
   # Restart services
   docker-compose -f docker-compose.prod.yml up -d
   ```

3. **Verification Steps**
   ```bash
   # Check application health
   curl -f http://localhost:8000/health
   
   # Check MCP server health
   curl -f http://localhost:8000/health/mcp/server
   
   # Verify database connectivity
   curl -f http://localhost:8000/health/database
   ```

## Maintenance Procedures

### Rolling Updates

```bash
#!/bin/bash
# rolling-update.sh

# Build new image
docker build -t second-brain-database:new .

# Update one instance at a time
for i in {1..3}; do
    echo "Updating instance $i"
    
    # Stop instance
    docker stop second-brain-mcp-$i
    
    # Start with new image
    docker run -d --name second-brain-mcp-$i \
        --env-file .env.production \
        second-brain-database:new
    
    # Wait for health check
    sleep 30
    
    # Verify health
    if ! curl -f http://localhost:8000/health; then
        echo "Health check failed for instance $i"
        exit 1
    fi
    
    echo "Instance $i updated successfully"
done
```

### Database Maintenance

```bash
#!/bin/bash
# db-maintenance.sh

# Compact database
mongo --eval "db.runCommand({compact: 'families'})"
mongo --eval "db.runCommand({compact: 'users'})"

# Rebuild indexes
mongo --eval "db.families.reIndex()"
mongo --eval "db.users.reIndex()"

# Update statistics
mongo --eval "db.runCommand({planCacheClear: 'families'})"
```

### Log Rotation

```bash
# /etc/logrotate.d/mcp-server
/app/logs/mcp.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 appuser appuser
    postrotate
        /usr/bin/docker kill -s USR1 $(docker ps -q --filter name=second-brain-mcp)
    endscript
}
```

## Performance Tuning

### Application Tuning

```bash
# Environment variables for performance
MCP_MAX_CONCURRENT_TOOLS=100
MCP_REQUEST_TIMEOUT=60
MCP_CONNECTION_POOL_SIZE=20
MCP_CACHE_TTL=300

# Uvicorn workers
uvicorn src.second_brain_database.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker
```

### Database Optimization

```javascript
// MongoDB indexes for MCP operations
db.families.createIndex({"owner_id": 1, "created_at": -1})
db.families.createIndex({"members.user_id": 1})
db.mcp_audit_log.createIndex({"timestamp": -1, "user_id": 1})
db.mcp_audit_log.createIndex({"tool_name": 1, "timestamp": -1})

// TTL index for audit logs (90 days)
db.mcp_audit_log.createIndex({"timestamp": 1}, {expireAfterSeconds: 7776000})
```

### Redis Configuration

```redis
# redis.conf optimizations
maxmemory 2gb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
```

## Troubleshooting

### Common Issues

1. **MCP Server Won't Start**
   ```bash
   # Check logs
   docker logs second-brain-mcp
   
   # Verify configuration
   docker exec second-brain-mcp env | grep MCP_
   
   # Test connectivity
   docker exec second-brain-mcp curl -f http://localhost:3001/health
   ```

2. **Authentication Failures**
   ```bash
   # Check JWT configuration
   docker exec second-brain-mcp python -c "from src.second_brain_database.config import settings; print(settings.SECRET_KEY[:10])"
   
   # Verify database connectivity
   docker exec second-brain-mcp python -c "from src.second_brain_database.database import db_manager; print(db_manager.client.server_info())"
   ```

3. **Performance Issues**
   ```bash
   # Monitor resource usage
   docker stats second-brain-mcp
   
   # Check MCP metrics
   curl http://localhost:8000/health/mcp/metrics
   
   # Review slow queries
   docker exec mongodb mongo --eval "db.setProfilingLevel(2, {slowms: 100})"
   ```

### Debug Mode

```bash
# Enable debug mode
MCP_DEBUG_MODE=true docker-compose up -d

# View detailed logs
docker logs -f second-brain-mcp | grep MCP
```

This comprehensive deployment guide ensures reliable, secure, and maintainable production deployment of the FastMCP Gateway Integration.
# OAuth2 Provider Configuration Guide

## Overview

This guide covers how to configure and deploy the Second Brain Database OAuth2 authorization server. The OAuth2 provider is built into the main application and can be enabled and configured through environment variables and settings.

## Table of Contents

1. [Environment Configuration](#environment-configuration)
2. [OAuth2 Settings](#oauth2-settings)
3. [Security Configuration](#security-configuration)
4. [Database Configuration](#database-configuration)
5. [Redis Configuration](#redis-configuration)
6. [Deployment Configuration](#deployment-configuration)
7. [Monitoring and Logging](#monitoring-and-logging)
8. [Performance Tuning](#performance-tuning)
9. [Troubleshooting](#troubleshooting)

## Environment Configuration

### Required Environment Variables

The OAuth2 provider requires the following environment variables to be set:

```bash
# Core Application Settings
SECRET_KEY=your-jwt-secret-key-here
FERNET_KEY=your-fernet-encryption-key-here

# Database Configuration
MONGODB_URL=mongodb://localhost:27017
MONGODB_DATABASE=second_brain_database

# Redis Configuration (required for OAuth2 token storage)
REDIS_URL=redis://localhost:6379

# OAuth2 Specific Settings (optional, defaults provided)
OAUTH2_ENABLED=true
OAUTH2_ACCESS_TOKEN_EXPIRE_MINUTES=60
OAUTH2_REFRESH_TOKEN_EXPIRE_DAYS=30
OAUTH2_AUTHORIZATION_CODE_EXPIRE_MINUTES=10
OAUTH2_RATE_LIMIT_ENABLED=true
OAUTH2_AUDIT_LOGGING_ENABLED=true
```

### Configuration File

You can also use a configuration file (`.sbd` or `.env`) instead of environment variables:

```ini
# .sbd configuration file
SECRET_KEY=your-jwt-secret-key-here
FERNET_KEY=your-fernet-encryption-key-here
MONGODB_URL=mongodb://localhost:27017
MONGODB_DATABASE=second_brain_database
REDIS_URL=redis://localhost:6379

# OAuth2 Configuration
OAUTH2_ENABLED=true
OAUTH2_ACCESS_TOKEN_EXPIRE_MINUTES=60
OAUTH2_REFRESH_TOKEN_EXPIRE_DAYS=30
OAUTH2_AUTHORIZATION_CODE_EXPIRE_MINUTES=10
OAUTH2_RATE_LIMIT_ENABLED=true
OAUTH2_AUDIT_LOGGING_ENABLED=true
```

## OAuth2 Settings

### Core OAuth2 Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `OAUTH2_ENABLED` | `true` | Enable/disable OAuth2 provider functionality |
| `OAUTH2_ISSUER` | Application URL | OAuth2 issuer identifier (usually your domain) |
| `OAUTH2_ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Access token lifetime in minutes |
| `OAUTH2_REFRESH_TOKEN_EXPIRE_DAYS` | `30` | Refresh token lifetime in days |
| `OAUTH2_AUTHORIZATION_CODE_EXPIRE_MINUTES` | `10` | Authorization code lifetime in minutes |

### Security Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `OAUTH2_REQUIRE_PKCE` | `true` | Require PKCE for all authorization flows |
| `OAUTH2_REQUIRE_STATE` | `true` | Require state parameter for CSRF protection |
| `OAUTH2_ENCRYPT_TOKENS` | `true` | Encrypt refresh tokens and auth codes at rest |
| `OAUTH2_ROTATE_REFRESH_TOKENS` | `true` | Rotate refresh tokens on each use |

### Rate Limiting Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `OAUTH2_RATE_LIMIT_ENABLED` | `true` | Enable rate limiting for OAuth2 endpoints |
| `OAUTH2_AUTHORIZE_RATE_LIMIT` | `100/5min` | Rate limit for authorization endpoint |
| `OAUTH2_TOKEN_RATE_LIMIT` | `200/5min` | Rate limit for token endpoint |
| `OAUTH2_CLIENT_REGISTRATION_RATE_LIMIT` | `10/1hour` | Rate limit for client registration |

### Scope Configuration

Configure available OAuth2 scopes:

```python
# In your application settings
OAUTH2_AVAILABLE_SCOPES = {
    "read:profile": "Read user profile information",
    "write:profile": "Update user profile information", 
    "read:data": "Read user's stored data and documents",
    "write:data": "Create, update, and delete user data",
    "read:tokens": "View user's API tokens",
    "write:tokens": "Create and manage user API tokens",
    "admin": "Administrative access (restricted)"
}

OAUTH2_DEFAULT_SCOPES = ["read:profile"]
```

## Security Configuration

### HTTPS Requirements

OAuth2 requires HTTPS in production. Configure your reverse proxy or load balancer:

#### Nginx Configuration

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    ssl_certificate /path/to/certificate.crt;
    ssl_certificate_key /path/to/private.key;
    
    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options DENY always;
    add_header X-XSS-Protection "1; mode=block" always;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

#### Apache Configuration

```apache
<VirtualHost *:443>
    ServerName your-domain.com
    
    SSLEngine on
    SSLCertificateFile /path/to/certificate.crt
    SSLCertificateKeyFile /path/to/private.key
    
    # Security headers
    Header always set Strict-Transport-Security "max-age=31536000; includeSubDomains"
    Header always set X-Content-Type-Options nosniff
    Header always set X-Frame-Options DENY
    Header always set X-XSS-Protection "1; mode=block"
    
    ProxyPreserveHost On
    ProxyPass / http://127.0.0.1:8000/
    ProxyPassReverse / http://127.0.0.1:8000/
</VirtualHost>
```

### Encryption Keys

Generate secure encryption keys:

```bash
# Generate SECRET_KEY for JWT signing
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Generate FERNET_KEY for token encryption
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Client Secret Security

Client secrets are automatically hashed using bcrypt. Configure bcrypt rounds:

```bash
# Higher rounds = more secure but slower
OAUTH2_CLIENT_SECRET_BCRYPT_ROUNDS=12
```

## Database Configuration

### MongoDB Collections

The OAuth2 provider uses the following MongoDB collections:

- `oauth2_clients`: OAuth2 client applications
- `oauth2_user_consents`: User consent records
- `oauth2_authorization_codes`: Authorization codes (with TTL)

### MongoDB Indexes

Create indexes for optimal performance:

```javascript
// MongoDB shell commands
use second_brain_database;

// OAuth2 clients indexes
db.oauth2_clients.createIndex({ "client_id": 1 }, { unique: true });
db.oauth2_clients.createIndex({ "owner_user_id": 1 });
db.oauth2_clients.createIndex({ "is_active": 1 });

// User consents indexes
db.oauth2_user_consents.createIndex({ "user_id": 1, "client_id": 1 }, { unique: true });
db.oauth2_user_consents.createIndex({ "client_id": 1 });
db.oauth2_user_consents.createIndex({ "is_active": 1 });

// Authorization codes indexes (with TTL)
db.oauth2_authorization_codes.createIndex({ "code": 1 }, { unique: true });
db.oauth2_authorization_codes.createIndex({ "expires_at": 1 }, { expireAfterSeconds: 0 });
db.oauth2_authorization_codes.createIndex({ "client_id": 1 });
db.oauth2_authorization_codes.createIndex({ "user_id": 1 });
```

### MongoDB Configuration

```bash
# MongoDB connection settings
MONGODB_URL=mongodb://username:password@host:port/database?authSource=admin
MONGODB_DATABASE=second_brain_database
MONGODB_MAX_CONNECTIONS=100
MONGODB_MIN_CONNECTIONS=10
MONGODB_CONNECT_TIMEOUT_MS=5000
MONGODB_SERVER_SELECTION_TIMEOUT_MS=5000
```

## Redis Configuration

### Redis for Token Storage

OAuth2 uses Redis for:
- Refresh token storage
- Authorization code caching
- Rate limiting counters
- Session state management

### Redis Configuration

```bash
# Redis connection settings
REDIS_URL=redis://username:password@host:port/database
REDIS_MAX_CONNECTIONS=20
REDIS_RETRY_ON_TIMEOUT=true
REDIS_SOCKET_CONNECT_TIMEOUT=5
REDIS_SOCKET_TIMEOUT=5
```

### Redis Key Patterns

The OAuth2 provider uses the following Redis key patterns:

```
oauth2:refresh_tokens:{token_hash}     # Refresh token data
oauth2:auth_codes:{code}               # Authorization codes
oauth2:rate_limit:{client_id}:{endpoint}  # Rate limiting counters
oauth2:consent_state:{state}           # Consent flow state
oauth2:encrypted_auth_codes:{code}     # Encrypted authorization codes
```

### Redis Memory Optimization

Configure Redis for optimal memory usage:

```redis
# redis.conf
maxmemory 256mb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
```

## Deployment Configuration

### Docker Deployment

#### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY .sbd .

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start application
CMD ["uvicorn", "src.second_brain_database.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### Docker Compose

```yaml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - SECRET_KEY=${SECRET_KEY}
      - FERNET_KEY=${FERNET_KEY}
      - MONGODB_URL=mongodb://mongo:27017
      - MONGODB_DATABASE=second_brain_database
      - REDIS_URL=redis://redis:6379
    depends_on:
      - mongo
      - redis
    restart: unless-stopped
    
  mongo:
    image: mongo:7
    ports:
      - "27017:27017"
    volumes:
      - mongo_data:/data/db
    environment:
      - MONGO_INITDB_ROOT_USERNAME=${MONGO_USERNAME}
      - MONGO_INITDB_ROOT_PASSWORD=${MONGO_PASSWORD}
    restart: unless-stopped
    
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes
    restart: unless-stopped

volumes:
  mongo_data:
  redis_data:
```

### Kubernetes Deployment

#### ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: oauth2-config
data:
  OAUTH2_ENABLED: "true"
  OAUTH2_ACCESS_TOKEN_EXPIRE_MINUTES: "60"
  OAUTH2_REFRESH_TOKEN_EXPIRE_DAYS: "30"
  OAUTH2_RATE_LIMIT_ENABLED: "true"
  MONGODB_DATABASE: "second_brain_database"
```

#### Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: oauth2-provider
spec:
  replicas: 3
  selector:
    matchLabels:
      app: oauth2-provider
  template:
    metadata:
      labels:
        app: oauth2-provider
    spec:
      containers:
      - name: oauth2-provider
        image: your-registry/oauth2-provider:latest
        ports:
        - containerPort: 8000
        env:
        - name: SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: oauth2-secrets
              key: secret-key
        - name: FERNET_KEY
          valueFrom:
            secretKeyRef:
              name: oauth2-secrets
              key: fernet-key
        envFrom:
        - configMapRef:
            name: oauth2-config
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /oauth2/health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
```

## Monitoring and Logging

### Prometheus Metrics

The OAuth2 provider exposes Prometheus metrics:

```
# OAuth2 specific metrics
oauth2_authorization_requests_total{client_id, status}
oauth2_token_requests_total{client_id, grant_type, status}
oauth2_active_tokens{client_id, token_type}
oauth2_client_registrations_total{status}
oauth2_consent_decisions_total{client_id, decision}
oauth2_rate_limit_hits_total{client_id, endpoint}
```

### Logging Configuration

Configure structured logging for OAuth2 events:

```python
# Logging configuration
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "oauth2": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S"
        }
    },
    "handlers": {
        "oauth2_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "/var/log/oauth2.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
            "formatter": "oauth2"
        }
    },
    "loggers": {
        "oauth2": {
            "handlers": ["oauth2_file"],
            "level": "INFO",
            "propagate": False
        }
    }
}
```

### Audit Logging

Enable comprehensive audit logging:

```bash
# Audit logging settings
OAUTH2_AUDIT_LOGGING_ENABLED=true
OAUTH2_AUDIT_LOG_LEVEL=INFO
OAUTH2_AUDIT_LOG_FILE=/var/log/oauth2-audit.log
OAUTH2_AUDIT_LOG_MAX_SIZE=50MB
OAUTH2_AUDIT_LOG_BACKUP_COUNT=10
```

## Performance Tuning

### Application Performance

```bash
# Uvicorn performance settings
UVICORN_WORKERS=4
UVICORN_WORKER_CLASS=uvicorn.workers.UvicornWorker
UVICORN_MAX_REQUESTS=1000
UVICORN_MAX_REQUESTS_JITTER=100
```

### Database Performance

```bash
# MongoDB connection pool settings
MONGODB_MAX_CONNECTIONS=100
MONGODB_MIN_CONNECTIONS=10
MONGODB_MAX_IDLE_TIME_MS=30000
```

### Redis Performance

```bash
# Redis connection pool settings
REDIS_MAX_CONNECTIONS=20
REDIS_CONNECTION_POOL_MAX_CONNECTIONS=50
REDIS_RETRY_ON_TIMEOUT=true
```

### Caching Configuration

```bash
# Enable caching for frequently accessed data
OAUTH2_CACHE_CLIENT_INFO=true
OAUTH2_CACHE_CLIENT_INFO_TTL=300  # 5 minutes
OAUTH2_CACHE_CONSENT_INFO=true
OAUTH2_CACHE_CONSENT_INFO_TTL=600  # 10 minutes
```

## Troubleshooting

### Common Configuration Issues

#### 1. OAuth2 Provider Not Starting

**Symptoms**: Application starts but OAuth2 endpoints return 404

**Solutions**:
- Check `OAUTH2_ENABLED=true` in configuration
- Verify all required environment variables are set
- Check application logs for initialization errors

#### 2. Token Generation Failures

**Symptoms**: Token endpoint returns 500 errors

**Solutions**:
- Verify `SECRET_KEY` is set and valid
- Check Redis connectivity
- Ensure MongoDB is accessible
- Verify `FERNET_KEY` is properly formatted

#### 3. Client Registration Failures

**Symptoms**: Client registration returns validation errors

**Solutions**:
- Ensure redirect URIs use HTTPS (except localhost)
- Check scope names are valid
- Verify user has proper permissions

#### 4. Rate Limiting Issues

**Symptoms**: Clients receiving 429 Too Many Requests

**Solutions**:
- Adjust rate limiting settings
- Check Redis for rate limit counters
- Monitor client request patterns

### Debug Mode

Enable debug mode for troubleshooting:

```bash
# Debug settings
DEBUG=true
OAUTH2_DEBUG_MODE=true
OAUTH2_LOG_LEVEL=DEBUG
OAUTH2_TRACE_REQUESTS=true
```

### Health Checks

Monitor OAuth2 provider health:

```bash
# Check overall application health
curl https://your-domain.com/health

# Check OAuth2 provider health
curl https://your-domain.com/oauth2/health

# Check OAuth2 configuration
curl https://your-domain.com/oauth2/.well-known/oauth-authorization-server
```

### Log Analysis

Common log patterns to monitor:

```bash
# Authorization failures
grep "authorization_failed" /var/log/oauth2.log

# Token generation errors
grep "token_generation_failed" /var/log/oauth2.log

# Rate limiting events
grep "rate_limit_exceeded" /var/log/oauth2.log

# Security violations
grep "security_violation" /var/log/oauth2-audit.log
```

## Production Checklist

Before deploying to production:

- [ ] HTTPS is properly configured
- [ ] All secrets are securely generated and stored
- [ ] Database indexes are created
- [ ] Redis is configured with persistence
- [ ] Rate limiting is enabled and tuned
- [ ] Monitoring and alerting are set up
- [ ] Backup procedures are in place
- [ ] Security headers are configured
- [ ] Log rotation is configured
- [ ] Health checks are working
- [ ] Load testing has been performed
- [ ] Disaster recovery plan is documented

## Support

For additional configuration support:

1. Check the [Integration Guide](./OAUTH2_INTEGRATION.md)
2. Review the [API Reference](./OAUTH2_API_REFERENCE.md)
3. See [Integration Examples](./examples/)
4. Check application logs for detailed error messages
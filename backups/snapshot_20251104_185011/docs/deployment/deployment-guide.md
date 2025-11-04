# Family Management System Deployment Guide

## Overview

This guide provides comprehensive instructions for deploying the Family Management System in production environments. The system is built with FastAPI and requires MongoDB, Redis, and proper configuration management.

## Prerequisites

### System Requirements

**Minimum Requirements:**
- CPU: 2 cores
- RAM: 4GB
- Storage: 20GB SSD
- Network: 1Gbps

**Recommended Requirements:**
- CPU: 4+ cores
- RAM: 8GB+
- Storage: 50GB+ SSD
- Network: 1Gbps+

### Software Dependencies

- **Python**: 3.11+ (recommended 3.12)
- **uv**: Modern Python package manager
- **MongoDB**: 6.0+ with replica set support
- **Redis**: 7.0+ with persistence enabled
- **Nginx**: For reverse proxy and SSL termination
- **Docker**: Optional, for containerized deployment

## Environment Setup

### 1. Python Environment

```bash
# Install uv package manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone repository
git clone <repository-url>
cd second_brain_database

# Create virtual environment and install dependencies
uv sync --extra prod

# Verify installation
uv run python -c "import second_brain_database; print('Installation successful')"
```

### 2. Database Setup

#### MongoDB Configuration

Create MongoDB configuration file `/etc/mongod.conf`:

```yaml
# mongod.conf
storage:
  dbPath: /var/lib/mongodb
  journal:
    enabled: true

systemLog:
  destination: file
  logAppend: true
  path: /var/log/mongodb/mongod.log

net:
  port: 27017
  bindIp: 127.0.0.1

processManagement:
  timeZoneInfo: /usr/share/zoneinfo

# Enable replica set for transactions
replication:
  replSetName: "rs0"

# Security configuration
security:
  authorization: enabled
  keyFile: /etc/mongodb-keyfile

# Performance tuning
operationProfiling:
  slowOpThresholdMs: 100
  mode: slowOp
```

#### Initialize Replica Set

```bash
# Start MongoDB
sudo systemctl start mongod

# Connect to MongoDB
mongosh

# Initialize replica set
rs.initiate({
  _id: "rs0",
  members: [
    { _id: 0, host: "localhost:27017" }
  ]
})

# Create admin user
use admin
db.createUser({
  user: "admin",
  pwd: "secure_password_here",
  roles: ["root"]
})

# Create application user
use second_brain_database
db.createUser({
  user: "sbd_app",
  pwd: "app_password_here",
  roles: [
    { role: "readWrite", db: "second_brain_database" },
    { role: "dbAdmin", db: "second_brain_database" }
  ]
})
```

#### Redis Configuration

Create Redis configuration file `/etc/redis/redis.conf`:

```conf
# Basic configuration
bind 127.0.0.1
port 6379
timeout 0
tcp-keepalive 300

# Memory management
maxmemory 2gb
maxmemory-policy allkeys-lru

# Persistence
save 900 1
save 300 10
save 60 10000

# Security
requirepass redis_password_here
rename-command FLUSHDB ""
rename-command FLUSHALL ""
rename-command DEBUG ""

# Logging
loglevel notice
logfile /var/log/redis/redis-server.log

# Performance
tcp-backlog 511
databases 16
```

### 3. Application Configuration

Create production configuration file `.sbd`:

```bash
# Core application settings
SECRET_KEY=your_super_secure_jwt_secret_key_here_min_32_chars
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO

# Database configuration
MONGODB_URL=mongodb://sbd_app:app_password_here@localhost:27017/second_brain_database?authSource=second_brain_database&replicaSet=rs0
MONGODB_DATABASE=second_brain_database

# Redis configuration
REDIS_URL=redis://:redis_password_here@localhost:6379/0

# Security configuration
FERNET_KEY=your_fernet_encryption_key_here_32_bytes_base64_encoded
BCRYPT_ROUNDS=12

# External services
TURNSTILE_SITEKEY=your_cloudflare_turnstile_site_key
TURNSTILE_SECRET=your_cloudflare_turnstile_secret

# Email configuration (if using SMTP)
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=noreply@yourdomain.com
SMTP_PASSWORD=smtp_password_here
SMTP_USE_TLS=true

# Rate limiting
RATE_LIMIT_STORAGE_URL=redis://:redis_password_here@localhost:6379/1

# Monitoring
ENABLE_METRICS=true
METRICS_PORT=9090

# Family system limits
DEFAULT_FAMILY_LIMIT=3
DEFAULT_MEMBER_LIMIT=5
MAX_FAMILY_LIMIT=10
MAX_MEMBER_LIMIT=20

# Token system
DEFAULT_SPENDING_LIMIT=100
MAX_SPENDING_LIMIT=10000
TOKEN_REQUEST_EXPIRY_HOURS=168

# Security features
ENABLE_IP_LOCKDOWN=true
ENABLE_USER_AGENT_LOCKDOWN=true
REQUIRE_2FA_FOR_ADMIN=true
SESSION_TIMEOUT_HOURS=24

# Performance settings
MAX_WORKERS=4
WORKER_TIMEOUT=30
KEEPALIVE_TIMEOUT=5
```

### 4. Generate Encryption Keys

```bash
# Generate Fernet key for encryption
uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Generate JWT secret key
uv run python -c "import secrets; print(secrets.token_urlsafe(32))"

# Generate MongoDB keyfile
openssl rand -base64 756 > /etc/mongodb-keyfile
chmod 400 /etc/mongodb-keyfile
chown mongodb:mongodb /etc/mongodb-keyfile
```

## Deployment Methods

### Method 1: Direct Deployment

#### 1. System Service Configuration

Create systemd service file `/etc/systemd/system/sbd-api.service`:

```ini
[Unit]
Description=Second Brain Database API
After=network.target mongodb.service redis.service
Requires=mongodb.service redis.service

[Service]
Type=exec
User=sbd
Group=sbd
WorkingDirectory=/opt/second_brain_database
Environment=PATH=/opt/second_brain_database/.venv/bin
ExecStart=/opt/second_brain_database/.venv/bin/uvicorn second_brain_database.main:app --host 0.0.0.0 --port 8000 --workers 4
ExecReload=/bin/kill -HUP $MAINPID
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=sbd-api

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/second_brain_database/logs

[Install]
WantedBy=multi-user.target
```

#### 2. User and Directory Setup

```bash
# Create application user
sudo useradd -r -s /bin/false sbd

# Create application directory
sudo mkdir -p /opt/second_brain_database
sudo chown sbd:sbd /opt/second_brain_database

# Copy application files
sudo cp -r . /opt/second_brain_database/
sudo chown -R sbd:sbd /opt/second_brain_database

# Create log directory
sudo mkdir -p /var/log/sbd
sudo chown sbd:sbd /var/log/sbd
```

#### 3. Start Services

```bash
# Enable and start services
sudo systemctl enable mongodb redis sbd-api
sudo systemctl start mongodb redis sbd-api

# Check status
sudo systemctl status sbd-api
```

### Method 2: Docker Deployment

#### 1. Docker Compose Configuration

Create `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  mongodb:
    image: mongo:7.0
    container_name: sbd-mongodb
    restart: unless-stopped
    environment:
      MONGO_INITDB_ROOT_USERNAME: admin
      MONGO_INITDB_ROOT_PASSWORD: ${MONGO_ROOT_PASSWORD}
      MONGO_INITDB_DATABASE: second_brain_database
    volumes:
      - mongodb_data:/data/db
      - ./docker/mongodb/init-replica.js:/docker-entrypoint-initdb.d/init-replica.js:ro
      - ./docker/mongodb/mongod.conf:/etc/mongod.conf:ro
    command: ["mongod", "--config", "/etc/mongod.conf", "--replSet", "rs0"]
    networks:
      - sbd-network
    ports:
      - "27017:27017"

  redis:
    image: redis:7.0-alpine
    container_name: sbd-redis
    restart: unless-stopped
    command: redis-server --requirepass ${REDIS_PASSWORD} --appendonly yes
    volumes:
      - redis_data:/data
    networks:
      - sbd-network
    ports:
      - "6379:6379"

  api:
    build:
      context: .
      dockerfile: Dockerfile.prod
    container_name: sbd-api
    restart: unless-stopped
    environment:
      - MONGODB_URL=mongodb://sbd_app:${MONGO_APP_PASSWORD}@mongodb:27017/second_brain_database?authSource=second_brain_database&replicaSet=rs0
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
      - SECRET_KEY=${SECRET_KEY}
      - FERNET_KEY=${FERNET_KEY}
    volumes:
      - ./logs:/app/logs
      - ./.sbd:/app/.sbd:ro
    depends_on:
      - mongodb
      - redis
    networks:
      - sbd-network
    ports:
      - "8000:8000"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  nginx:
    image: nginx:alpine
    container_name: sbd-nginx
    restart: unless-stopped
    volumes:
      - ./docker/nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./docker/nginx/ssl:/etc/nginx/ssl:ro
    depends_on:
      - api
    networks:
      - sbd-network
    ports:
      - "80:80"
      - "443:443"

volumes:
  mongodb_data:
  redis_data:

networks:
  sbd-network:
    driver: bridge
```

#### 2. Production Dockerfile

Create `Dockerfile.prod`:

```dockerfile
FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PATH="/app/.venv/bin:$PATH"

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Create app user
RUN useradd -r -s /bin/false appuser

# Set work directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Copy application code
COPY src/ ./src/
COPY scripts/ ./scripts/

# Create logs directory
RUN mkdir -p logs && chown appuser:appuser logs

# Switch to app user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Run application
CMD ["uvicorn", "src.second_brain_database.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

#### 3. Deploy with Docker

```bash
# Create environment file
cp .env.example .env.prod
# Edit .env.prod with production values

# Build and start services
docker-compose -f docker-compose.prod.yml --env-file .env.prod up -d

# Check logs
docker-compose -f docker-compose.prod.yml logs -f api
```

## Reverse Proxy Configuration

### Nginx Configuration

Create `/etc/nginx/sites-available/sbd-api`:

```nginx
# Rate limiting
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
limit_req_zone $binary_remote_addr zone=auth:10m rate=5r/s;

# Upstream servers
upstream sbd_api {
    server 127.0.0.1:8000;
    # Add more servers for load balancing
    # server 127.0.0.1:8001;
    # server 127.0.0.1:8002;
}

server {
    listen 80;
    server_name api.yourdomain.com;
    
    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.yourdomain.com;

    # SSL configuration
    ssl_certificate /etc/ssl/certs/yourdomain.com.crt;
    ssl_certificate_key /etc/ssl/private/yourdomain.com.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin";

    # Logging
    access_log /var/log/nginx/sbd-api.access.log;
    error_log /var/log/nginx/sbd-api.error.log;

    # General settings
    client_max_body_size 10M;
    client_body_timeout 60s;
    client_header_timeout 60s;

    # Compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;

    # API endpoints
    location / {
        # Rate limiting
        limit_req zone=api burst=20 nodelay;
        
        # Proxy settings
        proxy_pass http://sbd_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
        
        # Buffering
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
    }

    # Authentication endpoints with stricter rate limiting
    location /auth/ {
        limit_req zone=auth burst=10 nodelay;
        
        proxy_pass http://sbd_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Health check endpoint
    location /health {
        proxy_pass http://sbd_api;
        access_log off;
    }

    # Static files (if any)
    location /static/ {
        alias /opt/second_brain_database/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

Enable the site:

```bash
sudo ln -s /etc/nginx/sites-available/sbd-api /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## SSL/TLS Configuration

### Using Let's Encrypt

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d api.yourdomain.com

# Test renewal
sudo certbot renew --dry-run

# Set up automatic renewal
echo "0 12 * * * /usr/bin/certbot renew --quiet" | sudo crontab -
```

### Using Custom Certificates

```bash
# Create SSL directory
sudo mkdir -p /etc/ssl/private /etc/ssl/certs

# Copy certificates
sudo cp yourdomain.com.crt /etc/ssl/certs/
sudo cp yourdomain.com.key /etc/ssl/private/

# Set permissions
sudo chmod 644 /etc/ssl/certs/yourdomain.com.crt
sudo chmod 600 /etc/ssl/private/yourdomain.com.key
```

## Database Migrations

### Initial Setup

```bash
# Run database migrations
uv run python -m second_brain_database.migrations.migration_manager

# Create indexes
uv run python -c "
from second_brain_database.database.family_audit_indexes import create_family_audit_indexes
import asyncio
asyncio.run(create_family_audit_indexes())
"

# Verify setup
uv run python -c "
from second_brain_database.database import get_database
import asyncio

async def verify():
    db = await get_database()
    collections = await db.list_collection_names()
    print('Collections:', collections)

asyncio.run(verify())
"
```

### Migration Scripts

Create migration script `scripts/migrate.py`:

```python
#!/usr/bin/env python3
"""Database migration script for production deployment."""

import asyncio
import logging
from second_brain_database.database import get_database
from second_brain_database.migrations.migration_manager import MigrationManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_migrations():
    """Run all pending migrations."""
    try:
        db = await get_database()
        migration_manager = MigrationManager(db)
        
        logger.info("Starting database migrations...")
        await migration_manager.run_migrations()
        logger.info("Migrations completed successfully")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(run_migrations())
```

## Monitoring Setup

### Application Metrics

The application exposes Prometheus metrics on port 9090. Configure Prometheus to scrape metrics:

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'sbd-api'
    static_configs:
      - targets: ['localhost:9090']
    scrape_interval: 15s
    metrics_path: /metrics
```

### Health Checks

Configure health check monitoring:

```bash
# Create health check script
cat > /opt/monitoring/check_sbd_health.sh << 'EOF'
#!/bin/bash

HEALTH_URL="http://localhost:8000/health"
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "$HEALTH_URL")

if [ "$RESPONSE" = "200" ]; then
    echo "OK: SBD API is healthy"
    exit 0
else
    echo "CRITICAL: SBD API health check failed (HTTP $RESPONSE)"
    exit 2
fi
EOF

chmod +x /opt/monitoring/check_sbd_health.sh

# Add to cron for regular checks
echo "*/5 * * * * /opt/monitoring/check_sbd_health.sh" | crontab -
```

### Log Aggregation

Configure log rotation and aggregation:

```bash
# Create logrotate configuration
cat > /etc/logrotate.d/sbd-api << 'EOF'
/var/log/sbd/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 sbd sbd
    postrotate
        systemctl reload sbd-api
    endscript
}
EOF
```

## Security Hardening

### Firewall Configuration

```bash
# Configure UFW firewall
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow SSH
sudo ufw allow ssh

# Allow HTTP/HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Allow MongoDB (only from localhost)
sudo ufw allow from 127.0.0.1 to any port 27017

# Allow Redis (only from localhost)
sudo ufw allow from 127.0.0.1 to any port 6379

# Enable firewall
sudo ufw enable
```

### System Security

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install security updates automatically
sudo apt install unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades

# Configure fail2ban for SSH protection
sudo apt install fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban

# Disable root login
sudo passwd -l root

# Configure SSH security
sudo sed -i 's/#PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config
sudo sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo systemctl restart ssh
```

## Backup and Recovery

### Database Backup

Create backup script `/opt/scripts/backup_mongodb.sh`:

```bash
#!/bin/bash

BACKUP_DIR="/opt/backups/mongodb"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="sbd_backup_$DATE"

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Run mongodump
mongodump --uri="mongodb://sbd_app:app_password_here@localhost:27017/second_brain_database?authSource=second_brain_database" \
          --out="$BACKUP_DIR/$BACKUP_NAME"

# Compress backup
tar -czf "$BACKUP_DIR/$BACKUP_NAME.tar.gz" -C "$BACKUP_DIR" "$BACKUP_NAME"
rm -rf "$BACKUP_DIR/$BACKUP_NAME"

# Keep only last 7 days of backups
find "$BACKUP_DIR" -name "sbd_backup_*.tar.gz" -mtime +7 -delete

echo "Backup completed: $BACKUP_DIR/$BACKUP_NAME.tar.gz"
```

### Redis Backup

Redis automatically creates RDB snapshots. Configure additional backup:

```bash
#!/bin/bash

BACKUP_DIR="/opt/backups/redis"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

# Copy RDB file
cp /var/lib/redis/dump.rdb "$BACKUP_DIR/dump_$DATE.rdb"

# Keep only last 7 days
find "$BACKUP_DIR" -name "dump_*.rdb" -mtime +7 -delete
```

### Automated Backups

```bash
# Add to crontab
crontab -e

# Add these lines:
# Daily database backup at 2 AM
0 2 * * * /opt/scripts/backup_mongodb.sh

# Daily Redis backup at 2:30 AM
30 2 * * * /opt/scripts/backup_redis.sh
```

## Performance Tuning

### Application Tuning

```bash
# Optimize Python settings
export PYTHONOPTIMIZE=1
export PYTHONDONTWRITEBYTECODE=1

# Increase file descriptor limits
echo "sbd soft nofile 65536" >> /etc/security/limits.conf
echo "sbd hard nofile 65536" >> /etc/security/limits.conf
```

### MongoDB Tuning

```javascript
// Connect to MongoDB and run these optimizations
use second_brain_database

// Create indexes for better performance
db.families.createIndex({ "admin_user_ids": 1 })
db.families.createIndex({ "created_at": 1 })
db.family_relationships.createIndex({ "family_id": 1, "status": 1 })
db.family_invitations.createIndex({ "family_id": 1, "status": 1 })
db.family_invitations.createIndex({ "expires_at": 1 })
db.family_token_requests.createIndex({ "family_id": 1, "status": 1 })
db.family_notifications.createIndex({ "recipient_user_ids": 1, "created_at": -1 })

// Set up TTL indexes for cleanup
db.family_invitations.createIndex({ "expires_at": 1 }, { expireAfterSeconds: 0 })
db.family_token_requests.createIndex({ "expires_at": 1 }, { expireAfterSeconds: 0 })
```

### Redis Tuning

```conf
# Add to redis.conf
maxmemory-samples 10
hash-max-ziplist-entries 512
hash-max-ziplist-value 64
list-max-ziplist-size -2
set-max-intset-entries 512
zset-max-ziplist-entries 128
zset-max-ziplist-value 64
```

## Troubleshooting

### Common Issues

1. **Application won't start**
   - Check configuration file syntax
   - Verify database connectivity
   - Check log files for errors

2. **Database connection errors**
   - Verify MongoDB is running
   - Check authentication credentials
   - Ensure replica set is initialized

3. **High memory usage**
   - Monitor Redis memory usage
   - Check for memory leaks in application
   - Optimize database queries

4. **Slow response times**
   - Check database indexes
   - Monitor system resources
   - Review application logs

### Log Locations

- Application logs: `/var/log/sbd/`
- MongoDB logs: `/var/log/mongodb/mongod.log`
- Redis logs: `/var/log/redis/redis-server.log`
- Nginx logs: `/var/log/nginx/`
- System logs: `/var/log/syslog`

### Diagnostic Commands

```bash
# Check service status
sudo systemctl status sbd-api mongodb redis nginx

# Check application health
curl http://localhost:8000/health

# Check database connectivity
mongosh --eval "db.adminCommand('ping')"

# Check Redis connectivity
redis-cli ping

# Monitor system resources
htop
iotop
netstat -tulpn
```

This deployment guide provides a comprehensive foundation for deploying the Family Management System in production environments with proper security, monitoring, and performance considerations.
# FastMCP Gateway Integration - Comprehensive Configuration Guide

## Overview

The FastMCP Gateway Integration provides a production-ready, security-first MCP server that integrates seamlessly with the existing Second Brain Database infrastructure. This comprehensive guide covers all configuration options, environment-specific setups, security best practices, troubleshooting procedures, and integration details.

The MCP server leverages FastMCP framework for automatic tool discovery and registration while maintaining enterprise-grade security, auditability, and operational excellence through integration with existing authentication, authorization, and monitoring systems.

## Configuration Architecture

### Configuration Loading Priority

Configuration is loaded and merged in the following priority order (highest to lowest):

1. **Environment variables** (highest priority) - Runtime configuration
2. **Command line arguments** - Deployment-specific overrides  
3. **`.sbd` file** in project root - Primary configuration file
4. **`.env` file** in project root - Fallback configuration
5. **Default values in config.py** (lowest priority) - Built-in defaults

### Configuration Validation

All configuration is validated at startup using Pydantic validators:

```python
# Configuration validation example
from src.second_brain_database.config import settings

# Validate configuration without starting server
try:
    print(f"MCP Server: {settings.MCP_SERVER_NAME}")
    print(f"Security Enabled: {settings.MCP_SECURITY_ENABLED}")
    print(f"Configuration valid ✓")
except ValidationError as e:
    print(f"Configuration error: {e}")
```

### Configuration File Formats

#### .sbd File Format (Recommended)
```bash
# .sbd - Primary configuration file
# Core MCP Settings
MCP_ENABLED=true
MCP_SERVER_NAME=SecondBrainMCP
MCP_SERVER_PORT=3001

# Security Configuration  
MCP_SECURITY_ENABLED=true
MCP_REQUIRE_AUTH=true
MCP_AUDIT_ENABLED=true

# Performance Settings
MCP_MAX_CONCURRENT_TOOLS=50
MCP_REQUEST_TIMEOUT=30
```

#### Environment Variables (Production)
```bash
# Production environment variables
export MCP_ENABLED=true
export MCP_SECURITY_ENABLED=true
export MCP_RATE_LIMIT_ENABLED=true
export MCP_DEBUG_MODE=false
```

## Complete Configuration Reference

### Core Server Configuration

#### Basic Server Settings
```bash
# Server Control
MCP_ENABLED=true                    # Enable/disable MCP server (default: true)
MCP_DEBUG_MODE=false               # Enable debug logging (default: false)

# Server Identity
MCP_SERVER_NAME="SecondBrainMCP"   # MCP server name (default: "SecondBrainMCP")
MCP_SERVER_VERSION="1.0.0"        # Server version (default: "1.0.0")
MCP_SERVER_DESCRIPTION="Second Brain Database MCP Server"  # Server description

# Network Configuration
MCP_SERVER_HOST="localhost"        # Host to bind server to (default: "localhost")
MCP_SERVER_PORT=3001              # Port for MCP server (default: 3001, range: 1024-65535)

# Connection Settings
MCP_CONNECTION_TIMEOUT=10          # Connection timeout in seconds (default: 10)
MCP_KEEPALIVE_TIMEOUT=5           # Keep-alive timeout in seconds (default: 5)
```

#### Performance and Resource Management
```bash
# Concurrency Control
MCP_MAX_CONCURRENT_TOOLS=50        # Maximum concurrent tool executions (default: 50)
MCP_REQUEST_TIMEOUT=30            # Request timeout in seconds (default: 30)
MCP_TOOL_EXECUTION_TIMEOUT=60     # Tool execution timeout in seconds (default: 60)

# Resource Limits
MCP_MAX_REQUEST_SIZE=1048576       # Maximum request size in bytes (1MB default)
MCP_MAX_RESPONSE_SIZE=10485760     # Maximum response size in bytes (10MB default)

# Memory Management
MCP_MEMORY_LIMIT_MB=512           # Memory limit per worker in MB (default: 512)
MCP_GARBAGE_COLLECTION_THRESHOLD=100  # GC threshold for tool executions (default: 100)
```

### Comprehensive Security Configuration

#### Authentication and Authorization
```bash
# Core Security
MCP_SECURITY_ENABLED=true          # Enable security for MCP tools (default: true)
MCP_REQUIRE_AUTH=true              # Require authentication for all tools (default: true)
MCP_AUDIT_ENABLED=true             # Enable comprehensive audit logging (default: true)

# Authentication Methods
MCP_JWT_ENABLED=true               # Enable JWT token authentication (default: true)
MCP_PERMANENT_TOKEN_ENABLED=true   # Enable permanent token auth (default: true)
MCP_WEBAUTHN_ENABLED=false         # Enable WebAuthn authentication (default: false)

# Session Management
MCP_SESSION_TIMEOUT=3600           # Session timeout in seconds (default: 3600)
MCP_TOKEN_REFRESH_ENABLED=true     # Enable automatic token refresh (default: true)
MCP_MULTI_SESSION_ENABLED=true     # Allow multiple sessions per user (default: true)
```

#### Rate Limiting and Abuse Prevention
```bash
# Global Rate Limiting
MCP_RATE_LIMIT_ENABLED=true        # Enable rate limiting (default: true)
MCP_RATE_LIMIT_REQUESTS=100        # Max requests per period per user (default: 100)
MCP_RATE_LIMIT_PERIOD=60          # Rate limit period in seconds (default: 60)
MCP_RATE_LIMIT_BURST=10           # Burst limit for requests (default: 10)

# Tool-Specific Rate Limits
MCP_FAMILY_RATE_LIMIT=50          # Family tools rate limit (default: 50)
MCP_AUTH_RATE_LIMIT=20            # Auth tools rate limit (default: 20)
MCP_SHOP_RATE_LIMIT=30            # Shop tools rate limit (default: 30)
MCP_ADMIN_RATE_LIMIT=10           # Admin tools rate limit (default: 10)

# Abuse Detection
MCP_ANOMALY_DETECTION_ENABLED=true # Enable behavioral anomaly detection (default: true)
MCP_SUSPICIOUS_ACTIVITY_THRESHOLD=5 # Threshold for suspicious activity alerts (default: 5)
MCP_AUTO_BLOCK_ENABLED=true        # Enable automatic blocking of suspicious IPs (default: true)
MCP_BLOCK_DURATION=3600           # Auto-block duration in seconds (default: 3600)
```

#### Access Control and Network Security
```bash
# Origin and CORS Control
MCP_CORS_ENABLED=false             # Enable CORS for MCP server (default: false)
MCP_ALLOWED_ORIGINS=""             # Comma-separated allowed origins (default: empty)
MCP_ALLOWED_METHODS="GET,POST"     # Allowed HTTP methods (default: "GET,POST")
MCP_ALLOWED_HEADERS="Authorization,Content-Type"  # Allowed headers

# IP and Geographic Restrictions
MCP_IP_WHITELIST=""               # Comma-separated IP whitelist (default: empty)
MCP_IP_BLACKLIST=""               # Comma-separated IP blacklist (default: empty)
MCP_GEO_BLOCKING_ENABLED=false    # Enable geographic blocking (default: false)
MCP_ALLOWED_COUNTRIES=""          # Comma-separated country codes (default: empty)

# Advanced Security Features
MCP_IP_LOCKDOWN_ENABLED=false     # Enable IP address lockdown (default: false)
MCP_USER_AGENT_LOCKDOWN_ENABLED=false  # Enable user agent lockdown (default: false)
MCP_DEVICE_FINGERPRINTING_ENABLED=false # Enable device fingerprinting (default: false)
MCP_REQUIRE_2FA_FOR_ADMIN=true     # Require 2FA for admin operations (default: true)
```

### Tool Categories and Feature Configuration

#### Tool Category Controls
```bash
# Core Tool Categories
MCP_TOOLS_ENABLED=true             # Enable MCP tools globally (default: true)
MCP_RESOURCES_ENABLED=true         # Enable MCP resources (default: true)
MCP_PROMPTS_ENABLED=true          # Enable MCP prompts (default: true)

# Family Management Tools
MCP_FAMILY_TOOLS_ENABLED=true      # Enable family management tools (default: true)
MCP_FAMILY_MAX_MEMBERS=10          # Maximum family members (default: 10)
MCP_FAMILY_MAX_INVITATIONS=5       # Maximum pending invitations (default: 5)
MCP_FAMILY_MAX_FAMILIES_PER_USER=3 # Maximum families per user (default: 3)
MCP_FAMILY_ALLOW_DELETION=true     # Allow family deletion (default: true)

# Authentication and Profile Tools
MCP_AUTH_TOOLS_ENABLED=true        # Enable authentication tools (default: true)
MCP_PROFILE_TOOLS_ENABLED=true     # Enable profile management tools (default: true)
MCP_AUTH_ALLOW_PASSWORD_RESET=true # Allow password reset via MCP (default: true)
MCP_AUTH_ALLOW_EMAIL_CHANGE=true   # Allow email changes via MCP (default: true)
MCP_AUTH_REQUIRE_2FA_FOR_ADMIN=true # Require 2FA for admin operations (default: true)

# Shop and Asset Management Tools
MCP_SHOP_TOOLS_ENABLED=true        # Enable shop and asset tools (default: true)
MCP_SHOP_MAX_PURCHASE_AMOUNT=1000  # Maximum single purchase amount (default: 1000)
MCP_SHOP_REFUND_ENABLED=true       # Enable refund processing (default: true)
MCP_SHOP_RENTAL_ENABLED=true       # Enable asset rentals (default: true)
MCP_SHOP_BULK_PURCHASE_ENABLED=false # Enable bulk purchases (default: false)

# Workspace and Team Tools
MCP_WORKSPACE_TOOLS_ENABLED=true   # Enable workspace tools (default: true)
MCP_WORKSPACE_MAX_MEMBERS=50       # Maximum workspace members (default: 50)
MCP_WORKSPACE_MAX_WORKSPACES_PER_USER=5 # Maximum workspaces per user (default: 5)
MCP_WORKSPACE_ALLOW_DELETION=true  # Allow workspace deletion (default: true)

# Administrative and System Tools
MCP_ADMIN_TOOLS_ENABLED=false      # Enable admin tools (default: false)
MCP_SYSTEM_TOOLS_ENABLED=false     # Enable system management tools (default: false)
MCP_ADMIN_REQUIRE_SUPER_USER=true  # Require super user for admin tools (default: true)
MCP_SYSTEM_MONITORING_ENABLED=true # Enable system monitoring tools (default: true)
```

#### Business Logic Limits and Constraints
```bash
# SBD Token Management
MCP_SBD_MAX_REQUEST_AMOUNT=500     # Maximum SBD token request amount (default: 500)
MCP_SBD_DAILY_REQUEST_LIMIT=1000   # Daily SBD request limit per user (default: 1000)
MCP_SBD_TRANSFER_ENABLED=true      # Enable SBD transfers between users (default: true)
MCP_SBD_MIN_TRANSFER_AMOUNT=1      # Minimum transfer amount (default: 1)

# Content and Data Limits
MCP_MAX_DESCRIPTION_LENGTH=500     # Maximum description length (default: 500)
MCP_MAX_NAME_LENGTH=100           # Maximum name length (default: 100)
MCP_MAX_SEARCH_RESULTS=100        # Maximum search results returned (default: 100)
MCP_MAX_HISTORY_ITEMS=1000        # Maximum history items returned (default: 1000)

# File and Asset Limits
MCP_MAX_AVATAR_SIZE_MB=5          # Maximum avatar file size in MB (default: 5)
MCP_MAX_BANNER_SIZE_MB=10         # Maximum banner file size in MB (default: 10)
MCP_ALLOWED_IMAGE_FORMATS="jpg,jpeg,png,gif,webp" # Allowed image formats
MCP_ASSET_CACHE_DURATION=3600     # Asset cache duration in seconds (default: 3600)
```

## Environment-Specific Configuration Guides

### Development Environment Setup

#### Complete Development Configuration (.env.development)
```bash
# === DEVELOPMENT ENVIRONMENT CONFIGURATION ===

# Core Server Settings
MCP_ENABLED=true
MCP_DEBUG_MODE=true                # Enable detailed logging for debugging
MCP_SERVER_HOST="localhost"        # Local development only
MCP_SERVER_PORT=3001

# Security Settings (Relaxed for Development)
MCP_SECURITY_ENABLED=true          # Keep security enabled for testing
MCP_REQUIRE_AUTH=true              # Test authentication flows
MCP_AUDIT_ENABLED=true             # Enable audit for debugging
MCP_RATE_LIMIT_ENABLED=false       # Disable to avoid interruptions during testing

# Tool Access (Full Access for Development)
MCP_FAMILY_TOOLS_ENABLED=true
MCP_AUTH_TOOLS_ENABLED=true
MCP_PROFILE_TOOLS_ENABLED=true
MCP_SHOP_TOOLS_ENABLED=true
MCP_WORKSPACE_TOOLS_ENABLED=true
MCP_ADMIN_TOOLS_ENABLED=true       # Enable for testing admin functionality
MCP_SYSTEM_TOOLS_ENABLED=true      # Enable for system testing

# Performance Settings (Relaxed)
MCP_MAX_CONCURRENT_TOOLS=25        # Lower for development resources
MCP_REQUEST_TIMEOUT=60             # Higher timeout for debugging
MCP_TOOL_EXECUTION_TIMEOUT=120     # Extended timeout for debugging

# Development-Specific Features
MCP_CORS_ENABLED=true              # Enable CORS for frontend development
MCP_ALLOWED_ORIGINS="http://localhost:3000,http://localhost:8080,http://127.0.0.1:3000"
MCP_ANOMALY_DETECTION_ENABLED=false # Disable to avoid false positives during testing
MCP_AUTO_BLOCK_ENABLED=false       # Disable auto-blocking during development

# Monitoring and Observability
MCP_METRICS_ENABLED=true
MCP_HEALTH_CHECK_ENABLED=true
MCP_PERFORMANCE_MONITORING=true

# Cache Settings (Short TTL for development)
MCP_CACHE_ENABLED=true
MCP_CACHE_TTL=60                   # Short cache for rapid development
MCP_CONTEXT_CACHE_TTL=30

# Error Handling (Verbose for debugging)
MCP_ERROR_RECOVERY_ENABLED=true
MCP_CIRCUIT_BREAKER_ENABLED=false  # Disable to see all errors during development
MCP_RETRY_ENABLED=false            # Disable retries to see immediate failures
```

#### Development Setup Script
```bash
#!/bin/bash
# setup-dev-mcp.sh

echo "Setting up MCP development environment..."

# Copy development configuration
cp .env.development .sbd

# Install development dependencies
uv sync --extra dev

# Start development services
docker-compose -f docker-compose.dev.yml up -d mongodb redis

# Wait for services
sleep 10

# Verify MCP configuration
python -c "
from src.second_brain_database.config import settings
print(f'MCP Enabled: {settings.MCP_ENABLED}')
print(f'Debug Mode: {settings.MCP_DEBUG_MODE}')
print(f'Admin Tools: {settings.MCP_ADMIN_TOOLS_ENABLED}')
print('Development configuration loaded successfully ✓')
"

# Start application with hot reload
echo "Starting FastAPI with MCP server..."
uv run uvicorn src.second_brain_database.main:app --reload --host 0.0.0.0 --port 8000
```

### Staging Environment Setup

#### Complete Staging Configuration (.env.staging)
```bash
# === STAGING ENVIRONMENT CONFIGURATION ===

# Core Server Settings
MCP_ENABLED=true
MCP_DEBUG_MODE=false               # Disable debug in staging
MCP_SERVER_HOST="0.0.0.0"         # Accept connections from load balancer
MCP_SERVER_PORT=3001

# Security Settings (Production-like with some relaxation)
MCP_SECURITY_ENABLED=true
MCP_REQUIRE_AUTH=true
MCP_AUDIT_ENABLED=true
MCP_RATE_LIMIT_ENABLED=true
MCP_RATE_LIMIT_REQUESTS=200        # Higher limit for testing
MCP_RATE_LIMIT_PERIOD=60

# Authentication and Authorization
MCP_JWT_ENABLED=true
MCP_PERMANENT_TOKEN_ENABLED=true
MCP_SESSION_TIMEOUT=7200           # 2 hours for testing sessions
MCP_REQUIRE_2FA_FOR_ADMIN=true

# Tool Access (Most tools enabled for testing)
MCP_FAMILY_TOOLS_ENABLED=true
MCP_AUTH_TOOLS_ENABLED=true
MCP_PROFILE_TOOLS_ENABLED=true
MCP_SHOP_TOOLS_ENABLED=true
MCP_WORKSPACE_TOOLS_ENABLED=true
MCP_ADMIN_TOOLS_ENABLED=true       # Enable for staging testing
MCP_SYSTEM_TOOLS_ENABLED=false     # Disable system tools in staging

# Performance Settings
MCP_MAX_CONCURRENT_TOOLS=40
MCP_REQUEST_TIMEOUT=45
MCP_TOOL_EXECUTION_TIMEOUT=90

# Network and Access Control
MCP_CORS_ENABLED=true
MCP_ALLOWED_ORIGINS="https://staging.yourdomain.com,https://staging-api.yourdomain.com"
MCP_IP_LOCKDOWN_ENABLED=false      # Disable for testing from various IPs
MCP_USER_AGENT_LOCKDOWN_ENABLED=false

# Monitoring and Alerting
MCP_METRICS_ENABLED=true
MCP_HEALTH_CHECK_ENABLED=true
MCP_PERFORMANCE_MONITORING=true
MCP_ANOMALY_DETECTION_ENABLED=true
MCP_AUTO_BLOCK_ENABLED=false       # Disable auto-blocking in staging

# Cache Settings
MCP_CACHE_ENABLED=true
MCP_CACHE_TTL=300                  # 5 minutes
MCP_CONTEXT_CACHE_TTL=60

# Error Handling and Recovery
MCP_ERROR_RECOVERY_ENABLED=true
MCP_CIRCUIT_BREAKER_ENABLED=true
MCP_RETRY_ENABLED=true
MCP_RETRY_MAX_ATTEMPTS=2           # Fewer retries in staging
```

#### Staging Deployment Script
```bash
#!/bin/bash
# deploy-staging-mcp.sh

echo "Deploying MCP to staging environment..."

# Set staging environment
export ENVIRONMENT=staging

# Pull latest images
docker-compose -f docker-compose.staging.yml pull

# Deploy with zero downtime
docker-compose -f docker-compose.staging.yml up -d --remove-orphans

# Wait for services to be ready
echo "Waiting for services to start..."
sleep 30

# Health checks
echo "Running health checks..."
curl -f https://staging-api.yourdomain.com/health || exit 1
curl -f https://staging-api.yourdomain.com/health/mcp/server || exit 1

# Run integration tests
echo "Running MCP integration tests..."
pytest tests/test_mcp_staging.py -v

echo "Staging deployment completed successfully ✓"
```

### Production Environment Setup

#### Complete Production Configuration (Environment Variables)
```bash
# === PRODUCTION ENVIRONMENT CONFIGURATION ===

# Core Server Settings
export MCP_ENABLED=true
export MCP_DEBUG_MODE=false        # Never enable debug in production
export MCP_SERVER_HOST="0.0.0.0"
export MCP_SERVER_PORT=3001

# Maximum Security Configuration
export MCP_SECURITY_ENABLED=true
export MCP_REQUIRE_AUTH=true
export MCP_AUDIT_ENABLED=true

# Strict Rate Limiting
export MCP_RATE_LIMIT_ENABLED=true
export MCP_RATE_LIMIT_REQUESTS=100
export MCP_RATE_LIMIT_PERIOD=60
export MCP_RATE_LIMIT_BURST=5      # Lower burst in production

# Authentication and Session Management
export MCP_JWT_ENABLED=true
export MCP_PERMANENT_TOKEN_ENABLED=true
export MCP_SESSION_TIMEOUT=3600    # 1 hour sessions
export MCP_TOKEN_REFRESH_ENABLED=true
export MCP_REQUIRE_2FA_FOR_ADMIN=true

# Tool Access (Restricted)
export MCP_FAMILY_TOOLS_ENABLED=true
export MCP_AUTH_TOOLS_ENABLED=true
export MCP_PROFILE_TOOLS_ENABLED=true
export MCP_SHOP_TOOLS_ENABLED=true
export MCP_WORKSPACE_TOOLS_ENABLED=true
export MCP_ADMIN_TOOLS_ENABLED=false      # Disable admin tools in production
export MCP_SYSTEM_TOOLS_ENABLED=false     # Disable system tools in production

# Performance Settings (Optimized)
export MCP_MAX_CONCURRENT_TOOLS=50
export MCP_REQUEST_TIMEOUT=30
export MCP_TOOL_EXECUTION_TIMEOUT=60
export MCP_CONNECTION_TIMEOUT=10

# Advanced Security Features
export MCP_IP_LOCKDOWN_ENABLED=true
export MCP_USER_AGENT_LOCKDOWN_ENABLED=true
export MCP_ANOMALY_DETECTION_ENABLED=true
export MCP_AUTO_BLOCK_ENABLED=true
export MCP_BLOCK_DURATION=3600

# Network Security
export MCP_CORS_ENABLED=false      # Disable CORS in production
export MCP_ALLOWED_ORIGINS="https://yourdomain.com,https://api.yourdomain.com"
export MCP_IP_WHITELIST=""          # Configure based on your infrastructure
export MCP_GEO_BLOCKING_ENABLED=false # Enable if needed

# Monitoring and Observability
export MCP_METRICS_ENABLED=true
export MCP_HEALTH_CHECK_ENABLED=true
export MCP_PERFORMANCE_MONITORING=true

# Cache Settings (Optimized)
export MCP_CACHE_ENABLED=true
export MCP_CACHE_TTL=300           # 5 minutes
export MCP_CONTEXT_CACHE_TTL=60    # 1 minute

# Error Handling and Recovery
export MCP_ERROR_RECOVERY_ENABLED=true
export MCP_CIRCUIT_BREAKER_ENABLED=true
export MCP_RETRY_ENABLED=true
export MCP_RETRY_MAX_ATTEMPTS=3
export MCP_RETRY_BACKOFF_FACTOR=2.0

# Business Logic Limits (Production Values)
export MCP_FAMILY_MAX_MEMBERS=10
export MCP_WORKSPACE_MAX_MEMBERS=50
export MCP_SBD_MAX_REQUEST_AMOUNT=500
export MCP_SHOP_MAX_PURCHASE_AMOUNT=1000
```

#### Production Deployment with Kubernetes
```yaml
# k8s/mcp-production-config.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: mcp-production-config
  namespace: production
data:
  # Core Settings
  MCP_ENABLED: "true"
  MCP_DEBUG_MODE: "false"
  MCP_SERVER_HOST: "0.0.0.0"
  MCP_SERVER_PORT: "3001"
  
  # Security Settings
  MCP_SECURITY_ENABLED: "true"
  MCP_REQUIRE_AUTH: "true"
  MCP_AUDIT_ENABLED: "true"
  
  # Rate Limiting
  MCP_RATE_LIMIT_ENABLED: "true"
  MCP_RATE_LIMIT_REQUESTS: "100"
  MCP_RATE_LIMIT_PERIOD: "60"
  
  # Tool Access
  MCP_FAMILY_TOOLS_ENABLED: "true"
  MCP_AUTH_TOOLS_ENABLED: "true"
  MCP_PROFILE_TOOLS_ENABLED: "true"
  MCP_SHOP_TOOLS_ENABLED: "true"
  MCP_WORKSPACE_TOOLS_ENABLED: "true"
  MCP_ADMIN_TOOLS_ENABLED: "false"
  MCP_SYSTEM_TOOLS_ENABLED: "false"
  
  # Performance
  MCP_MAX_CONCURRENT_TOOLS: "50"
  MCP_REQUEST_TIMEOUT: "30"
  
  # Advanced Security
  MCP_IP_LOCKDOWN_ENABLED: "true"
  MCP_USER_AGENT_LOCKDOWN_ENABLED: "true"
  MCP_ANOMALY_DETECTION_ENABLED: "true"
  MCP_AUTO_BLOCK_ENABLED: "true"

---
apiVersion: v1
kind: Secret
metadata:
  name: mcp-production-secrets
  namespace: production
type: Opaque
stringData:
  SECRET_KEY: "your-production-secret-key"
  MONGODB_URL: "mongodb://mongodb-service:27017"
  REDIS_URL: "redis://redis-service:6379"
```

## Advanced Configuration Options

### Monitoring and Observability Configuration

#### Health Check and Metrics Settings
```bash
# Health Check Configuration
MCP_HEALTH_CHECK_ENABLED=true      # Enable health check endpoints (default: true)
MCP_HEALTH_CHECK_INTERVAL=30       # Health check interval in seconds (default: 30)
MCP_HEALTH_CHECK_TIMEOUT=5         # Health check timeout in seconds (default: 5)
MCP_HEALTH_CHECK_DEEP=true         # Enable deep health checks (default: true)

# Metrics and Monitoring
MCP_METRICS_ENABLED=true           # Enable metrics collection (default: true)
MCP_METRICS_PORT=9090              # Metrics endpoint port (default: 9090)
MCP_PROMETHEUS_ENABLED=true        # Enable Prometheus metrics (default: true)
MCP_PERFORMANCE_MONITORING=true    # Enable performance monitoring (default: true)

# Alerting Configuration
MCP_ALERTING_ENABLED=true          # Enable alerting system (default: true)
MCP_ALERT_ERROR_RATE_THRESHOLD=0.05 # Error rate threshold for alerts (5%)
MCP_ALERT_RESPONSE_TIME_THRESHOLD=5000 # Response time threshold in ms (5 seconds)
MCP_ALERT_CONCURRENT_TOOLS_THRESHOLD=40 # Concurrent tools threshold (80% of max)
MCP_ALERT_MEMORY_THRESHOLD=80      # Memory usage threshold percentage (80%)

# Log Configuration
MCP_LOG_LEVEL="INFO"               # Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
MCP_LOG_FORMAT="json"              # Log format (json, text) (default: json)
MCP_LOG_FILE_ENABLED=true          # Enable file logging (default: true)
MCP_LOG_FILE_PATH="/app/logs/mcp.log" # Log file path
MCP_LOG_ROTATION_SIZE=10485760     # Log rotation size in bytes (10MB)
MCP_LOG_RETENTION_DAYS=30          # Log retention in days (default: 30)
```

#### Performance Monitoring and Profiling
```bash
# Performance Tracking
MCP_TRACK_TOOL_PERFORMANCE=true    # Track individual tool performance (default: true)
MCP_TRACK_USER_SESSIONS=true       # Track user session metrics (default: true)
MCP_TRACK_RESOURCE_USAGE=true      # Track resource usage metrics (default: true)

# Profiling Configuration
MCP_PROFILING_ENABLED=false        # Enable performance profiling (default: false)
MCP_PROFILING_SAMPLE_RATE=0.01     # Profiling sample rate (1%) (default: 0.01)
MCP_PROFILING_OUTPUT_DIR="/app/profiles" # Profiling output directory

# Tracing Configuration
MCP_TRACING_ENABLED=false          # Enable distributed tracing (default: false)
MCP_TRACING_SAMPLE_RATE=0.1        # Tracing sample rate (10%) (default: 0.1)
MCP_JAEGER_ENDPOINT=""             # Jaeger endpoint for tracing
```

### Caching and Performance Configuration

#### Cache Management Settings
```bash
# Core Cache Configuration
MCP_CACHE_ENABLED=true             # Enable caching system (default: true)
MCP_CACHE_BACKEND="redis"          # Cache backend (redis, memory) (default: redis)
MCP_CACHE_TTL=300                  # Default cache TTL in seconds (5 minutes)
MCP_CACHE_MAX_SIZE=1000            # Maximum cache entries (default: 1000)

# Specific Cache Settings
MCP_CONTEXT_CACHE_TTL=60           # User context cache TTL in seconds (default: 60)
MCP_PERMISSION_CACHE_TTL=300       # Permission cache TTL in seconds (default: 300)
MCP_TOOL_RESULT_CACHE_TTL=180      # Tool result cache TTL in seconds (default: 180)
MCP_RESOURCE_CACHE_TTL=600         # Resource cache TTL in seconds (default: 600)

# Cache Optimization
MCP_CACHE_COMPRESSION_ENABLED=true # Enable cache compression (default: true)
MCP_CACHE_SERIALIZATION="pickle"   # Cache serialization format (pickle, json)
MCP_CACHE_KEY_PREFIX="mcp:"        # Cache key prefix (default: "mcp:")
MCP_CACHE_NAMESPACE_ENABLED=true   # Enable cache namespacing (default: true)

# Cache Invalidation
MCP_CACHE_AUTO_INVALIDATION=true   # Enable automatic cache invalidation (default: true)
MCP_CACHE_INVALIDATION_EVENTS=true # Enable event-based cache invalidation (default: true)
MCP_CACHE_WARMUP_ENABLED=true      # Enable cache warmup on startup (default: true)
```

#### Connection Pool and Resource Management
```bash
# Database Connection Pooling
MCP_DB_POOL_SIZE=20                # Database connection pool size (default: 20)
MCP_DB_MAX_OVERFLOW=30             # Maximum connection overflow (default: 30)
MCP_DB_POOL_TIMEOUT=30             # Connection pool timeout in seconds (default: 30)
MCP_DB_POOL_RECYCLE=3600          # Connection recycle time in seconds (default: 3600)

# Redis Connection Pooling
MCP_REDIS_POOL_SIZE=10             # Redis connection pool size (default: 10)
MCP_REDIS_MAX_CONNECTIONS=50       # Maximum Redis connections (default: 50)
MCP_REDIS_SOCKET_TIMEOUT=5         # Redis socket timeout in seconds (default: 5)
MCP_REDIS_SOCKET_CONNECT_TIMEOUT=5 # Redis connection timeout in seconds (default: 5)

# Memory Management
MCP_MEMORY_LIMIT_MB=512            # Memory limit per worker in MB (default: 512)
MCP_MEMORY_MONITORING_ENABLED=true # Enable memory monitoring (default: true)
MCP_GARBAGE_COLLECTION_THRESHOLD=100 # GC threshold for tool executions (default: 100)
MCP_MEMORY_CLEANUP_INTERVAL=300    # Memory cleanup interval in seconds (default: 300)
```

### Error Handling and Recovery Configuration

#### Circuit Breaker and Retry Settings
```bash
# Circuit Breaker Configuration
MCP_CIRCUIT_BREAKER_ENABLED=true   # Enable circuit breaker pattern (default: true)
MCP_CIRCUIT_BREAKER_FAILURE_THRESHOLD=5 # Failure threshold to open circuit (default: 5)
MCP_CIRCUIT_BREAKER_RECOVERY_TIMEOUT=60 # Recovery timeout in seconds (default: 60)
MCP_CIRCUIT_BREAKER_EXPECTED_EXCEPTION_RATE=0.5 # Expected exception rate (50%)

# Retry Configuration
MCP_RETRY_ENABLED=true             # Enable retry logic (default: true)
MCP_RETRY_MAX_ATTEMPTS=3           # Maximum retry attempts (default: 3)
MCP_RETRY_BACKOFF_FACTOR=2.0       # Exponential backoff factor (default: 2.0)
MCP_RETRY_MIN_DELAY=1              # Minimum retry delay in seconds (default: 1)
MCP_RETRY_MAX_DELAY=60             # Maximum retry delay in seconds (default: 60)

# Error Recovery
MCP_ERROR_RECOVERY_ENABLED=true    # Enable error recovery mechanisms (default: true)
MCP_GRACEFUL_DEGRADATION_ENABLED=true # Enable graceful degradation (default: true)
MCP_FALLBACK_RESPONSES_ENABLED=true # Enable fallback responses (default: true)
MCP_ERROR_NOTIFICATION_ENABLED=true # Enable error notifications (default: true)

# Timeout Configuration
MCP_GLOBAL_TIMEOUT=120             # Global operation timeout in seconds (default: 120)
MCP_DATABASE_TIMEOUT=30            # Database operation timeout in seconds (default: 30)
MCP_REDIS_TIMEOUT=10               # Redis operation timeout in seconds (default: 10)
MCP_EXTERNAL_API_TIMEOUT=15        # External API timeout in seconds (default: 15)
```

#### Error Classification and Handling
```bash
# Error Classification
MCP_ERROR_CLASSIFICATION_ENABLED=true # Enable error classification (default: true)
MCP_TRANSIENT_ERROR_RETRY=true     # Retry transient errors automatically (default: true)
MCP_PERMANENT_ERROR_RETRY=false    # Don't retry permanent errors (default: false)
MCP_UNKNOWN_ERROR_RETRY=true       # Retry unknown errors (default: true)

# Error Reporting
MCP_ERROR_REPORTING_ENABLED=true   # Enable error reporting (default: true)
MCP_ERROR_SAMPLING_RATE=1.0        # Error sampling rate (100%) (default: 1.0)
MCP_SENTRY_ENABLED=false           # Enable Sentry error tracking (default: false)
MCP_SENTRY_DSN=""                  # Sentry DSN for error tracking

# Error Response Configuration
MCP_DETAILED_ERRORS_IN_RESPONSE=false # Include detailed errors in responses (default: false)
MCP_ERROR_CODES_ENABLED=true       # Enable structured error codes (default: true)
MCP_USER_FRIENDLY_ERRORS=true      # Enable user-friendly error messages (default: true)
```

### Integration with Existing Systems Configuration

#### FastAPI Integration Settings
```bash
# FastAPI Lifecycle Integration
MCP_FASTAPI_INTEGRATION_ENABLED=true # Enable FastAPI integration (default: true)
MCP_LIFESPAN_INTEGRATION=true      # Integrate with FastAPI lifespan (default: true)
MCP_STARTUP_TIMEOUT=60             # Startup timeout in seconds (default: 60)
MCP_SHUTDOWN_TIMEOUT=30            # Shutdown timeout in seconds (default: 30)

# Dependency Injection
MCP_USE_EXISTING_DEPENDENCIES=true # Use existing FastAPI dependencies (default: true)
MCP_AUTH_DEPENDENCY_OVERRIDE=false # Override auth dependency (default: false)
MCP_DB_DEPENDENCY_OVERRIDE=false   # Override database dependency (default: false)

# Route Integration
MCP_HEALTH_ROUTES_ENABLED=true     # Enable MCP health routes (default: true)
MCP_METRICS_ROUTES_ENABLED=true    # Enable MCP metrics routes (default: true)
MCP_ADMIN_ROUTES_ENABLED=false     # Enable MCP admin routes (default: false)
```

#### Database Integration Settings
```bash
# MongoDB Integration
MCP_USE_EXISTING_DB_MANAGER=true   # Use existing database manager (default: true)
MCP_DB_COLLECTION_PREFIX="mcp_"    # Collection prefix for MCP data (default: "mcp_")
MCP_AUDIT_COLLECTION="mcp_audit_log" # Audit log collection name
MCP_METRICS_COLLECTION="mcp_metrics" # Metrics collection name

# Database Indexes
MCP_AUTO_CREATE_INDEXES=true       # Auto-create required indexes (default: true)
MCP_INDEX_BACKGROUND_CREATION=true # Create indexes in background (default: true)
MCP_COMPOUND_INDEXES_ENABLED=true  # Enable compound indexes (default: true)

# Data Retention
MCP_AUDIT_LOG_RETENTION_DAYS=90    # Audit log retention in days (default: 90)
MCP_METRICS_RETENTION_DAYS=30      # Metrics retention in days (default: 30)
MCP_SESSION_DATA_RETENTION_HOURS=24 # Session data retention in hours (default: 24)
```

#### Redis Integration Settings
```bash
# Redis Manager Integration
MCP_USE_EXISTING_REDIS_MANAGER=true # Use existing Redis manager (default: true)
MCP_REDIS_KEY_PREFIX="mcp:"        # Redis key prefix (default: "mcp:")
MCP_REDIS_NAMESPACE="second_brain" # Redis namespace (default: "second_brain")

# Redis Usage Patterns
MCP_REDIS_FOR_CACHING=true         # Use Redis for caching (default: true)
MCP_REDIS_FOR_RATE_LIMITING=true   # Use Redis for rate limiting (default: true)
MCP_REDIS_FOR_SESSIONS=true        # Use Redis for session storage (default: true)
MCP_REDIS_FOR_LOCKS=true           # Use Redis for distributed locks (default: true)

# Redis Configuration
MCP_REDIS_CLUSTER_MODE=false       # Enable Redis cluster mode (default: false)
MCP_REDIS_SENTINEL_MODE=false      # Enable Redis sentinel mode (default: false)
MCP_REDIS_SSL_ENABLED=false        # Enable Redis SSL (default: false)
```

#### Authentication System Integration
```bash
# Authentication Integration
MCP_USE_EXISTING_AUTH_SYSTEM=true  # Use existing auth system (default: true)
MCP_AUTH_MANAGER_INTEGRATION=true  # Integrate with existing auth manager (default: true)
MCP_SECURITY_MANAGER_INTEGRATION=true # Integrate with security manager (default: true)

# Token Validation
MCP_JWT_VALIDATION_STRICT=true     # Strict JWT validation (default: true)
MCP_TOKEN_BLACKLIST_ENABLED=true   # Enable token blacklisting (default: true)
MCP_TOKEN_REFRESH_INTEGRATION=true # Integrate with token refresh (default: true)

# Permission System Integration
MCP_USE_EXISTING_PERMISSIONS=true  # Use existing permission system (default: true)
MCP_RBAC_INTEGRATION=true          # Integrate with RBAC system (default: true)
MCP_PERMISSION_CACHING_ENABLED=true # Enable permission caching (default: true)
```

#### Logging System Integration
```bash
# Logging Manager Integration
MCP_USE_EXISTING_LOGGING=true      # Use existing logging manager (default: true)
MCP_STRUCTURED_LOGGING=true        # Enable structured logging (default: true)
MCP_LOG_CORRELATION_ID=true        # Enable log correlation IDs (default: true)

# Log Aggregation
MCP_LOG_AGGREGATION_ENABLED=false  # Enable log aggregation (default: false)
MCP_ELASTICSEARCH_ENABLED=false    # Enable Elasticsearch logging (default: false)
MCP_FLUENTD_ENABLED=false          # Enable Fluentd logging (default: false)
MCP_SYSLOG_ENABLED=false           # Enable syslog integration (default: false)

# Audit Integration
MCP_AUDIT_INTEGRATION_ENABLED=true # Enable audit integration (default: true)
MCP_AUDIT_STRUCTURED_FORMAT=true   # Use structured audit format (default: true)
MCP_AUDIT_REAL_TIME_STREAMING=false # Enable real-time audit streaming (default: false)
```

## Security Configuration Best Practices

### Production Security Hardening

#### Essential Security Settings
```bash
# === CRITICAL SECURITY SETTINGS ===
# These settings MUST be configured for production

# Core Security
MCP_SECURITY_ENABLED=true          # NEVER disable in production
MCP_REQUIRE_AUTH=true              # ALWAYS require authentication
MCP_DEBUG_MODE=false               # NEVER enable debug in production

# Authentication Security
MCP_JWT_ENABLED=true
MCP_SESSION_TIMEOUT=3600           # 1 hour maximum
MCP_TOKEN_REFRESH_ENABLED=true
MCP_REQUIRE_2FA_FOR_ADMIN=true     # MANDATORY for admin operations

# Rate Limiting (CRITICAL for DoS protection)
MCP_RATE_LIMIT_ENABLED=true
MCP_RATE_LIMIT_REQUESTS=100        # Adjust based on expected load
MCP_RATE_LIMIT_PERIOD=60
MCP_RATE_LIMIT_BURST=5             # Low burst in production

# Access Control
MCP_ADMIN_TOOLS_ENABLED=false      # DISABLE admin tools in production
MCP_SYSTEM_TOOLS_ENABLED=false     # DISABLE system tools in production
MCP_IP_LOCKDOWN_ENABLED=true       # ENABLE IP lockdown
MCP_USER_AGENT_LOCKDOWN_ENABLED=true # ENABLE user agent lockdown

# Monitoring and Alerting (ESSENTIAL for security)
MCP_AUDIT_ENABLED=true             # MANDATORY for compliance
MCP_ANOMALY_DETECTION_ENABLED=true # ENABLE threat detection
MCP_AUTO_BLOCK_ENABLED=true        # ENABLE automatic blocking
```

#### Network Security Configuration
```bash
# Network Access Control
MCP_CORS_ENABLED=false             # DISABLE CORS in production
MCP_ALLOWED_ORIGINS="https://yourdomain.com" # RESTRICT to your domains only
MCP_IP_WHITELIST="10.0.0.0/8,172.16.0.0/12" # WHITELIST internal networks only

# Geographic and Advanced Controls
MCP_GEO_BLOCKING_ENABLED=true      # ENABLE if serving specific regions
MCP_ALLOWED_COUNTRIES="US,CA,GB"   # RESTRICT to allowed countries
MCP_DEVICE_FINGERPRINTING_ENABLED=true # ENABLE device tracking

# TLS and Encryption
MCP_TLS_REQUIRED=true              # REQUIRE TLS for all connections
MCP_TLS_MIN_VERSION="1.2"          # MINIMUM TLS 1.2
MCP_HSTS_ENABLED=true              # ENABLE HTTP Strict Transport Security
```

#### Data Protection Settings
```bash
# Data Encryption
MCP_ENCRYPT_SENSITIVE_DATA=true    # ENCRYPT sensitive data at rest
MCP_ENCRYPT_AUDIT_LOGS=true        # ENCRYPT audit logs
MCP_ENCRYPT_CACHE_DATA=true        # ENCRYPT cached data

# Data Retention and Privacy
MCP_DATA_RETENTION_ENABLED=true    # ENABLE data retention policies
MCP_AUDIT_LOG_RETENTION_DAYS=90    # MINIMUM 90 days for compliance
MCP_PII_ANONYMIZATION_ENABLED=true # ANONYMIZE PII in logs
MCP_GDPR_COMPLIANCE_MODE=true      # ENABLE GDPR compliance features
```

### Security Configuration Validation

#### Automated Security Validation Script
```bash
#!/bin/bash
# validate-mcp-security.sh

echo "Validating MCP security configuration..."

# Check critical security settings
python3 << 'EOF'
import os
import sys

def check_setting(name, expected_value=None, required=True):
    value = os.getenv(name)
    if required and not value:
        print(f"❌ CRITICAL: {name} is not set")
        return False
    if expected_value and value != expected_value:
        print(f"⚠️  WARNING: {name} is '{value}', expected '{expected_value}'")
        return False
    print(f"✅ {name}: {value}")
    return True

# Critical security checks
security_ok = True
security_ok &= check_setting("MCP_SECURITY_ENABLED", "true")
security_ok &= check_setting("MCP_REQUIRE_AUTH", "true")
security_ok &= check_setting("MCP_DEBUG_MODE", "false")
security_ok &= check_setting("MCP_RATE_LIMIT_ENABLED", "true")
security_ok &= check_setting("MCP_AUDIT_ENABLED", "true")
security_ok &= check_setting("MCP_ADMIN_TOOLS_ENABLED", "false")

# Check for dangerous settings
if os.getenv("MCP_CORS_ENABLED") == "true":
    print("⚠️  WARNING: CORS is enabled - ensure ALLOWED_ORIGINS is restricted")

if os.getenv("MCP_ALLOWED_ORIGINS") == "*":
    print("❌ CRITICAL: CORS allows all origins - major security risk")
    security_ok = False

if not security_ok:
    print("\n❌ Security validation FAILED - fix issues before deployment")
    sys.exit(1)
else:
    print("\n✅ Security validation PASSED")
EOF

echo "Security validation completed."
```

#### Security Checklist for Production
```bash
# Production Security Checklist
# Run this before deploying to production

echo "=== MCP PRODUCTION SECURITY CHECKLIST ==="

# 1. Authentication and Authorization
[ "$MCP_SECURITY_ENABLED" = "true" ] && echo "✅ Security enabled" || echo "❌ Security disabled"
[ "$MCP_REQUIRE_AUTH" = "true" ] && echo "✅ Authentication required" || echo "❌ Authentication not required"
[ "$MCP_ADMIN_TOOLS_ENABLED" = "false" ] && echo "✅ Admin tools disabled" || echo "❌ Admin tools enabled"

# 2. Rate Limiting and DoS Protection
[ "$MCP_RATE_LIMIT_ENABLED" = "true" ] && echo "✅ Rate limiting enabled" || echo "❌ Rate limiting disabled"
[ "$MCP_AUTO_BLOCK_ENABLED" = "true" ] && echo "✅ Auto-blocking enabled" || echo "❌ Auto-blocking disabled"

# 3. Monitoring and Auditing
[ "$MCP_AUDIT_ENABLED" = "true" ] && echo "✅ Audit logging enabled" || echo "❌ Audit logging disabled"
[ "$MCP_ANOMALY_DETECTION_ENABLED" = "true" ] && echo "✅ Anomaly detection enabled" || echo "❌ Anomaly detection disabled"

# 4. Network Security
[ "$MCP_CORS_ENABLED" = "false" ] && echo "✅ CORS disabled" || echo "⚠️  CORS enabled - check origins"
[ -n "$MCP_IP_WHITELIST" ] && echo "✅ IP whitelist configured" || echo "⚠️  No IP whitelist"

# 5. Debug and Development Features
[ "$MCP_DEBUG_MODE" = "false" ] && echo "✅ Debug mode disabled" || echo "❌ Debug mode enabled"
[ "$MCP_PROFILING_ENABLED" = "false" ] && echo "✅ Profiling disabled" || echo "⚠️  Profiling enabled"

echo "=== END SECURITY CHECKLIST ==="
```

## Configuration Validation and Troubleshooting

### Comprehensive Configuration Validation

#### Required Settings Validation
```bash
# Required environment variables for MCP server
REQUIRED_SETTINGS=(
    "SECRET_KEY"                    # JWT secret key (minimum 32 characters)
    "MONGODB_URL"                   # MongoDB connection string
    "MONGODB_DATABASE"              # MongoDB database name
    "REDIS_URL"                     # Redis connection string
)

# MCP-specific required settings
MCP_REQUIRED_SETTINGS=(
    "MCP_ENABLED"                   # Must be 'true' to start MCP server
    "MCP_SERVER_PORT"               # Port number (1024-65535)
    "MCP_SECURITY_ENABLED"          # Must be 'true' for production
)

# Validation script
for setting in "${REQUIRED_SETTINGS[@]}"; do
    if [ -z "${!setting}" ]; then
        echo "❌ ERROR: Required setting $setting is not configured"
        exit 1
    fi
done

echo "✅ All required settings are configured"
```

#### Configuration Testing Script
```bash
#!/bin/bash
# test-mcp-config.sh

echo "Testing MCP configuration..."

# Test configuration loading
python3 -c "
from src.second_brain_database.config import settings
print(f'✅ Configuration loaded successfully')
print(f'   MCP Enabled: {settings.MCP_ENABLED}')
print(f'   Server Port: {settings.MCP_SERVER_PORT}')
print(f'   Security: {settings.MCP_SECURITY_ENABLED}')
print(f'   Debug Mode: {settings.MCP_DEBUG_MODE}')
" || {
    echo "❌ Configuration loading failed"
    exit 1
}

# Test database connectivity
python3 -c "
from src.second_brain_database.database import db_manager
try:
    info = db_manager.client.server_info()
    print(f'✅ MongoDB connected: {info[\"version\"]}')
except Exception as e:
    print(f'❌ MongoDB connection failed: {e}')
    exit(1)
" || exit 1

# Test Redis connectivity
python3 -c "
from src.second_brain_database.managers.redis_manager import redis_manager
try:
    redis_manager.client.ping()
    print('✅ Redis connected successfully')
except Exception as e:
    print(f'❌ Redis connection failed: {e}')
    exit(1)
" || exit 1

echo "✅ All configuration tests passed"
```

### Common Configuration Issues and Solutions

#### Issue 1: MCP Server Won't Start
```bash
# Diagnostic steps
echo "Diagnosing MCP server startup issues..."

# Check if MCP is enabled
if [ "$MCP_ENABLED" != "true" ]; then
    echo "❌ MCP_ENABLED is not set to 'true'"
    echo "Solution: export MCP_ENABLED=true"
fi

# Check port availability
if netstat -tlnp | grep -q ":$MCP_SERVER_PORT "; then
    echo "❌ Port $MCP_SERVER_PORT is already in use"
    echo "Solution: Change MCP_SERVER_PORT or kill process using the port"
    lsof -i :$MCP_SERVER_PORT
fi

# Check dependencies
python3 -c "
try:
    import fastmcp
    print('✅ FastMCP dependency available')
except ImportError:
    print('❌ FastMCP not installed')
    print('Solution: uv add fastmcp')
"
```

#### Issue 2: Authentication Failures
```bash
# Diagnostic steps for auth issues
echo "Diagnosing authentication issues..."

# Check JWT secret
if [ ${#SECRET_KEY} -lt 32 ]; then
    echo "❌ SECRET_KEY is too short (minimum 32 characters)"
    echo "Solution: Generate a longer secret key"
fi

# Check auth configuration
python3 -c "
from src.second_brain_database.config import settings
if not settings.MCP_SECURITY_ENABLED:
    print('❌ MCP security is disabled')
if not settings.MCP_REQUIRE_AUTH:
    print('❌ Authentication is not required')
print('✅ Authentication configuration checked')
"
```

#### Issue 3: Performance Problems
```bash
# Performance diagnostic script
echo "Diagnosing MCP performance issues..."

# Check resource limits
python3 -c "
import psutil
import os

# Memory usage
memory = psutil.virtual_memory()
print(f'Memory usage: {memory.percent}%')
if memory.percent > 80:
    print('⚠️  High memory usage detected')

# CPU usage
cpu = psutil.cpu_percent(interval=1)
print(f'CPU usage: {cpu}%')
if cpu > 80:
    print('⚠️  High CPU usage detected')

# Check MCP-specific settings
mcp_concurrent = os.getenv('MCP_MAX_CONCURRENT_TOOLS', '50')
print(f'Max concurrent tools: {mcp_concurrent}')
if int(mcp_concurrent) > 100:
    print('⚠️  Very high concurrent tool limit')
"

# Check database performance
python3 -c "
from src.second_brain_database.database import db_manager
import time

start = time.time()
try:
    db_manager.client.admin.command('ping')
    duration = time.time() - start
    print(f'Database ping: {duration*1000:.2f}ms')
    if duration > 0.1:
        print('⚠️  Slow database response')
except Exception as e:
    print(f'❌ Database error: {e}')
"
```

### Configuration Backup and Recovery

#### Configuration Backup Script
```bash
#!/bin/bash
# backup-mcp-config.sh

BACKUP_DIR="/backups/mcp-config"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

# Backup configuration files
echo "Backing up MCP configuration..."

# Environment files
[ -f .sbd ] && cp .sbd "$BACKUP_DIR/sbd_$DATE"
[ -f .env ] && cp .env "$BACKUP_DIR/env_$DATE"
[ -f .env.production ] && cp .env.production "$BACKUP_DIR/env_production_$DATE"

# Docker and Kubernetes configs
[ -f docker-compose.yml ] && cp docker-compose.yml "$BACKUP_DIR/docker_compose_$DATE.yml"
[ -d k8s ] && tar -czf "$BACKUP_DIR/k8s_config_$DATE.tar.gz" k8s/

# Current environment variables
env | grep MCP_ > "$BACKUP_DIR/mcp_env_vars_$DATE.txt"

echo "Configuration backup completed: $BACKUP_DIR"
```

#### Configuration Recovery Script
```bash
#!/bin/bash
# restore-mcp-config.sh

BACKUP_DIR="/backups/mcp-config"
RESTORE_DATE="$1"

if [ -z "$RESTORE_DATE" ]; then
    echo "Usage: $0 <backup_date>"
    echo "Available backups:"
    ls -la "$BACKUP_DIR" | grep -E "(sbd|env)_[0-9]{8}_[0-9]{6}"
    exit 1
fi

echo "Restoring MCP configuration from $RESTORE_DATE..."

# Restore configuration files
[ -f "$BACKUP_DIR/sbd_$RESTORE_DATE" ] && cp "$BACKUP_DIR/sbd_$RESTORE_DATE" .sbd
[ -f "$BACKUP_DIR/env_$RESTORE_DATE" ] && cp "$BACKUP_DIR/env_$RESTORE_DATE" .env

# Validate restored configuration
./validate-mcp-security.sh

echo "Configuration restored successfully"
```

## Complete Configuration Examples

### Minimal Configuration (Quick Start)
```bash
# .sbd - Minimal configuration for local development
MCP_ENABLED=true
MCP_DEBUG_MODE=true
MCP_SECURITY_ENABLED=true
MCP_RATE_LIMIT_ENABLED=false
```

### High-Security Enterprise Configuration
```bash
# .sbd - Maximum security for enterprise production
# === CORE SECURITY ===
MCP_ENABLED=true
MCP_SECURITY_ENABLED=true
MCP_REQUIRE_AUTH=true
MCP_DEBUG_MODE=false

# === AUTHENTICATION ===
MCP_JWT_ENABLED=true
MCP_PERMANENT_TOKEN_ENABLED=true
MCP_SESSION_TIMEOUT=1800           # 30 minutes
MCP_REQUIRE_2FA_FOR_ADMIN=true
MCP_TOKEN_REFRESH_ENABLED=true

# === RATE LIMITING ===
MCP_RATE_LIMIT_ENABLED=true
MCP_RATE_LIMIT_REQUESTS=50         # Conservative limit
MCP_RATE_LIMIT_PERIOD=60
MCP_RATE_LIMIT_BURST=3             # Very low burst

# === ACCESS CONTROL ===
MCP_ADMIN_TOOLS_ENABLED=false
MCP_SYSTEM_TOOLS_ENABLED=false
MCP_IP_LOCKDOWN_ENABLED=true
MCP_USER_AGENT_LOCKDOWN_ENABLED=true
MCP_GEO_BLOCKING_ENABLED=true
MCP_ALLOWED_COUNTRIES="US,CA"

# === MONITORING ===
MCP_AUDIT_ENABLED=true
MCP_ANOMALY_DETECTION_ENABLED=true
MCP_AUTO_BLOCK_ENABLED=true
MCP_BLOCK_DURATION=7200            # 2 hours

# === NETWORK SECURITY ===
MCP_CORS_ENABLED=false
MCP_ALLOWED_ORIGINS="https://secure.yourdomain.com"
MCP_IP_WHITELIST="10.0.0.0/8"
MCP_TLS_REQUIRED=true

# === DATA PROTECTION ===
MCP_ENCRYPT_SENSITIVE_DATA=true
MCP_ENCRYPT_AUDIT_LOGS=true
MCP_PII_ANONYMIZATION_ENABLED=true
MCP_GDPR_COMPLIANCE_MODE=true
```

### High-Performance Configuration
```bash
# .sbd - Optimized for high-performance production
# === PERFORMANCE SETTINGS ===
MCP_ENABLED=true
MCP_MAX_CONCURRENT_TOOLS=100       # High concurrency
MCP_REQUEST_TIMEOUT=45
MCP_TOOL_EXECUTION_TIMEOUT=90

# === CONNECTION POOLING ===
MCP_DB_POOL_SIZE=50
MCP_DB_MAX_OVERFLOW=100
MCP_REDIS_POOL_SIZE=25
MCP_REDIS_MAX_CONNECTIONS=100

# === CACHING OPTIMIZATION ===
MCP_CACHE_ENABLED=true
MCP_CACHE_TTL=600                  # 10 minutes
MCP_CONTEXT_CACHE_TTL=120          # 2 minutes
MCP_PERMISSION_CACHE_TTL=600
MCP_CACHE_COMPRESSION_ENABLED=true

# === MEMORY MANAGEMENT ===
MCP_MEMORY_LIMIT_MB=1024           # 1GB per worker
MCP_GARBAGE_COLLECTION_THRESHOLD=50
MCP_MEMORY_CLEANUP_INTERVAL=180

# === ERROR HANDLING ===
MCP_CIRCUIT_BREAKER_ENABLED=true
MCP_RETRY_ENABLED=true
MCP_RETRY_MAX_ATTEMPTS=2           # Fast failure
MCP_GRACEFUL_DEGRADATION_ENABLED=true

# === MONITORING ===
MCP_METRICS_ENABLED=true
MCP_PERFORMANCE_MONITORING=true
MCP_PROFILING_ENABLED=false        # Disable in production
```

### Multi-Tenant SaaS Configuration
```bash
# .sbd - Configuration for multi-tenant SaaS deployment
# === TENANT ISOLATION ===
MCP_ENABLED=true
MCP_MULTI_TENANT_MODE=true
MCP_TENANT_ISOLATION_ENABLED=true
MCP_TENANT_RATE_LIMITING=true

# === SECURITY ===
MCP_SECURITY_ENABLED=true
MCP_REQUIRE_AUTH=true
MCP_TENANT_BASED_AUTH=true
MCP_CROSS_TENANT_ACCESS_DENIED=true

# === RATE LIMITING PER TENANT ===
MCP_RATE_LIMIT_ENABLED=true
MCP_RATE_LIMIT_PER_TENANT=true
MCP_TENANT_RATE_LIMIT_REQUESTS=200
MCP_TENANT_BURST_LIMIT=20

# === RESOURCE LIMITS PER TENANT ===
MCP_TENANT_MAX_CONCURRENT_TOOLS=20
MCP_TENANT_MAX_FAMILIES=5
MCP_TENANT_MAX_WORKSPACES=10
MCP_TENANT_STORAGE_LIMIT_MB=1000

# === MONITORING PER TENANT ===
MCP_TENANT_METRICS_ENABLED=true
MCP_TENANT_AUDIT_SEPARATION=true
MCP_TENANT_BILLING_METRICS=true

# === CACHING ===
MCP_TENANT_CACHE_ISOLATION=true
MCP_CACHE_NAMESPACE_ENABLED=true
```

### Development Team Configuration
```bash
# .sbd - Developer-friendly configuration with security
# === DEVELOPMENT FEATURES ===
MCP_ENABLED=true
MCP_DEBUG_MODE=true
MCP_SECURITY_ENABLED=true          # Keep security for realistic testing
MCP_RATE_LIMIT_ENABLED=false       # Disable to avoid interruptions

# === TOOL ACCESS ===
MCP_FAMILY_TOOLS_ENABLED=true
MCP_AUTH_TOOLS_ENABLED=true
MCP_PROFILE_TOOLS_ENABLED=true
MCP_SHOP_TOOLS_ENABLED=true
MCP_WORKSPACE_TOOLS_ENABLED=true
MCP_ADMIN_TOOLS_ENABLED=true       # Enable for testing
MCP_SYSTEM_TOOLS_ENABLED=true      # Enable for debugging

# === DEVELOPMENT CONVENIENCE ===
MCP_CORS_ENABLED=true
MCP_ALLOWED_ORIGINS="http://localhost:3000,http://localhost:8080,http://127.0.0.1:3000"
MCP_AUTO_BLOCK_ENABLED=false       # Don't block during development
MCP_ANOMALY_DETECTION_ENABLED=false # Avoid false positives

# === DEBUGGING ===
MCP_DETAILED_ERRORS_IN_RESPONSE=true # Show detailed errors
MCP_PROFILING_ENABLED=true         # Enable profiling for optimization
MCP_TRACING_ENABLED=true           # Enable tracing for debugging

# === FAST ITERATION ===
MCP_CACHE_TTL=30                   # Short cache for rapid changes
MCP_CONTEXT_CACHE_TTL=10
MCP_HOT_RELOAD_ENABLED=true        # Enable hot reload if supported
```

### Microservices Configuration
```bash
# .sbd - Configuration for microservices architecture
# === SERVICE DISCOVERY ===
MCP_ENABLED=true
MCP_SERVICE_NAME="mcp-gateway"
MCP_SERVICE_VERSION="1.0.0"
MCP_HEALTH_CHECK_ENABLED=true

# === INTER-SERVICE COMMUNICATION ===
MCP_SERVICE_MESH_ENABLED=true
MCP_ISTIO_INTEGRATION=true
MCP_CONSUL_INTEGRATION=false
MCP_CIRCUIT_BREAKER_ENABLED=true

# === DISTRIBUTED TRACING ===
MCP_TRACING_ENABLED=true
MCP_JAEGER_ENDPOINT="http://jaeger:14268/api/traces"
MCP_TRACE_SAMPLING_RATE=0.1

# === METRICS AND MONITORING ===
MCP_PROMETHEUS_ENABLED=true
MCP_METRICS_PORT=9090
MCP_CUSTOM_METRICS_ENABLED=true
MCP_SLI_SLO_MONITORING=true

# === RESILIENCE ===
MCP_BULKHEAD_PATTERN_ENABLED=true
MCP_TIMEOUT_CASCADING_PREVENTION=true
MCP_GRACEFUL_DEGRADATION_ENABLED=true
MCP_FALLBACK_RESPONSES_ENABLED=true

# === SECURITY IN MICROSERVICES ===
MCP_MUTUAL_TLS_ENABLED=true
MCP_SERVICE_TO_SERVICE_AUTH=true
MCP_JWT_VALIDATION_STRICT=true
```

## Configuration Management Best Practices

### Security Best Practices

#### Secret Management
```bash
# 1. NEVER commit secrets to version control
# Use .gitignore to exclude configuration files
echo ".sbd" >> .gitignore
echo ".env*" >> .gitignore
echo "secrets/" >> .gitignore

# 2. Use environment variables for sensitive data in production
export SECRET_KEY=$(openssl rand -base64 32)
export MONGODB_PASSWORD=$(vault kv get -field=password secret/mongodb)

# 3. Rotate secrets regularly
# Example: Monthly JWT secret rotation
NEW_SECRET=$(openssl rand -base64 32)
kubectl create secret generic mcp-secrets --from-literal=SECRET_KEY="$NEW_SECRET"

# 4. Use secret management services
# AWS Secrets Manager
SECRET_KEY=$(aws secretsmanager get-secret-value --secret-id prod/mcp/jwt-key --query SecretString --output text)

# HashiCorp Vault
SECRET_KEY=$(vault kv get -field=jwt_key secret/mcp/production)
```

#### Configuration Validation and Auditing
```bash
# 5. Validate configuration before deployment
./scripts/validate-mcp-config.sh production

# 6. Audit configuration changes
git log --oneline -- .sbd docker-compose.yml k8s/

# 7. Use configuration as code
# Store infrastructure configuration in version control
# Use tools like Terraform, Ansible, or Kubernetes manifests
```

### Environment Management

#### Environment Separation Strategy
```bash
# 1. Use separate configuration files per environment
.sbd.development      # Development settings
.sbd.staging         # Staging settings  
.sbd.production      # Production settings (template only, use env vars)

# 2. Environment-specific validation
case "$ENVIRONMENT" in
    "production")
        # Strict validation for production
        [ "$MCP_DEBUG_MODE" = "false" ] || { echo "Debug mode must be disabled in production"; exit 1; }
        [ "$MCP_ADMIN_TOOLS_ENABLED" = "false" ] || { echo "Admin tools must be disabled in production"; exit 1; }
        ;;
    "development")
        # Relaxed validation for development
        echo "Development environment - relaxed validation"
        ;;
esac

# 3. Configuration promotion pipeline
# Development -> Staging -> Production
# Each environment validates configuration before promotion
```

#### Infrastructure as Code
```yaml
# terraform/mcp-config.tf
resource "kubernetes_config_map" "mcp_config" {
  metadata {
    name      = "mcp-config"
    namespace = var.environment
  }

  data = {
    MCP_ENABLED                = "true"
    MCP_SECURITY_ENABLED      = var.environment == "production" ? "true" : "true"
    MCP_DEBUG_MODE            = var.environment == "production" ? "false" : "true"
    MCP_ADMIN_TOOLS_ENABLED   = var.environment == "production" ? "false" : "true"
    MCP_RATE_LIMIT_REQUESTS   = var.environment == "production" ? "100" : "200"
  }
}
```

### Monitoring and Alerting

#### Configuration Drift Detection
```bash
#!/bin/bash
# monitor-config-drift.sh

# Compare current configuration with baseline
BASELINE_CONFIG="/etc/mcp/baseline.sbd"
CURRENT_CONFIG=".sbd"

if ! diff -q "$BASELINE_CONFIG" "$CURRENT_CONFIG" > /dev/null; then
    echo "⚠️  Configuration drift detected!"
    diff "$BASELINE_CONFIG" "$CURRENT_CONFIG"
    
    # Send alert
    curl -X POST "$SLACK_WEBHOOK" -d "{\"text\":\"MCP configuration drift detected in $ENVIRONMENT\"}"
fi
```

#### Configuration Change Alerts
```yaml
# prometheus-alerts.yml
groups:
- name: mcp-config
  rules:
  - alert: MCPConfigurationChanged
    expr: increase(mcp_config_reload_total[5m]) > 0
    for: 0m
    labels:
      severity: warning
    annotations:
      summary: "MCP configuration has been reloaded"
      description: "MCP server configuration was reloaded {{ $value }} times in the last 5 minutes"

  - alert: MCPSecurityDisabled
    expr: mcp_security_enabled == 0
    for: 0m
    labels:
      severity: critical
    annotations:
      summary: "MCP security has been disabled"
      description: "MCP server is running with security disabled - immediate action required"
```

### Configuration Backup and Recovery

#### Automated Backup Strategy
```bash
#!/bin/bash
# backup-mcp-config-automated.sh

BACKUP_BUCKET="s3://your-backup-bucket/mcp-config"
DATE=$(date +%Y%m%d_%H%M%S)
ENVIRONMENT=${ENVIRONMENT:-production}

# Create backup archive
tar -czf "mcp-config-$ENVIRONMENT-$DATE.tar.gz" \
    .sbd* \
    docker-compose*.yml \
    k8s/ \
    nginx.conf

# Upload to S3 with versioning
aws s3 cp "mcp-config-$ENVIRONMENT-$DATE.tar.gz" \
    "$BACKUP_BUCKET/$ENVIRONMENT/" \
    --storage-class STANDARD_IA

# Cleanup local backup
rm "mcp-config-$ENVIRONMENT-$DATE.tar.gz"

# Retain only last 30 days of backups
aws s3 ls "$BACKUP_BUCKET/$ENVIRONMENT/" | \
    awk '{print $4}' | \
    sort | \
    head -n -30 | \
    xargs -I {} aws s3 rm "$BACKUP_BUCKET/$ENVIRONMENT/{}"

echo "Configuration backup completed for $ENVIRONMENT"
```

#### Disaster Recovery Procedures
```bash
#!/bin/bash
# restore-mcp-config-disaster.sh

ENVIRONMENT=${1:-production}
BACKUP_DATE=${2:-latest}

echo "Starting disaster recovery for MCP configuration..."
echo "Environment: $ENVIRONMENT"
echo "Backup date: $BACKUP_DATE"

# Download latest backup if no specific date provided
if [ "$BACKUP_DATE" = "latest" ]; then
    BACKUP_FILE=$(aws s3 ls "s3://your-backup-bucket/mcp-config/$ENVIRONMENT/" | \
                  sort | tail -n 1 | awk '{print $4}')
else
    BACKUP_FILE="mcp-config-$ENVIRONMENT-$BACKUP_DATE.tar.gz"
fi

# Download and extract backup
aws s3 cp "s3://your-backup-bucket/mcp-config/$ENVIRONMENT/$BACKUP_FILE" .
tar -xzf "$BACKUP_FILE"

# Validate restored configuration
./scripts/validate-mcp-config.sh "$ENVIRONMENT"

# Apply configuration based on deployment method
case "$DEPLOYMENT_METHOD" in
    "docker-compose")
        docker-compose -f "docker-compose.$ENVIRONMENT.yml" up -d
        ;;
    "kubernetes")
        kubectl apply -f k8s/
        ;;
    *)
        echo "Unknown deployment method: $DEPLOYMENT_METHOD"
        exit 1
        ;;
esac

# Verify service health
sleep 30
curl -f "http://localhost:8000/health/mcp/server" || {
    echo "❌ MCP server health check failed after restore"
    exit 1
}

echo "✅ Disaster recovery completed successfully"
```

## Advanced Troubleshooting

### Configuration Debugging Tools

#### Comprehensive Configuration Diagnostic
```bash
#!/bin/bash
# diagnose-mcp-config.sh

echo "=== MCP CONFIGURATION DIAGNOSTIC ==="

# 1. Environment Analysis
echo "1. Environment Analysis:"
echo "   Current environment: ${ENVIRONMENT:-not_set}"
echo "   Configuration files:"
ls -la .sbd* .env* 2>/dev/null || echo "   No configuration files found"

# 2. Configuration Loading Test
echo "2. Configuration Loading:"
python3 -c "
try:
    from src.second_brain_database.config import settings
    print(f'   ✅ Configuration loaded successfully')
    print(f'   MCP Enabled: {settings.MCP_ENABLED}')
    print(f'   Server Port: {settings.MCP_SERVER_PORT}')
    print(f'   Security: {settings.MCP_SECURITY_ENABLED}')
    print(f'   Debug Mode: {settings.MCP_DEBUG_MODE}')
except Exception as e:
    print(f'   ❌ Configuration loading failed: {e}')
"

# 3. Dependency Check
echo "3. Dependency Check:"
python3 -c "
dependencies = ['fastmcp', 'fastapi', 'pydantic', 'pymongo', 'redis']
for dep in dependencies:
    try:
        __import__(dep)
        print(f'   ✅ {dep} available')
    except ImportError:
        print(f'   ❌ {dep} missing')
"

# 4. Network Connectivity
echo "4. Network Connectivity:"
# Check if port is available
if netstat -tlnp 2>/dev/null | grep -q ":${MCP_SERVER_PORT:-3001} "; then
    echo "   ⚠️  Port ${MCP_SERVER_PORT:-3001} is in use"
    lsof -i :${MCP_SERVER_PORT:-3001} 2>/dev/null || echo "   Cannot determine process using port"
else
    echo "   ✅ Port ${MCP_SERVER_PORT:-3001} is available"
fi

# 5. Database Connectivity
echo "5. Database Connectivity:"
python3 -c "
from src.second_brain_database.database import db_manager
try:
    info = db_manager.client.server_info()
    print(f'   ✅ MongoDB connected: {info[\"version\"]}')
except Exception as e:
    print(f'   ❌ MongoDB connection failed: {e}')
"

# 6. Redis Connectivity
echo "6. Redis Connectivity:"
python3 -c "
from src.second_brain_database.managers.redis_manager import redis_manager
try:
    redis_manager.client.ping()
    print('   ✅ Redis connected successfully')
except Exception as e:
    print(f'   ❌ Redis connection failed: {e}')
"

# 7. Security Configuration Validation
echo "7. Security Configuration:"
python3 -c "
import os
security_checks = [
    ('MCP_SECURITY_ENABLED', 'true'),
    ('MCP_REQUIRE_AUTH', 'true'),
    ('MCP_DEBUG_MODE', 'false'),
    ('MCP_ADMIN_TOOLS_ENABLED', 'false')
]

for setting, expected in security_checks:
    actual = os.getenv(setting, 'not_set')
    if actual == expected:
        print(f'   ✅ {setting}: {actual}')
    else:
        print(f'   ⚠️  {setting}: {actual} (expected: {expected})')
"

echo "=== DIAGNOSTIC COMPLETE ==="
```

#### Performance Configuration Analysis
```bash
#!/bin/bash
# analyze-mcp-performance-config.sh

echo "=== MCP PERFORMANCE CONFIGURATION ANALYSIS ==="

python3 -c "
import os
import psutil

# Current system resources
memory = psutil.virtual_memory()
cpu_count = psutil.cpu_count()

print(f'System Resources:')
print(f'  Total Memory: {memory.total // (1024**3)} GB')
print(f'  Available Memory: {memory.available // (1024**3)} GB')
print(f'  CPU Cores: {cpu_count}')

# MCP configuration analysis
mcp_concurrent = int(os.getenv('MCP_MAX_CONCURRENT_TOOLS', '50'))
mcp_memory_limit = int(os.getenv('MCP_MEMORY_LIMIT_MB', '512'))
db_pool_size = int(os.getenv('MCP_DB_POOL_SIZE', '20'))

print(f'\\nMCP Configuration:')
print(f'  Max Concurrent Tools: {mcp_concurrent}')
print(f'  Memory Limit per Worker: {mcp_memory_limit} MB')
print(f'  Database Pool Size: {db_pool_size}')

# Performance recommendations
print(f'\\nRecommendations:')

# Memory recommendations
total_memory_needed = mcp_concurrent * mcp_memory_limit
if total_memory_needed > memory.available // (1024**2):
    print(f'  ⚠️  Memory: Reduce concurrent tools or increase system memory')
    print(f'     Current config needs ~{total_memory_needed} MB, available: {memory.available // (1024**2)} MB')
else:
    print(f'  ✅ Memory: Configuration looks good')

# CPU recommendations
if mcp_concurrent > cpu_count * 2:
    print(f'  ⚠️  CPU: Consider reducing concurrent tools (current: {mcp_concurrent}, CPUs: {cpu_count})')
else:
    print(f'  ✅ CPU: Configuration looks good')

# Database pool recommendations
if db_pool_size < mcp_concurrent // 5:
    print(f'  ⚠️  Database: Consider increasing pool size for high concurrency')
else:
    print(f'  ✅ Database: Pool size looks adequate')
"
```

### Configuration Validation Scripts

#### Pre-Deployment Validation
```bash
#!/bin/bash
# pre-deployment-validation.sh

ENVIRONMENT=${1:-production}
EXIT_CODE=0

echo "=== PRE-DEPLOYMENT VALIDATION FOR $ENVIRONMENT ==="

# Load environment-specific configuration
if [ -f ".sbd.$ENVIRONMENT" ]; then
    source ".sbd.$ENVIRONMENT"
elif [ -f ".sbd" ]; then
    source ".sbd"
else
    echo "❌ No configuration file found"
    exit 1
fi

# Critical security validations for production
if [ "$ENVIRONMENT" = "production" ]; then
    echo "Production Security Validations:"
    
    # Must be disabled in production
    MUST_BE_FALSE=("MCP_DEBUG_MODE" "MCP_ADMIN_TOOLS_ENABLED" "MCP_SYSTEM_TOOLS_ENABLED")
    for setting in "${MUST_BE_FALSE[@]}"; do
        if [ "${!setting}" = "true" ]; then
            echo "❌ $setting must be false in production"
            EXIT_CODE=1
        else
            echo "✅ $setting: ${!setting}"
        fi
    done
    
    # Must be enabled in production
    MUST_BE_TRUE=("MCP_SECURITY_ENABLED" "MCP_REQUIRE_AUTH" "MCP_AUDIT_ENABLED" "MCP_RATE_LIMIT_ENABLED")
    for setting in "${MUST_BE_TRUE[@]}"; do
        if [ "${!setting}" != "true" ]; then
            echo "❌ $setting must be true in production"
            EXIT_CODE=1
        else
            echo "✅ $setting: ${!setting}"
        fi
    done
fi

# Validate required settings
echo "Required Settings Validation:"
REQUIRED=("SECRET_KEY" "MONGODB_URL" "REDIS_URL")
for setting in "${REQUIRED[@]}"; do
    if [ -z "${!setting}" ]; then
        echo "❌ $setting is required but not set"
        EXIT_CODE=1
    else
        echo "✅ $setting is configured"
    fi
done

# Validate numeric ranges
echo "Numeric Validation:"
if [ "$MCP_SERVER_PORT" -lt 1024 ] || [ "$MCP_SERVER_PORT" -gt 65535 ]; then
    echo "❌ MCP_SERVER_PORT must be between 1024 and 65535"
    EXIT_CODE=1
else
    echo "✅ MCP_SERVER_PORT: $MCP_SERVER_PORT"
fi

# Test configuration loading
echo "Configuration Loading Test:"
python3 -c "
from src.second_brain_database.config import settings
print('✅ Configuration loads successfully')
" || {
    echo "❌ Configuration loading failed"
    EXIT_CODE=1
}

if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ All validations passed - ready for deployment"
else
    echo "❌ Validation failed - fix issues before deployment"
fi

exit $EXIT_CODE
```

This comprehensive configuration guide provides complete coverage of all MCP configuration options, environment-specific setups, security best practices, troubleshooting procedures, and integration details. The documentation includes practical examples, validation scripts, and operational procedures to ensure successful deployment and maintenance of the FastMCP Gateway Integration.
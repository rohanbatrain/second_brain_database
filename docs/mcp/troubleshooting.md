# MCP Troubleshooting Guide

## Overview

This guide provides comprehensive troubleshooting information for the FastMCP Gateway Integration, covering common issues, diagnostic procedures, and resolution strategies.

## Quick Diagnostic Checklist

### System Health Check

```bash
# 1. Check application health
curl -f http://localhost:8000/health

# 2. Check MCP server health
curl -f http://localhost:8000/health/mcp/server

# 3. Check MCP tools availability
curl -f http://localhost:8000/health/mcp/tools

# 4. Check database connectivity
curl -f http://localhost:8000/health/database

# 5. Check Redis connectivity
curl -f http://localhost:8000/health/redis
```

### Configuration Validation

```bash
# Validate MCP configuration
python -c "
from src.second_brain_database.config import settings
print('MCP Enabled:', settings.MCP_ENABLED)
print('MCP Port:', settings.MCP_SERVER_PORT)
print('Security Enabled:', settings.MCP_SECURITY_ENABLED)
"

# Check environment variables
env | grep MCP_ | sort
```

### Log Analysis

```bash
# Check recent MCP logs
tail -n 100 /app/logs/mcp.log | grep ERROR

# Check FastAPI logs
docker logs second-brain-mcp | grep MCP

# Check system logs
journalctl -u second-brain-mcp --since "1 hour ago"
```

## Common Issues and Solutions

### 1. MCP Server Won't Start

#### Symptoms
- Application starts but MCP server is not accessible
- Error messages about MCP initialization
- Health check fails for MCP endpoints

#### Diagnostic Steps

```bash
# Check if MCP is enabled
echo $MCP_ENABLED

# Verify port availability
netstat -tlnp | grep 3001

# Check for port conflicts
lsof -i :3001

# Review startup logs
docker logs second-brain-mcp | grep -A 10 -B 10 "MCP"
```

#### Common Causes and Solutions

**Cause: MCP disabled in configuration**
```bash
# Solution: Enable MCP in configuration
export MCP_ENABLED=true
# or add to .sbd/.env file
echo "MCP_ENABLED=true" >> .sbd
```

**Cause: Port already in use**
```bash
# Solution: Change MCP port or kill conflicting process
export MCP_SERVER_PORT=3002
# or kill the process using the port
sudo kill $(lsof -t -i:3001)
```

**Cause: Missing dependencies**
```bash
# Solution: Install FastMCP
uv add fastmcp

# Verify installation
python -c "import fastmcp; print('FastMCP installed successfully')"
```

**Cause: Database connection issues**
```bash
# Solution: Verify MongoDB connectivity
python -c "
from src.second_brain_database.database import db_manager
try:
    info = db_manager.client.server_info()
    print('MongoDB connected:', info['version'])
except Exception as e:
    print('MongoDB connection failed:', e)
"
```

### 2. Authentication Failures

#### Symptoms
- "Authentication required" errors for all MCP tools
- Valid tokens being rejected
- Inconsistent authentication behavior

#### Diagnostic Steps

```bash
# Check JWT configuration
python -c "
from src.second_brain_database.config import settings
print('Secret key length:', len(settings.SECRET_KEY))
print('JWT algorithm:', settings.JWT_ALGORITHM)
"

# Test token validation
python -c "
from src.second_brain_database.routes.auth.dependencies import get_current_user_dep
# Test with actual token
"

# Check user permissions
python -c "
from src.second_brain_database.managers.security_manager import security_manager
# Check user role and permissions
"
```

#### Common Causes and Solutions

**Cause: Invalid or expired JWT secret**
```bash
# Solution: Verify and update JWT secret
# Check if SECRET_KEY is properly set
echo ${SECRET_KEY} | wc -c  # Should be at least 32 characters

# Generate new secret if needed
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Cause: Token expiration**
```bash
# Solution: Check token expiration settings
export JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60  # Increase if needed

# Verify token is not expired
python -c "
import jwt
from datetime import datetime
token = 'your_token_here'
try:
    payload = jwt.decode(token, verify=False)
    exp = datetime.fromtimestamp(payload['exp'])
    print('Token expires:', exp)
    print('Current time:', datetime.now())
except Exception as e:
    print('Token decode error:', e)
"
```

**Cause: User permissions issues**
```bash
# Solution: Check user roles and permissions
python -c "
from src.second_brain_database.database import db_manager
user_id = 'your_user_id'
user = db_manager.get_collection('users').find_one({'_id': user_id})
print('User role:', user.get('role'))
print('User permissions:', user.get('permissions', []))
"
```

### 3. Rate Limiting Issues

#### Symptoms
- "Rate limit exceeded" errors
- Legitimate requests being blocked
- Inconsistent rate limiting behavior

#### Diagnostic Steps

```bash
# Check rate limit configuration
python -c "
from src.second_brain_database.config import settings
print('Rate limit enabled:', settings.MCP_RATE_LIMIT_ENABLED)
print('Requests per period:', settings.MCP_RATE_LIMIT_REQUESTS)
print('Period (seconds):', settings.MCP_RATE_LIMIT_PERIOD)
"

# Check Redis connectivity (rate limiting storage)
redis-cli ping

# Check current rate limit status
redis-cli keys "rate_limit:*" | head -10
```

#### Common Causes and Solutions

**Cause: Rate limits too restrictive**
```bash
# Solution: Adjust rate limit settings
export MCP_RATE_LIMIT_REQUESTS=200  # Increase limit
export MCP_RATE_LIMIT_PERIOD=60     # Keep period

# Or disable for testing
export MCP_RATE_LIMIT_ENABLED=false
```

**Cause: Redis connection issues**
```bash
# Solution: Verify Redis connectivity
redis-cli info server

# Check Redis configuration
python -c "
from src.second_brain_database.managers.redis_manager import redis_manager
try:
    redis_manager.client.ping()
    print('Redis connected successfully')
except Exception as e:
    print('Redis connection failed:', e)
"
```

**Cause: Shared IP addresses**
```bash
# Solution: Use user-based rate limiting instead of IP-based
# Modify rate limiting key to include user ID
# This requires code changes in security_manager.py
```

### 4. Tool Execution Failures

#### Symptoms
- Specific MCP tools failing with errors
- Timeout errors during tool execution
- Inconsistent tool behavior

#### Diagnostic Steps

```bash
# List available tools
curl http://localhost:8000/health/mcp/tools | jq '.tools[].name'

# Test specific tool execution
python -c "
from src.second_brain_database.integrations.mcp.tools.family_tools import get_family_info
# Test tool directly
"

# Check tool permissions
python -c "
from src.second_brain_database.integrations.mcp.security import get_tool_permissions
print('Tool permissions:', get_tool_permissions('get_family_info'))
"
```

#### Common Causes and Solutions

**Cause: Missing tool permissions**
```bash
# Solution: Grant required permissions to user
python -c "
from src.second_brain_database.database import db_manager
# Update user permissions in database
db_manager.get_collection('users').update_one(
    {'_id': 'user_id'},
    {'$addToSet': {'permissions': {'$each': ['family:read', 'family:write']}}}
)
"
```

**Cause: Database connection issues in tools**
```bash
# Solution: Verify database managers are properly initialized
python -c "
from src.second_brain_database.managers.family_manager import FamilyManager
from src.second_brain_database.database import db_manager
fm = FamilyManager(db_manager=db_manager)
print('FamilyManager initialized successfully')
"
```

**Cause: Tool timeout issues**
```bash
# Solution: Increase timeout settings
export MCP_REQUEST_TIMEOUT=60  # Increase from default 30 seconds

# Check for long-running database queries
# Enable MongoDB profiling to identify slow queries
```

### 5. Performance Issues

#### Symptoms
- Slow MCP tool responses
- High CPU or memory usage
- Connection timeouts

#### Diagnostic Steps

```bash
# Check system resources
top -p $(pgrep -f "uvicorn")
free -h
df -h

# Check MCP performance metrics
curl http://localhost:8000/health/mcp/metrics

# Monitor database performance
python -c "
from src.second_brain_database.database import db_manager
stats = db_manager.client.admin.command('serverStatus')
print('Database connections:', stats['connections'])
print('Operations per second:', stats['opcounters'])
"

# Check Redis performance
redis-cli info stats
```

#### Common Causes and Solutions

**Cause: Too many concurrent connections**
```bash
# Solution: Limit concurrent tool executions
export MCP_MAX_CONCURRENT_TOOLS=25  # Reduce from default 50

# Monitor connection usage
netstat -an | grep :3001 | wc -l
```

**Cause: Database query performance**
```bash
# Solution: Add database indexes for MCP queries
python -c "
from src.second_brain_database.database import db_manager

# Add indexes for common MCP queries
db_manager.get_collection('families').create_index([('owner_id', 1), ('created_at', -1)])
db_manager.get_collection('users').create_index([('email', 1)])
db_manager.get_collection('audit_log').create_index([('timestamp', -1), ('user_id', 1)])
"
```

**Cause: Memory leaks**
```bash
# Solution: Monitor memory usage and restart if needed
# Add memory monitoring to health checks
python -c "
import psutil
process = psutil.Process()
print('Memory usage:', process.memory_info().rss / 1024 / 1024, 'MB')
print('CPU usage:', process.cpu_percent())
"
```

### 6. Security and Permission Issues

#### Symptoms
- "Permission denied" errors for authorized users
- Security violations being logged incorrectly
- Inconsistent permission enforcement

#### Diagnostic Steps

```bash
# Check user roles and permissions
python -c "
from src.second_brain_database.database import db_manager
user = db_manager.get_collection('users').find_one({'email': 'user@example.com'})
print('User role:', user.get('role'))
print('Permissions:', user.get('permissions', []))
"

# Check security configuration
python -c "
from src.second_brain_database.config import settings
print('Security enabled:', settings.MCP_SECURITY_ENABLED)
print('Auth required:', settings.MCP_REQUIRE_AUTH)
print('Audit enabled:', settings.MCP_AUDIT_ENABLED)
"

# Review security logs
grep "SECURITY" /app/logs/mcp.log | tail -20
```

#### Common Causes and Solutions

**Cause: Incorrect role assignments**
```bash
# Solution: Update user roles
python -c "
from src.second_brain_database.database import db_manager
db_manager.get_collection('users').update_one(
    {'email': 'user@example.com'},
    {'$set': {'role': 'admin'}}
)
"
```

**Cause: Permission inheritance issues**
```bash
# Solution: Verify permission inheritance logic
python -c "
from src.second_brain_database.integrations.mcp.security import get_user_permissions
permissions = get_user_permissions('user_id')
print('Effective permissions:', permissions)
"
```

## Advanced Troubleshooting

### Debug Mode

Enable debug mode for detailed logging:

```bash
# Enable debug mode
export MCP_DEBUG_MODE=true

# Restart application
docker-compose restart

# Monitor debug logs
tail -f /app/logs/mcp.log | grep DEBUG
```

### Database Debugging

```python
# Enable MongoDB profiling for slow queries
from src.second_brain_database.database import db_manager

# Profile slow operations (>100ms)
db_manager.client.admin.command('profile', 2, slowms=100)

# View profiling data
profiling_data = list(db_manager.client.admin.system.profile.find().limit(10))
for op in profiling_data:
    print(f"Operation: {op['command']}")
    print(f"Duration: {op['millis']}ms")
    print("---")
```

### Network Debugging

```bash
# Check network connectivity
telnet localhost 3001

# Monitor network traffic
tcpdump -i any port 3001

# Check DNS resolution
nslookup localhost

# Test with curl
curl -v http://localhost:3001/health
```

### Memory and Performance Profiling

```python
# Memory profiling
import tracemalloc
import psutil

tracemalloc.start()

# Run MCP operations
# ...

current, peak = tracemalloc.get_traced_memory()
print(f"Current memory usage: {current / 1024 / 1024:.1f} MB")
print(f"Peak memory usage: {peak / 1024 / 1024:.1f} MB")

# Process monitoring
process = psutil.Process()
print(f"CPU usage: {process.cpu_percent()}%")
print(f"Memory usage: {process.memory_info().rss / 1024 / 1024:.1f} MB")
```

## Error Code Reference

### MCP-Specific Error Codes

| Code | Description | Common Causes | Solutions |
|------|-------------|---------------|-----------|
| MCP_AUTH_001 | Authentication required | Missing or invalid token | Provide valid JWT or permanent token |
| MCP_AUTH_002 | Token expired | JWT token past expiration | Refresh token or re-authenticate |
| MCP_AUTH_003 | Invalid token format | Malformed token | Check token format and encoding |
| MCP_PERM_001 | Insufficient permissions | User lacks required permissions | Grant necessary permissions to user |
| MCP_PERM_002 | Role not authorized | User role cannot perform action | Update user role or permissions |
| MCP_RATE_001 | Rate limit exceeded | Too many requests | Wait for rate limit reset or increase limits |
| MCP_RATE_002 | Rate limit configuration error | Invalid rate limit settings | Check rate limit configuration |
| MCP_TOOL_001 | Tool not found | Tool name incorrect or not registered | Verify tool name and registration |
| MCP_TOOL_002 | Tool execution failed | Internal tool error | Check tool logs and dependencies |
| MCP_TOOL_003 | Tool timeout | Tool execution took too long | Increase timeout or optimize tool |
| MCP_VAL_001 | Invalid parameters | Parameter validation failed | Check parameter types and values |
| MCP_VAL_002 | Missing required parameter | Required parameter not provided | Provide all required parameters |
| MCP_DB_001 | Database connection failed | MongoDB unavailable | Check database connectivity |
| MCP_DB_002 | Database query failed | Query execution error | Check query syntax and data |
| MCP_REDIS_001 | Redis connection failed | Redis unavailable | Check Redis connectivity |
| MCP_REDIS_002 | Cache operation failed | Redis operation error | Check Redis configuration |

### HTTP Status Codes

| Status | Description | When Used |
|--------|-------------|-----------|
| 200 | OK | Successful tool execution |
| 400 | Bad Request | Invalid parameters or malformed request |
| 401 | Unauthorized | Authentication required or failed |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Tool or resource not found |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Unexpected server error |
| 502 | Bad Gateway | MCP server unavailable |
| 503 | Service Unavailable | System maintenance or overload |
| 504 | Gateway Timeout | Tool execution timeout |

## Monitoring and Alerting Setup

### Health Check Monitoring

```bash
#!/bin/bash
# health-monitor.sh

# Check MCP server health
if ! curl -f http://localhost:8000/health/mcp/server > /dev/null 2>&1; then
    echo "ALERT: MCP server health check failed"
    # Send alert notification
    curl -X POST "https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK" \
         -H 'Content-type: application/json' \
         --data '{"text":"MCP server health check failed"}'
fi

# Check tool availability
tool_count=$(curl -s http://localhost:8000/health/mcp/tools | jq '.tools | length')
if [ "$tool_count" -lt 50 ]; then
    echo "ALERT: Low tool count: $tool_count"
fi
```

### Log Monitoring

```bash
#!/bin/bash
# log-monitor.sh

# Monitor for errors in MCP logs
tail -f /app/logs/mcp.log | while read line; do
    if echo "$line" | grep -q "ERROR\|CRITICAL"; then
        echo "ALERT: Error detected in MCP logs: $line"
        # Send alert
    fi
    
    if echo "$line" | grep -q "rate_limit_exceeded"; then
        echo "WARNING: Rate limit exceeded: $line"
    fi
done
```

### Performance Monitoring

```python
# performance-monitor.py
import asyncio
import time
from src.second_brain_database.integrations.mcp.monitoring import get_mcp_metrics

async def monitor_performance():
    while True:
        metrics = await get_mcp_metrics()
        
        # Check response times
        if metrics.get('avg_response_time', 0) > 5000:  # 5 seconds
            print("ALERT: High response time:", metrics['avg_response_time'])
        
        # Check error rates
        error_rate = metrics.get('error_rate', 0)
        if error_rate > 0.05:  # 5%
            print("ALERT: High error rate:", error_rate)
        
        # Check concurrent tools
        concurrent = metrics.get('concurrent_tools', 0)
        if concurrent > 40:  # 80% of max
            print("WARNING: High concurrent tool usage:", concurrent)
        
        await asyncio.sleep(60)  # Check every minute

if __name__ == "__main__":
    asyncio.run(monitor_performance())
```

## Recovery Procedures

### Service Recovery

```bash
#!/bin/bash
# mcp-recovery.sh

echo "Starting MCP service recovery..."

# 1. Stop services gracefully
docker-compose stop

# 2. Check for resource issues
free -h
df -h

# 3. Clean up if needed
docker system prune -f

# 4. Restart services
docker-compose up -d

# 5. Wait for startup
sleep 30

# 6. Verify health
if curl -f http://localhost:8000/health/mcp/server; then
    echo "MCP service recovery successful"
else
    echo "MCP service recovery failed"
    exit 1
fi
```

### Database Recovery

```bash
#!/bin/bash
# db-recovery.sh

echo "Starting database recovery..."

# 1. Check MongoDB status
if ! mongo --eval "db.adminCommand('ismaster')" > /dev/null 2>&1; then
    echo "MongoDB is down, attempting restart..."
    docker-compose restart mongodb
    sleep 30
fi

# 2. Check for corruption
mongo --eval "db.runCommand({validate: 'families'})"

# 3. Repair if needed
if [ $? -ne 0 ]; then
    echo "Database corruption detected, running repair..."
    mongo --eval "db.repairDatabase()"
fi

# 4. Rebuild indexes
mongo --eval "
    db.families.reIndex();
    db.users.reIndex();
    db.audit_log.reIndex();
"

echo "Database recovery completed"
```

## Getting Help

### Internal Resources

1. **Check application logs** for detailed error information
2. **Review configuration** for common misconfigurations
3. **Test individual components** to isolate issues
4. **Monitor system resources** for performance bottlenecks

### External Resources

1. **FastMCP Documentation**: https://github.com/jlowin/fastmcp
2. **FastAPI Documentation**: https://fastapi.tiangolo.com/
3. **MongoDB Documentation**: https://docs.mongodb.com/
4. **Redis Documentation**: https://redis.io/documentation

### Support Escalation

If issues persist after following this guide:

1. **Collect diagnostic information**:
   ```bash
   # System information
   uname -a
   docker version
   python --version
   
   # Configuration
   env | grep MCP_ > mcp-config.txt
   
   # Logs
   docker logs second-brain-mcp > mcp-logs.txt
   tail -1000 /app/logs/mcp.log > mcp-app-logs.txt
   
   # Health status
   curl http://localhost:8000/health > health-status.json
   ```

2. **Document the issue**:
   - Exact error messages
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment details
   - Recent changes

3. **Create support ticket** with all collected information

This troubleshooting guide should help resolve most common issues with the FastMCP Gateway Integration. For complex issues, systematic diagnosis and step-by-step resolution following this guide will identify and resolve problems efficiently.
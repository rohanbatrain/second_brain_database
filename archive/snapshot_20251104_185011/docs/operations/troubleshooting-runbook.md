# Family Management System Troubleshooting Runbook

## Overview

This runbook provides step-by-step troubleshooting procedures for common issues in the Family Management System. It includes diagnostic commands, resolution steps, and escalation procedures.

## Quick Reference

### Emergency Contacts
- **On-Call Engineer**: +1-XXX-XXX-XXXX
- **Database Admin**: +1-XXX-XXX-XXXX
- **Security Team**: security@yourdomain.com
- **DevOps Team**: devops@yourdomain.com

### Critical Service URLs
- **API Health**: https://api.yourdomain.com/health
- **Monitoring Dashboard**: https://monitoring.yourdomain.com
- **Log Aggregation**: https://logs.yourdomain.com
- **Status Page**: https://status.yourdomain.com

### Service Dependencies
- **MongoDB**: Primary database
- **Redis**: Caching and rate limiting
- **Nginx**: Reverse proxy and load balancer
- **External APIs**: Email service, authentication providers

## Common Issues and Solutions

### 1. Application Not Responding

#### Symptoms
- HTTP 502/503 errors
- Timeouts on API requests
- Health check failures

#### Diagnostic Steps

```bash
# Check if application is running
sudo systemctl status sbd-api

# Check application logs
sudo journalctl -u sbd-api -f --lines=50

# Check process status
ps aux | grep uvicorn

# Check port availability
netstat -tulpn | grep :8000

# Test local connectivity
curl -v http://localhost:8000/health
```

#### Resolution Steps

1. **Restart Application Service**
   ```bash
   sudo systemctl restart sbd-api
   sudo systemctl status sbd-api
   ```

2. **Check Configuration**
   ```bash
   # Validate configuration file
   uv run python -c "
   from second_brain_database.config import get_settings
   settings = get_settings()
   print('Configuration loaded successfully')
   "
   ```

3. **Check Resource Usage**
   ```bash
   # Check memory usage
   free -h
   
   # Check CPU usage
   top -p $(pgrep -f uvicorn)
   
   # Check disk space
   df -h
   ```

4. **Check Dependencies**
   ```bash
   # Test MongoDB connection
   mongosh --eval "db.adminCommand('ping')"
   
   # Test Redis connection
   redis-cli ping
   ```

#### Escalation
If application doesn't start after restart, escalate to DevOps team with:
- Application logs from last 30 minutes
- System resource usage
- Configuration file (sanitized)

### 2. Database Connection Issues

#### Symptoms
- "Database connection failed" errors
- Slow response times
- MongoDB connection timeouts

#### Diagnostic Steps

```bash
# Check MongoDB service status
sudo systemctl status mongod

# Check MongoDB logs
sudo tail -f /var/log/mongodb/mongod.log

# Test connection
mongosh --eval "
db.adminCommand('ping')
db.runCommand({connectionStatus: 1})
"

# Check replica set status
mongosh --eval "rs.status()"

# Check database connections
mongosh --eval "db.serverStatus().connections"
```

#### Resolution Steps

1. **Restart MongoDB Service**
   ```bash
   sudo systemctl restart mongod
   sudo systemctl status mongod
   ```

2. **Check Replica Set Health**
   ```bash
   mongosh --eval "
   rs.status()
   rs.isMaster()
   "
   ```

3. **Check Disk Space**
   ```bash
   df -h /var/lib/mongodb
   ```

4. **Check Memory Usage**
   ```bash
   mongosh --eval "db.serverStatus().mem"
   ```

5. **Repair Database (if corrupted)**
   ```bash
   # Stop application first
   sudo systemctl stop sbd-api
   
   # Repair database
   sudo -u mongodb mongod --repair --dbpath /var/lib/mongodb
   
   # Restart services
   sudo systemctl start mongod
   sudo systemctl start sbd-api
   ```

#### Escalation
If MongoDB issues persist, escalate to Database Admin with:
- MongoDB logs from last hour
- Replica set status output
- Disk and memory usage statistics

### 3. Redis Connection Issues

#### Symptoms
- Cache misses
- Rate limiting not working
- Session management failures

#### Diagnostic Steps

```bash
# Check Redis service status
sudo systemctl status redis

# Check Redis logs
sudo tail -f /var/log/redis/redis-server.log

# Test connection
redis-cli ping

# Check Redis info
redis-cli info

# Check memory usage
redis-cli info memory

# Check connected clients
redis-cli info clients
```

#### Resolution Steps

1. **Restart Redis Service**
   ```bash
   sudo systemctl restart redis
   sudo systemctl status redis
   ```

2. **Check Configuration**
   ```bash
   redis-cli config get "*"
   ```

3. **Check Memory Usage**
   ```bash
   redis-cli info memory | grep used_memory_human
   ```

4. **Clear Cache (if needed)**
   ```bash
   # WARNING: This will clear all cached data
   redis-cli flushall
   ```

#### Escalation
If Redis issues persist, escalate to DevOps team with:
- Redis logs and configuration
- Memory usage statistics
- Connected clients information

### 4. High Error Rates

#### Symptoms
- Increased 4xx/5xx HTTP responses
- Error alerts from monitoring
- User complaints about failures

#### Diagnostic Steps

```bash
# Check application logs for errors
sudo journalctl -u sbd-api --since "1 hour ago" | grep ERROR

# Check Nginx error logs
sudo tail -f /var/log/nginx/sbd-api.error.log

# Check error metrics
curl -s http://localhost:9090/metrics | grep error

# Check recent deployments
git log --oneline --since="24 hours ago"
```

#### Resolution Steps

1. **Identify Error Patterns**
   ```bash
   # Analyze error logs
   sudo journalctl -u sbd-api --since "1 hour ago" | grep ERROR | sort | uniq -c | sort -nr
   ```

2. **Check Recent Changes**
   ```bash
   # Check if errors started after deployment
   git log --oneline --since="$(date -d '1 hour ago')"
   ```

3. **Rollback if Necessary**
   ```bash
   # If errors started after recent deployment
   git checkout <previous_stable_commit>
   sudo systemctl restart sbd-api
   ```

4. **Check External Dependencies**
   ```bash
   # Test external API connectivity
   curl -v https://external-api.example.com/health
   ```

#### Escalation
If error rates remain high, escalate to Development team with:
- Error log samples
- Error rate graphs from monitoring
- Recent deployment information

### 5. Performance Issues

#### Symptoms
- Slow response times
- High CPU/memory usage
- Timeout errors

#### Diagnostic Steps

```bash
# Check system resources
htop
iotop
free -h

# Check application performance
curl -w "@curl-format.txt" -o /dev/null -s http://localhost:8000/health

# Check database performance
mongosh --eval "
db.currentOp()
db.serverStatus().opcounters
"

# Check slow queries
mongosh --eval "db.setProfilingLevel(2, {slowms: 100})"
```

#### Resolution Steps

1. **Identify Resource Bottlenecks**
   ```bash
   # Check CPU usage by process
   top -p $(pgrep -f uvicorn)
   
   # Check memory usage
   ps aux --sort=-%mem | head -10
   
   # Check I/O usage
   iotop -o
   ```

2. **Optimize Database Queries**
   ```bash
   # Check slow operations
   mongosh --eval "db.currentOp({'secs_running': {\$gte: 5}})"
   
   # Kill slow operations if necessary
   mongosh --eval "db.killOp(<opid>)"
   ```

3. **Scale Resources**
   ```bash
   # Increase worker processes (temporary)
   sudo systemctl edit sbd-api
   # Add: ExecStart=/path/to/uvicorn --workers 8
   sudo systemctl daemon-reload
   sudo systemctl restart sbd-api
   ```

4. **Clear Caches**
   ```bash
   # Clear Redis cache
   redis-cli flushall
   
   # Clear application cache
   curl -X POST http://localhost:8000/admin/clear-cache
   ```

#### Escalation
If performance issues persist, escalate to DevOps team with:
- System resource usage graphs
- Database performance metrics
- Application response time data

### 6. Authentication Issues

#### Symptoms
- Users cannot log in
- JWT token validation failures
- 401 Unauthorized errors

#### Diagnostic Steps

```bash
# Check authentication logs
sudo journalctl -u sbd-api | grep -i auth

# Test JWT token validation
curl -H "Authorization: Bearer <test_token>" http://localhost:8000/family/my-families

# Check Redis for session data
redis-cli keys "*session*"

# Check 2FA service
curl -v https://2fa-service.example.com/health
```

#### Resolution Steps

1. **Verify JWT Configuration**
   ```bash
   # Check JWT secret key is set
   uv run python -c "
   from second_brain_database.config import get_settings
   settings = get_settings()
   print('JWT secret configured:', bool(settings.SECRET_KEY))
   "
   ```

2. **Check External Auth Services**
   ```bash
   # Test external authentication provider
   curl -v https://auth-provider.example.com/health
   ```

3. **Clear Authentication Cache**
   ```bash
   # Clear auth-related Redis keys
   redis-cli --scan --pattern "*auth*" | xargs redis-cli del
   ```

4. **Restart Authentication Services**
   ```bash
   sudo systemctl restart sbd-api
   ```

#### Escalation
If authentication issues persist, escalate to Security team with:
- Authentication error logs
- External service status
- User impact assessment

### 7. Rate Limiting Issues

#### Symptoms
- Excessive 429 errors
- Rate limiting not working
- Users blocked incorrectly

#### Diagnostic Steps

```bash
# Check rate limiting logs
sudo journalctl -u sbd-api | grep -i "rate limit"

# Check Redis rate limit keys
redis-cli keys "*rate_limit*"

# Check rate limit configuration
uv run python -c "
from second_brain_database.managers.security_manager import security_manager
print('Rate limiting enabled:', security_manager.rate_limiting_enabled)
"
```

#### Resolution Steps

1. **Check Rate Limit Configuration**
   ```bash
   # Verify rate limit settings
   redis-cli hgetall rate_limit_config
   ```

2. **Clear Rate Limit Data**
   ```bash
   # Clear specific user's rate limits
   redis-cli del "rate_limit:user:<user_id>:*"
   
   # Clear all rate limits (emergency only)
   redis-cli --scan --pattern "*rate_limit*" | xargs redis-cli del
   ```

3. **Adjust Rate Limits**
   ```bash
   # Temporarily increase limits
   curl -X POST http://localhost:8000/admin/rate-limits \
     -H "Content-Type: application/json" \
     -d '{"endpoint": "/family/create", "limit": 10, "window": 3600}'
   ```

#### Escalation
If rate limiting issues persist, escalate to Development team with:
- Rate limiting configuration
- User impact data
- Redis key analysis

### 8. Family Management Specific Issues

#### Symptoms
- Family creation failures
- Invitation emails not sent
- SBD account issues

#### Diagnostic Steps

```bash
# Check family-specific logs
sudo journalctl -u sbd-api | grep -i family

# Check email service status
curl -v https://email-service.example.com/health

# Check SBD token service
curl -v https://sbd-tokens.example.com/health

# Check family data integrity
mongosh --eval "
db.families.countDocuments()
db.family_relationships.countDocuments()
db.family_invitations.countDocuments({status: 'pending'})
"
```

#### Resolution Steps

1. **Check Email Service**
   ```bash
   # Test email sending
   uv run python -c "
   from second_brain_database.managers.email import send_test_email
   import asyncio
   asyncio.run(send_test_email('test@example.com'))
   "
   ```

2. **Check SBD Integration**
   ```bash
   # Test SBD token validation
   curl -X POST http://localhost:8000/family/validate-spending \
     -H "Content-Type: application/json" \
     -d '{"account_username": "test", "user_id": "test", "amount": 10}'
   ```

3. **Clean Up Expired Data**
   ```bash
   # Clean expired invitations
   curl -X POST http://localhost:8000/admin/cleanup-expired-invitations
   ```

#### Escalation
If family management issues persist, escalate to Development team with:
- Family operation logs
- External service status
- Data integrity check results

## Monitoring and Alerting Procedures

### Alert Response Procedures

#### Critical Alerts (P1)
- **Response Time**: 15 minutes
- **Actions**:
  1. Acknowledge alert in monitoring system
  2. Check service status and logs
  3. Implement immediate fix or workaround
  4. Update status page
  5. Notify stakeholders

#### High Priority Alerts (P2)
- **Response Time**: 1 hour
- **Actions**:
  1. Acknowledge alert
  2. Investigate root cause
  3. Implement fix within 4 hours
  4. Document resolution

#### Medium Priority Alerts (P3)
- **Response Time**: 4 hours
- **Actions**:
  1. Acknowledge alert
  2. Schedule investigation
  3. Implement fix within 24 hours

### Escalation Matrix

| Issue Type | Primary Contact | Secondary Contact | Executive Contact |
|------------|----------------|-------------------|-------------------|
| Service Outage | On-Call Engineer | DevOps Lead | CTO |
| Security Incident | Security Team | CISO | CEO |
| Data Loss | Database Admin | DevOps Lead | CTO |
| Performance Issues | DevOps Team | Engineering Lead | CTO |

## Recovery Procedures

### Service Recovery Checklist

1. **Immediate Response**
   - [ ] Acknowledge incident
   - [ ] Assess impact and severity
   - [ ] Implement immediate mitigation
   - [ ] Update status page

2. **Investigation**
   - [ ] Gather logs and metrics
   - [ ] Identify root cause
   - [ ] Document timeline
   - [ ] Assess data integrity

3. **Resolution**
   - [ ] Implement permanent fix
   - [ ] Test fix in staging
   - [ ] Deploy to production
   - [ ] Verify resolution

4. **Post-Incident**
   - [ ] Update documentation
   - [ ] Conduct post-mortem
   - [ ] Implement preventive measures
   - [ ] Update runbooks

### Data Recovery Procedures

#### Database Recovery

```bash
# Stop application
sudo systemctl stop sbd-api

# Restore from backup
mongorestore --uri="mongodb://localhost:27017/second_brain_database" \
  --drop /opt/backups/mongodb/latest/

# Verify data integrity
mongosh --eval "
db.families.countDocuments()
db.users.countDocuments()
"

# Restart application
sudo systemctl start sbd-api
```

#### Redis Recovery

```bash
# Stop Redis
sudo systemctl stop redis

# Restore RDB file
sudo cp /opt/backups/redis/latest/dump.rdb /var/lib/redis/

# Start Redis
sudo systemctl start redis

# Verify data
redis-cli info keyspace
```

## Performance Optimization

### Quick Performance Fixes

1. **Increase Worker Processes**
   ```bash
   # Edit service file
   sudo systemctl edit sbd-api
   # Add: ExecStart with --workers 8
   sudo systemctl daemon-reload
   sudo systemctl restart sbd-api
   ```

2. **Optimize Database Connections**
   ```bash
   # Increase connection pool size
   export MONGODB_MAX_POOL_SIZE=50
   sudo systemctl restart sbd-api
   ```

3. **Clear Caches**
   ```bash
   # Clear Redis cache
   redis-cli flushall
   
   # Clear application cache
   curl -X POST http://localhost:8000/admin/clear-cache
   ```

4. **Enable Compression**
   ```bash
   # Enable gzip in Nginx
   sudo nginx -s reload
   ```

### Long-term Optimizations

1. **Database Indexing**
   ```javascript
   // Add missing indexes
   db.families.createIndex({"admin_user_ids": 1})
   db.family_relationships.createIndex({"family_id": 1, "status": 1})
   ```

2. **Connection Pooling**
   ```python
   # Optimize connection pool settings
   MONGODB_MAX_POOL_SIZE = 100
   MONGODB_MIN_POOL_SIZE = 10
   ```

3. **Caching Strategy**
   ```python
   # Implement aggressive caching
   CACHE_TTL = 300  # 5 minutes
   ENABLE_QUERY_CACHE = True
   ```

## Security Incident Response

### Security Incident Checklist

1. **Immediate Response**
   - [ ] Isolate affected systems
   - [ ] Preserve evidence
   - [ ] Notify security team
   - [ ] Document incident

2. **Assessment**
   - [ ] Determine scope of breach
   - [ ] Identify compromised data
   - [ ] Assess ongoing threats
   - [ ] Notify stakeholders

3. **Containment**
   - [ ] Block malicious traffic
   - [ ] Revoke compromised credentials
   - [ ] Apply security patches
   - [ ] Monitor for persistence

4. **Recovery**
   - [ ] Restore from clean backups
   - [ ] Implement additional controls
   - [ ] Verify system integrity
   - [ ] Resume normal operations

5. **Post-Incident**
   - [ ] Conduct forensic analysis
   - [ ] Update security measures
   - [ ] Notify authorities if required
   - [ ] Document lessons learned

### Emergency Contacts for Security

- **Security Team**: security@yourdomain.com
- **CISO**: +1-XXX-XXX-XXXX
- **Legal Team**: legal@yourdomain.com
- **External Security Firm**: +1-XXX-XXX-XXXX

This troubleshooting runbook provides comprehensive guidance for resolving common issues and handling incidents in the Family Management System. Regular updates and team training ensure effective incident response.
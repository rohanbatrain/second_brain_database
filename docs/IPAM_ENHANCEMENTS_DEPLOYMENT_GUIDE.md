# IPAM Backend Enhancements - Deployment Guide

## Overview

This guide provides step-by-step instructions for deploying the IPAM backend enhancements to production. The deployment is designed to be zero-downtime and backward compatible with existing IPAM functionality.

**Deployment Type**: Rolling deployment (zero downtime)  
**Backward Compatibility**: Yes (100%)  
**Estimated Time**: 30-45 minutes  
**Rollback Time**: 5-10 minutes

---

## Table of Contents

1. [Pre-Deployment Checklist](#1-pre-deployment-checklist)
2. [Environment Preparation](#2-environment-preparation)
3. [Database Migration](#3-database-migration)
4. [Application Deployment](#4-application-deployment)
5. [Verification & Testing](#5-verification--testing)
6. [Monitoring Setup](#6-monitoring-setup)
7. [Post-Deployment Tasks](#7-post-deployment-tasks)
8. [Rollback Procedures](#8-rollback-procedures)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. Pre-Deployment Checklist

### 1.1 Code Verification

Ensure all code is ready for deployment:

```bash
# Verify syntax
python -m py_compile src/second_brain_database/routes/ipam/routes.py
python -m py_compile src/second_brain_database/managers/ipam_manager.py

# Run linting
uv run ruff check src/second_brain_database/routes/ipam/
uv run ruff check src/second_brain_database/managers/

# Run type checking
uv run mypy src/second_brain_database/routes/ipam/
uv run mypy src/second_brain_database/managers/
```

**Checklist:**
- [ ] No syntax errors
- [ ] No linting errors
- [ ] No type checking errors
- [ ] All imports resolve correctly


### 1.2 Test Suite Verification

Run the complete test suite to ensure all functionality works:

```bash
# Run all IPAM enhancement tests
uv run pytest tests/test_ipam_enhancements.py -v

# Run with coverage
uv run pytest tests/test_ipam_enhancements.py \
  --cov=src.second_brain_database.routes.ipam \
  --cov=src.second_brain_database.managers.ipam_manager \
  --cov-report=html \
  --cov-report=term

# Check coverage threshold
uv run pytest tests/test_ipam_enhancements.py --cov --cov-fail-under=80
```

**Checklist:**
- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] Code coverage > 80%
- [ ] No test failures or warnings

### 1.3 Documentation Review

Verify all documentation is complete and accurate:

**Checklist:**
- [ ] API documentation complete (`docs/IPAM_ENHANCEMENTS_API_GUIDE.md`)
- [ ] Migration guide complete (`docs/IPAM_ENHANCEMENTS_MIGRATION_GUIDE.md`)
- [ ] Deployment guide reviewed (this document)
- [ ] OpenAPI/Swagger documentation auto-generated
- [ ] Changelog updated with new features

### 1.4 Backup Strategy

Ensure backup procedures are in place:

```bash
# Create full database backup
mongodump --uri="mongodb://production-host:27017" \
  --db=ipam_production \
  --out=backup_pre_deployment_$(date +%Y%m%d_%H%M%S) \
  --gzip

# Verify backup
ls -lh backup_pre_deployment_*/

# Test backup restoration (on dev environment)
mongorestore --uri="mongodb://dev-host:27017" \
  --db=ipam_dev_restore_test \
  --gzip \
  backup_pre_deployment_*/ipam_production/
```

**Checklist:**
- [ ] Full database backup created
- [ ] Backup verified and tested
- [ ] Backup stored in secure location
- [ ] Restoration procedure tested

---

## 2. Environment Preparation

### 2.1 System Requirements

Verify production environment meets requirements:

**Infrastructure:**
- Python 3.11+
- MongoDB 4.4+ (with replica set for transactions)
- Redis 6.0+ (for caching and rate limiting)
- Minimum 4GB RAM
- Minimum 20GB disk space

**Network:**
- Outbound HTTPS access (for webhook deliveries)
- Redis connection (localhost or remote)
- MongoDB connection (localhost or remote)

### 2.2 Environment Variables

Set required environment variables in production:

```bash
# Core settings
export SECRET_KEY="<production-secret-key>"
export MONGODB_URL="mongodb://production-host:27017"
export MONGODB_DATABASE="ipam_production"
export REDIS_URL="redis://production-host:6379"
export FERNET_KEY="<production-fernet-key>"

# Optional: Performance tuning
export IPAM_CACHE_TTL=300  # Dashboard cache: 5 minutes
export IPAM_FORECAST_CACHE_TTL=86400  # Forecast cache: 24 hours
export IPAM_RATE_LIMIT_PER_HOUR=100  # API rate limit

# Optional: Feature flags
export IPAM_ENABLE_WEBHOOKS=true
export IPAM_ENABLE_NOTIFICATIONS=true
export IPAM_ENABLE_BACKGROUND_TASKS=true
```

**Checklist:**
- [ ] All required environment variables set
- [ ] Secrets properly secured (not in version control)
- [ ] Redis connection tested
- [ ] MongoDB connection tested

### 2.3 Dependencies Installation

Install all required dependencies:

```bash
# Sync dependencies
uv sync --extra dev

# Verify installation
uv run python -c "import fastapi, motor, redis, pydantic; print('Dependencies OK')"

# Check versions
uv run python -c "import fastapi; print(f'FastAPI: {fastapi.__version__}')"
uv run python -c "import motor; print(f'Motor: {motor.version}')"
```

**Checklist:**
- [ ] All dependencies installed
- [ ] No version conflicts
- [ ] Import tests pass

---

## 3. Database Migration

### 3.1 Pre-Migration Verification

Before running the migration, verify the database state:

```bash
# Check current collections
mongosh $MONGODB_URL/$MONGODB_DATABASE --eval "
  print('Current collections:');
  db.getCollectionNames().forEach(c => print('  - ' + c));
"

# Check for existing enhancement collections (should not exist)
mongosh $MONGODB_URL/$MONGODB_DATABASE --eval "
  const enhancementCollections = [
    'ipam_reservations',
    'ipam_shares',
    'ipam_user_preferences',
    'ipam_notifications',
    'ipam_notification_rules',
    'ipam_webhooks',
    'ipam_webhook_deliveries',
    'ipam_bulk_jobs'
  ];
  
  enhancementCollections.forEach(name => {
    const exists = db.getCollectionNames().includes(name);
    print(name + ': ' + (exists ? 'EXISTS (WARNING)' : 'Not found (OK)'));
  });
"
```

**Checklist:**
- [ ] Database connection successful
- [ ] Existing IPAM collections present
- [ ] No enhancement collections exist yet
- [ ] Database has sufficient space

### 3.2 Run Database Migration

Execute the migration script:

```bash
# Dry run first (check only, no changes)
uv run python scripts/run_ipam_enhancements_migration.py --dry-run

# Run actual migration
uv run python scripts/run_ipam_enhancements_migration.py

# Expected output:
# ================================================================================
# Starting IPAM Backend Enhancements Migration
# ================================================================================
# Connecting to database...
# Database connection successful
# 
# Executing migration...
# ✓ Created collection: ipam_reservations
# ✓ Created collection: ipam_shares
# ✓ Created collection: ipam_user_preferences
# ✓ Created collection: ipam_notifications
# ✓ Created collection: ipam_notification_rules
# ✓ Created collection: ipam_webhooks
# ✓ Created collection: ipam_webhook_deliveries
# ✓ Created collection: ipam_bulk_jobs
# 
# ✓ Created 20+ indexes
# 
# ================================================================================
# Migration Results:
# ================================================================================
# Status: completed
# Duration: 2.34 seconds
# Collections created: 8
# Indexes created: 20+
# 
# ✅ IPAM backend enhancements migration completed successfully!
```

**Checklist:**
- [ ] Migration completed successfully
- [ ] All 8 collections created
- [ ] All indexes created
- [ ] No error messages
- [ ] Migration logged

### 3.3 Verify Database Indexes

Run the index verification script:

```bash
# Verify all indexes
uv run python scripts/verify_ipam_indexes.py

# Expected output:
# ================================================================================
# IPAM Backend Enhancements - Index Verification
# ================================================================================
# ✓ Connected to database
# ✓ Database health check passed
# 
# ✓ ipam_reservations: All indexes present (4 indexes)
# ✓ ipam_shares: All indexes present (3 indexes)
# ✓ ipam_user_preferences: All indexes present (1 index)
# ✓ ipam_notifications: All indexes present (2 indexes)
# ✓ ipam_notification_rules: All indexes present (2 indexes)
# ✓ ipam_webhooks: All indexes present (2 indexes)
# ✓ ipam_webhook_deliveries: All indexes present (2 indexes)
# ✓ ipam_bulk_jobs: All indexes present (2 indexes)
# 
# ================================================================================
# Verification Summary
# ================================================================================
# ✓ All indexes verified successfully!
#   Collections checked: 8
#   Total indexes: 20+
# ================================================================================
```

**Checklist:**
- [ ] All collections have required indexes
- [ ] No missing indexes
- [ ] Index verification passed
- [ ] Performance indexes in place

---

## 4. Application Deployment

### 4.1 Code Deployment

Deploy the new code to production:

```bash
# Pull latest code
git pull origin main

# Verify correct branch and commit
git log -1 --oneline

# Install/update dependencies
uv sync

# Run final syntax check
python -m py_compile src/second_brain_database/routes/ipam/routes.py
```

**Checklist:**
- [ ] Latest code deployed
- [ ] Correct branch/commit verified
- [ ] Dependencies updated
- [ ] No syntax errors

### 4.2 Application Restart (Zero Downtime)

For zero-downtime deployment, use a rolling restart strategy:

**Option A: Using systemd (recommended)**

```bash
# Reload systemd configuration
sudo systemctl daemon-reload

# Restart service with graceful shutdown
sudo systemctl reload ipam-backend

# Or restart if reload not supported
sudo systemctl restart ipam-backend

# Check status
sudo systemctl status ipam-backend
```

**Option B: Using process manager (PM2, Supervisor)**

```bash
# PM2 example
pm2 reload ipam-backend --update-env

# Supervisor example
supervisorctl restart ipam-backend
```

**Option C: Manual restart (development)**

```bash
# Stop current process (Ctrl+C or kill)
pkill -f "uvicorn.*main:app"

# Start new process
uv run uvicorn src.second_brain_database.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  --log-level info
```

**Checklist:**
- [ ] Application restarted successfully
- [ ] No startup errors
- [ ] All workers started
- [ ] Health check passes

### 4.3 Verify Application Startup

Check that the application started correctly:

```bash
# Check process is running
ps aux | grep uvicorn

# Check logs for errors
tail -f logs/app.log | grep -i error

# Check health endpoint
curl http://localhost:8000/health

# Expected: {"status": "healthy"}
```

**Checklist:**
- [ ] Process running
- [ ] No error logs
- [ ] Health check passes
- [ ] All routes registered

---

## 5. Verification & Testing

### 5.1 API Endpoint Verification

Verify all new endpoints are accessible:

```bash
# Set authentication token
export TOKEN="<production-jwt-token>"

# Check OpenAPI documentation
curl http://localhost:8000/openapi.json | jq '.paths | keys | .[] | select(contains("ipam"))'

# Expected: List of all IPAM endpoints including new ones
```

**Verify new endpoint groups:**

```bash
# Reservations
curl -X GET http://localhost:8000/ipam/reservations \
  -H "Authorization: Bearer $TOKEN"

# Preferences
curl -X GET http://localhost:8000/ipam/preferences \
  -H "Authorization: Bearer $TOKEN"

# Dashboard Statistics
curl -X GET http://localhost:8000/ipam/statistics/dashboard \
  -H "Authorization: Bearer $TOKEN"

# Notifications
curl -X GET http://localhost:8000/ipam/notifications/unread \
  -H "Authorization: Bearer $TOKEN"

# Shares
curl -X GET http://localhost:8000/ipam/shares \
  -H "Authorization: Bearer $TOKEN"

# Webhooks
curl -X GET http://localhost:8000/ipam/webhooks \
  -H "Authorization: Bearer $TOKEN"
```

**Checklist:**
- [ ] All endpoints return 200 or appropriate status
- [ ] No 500 errors
- [ ] Authentication working
- [ ] Response format correct

### 5.2 Smoke Tests

Run critical path smoke tests:

```bash
# Test 1: Create and list reservation
curl -X POST http://localhost:8000/ipam/reservations \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "resource_type": "region",
    "x_octet": 99,
    "y_octet": 99,
    "reason": "Deployment smoke test",
    "expires_in_days": 1
  }'

# Verify creation
curl http://localhost:8000/ipam/reservations \
  -H "Authorization: Bearer $TOKEN" | jq '.results | length'

# Test 2: Dashboard statistics
curl http://localhost:8000/ipam/statistics/dashboard \
  -H "Authorization: Bearer $TOKEN" | jq '.total_countries'

# Test 3: User preferences
curl http://localhost:8000/ipam/preferences \
  -H "Authorization: Bearer $TOKEN" | jq 'keys'

# Test 4: Notifications
curl http://localhost:8000/ipam/notifications/unread \
  -H "Authorization: Bearer $TOKEN" | jq '.unread_count'
```

**Checklist:**
- [ ] Reservation creation works
- [ ] Dashboard statistics returns data
- [ ] Preferences endpoint works
- [ ] Notifications endpoint works

### 5.3 Performance Testing

Verify performance meets requirements:

```bash
# Test dashboard response time (should be < 500ms)
time curl -s http://localhost:8000/ipam/statistics/dashboard \
  -H "Authorization: Bearer $TOKEN" > /dev/null

# Test forecast response time (should be < 1s)
time curl -s "http://localhost:8000/ipam/statistics/forecast/country/USA" \
  -H "Authorization: Bearer $TOKEN" > /dev/null

# Test caching (second request should be faster)
time curl -s http://localhost:8000/ipam/statistics/dashboard \
  -H "Authorization: Bearer $TOKEN" > /dev/null
```

**Checklist:**
- [ ] Dashboard < 500ms
- [ ] Forecast < 1s
- [ ] Caching working (second request faster)
- [ ] No timeout errors

### 5.4 Background Tasks Verification

Verify background tasks are running:

```bash
# Check logs for background task registration
tail -f logs/app.log | grep -E "(BackgroundTask|reservation_expiration|share_expiration|notification_cleanup)"

# Expected output:
# [BackgroundTasks] Registered: reservation_expiration_checker (hourly)
# [BackgroundTasks] Registered: share_expiration_checker (hourly)
# [BackgroundTasks] Registered: notification_cleanup (daily)
```

**Checklist:**
- [ ] Reservation expiration task registered
- [ ] Share expiration task registered
- [ ] Notification cleanup task registered
- [ ] No task errors in logs

---

## 6. Monitoring Setup

### 6.1 Application Monitoring

Set up monitoring for the new features:

**Metrics to monitor:**
- API response times (p50, p95, p99)
- Error rates (4xx, 5xx)
- Request rates per endpoint
- Cache hit rates (Redis)
- Database query times
- Background task execution times

**Example: Prometheus metrics**

```python
# Already included in the application
# Metrics exposed at /metrics endpoint

# Check metrics endpoint
curl http://localhost:8000/metrics
```

**Checklist:**
- [ ] Metrics endpoint accessible
- [ ] Response time metrics present
- [ ] Error rate metrics present
- [ ] Cache metrics present

### 6.2 Log Monitoring

Configure log aggregation and alerting:

```bash
# Check log format
tail -f logs/app.log

# Expected format:
# [2025-11-13 10:00:00] [INFO] [ipam.reservations] Created reservation: 550e8400...
# [2025-11-13 10:00:01] [INFO] [ipam.statistics] Dashboard cache hit
# [2025-11-13 10:00:02] [INFO] [ipam.webhooks] Webhook delivered: 200 OK (145ms)
```

**Log levels to monitor:**
- ERROR: Immediate attention required
- WARNING: Potential issues
- INFO: Normal operations
- DEBUG: Detailed troubleshooting

**Checklist:**
- [ ] Logs being written
- [ ] Log format correct
- [ ] Log rotation configured
- [ ] Error alerting configured

### 6.3 Database Monitoring

Monitor database performance:

```bash
# Check MongoDB slow queries
mongosh $MONGODB_URL/$MONGODB_DATABASE --eval "
  db.setProfilingLevel(1, { slowms: 100 });
  print('Slow query profiling enabled (>100ms)');
"

# Check Redis memory usage
redis-cli INFO memory | grep used_memory_human

# Check Redis hit rate
redis-cli INFO stats | grep keyspace
```

**Checklist:**
- [ ] Slow query logging enabled
- [ ] Redis memory usage acceptable
- [ ] Redis hit rate > 80%
- [ ] No connection pool exhaustion

---

## 7. Post-Deployment Tasks

### 7.1 Documentation Updates

Update production documentation:

**Checklist:**
- [ ] Update API documentation with production URLs
- [ ] Update runbooks with new features
- [ ] Update incident response procedures
- [ ] Notify stakeholders of deployment

### 7.2 User Communication

Communicate new features to users:

**Checklist:**
- [ ] Send release notes to users
- [ ] Update user documentation
- [ ] Provide training materials
- [ ] Set up support channels

### 7.3 Cleanup

Clean up deployment artifacts:

```bash
# Remove backup files (after verification period)
# Keep for at least 7 days
rm -rf backup_pre_deployment_*

# Clean up old logs
find logs/ -name "*.log.*" -mtime +30 -delete

# Clean up test data
mongosh $MONGODB_URL/$MONGODB_DATABASE --eval "
  db.ipam_reservations.deleteMany({reason: /test|smoke/i});
"
```

**Checklist:**
- [ ] Old backups archived
- [ ] Test data cleaned up
- [ ] Temporary files removed
- [ ] Deployment artifacts documented

---

## 8. Rollback Procedures

If critical issues are discovered, follow these rollback procedures:

### 8.1 Immediate Rollback (Application Only)

If the issue is in the application code:

```bash
# Step 1: Stop current application
sudo systemctl stop ipam-backend

# Step 2: Checkout previous version
git checkout <previous-commit-hash>

# Step 3: Reinstall dependencies
uv sync

# Step 4: Restart application
sudo systemctl start ipam-backend

# Step 5: Verify rollback
curl http://localhost:8000/health
```

**Time estimate:** 5 minutes

### 8.2 Full Rollback (Application + Database)

If database changes need to be reverted:

```bash
# Step 1: Stop application
sudo systemctl stop ipam-backend

# Step 2: Backup current state (for analysis)
mongodump --uri="$MONGODB_URL" \
  --db=$MONGODB_DATABASE \
  --out=backup_rollback_$(date +%Y%m%d_%H%M%S) \
  --gzip

# Step 3: Run database rollback
uv run python scripts/run_ipam_enhancements_migration.py --rollback

# Step 4: Restore previous code
git checkout <previous-commit-hash>
uv sync

# Step 5: Restart application
sudo systemctl start ipam-backend

# Step 6: Verify rollback
curl http://localhost:8000/health
curl http://localhost:8000/ipam/countries \
  -H "Authorization: Bearer $TOKEN"
```

**Time estimate:** 10 minutes

**WARNING:** Rolling back the database will delete all data in the enhancement collections (reservations, shares, preferences, notifications, webhooks).

### 8.3 Rollback Verification

After rollback, verify system is stable:

```bash
# Check application health
curl http://localhost:8000/health

# Check existing IPAM functionality
curl http://localhost:8000/ipam/countries \
  -H "Authorization: Bearer $TOKEN"

# Check logs for errors
tail -f logs/app.log | grep -i error

# Monitor for 15 minutes
watch -n 30 'curl -s http://localhost:8000/health'
```

**Checklist:**
- [ ] Application running
- [ ] Health check passes
- [ ] Existing functionality works
- [ ] No error logs
- [ ] System stable for 15+ minutes

---

## 9. Troubleshooting

### Issue 1: Migration Fails

**Symptoms:**
- Migration script exits with error
- Collections not created
- Indexes missing

**Diagnosis:**
```bash
# Check MongoDB connection
mongosh $MONGODB_URL/$MONGODB_DATABASE --eval "db.runCommand({ping: 1})"

# Check permissions
mongosh $MONGODB_URL/$MONGODB_DATABASE --eval "
  db.runCommand({connectionStatus: 1}).authInfo
"

# Check disk space
df -h
```

**Solutions:**
1. Verify MongoDB connection string
2. Ensure user has createCollection and createIndex permissions
3. Check disk space (need at least 1GB free)
4. Review migration logs for specific error

### Issue 2: Endpoints Return 404

**Symptoms:**
- New endpoints return 404 Not Found
- OpenAPI docs don't show new endpoints

**Diagnosis:**
```bash
# Check if routes are registered
curl http://localhost:8000/openapi.json | jq '.paths | keys'

# Check application logs
tail -f logs/app.log | grep -i "route"

# Check for import errors
python -c "from src.second_brain_database.routes.ipam import routes"
```

**Solutions:**
1. Restart application
2. Check for import errors in routes.py
3. Verify router is registered in main.py
4. Check for syntax errors

### Issue 3: Slow Performance

**Symptoms:**
- Dashboard takes > 500ms
- Forecast takes > 1s
- High CPU usage

**Diagnosis:**
```bash
# Check Redis connection
redis-cli ping

# Check cache hit rate
redis-cli INFO stats | grep keyspace_hits

# Check MongoDB slow queries
mongosh $MONGODB_URL/$MONGODB_DATABASE --eval "
  db.system.profile.find({millis: {\$gt: 100}}).sort({ts: -1}).limit(5).pretty()
"

# Check application metrics
curl http://localhost:8000/metrics | grep response_time
```

**Solutions:**
1. Verify Redis is running and connected
2. Check cache TTL settings
3. Verify indexes are created
4. Review slow queries and optimize
5. Increase cache TTL if appropriate

### Issue 4: Background Tasks Not Running

**Symptoms:**
- Expired reservations not cleaned up
- Expired shares still accessible
- Old notifications not deleted

**Diagnosis:**
```bash
# Check logs for background task execution
tail -f logs/app.log | grep -E "(reservation_expiration|share_expiration|notification_cleanup)"

# Check if tasks are registered
curl http://localhost:8000/health | jq '.background_tasks'

# Check for errors in task execution
tail -f logs/app.log | grep -i "background.*error"
```

**Solutions:**
1. Verify background tasks are enabled in config
2. Check for errors in task execution
3. Restart application to re-register tasks
4. Verify task schedule is correct

### Issue 5: Webhook Deliveries Failing

**Symptoms:**
- Webhooks not being delivered
- High failure_count in webhooks
- Webhooks automatically disabled

**Diagnosis:**
```bash
# Check webhook delivery logs
mongosh $MONGODB_URL/$MONGODB_DATABASE --eval "
  db.ipam_webhook_deliveries.find().sort({delivered_at: -1}).limit(10).pretty()
"

# Test webhook URL manually
curl -X POST https://webhook-url.com/endpoint \
  -H "Content-Type: application/json" \
  -d '{"test": "data"}'

# Check network connectivity
ping webhook-host.com
```

**Solutions:**
1. Verify webhook URL is accessible
2. Check firewall rules for outbound HTTPS
3. Verify webhook endpoint accepts POST requests
4. Check webhook signature verification on receiving end
5. Re-enable webhook if disabled due to failures

---

## Success Criteria

Deployment is considered successful when:

### Functional Requirements
- [ ] All 31 new endpoints operational
- [ ] All existing IPAM functionality unchanged
- [ ] All smoke tests pass
- [ ] No critical errors in logs

### Performance Requirements
- [ ] Dashboard statistics < 500ms
- [ ] Capacity forecast < 1s
- [ ] Cache hit rate > 80%
- [ ] API response times within SLA

### Reliability Requirements
- [ ] No application crashes
- [ ] Error rate < 0.1%
- [ ] Uptime > 99.9%
- [ ] Background tasks executing on schedule

### Security Requirements
- [ ] Authentication working correctly
- [ ] Authorization checks enforced
- [ ] Rate limiting active
- [ ] No security vulnerabilities

---

## Deployment Sign-Off

### Pre-Deployment
- [ ] Code review completed
- [ ] Tests passing
- [ ] Documentation complete
- [ ] Backup created

**Approved by:** ________________  
**Date:** ________________

### Post-Deployment
- [ ] Deployment successful
- [ ] Verification complete
- [ ] Monitoring configured
- [ ] No critical issues

**Verified by:** ________________  
**Date:** ________________

---

## Contact Information

**Deployment Team:**
- Lead: ________________
- Backend: ________________
- DevOps: ________________
- QA: ________________

**Escalation:**
- On-call: ________________
- Manager: ________________

---

**Document Version:** 1.0  
**Last Updated:** 2025-11-13  
**Status:** Ready for Production Deployment

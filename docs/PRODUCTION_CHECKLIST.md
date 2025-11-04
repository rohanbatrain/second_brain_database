# Production Deployment Checklist

## Pre-Deployment Checklist

### ✅ Configuration
- [ ] `.sbd` file created with all required settings
- [ ] `MCP_ENABLED=true` set
- [ ] Secure `SECRET_KEY` and `FERNET_KEY` generated
- [ ] Database URLs configured correctly
- [ ] `MCP_DEBUG_MODE=false` for production
- [ ] `MCP_SECURITY_ENABLED=true`
- [ ] `MCP_RATE_LIMIT_ENABLED=true`

### ✅ Dependencies
- [ ] FastMCP library installed (`uv add fastmcp`)
- [ ] aiohttp installed for HTTP fallback
- [ ] All Python dependencies installed (`uv sync`)
- [ ] MongoDB running and accessible
- [ ] Redis running and accessible

### ✅ Security
- [ ] Strong SECRET_KEY (32+ characters)
- [ ] Unique FERNET_KEY generated
- [ ] Database credentials secured
- [ ] Firewall rules configured
- [ ] SSL/TLS certificates ready (for production)

### ✅ Testing
- [ ] Run `python test_mcp_startup.py` - passes
- [ ] Run `python check_mcp_health.py` - all green
- [ ] FastAPI server starts without errors
- [ ] MCP server accessible on port 3001
- [ ] Database connections working
- [ ] Redis connections working

## Deployment Steps

### 1. Environment Setup
```bash
# Clone repository
git clone <repository-url>
cd second_brain_database

# Install dependencies
uv sync

# Create configuration
cp .sbd.example .sbd
# Edit .sbd with your settings
```

### 2. Database Setup
```bash
# Start MongoDB
sudo systemctl start mongod

# Start Redis
sudo systemctl start redis

# Verify connections
python -c "from src.second_brain_database.database import db_manager; import asyncio; asyncio.run(db_manager.connect())"
```

### 3. Server Startup
```bash
# Test startup capability
python test_mcp_startup.py

# Start production server
python start_mcp_server.py
# OR
uv run uvicorn src.second_brain_database.main:app --host 0.0.0.0 --port 8000
```

### 4. Health Verification
```bash
# Check all systems
python check_mcp_health.py

# Manual health checks
curl http://localhost:8000/health
curl http://localhost:3001/health
curl http://localhost:3001/tools
```

## Post-Deployment Checklist

### ✅ Functionality
- [ ] FastAPI server responding on port 8000
- [ ] MCP server responding on port 3001
- [ ] Health checks passing
- [ ] Tools list returns 138+ tools
- [ ] Authentication working
- [ ] Database operations working
- [ ] Redis caching working

### ✅ Performance
- [ ] Response times < 200ms for health checks
- [ ] Memory usage stable
- [ ] No memory leaks detected
- [ ] Connection pooling working
- [ ] Background tasks running

### ✅ Security
- [ ] Authentication required for all tools
- [ ] Rate limiting active
- [ ] Audit logging working
- [ ] Error handling not exposing sensitive data
- [ ] HTTPS configured (production)

### ✅ Monitoring
- [ ] Health check endpoints accessible
- [ ] Performance metrics collecting
- [ ] Error alerts configured
- [ ] Log aggregation working
- [ ] Monitoring dashboards setup

## VSCode MCP Extension Setup

### 1. Install Extension
- Install MCP extension in VSCode
- Restart VSCode

### 2. Configure Server
Add to VSCode settings or MCP configuration:
```json
{
  "mcp.servers": {
    "SecondBrainMCP": {
      "url": "http://localhost:3001",
      "name": "Second Brain Database",
      "description": "Knowledge management and family coordination"
    }
  }
}
```

### 3. Test Connection
- Open VSCode MCP panel
- Verify "SecondBrainMCP" server appears
- Test tool execution
- Verify authentication works

## Production Hardening

### Security Hardening
- [ ] Change default ports if needed
- [ ] Configure reverse proxy (nginx/Apache)
- [ ] Set up SSL/TLS certificates
- [ ] Configure firewall rules
- [ ] Set up fail2ban for brute force protection
- [ ] Regular security updates

### Performance Optimization
- [ ] Configure connection pooling
- [ ] Set up Redis persistence
- [ ] Configure log rotation
- [ ] Set up monitoring alerts
- [ ] Configure backup strategies
- [ ] Set up load balancing (if needed)

### Maintenance
- [ ] Set up automated backups
- [ ] Configure log retention
- [ ] Set up monitoring alerts
- [ ] Plan update procedures
- [ ] Document rollback procedures
- [ ] Set up health monitoring

## Troubleshooting Guide

### Common Issues

1. **Server won't start**
   - Check `.sbd` configuration
   - Verify database connections
   - Check port availability
   - Review error logs

2. **MCP tools not working**
   - Verify authentication
   - Check user permissions
   - Review rate limiting
   - Check tool registration

3. **Performance issues**
   - Monitor memory usage
   - Check database performance
   - Review connection pooling
   - Analyze slow queries

4. **VSCode connection fails**
   - Verify server is running
   - Check port accessibility
   - Review MCP configuration
   - Test with curl commands

### Health Check Commands
```bash
# System health
python check_mcp_health.py

# Individual components
curl http://localhost:8000/health
curl http://localhost:3001/health
curl http://localhost:3001/

# Database connectivity
python -c "from src.second_brain_database.database import db_manager; import asyncio; print('DB OK' if asyncio.run(db_manager.connect()) else 'DB FAIL')"

# Redis connectivity  
python -c "from src.second_brain_database.managers.redis_manager import redis_manager; import asyncio; print('Redis OK' if asyncio.run(redis_manager.get_redis()) else 'Redis FAIL')"
```

## Success Criteria

✅ **Deployment Successful When:**
- All health checks pass
- MCP server responds on port 3001
- FastAPI server responds on port 8000
- VSCode MCP extension connects successfully
- Tools execute without errors
- Authentication and authorization working
- Performance metrics within acceptable ranges
- No critical errors in logs

## Rollback Plan

If deployment fails:
1. Stop all services
2. Restore previous configuration
3. Restart with known good configuration
4. Verify health checks
5. Document issues for future resolution

## Support Contacts

- **Technical Issues**: Check logs and run diagnostic scripts
- **Configuration Help**: Review MCP_SERVER_SETUP.md
- **Performance Issues**: Monitor system resources and database performance
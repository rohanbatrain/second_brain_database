# 📊 Log Monitoring & Debugging Guide

Complete guide for monitoring and troubleshooting your Second Brain Database services.

## 🎯 Quick Log Access

### View Logs in Current Terminal

```bash
# Interactive menu - choose service by number or name
./scripts/startall/attach_service.sh

# Direct service access
./scripts/startall/attach_service.sh fastapi
./scripts/startall/attach_service.sh celery_worker
./scripts/startall/attach_service.sh flower
```

### Open Logs in New Terminal Windows

```bash
# Single service in new Terminal window
./scripts/startall/open_service_terminal.sh fastapi

# Open ALL services in separate Terminal tabs
./scripts/startall/open_all_terminals.sh
```

### Quick Tail Commands

```bash
# Follow live logs
tail -f logs/fastapi.log
tail -f logs/celery_worker.log
tail -f logs/celery_beat.log
tail -f logs/flower.log
tail -f logs/voice_worker.log

# View startup log
tail -f logs/startup_$(ls -t logs/startup_* | head -1 | xargs basename)

# Last 100 lines
tail -100 logs/fastapi.log

# Follow multiple logs at once
tail -f logs/fastapi.log logs/celery_worker.log
```

---

## 📁 Log File Locations

All logs are stored in `logs/` directory:

| Service | Log File | Purpose |
|---------|----------|---------|
| **FastAPI** | `logs/fastapi.log` | API requests, responses, errors |
| **Celery Worker** | `logs/celery_worker.log` | Task execution (AI, workflows) |
| **Celery Beat** | `logs/celery_beat.log` | Scheduled task triggers |
| **Flower** | `logs/flower.log` | Task monitoring dashboard |
| **Voice Worker** | `logs/voice_worker.log` | LiveKit voice processing |
| **LiveKit** | `logs/livekit.log` | WebRTC server logs |
| **Ollama** | `logs/ollama.log` | LLM model serving |
| **Redis** | `logs/redis.log` | Cache & message broker |
| **Startup** | `logs/startup_YYYYMMDD_HHMMSS.log` | Service startup logs |
| **Import Tests** | `logs/fastapi_import_test.log` | FastAPI import validation |
| **Import Tests** | `logs/celery_import_test.log` | Celery import validation |

---

## 🔍 Filtering & Searching Logs

### Find Errors Across All Logs

```bash
# Real-time error monitoring (all services)
tail -f logs/*.log | grep -i error

# Count errors in last hour
grep -i error logs/fastapi.log | tail -100

# Find specific error type
grep "ValueError" logs/celery_worker.log

# Show errors with 3 lines of context
grep -i -C 3 error logs/fastapi.log
```

### Search for Specific Events

```bash
# API requests to specific endpoint
grep "POST /api/ai/chat" logs/fastapi.log

# Successful task completions
grep "Task.*succeeded" logs/celery_worker.log

# Failed tasks
grep "Task.*failed" logs/celery_worker.log | tail -20

# Database queries
grep "SELECT\|INSERT\|UPDATE" logs/fastapi.log

# User-specific logs (replace USER_ID)
grep "user_id.*12345" logs/fastapi.log
```

### Advanced Filtering with `grep`

```bash
# Multiple patterns (OR logic)
grep -E "error|warning|critical" logs/fastapi.log

# Case-insensitive
grep -i "exception" logs/celery_worker.log

# Exclude patterns (NOT logic)
grep error logs/fastapi.log | grep -v "health check"

# Show only matching part
grep -o "Task.*succeeded" logs/celery_worker.log

# Count occurrences
grep -c "ERROR" logs/fastapi.log
```

---

## 🚨 Production-Ready Error Handling

### Service Failure Scenarios

The startup script now handles failures gracefully:

#### **Critical Failures** (Startup stops)
- ❌ MongoDB not accessible
- ❌ Redis fails to start
- ❌ FastAPI fails to start

```bash
# If MongoDB fails:
[ERROR] MongoDB not accessible on port 27017
[WARNING] Please ensure MongoDB Docker container is running:
  docker run -d -p 27017:27017 --name mongodb mongo
Or start existing container:
  docker start mongodb
```

#### **Non-Critical Failures** (Startup continues)
- ⚠️ Celery Worker fails
- ⚠️ Celery Beat fails
- ⚠️ Voice Worker fails
- ⚠️ Flower fails
- ⚠️ LiveKit not installed
- ⚠️ Ollama not installed

```bash
# If Celery fails:
[ERROR] Celery Worker failed to start. Check logs: tail -f logs/celery_worker.log
[WARNING] ⚠ Startup completed with some failures
Failed services: celery_worker
```

### Check Service Status

```bash
# Check what's running
ps aux | grep -E 'fastapi|celery|flower|ollama|livekit|redis'

# Check PIDs
ls -lh pids/
cat pids/fastapi.pid

# Verify ports
lsof -i :8000  # FastAPI
lsof -i :6379  # Redis
lsof -i :27017 # MongoDB
lsof -i :5555  # Flower
lsof -i :11434 # Ollama
```

---

## 📈 Monitoring Patterns

### 1. **API Request Monitoring**

```bash
# Watch all incoming requests
tail -f logs/fastapi.log | grep "INFO.*GET\|POST\|PUT\|DELETE"

# Monitor specific endpoint
tail -f logs/fastapi.log | grep "/api/ai/chat"

# Track response times (if logged)
tail -f logs/fastapi.log | grep "completed in"

# Count requests per minute
watch -n 60 'grep "$(date +%H:%M)" logs/fastapi.log | wc -l'
```

### 2. **Task Queue Monitoring**

```bash
# Watch task executions
tail -f logs/celery_worker.log | grep "Task.*received\|succeeded\|failed"

# Monitor specific queue
tail -f logs/celery_worker.log | grep "queue:ai"

# Count pending tasks (via Flower API)
curl -s http://localhost:5555/api/tasks | jq '.active | length'

# Or use Flower web UI:
open http://localhost:5555
```

### 3. **Error Pattern Detection**

```bash
# Find recurring errors
grep -i error logs/fastapi.log | sort | uniq -c | sort -rn

# Track error rate over time
for i in {00..23}; do
  echo "Hour $i: $(grep "$i:" logs/fastapi.log | grep -i error | wc -l) errors"
done

# Get last 10 unique errors
grep -i error logs/fastapi.log | tail -50 | cut -d']' -f3- | sort -u | tail -10
```

### 4. **Performance Debugging**

```bash
# Find slow requests (if response time logged)
grep "completed in.*[0-9][0-9][0-9]ms" logs/fastapi.log

# Database connection issues
grep -i "connection\|timeout\|pool" logs/fastapi.log

# Memory/CPU warnings
grep -i "memory\|cpu\|resource" logs/*.log
```

---

## 🛠️ Troubleshooting Common Issues

### FastAPI Won't Start

```bash
# 1. Check if port is in use
lsof -i :8000

# 2. Check for import/module errors (NEW!)
cat logs/fastapi_import_test.log

# 3. View detailed startup logs
tail -100 logs/fastapi.log

# 4. Look for import errors
grep -i "importerror\|modulenotfounderror" logs/fastapi.log

# 5. Test imports manually
python -c "from src.second_brain_database.main import app; print('✓ OK')"

# 6. Check for missing dependencies
python -c "from src.second_brain_database.integrations.langchain.orchestrator import LangChainOrchestrator"
```

### Celery Worker Issues

```bash
# 1. Check Redis connection
redis-cli ping

# 2. Check for import errors (NEW!)
cat logs/celery_import_test.log

# 3. View worker startup
tail -100 logs/celery_worker.log

# 4. Check for task failures
grep "Task.*FAILURE" logs/celery_worker.log | tail -10

# 5. Inspect task errors
grep -A 10 "Traceback" logs/celery_worker.log | tail -50

# 6. Test Celery imports manually
python -c "from src.second_brain_database.celery_app import celery_app; print('✓ OK')"
```

### MongoDB Connection Problems

```bash
# 1. Check Docker container status
docker ps | grep mongo

# 2. Check if port is accessible
nc -z localhost 27017 && echo "✓ MongoDB reachable"

# 3. View MongoDB logs (Docker)
docker logs mongodb --tail 100 --follow

# 4. Test connection from Python
python -c "from pymongo import MongoClient; print(MongoClient('mongodb://localhost:27017').server_info())"
```

### Voice Worker Not Starting

```bash
# 1. Check LiveKit server status
curl -s http://localhost:7880/rtc | head -10

# 2. View voice worker logs
tail -100 logs/voice_worker.log

# 3. Check environment variables
grep LIVEKIT logs/voice_worker.log

# 4. Verify LiveKit installation
which livekit-server
```

---

## 📊 Log Rotation & Cleanup

### Manual Cleanup

```bash
# Archive old logs (keep last 7 days)
find logs/ -name "*.log" -mtime +7 -exec gzip {} \;

# Delete very old logs (>30 days)
find logs/ -name "*.log.gz" -mtime +30 -delete

# Clear all logs (use with caution!)
rm -f logs/*.log

# Keep logs but truncate (empty while preserving file)
truncate -s 0 logs/fastapi.log
```

### Automated Log Rotation Setup

```bash
# Create logrotate config (macOS/Linux)
cat > /usr/local/etc/logrotate.d/second_brain <<'EOF'
/Users/rohan/Documents/repos/second_brain_database/logs/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    create 644 rohan staff
}
EOF

# Test logrotate
logrotate -d /usr/local/etc/logrotate.d/second_brain
```

---

## 🔔 Real-Time Monitoring Dashboard

### Using `watch` for Live Updates

```bash
# Monitor all service PIDs
watch -n 2 'ps aux | grep -E "fastapi|celery|flower" | grep -v grep'

# Count recent errors
watch -n 10 'tail -1000 logs/fastapi.log | grep -c ERROR'

# Active Celery tasks
watch -n 5 'curl -s http://localhost:5555/api/tasks | jq ".active | length"'
```

### Using `multitail` (Install: `brew install multitail`)

```bash
# View multiple logs in split screen
multitail logs/fastapi.log logs/celery_worker.log logs/celery_beat.log

# With colors and filtering
multitail -ci green -I logs/fastapi.log -ci red -I logs/celery_worker.log
```

### Using `tmux` for Persistent Sessions

```bash
# Create monitoring session
tmux new-session -d -s logs
tmux split-window -v
tmux split-window -h
tmux select-pane -t 0
tmux send-keys "tail -f logs/fastapi.log" Enter
tmux select-pane -t 1
tmux send-keys "tail -f logs/celery_worker.log" Enter
tmux select-pane -t 2
tmux send-keys "tail -f logs/flower.log" Enter

# Attach to session
tmux attach -t logs
```

---

## 🎓 Advanced Log Analysis

### Extract JSON Logs for Analysis

```bash
# Extract all JSON-formatted log entries
grep -o '{.*}' logs/fastapi.log | jq '.' > parsed_logs.json

# Analyze API response times
grep "completed_in" logs/fastapi.log | \
  jq -r '.completed_in' | \
  awk '{sum+=$1; count++} END {print "Avg:", sum/count "ms"}'
```

### Performance Profiling

```bash
# Requests per second
grep "$(date +%Y-%m-%d)" logs/fastapi.log | wc -l | \
  awk -v secs=$((60*60*24)) '{print $1/secs " req/sec"}'

# Error rate percentage
total=$(grep "HTTP" logs/fastapi.log | wc -l)
errors=$(grep "HTTP.*[45][0-9][0-9]" logs/fastapi.log | wc -l)
awk -v e=$errors -v t=$total 'BEGIN {printf "Error rate: %.2f%%\n", (e/t)*100}'
```

### Custom Log Parsing Script

```bash
# Create analysis script
cat > analyze_logs.sh <<'EOF'
#!/bin/bash
echo "=== Log Analysis Report ==="
echo "Date: $(date)"
echo ""
echo "Total Requests: $(grep -c "HTTP" logs/fastapi.log)"
echo "Errors (5xx): $(grep -c "HTTP.*5[0-9][0-9]" logs/fastapi.log)"
echo "Client Errors (4xx): $(grep -c "HTTP.*4[0-9][0-9]" logs/fastapi.log)"
echo "Celery Tasks Completed: $(grep -c "succeeded" logs/celery_worker.log)"
echo "Celery Tasks Failed: $(grep -c "failed" logs/celery_worker.log)"
echo ""
echo "Top 5 Endpoints:"
grep "HTTP" logs/fastapi.log | awk '{print $6}' | sort | uniq -c | sort -rn | head -5
EOF

chmod +x analyze_logs.sh
./analyze_logs.sh
```

---

## 🚀 Production Monitoring Checklist

### Daily Checks
- [ ] Check startup logs for failures: `tail logs/startup_*.log`
- [ ] Review error counts: `grep -c ERROR logs/*.log`
- [ ] Verify all services running: `ps aux | grep -E 'fastapi|celery'`
- [ ] Check Flower dashboard: http://localhost:5555

### Weekly Checks
- [ ] Analyze error patterns: `grep ERROR logs/*.log | sort | uniq -c`
- [ ] Review task failure rates in Flower
- [ ] Check log file sizes: `du -sh logs/`
- [ ] Rotate/compress old logs

### Monthly Checks
- [ ] Archive logs older than 30 days
- [ ] Review performance trends
- [ ] Update log retention policies
- [ ] Test disaster recovery procedures

---

## 🆘 Emergency Debugging

### System Completely Down

```bash
# 1. Check all services
./stop.sh
sleep 5
./start.sh

# 2. View startup log
tail -f logs/startup_*.log

# 3. Check system resources
top -l 1 | grep "CPU\|PhysMem"
df -h

# 4. Clear PIDs and retry
rm -f pids/*.pid
./start.sh
```

### Hung Processes

```bash
# Find and kill hung processes
ps aux | grep -E 'fastapi|celery' | awk '{print $2}' | xargs kill -9

# Clean up and restart
./stop.sh
rm -f pids/*.pid
./start.sh
```

### Database Issues

```bash
# Restart MongoDB Docker
docker restart mongodb

# Check MongoDB logs
docker logs mongodb --tail 100

# Test connection
python -c "from pymongo import MongoClient; print(MongoClient().server_info())"
```

---

## 📞 Support & Resources

- **Startup Issues**: Check `logs/startup_YYYYMMDD_HHMMSS.log`
- **API Errors**: Check `logs/fastapi.log`
- **Task Failures**: Check `logs/celery_worker.log` and http://localhost:5555
- **Voice Issues**: Check `logs/voice_worker.log` and `logs/livekit.log`

**Quick Help Commands:**
```bash
# Service status
./scripts/startall/attach_service.sh

# View all logs
./scripts/startall/open_all_terminals.sh

# Emergency restart
./stop.sh && sleep 5 && ./start.sh
```

---

**Pro Tips:**
- 💡 Use `grep -i` for case-insensitive searches
- 💡 Pipe to `less` for scrollable output: `grep ERROR logs/*.log | less`
- 💡 Use `watch` for live updates: `watch -n 5 'tail -20 logs/fastapi.log'`
- 💡 Set up log alerts: `grep -i error logs/fastapi.log && osascript -e 'display notification "Errors detected!"'`

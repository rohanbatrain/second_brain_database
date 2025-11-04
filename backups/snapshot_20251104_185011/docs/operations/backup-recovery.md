# Backup and Recovery Procedures

## Overview

This document outlines comprehensive backup and recovery procedures for the Family Management System. It covers data backup strategies, recovery procedures, disaster recovery planning, and business continuity measures.

## Backup Strategy

### Backup Types

1. **Full Backups**: Complete system and data backup
2. **Incremental Backups**: Changes since last backup
3. **Differential Backups**: Changes since last full backup
4. **Point-in-Time Recovery**: Transaction log backups

### Backup Schedule

| Backup Type | Frequency | Retention | Storage Location |
|-------------|-----------|-----------|------------------|
| Full System | Weekly | 12 weeks | Off-site storage |
| Database Full | Daily | 30 days | Local + Cloud |
| Database Incremental | Every 4 hours | 7 days | Local storage |
| Transaction Logs | Every 15 minutes | 24 hours | Local storage |
| Configuration | On change | 90 days | Version control |
| Application Code | On deployment | Indefinite | Git repository |

### Recovery Point Objective (RPO)
- **Critical Data**: 15 minutes
- **Application Data**: 4 hours
- **Configuration**: 24 hours

### Recovery Time Objective (RTO)
- **Critical Services**: 1 hour
- **Full System**: 4 hours
- **Complete Disaster Recovery**: 24 hours

## Database Backup Procedures

### MongoDB Backup

#### Automated Daily Backup Script

Create `/opt/scripts/backup_mongodb.sh`:

```bash
#!/bin/bash

# MongoDB Backup Script
# Runs daily via cron at 2:00 AM

set -e

# Configuration
BACKUP_DIR="/opt/backups/mongodb"
RETENTION_DAYS=30
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="mongodb_backup_$DATE"
LOG_FILE="/var/log/backup/mongodb_backup.log"

# MongoDB connection details
MONGO_URI="mongodb://backup_user:backup_password@localhost:27017/second_brain_database?authSource=admin&replicaSet=rs0"
DATABASE_NAME="second_brain_database"

# S3 configuration for off-site storage
S3_BUCKET="sbd-backups"
S3_PREFIX="mongodb"

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Create backup directory
mkdir -p "$BACKUP_DIR"
mkdir -p "$(dirname "$LOG_FILE")"

log "Starting MongoDB backup: $BACKUP_NAME"

# Create backup
log "Creating mongodump..."
if mongodump --uri="$MONGO_URI" --db="$DATABASE_NAME" --out="$BACKUP_DIR/$BACKUP_NAME"; then
    log "Mongodump completed successfully"
else
    log "ERROR: Mongodump failed"
    exit 1
fi

# Compress backup
log "Compressing backup..."
if tar -czf "$BACKUP_DIR/$BACKUP_NAME.tar.gz" -C "$BACKUP_DIR" "$BACKUP_NAME"; then
    log "Compression completed successfully"
    rm -rf "$BACKUP_DIR/$BACKUP_NAME"
else
    log "ERROR: Compression failed"
    exit 1
fi

# Calculate backup size
BACKUP_SIZE=$(du -h "$BACKUP_DIR/$BACKUP_NAME.tar.gz" | cut -f1)
log "Backup size: $BACKUP_SIZE"

# Upload to S3 (if configured)
if command -v aws &> /dev/null && [ -n "$S3_BUCKET" ]; then
    log "Uploading to S3..."
    if aws s3 cp "$BACKUP_DIR/$BACKUP_NAME.tar.gz" "s3://$S3_BUCKET/$S3_PREFIX/$BACKUP_NAME.tar.gz"; then
        log "S3 upload completed successfully"
    else
        log "WARNING: S3 upload failed"
    fi
fi

# Verify backup integrity
log "Verifying backup integrity..."
if tar -tzf "$BACKUP_DIR/$BACKUP_NAME.tar.gz" > /dev/null; then
    log "Backup integrity verified"
else
    log "ERROR: Backup integrity check failed"
    exit 1
fi

# Clean up old backups
log "Cleaning up old backups..."
find "$BACKUP_DIR" -name "mongodb_backup_*.tar.gz" -mtime +$RETENTION_DAYS -delete
log "Cleanup completed"

# Send notification
if command -v mail &> /dev/null; then
    echo "MongoDB backup completed successfully: $BACKUP_NAME ($BACKUP_SIZE)" | \
        mail -s "MongoDB Backup Success" admin@yourdomain.com
fi

log "MongoDB backup completed: $BACKUP_NAME"
```

#### Point-in-Time Recovery Setup

Enable MongoDB oplog for point-in-time recovery:

```javascript
// Connect to MongoDB primary
use local

// Check oplog size
db.oplog.rs.stats()

// Resize oplog if needed (example: 10GB)
db.adminCommand({replSetResizeOplog: 1, size: 10240})
```

#### Incremental Backup Script

Create `/opt/scripts/backup_mongodb_incremental.sh`:

```bash
#!/bin/bash

# MongoDB Incremental Backup Script
# Runs every 4 hours via cron

set -e

BACKUP_DIR="/opt/backups/mongodb/incremental"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="mongodb_incremental_$DATE"
LOG_FILE="/var/log/backup/mongodb_incremental.log"

# Get last backup timestamp
LAST_BACKUP_FILE="/opt/backups/mongodb/.last_backup_timestamp"
if [ -f "$LAST_BACKUP_FILE" ]; then
    LAST_TIMESTAMP=$(cat "$LAST_BACKUP_FILE")
else
    # If no previous backup, use 24 hours ago
    LAST_TIMESTAMP=$(date -d "24 hours ago" --iso-8601=seconds)
fi

CURRENT_TIMESTAMP=$(date --iso-8601=seconds)

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

mkdir -p "$BACKUP_DIR"

log "Starting incremental backup from $LAST_TIMESTAMP to $CURRENT_TIMESTAMP"

# Backup oplog entries since last backup
mongodump --uri="mongodb://backup_user:backup_password@localhost:27017/local?authSource=admin" \
    --collection=oplog.rs \
    --query="{\"ts\": {\$gte: Timestamp($(date -d "$LAST_TIMESTAMP" +%s), 0)}}" \
    --out="$BACKUP_DIR/$BACKUP_NAME"

# Compress backup
tar -czf "$BACKUP_DIR/$BACKUP_NAME.tar.gz" -C "$BACKUP_DIR" "$BACKUP_NAME"
rm -rf "$BACKUP_DIR/$BACKUP_NAME"

# Update timestamp
echo "$CURRENT_TIMESTAMP" > "$LAST_BACKUP_FILE"

log "Incremental backup completed: $BACKUP_NAME"
```

### Redis Backup

#### Redis Backup Script

Create `/opt/scripts/backup_redis.sh`:

```bash
#!/bin/bash

# Redis Backup Script

set -e

BACKUP_DIR="/opt/backups/redis"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="redis_backup_$DATE"
LOG_FILE="/var/log/backup/redis_backup.log"
REDIS_DATA_DIR="/var/lib/redis"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

mkdir -p "$BACKUP_DIR"

log "Starting Redis backup: $BACKUP_NAME"

# Force Redis to save current state
redis-cli BGSAVE

# Wait for background save to complete
while [ "$(redis-cli LASTSAVE)" = "$(redis-cli LASTSAVE)" ]; do
    sleep 1
done

# Copy RDB file
cp "$REDIS_DATA_DIR/dump.rdb" "$BACKUP_DIR/dump_$DATE.rdb"

# Also backup AOF file if enabled
if [ -f "$REDIS_DATA_DIR/appendonly.aof" ]; then
    cp "$REDIS_DATA_DIR/appendonly.aof" "$BACKUP_DIR/appendonly_$DATE.aof"
fi

# Compress backup
tar -czf "$BACKUP_DIR/$BACKUP_NAME.tar.gz" -C "$BACKUP_DIR" dump_$DATE.rdb appendonly_$DATE.aof 2>/dev/null || \
tar -czf "$BACKUP_DIR/$BACKUP_NAME.tar.gz" -C "$BACKUP_DIR" dump_$DATE.rdb

# Clean up individual files
rm -f "$BACKUP_DIR/dump_$DATE.rdb" "$BACKUP_DIR/appendonly_$DATE.aof"

# Clean up old backups (keep 7 days)
find "$BACKUP_DIR" -name "redis_backup_*.tar.gz" -mtime +7 -delete

log "Redis backup completed: $BACKUP_NAME"
```

## Application Backup Procedures

### Configuration Backup

Create `/opt/scripts/backup_config.sh`:

```bash
#!/bin/bash

# Configuration Backup Script

set -e

BACKUP_DIR="/opt/backups/config"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="config_backup_$DATE"
LOG_FILE="/var/log/backup/config_backup.log"

CONFIG_DIRS=(
    "/etc/nginx"
    "/etc/systemd/system"
    "/etc/prometheus"
    "/etc/grafana"
    "/opt/second_brain_database"
)

CONFIG_FILES=(
    "/etc/mongod.conf"
    "/etc/redis/redis.conf"
    "/.sbd"
)

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

mkdir -p "$BACKUP_DIR/$BACKUP_NAME"

log "Starting configuration backup: $BACKUP_NAME"

# Backup directories
for dir in "${CONFIG_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        log "Backing up directory: $dir"
        cp -r "$dir" "$BACKUP_DIR/$BACKUP_NAME/"
    fi
done

# Backup individual files
for file in "${CONFIG_FILES[@]}"; do
    if [ -f "$file" ]; then
        log "Backing up file: $file"
        cp "$file" "$BACKUP_DIR/$BACKUP_NAME/"
    fi
done

# Create system info snapshot
log "Creating system info snapshot"
{
    echo "=== System Information ==="
    uname -a
    echo ""
    echo "=== Installed Packages ==="
    dpkg -l
    echo ""
    echo "=== Running Services ==="
    systemctl list-units --type=service --state=running
    echo ""
    echo "=== Network Configuration ==="
    ip addr show
    echo ""
    echo "=== Disk Usage ==="
    df -h
} > "$BACKUP_DIR/$BACKUP_NAME/system_info.txt"

# Compress backup
tar -czf "$BACKUP_DIR/$BACKUP_NAME.tar.gz" -C "$BACKUP_DIR" "$BACKUP_NAME"
rm -rf "$BACKUP_DIR/$BACKUP_NAME"

# Clean up old backups (keep 90 days)
find "$BACKUP_DIR" -name "config_backup_*.tar.gz" -mtime +90 -delete

log "Configuration backup completed: $BACKUP_NAME"
```

### Application Code Backup

```bash
#!/bin/bash

# Application Code Backup Script

set -e

BACKUP_DIR="/opt/backups/application"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="app_backup_$DATE"
APP_DIR="/opt/second_brain_database"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "/var/log/backup/app_backup.log"
}

mkdir -p "$BACKUP_DIR"

log "Starting application backup: $BACKUP_NAME"

# Create git bundle for version control
cd "$APP_DIR"
git bundle create "$BACKUP_DIR/$BACKUP_NAME.bundle" --all

# Backup current deployment
tar -czf "$BACKUP_DIR/$BACKUP_NAME.tar.gz" \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='logs/*' \
    --exclude='.venv' \
    -C "$(dirname "$APP_DIR")" "$(basename "$APP_DIR")"

log "Application backup completed: $BACKUP_NAME"
```

## Recovery Procedures

### Database Recovery

#### Full MongoDB Recovery

```bash
#!/bin/bash

# MongoDB Full Recovery Script

set -e

BACKUP_FILE="$1"
RECOVERY_DB="${2:-second_brain_database_recovery}"

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup_file> [recovery_database_name]"
    exit 1
fi

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log "Starting MongoDB recovery from: $BACKUP_FILE"

# Stop application to prevent data corruption
log "Stopping application..."
sudo systemctl stop sbd-api

# Extract backup
TEMP_DIR=$(mktemp -d)
tar -xzf "$BACKUP_FILE" -C "$TEMP_DIR"

# Find the backup directory
BACKUP_DIR=$(find "$TEMP_DIR" -name "second_brain_database" -type d | head -1)

if [ -z "$BACKUP_DIR" ]; then
    log "ERROR: Could not find database backup in archive"
    rm -rf "$TEMP_DIR"
    exit 1
fi

# Restore database
log "Restoring database to: $RECOVERY_DB"
mongorestore --uri="mongodb://localhost:27017/$RECOVERY_DB" \
    --drop "$BACKUP_DIR"

# Verify restoration
log "Verifying restoration..."
COLLECTION_COUNT=$(mongosh --quiet --eval "
db = db.getSiblingDB('$RECOVERY_DB');
print(db.getCollectionNames().length);
")

log "Restored $COLLECTION_COUNT collections"

# Clean up
rm -rf "$TEMP_DIR"

log "Recovery completed. Database restored to: $RECOVERY_DB"
log "To use recovered database, update configuration and restart application"
```

#### Point-in-Time Recovery

```bash
#!/bin/bash

# MongoDB Point-in-Time Recovery Script

set -e

TARGET_TIME="$1"
FULL_BACKUP="$2"
OPLOG_BACKUPS_DIR="$3"

if [ -z "$TARGET_TIME" ] || [ -z "$FULL_BACKUP" ] || [ -z "$OPLOG_BACKUPS_DIR" ]; then
    echo "Usage: $0 <target_time> <full_backup_file> <oplog_backups_directory>"
    echo "Example: $0 '2024-01-01T12:00:00Z' /opt/backups/mongodb/full_backup.tar.gz /opt/backups/mongodb/incremental/"
    exit 1
fi

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log "Starting point-in-time recovery to: $TARGET_TIME"

# Stop application
sudo systemctl stop sbd-api

# Restore full backup first
log "Restoring full backup..."
TEMP_DIR=$(mktemp -d)
tar -xzf "$FULL_BACKUP" -C "$TEMP_DIR"
BACKUP_DIR=$(find "$TEMP_DIR" -name "second_brain_database" -type d | head -1)

mongorestore --uri="mongodb://localhost:27017/second_brain_database_recovery" \
    --drop "$BACKUP_DIR"

# Apply oplog entries up to target time
log "Applying oplog entries up to $TARGET_TIME..."

# Convert target time to MongoDB timestamp
TARGET_TIMESTAMP=$(uv run python -c "
import datetime
from bson.timestamp import Timestamp
dt = datetime.datetime.fromisoformat('$TARGET_TIME'.replace('Z', '+00:00'))
ts = Timestamp(int(dt.timestamp()), 0)
print(f'{ts.time},{ts.inc}')
")

# Find and apply relevant oplog backups
for oplog_backup in "$OPLOG_BACKUPS_DIR"/mongodb_incremental_*.tar.gz; do
    if [ -f "$oplog_backup" ]; then
        log "Processing oplog backup: $(basename "$oplog_backup")"
        
        OPLOG_TEMP=$(mktemp -d)
        tar -xzf "$oplog_backup" -C "$OPLOG_TEMP"
        
        mongorestore --uri="mongodb://localhost:27017/second_brain_database_recovery" \
            --oplogReplay \
            --oplogLimit="$TARGET_TIMESTAMP" \
            "$OPLOG_TEMP"
        
        rm -rf "$OPLOG_TEMP"
    fi
done

# Clean up
rm -rf "$TEMP_DIR"

log "Point-in-time recovery completed to: $TARGET_TIME"
log "Recovered database: second_brain_database_recovery"
```

#### Redis Recovery

```bash
#!/bin/bash

# Redis Recovery Script

set -e

BACKUP_FILE="$1"

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <redis_backup_file>"
    exit 1
fi

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log "Starting Redis recovery from: $BACKUP_FILE"

# Stop Redis service
log "Stopping Redis..."
sudo systemctl stop redis

# Backup current data
CURRENT_DATA_DIR="/var/lib/redis"
BACKUP_CURRENT_DIR="/tmp/redis_backup_$(date +%Y%m%d_%H%M%S)"

log "Backing up current Redis data to: $BACKUP_CURRENT_DIR"
mkdir -p "$BACKUP_CURRENT_DIR"
cp "$CURRENT_DATA_DIR"/* "$BACKUP_CURRENT_DIR/" 2>/dev/null || true

# Extract and restore backup
TEMP_DIR=$(mktemp -d)
tar -xzf "$BACKUP_FILE" -C "$TEMP_DIR"

# Find RDB file
RDB_FILE=$(find "$TEMP_DIR" -name "dump_*.rdb" | head -1)
AOF_FILE=$(find "$TEMP_DIR" -name "appendonly_*.aof" | head -1)

if [ -n "$RDB_FILE" ]; then
    log "Restoring RDB file..."
    cp "$RDB_FILE" "$CURRENT_DATA_DIR/dump.rdb"
    chown redis:redis "$CURRENT_DATA_DIR/dump.rdb"
fi

if [ -n "$AOF_FILE" ]; then
    log "Restoring AOF file..."
    cp "$AOF_FILE" "$CURRENT_DATA_DIR/appendonly.aof"
    chown redis:redis "$CURRENT_DATA_DIR/appendonly.aof"
fi

# Start Redis service
log "Starting Redis..."
sudo systemctl start redis

# Verify recovery
sleep 5
if redis-cli ping > /dev/null; then
    log "Redis recovery successful"
    KEY_COUNT=$(redis-cli dbsize)
    log "Restored database contains $KEY_COUNT keys"
else
    log "ERROR: Redis recovery failed"
    exit 1
fi

# Clean up
rm -rf "$TEMP_DIR"

log "Redis recovery completed"
```

## Disaster Recovery Procedures

### Complete System Recovery

#### Recovery Checklist

1. **Infrastructure Setup**
   - [ ] Provision new servers
   - [ ] Install operating system
   - [ ] Configure network settings
   - [ ] Install required software

2. **Database Recovery**
   - [ ] Restore MongoDB from backup
   - [ ] Restore Redis from backup
   - [ ] Verify data integrity
   - [ ] Update connection strings

3. **Application Recovery**
   - [ ] Deploy application code
   - [ ] Restore configuration files
   - [ ] Update environment variables
   - [ ] Start application services

4. **Verification**
   - [ ] Test application functionality
   - [ ] Verify data consistency
   - [ ] Check external integrations
   - [ ] Update DNS records

#### Automated Recovery Script

Create `/opt/scripts/disaster_recovery.sh`:

```bash
#!/bin/bash

# Disaster Recovery Script

set -e

RECOVERY_CONFIG="$1"

if [ -z "$RECOVERY_CONFIG" ]; then
    echo "Usage: $0 <recovery_config_file>"
    exit 1
fi

# Source recovery configuration
source "$RECOVERY_CONFIG"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$RECOVERY_LOG"
}

log "Starting disaster recovery procedure"

# Phase 1: System Preparation
log "Phase 1: System preparation"
apt update && apt upgrade -y
apt install -y mongodb redis-server nginx python3 python3-pip

# Phase 2: Database Recovery
log "Phase 2: Database recovery"
systemctl start mongodb redis

# Restore MongoDB
if [ -n "$MONGODB_BACKUP_URL" ]; then
    log "Downloading MongoDB backup..."
    wget -O /tmp/mongodb_backup.tar.gz "$MONGODB_BACKUP_URL"
    
    log "Restoring MongoDB..."
    TEMP_DIR=$(mktemp -d)
    tar -xzf /tmp/mongodb_backup.tar.gz -C "$TEMP_DIR"
    mongorestore --drop "$TEMP_DIR"/*/
    rm -rf "$TEMP_DIR" /tmp/mongodb_backup.tar.gz
fi

# Restore Redis
if [ -n "$REDIS_BACKUP_URL" ]; then
    log "Downloading Redis backup..."
    wget -O /tmp/redis_backup.tar.gz "$REDIS_BACKUP_URL"
    
    log "Restoring Redis..."
    systemctl stop redis
    TEMP_DIR=$(mktemp -d)
    tar -xzf /tmp/redis_backup.tar.gz -C "$TEMP_DIR"
    cp "$TEMP_DIR"/dump_*.rdb /var/lib/redis/dump.rdb
    chown redis:redis /var/lib/redis/dump.rdb
    systemctl start redis
    rm -rf "$TEMP_DIR" /tmp/redis_backup.tar.gz
fi

# Phase 3: Application Recovery
log "Phase 3: Application recovery"

# Download and deploy application
if [ -n "$APPLICATION_REPO" ]; then
    log "Cloning application repository..."
    git clone "$APPLICATION_REPO" /opt/second_brain_database
    cd /opt/second_brain_database
    
    # Install dependencies
    pip3 install uv
    uv sync
fi

# Restore configuration
if [ -n "$CONFIG_BACKUP_URL" ]; then
    log "Downloading configuration backup..."
    wget -O /tmp/config_backup.tar.gz "$CONFIG_BACKUP_URL"
    
    log "Restoring configuration..."
    tar -xzf /tmp/config_backup.tar.gz -C /
    rm /tmp/config_backup.tar.gz
fi

# Phase 4: Service Startup
log "Phase 4: Starting services"
systemctl enable mongodb redis nginx sbd-api
systemctl start mongodb redis nginx sbd-api

# Phase 5: Verification
log "Phase 5: Verification"
sleep 30

# Test database connectivity
if mongosh --eval "db.adminCommand('ping')" > /dev/null; then
    log "MongoDB connectivity: OK"
else
    log "ERROR: MongoDB connectivity failed"
    exit 1
fi

if redis-cli ping > /dev/null; then
    log "Redis connectivity: OK"
else
    log "ERROR: Redis connectivity failed"
    exit 1
fi

# Test application health
if curl -f http://localhost:8000/health > /dev/null; then
    log "Application health: OK"
else
    log "ERROR: Application health check failed"
    exit 1
fi

log "Disaster recovery completed successfully"
```

#### Recovery Configuration Template

Create `/opt/config/recovery.conf`:

```bash
# Disaster Recovery Configuration

# Backup locations
MONGODB_BACKUP_URL="https://backups.yourdomain.com/mongodb/latest.tar.gz"
REDIS_BACKUP_URL="https://backups.yourdomain.com/redis/latest.tar.gz"
CONFIG_BACKUP_URL="https://backups.yourdomain.com/config/latest.tar.gz"

# Application source
APPLICATION_REPO="https://github.com/yourdomain/second_brain_database.git"
APPLICATION_BRANCH="main"

# Recovery settings
RECOVERY_LOG="/var/log/disaster_recovery.log"
NOTIFICATION_EMAIL="admin@yourdomain.com"

# Database settings
MONGODB_URI="mongodb://localhost:27017/second_brain_database"
REDIS_URI="redis://localhost:6379/0"

# Application settings
APP_PORT="8000"
APP_WORKERS="4"
```

## Backup Monitoring and Validation

### Backup Validation Script

Create `/opt/scripts/validate_backups.sh`:

```bash
#!/bin/bash

# Backup Validation Script

set -e

BACKUP_DIR="/opt/backups"
LOG_FILE="/var/log/backup/validation.log"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

validate_mongodb_backup() {
    local backup_file="$1"
    local temp_dir=$(mktemp -d)
    
    log "Validating MongoDB backup: $(basename "$backup_file")"
    
    # Extract backup
    if ! tar -xzf "$backup_file" -C "$temp_dir"; then
        log "ERROR: Failed to extract backup"
        return 1
    fi
    
    # Check for required collections
    local backup_db_dir=$(find "$temp_dir" -name "second_brain_database" -type d)
    if [ -z "$backup_db_dir" ]; then
        log "ERROR: Database directory not found in backup"
        rm -rf "$temp_dir"
        return 1
    fi
    
    # Check for essential collections
    local required_collections=("families" "users" "family_relationships")
    for collection in "${required_collections[@]}"; do
        if [ ! -f "$backup_db_dir/$collection.bson" ]; then
            log "ERROR: Missing collection: $collection"
            rm -rf "$temp_dir"
            return 1
        fi
    done
    
    log "MongoDB backup validation: PASSED"
    rm -rf "$temp_dir"
    return 0
}

validate_redis_backup() {
    local backup_file="$1"
    local temp_dir=$(mktemp -d)
    
    log "Validating Redis backup: $(basename "$backup_file")"
    
    # Extract backup
    if ! tar -xzf "$backup_file" -C "$temp_dir"; then
        log "ERROR: Failed to extract backup"
        return 1
    fi
    
    # Check for RDB file
    local rdb_file=$(find "$temp_dir" -name "dump_*.rdb")
    if [ -z "$rdb_file" ]; then
        log "ERROR: RDB file not found in backup"
        rm -rf "$temp_dir"
        return 1
    fi
    
    # Validate RDB file format (basic check)
    if ! file "$rdb_file" | grep -q "Redis"; then
        log "WARNING: RDB file format validation failed"
    fi
    
    log "Redis backup validation: PASSED"
    rm -rf "$temp_dir"
    return 0
}

# Main validation loop
log "Starting backup validation"

# Validate latest MongoDB backup
LATEST_MONGODB=$(find "$BACKUP_DIR/mongodb" -name "mongodb_backup_*.tar.gz" -type f -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2-)
if [ -n "$LATEST_MONGODB" ]; then
    validate_mongodb_backup "$LATEST_MONGODB"
else
    log "ERROR: No MongoDB backups found"
fi

# Validate latest Redis backup
LATEST_REDIS=$(find "$BACKUP_DIR/redis" -name "redis_backup_*.tar.gz" -type f -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2-)
if [ -n "$LATEST_REDIS" ]; then
    validate_redis_backup "$LATEST_REDIS"
else
    log "ERROR: No Redis backups found"
fi

log "Backup validation completed"
```

### Backup Monitoring Dashboard

Create monitoring queries for backup status:

```yaml
# Prometheus rules for backup monitoring
groups:
  - name: backup_monitoring
    rules:
      - alert: BackupFailed
        expr: time() - backup_last_success_timestamp > 86400
        for: 1h
        labels:
          severity: critical
        annotations:
          summary: "Backup has not completed successfully in 24 hours"
          
      - alert: BackupValidationFailed
        expr: backup_validation_success == 0
        for: 0m
        labels:
          severity: critical
        annotations:
          summary: "Backup validation failed"
          
      - alert: BackupSizeAnomaly
        expr: abs(backup_size_bytes - backup_size_bytes offset 1d) / backup_size_bytes > 0.5
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "Backup size changed significantly"
```

## Cron Job Configuration

Add backup jobs to crontab:

```bash
# Edit crontab
sudo crontab -e

# Add backup jobs
# Daily full MongoDB backup at 2:00 AM
0 2 * * * /opt/scripts/backup_mongodb.sh

# Incremental MongoDB backup every 4 hours
0 */4 * * * /opt/scripts/backup_mongodb_incremental.sh

# Daily Redis backup at 2:30 AM
30 2 * * * /opt/scripts/backup_redis.sh

# Weekly configuration backup on Sundays at 3:00 AM
0 3 * * 0 /opt/scripts/backup_config.sh

# Daily backup validation at 6:00 AM
0 6 * * * /opt/scripts/validate_backups.sh

# Weekly full system backup on Saturdays at 1:00 AM
0 1 * * 6 /opt/scripts/backup_full_system.sh
```

## Business Continuity Planning

### Communication Plan

1. **Internal Communication**
   - Incident commander designation
   - Team notification procedures
   - Status update intervals
   - Escalation matrix

2. **External Communication**
   - Customer notification templates
   - Status page updates
   - Media response procedures
   - Regulatory notifications

### Recovery Priorities

1. **Critical Systems** (RTO: 1 hour)
   - Authentication services
   - Core API functionality
   - Database services

2. **Important Systems** (RTO: 4 hours)
   - Family management features
   - Notification services
   - Monitoring systems

3. **Standard Systems** (RTO: 24 hours)
   - Reporting features
   - Analytics systems
   - Administrative tools

### Testing and Maintenance

#### Monthly Backup Tests
- Restore test database from backup
- Verify data integrity
- Test recovery procedures
- Update documentation

#### Quarterly DR Drills
- Full disaster recovery simulation
- Team training exercises
- Procedure validation
- Performance measurement

#### Annual DR Review
- Update recovery procedures
- Review and update RTOs/RPOs
- Capacity planning review
- Vendor contract review

This comprehensive backup and recovery documentation ensures data protection and business continuity for the Family Management System.
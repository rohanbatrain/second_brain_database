# IPAM Background Tasks Documentation

## Overview

This document describes the background tasks implemented for the IPAM (IP Address Management) system. These tasks run periodically to monitor capacity, clean up expired reservations, and send notifications to users.

## Background Tasks

### 1. Capacity Monitoring Task

**File**: `src/second_brain_database/routes/ipam/periodics/capacity_monitoring.py`

**Function**: `periodic_ipam_capacity_monitoring()`

**Purpose**: Monitors IPAM capacity thresholds and sends notifications when limits are approached or exceeded.

**Interval**: Configurable via `IPAM_CAPACITY_MONITORING_INTERVAL` (default: 900 seconds / 15 minutes)

**Features**:
- Monitors country-level utilization for all users with active allocations
- Monitors region-level utilization for all active regions
- Sends email notifications at configurable thresholds:
  - Warning threshold (default: 80%)
  - Critical threshold (default: 100%)
  - Region threshold (default: 90%)
- Supports per-country and per-region threshold overrides
- Logs all capacity events to `ipam_capacity_events` collection
- Prevents duplicate notifications using in-memory tracking

**Requirements Satisfied**: 19.1, 19.2, 19.3, 19.4, 19.5

### 2. Reservation Cleanup Task

**File**: `src/second_brain_database/routes/ipam/periodics/reservation_cleanup.py`

**Function**: `periodic_ipam_reservation_cleanup()`

**Purpose**: Automatically cleans up expired IPAM reservations and notifies owners.

**Interval**: Configurable via `IPAM_RESERVATION_CLEANUP_INTERVAL` (default: 3600 seconds / 1 hour)

**Features**:
- Queries expired region and host reservations
- Updates status from "Reserved" to "Available"
- Removes expiration timestamp
- Sends email notification to reservation owner
- Logs audit trail to `ipam_audit_history` collection
- Handles both region and host reservations

**Requirements Satisfied**: 17.4

## Configuration

### Settings (config.py)

All IPAM background task settings are configurable via environment variables or the `.sbd` configuration file:

#### Rate Limiting
```python
IPAM_REGION_CREATE_RATE_LIMIT: int = 100  # Max regions per hour per user
IPAM_HOST_CREATE_RATE_LIMIT: int = 1000  # Max hosts per hour per user
IPAM_QUERY_RATE_LIMIT: int = 500  # Max queries per hour per user
```

#### Audit and Retention
```python
IPAM_AUDIT_RETENTION_DAYS: int = 365  # Days to keep audit history
```

#### Quotas
```python
IPAM_DEFAULT_REGION_QUOTA: int = 1000  # Default max regions per user
IPAM_DEFAULT_HOST_QUOTA: int = 10000  # Default max hosts per user
```

#### Capacity Thresholds
```python
IPAM_CAPACITY_WARNING_THRESHOLD: int = 80  # Warning at 80% utilization
IPAM_CAPACITY_CRITICAL_THRESHOLD: int = 100  # Critical at 100% utilization
IPAM_REGION_CAPACITY_THRESHOLD: int = 90  # Region warning at 90% utilization
```

#### Notification Configuration
```python
IPAM_NOTIFICATION_ENABLED: bool = True  # Enable/disable notifications
IPAM_NOTIFICATION_CHANNELS: str = "email"  # Comma-separated: email,webhook,in-app
IPAM_NOTIFICATION_EMAIL_ENABLED: bool = True  # Enable email notifications
IPAM_NOTIFICATION_WEBHOOK_ENABLED: bool = False  # Enable webhook notifications
IPAM_NOTIFICATION_WEBHOOK_URL: Optional[str] = None  # Webhook URL
IPAM_NOTIFICATION_IN_APP_ENABLED: bool = False  # Enable in-app notifications
```

#### Per-Country Threshold Overrides
```python
# JSON format: {"India": {"warning": 70, "critical": 90}, "United States": {"warning": 85, "critical": 95}}
IPAM_COUNTRY_THRESHOLDS: Optional[str] = None
```

#### Per-Region Threshold Overrides
```python
# JSON format: {"region_id_1": 85, "region_id_2": 95}
IPAM_REGION_THRESHOLDS: Optional[str] = None
```

#### Background Task Intervals
```python
IPAM_CAPACITY_MONITORING_INTERVAL: int = 900  # 15 minutes in seconds
IPAM_RESERVATION_CLEANUP_INTERVAL: int = 3600  # 1 hour in seconds
```

### Example Configuration

**.sbd file**:
```bash
# IPAM Capacity Monitoring
IPAM_CAPACITY_WARNING_THRESHOLD=75
IPAM_CAPACITY_CRITICAL_THRESHOLD=95
IPAM_REGION_CAPACITY_THRESHOLD=85

# IPAM Notifications
IPAM_NOTIFICATION_ENABLED=true
IPAM_NOTIFICATION_CHANNELS=email,webhook
IPAM_NOTIFICATION_WEBHOOK_URL=https://hooks.example.com/ipam-alerts

# Per-country thresholds (JSON)
IPAM_COUNTRY_THRESHOLDS='{"India": {"warning": 70, "critical": 90}, "United States": {"warning": 85, "critical": 95}}'

# Per-region thresholds (JSON)
IPAM_REGION_THRESHOLDS='{"507f1f77bcf86cd799439011": 85, "507f1f77bcf86cd799439012": 95}'

# Task intervals
IPAM_CAPACITY_MONITORING_INTERVAL=600  # 10 minutes
IPAM_RESERVATION_CLEANUP_INTERVAL=1800  # 30 minutes
```

## Email Notifications

### Capacity Warning Email

**Subject**: `WARNING: IPAM Capacity Alert for {country}`

**Content**:
- User greeting
- Country name
- Current utilization percentage
- Allocated vs. total capacity
- Threshold type (WARNING)
- Link to view allocations

### Capacity Critical Email

**Subject**: `CRITICAL: IPAM Capacity Exhausted for {country}`

**Content**:
- User greeting
- Country name
- Current utilization percentage
- Allocated vs. total capacity
- Threshold type (CRITICAL)
- Warning that no more regions can be allocated
- Link to view allocations

### Region Capacity Email

**Subject**: `IPAM Region Capacity Alert: {region_name}`

**Content**:
- User greeting
- Region name and CIDR
- Current utilization percentage
- Allocated hosts vs. total capacity
- Suggestion to plan for additional regions
- Link to view region

### Reservation Expiration Email

**Subject**: `IPAM Reservation Expired: {resource_name}`

**Content**:
- User greeting
- Resource type (region or host)
- Resource name
- IP address or CIDR
- Notification that status changed to "Available"
- Suggestion to create new reservation or allocate permanently
- Link to view IPAM allocations

## Database Collections

### ipam_capacity_events

Stores capacity threshold events for audit and analytics.

**Schema**:
```python
{
    "user_id": str,
    "resource_type": str,  # "country" or "region"
    "resource_identifier": str,  # Country name or region ID
    "utilization_percentage": float,
    "threshold_type": str,  # "warning" or "critical"
    "capacity_stats": dict,  # Full utilization statistics
    "timestamp": datetime
}
```

### ipam_audit_history

Stores audit trail for all IPAM operations including reservation expirations.

**Schema** (for reservation expiration):
```python
{
    "user_id": str,
    "action_type": "reservation_expired",
    "resource_type": str,  # "region" or "host"
    "resource_id": str,
    "ip_address": str,  # For hosts
    "cidr": str,  # For regions
    "snapshot": {
        "resource_name": str,
        "status": "Reserved",
        "expired_at": datetime,
        "cleaned_up_at": datetime
    },
    "reason": "Reservation expired automatically",
    "timestamp": datetime,
    "metadata": {
        "automated": true,
        "cleanup_task": "periodic_ipam_reservation_cleanup"
    }
}
```

## Integration with Main Application

The background tasks are registered in `main.py` during application startup:

```python
from second_brain_database.routes.ipam.periodics.capacity_monitoring import periodic_ipam_capacity_monitoring
from second_brain_database.routes.ipam.periodics.reservation_cleanup import periodic_ipam_reservation_cleanup

# In lifespan function
background_tasks.update({
    # ... other tasks ...
    "ipam_capacity_monitoring": asyncio.create_task(periodic_ipam_capacity_monitoring()),
    "ipam_reservation_cleanup": asyncio.create_task(periodic_ipam_reservation_cleanup()),
})
```

Tasks are automatically:
- Started during application startup
- Cancelled during application shutdown
- Logged with comprehensive lifecycle events
- Monitored for errors with automatic retry

## Monitoring and Logging

All background tasks use structured logging with the following prefixes:
- `[IPAMCapacityMonitoring]` - Capacity monitoring task
- `[IPAMReservationCleanup]` - Reservation cleanup task

**Log Levels**:
- `INFO`: Task start/stop, summary statistics
- `DEBUG`: Detailed operation logs
- `WARNING`: Non-critical errors (e.g., user email not found)
- `ERROR`: Critical errors with full traceback

**Metrics Logged**:
- Task execution duration
- Number of users monitored
- Number of notifications sent
- Number of reservations cleaned up
- Number of errors encountered

## Error Handling

Both tasks implement robust error handling:

1. **Per-user error isolation**: Errors for one user don't affect others
2. **Automatic retry**: Tasks continue running even after errors
3. **Graceful degradation**: Missing user emails or other issues are logged but don't stop the task
4. **Cancellation support**: Tasks respond to cancellation signals during shutdown

## Future Enhancements

Potential future improvements:

1. **Webhook notifications**: Support for webhook-based alerts
2. **In-app notifications**: Real-time notifications in the UI
3. **Slack/Teams integration**: Send alerts to team channels
4. **Custom notification templates**: User-configurable email templates
5. **Notification preferences**: Per-user notification settings
6. **Capacity forecasting**: Predict when capacity will be exhausted
7. **Auto-scaling**: Automatically request additional capacity
8. **Dashboard integration**: Real-time capacity monitoring UI

## Testing

To test the background tasks:

1. **Manual trigger**: Create a test script to call the task functions directly
2. **Mock data**: Create test allocations with high utilization
3. **Time manipulation**: Use mock datetime to test expiration logic
4. **Email verification**: Check console output for development email logs
5. **Database verification**: Query collections to verify audit trails

Example test script:
```python
import asyncio
from second_brain_database.routes.ipam.periodics.capacity_monitoring import periodic_ipam_capacity_monitoring

async def test_capacity_monitoring():
    # Run one iteration
    task = asyncio.create_task(periodic_ipam_capacity_monitoring())
    await asyncio.sleep(5)  # Let it run for 5 seconds
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        print("Task cancelled successfully")

asyncio.run(test_capacity_monitoring())
```

## Troubleshooting

### Task not running

1. Check application logs for startup errors
2. Verify task is registered in `main.py`
3. Check for import errors in periodic modules

### Notifications not sent

1. Verify `IPAM_NOTIFICATION_ENABLED=true`
2. Check email manager configuration
3. Verify user has valid email address
4. Check notification tracking (may be suppressed to avoid spam)

### High memory usage

1. Reduce monitoring interval
2. Clear notification tracking sets periodically
3. Limit number of users processed per iteration

### Database performance

1. Ensure indexes are created (see `ipam_indexes.py`)
2. Monitor query performance in logs
3. Consider adding pagination for large user sets

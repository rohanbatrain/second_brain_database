# IPAM Manager Logging Enhancements

## Overview

This document describes the comprehensive structured logging enhancements made to the IPAM Manager to improve observability, performance tracking, and operational monitoring.

## Logging Enhancements Summary

### 1. Quota Management Logging

**Enhanced Methods:**
- `check_user_quota()`
- `get_user_quota()`
- `update_quota_counter()`

**Improvements:**
- **Quota Check Events**: Log every quota check with detailed context including current usage, limit, available capacity, and usage percentage
- **Quota Warning Events**: Log WARNING level when usage exceeds 80% threshold
- **Quota Exceeded Events**: Log ERROR level with full context when quota is exceeded
- **Format**: `user=%s resource=%s current=%d limit=%d available=%d usage=%.1f%%`

**Example Logs:**
```
INFO: Quota check: user=user123 resource=region current=750 limit=1000 available=250 usage=75.0%
WARNING: Quota warning: user=user123 resource=region current=850 limit=1000 usage=85.0% threshold=80%
WARNING: Quota exceeded: user=user123 resource=host current=10000 limit=10000 usage=100.0% - allocation denied
```

### 2. Cache Operations Logging

**Enhanced Methods:**
- `get_country_mapping()`
- `get_country_by_x_octet()`
- `get_user_quota()`
- `find_next_xy()`

**Improvements:**
- **Cache Hit Tracking**: Log DEBUG level for successful cache retrievals with operation name and key
- **Cache Miss Tracking**: Log DEBUG level when cache lookup fails, triggering database query
- **Cache Error Tracking**: Log WARNING level for cache operation failures
- **Performance Metrics**: Include cache key and relevant identifiers for correlation

**Example Logs:**
```
DEBUG: Cache hit: operation=get_country_mapping key=ipam:country_mapping:India country=India
DEBUG: Cache miss: operation=get_user_quota key=ipam:user_quota:user123 user_id=user123
WARNING: Cache error: operation=get_country_by_x_octet key=ipam:x_octet_mapping:5 error=Connection timeout
DEBUG: Cache hit: operation=find_next_xy key=ipam:allocated_y:user123:5 user_id=user123 x_octet=5 allocated_count=45
```

### 3. Auto-Allocation Algorithm Logging

**Enhanced Methods:**
- `find_next_xy()`
- `find_next_z()`

**Improvements:**
- **Capacity Warnings**: Log WARNING when utilization exceeds 80% for regions or 90% for hosts
- **Allocation Success**: Log INFO with comprehensive context including allocated values, utilization, and duration
- **Capacity Exhaustion**: Log ERROR with full capacity details when no addresses available
- **Performance Tracking**: Include duration_ms for all operations

**Example Logs:**
```
WARNING: Capacity warning: user=user123 country=India x_octet=5 allocated=220 capacity=256 utilization=85.9%
INFO: Auto-allocation success: operation=find_next_xy user=user123 country=India x=5 y=45 allocated=220 capacity=256 utilization=85.9% duration_ms=12.5
ERROR: Capacity exhausted: operation=find_next_z user=user123 region=abc123 allocated=254 capacity=254 utilization=100.0% duration_ms=8.3
WARNING: Capacity warning: user=user123 region=abc123 allocated=230 capacity=254 utilization=90.6%
INFO: Auto-allocation success: operation=find_next_z user=user123 region=abc123 z=231 allocated=230 capacity=254 utilization=90.6% duration_ms=5.2
```

### 4. Concurrent Conflict and Retry Logging

**Enhanced Methods:**
- `allocate_region()`
- `allocate_host()`

**Improvements:**
- **Retry Attempts**: Log WARNING for each retry attempt with backoff timing
- **Max Retries Exceeded**: Log ERROR when all retry attempts exhausted
- **Conflict Context**: Include full allocation context (user, country/region, X.Y.Z values)
- **Backoff Tracking**: Log backoff duration in milliseconds

**Example Logs:**
```
WARNING: Concurrent conflict: operation=allocate_region user=user123 country=India x=5 y=45 attempt=1/3 backoff_ms=100.0 - retrying
WARNING: Concurrent conflict: operation=allocate_host user=user123 region=abc123 x=5 y=45 z=100 attempt=2/3 backoff_ms=200.0 - retrying
ERROR: Concurrent conflict: operation=allocate_region user=user123 country=India x=5 y=45 attempt=3/3 - max retries exceeded
```

### 5. Allocation Success Logging

**Enhanced Methods:**
- `allocate_region()`
- `allocate_host()`
- `allocate_hosts_batch()`

**Improvements:**
- **Comprehensive Context**: Log all relevant identifiers (user, country, region, IP, CIDR)
- **Quota Tracking**: Include current quota usage after allocation
- **Performance Metrics**: Duration in milliseconds
- **Result Status**: Explicit success/partial/failure indicators

**Example Logs:**
```
INFO: Allocation success: operation=allocate_region user=user123 country=India region=Mumbai-DC1 cidr=10.5.45.0/24 x=5 y=45 quota_used=751/1000 duration_ms=125.3 result=success
INFO: Allocation success: operation=allocate_host user=user123 region=abc123 hostname=web-01 ip=10.5.45.100 x=5 y=45 z=100 quota_used=5001/10000 duration_ms=45.7 result=success
INFO: Batch allocation success: operation=allocate_hosts_batch user=user123 region=abc123 prefix=web-server requested=50 allocated=50 failed=0 duration_ms=1250.5 result=success
WARNING: Batch allocation partial: operation=allocate_hosts_batch user=user123 region=abc123 prefix=web-server requested=50 allocated=45 failed=5 duration_ms=1180.2 result=partial
```

### 6. Update Operations Logging

**Enhanced Methods:**
- `update_region()`
- `update_host()`

**Improvements:**
- **Field-Level Changes**: Log which fields were modified
- **Change Count**: Number of fields updated
- **Performance Tracking**: Duration in milliseconds
- **Result Status**: Explicit success indicator

**Example Logs:**
```
INFO: Update success: operation=update_region user=user123 region=abc123 changes=3 fields=region_name,description,status duration_ms=35.2 result=success
INFO: Update success: operation=update_host user=user123 host=xyz789 changes=2 fields=hostname,device_type duration_ms=28.7 result=success
```

## Log Level Guidelines

### INFO Level
- Successful allocation operations
- Successful update operations
- Quota checks (normal usage)
- Auto-allocation success with metrics

### WARNING Level
- Capacity approaching thresholds (80% regions, 90% hosts)
- Quota usage exceeding 80% threshold
- Concurrent conflicts with retry attempts
- Partial batch allocation failures
- Cache operation failures

### ERROR Level
- Capacity exhausted (100% utilization)
- Quota exceeded (allocation denied)
- Max retry attempts exceeded
- Operation failures with exceptions

### DEBUG Level
- Cache hits and misses
- Detailed operation flow
- Internal state transitions

## Structured Logging Format

All enhanced logs follow a consistent structured format:

```
LEVEL: Category: key1=value1 key2=value2 ... - optional_message
```

**Key Components:**
- **operation**: Name of the operation (e.g., allocate_region, find_next_xy)
- **user**: User ID for isolation tracking
- **country/region/host**: Resource identifiers
- **x/y/z**: IP octet values
- **allocated/capacity**: Current usage and limits
- **utilization**: Percentage utilization
- **duration_ms**: Operation duration in milliseconds
- **result**: Operation outcome (success/partial/failure)
- **attempt**: Retry attempt number (for conflicts)
- **quota_used**: Current quota usage after operation

## Performance Monitoring

All operations now include duration tracking in milliseconds:
- Auto-allocation algorithms: `duration_ms=X.X`
- Database operations: Tracked via db_manager.log_query_*
- Cache operations: Implicit in cache hit/miss patterns
- Full allocation flows: End-to-end timing

## Observability Benefits

1. **Capacity Planning**: Track utilization trends and identify when to expand capacity
2. **Performance Analysis**: Identify slow operations and optimization opportunities
3. **Quota Management**: Monitor user quota consumption and predict exhaustion
4. **Concurrency Debugging**: Track concurrent conflicts and retry patterns
5. **Cache Effectiveness**: Measure cache hit rates and identify cache issues
6. **Operational Monitoring**: Real-time visibility into allocation patterns and failures

## Integration with Existing Infrastructure

The enhanced logging integrates seamlessly with:
- **logging_manager**: Uses centralized logger with `[IPAMManager]` prefix
- **db_manager**: Leverages existing query logging infrastructure
- **redis_manager**: Cache operations tracked independently
- **error_handling**: Exception context preserved in error logs
- **FastAPI instrumentation**: Automatic request/response metrics (see task 11.2)

## Next Steps

Task 11.2 will verify that IPAM endpoints are captured by the existing FastAPI instrumentation in main.py for automatic request/response metrics, ensuring comprehensive observability without manual Prometheus metric creation.

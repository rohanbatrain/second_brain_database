# IPAM Metrics Monitoring Guide

## Overview

The IPAM backend includes comprehensive metrics tracking for monitoring system performance, errors, and usage patterns. Metrics are stored in Redis for real-time access and can be queried via API endpoints.

## Metrics Tracked

### 1. Error Rates
- Error counts by type (capacity_exhausted, quota_exceeded, validation_error, etc.)
- Errors per endpoint
- Errors per user
- Errors per minute (rate calculation)
- Total error count

### 2. Request Rates
- Total request count
- Requests per minute
- Requests per endpoint
- Requests per user

### 3. Response Times
- Global average response time
- Per-endpoint average response time
- Response time tracking for performance monitoring

### 4. Capacity Warnings
- Capacity warnings by resource type (country, region, host)
- Total capacity warnings
- Utilization tracking

### 5. Quota Exceeded Events
- Quota exceeded counts by type (region, host)
- Per-user quota tracking
- Total quota exceeded events

### 6. Operation Success/Failure
- Success and failure counts per operation type
- Success rate calculation
- Operation tracking (allocate_region, allocate_host, retire_region, release_host)

### 7. Allocation Rates
- Allocations per minute by resource type
- Total allocation counts
- Allocation rate trends

## API Endpoints

### Get Comprehensive Metrics
```bash
GET /ipam/metrics
```

Returns all metrics in a single response:
```json
{
  "timestamp": "2025-11-13T16:58:26Z",
  "requests": {
    "requests_per_minute": 45.0,
    "average_response_time": 0.125
  },
  "errors": {
    "capacity_exhausted": 5,
    "quota_exceeded": 12,
    "total": 17,
    "errors_per_minute": 0.5
  },
  "capacity_warnings": {
    "country": 3,
    "region": 8,
    "total": 11
  },
  "quota_exceeded": {
    "region": 5,
    "host": 7,
    "total": 12
  },
  "operations": {
    "allocate_region": {
      "success_count": 150,
      "failure_count": 5,
      "total_count": 155,
      "success_rate": 96.8
    }
  },
  "allocation_rates": {
    "regions_per_minute": 2.5,
    "hosts_per_minute": 15.3
  }
}
```

### Get Error Rates
```bash
GET /ipam/metrics/errors
```

Returns detailed error information:
```json
{
  "capacity_exhausted": 5,
  "quota_exceeded": 12,
  "validation_error": 3,
  "total": 20,
  "errors_per_minute": 0.5
}
```

### Get Endpoint-Specific Metrics
```bash
GET /ipam/metrics/endpoint/{endpoint_path}
```

Example:
```bash
GET /ipam/metrics/endpoint/ipam/regions
```

Returns:
```json
{
  "endpoint": "/ipam/regions",
  "errors": {
    "capacity_exhausted": 3,
    "validation_error": 1
  },
  "average_response_time": 0.145
}
```

## Verification Script

A verification script is provided to test the metrics system:

```bash
python scripts/verify_ipam_metrics.py
```

This script verifies:
- Redis connection
- Metrics tracker initialization
- Metrics tracking functionality
- Metrics retrieval
- Metrics summary generation
- Performance requirements
- Cleanup operations

## Metrics Storage

Metrics are stored in Redis with the following key patterns:

- `ipam:metrics:errors:{type}` - Error counts by type
- `ipam:metrics:errors:endpoint:{endpoint}:{type}` - Errors per endpoint
- `ipam:metrics:errors:user:{user_id}` - Errors per user
- `ipam:metrics:errors:minute:{minute}` - Errors per minute
- `ipam:metrics:requests:total` - Total requests
- `ipam:metrics:requests:minute:{minute}` - Requests per minute
- `ipam:metrics:requests:endpoint:{endpoint}` - Requests per endpoint
- `ipam:metrics:response_time:global` - Global response time stats
- `ipam:metrics:response_time:endpoint:{endpoint}` - Per-endpoint response times
- `ipam:metrics:capacity_warnings:{type}` - Capacity warnings
- `ipam:metrics:quota_exceeded:{type}` - Quota exceeded events
- `ipam:metrics:operations:{type}:success` - Successful operations
- `ipam:metrics:operations:{type}:failure` - Failed operations
- `ipam:metrics:allocations:{type}:minute:{minute}` - Allocations per minute

## Metrics TTL

- Most metrics: 1 hour (3600 seconds)
- Per-minute metrics: 2 minutes (120 seconds)
- Total counters: No expiration

## Performance Considerations

- Metrics tracking is designed to be non-blocking and fast (< 10ms per operation)
- Metrics retrieval is optimized for quick access (< 100ms)
- Redis is used for real-time metrics storage
- Metrics are automatically cleaned up based on TTL

## Monitoring Best Practices

1. **Set up alerts** for:
   - High error rates (> 1% of requests)
   - Slow response times (> 500ms for dashboard, > 1s for forecast)
   - Capacity warnings
   - Quota exceeded events

2. **Regular monitoring**:
   - Check metrics dashboard daily
   - Review error trends weekly
   - Analyze capacity utilization monthly

3. **Performance tracking**:
   - Monitor average response times
   - Track requests per minute
   - Identify slow endpoints

4. **Capacity planning**:
   - Review capacity warnings
   - Track allocation rates
   - Plan for resource expansion

## Integration with Monitoring Tools

The metrics can be integrated with external monitoring tools:

- **Prometheus**: Metrics can be exported in Prometheus format
- **Grafana**: Create dashboards using the metrics API
- **DataDog/New Relic**: Custom integrations via API
- **CloudWatch**: Export metrics to AWS CloudWatch

## Troubleshooting

### Metrics not updating
- Check Redis connection
- Verify metrics tracker is initialized
- Check for errors in application logs

### High memory usage in Redis
- Review metrics TTL settings
- Check for metrics key accumulation
- Consider increasing cleanup frequency

### Slow metrics retrieval
- Check Redis performance
- Review query patterns
- Consider caching frequently accessed metrics

## Configuration

Metrics can be configured via environment variables:

```bash
# Redis connection
REDIS_URL=redis://localhost:6379/0

# Metrics TTL (optional, default: 3600 seconds)
IPAM_METRICS_TTL=3600
```

## Security

- Metrics endpoints require authentication
- Rate limiting: 100 requests per hour per user
- Required permission: `ipam:read`
- Sensitive data is excluded from metrics

## Support

For issues or questions about metrics monitoring:
- Check application logs for errors
- Run verification script: `python scripts/verify_ipam_metrics.py`
- Review Redis health and connectivity
- Contact system administrators for assistance

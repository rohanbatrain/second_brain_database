# Rate Limiting Policies and Best Practices

## Overview

The Family Management API implements comprehensive rate limiting to ensure fair usage, prevent abuse, and maintain system stability. This document outlines the rate limiting policies, implementation details, and best practices for handling rate limits in your applications.

## Rate Limiting Strategy

### Multi-Tier Rate Limiting

The API uses a multi-tier approach with different limits for different types of operations:

1. **Global Rate Limits**: Overall API usage per user
2. **Operation-Specific Limits**: Tailored limits for specific endpoints
3. **Security-Sensitive Limits**: Stricter limits for sensitive operations
4. **IP-Based Limits**: Limits for unauthenticated endpoints

### Rate Limiting Algorithms

- **Token Bucket**: For burst traffic handling
- **Sliding Window**: For precise rate calculations
- **Fixed Window**: For simple daily/hourly limits

## Rate Limit Policies

### Authentication Operations

| Operation | Limit | Window | Notes |
|-----------|-------|---------|-------|
| Login Attempts | 10 | 15 minutes | Per IP address |
| Password Reset | 5 | 1 hour | Per email address |
| 2FA Verification | 10 | 15 minutes | Per user |
| Token Refresh | 20 | 1 hour | Per user |
| WebAuthn Registration | 5 | 1 hour | Per user |
| WebAuthn Authentication | 15 | 15 minutes | Per user |

### Family Management Operations

| Operation | Limit | Window | Notes |
|-----------|-------|---------|-------|
| Create Family | 5 | 1 hour | Per user |
| List Families | 20 | 1 hour | Per user |
| Invite Member | 10 | 1 hour | Per user |
| Respond to Invitation | 20 | 1 hour | Per user |
| Resend Invitation | 5 | 1 hour | Per user |
| Cancel Invitation | 10 | 1 hour | Per user |

### SBD Account Operations

| Operation | Limit | Window | Notes |
|-----------|-------|---------|-------|
| Get Account Info | 30 | 1 hour | Per user |
| Update Permissions | 10 | 1 hour | Admin only |
| Freeze/Unfreeze Account | 5 | 1 hour | Admin only, requires 2FA |
| Validate Spending | 100 | 1 hour | Per user |
| Transaction History | 20 | 1 hour | Per user |

### Token Request Operations

| Operation | Limit | Window | Notes |
|-----------|-------|---------|-------|
| Create Token Request | 10 | 24 hours | Per user |
| Review Token Request | 20 | 1 hour | Admin only |
| List Token Requests | 20 | 1 hour | Per user |

### Notification Operations

| Operation | Limit | Window | Notes |
|-----------|-------|---------|-------|
| Get Notifications | 30 | 1 hour | Per user |
| Mark as Read | 50 | 1 hour | Per user |
| Update Preferences | 5 | 1 hour | Per user |

### Administrative Operations

| Operation | Limit | Window | Notes |
|-----------|-------|---------|-------|
| Health Checks | 60 | 1 hour | Per user |
| System Metrics | 10 | 1 hour | Admin only |
| Audit Logs | 5 | 1 hour | Admin only |
| Cleanup Operations | 2 | 1 hour | Admin only |

### Unauthenticated Operations

| Operation | Limit | Window | Notes |
|-----------|-------|---------|-------|
| Accept Invitation (Token) | 10 | 1 hour | Per IP address |
| Decline Invitation (Token) | 10 | 1 hour | Per IP address |
| Public Health Check | 20 | 1 hour | Per IP address |

## Rate Limit Headers

All API responses include rate limiting information in headers:

```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640995200
X-RateLimit-Window: 3600
X-RateLimit-Type: user
X-RateLimit-Retry-After: 3600
```

### Header Descriptions

- **X-RateLimit-Limit**: Maximum requests allowed in the window
- **X-RateLimit-Remaining**: Requests remaining in current window
- **X-RateLimit-Reset**: Unix timestamp when the window resets
- **X-RateLimit-Window**: Window duration in seconds
- **X-RateLimit-Type**: Type of rate limit (user, ip, operation)
- **X-RateLimit-Retry-After**: Seconds until next request allowed (when rate limited)

## Rate Limit Responses

### Rate Limit Exceeded (429)

When rate limits are exceeded, the API returns:

```json
{
  "error": "RATE_LIMIT_EXCEEDED",
  "message": "Too many requests. Please try again later.",
  "details": {
    "limit": 10,
    "window": 3600,
    "reset_at": "2024-01-01T13:00:00Z",
    "limit_type": "family_create"
  },
  "retry_after": 3600
}
```

### Rate Limit Warning (200 with headers)

When approaching rate limits:

```http
HTTP/1.1 200 OK
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 5
X-RateLimit-Warning: true
X-RateLimit-Warning-Threshold: 10
```

## Client Implementation Best Practices

### 1. Respect Rate Limit Headers

```javascript
class RateLimitAwareClient {
  constructor(baseUrl) {
    this.baseUrl = baseUrl;
    this.rateLimitInfo = new Map();
  }
  
  async makeRequest(endpoint, options = {}) {
    // Check if we're rate limited
    const rateLimitKey = this.getRateLimitKey(endpoint, options);
    const rateLimitInfo = this.rateLimitInfo.get(rateLimitKey);
    
    if (rateLimitInfo && rateLimitInfo.remaining <= 0) {
      const waitTime = rateLimitInfo.resetTime - Date.now();
      if (waitTime > 0) {
        console.log(`Rate limited. Waiting ${waitTime}ms`);
        await this.sleep(waitTime);
      }
    }
    
    const response = await fetch(`${this.baseUrl}${endpoint}`, options);
    
    // Update rate limit info from headers
    this.updateRateLimitInfo(rateLimitKey, response.headers);
    
    if (response.status === 429) {
      const retryAfter = response.headers.get('X-RateLimit-Retry-After');
      throw new RateLimitError(`Rate limited. Retry after ${retryAfter}s`, retryAfter);
    }
    
    return response;
  }
  
  updateRateLimitInfo(key, headers) {
    const limit = parseInt(headers.get('X-RateLimit-Limit'));
    const remaining = parseInt(headers.get('X-RateLimit-Remaining'));
    const reset = parseInt(headers.get('X-RateLimit-Reset'));
    
    if (limit && remaining !== null && reset) {
      this.rateLimitInfo.set(key, {
        limit,
        remaining,
        resetTime: reset * 1000 // Convert to milliseconds
      });
    }
  }
  
  getRateLimitKey(endpoint, options) {
    // Create a key based on endpoint and method
    const method = options.method || 'GET';
    return `${method}:${endpoint}`;
  }
  
  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}
```

### 2. Implement Exponential Backoff

```javascript
class ExponentialBackoffClient {
  async makeRequestWithBackoff(url, options, maxRetries = 3) {
    let attempt = 1;
    let baseDelay = 1000; // 1 second
    
    while (attempt <= maxRetries) {
      try {
        const response = await fetch(url, options);
        
        if (response.status === 429) {
          if (attempt === maxRetries) {
            throw new Error('Max retries exceeded');
          }
          
          // Get retry-after from header or calculate exponential backoff
          const retryAfter = response.headers.get('X-RateLimit-Retry-After');
          const delay = retryAfter ? 
            parseInt(retryAfter) * 1000 : 
            baseDelay * Math.pow(2, attempt - 1);
          
          // Add jitter to prevent thundering herd
          const jitter = Math.random() * 1000;
          const totalDelay = delay + jitter;
          
          console.log(`Rate limited. Retrying in ${totalDelay}ms (attempt ${attempt})`);
          await this.sleep(totalDelay);
          
          attempt++;
          continue;
        }
        
        return response;
      } catch (error) {
        if (attempt === maxRetries) {
          throw error;
        }
        
        const delay = baseDelay * Math.pow(2, attempt - 1);
        await this.sleep(delay);
        attempt++;
      }
    }
  }
  
  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}
```

### 3. Request Queuing and Throttling

```javascript
class RequestQueue {
  constructor(maxConcurrent = 5, minInterval = 100) {
    this.maxConcurrent = maxConcurrent;
    this.minInterval = minInterval;
    this.queue = [];
    this.active = 0;
    this.lastRequestTime = 0;
  }
  
  async enqueue(requestFn) {
    return new Promise((resolve, reject) => {
      this.queue.push({ requestFn, resolve, reject });
      this.processQueue();
    });
  }
  
  async processQueue() {
    if (this.active >= this.maxConcurrent || this.queue.length === 0) {
      return;
    }
    
    const { requestFn, resolve, reject } = this.queue.shift();
    this.active++;
    
    try {
      // Ensure minimum interval between requests
      const now = Date.now();
      const timeSinceLastRequest = now - this.lastRequestTime;
      if (timeSinceLastRequest < this.minInterval) {
        await this.sleep(this.minInterval - timeSinceLastRequest);
      }
      
      this.lastRequestTime = Date.now();
      const result = await requestFn();
      resolve(result);
    } catch (error) {
      reject(error);
    } finally {
      this.active--;
      // Process next item in queue
      setTimeout(() => this.processQueue(), 0);
    }
  }
  
  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

// Usage
const requestQueue = new RequestQueue(3, 200); // Max 3 concurrent, 200ms between requests

async function makeQueuedRequest(url, options) {
  return requestQueue.enqueue(() => fetch(url, options));
}
```

### 4. Rate Limit Monitoring

```javascript
class RateLimitMonitor {
  constructor() {
    this.metrics = new Map();
    this.alerts = [];
  }
  
  recordRequest(endpoint, rateLimitHeaders) {
    const key = endpoint;
    const now = Date.now();
    
    if (!this.metrics.has(key)) {
      this.metrics.set(key, {
        requests: [],
        rateLimits: []
      });
    }
    
    const metric = this.metrics.get(key);
    metric.requests.push(now);
    
    if (rateLimitHeaders) {
      const remaining = parseInt(rateLimitHeaders.get('X-RateLimit-Remaining'));
      const limit = parseInt(rateLimitHeaders.get('X-RateLimit-Limit'));
      
      metric.rateLimits.push({
        timestamp: now,
        remaining,
        limit,
        utilization: ((limit - remaining) / limit) * 100
      });
      
      // Alert if utilization is high
      if (remaining / limit < 0.1) { // Less than 10% remaining
        this.addAlert(endpoint, 'HIGH_UTILIZATION', {
          remaining,
          limit,
          utilization: ((limit - remaining) / limit) * 100
        });
      }
    }
    
    // Clean old data (keep last hour)
    const oneHourAgo = now - (60 * 60 * 1000);
    metric.requests = metric.requests.filter(time => time > oneHourAgo);
    metric.rateLimits = metric.rateLimits.filter(rl => rl.timestamp > oneHourAgo);
  }
  
  addAlert(endpoint, type, data) {
    this.alerts.push({
      timestamp: Date.now(),
      endpoint,
      type,
      data
    });
    
    // Keep only recent alerts
    const oneHourAgo = Date.now() - (60 * 60 * 1000);
    this.alerts = this.alerts.filter(alert => alert.timestamp > oneHourAgo);
    
    console.warn(`Rate limit alert: ${type} for ${endpoint}`, data);
  }
  
  getMetrics(endpoint) {
    const metric = this.metrics.get(endpoint);
    if (!metric) return null;
    
    const now = Date.now();
    const oneHourAgo = now - (60 * 60 * 1000);
    
    const recentRequests = metric.requests.filter(time => time > oneHourAgo);
    const recentRateLimits = metric.rateLimits.filter(rl => rl.timestamp > oneHourAgo);
    
    return {
      endpoint,
      requestCount: recentRequests.length,
      averageUtilization: recentRateLimits.length > 0 ?
        recentRateLimits.reduce((sum, rl) => sum + rl.utilization, 0) / recentRateLimits.length :
        0,
      currentUtilization: recentRateLimits.length > 0 ?
        recentRateLimits[recentRateLimits.length - 1].utilization :
        0,
      alerts: this.alerts.filter(alert => alert.endpoint === endpoint)
    };
  }
}
```

## Advanced Rate Limiting Strategies

### 1. Adaptive Rate Limiting

```javascript
class AdaptiveRateLimiter {
  constructor() {
    this.baseDelays = new Map();
    this.successRates = new Map();
    this.adaptationFactor = 1.0;
  }
  
  async makeAdaptiveRequest(endpoint, requestFn) {
    const key = endpoint;
    let delay = this.baseDelays.get(key) || 100;
    
    const startTime = Date.now();
    
    try {
      // Apply current delay
      if (delay > 100) {
        await this.sleep(delay);
      }
      
      const response = await requestFn();
      
      // Success - reduce delay
      if (response.ok) {
        this.recordSuccess(key);
        delay = Math.max(100, delay * 0.9); // Reduce by 10%
      } else if (response.status === 429) {
        // Rate limited - increase delay
        this.recordFailure(key);
        delay = Math.min(10000, delay * 2); // Double delay, max 10s
      }
      
      this.baseDelays.set(key, delay);
      return response;
      
    } catch (error) {
      this.recordFailure(key);
      delay = Math.min(10000, delay * 1.5); // Increase by 50%
      this.baseDelays.set(key, delay);
      throw error;
    }
  }
  
  recordSuccess(key) {
    if (!this.successRates.has(key)) {
      this.successRates.set(key, { successes: 0, total: 0 });
    }
    
    const stats = this.successRates.get(key);
    stats.successes++;
    stats.total++;
    
    // Keep rolling window of last 100 requests
    if (stats.total > 100) {
      stats.successes = Math.floor(stats.successes * 0.9);
      stats.total = 100;
    }
  }
  
  recordFailure(key) {
    if (!this.successRates.has(key)) {
      this.successRates.set(key, { successes: 0, total: 0 });
    }
    
    const stats = this.successRates.get(key);
    stats.total++;
    
    if (stats.total > 100) {
      stats.successes = Math.floor(stats.successes * 0.9);
      stats.total = 100;
    }
  }
  
  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}
```

### 2. Priority-Based Request Handling

```javascript
class PriorityRequestManager {
  constructor() {
    this.queues = {
      high: [],
      normal: [],
      low: []
    };
    this.processing = false;
  }
  
  async enqueueRequest(requestFn, priority = 'normal') {
    return new Promise((resolve, reject) => {
      const request = { requestFn, resolve, reject, timestamp: Date.now() };
      
      if (!this.queues[priority]) {
        priority = 'normal';
      }
      
      this.queues[priority].push(request);
      this.processQueues();
    });
  }
  
  async processQueues() {
    if (this.processing) return;
    this.processing = true;
    
    try {
      while (this.hasRequests()) {
        const request = this.getNextRequest();
        if (!request) break;
        
        try {
          const result = await request.requestFn();
          request.resolve(result);
        } catch (error) {
          request.reject(error);
        }
        
        // Small delay between requests
        await this.sleep(50);
      }
    } finally {
      this.processing = false;
    }
  }
  
  hasRequests() {
    return this.queues.high.length > 0 ||
           this.queues.normal.length > 0 ||
           this.queues.low.length > 0;
  }
  
  getNextRequest() {
    // Process high priority first
    if (this.queues.high.length > 0) {
      return this.queues.high.shift();
    }
    
    // Then normal priority
    if (this.queues.normal.length > 0) {
      return this.queues.normal.shift();
    }
    
    // Finally low priority
    if (this.queues.low.length > 0) {
      return this.queues.low.shift();
    }
    
    return null;
  }
  
  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

// Usage
const priorityManager = new PriorityRequestManager();

// High priority: Critical operations
await priorityManager.enqueueRequest(
  () => fetch('/family/123/sbd-account/freeze', { method: 'POST' }),
  'high'
);

// Normal priority: Regular operations
await priorityManager.enqueueRequest(
  () => fetch('/family/my-families'),
  'normal'
);

// Low priority: Background operations
await priorityManager.enqueueRequest(
  () => fetch('/family/123/sbd-account/transactions'),
  'low'
);
```

## Rate Limit Optimization Strategies

### 1. Request Batching

```javascript
class RequestBatcher {
  constructor(batchSize = 10, flushInterval = 1000) {
    this.batchSize = batchSize;
    this.flushInterval = flushInterval;
    this.batches = new Map();
    this.timers = new Map();
  }
  
  async batchRequest(batchKey, requestData) {
    if (!this.batches.has(batchKey)) {
      this.batches.set(batchKey, []);
    }
    
    const batch = this.batches.get(batchKey);
    
    return new Promise((resolve, reject) => {
      batch.push({ requestData, resolve, reject });
      
      // Flush if batch is full
      if (batch.length >= this.batchSize) {
        this.flushBatch(batchKey);
      } else {
        // Set timer to flush batch
        this.setFlushTimer(batchKey);
      }
    });
  }
  
  setFlushTimer(batchKey) {
    if (this.timers.has(batchKey)) {
      return; // Timer already set
    }
    
    const timer = setTimeout(() => {
      this.flushBatch(batchKey);
    }, this.flushInterval);
    
    this.timers.set(batchKey, timer);
  }
  
  async flushBatch(batchKey) {
    const batch = this.batches.get(batchKey);
    if (!batch || batch.length === 0) return;
    
    // Clear timer
    const timer = this.timers.get(batchKey);
    if (timer) {
      clearTimeout(timer);
      this.timers.delete(batchKey);
    }
    
    // Remove batch from map
    this.batches.delete(batchKey);
    
    try {
      // Process batch based on batch key
      const results = await this.processBatch(batchKey, batch);
      
      // Resolve individual promises
      batch.forEach((item, index) => {
        item.resolve(results[index]);
      });
    } catch (error) {
      // Reject all promises in batch
      batch.forEach(item => {
        item.reject(error);
      });
    }
  }
  
  async processBatch(batchKey, batch) {
    switch (batchKey) {
      case 'validate_spending':
        return this.processSpendingValidationBatch(batch);
      case 'get_notifications':
        return this.processNotificationBatch(batch);
      default:
        throw new Error(`Unknown batch type: ${batchKey}`);
    }
  }
  
  async processSpendingValidationBatch(batch) {
    const validations = batch.map(item => item.requestData);
    
    const response = await fetch('/family/validate-spending-batch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ validations })
    });
    
    const results = await response.json();
    return results.validations;
  }
}
```

### 2. Caching Strategy

```javascript
class CachedApiClient {
  constructor(baseUrl, defaultTtl = 300000) { // 5 minutes default
    this.baseUrl = baseUrl;
    this.defaultTtl = defaultTtl;
    this.cache = new Map();
    this.cacheTtls = new Map();
  }
  
  async get(endpoint, options = {}) {
    const cacheKey = this.getCacheKey(endpoint, options);
    const cached = this.getFromCache(cacheKey);
    
    if (cached) {
      console.log(`Cache hit for ${endpoint}`);
      return cached;
    }
    
    console.log(`Cache miss for ${endpoint}`);
    const response = await fetch(`${this.baseUrl}${endpoint}`, options);
    const data = await response.json();
    
    // Cache successful responses
    if (response.ok) {
      this.setCache(cacheKey, data, this.getTtl(endpoint));
    }
    
    return data;
  }
  
  getCacheKey(endpoint, options) {
    const method = options.method || 'GET';
    const params = new URLSearchParams(options.params || {}).toString();
    return `${method}:${endpoint}${params ? '?' + params : ''}`;
  }
  
  getFromCache(key) {
    const ttl = this.cacheTtls.get(key);
    if (!ttl || Date.now() > ttl) {
      this.cache.delete(key);
      this.cacheTtls.delete(key);
      return null;
    }
    
    return this.cache.get(key);
  }
  
  setCache(key, data, ttl) {
    this.cache.set(key, data);
    this.cacheTtls.set(key, Date.now() + ttl);
  }
  
  getTtl(endpoint) {
    // Different TTLs for different endpoints
    const ttlMap = {
      '/family/my-families': 300000,        // 5 minutes
      '/family/.*/sbd-account': 60000,      // 1 minute
      '/family/.*/notifications': 30000,     // 30 seconds
      '/family/.*/token-requests': 60000,   // 1 minute
    };
    
    for (const [pattern, ttl] of Object.entries(ttlMap)) {
      if (new RegExp(pattern).test(endpoint)) {
        return ttl;
      }
    }
    
    return this.defaultTtl;
  }
  
  invalidateCache(pattern) {
    const regex = new RegExp(pattern);
    
    for (const key of this.cache.keys()) {
      if (regex.test(key)) {
        this.cache.delete(key);
        this.cacheTtls.delete(key);
      }
    }
  }
}
```

## Monitoring and Alerting

### Rate Limit Metrics to Track

1. **Request Volume**: Requests per endpoint per time period
2. **Rate Limit Utilization**: Percentage of rate limit used
3. **Rate Limit Violations**: Number of 429 responses
4. **Response Times**: Impact of rate limiting on performance
5. **Error Rates**: Correlation between rate limits and errors

### Alerting Thresholds

```javascript
const alertThresholds = {
  HIGH_UTILIZATION: 80,      // Alert when 80% of rate limit used
  FREQUENT_VIOLATIONS: 10,   // Alert after 10 rate limit violations
  SUSTAINED_HIGH_USAGE: 70,  // Alert if usage stays above 70% for 10 minutes
  ERROR_RATE_SPIKE: 5        // Alert if error rate exceeds 5%
};
```

### Dashboard Metrics

Create dashboards to monitor:
- Rate limit utilization by endpoint
- Rate limit violations over time
- Request patterns and trends
- User behavior analysis
- System performance impact

## Troubleshooting Common Issues

### Issue 1: Frequent Rate Limiting

**Symptoms**: Regular 429 responses, high rate limit utilization

**Solutions**:
1. Implement request queuing
2. Add caching for frequently accessed data
3. Batch similar requests
4. Optimize request patterns
5. Consider upgrading rate limits if justified

### Issue 2: Bursty Traffic Patterns

**Symptoms**: Occasional rate limiting during peak usage

**Solutions**:
1. Implement exponential backoff
2. Use adaptive rate limiting
3. Spread requests over time
4. Implement priority queuing
5. Cache aggressively during peak times

### Issue 3: Inefficient Request Patterns

**Symptoms**: High request volume for simple operations

**Solutions**:
1. Combine multiple operations into single requests
2. Use batch endpoints where available
3. Implement client-side caching
4. Optimize data fetching patterns
5. Use webhooks for real-time updates instead of polling

By following these rate limiting policies and best practices, you can build robust applications that work efficiently within the API's constraints while providing a great user experience.
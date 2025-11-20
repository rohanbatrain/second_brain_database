# Performance Tuning and Optimization Guide

## Overview

This guide provides comprehensive performance optimization strategies for the Family Management System. It covers application-level optimizations, database tuning, caching strategies, and system-level improvements.

## Performance Monitoring Baseline

### Key Performance Indicators (KPIs)

| Metric | Target | Warning | Critical |
|--------|--------|---------|----------|
| API Response Time (95th percentile) | < 500ms | > 1s | > 2s |
| Database Query Time (95th percentile) | < 100ms | > 500ms | > 1s |
| Cache Hit Rate | > 90% | < 80% | < 70% |
| CPU Usage | < 70% | > 80% | > 90% |
| Memory Usage | < 80% | > 90% | > 95% |
| Disk I/O Wait | < 10% | > 20% | > 30% |
| Concurrent Users | 1000+ | - | - |
| Error Rate | < 0.1% | > 1% | > 5% |

### Performance Testing Framework

Create `/opt/scripts/performance_test.py`:

```python
#!/usr/bin/env python3
"""Performance testing framework for Family Management System."""

import asyncio
import aiohttp
import time
import statistics
import json
from typing import List, Dict, Any
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor

@dataclass
class TestResult:
    endpoint: str
    method: str
    response_times: List[float]
    success_count: int
    error_count: int
    status_codes: Dict[int, int]

class PerformanceTester:
    def __init__(self, base_url: str, auth_token: str = None):
        self.base_url = base_url
        self.auth_token = auth_token
        self.session = None
    
    async def __aenter__(self):
        connector = aiohttp.TCPConnector(limit=100, limit_per_host=50)
        timeout = aiohttp.ClientTimeout(total=30)
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def test_endpoint(self, endpoint: str, method: str = 'GET', 
                          data: Dict = None, concurrent_users: int = 10, 
                          requests_per_user: int = 10) -> TestResult:
        """Test a single endpoint with concurrent users."""
        
        headers = {}
        if self.auth_token:
            headers['Authorization'] = f'Bearer {self.auth_token}'
        
        response_times = []
        success_count = 0
        error_count = 0
        status_codes = {}
        
        async def make_request():
            start_time = time.time()
            try:
                async with self.session.request(
                    method, 
                    f"{self.base_url}{endpoint}",
                    headers=headers,
                    json=data
                ) as response:
                    await response.text()  # Consume response
                    response_time = time.time() - start_time
                    
                    status_codes[response.status] = status_codes.get(response.status, 0) + 1
                    
                    if response.status < 400:
                        return response_time, True
                    else:
                        return response_time, False
            except Exception as e:
                response_time = time.time() - start_time
                return response_time, False
        
        # Create tasks for concurrent execution
        tasks = []
        for _ in range(concurrent_users):
            for _ in range(requests_per_user):
                tasks.append(make_request())
        
        # Execute all requests concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for result in results:
            if isinstance(result, Exception):
                error_count += 1
                response_times.append(30.0)  # Timeout value
            else:
                response_time, success = result
                response_times.append(response_time)
                if success:
                    success_count += 1
                else:
                    error_count += 1
        
        return TestResult(
            endpoint=endpoint,
            method=method,
            response_times=response_times,
            success_count=success_count,
            error_count=error_count,
            status_codes=status_codes
        )
    
    def analyze_results(self, result: TestResult) -> Dict[str, Any]:
        """Analyze test results and provide statistics."""
        
        if not result.response_times:
            return {"error": "No response times recorded"}
        
        return {
            "endpoint": result.endpoint,
            "method": result.method,
            "total_requests": len(result.response_times),
            "success_rate": result.success_count / len(result.response_times) * 100,
            "error_rate": result.error_count / len(result.response_times) * 100,
            "response_times": {
                "min": min(result.response_times) * 1000,  # Convert to ms
                "max": max(result.response_times) * 1000,
                "mean": statistics.mean(result.response_times) * 1000,
                "median": statistics.median(result.response_times) * 1000,
                "p95": statistics.quantiles(result.response_times, n=20)[18] * 1000,
                "p99": statistics.quantiles(result.response_times, n=100)[98] * 1000,
            },
            "status_codes": result.status_codes,
            "requests_per_second": len(result.response_times) / sum(result.response_times)
        }

async def run_performance_tests():
    """Run comprehensive performance tests."""
    
    test_scenarios = [
        {"endpoint": "/health", "method": "GET", "users": 50, "requests": 20},
        {"endpoint": "/family/my-families", "method": "GET", "users": 20, "requests": 10},
        {"endpoint": "/family/create", "method": "POST", "users": 10, "requests": 5, 
         "data": {"name": "Test Family"}},
        {"endpoint": "/family/123/sbd-account", "method": "GET", "users": 15, "requests": 10},
    ]
    
    async with PerformanceTester("http://localhost:8000", "test_token") as tester:
        results = []
        
        for scenario in test_scenarios:
            print(f"Testing {scenario['endpoint']}...")
            
            result = await tester.test_endpoint(
                endpoint=scenario["endpoint"],
                method=scenario["method"],
                data=scenario.get("data"),
                concurrent_users=scenario["users"],
                requests_per_user=scenario["requests"]
            )
            
            analysis = tester.analyze_results(result)
            results.append(analysis)
            
            print(f"  Success Rate: {analysis['success_rate']:.1f}%")
            print(f"  Mean Response Time: {analysis['response_times']['mean']:.1f}ms")
            print(f"  95th Percentile: {analysis['response_times']['p95']:.1f}ms")
            print(f"  Requests/sec: {analysis['requests_per_second']:.1f}")
            print()
        
        # Save results
        with open("/tmp/performance_test_results.json", "w") as f:
            json.dump(results, f, indent=2)
        
        print("Performance test results saved to /tmp/performance_test_results.json")

if __name__ == "__main__":
    asyncio.run(run_performance_tests())
```

## Application-Level Optimizations

### FastAPI Optimizations

#### 1. Async/Await Optimization

```python
# Optimized async patterns
class OptimizedFamilyManager:
    async def get_family_with_members(self, family_id: str) -> Dict:
        """Optimized family data retrieval with concurrent queries."""
        
        # Execute multiple queries concurrently
        family_task = self.get_family(family_id)
        members_task = self.get_family_members(family_id)
        sbd_account_task = self.get_sbd_account(family_id)
        
        family, members, sbd_account = await asyncio.gather(
            family_task, members_task, sbd_account_task
        )
        
        return {
            "family": family,
            "members": members,
            "sbd_account": sbd_account
        }
    
    async def batch_family_operations(self, operations: List[Dict]) -> List[Dict]:
        """Batch multiple family operations for efficiency."""
        
        tasks = []
        for operation in operations:
            if operation["type"] == "create":
                tasks.append(self.create_family(**operation["params"]))
            elif operation["type"] == "invite":
                tasks.append(self.invite_member(**operation["params"]))
            # Add more operation types as needed
        
        return await asyncio.gather(*tasks, return_exceptions=True)
```

#### 2. Response Optimization

```python
from fastapi.responses import ORJSONResponse
from fastapi.middleware.gzip import GZipMiddleware

# Use faster JSON serialization
app.default_response_class = ORJSONResponse

# Enable compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Optimize response models
class OptimizedFamilyResponse(BaseModel):
    """Optimized response model with selective field loading."""
    
    family_id: str
    name: str
    member_count: int
    is_admin: bool
    
    # Optional fields loaded on demand
    members: Optional[List[FamilyMemberResponse]] = None
    sbd_account: Optional[SBDAccountResponse] = None
    
    class Config:
        # Enable field aliasing for smaller payloads
        allow_population_by_field_name = True
        fields = {
            "family_id": {"alias": "id"},
            "member_count": {"alias": "count"}
        }
```

#### 3. Connection Pool Optimization

```python
# Optimized database connection settings
class OptimizedDatabaseConfig:
    MONGODB_MAX_POOL_SIZE = 100
    MONGODB_MIN_POOL_SIZE = 10
    MONGODB_MAX_IDLE_TIME_MS = 30000
    MONGODB_WAIT_QUEUE_TIMEOUT_MS = 5000
    MONGODB_SERVER_SELECTION_TIMEOUT_MS = 5000
    
    # Redis connection pool
    REDIS_MAX_CONNECTIONS = 50
    REDIS_RETRY_ON_TIMEOUT = True
    REDIS_SOCKET_KEEPALIVE = True
    REDIS_SOCKET_KEEPALIVE_OPTIONS = {
        1: 1,  # TCP_KEEPIDLE
        2: 3,  # TCP_KEEPINTVL
        3: 5,  # TCP_KEEPCNT
    }

# Apply optimized settings
async def get_optimized_database():
    client = AsyncIOMotorClient(
        MONGODB_URL,
        maxPoolSize=OptimizedDatabaseConfig.MONGODB_MAX_POOL_SIZE,
        minPoolSize=OptimizedDatabaseConfig.MONGODB_MIN_POOL_SIZE,
        maxIdleTimeMS=OptimizedDatabaseConfig.MONGODB_MAX_IDLE_TIME_MS,
        waitQueueTimeoutMS=OptimizedDatabaseConfig.MONGODB_WAIT_QUEUE_TIMEOUT_MS,
        serverSelectionTimeoutMS=OptimizedDatabaseConfig.MONGODB_SERVER_SELECTION_TIMEOUT_MS
    )
    return client[MONGODB_DATABASE]
```

### Caching Strategies

#### 1. Multi-Level Caching

```python
import asyncio
from functools import wraps
from typing import Optional, Any
import hashlib
import json

class MultiLevelCache:
    """Multi-level caching with memory and Redis."""
    
    def __init__(self, redis_client, memory_cache_size: int = 1000):
        self.redis_client = redis_client
        self.memory_cache = {}
        self.memory_cache_size = memory_cache_size
        self.memory_access_order = []
    
    def _generate_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate cache key from function arguments."""
        key_data = json.dumps([args, sorted(kwargs.items())], sort_keys=True)
        key_hash = hashlib.md5(key_data.encode()).hexdigest()
        return f"{prefix}:{key_hash}"
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache (memory first, then Redis)."""
        
        # Check memory cache first
        if key in self.memory_cache:
            # Update access order
            self.memory_access_order.remove(key)
            self.memory_access_order.append(key)
            return self.memory_cache[key]
        
        # Check Redis cache
        try:
            value = await self.redis_client.get(key)
            if value:
                decoded_value = json.loads(value)
                # Store in memory cache
                self._store_in_memory(key, decoded_value)
                return decoded_value
        except Exception:
            pass
        
        return None
    
    async def set(self, key: str, value: Any, ttl: int = 300):
        """Set value in both memory and Redis cache."""
        
        # Store in memory cache
        self._store_in_memory(key, value)
        
        # Store in Redis cache
        try:
            await self.redis_client.setex(
                key, ttl, json.dumps(value, default=str)
            )
        except Exception:
            pass
    
    def _store_in_memory(self, key: str, value: Any):
        """Store value in memory cache with LRU eviction."""
        
        if key in self.memory_cache:
            self.memory_access_order.remove(key)
        elif len(self.memory_cache) >= self.memory_cache_size:
            # Evict least recently used
            oldest_key = self.memory_access_order.pop(0)
            del self.memory_cache[oldest_key]
        
        self.memory_cache[key] = value
        self.memory_access_order.append(key)

# Cache decorator
def cached(prefix: str, ttl: int = 300):
    """Decorator for caching function results."""
    
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache = get_cache_instance()  # Get cache instance
            cache_key = cache._generate_key(prefix, *args, **kwargs)
            
            # Try to get from cache
            cached_result = await cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            await cache.set(cache_key, result, ttl)
            return result
        
        return wrapper
    return decorator

# Usage example
class CachedFamilyManager:
    @cached("family_data", ttl=600)  # 10 minutes
    async def get_family(self, family_id: str) -> Dict:
        """Get family data with caching."""
        return await self._fetch_family_from_db(family_id)
    
    @cached("family_members", ttl=300)  # 5 minutes
    async def get_family_members(self, family_id: str) -> List[Dict]:
        """Get family members with caching."""
        return await self._fetch_members_from_db(family_id)
```

#### 2. Cache Warming and Invalidation

```python
class CacheManager:
    """Manage cache warming and invalidation."""
    
    def __init__(self, cache: MultiLevelCache):
        self.cache = cache
    
    async def warm_family_cache(self, family_id: str):
        """Pre-warm cache for family data."""
        
        # Warm essential family data
        tasks = [
            self._warm_family_basic_data(family_id),
            self._warm_family_members(family_id),
            self._warm_sbd_account(family_id),
            self._warm_recent_notifications(family_id)
        ]
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def invalidate_family_cache(self, family_id: str):
        """Invalidate all cache entries for a family."""
        
        cache_patterns = [
            f"family_data:*{family_id}*",
            f"family_members:*{family_id}*",
            f"sbd_account:*{family_id}*",
            f"notifications:*{family_id}*"
        ]
        
        for pattern in cache_patterns:
            await self._invalidate_pattern(pattern)
    
    async def _invalidate_pattern(self, pattern: str):
        """Invalidate cache entries matching pattern."""
        try:
            keys = await self.cache.redis_client.keys(pattern)
            if keys:
                await self.cache.redis_client.delete(*keys)
        except Exception:
            pass
    
    async def cache_health_check(self) -> Dict[str, Any]:
        """Check cache health and performance."""
        
        # Test cache performance
        test_key = "cache_health_test"
        test_value = {"timestamp": time.time()}
        
        # Measure set performance
        start_time = time.time()
        await self.cache.set(test_key, test_value, 60)
        set_time = time.time() - start_time
        
        # Measure get performance
        start_time = time.time()
        retrieved_value = await self.cache.get(test_key)
        get_time = time.time() - start_time
        
        # Get cache statistics
        memory_cache_size = len(self.cache.memory_cache)
        
        try:
            redis_info = await self.cache.redis_client.info("memory")
            redis_memory = redis_info.get("used_memory_human", "unknown")
        except Exception:
            redis_memory = "unavailable"
        
        return {
            "status": "healthy" if retrieved_value else "unhealthy",
            "performance": {
                "set_time_ms": set_time * 1000,
                "get_time_ms": get_time * 1000
            },
            "statistics": {
                "memory_cache_size": memory_cache_size,
                "memory_cache_limit": self.cache.memory_cache_size,
                "redis_memory_usage": redis_memory
            }
        }
```

## Database Optimizations

### MongoDB Performance Tuning

#### 1. Index Optimization

```javascript
// Family Management System - Optimized Indexes

// Families collection
db.families.createIndex(
    { "admin_user_ids": 1 },
    { name: "idx_families_admin_users" }
);

db.families.createIndex(
    { "created_at": -1 },
    { name: "idx_families_created_desc" }
);

db.families.createIndex(
    { "is_active": 1, "created_at": -1 },
    { name: "idx_families_active_created" }
);

// Compound index for family queries
db.families.createIndex(
    { "admin_user_ids": 1, "is_active": 1 },
    { name: "idx_families_admin_active" }
);

// Family relationships collection
db.family_relationships.createIndex(
    { "family_id": 1, "status": 1 },
    { name: "idx_relationships_family_status" }
);

db.family_relationships.createIndex(
    { "user_a_id": 1, "user_b_id": 1 },
    { name: "idx_relationships_users", unique: true }
);

// Family invitations collection
db.family_invitations.createIndex(
    { "family_id": 1, "status": 1 },
    { name: "idx_invitations_family_status" }
);

db.family_invitations.createIndex(
    { "invitee_user_id": 1, "status": 1 },
    { name: "idx_invitations_invitee_status" }
);

// TTL index for expired invitations
db.family_invitations.createIndex(
    { "expires_at": 1 },
    { name: "idx_invitations_expires", expireAfterSeconds: 0 }
);

// Family token requests collection
db.family_token_requests.createIndex(
    { "family_id": 1, "status": 1, "created_at": -1 },
    { name: "idx_token_requests_family_status_created" }
);

db.family_token_requests.createIndex(
    { "requester_user_id": 1, "status": 1 },
    { name: "idx_token_requests_requester_status" }
);

// TTL index for expired token requests
db.family_token_requests.createIndex(
    { "expires_at": 1 },
    { name: "idx_token_requests_expires", expireAfterSeconds: 0 }
);

// Family notifications collection
db.family_notifications.createIndex(
    { "recipient_user_ids": 1, "created_at": -1 },
    { name: "idx_notifications_recipients_created" }
);

db.family_notifications.createIndex(
    { "family_id": 1, "type": 1, "created_at": -1 },
    { name: "idx_notifications_family_type_created" }
);

// Sparse index for read notifications
db.family_notifications.createIndex(
    { "read_by": 1 },
    { name: "idx_notifications_read_by", sparse: true }
);
```

#### 2. Query Optimization

```python
class OptimizedFamilyQueries:
    """Optimized database queries for family operations."""
    
    async def get_user_families_optimized(self, user_id: str) -> List[Dict]:
        """Optimized query to get user's families."""
        
        # Use aggregation pipeline for efficient joins
        pipeline = [
            {
                "$match": {
                    "admin_user_ids": user_id,
                    "is_active": True
                }
            },
            {
                "$lookup": {
                    "from": "family_relationships",
                    "let": {"family_id": "$family_id"},
                    "pipeline": [
                        {
                            "$match": {
                                "$expr": {
                                    "$and": [
                                        {"$eq": ["$family_id", "$$family_id"]},
                                        {"$eq": ["$status", "active"]}
                                    ]
                                }
                            }
                        },
                        {"$count": "member_count"}
                    ],
                    "as": "member_info"
                }
            },
            {
                "$addFields": {
                    "member_count": {
                        "$ifNull": [
                            {"$arrayElemAt": ["$member_info.member_count", 0]},
                            0
                        ]
                    }
                }
            },
            {
                "$project": {
                    "family_id": 1,
                    "name": 1,
                    "admin_user_ids": 1,
                    "member_count": 1,
                    "created_at": 1,
                    "sbd_account": 1
                }
            },
            {"$sort": {"created_at": -1}}
        ]
        
        cursor = self.db.families.aggregate(pipeline)
        return await cursor.to_list(length=None)
    
    async def get_family_dashboard_data(self, family_id: str) -> Dict:
        """Get comprehensive family dashboard data in single query."""
        
        pipeline = [
            {"$match": {"family_id": family_id}},
            {
                "$lookup": {
                    "from": "family_relationships",
                    "localField": "family_id",
                    "foreignField": "family_id",
                    "as": "relationships"
                }
            },
            {
                "$lookup": {
                    "from": "family_token_requests",
                    "let": {"family_id": "$family_id"},
                    "pipeline": [
                        {
                            "$match": {
                                "$expr": {
                                    "$and": [
                                        {"$eq": ["$family_id", "$$family_id"]},
                                        {"$eq": ["$status", "pending"]}
                                    ]
                                }
                            }
                        },
                        {"$sort": {"created_at": -1}},
                        {"$limit": 5}
                    ],
                    "as": "pending_requests"
                }
            },
            {
                "$lookup": {
                    "from": "family_notifications",
                    "let": {"family_id": "$family_id"},
                    "pipeline": [
                        {
                            "$match": {
                                "$expr": {"$eq": ["$family_id", "$$family_id"]}
                            }
                        },
                        {"$sort": {"created_at": -1}},
                        {"$limit": 10}
                    ],
                    "as": "recent_notifications"
                }
            }
        ]
        
        cursor = self.db.families.aggregate(pipeline)
        result = await cursor.to_list(length=1)
        return result[0] if result else None
```

#### 3. Connection Pool Tuning

```python
# MongoDB connection optimization
MONGODB_SETTINGS = {
    # Connection pool settings
    "maxPoolSize": 100,
    "minPoolSize": 10,
    "maxIdleTimeMS": 30000,
    "waitQueueTimeoutMS": 5000,
    
    # Server selection and socket settings
    "serverSelectionTimeoutMS": 5000,
    "socketTimeoutMS": 20000,
    "connectTimeoutMS": 10000,
    
    # Write concern for performance
    "w": 1,
    "j": False,  # Don't wait for journal sync for better performance
    
    # Read preferences
    "readPreference": "primaryPreferred",
    "readConcernLevel": "local",
    
    # Compression
    "compressors": ["zstd", "zlib"],
    
    # Retry settings
    "retryWrites": True,
    "retryReads": True
}
```

### Redis Performance Tuning

#### 1. Redis Configuration Optimization

```conf
# /etc/redis/redis.conf - Performance optimizations

# Memory management
maxmemory 4gb
maxmemory-policy allkeys-lru
maxmemory-samples 10

# Persistence optimization for performance
save 900 1
save 300 10
save 60 10000

# Disable RDB compression for faster saves (if disk space allows)
rdbcompression no

# AOF configuration for durability vs performance balance
appendonly yes
appendfsync everysec
no-appendfsync-on-rewrite yes
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb

# Network and connection settings
tcp-backlog 511
tcp-keepalive 300
timeout 0

# Client output buffer limits
client-output-buffer-limit normal 0 0 0
client-output-buffer-limit replica 256mb 64mb 60
client-output-buffer-limit pubsub 32mb 8mb 60

# Hash optimization
hash-max-ziplist-entries 512
hash-max-ziplist-value 64

# List optimization
list-max-ziplist-size -2
list-compress-depth 0

# Set optimization
set-max-intset-entries 512

# Sorted set optimization
zset-max-ziplist-entries 128
zset-max-ziplist-value 64

# HyperLogLog optimization
hll-sparse-max-bytes 3000

# Streams optimization
stream-node-max-bytes 4096
stream-node-max-entries 100

# Threading (Redis 6.0+)
io-threads 4
io-threads-do-reads yes

# Memory usage optimization
activerehashing yes
client-query-buffer-limit 1gb
proto-max-bulk-len 512mb
```

#### 2. Redis Usage Patterns

```python
class OptimizedRedisManager:
    """Optimized Redis operations for family management."""
    
    def __init__(self, redis_client):
        self.redis = redis_client
    
    async def batch_cache_operations(self, operations: List[Dict]) -> List[Any]:
        """Batch multiple Redis operations for efficiency."""
        
        pipe = self.redis.pipeline()
        
        for op in operations:
            if op["type"] == "set":
                pipe.setex(op["key"], op["ttl"], op["value"])
            elif op["type"] == "get":
                pipe.get(op["key"])
            elif op["type"] == "delete":
                pipe.delete(op["key"])
            elif op["type"] == "incr":
                pipe.incr(op["key"])
        
        return await pipe.execute()
    
    async def optimized_rate_limiting(self, key: str, limit: int, window: int) -> bool:
        """Optimized sliding window rate limiting."""
        
        now = time.time()
        window_start = now - window
        
        pipe = self.redis.pipeline()
        
        # Remove expired entries
        pipe.zremrangebyscore(key, 0, window_start)
        
        # Count current requests
        pipe.zcard(key)
        
        # Add current request
        pipe.zadd(key, {str(now): now})
        
        # Set expiration
        pipe.expire(key, window)
        
        results = await pipe.execute()
        current_count = results[1]
        
        return current_count < limit
    
    async def cache_family_data_efficiently(self, family_id: str, data: Dict):
        """Cache family data with optimized structure."""
        
        # Use hash for structured data
        cache_key = f"family:{family_id}"
        
        # Flatten nested data for hash storage
        flattened_data = self._flatten_dict(data)
        
        pipe = self.redis.pipeline()
        pipe.delete(cache_key)  # Clear existing data
        pipe.hmset(cache_key, flattened_data)
        pipe.expire(cache_key, 600)  # 10 minutes TTL
        
        await pipe.execute()
    
    def _flatten_dict(self, d: Dict, parent_key: str = '', sep: str = '.') -> Dict:
        """Flatten nested dictionary for Redis hash storage."""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep=sep).items())
            else:
                items.append((new_key, json.dumps(v) if not isinstance(v, str) else v))
        return dict(items)
```

## System-Level Optimizations

### Operating System Tuning

#### 1. Kernel Parameters

Create `/etc/sysctl.d/99-sbd-performance.conf`:

```conf
# Network optimizations
net.core.somaxconn = 65535
net.core.netdev_max_backlog = 5000
net.ipv4.tcp_max_syn_backlog = 65535
net.ipv4.tcp_fin_timeout = 30
net.ipv4.tcp_keepalive_time = 1200
net.ipv4.tcp_keepalive_probes = 3
net.ipv4.tcp_keepalive_intvl = 15

# Memory management
vm.swappiness = 1
vm.dirty_ratio = 15
vm.dirty_background_ratio = 5
vm.overcommit_memory = 1

# File system optimizations
fs.file-max = 2097152
fs.nr_open = 1048576

# Process limits
kernel.pid_max = 4194304
```

#### 2. System Limits

Create `/etc/security/limits.d/99-sbd.conf`:

```conf
# Limits for SBD application
sbd soft nofile 65536
sbd hard nofile 65536
sbd soft nproc 32768
sbd hard nproc 32768

# MongoDB limits
mongodb soft nofile 64000
mongodb hard nofile 64000
mongodb soft nproc 32000
mongodb hard nproc 32000

# Redis limits
redis soft nofile 65536
redis hard nofile 65536
```

#### 3. CPU and Memory Optimization

```bash
#!/bin/bash
# CPU and memory optimization script

# Set CPU governor to performance
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor

# Disable transparent huge pages (for MongoDB)
echo never | sudo tee /sys/kernel/mm/transparent_hugepage/enabled
echo never | sudo tee /sys/kernel/mm/transparent_hugepage/defrag

# Set I/O scheduler to deadline for SSDs
echo deadline | sudo tee /sys/block/*/queue/scheduler

# Increase read-ahead for better sequential I/O
echo 4096 | sudo tee /sys/block/*/queue/read_ahead_kb
```

### Nginx Optimization

#### 1. Nginx Configuration

```nginx
# /etc/nginx/nginx.conf - Performance optimizations

user nginx;
worker_processes auto;
worker_cpu_affinity auto;
worker_rlimit_nofile 65535;

error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 8192;
    use epoll;
    multi_accept on;
    accept_mutex off;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
    
    # Logging optimization
    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                   '$status $body_bytes_sent "$http_referer" '
                   '"$http_user_agent" "$http_x_forwarded_for" '
                   'rt=$request_time uct="$upstream_connect_time" '
                   'uht="$upstream_header_time" urt="$upstream_response_time"';
    
    access_log /var/log/nginx/access.log main buffer=64k flush=5s;
    
    # Performance settings
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    keepalive_requests 1000;
    
    # Buffer sizes
    client_body_buffer_size 128k;
    client_max_body_size 10m;
    client_header_buffer_size 1k;
    large_client_header_buffers 4 4k;
    output_buffers 1 32k;
    postpone_output 1460;
    
    # Timeouts
    client_header_timeout 3m;
    client_body_timeout 3m;
    send_timeout 3m;
    
    # Compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types
        text/plain
        text/css
        text/xml
        text/javascript
        application/json
        application/javascript
        application/xml+rss
        application/atom+xml
        image/svg+xml;
    
    # Caching
    open_file_cache max=200000 inactive=20s;
    open_file_cache_valid 30s;
    open_file_cache_min_uses 2;
    open_file_cache_errors on;
    
    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req_zone $binary_remote_addr zone=login:10m rate=5r/s;
    
    # Connection limiting
    limit_conn_zone $binary_remote_addr zone=conn_limit_per_ip:10m;
    limit_conn conn_limit_per_ip 20;
    
    # Upstream configuration
    upstream sbd_backend {
        least_conn;
        server 127.0.0.1:8000 max_fails=3 fail_timeout=30s;
        # Add more servers for load balancing
        # server 127.0.0.1:8001 max_fails=3 fail_timeout=30s;
        # server 127.0.0.1:8002 max_fails=3 fail_timeout=30s;
        
        keepalive 32;
    }
    
    server {
        listen 80;
        server_name api.yourdomain.com;
        return 301 https://$server_name$request_uri;
    }
    
    server {
        listen 443 ssl http2;
        server_name api.yourdomain.com;
        
        # SSL optimization
        ssl_certificate /etc/ssl/certs/yourdomain.com.crt;
        ssl_certificate_key /etc/ssl/private/yourdomain.com.key;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
        ssl_prefer_server_ciphers off;
        ssl_session_cache shared:SSL:10m;
        ssl_session_timeout 10m;
        ssl_session_tickets off;
        
        # OCSP stapling
        ssl_stapling on;
        ssl_stapling_verify on;
        
        location / {
            limit_req zone=api burst=20 nodelay;
            
            proxy_pass http://sbd_backend;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            
            # Proxy timeouts
            proxy_connect_timeout 5s;
            proxy_send_timeout 60s;
            proxy_read_timeout 60s;
            
            # Proxy buffering
            proxy_buffering on;
            proxy_buffer_size 4k;
            proxy_buffers 8 4k;
            proxy_busy_buffers_size 8k;
        }
        
        # Health check endpoint (no rate limiting)
        location /health {
            access_log off;
            proxy_pass http://sbd_backend;
        }
        
        # Static files caching
        location ~* \.(jpg|jpeg|png|gif|ico|css|js)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
    }
}
```

## Performance Monitoring and Alerting

### Performance Metrics Collection

Create `/opt/scripts/collect_performance_metrics.py`:

```python
#!/usr/bin/env python3
"""Collect and analyze performance metrics."""

import asyncio
import aiohttp
import psutil
import time
import json
from datetime import datetime
from typing import Dict, Any

class PerformanceCollector:
    def __init__(self, api_base_url: str):
        self.api_base_url = api_base_url
    
    async def collect_system_metrics(self) -> Dict[str, Any]:
        """Collect system performance metrics."""
        
        # CPU metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        load_avg = psutil.getloadavg()
        
        # Memory metrics
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        
        # Disk metrics
        disk_usage = psutil.disk_usage('/')
        disk_io = psutil.disk_io_counters()
        
        # Network metrics
        network_io = psutil.net_io_counters()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "cpu": {
                "percent": cpu_percent,
                "count": cpu_count,
                "load_avg_1m": load_avg[0],
                "load_avg_5m": load_avg[1],
                "load_avg_15m": load_avg[2]
            },
            "memory": {
                "total": memory.total,
                "available": memory.available,
                "percent": memory.percent,
                "used": memory.used,
                "free": memory.free
            },
            "swap": {
                "total": swap.total,
                "used": swap.used,
                "free": swap.free,
                "percent": swap.percent
            },
            "disk": {
                "total": disk_usage.total,
                "used": disk_usage.used,
                "free": disk_usage.free,
                "percent": (disk_usage.used / disk_usage.total) * 100,
                "read_bytes": disk_io.read_bytes if disk_io else 0,
                "write_bytes": disk_io.write_bytes if disk_io else 0
            },
            "network": {
                "bytes_sent": network_io.bytes_sent,
                "bytes_recv": network_io.bytes_recv,
                "packets_sent": network_io.packets_sent,
                "packets_recv": network_io.packets_recv
            }
        }
    
    async def collect_application_metrics(self) -> Dict[str, Any]:
        """Collect application performance metrics."""
        
        metrics = {}
        
        try:
            async with aiohttp.ClientSession() as session:
                # Health check response time
                start_time = time.time()
                async with session.get(f"{self.api_base_url}/health") as response:
                    health_response_time = time.time() - start_time
                    health_status = response.status
                
                # Prometheus metrics
                async with session.get(f"{self.api_base_url}/metrics") as response:
                    if response.status == 200:
                        metrics_text = await response.text()
                        metrics.update(self._parse_prometheus_metrics(metrics_text))
                
                metrics.update({
                    "health_check": {
                        "response_time": health_response_time,
                        "status_code": health_status,
                        "status": "healthy" if health_status == 200 else "unhealthy"
                    }
                })
        
        except Exception as e:
            metrics["error"] = str(e)
        
        return metrics
    
    def _parse_prometheus_metrics(self, metrics_text: str) -> Dict[str, Any]:
        """Parse Prometheus metrics format."""
        
        parsed_metrics = {}
        
        for line in metrics_text.split('\n'):
            if line.startswith('#') or not line.strip():
                continue
            
            try:
                metric_name, metric_value = line.split(' ', 1)
                
                # Extract metric name without labels
                base_name = metric_name.split('{')[0]
                
                if base_name not in parsed_metrics:
                    parsed_metrics[base_name] = []
                
                parsed_metrics[base_name].append({
                    "full_name": metric_name,
                    "value": float(metric_value)
                })
            
            except (ValueError, IndexError):
                continue
        
        return parsed_metrics

async def main():
    collector = PerformanceCollector("http://localhost:8000")
    
    # Collect metrics
    system_metrics = await collector.collect_system_metrics()
    app_metrics = await collector.collect_application_metrics()
    
    # Combine metrics
    all_metrics = {
        "system": system_metrics,
        "application": app_metrics
    }
    
    # Save to file
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"/tmp/performance_metrics_{timestamp}.json"
    
    with open(filename, 'w') as f:
        json.dump(all_metrics, f, indent=2)
    
    print(f"Performance metrics saved to {filename}")
    
    # Check for performance issues
    issues = []
    
    if system_metrics["cpu"]["percent"] > 80:
        issues.append(f"High CPU usage: {system_metrics['cpu']['percent']}%")
    
    if system_metrics["memory"]["percent"] > 90:
        issues.append(f"High memory usage: {system_metrics['memory']['percent']}%")
    
    if system_metrics["disk"]["percent"] > 90:
        issues.append(f"High disk usage: {system_metrics['disk']['percent']}%")
    
    if app_metrics.get("health_check", {}).get("response_time", 0) > 1.0:
        issues.append(f"Slow health check: {app_metrics['health_check']['response_time']:.2f}s")
    
    if issues:
        print("Performance issues detected:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("No performance issues detected")

if __name__ == "__main__":
    asyncio.run(main())
```

This comprehensive performance optimization guide provides the foundation for maintaining high performance in the Family Management System across all layers of the application stack.
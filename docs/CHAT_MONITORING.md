# Chat System Monitoring and Observability

This document describes the comprehensive monitoring and observability features implemented for the LangGraph-based chat system.

## Overview

The chat system includes two complementary monitoring approaches:

1. **Logging**: Detailed execution logs with timing information
2. **Metrics**: Real-time performance and usage metrics

## Logging Features

### Structured Logging

All chat components use the existing Second Brain logging infrastructure with specialized chat logging utilities:

- **Graph Node Execution**: Each graph node logs execution time and success/failure status
- **Token Usage**: Detailed token tracking per request (prompt, completion, total)
- **Streaming Errors**: Full stack traces with context information
- **Cache Operations**: Cache hits, misses, and storage operations
- **Session Operations**: Create, update, delete operations with audit trail
- **Rate Limiting**: Rate limit checks and blocks
- **Vector Search**: Search operations with timing and results count

### Log Levels

- **INFO**: Normal operations, successful completions
- **DEBUG**: Detailed execution flow, cache operations
- **WARNING**: Rate limit blocks, cache failures (non-critical)
- **ERROR**: Failures with full stack traces

### Example Log Output

```
[2025-01-15 10:30:45] INFO in Second_Brain_Database.Chat: [detect_vector_intent] Starting execution for session abc-123
[2025-01-15 10:30:45] INFO in Second_Brain_Database.Chat: [detect_vector_intent] Completed execution for session abc-123 - Status: SUCCESS, Time: 0.234s
[2025-01-15 10:30:46] INFO in Second_Brain_Database.Chat: [TokenUsage] Session: abc-123, Message: msg-456, Model: llama2, Tokens: 1250 (prompt: 450, completion: 800), Cost: $0.0000
[2025-01-15 10:30:46] INFO in Second_Brain_Database.Chat: [VectorRAGGraph] Execution completed for session abc-123 - Status: SUCCESS, Time: 2.145s, Question: 'What is the main topic...'
```

## Metrics Tracking

### Real-Time Metrics

The `ChatMetricsTracker` class tracks the following metrics in Redis:

#### 1. Message Rate
- **Messages per second**: Instantaneous rate based on last minute
- **Per-user message count**: Total messages per user (1-hour TTL)
- **Per-session message count**: Total messages per session (1-hour TTL)

#### 2. Response Time
- **Global average**: Average response time across all requests
- **Per-user average**: Average response time per user
- **Per-session average**: Average response time per session

#### 3. Token Usage
- **Global totals**: Total, prompt, and completion tokens
- **Per-user totals**: Total tokens per user (1-hour TTL)
- **Per-session totals**: Total tokens per session (1-hour TTL)

#### 4. Error Rates
- **By error type**: Count of each error type (e.g., "llm_timeout", "vector_search_failed")
- **Total errors**: Overall error count

#### 5. Cache Performance
- **Hit rate**: Percentage of cache hits vs. total requests
- **Hits/misses**: Individual counts

#### 6. Vector Search Performance
- **Average search time**: Mean execution time for vector searches
- **Average chunks found**: Mean number of chunks retrieved

#### 7. Graph Execution Statistics
- **Per-graph metrics**: For VectorRAGGraph, GeneralResponseGraph, MasterWorkflowGraph
  - Average execution time
  - Success/failure counts
  - Success rate percentage

### Accessing Metrics

#### Via API Endpoint

```bash
GET /chat/metrics
Authorization: Bearer <token>
```

Response:
```json
{
  "status": "success",
  "timestamp": "2025-01-15T10:30:45.123Z",
  "metrics": {
    "messages_per_second": 2.5,
    "average_response_time": 1.234,
    "token_usage": {
      "total_tokens": 125000,
      "prompt_tokens": 45000,
      "completion_tokens": 80000
    },
    "error_rates": {
      "llm_timeout": 5,
      "vector_search_failed": 2,
      "total": 7
    },
    "cache_hit_rate": 45.6,
    "vector_search": {
      "avg_time": 0.456,
      "avg_chunks": 4.2
    },
    "graphs": {
      "VectorRAGGraph": {
        "avg_time": 2.145,
        "success_count": 150,
        "failure_count": 3,
        "success_rate": 98.04
      },
      "GeneralResponseGraph": {
        "avg_time": 1.234,
        "success_count": 200,
        "failure_count": 1,
        "success_rate": 99.50
      },
      "MasterWorkflowGraph": {
        "avg_time": 1.567,
        "success_count": 350,
        "failure_count": 4,
        "success_rate": 98.87
      }
    }
  }
}
```

#### Programmatically

```python
from second_brain_database.chat.utils.metrics_tracker import get_metrics_tracker
from second_brain_database.managers.redis_manager import redis_manager

# Get metrics tracker
metrics = get_metrics_tracker(redis_manager=redis_manager)

# Get specific metrics
messages_per_sec = await metrics.get_messages_per_second()
avg_response_time = await metrics.get_average_response_time(user_id="user-123")
token_usage = await metrics.get_token_usage(session_id="session-456")
cache_hit_rate = await metrics.get_cache_hit_rate()

# Get comprehensive summary
summary = await metrics.get_metrics_summary()
```

## Integration with Existing Infrastructure

### Loki Integration

All chat logs are automatically sent to Loki (if configured) via the existing Second Brain logging infrastructure:

- Logs are buffered locally if Loki is unavailable
- Automatic retry and flush when Loki comes back online
- Per-worker log files in `logs/` directory
- Worker registry for tracking active processes

### Prometheus Integration

While metrics are currently stored in Redis, they can be exported to Prometheus using the existing `fastapi-instrumentator` integration:

1. Add custom metrics collectors in `src/second_brain_database/main.py`
2. Export metrics from Redis to Prometheus format
3. Configure Prometheus to scrape the `/metrics` endpoint

### Redis Storage

Metrics are stored in Redis with the following key patterns:

- `chat:metrics:messages:*` - Message counts
- `chat:metrics:response_time:*` - Response times
- `chat:metrics:tokens:*` - Token usage
- `chat:metrics:errors:*` - Error counts
- `chat:metrics:cache:*` - Cache statistics
- `chat:metrics:vector_search:*` - Vector search stats
- `chat:metrics:graph:*` - Graph execution stats

All metrics have a 1-hour TTL by default to prevent unbounded growth.

## Monitoring Best Practices

### 1. Set Up Alerts

Monitor these key metrics and set up alerts:

- **Error rate > 5%**: Indicates system issues
- **Average response time > 5s**: Performance degradation
- **Cache hit rate < 20%**: Cache not effective
- **Messages per second > 100**: Potential overload

### 2. Regular Log Review

Review logs regularly for:

- Recurring error patterns
- Slow graph executions (> 5s)
- Failed vector searches
- Rate limit violations

### 3. Performance Optimization

Use metrics to identify optimization opportunities:

- Low cache hit rate → Adjust cache TTL or key generation
- High vector search time → Optimize Qdrant configuration
- High token usage → Optimize prompts or context window

### 4. Capacity Planning

Track trends over time:

- Messages per second growth
- Token usage growth
- Storage requirements (MongoDB, Redis, Qdrant)

## Troubleshooting

### High Error Rates

1. Check error logs for specific error types
2. Review graph execution logs for failures
3. Verify external service health (Ollama, Qdrant)

### Slow Response Times

1. Check graph execution times in logs
2. Review vector search performance
3. Verify LLM response times
4. Check database query performance

### Low Cache Hit Rate

1. Review cache key generation logic
2. Check cache TTL settings
3. Verify query patterns (similar queries should hit cache)

### Missing Metrics

1. Verify Redis connectivity
2. Check metrics tracker initialization
3. Review error logs for metrics tracking failures

## Future Enhancements

Potential improvements to monitoring:

1. **Historical Metrics**: Store metrics in MongoDB for long-term analysis
2. **User-Specific Dashboards**: Per-user metrics and usage patterns
3. **Anomaly Detection**: Automatic detection of unusual patterns
4. **Cost Tracking**: Detailed cost analysis for different LLM providers
5. **A/B Testing**: Compare performance of different models or configurations

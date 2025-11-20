# Chat System Configuration Guide

This document provides comprehensive documentation for all chat system configuration variables in Second Brain Database.

## Table of Contents

- [Overview](#overview)
- [Chat Configuration Variables](#chat-configuration-variables)
- [Ollama Configuration](#ollama-configuration)
- [Redis Configuration for Chat](#redis-configuration-for-chat)
- [Environment Setup](#environment-setup)
- [Production Recommendations](#production-recommendations)

## Overview

The chat system in Second Brain Database is built on LangGraph and provides:
- **VectorRAG**: Query vector knowledge bases using natural language
- **General Chat**: Conversational AI responses with context awareness
- **Streaming Responses**: AI SDK Data Stream Protocol compatible streaming
- **Session Management**: Persistent chat sessions with history
- **Token Tracking**: Comprehensive token usage monitoring

All chat features integrate with existing Second Brain infrastructure (MongoDB, Redis, Qdrant, Ollama).

## Chat Configuration Variables

### Feature Toggle

#### `CHAT_ENABLED`
- **Type**: `bool`
- **Default**: `True`
- **Description**: Master switch to enable/disable the entire chat system
- **Usage**: Set to `False` to completely disable chat functionality
- **Example**: `CHAT_ENABLED=true`

### Conversation History Configuration

#### `CHAT_MAX_HISTORY_LENGTH`
- **Type**: `int`
- **Default**: `20`
- **Description**: Maximum number of messages to include in conversation context for LLM
- **Rationale**: Balances context quality with token usage and performance
- **Range**: 5-50 messages recommended
- **Example**: `CHAT_MAX_HISTORY_LENGTH=20`

#### `CHAT_HISTORY_CACHE_TTL`
- **Type**: `int`
- **Default**: `3600` (1 hour)
- **Description**: Time-to-live for conversation history cache in Redis (seconds)
- **Rationale**: Reduces MongoDB queries for frequently accessed conversations
- **Range**: 300-7200 seconds (5 minutes to 2 hours)
- **Example**: `CHAT_HISTORY_CACHE_TTL=3600`

### Vector Search Configuration

#### `CHAT_DEFAULT_TOP_K`
- **Type**: `int`
- **Default**: `5`
- **Description**: Default number of vector search results to retrieve from Qdrant
- **Rationale**: Provides sufficient context without overwhelming the LLM
- **Range**: 3-10 results recommended
- **Example**: `CHAT_DEFAULT_TOP_K=5`

### Streaming Configuration

#### `CHAT_STREAM_TIMEOUT`
- **Type**: `int`
- **Default**: `300` (5 minutes)
- **Description**: Maximum time allowed for streaming response generation (seconds)
- **Rationale**: Prevents hung connections and resource exhaustion
- **Range**: 60-600 seconds (1-10 minutes)
- **Example**: `CHAT_STREAM_TIMEOUT=300`

### Rate Limiting Configuration

#### `CHAT_ENABLE_RATE_LIMITING`
- **Type**: `bool`
- **Default**: `True`
- **Description**: Enable rate limiting for chat operations
- **Usage**: Set to `False` only in development/testing environments
- **Example**: `CHAT_ENABLE_RATE_LIMITING=true`

#### `CHAT_MESSAGE_RATE_LIMIT`
- **Type**: `int`
- **Default**: `20`
- **Description**: Maximum messages per minute per user
- **Rationale**: Prevents abuse while allowing natural conversation flow
- **Range**: 10-60 messages/minute
- **Example**: `CHAT_MESSAGE_RATE_LIMIT=20`

#### `CHAT_SESSION_CREATE_LIMIT`
- **Type**: `int`
- **Default**: `5`
- **Description**: Maximum chat sessions created per hour per user
- **Rationale**: Prevents session spam while allowing legitimate use
- **Range**: 3-20 sessions/hour
- **Example**: `CHAT_SESSION_CREATE_LIMIT=5`

### Query Caching Configuration

#### `CHAT_ENABLE_QUERY_CACHE`
- **Type**: `bool`
- **Default**: `True`
- **Description**: Enable caching of query responses in Redis
- **Rationale**: Reduces redundant LLM calls for identical queries
- **Usage**: Disable for testing or when responses must always be fresh
- **Example**: `CHAT_ENABLE_QUERY_CACHE=true`

#### `CHAT_CACHE_TTL`
- **Type**: `int`
- **Default**: `3600` (1 hour)
- **Description**: Time-to-live for cached query responses (seconds)
- **Rationale**: Balances cache hit rate with response freshness
- **Range**: 300-7200 seconds (5 minutes to 2 hours)
- **Example**: `CHAT_CACHE_TTL=3600`

### Input Validation Configuration

#### `CHAT_TOKEN_ENCODING`
- **Type**: `str`
- **Default**: `"cl100k_base"`
- **Description**: Token encoding scheme for tiktoken (GPT-4 tokenizer)
- **Rationale**: Provides accurate token estimation for Ollama models
- **Options**: `"cl100k_base"` (GPT-4), `"p50k_base"` (GPT-3), `"r50k_base"` (GPT-2)
- **Example**: `CHAT_TOKEN_ENCODING=cl100k_base`

#### `CHAT_MAX_QUERY_LENGTH`
- **Type**: `int`
- **Default**: `10000`
- **Description**: Maximum query length in characters
- **Rationale**: Prevents excessively long queries that could cause performance issues
- **Range**: 1000-50000 characters
- **Example**: `CHAT_MAX_QUERY_LENGTH=10000`

#### `CHAT_MAX_MESSAGE_LENGTH`
- **Type**: `int`
- **Default**: `50000`
- **Description**: Maximum message content length in characters
- **Rationale**: Allows longer responses while preventing abuse
- **Range**: 10000-100000 characters
- **Example**: `CHAT_MAX_MESSAGE_LENGTH=50000`

### Error Recovery Configuration

#### `CHAT_LLM_MAX_RETRIES`
- **Type**: `int`
- **Default**: `3`
- **Description**: Maximum retry attempts for failed LLM calls
- **Rationale**: Handles transient Ollama failures gracefully
- **Range**: 1-5 retries
- **Example**: `CHAT_LLM_MAX_RETRIES=3`

#### `CHAT_LLM_BACKOFF_FACTOR`
- **Type**: `float`
- **Default**: `2.0`
- **Description**: Exponential backoff factor for LLM retries
- **Rationale**: Prevents overwhelming Ollama with rapid retry attempts
- **Range**: 1.5-3.0
- **Example**: `CHAT_LLM_BACKOFF_FACTOR=2.0`

#### `CHAT_VECTOR_MAX_RETRIES`
- **Type**: `int`
- **Default**: `2`
- **Description**: Maximum retry attempts for failed vector search operations
- **Rationale**: Handles transient Qdrant failures
- **Range**: 1-3 retries
- **Example**: `CHAT_VECTOR_MAX_RETRIES=2`

#### `CHAT_VECTOR_BACKOFF_FACTOR`
- **Type**: `float`
- **Default**: `1.5`
- **Description**: Exponential backoff factor for vector search retries
- **Rationale**: Allows Qdrant to recover from temporary issues
- **Range**: 1.0-2.5
- **Example**: `CHAT_VECTOR_BACKOFF_FACTOR=1.5`

### Session Management Configuration

#### `CHAT_AUTO_GENERATE_TITLES`
- **Type**: `bool`
- **Default**: `True`
- **Description**: Automatically generate session titles from first user message
- **Rationale**: Improves UX by providing meaningful session identifiers
- **Usage**: Set to `False` if you want to require manual title setting
- **Example**: `CHAT_AUTO_GENERATE_TITLES=true`

#### `CHAT_TITLE_MAX_LENGTH`
- **Type**: `int`
- **Default**: `50`
- **Description**: Maximum length for auto-generated session titles (characters)
- **Rationale**: Keeps titles concise and readable in UI
- **Range**: 30-100 characters
- **Example**: `CHAT_TITLE_MAX_LENGTH=50`

### Feedback and Analytics Configuration

#### `CHAT_ENABLE_MESSAGE_VOTING`
- **Type**: `bool`
- **Default**: `True`
- **Description**: Enable message voting (upvote/downvote) functionality
- **Rationale**: Collects user feedback for response quality improvement
- **Usage**: Disable if you don't need feedback collection
- **Example**: `CHAT_ENABLE_MESSAGE_VOTING=true`

#### `CHAT_ENABLE_SESSION_STATISTICS`
- **Type**: `bool`
- **Default**: `True`
- **Description**: Enable session statistics tracking (message count, tokens, duration)
- **Rationale**: Provides usage analytics and monitoring data
- **Usage**: Disable to reduce database writes (not recommended)
- **Example**: `CHAT_ENABLE_SESSION_STATISTICS=true`

## Ollama Configuration

The chat system requires Ollama for LLM operations. These settings are shared with other Second Brain features.

### `OLLAMA_HOST`
- **Type**: `str`
- **Default**: `"http://127.0.0.1:11434"`
- **Description**: Ollama API server URL
- **Requirements**: Ollama must be running and accessible
- **Example**: `OLLAMA_HOST=http://127.0.0.1:11434`

### `OLLAMA_CHAT_MODEL`
- **Type**: `str`
- **Default**: `"llama3.2:latest"`
- **Description**: Ollama model to use for chat operations
- **Supported Models**: Any Ollama model (llama3.2, mistral, mixtral, etc.)
- **Requirements**: Model must be pulled via `ollama pull <model>`
- **Example**: `OLLAMA_CHAT_MODEL=llama3.2:latest`

### `OLLAMA_TIMEOUT`
- **Type**: `int`
- **Default**: `120` (2 minutes)
- **Description**: Request timeout for Ollama API calls (seconds)
- **Rationale**: Allows time for model inference while preventing hung requests
- **Range**: 60-300 seconds
- **Example**: `OLLAMA_TIMEOUT=120`

### Installing and Running Ollama

```bash
# Install Ollama (macOS/Linux)
curl -fsSL https://ollama.com/install.sh | sh

# Pull the chat model
ollama pull llama3.2:latest

# Start Ollama server (runs on port 11434 by default)
ollama serve

# Verify Ollama is running
curl http://localhost:11434/api/tags
```

## Redis Configuration for Chat

The chat system uses Redis for:
- **Conversation history caching**: Reduces MongoDB queries
- **Query response caching**: Avoids redundant LLM calls
- **Rate limiting**: Tracks user request counts

### Required Redis Settings

These settings are shared with other Second Brain features:

#### `REDIS_URL`
- **Type**: `str`
- **Description**: Complete Redis connection URL
- **Format**: `redis://[username:password@]host:port/db`
- **Example**: `REDIS_URL=redis://localhost:6379/0`

#### `REDIS_HOST`
- **Type**: `str`
- **Default**: `"127.0.0.1"`
- **Description**: Redis server hostname
- **Example**: `REDIS_HOST=127.0.0.1`

#### `REDIS_PORT`
- **Type**: `int`
- **Default**: `6379`
- **Description**: Redis server port
- **Example**: `REDIS_PORT=6379`

#### `REDIS_DB`
- **Type**: `int`
- **Default**: `0`
- **Description**: Redis database number (0-15)
- **Example**: `REDIS_DB=0`

### Redis Cache Keys Used by Chat System

The chat system uses the following Redis key patterns:

- `chat:history:{session_id}` - Conversation history cache
- `chat:cache:{query_hash}` - Query response cache
- `chat:rate:message:{user_id}` - Message rate limit counter
- `chat:rate:session:{user_id}` - Session creation rate limit counter

### Installing and Running Redis

```bash
# Install Redis (macOS)
brew install redis

# Install Redis (Ubuntu/Debian)
sudo apt-get install redis-server

# Start Redis server
redis-server

# Verify Redis is running
redis-cli ping
# Should return: PONG
```

## Environment Setup

### Development Environment (.sbd or .env file)

```bash
# Chat System Configuration
CHAT_ENABLED=true
CHAT_MAX_HISTORY_LENGTH=20
CHAT_HISTORY_CACHE_TTL=3600
CHAT_DEFAULT_TOP_K=5
CHAT_STREAM_TIMEOUT=300

# Rate Limiting
CHAT_ENABLE_RATE_LIMITING=true
CHAT_MESSAGE_RATE_LIMIT=20
CHAT_SESSION_CREATE_LIMIT=5

# Query Caching
CHAT_ENABLE_QUERY_CACHE=true
CHAT_CACHE_TTL=3600

# Input Validation
CHAT_TOKEN_ENCODING=cl100k_base
CHAT_MAX_QUERY_LENGTH=10000
CHAT_MAX_MESSAGE_LENGTH=50000

# Error Recovery
CHAT_LLM_MAX_RETRIES=3
CHAT_LLM_BACKOFF_FACTOR=2.0
CHAT_VECTOR_MAX_RETRIES=2
CHAT_VECTOR_BACKOFF_FACTOR=1.5

# Session Management
CHAT_AUTO_GENERATE_TITLES=true
CHAT_TITLE_MAX_LENGTH=50

# Feedback and Analytics
CHAT_ENABLE_MESSAGE_VOTING=true
CHAT_ENABLE_SESSION_STATISTICS=true

# Ollama Configuration
OLLAMA_HOST=http://127.0.0.1:11434
OLLAMA_CHAT_MODEL=llama3.2:latest
OLLAMA_TIMEOUT=120

# Redis Configuration
REDIS_URL=redis://localhost:6379/0
```

### Production Environment

For production deployments, use environment variables:

```bash
# Production-optimized settings
export CHAT_ENABLED=true
export CHAT_MAX_HISTORY_LENGTH=15
export CHAT_HISTORY_CACHE_TTL=1800
export CHAT_MESSAGE_RATE_LIMIT=10
export CHAT_SESSION_CREATE_LIMIT=3
export CHAT_STREAM_TIMEOUT=180
export CHAT_LLM_MAX_RETRIES=2
export OLLAMA_HOST=http://ollama-service:11434
export REDIS_URL=redis://redis-service:6379/0
```

## Production Recommendations

### Performance Optimization

1. **Conversation History**
   - Set `CHAT_MAX_HISTORY_LENGTH=15` to reduce token usage
   - Increase `CHAT_HISTORY_CACHE_TTL=7200` for high-traffic scenarios

2. **Query Caching**
   - Keep `CHAT_ENABLE_QUERY_CACHE=true` in production
   - Adjust `CHAT_CACHE_TTL` based on content freshness requirements

3. **Rate Limiting**
   - Lower `CHAT_MESSAGE_RATE_LIMIT=10` for stricter abuse prevention
   - Adjust `CHAT_SESSION_CREATE_LIMIT=3` based on expected usage patterns

### Security Considerations

1. **Rate Limiting**
   - Always keep `CHAT_ENABLE_RATE_LIMITING=true` in production
   - Monitor rate limit violations in logs

2. **Input Validation**
   - Keep `CHAT_MAX_QUERY_LENGTH` and `CHAT_MAX_MESSAGE_LENGTH` at reasonable values
   - Monitor for attempts to bypass validation

3. **Resource Protection**
   - Set `CHAT_STREAM_TIMEOUT` to prevent resource exhaustion
   - Configure `CHAT_LLM_MAX_RETRIES` to avoid retry storms

### Monitoring and Observability

1. **Session Statistics**
   - Keep `CHAT_ENABLE_SESSION_STATISTICS=true` for usage analytics
   - Monitor token usage trends via MongoDB queries

2. **Message Voting**
   - Enable `CHAT_ENABLE_MESSAGE_VOTING=true` to collect quality feedback
   - Analyze voting patterns to improve responses

3. **Error Recovery**
   - Monitor retry metrics in application logs
   - Adjust retry settings based on Ollama/Qdrant reliability

### Scaling Considerations

1. **Redis Scaling**
   - Use Redis Cluster for high-availability deployments
   - Consider separate Redis instances for caching vs. rate limiting

2. **Ollama Scaling**
   - Deploy multiple Ollama instances behind a load balancer
   - Use GPU-accelerated instances for better performance

3. **MongoDB Scaling**
   - Ensure proper indexes on chat collections (see migration scripts)
   - Consider sharding for very high message volumes

## Troubleshooting

### Chat System Not Working

1. **Check Ollama Connection**
   ```bash
   curl http://localhost:11434/api/tags
   ```

2. **Verify Redis Connection**
   ```bash
   redis-cli ping
   ```

3. **Check Configuration**
   ```bash
   # Verify CHAT_ENABLED is true
   echo $CHAT_ENABLED
   ```

### Slow Response Times

1. **Reduce History Length**
   - Lower `CHAT_MAX_HISTORY_LENGTH` to reduce context size

2. **Enable Query Caching**
   - Ensure `CHAT_ENABLE_QUERY_CACHE=true`

3. **Optimize Vector Search**
   - Reduce `CHAT_DEFAULT_TOP_K` to retrieve fewer results

### Rate Limit Issues

1. **Adjust Limits**
   - Increase `CHAT_MESSAGE_RATE_LIMIT` for legitimate high-volume users
   - Increase `CHAT_SESSION_CREATE_LIMIT` if users need more sessions

2. **Monitor Redis**
   - Check Redis memory usage
   - Verify rate limit keys are expiring properly

## Additional Resources

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [Ollama Documentation](https://ollama.com/docs)
- [AI SDK Data Stream Protocol](https://sdk.vercel.ai/docs/ai-sdk-ui/stream-protocol)
- [Second Brain Database README](../README.md)

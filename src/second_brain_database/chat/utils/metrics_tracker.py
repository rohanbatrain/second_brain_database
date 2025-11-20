"""Metrics tracking for chat operations.

This module provides comprehensive metrics tracking for chat operations including:
- Messages per second
- Average response time
- Token usage per user/session
- Error rates by type
- Cache hit rates
- Vector search performance

Requirements: Monitoring from design (task 24.2)
"""

import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import RedisManager

logger = get_logger("Second_Brain_Database.Chat.Metrics")


class ChatMetricsTracker:
    """Tracker for chat system metrics.
    
    This class provides methods to track and retrieve various metrics about
    chat system performance and usage. Metrics are stored in Redis for
    real-time access and MongoDB for historical analysis.
    
    Metrics tracked:
    - Messages per second (instantaneous and average)
    - Average response time per session/user
    - Token usage per user/session
    - Error rates by error type
    - Cache hit/miss rates
    - Vector search performance
    - Graph execution times
    
    Attributes:
        redis_manager: Redis manager for real-time metrics storage
        db: MongoDB database for historical metrics
        metrics_ttl: TTL for Redis metrics (default: 1 hour)
    """
    
    def __init__(
        self,
        redis_manager: RedisManager,
        db: Optional[AsyncIOMotorDatabase] = None,
        metrics_ttl: int = 3600
    ):
        """Initialize ChatMetricsTracker.
        
        Args:
            redis_manager: Redis manager for metrics storage
            db: Optional MongoDB database for historical metrics
            metrics_ttl: TTL for Redis metrics in seconds (default: 1 hour)
        """
        self.redis_manager = redis_manager
        self.db = db
        self.metrics_ttl = metrics_ttl
        self._redis_client = redis_manager.get_client()
    
    # Message Rate Tracking
    
    async def track_message(self, session_id: str, user_id: str):
        """Track a new message for rate calculation.
        
        This method increments message counters for calculating messages per second.
        
        Args:
            session_id: ID of the chat session
            user_id: ID of the user sending the message
        """
        try:
            current_time = int(time.time())
            
            # Track global message count
            await self._redis_client.incr("chat:metrics:messages:total")
            
            # Track messages per minute (for rate calculation)
            minute_key = f"chat:metrics:messages:minute:{current_time // 60}"
            await self._redis_client.incr(minute_key)
            await self._redis_client.expire(minute_key, 120)  # Keep for 2 minutes
            
            # Track per-user message count
            user_key = f"chat:metrics:messages:user:{user_id}"
            await self._redis_client.incr(user_key)
            await self._redis_client.expire(user_key, self.metrics_ttl)
            
            # Track per-session message count
            session_key = f"chat:metrics:messages:session:{session_id}"
            await self._redis_client.incr(session_key)
            await self._redis_client.expire(session_key, self.metrics_ttl)
            
            logger.debug(f"Tracked message for session {session_id}, user {user_id}")
            
        except Exception as e:
            logger.error(f"Error tracking message: {e}", exc_info=True)
    
    async def get_messages_per_second(self) -> float:
        """Get current messages per second rate.
        
        Calculates the instantaneous message rate based on the last minute.
        
        Returns:
            float: Messages per second (averaged over last minute)
        """
        try:
            current_time = int(time.time())
            current_minute = current_time // 60
            
            # Get message count for current minute
            minute_key = f"chat:metrics:messages:minute:{current_minute}"
            count = await self._redis_client.get(minute_key)
            
            if count is None:
                return 0.0
            
            # Calculate messages per second (divide by 60)
            messages_per_second = int(count) / 60.0
            
            return messages_per_second
            
        except Exception as e:
            logger.error(f"Error calculating messages per second: {e}", exc_info=True)
            return 0.0
    
    # Response Time Tracking
    
    async def track_response_time(
        self,
        session_id: str,
        user_id: str,
        response_time: float
    ):
        """Track response time for a chat request.
        
        This method stores response times for calculating averages.
        
        Args:
            session_id: ID of the chat session
            user_id: ID of the user
            response_time: Response time in seconds
        """
        try:
            # Track global average response time
            await self._update_average(
                "chat:metrics:response_time:global",
                response_time
            )
            
            # Track per-user average response time
            user_key = f"chat:metrics:response_time:user:{user_id}"
            await self._update_average(user_key, response_time)
            
            # Track per-session average response time
            session_key = f"chat:metrics:response_time:session:{session_id}"
            await self._update_average(session_key, response_time)
            
            logger.debug(
                f"Tracked response time {response_time:.3f}s for "
                f"session {session_id}, user {user_id}"
            )
            
        except Exception as e:
            logger.error(f"Error tracking response time: {e}", exc_info=True)
    
    async def get_average_response_time(
        self,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> float:
        """Get average response time.
        
        Args:
            user_id: Optional user ID to get user-specific average
            session_id: Optional session ID to get session-specific average
            
        Returns:
            float: Average response time in seconds
        """
        try:
            if session_id:
                key = f"chat:metrics:response_time:session:{session_id}"
            elif user_id:
                key = f"chat:metrics:response_time:user:{user_id}"
            else:
                key = "chat:metrics:response_time:global"
            
            avg = await self._get_average(key)
            return avg
            
        except Exception as e:
            logger.error(f"Error getting average response time: {e}", exc_info=True)
            return 0.0
    
    # Token Usage Tracking
    
    async def track_token_usage(
        self,
        session_id: str,
        user_id: str,
        total_tokens: int,
        prompt_tokens: int,
        completion_tokens: int,
        cost: float = 0.0
    ):
        """Track token usage for a chat request.
        
        Args:
            session_id: ID of the chat session
            user_id: ID of the user
            total_tokens: Total tokens used
            prompt_tokens: Prompt tokens used
            completion_tokens: Completion tokens used
            cost: Estimated cost (0.0 for Ollama)
        """
        try:
            # Track global token usage
            await self._redis_client.incrby("chat:metrics:tokens:total", total_tokens)
            await self._redis_client.incrby("chat:metrics:tokens:prompt", prompt_tokens)
            await self._redis_client.incrby("chat:metrics:tokens:completion", completion_tokens)
            
            # Track per-user token usage
            user_total_key = f"chat:metrics:tokens:user:{user_id}:total"
            await self._redis_client.incrby(user_total_key, total_tokens)
            await self._redis_client.expire(user_total_key, self.metrics_ttl)
            
            # Track per-session token usage
            session_total_key = f"chat:metrics:tokens:session:{session_id}:total"
            await self._redis_client.incrby(session_total_key, total_tokens)
            await self._redis_client.expire(session_total_key, self.metrics_ttl)
            
            logger.debug(
                f"Tracked {total_tokens} tokens for session {session_id}, user {user_id}"
            )
            
        except Exception as e:
            logger.error(f"Error tracking token usage: {e}", exc_info=True)
    
    async def get_token_usage(
        self,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, int]:
        """Get token usage statistics.
        
        Args:
            user_id: Optional user ID to get user-specific usage
            session_id: Optional session ID to get session-specific usage
            
        Returns:
            Dict with total_tokens, prompt_tokens, completion_tokens
        """
        try:
            if session_id:
                total_key = f"chat:metrics:tokens:session:{session_id}:total"
                total = await self._redis_client.get(total_key)
                return {
                    "total_tokens": int(total) if total else 0,
                    "prompt_tokens": 0,  # Not tracked per session
                    "completion_tokens": 0  # Not tracked per session
                }
            elif user_id:
                total_key = f"chat:metrics:tokens:user:{user_id}:total"
                total = await self._redis_client.get(total_key)
                return {
                    "total_tokens": int(total) if total else 0,
                    "prompt_tokens": 0,  # Not tracked per user
                    "completion_tokens": 0  # Not tracked per user
                }
            else:
                # Global token usage
                total = await self._redis_client.get("chat:metrics:tokens:total")
                prompt = await self._redis_client.get("chat:metrics:tokens:prompt")
                completion = await self._redis_client.get("chat:metrics:tokens:completion")
                
                return {
                    "total_tokens": int(total) if total else 0,
                    "prompt_tokens": int(prompt) if prompt else 0,
                    "completion_tokens": int(completion) if completion else 0
                }
            
        except Exception as e:
            logger.error(f"Error getting token usage: {e}", exc_info=True)
            return {"total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0}
    
    # Error Rate Tracking
    
    async def track_error(
        self,
        error_type: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None
    ):
        """Track an error occurrence.
        
        Args:
            error_type: Type/category of error (e.g., "llm_timeout", "vector_search_failed")
            session_id: Optional session ID where error occurred
            user_id: Optional user ID associated with error
        """
        try:
            # Track global error count by type
            error_key = f"chat:metrics:errors:{error_type}"
            await self._redis_client.incr(error_key)
            await self._redis_client.expire(error_key, self.metrics_ttl)
            
            # Track total error count
            await self._redis_client.incr("chat:metrics:errors:total")
            
            logger.debug(f"Tracked error: {error_type}")
            
        except Exception as e:
            logger.error(f"Error tracking error metric: {e}", exc_info=True)
    
    async def get_error_rates(self) -> Dict[str, int]:
        """Get error counts by type.
        
        Returns:
            Dict mapping error types to counts
        """
        try:
            # Get all error keys
            error_keys = []
            async for key in self._redis_client.scan_iter("chat:metrics:errors:*"):
                if key != b"chat:metrics:errors:total":
                    error_keys.append(key)
            
            # Get counts for each error type
            error_rates = {}
            for key in error_keys:
                count = await self._redis_client.get(key)
                if count:
                    # Extract error type from key
                    error_type = key.decode().replace("chat:metrics:errors:", "")
                    error_rates[error_type] = int(count)
            
            # Get total error count
            total = await self._redis_client.get("chat:metrics:errors:total")
            error_rates["total"] = int(total) if total else 0
            
            return error_rates
            
        except Exception as e:
            logger.error(f"Error getting error rates: {e}", exc_info=True)
            return {"total": 0}
    
    # Cache Performance Tracking
    
    async def track_cache_hit(self, session_id: str):
        """Track a cache hit."""
        try:
            await self._redis_client.incr("chat:metrics:cache:hits")
            logger.debug(f"Tracked cache hit for session {session_id}")
        except Exception as e:
            logger.error(f"Error tracking cache hit: {e}", exc_info=True)
    
    async def track_cache_miss(self, session_id: str):
        """Track a cache miss."""
        try:
            await self._redis_client.incr("chat:metrics:cache:misses")
            logger.debug(f"Tracked cache miss for session {session_id}")
        except Exception as e:
            logger.error(f"Error tracking cache miss: {e}", exc_info=True)
    
    async def get_cache_hit_rate(self) -> float:
        """Get cache hit rate as a percentage.
        
        Returns:
            float: Cache hit rate (0.0 to 100.0)
        """
        try:
            hits = await self._redis_client.get("chat:metrics:cache:hits")
            misses = await self._redis_client.get("chat:metrics:cache:misses")
            
            hits = int(hits) if hits else 0
            misses = int(misses) if misses else 0
            
            total = hits + misses
            if total == 0:
                return 0.0
            
            hit_rate = (hits / total) * 100.0
            return hit_rate
            
        except Exception as e:
            logger.error(f"Error calculating cache hit rate: {e}", exc_info=True)
            return 0.0
    
    # Vector Search Performance Tracking
    
    async def track_vector_search(
        self,
        session_id: str,
        execution_time: float,
        chunks_found: int
    ):
        """Track vector search performance.
        
        Args:
            session_id: ID of the chat session
            execution_time: Search execution time in seconds
            chunks_found: Number of chunks retrieved
        """
        try:
            # Track average search time
            await self._update_average(
                "chat:metrics:vector_search:time",
                execution_time
            )
            
            # Track average chunks found
            await self._update_average(
                "chat:metrics:vector_search:chunks",
                float(chunks_found)
            )
            
            logger.debug(
                f"Tracked vector search: {execution_time:.3f}s, {chunks_found} chunks"
            )
            
        except Exception as e:
            logger.error(f"Error tracking vector search: {e}", exc_info=True)
    
    async def get_vector_search_stats(self) -> Dict[str, float]:
        """Get vector search performance statistics.
        
        Returns:
            Dict with avg_time and avg_chunks
        """
        try:
            avg_time = await self._get_average("chat:metrics:vector_search:time")
            avg_chunks = await self._get_average("chat:metrics:vector_search:chunks")
            
            return {
                "avg_time": avg_time,
                "avg_chunks": avg_chunks
            }
            
        except Exception as e:
            logger.error(f"Error getting vector search stats: {e}", exc_info=True)
            return {"avg_time": 0.0, "avg_chunks": 0.0}
    
    # Graph Execution Time Tracking
    
    async def track_graph_execution(
        self,
        graph_name: str,
        execution_time: float,
        success: bool
    ):
        """Track graph execution time and success rate.
        
        Args:
            graph_name: Name of the graph (VectorRAG, GeneralResponse, MasterWorkflow)
            execution_time: Execution time in seconds
            success: Whether execution was successful
        """
        try:
            # Track average execution time
            time_key = f"chat:metrics:graph:{graph_name}:time"
            await self._update_average(time_key, execution_time)
            
            # Track success/failure counts
            if success:
                success_key = f"chat:metrics:graph:{graph_name}:success"
                await self._redis_client.incr(success_key)
                await self._redis_client.expire(success_key, self.metrics_ttl)
            else:
                failure_key = f"chat:metrics:graph:{graph_name}:failure"
                await self._redis_client.incr(failure_key)
                await self._redis_client.expire(failure_key, self.metrics_ttl)
            
            logger.debug(
                f"Tracked {graph_name} execution: {execution_time:.3f}s, "
                f"success={success}"
            )
            
        except Exception as e:
            logger.error(f"Error tracking graph execution: {e}", exc_info=True)
    
    async def get_graph_stats(self, graph_name: str) -> Dict[str, any]:
        """Get statistics for a specific graph.
        
        Args:
            graph_name: Name of the graph
            
        Returns:
            Dict with avg_time, success_count, failure_count, success_rate
        """
        try:
            time_key = f"chat:metrics:graph:{graph_name}:time"
            success_key = f"chat:metrics:graph:{graph_name}:success"
            failure_key = f"chat:metrics:graph:{graph_name}:failure"
            
            avg_time = await self._get_average(time_key)
            success_count = await self._redis_client.get(success_key)
            failure_count = await self._redis_client.get(failure_key)
            
            success_count = int(success_count) if success_count else 0
            failure_count = int(failure_count) if failure_count else 0
            
            total = success_count + failure_count
            success_rate = (success_count / total * 100.0) if total > 0 else 0.0
            
            return {
                "avg_time": avg_time,
                "success_count": success_count,
                "failure_count": failure_count,
                "success_rate": success_rate
            }
            
        except Exception as e:
            logger.error(f"Error getting graph stats: {e}", exc_info=True)
            return {
                "avg_time": 0.0,
                "success_count": 0,
                "failure_count": 0,
                "success_rate": 0.0
            }
    
    # Helper Methods
    
    async def _update_average(self, key: str, value: float):
        """Update a running average in Redis.
        
        Uses a simple moving average approach with count and sum.
        
        Args:
            key: Redis key for the average
            value: New value to include in average
        """
        try:
            count_key = f"{key}:count"
            sum_key = f"{key}:sum"
            
            # Increment count
            await self._redis_client.incr(count_key)
            await self._redis_client.expire(count_key, self.metrics_ttl)
            
            # Add to sum
            await self._redis_client.incrbyfloat(sum_key, value)
            await self._redis_client.expire(sum_key, self.metrics_ttl)
            
        except Exception as e:
            logger.error(f"Error updating average for {key}: {e}", exc_info=True)
    
    async def _get_average(self, key: str) -> float:
        """Get a running average from Redis.
        
        Args:
            key: Redis key for the average
            
        Returns:
            float: Average value
        """
        try:
            count_key = f"{key}:count"
            sum_key = f"{key}:sum"
            
            count = await self._redis_client.get(count_key)
            total = await self._redis_client.get(sum_key)
            
            if not count or not total:
                return 0.0
            
            count = int(count)
            total = float(total)
            
            if count == 0:
                return 0.0
            
            return total / count
            
        except Exception as e:
            logger.error(f"Error getting average for {key}: {e}", exc_info=True)
            return 0.0
    
    # Summary Methods
    
    async def get_metrics_summary(self) -> Dict[str, any]:
        """Get a comprehensive summary of all metrics.
        
        Returns:
            Dict with all tracked metrics
        """
        try:
            summary = {
                "messages_per_second": await self.get_messages_per_second(),
                "average_response_time": await self.get_average_response_time(),
                "token_usage": await self.get_token_usage(),
                "error_rates": await self.get_error_rates(),
                "cache_hit_rate": await self.get_cache_hit_rate(),
                "vector_search": await self.get_vector_search_stats(),
                "graphs": {
                    "VectorRAGGraph": await self.get_graph_stats("VectorRAGGraph"),
                    "GeneralResponseGraph": await self.get_graph_stats("GeneralResponseGraph"),
                    "MasterWorkflowGraph": await self.get_graph_stats("MasterWorkflowGraph")
                }
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"Error getting metrics summary: {e}", exc_info=True)
            return {}


# Global metrics tracker instance (initialized on first use)
_metrics_tracker: Optional[ChatMetricsTracker] = None


def get_metrics_tracker(
    redis_manager: RedisManager,
    db: Optional[AsyncIOMotorDatabase] = None
) -> ChatMetricsTracker:
    """Get or create global metrics tracker instance.
    
    Args:
        redis_manager: Redis manager for metrics storage
        db: Optional MongoDB database for historical metrics
        
    Returns:
        ChatMetricsTracker: Global metrics tracker instance
    """
    global _metrics_tracker
    
    if _metrics_tracker is None:
        _metrics_tracker = ChatMetricsTracker(
            redis_manager=redis_manager,
            db=db
        )
    
    return _metrics_tracker

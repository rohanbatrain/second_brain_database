"""Query cache manager for chat system."""

import hashlib
import json
from typing import Dict, Optional

from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import RedisManager

logger = get_logger()


class QueryCacheManager:
    """
    Manages query response caching to reduce redundant LLM calls.
    
    This manager caches complete query responses (text + metadata) in Redis
    to avoid re-processing identical queries within a time window.
    """

    def __init__(self, redis_manager: RedisManager):
        """
        Initialize the query cache manager.
        
        Args:
            redis_manager: Redis manager instance for caching
        """
        self.redis_manager = redis_manager
        self.cache_ttl = 3600  # 1 hour TTL for cached responses
        self.logger = logger

    def _generate_cache_key(self, query: str, kb_id: Optional[str] = None) -> str:
        """
        Generate cache key from query and knowledge base ID.
        
        Uses SHA256 hashing to create a consistent, collision-resistant key
        from the query text and optional knowledge base identifier.
        
        Args:
            query: The user query text
            kb_id: Optional knowledge base ID for context-specific caching
            
        Returns:
            Redis cache key in format "chat:cache:{hash}"
        """
        # Combine query and kb_id for cache key generation
        content = f"{query}:{kb_id or 'general'}"
        
        # Generate SHA256 hash for consistent key generation
        hash_digest = hashlib.sha256(content.encode()).hexdigest()
        
        return f"chat:cache:{hash_digest}"

    async def get_cached_response(
        self, query: str, kb_id: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Check if query was recently answered and return cached response.
        
        Args:
            query: The user query text
            kb_id: Optional knowledge base ID for context-specific caching
            
        Returns:
            Cached response dictionary if found, None otherwise
        """
        cache_key = self._generate_cache_key(query, kb_id)
        
        try:
            cached = await self.redis_manager.get(cache_key)
            
            if cached:
                self.logger.debug(
                    f"[QueryCacheManager] Cache hit for query hash: "
                    f"{cache_key.split(':')[-1][:16]}..."
                )
                # Handle both JSON string and dict responses
                return cached if isinstance(cached, dict) else json.loads(cached)
            
            self.logger.debug(
                f"[QueryCacheManager] Cache miss for query hash: "
                f"{cache_key.split(':')[-1][:16]}..."
            )
            return None
            
        except Exception as e:
            self.logger.warning(
                f"[QueryCacheManager] Failed to retrieve cached response: {e}. "
                "Continuing without cache."
            )
            return None

    async def cache_response(
        self, query: str, response: Dict, kb_id: Optional[str] = None
    ) -> None:
        """
        Cache response for 1 hour to reduce redundant LLM calls.
        
        Args:
            query: The user query text
            response: Complete response dictionary (text + metadata)
            kb_id: Optional knowledge base ID for context-specific caching
        """
        cache_key = self._generate_cache_key(query, kb_id)
        
        try:
            await self.redis_manager.set_json(cache_key, response, expiry=self.cache_ttl)
            
            self.logger.debug(
                f"[QueryCacheManager] Cached response for query hash: "
                f"{cache_key.split(':')[-1][:16]}... with TTL {self.cache_ttl}s"
            )
            
        except Exception as e:
            self.logger.warning(
                f"[QueryCacheManager] Failed to cache response: {e}. "
                "Continuing without cache."
            )

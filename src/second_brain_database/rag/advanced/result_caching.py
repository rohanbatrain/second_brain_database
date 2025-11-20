"""
Advanced RAG Features - Result Caching System

Sophisticated caching system for RAG query results with TTL management,
cache invalidation strategies, intelligent cache warming, and performance
optimization for frequently accessed content.
"""

import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
import hashlib
import json
import pickle
from typing import Any, Dict, List, Optional, Tuple, Union
import zlib

from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.rag.core.exceptions import RAGError
from second_brain_database.rag.core.types import DocumentChunk, QueryRequest, QueryResponse

logger = get_logger()


class CacheStrategy(str, Enum):
    """Cache invalidation strategies."""
    TTL = "ttl"                          # Time-based expiration
    LRU = "lru"                          # Least recently used
    LFU = "lfu"                          # Least frequently used
    ADAPTIVE = "adaptive"                # Adaptive based on access patterns
    CONTENT_BASED = "content_based"      # Based on content changes


class CacheLevel(str, Enum):
    """Cache levels for different types of data."""
    QUERY_RESULT = "query_result"        # Full query results
    CHUNK_EMBEDDING = "chunk_embedding"  # Document chunk embeddings
    SYNTHESIS_RESULT = "synthesis_result" # Synthesis results
    QUERY_PLAN = "query_plan"            # Query execution plans
    USER_CONTEXT = "user_context"        # User-specific context


@dataclass
class CacheEntry:
    """A cache entry with metadata."""
    key: str
    data: Any
    cache_level: CacheLevel
    created_at: datetime
    last_accessed: datetime
    access_count: int
    ttl_seconds: int
    size_bytes: int
    tags: List[str]
    metadata: Dict[str, Any]


@dataclass
class CacheStats:
    """Cache performance statistics."""
    total_entries: int
    total_size_bytes: int
    hit_rate: float
    miss_rate: float
    avg_access_time_ms: float
    eviction_count: int
    cache_levels: Dict[str, int]
    top_accessed_keys: List[Tuple[str, int]]


class IntelligentCacheManager:
    """
    Intelligent caching system for RAG operations.
    
    Provides sophisticated caching with multiple strategies, automatic
    invalidation, cache warming, and performance optimization.
    """
    
    def __init__(
        self,
        default_ttl_seconds: int = 3600,  # 1 hour
        max_cache_size_mb: int = 500,     # 500 MB
        compression_enabled: bool = True,
        warm_cache_enabled: bool = True
    ):
        """
        Initialize intelligent cache manager.
        
        Args:
            default_ttl_seconds: Default TTL for cache entries
            max_cache_size_mb: Maximum cache size in MB
            compression_enabled: Whether to compress cached data
            warm_cache_enabled: Whether to enable cache warming
        """
        self.default_ttl = default_ttl_seconds
        self.max_cache_size = max_cache_size_mb * 1024 * 1024  # Convert to bytes
        self.compression_enabled = compression_enabled
        self.warm_cache_enabled = warm_cache_enabled
        
        # Cache prefixes for different levels
        self.cache_prefixes = {
            CacheLevel.QUERY_RESULT: "rag:query:",
            CacheLevel.CHUNK_EMBEDDING: "rag:chunk:",
            CacheLevel.SYNTHESIS_RESULT: "rag:synthesis:",
            CacheLevel.QUERY_PLAN: "rag:plan:",
            CacheLevel.USER_CONTEXT: "rag:context:"
        }
        
        # TTL configurations for different cache levels
        self.ttl_configs = {
            CacheLevel.QUERY_RESULT: 3600,      # 1 hour
            CacheLevel.CHUNK_EMBEDDING: 86400,  # 24 hours
            CacheLevel.SYNTHESIS_RESULT: 7200,  # 2 hours
            CacheLevel.QUERY_PLAN: 1800,        # 30 minutes
            CacheLevel.USER_CONTEXT: 3600       # 1 hour
        }
        
        # Statistics tracking
        self.stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "access_times": [],
            "cache_size": 0
        }
        
        logger.info("Initialized intelligent cache manager")
    
    async def get(
        self,
        key: str,
        cache_level: CacheLevel,
        user_id: Optional[str] = None
    ) -> Optional[Any]:
        """
        Get cached data.
        
        Args:
            key: Cache key
            cache_level: Cache level
            user_id: Optional user ID for user-specific caching
            
        Returns:
            Cached data or None if not found
        """
        try:
            start_time = datetime.utcnow()
            
            # Generate full cache key
            full_key = self._generate_cache_key(key, cache_level, user_id)
            
            # Get from Redis
            cached_data = await redis_manager.get(full_key)
            
            access_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            self.stats["access_times"].append(access_time)
            
            if cached_data:
                self.stats["hits"] += 1
                
                # Update access metadata
                await self._update_access_metadata(full_key)
                
                # Deserialize data
                data = await self._deserialize_data(cached_data)
                
                logger.debug(f"Cache hit for key: {key} (level: {cache_level})")
                return data
            else:
                self.stats["misses"] += 1
                logger.debug(f"Cache miss for key: {key} (level: {cache_level})")
                return None
                
        except Exception as e:
            logger.error(f"Cache get failed for key {key}: {e}")
            self.stats["misses"] += 1
            return None
    
    async def set(
        self,
        key: str,
        data: Any,
        cache_level: CacheLevel,
        ttl_seconds: Optional[int] = None,
        tags: Optional[List[str]] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Set cached data.
        
        Args:
            key: Cache key
            data: Data to cache
            cache_level: Cache level
            ttl_seconds: TTL override
            tags: Cache tags for invalidation
            user_id: Optional user ID for user-specific caching
            metadata: Optional metadata
            
        Returns:
            True if cached successfully
        """
        try:
            # Generate full cache key
            full_key = self._generate_cache_key(key, cache_level, user_id)
            
            # Use configured TTL or default
            ttl = ttl_seconds or self.ttl_configs.get(cache_level, self.default_ttl)
            
            # Serialize data
            serialized_data = await self._serialize_data(data)
            
            # Create cache entry metadata
            entry_metadata = {
                "cache_level": cache_level,
                "created_at": datetime.utcnow().isoformat(),
                "last_accessed": datetime.utcnow().isoformat(),
                "access_count": 0,
                "size_bytes": len(serialized_data),
                "tags": tags or [],
                "metadata": metadata or {}
            }
            
            # Check cache size limits
            if not await self._check_cache_limits(len(serialized_data)):
                await self._evict_cache_entries()
            
            # Store in Redis with TTL
            await redis_manager.set(
                full_key,
                serialized_data,
                ex=ttl
            )
            
            # Store metadata
            await redis_manager.set(
                f"{full_key}:meta",
                json.dumps(entry_metadata),
                ex=ttl
            )
            
            # Update tags index for invalidation
            if tags:
                await self._update_tags_index(full_key, tags, ttl)
            
            # Update statistics
            self.stats["cache_size"] += len(serialized_data)
            
            logger.debug(
                f"Cached data for key: {key} (level: {cache_level}, "
                f"size: {len(serialized_data)} bytes, TTL: {ttl}s)"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Cache set failed for key {key}: {e}")
            return False
    
    async def invalidate(
        self,
        key: Optional[str] = None,
        cache_level: Optional[CacheLevel] = None,
        tags: Optional[List[str]] = None,
        user_id: Optional[str] = None,
        pattern: Optional[str] = None
    ) -> int:
        """
        Invalidate cached data.
        
        Args:
            key: Specific cache key to invalidate
            cache_level: Cache level to invalidate
            tags: Tags to invalidate
            user_id: User-specific invalidation
            pattern: Pattern-based invalidation
            
        Returns:
            Number of entries invalidated
        """
        try:
            invalidated_count = 0
            
            if key and cache_level:
                # Invalidate specific key
                full_key = self._generate_cache_key(key, cache_level, user_id)
                await redis_manager.delete(full_key, f"{full_key}:meta")
                invalidated_count = 1
                
            elif tags:
                # Invalidate by tags
                invalidated_count = await self._invalidate_by_tags(tags)
                
            elif pattern:
                # Invalidate by pattern
                invalidated_count = await self._invalidate_by_pattern(pattern)
                
            elif cache_level:
                # Invalidate entire cache level
                prefix = self.cache_prefixes[cache_level]
                pattern = f"{prefix}*"
                invalidated_count = await self._invalidate_by_pattern(pattern)
            
            logger.info(f"Invalidated {invalidated_count} cache entries")
            return invalidated_count
            
        except Exception as e:
            logger.error(f"Cache invalidation failed: {e}")
            return 0
    
    async def warm_cache(
        self,
        queries: List[str],
        vector_store_service,
        llm_service,
        user_id: Optional[str] = None
    ) -> int:
        """
        Warm cache with frequently accessed queries.
        
        Args:
            queries: List of queries to warm
            vector_store_service: Vector store service
            llm_service: LLM service
            user_id: Optional user ID
            
        Returns:
            Number of entries warmed
        """
        if not self.warm_cache_enabled:
            return 0
        
        try:
            warmed_count = 0
            
            for query in queries:
                try:
                    # Check if already cached
                    cache_key = self._generate_query_cache_key(query, user_id)
                    existing = await self.get(cache_key, CacheLevel.QUERY_RESULT, user_id)
                    
                    if not existing:
                        # Execute query and cache result
                        search_results = await vector_store_service.search(
                            query=query,
                            top_k=5,
                            user_id=user_id or "system"
                        )
                        
                        # Cache the results
                        await self.set(
                            cache_key,
                            search_results,
                            CacheLevel.QUERY_RESULT,
                            tags=["warm_cache"],
                            user_id=user_id
                        )
                        
                        warmed_count += 1
                        
                        # Small delay to avoid overwhelming the system
                        await asyncio.sleep(0.1)
                        
                except Exception as e:
                    logger.warning(f"Failed to warm cache for query '{query}': {e}")
                    continue
            
            logger.info(f"Warmed cache with {warmed_count} queries")
            return warmed_count
            
        except Exception as e:
            logger.error(f"Cache warming failed: {e}")
            return 0
    
    async def get_stats(self) -> CacheStats:
        """Get cache performance statistics."""
        try:
            total_hits = self.stats["hits"]
            total_misses = self.stats["misses"]
            total_requests = total_hits + total_misses
            
            hit_rate = (total_hits / total_requests) if total_requests > 0 else 0.0
            miss_rate = 1.0 - hit_rate
            
            avg_access_time = (
                sum(self.stats["access_times"]) / len(self.stats["access_times"])
                if self.stats["access_times"] else 0.0
            )
            
            # Get cache level statistics
            cache_level_stats = {}
            for level in CacheLevel:
                prefix = self.cache_prefixes[level]
                keys = await redis_manager.keys(f"{prefix}*")
                cache_level_stats[level.value] = len([k for k in keys if not k.endswith(":meta")])
            
            # Get top accessed keys (simplified - in production, maintain proper counters)
            top_accessed = []
            
            return CacheStats(
                total_entries=sum(cache_level_stats.values()),
                total_size_bytes=self.stats["cache_size"],
                hit_rate=hit_rate,
                miss_rate=miss_rate,
                avg_access_time_ms=avg_access_time,
                eviction_count=self.stats["evictions"],
                cache_levels=cache_level_stats,
                top_accessed_keys=top_accessed
            )
            
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return CacheStats(
                total_entries=0,
                total_size_bytes=0,
                hit_rate=0.0,
                miss_rate=1.0,
                avg_access_time_ms=0.0,
                eviction_count=0,
                cache_levels={},
                top_accessed_keys=[]
            )
    
    async def clear_cache(
        self,
        cache_level: Optional[CacheLevel] = None,
        user_id: Optional[str] = None
    ) -> int:
        """
        Clear cache entries.
        
        Args:
            cache_level: Specific cache level to clear
            user_id: User-specific cache to clear
            
        Returns:
            Number of entries cleared
        """
        try:
            if cache_level:
                return await self.invalidate(cache_level=cache_level, user_id=user_id)
            else:
                # Clear all cache levels
                total_cleared = 0
                for level in CacheLevel:
                    cleared = await self.invalidate(cache_level=level, user_id=user_id)
                    total_cleared += cleared
                
                # Reset statistics
                self.stats = {
                    "hits": 0,
                    "misses": 0,
                    "evictions": 0,
                    "access_times": [],
                    "cache_size": 0
                }
                
                return total_cleared
                
        except Exception as e:
            logger.error(f"Cache clear failed: {e}")
            return 0
    
    def _generate_cache_key(
        self,
        key: str,
        cache_level: CacheLevel,
        user_id: Optional[str] = None
    ) -> str:
        """Generate full cache key."""
        prefix = self.cache_prefixes[cache_level]
        
        if user_id:
            return f"{prefix}{user_id}:{self._hash_key(key)}"
        else:
            return f"{prefix}{self._hash_key(key)}"
    
    def _generate_query_cache_key(self, query: str, user_id: Optional[str] = None) -> str:
        """Generate cache key for a query."""
        return self._hash_key(f"query:{query}{user_id or ''}")
    
    def _hash_key(self, key: str) -> str:
        """Generate hash for cache key."""
        return hashlib.sha256(key.encode()).hexdigest()[:16]
    
    async def _serialize_data(self, data: Any) -> bytes:
        """Serialize data for caching."""
        try:
            # Convert to JSON-serializable format if needed
            if hasattr(data, '__dict__'):
                data = asdict(data) if hasattr(data, '__dataclass_fields__') else data.__dict__
            
            serialized = pickle.dumps(data)
            
            if self.compression_enabled:
                serialized = zlib.compress(serialized)
            
            return serialized
            
        except Exception as e:
            logger.error(f"Data serialization failed: {e}")
            raise
    
    async def _deserialize_data(self, data: bytes) -> Any:
        """Deserialize cached data."""
        try:
            if self.compression_enabled:
                data = zlib.decompress(data)
            
            return pickle.loads(data)
            
        except Exception as e:
            logger.error(f"Data deserialization failed: {e}")
            raise
    
    async def _update_access_metadata(self, cache_key: str):
        """Update access metadata for a cache entry."""
        try:
            meta_key = f"{cache_key}:meta"
            metadata_str = await redis_manager.get(meta_key)
            
            if metadata_str:
                metadata = json.loads(metadata_str)
                metadata["last_accessed"] = datetime.utcnow().isoformat()
                metadata["access_count"] = metadata.get("access_count", 0) + 1
                
                # Update metadata with same TTL as original
                ttl = await redis_manager.ttl(cache_key)
                if ttl > 0:
                    await redis_manager.set(meta_key, json.dumps(metadata), ex=ttl)
                    
        except Exception as e:
            logger.warning(f"Failed to update access metadata: {e}")
    
    async def _check_cache_limits(self, new_entry_size: int) -> bool:
        """Check if new entry fits within cache limits."""
        try:
            current_size = self.stats["cache_size"]
            return (current_size + new_entry_size) <= self.max_cache_size
            
        except Exception:
            return True  # Allow caching if check fails
    
    async def _evict_cache_entries(self, target_size: Optional[int] = None):
        """Evict cache entries to make space."""
        try:
            target_size = target_size or (self.max_cache_size * 0.8)  # 80% of max size
            
            # Get all cache keys with metadata
            all_keys = []
            for level in CacheLevel:
                prefix = self.cache_prefixes[level]
                keys = await redis_manager.keys(f"{prefix}*")
                cache_keys = [k for k in keys if not k.endswith(":meta")]
                
                for key in cache_keys:
                    meta_key = f"{key}:meta"
                    metadata_str = await redis_manager.get(meta_key)
                    if metadata_str:
                        metadata = json.loads(metadata_str)
                        all_keys.append((key, metadata))
            
            # Sort by access patterns (LRU strategy)
            all_keys.sort(key=lambda x: (
                x[1].get("access_count", 0),
                x[1].get("last_accessed", "1970-01-01")
            ))
            
            # Evict entries until target size is reached
            evicted_count = 0
            current_size = self.stats["cache_size"]
            
            for key, metadata in all_keys:
                if current_size <= target_size:
                    break
                
                entry_size = metadata.get("size_bytes", 0)
                await redis_manager.delete(key, f"{key}:meta")
                
                current_size -= entry_size
                evicted_count += 1
                self.stats["evictions"] += 1
            
            self.stats["cache_size"] = current_size
            
            if evicted_count > 0:
                logger.info(f"Evicted {evicted_count} cache entries")
                
        except Exception as e:
            logger.error(f"Cache eviction failed: {e}")
    
    async def _update_tags_index(self, cache_key: str, tags: List[str], ttl: int):
        """Update tags index for cache invalidation."""
        try:
            for tag in tags:
                tag_key = f"rag:tags:{tag}"
                await redis_manager.sadd(tag_key, cache_key)
                await redis_manager.expire(tag_key, ttl)
                
        except Exception as e:
            logger.warning(f"Failed to update tags index: {e}")
    
    async def _invalidate_by_tags(self, tags: List[str]) -> int:
        """Invalidate cache entries by tags."""
        try:
            invalidated_count = 0
            
            for tag in tags:
                tag_key = f"rag:tags:{tag}"
                cache_keys = await redis_manager.smembers(tag_key)
                
                if cache_keys:
                    # Delete cache entries and their metadata
                    keys_to_delete = []
                    for cache_key in cache_keys:
                        keys_to_delete.extend([cache_key, f"{cache_key}:meta"])
                    
                    await redis_manager.delete(*keys_to_delete)
                    invalidated_count += len(cache_keys)
                
                # Remove tag index
                await redis_manager.delete(tag_key)
            
            return invalidated_count
            
        except Exception as e:
            logger.error(f"Tag-based invalidation failed: {e}")
            return 0
    
    async def _invalidate_by_pattern(self, pattern: str) -> int:
        """Invalidate cache entries by pattern."""
        try:
            keys = await redis_manager.keys(pattern)
            
            if keys:
                # Include metadata keys
                all_keys = []
                for key in keys:
                    all_keys.extend([key, f"{key}:meta"])
                
                await redis_manager.delete(*all_keys)
                return len(keys)
            
            return 0
            
        except Exception as e:
            logger.error(f"Pattern-based invalidation failed: {e}")
            return 0
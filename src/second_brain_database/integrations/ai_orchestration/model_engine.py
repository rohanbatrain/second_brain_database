"""
Enhanced Model Engine with Performance Optimization and Caching

This module provides an optimized model engine for AI response generation using Ollama
with intelligent caching, connection pooling, and performance monitoring.

Features:
- Connection pooling for multiple Ollama instances
- Response caching with Redis integration
- Model warming for reduced latency
- Performance monitoring and metrics
- Intelligent cache invalidation
- Streaming token generation with optimization
"""

from typing import Dict, Any, List, Optional, AsyncGenerator, Tuple
from datetime import datetime, timezone, timedelta
import uuid
import asyncio
import hashlib
import json
import time
import re
from dataclasses import dataclass

from ...integrations.ollama import OllamaClient
from ...managers.redis_manager import redis_manager
from ...managers.logging_manager import get_logger
from ...config import settings

logger = get_logger(prefix="[ModelEngine]")


@dataclass
class ModelResponse:
    """Model response with metadata."""
    content: str
    model: str
    tokens_used: int
    response_time_ms: float
    cached: bool
    timestamp: datetime


@dataclass
class PerformanceMetrics:
    """Performance metrics for model operations."""
    total_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    avg_response_time_ms: float = 0.0
    total_tokens_generated: int = 0
    errors: int = 0
    last_updated: datetime = None


class ModelSelector:
    """
    Intelligent model selection based on query characteristics.
    
    Automatically selects the most appropriate model based on:
    - Query complexity and type
    - Required reasoning capabilities
    - Performance requirements
    """
    
    def __init__(self):
        self.logger = get_logger(prefix="[ModelSelector]")
        
        # Patterns that indicate need for reasoning model
        self.reasoning_patterns = [
            r'\b(why|how|explain|analyze|compare|evaluate|reason|think|solve|calculate)\b',
            r'\b(step by step|step-by-step|reasoning|logic|proof|derive)\b',
            r'\b(problem|equation|math|formula|algorithm)\b',
            r'\b(complex|difficult|challenging|intricate)\b',
            r'\?.*\?',  # Multiple questions
            r'\b(if.*then|given.*find|assume.*prove)\b'
        ]
        
        # Patterns that indicate simple/fast queries
        self.simple_patterns = [
            r'^\b(hi|hello|hey|thanks|thank you|yes|no|ok|okay)\b',
            r'^\b(what is|define|meaning of)\b.*\?$',
            r'^\b(list|name|tell me)\b.*\?$',
            r'^.{1,50}$',  # Very short queries
        ]
    
    def select_model(self, prompt: str, context: Optional[Dict] = None) -> str:
        """
        Select the most appropriate model for the given prompt.
        
        Args:
            prompt: The input prompt
            context: Optional context information
            
        Returns:
            Selected model name
        """
        if not settings.OLLAMA_AUTO_MODEL_SELECTION:
            return settings.OLLAMA_MODEL
        
        prompt_lower = prompt.lower()
        
        # Check for reasoning patterns
        reasoning_score = sum(1 for pattern in self.reasoning_patterns 
                            if re.search(pattern, prompt_lower, re.IGNORECASE))
        
        # Check for simple patterns
        simple_score = sum(1 for pattern in self.simple_patterns 
                         if re.search(pattern, prompt_lower, re.IGNORECASE))
        
        # Consider prompt length and complexity
        word_count = len(prompt.split())
        complexity_indicators = len(re.findall(r'[.!?]', prompt))
        
        # Decision logic
        if reasoning_score > 0 or (word_count > 20 and complexity_indicators > 1):
            selected_model = settings.OLLAMA_REASONING_MODEL
            self.logger.debug(f"Selected reasoning model '{selected_model}' for complex query")
        elif simple_score > 0 or word_count < 10:
            selected_model = settings.OLLAMA_FAST_MODEL
            self.logger.debug(f"Selected fast model '{selected_model}' for simple query")
        else:
            # Default to configured model
            selected_model = settings.OLLAMA_MODEL
            self.logger.debug(f"Selected default model '{selected_model}'")
        
        # Ensure selected model is available
        available_models = settings.ollama_available_models_list
        if selected_model not in available_models:
            self.logger.warning(f"Selected model '{selected_model}' not available, using default")
            selected_model = settings.OLLAMA_MODEL
        
        return selected_model
    
    def get_model_info(self, model_name: str) -> Dict[str, Any]:
        """Get information about a specific model."""
        model_info = {
            "name": model_name,
            "type": "general",
            "capabilities": ["text_generation", "conversation"],
            "performance": "medium"
        }
        
        if "deepseek-r1" in model_name.lower():
            model_info.update({
                "type": "reasoning",
                "capabilities": ["text_generation", "conversation", "reasoning", "problem_solving"],
                "performance": "high_quality",
                "specialization": "Complex reasoning and problem-solving tasks"
            })
        elif "gemma" in model_name.lower():
            model_info.update({
                "type": "fast",
                "capabilities": ["text_generation", "conversation"],
                "performance": "fast",
                "specialization": "Quick responses and general conversation"
            })
        
        return model_info


class ModelCache:
    """
    Intelligent caching system for AI model responses.
    
    Provides TTL-based caching with intelligent invalidation and
    performance optimization for frequently requested prompts.
    """
    
    def __init__(self):
        self.logger = get_logger(prefix="[ModelCache]")
        self.cache_prefix = "ai:model:cache"
        self.metrics_key = "ai:model:metrics"
        
    def _generate_cache_key(self, prompt: str, model: str, temperature: float) -> str:
        """Generate cache key for prompt/model/temperature combination."""
        # Create a hash of the prompt + model + temperature for consistent caching
        content = f"{prompt}:{model}:{temperature}"
        hash_obj = hashlib.sha256(content.encode('utf-8'))
        return f"{self.cache_prefix}:{hash_obj.hexdigest()[:16]}"
    
    async def get_cached_response(
        self, 
        prompt: str, 
        model: str, 
        temperature: float
    ) -> Optional[ModelResponse]:
        """
        Get cached response if available.
        
        Args:
            prompt: Input prompt
            model: Model name
            temperature: Model temperature
            
        Returns:
            Cached ModelResponse or None if not found
        """
        try:
            redis = await redis_manager.get_redis()
            cache_key = self._generate_cache_key(prompt, model, temperature)
            
            cached_data = await redis.get(cache_key)
            if cached_data:
                data = json.loads(cached_data)
                return ModelResponse(
                    content=data["content"],
                    model=data["model"],
                    tokens_used=data["tokens_used"],
                    response_time_ms=data["response_time_ms"],
                    cached=True,
                    timestamp=datetime.fromisoformat(data["timestamp"])
                )
                
        except Exception as e:
            self.logger.error("Failed to get cached response: %s", e)
            
        return None
    
    async def cache_response(
        self,
        prompt: str,
        model: str,
        temperature: float,
        response: ModelResponse,
        ttl: int = None
    ) -> bool:
        """
        Cache a model response.
        
        Args:
            prompt: Input prompt
            model: Model name
            temperature: Model temperature
            response: ModelResponse to cache
            ttl: Time to live in seconds (uses config default if None)
            
        Returns:
            True if cached successfully, False otherwise
        """
        try:
            redis = await redis_manager.get_redis()
            cache_key = self._generate_cache_key(prompt, model, temperature)
            
            cache_data = {
                "content": response.content,
                "model": response.model,
                "tokens_used": response.tokens_used,
                "response_time_ms": response.response_time_ms,
                "timestamp": response.timestamp.isoformat()
            }
            
            cache_ttl = ttl or settings.AI_CACHE_TTL
            await redis.setex(cache_key, cache_ttl, json.dumps(cache_data))
            
            self.logger.debug("Cached response for prompt hash %s", cache_key[-8:])
            return True
            
        except Exception as e:
            self.logger.error("Failed to cache response: %s", e)
            return False
    
    async def invalidate_cache_pattern(self, pattern: str) -> int:
        """
        Invalidate cache entries matching a pattern.
        
        Args:
            pattern: Redis pattern to match keys
            
        Returns:
            Number of keys invalidated
        """
        try:
            redis = await redis_manager.get_redis()
            keys = await redis.keys(f"{self.cache_prefix}:{pattern}")
            
            if keys:
                await redis.delete(*keys)
                self.logger.info("Invalidated %d cache entries matching pattern %s", len(keys), pattern)
                return len(keys)
                
        except Exception as e:
            self.logger.error("Failed to invalidate cache pattern %s: %s", pattern, e)
            
        return 0
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        try:
            redis = await redis_manager.get_redis()
            
            # Count total cache entries
            cache_keys = await redis.keys(f"{self.cache_prefix}:*")
            total_entries = len(cache_keys)
            
            # Get memory usage info if available
            memory_info = {}
            try:
                info = await redis.info("memory")
                memory_info = {
                    "used_memory": info.get("used_memory", 0),
                    "used_memory_human": info.get("used_memory_human", "0B")
                }
            except:
                pass
            
            return {
                "total_entries": total_entries,
                "cache_prefix": self.cache_prefix,
                "memory_info": memory_info,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            self.logger.error("Failed to get cache stats: %s", e)
            return {"error": str(e)}


class ModelEngine:
    """
    Enhanced model engine with performance optimization and caching.
    
    Provides connection pooling, intelligent caching, model warming,
    and comprehensive performance monitoring for Ollama integration.
    """
    
    def __init__(self):
        """Initialize the enhanced model engine."""
        self.logger = get_logger(prefix="[ModelEngine]")
        
        # Initialize configuration
        self.config = settings.ai_model_config
        self.performance_config = settings.ai_performance_config
        
        # Initialize client pool
        self.client_pool: List[OllamaClient] = []
        self.current_client_index = 0
        self.pool_lock = asyncio.Lock()
        
        # Initialize caching
        self.cache = ModelCache()
        
        # Initialize model selector
        self.model_selector = ModelSelector()
        
        # Initialize performance tracking
        self.metrics = PerformanceMetrics()
        self.metrics.last_updated = datetime.now(timezone.utc)
        
        # Model warming state
        self.warmed_models: Dict[str, datetime] = {}
        self.warming_in_progress: Dict[str, asyncio.Task] = {}
        
        # Initialize the client pool
        self._initialize_client_pool()
        
        # Background tasks will be started lazily when needed
        self._background_tasks_started = False
    
    def _initialize_client_pool(self):
        """Initialize the Ollama client pool."""
        try:
            pool_size = self.config["pool_size"]
            host = self.config["host"]
            timeout = self.config["timeout"]
            
            for i in range(pool_size):
                client = OllamaClient(
                    base_url=host,
                    model=self.config["model"],
                    timeout=timeout
                )
                self.client_pool.append(client)
            
            self.logger.info(
                "Initialized model engine with %d Ollama clients at %s",
                len(self.client_pool), host
            )
            
        except Exception as e:
            self.logger.error("Failed to initialize client pool: %s", e)
    
    def _start_background_tasks(self):
        """Start background tasks for maintenance and optimization."""
        try:
            # Check if we have a running event loop
            loop = asyncio.get_running_loop()
            
            # Start model warming if enabled
            if self.performance_config["model_warmup"]:
                loop.create_task(self._warm_default_model())
            
            # Start metrics collection task
            loop.create_task(self._metrics_collection_task())
            
            self._background_tasks_started = True
            self.logger.info("Background tasks started successfully")
            
        except RuntimeError:
            # No running event loop, tasks will be started later
            self.logger.debug("No running event loop, background tasks will be started later")
            self._background_tasks_started = False
    
    async def _ensure_background_tasks_started(self):
        """Ensure background tasks are started if not already running."""
        if not self._background_tasks_started:
            try:
                # Try to start background tasks now that we have an event loop
                self._start_background_tasks()
            except Exception as e:
                self.logger.warning("Failed to start background tasks: %s", e)
    
    async def _warm_default_model(self):
        """Warm up the default model for faster initial responses."""
        try:
            model = self.config["model"]
            if model not in self.warmed_models:
                self.logger.info("Warming up model: %s", model)
                
                # Use a simple prompt to warm up the model
                warm_prompt = "Hello, this is a model warmup request."
                
                client = await self.get_available_client()
                if client:
                    start_time = time.time()
                    await client.generate(warm_prompt, model=model, temperature=0.1)
                    warmup_time = (time.time() - start_time) * 1000
                    
                    self.warmed_models[model] = datetime.now(timezone.utc)
                    self.logger.info("Model %s warmed up in %.2fms", model, warmup_time)
                
        except Exception as e:
            self.logger.error("Failed to warm up model: %s", e)
    
    async def _metrics_collection_task(self):
        """Background task for collecting and persisting metrics."""
        while True:
            try:
                await asyncio.sleep(60)  # Collect metrics every minute
                await self._persist_metrics()
                
            except Exception as e:
                self.logger.error("Metrics collection task error: %s", e)
    
    async def _persist_metrics(self):
        """Persist current metrics to Redis."""
        try:
            redis = await redis_manager.get_redis()
            
            metrics_data = {
                "total_requests": self.metrics.total_requests,
                "cache_hits": self.metrics.cache_hits,
                "cache_misses": self.metrics.cache_misses,
                "avg_response_time_ms": self.metrics.avg_response_time_ms,
                "total_tokens_generated": self.metrics.total_tokens_generated,
                "errors": self.metrics.errors,
                "last_updated": self.metrics.last_updated.isoformat(),
                "cache_hit_rate": (
                    self.metrics.cache_hits / max(self.metrics.total_requests, 1) * 100
                )
            }
            
            await redis.setex(
                "ai:model:metrics",
                3600,  # 1 hour TTL
                json.dumps(metrics_data)
            )
            
        except Exception as e:
            self.logger.error("Failed to persist metrics: %s", e)
    
    async def get_available_client(self) -> Optional[OllamaClient]:
        """
        Get an available Ollama client from the pool using round-robin.
        
        Returns:
            Available OllamaClient or None if pool is empty
        """
        if not self.client_pool:
            return None
        
        async with self.pool_lock:
            client = self.client_pool[self.current_client_index]
            self.current_client_index = (self.current_client_index + 1) % len(self.client_pool)
            return client
    
    async def generate_response(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = None,
        max_tokens: Optional[int] = None,
        use_cache: bool = True,
        stream: bool = True
    ) -> AsyncGenerator[str, None]:
        """
        Generate AI response with caching and performance optimization.
        
        Args:
            prompt: Input prompt for the model
            model: Model name (uses default if None)
            temperature: Model temperature (uses default if None)
            max_tokens: Maximum tokens to generate
            use_cache: Whether to use caching
            stream: Whether to stream the response
            
        Yields:
            Response tokens or complete response
        """
        # Ensure background tasks are started
        await self._ensure_background_tasks_started()
        
        start_time = time.time()
        
        # Intelligent model selection
        if model is None:
            used_model = self.model_selector.select_model(prompt)
            self.logger.debug(f"Auto-selected model: {used_model}")
        else:
            used_model = model
            
        used_temperature = temperature if temperature is not None else self.config["temperature"]
        
        # Update metrics
        self.metrics.total_requests += 1
        
        try:
            # Check cache first if enabled
            if use_cache and self.performance_config["cache_enabled"] and not stream:
                cached_response = await self.cache.get_cached_response(
                    prompt, used_model, used_temperature
                )
                
                if cached_response:
                    self.metrics.cache_hits += 1
                    self.logger.debug("Cache hit for prompt (%.2fms)", 
                                    (time.time() - start_time) * 1000)
                    yield cached_response.content
                    return
            
            # Cache miss - generate new response
            self.metrics.cache_misses += 1
            
            # Get available client
            client = await self.get_available_client()
            if not client:
                self.metrics.errors += 1
                yield "I'm sorry, but the AI model is not available right now."
                return
            
            # Generate response
            if stream:
                async for token in self._generate_streaming_response(
                    client, prompt, used_model, used_temperature, max_tokens, start_time
                ):
                    yield token
            else:
                async for response in self._generate_complete_response(
                    client, prompt, used_model, used_temperature, max_tokens, 
                    start_time, use_cache
                ):
                    yield response
                    
        except Exception as e:
            self.metrics.errors += 1
            self.logger.error("Model generation failed: %s", e)
            yield f"I encountered an error generating a response: {str(e)}"
    
    async def _generate_streaming_response(
        self,
        client: OllamaClient,
        prompt: str,
        model: str,
        temperature: float,
        max_tokens: Optional[int],
        start_time: float
    ) -> AsyncGenerator[str, None]:
        """Generate streaming response with performance tracking."""
        try:
            token_count = 0
            first_token_time = None
            
            async for token in client.stream_generate(
                prompt, model=model, temperature=temperature
            ):
                if first_token_time is None:
                    first_token_time = time.time()
                    first_token_latency = (first_token_time - start_time) * 1000
                    self.logger.debug("First token latency: %.2fms", first_token_latency)
                
                token_count += 1
                yield token
                
                # Check max tokens limit
                if max_tokens and token_count >= max_tokens:
                    break
            
            # Update metrics
            total_time = (time.time() - start_time) * 1000
            self._update_response_metrics(total_time, token_count)
            
        except Exception as e:
            self.logger.error("Streaming generation failed: %s", e)
            raise
    
    async def _generate_complete_response(
        self,
        client: OllamaClient,
        prompt: str,
        model: str,
        temperature: float,
        max_tokens: Optional[int],
        start_time: float,
        use_cache: bool
    ) -> AsyncGenerator[str, None]:
        """Generate complete response with caching."""
        try:
            response = await client.generate(
                prompt, 
                model=model, 
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            # Calculate metrics
            total_time = (time.time() - start_time) * 1000
            token_count = len(response.split())  # Rough token estimate
            
            # Create response object
            model_response = ModelResponse(
                content=response,
                model=model,
                tokens_used=token_count,
                response_time_ms=total_time,
                cached=False,
                timestamp=datetime.now(timezone.utc)
            )
            
            # Cache the response if enabled
            if use_cache and self.performance_config["cache_enabled"]:
                await self.cache.cache_response(prompt, model, temperature, model_response)
            
            # Update metrics
            self._update_response_metrics(total_time, token_count)
            
            yield response
            
        except Exception as e:
            self.logger.error("Complete generation failed: %s", e)
            raise
    
    def _update_response_metrics(self, response_time_ms: float, token_count: int):
        """Update performance metrics."""
        # Update average response time
        total_responses = self.metrics.cache_hits + self.metrics.cache_misses
        if total_responses > 0:
            self.metrics.avg_response_time_ms = (
                (self.metrics.avg_response_time_ms * (total_responses - 1) + response_time_ms) 
                / total_responses
            )
        else:
            self.metrics.avg_response_time_ms = response_time_ms
        
        # Update token count
        self.metrics.total_tokens_generated += token_count
        self.metrics.last_updated = datetime.now(timezone.utc)
    
    async def warm_model(self, model: str) -> bool:
        """
        Warm up a specific model for faster responses.
        
        Args:
            model: Model name to warm up
            
        Returns:
            True if warming was successful, False otherwise
        """
        if model in self.warming_in_progress:
            # Warming already in progress
            await self.warming_in_progress[model]
            return model in self.warmed_models
        
        try:
            # Create warming task
            warming_task = asyncio.create_task(self._perform_model_warming(model))
            self.warming_in_progress[model] = warming_task
            
            # Wait for warming to complete
            success = await warming_task
            
            # Clean up
            del self.warming_in_progress[model]
            
            return success
            
        except Exception as e:
            self.logger.error("Failed to warm model %s: %s", model, e)
            if model in self.warming_in_progress:
                del self.warming_in_progress[model]
            return False
    
    async def _perform_model_warming(self, model: str) -> bool:
        """Perform the actual model warming."""
        try:
            client = await self.get_available_client()
            if not client:
                return False
            
            # Use a simple prompt to warm up the model
            warm_prompt = f"Hello, this is a warmup request for {model}."
            
            start_time = time.time()
            await client.generate(warm_prompt, model=model, temperature=0.1)
            warmup_time = (time.time() - start_time) * 1000
            
            self.warmed_models[model] = datetime.now(timezone.utc)
            self.logger.info("Model %s warmed up in %.2fms", model, warmup_time)
            
            return True
            
        except Exception as e:
            self.logger.error("Model warming failed for %s: %s", model, e)
            return False
    
    async def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get comprehensive performance metrics.
        
        Returns:
            Dictionary containing performance metrics
        """
        cache_stats = await self.cache.get_cache_stats()
        
        return {
            "requests": {
                "total": self.metrics.total_requests,
                "cache_hits": self.metrics.cache_hits,
                "cache_misses": self.metrics.cache_misses,
                "cache_hit_rate": (
                    self.metrics.cache_hits / max(self.metrics.total_requests, 1) * 100
                ),
                "errors": self.metrics.errors,
                "error_rate": (
                    self.metrics.errors / max(self.metrics.total_requests, 1) * 100
                )
            },
            "performance": {
                "avg_response_time_ms": self.metrics.avg_response_time_ms,
                "target_latency_ms": self.performance_config["target_latency"],
                "total_tokens_generated": self.metrics.total_tokens_generated,
                "tokens_per_request": (
                    self.metrics.total_tokens_generated / max(self.metrics.total_requests, 1)
                )
            },
            "cache": cache_stats,
            "pool": {
                "size": len(self.client_pool),
                "current_index": self.current_client_index
            },
            "models": {
                "warmed_models": list(self.warmed_models.keys()),
                "warming_in_progress": list(self.warming_in_progress.keys())
            },
            "config": {
                "cache_enabled": self.performance_config["cache_enabled"],
                "cache_ttl": self.performance_config["cache_ttl"],
                "model_warmup": self.performance_config["model_warmup"],
                "context_preload": self.performance_config["context_preload"]
            },
            "last_updated": self.metrics.last_updated.isoformat() if self.metrics.last_updated else None
        }
    
    async def invalidate_cache(self, pattern: str = "*") -> int:
        """
        Invalidate cached responses matching a pattern.
        
        Args:
            pattern: Pattern to match for cache invalidation
            
        Returns:
            Number of cache entries invalidated
        """
        return await self.cache.invalidate_cache_pattern(pattern)
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on the model engine.
        
        Returns:
            Health check results
        """
        health_status = {
            "status": "healthy",
            "client_pool_size": len(self.client_pool),
            "warmed_models": len(self.warmed_models),
            "cache_enabled": self.performance_config["cache_enabled"],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Test a client connection
        try:
            client = await self.get_available_client()
            if client:
                # Quick health check with minimal prompt
                start_time = time.time()
                await client.generate("test", model=self.config["model"], temperature=0.1)
                response_time = (time.time() - start_time) * 1000
                
                health_status["test_response_time_ms"] = response_time
                health_status["model_available"] = True
            else:
                health_status["status"] = "degraded"
                health_status["model_available"] = False
                
        except Exception as e:
            health_status["status"] = "unhealthy"
            health_status["error"] = str(e)
            health_status["model_available"] = False
        
        return health_status
    
    async def cleanup(self):
        """Clean up resources."""
        try:
            # Cancel warming tasks
            for task in self.warming_in_progress.values():
                task.cancel()
            
            # Close client connections
            for client in self.client_pool:
                await client.close()
            
            self.logger.info("Model engine cleanup completed")
            
        except Exception as e:
            self.logger.error("Error during model engine cleanup: %s", e)
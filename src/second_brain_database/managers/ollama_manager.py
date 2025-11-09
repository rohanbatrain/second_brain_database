"""Ollama LLM Manager.

This module provides a manager for interacting with Ollama local LLM models.
Supports text generation, chat, and embeddings with model selection and caching.

Features:
- Multiple model support with fallback
- Conversation context management
- Response streaming
- Embeddings generation
- Redis caching for responses
- Comprehensive error handling and logging
"""

import json
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx

from ..config import settings
from ..managers.logging_manager import get_logger
from ..managers.redis_manager import redis_manager

logger = get_logger(prefix="[OllamaManager]")


class OllamaManager:
    """Manager for Ollama LLM operations.

    This manager handles all interactions with Ollama models including
    text generation, chat, and embeddings with proper error handling,
    caching, and logging.

    Attributes:
        base_url: Ollama API base URL
        default_model: Default model to use
        chat_model: Model for chat operations
        embedding_model: Model for embeddings
        timeout: Request timeout in seconds
        cache_ttl: Cache TTL in seconds
    """

    def __init__(self):
        """Initialize Ollama manager with configuration."""
        self.base_url = settings.OLLAMA_HOST.rstrip("/")
        self.default_model = settings.OLLAMA_MODEL
        self.chat_model = settings.OLLAMA_CHAT_MODEL
        self.embedding_model = settings.OLLAMA_EMBEDDING_MODEL
        self.timeout = settings.OLLAMA_TIMEOUT
        self.cache_ttl = settings.OLLAMA_CACHE_TTL
        self._client = None

        logger.info(
            "Ollama manager initialized",
            extra={
                "base_url": self.base_url,
                "default_model": self.default_model,
                "chat_model": self.chat_model,
            }
        )

    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create HTTP client.

        Returns:
            Async HTTP client
        """
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout),
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def health_check(self) -> bool:
        """Check if Ollama service is healthy.

        Returns:
            True if service is healthy, False otherwise
        """
        try:
            response = await self.client.get("/api/tags")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Ollama health check failed: {e}", exc_info=True)
            return False

    async def list_models(self) -> List[Dict[str, Any]]:
        """List available models.

        Returns:
            List of model information dicts

        Raises:
            Exception: If API request fails
        """
        try:
            response = await self.client.get("/api/tags")
            response.raise_for_status()
            data = response.json()

            models = data.get("models", [])
            logger.info(f"Retrieved {len(models)} models from Ollama")
            return models

        except Exception as e:
            logger.error(f"Failed to list models: {e}", exc_info=True)
            raise

    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        cache_key: Optional[str] = None,
    ) -> str | AsyncGenerator[str, None]:
        """Generate text completion.

        Args:
            prompt: Input prompt
            model: Model name (defaults to configured model)
            system: System prompt
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
            stream: Enable streaming
            cache_key: Optional cache key for response

        Returns:
            Generated text or async generator if streaming

        Raises:
            Exception: If generation fails
        """
        model = model or self.default_model

        # Check cache for non-streaming requests
        if cache_key and not stream:
            cached = await self._get_cached_response(cache_key)
            if cached:
                logger.info(
                    f"Cache hit for generation",
                    extra={"cache_key": cache_key, "model": model}
                )
                return cached

        request_data = {
            "model": model,
            "prompt": prompt,
            "stream": stream,
            "options": {
                "temperature": temperature,
            }
        }

        if system:
            request_data["system"] = system

        if max_tokens:
            request_data["options"]["num_predict"] = max_tokens

        try:
            if stream:
                return self._generate_stream(request_data, model)
            else:
                response = await self.client.post(
                    "/api/generate",
                    json=request_data,
                )
                response.raise_for_status()
                result = response.json()
                text = result.get("response", "")

                # Cache response
                if cache_key:
                    await self._cache_response(cache_key, text)

                logger.info(
                    f"Generated text with {model}",
                    extra={
                        "model": model,
                        "prompt_length": len(prompt),
                        "response_length": len(text),
                    }
                )

                return text

        except Exception as e:
            logger.error(
                f"Text generation failed: {e}",
                exc_info=True,
                extra={"model": model, "prompt_length": len(prompt)}
            )
            raise

    async def _generate_stream(
        self,
        request_data: Dict[str, Any],
        model: str,
    ) -> AsyncGenerator[str, None]:
        """Stream text generation.

        Args:
            request_data: Request payload
            model: Model name

        Yields:
            Text chunks
        """
        async with self.client.stream(
            "POST",
            "/api/generate",
            json=request_data,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line:
                    try:
                        chunk = json.loads(line)
                        if "response" in chunk:
                            yield chunk["response"]
                    except json.JSONDecodeError:
                        continue

    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        cache_key: Optional[str] = None,
    ) -> str | AsyncGenerator[str, None]:
        """Chat completion with conversation context.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model name (defaults to chat model)
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            stream: Enable streaming
            cache_key: Optional cache key

        Returns:
            Response text or async generator if streaming

        Raises:
            Exception: If chat fails
        """
        model = model or self.chat_model

        # Check cache for non-streaming requests
        if cache_key and not stream:
            cached = await self._get_cached_response(cache_key)
            if cached:
                logger.info(
                    f"Cache hit for chat",
                    extra={"cache_key": cache_key, "model": model}
                )
                return cached

        request_data = {
            "model": model,
            "messages": messages,
            "stream": stream,
            "options": {
                "temperature": temperature,
            }
        }

        if max_tokens:
            request_data["options"]["num_predict"] = max_tokens

        try:
            if stream:
                return self._chat_stream(request_data, model)
            else:
                response = await self.client.post(
                    "/api/chat",
                    json=request_data,
                )
                response.raise_for_status()
                result = response.json()
                text = result.get("message", {}).get("content", "")

                # Cache response
                if cache_key:
                    await self._cache_response(cache_key, text)

                logger.info(
                    f"Chat completed with {model}",
                    extra={
                        "model": model,
                        "message_count": len(messages),
                        "response_length": len(text),
                    }
                )

                return text

        except Exception as e:
            logger.error(
                f"Chat failed: {e}",
                exc_info=True,
                extra={"model": model, "message_count": len(messages)}
            )
            raise

    async def _chat_stream(
        self,
        request_data: Dict[str, Any],
        model: str,
    ) -> AsyncGenerator[str, None]:
        """Stream chat completion.

        Args:
            request_data: Request payload
            model: Model name

        Yields:
            Text chunks
        """
        async with self.client.stream(
            "POST",
            "/api/chat",
            json=request_data,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line:
                    try:
                        chunk = json.loads(line)
                        if "message" in chunk and "content" in chunk["message"]:
                            yield chunk["message"]["content"]
                    except json.JSONDecodeError:
                        continue

    async def embed(
        self,
        text: str | List[str],
        model: Optional[str] = None,
        cache_key: Optional[str] = None,
    ) -> List[float] | List[List[float]]:
        """Generate embeddings for text.

        Args:
            text: Single text or list of texts
            model: Model name (defaults to embedding model)
            cache_key: Optional cache key

        Returns:
            Embedding vector(s)

        Raises:
            Exception: If embedding generation fails
        """
        model = model or self.embedding_model
        is_batch = isinstance(text, list)
        texts = text if is_batch else [text]

        # Check cache
        if cache_key and not is_batch:
            cached = await self._get_cached_response(cache_key)
            if cached:
                logger.info(
                    f"Cache hit for embedding",
                    extra={"cache_key": cache_key, "model": model}
                )
                return cached

        try:
            embeddings = []

            for txt in texts:
                response = await self.client.post(
                    "/api/embeddings",
                    json={
                        "model": model,
                        "prompt": txt,
                    }
                )
                response.raise_for_status()
                result = response.json()
                embedding = result.get("embedding", [])
                embeddings.append(embedding)

            # Cache single embedding
            if cache_key and not is_batch:
                await self._cache_response(cache_key, embeddings[0])

            logger.info(
                f"Generated {len(embeddings)} embeddings with {model}",
                extra={
                    "model": model,
                    "count": len(embeddings),
                    "dimension": len(embeddings[0]) if embeddings else 0,
                }
            )

            return embeddings if is_batch else embeddings[0]

        except Exception as e:
            logger.error(
                f"Embedding generation failed: {e}",
                exc_info=True,
                extra={"model": model, "text_count": len(texts)}
            )
            raise

    async def _get_cached_response(self, cache_key: str) -> Optional[Any]:
        """Get cached response.

        Args:
            cache_key: Cache key

        Returns:
            Cached response or None
        """
        try:
            cached = await redis_manager.get(f"ollama:cache:{cache_key}")
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Cache retrieval failed: {e}")
        return None

    async def _cache_response(self, cache_key: str, response: Any) -> None:
        """Cache response.

        Args:
            cache_key: Cache key
            response: Response to cache
        """
        try:
            await redis_manager.set(
                f"ollama:cache:{cache_key}",
                json.dumps(response),
                ex=self.cache_ttl,
            )
        except Exception as e:
            logger.warning(f"Cache storage failed: {e}")


# Global instance
ollama_manager = OllamaManager()

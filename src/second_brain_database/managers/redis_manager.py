"""
Redis manager for handling Redis connections and related utilities.

This module provides the RedisManager class, which manages
asynchronous Redis connections and exposes methods for
retrieving and interacting with Redis in a robust, production-ready way.

Logging:
    - Uses the centralized logging manager.
    - Logs connection attempts, successes, and failures.
    - All exceptions are logged with full traceback.
"""

from typing import Optional

from fastapi import HTTPException, status
import redis.asyncio as redis_async
import redis as redis_sync
import os
import sys

from second_brain_database.config import settings
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger()

REDIS_UNAVAILABLE_MSG: str = "Rate limiting service unavailable. Please try again later."


class RedisManager:
    """
    Manages a single Redis connection for the application.

    Attributes:
        redis_url: The Redis connection URL.
        _redis: The cached Redis connection instance.
        logger: The logger instance for this manager.
    """

    def __init__(self) -> None:
        """Initialize the RedisManager with config and logger.

        Behaviour:
        - Attempt to connect to a local Redis (built from environment: REDIS_HOST, REDIS_PORT, REDIS_DB)
          using the synchronous redis client and a short connect timeout.
        - If local connection fails, attempt to connect to `settings.REDIS_URL`.
        - If both attempts fail, exit the process (fail-fast).
        """
        self.logger = logger

        # Build a local redis url from environment or sensible defaults
        redis_host = os.environ.get("REDIS_HOST", "127.0.0.1")
        redis_port = os.environ.get("REDIS_PORT", "6379")
        redis_db = os.environ.get("REDIS_DB", "0")
        local_url = f"redis://{redis_host}:{redis_port}/{redis_db}"

        # Try local (synchronous) first to fail fast at startup if needed
        try:
            self.logger.info("[RedisManager] Attempting synchronous local Redis connect to %s", local_url)
            sync_client = redis_sync.from_url(local_url, socket_connect_timeout=2)
            sync_client.ping()
            self.redis_url = local_url
            self._redis: Optional[redis_async.Redis] = None
            self.logger.info("[RedisManager] Local Redis healthy at %s", local_url)
            return
        except Exception as e:
            self.logger.warning("[RedisManager] Local Redis unreachable (%s): %s", local_url, str(e))

        # Fallback to configured settings.REDIS_URL (be defensive: tests may swap in a MockSettings)
        try:
            self.logger.info("[RedisManager] Attempting synchronous connect to configured Redis URL")
            # Some test contexts replace `settings` with a mock that may not have attributes.
            # Be defensive: prefer explicit attribute access via getattr, then fall back to storage URI
            # or environment values so we never raise AttributeError here.
            redis_url_config = getattr(settings, "REDIS_URL", None)

            if not redis_url_config:
                # Try storage URI
                redis_url_config = getattr(settings, "REDIS_STORAGE_URI", None)

            if not redis_url_config:
                # As a last resort construct from settings or environment
                host = getattr(settings, "REDIS_HOST", os.environ.get("REDIS_HOST", "127.0.0.1"))
                port = getattr(settings, "REDIS_PORT", os.environ.get("REDIS_PORT", "6379"))
                db = getattr(settings, "REDIS_DB", os.environ.get("REDIS_DB", "0"))
                redis_url_config = f"redis://{host}:{port}/{db}"
                self.logger.debug("[RedisManager] No REDIS_URL in settings, constructed fallback %s", redis_url_config)

            sync_client = redis_sync.from_url(redis_url_config, socket_connect_timeout=5)
            sync_client.ping()
            self.redis_url = redis_url_config
            self._redis: Optional[redis_async.Redis] = None
            self.logger.info("[RedisManager] Connected to configured Redis URL %s", redis_url_config)
            return
        except Exception as e:
            self.logger.critical("[RedisManager] Configured Redis unreachable: %s", str(e), exc_info=True)
            self.logger.critical("[RedisManager] No Redis available (local and configured attempts failed). Exiting.")
            sys.exit(1)

    async def get_redis(self) -> redis_async.Redis:
        """
        Get or create the Redis connection.

        Returns:
            An active redis.Redis connection.

        Raises:
            HTTPException: If Redis is unavailable.

        Side-effects:
            Logs connection attempts and errors.
        """
        if self._redis is None:
            try:
                self.logger.info("[RedisManager] Attempting async connection to Redis at %s", self.redis_url)
                self._redis = await redis_async.from_url(self.redis_url, decode_responses=True)
                self.logger.info("[RedisManager] Successfully connected (async) to Redis at %s", self.redis_url)
            except Exception as conn_exc:
                self.logger.error("[RedisManager] Failed to create async Redis connection: %s", conn_exc, exc_info=True)
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=REDIS_UNAVAILABLE_MSG,
                ) from conn_exc
        return self._redis


redis_manager = RedisManager()

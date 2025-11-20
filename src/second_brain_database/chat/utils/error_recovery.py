"""Error recovery utilities for chat system with retry and fallback strategies."""

import asyncio
import logging
from typing import Any, Callable, Optional, Tuple, Type

logger = logging.getLogger(__name__)


class ErrorRecoveryHandler:
    """Handle errors with retry and fallback strategies for chat operations."""

    @staticmethod
    async def with_retry(
        func: Callable,
        max_retries: int = 3,
        backoff_factor: float = 2.0,
        exceptions: Tuple[Type[Exception], ...] = (Exception,),
    ) -> Any:
        """
        Execute function with exponential backoff retry.

        Args:
            func: Async function to execute
            max_retries: Maximum number of retry attempts
            backoff_factor: Exponential backoff multiplier
            exceptions: Tuple of exception types to catch and retry

        Returns:
            Result from successful function execution

        Raises:
            Exception: Re-raises the last exception if all retries fail
        """
        last_exception = None

        for attempt in range(max_retries):
            try:
                return await func()
            except exceptions as e:
                last_exception = e

                if attempt == max_retries - 1:
                    # Last attempt failed, re-raise
                    logger.error(
                        f"Function failed after {max_retries} attempts: {e}",
                        exc_info=True,
                    )
                    raise

                # Calculate wait time with exponential backoff
                wait_time = backoff_factor**attempt
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries} failed: {e}. "
                    f"Retrying in {wait_time:.1f}s..."
                )
                await asyncio.sleep(wait_time)

        # Should never reach here, but for type safety
        if last_exception:
            raise last_exception

    @staticmethod
    async def llm_call_with_fallback(
        primary_func: Callable,
        fallback_response: str = "I apologize, but I'm having trouble generating a response right now.",
    ) -> Any:
        """
        Call LLM with fallback to error message on failure.

        Implements retry logic with 3 attempts and 2.0 backoff factor.
        If all retries fail, returns fallback response instead of raising.

        Args:
            primary_func: Async function that calls the LLM
            fallback_response: Default response to return on failure

        Returns:
            LLM response or fallback response string
        """
        try:
            return await ErrorRecoveryHandler.with_retry(
                primary_func, max_retries=3, backoff_factor=2.0, exceptions=(Exception,)
            )
        except Exception as e:
            logger.error(f"LLM call failed after retries: {e}", exc_info=True)
            return fallback_response

    @staticmethod
    async def vector_search_with_fallback(
        search_func: Callable, fallback_to_general: bool = True
    ) -> Any:
        """
        Vector search with fallback to general response on failure.

        Implements retry logic with 2 attempts and 1.5 backoff factor.
        If all retries fail and fallback_to_general is True, returns
        a dict indicating fallback mode. Otherwise, re-raises exception.

        Args:
            search_func: Async function that performs vector search
            fallback_to_general: If True, return fallback dict instead of raising

        Returns:
            Search results or fallback dict with error information

        Raises:
            Exception: Re-raises if fallback_to_general is False
        """
        try:
            return await ErrorRecoveryHandler.with_retry(
                search_func, max_retries=2, backoff_factor=1.5, exceptions=(Exception,)
            )
        except Exception as e:
            logger.error(f"Vector search failed after retries: {e}", exc_info=True)

            if fallback_to_general:
                return {
                    "success": False,
                    "fallback": True,
                    "error": "Vector search unavailable, using general response",
                }
            else:
                raise

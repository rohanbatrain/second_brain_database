"""
MCP Error Recovery and Resilience Patterns

Implements comprehensive error recovery mechanisms for MCP operations including
circuit breaker patterns, retry logic with exponential backoff, and graceful
degradation for service unavailability.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
import time
from typing import Any, Callable, Dict, List, Optional, Type, Union

from ...config import settings
from ...managers.logging_manager import get_logger
from ...utils.error_handling import (
    BulkheadCapacityError,
    BulkheadSemaphore,
    CircuitBreaker,
    CircuitBreakerOpenError,
    ErrorContext,
    GracefulDegradationError,
    RetryConfig,
    RetryExhaustedError,
    RetryStrategy,
    get_bulkhead,
    get_circuit_breaker,
    retry_with_backoff,
    with_graceful_degradation,
)
from .exceptions import (
    MCPBulkheadError,
    MCPCircuitBreakerError,
    MCPError,
    MCPRetryExhaustedError,
    MCPServerError,
    MCPTimeoutError,
    MCPToolError,
    create_mcp_error_context,
)

logger = get_logger(prefix="[MCP_ErrorRecovery]")


class MCPServiceType(Enum):
    """Types of MCP services for circuit breaker categorization."""

    FAMILY_MANAGEMENT = "family_management"
    USER_AUTHENTICATION = "user_authentication"
    SHOP_SERVICES = "shop_services"
    WORKSPACE_MANAGEMENT = "workspace_management"
    SYSTEM_ADMINISTRATION = "system_administration"
    DATABASE_OPERATIONS = "database_operations"
    EXTERNAL_SERVICES = "external_services"


@dataclass
class MCPRecoveryConfig:
    """Configuration for MCP error recovery mechanisms."""

    # Circuit breaker settings
    circuit_breaker_enabled: bool = True
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout: int = 60
    circuit_breaker_half_open_max_calls: int = 3

    # Bulkhead settings
    bulkhead_enabled: bool = True
    bulkhead_capacity: int = 20
    bulkhead_timeout: float = 10.0

    # Retry settings
    retry_enabled: bool = True
    retry_max_attempts: int = 3
    retry_initial_delay: float = 1.0
    retry_backoff_factor: float = 2.0
    retry_max_delay: float = 30.0
    retry_strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF

    # Timeout settings
    operation_timeout: float = 30.0
    tool_execution_timeout: float = 60.0
    resource_access_timeout: float = 15.0

    # Graceful degradation settings
    graceful_degradation_enabled: bool = True
    fallback_cache_enabled: bool = True
    fallback_cache_ttl: int = 300  # 5 minutes

    # Health check settings
    health_check_interval: int = 30
    health_check_timeout: float = 5.0


class MCPCircuitBreakerManager:
    """
    Manages circuit breakers for different MCP service types.

    Provides centralized circuit breaker management with service-specific
    configurations and monitoring capabilities.
    """

    def __init__(self, config: MCPRecoveryConfig):
        self.config = config
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._service_configs: Dict[MCPServiceType, Dict[str, Any]] = {}
        self._initialize_service_configs()

    def _initialize_service_configs(self) -> None:
        """Initialize service-specific circuit breaker configurations."""
        self._service_configs = {
            MCPServiceType.FAMILY_MANAGEMENT: {
                "failure_threshold": 3,
                "recovery_timeout": 30,
                "expected_exception": (MCPToolError, ConnectionError, TimeoutError),
            },
            MCPServiceType.USER_AUTHENTICATION: {
                "failure_threshold": 5,
                "recovery_timeout": 60,
                "expected_exception": (MCPToolError, ConnectionError),
            },
            MCPServiceType.SHOP_SERVICES: {
                "failure_threshold": 4,
                "recovery_timeout": 45,
                "expected_exception": (MCPToolError, ConnectionError, TimeoutError),
            },
            MCPServiceType.WORKSPACE_MANAGEMENT: {
                "failure_threshold": 3,
                "recovery_timeout": 30,
                "expected_exception": (MCPToolError, ConnectionError),
            },
            MCPServiceType.SYSTEM_ADMINISTRATION: {
                "failure_threshold": 2,
                "recovery_timeout": 120,
                "expected_exception": (MCPServerError, ConnectionError, TimeoutError),
            },
            MCPServiceType.DATABASE_OPERATIONS: {
                "failure_threshold": 5,
                "recovery_timeout": 90,
                "expected_exception": (ConnectionError, TimeoutError, OSError),
            },
            MCPServiceType.EXTERNAL_SERVICES: {
                "failure_threshold": 3,
                "recovery_timeout": 60,
                "expected_exception": (ConnectionError, TimeoutError, OSError),
            },
        }

    def get_circuit_breaker(self, service_type: MCPServiceType, operation_name: str) -> CircuitBreaker:
        """
        Get or create circuit breaker for specific service and operation.

        Args:
            service_type: Type of MCP service
            operation_name: Specific operation name

        Returns:
            Circuit breaker instance
        """
        cb_name = f"mcp_{service_type.value}_{operation_name}"

        if cb_name not in self._circuit_breakers:
            service_config = self._service_configs.get(service_type, {})

            self._circuit_breakers[cb_name] = get_circuit_breaker(
                name=cb_name,
                failure_threshold=service_config.get(
                    "failure_threshold", self.config.circuit_breaker_failure_threshold
                ),
                recovery_timeout=service_config.get("recovery_timeout", self.config.circuit_breaker_recovery_timeout),
                expected_exception=service_config.get("expected_exception", Exception),
            )

            logger.info("Created circuit breaker for MCP service %s operation %s", service_type.value, operation_name)

        return self._circuit_breakers[cb_name]

    def get_all_circuit_breakers(self) -> Dict[str, CircuitBreaker]:
        """Get all circuit breakers."""
        return self._circuit_breakers.copy()

    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status of all circuit breakers."""
        status = {
            "healthy": True,
            "circuit_breakers": {},
            "summary": {"total": len(self._circuit_breakers), "open": 0, "half_open": 0, "closed": 0},
        }

        for name, cb in self._circuit_breakers.items():
            cb_stats = cb.get_stats()
            status["circuit_breakers"][name] = cb_stats

            # Update summary
            state = cb_stats["state"]
            if state == "open":
                status["summary"]["open"] += 1
                status["healthy"] = False
            elif state == "half_open":
                status["summary"]["half_open"] += 1
            else:
                status["summary"]["closed"] += 1

        return status


class MCPBulkheadManager:
    """
    Manages bulkhead semaphores for MCP resource isolation.

    Provides resource isolation to prevent cascading failures and
    ensure system stability under load.
    """

    def __init__(self, config: MCPRecoveryConfig):
        self.config = config
        self._bulkheads: Dict[str, BulkheadSemaphore] = {}
        self._resource_configs: Dict[str, int] = {}
        self._initialize_resource_configs()

    def _initialize_resource_configs(self) -> None:
        """Initialize resource-specific bulkhead configurations."""
        self._resource_configs = {
            "family_operations": 15,
            "user_authentication": 25,
            "shop_operations": 10,
            "workspace_operations": 12,
            "database_operations": 20,
            "external_api_calls": 8,
            "file_operations": 5,
            "email_operations": 3,
        }

    def get_bulkhead(self, resource_type: str) -> BulkheadSemaphore:
        """
        Get or create bulkhead semaphore for specific resource type.

        Args:
            resource_type: Type of resource to isolate

        Returns:
            Bulkhead semaphore instance
        """
        if resource_type not in self._bulkheads:
            capacity = self._resource_configs.get(resource_type, self.config.bulkhead_capacity)

            self._bulkheads[resource_type] = get_bulkhead(name=f"mcp_{resource_type}", capacity=capacity)

            logger.info("Created bulkhead for MCP resource type %s with capacity %d", resource_type, capacity)

        return self._bulkheads[resource_type]

    async def acquire_with_timeout(self, resource_type: str, timeout: Optional[float] = None) -> BulkheadSemaphore:
        """
        Acquire bulkhead semaphore with timeout.

        Args:
            resource_type: Type of resource
            timeout: Timeout for acquisition

        Returns:
            Acquired bulkhead semaphore

        Raises:
            MCPBulkheadError: If acquisition fails or times out
        """
        bulkhead = self.get_bulkhead(resource_type)
        timeout = timeout or self.config.bulkhead_timeout

        try:
            acquired = await bulkhead.acquire(timeout=timeout)
            if not acquired:
                raise MCPBulkheadError(
                    f"Failed to acquire bulkhead for {resource_type} within {timeout}s",
                    bulkhead_name=f"mcp_{resource_type}",
                )
            return bulkhead

        except asyncio.TimeoutError as e:
            raise MCPBulkheadError(
                f"Bulkhead acquisition timeout for {resource_type}", bulkhead_name=f"mcp_{resource_type}"
            ) from e

    def get_all_bulkheads(self) -> Dict[str, BulkheadSemaphore]:
        """Get all bulkhead semaphores."""
        return self._bulkheads.copy()

    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status of all bulkheads."""
        status = {
            "healthy": True,
            "bulkheads": {},
            "summary": {"total": len(self._bulkheads), "at_capacity": 0, "high_utilization": 0, "normal": 0},
        }

        for name, bulkhead in self._bulkheads.items():
            bulkhead_stats = bulkhead.get_stats()
            status["bulkheads"][name] = bulkhead_stats

            # Calculate utilization
            utilization = bulkhead_stats["active_count"] / bulkhead_stats["capacity"]

            if utilization >= 1.0:
                status["summary"]["at_capacity"] += 1
                status["healthy"] = False
            elif utilization >= 0.8:
                status["summary"]["high_utilization"] += 1
            else:
                status["summary"]["normal"] += 1

        return status


class MCPRetryManager:
    """
    Manages retry logic for MCP operations with configurable strategies.

    Provides intelligent retry mechanisms with exponential backoff,
    jitter, and operation-specific configurations.
    """

    def __init__(self, config: MCPRecoveryConfig):
        self.config = config
        self._operation_configs: Dict[str, RetryConfig] = {}
        self._initialize_operation_configs()

    def _initialize_operation_configs(self) -> None:
        """Initialize operation-specific retry configurations."""
        # Family management operations
        self._operation_configs["family_create"] = RetryConfig(
            max_attempts=2,
            initial_delay=1.0,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            retryable_exceptions=[ConnectionError, TimeoutError],
            non_retryable_exceptions=[ValueError, TypeError],
        )

        self._operation_configs["family_read"] = RetryConfig(
            max_attempts=3,
            initial_delay=0.5,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            retryable_exceptions=[ConnectionError, TimeoutError],
        )

        # Authentication operations
        self._operation_configs["user_auth"] = RetryConfig(
            max_attempts=2,
            initial_delay=2.0,
            strategy=RetryStrategy.FIXED_DELAY,
            retryable_exceptions=[ConnectionError],
            non_retryable_exceptions=[ValueError, PermissionError],
        )

        # Shop operations
        self._operation_configs["shop_purchase"] = RetryConfig(
            max_attempts=1,  # No retries for purchases to avoid double-charging
            initial_delay=0.0,
            strategy=RetryStrategy.FIXED_DELAY,
        )

        self._operation_configs["shop_browse"] = RetryConfig(
            max_attempts=3,
            initial_delay=1.0,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            retryable_exceptions=[ConnectionError, TimeoutError],
        )

        # Database operations
        self._operation_configs["database_read"] = RetryConfig(
            max_attempts=4,
            initial_delay=0.5,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            retryable_exceptions=[ConnectionError, TimeoutError, OSError],
        )

        self._operation_configs["database_write"] = RetryConfig(
            max_attempts=2,
            initial_delay=1.0,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            retryable_exceptions=[ConnectionError, TimeoutError],
            non_retryable_exceptions=[ValueError, TypeError],
        )

    def get_retry_config(self, operation_type: str) -> RetryConfig:
        """
        Get retry configuration for specific operation type.

        Args:
            operation_type: Type of operation

        Returns:
            Retry configuration
        """
        return self._operation_configs.get(
            operation_type,
            RetryConfig(
                max_attempts=self.config.retry_max_attempts,
                initial_delay=self.config.retry_initial_delay,
                backoff_factor=self.config.retry_backoff_factor,
                max_delay=self.config.retry_max_delay,
                strategy=self.config.retry_strategy,
            ),
        )

    async def execute_with_retry(
        self, func: Callable, operation_type: str, context: ErrorContext, *args, **kwargs
    ) -> Any:
        """
        Execute function with retry logic.

        Args:
            func: Function to execute
            operation_type: Type of operation for retry config
            context: Error context
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            MCPRetryExhaustedError: When all retry attempts are exhausted
        """
        if not self.config.retry_enabled:
            return await func(*args, **kwargs)

        retry_config = self.get_retry_config(operation_type)

        try:
            return await retry_with_backoff(func, retry_config, context, *args, **kwargs)
        except RetryExhaustedError as e:
            raise MCPRetryExhaustedError(
                f"MCP operation {operation_type} failed after {retry_config.max_attempts} attempts",
                retry_attempts=retry_config.max_attempts,
                last_error=e.args[0] if e.args else None,
            ) from e


class MCPGracefulDegradationManager:
    """
    Manages graceful degradation strategies for MCP operations.

    Provides fallback mechanisms and cached responses when primary
    services are unavailable or degraded.
    """

    def __init__(self, config: MCPRecoveryConfig):
        self.config = config
        self._fallback_cache: Dict[str, Dict[str, Any]] = {}
        self._fallback_functions: Dict[str, Callable] = {}
        self._initialize_fallback_functions()

    def _initialize_fallback_functions(self) -> None:
        """Initialize fallback functions for different operation types."""
        self._fallback_functions = {
            "get_family_info": self._fallback_get_family_info,
            "get_user_profile": self._fallback_get_user_profile,
            "list_shop_items": self._fallback_list_shop_items,
            "get_system_health": self._fallback_get_system_health,
        }

    async def _fallback_get_family_info(self, family_id: str, **kwargs) -> Dict[str, Any]:
        """Fallback for family info retrieval."""
        cache_key = f"family_info_{family_id}"
        cached = self._get_from_cache(cache_key)

        if cached:
            logger.info("Returning cached family info for %s", family_id)
            return cached

        # Return minimal family info
        return {
            "id": family_id,
            "name": "Family (Limited Info)",
            "status": "degraded_mode",
            "message": "Full family information is temporarily unavailable",
        }

    async def _fallback_get_user_profile(self, user_id: str, **kwargs) -> Dict[str, Any]:
        """Fallback for user profile retrieval."""
        cache_key = f"user_profile_{user_id}"
        cached = self._get_from_cache(cache_key)

        if cached:
            logger.info("Returning cached user profile for %s", user_id)
            return cached

        # Return minimal user info
        return {
            "id": user_id,
            "username": "User (Limited Info)",
            "status": "degraded_mode",
            "message": "Full profile information is temporarily unavailable",
        }

    async def _fallback_list_shop_items(self, **kwargs) -> Dict[str, Any]:
        """Fallback for shop item listing."""
        cache_key = "shop_items_list"
        cached = self._get_from_cache(cache_key)

        if cached:
            logger.info("Returning cached shop items")
            return cached

        # Return empty shop with message
        return {"items": [], "total": 0, "status": "degraded_mode", "message": "Shop is temporarily unavailable"}

    async def _fallback_get_system_health(self, **kwargs) -> Dict[str, Any]:
        """Fallback for system health check."""
        return {
            "status": "degraded",
            "message": "System health check is temporarily unavailable",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "services": {"mcp_server": "unknown", "database": "unknown", "cache": "unknown"},
        }

    def _get_from_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get item from fallback cache if not expired."""
        if not self.config.fallback_cache_enabled:
            return None

        cached_item = self._fallback_cache.get(cache_key)
        if not cached_item:
            return None

        # Check if expired
        cache_time = cached_item.get("cached_at", 0)
        if time.time() - cache_time > self.config.fallback_cache_ttl:
            del self._fallback_cache[cache_key]
            return None

        return cached_item.get("data")

    def _set_cache(self, cache_key: str, data: Dict[str, Any]) -> None:
        """Set item in fallback cache."""
        if not self.config.fallback_cache_enabled:
            return

        self._fallback_cache[cache_key] = {"data": data, "cached_at": time.time()}

    async def execute_with_fallback(
        self, primary_func: Callable, operation_type: str, context: ErrorContext, *args, **kwargs
    ) -> Any:
        """
        Execute function with graceful degradation fallback.

        Args:
            primary_func: Primary function to execute
            operation_type: Type of operation for fallback selection
            context: Error context
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Result from primary or fallback function
        """
        if not self.config.graceful_degradation_enabled:
            return await primary_func(*args, **kwargs)

        fallback_func = self._fallback_functions.get(operation_type)
        if not fallback_func:
            # No fallback available, execute primary function
            return await primary_func(*args, **kwargs)

        try:
            # Try primary function first
            result = await primary_func(*args, **kwargs)

            # Cache successful result for fallback
            if self.config.fallback_cache_enabled:
                cache_key = f"{operation_type}_{hash(str(args) + str(kwargs))}"
                self._set_cache(cache_key, result)

            return result

        except Exception as e:
            logger.warning(
                "Primary function failed for %s, attempting graceful degradation: %s", operation_type, str(e)
            )

            try:
                result = await fallback_func(*args, **kwargs)
                logger.info("Graceful degradation successful for %s", operation_type)
                return result

            except Exception as fallback_error:
                logger.error("Graceful degradation failed for %s: %s", operation_type, str(fallback_error))
                raise GracefulDegradationError(
                    f"Both primary and fallback functions failed for {operation_type}"
                ) from e


class MCPErrorRecoveryManager:
    """
    Centralized error recovery manager for MCP operations.

    Coordinates circuit breakers, bulkheads, retry logic, and graceful
    degradation to provide comprehensive error recovery capabilities.
    """

    def __init__(self, config: Optional[MCPRecoveryConfig] = None):
        self.config = config or MCPRecoveryConfig()
        self.circuit_breaker_manager = MCPCircuitBreakerManager(self.config)
        self.bulkhead_manager = MCPBulkheadManager(self.config)
        self.retry_manager = MCPRetryManager(self.config)
        self.degradation_manager = MCPGracefulDegradationManager(self.config)

        logger.info("MCP Error Recovery Manager initialized with config: %s", self.config)

    async def execute_with_recovery(
        self,
        func: Callable,
        service_type: MCPServiceType,
        operation_name: str,
        resource_type: Optional[str] = None,
        user_id: Optional[str] = None,
        request_id: Optional[str] = None,
        enable_fallback: bool = True,
        *args,
        **kwargs,
    ) -> Any:
        """
        Execute function with comprehensive error recovery.

        Args:
            func: Function to execute
            service_type: Type of MCP service
            operation_name: Name of the operation
            resource_type: Type of resource for bulkhead isolation
            user_id: User ID for context
            request_id: Request ID for tracking
            enable_fallback: Whether to enable graceful degradation
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            MCPError: Various MCP-specific errors based on failure type
        """
        # Create error context
        context = create_mcp_error_context(
            operation=f"{service_type.value}_{operation_name}",
            user_id=user_id,
            request_id=request_id,
            tool_name=operation_name,
        )

        # Get circuit breaker
        circuit_breaker = None
        if self.config.circuit_breaker_enabled:
            circuit_breaker = self.circuit_breaker_manager.get_circuit_breaker(service_type, operation_name)

        # Acquire bulkhead if specified
        bulkhead = None
        if self.config.bulkhead_enabled and resource_type:
            try:
                bulkhead = await self.bulkhead_manager.acquire_with_timeout(resource_type)
            except MCPBulkheadError:
                logger.warning("Bulkhead capacity exceeded for %s", resource_type)
                raise

        try:
            # Define execution function with all recovery mechanisms
            async def execute_with_all_recovery():
                # Circuit breaker protection
                if circuit_breaker:
                    try:
                        # Retry logic with circuit breaker
                        return await self.retry_manager.execute_with_retry(
                            lambda: circuit_breaker.call(func, *args, **kwargs), operation_name, context
                        )
                    except CircuitBreakerOpenError as e:
                        raise MCPCircuitBreakerError(
                            f"Circuit breaker open for {service_type.value}_{operation_name}",
                            circuit_breaker_name=circuit_breaker.name,
                        ) from e
                else:
                    # Retry logic without circuit breaker
                    return await self.retry_manager.execute_with_retry(func, operation_name, context, *args, **kwargs)

            # Execute with timeout
            try:
                result = await asyncio.wait_for(execute_with_all_recovery(), timeout=self.config.operation_timeout)
                return result

            except asyncio.TimeoutError as e:
                raise MCPTimeoutError(
                    f"Operation {operation_name} timed out after {self.config.operation_timeout}s",
                    timeout_duration=self.config.operation_timeout,
                    operation_type=operation_name,
                ) from e

        except Exception as e:
            # Try graceful degradation if enabled and available
            if enable_fallback and self.config.graceful_degradation_enabled:
                try:
                    return await self.degradation_manager.execute_with_fallback(
                        func, operation_name, context, *args, **kwargs
                    )
                except GracefulDegradationError:
                    # Fallback also failed, re-raise original error
                    pass

            # Convert to appropriate MCP error
            if isinstance(e, MCPError):
                raise
            elif isinstance(e, (ConnectionError, OSError)):
                raise MCPServerError(
                    f"Service unavailable for {operation_name}: {str(e)}", server_component=service_type.value
                ) from e
            else:
                raise MCPToolError(
                    f"Tool execution failed for {operation_name}: {str(e)}", tool_name=operation_name, original_error=e
                ) from e

        finally:
            # Release bulkhead
            if bulkhead:
                bulkhead.release()

    async def get_recovery_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status of all recovery mechanisms."""
        cb_health = await self.circuit_breaker_manager.get_health_status()
        bulkhead_health = await self.bulkhead_manager.get_health_status()

        overall_healthy = cb_health["healthy"] and bulkhead_health["healthy"]

        return {
            "healthy": overall_healthy,
            "circuit_breakers": cb_health,
            "bulkheads": bulkhead_health,
            "configuration": {
                "circuit_breaker_enabled": self.config.circuit_breaker_enabled,
                "bulkhead_enabled": self.config.bulkhead_enabled,
                "retry_enabled": self.config.retry_enabled,
                "graceful_degradation_enabled": self.config.graceful_degradation_enabled,
                "operation_timeout": self.config.operation_timeout,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# Global error recovery manager instance
mcp_recovery_manager = MCPErrorRecoveryManager()


# Decorator for easy error recovery integration
def with_mcp_recovery(
    service_type: MCPServiceType, operation_name: str, resource_type: Optional[str] = None, enable_fallback: bool = True
):
    """
    Decorator to add comprehensive error recovery to MCP functions.

    Args:
        service_type: Type of MCP service
        operation_name: Name of the operation
        resource_type: Type of resource for bulkhead isolation
        enable_fallback: Whether to enable graceful degradation
    """

    def decorator(func: Callable) -> Callable:
        async def wrapper(*args, **kwargs):
            # Extract user context if available
            user_id = kwargs.get("user_id")
            request_id = kwargs.get("request_id")

            return await mcp_recovery_manager.execute_with_recovery(
                func=func,
                service_type=service_type,
                operation_name=operation_name,
                resource_type=resource_type,
                user_id=user_id,
                request_id=request_id,
                enable_fallback=enable_fallback,
                *args,
                **kwargs,
            )

        return wrapper

    return decorator

"""
IPAM Manager for hierarchical IP allocation management.

This module provides the IPAMManager class, which manages IP address allocations
in a hierarchical structure (Global Root -> Country -> Region -> Host) with automatic
allocation, user isolation, and comprehensive audit capabilities.

Enterprise Features:
    - Dependency injection for testability and modularity
    - Transaction safety with MongoDB sessions for critical operations
    - Comprehensive error handling with custom exception hierarchy
    - Auto-allocation algorithms for X.Y and Z octets
    - User isolation with independent namespaces
    - Redis caching for performance optimization
    - Comprehensive audit logging for all operations
    - Quota management and enforcement
    - Concurrency control with retry logic

Logging:
    - Uses the centralized logging manager with structured context
    - Logs all allocation operations and security events
    - Performance metrics tracking for all database operations
    - All exceptions are logged with full traceback and context
"""

import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Protocol, Tuple, runtime_checkable

from bson import ObjectId
from pymongo.client_session import ClientSession
from pymongo.errors import DuplicateKeyError, PyMongoError

from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.utils.error_handling import (
    ErrorContext,
    ErrorSeverity,
    RetryConfig,
    RetryStrategy,
    handle_errors,
)

logger = get_logger(prefix="[IPAMManager]")

# Constants for IPAM management
DEFAULT_REGION_QUOTA = 1000
DEFAULT_HOST_QUOTA = 10000
QUOTA_WARNING_THRESHOLD = 0.8  # 80%
COUNTRY_MAPPING_CACHE_TTL = 86400  # 24 hours
ALLOCATED_Y_CACHE_TTL = 60  # 60 seconds
USER_QUOTA_CACHE_TTL = 60  # 60 seconds
MAX_RETRY_ATTEMPTS = 3
RETRY_BACKOFF_BASE = 0.1  # 100ms base backoff


# Custom exception hierarchy for IPAM operations
class IPAMError(Exception):
    """Base IPAM exception with enhanced context."""

    def __init__(self, message: str, error_code: str = None, context: Dict[str, Any] = None):
        super().__init__(message)
        self.error_code = error_code or "IPAM_ERROR"
        self.context = context or {}
        self.timestamp = datetime.now(timezone.utc)


class CapacityExhausted(IPAMError):
    """Address space capacity exhausted."""

    def __init__(self, message: str, resource_type: str = None, capacity: int = None, allocated: int = None):
        super().__init__(
            message,
            "CAPACITY_EXHAUSTED",
            {"resource_type": resource_type, "capacity": capacity, "allocated": allocated},
        )


class QuotaExceeded(IPAMError):
    """User quota exceeded."""

    def __init__(self, message: str, quota_type: str = None, limit: int = None, current: int = None):
        super().__init__(
            message, "QUOTA_EXCEEDED", {"quota_type": quota_type, "limit": limit, "current": current}
        )


class RegionNotFound(IPAMError):
    """Region does not exist or is not accessible."""

    def __init__(self, message: str, region_id: str = None):
        super().__init__(message, "REGION_NOT_FOUND", {"region_id": region_id})


class CountryNotFound(IPAMError):
    """Country does not exist in mapping."""

    def __init__(self, message: str, country: str = None):
        super().__init__(message, "COUNTRY_NOT_FOUND", {"country": country})


class DuplicateAllocation(IPAMError):
    """Duplicate allocation detected."""

    def __init__(self, message: str, resource_type: str = None, identifier: str = None):
        super().__init__(
            message, "DUPLICATE_ALLOCATION", {"resource_type": resource_type, "identifier": identifier}
        )


class ValidationError(IPAMError):
    """Input validation failed."""

    def __init__(self, message: str, field: str = None, value: Any = None):
        super().__init__(message, "VALIDATION_ERROR", {"field": field, "value": str(value) if value else None})


# Dependency injection protocols
@runtime_checkable
class DatabaseManagerProtocol(Protocol):
    """Protocol for database manager dependency injection."""

    def get_collection(self, collection_name: str) -> Any: ...
    def get_tenant_collection(self, collection_name: str) -> Any: ...
    def log_query_start(self, collection: str, operation: str, context: Dict[str, Any]) -> float: ...
    def log_query_success(
        self, collection: str, operation: str, start_time: float, count: int, info: str = None
    ) -> None: ...
    def log_query_error(
        self, collection: str, operation: str, start_time: float, error: Exception, context: Dict[str, Any]
    ) -> None: ...


@runtime_checkable
class RedisManagerProtocol(Protocol):
    """Protocol for Redis manager dependency injection."""

    async def get_redis(self) -> Any: ...
    async def set_with_expiry(self, key: str, value: Any, expiry: int) -> None: ...
    async def get(self, key: str) -> Any: ...
    async def delete(self, key: str) -> None: ...


class IPAMManager:
    """
    Enterprise-grade IPAM management system with dependency injection and transaction safety.

    This manager implements comprehensive IP allocation management with:
    - Dependency injection for testability and modularity
    - Transaction safety using MongoDB sessions for critical operations
    - Comprehensive error handling with detailed context
    - Auto-allocation algorithms for optimal address space utilization
    - User isolation with independent namespaces
    - Redis caching for performance optimization
    - Comprehensive audit logging and performance metrics
    """

    def __init__(
        self,
        db_manager_instance: DatabaseManagerProtocol = None,
        redis_manager_instance: RedisManagerProtocol = None,
    ) -> None:
        """
        Initialize IPAMManager with dependency injection.

        Args:
            db_manager_instance: Database manager for data operations
            redis_manager_instance: Redis manager for caching
        """
        # Dependency injection with fallback to global instances
        self.db_manager = db_manager_instance or db_manager
        self.redis_manager = redis_manager_instance or redis_manager

        self.logger = logger
        self.logger.debug("IPAMManager initialized with dependency injection")

        # Cache for frequently accessed data
        self._cache_ttl = 300  # 5 minutes default cache TTL

    async def _resolve_username(self, user_id: str) -> str:
        """
        Try to resolve a human-friendly username for a given user identifier.

        Tries to look up the `users` collection by ObjectId(_id) first, then
        by username fallback. If not found, returns the provided user_id as-is.
        """
        try:
            users_collection = self.db_manager.get_collection("users")
            # Try by ObjectId first
            try:
                obj_id = ObjectId(user_id)
                user_doc = await users_collection.find_one({"_id": obj_id}, {"username": 1})
            except Exception:
                user_doc = await users_collection.find_one({"username": user_id}, {"username": 1})

            if user_doc and "username" in user_doc:
                return user_doc["username"]
        except Exception:
            # Any error here should not block allocation; fall back to passed id
            pass

        return user_id

    # ==================== Country Mapping Methods ====================

    async def get_country_mapping(self, country: str) -> Dict[str, Any]:
        """
        Get country mapping with Redis caching (24hr TTL).

        Args:
            country: Country name

        Returns:
            Dict containing country mapping details

        Raises:
            CountryNotFound: If country does not exist in mapping
        """
        cache_key = f"ipam:country_mapping:{country}"

        # Try cache first
        try:
            cached = await self.redis_manager.get(cache_key)
            if cached:
                self.logger.debug("Cache hit: operation=get_country_mapping key=%s country=%s", cache_key, country)
                return cached
            else:
                self.logger.debug("Cache miss: operation=get_country_mapping key=%s country=%s", cache_key, country)
        except Exception as e:
            self.logger.warning("Cache error: operation=get_country_mapping key=%s error=%s", cache_key, str(e))

        # Query database
        start_time = self.db_manager.log_query_start(
            "continent_country_mapping", "get_country_mapping", {"country": country}
        )

        try:
            collection = self.db_manager.get_collection("continent_country_mapping")
            mapping = await collection.find_one({"country": country})

            if not mapping:
                self.db_manager.log_query_error(
                    "continent_country_mapping",
                    "get_country_mapping",
                    start_time,
                    CountryNotFound(f"Country not found: {country}"),
                    {"country": country},
                )
                raise CountryNotFound(f"Country not found: {country}", country=country)

            # Convert ObjectId to string for JSON serialization
            mapping["_id"] = str(mapping["_id"])

            # Cache the result
            try:
                await self.redis_manager.set_with_expiry(cache_key, mapping, COUNTRY_MAPPING_CACHE_TTL)
            except Exception as e:
                self.logger.warning("Redis cache write failed for country mapping: %s", e)

            self.db_manager.log_query_success(
                "continent_country_mapping", "get_country_mapping", start_time, 1, f"Found mapping for {country}"
            )

            return mapping

        except CountryNotFound:
            raise
        except Exception as e:
            self.db_manager.log_query_error(
                "continent_country_mapping", "get_country_mapping", start_time, e, {"country": country}
            )
            self.logger.error("Failed to get country mapping for %s: %s", country, e, exc_info=True)
            raise IPAMError(f"Failed to get country mapping: {str(e)}")

    async def get_all_countries(self, continent: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all countries with optional continent filtering.

        Args:
            continent: Optional continent filter

        Returns:
            List of country mappings
        """
        start_time = self.db_manager.log_query_start(
            "continent_country_mapping", "get_all_countries", {"continent": continent}
        )

        try:
            collection = self.db_manager.get_collection("continent_country_mapping")

            query = {}
            if continent:
                query["continent"] = continent

            cursor = collection.find(query).sort("country", 1)
            countries = await cursor.to_list(length=None)

            # Convert ObjectIds to strings
            for country in countries:
                country["_id"] = str(country["_id"])

            self.db_manager.log_query_success(
                "continent_country_mapping",
                "get_all_countries",
                start_time,
                len(countries),
                f"Found {len(countries)} countries",
            )

            return countries

        except Exception as e:
            self.db_manager.log_query_error(
                "continent_country_mapping", "get_all_countries", start_time, e, {"continent": continent}
            )
            self.logger.error("Failed to get all countries: %s", e, exc_info=True)
            raise IPAMError(f"Failed to get countries: {str(e)}")

    async def get_country_by_x_octet(self, x_octet: int) -> Dict[str, Any]:
        """
        Get country by X octet for IP interpretation.

        Args:
            x_octet: X octet value (0-255)

        Returns:
            Dict containing country mapping details

        Raises:
            CountryNotFound: If no country found for X octet
        """
        cache_key = f"ipam:x_octet_mapping:{x_octet}"

        # Try cache first
        try:
            cached = await self.redis_manager.get(cache_key)
            if cached:
                self.logger.debug("Cache hit: operation=get_country_by_x_octet key=%s x_octet=%d", cache_key, x_octet)
                return cached
            else:
                self.logger.debug("Cache miss: operation=get_country_by_x_octet key=%s x_octet=%d", cache_key, x_octet)
        except Exception as e:
            self.logger.warning("Cache error: operation=get_country_by_x_octet key=%s error=%s", cache_key, str(e))

        # Query database
        start_time = self.db_manager.log_query_start(
            "continent_country_mapping", "get_country_by_x_octet", {"x_octet": x_octet}
        )

        try:
            collection = self.db_manager.get_collection("continent_country_mapping")
            mapping = await collection.find_one({"x_start": {"$lte": x_octet}, "x_end": {"$gte": x_octet}})

            if not mapping:
                self.db_manager.log_query_error(
                    "continent_country_mapping",
                    "get_country_by_x_octet",
                    start_time,
                    CountryNotFound(f"No country found for X octet: {x_octet}"),
                    {"x_octet": x_octet},
                )
                raise CountryNotFound(f"No country found for X octet: {x_octet}")

            # Convert ObjectId to string
            mapping["_id"] = str(mapping["_id"])

            # Cache the result
            try:
                await self.redis_manager.set_with_expiry(cache_key, mapping, COUNTRY_MAPPING_CACHE_TTL)
            except Exception as e:
                self.logger.warning("Redis cache write failed for X octet mapping: %s", e)

            self.db_manager.log_query_success(
                "continent_country_mapping",
                "get_country_by_x_octet",
                start_time,
                1,
                f"Found country for X={x_octet}",
            )

            return mapping

        except CountryNotFound:
            raise
        except Exception as e:
            self.db_manager.log_query_error(
                "continent_country_mapping", "get_country_by_x_octet", start_time, e, {"x_octet": x_octet}
            )
            self.logger.error("Failed to get country by X octet %d: %s", x_octet, e, exc_info=True)
            raise IPAMError(f"Failed to get country by X octet: {str(e)}")

    # ==================== Auto-Allocation Algorithms ====================

    async def find_next_xy(self, user_id: str, country: str) -> Tuple[int, int]:
        """
        Find next available X.Y combination within country's X range.

        Algorithm:
        1. Get country's X range (e.g., India: 0-29)
        2. For each X in range (starting from x_start):
            a. Query allocated Y octets for this user and X
            b. If count < 256:
                - Find lowest Y not in allocated set (0-255)
                - Return (X, Y)
        3. If all X values exhausted, raise CapacityExhausted

        Optimization: Cache allocated Y sets per (user_id, X) in Redis
        with TTL of 60 seconds to reduce database queries.

        Args:
            user_id: User ID for isolation
            country: Country name

        Returns:
            Tuple of (x_octet, y_octet)

        Raises:
            CapacityExhausted: If no available X.Y combinations
            CountryNotFound: If country does not exist
        """
        start_time = time.time()
        self.logger.debug("Finding next X.Y for user %s in country %s", user_id, country)

        # Get country mapping
        mapping = await self.get_country_mapping(country)
        x_start = mapping["x_start"]
        x_end = mapping["x_end"]

        # Iterate through X range
        for x_octet in range(x_start, x_end + 1):
            cache_key = f"ipam:allocated_y:{user_id}:{x_octet}"

            # Try cache first
            allocated_y_set = None
            try:
                cached = await self.redis_manager.get(cache_key)
                if cached:
                    allocated_y_set = set(cached)
                    self.logger.debug(
                        "Cache hit: operation=find_next_xy key=%s user_id=%s x_octet=%d allocated_count=%d",
                        cache_key,
                        user_id,
                        x_octet,
                        len(allocated_y_set),
                    )
                else:
                    self.logger.debug("Cache miss: operation=find_next_xy key=%s user_id=%s x_octet=%d", cache_key, user_id, x_octet)
            except Exception as e:
                self.logger.warning("Cache error: operation=find_next_xy key=%s error=%s", cache_key, str(e))

            # Query database if not cached
            if allocated_y_set is None:
                try:
                    collection = self.db_manager.get_tenant_collection("ipam_regions")
                    cursor = collection.find(
                        {"user_id": user_id, "x_octet": x_octet}, {"y_octet": 1, "_id": 0}
                    )
                    allocated_y_list = await cursor.to_list(length=None)
                    allocated_y_set = {doc["y_octet"] for doc in allocated_y_list}

                    # Cache the result
                    try:
                        await self.redis_manager.set_with_expiry(
                            cache_key, list(allocated_y_set), ALLOCATED_Y_CACHE_TTL
                        )
                    except Exception as e:
                        self.logger.warning("Redis cache write failed for allocated Y: %s", e)

                except Exception as e:
                    self.logger.error("Failed to query allocated Y octets: %s", e, exc_info=True)
                    raise IPAMError(f"Failed to query allocated regions: {str(e)}")

            # Check if this X has capacity
            if len(allocated_y_set) < 256:
                # Calculate utilization for this X value
                x_utilization = (len(allocated_y_set) / 256) * 100

                # Log capacity warning if approaching threshold
                if x_utilization >= 80:
                    self.logger.warning(
                        "Capacity warning: user=%s country=%s x_octet=%d allocated=%d capacity=256 utilization=%.1f%%",
                        user_id,
                        country,
                        x_octet,
                        len(allocated_y_set),
                        x_utilization,
                    )

                # Find lowest available Y
                for y_octet in range(256):
                    if y_octet not in allocated_y_set:
                        duration = time.time() - start_time
                        self.logger.info(
                            "Auto-allocation success: operation=find_next_xy user=%s country=%s x=%d y=%d allocated=%d capacity=256 utilization=%.1f%% duration_ms=%.1f",
                            user_id,
                            country,
                            x_octet,
                            y_octet,
                            len(allocated_y_set),
                            x_utilization,
                            duration * 1000,
                        )
                        return (x_octet, y_octet)

        # All X values exhausted
        total_capacity = (x_end - x_start + 1) * 256
        duration = time.time() - start_time
        self.logger.error(
            "Capacity exhausted: operation=find_next_xy user=%s country=%s x_range=%d-%d allocated=%d capacity=%d utilization=100.0%% duration_ms=%.1f",
            user_id,
            country,
            x_start,
            x_end,
            total_capacity,
            total_capacity,
            duration * 1000,
        )
        raise CapacityExhausted(
            f"No available addresses in country {country}",
            resource_type="region",
            capacity=total_capacity,
            allocated=total_capacity,
        )

    async def find_next_z(self, user_id: str, region_id: str) -> int:
        """
        Find next available Z octet within region.

        Algorithm:
        1. Query allocated Z octets for this user and region
        2. Find lowest Z not in allocated set (1-254, excluding 0 and 255)
        3. If count >= 254, raise CapacityExhausted

        Args:
            user_id: User ID for isolation
            region_id: Region ID

        Returns:
            Z octet value (1-254)

        Raises:
            CapacityExhausted: If region is full (254 hosts allocated)
        """
        start_time = time.time()
        self.logger.debug("Finding next Z for user %s in region %s", user_id, region_id)

        try:
            collection = self.db_manager.get_tenant_collection("ipam_hosts")

            # Query allocated Z octets
            cursor = collection.find(
                {"user_id": user_id, "region_id": ObjectId(region_id)}, {"z_octet": 1, "_id": 0}
            )
            allocated_z_list = await cursor.to_list(length=None)
            allocated_z_set = {doc["z_octet"] for doc in allocated_z_list}

            # Calculate utilization
            region_utilization = (len(allocated_z_set) / 254) * 100

            # Check capacity
            if len(allocated_z_set) >= 254:
                duration = time.time() - start_time
                self.logger.error(
                    "Capacity exhausted: operation=find_next_z user=%s region=%s allocated=%d capacity=254 utilization=100.0%% duration_ms=%.1f",
                    user_id,
                    region_id,
                    len(allocated_z_set),
                    duration * 1000,
                )
                raise CapacityExhausted(
                    f"Region is full (254 hosts allocated)",
                    resource_type="host",
                    capacity=254,
                    allocated=254,
                )

            # Log capacity warning if approaching threshold
            if region_utilization >= 90:
                self.logger.warning(
                    "Capacity warning: user=%s region=%s allocated=%d capacity=254 utilization=%.1f%%",
                    user_id,
                    region_id,
                    len(allocated_z_set),
                    region_utilization,
                )

            # Find lowest available Z (1-254)
            for z_octet in range(1, 255):
                if z_octet not in allocated_z_set:
                    duration = time.time() - start_time
                    self.logger.info(
                        "Auto-allocation success: operation=find_next_z user=%s region=%s z=%d allocated=%d capacity=254 utilization=%.1f%% duration_ms=%.1f",
                        user_id,
                        region_id,
                        z_octet,
                        len(allocated_z_set),
                        region_utilization,
                        duration * 1000,
                    )
                    return z_octet

            # Should never reach here if capacity check is correct
            raise CapacityExhausted(
                f"Region is full (254 hosts allocated)",
                resource_type="host",
                capacity=254,
                allocated=len(allocated_z_set),
            )

        except CapacityExhausted:
            raise
        except Exception as e:
            self.logger.error("Failed to find next Z for region %s: %s", region_id, e, exc_info=True)
            raise IPAMError(f"Failed to find next available host address: {str(e)}")

    # ==================== Quota Management Methods ====================

    async def check_user_quota(self, user_id: str, resource_type: str) -> Dict[str, Any]:
        """
        Check user quota before allocation.

        Args:
            user_id: User ID
            resource_type: "region" or "host"

        Returns:
            Dict with quota information and availability

        Raises:
            QuotaExceeded: If quota is exceeded
        """
        quota_info = await self.get_user_quota(user_id)

        if resource_type == "region":
            current = quota_info["region_count"]
            limit = quota_info["region_quota"]
        elif resource_type == "host":
            current = quota_info["host_count"]
            limit = quota_info["host_quota"]
        else:
            raise ValidationError(f"Invalid resource type: {resource_type}", field="resource_type", value=resource_type)

        # Calculate usage percentage
        usage_percent = (current / limit) * 100 if limit > 0 else 0
        warning = usage_percent >= (QUOTA_WARNING_THRESHOLD * 100)

        # Log quota check with detailed context
        self.logger.info(
            "Quota check: user=%s resource=%s current=%d limit=%d available=%d usage=%.1f%%",
            user_id,
            resource_type,
            current,
            limit,
            limit - current,
            usage_percent,
        )

        # Check if quota exceeded
        if current >= limit:
            self.logger.warning(
                "Quota exceeded: user=%s resource=%s current=%d limit=%d usage=100.0%% - allocation denied",
                user_id,
                resource_type,
                current,
                limit,
            )
            raise QuotaExceeded(
                f"{resource_type.capitalize()} quota exceeded",
                quota_type=resource_type,
                limit=limit,
                current=current,
            )

        # Log warning if approaching quota threshold
        if warning:
            self.logger.warning(
                "Quota warning: user=%s resource=%s current=%d limit=%d usage=%.1f%% threshold=%.0f%%",
                user_id,
                resource_type,
                current,
                limit,
                usage_percent,
                QUOTA_WARNING_THRESHOLD * 100,
            )

        return {
            "current": current,
            "limit": limit,
            "available": limit - current,
            "usage_percent": usage_percent,
            "warning": warning,
        }

    async def get_user_quota(self, user_id: str) -> Dict[str, Any]:
        """
        Get user quota with Redis caching (60s TTL).

        Args:
            user_id: User ID

        Returns:
            Dict containing quota information
        """
        cache_key = f"ipam:user_quota:{user_id}"

        # Try cache first
        try:
            cached = await self.redis_manager.get(cache_key)
            if cached:
                self.logger.debug("Cache hit: operation=get_user_quota key=%s user_id=%s", cache_key, user_id)
                return cached
            else:
                self.logger.debug("Cache miss: operation=get_user_quota key=%s user_id=%s", cache_key, user_id)
        except Exception as e:
            self.logger.warning("Cache error: operation=get_user_quota key=%s error=%s", cache_key, str(e))

        # Query database
        start_time = self.db_manager.log_query_start("ipam_user_quotas", "get_user_quota", {"user_id": user_id})

        try:
            collection = self.db_manager.get_tenant_collection("ipam_user_quotas")
            quota_doc = await collection.find_one({"user_id": user_id})

            if not quota_doc:
                # Create default quota document
                quota_doc = {
                    "user_id": user_id,
                    "region_quota": DEFAULT_REGION_QUOTA,
                    "host_quota": DEFAULT_HOST_QUOTA,
                    "region_count": 0,
                    "host_count": 0,
                    "last_updated": datetime.now(timezone.utc),
                }
                await collection.insert_one(quota_doc)
                self.logger.info("Created default quota for user %s", user_id)

            # Convert ObjectId to string
            if "_id" in quota_doc:
                quota_doc["_id"] = str(quota_doc["_id"])

            # Cache the result
            try:
                await self.redis_manager.set_with_expiry(cache_key, quota_doc, USER_QUOTA_CACHE_TTL)
            except Exception as e:
                self.logger.warning("Redis cache write failed for user quota: %s", e)

            self.db_manager.log_query_success(
                "ipam_user_quotas", "get_user_quota", start_time, 1, f"Found quota for {user_id}"
            )

            return quota_doc

        except Exception as e:
            self.db_manager.log_query_error("ipam_user_quotas", "get_user_quota", start_time, e, {"user_id": user_id})
            self.logger.error("Failed to get user quota for %s: %s", user_id, e, exc_info=True)
            raise IPAMError(f"Failed to get user quota: {str(e)}")

    async def update_quota_counter(
        self, user_id: str, resource_type: str, delta: int, session: ClientSession = None
    ) -> None:
        """
        Update quota counter atomically.

        Args:
            user_id: User ID
            resource_type: "region" or "host"
            delta: Change amount (positive or negative)
            session: Optional MongoDB session for transactions
        """
        start_time = self.db_manager.log_query_start(
            "ipam_user_quotas", "update_quota_counter", {"user_id": user_id, "resource_type": resource_type, "delta": delta}
        )

        try:
            collection = self.db_manager.get_tenant_collection("ipam_user_quotas")

            # Determine field to update
            if resource_type == "region":
                field = "region_count"
            elif resource_type == "host":
                field = "host_count"
            else:
                raise ValidationError(f"Invalid resource type: {resource_type}", field="resource_type", value=resource_type)

            # Atomic update
            update_doc = {
                "$inc": {field: delta},
                "$set": {"last_updated": datetime.now(timezone.utc)},
            }

            if session:
                await collection.update_one({"user_id": user_id}, update_doc, upsert=True, session=session)
            else:
                await collection.update_one({"user_id": user_id}, update_doc, upsert=True)

            # Invalidate cache
            cache_key = f"ipam:user_quota:{user_id}"
            try:
                await self.redis_manager.delete(cache_key)
            except Exception as e:
                self.logger.warning("Failed to invalidate quota cache: %s", e)

            self.db_manager.log_query_success(
                "ipam_user_quotas",
                "update_quota_counter",
                start_time,
                1,
                f"Updated {resource_type} count by {delta}",
            )

            self.logger.debug("Updated quota counter for user %s: %s %+d", user_id, resource_type, delta)

        except Exception as e:
            self.db_manager.log_query_error(
                "ipam_user_quotas",
                "update_quota_counter",
                start_time,
                e,
                {"user_id": user_id, "resource_type": resource_type, "delta": delta},
            )
            self.logger.error("Failed to update quota counter: %s", e, exc_info=True)
            raise IPAMError(f"Failed to update quota counter: {str(e)}")

    # ==================== Region Allocation Methods ====================

    @handle_errors(
        operation_name="allocate_region",
        retry_config=RetryConfig(
            max_attempts=MAX_RETRY_ATTEMPTS,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            retryable_exceptions=[PyMongoError, DuplicateKeyError],
            non_retryable_exceptions=[QuotaExceeded, CapacityExhausted, ValidationError],
        ),
        timeout=30.0,
        user_friendly_errors=True,
    )
    async def allocate_region(
        self,
        user_id: str,
        country: str,
        region_name: str,
        description: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Allocate a new region with auto-allocation and transaction support.

        Args:
            user_id: User ID for isolation
            country: Country name
            region_name: User-provided region name
            description: Optional description
            tags: Optional key-value tags

        Returns:
            Dict containing region allocation details

        Raises:
            QuotaExceeded: If user quota exceeded
            CapacityExhausted: If country capacity exhausted
            DuplicateAllocation: If region name already exists
            ValidationError: If input validation fails
        """
        start_time = time.time()
        operation_context = {
            "user_id": user_id,
            "country": country,
            "region_name": region_name,
            "operation": "allocate_region",
        }
        db_start_time = self.db_manager.log_query_start("ipam_regions", "allocate_region", operation_context)

        try:
            # Validate inputs
            if not region_name or len(region_name.strip()) == 0:
                raise ValidationError("Region name is required", field="region_name", value=region_name)

            if len(region_name) > 100:
                raise ValidationError("Region name too long (max 100 characters)", field="region_name", value=region_name)

            # Check quota
            quota_info = await self.check_user_quota(user_id, "region")
            self.logger.debug("Quota check passed for user %s: %s", user_id, quota_info)

            # Get country mapping
            mapping = await self.get_country_mapping(country)
            continent = mapping["continent"]

            # Check for duplicate region name
            collection = self.db_manager.get_tenant_collection("ipam_regions")
            existing = await collection.find_one({"user_id": user_id, "country": country, "region_name": region_name})
            if existing:
                raise DuplicateAllocation(
                    f"Region name '{region_name}' already exists in {country}",
                    resource_type="region",
                    identifier=region_name,
                )

            # Attempt allocation with retry logic
            for attempt in range(MAX_RETRY_ATTEMPTS):
                try:
                    # Find next available X.Y
                    x_octet, y_octet = await self.find_next_xy(user_id, country)

                    # Build region document
                    now = datetime.now(timezone.utc)
                    # Resolve human-friendly owner name where possible
                    owner_name = await self._resolve_username(user_id)

                    region_doc = {
                        "user_id": user_id,
                        "owner_id": user_id,
                        "owner": owner_name,
                        "country": country,
                        "continent": continent,
                        "x_octet": x_octet,
                        "y_octet": y_octet,
                        "cidr": f"10.{x_octet}.{y_octet}.0/24",
                        "region_name": region_name,
                        "description": description or "",
                        "status": "Active",
                        "tags": tags or {},
                        "comments": [],
                        "created_at": now,
                        "updated_at": now,
                        "created_by": user_id,
                        "updated_by": user_id,
                    }

                    # Use transactions if supported
                    if getattr(self.db_manager, "transactions_supported", False):
                        session = await self.db_manager.client.start_session()
                        try:
                            async with session.start_transaction():
                                # Insert region
                                result = await collection.insert_one(region_doc, session=session)
                                region_doc["_id"] = result.inserted_id

                                # Update quota counter
                                await self.update_quota_counter(user_id, "region", 1, session=session)

                                self.logger.info(
                                    "Region allocated with transaction: %s for user %s in %s (X=%d, Y=%d)",
                                    region_name,
                                    user_id,
                                    country,
                                    x_octet,
                                    y_octet,
                                )
                        finally:
                            await session.end_session()
                    else:
                        # Fallback without transactions
                        result = await collection.insert_one(region_doc)
                        region_doc["_id"] = result.inserted_id

                        # Update quota counter
                        await self.update_quota_counter(user_id, "region", 1)

                        self.logger.info(
                            "Region allocated (no transaction): %s for user %s in %s (X=%d, Y=%d)",
                            region_name,
                            user_id,
                            country,
                            x_octet,
                            y_octet,
                        )

                    # Invalidate cache
                    cache_key = f"ipam:allocated_y:{user_id}:{x_octet}"
                    try:
                        await self.redis_manager.delete(cache_key)
                    except Exception as e:
                        self.logger.warning("Failed to invalidate allocated Y cache: %s", e)

                    # Log success
                    duration = time.time() - start_time
                    self.db_manager.log_query_success(
                        "ipam_regions",
                        "allocate_region",
                        db_start_time,
                        1,
                        f"Allocated region {region_name} at {x_octet}.{y_octet}",
                    )

                    # Convert ObjectId to string
                    region_doc["_id"] = str(region_doc["_id"])

                    # Add quota info to response
                    region_doc["quota_info"] = quota_info

                    self.logger.info(
                        "Allocation success: operation=allocate_region user=%s country=%s region=%s cidr=%s x=%d y=%d quota_used=%d/%d duration_ms=%.1f result=success",
                        user_id,
                        country,
                        region_name,
                        region_doc["cidr"],
                        x_octet,
                        y_octet,
                        quota_info["current"] + 1,
                        quota_info["limit"],
                        duration * 1000,
                    )

                    return region_doc

                except DuplicateKeyError as e:
                    # Concurrent allocation conflict - retry
                    if attempt < MAX_RETRY_ATTEMPTS - 1:
                        backoff = RETRY_BACKOFF_BASE * (2**attempt)
                        self.logger.warning(
                            "Concurrent conflict: operation=allocate_region user=%s country=%s x=%d y=%d attempt=%d/%d backoff_ms=%.1f - retrying",
                            user_id,
                            country,
                            x_octet,
                            y_octet,
                            attempt + 1,
                            MAX_RETRY_ATTEMPTS,
                            backoff * 1000,
                        )
                        await asyncio.sleep(backoff)
                        continue
                    else:
                        self.logger.error(
                            "Concurrent conflict: operation=allocate_region user=%s country=%s x=%d y=%d attempt=%d/%d - max retries exceeded",
                            user_id,
                            country,
                            x_octet,
                            y_octet,
                            attempt + 1,
                            MAX_RETRY_ATTEMPTS,
                        )
                        raise DuplicateAllocation(
                            "Failed to allocate region after multiple attempts (concurrent conflict)",
                            resource_type="region",
                            identifier=f"{x_octet}.{y_octet}",
                        )

        except (QuotaExceeded, CapacityExhausted, DuplicateAllocation, ValidationError, CountryNotFound) as err:
            # Expected errors - don't wrap
            self.db_manager.log_query_error("ipam_regions", "allocate_region", db_start_time, err, operation_context)
            raise
        except Exception as err:
            self.db_manager.log_query_error("ipam_regions", "allocate_region", db_start_time, err, operation_context)
            self.logger.error("Failed to allocate region: %s", err, exc_info=True)
            raise IPAMError(f"Failed to allocate region: {str(err)}")

    # ==================== Host Allocation Methods ====================

    @handle_errors(
        operation_name="allocate_host",
        retry_config=RetryConfig(
            max_attempts=MAX_RETRY_ATTEMPTS,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            retryable_exceptions=[PyMongoError, DuplicateKeyError],
            non_retryable_exceptions=[QuotaExceeded, CapacityExhausted, ValidationError, RegionNotFound],
        ),
        timeout=30.0,
        user_friendly_errors=True,
    )
    async def allocate_host(
        self,
        user_id: str,
        region_id: str,
        hostname: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Allocate a new host with auto-allocation and transaction support.

        Args:
            user_id: User ID for isolation
            region_id: Region ID
            hostname: User-provided hostname
            metadata: Optional metadata (device_type, os_type, application, etc.)

        Returns:
            Dict containing host allocation details

        Raises:
            QuotaExceeded: If user quota exceeded
            CapacityExhausted: If region capacity exhausted
            RegionNotFound: If region does not exist or not owned by user
            DuplicateAllocation: If hostname already exists in region
            ValidationError: If input validation fails
        """
        start_time = time.time()
        operation_context = {
            "user_id": user_id,
            "region_id": region_id,
            "hostname": hostname,
            "operation": "allocate_host",
        }
        db_start_time = self.db_manager.log_query_start("ipam_hosts", "allocate_host", operation_context)

        try:
            # Validate inputs
            if not hostname or len(hostname.strip()) == 0:
                raise ValidationError("Hostname is required", field="hostname", value=hostname)

            if len(hostname) > 100:
                raise ValidationError("Hostname too long (max 100 characters)", field="hostname", value=hostname)

            # Check quota
            quota_info = await self.check_user_quota(user_id, "host")
            self.logger.debug("Quota check passed for user %s: %s", user_id, quota_info)

            # Get and validate region
            regions_collection = self.db_manager.get_tenant_collection("ipam_regions")
            region = await regions_collection.find_one({"_id": ObjectId(region_id), "user_id": user_id})

            if not region:
                raise RegionNotFound(f"Region not found or not accessible: {region_id}", region_id=region_id)

            if region["status"] != "Active":
                raise ValidationError(
                    f"Region is not active (status: {region['status']})", field="region_status", value=region["status"]
                )

            x_octet = region["x_octet"]
            y_octet = region["y_octet"]

            # Check for duplicate hostname
            hosts_collection = self.db_manager.get_tenant_collection("ipam_hosts")
            existing = await hosts_collection.find_one(
                {"user_id": user_id, "region_id": ObjectId(region_id), "hostname": hostname}
            )
            if existing:
                raise DuplicateAllocation(
                    f"Hostname '{hostname}' already exists in region",
                    resource_type="host",
                    identifier=hostname,
                )

            # Extract metadata
            metadata = metadata or {}
            device_type = metadata.get("device_type", "")
            os_type = metadata.get("os_type", "")
            application = metadata.get("application", "")
            cost_center = metadata.get("cost_center", "")
            purpose = metadata.get("purpose", "")
            notes = metadata.get("notes", "")
            tags = metadata.get("tags", {})

            # Attempt allocation with retry logic
            for attempt in range(MAX_RETRY_ATTEMPTS):
                try:
                    # Find next available Z
                    z_octet = await self.find_next_z(user_id, region_id)

                    # Build host document
                    now = datetime.now(timezone.utc)
                    # Resolve human-friendly owner name where possible
                    owner_name = await self._resolve_username(user_id)

                    host_doc = {
                        "user_id": user_id,
                        "owner_id": user_id,
                        "owner": owner_name,
                        "region_id": ObjectId(region_id),
                        "x_octet": x_octet,
                        "y_octet": y_octet,
                        "z_octet": z_octet,
                        "ip_address": f"10.{x_octet}.{y_octet}.{z_octet}",
                        "hostname": hostname,
                        "device_type": device_type,
                        "os_type": os_type,
                        "application": application,
                        "cost_center": cost_center,
                        "purpose": purpose,
                        "status": "Active",
                        "tags": tags,
                        "notes": notes,
                        "comments": [],
                        "created_at": now,
                        "updated_at": now,
                        "created_by": user_id,
                        "updated_by": user_id,
                    }

                    # Use transactions if supported
                    if getattr(self.db_manager, "transactions_supported", False):
                        session = await self.db_manager.client.start_session()
                        try:
                            async with session.start_transaction():
                                # Insert host
                                result = await hosts_collection.insert_one(host_doc, session=session)
                                host_doc["_id"] = result.inserted_id

                                # Update quota counter
                                await self.update_quota_counter(user_id, "host", 1, session=session)

                                self.logger.info(
                                    "Host allocated with transaction: %s for user %s at %s",
                                    hostname,
                                    user_id,
                                    host_doc["ip_address"],
                                )
                        finally:
                            await session.end_session()
                    else:
                        # Fallback without transactions
                        result = await hosts_collection.insert_one(host_doc)
                        host_doc["_id"] = result.inserted_id

                        # Update quota counter
                        await self.update_quota_counter(user_id, "host", 1)

                        self.logger.info(
                            "Host allocated (no transaction): %s for user %s at %s",
                            hostname,
                            user_id,
                            host_doc["ip_address"],
                        )

                    # Log success
                    duration = time.time() - start_time
                    self.db_manager.log_query_success(
                        "ipam_hosts",
                        "allocate_host",
                        db_start_time,
                        1,
                        f"Allocated host {hostname} at {host_doc['ip_address']}",
                    )

                    # Convert ObjectIds to strings
                    host_doc["_id"] = str(host_doc["_id"])
                    host_doc["region_id"] = str(host_doc["region_id"])

                    # Add quota info and region context to response
                    host_doc["quota_info"] = quota_info
                    host_doc["region_name"] = region["region_name"]
                    host_doc["country"] = region["country"]
                    host_doc["continent"] = region["continent"]

                    self.logger.info(
                        "Allocation success: operation=allocate_host user=%s region=%s hostname=%s ip=%s x=%d y=%d z=%d quota_used=%d/%d duration_ms=%.1f result=success",
                        user_id,
                        region_id,
                        hostname,
                        host_doc["ip_address"],
                        x_octet,
                        y_octet,
                        z_octet,
                        quota_info["current"] + 1,
                        quota_info["limit"],
                        duration * 1000,
                    )

                    return host_doc

                except DuplicateKeyError as e:
                    # Concurrent allocation conflict - retry
                    if attempt < MAX_RETRY_ATTEMPTS - 1:
                        backoff = RETRY_BACKOFF_BASE * (2**attempt)
                        self.logger.warning(
                            "Concurrent conflict: operation=allocate_host user=%s region=%s x=%d y=%d z=%d attempt=%d/%d backoff_ms=%.1f - retrying",
                            user_id,
                            region_id,
                            x_octet,
                            y_octet,
                            z_octet,
                            attempt + 1,
                            MAX_RETRY_ATTEMPTS,
                            backoff * 1000,
                        )
                        await asyncio.sleep(backoff)
                        continue
                    else:
                        self.logger.error(
                            "Concurrent conflict: operation=allocate_host user=%s region=%s x=%d y=%d z=%d attempt=%d/%d - max retries exceeded",
                            user_id,
                            region_id,
                            x_octet,
                            y_octet,
                            z_octet,
                            attempt + 1,
                            MAX_RETRY_ATTEMPTS,
                        )
                        raise DuplicateAllocation(
                            "Failed to allocate host after multiple attempts (concurrent conflict)",
                            resource_type="host",
                            identifier=f"{x_octet}.{y_octet}.{z_octet}",
                        )

        except (QuotaExceeded, CapacityExhausted, DuplicateAllocation, ValidationError, RegionNotFound) as err:
            # Expected errors - don't wrap
            self.db_manager.log_query_error("ipam_hosts", "allocate_host", db_start_time, err, operation_context)
            raise
        except Exception as err:
            self.db_manager.log_query_error("ipam_hosts", "allocate_host", db_start_time, err, operation_context)
            self.logger.error("Failed to allocate host: %s", err, exc_info=True)
            raise IPAMError(f"Failed to allocate host: {str(err)}")

    @handle_errors(
        operation_name="allocate_hosts_batch",
        retry_config=RetryConfig(
            max_attempts=MAX_RETRY_ATTEMPTS,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            retryable_exceptions=[PyMongoError],
            non_retryable_exceptions=[QuotaExceeded, CapacityExhausted, ValidationError, RegionNotFound],
        ),
        timeout=60.0,
        user_friendly_errors=True,
    )
    async def allocate_hosts_batch(
        self,
        user_id: str,
        region_id: str,
        count: int,
        hostname_prefix: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Allocate multiple hosts in a single transaction.

        Args:
            user_id: User ID for isolation
            region_id: Region ID
            count: Number of hosts to allocate
            hostname_prefix: Prefix for generated hostnames (e.g., "web-server")
            metadata: Optional metadata applied to all hosts

        Returns:
            Dict containing batch allocation results with success/failure details

        Raises:
            QuotaExceeded: If user quota exceeded
            CapacityExhausted: If region capacity exhausted
            RegionNotFound: If region does not exist or not owned by user
            ValidationError: If input validation fails (e.g., count > 100)
        """
        start_time = time.time()
        operation_context = {
            "user_id": user_id,
            "region_id": region_id,
            "count": count,
            "hostname_prefix": hostname_prefix,
            "operation": "allocate_hosts_batch",
        }
        db_start_time = self.db_manager.log_query_start("ipam_hosts", "allocate_hosts_batch", operation_context)

        try:
            # Validate inputs
            if count <= 0:
                raise ValidationError("Count must be positive", field="count", value=count)

            if count > 100:
                raise ValidationError("Batch size limit exceeded (max 100 hosts)", field="count", value=count)

            if not hostname_prefix or len(hostname_prefix.strip()) == 0:
                raise ValidationError("Hostname prefix is required", field="hostname_prefix", value=hostname_prefix)

            # Check quota (ensure user has enough quota for all hosts)
            quota_info = await self.check_user_quota(user_id, "host")
            if quota_info["available"] < count:
                raise QuotaExceeded(
                    f"Insufficient quota for batch allocation (need {count}, have {quota_info['available']})",
                    quota_type="host",
                    limit=quota_info["limit"],
                    current=quota_info["current"],
                )

            # Get and validate region
            regions_collection = self.db_manager.get_tenant_collection("ipam_regions")
            region = await regions_collection.find_one({"_id": ObjectId(region_id), "user_id": user_id})

            if not region:
                raise RegionNotFound(f"Region not found or not accessible: {region_id}", region_id=region_id)

            if region["status"] != "Active":
                raise ValidationError(
                    f"Region is not active (status: {region['status']})", field="region_status", value=region["status"]
                )

            x_octet = region["x_octet"]
            y_octet = region["y_octet"]

            # Get currently allocated Z octets
            hosts_collection = self.db_manager.get_tenant_collection("ipam_hosts")
            cursor = hosts_collection.find(
                {"user_id": user_id, "region_id": ObjectId(region_id)}, {"z_octet": 1, "_id": 0}
            )
            allocated_z_list = await cursor.to_list(length=None)
            allocated_z_set = {doc["z_octet"] for doc in allocated_z_list}

            # Check capacity
            available_capacity = 254 - len(allocated_z_set)
            if available_capacity < count:
                raise CapacityExhausted(
                    f"Insufficient capacity in region (need {count}, have {available_capacity})",
                    resource_type="host",
                    capacity=254,
                    allocated=len(allocated_z_set),
                )

            # Find consecutive Z values
            z_octets = []
            for z in range(1, 255):
                if z not in allocated_z_set:
                    z_octets.append(z)
                    if len(z_octets) == count:
                        break

            if len(z_octets) < count:
                raise CapacityExhausted(
                    f"Could not find {count} available addresses",
                    resource_type="host",
                    capacity=254,
                    allocated=len(allocated_z_set),
                )

            # Extract metadata
            metadata = metadata or {}
            device_type = metadata.get("device_type", "")
            os_type = metadata.get("os_type", "")
            application = metadata.get("application", "")
            cost_center = metadata.get("cost_center", "")
            purpose = metadata.get("purpose", "")
            notes = metadata.get("notes", "")
            tags = metadata.get("tags", {})

            # Build host documents
            now = datetime.now(timezone.utc)
            host_docs = []
            for i, z_octet in enumerate(z_octets):
                hostname = f"{hostname_prefix}-{i + 1:03d}"  # e.g., "web-server-001"
                # Resolve owner name once for the batch
                owner_name = await self._resolve_username(user_id)

                host_doc = {
                    "user_id": user_id,
                    "owner_id": user_id,
                    "owner": owner_name,
                    "region_id": ObjectId(region_id),
                    "x_octet": x_octet,
                    "y_octet": y_octet,
                    "z_octet": z_octet,
                    "ip_address": f"10.{x_octet}.{y_octet}.{z_octet}",
                    "hostname": hostname,
                    "device_type": device_type,
                    "os_type": os_type,
                    "application": application,
                    "cost_center": cost_center,
                    "purpose": purpose,
                    "status": "Active",
                    "tags": tags,
                    "notes": notes,
                    "comments": [],
                    "created_at": now,
                    "updated_at": now,
                    "created_by": user_id,
                    "updated_by": user_id,
                }
                host_docs.append(host_doc)

            # Use transactions if supported
            success_count = 0
            failed_hosts = []

            if getattr(self.db_manager, "transactions_supported", False):
                session = await self.db_manager.client.start_session()
                try:
                    async with session.start_transaction():
                        # Insert all hosts
                        result = await hosts_collection.insert_many(host_docs, session=session)
                        success_count = len(result.inserted_ids)

                        # Update quota counter
                        await self.update_quota_counter(user_id, "host", success_count, session=session)

                        self.logger.info(
                            "Batch allocated %d hosts with transaction for user %s in region %s",
                            success_count,
                            user_id,
                            region_id,
                        )
                finally:
                    await session.end_session()
            else:
                # Fallback without transactions - insert one by one
                for host_doc in host_docs:
                    try:
                        result = await hosts_collection.insert_one(host_doc)
                        host_doc["_id"] = result.inserted_id
                        success_count += 1
                    except Exception as e:
                        self.logger.warning("Failed to insert host %s: %s", host_doc["hostname"], e)
                        failed_hosts.append({"hostname": host_doc["hostname"], "error": str(e)})

                # Update quota counter for successful allocations
                if success_count > 0:
                    await self.update_quota_counter(user_id, "host", success_count)

                self.logger.info(
                    "Batch allocated %d/%d hosts (no transaction) for user %s in region %s",
                    success_count,
                    count,
                    user_id,
                    region_id,
                )

            # Log success
            duration = time.time() - start_time
            self.db_manager.log_query_success(
                "ipam_hosts",
                "allocate_hosts_batch",
                db_start_time,
                success_count,
                f"Batch allocated {success_count}/{count} hosts",
            )

            # Build response
            allocated_hosts = []
            for host_doc in host_docs[:success_count]:
                allocated_hosts.append({
                    "hostname": host_doc["hostname"],
                    "ip_address": host_doc["ip_address"],
                    "z_octet": host_doc["z_octet"],
                })

            result = {
                "success": success_count == count,
                "total_requested": count,
                "total_allocated": success_count,
                "total_failed": len(failed_hosts),
                "allocated_hosts": allocated_hosts,
                "failed_hosts": failed_hosts,
                "region_id": region_id,
                "region_name": region["region_name"],
                "country": region["country"],
                "duration_seconds": duration,
            }

            if success_count == count:
                self.logger.info(
                    "Batch allocation success: operation=allocate_hosts_batch user=%s region=%s prefix=%s requested=%d allocated=%d failed=%d duration_ms=%.1f result=success",
                    user_id,
                    region_id,
                    hostname_prefix,
                    count,
                    success_count,
                    len(failed_hosts),
                    duration * 1000,
                )
            else:
                self.logger.warning(
                    "Batch allocation partial: operation=allocate_hosts_batch user=%s region=%s prefix=%s requested=%d allocated=%d failed=%d duration_ms=%.1f result=partial",
                    user_id,
                    region_id,
                    hostname_prefix,
                    count,
                    success_count,
                    len(failed_hosts),
                    duration * 1000,
                )

            return result

        except (QuotaExceeded, CapacityExhausted, ValidationError, RegionNotFound) as err:
            # Expected errors - don't wrap
            self.db_manager.log_query_error("ipam_hosts", "allocate_hosts_batch", db_start_time, err, operation_context)
            raise
        except Exception as err:
            self.db_manager.log_query_error("ipam_hosts", "allocate_hosts_batch", db_start_time, err, operation_context)
            self.logger.error("Failed to batch allocate hosts: %s", err, exc_info=True)
            raise IPAMError(f"Failed to batch allocate hosts: {str(err)}")

    # ==================== Region Query Methods ====================

    async def get_regions(
        self,
        user_id: str,
        filters: Optional[Dict[str, Any]] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """
        Get regions with filtering and pagination.

        Args:
            user_id: User ID for isolation
            filters: Optional filters (status, owner, country, tags, date_from, date_to)
            page: Page number (1-indexed)
            page_size: Items per page (max 100)

        Returns:
            Dict containing regions list and pagination info
        """
        start_time = self.db_manager.log_query_start(
            "ipam_regions", "get_regions", {"user_id": user_id, "filters": filters}
        )

        try:
            # Validate pagination
            if page < 1:
                page = 1
            if page_size < 1 or page_size > 100:
                page_size = 50

            # Build query with user isolation
            query = {"user_id": user_id}

            # Apply filters
            filters = filters or {}
            if "status" in filters:
                query["status"] = filters["status"]
            if "owner" in filters:
                # Support filtering by either human-friendly owner name or owner id
                owner_val = filters["owner"]
                query["$or"] = [{"owner": owner_val}, {"owner_id": owner_val}]
            if "country" in filters:
                query["country"] = filters["country"]
            if "continent" in filters:
                query["continent"] = filters["continent"]
            if "tags" in filters and isinstance(filters["tags"], dict):
                for key, value in filters["tags"].items():
                    query[f"tags.{key}"] = value

            # Date range filters
            if "date_from" in filters or "date_to" in filters:
                date_query = {}
                if "date_from" in filters:
                    date_query["$gte"] = filters["date_from"]
                if "date_to" in filters:
                    date_query["$lte"] = filters["date_to"]
                if date_query:
                    query["created_at"] = date_query

            # Get total count
            collection = self.db_manager.get_tenant_collection("ipam_regions")
            total_count = await collection.count_documents(query)

            # Calculate pagination
            skip = (page - 1) * page_size
            total_pages = (total_count + page_size - 1) // page_size

            # Query with pagination
            cursor = collection.find(query).sort("created_at", -1).skip(skip).limit(page_size)
            regions = await cursor.to_list(length=page_size)

            # Enrich regions with host counts and utilization
            hosts_collection = self.db_manager.get_tenant_collection("ipam_hosts")
            for region in regions:
                region["_id"] = str(region["_id"])
                region_id_obj = ObjectId(region["_id"])
                
                # Count allocated hosts
                allocated_hosts = await hosts_collection.count_documents({
                    "user_id": user_id,
                    "region_id": region_id_obj
                })
                region["allocated_hosts"] = allocated_hosts
                
                # Calculate utilization percentage (254 usable IPs in /24)
                region["utilization_percentage"] = round((allocated_hosts / 254) * 100, 2) if allocated_hosts > 0 else 0.0

            self.db_manager.log_query_success(
                "ipam_regions", "get_regions", start_time, len(regions), f"Found {len(regions)} regions"
            )

            return {
                "regions": regions,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total_count": total_count,
                    "total_pages": total_pages,
                    "has_next": page < total_pages,
                    "has_prev": page > 1,
                },
            }

        except Exception as e:
            self.db_manager.log_query_error(
                "ipam_regions", "get_regions", start_time, e, {"user_id": user_id, "filters": filters}
            )
            self.logger.error("Failed to get regions: %s", e, exc_info=True)
            raise IPAMError(f"Failed to get regions: {str(e)}")

    async def get_region_by_id(self, user_id: str, region_id: str) -> Dict[str, Any]:
        """
        Get region by ID with ownership validation.

        Args:
            user_id: User ID for isolation
            region_id: Region ID

        Returns:
            Dict containing region details

        Raises:
            RegionNotFound: If region does not exist or not owned by user
        """
        start_time = self.db_manager.log_query_start(
            "ipam_regions", "get_region_by_id", {"user_id": user_id, "region_id": region_id}
        )

        try:
            collection = self.db_manager.get_tenant_collection("ipam_regions")
            region = await collection.find_one({"_id": ObjectId(region_id), "user_id": user_id})

            if not region:
                self.db_manager.log_query_error(
                    "ipam_regions",
                    "get_region_by_id",
                    start_time,
                    RegionNotFound(f"Region not found: {region_id}"),
                    {"user_id": user_id, "region_id": region_id},
                )
                raise RegionNotFound(f"Region not found or not accessible: {region_id}", region_id=region_id)

            # Convert ObjectId to string
            region["_id"] = str(region["_id"])
            
            # Enrich with host count and utilization
            hosts_collection = self.db_manager.get_tenant_collection("ipam_hosts")
            allocated_hosts = await hosts_collection.count_documents({
                "user_id": user_id,
                "region_id": ObjectId(region_id)
            })
            region["allocated_hosts"] = allocated_hosts
            region["utilization_percentage"] = round((allocated_hosts / 254) * 100, 2) if allocated_hosts > 0 else 0.0

            self.db_manager.log_query_success(
                "ipam_regions", "get_region_by_id", start_time, 1, f"Found region {region_id}"
            )

            return region

        except RegionNotFound:
            raise
        except Exception as e:
            self.db_manager.log_query_error(
                "ipam_regions", "get_region_by_id", start_time, e, {"user_id": user_id, "region_id": region_id}
            )
            self.logger.error("Failed to get region by ID: %s", e, exc_info=True)
            raise IPAMError(f"Failed to get region: {str(e)}")

    # ==================== Update and Lifecycle Operations ====================

    @handle_errors(
        operation_name="update_region",
        timeout=30.0,
        user_friendly_errors=True,
    )
    async def update_region(
        self,
        user_id: str,
        region_id: str,
        updates: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Update region with ownership validation and audit trail.

        Args:
            user_id: User ID for isolation
            region_id: Region ID
            updates: Dict containing fields to update (region_name, description, owner, status, tags)

        Returns:
            Dict containing updated region details

        Raises:
            RegionNotFound: If region does not exist or not owned by user
            ValidationError: If update validation fails
        """
        start_time = time.time()
        operation_context = {
            "user_id": user_id,
            "region_id": region_id,
            "updates": updates,
            "operation": "update_region",
        }
        db_start_time = self.db_manager.log_query_start("ipam_regions", "update_region", operation_context)

        try:
            # Get existing region with ownership validation
            collection = self.db_manager.get_tenant_collection("ipam_regions")
            region = await collection.find_one({"_id": ObjectId(region_id), "user_id": user_id})

            if not region:
                raise RegionNotFound(f"Region not found or not accessible: {region_id}", region_id=region_id)

            # Build update document with allowed fields only
            update_doc = {}
            allowed_fields = ["region_name", "description", "owner", "status", "tags"]
            field_changes = []

            for field in allowed_fields:
                if field in updates:
                    new_value = updates[field]
                    old_value = region.get(field)

                    # Validate specific fields
                    if field == "region_name":
                        if not new_value or len(str(new_value).strip()) == 0:
                            raise ValidationError("Region name cannot be empty", field="region_name", value=new_value)
                        if len(str(new_value)) > 100:
                            raise ValidationError(
                                "Region name too long (max 100 characters)", field="region_name", value=new_value
                            )

                        # Check for duplicate region name (if changed)
                        if new_value != old_value:
                            existing = await collection.find_one({
                                "user_id": user_id,
                                "country": region["country"],
                                "region_name": new_value,
                                "_id": {"$ne": ObjectId(region_id)}
                            })
                            if existing:
                                raise DuplicateAllocation(
                                    f"Region name '{new_value}' already exists in {region['country']}",
                                    resource_type="region",
                                    identifier=new_value,
                                )

                    elif field == "status":
                        valid_statuses = ["Active", "Reserved", "Retired"]
                        if new_value not in valid_statuses:
                            raise ValidationError(
                                f"Invalid status (must be one of: {', '.join(valid_statuses)})",
                                field="status",
                                value=new_value,
                            )

                    elif field == "tags":
                        if not isinstance(new_value, dict):
                            raise ValidationError("Tags must be a dictionary", field="tags", value=type(new_value))

                    # Record change
                    if new_value != old_value:
                        update_doc[field] = new_value
                        field_changes.append({
                            "field": field,
                            "old_value": old_value,
                            "new_value": new_value,
                        })

            # If no changes, return existing region
            if not update_doc:
                self.logger.info("No changes detected for region %s", region_id)
                region["_id"] = str(region["_id"])
                return region

            # Add update metadata
            now = datetime.now(timezone.utc)
            update_doc["updated_at"] = now
            update_doc["updated_by"] = user_id

            # Perform update
            result = await collection.update_one(
                {"_id": ObjectId(region_id), "user_id": user_id},
                {"$set": update_doc}
            )

            if result.modified_count == 0:
                raise IPAMError("Failed to update region (no documents modified)")

            # Log audit trail
            await self._log_audit_event(
                user_id=user_id,
                action_type="update",
                resource_type="region",
                resource_id=region_id,
                cidr=region["cidr"],
                snapshot=region,
                changes=field_changes,
                reason=updates.get("reason", "Region updated"),
            )

            # Invalidate Redis caches
            await self._invalidate_region_caches(user_id, region["x_octet"], region_id)

            # Get updated region
            updated_region = await collection.find_one({"_id": ObjectId(region_id)})
            updated_region["_id"] = str(updated_region["_id"])

            # Log success
            duration = time.time() - start_time
            self.db_manager.log_query_success(
                "ipam_regions",
                "update_region",
                db_start_time,
                1,
                f"Updated region {region_id} with {len(field_changes)} changes",
            )

            self.logger.info(
                "Update success: operation=update_region user=%s region=%s changes=%d fields=%s duration_ms=%.1f result=success",
                user_id,
                region_id,
                len(field_changes),
                ",".join([c["field"] for c in field_changes]),
                duration * 1000,
            )

            return updated_region

        except (RegionNotFound, ValidationError, DuplicateAllocation):
            self.db_manager.log_query_error("ipam_regions", "update_region", db_start_time, e, operation_context)
            raise
        except Exception as e:
            self.db_manager.log_query_error("ipam_regions", "update_region", db_start_time, e, operation_context)
            self.logger.error("Failed to update region: %s", e, exc_info=True)
            raise IPAMError(f"Failed to update region: {str(e)}")

            if not region:
                self.db_manager.log_query_error(
                    "ipam_regions",
                    "get_region_by_id",
                    start_time,
                    RegionNotFound(f"Region not found: {region_id}"),
                    {"user_id": user_id, "region_id": region_id},
                )
                raise RegionNotFound(f"Region not found or not accessible: {region_id}", region_id=region_id)

            # Convert ObjectId to string
            region["_id"] = str(region["_id"])

            # Get host count for this region
            hosts_collection = self.db_manager.get_tenant_collection("ipam_hosts")
            host_count = await hosts_collection.count_documents(
                {"user_id": user_id, "region_id": ObjectId(region_id)}
            )
            region["host_count"] = host_count

            self.db_manager.log_query_success(
                "ipam_regions", "get_region_by_id", start_time, 1, f"Found region {region_id}"
            )

            return region

        except RegionNotFound:
            raise
        except Exception as e:
            self.db_manager.log_query_error(
                "ipam_regions", "get_region_by_id", start_time, e, {"user_id": user_id, "region_id": region_id}
            )
            self.logger.error("Failed to get region by ID: %s", e, exc_info=True)
            raise IPAMError(f"Failed to get region: {str(e)}")

    async def get_regions_by_country(self, user_id: str, country: str) -> List[Dict[str, Any]]:
        """
        Get all regions for a specific country.

        Args:
            user_id: User ID for isolation
            country: Country name

        Returns:
            List of regions in the country
        """
        start_time = self.db_manager.log_query_start(
            "ipam_regions", "get_regions_by_country", {"user_id": user_id, "country": country}
        )

        try:
            collection = self.db_manager.get_tenant_collection("ipam_regions")
            cursor = collection.find({"user_id": user_id, "country": country}).sort("created_at", -1)
            regions = await cursor.to_list(length=None)

            # Convert ObjectIds to strings
            for region in regions:
                region["_id"] = str(region["_id"])

            self.db_manager.log_query_success(
                "ipam_regions",
                "get_regions_by_country",
                start_time,
                len(regions),
                f"Found {len(regions)} regions in {country}",
            )

            return regions

        except Exception as e:
            self.db_manager.log_query_error(
                "ipam_regions", "get_regions_by_country", start_time, e, {"user_id": user_id, "country": country}
            )
            self.logger.error("Failed to get regions by country: %s", e, exc_info=True)
            raise IPAMError(f"Failed to get regions by country: {str(e)}")

    # ==================== Host Query Methods ====================

    async def get_hosts(
        self,
        user_id: str,
        filters: Optional[Dict[str, Any]] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """
        Get hosts with filtering and pagination.

        Args:
            user_id: User ID for isolation
            filters: Optional filters (status, hostname, region_id, device_type, tags, date_from, date_to)
            page: Page number (1-indexed)
            page_size: Items per page (max 100)

        Returns:
            Dict containing hosts list and pagination info
        """
        start_time = self.db_manager.log_query_start(
            "ipam_hosts", "get_hosts", {"user_id": user_id, "filters": filters}
        )

        try:
            # Validate pagination
            if page < 1:
                page = 1
            if page_size < 1 or page_size > 100:
                page_size = 50

            # Build query with user isolation
            query = {"user_id": user_id}

            # Apply filters
            filters = filters or {}
            if "status" in filters:
                query["status"] = filters["status"]
            if "hostname" in filters:
                # Support partial hostname matching
                query["hostname"] = {"$regex": filters["hostname"], "$options": "i"}
            if "region_id" in filters:
                query["region_id"] = ObjectId(filters["region_id"])
            if "device_type" in filters:
                query["device_type"] = filters["device_type"]
            if "os_type" in filters:
                query["os_type"] = filters["os_type"]
            if "application" in filters:
                query["application"] = filters["application"]
            if "owner" in filters:
                # Support filtering by either human-friendly owner name or owner id
                owner_val = filters["owner"]
                query["$or"] = [{"owner": owner_val}, {"owner_id": owner_val}]
            if "tags" in filters and isinstance(filters["tags"], dict):
                for key, value in filters["tags"].items():
                    query[f"tags.{key}"] = value

            # Date range filters
            if "date_from" in filters or "date_to" in filters:
                date_query = {}
                if "date_from" in filters:
                    date_query["$gte"] = filters["date_from"]
                if "date_to" in filters:
                    date_query["$lte"] = filters["date_to"]
                if date_query:
                    query["created_at"] = date_query

            # Get total count
            collection = self.db_manager.get_tenant_collection("ipam_hosts")
            total_count = await collection.count_documents(query)

            # Calculate pagination
            skip = (page - 1) * page_size
            total_pages = (total_count + page_size - 1) // page_size

            # Query with pagination
            cursor = collection.find(query).sort("created_at", -1).skip(skip).limit(page_size)
            hosts = await cursor.to_list(length=page_size)

            # Convert ObjectIds to strings
            for host in hosts:
                host["_id"] = str(host["_id"])
                host["region_id"] = str(host["region_id"])

            self.db_manager.log_query_success(
                "ipam_hosts", "get_hosts", start_time, len(hosts), f"Found {len(hosts)} hosts"
            )

            return {
                "hosts": hosts,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total_count": total_count,
                    "total_pages": total_pages,
                    "has_next": page < total_pages,
                    "has_prev": page > 1,
                },
            }

        except Exception as e:
            self.db_manager.log_query_error(
                "ipam_hosts", "get_hosts", start_time, e, {"user_id": user_id, "filters": filters}
            )
            self.logger.error("Failed to get hosts: %s", e, exc_info=True)
            raise IPAMError(f"Failed to get hosts: {str(e)}")

    async def get_host_by_id(self, user_id: str, host_id: str) -> Dict[str, Any]:
        """
        Get host by ID with ownership validation.

        Args:
            user_id: User ID for isolation
            host_id: Host ID

        Returns:
            Dict containing host details with region context

        Raises:
            IPAMError: If host does not exist or not owned by user
        """
        start_time = self.db_manager.log_query_start(
            "ipam_hosts", "get_host_by_id", {"user_id": user_id, "host_id": host_id}
        )

        try:
            collection = self.db_manager.get_tenant_collection("ipam_hosts")
            host = await collection.find_one({"_id": ObjectId(host_id), "user_id": user_id})

            if not host:
                self.db_manager.log_query_error(
                    "ipam_hosts",
                    "get_host_by_id",
                    start_time,
                    IPAMError(f"Host not found: {host_id}"),
                    {"user_id": user_id, "host_id": host_id},
                )
                raise IPAMError(f"Host not found or not accessible: {host_id}")

            # Convert ObjectIds to strings
            host["_id"] = str(host["_id"])
            region_id = str(host["region_id"])
            host["region_id"] = region_id

            # Get region context
            try:
                region = await self.get_region_by_id(user_id, region_id)
                host["region_name"] = region["region_name"]
                host["country"] = region["country"]
                host["continent"] = region["continent"]
            except Exception as e:
                self.logger.warning("Failed to get region context for host %s: %s", host_id, e)

            self.db_manager.log_query_success("ipam_hosts", "get_host_by_id", start_time, 1, f"Found host {host_id}")

            return host

        except IPAMError:
            raise
        except Exception as e:
            self.db_manager.log_query_error(
                "ipam_hosts", "get_host_by_id", start_time, e, {"user_id": user_id, "host_id": host_id}
            )
            self.logger.error("Failed to get host by ID: %s", e, exc_info=True)
            raise IPAMError(f"Failed to get host: {str(e)}")

    async def get_hosts_by_region(self, user_id: str, region_id: str) -> List[Dict[str, Any]]:
        """
        Get all hosts in a specific region.

        Args:
            user_id: User ID for isolation
            region_id: Region ID

        Returns:
            List of hosts in the region
        """
        start_time = self.db_manager.log_query_start(
            "ipam_hosts", "get_hosts_by_region", {"user_id": user_id, "region_id": region_id}
        )

        try:
            collection = self.db_manager.get_tenant_collection("ipam_hosts")
            cursor = collection.find({"user_id": user_id, "region_id": ObjectId(region_id)}).sort("z_octet", 1)
            hosts = await cursor.to_list(length=None)

            # Convert ObjectIds to strings
            for host in hosts:
                host["_id"] = str(host["_id"])
                host["region_id"] = str(host["region_id"])

            self.db_manager.log_query_success(
                "ipam_hosts",
                "get_hosts_by_region",
                start_time,
                len(hosts),
                f"Found {len(hosts)} hosts in region",
            )

            return hosts

        except Exception as e:
            self.db_manager.log_query_error(
                "ipam_hosts", "get_hosts_by_region", start_time, e, {"user_id": user_id, "region_id": region_id}
            )
            self.logger.error("Failed to get hosts by region: %s", e, exc_info=True)
            raise IPAMError(f"Failed to get hosts by region: {str(e)}")

    async def get_host_by_ip(self, user_id: str, ip_address: str) -> Dict[str, Any]:
        """
        Get host by IP address.

        Args:
            user_id: User ID for isolation
            ip_address: IP address (e.g., "10.1.2.3")

        Returns:
            Dict containing host details

        Raises:
            IPAMError: If host does not exist or not owned by user
        """
        start_time = self.db_manager.log_query_start(
            "ipam_hosts", "get_host_by_ip", {"user_id": user_id, "ip_address": ip_address}
        )

        try:
            collection = self.db_manager.get_tenant_collection("ipam_hosts")
            host = await collection.find_one({"user_id": user_id, "ip_address": ip_address})

            if not host:
                self.db_manager.log_query_error(
                    "ipam_hosts",
                    "get_host_by_ip",
                    start_time,
                    IPAMError(f"Host not found: {ip_address}"),
                    {"user_id": user_id, "ip_address": ip_address},
                )
                raise IPAMError(f"Host not found or not accessible: {ip_address}")

            # Convert ObjectIds to strings
            host["_id"] = str(host["_id"])
            region_id = str(host["region_id"])
            host["region_id"] = region_id

            # Get region context
            try:
                region = await self.get_region_by_id(user_id, region_id)
                host["region_name"] = region["region_name"]
                host["country"] = region["country"]
                host["continent"] = region["continent"]
            except Exception as e:
                self.logger.warning("Failed to get region context for host %s: %s", ip_address, e)

            self.db_manager.log_query_success(
                "ipam_hosts", "get_host_by_ip", start_time, 1, f"Found host {ip_address}"
            )

            return host

        except IPAMError:
            raise
        except Exception as e:
            self.db_manager.log_query_error(
                "ipam_hosts", "get_host_by_ip", start_time, e, {"user_id": user_id, "ip_address": ip_address}
            )
            self.logger.error("Failed to get host by IP: %s", e, exc_info=True)
            raise IPAMError(f"Failed to get host by IP: {str(e)}")

    # ==================== IP Address Interpretation ====================

    async def interpret_ip_address(self, user_id: str, ip_address: str) -> Dict[str, Any]:
        """
        Interpret IP address and return hierarchical allocation details.

        Returns hierarchical structure:
        Global Root (10.0.0.0/8) -> Continent -> Country -> Region -> Host

        Args:
            user_id: User ID for isolation
            ip_address: IP address in format "10.X.Y.Z"

        Returns:
            Dict containing hierarchical allocation details

        Raises:
            ValidationError: If IP address format is invalid
            IPAMError: If address is not allocated or not owned by user
        """
        start_time = self.db_manager.log_query_start(
            "ipam_hosts", "interpret_ip_address", {"user_id": user_id, "ip_address": ip_address}
        )

        try:
            # Parse IP address
            parts = ip_address.split(".")
            if len(parts) != 4:
                raise ValidationError("Invalid IP address format", field="ip_address", value=ip_address)

            try:
                octets = [int(part) for part in parts]
            except ValueError:
                raise ValidationError("Invalid IP address format", field="ip_address", value=ip_address)

            # Validate 10.0.0.0/8 range
            if octets[0] != 10:
                raise ValidationError(
                    "IP address must be in 10.0.0.0/8 range", field="ip_address", value=ip_address
                )

            for octet in octets:
                if octet < 0 or octet > 255:
                    raise ValidationError("Invalid octet value", field="ip_address", value=ip_address)

            x_octet, y_octet, z_octet = octets[1], octets[2], octets[3]

            # Build hierarchical response
            result = {
                "ip_address": ip_address,
                "hierarchy": {
                    "global_root": {
                        "cidr": "10.0.0.0/8",
                        "description": "Global IPAM Root",
                    }
                },
            }

            # Get country mapping from X octet
            try:
                country_mapping = await self.get_country_by_x_octet(x_octet)
                result["hierarchy"]["continent"] = {
                    "name": country_mapping["continent"],
                    "x_range": f"{country_mapping['x_start']}-{country_mapping['x_end']}",
                }
                result["hierarchy"]["country"] = {
                    "name": country_mapping["country"],
                    "code": country_mapping["code"],
                    "x_range": f"{country_mapping['x_start']}-{country_mapping['x_end']}",
                    "cidr": f"10.{country_mapping['x_start']}-{country_mapping['x_end']}.0.0/16",
                }
            except CountryNotFound:
                # X octet not mapped to any country
                result["hierarchy"]["continent"] = None
                result["hierarchy"]["country"] = None
                result["status"] = "unallocated"
                result["message"] = f"X octet {x_octet} is not mapped to any country"

                self.db_manager.log_query_success(
                    "ipam_hosts",
                    "interpret_ip_address",
                    start_time,
                    0,
                    f"IP {ip_address} not mapped (X={x_octet})",
                )
                return result

            # Look up region
            regions_collection = self.db_manager.get_tenant_collection("ipam_regions")
            region = await regions_collection.find_one({"user_id": user_id, "x_octet": x_octet, "y_octet": y_octet})

            if not region:
                # Region not allocated by this user
                result["hierarchy"]["region"] = None
                result["hierarchy"]["host"] = None
                result["status"] = "not_allocated"
                result["message"] = f"Region 10.{x_octet}.{y_octet}.0/24 is not allocated"

                self.db_manager.log_query_success(
                    "ipam_hosts",
                    "interpret_ip_address",
                    start_time,
                    0,
                    f"IP {ip_address} region not allocated",
                )
                return result

            # Add region details
            result["hierarchy"]["region"] = {
                "region_id": str(region["_id"]),
                "region_name": region["region_name"],
                "cidr": region["cidr"],
                "description": region.get("description", ""),
                "status": region["status"],
                "owner": region["owner"],
                "tags": region.get("tags", {}),
                "created_at": region["created_at"].isoformat() if isinstance(region["created_at"], datetime) else region["created_at"],
            }

            # Look up host
            hosts_collection = self.db_manager.get_tenant_collection("ipam_hosts")
            host = await hosts_collection.find_one(
                {"user_id": user_id, "x_octet": x_octet, "y_octet": y_octet, "z_octet": z_octet}
            )

            if not host:
                # Host not allocated
                result["hierarchy"]["host"] = None
                result["status"] = "region_allocated"
                result["message"] = f"Host {ip_address} is not allocated (region exists)"

                self.db_manager.log_query_success(
                    "ipam_hosts",
                    "interpret_ip_address",
                    start_time,
                    1,
                    f"IP {ip_address} region allocated, host not allocated",
                )
                return result

            # Add host details
            result["hierarchy"]["host"] = {
                "host_id": str(host["_id"]),
                "hostname": host["hostname"],
                "ip_address": host["ip_address"],
                "device_type": host.get("device_type", ""),
                "os_type": host.get("os_type", ""),
                "application": host.get("application", ""),
                "status": host["status"],
                "owner": host["owner"],
                "purpose": host.get("purpose", ""),
                "tags": host.get("tags", {}),
                "created_at": host["created_at"].isoformat() if isinstance(host["created_at"], datetime) else host["created_at"],
            }

            result["status"] = "fully_allocated"
            result["message"] = f"IP {ip_address} is fully allocated"

            self.db_manager.log_query_success(
                "ipam_hosts", "interpret_ip_address", start_time, 1, f"IP {ip_address} fully allocated"
            )

            return result

        except (ValidationError, CountryNotFound):
            self.db_manager.log_query_error(
                "ipam_hosts", "interpret_ip_address", start_time, e, {"user_id": user_id, "ip_address": ip_address}
            )
            raise
        except Exception as e:
            self.db_manager.log_query_error(
                "ipam_hosts", "interpret_ip_address", start_time, e, {"user_id": user_id, "ip_address": ip_address}
            )
            self.logger.error("Failed to interpret IP address: %s", e, exc_info=True)
            raise IPAMError(f"Failed to interpret IP address: {str(e)}")

    async def bulk_lookup_ips(self, user_id: str, ip_addresses: List[str]) -> Dict[str, Any]:
        """
        Lookup multiple IP addresses in a single request.

        Args:
            user_id: User ID for isolation
            ip_addresses: List of IP addresses to lookup

        Returns:
            Dict containing lookup results for each IP address
        """
        start_time = time.time()
        self.logger.debug("Bulk IP lookup for user %s: %d addresses", user_id, len(ip_addresses))

        results = []
        for ip_address in ip_addresses:
            try:
                result = await self.interpret_ip_address(user_id, ip_address)
                results.append(result)
            except Exception as e:
                # Include error in results instead of failing entire batch
                results.append({
                    "ip_address": ip_address,
                    "status": "error",
                    "error": str(e),
                    "hierarchy": None,
                })

        duration = time.time() - start_time
        self.logger.info("Bulk IP lookup completed in %.3fs: %d addresses", duration, len(ip_addresses))

        return {
            "total_count": len(ip_addresses),
            "results": results,
            "duration_seconds": duration,
        }

    # ==================== Search Functionality ====================

    async def search_allocations(
        self,
        user_id: str,
        search_params: Dict[str, Any],
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """
        Search allocations with multi-filter support.

        Supports:
        - IP/CIDR exact and partial matching
        - Hostname/region name case-insensitive partial matching with wildcards
        - Multi-filter AND logic (continent, country, status, owner, tags, date ranges)
        - Pagination

        Args:
            user_id: User ID for isolation
            search_params: Search parameters
            page: Page number (1-indexed)
            page_size: Items per page (max 100)

        Returns:
            Dict containing search results with hierarchical context
        """
        start_time = time.time()
        self.logger.debug("Search allocations for user %s: %s", user_id, search_params)

        try:
            # Validate pagination
            if page < 1:
                page = 1
            if page_size < 1 or page_size > 100:
                page_size = 50

            results = {
                "regions": [],
                "hosts": [],
                "pagination": {},
            }

            # Search regions
            if search_params.get("search_regions", True):
                region_query = {"user_id": user_id}

                # Apply filters
                if "continent" in search_params:
                    region_query["continent"] = search_params["continent"]
                if "country" in search_params:
                    region_query["country"] = search_params["country"]
                if "status" in search_params:
                    region_query["status"] = search_params["status"]
                if "owner" in search_params:
                    # Support filtering by either human-friendly owner name or owner id
                    owner_val = search_params["owner"]
                    region_query["$or"] = [{"owner": owner_val}, {"owner_id": owner_val}]
                if "region_name" in search_params:
                    # Case-insensitive partial matching
                    region_query["region_name"] = {"$regex": search_params["region_name"], "$options": "i"}
                if "tags" in search_params and isinstance(search_params["tags"], dict):
                    for key, value in search_params["tags"].items():
                        region_query[f"tags.{key}"] = value

                # Date range filters
                if "date_from" in search_params or "date_to" in search_params:
                    date_query = {}
                    if "date_from" in search_params:
                        date_query["$gte"] = search_params["date_from"]
                    if "date_to" in search_params:
                        date_query["$lte"] = search_params["date_to"]
                    if date_query:
                        region_query["created_at"] = date_query

                # CIDR matching
                if "cidr" in search_params:
                    region_query["cidr"] = {"$regex": search_params["cidr"], "$options": "i"}

                # Query regions
                regions_collection = self.db_manager.get_tenant_collection("ipam_regions")
                region_count = await regions_collection.count_documents(region_query)
                skip = (page - 1) * page_size

                cursor = regions_collection.find(region_query).sort("created_at", -1).skip(skip).limit(page_size)
                regions = await cursor.to_list(length=page_size)

                # Convert ObjectIds to strings
                for region in regions:
                    region["_id"] = str(region["_id"])
                    region["resource_type"] = "region"

                results["regions"] = regions

            # Search hosts
            if search_params.get("search_hosts", True):
                host_query = {"user_id": user_id}

                # Apply filters
                if "status" in search_params:
                    host_query["status"] = search_params["status"]
                if "owner" in search_params:
                    # Support filtering by either human-friendly owner name or owner id
                    owner_val = search_params["owner"]
                    host_query["$or"] = [{"owner": owner_val}, {"owner_id": owner_val}]
                if "hostname" in search_params:
                    # Case-insensitive partial matching
                    host_query["hostname"] = {"$regex": search_params["hostname"], "$options": "i"}
                if "device_type" in search_params:
                    host_query["device_type"] = search_params["device_type"]
                if "os_type" in search_params:
                    host_query["os_type"] = search_params["os_type"]
                if "application" in search_params:
                    host_query["application"] = search_params["application"]
                if "tags" in search_params and isinstance(search_params["tags"], dict):
                    for key, value in search_params["tags"].items():
                        host_query[f"tags.{key}"] = value

                # Date range filters
                if "date_from" in search_params or "date_to" in search_params:
                    date_query = {}
                    if "date_from" in search_params:
                        date_query["$gte"] = search_params["date_from"]
                    if "date_to" in search_params:
                        date_query["$lte"] = search_params["date_to"]
                    if date_query:
                        host_query["created_at"] = date_query

                # IP address matching
                if "ip_address" in search_params:
                    host_query["ip_address"] = {"$regex": search_params["ip_address"], "$options": "i"}

                # Query hosts
                hosts_collection = self.db_manager.get_tenant_collection("ipam_hosts")
                host_count = await hosts_collection.count_documents(host_query)
                skip = (page - 1) * page_size

                cursor = hosts_collection.find(host_query).sort("created_at", -1).skip(skip).limit(page_size)
                hosts = await cursor.to_list(length=page_size)

                # Convert ObjectIds to strings and add region context
                for host in hosts:
                    host["_id"] = str(host["_id"])
                    host["region_id"] = str(host["region_id"])
                    host["resource_type"] = "host"

                    # Add region context if needed
                    if search_params.get("include_context", False):
                        try:
                            region = await self.get_region_by_id(user_id, host["region_id"])
                            host["region_name"] = region["region_name"]
                            host["country"] = region["country"]
                            host["continent"] = region["continent"]
                        except Exception as e:
                            self.logger.warning("Failed to get region context: %s", e)

                results["hosts"] = hosts

            # Calculate pagination
            total_count = len(results["regions"]) + len(results["hosts"])
            total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1

            results["pagination"] = {
                "page": page,
                "page_size": page_size,
                "total_count": total_count,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1,
            }

            duration = time.time() - start_time
            results["duration_seconds"] = duration

            self.logger.info(
                "Search completed in %.3fs: %d regions, %d hosts",
                duration,
                len(results["regions"]),
                len(results["hosts"]),
            )

            return results

        except Exception as e:
            self.logger.error("Failed to search allocations: %s", e, exc_info=True)
            raise IPAMError(f"Failed to search allocations: {str(e)}")

    @handle_errors(
        operation_name="update_host",
        timeout=30.0,
        user_friendly_errors=True,
    )
    async def update_host(
        self,
        user_id: str,
        host_id: str,
        updates: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Update host with ownership validation and audit trail.

        Args:
            user_id: User ID for isolation
            host_id: Host ID
            updates: Dict containing fields to update (hostname, device_type, owner, purpose, status, tags, notes)

        Returns:
            Dict containing updated host details

        Raises:
            IPAMError: If host does not exist or not owned by user
            ValidationError: If update validation fails
        """
        start_time = time.time()
        operation_context = {
            "user_id": user_id,
            "host_id": host_id,
            "updates": updates,
            "operation": "update_host",
        }
        db_start_time = self.db_manager.log_query_start("ipam_hosts", "update_host", operation_context)

        try:
            # Get existing host with ownership validation
            collection = self.db_manager.get_tenant_collection("ipam_hosts")
            host = await collection.find_one({"_id": ObjectId(host_id), "user_id": user_id})

            if not host:
                raise IPAMError(f"Host not found or not accessible: {host_id}")

            # Build update document with allowed fields only
            update_doc = {}
            allowed_fields = ["hostname", "device_type", "owner", "purpose", "status", "tags", "notes", "os_type", "application", "cost_center"]
            field_changes = []

            for field in allowed_fields:
                if field in updates:
                    new_value = updates[field]
                    old_value = host.get(field)

                    # Validate specific fields
                    if field == "hostname":
                        if not new_value or len(str(new_value).strip()) == 0:
                            raise ValidationError("Hostname cannot be empty", field="hostname", value=new_value)
                        if len(str(new_value)) > 100:
                            raise ValidationError(
                                "Hostname too long (max 100 characters)", field="hostname", value=new_value
                            )

                        # Check for duplicate hostname (if changed)
                        if new_value != old_value:
                            existing = await collection.find_one({
                                "user_id": user_id,
                                "region_id": host["region_id"],
                                "hostname": new_value,
                                "_id": {"$ne": ObjectId(host_id)}
                            })
                            if existing:
                                raise DuplicateAllocation(
                                    f"Hostname '{new_value}' already exists in region",
                                    resource_type="host",
                                    identifier=new_value,
                                )

                    elif field == "status":
                        valid_statuses = ["Active", "Reserved", "Released"]
                        if new_value not in valid_statuses:
                            raise ValidationError(
                                f"Invalid status (must be one of: {', '.join(valid_statuses)})",
                                field="status",
                                value=new_value,
                            )

                    elif field == "tags":
                        if not isinstance(new_value, dict):
                            raise ValidationError("Tags must be a dictionary", field="tags", value=type(new_value))

                    elif field == "notes":
                        if new_value and len(str(new_value)) > 2000:
                            raise ValidationError(
                                "Notes too long (max 2000 characters)", field="notes", value=len(str(new_value))
                            )

                    # Record change
                    if new_value != old_value:
                        update_doc[field] = new_value
                        field_changes.append({
                            "field": field,
                            "old_value": old_value,
                            "new_value": new_value,
                        })

            # If no changes, return existing host
            if not update_doc:
                self.logger.info("No changes detected for host %s", host_id)
                host["_id"] = str(host["_id"])
                host["region_id"] = str(host["region_id"])
                return host

            # Add update metadata
            now = datetime.now(timezone.utc)
            update_doc["updated_at"] = now
            update_doc["updated_by"] = user_id

            # Perform update
            result = await collection.update_one(
                {"_id": ObjectId(host_id), "user_id": user_id},
                {"$set": update_doc}
            )

            if result.modified_count == 0:
                raise IPAMError("Failed to update host (no documents modified)")

            # Log audit trail
            await self._log_audit_event(
                user_id=user_id,
                action_type="update",
                resource_type="host",
                resource_id=host_id,
                ip_address=host["ip_address"],
                snapshot=host,
                changes=field_changes,
                reason=updates.get("reason", "Host updated"),
            )

            # Get updated host
            updated_host = await collection.find_one({"_id": ObjectId(host_id)})
            updated_host["_id"] = str(updated_host["_id"])
            updated_host["region_id"] = str(updated_host["region_id"])

            # Log success
            duration = time.time() - start_time
            self.db_manager.log_query_success(
                "ipam_hosts",
                "update_host",
                db_start_time,
                1,
                f"Updated host {host_id} with {len(field_changes)} changes",
            )

            self.logger.info(
                "Host update completed successfully in %.3fs: %s (%d changes)",
                duration,
                host_id,
                len(field_changes),
            )

            return updated_host

        except (ValidationError, DuplicateAllocation):
            self.db_manager.log_query_error("ipam_hosts", "update_host", db_start_time, e, operation_context)
            raise
        except Exception as e:
            self.db_manager.log_query_error("ipam_hosts", "update_host", db_start_time, e, operation_context)
            self.logger.error("Failed to update host: %s", e, exc_info=True)
            raise IPAMError(f"Failed to update host: {str(e)}")

    @handle_errors(
        operation_name="retire_allocation",
        timeout=60.0,
        user_friendly_errors=True,
    )
    async def retire_allocation(
        self,
        user_id: str,
        resource_type: str,
        resource_id: str,
        reason: str,
        cascade: bool = False,
    ) -> Dict[str, Any]:
        """
        Retire allocation with hard delete and audit trail.

        Process:
        1. Validate ownership
        2. Copy to audit history
        3. Delete from active collection (hard delete)
        4. If cascade=true for regions, retire all child hosts
        5. Update quota counters
        6. Invalidate Redis caches

        Args:
            user_id: User ID for isolation
            resource_type: "region" or "host"
            resource_id: Resource ID
            reason: Reason for retirement (required)
            cascade: If true, retire all child hosts when retiring a region

        Returns:
            Dict containing retirement result

        Raises:
            ValidationError: If resource_type invalid or reason missing
            IPAMError: If resource does not exist or not owned by user
        """
        start_time = time.time()
        operation_context = {
            "user_id": user_id,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "reason": reason,
            "cascade": cascade,
            "operation": "retire_allocation",
        }
        db_start_time = self.db_manager.log_query_start(
            f"ipam_{resource_type}s", "retire_allocation", operation_context
        )

        try:
            # Validate inputs
            if resource_type not in ["region", "host"]:
                raise ValidationError(
                    f"Invalid resource type (must be 'region' or 'host')",
                    field="resource_type",
                    value=resource_type,
                )

            if not reason or len(reason.strip()) == 0:
                raise ValidationError("Reason is required for retirement", field="reason", value=reason)

            # Get resource with ownership validation
            collection_name = f"ipam_{resource_type}s"
            collection = self.db_manager.get_collection(collection_name)
            resource = await collection.find_one({"_id": ObjectId(resource_id), "user_id": user_id})

            if not resource:
                raise IPAMError(f"{resource_type.capitalize()} not found or not accessible: {resource_id}")

            retired_count = 0
            child_hosts_retired = []

            # Handle region retirement with cascade
            if resource_type == "region" and cascade:
                # Get all child hosts
                hosts_collection = self.db_manager.get_tenant_collection("ipam_hosts")
                cursor = hosts_collection.find({"user_id": user_id, "region_id": ObjectId(resource_id)})
                child_hosts = await cursor.to_list(length=None)

                self.logger.info(
                    "Retiring region %s with cascade: found %d child hosts",
                    resource_id,
                    len(child_hosts),
                )

                # Retire each child host
                for host in child_hosts:
                    try:
                        # Copy host to audit history
                        await self._log_audit_event(
                            user_id=user_id,
                            action_type="retire",
                            resource_type="host",
                            resource_id=str(host["_id"]),
                            ip_address=host["ip_address"],
                            snapshot=host,
                            changes=[],
                            reason=f"Cascade retirement from region: {reason}",
                        )

                        # Hard delete host
                        await hosts_collection.delete_one({"_id": host["_id"]})

                        child_hosts_retired.append({
                            "host_id": str(host["_id"]),
                            "hostname": host["hostname"],
                            "ip_address": host["ip_address"],
                        })

                        retired_count += 1

                    except Exception as e:
                        self.logger.error("Failed to retire child host %s: %s", host["_id"], e)

                # Update host quota counter
                if retired_count > 0:
                    await self.update_quota_counter(user_id, "host", -retired_count)

            # Copy resource to audit history
            await self._log_audit_event(
                user_id=user_id,
                action_type="retire",
                resource_type=resource_type,
                resource_id=resource_id,
                cidr=resource.get("cidr") if resource_type == "region" else None,
                ip_address=resource.get("ip_address") if resource_type == "host" else None,
                snapshot=resource,
                changes=[],
                reason=reason,
            )

            # Hard delete resource from active collection
            result = await collection.delete_one({"_id": ObjectId(resource_id), "user_id": user_id})

            if result.deleted_count == 0:
                raise IPAMError(f"Failed to retire {resource_type} (no documents deleted)")

            # Update quota counter for the resource itself
            await self.update_quota_counter(user_id, resource_type, -1)

            # Invalidate Redis caches
            if resource_type == "region":
                await self._invalidate_region_caches(user_id, resource["x_octet"], resource_id)
            elif resource_type == "host":
                # Invalidate any host-related caches if needed
                pass

            # Log success
            duration = time.time() - start_time
            self.db_manager.log_query_success(
                collection_name,
                "retire_allocation",
                db_start_time,
                1 + retired_count,
                f"Retired {resource_type} {resource_id} and {retired_count} child hosts",
            )

            result_data = {
                "success": True,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "reason": reason,
                "cascade": cascade,
                "child_hosts_retired": len(child_hosts_retired),
                "child_hosts": child_hosts_retired,
                "duration_seconds": duration,
            }

            if resource_type == "region":
                result_data["cidr"] = resource["cidr"]
                result_data["region_name"] = resource["region_name"]
            elif resource_type == "host":
                result_data["ip_address"] = resource["ip_address"]
                result_data["hostname"] = resource["hostname"]

            self.logger.info(
                "%s retirement completed successfully in %.3fs: %s (%d total resources retired)",
                resource_type.capitalize(),
                duration,
                resource_id,
                1 + retired_count,
            )

            return result_data

        except (ValidationError,):
            self.db_manager.log_query_error(
                f"ipam_{resource_type}s", "retire_allocation", db_start_time, e, operation_context
            )
            raise
        except Exception as e:
            self.db_manager.log_query_error(
                f"ipam_{resource_type}s", "retire_allocation", db_start_time, e, operation_context
            )
            self.logger.error("Failed to retire allocation: %s", e, exc_info=True)
            raise IPAMError(f"Failed to retire {resource_type}: {str(e)}")

    @handle_errors(
        operation_name="bulk_release_hosts",
        timeout=60.0,
        user_friendly_errors=True,
    )
    async def bulk_release_hosts(
        self,
        user_id: str,
        host_ids: List[str],
        reason: str,
    ) -> Dict[str, Any]:
        """
        Bulk release hosts with transaction support.

        Args:
            user_id: User ID for isolation
            host_ids: List of host IDs to release
            reason: Reason for release (required)

        Returns:
            Dict containing success/failure status for each operation

        Raises:
            ValidationError: If inputs invalid
        """
        start_time = time.time()
        operation_context = {
            "user_id": user_id,
            "host_count": len(host_ids),
            "reason": reason,
            "operation": "bulk_release_hosts",
        }
        db_start_time = self.db_manager.log_query_start("ipam_hosts", "bulk_release_hosts", operation_context)

        try:
            # Validate inputs
            if not host_ids or len(host_ids) == 0:
                raise ValidationError("Host IDs list cannot be empty", field="host_ids", value=host_ids)

            if len(host_ids) > 100:
                raise ValidationError(
                    "Bulk release limit exceeded (max 100 hosts)", field="host_ids", value=len(host_ids)
                )

            if not reason or len(reason.strip()) == 0:
                raise ValidationError("Reason is required for bulk release", field="reason", value=reason)

            collection = self.db_manager.get_tenant_collection("ipam_hosts")
            success_results = []
            failure_results = []

            # Use transactions if supported
            if getattr(self.db_manager, "transactions_supported", False):
                session = await self.db_manager.client.start_session()
                try:
                    async with session.start_transaction():
                        for host_id in host_ids:
                            try:
                                # Get host with ownership validation
                                host = await collection.find_one(
                                    {"_id": ObjectId(host_id), "user_id": user_id},
                                    session=session
                                )

                                if not host:
                                    failure_results.append({
                                        "host_id": host_id,
                                        "error": "Host not found or not accessible",
                                    })
                                    continue

                                # Copy to audit history
                                await self._log_audit_event(
                                    user_id=user_id,
                                    action_type="release",
                                    resource_type="host",
                                    resource_id=host_id,
                                    ip_address=host["ip_address"],
                                    snapshot=host,
                                    changes=[],
                                    reason=reason,
                                )

                                # Hard delete
                                result = await collection.delete_one(
                                    {"_id": ObjectId(host_id), "user_id": user_id},
                                    session=session
                                )

                                if result.deleted_count > 0:
                                    success_results.append({
                                        "host_id": host_id,
                                        "hostname": host["hostname"],
                                        "ip_address": host["ip_address"],
                                    })
                                else:
                                    failure_results.append({
                                        "host_id": host_id,
                                        "error": "Failed to delete host",
                                    })

                            except Exception as e:
                                self.logger.error("Failed to release host %s: %s", host_id, e)
                                failure_results.append({
                                    "host_id": host_id,
                                    "error": str(e),
                                })

                        # Update quota counter for successful releases
                        if len(success_results) > 0:
                            await self.update_quota_counter(user_id, "host", -len(success_results), session=session)

                finally:
                    await session.end_session()
            else:
                # Fallback without transactions
                for host_id in host_ids:
                    try:
                        # Get host with ownership validation
                        host = await collection.find_one({"_id": ObjectId(host_id), "user_id": user_id})

                        if not host:
                            failure_results.append({
                                "host_id": host_id,
                                "error": "Host not found or not accessible",
                            })
                            continue

                        # Copy to audit history
                        await self._log_audit_event(
                            user_id=user_id,
                            action_type="release",
                            resource_type="host",
                            resource_id=host_id,
                            ip_address=host["ip_address"],
                            snapshot=host,
                            changes=[],
                            reason=reason,
                        )

                        # Hard delete
                        result = await collection.delete_one({"_id": ObjectId(host_id), "user_id": user_id})

                        if result.deleted_count > 0:
                            success_results.append({
                                "host_id": host_id,
                                "hostname": host["hostname"],
                                "ip_address": host["ip_address"],
                            })
                        else:
                            failure_results.append({
                                "host_id": host_id,
                                "error": "Failed to delete host",
                            })

                    except Exception as e:
                        self.logger.error("Failed to release host %s: %s", host_id, e)
                        failure_results.append({
                            "host_id": host_id,
                            "error": str(e),
                        })

                # Update quota counter for successful releases
                if len(success_results) > 0:
                    await self.update_quota_counter(user_id, "host", -len(success_results))

            # Log success
            duration = time.time() - start_time
            self.db_manager.log_query_success(
                "ipam_hosts",
                "bulk_release_hosts",
                db_start_time,
                len(success_results),
                f"Released {len(success_results)}/{len(host_ids)} hosts",
            )

            result_data = {
                "success": len(failure_results) == 0,
                "total_requested": len(host_ids),
                "total_released": len(success_results),
                "total_failed": len(failure_results),
                "released_hosts": success_results,
                "failed_hosts": failure_results,
                "reason": reason,
                "duration_seconds": duration,
            }

            self.logger.info(
                "Bulk host release completed in %.3fs: %d/%d successful",
                duration,
                len(success_results),
                len(host_ids),
            )

            return result_data

        except (ValidationError,):
            self.db_manager.log_query_error("ipam_hosts", "bulk_release_hosts", db_start_time, e, operation_context)
            raise
        except Exception as e:
            self.db_manager.log_query_error("ipam_hosts", "bulk_release_hosts", db_start_time, e, operation_context)
            self.logger.error("Failed to bulk release hosts: %s", e, exc_info=True)
            raise IPAMError(f"Failed to bulk release hosts: {str(e)}")

    @handle_errors(
        operation_name="reserve_allocation",
        timeout=30.0,
        user_friendly_errors=True,
    )
    async def reserve_allocation(
        self,
        user_id: str,
        resource_type: str,
        x: int,
        y: Optional[int] = None,
        z: Optional[int] = None,
        reason: str = "",
        expires_at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Reserve specific IP address or range.

        Args:
            user_id: User ID for isolation
            resource_type: "region" or "host"
            x: X octet value (0-255)
            y: Y octet value (0-255), required for host reservations
            z: Z octet value (1-254), required for host reservations
            reason: Reason for reservation
            expires_at: Optional expiration datetime

        Returns:
            Dict containing reservation details

        Raises:
            ValidationError: If inputs invalid
            DuplicateAllocation: If address already allocated or reserved
        """
        start_time = time.time()
        operation_context = {
            "user_id": user_id,
            "resource_type": resource_type,
            "x": x,
            "y": y,
            "z": z,
            "reason": reason,
            "expires_at": expires_at,
            "operation": "reserve_allocation",
        }
        db_start_time = self.db_manager.log_query_start(
            f"ipam_{resource_type}s", "reserve_allocation", operation_context
        )

        try:
            # Validate inputs
            if resource_type not in ["region", "host"]:
                raise ValidationError(
                    f"Invalid resource type (must be 'region' or 'host')",
                    field="resource_type",
                    value=resource_type,
                )

            if x < 0 or x > 255:
                raise ValidationError("X octet must be between 0 and 255", field="x", value=x)

            if resource_type == "region":
                if y is None:
                    raise ValidationError("Y octet is required for region reservations", field="y", value=y)
                if y < 0 or y > 255:
                    raise ValidationError("Y octet must be between 0 and 255", field="y", value=y)

            elif resource_type == "host":
                if y is None or z is None:
                    raise ValidationError(
                        "Y and Z octets are required for host reservations", field="y,z", value=f"{y},{z}"
                    )
                if y < 0 or y > 255:
                    raise ValidationError("Y octet must be between 0 and 255", field="y", value=y)
                if z < 1 or z > 254:
                    raise ValidationError("Z octet must be between 1 and 254", field="z", value=z)

            # Get country mapping for X octet
            country_mapping = await self.get_country_by_x_octet(x)

            # Check if already allocated
            collection_name = f"ipam_{resource_type}s"
            collection = self.db_manager.get_collection(collection_name)

            if resource_type == "region":
                existing = await collection.find_one({"user_id": user_id, "x_octet": x, "y_octet": y})
                if existing:
                    raise DuplicateAllocation(
                        f"Region {x}.{y} is already allocated or reserved",
                        resource_type="region",
                        identifier=f"{x}.{y}",
                    )

                # Create reservation document
                now = datetime.now(timezone.utc)
                owner_name = await self._resolve_username(user_id)
                reservation_doc = {
                    "user_id": user_id,
                    "owner_id": user_id,
                    "owner": owner_name,
                    "country": country_mapping["country"],
                    "continent": country_mapping["continent"],
                    "x_octet": x,
                    "y_octet": y,
                    "cidr": f"10.{x}.{y}.0/24",
                    "region_name": f"Reserved-{x}-{y}",
                    "description": reason or "Reserved allocation",
                    "status": "Reserved",
                    "tags": {"reservation": "true"},
                    "comments": [],
                    "expires_at": expires_at,
                    "created_at": now,
                    "updated_at": now,
                    "created_by": user_id,
                    "updated_by": user_id,
                }

                result = await collection.insert_one(reservation_doc)
                reservation_doc["_id"] = str(result.inserted_id)

                # Update quota counter
                await self.update_quota_counter(user_id, "region", 1)

                # Invalidate cache
                cache_key = f"ipam:allocated_y:{user_id}:{x}"
                try:
                    await self.redis_manager.delete(cache_key)
                except Exception as e:
                    self.logger.warning("Failed to invalidate cache: %s", e)

            elif resource_type == "host":
                existing = await collection.find_one({"user_id": user_id, "x_octet": x, "y_octet": y, "z_octet": z})
                if existing:
                    raise DuplicateAllocation(
                        f"Host {x}.{y}.{z} is already allocated or reserved",
                        resource_type="host",
                        identifier=f"{x}.{y}.{z}",
                    )

                # Check if region exists
                regions_collection = self.db_manager.get_tenant_collection("ipam_regions")
                region = await regions_collection.find_one({"user_id": user_id, "x_octet": x, "y_octet": y})

                if not region:
                    raise ValidationError(
                        f"Region {x}.{y} does not exist. Create region first before reserving hosts.",
                        field="region",
                        value=f"{x}.{y}",
                    )

                # Create reservation document
                now = datetime.now(timezone.utc)
                owner_name = await self._resolve_username(user_id)
                reservation_doc = {
                    "user_id": user_id,
                    "owner_id": user_id,
                    "owner": owner_name,
                    "region_id": region["_id"],
                    "x_octet": x,
                    "y_octet": y,
                    "z_octet": z,
                    "ip_address": f"10.{x}.{y}.{z}",
                    "hostname": f"reserved-{x}-{y}-{z}",
                    "device_type": "Reserved",
                    "os_type": "",
                    "application": "",
                    "cost_center": "",
                    "purpose": reason or "Reserved allocation",
                    "status": "Reserved",
                    "tags": {"reservation": "true"},
                    "notes": reason or "",
                    "comments": [],
                    "expires_at": expires_at,
                    "created_at": now,
                    "updated_at": now,
                    "created_by": user_id,
                    "updated_by": user_id,
                }

                result = await collection.insert_one(reservation_doc)
                reservation_doc["_id"] = str(result.inserted_id)
                reservation_doc["region_id"] = str(reservation_doc["region_id"])

                # Update quota counter
                await self.update_quota_counter(user_id, "host", 1)

            # Log audit trail
            await self._log_audit_event(
                user_id=user_id,
                action_type="reserve",
                resource_type=resource_type,
                resource_id=str(reservation_doc["_id"]),
                cidr=reservation_doc.get("cidr"),
                ip_address=reservation_doc.get("ip_address"),
                snapshot=reservation_doc,
                changes=[],
                reason=reason or "Reservation created",
            )

            # Log success
            duration = time.time() - start_time
            self.db_manager.log_query_success(
                collection_name,
                "reserve_allocation",
                db_start_time,
                1,
                f"Reserved {resource_type} at {x}.{y}" + (f".{z}" if z is not None else ""),
            )

            self.logger.info(
                "Reservation created successfully in %.3fs: %s at %s",
                duration,
                resource_type,
                reservation_doc.get("cidr") or reservation_doc.get("ip_address"),
            )

            return reservation_doc

        except (ValidationError, DuplicateAllocation, CountryNotFound):
            self.db_manager.log_query_error(
                f"ipam_{resource_type}s", "reserve_allocation", db_start_time, e, operation_context
            )
            raise
        except Exception as e:
            self.db_manager.log_query_error(
                f"ipam_{resource_type}s", "reserve_allocation", db_start_time, e, operation_context
            )
            self.logger.error("Failed to reserve allocation: %s", e, exc_info=True)
            raise IPAMError(f"Failed to reserve {resource_type}: {str(e)}")

    @handle_errors(
        operation_name="convert_reservation_to_active",
        timeout=30.0,
        user_friendly_errors=True,
    )
    async def convert_reservation_to_active(
        self,
        user_id: str,
        reservation_id: str,
        resource_type: str,
        new_name: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Convert reservation to active allocation.

        Args:
            user_id: User ID for isolation
            reservation_id: Reservation ID
            resource_type: "region" or "host"
            new_name: New region name or hostname
            metadata: Optional metadata for the active allocation

        Returns:
            Dict containing converted allocation details

        Raises:
            ValidationError: If inputs invalid or reservation not found
        """
        start_time = time.time()
        operation_context = {
            "user_id": user_id,
            "reservation_id": reservation_id,
            "resource_type": resource_type,
            "new_name": new_name,
            "operation": "convert_reservation_to_active",
        }
        db_start_time = self.db_manager.log_query_start(
            f"ipam_{resource_type}s", "convert_reservation_to_active", operation_context
        )

        try:
            # Validate inputs
            if resource_type not in ["region", "host"]:
                raise ValidationError(
                    f"Invalid resource type (must be 'region' or 'host')",
                    field="resource_type",
                    value=resource_type,
                )

            if not new_name or len(new_name.strip()) == 0:
                raise ValidationError(
                    f"New {resource_type} name is required", field="new_name", value=new_name
                )

            # Get reservation with ownership validation
            collection_name = f"ipam_{resource_type}s"
            collection = self.db_manager.get_collection(collection_name)
            reservation = await collection.find_one({
                "_id": ObjectId(reservation_id),
                "user_id": user_id,
                "status": "Reserved"
            })

            if not reservation:
                raise ValidationError(
                    f"Reservation not found or not in Reserved status",
                    field="reservation_id",
                    value=reservation_id,
                )

            # Build update document
            metadata = metadata or {}
            update_doc = {
                "status": "Active",
                "updated_at": datetime.now(timezone.utc),
                "updated_by": user_id,
            }

            if resource_type == "region":
                update_doc["region_name"] = new_name
                if "description" in metadata:
                    update_doc["description"] = metadata["description"]
                if "tags" in metadata:
                    update_doc["tags"] = metadata["tags"]

            elif resource_type == "host":
                update_doc["hostname"] = new_name
                if "device_type" in metadata:
                    update_doc["device_type"] = metadata["device_type"]
                if "os_type" in metadata:
                    update_doc["os_type"] = metadata["os_type"]
                if "application" in metadata:
                    update_doc["application"] = metadata["application"]
                if "purpose" in metadata:
                    update_doc["purpose"] = metadata["purpose"]
                if "tags" in metadata:
                    update_doc["tags"] = metadata["tags"]
                if "notes" in metadata:
                    update_doc["notes"] = metadata["notes"]

            # Remove reservation-specific fields
            update_doc["tags"] = update_doc.get("tags", {})
            if "reservation" in update_doc["tags"]:
                del update_doc["tags"]["reservation"]

            # Perform update
            result = await collection.update_one(
                {"_id": ObjectId(reservation_id), "user_id": user_id},
                {"$set": update_doc, "$unset": {"expires_at": ""}}
            )

            if result.modified_count == 0:
                raise IPAMError("Failed to convert reservation (no documents modified)")

            # Log audit trail
            await self._log_audit_event(
                user_id=user_id,
                action_type="convert_reservation",
                resource_type=resource_type,
                resource_id=reservation_id,
                cidr=reservation.get("cidr"),
                ip_address=reservation.get("ip_address"),
                snapshot=reservation,
                changes=[{"field": "status", "old_value": "Reserved", "new_value": "Active"}],
                reason="Reservation converted to active allocation",
            )

            # Get updated allocation
            updated = await collection.find_one({"_id": ObjectId(reservation_id)})
            updated["_id"] = str(updated["_id"])
            if "region_id" in updated:
                updated["region_id"] = str(updated["region_id"])

            # Log success
            duration = time.time() - start_time
            self.db_manager.log_query_success(
                collection_name,
                "convert_reservation_to_active",
                db_start_time,
                1,
                f"Converted reservation {reservation_id} to active",
            )

            self.logger.info(
                "Reservation conversion completed successfully in %.3fs: %s",
                duration,
                reservation_id,
            )

            return updated

        except (ValidationError,):
            self.db_manager.log_query_error(
                f"ipam_{resource_type}s", "convert_reservation_to_active", db_start_time, e, operation_context
            )
            raise
        except Exception as e:
            self.db_manager.log_query_error(
                f"ipam_{resource_type}s", "convert_reservation_to_active", db_start_time, e, operation_context
            )
            self.logger.error("Failed to convert reservation: %s", e, exc_info=True)
            raise IPAMError(f"Failed to convert reservation: {str(e)}")

    @handle_errors(
        operation_name="add_comment",
        timeout=30.0,
        user_friendly_errors=True,
    )
    async def add_comment(
        self,
        user_id: str,
        resource_type: str,
        resource_id: str,
        comment_text: str,
    ) -> Dict[str, Any]:
        """
        Add comment to region or host.

        Args:
            user_id: User ID for isolation
            resource_type: "region" or "host"
            resource_id: Resource ID
            comment_text: Comment text (max 2000 characters)

        Returns:
            Dict containing updated resource with comments

        Raises:
            ValidationError: If inputs invalid
            IPAMError: If resource does not exist or not owned by user
        """
        start_time = time.time()
        operation_context = {
            "user_id": user_id,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "comment_length": len(comment_text) if comment_text else 0,
            "operation": "add_comment",
        }
        db_start_time = self.db_manager.log_query_start(
            f"ipam_{resource_type}s", "add_comment", operation_context
        )

        try:
            # Validate inputs
            if resource_type not in ["region", "host"]:
                raise ValidationError(
                    f"Invalid resource type (must be 'region' or 'host')",
                    field="resource_type",
                    value=resource_type,
                )

            if not comment_text or len(comment_text.strip()) == 0:
                raise ValidationError("Comment text cannot be empty", field="comment_text", value=comment_text)

            if len(comment_text) > 2000:
                raise ValidationError(
                    "Comment text too long (max 2000 characters)",
                    field="comment_text",
                    value=len(comment_text),
                )

            # Get resource with ownership validation
            collection_name = f"ipam_{resource_type}s"
            collection = self.db_manager.get_collection(collection_name)
            resource = await collection.find_one({"_id": ObjectId(resource_id), "user_id": user_id})

            if not resource:
                raise IPAMError(f"{resource_type.capitalize()} not found or not accessible: {resource_id}")

            # Create comment entry
            now = datetime.now(timezone.utc)
            comment_entry = {
                "text": comment_text.strip(),
                "author_id": user_id,
                "timestamp": now,
            }

            # Add comment to array (prepend for most recent first)
            result = await collection.update_one(
                {"_id": ObjectId(resource_id), "user_id": user_id},
                {
                    "$push": {"comments": {"$each": [comment_entry], "$position": 0}},
                    "$set": {"updated_at": now, "updated_by": user_id},
                }
            )

            if result.modified_count == 0:
                raise IPAMError("Failed to add comment (no documents modified)")

            # Get updated resource
            updated_resource = await collection.find_one({"_id": ObjectId(resource_id)})
            updated_resource["_id"] = str(updated_resource["_id"])
            if "region_id" in updated_resource:
                updated_resource["region_id"] = str(updated_resource["region_id"])

            # Log success
            duration = time.time() - start_time
            self.db_manager.log_query_success(
                collection_name,
                "add_comment",
                db_start_time,
                1,
                f"Added comment to {resource_type} {resource_id}",
            )

            self.logger.info(
                "Comment added successfully in %.3fs to %s %s",
                duration,
                resource_type,
                resource_id,
            )

            return updated_resource

        except (ValidationError,):
            self.db_manager.log_query_error(
                f"ipam_{resource_type}s", "add_comment", db_start_time, e, operation_context
            )
            raise
        except Exception as e:
            self.db_manager.log_query_error(
                f"ipam_{resource_type}s", "add_comment", db_start_time, e, operation_context
            )
            self.logger.error("Failed to add comment: %s", e, exc_info=True)
            raise IPAMError(f"Failed to add comment: {str(e)}")

    # ==================== Statistics and Utilization Methods ====================

    async def calculate_country_utilization(self, user_id: str, country: str) -> Dict[str, Any]:
        """
        Calculate country utilization statistics with Redis caching (5min TTL).

        Args:
            user_id: User ID for isolation
            country: Country name

        Returns:
            Dict containing utilization statistics with breakdown by X value

        Raises:
            CountryNotFound: If country does not exist in mapping
        """
        cache_key = f"ipam:country_util:{user_id}:{country}"

        # Try cache first
        try:
            cached = await self.redis_manager.get(cache_key)
            if cached:
                self.logger.debug("Country utilization cache hit for user %s, country %s", user_id, country)
                return cached
        except Exception as e:
            self.logger.warning("Redis cache read failed for country utilization: %s", e)

        start_time = self.db_manager.log_query_start(
            "ipam_regions", "calculate_country_utilization", {"user_id": user_id, "country": country}
        )

        try:
            # Get country mapping
            mapping = await self.get_country_mapping(country)
            x_start = mapping["x_start"]
            x_end = mapping["x_end"]
            x_range_size = x_end - x_start + 1

            # Calculate total capacity: (X range size) × 256 regions per X value
            total_capacity = x_range_size * 256

            # Count allocated regions within user's namespace
            collection = self.db_manager.get_tenant_collection("ipam_regions")
            allocated_count = await collection.count_documents({"user_id": user_id, "country": country})

            # Compute utilization percentage
            utilization_percent = (allocated_count / total_capacity * 100) if total_capacity > 0 else 0

            # Get breakdown by X value within range
            x_breakdown = []
            for x_octet in range(x_start, x_end + 1):
                x_allocated = await collection.count_documents(
                    {"user_id": user_id, "country": country, "x_octet": x_octet}
                )
                x_utilization = (x_allocated / 256 * 100) if 256 > 0 else 0

                x_breakdown.append({
                    "x_octet": x_octet,
                    "allocated": x_allocated,
                    "capacity": 256,
                    "available": 256 - x_allocated,
                    "utilization_percent": round(x_utilization, 2),
                })

            # Build result
            result = {
                "country": country,
                "continent": mapping["continent"],
                "x_range": {"start": x_start, "end": x_end, "size": x_range_size},
                "total_capacity": total_capacity,
                "allocated": allocated_count,
                "available": total_capacity - allocated_count,
                "utilization_percent": round(utilization_percent, 2),
                "x_breakdown": x_breakdown,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            # Cache the result with 5min TTL
            try:
                await self.redis_manager.set_with_expiry(cache_key, result, 300)  # 5 minutes
            except Exception as e:
                self.logger.warning("Redis cache write failed for country utilization: %s", e)

            self.db_manager.log_query_success(
                "ipam_regions",
                "calculate_country_utilization",
                start_time,
                allocated_count,
                f"Calculated utilization for {country}: {utilization_percent:.2f}%",
            )

            self.logger.info(
                "Country utilization calculated for user %s, country %s: %.2f%% (%d/%d)",
                user_id,
                country,
                utilization_percent,
                allocated_count,
                total_capacity,
            )

            return result

        except CountryNotFound:
            self.db_manager.log_query_error(
                "ipam_regions",
                "calculate_country_utilization",
                start_time,
                e,
                {"user_id": user_id, "country": country},
            )
            raise
        except Exception as e:
            self.db_manager.log_query_error(
                "ipam_regions",
                "calculate_country_utilization",
                start_time,
                e,
                {"user_id": user_id, "country": country},
            )
            self.logger.error("Failed to calculate country utilization: %s", e, exc_info=True)
            raise IPAMError(f"Failed to calculate country utilization: {str(e)}")

    async def calculate_region_utilization(self, user_id: str, region_id: str) -> Dict[str, Any]:
        """
        Calculate region utilization statistics with Redis caching.

        Args:
            user_id: User ID for isolation
            region_id: Region ID

        Returns:
            Dict containing region utilization statistics

        Raises:
            RegionNotFound: If region does not exist or not owned by user
        """
        cache_key = f"ipam:region_util:{user_id}:{region_id}"

        # Try cache first
        try:
            cached = await self.redis_manager.get(cache_key)
            if cached:
                self.logger.debug("Region utilization cache hit for user %s, region %s", user_id, region_id)
                return cached
        except Exception as e:
            self.logger.warning("Redis cache read failed for region utilization: %s", e)

        start_time = self.db_manager.log_query_start(
            "ipam_hosts", "calculate_region_utilization", {"user_id": user_id, "region_id": region_id}
        )

        try:
            # Get and validate region
            regions_collection = self.db_manager.get_tenant_collection("ipam_regions")
            region = await regions_collection.find_one({"_id": ObjectId(region_id), "user_id": user_id})

            if not region:
                raise RegionNotFound(f"Region not found or not accessible: {region_id}", region_id=region_id)

            # Count allocated hosts (max 254 usable per region)
            hosts_collection = self.db_manager.get_tenant_collection("ipam_hosts")
            allocated_count = await hosts_collection.count_documents(
                {"user_id": user_id, "region_id": ObjectId(region_id)}
            )

            # Compute utilization percentage
            max_hosts = 254  # Z octets 1-254
            utilization_percent = (allocated_count / max_hosts * 100) if max_hosts > 0 else 0

            # Build result
            result = {
                "region_id": region_id,
                "region_name": region["region_name"],
                "country": region["country"],
                "continent": region["continent"],
                "cidr": region["cidr"],
                "x_octet": region["x_octet"],
                "y_octet": region["y_octet"],
                "max_hosts": max_hosts,
                "allocated": allocated_count,
                "available": max_hosts - allocated_count,
                "utilization_percent": round(utilization_percent, 2),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            # Cache the result with 5min TTL
            try:
                await self.redis_manager.set_with_expiry(cache_key, result, 300)  # 5 minutes
            except Exception as e:
                self.logger.warning("Redis cache write failed for region utilization: %s", e)

            self.db_manager.log_query_success(
                "ipam_hosts",
                "calculate_region_utilization",
                start_time,
                allocated_count,
                f"Calculated utilization for region {region_id}: {utilization_percent:.2f}%",
            )

            self.logger.info(
                "Region utilization calculated for user %s, region %s: %.2f%% (%d/%d)",
                user_id,
                region_id,
                utilization_percent,
                allocated_count,
                max_hosts,
            )

            return result

        except RegionNotFound:
            self.db_manager.log_query_error(
                "ipam_hosts",
                "calculate_region_utilization",
                start_time,
                e,
                {"user_id": user_id, "region_id": region_id},
            )
            raise
        except Exception as e:
            self.db_manager.log_query_error(
                "ipam_hosts",
                "calculate_region_utilization",
                start_time,
                e,
                {"user_id": user_id, "region_id": region_id},
            )
            self.logger.error("Failed to calculate region utilization: %s", e, exc_info=True)
            raise IPAMError(f"Failed to calculate region utilization: {str(e)}")

    async def get_continent_statistics(self, user_id: str, continent: str) -> Dict[str, Any]:
        """
        Get aggregated statistics for a continent.

        Args:
            user_id: User ID for isolation
            continent: Continent name

        Returns:
            Dict containing continent-level statistics with country breakdown
        """
        start_time = self.db_manager.log_query_start(
            "ipam_regions", "get_continent_statistics", {"user_id": user_id, "continent": continent}
        )

        try:
            # Get all countries in continent
            countries = await self.get_all_countries(continent=continent)

            if not countries:
                raise ValidationError(f"No countries found for continent: {continent}", field="continent", value=continent)

            # Calculate statistics for each country
            country_stats = []
            total_capacity = 0
            total_allocated = 0

            for country_mapping in countries:
                country_name = country_mapping["country"]

                # Get country utilization
                try:
                    util = await self.calculate_country_utilization(user_id, country_name)
                    country_stats.append({
                        "country": country_name,
                        "total_capacity": util["total_capacity"],
                        "allocated": util["allocated"],
                        "available": util["available"],
                        "utilization_percent": util["utilization_percent"],
                    })
                    total_capacity += util["total_capacity"]
                    total_allocated += util["allocated"]
                except Exception as e:
                    self.logger.warning("Failed to get utilization for country %s: %s", country_name, e)

            # Calculate continent-level utilization
            continent_utilization = (total_allocated / total_capacity * 100) if total_capacity > 0 else 0

            # Build result
            result = {
                "continent": continent,
                "total_capacity": total_capacity,
                "allocated": total_allocated,
                "available": total_capacity - total_allocated,
                "utilization_percent": round(continent_utilization, 2),
                "country_count": len(countries),
                "country_breakdown": country_stats,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            self.db_manager.log_query_success(
                "ipam_regions",
                "get_continent_statistics",
                start_time,
                len(country_stats),
                f"Calculated statistics for continent {continent}",
            )

            self.logger.info(
                "Continent statistics calculated for user %s, continent %s: %.2f%% (%d/%d)",
                user_id,
                continent,
                continent_utilization,
                total_allocated,
                total_capacity,
            )

            return result

        except ValidationError:
            self.db_manager.log_query_error(
                "ipam_regions", "get_continent_statistics", start_time, e, {"user_id": user_id, "continent": continent}
            )
            raise
        except Exception as e:
            self.db_manager.log_query_error(
                "ipam_regions", "get_continent_statistics", start_time, e, {"user_id": user_id, "continent": continent}
            )
            self.logger.error("Failed to get continent statistics: %s", e, exc_info=True)
            raise IPAMError(f"Failed to get continent statistics: {str(e)}")

    async def get_top_utilized_resources(self, user_id: str, limit: int = 10) -> Dict[str, Any]:
        """
        Get top utilized regions and countries.

        Args:
            user_id: User ID for isolation
            limit: Maximum number of results to return (default: 10)

        Returns:
            Dict containing top utilized regions and countries
        """
        start_time = self.db_manager.log_query_start(
            "ipam_regions", "get_top_utilized_resources", {"user_id": user_id, "limit": limit}
        )

        try:
            # Get all user's regions
            regions_collection = self.db_manager.get_tenant_collection("ipam_regions")
            cursor = regions_collection.find({"user_id": user_id})
            regions = await cursor.to_list(length=None)

            # Calculate utilization for each region
            region_utilizations = []
            for region in regions:
                region_id = str(region["_id"])
                try:
                    util = await self.calculate_region_utilization(user_id, region_id)
                    region_utilizations.append({
                        "region_id": region_id,
                        "region_name": region["region_name"],
                        "country": region["country"],
                        "cidr": region["cidr"],
                        "allocated": util["allocated"],
                        "capacity": util["max_hosts"],
                        "utilization_percent": util["utilization_percent"],
                    })
                except Exception as e:
                    self.logger.warning("Failed to calculate utilization for region %s: %s", region_id, e)

            # Sort by utilization percentage (descending) and take top N
            top_regions = sorted(region_utilizations, key=lambda x: x["utilization_percent"], reverse=True)[:limit]

            # Get unique countries from user's regions
            countries = set(region["country"] for region in regions)

            # Calculate utilization for each country
            country_utilizations = []
            for country in countries:
                try:
                    util = await self.calculate_country_utilization(user_id, country)
                    country_utilizations.append({
                        "country": country,
                        "continent": util["continent"],
                        "allocated": util["allocated"],
                        "capacity": util["total_capacity"],
                        "utilization_percent": util["utilization_percent"],
                    })
                except Exception as e:
                    self.logger.warning("Failed to calculate utilization for country %s: %s", country, e)

            # Sort by utilization percentage (descending) and take top N
            top_countries = sorted(country_utilizations, key=lambda x: x["utilization_percent"], reverse=True)[:limit]

            # Build result
            result = {
                "top_regions": top_regions,
                "top_countries": top_countries,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            self.db_manager.log_query_success(
                "ipam_regions",
                "get_top_utilized_resources",
                start_time,
                len(top_regions) + len(top_countries),
                f"Found top {limit} utilized resources",
            )

            self.logger.info(
                "Top utilized resources calculated for user %s: %d regions, %d countries",
                user_id,
                len(top_regions),
                len(top_countries),
            )

            return result

        except Exception as e:
            self.db_manager.log_query_error(
                "ipam_regions", "get_top_utilized_resources", start_time, e, {"user_id": user_id, "limit": limit}
            )
            self.logger.error("Failed to get top utilized resources: %s", e, exc_info=True)
            raise IPAMError(f"Failed to get top utilized resources: {str(e)}")

    async def get_allocation_velocity(self, user_id: str, time_range: str = "week") -> Dict[str, Any]:
        """
        Calculate allocation velocity (allocations per time period).

        Args:
            user_id: User ID for isolation
            time_range: Time range for calculation ("day", "week", "month")

        Returns:
            Dict containing allocation velocity metrics
        """
        start_time = self.db_manager.log_query_start(
            "ipam_regions", "get_allocation_velocity", {"user_id": user_id, "time_range": time_range}
        )

        try:
            # Determine time period
            now = datetime.now(timezone.utc)
            if time_range == "day":
                days = 1
                group_format = "%Y-%m-%d %H:00"
                period_label = "hour"
            elif time_range == "week":
                days = 7
                group_format = "%Y-%m-%d"
                period_label = "day"
            elif time_range == "month":
                days = 30
                group_format = "%Y-%m-%d"
                period_label = "day"
            else:
                raise ValidationError(f"Invalid time range: {time_range}", field="time_range", value=time_range)

            # Calculate start date
            from datetime import timedelta
            start_date = now - timedelta(days=days)

            # Query regions created in time range
            regions_collection = self.db_manager.get_tenant_collection("ipam_regions")
            region_cursor = regions_collection.find(
                {"user_id": user_id, "created_at": {"$gte": start_date}}
            ).sort("created_at", 1)
            regions = await region_cursor.to_list(length=None)

            # Query hosts created in time range
            hosts_collection = self.db_manager.get_tenant_collection("ipam_hosts")
            host_cursor = hosts_collection.find(
                {"user_id": user_id, "created_at": {"$gte": start_date}}
            ).sort("created_at", 1)
            hosts = await host_cursor.to_list(length=None)

            # Group by time period
            region_velocity = {}
            for region in regions:
                period_key = region["created_at"].strftime(group_format)
                region_velocity[period_key] = region_velocity.get(period_key, 0) + 1

            host_velocity = {}
            for host in hosts:
                period_key = host["created_at"].strftime(group_format)
                host_velocity[period_key] = host_velocity.get(period_key, 0) + 1

            # Calculate averages
            total_regions = len(regions)
            total_hosts = len(hosts)
            avg_regions_per_period = total_regions / days if days > 0 else 0
            avg_hosts_per_period = total_hosts / days if days > 0 else 0

            # Build result
            result = {
                "time_range": time_range,
                "start_date": start_date.isoformat(),
                "end_date": now.isoformat(),
                "period_label": period_label,
                "total_regions_allocated": total_regions,
                "total_hosts_allocated": total_hosts,
                "avg_regions_per_period": round(avg_regions_per_period, 2),
                "avg_hosts_per_period": round(avg_hosts_per_period, 2),
                "region_velocity": [
                    {"period": k, "count": v} for k, v in sorted(region_velocity.items())
                ],
                "host_velocity": [
                    {"period": k, "count": v} for k, v in sorted(host_velocity.items())
                ],
                "timestamp": now.isoformat(),
            }

            self.db_manager.log_query_success(
                "ipam_regions",
                "get_allocation_velocity",
                start_time,
                total_regions + total_hosts,
                f"Calculated allocation velocity for {time_range}",
            )

            self.logger.info(
                "Allocation velocity calculated for user %s, time_range %s: %.2f regions/period, %.2f hosts/period",
                user_id,
                time_range,
                avg_regions_per_period,
                avg_hosts_per_period,
            )

            return result

        except ValidationError:
            self.db_manager.log_query_error(
                "ipam_regions", "get_allocation_velocity", start_time, e, {"user_id": user_id, "time_range": time_range}
            )
            raise
        except Exception as e:
            self.db_manager.log_query_error(
                "ipam_regions", "get_allocation_velocity", start_time, e, {"user_id": user_id, "time_range": time_range}
            )
            self.logger.error("Failed to get allocation velocity: %s", e, exc_info=True)
            raise IPAMError(f"Failed to get allocation velocity: {str(e)}")

    async def get_next_available_region(self, user_id: str, country: str) -> Optional[Dict[str, Any]]:
        """
        Preview next available region CIDR that would be allocated.

        Args:
            user_id: User ID for isolation
            country: Country name

        Returns:
            Dict with next available CIDR or None if exhausted
        """
        start_time = self.db_manager.log_query_start(
            "ipam_regions", "get_next_available_region", {"user_id": user_id, "country": country}
        )

        try:
            # Try to find next X.Y
            try:
                x_octet, y_octet = await self.find_next_xy(user_id, country)
                cidr = f"10.{x_octet}.{y_octet}.0/24"

                result = {
                    "available": True,
                    "next_cidr": cidr,
                    "x_octet": x_octet,
                    "y_octet": y_octet,
                    "country": country,
                }

                self.db_manager.log_query_success(
                    "ipam_regions",
                    "get_next_available_region",
                    start_time,
                    1,
                    f"Next available: {cidr}",
                )

                self.logger.info("Next available region for user %s in %s: %s", user_id, country, cidr)

                return result

            except CapacityExhausted as e:
                # Capacity exhausted
                result = {
                    "available": False,
                    "message": str(e),
                    "country": country,
                }

                self.db_manager.log_query_success(
                    "ipam_regions",
                    "get_next_available_region",
                    start_time,
                    0,
                    f"No available regions in {country}",
                )

                self.logger.info("No available regions for user %s in %s", user_id, country)

                return result

        except CountryNotFound:
            self.db_manager.log_query_error(
                "ipam_regions", "get_next_available_region", start_time, e, {"user_id": user_id, "country": country}
            )
            raise
        except Exception as e:
            self.db_manager.log_query_error(
                "ipam_regions", "get_next_available_region", start_time, e, {"user_id": user_id, "country": country}
            )
            self.logger.error("Failed to get next available region: %s", e, exc_info=True)
            raise IPAMError(f"Failed to get next available region: {str(e)}")

    async def get_next_available_host(self, user_id: str, region_id: str) -> Optional[Dict[str, Any]]:
        """
        Preview next available host IP that would be allocated.

        Args:
            user_id: User ID for isolation
            region_id: Region ID

        Returns:
            Dict with next available IP or None if exhausted
        """
        start_time = self.db_manager.log_query_start(
            "ipam_hosts", "get_next_available_host", {"user_id": user_id, "region_id": region_id}
        )

        try:
            # Get and validate region
            regions_collection = self.db_manager.get_tenant_collection("ipam_regions")
            region = await regions_collection.find_one({"_id": ObjectId(region_id), "user_id": user_id})

            if not region:
                raise RegionNotFound(f"Region not found or not accessible: {region_id}", region_id=region_id)

            x_octet = region["x_octet"]
            y_octet = region["y_octet"]

            # Try to find next Z
            try:
                z_octet = await self.find_next_z(user_id, region_id)
                ip_address = f"10.{x_octet}.{y_octet}.{z_octet}"

                result = {
                    "available": True,
                    "next_ip": ip_address,
                    "x_octet": x_octet,
                    "y_octet": y_octet,
                    "z_octet": z_octet,
                    "region_id": region_id,
                    "region_name": region["region_name"],
                }

                self.db_manager.log_query_success(
                    "ipam_hosts",
                    "get_next_available_host",
                    start_time,
                    1,
                    f"Next available: {ip_address}",
                )

                self.logger.info("Next available host for user %s in region %s: %s", user_id, region_id, ip_address)

                return result

            except CapacityExhausted as e:
                # Capacity exhausted
                result = {
                    "available": False,
                    "message": str(e),
                    "region_id": region_id,
                    "region_name": region["region_name"],
                }

                self.db_manager.log_query_success(
                    "ipam_hosts",
                    "get_next_available_host",
                    start_time,
                    0,
                    f"No available hosts in region {region_id}",
                )

                self.logger.info("No available hosts for user %s in region %s", user_id, region_id)

                return result

        except RegionNotFound:
            self.db_manager.log_query_error(
                "ipam_hosts", "get_next_available_host", start_time, e, {"user_id": user_id, "region_id": region_id}
            )
            raise
        except Exception as e:
            self.db_manager.log_query_error(
                "ipam_hosts", "get_next_available_host", start_time, e, {"user_id": user_id, "region_id": region_id}
            )
            self.logger.error("Failed to get next available host: %s", e, exc_info=True)
            raise IPAMError(f"Failed to get next available host: {str(e)}")

    # ==================== Audit History Methods ====================

    async def get_audit_history(
        self,
        user_id: str,
        filters: Optional[Dict[str, Any]] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """
        Get audit history with filtering and pagination.

        Supports filtering by:
        - date_from/date_to: Date range filter
        - action_type: Filter by action (create, update, release, retire, etc.)
        - resource_type: Filter by resource type (region, host)
        - ip_address: Filter by IP address or CIDR
        - country: Filter by country name
        - region_name: Filter by region name
        - hostname: Filter by hostname

        Args:
            user_id: User ID to filter audit history
            filters: Optional filters dictionary
            page: Page number (1-indexed)
            page_size: Number of results per page (max 100)

        Returns:
            Dict containing:
                - audit_events: List of audit records with field-level changes
                - pagination: Pagination metadata
                - total_count: Total number of matching records

        Raises:
            IPAMError: If query fails

        Example:
            >>> history = await ipam_manager.get_audit_history(
            ...     user_id="user123",
            ...     filters={
            ...         "date_from": "2025-01-01",
            ...         "date_to": "2025-12-31",
            ...         "action_type": "create",
            ...         "resource_type": "region"
            ...     },
            ...     page=1,
            ...     page_size=50
            ... )
        """
        operation_context = {
            "user_id": user_id,
            "filters": filters,
            "page": page,
            "page_size": page_size,
            "operation": "get_audit_history",
        }
        start_time = self.db_manager.log_query_start("ipam_audit_history", "find", operation_context)

        try:
            filters = filters or {}
            page_size = min(page_size, 100)  # Cap at 100
            skip = (page - 1) * page_size

            # Build query
            query = {"user_id": user_id}

            # Date range filter
            if "date_from" in filters or "date_to" in filters:
                query["timestamp"] = {}
                if "date_from" in filters:
                    date_from = datetime.fromisoformat(filters["date_from"].replace("Z", "+00:00"))
                    query["timestamp"]["$gte"] = date_from
                if "date_to" in filters:
                    date_to = datetime.fromisoformat(filters["date_to"].replace("Z", "+00:00"))
                    query["timestamp"]["$lte"] = date_to

            # Action type filter
            if "action_type" in filters:
                query["action_type"] = filters["action_type"]

            # Resource type filter
            if "resource_type" in filters:
                query["resource_type"] = filters["resource_type"]

            # IP address filter (exact or partial match)
            if "ip_address" in filters:
                ip_filter = filters["ip_address"]
                if "/" in ip_filter:  # CIDR
                    query["cidr"] = {"$regex": f"^{ip_filter.split('/')[0]}"}
                else:
                    query["$or"] = [
                        {"ip_address": {"$regex": ip_filter}},
                        {"cidr": {"$regex": ip_filter}},
                    ]

            # Country filter
            if "country" in filters:
                query["metadata.country"] = filters["country"]

            # Region name filter
            if "region_name" in filters:
                query["metadata.region_name"] = {"$regex": filters["region_name"], "$options": "i"}

            # Hostname filter
            if "hostname" in filters:
                query["metadata.hostname"] = {"$regex": filters["hostname"], "$options": "i"}

            # Get collection
            collection = self.db_manager.get_tenant_collection("ipam_audit_history")

            # Get total count
            total_count = await collection.count_documents(query)

            # Get audit events (sorted by timestamp descending - most recent first)
            cursor = collection.find(query).sort("timestamp", -1).skip(skip).limit(page_size)
            audit_events = await cursor.to_list(length=page_size)

            # Convert ObjectIds to strings
            for event in audit_events:
                event["_id"] = str(event["_id"])
                if "resource_id" in event:
                    event["resource_id"] = str(event["resource_id"])

            self.db_manager.log_query_success(
                "ipam_audit_history",
                "find",
                start_time,
                result_info={"total_count": total_count, "page": page, "returned": len(audit_events)}
            )

            self.logger.info(
                "audit_history_retrieved",
                extra={
                    "user_id": user_id,
                    "total_count": total_count,
                    "page": page,
                    "page_size": page_size,
                    "filters": filters,
                },
            )

            return {
                "audit_events": audit_events,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total_pages": (total_count + page_size - 1) // page_size,
                    "has_next": skip + page_size < total_count,
                    "has_prev": page > 1,
                },
                "total_count": total_count,
            }

        except Exception as e:
            self.db_manager.log_query_error("ipam_audit_history", "find", start_time, e, query=query)
            self.logger.error(
                "get_audit_history_failed",
                extra={"user_id": user_id, "filters": filters, "error": str(e)},
                exc_info=True,
            )
            raise IPAMError(f"Failed to get audit history: {str(e)}")

    async def get_audit_history_for_ip(
        self,
        user_id: str,
        ip_address: str,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """
        Get complete audit history for a specific IP address.

        Returns all historical allocations, updates, and deletions for the given IP,
        showing the complete lifecycle of the address.

        Args:
            user_id: User ID to filter audit history
            ip_address: IP address to query (e.g., "10.5.23.45")
            page: Page number (1-indexed)
            page_size: Number of results per page

        Returns:
            Dict containing:
                - ip_address: The queried IP address
                - audit_events: List of all events for this IP
                - pagination: Pagination metadata
                - total_count: Total number of events

        Raises:
            IPAMError: If query fails

        Example:
            >>> history = await ipam_manager.get_audit_history_for_ip(
            ...     user_id="user123",
            ...     ip_address="10.5.23.45"
            ... )
        """
        operation_context = {
            "user_id": user_id,
            "ip_address": ip_address,
            "page": page,
            "page_size": page_size,
            "operation": "get_audit_history_for_ip",
        }
        start_time = self.db_manager.log_query_start("ipam_audit_history", "find", operation_context)

        try:
            page_size = min(page_size, 100)
            skip = (page - 1) * page_size

            # Build query for specific IP
            query = {"user_id": user_id, "ip_address": ip_address}

            collection = self.db_manager.get_tenant_collection("ipam_audit_history")

            # Get total count
            total_count = await collection.count_documents(query)

            # Get audit events (sorted by timestamp descending)
            cursor = collection.find(query).sort("timestamp", -1).skip(skip).limit(page_size)
            audit_events = await cursor.to_list(length=page_size)

            # Convert ObjectIds to strings
            for event in audit_events:
                event["_id"] = str(event["_id"])
                if "resource_id" in event:
                    event["resource_id"] = str(event["resource_id"])

            self.db_manager.log_query_success(
                "ipam_audit_history",
                "find",
                start_time,
                result_info={"ip_address": ip_address, "total_count": total_count, "returned": len(audit_events)}
            )

            self.logger.info(
                "ip_audit_history_retrieved",
                extra={
                    "user_id": user_id,
                    "ip_address": ip_address,
                    "total_count": total_count,
                },
            )

            return {
                "ip_address": ip_address,
                "audit_events": audit_events,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total_pages": (total_count + page_size - 1) // page_size,
                    "has_next": skip + page_size < total_count,
                    "has_prev": page > 1,
                },
                "total_count": total_count,
            }

        except Exception as e:
            self.db_manager.log_query_error("ipam_audit_history", "find", start_time, e, query=query)
            self.logger.error(
                "get_ip_audit_history_failed",
                extra={"user_id": user_id, "ip_address": ip_address, "error": str(e)},
                exc_info=True,
            )
            raise IPAMError(f"Failed to get audit history for IP: {str(e)}")

    async def export_audit_history(
        self,
        user_id: str,
        filters: Optional[Dict[str, Any]] = None,
        format: str = "json",
    ) -> Dict[str, Any]:
        """
        Export audit history in CSV or JSON format.

        Exports all audit records matching the filters without pagination limits.
        Useful for compliance reporting and regulatory requirements.

        Args:
            user_id: User ID to filter audit history
            filters: Optional filters (same as get_audit_history)
            format: Export format - "json" or "csv"

        Returns:
            Dict containing:
                - format: Export format used
                - data: Exported data (JSON array or CSV string)
                - total_count: Number of records exported
                - exported_at: Export timestamp

        Raises:
            IPAMError: If export fails
            ValidationError: If format is invalid

        Example:
            >>> export = await ipam_manager.export_audit_history(
            ...     user_id="user123",
            ...     filters={"date_from": "2025-01-01"},
            ...     format="csv"
            ... )
        """
        operation_context = {
            "user_id": user_id,
            "filters": filters,
            "format": format,
            "operation": "export_audit_history",
        }
        start_time = self.db_manager.log_query_start("ipam_audit_history", "export", operation_context)

        try:
            # Validate format
            if format not in ["json", "csv"]:
                raise ValidationError(
                    "Invalid export format. Must be 'json' or 'csv'",
                    field="format",
                    value=format,
                )

            filters = filters or {}

            # Build query (same as get_audit_history)
            query = {"user_id": user_id}

            # Date range filter
            if "date_from" in filters or "date_to" in filters:
                query["timestamp"] = {}
                if "date_from" in filters:
                    date_from = datetime.fromisoformat(filters["date_from"].replace("Z", "+00:00"))
                    query["timestamp"]["$gte"] = date_from
                if "date_to" in filters:
                    date_to = datetime.fromisoformat(filters["date_to"].replace("Z", "+00:00"))
                    query["timestamp"]["$lte"] = date_to

            # Action type filter
            if "action_type" in filters:
                query["action_type"] = filters["action_type"]

            # Resource type filter
            if "resource_type" in filters:
                query["resource_type"] = filters["resource_type"]

            # IP address filter
            if "ip_address" in filters:
                ip_filter = filters["ip_address"]
                if "/" in ip_filter:
                    query["cidr"] = {"$regex": f"^{ip_filter.split('/')[0]}"}
                else:
                    query["$or"] = [
                        {"ip_address": {"$regex": ip_filter}},
                        {"cidr": {"$regex": ip_filter}},
                    ]

            # Country filter
            if "country" in filters:
                query["metadata.country"] = filters["country"]

            # Get collection
            collection = self.db_manager.get_tenant_collection("ipam_audit_history")

            # Get all matching records (sorted by timestamp)
            cursor = collection.find(query).sort("timestamp", -1)
            audit_events = await cursor.to_list(length=None)

            # Convert ObjectIds to strings for JSON serialization
            for event in audit_events:
                event["_id"] = str(event["_id"])
                if "resource_id" in event:
                    event["resource_id"] = str(event["resource_id"])
                # Convert datetime to ISO string
                if "timestamp" in event:
                    event["timestamp"] = event["timestamp"].isoformat()

            total_count = len(audit_events)

            # Format data based on requested format
            if format == "json":
                data = audit_events
            else:  # csv
                data = self._format_audit_history_as_csv(audit_events)

            self.db_manager.log_query_success(
                "ipam_audit_history",
                "export",
                start_time,
                result_info={"format": format, "total_count": total_count}
            )

            self.logger.info(
                "audit_history_exported",
                extra={
                    "user_id": user_id,
                    "format": format,
                    "total_count": total_count,
                    "filters": filters,
                },
            )

            return {
                "format": format,
                "data": data,
                "total_count": total_count,
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "filters": filters,
            }

        except ValidationError:
            raise
        except Exception as e:
            self.db_manager.log_query_error("ipam_audit_history", "export", start_time, e, query=query)
            self.logger.error(
                "export_audit_history_failed",
                extra={"user_id": user_id, "format": format, "filters": filters, "error": str(e)},
                exc_info=True,
            )
            raise IPAMError(f"Failed to export audit history: {str(e)}")

    def _format_audit_history_as_csv(self, audit_events: List[Dict[str, Any]]) -> str:
        """
        Format audit events as CSV string.

        Args:
            audit_events: List of audit event documents

        Returns:
            CSV formatted string with headers and data rows
        """
        import csv
        import io

        output = io.StringIO()
        
        if not audit_events:
            return ""

        # Define CSV headers
        headers = [
            "timestamp",
            "action_type",
            "resource_type",
            "resource_id",
            "ip_address",
            "cidr",
            "country",
            "region_name",
            "hostname",
            "x_octet",
            "y_octet",
            "z_octet",
            "status",
            "owner",
            "reason",
            "changes",
        ]

        writer = csv.DictWriter(output, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()

        # Write data rows
        for event in audit_events:
            row = {
                "timestamp": event.get("timestamp", ""),
                "action_type": event.get("action_type", ""),
                "resource_type": event.get("resource_type", ""),
                "resource_id": event.get("resource_id", ""),
                "ip_address": event.get("ip_address", ""),
                "cidr": event.get("cidr", ""),
                "country": event.get("metadata", {}).get("country", ""),
                "region_name": event.get("metadata", {}).get("region_name", ""),
                "hostname": event.get("metadata", {}).get("hostname", ""),
                "x_octet": event.get("metadata", {}).get("x_octet", ""),
                "y_octet": event.get("metadata", {}).get("y_octet", ""),
                "z_octet": event.get("metadata", {}).get("z_octet", ""),
                "status": event.get("metadata", {}).get("status", ""),
                "owner": event.get("metadata", {}).get("owner", ""),
                "reason": event.get("reason", ""),
                "changes": str(event.get("changes", [])) if event.get("changes") else "",
            }
            writer.writerow(row)

        return output.getvalue()

    # ==================== Helper Methods ====================

    async def _log_audit_event(
        self,
        user_id: str,
        action_type: str,
        resource_type: str,
        resource_id: str,
        snapshot: Dict[str, Any],
        changes: List[Dict[str, Any]],
        reason: str,
        cidr: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        """
        Log audit event to ipam_audit_history collection.

        Args:
            user_id: User ID who performed action
            action_type: "create", "update", "release", "retire", "reserve", "convert_reservation"
            resource_type: "region" or "host"
            resource_id: Resource ID
            snapshot: Complete resource state
            changes: List of field-level changes
            reason: Reason for action
            cidr: CIDR for regions
            ip_address: IP address for hosts
        """
        try:
            collection = self.db_manager.get_tenant_collection("ipam_audit_history")

            # Prepare snapshot (remove _id for storage)
            snapshot_copy = dict(snapshot)
            if "_id" in snapshot_copy:
                snapshot_copy["_id"] = str(snapshot_copy["_id"])
            if "region_id" in snapshot_copy:
                snapshot_copy["region_id"] = str(snapshot_copy["region_id"])

            audit_doc = {
                "user_id": user_id,
                "action_type": action_type,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "ip_address": ip_address,
                "cidr": cidr,
                "snapshot": snapshot_copy,
                "changes": changes,
                "reason": reason,
                "timestamp": datetime.now(timezone.utc),
                "metadata": {
                    "user_agent": None,  # Can be populated from request context
                    "ip_source": None,   # Can be populated from request context
                },
            }

            await collection.insert_one(audit_doc)
            self.logger.debug("Audit event logged: %s %s for %s", action_type, resource_type, resource_id)

        except Exception as e:
            # Don't fail the main operation if audit logging fails
            self.logger.error("Failed to log audit event: %s", e, exc_info=True)

    async def _invalidate_region_caches(self, user_id: str, x_octet: int, region_id: str) -> None:
        """
        Invalidate Redis caches for region-related data.

        Args:
            user_id: User ID
            x_octet: X octet value
            region_id: Region ID
        """
        try:
            # Invalidate allocated Y cache
            cache_key = f"ipam:allocated_y:{user_id}:{x_octet}"
            await self.redis_manager.delete(cache_key)

            # Invalidate user quota cache
            quota_cache_key = f"ipam:user_quota:{user_id}"
            await self.redis_manager.delete(quota_cache_key)

            self.logger.debug("Invalidated caches for user %s, X=%d", user_id, x_octet)

        except Exception as e:
            # Don't fail the main operation if cache invalidation fails
            self.logger.warning("Failed to invalidate caches: %s", e)

    # ==================== Import/Export Methods ====================

    async def export_allocations(
        self,
        user_id: str,
        format: str,
        filters: Optional[Dict[str, Any]] = None,
        include_hierarchy: bool = False,
    ) -> str:
        """
        Create export job for allocations (async processing).

        Args:
            user_id: User ID for isolation
            format: Export format ("csv" or "json")
            filters: Optional filters to apply
            include_hierarchy: Include hierarchical structure (country → regions → hosts)

        Returns:
            Job ID for status tracking

        Raises:
            ValidationError: If format is invalid
        """
        start_time = time.time()
        operation_context = {
            "user_id": user_id,
            "format": format,
            "include_hierarchy": include_hierarchy,
            "operation": "export_allocations",
        }
        db_start_time = self.db_manager.log_query_start("ipam_export_jobs", "export_allocations", operation_context)

        try:
            # Validate format
            if format not in ["csv", "json"]:
                raise ValidationError(f"Invalid export format: {format}", field="format", value=format)

            # Create export job record
            job_id = str(ObjectId())
            collection = self.db_manager.get_tenant_collection("ipam_export_jobs")

            job_doc = {
                "_id": ObjectId(job_id),
                "user_id": user_id,
                "format": format,
                "filters": filters or {},
                "include_hierarchy": include_hierarchy,
                "status": "pending",
                "created_at": datetime.now(timezone.utc),
                "completed_at": None,
                "download_url": None,
                "expires_at": None,
                "error": None,
            }

            await collection.insert_one(job_doc)

            # Start async export processing
            asyncio.create_task(self._process_export_job(job_id, user_id, format, filters, include_hierarchy))

            duration = time.time() - start_time
            self.db_manager.log_query_success(
                "ipam_export_jobs",
                "export_allocations",
                db_start_time,
                1,
                f"Created export job {job_id}",
            )
            self.logger.info(
                "Created export job %s for user %s (format=%s, %.3fs)",
                job_id,
                user_id,
                format,
                duration,
            )

            return job_id

        except ValidationError:
            raise
        except Exception as e:
            self.db_manager.log_query_error(
                "ipam_export_jobs",
                "export_allocations",
                db_start_time,
                e,
                operation_context,
            )
            self.logger.error("Failed to create export job: %s", e, exc_info=True)
            raise IPAMError(f"Failed to create export job: {str(e)}")

    async def _process_export_job(
        self,
        job_id: str,
        user_id: str,
        format: str,
        filters: Optional[Dict[str, Any]],
        include_hierarchy: bool,
    ) -> None:
        """
        Process export job asynchronously.

        Args:
            job_id: Export job ID
            user_id: User ID
            format: Export format
            filters: Optional filters
            include_hierarchy: Include hierarchical structure
        """
        import csv
        import io
        import json

        try:
            self.logger.info("Processing export job %s for user %s", job_id, user_id)

            # Query allocations based on filters
            regions_data = []
            hosts_data = []

            # Build query from filters
            query = {"user_id": user_id}
            if filters:
                if "country" in filters:
                    query["country"] = filters["country"]
                if "status" in filters:
                    query["status"] = filters["status"]
                if "continent" in filters:
                    query["continent"] = filters["continent"]

            # Fetch regions
            regions_collection = self.db_manager.get_tenant_collection("ipam_regions")
            regions_cursor = regions_collection.find(query)
            regions = await regions_cursor.to_list(length=None)

            # Fetch hosts for each region
            hosts_collection = self.db_manager.get_tenant_collection("ipam_hosts")
            for region in regions:
                region_dict = {
                    "region_id": str(region["_id"]),
                    "country": region["country"],
                    "continent": region["continent"],
                    "x_octet": region["x_octet"],
                    "y_octet": region["y_octet"],
                    "cidr": region["cidr"],
                    "region_name": region["region_name"],
                    "description": region.get("description", ""),
                    # legacy field kept for backward compatibility
                    "owner": region.get("owner", ""),
                    # explicit fields introduced to disambiguate owner values
                    "owner_name": region.get("owner", ""),
                    "owner_id": region.get("owner_id", ""),
                    "status": region["status"],
                    "tags": json.dumps(region.get("tags", {})),
                    "created_at": region["created_at"].isoformat(),
                }
                regions_data.append(region_dict)

                # Fetch hosts for this region
                hosts_cursor = hosts_collection.find({"user_id": user_id, "region_id": region["_id"]})
                hosts = await hosts_cursor.to_list(length=None)

                for host in hosts:
                    host_dict = {
                        "host_id": str(host["_id"]),
                        "region_id": str(host["region_id"]),
                        "region_name": region["region_name"],
                        "x_octet": host["x_octet"],
                        "y_octet": host["y_octet"],
                        "z_octet": host["z_octet"],
                        "ip_address": host["ip_address"],
                        "hostname": host["hostname"],
                        "device_type": host.get("device_type", ""),
                        "os_type": host.get("os_type", ""),
                        "application": host.get("application", ""),
                        # legacy field kept for backward compatibility
                        "owner": host.get("owner", ""),
                        # explicit fields introduced to disambiguate owner values
                        "owner_name": host.get("owner", ""),
                        "owner_id": host.get("owner_id", ""),
                        "purpose": host.get("purpose", ""),
                        "status": host["status"],
                        "tags": json.dumps(host.get("tags", {})),
                        "created_at": host["created_at"].isoformat(),
                    }
                    hosts_data.append(host_dict)

            # Generate export file
            export_content = None
            if format == "csv":
                export_content = self._generate_csv_export(regions_data, hosts_data, include_hierarchy)
            elif format == "json":
                export_content = self._generate_json_export(regions_data, hosts_data, include_hierarchy)

            # Store export content (in production, upload to S3 or similar)
            # For now, store in database
            jobs_collection = self.db_manager.get_tenant_collection("ipam_export_jobs")
            download_url = f"/api/v1/ipam/export/{job_id}/download"
            expires_at = datetime.now(timezone.utc).replace(hour=23, minute=59, second=59)  # End of day

            await jobs_collection.update_one(
                {"_id": ObjectId(job_id)},
                {
                    "$set": {
                        "status": "completed",
                        "completed_at": datetime.now(timezone.utc),
                        "download_url": download_url,
                        "expires_at": expires_at,
                        "export_content": export_content,
                        "regions_count": len(regions_data),
                        "hosts_count": len(hosts_data),
                    }
                },
            )

            self.logger.info(
                "Export job %s completed: %d regions, %d hosts",
                job_id,
                len(regions_data),
                len(hosts_data),
            )

        except Exception as e:
            self.logger.error("Export job %s failed: %s", job_id, e, exc_info=True)

            # Update job status to failed
            try:
                jobs_collection = self.db_manager.get_tenant_collection("ipam_export_jobs")
                await jobs_collection.update_one(
                    {"_id": ObjectId(job_id)},
                    {
                        "$set": {
                            "status": "failed",
                            "completed_at": datetime.now(timezone.utc),
                            "error": str(e),
                        }
                    },
                )
            except Exception as update_error:
                self.logger.error("Failed to update job status: %s", update_error)

    def _generate_csv_export(
        self,
        regions_data: List[Dict[str, Any]],
        hosts_data: List[Dict[str, Any]],
        include_hierarchy: bool,
    ) -> str:
        """
        Generate CSV export content.

        Args:
            regions_data: List of region dictionaries
            hosts_data: List of host dictionaries
            include_hierarchy: Include hierarchical structure

        Returns:
            CSV content as string
        """
        import csv
        import io

        output = io.StringIO()

        if include_hierarchy:
            # Combined export with hierarchy
            writer = csv.writer(output)
            writer.writerow([
                "Type",
                "Country",
                "Continent",
                "Region Name",
                "CIDR",
                "IP Address",
                "Hostname",
                "Device Type",
                "Owner",
                "Status",
                "Tags",
                "Created At",
            ])

            for region in regions_data:
                writer.writerow([
                    "Region",
                    region["country"],
                    region["continent"],
                    region["region_name"],
                    region["cidr"],
                    "",
                    "",
                    "",
                    region["owner"],
                    region["status"],
                    region["tags"],
                    region["created_at"],
                ])

                # Add hosts under this region
                region_hosts = [h for h in hosts_data if h["region_id"] == region["region_id"]]
                for host in region_hosts:
                    writer.writerow([
                        "Host",
                        "",
                        "",
                        region["region_name"],
                        "",
                        host["ip_address"],
                        host["hostname"],
                        host["device_type"],
                        host["owner"],
                        host["status"],
                        host["tags"],
                        host["created_at"],
                    ])
        else:
            # Separate regions and hosts
            # Regions CSV
            if regions_data:
                writer = csv.DictWriter(output, fieldnames=regions_data[0].keys())
                writer.writeheader()
                writer.writerows(regions_data)

            output.write("\n\n# Hosts\n")

            # Hosts CSV
            if hosts_data:
                writer = csv.DictWriter(output, fieldnames=hosts_data[0].keys())
                writer.writeheader()
                writer.writerows(hosts_data)

        return output.getvalue()

    def _generate_json_export(
        self,
        regions_data: List[Dict[str, Any]],
        hosts_data: List[Dict[str, Any]],
        include_hierarchy: bool,
    ) -> str:
        """
        Generate JSON export content.

        Args:
            regions_data: List of region dictionaries
            hosts_data: List of host dictionaries
            include_hierarchy: Include hierarchical structure

        Returns:
            JSON content as string
        """
        import json

        if include_hierarchy:
            # Build hierarchical structure
            export_data = {
                "export_metadata": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "total_regions": len(regions_data),
                    "total_hosts": len(hosts_data),
                },
                "regions": [],
            }

            for region in regions_data:
                region_hosts = [h for h in hosts_data if h["region_id"] == region["region_id"]]
                region_with_hosts = {
                    **region,
                    "hosts": region_hosts,
                }
                export_data["regions"].append(region_with_hosts)

            return json.dumps(export_data, indent=2)
        else:
            # Flat structure
            export_data = {
                "export_metadata": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "total_regions": len(regions_data),
                    "total_hosts": len(hosts_data),
                },
                "regions": regions_data,
                "hosts": hosts_data,
            }
            return json.dumps(export_data, indent=2)

    async def get_export_job_status(self, user_id: str, job_id: str) -> Dict[str, Any]:
        """
        Get export job status.

        Args:
            user_id: User ID for isolation
            job_id: Export job ID

        Returns:
            Dict containing job status

        Raises:
            IPAMError: If job not found or access denied
        """
        start_time = self.db_manager.log_query_start(
            "ipam_export_jobs",
            "get_export_job_status",
            {"user_id": user_id, "job_id": job_id},
        )

        try:
            collection = self.db_manager.get_tenant_collection("ipam_export_jobs")
            job = await collection.find_one({"_id": ObjectId(job_id), "user_id": user_id})

            if not job:
                raise IPAMError(f"Export job not found or access denied: {job_id}")

            # Convert ObjectId to string
            job["_id"] = str(job["_id"])

            # Remove export content from status response
            if "export_content" in job:
                del job["export_content"]

            self.db_manager.log_query_success(
                "ipam_export_jobs",
                "get_export_job_status",
                start_time,
                1,
                f"Found job {job_id}",
            )

            return job

        except Exception as e:
            self.db_manager.log_query_error(
                "ipam_export_jobs",
                "get_export_job_status",
                start_time,
                e,
                {"user_id": user_id, "job_id": job_id},
            )
            self.logger.error("Failed to get export job status: %s", e, exc_info=True)
            raise IPAMError(f"Failed to get export job status: {str(e)}")

    async def get_export_download_url(self, user_id: str, job_id: str) -> Dict[str, Any]:
        """
        Get export download URL and content.

        Args:
            user_id: User ID for isolation
            job_id: Export job ID

        Returns:
            Dict containing download URL and content

        Raises:
            IPAMError: If job not found, not completed, or access denied
        """
        start_time = self.db_manager.log_query_start(
            "ipam_export_jobs",
            "get_export_download_url",
            {"user_id": user_id, "job_id": job_id},
        )

        try:
            collection = self.db_manager.get_tenant_collection("ipam_export_jobs")
            job = await collection.find_one({"_id": ObjectId(job_id), "user_id": user_id})

            if not job:
                raise IPAMError(f"Export job not found or access denied: {job_id}")

            if job["status"] != "completed":
                raise IPAMError(f"Export job not completed yet: {job['status']}")

            # Check if expired
            if job.get("expires_at") and job["expires_at"] < datetime.now(timezone.utc):
                raise IPAMError("Export has expired")

            self.db_manager.log_query_success(
                "ipam_export_jobs",
                "get_export_download_url",
                start_time,
                1,
                f"Retrieved export content for job {job_id}",
            )

            return {
                "job_id": str(job["_id"]),
                "download_url": job["download_url"],
                "format": job["format"],
                "content": job.get("export_content", ""),
                "expires_at": job.get("expires_at"),
            }

        except Exception as e:
            self.db_manager.log_query_error(
                "ipam_export_jobs",
                "get_export_download_url",
                start_time,
                e,
                {"user_id": user_id, "job_id": job_id},
            )
            self.logger.error("Failed to get export download URL: %s", e, exc_info=True)
            raise IPAMError(f"Failed to get export download URL: {str(e)}")

    async def import_allocations(
        self,
        user_id: str,
        file_content: str,
        file_format: str,
        mode: str = "preview",
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Import allocations from CSV/JSON with validation.

        Args:
            user_id: User ID for isolation
            file_content: File content as string
            file_format: File format ("csv" or "json")
            mode: Import mode ("auto", "manual", "preview")
            force: Skip existing allocations without error

        Returns:
            Dict containing import results and validation report

        Raises:
            ValidationError: If file format is invalid or validation fails
        """
        start_time = time.time()
        operation_context = {
            "user_id": user_id,
            "format": file_format,
            "mode": mode,
            "force": force,
            "operation": "import_allocations",
        }
        db_start_time = self.db_manager.log_query_start("ipam_regions", "import_allocations", operation_context)

        try:
            # Validate format
            if file_format not in ["csv", "json"]:
                raise ValidationError(f"Invalid file format: {file_format}", field="format", value=file_format)

            # Validate mode
            if mode not in ["auto", "manual", "preview"]:
                raise ValidationError(f"Invalid import mode: {mode}", field="mode", value=mode)

            # Parse file
            if file_format == "csv":
                parsed_data = self._parse_csv_import(file_content)
            else:
                parsed_data = self._parse_json_import(file_content)

            # Validate parsed data
            validation_result = await self._validate_import_data(user_id, parsed_data, mode)

            # If preview mode, return validation results without importing
            if mode == "preview":
                duration = time.time() - start_time
                self.logger.info(
                    "Import preview completed for user %s: %d valid, %d invalid (%.3fs)",
                    user_id,
                    validation_result["valid_rows"],
                    validation_result["invalid_rows"],
                    duration,
                )
                return validation_result

            # If validation failed and not force mode, return errors
            if not validation_result["valid"] and not force:
                return validation_result

            # Import valid allocations
            import_result = await self._import_validated_data(
                user_id,
                parsed_data,
                validation_result,
                mode,
                force,
            )

            duration = time.time() - start_time
            self.db_manager.log_query_success(
                "ipam_regions",
                "import_allocations",
                db_start_time,
                import_result["successful"],
                f"Imported {import_result['successful']} allocations",
            )
            self.logger.info(
                "Import completed for user %s: %d successful, %d failed (%.3fs)",
                user_id,
                import_result["successful"],
                import_result["failed"],
                duration,
            )

            return import_result

        except ValidationError:
            raise
        except Exception as e:
            self.db_manager.log_query_error(
                "ipam_regions",
                "import_allocations",
                db_start_time,
                e,
                operation_context,
            )
            self.logger.error("Failed to import allocations: %s", e, exc_info=True)
            raise IPAMError(f"Failed to import allocations: {str(e)}")

    def _parse_csv_import(self, file_content: str) -> List[Dict[str, Any]]:
        """
        Parse CSV import file.

        Args:
            file_content: CSV file content

        Returns:
            List of parsed row dictionaries

        Raises:
            ValidationError: If CSV parsing fails
        """
        import csv
        import io

        try:
            parsed_data = []
            reader = csv.DictReader(io.StringIO(file_content))

            for line_num, row in enumerate(reader, start=2):  # Start at 2 (header is line 1)
                parsed_data.append({
                    "line_number": line_num,
                    "data": row,
                })

            return parsed_data

        except Exception as e:
            raise ValidationError(f"Failed to parse CSV file: {str(e)}", field="file_content")

    def _parse_json_import(self, file_content: str) -> List[Dict[str, Any]]:
        """
        Parse JSON import file.

        Args:
            file_content: JSON file content

        Returns:
            List of parsed row dictionaries

        Raises:
            ValidationError: If JSON parsing fails
        """
        import json

        try:
            data = json.loads(file_content)

            # Support both array format and object with regions/hosts
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                items = data.get("regions", []) + data.get("hosts", [])
            else:
                raise ValidationError("Invalid JSON structure", field="file_content")

            parsed_data = []
            for idx, item in enumerate(items, start=1):
                parsed_data.append({
                    "line_number": idx,
                    "data": item,
                })

            return parsed_data

        except json.JSONDecodeError as e:
            raise ValidationError(f"Failed to parse JSON file: {str(e)}", field="file_content")
        except Exception as e:
            raise ValidationError(f"Failed to parse JSON file: {str(e)}", field="file_content")

    async def _validate_import_data(
        self,
        user_id: str,
        parsed_data: List[Dict[str, Any]],
        mode: str,
    ) -> Dict[str, Any]:
        """
        Validate import data.

        Args:
            user_id: User ID
            parsed_data: Parsed data from file
            mode: Import mode

        Returns:
            Validation result dictionary
        """
        errors = []
        warnings = []
        valid_rows = 0
        invalid_rows = 0

        # Track duplicates within file
        seen_region_names = {}
        seen_hostnames = {}
        seen_ips = set()

        for item in parsed_data:
            line_num = item["line_number"]
            row = item["data"]
            row_errors = []

            # Determine if this is a region or host
            is_region = "region_name" in row and "cidr" in row
            is_host = "hostname" in row and "ip_address" in row

            if is_region:
                # Validate region
                if not row.get("country"):
                    row_errors.append("Missing required field: country")
                if not row.get("region_name"):
                    row_errors.append("Missing required field: region_name")

                # Check for duplicate region name within file
                country = row.get("country", "")
                region_name = row.get("region_name", "")
                key = f"{country}:{region_name}"
                if key in seen_region_names:
                    row_errors.append(
                        f"Duplicate region name '{region_name}' in country '{country}' "
                        f"(also on line {seen_region_names[key]})"
                    )
                else:
                    seen_region_names[key] = line_num

                # Validate country exists
                if country:
                    try:
                        await self.get_country_mapping(country)
                    except CountryNotFound:
                        row_errors.append(f"Country not found: {country}")

                # Check for existing allocation (conflict)
                if mode == "manual" and not row_errors:
                    regions_collection = self.db_manager.get_tenant_collection("ipam_regions")
                    existing = await regions_collection.find_one({
                        "user_id": user_id,
                        "country": country,
                        "region_name": region_name,
                    })
                    if existing:
                        row_errors.append(f"Region '{region_name}' already exists in {country}")

            elif is_host:
                # Validate host
                if not row.get("region_name") and not row.get("region_id"):
                    row_errors.append("Missing required field: region_name or region_id")
                if not row.get("hostname"):
                    row_errors.append("Missing required field: hostname")
                if not row.get("ip_address"):
                    row_errors.append("Missing required field: ip_address")

                # Validate IP format
                ip_address = row.get("ip_address", "")
                if ip_address:
                    if not self._validate_ip_format(ip_address):
                        row_errors.append(f"Invalid IP address format: {ip_address}")

                    # Check for duplicate IP within file
                    if ip_address in seen_ips:
                        row_errors.append(f"Duplicate IP address: {ip_address}")
                    else:
                        seen_ips.add(ip_address)

                # Check for duplicate hostname within region
                region_name = row.get("region_name", "")
                hostname = row.get("hostname", "")
                key = f"{region_name}:{hostname}"
                if key in seen_hostnames:
                    row_errors.append(
                        f"Duplicate hostname '{hostname}' in region '{region_name}' "
                        f"(also on line {seen_hostnames[key]})"
                    )
                else:
                    seen_hostnames[key] = line_num

                # Check for existing allocation (conflict)
                if mode == "manual" and ip_address and not row_errors:
                    hosts_collection = self.db_manager.get_tenant_collection("ipam_hosts")
                    existing = await hosts_collection.find_one({
                        "user_id": user_id,
                        "ip_address": ip_address,
                    })
                    if existing:
                        row_errors.append(f"IP address {ip_address} already allocated")

            else:
                row_errors.append("Cannot determine if row is region or host (missing required fields)")

            # Record errors for this row
            if row_errors:
                invalid_rows += 1
                errors.append({
                    "line_number": line_num,
                    "errors": row_errors,
                    "row_data": row,
                })
            else:
                valid_rows += 1

        # Build validation result
        validation_result = {
            "valid": len(errors) == 0,
            "total_rows": len(parsed_data),
            "valid_rows": valid_rows,
            "invalid_rows": invalid_rows,
            "errors": errors,
            "warnings": warnings,
        }

        return validation_result

    def _validate_ip_format(self, ip_address: str) -> bool:
        """
        Validate IP address format (10.0.0.0/8 range).

        Args:
            ip_address: IP address string

        Returns:
            True if valid, False otherwise
        """
        import re

        # Basic IP format validation
        pattern = r"^10\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$"
        match = re.match(pattern, ip_address)

        if not match:
            return False

        # Validate octet ranges
        x, y, z = match.groups()
        try:
            x_val = int(x)
            y_val = int(y)
            z_val = int(z)

            if not (0 <= x_val <= 255):
                return False
            if not (0 <= y_val <= 255):
                return False
            if not (1 <= z_val <= 254):  # Exclude 0 and 255
                return False

            return True
        except ValueError:
            return False

    async def _import_validated_data(
        self,
        user_id: str,
        parsed_data: List[Dict[str, Any]],
        validation_result: Dict[str, Any],
        mode: str,
        force: bool,
    ) -> Dict[str, Any]:
        """
        Import validated data with transaction support.

        Args:
            user_id: User ID
            parsed_data: Parsed data from file
            validation_result: Validation results
            mode: Import mode
            force: Skip existing allocations

        Returns:
            Import result dictionary
        """
        successful = 0
        failed = 0
        skipped = 0
        results = []

        # Get error line numbers for quick lookup
        error_lines = {err["line_number"] for err in validation_result["errors"]}

        for item in parsed_data:
            line_num = item["line_number"]
            row = item["data"]

            # Skip invalid rows
            if line_num in error_lines:
                if not force:
                    failed += 1
                    results.append({
                        "line_number": line_num,
                        "status": "failed",
                        "reason": "Validation errors",
                    })
                else:
                    skipped += 1
                    results.append({
                        "line_number": line_num,
                        "status": "skipped",
                        "reason": "Validation errors (force mode)",
                    })
                continue

            # Determine if region or host
            is_region = "region_name" in row and "country" in row
            is_host = "hostname" in row and "ip_address" in row

            try:
                if is_region:
                    # Import region
                    if mode == "auto":
                        # Auto-allocate X.Y
                        region = await self.allocate_region(
                            user_id=user_id,
                            country=row["country"],
                            region_name=row["region_name"],
                            description=row.get("description"),
                            tags=self._parse_tags(row.get("tags")),
                        )
                    else:
                        # Manual mode - use provided X.Y values
                        # This would require a separate method to create region with specific X.Y
                        # For now, use auto-allocation
                        region = await self.allocate_region(
                            user_id=user_id,
                            country=row["country"],
                            region_name=row["region_name"],
                            description=row.get("description"),
                            tags=self._parse_tags(row.get("tags")),
                        )

                    successful += 1
                    results.append({
                        "line_number": line_num,
                        "status": "success",
                        "resource_type": "region",
                        "resource_id": region["region_id"],
                        "cidr": region["cidr"],
                    })

                elif is_host:
                    # Import host
                    # First, find the region by name
                    regions_collection = self.db_manager.get_tenant_collection("ipam_regions")
                    region = await regions_collection.find_one({
                        "user_id": user_id,
                        "region_name": row.get("region_name"),
                    })

                    if not region:
                        failed += 1
                        results.append({
                            "line_number": line_num,
                            "status": "failed",
                            "reason": f"Region not found: {row.get('region_name')}",
                        })
                        continue

                    if mode == "auto":
                        # Auto-allocate Z
                        host = await self.allocate_host(
                            user_id=user_id,
                            region_id=str(region["_id"]),
                            hostname=row["hostname"],
                            metadata={
                                "device_type": row.get("device_type"),
                                "os_type": row.get("os_type"),
                                "application": row.get("application"),
                                "owner": row.get("owner"),
                                "purpose": row.get("purpose"),
                                "tags": self._parse_tags(row.get("tags")),
                            },
                        )
                    else:
                        # Manual mode - use provided IP
                        # This would require a separate method to create host with specific IP
                        # For now, use auto-allocation
                        host = await self.allocate_host(
                            user_id=user_id,
                            region_id=str(region["_id"]),
                            hostname=row["hostname"],
                            metadata={
                                "device_type": row.get("device_type"),
                                "os_type": row.get("os_type"),
                                "application": row.get("application"),
                                "owner": row.get("owner"),
                                "purpose": row.get("purpose"),
                                "tags": self._parse_tags(row.get("tags")),
                            },
                        )

                    successful += 1
                    results.append({
                        "line_number": line_num,
                        "status": "success",
                        "resource_type": "host",
                        "resource_id": host["host_id"],
                        "ip_address": host["ip_address"],
                    })

            except Exception as e:
                failed += 1
                results.append({
                    "line_number": line_num,
                    "status": "failed",
                    "reason": str(e),
                })
                self.logger.warning("Failed to import row %d: %s", line_num, e)

        return {
            "total_rows": len(parsed_data),
            "successful": successful,
            "failed": failed,
            "skipped": skipped,
            "results": results,
            "validation": validation_result,
        }

    def _parse_tags(self, tags_str: Optional[str]) -> Optional[Dict[str, str]]:
        """
        Parse tags string to dictionary.

        Args:
            tags_str: Tags string (e.g., "key1=value1;key2=value2")

        Returns:
            Tags dictionary or None
        """
        import json

        if not tags_str:
            return None

        try:
            # Try JSON format first
            return json.loads(tags_str)
        except (json.JSONDecodeError, TypeError):
            pass

        try:
            # Try key=value;key=value format
            tags = {}
            for pair in tags_str.split(";"):
                if "=" in pair:
                    key, value = pair.split("=", 1)
                    tags[key.strip()] = value.strip()
            return tags if tags else None
        except Exception:
            return None

    # ==================== IPAM Enhancements: Reservation Management ====================

    async def validate_reservation(
        self, user_id: str, x_octet: int, y_octet: int, z_octet: Optional[int] = None
    ) -> bool:
        """
        Validate reservation doesn't conflict with existing allocations or reservations.

        Args:
            user_id: User ID for isolation
            x_octet: X octet value
            y_octet: Y octet value
            z_octet: Z octet value (for host reservations)

        Returns:
            True if reservation is valid

        Raises:
            DuplicateAllocation: If address is already allocated or reserved
        """
        try:
            if z_octet is not None:
                # Host reservation - check if already allocated
                hosts_collection = self.db_manager.get_tenant_collection("ipam_hosts")
                existing_host = await hosts_collection.find_one({
                    "user_id": user_id,
                    "x_octet": x_octet,
                    "y_octet": y_octet,
                    "z_octet": z_octet,
                    "status": {"$ne": "Released"}
                })
                if existing_host:
                    raise DuplicateAllocation(
                        f"IP address 10.{x_octet}.{y_octet}.{z_octet} is already allocated",
                        resource_type="host",
                        identifier=f"10.{x_octet}.{y_octet}.{z_octet}"
                    )
            else:
                # Region reservation - check if already allocated
                regions_collection = self.db_manager.get_tenant_collection("ipam_regions")
                existing_region = await regions_collection.find_one({
                    "user_id": user_id,
                    "x_octet": x_octet,
                    "y_octet": y_octet,
                    "status": {"$ne": "Retired"}
                })
                if existing_region:
                    raise DuplicateAllocation(
                        f"Region 10.{x_octet}.{y_octet}.0/24 is already allocated",
                        resource_type="region",
                        identifier=f"10.{x_octet}.{y_octet}.0/24"
                    )

            # Check if already reserved
            reservations_collection = self.db_manager.get_tenant_collection("ipam_reservations")
            existing_reservation = await reservations_collection.find_one({
                "user_id": user_id,
                "x_octet": x_octet,
                "y_octet": y_octet,
                "z_octet": z_octet,
                "status": "active"
            })
            if existing_reservation:
                address = f"10.{x_octet}.{y_octet}.{z_octet}" if z_octet else f"10.{x_octet}.{y_octet}.0/24"
                raise DuplicateAllocation(
                    f"Address {address} is already reserved",
                    resource_type="host" if z_octet else "region",
                    identifier=address
                )

            return True

        except DuplicateAllocation:
            raise
        except Exception as e:
            self.logger.error("Failed to validate reservation: %s", e, exc_info=True)
            raise IPAMError(f"Failed to validate reservation: {str(e)}")

    async def create_reservation(
        self,
        user_id: str,
        resource_type: str,
        x_octet: int,
        y_octet: int,
        z_octet: Optional[int],
        reason: str,
        expires_in_days: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Create a new reservation.

        Args:
            user_id: User ID for isolation
            resource_type: "region" or "host"
            x_octet: X octet value
            y_octet: Y octet value
            z_octet: Z octet value (required for host reservations)
            reason: Reason for reservation
            expires_in_days: Optional expiration in days (max 90)

        Returns:
            Dict containing reservation details

        Raises:
            ValidationError: If validation fails
            DuplicateAllocation: If address is already allocated or reserved
        """
        try:
            # Validate reservation
            await self.validate_reservation(user_id, x_octet, y_octet, z_octet)

            # Calculate expiration
            now = datetime.now(timezone.utc)
            expires_at = None
            if expires_in_days:
                from datetime import timedelta
                expires_at = now + timedelta(days=min(expires_in_days, 90))

            # Build reservation document
            reserved_address = f"10.{x_octet}.{y_octet}.{z_octet}" if z_octet else f"10.{x_octet}.{y_octet}.0/24"
            
            reservation_doc = {
                "user_id": user_id,
                "resource_type": resource_type,
                "x_octet": x_octet,
                "y_octet": y_octet,
                "z_octet": z_octet,
                "reason": reason,
                "status": "active",
                "expires_at": expires_at,
                "created_at": now,
                "created_by": user_id,
                "metadata": {}
            }

            # Insert reservation
            collection = self.db_manager.get_tenant_collection("ipam_reservations")
            result = await collection.insert_one(reservation_doc)
            reservation_doc["_id"] = result.inserted_id

            self.logger.info(
                "Reservation created: user=%s type=%s address=%s expires=%s",
                user_id, resource_type, reserved_address, expires_at
            )

            # Convert ObjectId to string
            reservation_doc["_id"] = str(reservation_doc["_id"])
            reservation_doc["reserved_address"] = reserved_address

            return reservation_doc

        except (ValidationError, DuplicateAllocation):
            raise
        except Exception as e:
            self.logger.error("Failed to create reservation: %s", e, exc_info=True)
            raise IPAMError(f"Failed to create reservation: {str(e)}")

    async def get_reservations(
        self,
        user_id: str,
        filters: Optional[Dict[str, Any]] = None,
        page: int = 1,
        page_size: int = 50
    ) -> Dict[str, Any]:
        """
        Get user's reservations with filtering and pagination.

        Args:
            user_id: User ID for isolation
            filters: Optional filters (status, resource_type)
            page: Page number
            page_size: Items per page

        Returns:
            Dict containing reservations list and pagination info
        """
        try:
            # Build query
            query = {"user_id": user_id}
            filters = filters or {}
            
            if "status" in filters:
                query["status"] = filters["status"]
            if "resource_type" in filters:
                query["resource_type"] = filters["resource_type"]

            # Get total count
            collection = self.db_manager.get_tenant_collection("ipam_reservations")
            total_count = await collection.count_documents(query)

            # Calculate pagination
            skip = (page - 1) * page_size
            total_pages = (total_count + page_size - 1) // page_size

            # Query with pagination
            cursor = collection.find(query).sort("created_at", -1).skip(skip).limit(page_size)
            reservations = await cursor.to_list(length=page_size)

            # Convert ObjectIds and add reserved_address
            for reservation in reservations:
                reservation["_id"] = str(reservation["_id"])
                x, y, z = reservation["x_octet"], reservation["y_octet"], reservation.get("z_octet")
                reservation["reserved_address"] = f"10.{x}.{y}.{z}" if z else f"10.{x}.{y}.0/24"

            return {
                "reservations": reservations,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total_count": total_count,
                    "total_pages": total_pages,
                    "has_next": page < total_pages,
                    "has_prev": page > 1,
                },
            }

        except Exception as e:
            self.logger.error("Failed to get reservations: %s", e, exc_info=True)
            raise IPAMError(f"Failed to get reservations: {str(e)}")

    async def get_reservation_by_id(self, user_id: str, reservation_id: str) -> Dict[str, Any]:
        """
        Get reservation by ID with ownership validation.

        Args:
            user_id: User ID for isolation
            reservation_id: Reservation ID

        Returns:
            Dict containing reservation details

        Raises:
            IPAMError: If reservation not found
        """
        try:
            collection = self.db_manager.get_tenant_collection("ipam_reservations")
            reservation = await collection.find_one({"_id": ObjectId(reservation_id), "user_id": user_id})

            if not reservation:
                raise IPAMError(f"Reservation not found: {reservation_id}")

            reservation["_id"] = str(reservation["_id"])
            x, y, z = reservation["x_octet"], reservation["y_octet"], reservation.get("z_octet")
            reservation["reserved_address"] = f"10.{x}.{y}.{z}" if z else f"10.{x}.{y}.0/24"

            return reservation

        except IPAMError:
            raise
        except Exception as e:
            self.logger.error("Failed to get reservation: %s", e, exc_info=True)
            raise IPAMError(f"Failed to get reservation: {str(e)}")

    async def convert_reservation(
        self,
        user_id: str,
        reservation_id: str,
        region_name: Optional[str] = None,
        hostname: Optional[str] = None,
        description: Optional[str] = None,
        owner: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Convert reservation to actual allocation.

        Args:
            user_id: User ID for isolation
            reservation_id: Reservation ID
            region_name: Region name (for region conversion)
            hostname: Hostname (for host conversion)
            description: Optional description
            owner: Optional owner
            tags: Optional tags
            metadata: Optional metadata

        Returns:
            Dict containing allocation details

        Raises:
            IPAMError: If reservation not found or conversion fails
        """
        try:
            # Get reservation
            reservation = await self.get_reservation_by_id(user_id, reservation_id)

            if reservation["status"] != "active":
                raise ValidationError(
                    f"Cannot convert reservation with status: {reservation['status']}",
                    field="status",
                    value=reservation["status"]
                )

            resource_type = reservation["resource_type"]
            x_octet = reservation["x_octet"]
            y_octet = reservation["y_octet"]
            z_octet = reservation.get("z_octet")

            # Convert based on type
            if resource_type == "region":
                if not region_name:
                    raise ValidationError("region_name is required for region conversion", field="region_name")

                # Get country for this X octet
                country_mapping = await self.get_country_by_x_octet(x_octet)
                country = country_mapping["country"]

                # Create region with specific X.Y
                regions_collection = self.db_manager.get_tenant_collection("ipam_regions")
                now = datetime.now(timezone.utc)
                
                region_doc = {
                    "user_id": user_id,
                    "country": country,
                    "continent": country_mapping["continent"],
                    "x_octet": x_octet,
                    "y_octet": y_octet,
                    "cidr": f"10.{x_octet}.{y_octet}.0/24",
                    "region_name": region_name,
                    "description": description or f"Converted from reservation: {reservation['reason']}",
                    "owner": owner or user_id,
                    "status": "Active",
                    "tags": tags or {},
                    "comments": [],
                    "created_at": now,
                    "updated_at": now,
                    "created_by": user_id,
                    "updated_by": user_id,
                }

                result = await regions_collection.insert_one(region_doc)
                region_doc["_id"] = str(result.inserted_id)

                # Update quota
                await self.update_quota_counter(user_id, "region", 1)

                allocation = region_doc

            else:  # host
                if not hostname:
                    raise ValidationError("hostname is required for host conversion", field="hostname")

                # Find region for this X.Y
                regions_collection = self.db_manager.get_tenant_collection("ipam_regions")
                region = await regions_collection.find_one({
                    "user_id": user_id,
                    "x_octet": x_octet,
                    "y_octet": y_octet,
                    "status": "Active"
                })

                if not region:
                    raise IPAMError(f"No active region found for 10.{x_octet}.{y_octet}.0/24")

                # Create host with specific Z
                hosts_collection = self.db_manager.get_tenant_collection("ipam_hosts")
                now = datetime.now(timezone.utc)
                
                metadata = metadata or {}
                host_doc = {
                    "user_id": user_id,
                    "region_id": region["_id"],
                    "x_octet": x_octet,
                    "y_octet": y_octet,
                    "z_octet": z_octet,
                    "ip_address": f"10.{x_octet}.{y_octet}.{z_octet}",
                    "hostname": hostname,
                    "device_type": metadata.get("device_type", ""),
                    "os_type": metadata.get("os_type", ""),
                    "application": metadata.get("application", ""),
                    "cost_center": metadata.get("cost_center", ""),
                    "owner": owner or user_id,
                    "purpose": metadata.get("purpose", f"Converted from reservation: {reservation['reason']}"),
                    "status": "Active",
                    "tags": tags or {},
                    "notes": "",
                    "comments": [],
                    "created_at": now,
                    "updated_at": now,
                    "created_by": user_id,
                    "updated_by": user_id,
                }

                result = await hosts_collection.insert_one(host_doc)
                host_doc["_id"] = str(result.inserted_id)
                host_doc["region_id"] = str(host_doc["region_id"])

                # Update quota
                await self.update_quota_counter(user_id, "host", 1)

                allocation = host_doc

            # Mark reservation as converted
            reservations_collection = self.db_manager.get_tenant_collection("ipam_reservations")
            await reservations_collection.update_one(
                {"_id": ObjectId(reservation_id)},
                {"$set": {"status": "converted", "converted_at": datetime.now(timezone.utc)}}
            )

            # Create audit trail
            await self._log_audit_event(
                user_id=user_id,
                action_type="convert_reservation",
                resource_type=resource_type,
                resource_id=str(allocation["_id"]),
                cidr=allocation.get("cidr") or allocation.get("ip_address"),
                snapshot=allocation,
                changes=[],
                reason=f"Converted from reservation: {reservation['reason']}"
            )

            self.logger.info(
                "Reservation converted: user=%s reservation_id=%s type=%s allocation_id=%s",
                user_id, reservation_id, resource_type, allocation["_id"]
            )

            return {
                "resource_type": resource_type,
                "resource_id": str(allocation["_id"]),
                "allocation": allocation
            }

        except (ValidationError, IPAMError):
            raise
        except Exception as e:
            self.logger.error("Failed to convert reservation: %s", e, exc_info=True)
            raise IPAMError(f"Failed to convert reservation: {str(e)}")

    async def delete_reservation(self, user_id: str, reservation_id: str) -> None:
        """
        Delete (cancel) a reservation.

        Args:
            user_id: User ID for isolation
            reservation_id: Reservation ID

        Raises:
            IPAMError: If reservation not found
        """
        try:
            collection = self.db_manager.get_tenant_collection("ipam_reservations")
            result = await collection.delete_one({"_id": ObjectId(reservation_id), "user_id": user_id})

            if result.deleted_count == 0:
                raise IPAMError(f"Reservation not found: {reservation_id}")

            self.logger.info("Reservation deleted: user=%s reservation_id=%s", user_id, reservation_id)

        except IPAMError:
            raise
        except Exception as e:
            self.logger.error("Failed to delete reservation: %s", e, exc_info=True)
            raise IPAMError(f"Failed to delete reservation: {str(e)}")

    # ==================== IPAM Enhancements: User Preferences ====================

    async def get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """
        Get user preferences.

        Args:
            user_id: User ID

        Returns:
            Dict containing user preferences
        """
        try:
            collection = self.db_manager.get_tenant_collection("ipam_user_preferences")
            preferences = await collection.find_one({"user_id": user_id})

            if not preferences:
                # Create default preferences
                now = datetime.now(timezone.utc)
                preferences = {
                    "user_id": user_id,
                    "saved_filters": [],
                    "dashboard_layout": {},
                    "notification_settings": {},
                    "theme_preference": None,
                    "updated_at": now
                }
                await collection.insert_one(preferences)

            preferences["_id"] = str(preferences["_id"])
            return preferences

        except Exception as e:
            self.logger.error("Failed to get user preferences: %s", e, exc_info=True)
            raise IPAMError(f"Failed to get user preferences: {str(e)}")

    async def update_user_preferences(
        self,
        user_id: str,
        dashboard_layout: Optional[Dict[str, Any]] = None,
        notification_settings: Optional[Dict[str, Any]] = None,
        theme_preference: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update user preferences (merge with existing).

        Args:
            user_id: User ID
            dashboard_layout: Optional dashboard layout
            notification_settings: Optional notification settings
            theme_preference: Optional theme preference

        Returns:
            Dict containing updated preferences
        """
        try:
            collection = self.db_manager.get_tenant_collection("ipam_user_preferences")
            
            # Build update document
            update_doc = {"$set": {"updated_at": datetime.now(timezone.utc)}}
            
            if dashboard_layout is not None:
                update_doc["$set"]["dashboard_layout"] = dashboard_layout
            if notification_settings is not None:
                update_doc["$set"]["notification_settings"] = notification_settings
            if theme_preference is not None:
                update_doc["$set"]["theme_preference"] = theme_preference

            # Update or create
            await collection.update_one(
                {"user_id": user_id},
                update_doc,
                upsert=True
            )

            # Return updated preferences
            return await self.get_user_preferences(user_id)

        except Exception as e:
            self.logger.error("Failed to update user preferences: %s", e, exc_info=True)
            raise IPAMError(f"Failed to update user preferences: {str(e)}")

    async def save_filter(
        self,
        user_id: str,
        name: str,
        criteria: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Save a search filter.

        Args:
            user_id: User ID
            name: Filter name
            criteria: Filter criteria

        Returns:
            Dict containing saved filter

        Raises:
            ValidationError: If filter limit exceeded
        """
        try:
            import uuid
            
            collection = self.db_manager.get_tenant_collection("ipam_user_preferences")
            preferences = await self.get_user_preferences(user_id)

            # Check filter limit
            if len(preferences.get("saved_filters", [])) >= 50:
                raise ValidationError(
                    "Maximum 50 saved filters per user",
                    field="saved_filters",
                    value=len(preferences["saved_filters"])
                )

            # Create filter
            filter_doc = {
                "filter_id": str(uuid.uuid4()),
                "name": name,
                "criteria": criteria,
                "created_at": datetime.now(timezone.utc)
            }

            # Add to preferences
            await collection.update_one(
                {"user_id": user_id},
                {"$push": {"saved_filters": filter_doc}}
            )

            self.logger.info("Filter saved: user=%s name=%s", user_id, name)
            return filter_doc

        except ValidationError:
            raise
        except Exception as e:
            self.logger.error("Failed to save filter: %s", e, exc_info=True)
            raise IPAMError(f"Failed to save filter: {str(e)}")

    async def get_saved_filters(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get user's saved filters.

        Args:
            user_id: User ID

        Returns:
            List of saved filters
        """
        try:
            preferences = await self.get_user_preferences(user_id)
            return preferences.get("saved_filters", [])

        except Exception as e:
            self.logger.error("Failed to get saved filters: %s", e, exc_info=True)
            raise IPAMError(f"Failed to get saved filters: {str(e)}")

    async def delete_filter(self, user_id: str, filter_id: str) -> None:
        """
        Delete a saved filter.

        Args:
            user_id: User ID
            filter_id: Filter ID

        Raises:
            IPAMError: If filter not found
        """
        try:
            collection = self.db_manager.get_tenant_collection("ipam_user_preferences")
            result = await collection.update_one(
                {"user_id": user_id},
                {"$pull": {"saved_filters": {"filter_id": filter_id}}}
            )

            if result.modified_count == 0:
                raise IPAMError(f"Filter not found: {filter_id}")

            self.logger.info("Filter deleted: user=%s filter_id=%s", user_id, filter_id)

        except IPAMError:
            raise
        except Exception as e:
            self.logger.error("Failed to delete filter: %s", e, exc_info=True)
            raise IPAMError(f"Failed to delete filter: {str(e)}")

    # ==================== IPAM Enhancements: Dashboard Statistics ====================

    async def calculate_dashboard_stats(self, user_id: str) -> Dict[str, Any]:
        """
        Calculate dashboard statistics with caching.

        Args:
            user_id: User ID

        Returns:
            Dict containing dashboard statistics
        """
        cache_key = f"ipam:dashboard_stats:{user_id}"

        # Try cache first
        try:
            cached = await self.redis_manager.get(cache_key)
            if cached:
                self.logger.debug("Cache hit: dashboard_stats for user %s", user_id)
                return cached
        except Exception as e:
            self.logger.warning("Cache error for dashboard stats: %s", e)

        try:
            from datetime import timedelta
            
            # Get total counts
            regions_collection = self.db_manager.get_tenant_collection("ipam_regions")
            hosts_collection = self.db_manager.get_tenant_collection("ipam_hosts")

            total_regions = await regions_collection.count_documents({"user_id": user_id})
            total_hosts = await hosts_collection.count_documents({"user_id": user_id})

            # Get total available countries from continent-country mapping
            all_countries = await self.get_all_countries()
            total_countries = len(all_countries)

            # Calculate overall utilization (simplified)
            overall_utilization = 0.0
            if total_regions > 0:
                # Average utilization across all regions
                utilization_pipeline = [
                    {"$match": {"user_id": user_id}},
                    {"$lookup": {
                        "from": "ipam_hosts",
                        "let": {"region_id": "$_id"},
                        "pipeline": [
                            {"$match": {"$expr": {"$eq": ["$region_id", "$$region_id"]}}}
                        ],
                        "as": "hosts"
                    }},
                    {"$project": {
                        "host_count": {"$size": "$hosts"},
                        "utilization": {"$multiply": [{"$divide": [{"$size": "$hosts"}, 254]}, 100]}
                    }},
                    {"$group": {
                        "_id": None,
                        "avg_utilization": {"$avg": "$utilization"}
                    }}
                ]
                util_result = await regions_collection.aggregate(utilization_pipeline).to_list(1)
                overall_utilization = round(util_result[0]["avg_utilization"], 2) if util_result else 0.0

            # Get top 5 countries by allocation
            top_countries_pipeline = [
                {"$match": {"user_id": user_id}},
                {"$group": {
                    "_id": "$country",
                    "regions": {"$sum": 1}
                }},
                {"$sort": {"regions": -1}},
                {"$limit": 5}
            ]
            top_countries_cursor = regions_collection.aggregate(top_countries_pipeline)
            top_countries = await top_countries_cursor.to_list(5)
            
            # Format top countries
            top_countries_formatted = []
            for country in top_countries:
                # Get utilization for this country
                country_regions = await regions_collection.find({
                    "user_id": user_id,
                    "country": country["_id"]
                }).to_list(None)
                
                country_hosts = 0
                for region in country_regions:
                    region_hosts = await hosts_collection.count_documents({
                        "user_id": user_id,
                        "region_id": region["_id"]
                    })
                    country_hosts += region_hosts
                
                country_utilization = (country_hosts / (len(country_regions) * 254) * 100) if country_regions else 0
                
                top_countries_formatted.append({
                    "country": country["_id"],
                    "regions": country["regions"],
                    "utilization": round(country_utilization, 2)
                })

            # Get recent activity count (last 7 days)
            seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
            recent_regions = await regions_collection.count_documents({
                "user_id": user_id,
                "created_at": {"$gte": seven_days_ago}
            })
            recent_hosts = await hosts_collection.count_documents({
                "user_id": user_id,
                "created_at": {"$gte": seven_days_ago}
            })
            recent_activity_count = recent_regions + recent_hosts

            # Calculate capacity warnings (regions > 80% utilized)
            capacity_warnings = 0
            all_regions = await regions_collection.find({"user_id": user_id}).to_list(None)
            for region in all_regions:
                host_count = await hosts_collection.count_documents({
                    "user_id": user_id,
                    "region_id": region["_id"]
                })
                if (host_count / 254) > 0.8:
                    capacity_warnings += 1

            # Build response
            stats = {
                "total_countries": total_countries,
                "total_regions": total_regions,
                "total_hosts": total_hosts,
                "overall_utilization": overall_utilization,
                "top_countries": top_countries_formatted,
                "recent_activity_count": recent_activity_count,
                "capacity_warnings": capacity_warnings,
                "cached_at": datetime.now(timezone.utc)
            }

            # Cache for 5 minutes
            try:
                await self.redis_manager.set_with_expiry(cache_key, stats, 300)
            except Exception as e:
                self.logger.warning("Failed to cache dashboard stats: %s", e)

            return stats

        except Exception as e:
            self.logger.error("Failed to calculate dashboard stats: %s", e, exc_info=True)
            raise IPAMError(f"Failed to calculate dashboard stats: {str(e)}")

    # ==================== IPAM Enhancements: Capacity Forecasting ====================

    async def calculate_forecast(
        self,
        user_id: str,
        resource_type: str,
        resource_id: str
    ) -> Dict[str, Any]:
        """
        Calculate capacity forecast based on historical data.

        Args:
            user_id: User ID
            resource_type: "country" or "region"
            resource_id: Resource ID (country name or region ID)

        Returns:
            Dict containing forecast data
        """
        cache_key = f"ipam:forecast:{user_id}:{resource_type}:{resource_id}"

        # Try cache first (24-hour TTL)
        try:
            cached = await self.redis_manager.get(cache_key)
            if cached:
                self.logger.debug("Cache hit: forecast for %s %s", resource_type, resource_id)
                return cached
        except Exception as e:
            self.logger.warning("Cache error for forecast: %s", e)

        try:
            from datetime import timedelta
            
            # Get historical allocations (last 90 days)
            ninety_days_ago = datetime.now(timezone.utc) - timedelta(days=90)
            
            audit_collection = self.db_manager.get_tenant_collection("ipam_audit_history")
            
            # Build query based on resource type
            if resource_type == "country":
                query = {
                    "user_id": user_id,
                    "action_type": "create",
                    "resource_type": "region",
                    "timestamp": {"$gte": ninety_days_ago}
                }
                # Filter by country in snapshot
                allocations = []
                cursor = audit_collection.find(query).sort("timestamp", 1)
                async for doc in cursor:
                    if doc.get("snapshot", {}).get("country") == resource_id:
                        allocations.append(doc)
            else:  # region
                query = {
                    "user_id": user_id,
                    "action_type": "create",
                    "resource_type": "host",
                    "resource_id": resource_id,
                    "timestamp": {"$gte": ninety_days_ago}
                }
                allocations = await audit_collection.find(query).sort("timestamp", 1).to_list(None)

            # Check if we have enough data
            if len(allocations) < 10:
                return {
                    "resource_type": resource_type,
                    "resource_id": resource_id,
                    "confidence_level": "insufficient_data",
                    "recommendation": "Need at least 10 allocations in the past 90 days for accurate forecast",
                    "data_points": len(allocations),
                    "forecast_period_days": 90
                }

            # Calculate daily allocation rate
            first_allocation = allocations[0]["timestamp"]
            last_allocation = allocations[-1]["timestamp"]
            days_span = (last_allocation - first_allocation).days
            
            if days_span == 0:
                days_span = 1
            
            daily_rate = len(allocations) / days_span

            # Get current utilization
            if resource_type == "country":
                # Count regions in country
                regions_collection = self.db_manager.get_tenant_collection("ipam_regions")
                allocated = await regions_collection.count_documents({
                    "user_id": user_id,
                    "country": resource_id
                })
                
                # Get country capacity
                country_mapping = await self.get_country_mapping(resource_id)
                capacity = (country_mapping["x_end"] - country_mapping["x_start"] + 1) * 256
                
            else:  # region
                # Count hosts in region
                hosts_collection = self.db_manager.get_tenant_collection("ipam_hosts")
                allocated = await hosts_collection.count_documents({
                    "user_id": user_id,
                    "region_id": ObjectId(resource_id)
                })
                capacity = 254

            current_utilization = (allocated / capacity * 100) if capacity > 0 else 0
            remaining_capacity = capacity - allocated

            # Calculate exhaustion date
            exhaustion_date = None
            if daily_rate > 0 and remaining_capacity > 0:
                days_until_exhaustion = remaining_capacity / daily_rate
                exhaustion_date = datetime.now(timezone.utc) + timedelta(days=days_until_exhaustion)

            # Determine confidence level
            if len(allocations) > 50:
                confidence = "high"
            elif len(allocations) > 20:
                confidence = "medium"
            else:
                confidence = "low"

            # Generate recommendation
            if exhaustion_date:
                days_remaining = (exhaustion_date - datetime.now(timezone.utc)).days
                if days_remaining < 30:
                    recommendation = f"Critical: Capacity will be exhausted in approximately {days_remaining} days. Immediate action required."
                elif days_remaining < 90:
                    recommendation = f"Warning: Capacity will be exhausted in approximately {days_remaining} days. Plan expansion soon."
                else:
                    recommendation = f"Capacity is healthy. Estimated {days_remaining} days until exhaustion."
            else:
                recommendation = "No allocation activity detected. Capacity is stable."

            forecast = {
                "resource_type": resource_type,
                "resource_id": resource_id,
                "current_utilization": round(current_utilization, 2),
                "daily_allocation_rate": round(daily_rate, 2),
                "estimated_exhaustion_date": exhaustion_date,
                "confidence_level": confidence,
                "recommendation": recommendation,
                "data_points": len(allocations),
                "forecast_period_days": 90
            }

            # Cache for 24 hours
            try:
                await self.redis_manager.set_with_expiry(cache_key, forecast, 86400)
            except Exception as e:
                self.logger.warning("Failed to cache forecast: %s", e)

            return forecast

        except Exception as e:
            self.logger.error("Failed to calculate forecast: %s", e, exc_info=True)
            raise IPAMError(f"Failed to calculate forecast: {str(e)}")

    async def calculate_trends(
        self,
        user_id: str,
        group_by: str = "day",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        resource_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calculate allocation trends.

        Args:
            user_id: User ID
            group_by: Grouping period ("day", "week", "month")
            start_date: Optional start date
            end_date: Optional end date
            resource_type: Optional resource type filter

        Returns:
            Dict containing trend data
        """
        try:
            from datetime import timedelta
            
            # Default date range (last 90 days)
            if not end_date:
                end_date = datetime.now(timezone.utc)
            if not start_date:
                start_date = end_date - timedelta(days=90)

            # Build query
            query = {
                "user_id": user_id,
                "timestamp": {"$gte": start_date, "$lte": end_date}
            }
            
            if resource_type:
                query["resource_type"] = resource_type

            # Determine grouping format
            if group_by == "day":
                date_format = "%Y-%m-%d"
            elif group_by == "week":
                date_format = "%Y-W%U"
            elif group_by == "month":
                date_format = "%Y-%m"
            else:
                raise ValidationError("Invalid group_by value", field="group_by", value=group_by)

            # Aggregate allocations and releases
            audit_collection = self.db_manager.get_tenant_collection("ipam_audit_history")
            
            pipeline = [
                {"$match": query},
                {"$project": {
                    "date_group": {"$dateToString": {"format": date_format, "date": "$timestamp"}},
                    "action_type": 1
                }},
                {"$group": {
                    "_id": {
                        "date": "$date_group",
                        "action": "$action_type"
                    },
                    "count": {"$sum": 1}
                }},
                {"$sort": {"_id.date": 1}}
            ]
            
            results = await audit_collection.aggregate(pipeline).to_list(None)

            # Process results into time series
            time_series_data = {}
            for result in results:
                date = result["_id"]["date"]
                action = result["_id"]["action"]
                count = result["count"]
                
                if date not in time_series_data:
                    time_series_data[date] = {"allocations": 0, "releases": 0}
                
                if action == "create":
                    time_series_data[date]["allocations"] = count
                elif action in ["retire", "release"]:
                    time_series_data[date]["releases"] = count

            # Build time series list
            time_series = []
            for date, data in sorted(time_series_data.items()):
                net_growth = data["allocations"] - data["releases"]
                time_series.append({
                    "timestamp": date,
                    "allocations": data["allocations"],
                    "releases": data["releases"],
                    "net_growth": net_growth
                })

            # Calculate summary
            total_allocations = sum(d["allocations"] for d in time_series)
            total_releases = sum(d["releases"] for d in time_series)
            days_in_period = (end_date - start_date).days or 1
            average_daily_rate = total_allocations / days_in_period

            summary = {
                "total_allocations": total_allocations,
                "total_releases": total_releases,
                "average_daily_rate": round(average_daily_rate, 2)
            }

            return {
                "time_series": time_series,
                "summary": summary,
                "group_by": group_by,
                "start_date": start_date,
                "end_date": end_date
            }

        except ValidationError:
            raise
        except Exception as e:
            self.logger.error("Failed to calculate trends: %s", e, exc_info=True)
            raise IPAMError(f"Failed to calculate trends: {str(e)}")

    # ==================== IPAM Enhancements: Notification System ====================

    async def create_notification_rule(
        self,
        user_id: str,
        rule_name: str,
        conditions: Dict[str, Any],
        notification_channels: List[str]
    ) -> Dict[str, Any]:
        """
        Create a notification rule.

        Args:
            user_id: User ID
            rule_name: Rule name
            conditions: Rule conditions
            notification_channels: Notification channels

        Returns:
            Dict containing rule details
        """
        try:
            now = datetime.now(timezone.utc)
            
            rule_doc = {
                "user_id": user_id,
                "rule_name": rule_name,
                "conditions": conditions,
                "notification_channels": notification_channels,
                "is_active": True,
                "last_triggered": None,
                "created_at": now,
                "updated_at": now
            }

            collection = self.db_manager.get_tenant_collection("ipam_notification_rules")
            result = await collection.insert_one(rule_doc)
            rule_doc["_id"] = str(result.inserted_id)

            self.logger.info("Notification rule created: user=%s name=%s", user_id, rule_name)
            return rule_doc

        except Exception as e:
            self.logger.error("Failed to create notification rule: %s", e, exc_info=True)
            raise IPAMError(f"Failed to create notification rule: {str(e)}")

    async def evaluate_notification_rules(
        self,
        user_id: str,
        event_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Evaluate notification rules and create notifications.

        Args:
            user_id: User ID
            event_data: Event data to evaluate

        Returns:
            List of created notifications
        """
        try:
            collection = self.db_manager.get_tenant_collection("ipam_notification_rules")
            rules = await collection.find({"user_id": user_id, "is_active": True}).to_list(None)

            created_notifications = []
            
            for rule in rules:
                conditions = rule["conditions"]
                should_trigger = False
                
                # Evaluate utilization threshold
                if "utilization_threshold" in conditions:
                    threshold = conditions["utilization_threshold"]
                    current_util = event_data.get("utilization", 0)
                    if current_util >= threshold:
                        should_trigger = True

                # Evaluate resource type filter
                if "resource_type" in conditions:
                    if event_data.get("resource_type") != conditions["resource_type"]:
                        should_trigger = False

                # Evaluate specific resource IDs
                if "resource_ids" in conditions and conditions["resource_ids"]:
                    if event_data.get("resource_id") not in conditions["resource_ids"]:
                        should_trigger = False

                if should_trigger:
                    # Create notification
                    notification = await self.create_notification(
                        user_id=user_id,
                        notification_type=rule["rule_name"],
                        severity="warning" if event_data.get("utilization", 0) < 90 else "critical",
                        message=f"Rule '{rule['rule_name']}' triggered: {event_data.get('message', 'Condition met')}",
                        resource_type=event_data.get("resource_type"),
                        resource_id=event_data.get("resource_id"),
                        resource_link=event_data.get("resource_link")
                    )
                    created_notifications.append(notification)

                    # Update last_triggered
                    await collection.update_one(
                        {"_id": rule["_id"]},
                        {"$set": {"last_triggered": datetime.now(timezone.utc)}}
                    )

            return created_notifications

        except Exception as e:
            self.logger.error("Failed to evaluate notification rules: %s", e, exc_info=True)
            raise IPAMError(f"Failed to evaluate notification rules: {str(e)}")

    async def create_notification(
        self,
        user_id: str,
        notification_type: str,
        severity: str,
        message: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        resource_link: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a notification.

        Args:
            user_id: User ID
            notification_type: Notification type
            severity: Severity level ("info", "warning", "critical")
            message: Notification message
            resource_type: Optional resource type
            resource_id: Optional resource ID
            resource_link: Optional resource link

        Returns:
            Dict containing notification details
        """
        try:
            from datetime import timedelta
            
            now = datetime.now(timezone.utc)
            expires_at = now + timedelta(days=90)
            
            notification_doc = {
                "user_id": user_id,
                "notification_type": notification_type,
                "severity": severity,
                "message": message,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "resource_link": resource_link,
                "is_read": False,
                "read_at": None,
                "created_at": now,
                "expires_at": expires_at
            }

            collection = self.db_manager.get_tenant_collection("ipam_notifications")
            result = await collection.insert_one(notification_doc)
            notification_doc["_id"] = str(result.inserted_id)

            self.logger.info("Notification created: user=%s type=%s severity=%s", user_id, notification_type, severity)
            return notification_doc

        except Exception as e:
            self.logger.error("Failed to create notification: %s", e, exc_info=True)
            raise IPAMError(f"Failed to create notification: {str(e)}")

    async def get_notifications(
        self,
        user_id: str,
        filters: Optional[Dict[str, Any]] = None,
        page: int = 1,
        page_size: int = 50
    ) -> Dict[str, Any]:
        """
        Get user notifications with filtering and pagination.

        Args:
            user_id: User ID
            filters: Optional filters (is_read, severity)
            page: Page number
            page_size: Items per page

        Returns:
            Dict containing notifications and pagination
        """
        try:
            query = {"user_id": user_id}
            filters = filters or {}
            
            if "is_read" in filters:
                query["is_read"] = filters["is_read"]
            if "severity" in filters:
                query["severity"] = filters["severity"]

            collection = self.db_manager.get_tenant_collection("ipam_notifications")
            total_count = await collection.count_documents(query)

            skip = (page - 1) * page_size
            total_pages = (total_count + page_size - 1) // page_size

            cursor = collection.find(query).sort("created_at", -1).skip(skip).limit(page_size)
            notifications = await cursor.to_list(page_size)

            for notification in notifications:
                notification["_id"] = str(notification["_id"])

            # Get unread count
            unread_count = await collection.count_documents({"user_id": user_id, "is_read": False})

            return {
                "notifications": notifications,
                "unread_count": unread_count,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total_count": total_count,
                    "total_pages": total_pages,
                    "has_next": page < total_pages,
                    "has_prev": page > 1,
                }
            }

        except Exception as e:
            self.logger.error("Failed to get notifications: %s", e, exc_info=True)
            raise IPAMError(f"Failed to get notifications: {str(e)}")

    async def mark_notification_read(self, user_id: str, notification_id: str, is_read: bool = True) -> None:
        """
        Mark notification as read/unread.

        Args:
            user_id: User ID
            notification_id: Notification ID
            is_read: Read status

        Raises:
            IPAMError: If notification not found
        """
        try:
            collection = self.db_manager.get_tenant_collection("ipam_notifications")
            result = await collection.update_one(
                {"_id": ObjectId(notification_id), "user_id": user_id},
                {"$set": {"is_read": is_read, "read_at": datetime.now(timezone.utc) if is_read else None}}
            )

            if result.modified_count == 0:
                raise IPAMError(f"Notification not found: {notification_id}")

            self.logger.info("Notification marked as %s: user=%s id=%s", "read" if is_read else "unread", user_id, notification_id)

        except IPAMError:
            raise
        except Exception as e:
            self.logger.error("Failed to mark notification: %s", e, exc_info=True)
            raise IPAMError(f"Failed to mark notification: {str(e)}")

    async def delete_notification(self, user_id: str, notification_id: str) -> None:
        """
        Delete (dismiss) a notification.

        Args:
            user_id: User ID
            notification_id: Notification ID

        Raises:
            IPAMError: If notification not found
        """
        try:
            collection = self.db_manager.get_tenant_collection("ipam_notifications")
            result = await collection.delete_one({"_id": ObjectId(notification_id), "user_id": user_id})

            if result.deleted_count == 0:
                raise IPAMError(f"Notification not found: {notification_id}")

            self.logger.info("Notification deleted: user=%s id=%s", user_id, notification_id)

        except IPAMError:
            raise
        except Exception as e:
            self.logger.error("Failed to delete notification: %s", e, exc_info=True)
            raise IPAMError(f"Failed to delete notification: {str(e)}")

    # ==================== IPAM Enhancements: Shareable Links ====================

    async def create_share(
        self,
        user_id: str,
        resource_type: str,
        resource_id: str,
        expires_in_days: int,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a shareable link.

        Args:
            user_id: User ID
            resource_type: Resource type ("country", "region", "host")
            resource_id: Resource ID
            expires_in_days: Expiration in days (max 90)
            description: Optional description

        Returns:
            Dict containing share details
        """
        try:
            import uuid
            from datetime import timedelta
            
            # Validate resource exists and user owns it
            if resource_type == "region":
                region = await self.get_region_by_id(user_id, resource_id)
                if not region:
                    raise IPAMError(f"Region not found: {resource_id}")
            elif resource_type == "host":
                host = await self.get_host_by_id(user_id, resource_id)
                if not host:
                    raise IPAMError(f"Host not found: {resource_id}")
            elif resource_type == "country":
                # Just validate country exists
                await self.get_country_mapping(resource_id)

            # Generate share token
            share_token = str(uuid.uuid4())
            
            now = datetime.now(timezone.utc)
            expires_at = now + timedelta(days=min(expires_in_days, 90))
            
            share_doc = {
                "share_token": share_token,
                "user_id": user_id,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "expires_at": expires_at,
                "view_count": 0,
                "last_accessed": None,
                "created_at": now,
                "created_by": user_id,
                "is_active": True,
                "description": description
            }

            collection = self.db_manager.get_tenant_collection("ipam_shares")
            result = await collection.insert_one(share_doc)
            share_doc["_id"] = str(result.inserted_id)

            # Build share URL (will be completed by API layer)
            share_doc["share_url"] = f"/ipam/shares/{share_token}"

            self.logger.info("Share created: user=%s type=%s resource=%s token=%s", user_id, resource_type, resource_id, share_token)
            return share_doc

        except (IPAMError, CountryNotFound):
            raise
        except Exception as e:
            self.logger.error("Failed to create share: %s", e, exc_info=True)
            raise IPAMError(f"Failed to create share: {str(e)}")

    async def get_shared_resource(self, share_token: str) -> Dict[str, Any]:
        """
        Get shared resource (no auth required).

        Args:
            share_token: Share token

        Returns:
            Dict containing sanitized resource data

        Raises:
            IPAMError: If share not found or expired
        """
        try:
            collection = self.db_manager.get_tenant_collection("ipam_shares")
            share = await collection.find_one({"share_token": share_token, "is_active": True})

            if not share:
                raise IPAMError("Share not found or has been revoked")

            # Check expiration
            if share["expires_at"] < datetime.now(timezone.utc):
                raise IPAMError("Share has expired")

            # Get resource data
            resource_type = share["resource_type"]
            resource_id = share["resource_id"]
            user_id = share["user_id"]

            if resource_type == "region":
                resource_data = await self.get_region_by_id(user_id, resource_id)
            elif resource_type == "host":
                resource_data = await self.get_host_by_id(user_id, resource_id)
            elif resource_type == "country":
                resource_data = await self.get_country_mapping(resource_id)
            else:
                raise IPAMError(f"Invalid resource type: {resource_type}")

            # Sanitize data (remove sensitive fields)
            sanitized_data = self._sanitize_shared_resource(resource_data)

            # Update view count and last accessed
            await collection.update_one(
                {"_id": share["_id"]},
                {
                    "$inc": {"view_count": 1},
                    "$set": {"last_accessed": datetime.now(timezone.utc)}
                }
            )

            # Get username for shared_by
            users_collection = self.db_manager.get_collection("users")
            user = await users_collection.find_one({"_id": user_id}, {"username": 1})
            shared_by = user.get("username", "Unknown") if user else "Unknown"

            return {
                "resource_type": resource_type,
                "resource_data": sanitized_data,
                "shared_by": shared_by,
                "created_at": share["created_at"]
            }

        except IPAMError:
            raise
        except Exception as e:
            self.logger.error("Failed to get shared resource: %s", e, exc_info=True)
            raise IPAMError(f"Failed to get shared resource: {str(e)}")

    def _sanitize_shared_resource(self, resource_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize resource data for sharing (remove sensitive info).

        Args:
            resource_data: Resource data

        Returns:
            Sanitized resource data
        """
        # Remove sensitive fields
        sensitive_fields = ["user_id", "created_by", "updated_by", "owner", "comments", "notes"]
        sanitized = {k: v for k, v in resource_data.items() if k not in sensitive_fields}
        return sanitized

    async def list_user_shares(self, user_id: str) -> List[Dict[str, Any]]:
        """
        List user's active shares.

        Args:
            user_id: User ID

        Returns:
            List of shares
        """
        try:
            collection = self.db_manager.get_tenant_collection("ipam_shares")
            cursor = collection.find({"user_id": user_id, "is_active": True}).sort("created_at", -1)
            shares = await cursor.to_list(None)

            for share in shares:
                share["_id"] = str(share["_id"])
                share["share_url"] = f"/ipam/shares/{share['share_token']}"

            return shares

        except Exception as e:
            self.logger.error("Failed to list shares: %s", e, exc_info=True)
            raise IPAMError(f"Failed to list shares: {str(e)}")

    async def revoke_share(self, user_id: str, share_id: str) -> None:
        """
        Revoke (delete) a share.

        Args:
            user_id: User ID
            share_id: Share ID

        Raises:
            IPAMError: If share not found
        """
        try:
            collection = self.db_manager.get_tenant_collection("ipam_shares")
            result = await collection.update_one(
                {"_id": ObjectId(share_id), "user_id": user_id},
                {"$set": {"is_active": False}}
            )

            if result.modified_count == 0:
                raise IPAMError(f"Share not found: {share_id}")

            self.logger.info("Share revoked: user=%s share_id=%s", user_id, share_id)

        except IPAMError:
            raise
        except Exception as e:
            self.logger.error("Failed to revoke share: %s", e, exc_info=True)
            raise IPAMError(f"Failed to revoke share: {str(e)}")

    # ==================== IPAM Enhancements: Webhook System ====================

    async def create_webhook(
        self,
        user_id: str,
        webhook_url: str,
        events: List[str],
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a webhook.

        Args:
            user_id: User ID
            webhook_url: Webhook URL
            events: List of events to subscribe to
            description: Optional description

        Returns:
            Dict containing webhook details with secret key
        """
        try:
            import secrets
            
            # Generate secret key for HMAC
            secret_key = secrets.token_urlsafe(32)
            
            now = datetime.now(timezone.utc)
            
            webhook_doc = {
                "user_id": user_id,
                "webhook_url": webhook_url,
                "secret_key": secret_key,
                "events": events,
                "is_active": True,
                "failure_count": 0,
                "last_delivery": None,
                "description": description,
                "created_at": now,
                "updated_at": now
            }

            collection = self.db_manager.get_tenant_collection("ipam_webhooks")
            result = await collection.insert_one(webhook_doc)
            webhook_doc["_id"] = str(result.inserted_id)

            self.logger.info("Webhook created: user=%s url=%s events=%s", user_id, webhook_url, events)
            return webhook_doc

        except Exception as e:
            self.logger.error("Failed to create webhook: %s", e, exc_info=True)
            raise IPAMError(f"Failed to create webhook: {str(e)}")

    async def deliver_webhook(
        self,
        webhook_id: ObjectId,
        event_type: str,
        payload: Dict[str, Any]
    ) -> None:
        """
        Deliver webhook with retry logic (async, non-blocking).

        Args:
            webhook_id: Webhook ID
            event_type: Event type
            payload: Event payload
        """
        try:
            import hmac
            import hashlib
            import json
            import httpx
            
            collection = self.db_manager.get_tenant_collection("ipam_webhooks")
            webhook = await collection.find_one({"_id": webhook_id})

            if not webhook or not webhook["is_active"]:
                return

            # Generate HMAC signature
            payload_json = json.dumps(payload)
            signature = hmac.new(
                webhook["secret_key"].encode(),
                payload_json.encode(),
                hashlib.sha256
            ).hexdigest()

            headers = {
                "Content-Type": "application/json",
                "X-IPAM-Signature": f"sha256={signature}",
                "X-IPAM-Event": event_type
            }

            # Retry logic (3 attempts with exponential backoff)
            max_attempts = 3
            for attempt in range(1, max_attempts + 1):
                try:
                    start_time = time.time()
                    
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        response = await client.post(
                            webhook["webhook_url"],
                            json=payload,
                            headers=headers
                        )
                    
                    response_time_ms = int((time.time() - start_time) * 1000)

                    # Log delivery
                    deliveries_collection = self.db_manager.get_tenant_collection("ipam_webhook_deliveries")
                    await deliveries_collection.insert_one({
                        "webhook_id": webhook_id,
                        "event_type": event_type,
                        "payload": payload,
                        "status_code": response.status_code,
                        "response_time_ms": response_time_ms,
                        "error_message": None,
                        "attempt_number": attempt,
                        "delivered_at": datetime.now(timezone.utc)
                    })

                    if response.status_code < 500:
                        # Success or client error (don't retry)
                        await collection.update_one(
                            {"_id": webhook_id},
                            {"$set": {"last_delivery": datetime.now(timezone.utc), "failure_count": 0}}
                        )
                        return

                except Exception as e:
                    self.logger.error("Webhook delivery failed (attempt %d): %s", attempt, e)
                    
                    # Log failed delivery
                    deliveries_collection = self.db_manager.get_tenant_collection("ipam_webhook_deliveries")
                    await deliveries_collection.insert_one({
                        "webhook_id": webhook_id,
                        "event_type": event_type,
                        "payload": payload,
                        "status_code": None,
                        "response_time_ms": None,
                        "error_message": str(e),
                        "attempt_number": attempt,
                        "delivered_at": datetime.now(timezone.utc)
                    })

                # Exponential backoff
                if attempt < max_attempts:
                    await asyncio.sleep(2 ** attempt)

            # All attempts failed
            await collection.update_one(
                {"_id": webhook_id},
                {"$inc": {"failure_count": 1}}
            )

            # Disable webhook after 10 consecutive failures
            if webhook["failure_count"] >= 9:
                await collection.update_one(
                    {"_id": webhook_id},
                    {"$set": {"is_active": False}}
                )
                self.logger.warning("Webhook disabled after 10 failures: %s", webhook_id)

        except Exception as e:
            self.logger.error("Failed to deliver webhook: %s", e, exc_info=True)

    async def get_webhooks(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get user's webhooks.

        Args:
            user_id: User ID

        Returns:
            List of webhooks (without secret keys)
        """
        try:
            collection = self.db_manager.get_tenant_collection("ipam_webhooks")
            cursor = collection.find({"user_id": user_id}).sort("created_at", -1)
            webhooks = await cursor.to_list(None)

            for webhook in webhooks:
                webhook["_id"] = str(webhook["_id"])
                # Don't expose secret key in list
                webhook.pop("secret_key", None)

            return webhooks

        except Exception as e:
            self.logger.error("Failed to get webhooks: %s", e, exc_info=True)
            raise IPAMError(f"Failed to get webhooks: {str(e)}")

    async def delete_webhook(self, user_id: str, webhook_id: str) -> None:
        """
        Delete a webhook.

        Args:
            user_id: User ID
            webhook_id: Webhook ID

        Raises:
            IPAMError: If webhook not found
        """
        try:
            collection = self.db_manager.get_tenant_collection("ipam_webhooks")
            result = await collection.delete_one({"_id": ObjectId(webhook_id), "user_id": user_id})

            if result.deleted_count == 0:
                raise IPAMError(f"Webhook not found: {webhook_id}")

            self.logger.info("Webhook deleted: user=%s webhook_id=%s", user_id, webhook_id)

        except IPAMError:
            raise
        except Exception as e:
            self.logger.error("Failed to delete webhook: %s", e, exc_info=True)
            raise IPAMError(f"Failed to delete webhook: {str(e)}")

    async def get_webhook_deliveries(
        self,
        user_id: str,
        webhook_id: str,
        page: int = 1,
        page_size: int = 50
    ) -> Dict[str, Any]:
        """
        Get webhook delivery history.

        Args:
            user_id: User ID
            webhook_id: Webhook ID
            page: Page number
            page_size: Items per page

        Returns:
            Dict containing deliveries and pagination
        """
        try:
            # Verify webhook ownership
            webhooks_collection = self.db_manager.get_tenant_collection("ipam_webhooks")
            webhook = await webhooks_collection.find_one({"_id": ObjectId(webhook_id), "user_id": user_id})
            
            if not webhook:
                raise IPAMError(f"Webhook not found: {webhook_id}")

            # Get deliveries
            deliveries_collection = self.db_manager.get_tenant_collection("ipam_webhook_deliveries")
            query = {"webhook_id": ObjectId(webhook_id)}
            
            total_count = await deliveries_collection.count_documents(query)
            skip = (page - 1) * page_size
            total_pages = (total_count + page_size - 1) // page_size

            cursor = deliveries_collection.find(query).sort("delivered_at", -1).skip(skip).limit(page_size)
            deliveries = await cursor.to_list(page_size)

            for delivery in deliveries:
                delivery["_id"] = str(delivery["_id"])
                delivery["webhook_id"] = str(delivery["webhook_id"])

            return {
                "deliveries": deliveries,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total_count": total_count,
                    "total_pages": total_pages,
                    "has_next": page < total_pages,
                    "has_prev": page > 1,
                }
            }

        except IPAMError:
            raise
        except Exception as e:
            self.logger.error("Failed to get webhook deliveries: %s", e, exc_info=True)
            raise IPAMError(f"Failed to get webhook deliveries: {str(e)}")

    # ==================== IPAM Enhancements: Bulk Operations ====================

    async def bulk_update_tags(
        self,
        user_id: str,
        resource_type: str,
        resource_ids: List[str],
        operation: str,
        tags: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Bulk update tags on resources.

        Args:
            user_id: User ID
            resource_type: "region" or "host"
            resource_ids: List of resource IDs (max 500)
            operation: "add", "remove", or "replace"
            tags: Tags to add/remove/replace

        Returns:
            Dict containing operation results
        """
        try:
            import uuid
            
            # Validate
            if len(resource_ids) > 500:
                raise ValidationError("Maximum 500 resources per bulk operation", field="resource_ids")

            # For large operations (> 100), create async job
            if len(resource_ids) > 100:
                job_id = str(uuid.uuid4())
                
                job_doc = {
                    "job_id": job_id,
                    "user_id": user_id,
                    "operation_type": "bulk_tag_update",
                    "total_items": len(resource_ids),
                    "processed_items": 0,
                    "successful_items": 0,
                    "failed_items": 0,
                    "status": "pending",
                    "results": [],
                    "created_at": datetime.now(timezone.utc),
                    "completed_at": None
                }

                jobs_collection = self.db_manager.get_tenant_collection("ipam_bulk_jobs")
                await jobs_collection.insert_one(job_doc)

                # Process async (would be handled by background worker)
                # For now, return job ID
                return {
                    "job_id": job_id,
                    "status": "pending",
                    "total_items": len(resource_ids),
                    "message": "Bulk operation queued for processing"
                }

            # Process synchronously for small operations
            collection_name = "ipam_regions" if resource_type == "region" else "ipam_hosts"
            collection = self.db_manager.get_collection(collection_name)

            successful = 0
            failed = 0
            results = []

            for resource_id in resource_ids:
                try:
                    # Build update based on operation
                    if operation == "add":
                        update_doc = {"$set": {f"tags.{k}": v for k, v in tags.items()}}
                    elif operation == "remove":
                        update_doc = {"$unset": {f"tags.{k}": "" for k in tags.keys()}}
                    elif operation == "replace":
                        update_doc = {"$set": {"tags": tags}}
                    else:
                        raise ValidationError("Invalid operation", field="operation", value=operation)

                    result = await collection.update_one(
                        {"_id": ObjectId(resource_id), "user_id": user_id},
                        update_doc
                    )

                    if result.modified_count > 0:
                        successful += 1
                        results.append({"resource_id": resource_id, "status": "success"})
                    else:
                        failed += 1
                        results.append({"resource_id": resource_id, "status": "failed", "reason": "Not found or no changes"})

                except Exception as e:
                    failed += 1
                    results.append({"resource_id": resource_id, "status": "failed", "reason": str(e)})

            return {
                "total_requested": len(resource_ids),
                "successful": successful,
                "failed": failed,
                "results": results
            }

        except ValidationError:
            raise
        except Exception as e:
            self.logger.error("Failed bulk tag update: %s", e, exc_info=True)
            raise IPAMError(f"Failed bulk tag update: {str(e)}")

    async def get_bulk_job_status(self, user_id: str, job_id: str) -> Dict[str, Any]:
        """
        Get bulk job status.

        Args:
            user_id: User ID
            job_id: Job ID

        Returns:
            Dict containing job status

        Raises:
            IPAMError: If job not found
        """
        try:
            collection = self.db_manager.get_tenant_collection("ipam_bulk_jobs")
            job = await collection.find_one({"job_id": job_id, "user_id": user_id})

            if not job:
                raise IPAMError(f"Job not found: {job_id}")

            job["_id"] = str(job["_id"])
            
            # Calculate progress
            if job["total_items"] > 0:
                job["progress_percent"] = (job["processed_items"] / job["total_items"]) * 100
            else:
                job["progress_percent"] = 0.0

            return job

        except IPAMError:
            raise
        except Exception as e:
            self.logger.error("Failed to get bulk job status: %s", e, exc_info=True)
            raise IPAMError(f"Failed to get bulk job status: {str(e)}")

    async def get_top_countries_by_utilization(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get top countries ranked by utilization percentage.

        Args:
            user_id: User ID for ownership filtering
            limit: Maximum number of countries to return

        Returns:
            List of countries with utilization metrics
        """
        try:
            # Get all regions for the user (using pagination with large page size)
            regions_result = await self.get_regions(user_id, page=1, page_size=100)
            regions = regions_result.get("regions", [])
            
            # Group by country and calculate utilization
            country_stats = {}
            for region in regions:
                country = region.get("country")
                if not country:
                    continue
                    
                if country not in country_stats:
                    country_stats[country] = {
                        "country": country,
                        "continent": region.get("continent", "Unknown"),
                        "total_regions": 0,
                        "allocated_hosts": 0,
                        "total_capacity": 0
                    }
                
                country_stats[country]["total_regions"] += 1
                country_stats[country]["allocated_hosts"] += region.get("allocated_hosts", 0)
                country_stats[country]["total_capacity"] += region.get("total_capacity", 0)
            
            # Calculate utilization percentage
            result = []
            for country_data in country_stats.values():
                if country_data["total_capacity"] > 0:
                    utilization = (country_data["allocated_hosts"] / country_data["total_capacity"]) * 100
                else:
                    utilization = 0.0
                    
                country_data["utilization_percentage"] = round(utilization, 2)
                result.append(country_data)
            
            # Sort by utilization and limit
            result.sort(key=lambda x: x["utilization_percentage"], reverse=True)
            return result[:limit]
            
        except Exception as e:
            self.logger.error("Failed to get top countries by utilization: %s", e, exc_info=True)
            raise IPAMError(f"Failed to get top countries: {str(e)}")

    async def get_recent_activity(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent allocation and modification activity from audit logs.

        Args:
            user_id: User ID for ownership filtering
            limit: Maximum number of activities to return

        Returns:
            List of recent activities
        """
        try:
            # Get recent audit entries
            audit_collection = self.db_manager.get_tenant_collection("ipam_audit")
            
            cursor = audit_collection.find(
                {"user_id": user_id},
                {
                    "timestamp": 1,
                    "action": 1,
                    "resource_type": 1,
                    "resource_id": 1,
                    "resource_name": 1,
                    "user_id": 1,
                    "details": 1
                }
            ).sort("timestamp", -1).limit(limit)
            
            activities = await cursor.to_list(length=limit)
            
            # Format activities
            result = []
            for activity in activities:
                result.append({
                    "timestamp": activity.get("timestamp").isoformat() if activity.get("timestamp") else None,
                    "action": activity.get("action"),
                    "resource_type": activity.get("resource_type"),
                    "resource_id": str(activity.get("resource_id", "")),
                    "resource_name": activity.get("resource_name"),
                    "user_id": activity.get("user_id"),
                    "details": activity.get("details", {})
                })
            
            return result
            
        except Exception as e:
            self.logger.error("Failed to get recent activity: %s", e, exc_info=True)
            raise IPAMError(f"Failed to get recent activity: {str(e)}")


# Global instance
ipam_manager = IPAMManager()
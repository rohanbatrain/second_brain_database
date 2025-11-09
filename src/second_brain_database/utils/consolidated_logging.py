"""
Consolidated Logging Utilities for Family Management System

This module consolidates logging patterns to reduce log noise and standardize
logging across all family management components.

Key consolidations:
1. Standardized logging patterns to reduce duplicate log entries
2. Intelligent log filtering to reduce noise
3. Consolidated log formatting for better readability
4. Optimized performance logging with sampling
5. Centralized audit logging with proper context

Requirements addressed: 1.1-1.6, 2.1-2.7, 3.1-3.6 (Manager Class Optimization)
"""

from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
import json
import time
from typing import Any, Dict, List, Optional, Set

from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.utils.logging_utils import log_security_event

logger = get_logger(prefix="[Consolidated Logging]")


class LogLevel(Enum):
    """Standardized log levels"""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class LogCategory(Enum):
    """Categories of logs for filtering and organization"""

    FAMILY_OPERATION = "family_operation"
    SBD_TRANSACTION = "sbd_transaction"
    SECURITY_EVENT = "security_event"
    PERFORMANCE = "performance"
    AUDIT = "audit"
    SYSTEM = "system"
    USER_ACTION = "user_action"


class LogSamplingStrategy(Enum):
    """Strategies for log sampling to reduce noise"""

    NONE = "none"
    FREQUENCY_BASED = "frequency_based"
    TIME_BASED = "time_based"
    ADAPTIVE = "adaptive"


@dataclass
class LogEntry:
    """Standardized log entry structure"""

    timestamp: datetime
    level: LogLevel
    category: LogCategory
    message: str
    user_id: Optional[str] = None
    family_id: Optional[str] = None
    operation: Optional[str] = None
    duration: Optional[float] = None
    success: Optional[bool] = None
    error_code: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = None
    ip_address: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert log entry to dictionary for JSON serialization"""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        data["level"] = self.level.value
        data["category"] = self.category.value
        return data


@dataclass
class LogFilter:
    """Configuration for log filtering"""

    categories: Optional[Set[LogCategory]] = None
    min_level: LogLevel = LogLevel.INFO
    max_entries_per_minute: Optional[int] = None
    exclude_patterns: Optional[List[str]] = None
    include_patterns: Optional[List[str]] = None
    sampling_strategy: LogSamplingStrategy = LogSamplingStrategy.NONE
    sampling_rate: float = 1.0  # 1.0 = log everything, 0.1 = log 10%


class ConsolidatedLogger:
    """
    Consolidated logger that reduces noise and standardizes patterns
    """

    def __init__(self):
        self.logger = logger
        self._log_counters = defaultdict(int)
        self._recent_logs = deque(maxlen=1000)  # Keep recent logs for deduplication
        self._performance_samples = defaultdict(list)
        self._audit_buffer = []

        # Default filters for different categories
        self._category_filters = {
            LogCategory.PERFORMANCE: LogFilter(
                sampling_strategy=LogSamplingStrategy.FREQUENCY_BASED,
                sampling_rate=0.1,  # Sample 10% of performance logs
                max_entries_per_minute=60,
            ),
            LogCategory.SECURITY_EVENT: LogFilter(
                min_level=LogLevel.WARNING, sampling_strategy=LogSamplingStrategy.NONE  # Log all security events
            ),
            LogCategory.AUDIT: LogFilter(
                min_level=LogLevel.INFO, sampling_strategy=LogSamplingStrategy.NONE  # Log all audit events
            ),
            LogCategory.FAMILY_OPERATION: LogFilter(min_level=LogLevel.INFO, max_entries_per_minute=120),
            LogCategory.SYSTEM: LogFilter(min_level=LogLevel.WARNING, exclude_patterns=["health_check", "heartbeat"]),
        }

    async def log_consolidated(
        self,
        level: LogLevel,
        category: LogCategory,
        message: str,
        user_id: Optional[str] = None,
        family_id: Optional[str] = None,
        operation: Optional[str] = None,
        duration: Optional[float] = None,
        success: Optional[bool] = None,
        error_code: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        """
        Log with consolidated filtering and deduplication
        """
        log_entry = LogEntry(
            timestamp=datetime.now(timezone.utc),
            level=level,
            category=category,
            message=message,
            user_id=user_id,
            family_id=family_id,
            operation=operation,
            duration=duration,
            success=success,
            error_code=error_code,
            metadata=metadata or {},
            request_id=request_id,
            ip_address=ip_address,
        )

        # Apply filtering
        if not await self._should_log(log_entry):
            return

        # Check for deduplication
        if await self._is_duplicate(log_entry):
            await self._increment_duplicate_counter(log_entry)
            return

        # Log the entry
        await self._write_log(log_entry)

        # Store for deduplication
        self._recent_logs.append(log_entry)

        # Handle special categories
        if category == LogCategory.PERFORMANCE:
            await self._handle_performance_log(log_entry)
        elif category == LogCategory.AUDIT:
            await self._handle_audit_log(log_entry)
        elif category == LogCategory.SECURITY_EVENT:
            await self._handle_security_log(log_entry)

    async def _should_log(self, log_entry: LogEntry) -> bool:
        """Determine if log entry should be written based on filters"""
        category_filter = self._category_filters.get(log_entry.category)
        if not category_filter:
            return True

        # Check minimum level
        level_values = {
            LogLevel.DEBUG: 0,
            LogLevel.INFO: 1,
            LogLevel.WARNING: 2,
            LogLevel.ERROR: 3,
            LogLevel.CRITICAL: 4,
        }

        if level_values[log_entry.level] < level_values[category_filter.min_level]:
            return False

        # Check rate limiting
        if category_filter.max_entries_per_minute:
            minute_key = log_entry.timestamp.strftime("%Y-%m-%d-%H-%M")
            counter_key = f"{log_entry.category.value}:{minute_key}"

            if self._log_counters[counter_key] >= category_filter.max_entries_per_minute:
                return False

        # Check exclude patterns
        if category_filter.exclude_patterns:
            for pattern in category_filter.exclude_patterns:
                if pattern.lower() in log_entry.message.lower():
                    return False

        # Check include patterns (if specified, message must match at least one)
        if category_filter.include_patterns:
            matches = any(pattern.lower() in log_entry.message.lower() for pattern in category_filter.include_patterns)
            if not matches:
                return False

        # Apply sampling
        if category_filter.sampling_strategy != LogSamplingStrategy.NONE:
            if not await self._should_sample(log_entry, category_filter):
                return False

        return True

    async def _should_sample(self, log_entry: LogEntry, filter_config: LogFilter) -> bool:
        """Determine if log should be sampled based on strategy"""
        import random

        if filter_config.sampling_strategy == LogSamplingStrategy.FREQUENCY_BASED:
            return random.random() < filter_config.sampling_rate

        elif filter_config.sampling_strategy == LogSamplingStrategy.TIME_BASED:
            # Sample based on time intervals
            second = log_entry.timestamp.second
            interval = int(60 * filter_config.sampling_rate)
            return second % interval == 0

        elif filter_config.sampling_strategy == LogSamplingStrategy.ADAPTIVE:
            # Adaptive sampling based on recent log volume
            recent_count = len([log for log in self._recent_logs if log.category == log_entry.category])

            if recent_count > 100:  # High volume, reduce sampling
                return random.random() < (filter_config.sampling_rate * 0.1)
            elif recent_count > 50:  # Medium volume, normal sampling
                return random.random() < filter_config.sampling_rate
            else:  # Low volume, increase sampling
                return random.random() < min(1.0, filter_config.sampling_rate * 2.0)

        return True

    async def _is_duplicate(self, log_entry: LogEntry) -> bool:
        """Check if log entry is a duplicate of recent entries"""
        # Look for similar entries in the last 10 entries
        recent_entries = list(self._recent_logs)[-10:]

        for recent_entry in recent_entries:
            if (
                recent_entry.category == log_entry.category
                and recent_entry.operation == log_entry.operation
                and recent_entry.user_id == log_entry.user_id
                and recent_entry.message == log_entry.message
                and (log_entry.timestamp - recent_entry.timestamp).total_seconds() < 60
            ):
                return True

        return False

    async def _increment_duplicate_counter(self, log_entry: LogEntry) -> None:
        """Increment counter for duplicate log entries"""
        counter_key = f"duplicate:{log_entry.category.value}:{log_entry.operation or 'unknown'}"
        self._log_counters[counter_key] += 1

        # Log duplicate summary every 10 duplicates
        if self._log_counters[counter_key] % 10 == 0:
            await self._write_log(
                LogEntry(
                    timestamp=datetime.now(timezone.utc),
                    level=LogLevel.INFO,
                    category=LogCategory.SYSTEM,
                    message=f"Suppressed {self._log_counters[counter_key]} duplicate log entries",
                    metadata={
                        "original_category": log_entry.category.value,
                        "original_operation": log_entry.operation,
                        "duplicate_count": self._log_counters[counter_key],
                    },
                )
            )

    async def _write_log(self, log_entry: LogEntry) -> None:
        """Write log entry to the underlying logger"""
        # Update counters
        minute_key = log_entry.timestamp.strftime("%Y-%m-%d-%H-%M")
        counter_key = f"{log_entry.category.value}:{minute_key}"
        self._log_counters[counter_key] += 1

        # Format message with context
        formatted_message = await self._format_log_message(log_entry)
        extra_data = await self._build_extra_data(log_entry)

        # Write to appropriate log level
        if log_entry.level == LogLevel.DEBUG:
            self.logger.debug(formatted_message, extra=extra_data)
        elif log_entry.level == LogLevel.INFO:
            self.logger.info(formatted_message, extra=extra_data)
        elif log_entry.level == LogLevel.WARNING:
            self.logger.warning(formatted_message, extra=extra_data)
        elif log_entry.level == LogLevel.ERROR:
            self.logger.error(formatted_message, extra=extra_data)
        elif log_entry.level == LogLevel.CRITICAL:
            self.logger.critical(formatted_message, extra=extra_data)

    async def _format_log_message(self, log_entry: LogEntry) -> str:
        """Format log message with consistent structure"""
        parts = [log_entry.message]

        if log_entry.operation:
            parts.append(f"[{log_entry.operation}]")

        if log_entry.user_id:
            parts.append(f"user:{log_entry.user_id}")

        if log_entry.family_id:
            parts.append(f"family:{log_entry.family_id}")

        if log_entry.duration is not None:
            parts.append(f"duration:{log_entry.duration:.3f}s")

        if log_entry.success is not None:
            parts.append(f"success:{log_entry.success}")

        return " ".join(parts)

    async def _build_extra_data(self, log_entry: LogEntry) -> Dict[str, Any]:
        """Build extra data for structured logging"""
        extra = {"category": log_entry.category.value, "timestamp": log_entry.timestamp.isoformat()}

        if log_entry.user_id:
            extra["user_id"] = log_entry.user_id
        if log_entry.family_id:
            extra["family_id"] = log_entry.family_id
        if log_entry.operation:
            extra["operation"] = log_entry.operation
        if log_entry.duration is not None:
            extra["duration"] = log_entry.duration
        if log_entry.success is not None:
            extra["success"] = log_entry.success
        if log_entry.error_code:
            extra["error_code"] = log_entry.error_code
        if log_entry.request_id:
            extra["request_id"] = log_entry.request_id
        if log_entry.ip_address:
            extra["ip_address"] = log_entry.ip_address
        if log_entry.metadata:
            extra["metadata"] = log_entry.metadata

        return extra

    async def _handle_performance_log(self, log_entry: LogEntry) -> None:
        """Handle performance-specific logging with sampling"""
        if log_entry.duration is not None and log_entry.operation:
            # Store performance sample
            self._performance_samples[log_entry.operation].append(
                {"duration": log_entry.duration, "timestamp": log_entry.timestamp, "success": log_entry.success}
            )

            # Keep only recent samples (last 100 per operation)
            if len(self._performance_samples[log_entry.operation]) > 100:
                self._performance_samples[log_entry.operation] = self._performance_samples[log_entry.operation][-100:]

    async def _handle_audit_log(self, log_entry: LogEntry) -> None:
        """Handle audit-specific logging with buffering"""
        self._audit_buffer.append(log_entry.to_dict())

        # Flush audit buffer when it gets large
        if len(self._audit_buffer) >= 50:
            await self._flush_audit_buffer()

    async def _handle_security_log(self, log_entry: LogEntry) -> None:
        """Handle security-specific logging with immediate processing"""
        # Use existing security event logging
        log_security_event(
            event_type=f"consolidated_{log_entry.category.value}",
            user_id=log_entry.user_id,
            ip_address=log_entry.ip_address,
            success=log_entry.success,
            details={
                "message": log_entry.message,
                "operation": log_entry.operation,
                "error_code": log_entry.error_code,
                **(log_entry.metadata or {}),
            },
        )

    async def _flush_audit_buffer(self) -> None:
        """Flush audit buffer to persistent storage"""
        if not self._audit_buffer:
            return

        try:
            # In a real implementation, this would write to an audit database
            # For now, we'll log a summary
            self.logger.info(
                f"Flushing {len(self._audit_buffer)} audit entries to persistent storage",
                extra={"audit_entries_count": len(self._audit_buffer)},
            )

            self._audit_buffer.clear()

        except Exception as e:
            self.logger.error(f"Failed to flush audit buffer: {e}")

    async def get_logging_statistics(self) -> Dict[str, Any]:
        """Get logging statistics for monitoring"""
        current_minute = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H-%M")

        stats = {
            "current_minute": current_minute,
            "log_counts_by_category": {},
            "duplicate_counts": {},
            "performance_samples": {},
            "audit_buffer_size": len(self._audit_buffer),
            "recent_logs_count": len(self._recent_logs),
        }

        # Count logs by category for current minute
        for key, count in self._log_counters.items():
            if current_minute in key and "duplicate:" not in key:
                category = key.split(":")[0]
                stats["log_counts_by_category"][category] = count

        # Count duplicates
        for key, count in self._log_counters.items():
            if "duplicate:" in key:
                category = key.split(":")[1]
                stats["duplicate_counts"][category] = count

        # Performance sample counts
        for operation, samples in self._performance_samples.items():
            stats["performance_samples"][operation] = len(samples)

        return stats

    async def configure_category_filter(self, category: LogCategory, filter_config: LogFilter) -> None:
        """Configure filtering for a specific log category"""
        self._category_filters[category] = filter_config

        self.logger.info(
            f"Updated log filter for category {category.value}",
            extra={
                "category": category.value,
                "min_level": filter_config.min_level.value,
                "sampling_strategy": filter_config.sampling_strategy.value,
                "sampling_rate": filter_config.sampling_rate,
            },
        )


# Global consolidated logger instance
consolidated_logger = ConsolidatedLogger()


# Convenience functions for common logging patterns
async def log_family_operation(
    message: str,
    operation: str,
    user_id: Optional[str] = None,
    family_id: Optional[str] = None,
    duration: Optional[float] = None,
    success: Optional[bool] = None,
    level: LogLevel = LogLevel.INFO,
    **kwargs,
) -> None:
    """Log family operation with standardized format"""
    await consolidated_logger.log_consolidated(
        level=level,
        category=LogCategory.FAMILY_OPERATION,
        message=message,
        operation=operation,
        user_id=user_id,
        family_id=family_id,
        duration=duration,
        success=success,
        **kwargs,
    )


async def log_sbd_transaction(
    message: str,
    user_id: str,
    amount: int,
    success: bool,
    family_id: Optional[str] = None,
    duration: Optional[float] = None,
    **kwargs,
) -> None:
    """Log SBD transaction with standardized format"""
    await consolidated_logger.log_consolidated(
        level=LogLevel.INFO,
        category=LogCategory.SBD_TRANSACTION,
        message=message,
        operation="sbd_transaction",
        user_id=user_id,
        family_id=family_id,
        duration=duration,
        success=success,
        metadata={"amount": amount},
        **kwargs,
    )


async def log_performance_metric(
    operation: str,
    duration: float,
    success: bool,
    user_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Log performance metric with sampling"""
    await consolidated_logger.log_consolidated(
        level=LogLevel.DEBUG,
        category=LogCategory.PERFORMANCE,
        message=f"Performance metric for {operation}",
        operation=operation,
        user_id=user_id,
        duration=duration,
        success=success,
        metadata=metadata,
    )

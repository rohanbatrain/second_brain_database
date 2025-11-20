"""
Centralized datetime utilities for timezone-aware datetime handling.

This module provides timezone-aware datetime functions to replace deprecated
datetime.utcnow() usage throughout the application.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional


class DateTimeUtils:
    """Centralized datetime utilities with timezone awareness."""

    @staticmethod
    def utc_now() -> datetime:
        """
        Get current UTC datetime with timezone awareness.

        Replaces deprecated datetime.utcnow() with timezone-aware equivalent.

        Returns:
            datetime: Current UTC datetime with timezone information
        """
        return datetime.now(timezone.utc)

    @staticmethod
    def utc_timestamp() -> float:
        """
        Get current UTC timestamp.

        Returns:
            float: Current UTC timestamp as seconds since epoch
        """
        return DateTimeUtils.utc_now().timestamp()

    @staticmethod
    def format_iso(dt: datetime) -> str:
        """
        Format datetime as ISO string.

        Args:
            dt: Datetime object to format

        Returns:
            str: ISO formatted datetime string
        """
        return dt.isoformat()

    @staticmethod
    def from_timestamp(timestamp: float) -> datetime:
        """
        Create timezone-aware datetime from timestamp.

        Args:
            timestamp: Unix timestamp

        Returns:
            datetime: Timezone-aware datetime object
        """
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)

    @staticmethod
    def add_timedelta(dt: datetime, **kwargs) -> datetime:
        """
        Add timedelta to datetime while preserving timezone.

        Args:
            dt: Base datetime
            **kwargs: Arguments for timedelta (days, hours, minutes, seconds, etc.)

        Returns:
            datetime: New datetime with timedelta added
        """
        return dt + timedelta(**kwargs)

    @staticmethod
    def ensure_timezone_aware(dt: datetime, default_tz: Optional[timezone] = None) -> datetime:
        """
        Ensure datetime is timezone-aware.

        Args:
            dt: Datetime object to check
            default_tz: Default timezone to use if datetime is naive (defaults to UTC)

        Returns:
            datetime: Timezone-aware datetime object
        """
        if dt.tzinfo is None:
            if default_tz is None:
                default_tz = timezone.utc
            return dt.replace(tzinfo=default_tz)
        return dt

    @staticmethod
    def is_expired(expires_at: datetime, buffer_seconds: int = 0) -> bool:
        """
        Check if a datetime has expired.

        Args:
            expires_at: Expiration datetime
            buffer_seconds: Optional buffer in seconds to consider as expired early

        Returns:
            bool: True if expired, False otherwise
        """
        now = DateTimeUtils.utc_now()
        if buffer_seconds > 0:
            now = DateTimeUtils.add_timedelta(now, seconds=buffer_seconds)

        # Ensure both datetimes are timezone-aware for comparison
        expires_at = DateTimeUtils.ensure_timezone_aware(expires_at)
        return now >= expires_at


# Convenience functions for backward compatibility and ease of use
def utc_now() -> datetime:
    """Get current UTC datetime with timezone awareness."""
    return DateTimeUtils.utc_now()


def utc_timestamp() -> float:
    """Get current UTC timestamp."""
    return DateTimeUtils.utc_timestamp()


def format_iso(dt: datetime) -> str:
    """Format datetime as ISO string."""
    return DateTimeUtils.format_iso(dt)


def from_timestamp(timestamp: float) -> datetime:
    """Create timezone-aware datetime from timestamp."""
    return DateTimeUtils.from_timestamp(timestamp)


def add_timedelta(dt: datetime, **kwargs) -> datetime:
    """Add timedelta to datetime while preserving timezone."""
    return DateTimeUtils.add_timedelta(dt, **kwargs)


def ensure_timezone_aware(dt: datetime, default_tz: Optional[timezone] = None) -> datetime:
    """Ensure datetime is timezone-aware."""
    return DateTimeUtils.ensure_timezone_aware(dt, default_tz)


def is_expired(expires_at: datetime, buffer_seconds: int = 0) -> bool:
    """Check if a datetime has expired."""
    return DateTimeUtils.is_expired(expires_at, buffer_seconds)

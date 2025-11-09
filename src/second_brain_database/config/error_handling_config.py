"""
Error Handling and Resilience Configuration.

This module provides configuration settings for the enterprise error handling,
recovery, and resilience systems. It includes settings for circuit breakers,
bulkheads, retry strategies, monitoring thresholds, and alerting parameters.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List

from second_brain_database.config import settings


class CircuitBreakerProfile(Enum):
    """Predefined circuit breaker profiles for different service types."""

    CONSERVATIVE = "conservative"  # Low failure threshold, long recovery time
    BALANCED = "balanced"  # Moderate settings for most services
    AGGRESSIVE = "aggressive"  # High failure threshold, quick recovery


class RetryProfile(Enum):
    """Predefined retry profiles for different operation types."""

    QUICK = "quick"  # Few attempts, short delays
    STANDARD = "standard"  # Moderate attempts and delays
    PERSISTENT = "persistent"  # Many attempts, longer delays
    CRITICAL = "critical"  # Maximum attempts for critical operations


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breakers."""

    failure_threshold: int
    recovery_timeout: int  # seconds
    expected_exception: str = "Exception"
    profile: CircuitBreakerProfile = CircuitBreakerProfile.BALANCED


@dataclass
class BulkheadConfig:
    """Configuration for bulkhead semaphores."""

    capacity: int
    timeout: float = 5.0  # seconds


@dataclass
class RetryConfig:
    """Configuration for retry mechanisms."""

    max_attempts: int
    initial_delay: float  # seconds
    backoff_factor: float
    max_delay: float  # seconds
    strategy: str = "exponential_backoff"
    retryable_exceptions: List[str] = None
    non_retryable_exceptions: List[str] = None
    profile: RetryProfile = RetryProfile.STANDARD


@dataclass
class MonitoringConfig:
    """Configuration for error monitoring and alerting."""

    error_window_size: int = 100
    time_window_minutes: int = 15
    error_rate_threshold: float = 0.05  # 5%
    critical_error_rate_threshold: float = 0.10  # 10%
    anomaly_detection_threshold: float = 2.0  # standard deviations
    alert_cooldown_minutes: int = 30
    escalation_delay_minutes: int = 60


class ErrorHandlingConfig:
    """
    Centralized configuration for error handling and resilience systems.

    This class provides configuration for all error handling components
    including circuit breakers, bulkheads, retry mechanisms, and monitoring.
    """

    def __init__(self):
        self.monitoring = MonitoringConfig()
        self._load_from_settings()

    def _load_from_settings(self):
        """Load configuration from application settings."""
        # Override defaults with settings if available
        if hasattr(settings, "ERROR_HANDLING_CONFIG"):
            config = settings.ERROR_HANDLING_CONFIG

            # Update monitoring config
            if "monitoring" in config:
                mon_config = config["monitoring"]
                self.monitoring.error_window_size = mon_config.get(
                    "error_window_size", self.monitoring.error_window_size
                )
                self.monitoring.time_window_minutes = mon_config.get(
                    "time_window_minutes", self.monitoring.time_window_minutes
                )
                self.monitoring.error_rate_threshold = mon_config.get(
                    "error_rate_threshold", self.monitoring.error_rate_threshold
                )
                self.monitoring.critical_error_rate_threshold = mon_config.get(
                    "critical_error_rate_threshold", self.monitoring.critical_error_rate_threshold
                )
                self.monitoring.anomaly_detection_threshold = mon_config.get(
                    "anomaly_detection_threshold", self.monitoring.anomaly_detection_threshold
                )
                self.monitoring.alert_cooldown_minutes = mon_config.get(
                    "alert_cooldown_minutes", self.monitoring.alert_cooldown_minutes
                )
                self.monitoring.escalation_delay_minutes = mon_config.get(
                    "escalation_delay_minutes", self.monitoring.escalation_delay_minutes
                )

    def get_circuit_breaker_config(self, service_name: str) -> CircuitBreakerConfig:
        """Get circuit breaker configuration for a specific service."""
        # Predefined configurations for different services
        service_configs = {
            "database": CircuitBreakerConfig(
                failure_threshold=5,
                recovery_timeout=60,
                expected_exception="PyMongoError",
                profile=CircuitBreakerProfile.CONSERVATIVE,
            ),
            "redis": CircuitBreakerConfig(
                failure_threshold=3,
                recovery_timeout=30,
                expected_exception="ConnectionError",
                profile=CircuitBreakerProfile.BALANCED,
            ),
            "email": CircuitBreakerConfig(
                failure_threshold=10,
                recovery_timeout=120,
                expected_exception="EmailError",
                profile=CircuitBreakerProfile.AGGRESSIVE,
            ),
            "family_operations": CircuitBreakerConfig(
                failure_threshold=5,
                recovery_timeout=45,
                expected_exception="FamilyError",
                profile=CircuitBreakerProfile.BALANCED,
            ),
            "sbd_operations": CircuitBreakerConfig(
                failure_threshold=3,
                recovery_timeout=30,
                expected_exception="SBDError",
                profile=CircuitBreakerProfile.CONSERVATIVE,
            ),
            "external_api": CircuitBreakerConfig(
                failure_threshold=8,
                recovery_timeout=90,
                expected_exception="HTTPError",
                profile=CircuitBreakerProfile.AGGRESSIVE,
            ),
        }

        # Return specific config or default
        return service_configs.get(
            service_name,
            CircuitBreakerConfig(failure_threshold=5, recovery_timeout=60, profile=CircuitBreakerProfile.BALANCED),
        )

    def get_bulkhead_config(self, resource_name: str) -> BulkheadConfig:
        """Get bulkhead configuration for a specific resource."""
        # Predefined configurations for different resources
        resource_configs = {
            "database_connections": BulkheadConfig(capacity=20, timeout=10.0),
            "redis_connections": BulkheadConfig(capacity=15, timeout=5.0),
            "email_sending": BulkheadConfig(capacity=10, timeout=30.0),
            "family_creation": BulkheadConfig(capacity=5, timeout=15.0),
            "family_invitations": BulkheadConfig(capacity=10, timeout=10.0),
            "sbd_transactions": BulkheadConfig(capacity=8, timeout=20.0),
            "file_uploads": BulkheadConfig(capacity=3, timeout=60.0),
            "external_api_calls": BulkheadConfig(capacity=12, timeout=30.0),
        }

        # Return specific config or default
        return resource_configs.get(resource_name, BulkheadConfig(capacity=10, timeout=5.0))

    def get_retry_config(self, operation_type: str) -> RetryConfig:
        """Get retry configuration for a specific operation type."""
        # Predefined configurations for different operation types
        operation_configs = {
            "database_query": RetryConfig(
                max_attempts=3,
                initial_delay=1.0,
                backoff_factor=2.0,
                max_delay=30.0,
                strategy="exponential_backoff",
                retryable_exceptions=["PyMongoError", "ConnectionError", "TimeoutError"],
                non_retryable_exceptions=["ValidationError", "AuthenticationError"],
                profile=RetryProfile.STANDARD,
            ),
            "redis_operation": RetryConfig(
                max_attempts=3,
                initial_delay=0.5,
                backoff_factor=1.5,
                max_delay=10.0,
                strategy="exponential_backoff",
                retryable_exceptions=["ConnectionError", "TimeoutError"],
                non_retryable_exceptions=["ValidationError"],
                profile=RetryProfile.QUICK,
            ),
            "email_sending": RetryConfig(
                max_attempts=5,
                initial_delay=2.0,
                backoff_factor=2.0,
                max_delay=120.0,
                strategy="exponential_backoff",
                retryable_exceptions=["SMTPException", "ConnectionError"],
                non_retryable_exceptions=["ValidationError", "AuthenticationError"],
                profile=RetryProfile.PERSISTENT,
            ),
            "family_operation": RetryConfig(
                max_attempts=3,
                initial_delay=1.0,
                backoff_factor=2.0,
                max_delay=30.0,
                strategy="exponential_backoff",
                retryable_exceptions=["PyMongoError", "ConnectionError"],
                non_retryable_exceptions=["FamilyLimitExceeded", "ValidationError", "RateLimitExceeded"],
                profile=RetryProfile.STANDARD,
            ),
            "sbd_transaction": RetryConfig(
                max_attempts=2,
                initial_delay=1.0,
                backoff_factor=2.0,
                max_delay=10.0,
                strategy="exponential_backoff",
                retryable_exceptions=["ConnectionError", "TimeoutError"],
                non_retryable_exceptions=["InsufficientFundsError", "ValidationError"],
                profile=RetryProfile.QUICK,
            ),
            "external_api_call": RetryConfig(
                max_attempts=4,
                initial_delay=1.0,
                backoff_factor=2.0,
                max_delay=60.0,
                strategy="exponential_backoff",
                retryable_exceptions=["HTTPError", "ConnectionError", "TimeoutError"],
                non_retryable_exceptions=["AuthenticationError", "ValidationError"],
                profile=RetryProfile.STANDARD,
            ),
            "critical_operation": RetryConfig(
                max_attempts=5,
                initial_delay=2.0,
                backoff_factor=1.8,
                max_delay=180.0,
                strategy="exponential_backoff",
                retryable_exceptions=["Exception"],  # Retry most exceptions for critical ops
                non_retryable_exceptions=["ValidationError", "AuthenticationError"],
                profile=RetryProfile.CRITICAL,
            ),
        }

        # Return specific config or default
        return operation_configs.get(
            operation_type,
            RetryConfig(
                max_attempts=3,
                initial_delay=1.0,
                backoff_factor=2.0,
                max_delay=30.0,
                strategy="exponential_backoff",
                profile=RetryProfile.STANDARD,
            ),
        )

    def get_timeout_config(self, operation_type: str) -> float:
        """Get timeout configuration for a specific operation type."""
        # Predefined timeouts for different operation types (in seconds)
        timeout_configs = {
            "database_query": 30.0,
            "database_transaction": 60.0,
            "redis_operation": 5.0,
            "email_sending": 120.0,
            "family_creation": 45.0,
            "family_invitation": 30.0,
            "sbd_transaction": 20.0,
            "file_upload": 300.0,  # 5 minutes
            "external_api_call": 60.0,
            "health_check": 10.0,
            "user_authentication": 15.0,
            "password_reset": 30.0,
            "backup_operation": 600.0,  # 10 minutes
            "maintenance_task": 1800.0,  # 30 minutes
        }

        # Return specific timeout or default
        return timeout_configs.get(operation_type, 30.0)

    def get_fallback_config(self, operation_type: str) -> Dict[str, Any]:
        """Get fallback configuration for graceful degradation."""
        # Predefined fallback configurations
        fallback_configs = {
            "family_creation": {
                "enabled": True,
                "fallback_message": "Family creation is temporarily unavailable. Please try again later.",
                "degraded_features": ["sbd_account_creation", "email_notifications"],
                "available_features": ["basic_family_info"],
            },
            "family_invitations": {
                "enabled": True,
                "fallback_message": "Family invitations are temporarily unavailable. Please try again later.",
                "degraded_features": ["email_sending", "real_time_notifications"],
                "available_features": ["invitation_queuing"],
            },
            "sbd_transactions": {
                "enabled": True,
                "fallback_message": "SBD transactions are temporarily unavailable. Please try again later.",
                "degraded_features": ["real_time_processing", "transaction_notifications"],
                "available_features": ["balance_viewing", "transaction_queuing"],
            },
            "email_service": {
                "enabled": True,
                "fallback_message": "Email service is temporarily unavailable. Emails will be queued for later delivery.",
                "degraded_features": ["immediate_delivery"],
                "available_features": ["email_queuing", "local_notifications"],
            },
            "user_authentication": {
                "enabled": False,  # Critical service, no fallback
                "fallback_message": "Authentication service is temporarily unavailable. Please try again later.",
                "degraded_features": [],
                "available_features": [],
            },
        }

        # Return specific config or default
        return fallback_configs.get(
            operation_type,
            {
                "enabled": True,
                "fallback_message": "Service is temporarily unavailable. Please try again later.",
                "degraded_features": ["advanced_features"],
                "available_features": ["basic_operations"],
            },
        )

    def get_alerting_config(self) -> Dict[str, Any]:
        """Get alerting and escalation configuration."""
        return {
            "escalation_levels": {
                "level_1": {
                    "name": "Development Team",
                    "delay_minutes": 0,
                    "channels": ["slack", "email"],
                    "severity_threshold": "warning",
                },
                "level_2": {
                    "name": "Operations Team",
                    "delay_minutes": 30,
                    "channels": ["pagerduty", "slack", "email"],
                    "severity_threshold": "error",
                },
                "level_3": {
                    "name": "Management",
                    "delay_minutes": 60,
                    "channels": ["phone", "email"],
                    "severity_threshold": "critical",
                },
                "level_4": {
                    "name": "Executive",
                    "delay_minutes": 120,
                    "channels": ["phone", "sms"],
                    "severity_threshold": "critical",
                },
            },
            "alert_channels": {
                "slack": {"enabled": True, "webhook_url": None, "channel": "#alerts"},  # Set via environment
                "email": {
                    "enabled": True,
                    "smtp_config": None,  # Use existing email config
                    "recipients": [],  # Set via environment
                },
                "pagerduty": {"enabled": False, "integration_key": None, "service_key": None},  # Set via environment
                "phone": {"enabled": False, "provider": "twilio", "numbers": []},  # Set via environment
                "sms": {"enabled": False, "provider": "twilio", "numbers": []},  # Set via environment
            },
            "alert_suppression": {
                "enabled": True,
                "duplicate_window_minutes": 30,
                "max_alerts_per_hour": 10,
                "burst_threshold": 5,
            },
        }


# Global configuration instance
error_handling_config = ErrorHandlingConfig()


# Convenience functions for getting configurations
def get_circuit_breaker_config(service_name: str) -> CircuitBreakerConfig:
    """Get circuit breaker configuration for a service."""
    return error_handling_config.get_circuit_breaker_config(service_name)


def get_bulkhead_config(resource_name: str) -> BulkheadConfig:
    """Get bulkhead configuration for a resource."""
    return error_handling_config.get_bulkhead_config(resource_name)


def get_retry_config(operation_type: str) -> RetryConfig:
    """Get retry configuration for an operation."""
    return error_handling_config.get_retry_config(operation_type)


def get_timeout_config(operation_type: str) -> float:
    """Get timeout configuration for an operation."""
    return error_handling_config.get_timeout_config(operation_type)


def get_fallback_config(operation_type: str) -> Dict[str, Any]:
    """Get fallback configuration for an operation."""
    return error_handling_config.get_fallback_config(operation_type)


def get_monitoring_config() -> MonitoringConfig:
    """Get monitoring configuration."""
    return error_handling_config.monitoring


def get_alerting_config() -> Dict[str, Any]:
    """Get alerting configuration."""
    return error_handling_config.get_alerting_config()

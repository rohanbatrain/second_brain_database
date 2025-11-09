"""
Family Management System Monitoring Configuration.

This module contains configuration settings for family system monitoring,
alerting thresholds, and observability parameters.
"""

from dataclasses import dataclass
import os
from typing import Any, Dict


@dataclass
class MonitoringThresholds:
    """Monitoring thresholds for family system alerts."""

    # Performance thresholds (seconds)
    slow_operation_threshold: float = 2.0
    very_slow_operation_threshold: float = 5.0
    critical_operation_threshold: float = 10.0

    # Error rate thresholds (percentage)
    high_error_rate_threshold: float = 0.05  # 5%
    critical_error_rate_threshold: float = 0.10  # 10%

    # System health thresholds
    max_pending_invitations: int = 100
    max_pending_token_requests: int = 50
    max_response_time: float = 3.0  # seconds

    # SBD token thresholds
    max_frozen_accounts_percentage: float = 0.20  # 20%
    low_balance_threshold: int = 10  # SBD tokens

    # Rate limiting thresholds
    max_operations_per_minute: int = 100
    max_errors_per_minute: int = 10


@dataclass
class AlertingConfig:
    """Configuration for alerting systems."""

    # Alert cooldown periods (seconds)
    alert_cooldown_period: int = 1800  # 30 minutes
    critical_alert_cooldown: int = 300  # 5 minutes

    # Alert channels (would be configured per environment)
    enable_email_alerts: bool = True
    enable_slack_alerts: bool = False
    enable_pagerduty_alerts: bool = False

    # Alert recipients
    admin_email: str = os.getenv("FAMILY_ADMIN_EMAIL", "admin@example.com")
    slack_webhook_url: str = os.getenv("SLACK_WEBHOOK_URL", "")
    pagerduty_integration_key: str = os.getenv("PAGERDUTY_INTEGRATION_KEY", "")


@dataclass
class MetricsConfig:
    """Configuration for metrics collection."""

    # Collection intervals (seconds)
    health_check_interval: int = 300  # 5 minutes
    metrics_collection_interval: int = 60  # 1 minute
    performance_data_retention: int = 3600  # 1 hour

    # Metrics storage
    enable_prometheus_metrics: bool = True
    prometheus_port: int = 9090
    metrics_prefix: str = "family_system"

    # Data retention
    operation_data_retention_hours: int = 24
    error_data_retention_hours: int = 72
    performance_data_retention_hours: int = 12


@dataclass
class LoggingConfig:
    """Configuration for family system logging."""

    # Log levels
    default_log_level: str = "INFO"
    performance_log_level: str = "DEBUG"
    security_log_level: str = "INFO"
    audit_log_level: str = "INFO"

    # Structured logging
    enable_structured_logging: bool = True
    log_format: str = "json"

    # Log destinations
    enable_file_logging: bool = True
    enable_loki_logging: bool = True
    enable_console_logging: bool = True

    # Log rotation
    max_log_file_size: str = "100MB"
    max_log_files: int = 10


# Environment-specific configurations
MONITORING_CONFIGS = {
    "development": {
        "thresholds": MonitoringThresholds(
            slow_operation_threshold=3.0,
            very_slow_operation_threshold=8.0,
            high_error_rate_threshold=0.10,
            critical_error_rate_threshold=0.20,
        ),
        "alerting": AlertingConfig(enable_email_alerts=False, enable_slack_alerts=False, alert_cooldown_period=300),
        "metrics": MetricsConfig(health_check_interval=600, metrics_collection_interval=120),
        "logging": LoggingConfig(default_log_level="DEBUG", enable_console_logging=True),
    },
    "staging": {
        "thresholds": MonitoringThresholds(
            slow_operation_threshold=2.5,
            very_slow_operation_threshold=6.0,
            high_error_rate_threshold=0.08,
            critical_error_rate_threshold=0.15,
        ),
        "alerting": AlertingConfig(enable_email_alerts=True, enable_slack_alerts=True, alert_cooldown_period=900),
        "metrics": MetricsConfig(health_check_interval=300, metrics_collection_interval=60),
        "logging": LoggingConfig(default_log_level="INFO", enable_loki_logging=True),
    },
    "production": {
        "thresholds": MonitoringThresholds(),  # Use defaults
        "alerting": AlertingConfig(enable_email_alerts=True, enable_slack_alerts=True, enable_pagerduty_alerts=True),
        "metrics": MetricsConfig(),  # Use defaults
        "logging": LoggingConfig(
            default_log_level="INFO",
            performance_log_level="INFO",
            enable_loki_logging=True,
            enable_console_logging=False,
        ),
    },
}


def get_monitoring_config(environment: str = None) -> Dict[str, Any]:
    """
    Get monitoring configuration for the specified environment.

    Args:
        environment: Environment name (development, staging, production)

    Returns:
        Dictionary containing monitoring configuration
    """
    if environment is None:
        environment = os.getenv("ENV", "development").lower()

    config = MONITORING_CONFIGS.get(environment, MONITORING_CONFIGS["development"])

    return {
        "environment": environment,
        "thresholds": config["thresholds"],
        "alerting": config["alerting"],
        "metrics": config["metrics"],
        "logging": config["logging"],
    }


# Prometheus metrics configuration
PROMETHEUS_METRICS = {
    "family_operations_total": {
        "type": "counter",
        "description": "Total number of family operations",
        "labels": ["operation_type", "status"],
    },
    "family_operation_duration_seconds": {
        "type": "histogram",
        "description": "Duration of family operations in seconds",
        "labels": ["operation_type"],
        "buckets": [0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
    },
    "family_system_health": {
        "type": "gauge",
        "description": "Health status of family system components",
        "labels": ["component"],
    },
    "family_active_count": {"type": "gauge", "description": "Number of active families"},
    "family_members_total": {"type": "gauge", "description": "Total number of family members"},
    "family_invitations_pending": {"type": "gauge", "description": "Number of pending family invitations"},
    "family_token_requests_pending": {"type": "gauge", "description": "Number of pending token requests"},
    "family_sbd_balance_total": {"type": "gauge", "description": "Total SBD token balance across all families"},
    "family_errors_total": {
        "type": "counter",
        "description": "Total number of family operation errors",
        "labels": ["operation_type", "error_type"],
    },
}


# Health check endpoints configuration
HEALTH_CHECK_CONFIG = {
    "endpoints": {
        "/family/health/status": {
            "description": "Comprehensive family system health check",
            "timeout": 10,
            "critical": True,
        },
        "/family/health/readiness": {"description": "Family system readiness probe", "timeout": 5, "critical": True},
        "/family/health/liveness": {"description": "Family system liveness probe", "timeout": 3, "critical": False},
    },
    "components": {
        "database": {"description": "MongoDB connectivity for family collections", "timeout": 5, "critical": True},
        "redis": {"description": "Redis connectivity for family caching", "timeout": 3, "critical": True},
        "family_collections": {"description": "Family collections integrity", "timeout": 10, "critical": True},
        "sbd_integration": {"description": "SBD token integration health", "timeout": 5, "critical": False},
        "email_system": {"description": "Email system for invitations", "timeout": 3, "critical": False},
        "notification_system": {"description": "Family notification system", "timeout": 5, "critical": False},
    },
}


# Dashboard configuration for operational monitoring
DASHBOARD_CONFIG = {
    "refresh_interval": 30,  # seconds
    "charts": [
        {"title": "Family Operations Rate", "type": "line", "metrics": ["family_operations_total"], "time_range": "1h"},
        {
            "title": "Operation Response Times",
            "type": "histogram",
            "metrics": ["family_operation_duration_seconds"],
            "time_range": "1h",
        },
        {
            "title": "System Health Status",
            "type": "status",
            "metrics": ["family_system_health"],
            "time_range": "current",
        },
        {
            "title": "Family Statistics",
            "type": "stat",
            "metrics": [
                "family_active_count",
                "family_members_total",
                "family_invitations_pending",
                "family_token_requests_pending",
            ],
            "time_range": "current",
        },
        {"title": "Error Rates", "type": "line", "metrics": ["family_errors_total"], "time_range": "1h"},
        {
            "title": "SBD Token Metrics",
            "type": "stat",
            "metrics": ["family_sbd_balance_total"],
            "time_range": "current",
        },
    ],
}

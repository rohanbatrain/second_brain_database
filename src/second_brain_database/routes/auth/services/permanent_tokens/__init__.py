"""
Permanent tokens service package.

This package provides comprehensive functionality for permanent API tokens:
- Token generation with JWT and secure storage
- Redis cache-first validation with database fallback
- Token revocation and cache invalidation
- User token management and cleanup utilities
"""

from .analytics import (
    TokenUsageStats,
    UsageAnalytics,
    get_system_analytics,
    get_token_stats,
    get_user_analytics,
    token_analytics,
    track_token_usage,
)
from .audit_logger import (
    AuditEventType,
    AuditSeverity,
    audit_logger,
    log_suspicious_activity,
    log_token_created,
    log_token_revoked,
    log_token_validated,
    log_validation_failed,
)
from .cache_manager import (
    cleanup_expired_cache_entries,
    get_cache_statistics,
    invalidate_user_token_cache,
    refresh_token_cache,
    warm_frequently_used_tokens,
    warm_user_token_cache,
)
from .generator import (
    create_permanent_token,
    generate_secure_token_id,
    get_token_metadata,
    hash_token,
    update_last_used,
    validate_token_ownership,
)
from .maintenance import (
    DatabaseHealth,
    MaintenanceStats,
    get_database_health,
    run_audit_cleanup,
    run_full_maintenance,
    run_token_cleanup,
    start_periodic_maintenance,
    token_maintenance,
)
from .monitoring import (
    cache_monitor,
    get_cache_performance_metrics,
    perform_cache_health_check,
    record_cache_delete,
    record_cache_hit,
    record_cache_miss,
    record_cache_set,
    start_periodic_health_checks,
)
from .revocation import (
    cleanup_revoked_tokens,
    get_user_tokens,
    revoke_all_user_tokens,
    revoke_token_by_hash,
    revoke_token_by_id,
)
from .validator import (
    cache_token_data,
    get_cached_token_data,
    invalidate_token_cache,
    is_permanent_token,
    validate_permanent_token,
)

__all__ = [
    # Generator functions
    "create_permanent_token",
    "validate_token_ownership",
    "get_token_metadata",
    "update_last_used",
    "generate_secure_token_id",
    "hash_token",
    # Validator functions
    "validate_permanent_token",
    "is_permanent_token",
    "cache_token_data",
    "get_cached_token_data",
    "invalidate_token_cache",
    # Revocation functions
    "revoke_token_by_id",
    "revoke_token_by_hash",
    "revoke_all_user_tokens",
    "get_user_tokens",
    "cleanup_revoked_tokens",
    # Cache management functions
    "warm_user_token_cache",
    "warm_frequently_used_tokens",
    "invalidate_user_token_cache",
    "get_cache_statistics",
    "cleanup_expired_cache_entries",
    "refresh_token_cache",
    # Monitoring functions
    "get_cache_performance_metrics",
    "perform_cache_health_check",
    "record_cache_hit",
    "record_cache_miss",
    "record_cache_set",
    "record_cache_delete",
    "start_periodic_health_checks",
    "cache_monitor",
    # Audit logging functions
    "audit_logger",
    "log_token_created",
    "log_token_validated",
    "log_token_revoked",
    "log_validation_failed",
    "log_suspicious_activity",
    "AuditEventType",
    "AuditSeverity",
    # Analytics functions
    "token_analytics",
    "track_token_usage",
    "get_token_stats",
    "get_user_analytics",
    "get_system_analytics",
    "TokenUsageStats",
    "UsageAnalytics",
    # Maintenance functions
    "token_maintenance",
    "run_token_cleanup",
    "run_audit_cleanup",
    "run_full_maintenance",
    "get_database_health",
    "start_periodic_maintenance",
    "MaintenanceStats",
    "DatabaseHealth",
]

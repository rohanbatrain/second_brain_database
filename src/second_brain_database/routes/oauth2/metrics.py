"""
OAuth2 metrics collection for audit logging and monitoring.

This module provides comprehensive metrics collection for OAuth2 operations,
focusing on audit logging and in-memory metrics without Prometheus integration
to avoid conflicts with app-wide metrics.
"""

import time
from contextlib import contextmanager
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum

from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[OAuth2 Metrics]")

# Disable Prometheus metrics to avoid conflicts with app-wide metrics
PROMETHEUS_AVAILABLE = False


class OAuth2MetricType(str, Enum):
    """OAuth2 metric types for categorization."""
    
    # Request metrics
    AUTHORIZATION_REQUESTS = "authorization_requests"
    TOKEN_REQUESTS = "token_requests"
    CONSENT_REQUESTS = "consent_requests"
    
    # Success metrics
    AUTHORIZATION_GRANTED = "authorization_granted"
    TOKENS_ISSUED = "tokens_issued"
    TOKENS_REFRESHED = "tokens_refreshed"
    CONSENT_GRANTED = "consent_granted"
    
    # Error metrics
    AUTHORIZATION_ERRORS = "authorization_errors"
    TOKEN_ERRORS = "token_errors"
    VALIDATION_ERRORS = "validation_errors"
    
    # Security metrics
    RATE_LIMIT_HITS = "rate_limit_hits"
    SECURITY_VIOLATIONS = "security_violations"
    PKCE_FAILURES = "pkce_failures"
    
    # Performance metrics
    REQUEST_DURATION = "request_duration"
    TOKEN_GENERATION_TIME = "token_generation_time"
    DATABASE_OPERATION_TIME = "database_operation_time"


class OAuth2MetricsCollector:
    """
    OAuth2 metrics collector using in-memory storage for audit logging.
    
    Collects detailed metrics about OAuth2 operations for audit trails
    and monitoring without Prometheus integration.
    """
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(OAuth2MetricsCollector, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if OAuth2MetricsCollector._initialized:
            return
            
        self.logger = get_logger(prefix="[OAuth2 Metrics Collector]")
        
        # In-memory metrics storage
        self._metrics: Dict[str, Any] = {
            "counters": {},
            "histograms": {},
            "gauges": {},
            "last_updated": datetime.utcnow(),
            "system_info": {
                "version": "2.1",
                "supported_flows": "authorization_code",
                "pkce_required": True,
                "prometheus_available": False
            }
        }
        
        OAuth2MetricsCollector._initialized = True
        self.logger.info("OAuth2 metrics collector initialized with in-memory storage")
    
    def record_authorization_request(
        self,
        client_id: str,
        response_type: str,
        status: str,
        duration: Optional[float] = None
    ) -> None:
        """Record OAuth2 authorization request metrics."""
        try:
            key = f"authorization_requests_{client_id}_{response_type}_{status}"
            self._increment_counter(key)
            
            if duration is not None:
                self._record_histogram("authorization_request_duration", duration, {
                    "client_id": client_id,
                    "response_type": response_type,
                    "status": status
                })
            
            self._update_timestamp()
            
        except Exception as e:
            self.logger.error(f"Failed to record authorization request metrics: {e}")
    
    def record_token_request(
        self,
        client_id: str,
        grant_type: str,
        status: str,
        duration: Optional[float] = None
    ) -> None:
        """Record OAuth2 token request metrics."""
        try:
            key = f"token_requests_{client_id}_{grant_type}_{status}"
            self._increment_counter(key)
            
            if duration is not None:
                self._record_histogram("token_request_duration", duration, {
                    "client_id": client_id,
                    "grant_type": grant_type,
                    "status": status
                })
            
            self._update_timestamp()
            
        except Exception as e:
            self.logger.error(f"Failed to record token request metrics: {e}")
    
    def record_token_issued(
        self,
        client_id: str,
        token_type: str,
        grant_type: str,
        generation_duration: Optional[float] = None
    ) -> None:
        """Record OAuth2 token issuance metrics."""
        try:
            key = f"tokens_issued_{client_id}_{token_type}_{grant_type}"
            self._increment_counter(key)
            
            if generation_duration is not None:
                self._record_histogram("token_generation_duration", generation_duration, {
                    "client_id": client_id,
                    "token_type": token_type,
                    "grant_type": grant_type
                })
            
            self._update_timestamp()
            
        except Exception as e:
            self.logger.error(f"Failed to record token issued metrics: {e}")
    
    def record_consent_event(
        self,
        client_id: str,
        action: str,
        status: str,
        scope_count: int = 0
    ) -> None:
        """Record OAuth2 consent event metrics."""
        try:
            key = f"consent_events_{client_id}_{action}_{status}"
            self._increment_counter(key)
            
            if action == "granted" and status == "success":
                granted_key = f"consents_granted_{client_id}_{scope_count}"
                self._increment_counter(granted_key)
            
            self._update_timestamp()
            
        except Exception as e:
            self.logger.error(f"Failed to record consent event metrics: {e}")
    
    def record_authorization_error(
        self,
        client_id: str,
        error_code: str,
        severity: str
    ) -> None:
        """Record OAuth2 authorization error metrics."""
        try:
            key = f"authorization_errors_{client_id}_{error_code}_{severity}"
            self._increment_counter(key)
            self._update_timestamp()
            
        except Exception as e:
            self.logger.error(f"Failed to record authorization error metrics: {e}")
    
    def record_token_error(
        self,
        client_id: str,
        error_code: str,
        grant_type: str
    ) -> None:
        """Record OAuth2 token error metrics."""
        try:
            key = f"token_errors_{client_id}_{error_code}_{grant_type}"
            self._increment_counter(key)
            self._update_timestamp()
            
        except Exception as e:
            self.logger.error(f"Failed to record token error metrics: {e}")
    
    def record_security_violation(
        self,
        client_id: str,
        violation_type: str,
        severity: str
    ) -> None:
        """Record OAuth2 security violation metrics."""
        try:
            key = f"security_violations_{client_id}_{violation_type}_{severity}"
            self._increment_counter(key)
            self._update_timestamp()
            
        except Exception as e:
            self.logger.error(f"Failed to record security violation metrics: {e}")
    
    def record_rate_limit_hit(
        self,
        client_id: str,
        endpoint: str,
        limit_type: str
    ) -> None:
        """Record OAuth2 rate limit hit metrics."""
        try:
            key = f"rate_limit_hits_{client_id}_{endpoint}_{limit_type}"
            self._increment_counter(key)
            self._update_timestamp()
            
        except Exception as e:
            self.logger.error(f"Failed to record rate limit hit metrics: {e}")
    
    def record_pkce_failure(
        self,
        client_id: str,
        failure_type: str
    ) -> None:
        """Record PKCE validation failure metrics."""
        try:
            key = f"pkce_failures_{client_id}_{failure_type}"
            self._increment_counter(key)
            self._update_timestamp()
            
        except Exception as e:
            self.logger.error(f"Failed to record PKCE failure metrics: {e}")
    
    def record_database_operation(
        self,
        operation_type: str,
        collection: str,
        duration: float
    ) -> None:
        """Record OAuth2 database operation metrics."""
        try:
            self._record_histogram("database_operation_duration", duration, {
                "operation_type": operation_type,
                "collection": collection
            })
            self._update_timestamp()
            
        except Exception as e:
            self.logger.error(f"Failed to record database operation metrics: {e}")
    
    def update_active_counts(
        self,
        client_id: str,
        authorization_codes: int,
        refresh_tokens: int,
        consents: int
    ) -> None:
        """Update active resource count metrics."""
        try:
            self._set_gauge(f"active_authorization_codes_{client_id}", authorization_codes)
            self._set_gauge(f"active_refresh_tokens_{client_id}", refresh_tokens)
            self._set_gauge(f"active_consents_{client_id}", consents)
            self._update_timestamp()
            
        except Exception as e:
            self.logger.error(f"Failed to update active count metrics: {e}")
    
    def update_client_counts(
        self,
        confidential_active: int,
        confidential_inactive: int,
        public_active: int,
        public_inactive: int
    ) -> None:
        """Update registered client count metrics."""
        try:
            self._set_gauge("registered_clients_confidential_active", confidential_active)
            self._set_gauge("registered_clients_confidential_inactive", confidential_inactive)
            self._set_gauge("registered_clients_public_active", public_active)
            self._set_gauge("registered_clients_public_inactive", public_inactive)
            self._update_timestamp()
            
        except Exception as e:
            self.logger.error(f"Failed to update client count metrics: {e}")
    
    @contextmanager
    def time_request(self, endpoint: str, method: str):
        """Context manager for timing OAuth2 requests."""
        start_time = time.time()
        status = "success"
        
        try:
            yield
        except Exception:
            status = "error"
            raise
        finally:
            duration = time.time() - start_time
            try:
                self._record_histogram("request_duration", duration, {
                    "endpoint": endpoint,
                    "method": method,
                    "status": status
                })
            except Exception as e:
                self.logger.error(f"Failed to record request timing: {e}")
    
    @contextmanager
    def time_token_generation(self, token_type: str, grant_type: str):
        """Context manager for timing token generation."""
        start_time = time.time()
        
        try:
            yield
        finally:
            duration = time.time() - start_time
            try:
                self._record_histogram("token_generation_duration", duration, {
                    "token_type": token_type,
                    "grant_type": grant_type
                })
            except Exception as e:
                self.logger.error(f"Failed to record token generation timing: {e}")
    
    @contextmanager
    def time_database_operation(self, operation_type: str, collection: str):
        """Context manager for timing database operations."""
        start_time = time.time()
        
        try:
            yield
        finally:
            duration = time.time() - start_time
            try:
                self.record_database_operation(operation_type, collection, duration)
            except Exception as e:
                self.logger.error(f"Failed to record database operation timing: {e}")
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of all collected metrics."""
        try:
            return {
                "counters": dict(self._metrics["counters"]),
                "histograms": {
                    name: {
                        "count": len(values),
                        "avg": sum(v["value"] for v in values) / len(values) if values else 0,
                        "min": min(v["value"] for v in values) if values else 0,
                        "max": max(v["value"] for v in values) if values else 0,
                        "recent_values": values[-10:]  # Last 10 values
                    }
                    for name, values in self._metrics["histograms"].items()
                },
                "gauges": dict(self._metrics["gauges"]),
                "system_info": self._metrics["system_info"],
                "last_updated": self._metrics["last_updated"].isoformat(),
                "prometheus_available": PROMETHEUS_AVAILABLE
            }
        except Exception as e:
            self.logger.error(f"Failed to get metrics summary: {e}")
            return {}
    
    def get_fallback_metrics(self) -> Dict[str, Any]:
        """Get fallback metrics (same as metrics summary for this implementation)."""
        return self.get_metrics_summary()
    
    def _increment_counter(self, key: str) -> None:
        """Increment a counter metric."""
        self._metrics["counters"][key] = self._metrics["counters"].get(key, 0) + 1
    
    def _record_histogram(self, name: str, value: float, labels: Dict[str, str]) -> None:
        """Record a histogram value."""
        if name not in self._metrics["histograms"]:
            self._metrics["histograms"][name] = []
        
        self._metrics["histograms"][name].append({
            "value": value,
            "labels": labels,
            "timestamp": datetime.utcnow().timestamp()
        })
        
        # Keep only last 1000 values per histogram
        if len(self._metrics["histograms"][name]) > 1000:
            self._metrics["histograms"][name] = self._metrics["histograms"][name][-1000:]
    
    def _set_gauge(self, key: str, value: float) -> None:
        """Set a gauge metric value."""
        self._metrics["gauges"][key] = value
    
    def _update_timestamp(self) -> None:
        """Update the last updated timestamp."""
        self._metrics["last_updated"] = datetime.utcnow()


# Global OAuth2 metrics collector instance
oauth2_metrics = OAuth2MetricsCollector()


# Convenience functions for common metrics operations
def record_authorization_request(client_id: str, response_type: str, status: str, duration: Optional[float] = None) -> None:
    """Record authorization request metrics."""
    oauth2_metrics.record_authorization_request(client_id, response_type, status, duration)


def record_token_request(client_id: str, grant_type: str, status: str, duration: Optional[float] = None) -> None:
    """Record token request metrics."""
    oauth2_metrics.record_token_request(client_id, grant_type, status, duration)


def record_token_issued(client_id: str, token_type: str, grant_type: str, generation_duration: Optional[float] = None) -> None:
    """Record token issuance metrics."""
    oauth2_metrics.record_token_issued(client_id, token_type, grant_type, generation_duration)


def record_security_violation(client_id: str, violation_type: str, severity: str = "high") -> None:
    """Record security violation metrics."""
    oauth2_metrics.record_security_violation(client_id, violation_type, severity)


def record_rate_limit_hit(client_id: str, endpoint: str, limit_type: str = "requests") -> None:
    """Record rate limit hit metrics."""
    oauth2_metrics.record_rate_limit_hit(client_id, endpoint, limit_type)


def time_request(endpoint: str, method: str = "GET"):
    """Time OAuth2 request execution."""
    return oauth2_metrics.time_request(endpoint, method)


def time_token_generation(token_type: str, grant_type: str):
    """Time token generation execution."""
    return oauth2_metrics.time_token_generation(token_type, grant_type)


def time_database_operation(operation_type: str, collection: str):
    """Time database operation execution."""
    return oauth2_metrics.time_database_operation(operation_type, collection)
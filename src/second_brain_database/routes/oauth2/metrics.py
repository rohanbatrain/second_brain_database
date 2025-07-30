"""
OAuth2 metrics collection system for comprehensive monitoring and analytics.

This module provides enterprise-grade metrics collection for OAuth2 flows,
including completion rates, performance metrics, and operational insights.

Features:
- OAuth2 flow completion rate tracking by authentication method
- Performance metrics for all OAuth2 operations
- Security metrics and violation tracking
- Template rendering performance monitoring
- Real-time metrics for dashboards and alerting
- Integration with monitoring systems (Prometheus, etc.)
"""

import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
import threading

from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import redis_manager

logger = get_logger(prefix="[OAuth2 Metrics]")


class MetricType(str, Enum):
    """Types of metrics collected."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


class AuthMethod(str, Enum):
    """Authentication methods for metrics."""
    JWT_TOKEN = "jwt_token"
    BROWSER_SESSION = "browser_session"
    MIXED = "mixed"
    UNKNOWN = "unknown"


@dataclass
class MetricPoint:
    """Individual metric data point."""
    name: str
    value: float
    timestamp: datetime
    labels: Dict[str, str] = field(default_factory=dict)
    metric_type: MetricType = MetricType.GAUGE


@dataclass
class FlowMetric:
    """OAuth2 flow completion metrics."""
    client_id: str
    auth_method: AuthMethod
    response_type: str
    status: str  # success/failure/timeout
    duration: Optional[float] = None
    error_code: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class OAuth2MetricsCollector:
    """
    Comprehensive metrics collection system for OAuth2 operations.
    
    Collects and aggregates metrics for monitoring, alerting, and analytics.
    """
    
    def __init__(self):
        self.logger = get_logger(prefix="[OAuth2 Metrics Collector]")
        
        # Thread safety
        self._lock = threading.Lock()
        
        # Metrics storage
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.counters: Dict[str, int] = defaultdict(int)
        self.gauges: Dict[str, float] = defaultdict(float)
        self.histograms: Dict[str, List[float]] = defaultdict(list)
        
        # Flow completion tracking
        self.flow_completions: deque = deque(maxlen=5000)
        self.completion_rates: Dict[str, Dict[str, int]] = {
            "jwt_token": {"total": 0, "success": 0, "failure": 0},
            "browser_session": {"total": 0, "success": 0, "failure": 0},
            "mixed": {"total": 0, "success": 0, "failure": 0}
        }
        
        # Performance metrics
        self.performance_metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=500))
        
        # Security metrics
        self.security_violations: deque = deque(maxlen=1000)
        self.rate_limit_hits: deque = deque(maxlen=500)
        
        # Template metrics
        self.template_metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=200))
        
        # Error tracking
        self.error_counts: Dict[str, int] = defaultdict(int)
        self.error_details: deque = deque(maxlen=1000)
        
        # Health metrics
        self.health_metrics = {
            "last_updated": datetime.now(timezone.utc),
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "avg_response_time": 0.0,
            "error_rate": 0.0
        }
    
    def record_authorization_request(
        self,
        client_id: str,
        response_type: str,
        status: str,
        auth_method: str = "unknown",
        duration: Optional[float] = None,
        error_code: Optional[str] = None
    ) -> None:
        """Record OAuth2 authorization request metrics."""
        with self._lock:
            # Record flow metric
            flow_metric = FlowMetric(
                client_id=client_id,
                auth_method=AuthMethod(auth_method) if auth_method in AuthMethod.__members__.values() else AuthMethod.UNKNOWN,
                response_type=response_type,
                status=status,
                duration=duration,
                error_code=error_code
            )
            
            self.flow_completions.append(flow_metric)
            
            # Update completion rates
            auth_key = auth_method if auth_method in self.completion_rates else "browser_session"
            if auth_key not in self.completion_rates:
                self.completion_rates[auth_key] = {"total": 0, "success": 0, "failure": 0}
            
            if status == "requested":
                self.completion_rates[auth_key]["total"] += 1
            elif status == "success":
                self.completion_rates[auth_key]["success"] += 1
                self.completion_rates[auth_key]["total"] += 1  # Also increment total for success
            elif status == "failure":
                self.completion_rates[auth_key]["failure"] += 1
                self.completion_rates[auth_key]["total"] += 1  # Also increment total for failure
            
            # Record counters
            self.counters[f"oauth2_authorization_requests_total"] += 1
            self.counters[f"oauth2_authorization_requests_{status}"] += 1
            self.counters[f"oauth2_authorization_requests_{auth_method}_{status}"] += 1
            
            # Record duration if provided
            if duration is not None:
                self.performance_metrics["authorization_duration"].append(duration)
                self.histograms["oauth2_authorization_duration_seconds"].append(duration)
            
            # Record error if applicable
            if error_code:
                self.error_counts[f"authorization_{error_code}"] += 1
                self.error_details.append({
                    "timestamp": datetime.now(timezone.utc),
                    "operation": "authorization",
                    "error_code": error_code,
                    "client_id": client_id,
                    "auth_method": auth_method
                })
            
            # Update health metrics
            self.health_metrics["total_requests"] += 1
            if status == "success":
                self.health_metrics["successful_requests"] += 1
            elif status == "failure":
                self.health_metrics["failed_requests"] += 1
            
            self._update_health_metrics()
    
    def record_token_request(
        self,
        client_id: str,
        grant_type: str,
        status: str,
        duration: Optional[float] = None,
        error_code: Optional[str] = None
    ) -> None:
        """Record OAuth2 token request metrics."""
        with self._lock:
            # Record counters
            self.counters[f"oauth2_token_requests_total"] += 1
            self.counters[f"oauth2_token_requests_{status}"] += 1
            self.counters[f"oauth2_token_requests_{grant_type}_{status}"] += 1
            
            # Record duration if provided
            if duration is not None:
                self.performance_metrics["token_duration"].append(duration)
                self.histograms["oauth2_token_duration_seconds"].append(duration)
            
            # Record error if applicable
            if error_code:
                self.error_counts[f"token_{error_code}"] += 1
                self.error_details.append({
                    "timestamp": datetime.now(timezone.utc),
                    "operation": "token",
                    "error_code": error_code,
                    "client_id": client_id,
                    "grant_type": grant_type
                })
            
            # Update health metrics
            self.health_metrics["total_requests"] += 1
            if status == "success":
                self.health_metrics["successful_requests"] += 1
            elif status == "failure":
                self.health_metrics["failed_requests"] += 1
            
            self._update_health_metrics()
    
    def record_template_render_time(
        self,
        template_name: str,
        render_time: float,
        client_id: Optional[str] = None
    ) -> None:
        """Record template rendering performance metrics."""
        with self._lock:
            # Record template-specific metrics
            self.template_metrics[template_name].append(render_time)
            self.histograms[f"oauth2_template_render_duration_{template_name}"].append(render_time)
            
            # Record general template metrics
            self.performance_metrics["template_render_time"].append(render_time)
            self.counters["oauth2_template_renders_total"] += 1
            
            # Record slow renders
            if render_time > 0.5:  # More than 500ms
                self.counters["oauth2_template_renders_slow"] += 1
            
            if render_time > 2.0:  # More than 2 seconds
                self.counters["oauth2_template_renders_very_slow"] += 1
    
    def record_security_violation(
        self,
        client_id: str,
        violation_type: str,
        severity: str,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record security violation metrics."""
        with self._lock:
            # Record security violation
            violation_record = {
                "timestamp": datetime.now(timezone.utc),
                "client_id": client_id,
                "violation_type": violation_type,
                "severity": severity,
                "details": details
            }
            
            self.security_violations.append(violation_record)
            
            # Record counters
            self.counters["oauth2_security_violations_total"] += 1
            self.counters[f"oauth2_security_violations_{violation_type}"] += 1
            self.counters[f"oauth2_security_violations_{severity}"] += 1
    
    def record_rate_limit_hit(
        self,
        client_id: str,
        endpoint: str,
        limit_type: str,
        current_count: Optional[int] = None,
        limit_value: Optional[int] = None
    ) -> None:
        """Record rate limit hit metrics."""
        with self._lock:
            # Record rate limit hit
            rate_limit_record = {
                "timestamp": datetime.now(timezone.utc),
                "client_id": client_id,
                "endpoint": endpoint,
                "limit_type": limit_type,
                "current_count": current_count,
                "limit_value": limit_value
            }
            
            self.rate_limit_hits.append(rate_limit_record)
            
            # Record counters
            self.counters["oauth2_rate_limits_hit_total"] += 1
            self.counters[f"oauth2_rate_limits_hit_{endpoint}"] += 1
            self.counters[f"oauth2_rate_limits_hit_{limit_type}"] += 1
    
    def get_completion_rates(self) -> Dict[str, Dict[str, float]]:
        """Get OAuth2 flow completion rates by authentication method."""
        with self._lock:
            rates = {}
            
            for auth_method, stats in self.completion_rates.items():
                total = stats["total"]
                if total > 0:
                    success_rate = (stats["success"] / total) * 100
                    failure_rate = (stats["failure"] / total) * 100
                else:
                    success_rate = 0.0
                    failure_rate = 0.0
                
                rates[auth_method] = {
                    "success_rate": success_rate,
                    "failure_rate": failure_rate,
                    "total_flows": total,
                    "successful_flows": stats["success"],
                    "failed_flows": stats["failure"]
                }
            
            return rates
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance metrics summary."""
        with self._lock:
            summary = {}
            
            # Authorization performance
            auth_durations = list(self.performance_metrics["authorization_duration"])
            if auth_durations:
                summary["authorization"] = {
                    "avg_duration": sum(auth_durations) / len(auth_durations),
                    "max_duration": max(auth_durations),
                    "min_duration": min(auth_durations),
                    "p95_duration": self._calculate_percentile(auth_durations, 95),
                    "p99_duration": self._calculate_percentile(auth_durations, 99)
                }
            
            # Token performance
            token_durations = list(self.performance_metrics["token_duration"])
            if token_durations:
                summary["token"] = {
                    "avg_duration": sum(token_durations) / len(token_durations),
                    "max_duration": max(token_durations),
                    "min_duration": min(token_durations),
                    "p95_duration": self._calculate_percentile(token_durations, 95),
                    "p99_duration": self._calculate_percentile(token_durations, 99)
                }
            
            # Template performance
            template_summary = {}
            for template_name, render_times in self.template_metrics.items():
                if render_times:
                    times_list = list(render_times)
                    template_summary[template_name] = {
                        "avg_render_time": sum(times_list) / len(times_list),
                        "max_render_time": max(times_list),
                        "min_render_time": min(times_list),
                        "render_count": len(times_list),
                        "slow_renders": sum(1 for t in times_list if t > 0.5)
                    }
            
            summary["templates"] = template_summary
            
            return summary
    
    def get_security_summary(self) -> Dict[str, Any]:
        """Get security metrics summary."""
        with self._lock:
            violations_by_type = defaultdict(int)
            violations_by_severity = defaultdict(int)
            
            for violation in self.security_violations:
                violations_by_type[violation["violation_type"]] += 1
                violations_by_severity[violation["severity"]] += 1
            
            rate_limits_by_endpoint = defaultdict(int)
            rate_limits_by_type = defaultdict(int)
            
            for rate_limit in self.rate_limit_hits:
                rate_limits_by_endpoint[rate_limit["endpoint"]] += 1
                rate_limits_by_type[rate_limit["limit_type"]] += 1
            
            return {
                "security_violations": {
                    "total": len(self.security_violations),
                    "by_type": dict(violations_by_type),
                    "by_severity": dict(violations_by_severity)
                },
                "rate_limits": {
                    "total": len(self.rate_limit_hits),
                    "by_endpoint": dict(rate_limits_by_endpoint),
                    "by_type": dict(rate_limits_by_type)
                }
            }
    
    def get_health_metrics(self) -> Dict[str, Any]:
        """Get system health metrics."""
        with self._lock:
            return self.health_metrics.copy()
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all collected metrics."""
        return {
            "completion_rates": self.get_completion_rates(),
            "performance": self.get_performance_summary(),
            "security": self.get_security_summary(),
            "health": self.get_health_metrics(),
            "counters": dict(self.counters),
            "error_counts": dict(self.error_counts)
        }
    
    def _calculate_percentile(self, values: List[float], percentile: int) -> float:
        """Calculate percentile value from list of values."""
        if not values:
            return 0.0
        
        sorted_values = sorted(values)
        index = int((percentile / 100.0) * len(sorted_values))
        if index >= len(sorted_values):
            index = len(sorted_values) - 1
        
        return sorted_values[index]
    
    def _update_health_metrics(self) -> None:
        """Update health metrics calculations."""
        total = self.health_metrics["total_requests"]
        if total > 0:
            self.health_metrics["error_rate"] = (
                self.health_metrics["failed_requests"] / total
            ) * 100
        
        # Update average response time
        all_durations = []
        all_durations.extend(self.performance_metrics["authorization_duration"])
        all_durations.extend(self.performance_metrics["token_duration"])
        
        if all_durations:
            self.health_metrics["avg_response_time"] = sum(all_durations) / len(all_durations)
        
        self.health_metrics["last_updated"] = datetime.now(timezone.utc)


# Global metrics collector instance
oauth2_metrics = OAuth2MetricsCollector()


# Convenience functions for common metric operations
def record_auth_request(
    client_id: str,
    response_type: str,
    status: str,
    auth_method: str = "unknown",
    duration: Optional[float] = None,
    error_code: Optional[str] = None
) -> None:
    """Record authorization request metric."""
    oauth2_metrics.record_authorization_request(
        client_id, response_type, status, auth_method, duration, error_code
    )


def record_token_request(
    client_id: str,
    grant_type: str,
    status: str,
    duration: Optional[float] = None,
    error_code: Optional[str] = None
) -> None:
    """Record token request metric."""
    oauth2_metrics.record_token_request(client_id, grant_type, status, duration, error_code)


def record_template_performance(
    template_name: str,
    render_time: float,
    client_id: Optional[str] = None
) -> None:
    """Record template rendering performance."""
    oauth2_metrics.record_template_render_time(template_name, render_time, client_id)


def record_security_violation(
    client_id: str,
    violation_type: str,
    severity: str,
    details: Optional[Dict[str, Any]] = None
) -> None:
    """Record security violation."""
    oauth2_metrics.record_security_violation(client_id, violation_type, severity, details)


def record_rate_limit_hit(
    client_id: str,
    endpoint: str,
    limit_type: str,
    current_count: Optional[int] = None,
    limit_value: Optional[int] = None
) -> None:
    """Record rate limit hit."""
    oauth2_metrics.record_rate_limit_hit(client_id, endpoint, limit_type, current_count, limit_value)


# Context managers for timing operations
class time_request:
    """Context manager for timing OAuth2 requests."""
    
    def __init__(self, client_id: str, operation: str):
        self.client_id = client_id
        self.operation = operation
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = time.time() - self.start_time
            
            if self.operation == "authorization":
                status = "failure" if exc_type else "success"
                oauth2_metrics.record_authorization_request(
                    self.client_id, "code", status, auth_method="browser_session", duration=duration
                )
            elif self.operation == "token":
                status = "failure" if exc_type else "success"
                oauth2_metrics.record_token_request(
                    self.client_id, "authorization_code", status, duration=duration
                )


class time_template_render:
    """Context manager for timing template rendering."""
    
    def __init__(self, template_name: str, client_id: Optional[str] = None):
        self.template_name = template_name
        self.client_id = client_id
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = time.time() - self.start_time
            oauth2_metrics.record_template_render_time(
                self.template_name, duration, self.client_id
            )
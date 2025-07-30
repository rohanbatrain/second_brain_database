"""
Authentication method monitoring dashboard for OAuth2 enterprise coordination.

This module provides comprehensive monitoring dashboards and analytics for
authentication method usage patterns, performance metrics, and operational insights.

Features:
- Real-time authentication method usage dashboards
- Performance analytics and trend analysis
- Client behavior pattern analysis
- Security event monitoring and alerting
- Operational health metrics and diagnostics
- Historical data analysis and reporting
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict, deque
from dataclasses import dataclass, asdict

from fastapi import APIRouter, Request, HTTPException, Depends, status
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from second_brain_database.config import settings
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.routes.oauth2.auth_method_coordinator import (
    auth_method_coordinator, AuthMethodDecision, AuthenticationMethod, ClientType
)
from second_brain_database.routes.oauth2.monitoring import oauth2_monitoring

logger = get_logger(prefix="[Auth Method Dashboard]")


class DashboardMetrics(BaseModel):
    """Dashboard metrics data model."""
    timestamp: datetime
    total_requests: int
    method_distribution: Dict[str, int]
    client_type_distribution: Dict[str, int]
    success_rates: Dict[str, float]
    avg_decision_time: float
    cache_hit_rate: float
    security_events: int


class AuthMethodDashboard:
    """
    Authentication method monitoring dashboard system.
    
    Provides comprehensive dashboards and analytics for monitoring
    authentication method coordination and usage patterns.
    """
    
    def __init__(self):
        self.logger = get_logger(prefix="[Auth Method Dashboard]")
        
        # Historical metrics storage
        self.historical_metrics: deque = deque(maxlen=1440)  # 24 hours of minute data
        self.hourly_metrics: deque = deque(maxlen=168)  # 7 days of hourly data
        self.daily_metrics: deque = deque(maxlen=30)  # 30 days of daily data
        
        # Real-time metrics
        self.current_metrics = DashboardMetrics(
            timestamp=datetime.now(timezone.utc),
            total_requests=0,
            method_distribution={},
            client_type_distribution={},
            success_rates={},
            avg_decision_time=0.0,
            cache_hit_rate=0.0,
            security_events=0
        )
        
        # Dashboard configuration
        self.dashboard_config = {
            "refresh_interval": 30,  # seconds
            "alert_thresholds": {
                "error_rate": 5.0,  # percentage
                "avg_response_time": 1000.0,  # milliseconds
                "cache_hit_rate": 80.0  # percentage
            },
            "chart_colors": {
                "jwt_token": "#4CAF50",
                "browser_session": "#2196F3",
                "mixed": "#FF9800",
                "unknown": "#9E9E9E"
            }
        }
    
    async def get_dashboard_data(self) -> Dict[str, Any]:
        """
        Get comprehensive dashboard data.
        
        Returns:
            Dict[str, Any]: Dashboard data with metrics and charts
        """
        # Get current coordination statistics
        coord_stats = auth_method_coordinator.get_coordination_statistics()
        
        # Get OAuth2 monitoring data
        completion_rates = oauth2_monitoring.get_completion_rates()
        performance_metrics = oauth2_monitoring.get_performance_metrics()
        security_summary = oauth2_monitoring.get_security_summary()
        health_status = oauth2_monitoring.get_health_status()
        
        # Prepare dashboard data
        dashboard_data = {
            "overview": {
                "total_requests": sum(
                    stats["total_attempts"] 
                    for stats in coord_stats["method_statistics"].values()
                ),
                "active_flows": health_status["active_flows_count"],
                "active_sessions": health_status["active_sessions_count"],
                "error_rate": health_status["error_rate"],
                "avg_flow_duration": health_status["avg_flow_duration"]
            },
            "authentication_methods": {
                "distribution": self._calculate_method_distribution(coord_stats),
                "success_rates": self._calculate_success_rates(coord_stats),
                "performance": self._calculate_method_performance(coord_stats)
            },
            "client_analysis": {
                "client_types": coord_stats["client_summary"]["client_types"],
                "preferred_methods": coord_stats["client_summary"]["preferred_methods"],
                "total_clients": coord_stats["client_summary"]["total_clients"]
            },
            "performance_metrics": {
                "cache_performance": coord_stats["cache_performance"],
                "decision_performance": coord_stats["decision_performance"],
                "template_rendering": performance_metrics.get("template_rendering", {})
            },
            "security_monitoring": {
                "events_summary": security_summary,
                "suspicious_patterns": coord_stats["security_events"]["suspicious_patterns"],
                "rate_limited_ips": coord_stats["security_events"]["rate_limited_ips"]
            },
            "historical_data": {
                "hourly_trends": self._get_hourly_trends(),
                "daily_trends": self._get_daily_trends(),
                "completion_rates": completion_rates
            },
            "alerts": await self._generate_alerts(coord_stats, health_status),
            "configuration": self.dashboard_config
        }
        
        return dashboard_data    

    def _calculate_method_distribution(self, coord_stats: Dict[str, Any]) -> Dict[str, int]:
        """Calculate authentication method distribution."""
        distribution = {}
        for method, stats in coord_stats["method_statistics"].items():
            distribution[method] = stats["total_attempts"]
        return distribution
    
    def _calculate_success_rates(self, coord_stats: Dict[str, Any]) -> Dict[str, float]:
        """Calculate success rates for each authentication method."""
        success_rates = {}
        for method, stats in coord_stats["method_statistics"].items():
            success_rates[method] = stats["success_rate"]
        return success_rates
    
    def _calculate_method_performance(self, coord_stats: Dict[str, Any]) -> Dict[str, float]:
        """Calculate performance metrics for each authentication method."""
        performance = {}
        for method, stats in coord_stats["method_statistics"].items():
            performance[method] = stats["avg_response_time"]
        return performance
    
    def _get_hourly_trends(self) -> List[Dict[str, Any]]:
        """Get hourly trend data."""
        return list(self.hourly_metrics)
    
    def _get_daily_trends(self) -> List[Dict[str, Any]]:
        """Get daily trend data."""
        return list(self.daily_metrics)
    
    async def _generate_alerts(
        self, 
        coord_stats: Dict[str, Any], 
        health_status: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate alerts based on current metrics."""
        alerts = []
        
        # Error rate alert
        if health_status["error_rate"] > self.dashboard_config["alert_thresholds"]["error_rate"]:
            alerts.append({
                "type": "error_rate",
                "severity": "high",
                "message": f"Error rate is {health_status['error_rate']:.1f}%, above threshold",
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        
        # Cache hit rate alert
        cache_hit_rate = coord_stats["cache_performance"]["hit_rate_percentage"]
        if cache_hit_rate < self.dashboard_config["alert_thresholds"]["cache_hit_rate"]:
            alerts.append({
                "type": "cache_performance",
                "severity": "medium",
                "message": f"Cache hit rate is {cache_hit_rate:.1f}%, below threshold",
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        
        return alerts


# Global dashboard instance
auth_method_dashboard = AuthMethodDashboard()


# API endpoints for dashboard data
router = APIRouter(prefix="/oauth2/dashboard", tags=["OAuth2 Dashboard"])


@router.get("/data")
async def get_dashboard_data() -> JSONResponse:
    """Get comprehensive dashboard data."""
    try:
        data = await auth_method_dashboard.get_dashboard_data()
        return JSONResponse(content=data)
    except Exception as e:
        logger.error(f"Failed to get dashboard data: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve dashboard data"
        )


@router.get("/stats")
async def get_coordination_stats() -> JSONResponse:
    """Get authentication method coordination statistics."""
    try:
        stats = get_coordination_stats()
        return JSONResponse(content=stats)
    except Exception as e:
        logger.error(f"Failed to get coordination stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve coordination statistics"
        )
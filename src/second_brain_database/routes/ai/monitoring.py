"""
AI Monitoring and Metrics Dashboard Routes.

This module provides comprehensive monitoring endpoints for AI system performance,
user analytics, and operational metrics. Integrates with Prometheus metrics
and provides real-time monitoring capabilities.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, PlainTextResponse

from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.security_manager import security_manager
from second_brain_database.managers.ai_analytics_manager import ai_analytics_manager
from second_brain_database.routes.auth import enforce_all_lockdowns
from second_brain_database.utils.ai_metrics import ai_performance_monitor
from second_brain_database.utils.logging_utils import log_performance

logger = get_logger(prefix="[AI_MONITORING]")

router = APIRouter(prefix="/ai/monitoring", tags=["AI Monitoring"])


@router.get("/dashboard", response_model=dict)
async def get_ai_monitoring_dashboard(
    request: Request,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> dict:
    """
    Get comprehensive AI monitoring dashboard data.
    
    Returns real-time metrics, performance indicators, and system health
    information for AI monitoring dashboards and operational oversight.
    
    **Rate Limiting:** 30 requests per hour per user
    **Permissions:** Admin role required for full system metrics
    
    **Returns:**
    - Comprehensive monitoring dashboard data
    """
    user_id = str(current_user["_id"])
    user_role = current_user.get("role", "user")
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"ai_monitoring_dashboard_{user_id}",
        rate_limit_requests=30,
        rate_limit_period=3600
    )
    
    try:
        # Get real-time metrics
        system_metrics = ai_performance_monitor.get_performance_summary()
        
        # Get performance stats
        performance_stats = system_metrics.get("performance_metrics", {})
        
        # Extract metrics from new structure
        session_metrics = system_metrics.get("session_metrics", {})
        websocket_stats = system_metrics.get("websocket_stats", {})
        health_status = system_metrics.get("health_status", "unknown")
        
        # Calculate error rate
        total_messages = session_metrics.get("total_messages", 0)
        total_errors = session_metrics.get("total_errors", 0)
        overall_error_rate = (total_errors / max(total_messages, 1)) if total_messages > 0 else 0.0
        
        # Base dashboard data available to all users
        dashboard_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_role": user_role,
            "system_health": {
                "status": health_status,
                "total_active_sessions": session_metrics.get("active_sessions", 0),
                "total_requests": total_messages,
                "overall_error_rate": overall_error_rate
            },
            "performance_overview": {
                "avg_response_time_ms": performance_stats.get("avg_response_time_ms", 0),
                "avg_token_latency_ms": performance_stats.get("avg_token_latency_ms", 0),
                "response_time_compliance": performance_stats.get("response_time_compliance_pct", 100)
            }
        }
        
        # Add detailed metrics for admin users
        if user_role == "admin":
            # Get system analytics for the last 24 hours
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(hours=24)
            
            system_analytics = await ai_analytics_manager.get_system_analytics(
                start_date=start_date,
                end_date=end_date
            )
            
            dashboard_data.update({
                "detailed_metrics": system_metrics,
                "analytics_summary": system_analytics.get("summary", {}),
                "agent_breakdown": system_analytics.get("agent_breakdown", {}),
                "event_breakdown": system_analytics.get("event_breakdown", {}),
                "performance_trends": {
                    agent_type: {
                        "min_response_time": stats.min_response_time if stats.min_response_time != float('inf') else 0.0,
                        "max_response_time": stats.max_response_time,
                        "total_tokens": stats.total_tokens,
                        "total_messages": stats.total_messages
                    }
                    for agent_type, stats in performance_stats.items()
                }
            })
        
        logger.debug("Retrieved AI monitoring dashboard for user %s (%s)", user_id, user_role)
        return dashboard_data
        
    except Exception as e:
        logger.error("Failed to get AI monitoring dashboard: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "DASHBOARD_RETRIEVAL_FAILED",
                "message": "Failed to retrieve monitoring dashboard"
            }
        )


@router.get("/metrics/prometheus", response_class=PlainTextResponse)
async def get_prometheus_metrics(
    request: Request,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> PlainTextResponse:
    """
    Get AI metrics in Prometheus format.
    
    Returns AI-specific metrics in Prometheus exposition format for
    integration with monitoring systems and alerting.
    
    **Rate Limiting:** 60 requests per hour per user
    **Permissions:** Admin role required
    
    **Returns:**
    - Prometheus-formatted metrics
    """
    user_id = str(current_user["_id"])
    user_role = current_user.get("role", "user")
    
    # Check admin permissions
    if user_role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "INSUFFICIENT_PERMISSIONS",
                "message": "Prometheus metrics require admin permissions"
            }
        )
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"ai_prometheus_metrics_{user_id}",
        rate_limit_requests=60,
        rate_limit_period=3600
    )
    
    try:
        from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
        
        # Generate Prometheus metrics
        metrics_output = generate_latest()
        
        logger.debug("Generated Prometheus AI metrics for user %s", user_id)
        
        return PlainTextResponse(
            content=metrics_output.decode('utf-8'),
            media_type=CONTENT_TYPE_LATEST
        )
        
    except Exception as e:
        logger.error("Failed to generate Prometheus metrics: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "METRICS_GENERATION_FAILED",
                "message": "Failed to generate Prometheus metrics"
            }
        )


@router.get("/alerts", response_model=dict)
async def get_ai_system_alerts(
    request: Request,
    current_user: dict = Depends(enforce_all_lockdowns),
    severity: Optional[str] = Query(None, description="Filter by alert severity"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of alerts")
) -> dict:
    """
    Get AI system alerts and notifications.
    
    Returns current system alerts based on performance thresholds,
    error rates, and operational metrics for proactive monitoring.
    
    **Rate Limiting:** 20 requests per hour per user
    **Permissions:** Admin role required
    
    **Returns:**
    - System alerts and notifications
    """
    user_id = str(current_user["_id"])
    user_role = current_user.get("role", "user")
    
    # Check admin permissions
    if user_role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "INSUFFICIENT_PERMISSIONS",
                "message": "System alerts require admin permissions"
            }
        )
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"ai_alerts_{user_id}",
        rate_limit_requests=20,
        rate_limit_period=3600
    )
    
    try:
        # Get current system metrics
        system_metrics = ai_performance_monitor.get_performance_summary()
        performance_stats = system_metrics.get("performance_metrics", {})
        
        alerts = []
        
        # Check error rate alerts
        session_metrics = system_metrics.get("session_metrics", {})
        total_messages = session_metrics.get("total_messages", 0)
        total_errors = session_metrics.get("total_errors", 0)
        overall_error_rate = (total_errors / max(total_messages, 1)) if total_messages > 0 else 0.0
        
        if overall_error_rate > 0.1:  # 10% threshold
            alerts.append({
                "id": f"error_rate_{int(datetime.now().timestamp())}",
                "type": "error_rate",
                "severity": "high" if overall_error_rate > 0.2 else "medium",
                "title": "High System Error Rate",
                "message": f"Overall error rate is {overall_error_rate:.1%}, exceeding threshold",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metrics": {"error_rate": overall_error_rate}
            })
        
        # Check response time alerts
        avg_response_time_ms = performance_stats.get("avg_response_time_ms", 0)
        avg_response_time_s = avg_response_time_ms / 1000.0
        
        if avg_response_time_s > 5.0:  # 5 second threshold
            alerts.append({
                "id": f"response_time_{int(datetime.now().timestamp())}",
                "type": "response_time",
                "severity": "medium" if avg_response_time_s < 10.0 else "high",
                "title": "Slow System Response Time",
                "message": f"Average response time is {avg_response_time_s:.1f}s",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metrics": {
                    "response_time": avg_response_time_s
                }
            })
        
        # Check session count alerts
        total_sessions = session_metrics.get("active_sessions", 0)
        if total_sessions > 100:  # High session count threshold
            alerts.append({
                "id": f"session_count_{int(datetime.now().timestamp())}",
                "type": "session_count",
                "severity": "low",
                "title": "High Active Session Count",
                "message": f"Currently {total_sessions} active sessions",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metrics": {"active_sessions": total_sessions}
            })
        
        # Filter by severity if specified
        if severity:
            alerts = [alert for alert in alerts if alert["severity"] == severity]
        
        # Limit results
        alerts = alerts[:limit]
        
        alert_summary = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_alerts": len(alerts),
            "severity_breakdown": {
                "high": len([a for a in alerts if a["severity"] == "high"]),
                "medium": len([a for a in alerts if a["severity"] == "medium"]),
                "low": len([a for a in alerts if a["severity"] == "low"])
            },
            "alerts": alerts
        }
        
        logger.debug("Retrieved %d AI system alerts for user %s", len(alerts), user_id)
        return alert_summary
        
    except Exception as e:
        logger.error("Failed to get AI system alerts: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ALERTS_RETRIEVAL_FAILED",
                "message": "Failed to retrieve system alerts"
            }
        )


@router.get("/health/detailed", response_model=dict)
async def get_detailed_ai_health(
    request: Request,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> dict:
    """
    Get detailed AI system health information.
    
    Returns comprehensive health checks including component status,
    performance indicators, and operational metrics.
    
    **Rate Limiting:** 30 requests per hour per user
    
    **Returns:**
    - Detailed system health information
    """
    user_id = str(current_user["_id"])
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"ai_health_detailed_{user_id}",
        rate_limit_requests=30,
        rate_limit_period=3600
    )
    
    try:
        # Get system metrics
        system_metrics = ai_performance_monitor.get_performance_summary()
        performance_stats = system_metrics.get("performance_metrics", {})
        
        # Calculate health scores
        session_metrics = system_metrics.get("session_metrics", {})
        total_messages = session_metrics.get("total_messages", 0)
        total_errors = session_metrics.get("total_errors", 0)
        overall_error_rate = (total_errors / max(total_messages, 1)) if total_messages > 0 else 0.0
        total_sessions = session_metrics.get("active_sessions", 0)
        
        # Component health checks
        components = {}
        
        # AI Session Manager health
        session_health = "healthy"
        if total_sessions > 50:
            session_health = "warning"
        elif total_sessions > 100:
            session_health = "critical"
        
        components["session_manager"] = {
            "status": session_health,
            "active_sessions": total_sessions,
            "message": f"{total_sessions} active sessions"
        }
        
        # Agent health checks
        for agent_type, stats in performance_stats.items():
            agent_health = "healthy"
            issues = []
            
            if stats.error_rate > 0.1:
                agent_health = "warning" if stats.error_rate < 0.2 else "critical"
                issues.append(f"High error rate: {stats.error_rate:.1%}")
            
            if stats.average_response_time > 5.0:
                if agent_health == "healthy":
                    agent_health = "warning"
                issues.append(f"Slow response: {stats.average_response_time:.1f}s")
            
            components[f"agent_{agent_type}"] = {
                "status": agent_health,
                "error_rate": stats.error_rate,
                "response_time": stats.average_response_time,
                "active_sessions": stats.active_sessions,
                "total_requests": stats.total_requests,
                "message": "; ".join(issues) if issues else "Operating normally"
            }
        
        # Overall system health
        critical_components = [c for c in components.values() if c["status"] == "critical"]
        warning_components = [c for c in components.values() if c["status"] == "warning"]
        
        if critical_components:
            overall_status = "critical"
        elif warning_components:
            overall_status = "warning"
        else:
            overall_status = "healthy"
        
        health_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall_status": overall_status,
            "system_metrics": {
                "total_requests": system_metrics.get("total_requests", 0),
                "total_errors": system_metrics.get("total_errors", 0),
                "error_rate": overall_error_rate,
                "active_sessions": total_sessions
            },
            "components": components,
            "summary": {
                "healthy_components": len([c for c in components.values() if c["status"] == "healthy"]),
                "warning_components": len(warning_components),
                "critical_components": len(critical_components),
                "total_components": len(components)
            }
        }
        
        logger.debug("Retrieved detailed AI health for user %s", user_id)
        return health_data
        
    except Exception as e:
        logger.error("Failed to get detailed AI health: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "HEALTH_CHECK_FAILED",
                "message": "Failed to retrieve detailed health information"
            }
        )


@router.post("/metrics/reset")
async def reset_ai_metrics(
    request: Request,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> JSONResponse:
    """
    Reset AI metrics (admin only, for testing/maintenance).
    
    Resets all AI performance metrics and counters. This is primarily
    used for testing and maintenance purposes.
    
    **Rate Limiting:** 3 requests per hour per user
    **Permissions:** Admin role required
    
    **Returns:**
    - Success confirmation
    """
    user_id = str(current_user["_id"])
    user_role = current_user.get("role", "user")
    
    # Check admin permissions
    if user_role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "INSUFFICIENT_PERMISSIONS",
                "message": "Metrics reset requires admin permissions"
            }
        )
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"ai_metrics_reset_{user_id}",
        rate_limit_requests=3,
        rate_limit_period=3600
    )
    
    try:
        from second_brain_database.utils.ai_metrics import reset_ai_metrics
        
        # Reset metrics
        reset_ai_metrics()
        
        logger.warning("AI metrics reset by admin user %s", user_id)
        
        return JSONResponse(
            content={
                "status": "success",
                "message": "AI metrics have been reset",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "reset_by": user_id
            },
            status_code=status.HTTP_200_OK
        )
        
    except Exception as e:
        logger.error("Failed to reset AI metrics: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "METRICS_RESET_FAILED",
                "message": "Failed to reset AI metrics"
            }
        )
"""
AI Security Monitoring

This module provides real-time security monitoring and alerting
for AI orchestration operations.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
import json
import asyncio

from ....managers.logging_manager import get_logger
from ....managers.redis_manager import redis_manager
from ....config import settings
from .ai_security_manager import ai_security_manager
from .security_integration import ai_security_integration
from .config_validator import ai_security_config_validator

logger = get_logger(prefix="[AISecurityMonitoring]")


class AISecurityMonitor:
    """
    Real-time security monitoring for AI operations.
    """
    
    def __init__(self):
        self.logger = logger
        self.env_prefix = getattr(settings, "ENV_PREFIX", "dev")
        self.monitoring_enabled = getattr(settings, "AI_SECURITY_MONITORING_ENABLED", True)
        
        # Monitoring thresholds
        self.thresholds = {
            "high_error_rate": 0.1,  # 10% error rate
            "rapid_requests_per_minute": 100,
            "failed_auth_attempts": 5,
            "suspicious_patterns_per_hour": 10,
            "session_timeout_rate": 0.2,  # 20% timeout rate
            "quota_exceeded_rate": 0.05  # 5% quota exceeded rate
        }
        
        # Alert cooldown periods (seconds)
        self.alert_cooldowns = {
            "high_error_rate": 300,  # 5 minutes
            "security_breach": 60,   # 1 minute
            "quota_exceeded": 600,   # 10 minutes
            "suspicious_activity": 180  # 3 minutes
        }
    
    async def get_redis(self):
        """Get Redis connection."""
        return await redis_manager.get_redis()
    
    async def get_security_dashboard(self) -> Dict[str, Any]:
        """
        Get comprehensive security dashboard data.
        
        Returns:
            Dictionary with security metrics and status
        """
        try:
            dashboard_data = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "monitoring_enabled": self.monitoring_enabled,
                "system_status": await self._get_system_status(),
                "security_metrics": await self._get_security_metrics(),
                "threat_analysis": await self._get_threat_analysis(),
                "performance_metrics": await self._get_performance_metrics(),
                "recent_alerts": await self._get_recent_alerts(),
                "configuration_status": await self._get_configuration_status(),
                "recommendations": await self._get_security_recommendations()
            }
            
            return dashboard_data
            
        except Exception as e:
            self.logger.error("Error generating security dashboard: %s", str(e), exc_info=True)
            return {
                "error": "Failed to generate security dashboard",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    async def _get_system_status(self) -> Dict[str, Any]:
        """Get overall system security status."""
        try:
            redis_conn = await self.get_redis()
            
            # Check active sessions
            session_keys = await redis_conn.keys(f"{self.env_prefix}:ai_session:*")
            active_sessions = len(session_keys)
            
            # Check recent errors
            error_keys = await redis_conn.keys(f"{self.env_prefix}:ai_error:*")
            recent_errors = len(error_keys)
            
            # Check security violations
            violation_keys = await redis_conn.keys(f"{self.env_prefix}:ai_security_violation:*")
            security_violations = len(violation_keys)
            
            # Determine overall status
            if security_violations > 10:
                status = "CRITICAL"
            elif security_violations > 5 or recent_errors > 20:
                status = "WARNING"
            elif recent_errors > 10:
                status = "CAUTION"
            else:
                status = "HEALTHY"
            
            return {
                "overall_status": status,
                "active_sessions": active_sessions,
                "recent_errors": recent_errors,
                "security_violations": security_violations,
                "last_updated": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            self.logger.error("Error getting system status: %s", str(e))
            return {"overall_status": "UNKNOWN", "error": str(e)}
    
    async def _get_security_metrics(self) -> Dict[str, Any]:
        """Get detailed security metrics."""
        try:
            redis_conn = await self.get_redis()
            now = datetime.now(timezone.utc)
            hour_ago = now - timedelta(hours=1)
            day_ago = now - timedelta(days=1)
            
            metrics = {
                "authentication": {
                    "successful_logins_1h": 0,
                    "failed_logins_1h": 0,
                    "token_validations_1h": 0,
                    "permission_denials_1h": 0
                },
                "rate_limiting": {
                    "requests_blocked_1h": 0,
                    "quota_exceeded_1h": 0,
                    "rate_limit_violations_1h": 0
                },
                "threat_detection": {
                    "suspicious_patterns_1h": 0,
                    "injection_attempts_1h": 0,
                    "rapid_requests_1h": 0,
                    "blocked_ips_1h": 0
                },
                "sessions": {
                    "sessions_created_1h": 0,
                    "sessions_expired_1h": 0,
                    "session_timeouts_1h": 0,
                    "concurrent_sessions": 0
                }
            }
            
            # Get audit events from the last hour
            audit_keys = await redis_conn.keys(f"{self.env_prefix}:ai_audit:*")
            
            for key in audit_keys:
                try:
                    audit_data = await redis_conn.get(key)
                    if audit_data:
                        event = json.loads(audit_data)
                        event_time = datetime.fromisoformat(event.get("timestamp", ""))
                        
                        if event_time >= hour_ago:
                            event_type = event.get("event_type", "")
                            action = event.get("action", "")
                            success = event.get("success", True)
                            
                            # Categorize events
                            if event_type == "authentication":
                                if success:
                                    metrics["authentication"]["successful_logins_1h"] += 1
                                else:
                                    metrics["authentication"]["failed_logins_1h"] += 1
                            elif event_type == "permission_check" and not success:
                                metrics["authentication"]["permission_denials_1h"] += 1
                            elif event_type == "rate_limit_violation":
                                metrics["rate_limiting"]["requests_blocked_1h"] += 1
                            elif event_type == "quota_exceeded":
                                metrics["rate_limiting"]["quota_exceeded_1h"] += 1
                            elif event_type == "threat_detection":
                                metrics["threat_detection"]["suspicious_patterns_1h"] += 1
                            elif event_type == "session_management":
                                if action == "create_session":
                                    metrics["sessions"]["sessions_created_1h"] += 1
                                elif action == "session_expired":
                                    metrics["sessions"]["sessions_expired_1h"] += 1
                                    
                except Exception as e:
                    self.logger.debug("Error parsing audit event: %s", str(e))
                    continue
            
            # Get current concurrent sessions
            session_keys = await redis_conn.keys(f"{self.env_prefix}:ai_session:*")
            metrics["sessions"]["concurrent_sessions"] = len(session_keys)
            
            return metrics
            
        except Exception as e:
            self.logger.error("Error getting security metrics: %s", str(e))
            return {}
    
    async def _get_threat_analysis(self) -> Dict[str, Any]:
        """Get threat analysis and risk assessment."""
        try:
            redis_conn = await self.get_redis()
            
            # Analyze threat patterns
            threat_analysis = {
                "risk_level": "LOW",
                "active_threats": [],
                "threat_trends": {
                    "increasing": [],
                    "decreasing": [],
                    "stable": []
                },
                "geographic_analysis": {},
                "user_agent_analysis": {},
                "ip_reputation": {}
            }
            
            # Get recent security violations
            violation_keys = await redis_conn.keys(f"{self.env_prefix}:ai_security_violation:*")
            
            threat_counts = {}
            ip_counts = {}
            user_agent_counts = {}
            
            for key in violation_keys:
                try:
                    violation_data = await redis_conn.get(key)
                    if violation_data:
                        violation = json.loads(violation_data)
                        
                        # Count threat types
                        threat_type = violation.get("threat_type", "unknown")
                        threat_counts[threat_type] = threat_counts.get(threat_type, 0) + 1
                        
                        # Count IPs
                        ip_address = violation.get("ip_address", "unknown")
                        ip_counts[ip_address] = ip_counts.get(ip_address, 0) + 1
                        
                        # Count user agents
                        user_agent = violation.get("user_agent", "unknown")
                        user_agent_counts[user_agent] = user_agent_counts.get(user_agent, 0) + 1
                        
                except Exception as e:
                    self.logger.debug("Error parsing violation: %s", str(e))
                    continue
            
            # Determine risk level
            total_threats = sum(threat_counts.values())
            if total_threats > 50:
                threat_analysis["risk_level"] = "CRITICAL"
            elif total_threats > 20:
                threat_analysis["risk_level"] = "HIGH"
            elif total_threats > 5:
                threat_analysis["risk_level"] = "MEDIUM"
            
            # Identify active threats
            for threat_type, count in threat_counts.items():
                if count > 5:  # Threshold for active threat
                    threat_analysis["active_threats"].append({
                        "type": threat_type,
                        "count": count,
                        "severity": "HIGH" if count > 20 else "MEDIUM"
                    })
            
            # Top suspicious IPs
            top_ips = sorted(ip_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            threat_analysis["ip_reputation"] = {
                "suspicious_ips": [{"ip": ip, "violations": count} for ip, count in top_ips if count > 3]
            }
            
            return threat_analysis
            
        except Exception as e:
            self.logger.error("Error getting threat analysis: %s", str(e))
            return {"risk_level": "UNKNOWN", "error": str(e)}
    
    async def _get_performance_metrics(self) -> Dict[str, Any]:
        """Get AI performance and security performance metrics."""
        try:
            redis_conn = await self.get_redis()
            
            # Get performance data
            performance_keys = await redis_conn.keys(f"{self.env_prefix}:ai_performance:*")
            
            metrics = {
                "response_times": {
                    "avg_response_time_ms": 0,
                    "p95_response_time_ms": 0,
                    "p99_response_time_ms": 0
                },
                "throughput": {
                    "requests_per_minute": 0,
                    "successful_requests": 0,
                    "failed_requests": 0,
                    "error_rate": 0.0
                },
                "security_overhead": {
                    "avg_security_check_ms": 0,
                    "security_failures": 0,
                    "security_success_rate": 0.0
                }
            }
            
            # Calculate metrics from performance data
            response_times = []
            security_times = []
            total_requests = 0
            failed_requests = 0
            
            for key in performance_keys:
                try:
                    perf_data = await redis_conn.get(key)
                    if perf_data:
                        data = json.loads(perf_data)
                        
                        if "response_time_ms" in data:
                            response_times.append(data["response_time_ms"])
                        
                        if "security_check_ms" in data:
                            security_times.append(data["security_check_ms"])
                        
                        total_requests += 1
                        if not data.get("success", True):
                            failed_requests += 1
                            
                except Exception as e:
                    self.logger.debug("Error parsing performance data: %s", str(e))
                    continue
            
            # Calculate averages and percentiles
            if response_times:
                response_times.sort()
                metrics["response_times"]["avg_response_time_ms"] = sum(response_times) / len(response_times)
                metrics["response_times"]["p95_response_time_ms"] = response_times[int(len(response_times) * 0.95)]
                metrics["response_times"]["p99_response_time_ms"] = response_times[int(len(response_times) * 0.99)]
            
            if security_times:
                metrics["security_overhead"]["avg_security_check_ms"] = sum(security_times) / len(security_times)
            
            if total_requests > 0:
                metrics["throughput"]["successful_requests"] = total_requests - failed_requests
                metrics["throughput"]["failed_requests"] = failed_requests
                metrics["throughput"]["error_rate"] = failed_requests / total_requests
                metrics["security_overhead"]["security_success_rate"] = (total_requests - failed_requests) / total_requests
            
            return metrics
            
        except Exception as e:
            self.logger.error("Error getting performance metrics: %s", str(e))
            return {}
    
    async def _get_recent_alerts(self) -> List[Dict[str, Any]]:
        """Get recent security alerts."""
        try:
            redis_conn = await self.get_redis()
            
            # Get recent alerts
            alert_keys = await redis_conn.keys(f"{self.env_prefix}:ai_security_alert:*")
            alerts = []
            
            for key in alert_keys:
                try:
                    alert_data = await redis_conn.get(key)
                    if alert_data:
                        alert = json.loads(alert_data)
                        alerts.append(alert)
                except Exception as e:
                    self.logger.debug("Error parsing alert: %s", str(e))
                    continue
            
            # Sort by timestamp (most recent first)
            alerts.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            
            return alerts[:20]  # Return last 20 alerts
            
        except Exception as e:
            self.logger.error("Error getting recent alerts: %s", str(e))
            return []
    
    async def _get_configuration_status(self) -> Dict[str, Any]:
        """Get security configuration validation status."""
        try:
            # Run configuration validation
            validation_results = await ai_security_config_validator.validate_configuration()
            
            return {
                "last_validation": validation_results.get("validation_timestamp"),
                "security_score": validation_results.get("security_score", 0),
                "assessment": validation_results.get("assessment", "UNKNOWN"),
                "critical_issues": len(validation_results.get("critical_issues", [])),
                "warnings": validation_results.get("results_by_level", {}).get("WARNING", 0),
                "recommendations_count": len(validation_results.get("recommendations", []))
            }
            
        except Exception as e:
            self.logger.error("Error getting configuration status: %s", str(e))
            return {"error": str(e)}
    
    async def _get_security_recommendations(self) -> List[Dict[str, Any]]:
        """Get security recommendations based on current metrics."""
        try:
            recommendations = []
            
            # Get current metrics for analysis
            metrics = await self._get_security_metrics()
            threat_analysis = await self._get_threat_analysis()
            
            # Analyze authentication metrics
            auth_metrics = metrics.get("authentication", {})
            failed_logins = auth_metrics.get("failed_logins_1h", 0)
            
            if failed_logins > 20:
                recommendations.append({
                    "priority": "HIGH",
                    "category": "authentication",
                    "title": "High Failed Login Rate",
                    "description": f"{failed_logins} failed login attempts in the last hour",
                    "recommendation": "Consider implementing account lockout or CAPTCHA",
                    "action": "review_auth_logs"
                })
            
            # Analyze threat levels
            risk_level = threat_analysis.get("risk_level", "LOW")
            if risk_level in ["HIGH", "CRITICAL"]:
                recommendations.append({
                    "priority": "CRITICAL",
                    "category": "threat_detection",
                    "title": f"{risk_level} Risk Level Detected",
                    "description": "Multiple security threats detected",
                    "recommendation": "Review threat analysis and consider blocking suspicious IPs",
                    "action": "investigate_threats"
                })
            
            # Analyze rate limiting
            rate_metrics = metrics.get("rate_limiting", {})
            blocked_requests = rate_metrics.get("requests_blocked_1h", 0)
            
            if blocked_requests > 100:
                recommendations.append({
                    "priority": "MEDIUM",
                    "category": "rate_limiting",
                    "title": "High Rate Limiting Activity",
                    "description": f"{blocked_requests} requests blocked in the last hour",
                    "recommendation": "Review rate limiting thresholds and user patterns",
                    "action": "adjust_rate_limits"
                })
            
            return recommendations
            
        except Exception as e:
            self.logger.error("Error generating recommendations: %s", str(e))
            return []
    
    async def check_security_thresholds(self) -> List[Dict[str, Any]]:
        """
        Check if any security thresholds are exceeded and generate alerts.
        
        Returns:
            List of alerts generated
        """
        try:
            alerts_generated = []
            
            if not self.monitoring_enabled:
                return alerts_generated
            
            # Get current metrics
            metrics = await self._get_security_metrics()
            
            # Check error rate threshold
            throughput = metrics.get("throughput", {})
            error_rate = throughput.get("error_rate", 0)
            
            if error_rate > self.thresholds["high_error_rate"]:
                alert = await self._generate_threshold_alert(
                    "high_error_rate",
                    f"Error rate ({error_rate:.2%}) exceeds threshold ({self.thresholds['high_error_rate']:.2%})",
                    "HIGH",
                    {"error_rate": error_rate, "threshold": self.thresholds["high_error_rate"]}
                )
                if alert:
                    alerts_generated.append(alert)
            
            # Check failed authentication attempts
            auth_metrics = metrics.get("authentication", {})
            failed_logins = auth_metrics.get("failed_logins_1h", 0)
            
            if failed_logins > self.thresholds["failed_auth_attempts"]:
                alert = await self._generate_threshold_alert(
                    "failed_auth_attempts",
                    f"Failed authentication attempts ({failed_logins}) exceed threshold ({self.thresholds['failed_auth_attempts']})",
                    "MEDIUM",
                    {"failed_attempts": failed_logins, "threshold": self.thresholds["failed_auth_attempts"]}
                )
                if alert:
                    alerts_generated.append(alert)
            
            return alerts_generated
            
        except Exception as e:
            self.logger.error("Error checking security thresholds: %s", str(e))
            return []
    
    async def _generate_threshold_alert(
        self,
        alert_type: str,
        message: str,
        severity: str,
        details: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Generate a threshold-based alert with cooldown."""
        try:
            redis_conn = await self.get_redis()
            
            # Check cooldown
            cooldown_key = f"{self.env_prefix}:alert_cooldown:{alert_type}"
            if await redis_conn.exists(cooldown_key):
                return None  # Still in cooldown
            
            # Generate alert
            alert = {
                "alert_id": f"threshold_{alert_type}_{int(datetime.now().timestamp())}",
                "alert_type": alert_type,
                "severity": severity,
                "message": message,
                "details": details,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "component": "ai_security_monitoring"
            }
            
            # Store alert
            await ai_security_integration.generate_security_alert(
                alert_type, severity, details
            )
            
            # Set cooldown
            cooldown_period = self.alert_cooldowns.get(alert_type, 300)
            await redis_conn.setex(cooldown_key, cooldown_period, "1")
            
            self.logger.warning(
                "Security threshold alert: %s - %s", alert_type, message
            )
            
            return alert
            
        except Exception as e:
            self.logger.error("Error generating threshold alert: %s", str(e))
            return None


# Global instance
ai_security_monitor = AISecurityMonitor()
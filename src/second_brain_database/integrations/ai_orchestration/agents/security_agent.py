"""
Security & Admin Agent

This agent specializes in security monitoring and administrative operations
using existing admin tools and security systems.

Capabilities:
- Security monitoring and threat detection
- System health monitoring and diagnostics
- User management and administrative operations
- Audit trail analysis and compliance reporting
- Performance monitoring and optimization recommendations
"""

from typing import Dict, Any, List, Optional, AsyncGenerator
import json

from .base_agent import BaseAgent
from ..models.events import AIEvent, EventType
from ....integrations.mcp.context import MCPUserContext
from ....managers.logging_manager import get_logger

logger = get_logger(prefix="[SecurityAgent]")


class SecurityAgent(BaseAgent):
    """
    AI agent specialized in security monitoring and administrative operations.
    
    Integrates with existing admin_tools MCP tools and SecurityManager
    to provide natural language interface for security and admin operations.
    """
    
    def __init__(self, orchestrator=None):
        super().__init__("security", orchestrator)
        self.capabilities = [
            {
                "name": "security_monitoring",
                "description": "Monitor security events and threats",
                "required_permissions": ["admin:security", "security:monitor"]
            },
            {
                "name": "system_health",
                "description": "Monitor system health and performance",
                "required_permissions": ["admin:health", "system:monitor"]
            },
            {
                "name": "user_management",
                "description": "Manage users and administrative operations",
                "required_permissions": ["admin:users", "user:manage"]
            },
            {
                "name": "audit_analysis",
                "description": "Analyze audit trails and compliance",
                "required_permissions": ["admin:audit", "audit:view"]
            },
            {
                "name": "performance_monitoring",
                "description": "Monitor and optimize system performance",
                "required_permissions": ["admin:performance", "system:optimize"]
            }
        ]
    
    @property
    def agent_name(self) -> str:
        return "Security & Admin Assistant"
    
    @property
    def agent_description(self) -> str:
        return "I help monitor security, manage system health, handle administrative tasks, and ensure compliance with security policies."
    
    async def handle_request(
        self, 
        session_id: str, 
        request: str, 
        user_context: MCPUserContext,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[AIEvent, None]:
        """Handle security and admin requests with streaming responses."""
        try:
            # Check if user has admin permissions
            if not await self.validate_admin_access(user_context):
                yield await self.emit_error(
                    session_id, 
                    "Access denied. Administrative privileges required for security operations."
                )
                return
            
            # Add request to conversation history
            self.add_to_conversation_history(session_id, "user", request)
            
            # Classify the security task
            task_classification = await self.classify_security_task(request)
            task_type = task_classification.get("task_type", "general")
            
            self.logger.info(
                "Processing security request for session %s: %s (classified as %s)",
                session_id, request[:100], task_type
            )
            
            # Route to appropriate security operation
            if task_type == "security_monitoring":
                async for event in self.security_monitoring_workflow(session_id, request, user_context):
                    yield event
            elif task_type == "system_health":
                async for event in self.system_health_workflow(session_id, request, user_context):
                    yield event
            elif task_type == "user_management":
                async for event in self.user_management_workflow(session_id, request, user_context):
                    yield event
            elif task_type == "audit_analysis":
                async for event in self.audit_analysis_workflow(session_id, request, user_context):
                    yield event
            elif task_type == "performance_monitoring":
                async for event in self.performance_monitoring_workflow(session_id, request, user_context):
                    yield event
            elif task_type == "system_status":
                async for event in self.system_status_workflow(session_id, request, user_context):
                    yield event
            else:
                # General security assistance
                async for event in self.general_security_assistance(session_id, request, user_context):
                    yield event
                    
        except Exception as e:
            self.logger.error("Security request handling failed: %s", e)
            yield await self.emit_error(session_id, f"I encountered an issue processing your security request: {str(e)}")
    
    async def get_capabilities(self, user_context: MCPUserContext) -> List[Dict[str, Any]]:
        """Get security capabilities available to the user."""
        available_capabilities = []
        
        # Check admin access first
        if not await self.validate_admin_access(user_context):
            return []
        
        for capability in self.capabilities:
            required_perms = capability.get("required_permissions", [])
            if await self.validate_permissions(user_context, required_perms):
                available_capabilities.append(capability)
        
        return available_capabilities
    
    async def validate_admin_access(self, user_context: MCPUserContext) -> bool:
        """Validate that the user has administrative access."""
        # Check if user is admin or has admin permissions
        if user_context.role == "admin":
            return True
        
        admin_permissions = [
            "admin:security", "admin:health", "admin:users", 
            "admin:audit", "admin:performance", "system:admin"
        ]
        
        return user_context.has_any_permission(admin_permissions)
    
    async def classify_security_task(self, request: str) -> Dict[str, Any]:
        """Classify the type of security task from the request."""
        request_lower = request.lower()
        
        # Security monitoring patterns
        if any(phrase in request_lower for phrase in [
            "security alert", "threat", "suspicious", "attack", "breach", "intrusion"
        ]):
            return {"task_type": "security_monitoring", "confidence": 0.9}
        
        # System health patterns
        if any(phrase in request_lower for phrase in [
            "system health", "health check", "system status", "uptime", "availability"
        ]):
            return {"task_type": "system_health", "confidence": 0.9}
        
        # User management patterns
        if any(phrase in request_lower for phrase in [
            "user management", "manage users", "user account", "disable user", "user permissions"
        ]):
            return {"task_type": "user_management", "confidence": 0.9}
        
        # Audit analysis patterns
        if any(phrase in request_lower for phrase in [
            "audit", "compliance", "log analysis", "audit trail", "security logs"
        ]):
            return {"task_type": "audit_analysis", "confidence": 0.8}
        
        # Performance monitoring patterns
        if any(phrase in request_lower for phrase in [
            "performance", "metrics", "monitoring", "optimization", "resource usage"
        ]):
            return {"task_type": "performance_monitoring", "confidence": 0.8}
        
        # System status patterns
        if any(phrase in request_lower for phrase in [
            "status", "overview", "dashboard", "summary", "report"
        ]):
            return {"task_type": "system_status", "confidence": 0.7}
        
        return {"task_type": "general", "confidence": 0.5}
    
    async def security_monitoring_workflow(
        self, 
        session_id: str, 
        request: str, 
        user_context: MCPUserContext
    ) -> AsyncGenerator[AIEvent, None]:
        """Handle security monitoring workflow."""
        yield await self.emit_status(session_id, EventType.THINKING, "Analyzing security status...")
        
        try:
            # Get security monitoring data
            result = await self.execute_mcp_tool(
                session_id,
                "get_security_status",
                {"admin_user_id": user_context.user_id},
                user_context
            )
            
            if result and not result.get("error"):
                security_data = result.get("security_status", {})
                
                response = "**🔒 Security Status Report:**\n\n"
                
                # Threat level
                threat_level = security_data.get("threat_level", "unknown")
                threat_icons = {
                    "low": "🟢",
                    "medium": "🟡", 
                    "high": "🟠",
                    "critical": "🔴"
                }
                threat_icon = threat_icons.get(threat_level, "❓")
                
                response += f"**Threat Level:** {threat_icon} {threat_level.upper()}\n\n"
                
                # Recent security events
                recent_events = security_data.get("recent_events", [])
                if recent_events:
                    response += f"**Recent Security Events ({len(recent_events)}):**\n"
                    for event in recent_events[:5]:  # Show last 5 events
                        event_type = event.get("type", "unknown")
                        severity = event.get("severity", "info")
                        timestamp = event.get("timestamp", "unknown")
                        description = event.get("description", "No description")
                        
                        severity_icons = {
                            "info": "ℹ️",
                            "warning": "⚠️",
                            "error": "❌",
                            "critical": "🚨"
                        }
                        severity_icon = severity_icons.get(severity, "❓")
                        
                        response += f"  {severity_icon} **{event_type}** - {timestamp}\n"
                        response += f"     {description}\n\n"
                else:
                    response += "**Recent Security Events:** No recent events detected ✅\n\n"
                
                # Active security measures
                active_measures = security_data.get("active_measures", {})
                response += "**Active Security Measures:**\n"
                response += f"• Rate Limiting: {'✅ Active' if active_measures.get('rate_limiting') else '❌ Inactive'}\n"
                response += f"• IP Monitoring: {'✅ Active' if active_measures.get('ip_monitoring') else '❌ Inactive'}\n"
                response += f"• Audit Logging: {'✅ Active' if active_measures.get('audit_logging') else '❌ Inactive'}\n"
                response += f"• 2FA Enforcement: {'✅ Active' if active_measures.get('twofa_enforcement') else '❌ Inactive'}\n\n"
                
                # Recommendations
                recommendations = security_data.get("recommendations", [])
                if recommendations:
                    response += "**Security Recommendations:**\n"
                    for rec in recommendations:
                        response += f"• {rec}\n"
                
                yield await self.emit_response(session_id, response)
            else:
                yield await self.emit_response(
                    session_id,
                    "I couldn't retrieve security status information right now. Please try again later."
                )
                
        except Exception as e:
            self.logger.error("Security monitoring workflow failed: %s", e)
            yield await self.emit_error(session_id, f"Security monitoring failed: {str(e)}")
    
    async def system_health_workflow(
        self, 
        session_id: str, 
        request: str, 
        user_context: MCPUserContext
    ) -> AsyncGenerator[AIEvent, None]:
        """Handle system health monitoring workflow."""
        yield await self.emit_status(session_id, EventType.THINKING, "Checking system health...")
        
        try:
            # Get system health data
            result = await self.execute_mcp_tool(
                session_id,
                "get_system_health",
                {"admin_user_id": user_context.user_id},
                user_context
            )
            
            if result and not result.get("error"):
                health_data = result.get("system_health", {})
                
                response = "**🏥 System Health Report:**\n\n"
                
                # Overall status
                overall_status = health_data.get("overall_status", "unknown")
                status_icons = {
                    "healthy": "🟢",
                    "warning": "🟡",
                    "critical": "🔴",
                    "unknown": "❓"
                }
                status_icon = status_icons.get(overall_status, "❓")
                
                response += f"**Overall Status:** {status_icon} {overall_status.upper()}\n\n"
                
                # Service status
                services = health_data.get("services", {})
                if services:
                    response += "**Service Status:**\n"
                    for service_name, service_data in services.items():
                        status = service_data.get("status", "unknown")
                        uptime = service_data.get("uptime", "unknown")
                        
                        service_icon = "🟢" if status == "running" else "🔴" if status == "down" else "🟡"
                        response += f"  {service_icon} **{service_name}**: {status} (uptime: {uptime})\n"
                    response += "\n"
                
                # Resource usage
                resources = health_data.get("resources", {})
                if resources:
                    response += "**Resource Usage:**\n"
                    
                    cpu_usage = resources.get("cpu_usage", 0)
                    memory_usage = resources.get("memory_usage", 0)
                    disk_usage = resources.get("disk_usage", 0)
                    
                    response += f"• **CPU Usage:** {cpu_usage}%\n"
                    response += f"• **Memory Usage:** {memory_usage}%\n"
                    response += f"• **Disk Usage:** {disk_usage}%\n\n"
                
                # Database status
                database = health_data.get("database", {})
                if database:
                    db_status = database.get("status", "unknown")
                    connections = database.get("active_connections", 0)
                    response_time = database.get("avg_response_time", 0)
                    
                    db_icon = "🟢" if db_status == "healthy" else "🔴"
                    response += f"**Database:** {db_icon} {db_status}\n"
                    response += f"• Active Connections: {connections}\n"
                    response += f"• Avg Response Time: {response_time}ms\n\n"
                
                # Recent issues
                issues = health_data.get("recent_issues", [])
                if issues:
                    response += f"**Recent Issues ({len(issues)}):**\n"
                    for issue in issues[:3]:  # Show last 3 issues
                        issue_type = issue.get("type", "unknown")
                        severity = issue.get("severity", "info")
                        timestamp = issue.get("timestamp", "unknown")
                        description = issue.get("description", "No description")
                        
                        response += f"  ⚠️ **{issue_type}** ({severity}) - {timestamp}\n"
                        response += f"     {description}\n\n"
                else:
                    response += "**Recent Issues:** No issues detected ✅\n"
                
                yield await self.emit_response(session_id, response)
            else:
                yield await self.emit_response(
                    session_id,
                    "I couldn't retrieve system health information right now. Please try again later."
                )
                
        except Exception as e:
            self.logger.error("System health workflow failed: %s", e)
            yield await self.emit_error(session_id, f"System health check failed: {str(e)}")
    
    async def user_management_workflow(
        self, 
        session_id: str, 
        request: str, 
        user_context: MCPUserContext
    ) -> AsyncGenerator[AIEvent, None]:
        """Handle user management workflow."""
        yield await self.emit_status(session_id, EventType.THINKING, "Processing user management request...")
        
        try:
            # Determine user management operation
            operation = await self.classify_user_operation(request)
            
            if operation == "list_users":
                # Get user list
                result = await self.execute_mcp_tool(
                    session_id,
                    "get_user_list",
                    {
                        "admin_user_id": user_context.user_id,
                        "limit": 20
                    },
                    user_context
                )
                
                if result and not result.get("error"):
                    users = result.get("users", [])
                    
                    response = f"**👥 User Management ({len(users)} users):**\n\n"
                    
                    for user in users:
                        username = user.get("username", "Unknown")
                        email = user.get("email", "No email")
                        role = user.get("role", "user")
                        status = user.get("status", "active")
                        last_login = user.get("last_login", "Never")
                        
                        status_icon = "🟢" if status == "active" else "🔴" if status == "disabled" else "🟡"
                        
                        response += f"{status_icon} **{username}** ({role})\n"
                        response += f"   📧 {email}\n"
                        response += f"   🕐 Last login: {last_login}\n\n"
                    
                    response += "I can help you manage any of these users. What would you like to do?"
                    
                    yield await self.emit_response(session_id, response)
                else:
                    yield await self.emit_response(
                        session_id,
                        "I couldn't retrieve the user list right now. Please try again later."
                    )
            
            elif operation == "user_stats":
                # Get user statistics
                result = await self.execute_mcp_tool(
                    session_id,
                    "get_user_statistics",
                    {"admin_user_id": user_context.user_id},
                    user_context
                )
                
                if result and not result.get("error"):
                    stats = result.get("statistics", {})
                    
                    response = "**📊 User Statistics:**\n\n"
                    
                    total_users = stats.get("total_users", 0)
                    active_users = stats.get("active_users", 0)
                    new_users_today = stats.get("new_users_today", 0)
                    new_users_week = stats.get("new_users_week", 0)
                    
                    response += f"• **Total Users:** {total_users}\n"
                    response += f"• **Active Users:** {active_users}\n"
                    response += f"• **New Today:** {new_users_today}\n"
                    response += f"• **New This Week:** {new_users_week}\n\n"
                    
                    # User roles breakdown
                    roles = stats.get("user_roles", {})
                    if roles:
                        response += "**User Roles:**\n"
                        for role, count in roles.items():
                            response += f"• {role.title()}: {count}\n"
                        response += "\n"
                    
                    # Recent activity
                    recent_activity = stats.get("recent_activity", {})
                    if recent_activity:
                        response += "**Recent Activity:**\n"
                        logins_today = recent_activity.get("logins_today", 0)
                        registrations_today = recent_activity.get("registrations_today", 0)
                        response += f"• Logins Today: {logins_today}\n"
                        response += f"• Registrations Today: {registrations_today}\n"
                    
                    yield await self.emit_response(session_id, response)
                else:
                    yield await self.emit_response(
                        session_id,
                        "I couldn't retrieve user statistics right now. Please try again later."
                    )
            
            else:
                yield await self.emit_response(
                    session_id,
                    "I can help you list users, view user statistics, or manage specific user accounts. What would you like to do?"
                )
                
        except Exception as e:
            self.logger.error("User management workflow failed: %s", e)
            yield await self.emit_error(session_id, f"User management failed: {str(e)}")
    
    async def audit_analysis_workflow(
        self, 
        session_id: str, 
        request: str, 
        user_context: MCPUserContext
    ) -> AsyncGenerator[AIEvent, None]:
        """Handle audit analysis workflow."""
        yield await self.emit_status(session_id, EventType.THINKING, "Analyzing audit logs...")
        
        try:
            # Get audit analysis
            result = await self.execute_mcp_tool(
                session_id,
                "get_audit_analysis",
                {
                    "admin_user_id": user_context.user_id,
                    "time_range": "24h"
                },
                user_context
            )
            
            if result and not result.get("error"):
                audit_data = result.get("audit_analysis", {})
                
                response = "**📋 Audit Analysis (Last 24 Hours):**\n\n"
                
                # Summary statistics
                summary = audit_data.get("summary", {})
                total_events = summary.get("total_events", 0)
                unique_users = summary.get("unique_users", 0)
                failed_logins = summary.get("failed_logins", 0)
                
                response += f"• **Total Events:** {total_events}\n"
                response += f"• **Unique Users:** {unique_users}\n"
                response += f"• **Failed Logins:** {failed_logins}\n\n"
                
                # Top events by type
                event_types = audit_data.get("event_types", {})
                if event_types:
                    response += "**Event Types:**\n"
                    for event_type, count in sorted(event_types.items(), key=lambda x: x[1], reverse=True)[:5]:
                        response += f"• {event_type}: {count}\n"
                    response += "\n"
                
                # Suspicious activities
                suspicious = audit_data.get("suspicious_activities", [])
                if suspicious:
                    response += f"**🚨 Suspicious Activities ({len(suspicious)}):**\n"
                    for activity in suspicious[:5]:
                        activity_type = activity.get("type", "unknown")
                        user_id = activity.get("user_id", "unknown")
                        timestamp = activity.get("timestamp", "unknown")
                        description = activity.get("description", "No description")
                        
                        response += f"  ⚠️ **{activity_type}** - {timestamp}\n"
                        response += f"     User: {user_id}\n"
                        response += f"     {description}\n\n"
                else:
                    response += "**Suspicious Activities:** None detected ✅\n\n"
                
                # Compliance status
                compliance = audit_data.get("compliance", {})
                if compliance:
                    response += "**Compliance Status:**\n"
                    for check, status in compliance.items():
                        status_icon = "✅" if status else "❌"
                        response += f"• {check}: {status_icon}\n"
                
                yield await self.emit_response(session_id, response)
            else:
                yield await self.emit_response(
                    session_id,
                    "I couldn't retrieve audit analysis right now. Please try again later."
                )
                
        except Exception as e:
            self.logger.error("Audit analysis workflow failed: %s", e)
            yield await self.emit_error(session_id, f"Audit analysis failed: {str(e)}")
    
    async def performance_monitoring_workflow(
        self, 
        session_id: str, 
        request: str, 
        user_context: MCPUserContext
    ) -> AsyncGenerator[AIEvent, None]:
        """Handle performance monitoring workflow."""
        yield await self.emit_status(session_id, EventType.THINKING, "Analyzing system performance...")
        
        try:
            # Get performance metrics
            result = await self.execute_mcp_tool(
                session_id,
                "get_performance_metrics",
                {"admin_user_id": user_context.user_id},
                user_context
            )
            
            if result and not result.get("error"):
                performance_data = result.get("performance_metrics", {})
                
                response = "**📈 Performance Monitoring Report:**\n\n"
                
                # Response times
                response_times = performance_data.get("response_times", {})
                if response_times:
                    response += "**Response Times:**\n"
                    avg_response = response_times.get("average", 0)
                    p95_response = response_times.get("p95", 0)
                    p99_response = response_times.get("p99", 0)
                    
                    response += f"• Average: {avg_response}ms\n"
                    response += f"• 95th Percentile: {p95_response}ms\n"
                    response += f"• 99th Percentile: {p99_response}ms\n\n"
                
                # Throughput
                throughput = performance_data.get("throughput", {})
                if throughput:
                    response += "**Throughput:**\n"
                    requests_per_second = throughput.get("requests_per_second", 0)
                    requests_per_minute = throughput.get("requests_per_minute", 0)
                    
                    response += f"• Requests/Second: {requests_per_second}\n"
                    response += f"• Requests/Minute: {requests_per_minute}\n\n"
                
                # Error rates
                error_rates = performance_data.get("error_rates", {})
                if error_rates:
                    response += "**Error Rates:**\n"
                    error_rate_percent = error_rates.get("error_rate_percent", 0)
                    total_errors = error_rates.get("total_errors", 0)
                    
                    response += f"• Error Rate: {error_rate_percent}%\n"
                    response += f"• Total Errors: {total_errors}\n\n"
                
                # Resource utilization
                resources = performance_data.get("resource_utilization", {})
                if resources:
                    response += "**Resource Utilization:**\n"
                    cpu_avg = resources.get("cpu_average", 0)
                    memory_avg = resources.get("memory_average", 0)
                    disk_io = resources.get("disk_io", 0)
                    
                    response += f"• CPU Average: {cpu_avg}%\n"
                    response += f"• Memory Average: {memory_avg}%\n"
                    response += f"• Disk I/O: {disk_io} MB/s\n\n"
                
                # Performance recommendations
                recommendations = performance_data.get("recommendations", [])
                if recommendations:
                    response += "**Performance Recommendations:**\n"
                    for rec in recommendations:
                        response += f"• {rec}\n"
                
                yield await self.emit_response(session_id, response)
            else:
                yield await self.emit_response(
                    session_id,
                    "I couldn't retrieve performance metrics right now. Please try again later."
                )
                
        except Exception as e:
            self.logger.error("Performance monitoring workflow failed: %s", e)
            yield await self.emit_error(session_id, f"Performance monitoring failed: {str(e)}")
    
    async def system_status_workflow(
        self, 
        session_id: str, 
        request: str, 
        user_context: MCPUserContext
    ) -> AsyncGenerator[AIEvent, None]:
        """Handle system status overview workflow."""
        yield await self.emit_status(session_id, EventType.THINKING, "Getting system overview...")
        
        try:
            # Get comprehensive system status
            result = await self.execute_mcp_tool(
                session_id,
                "get_system_overview",
                {"admin_user_id": user_context.user_id},
                user_context
            )
            
            if result and not result.get("error"):
                system_data = result.get("system_overview", {})
                
                response = "**🖥️ System Status Overview:**\n\n"
                
                # Overall health
                overall_health = system_data.get("overall_health", "unknown")
                health_icon = "🟢" if overall_health == "healthy" else "🟡" if overall_health == "warning" else "🔴"
                
                response += f"**System Health:** {health_icon} {overall_health.upper()}\n\n"
                
                # Quick stats
                stats = system_data.get("quick_stats", {})
                if stats:
                    response += "**Quick Stats:**\n"
                    uptime = stats.get("uptime", "unknown")
                    active_users = stats.get("active_users", 0)
                    total_requests = stats.get("total_requests_today", 0)
                    avg_response_time = stats.get("avg_response_time", 0)
                    
                    response += f"• Uptime: {uptime}\n"
                    response += f"• Active Users: {active_users}\n"
                    response += f"• Requests Today: {total_requests}\n"
                    response += f"• Avg Response: {avg_response_time}ms\n\n"
                
                # Service status summary
                services_summary = system_data.get("services_summary", {})
                if services_summary:
                    response += "**Services:**\n"
                    running = services_summary.get("running", 0)
                    total = services_summary.get("total", 0)
                    
                    response += f"• Running: {running}/{total}\n"
                    
                    if running < total:
                        failed_services = services_summary.get("failed_services", [])
                        response += f"• Failed: {', '.join(failed_services)}\n"
                    response += "\n"
                
                # Recent alerts
                alerts = system_data.get("recent_alerts", [])
                if alerts:
                    response += f"**Recent Alerts ({len(alerts)}):**\n"
                    for alert in alerts[:3]:
                        alert_type = alert.get("type", "unknown")
                        severity = alert.get("severity", "info")
                        timestamp = alert.get("timestamp", "unknown")
                        
                        severity_icons = {
                            "info": "ℹ️",
                            "warning": "⚠️",
                            "error": "❌",
                            "critical": "🚨"
                        }
                        severity_icon = severity_icons.get(severity, "❓")
                        
                        response += f"  {severity_icon} {alert_type} - {timestamp}\n"
                    response += "\n"
                else:
                    response += "**Recent Alerts:** No alerts ✅\n\n"
                
                response += "Need more details? Ask me about specific areas like security, performance, or user management."
                
                yield await self.emit_response(session_id, response)
            else:
                yield await self.emit_response(
                    session_id,
                    "I couldn't retrieve system status right now. Please try again later."
                )
                
        except Exception as e:
            self.logger.error("System status workflow failed: %s", e)
            yield await self.emit_error(session_id, f"System status check failed: {str(e)}")
    
    async def general_security_assistance(
        self, 
        session_id: str, 
        request: str, 
        user_context: MCPUserContext
    ) -> AsyncGenerator[AIEvent, None]:
        """Handle general security assistance requests."""
        try:
            # Load user context for personalized response
            context = await self.load_user_context(user_context)
            
            # Emit thinking status
            yield await self.emit_status(session_id, EventType.THINKING, "Analyzing security status...")
            
            # Create a helpful response directly
            response = f"""Hello {context.get('username', 'there')}! I'm your Security & Admin Assistant AI. 🔒

**Security Status**: System is operating securely with active monitoring.

I can help you with:

🛡️ **Security Monitoring**
- Real-time threat detection and analysis
- Security dashboard and alerts
- Suspicious activity monitoring

📊 **System Health**
- Performance monitoring and diagnostics
- System status and uptime tracking
- Resource utilization analysis

👥 **User Management**
- User access control and permissions
- Account security reviews
- Authentication management

📋 **Audit & Compliance**
- Security audit trail analysis
- Compliance reporting and tracking
- Activity logging and review

⚙️ **Administrative Operations**
- System configuration management
- Security policy enforcement
- Administrative task automation

🔍 **Security Analysis**
- Risk assessment and mitigation
- Security incident investigation
- Vulnerability management

How can I assist you with security and administrative tasks today?"""

            # Emit the response
            yield await self.emit_response(session_id, response)
            
        except Exception as e:
            self.logger.error("General security assistance failed: %s", e)
            yield await self.emit_error(session_id, f"I encountered an issue: {str(e)}")
    
    # Helper methods for extracting information from requests
    
    async def classify_user_operation(self, request: str) -> str:
        """Classify the type of user management operation."""
        request_lower = request.lower()
        
        if any(word in request_lower for word in ["list users", "show users", "user list"]):
            return "list_users"
        elif any(word in request_lower for word in ["user stats", "user statistics", "user metrics"]):
            return "user_stats"
        elif any(word in request_lower for word in ["disable user", "block user", "suspend"]):
            return "disable_user"
        elif any(word in request_lower for word in ["enable user", "unblock user", "activate"]):
            return "enable_user"
        else:
            return "general"
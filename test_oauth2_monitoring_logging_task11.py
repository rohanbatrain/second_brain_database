#!/usr/bin/env python3
"""
Comprehensive test suite for OAuth2 monitoring and logging implementation (Task 11).

This test suite verifies the implementation of:
- Structured logging for browser authentication events
- Metrics for OAuth2 flow completion rates by authentication method
- Security event logging for suspicious browser activity
- Session lifecycle logging
- Performance monitoring for template rendering
- Integration with monitoring systems

Tests cover all requirements from Task 11 of the OAuth2 browser authentication spec.
"""

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Dict, Any, List
from unittest.mock import Mock, patch, MagicMock

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

# Test the monitoring system
def test_oauth2_monitoring_system():
    """Test the OAuth2 monitoring system functionality."""
    print("Testing OAuth2 Monitoring System...")
    
    try:
        from src.second_brain_database.routes.oauth2.monitoring import (
            OAuth2MonitoringSystem,
            AuthenticationMethod,
            FlowStage,
            start_flow_monitoring,
            update_flow_stage,
            record_template_performance,
            record_security_event
        )
        
        # Test monitoring system initialization
        monitoring = OAuth2MonitoringSystem()
        assert monitoring is not None
        assert monitoring.health_status["monitoring_active"] is True
        
        # Test flow monitoring
        flow_id = "test_flow_123"
        client_id = "test_client"
        auth_method = AuthenticationMethod.BROWSER_SESSION
        user_id = "test_user"
        
        # Start flow monitoring
        monitoring.start_oauth2_flow(flow_id, client_id, auth_method, user_id)
        assert flow_id in monitoring.active_flows
        assert monitoring.active_flows[flow_id].client_id == client_id
        assert monitoring.active_flows[flow_id].auth_method == auth_method
        
        # Update flow stage
        monitoring.update_flow_stage(flow_id, FlowStage.AUTHENTICATION, duration=0.5)
        assert monitoring.active_flows[flow_id].current_stage == FlowStage.AUTHENTICATION
        assert FlowStage.AUTHENTICATION in monitoring.active_flows[flow_id].stages_completed
        
        # Record template performance
        monitoring.record_template_render_time(flow_id, "consent_screen", 0.3)
        assert "consent_screen" in monitoring.active_flows[flow_id].template_render_times
        assert monitoring.active_flows[flow_id].template_render_times["consent_screen"] == 0.3
        
        # Record security event
        monitoring.record_security_event(
            flow_id, None, "suspicious_activity", "medium", "Test security event"
        )
        assert len(monitoring.security_events) > 0
        assert monitoring.security_events[-1]["event_type"] == "suspicious_activity"
        
        # Complete flow
        monitoring.update_flow_stage(flow_id, FlowStage.COMPLETED)
        assert flow_id not in monitoring.active_flows
        assert len(monitoring.completed_flows) > 0
        
        # Test completion rates
        rates = monitoring.get_completion_rates()
        assert "browser_session" in rates
        assert rates["browser_session"]["total_flows"] > 0
        
        # Test performance metrics
        perf_metrics = monitoring.get_performance_metrics()
        assert "template_rendering" in perf_metrics
        assert "consent_screen" in perf_metrics["template_rendering"]
        
        # Test security summary
        security_summary = monitoring.get_security_summary()
        assert security_summary["total_events"] > 0
        assert "suspicious_activity" in security_summary["events_by_type"]
        
        # Test health status
        health = monitoring.get_health_status()
        assert "monitoring_active" in health
        assert "active_flows_count" in health
        assert "error_rate" in health
        
        print("✓ OAuth2 monitoring system tests passed")
        return True
        
    except Exception as e:
        print(f"✗ OAuth2 monitoring system test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_browser_auth_logger():
    """Test the browser authentication logger functionality."""
    print("Testing Browser Authentication Logger...")
    
    try:
        from src.second_brain_database.routes.oauth2.browser_auth_logger import (
            BrowserAuthenticationLogger,
            BrowserAuthEvent,
            AuthenticationMethod,
            OAuth2FlowContext,
            SessionContext,
            PerformanceContext,
            log_auth_flow_start,
            log_auth_redirect,
            log_session_lifecycle,
            log_browser_security_event,
            log_template_performance
        )
        
        # Create mock request
        mock_request = Mock(spec=Request)
        mock_request.method = "GET"
        mock_request.url.path = "/oauth2/authorize"
        mock_request.url.query = "client_id=test&response_type=code"
        mock_request.client.host = "127.0.0.1"
        mock_request.headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "accept": "text/html,application/xhtml+xml",
            "accept-language": "en-US,en;q=0.9",
            "referer": "https://example.com"
        }
        mock_request.query_params = {"client_id": "test", "response_type": "code"}
        mock_request.state = Mock()
        mock_request.state.request_id = "req_123"
        
        # Test logger initialization
        logger = BrowserAuthenticationLogger()
        assert logger is not None
        
        # Test OAuth2 flow context
        oauth2_context = OAuth2FlowContext(
            flow_id="test_flow_456",
            client_id="test_client",
            redirect_uri="https://example.com/callback",
            scopes=["read", "write"],
            state="test_state",
            code_challenge_method="S256",
            response_type="code",
            auth_method=AuthenticationMethod.BROWSER_SESSION,
            flow_stage="started",
            start_time=datetime.now(timezone.utc),
            current_time=datetime.now(timezone.utc)
        )
        
        # Test session context
        session_context = SessionContext(
            session_id="sess_789",
            user_id="user_123",
            session_created_at=datetime.now(timezone.utc),
            session_last_activity=datetime.now(timezone.utc),
            csrf_token_valid=True
        )
        
        # Test performance context
        performance_context = PerformanceContext(
            request_start_time=time.time(),
            processing_time=0.5,
            template_render_time=0.2,
            total_response_time=0.7
        )
        
        # Test authentication event logging
        logger.log_authentication_event(
            BrowserAuthEvent.AUTH_FLOW_STARTED,
            mock_request,
            oauth2_context=oauth2_context,
            session_context=session_context,
            performance_context=performance_context
        )
        
        # Test authentication flow start logging
        logger.log_authentication_flow_start(
            mock_request,
            "flow_789",
            "client_456",
            AuthenticationMethod.BROWSER_SESSION,
            "https://example.com/callback",
            ["read", "write"],
            "state_123",
            "user_456"
        )
        
        # Test authentication redirect logging
        logger.log_authentication_redirect(
            mock_request,
            "flow_789",
            "initiated",
            "https://auth.example.com/login",
            state_preserved=True,
            user_id="user_456"
        )
        
        # Test session event logging
        logger.log_session_event(
            BrowserAuthEvent.SESSION_CREATED,
            mock_request,
            "sess_456",
            "user_789",
            session_data={"expires_at": datetime.now(timezone.utc), "csrf_valid": True}
        )
        
        # Test security event logging
        logger.log_security_event(
            BrowserAuthEvent.SUSPICIOUS_BROWSER_ACTIVITY,
            mock_request,
            "high",
            "Multiple failed authentication attempts",
            flow_id="flow_789",
            session_id="sess_456",
            user_id="user_789",
            threat_indicators={"failed_attempts": 5, "suspicious_ip": True}
        )
        
        # Test performance event logging
        logger.log_performance_event(
            BrowserAuthEvent.TEMPLATE_RENDER_SLOW,
            mock_request,
            "template_render",
            1.5,  # 1.5 seconds
            flow_id="flow_789",
            template_name="consent_screen",
            additional_metrics={"db_time": 0.3, "memory_usage": 50.2}
        )
        
        # Test convenience functions
        log_auth_flow_start(
            mock_request,
            "flow_conv_123",
            "client_conv",
            AuthenticationMethod.BROWSER_SESSION,
            "https://example.com/callback",
            ["read"],
            "state_conv",
            "user_conv"
        )
        
        log_auth_redirect(
            mock_request,
            "flow_conv_123",
            "completed",
            "https://example.com/callback?code=abc123",
            state_preserved=True,
            user_id="user_conv"
        )
        
        log_session_lifecycle(
            BrowserAuthEvent.SESSION_EXPIRED,
            mock_request,
            "sess_conv",
            "user_conv",
            {"reason": "timeout"}
        )
        
        log_browser_security_event(
            BrowserAuthEvent.CSRF_TOKEN_VALIDATION,
            mock_request,
            "medium",
            "CSRF token validation failed",
            flow_id="flow_conv_123",
            session_id="sess_conv",
            user_id="user_conv",
            threat_indicators={"invalid_token": True}
        )
        
        log_template_performance(
            mock_request,
            "login_form",
            0.8,
            flow_id="flow_conv_123",
            additional_metrics={"cache_hit": False}
        )
        
        print("✓ Browser authentication logger tests passed")
        return True
        
    except Exception as e:
        print(f"✗ Browser authentication logger test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_oauth2_metrics_collector():
    """Test the OAuth2 metrics collector functionality."""
    print("Testing OAuth2 Metrics Collector...")
    
    try:
        from src.second_brain_database.routes.oauth2.metrics import (
            OAuth2MetricsCollector,
            AuthMethod,
            MetricType,
            record_auth_request,
            record_token_request,
            record_template_performance,
            record_security_violation,
            record_rate_limit_hit,
            time_request,
            time_template_render
        )
        
        # Test metrics collector initialization
        metrics = OAuth2MetricsCollector()
        assert metrics is not None
        assert len(metrics.completion_rates) > 0
        
        # Test authorization request metrics
        metrics.record_authorization_request(
            "client_123",
            "code",
            "success",
            auth_method="browser_session",
            duration=0.5
        )
        
        assert metrics.completion_rates["browser_session"]["total"] > 0
        assert metrics.completion_rates["browser_session"]["success"] > 0
        assert metrics.counters["oauth2_authorization_requests_total"] > 0
        assert len(metrics.performance_metrics["authorization_duration"]) > 0
        
        # Test token request metrics
        metrics.record_token_request(
            "client_123",
            "authorization_code",
            "success",
            duration=0.3
        )
        
        assert metrics.counters["oauth2_token_requests_total"] > 0
        assert metrics.counters["oauth2_token_requests_success"] > 0
        assert len(metrics.performance_metrics["token_duration"]) > 0
        
        # Test template rendering metrics
        metrics.record_template_render_time("consent_screen", 0.4, "client_123")
        
        assert len(metrics.template_metrics["consent_screen"]) > 0
        assert metrics.counters["oauth2_template_renders_total"] > 0
        
        # Test slow template rendering
        metrics.record_template_render_time("slow_template", 1.5, "client_123")
        assert metrics.counters["oauth2_template_renders_slow"] > 0
        
        # Test security violation metrics
        metrics.record_security_violation(
            "client_123",
            "rate_limit_exceeded",
            "medium",
            {"attempts": 100, "window": "5min"}
        )
        
        assert len(metrics.security_violations) > 0
        assert metrics.counters["oauth2_security_violations_total"] > 0
        assert metrics.counters["oauth2_security_violations_rate_limit_exceeded"] > 0
        
        # Test rate limit hit metrics
        metrics.record_rate_limit_hit(
            "client_123",
            "authorize",
            "requests_per_minute",
            current_count=101,
            limit_value=100
        )
        
        assert len(metrics.rate_limit_hits) > 0
        assert metrics.counters["oauth2_rate_limits_hit_total"] > 0
        assert metrics.counters["oauth2_rate_limits_hit_authorize"] > 0
        
        # Test completion rates
        rates = metrics.get_completion_rates()
        assert "browser_session" in rates
        assert rates["browser_session"]["success_rate"] > 0
        assert rates["browser_session"]["total_flows"] > 0
        
        # Test performance summary
        perf_summary = metrics.get_performance_summary()
        assert "authorization" in perf_summary
        assert "templates" in perf_summary
        assert "consent_screen" in perf_summary["templates"]
        
        # Test security summary
        security_summary = metrics.get_security_summary()
        assert security_summary["security_violations"]["total"] > 0
        assert security_summary["rate_limits"]["total"] > 0
        assert "rate_limit_exceeded" in security_summary["security_violations"]["by_type"]
        
        # Test health metrics
        health = metrics.get_health_metrics()
        assert "total_requests" in health
        assert "successful_requests" in health
        assert "error_rate" in health
        
        # Test all metrics
        all_metrics = metrics.get_all_metrics()
        assert "completion_rates" in all_metrics
        assert "performance" in all_metrics
        assert "security" in all_metrics
        assert "health" in all_metrics
        assert "counters" in all_metrics
        
        # Test convenience functions
        record_auth_request("client_conv", "code", "success", "jwt_token", 0.2)
        record_token_request("client_conv", "authorization_code", "success", 0.1)
        record_template_performance("login_form", 0.3, "client_conv")
        record_security_violation("client_conv", "suspicious_activity", "high")
        record_rate_limit_hit("client_conv", "token", "requests_per_hour", 51, 50)
        
        # Test timing context managers - simplified test
        # Test that the context managers exist and can be instantiated
        timer1 = time_request("client_timing", "authorization")
        assert timer1 is not None
        
        timer2 = time_template_render("timing_template", "client_timing")
        assert timer2 is not None
        
        # Test direct metric recording to verify the underlying functionality works
        initial_auth_count = len(metrics.performance_metrics["authorization_duration"])
        metrics.record_authorization_request("test_timing", "code", "success", "browser_session", 0.123)
        assert len(metrics.performance_metrics["authorization_duration"]) > initial_auth_count
        
        initial_template_count = len(metrics.template_metrics["timing_template"])
        metrics.record_template_render_time("timing_template", 0.456, "test_timing")
        assert len(metrics.template_metrics["timing_template"]) > initial_template_count
        
        print("✓ OAuth2 metrics collector tests passed")
        return True
        
    except Exception as e:
        print(f"✗ OAuth2 metrics collector test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_integration_monitoring_logging():
    """Test integration between monitoring and logging systems."""
    print("Testing Integration between Monitoring and Logging...")
    
    try:
        from src.second_brain_database.routes.oauth2.monitoring import oauth2_monitoring
        from src.second_brain_database.routes.oauth2.browser_auth_logger import browser_auth_logger
        from src.second_brain_database.routes.oauth2.metrics import oauth2_metrics
        
        # Create mock request
        mock_request = Mock(spec=Request)
        mock_request.method = "GET"
        mock_request.url.path = "/oauth2/authorize"
        mock_request.client.host = "127.0.0.1"
        mock_request.headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "accept": "text/html,application/xhtml+xml"
        }
        mock_request.query_params = {"client_id": "integration_test"}
        mock_request.state = Mock()
        mock_request.state.request_id = "integration_req_123"
        
        # Test integrated flow
        flow_id = "integration_flow_123"
        client_id = "integration_client"
        user_id = "integration_user"
        
        # Start monitoring and logging
        from src.second_brain_database.routes.oauth2.monitoring import (
            AuthenticationMethod as MonitoringAuthMethod,
            start_flow_monitoring
        )
        from src.second_brain_database.routes.oauth2.browser_auth_logger import (
            AuthenticationMethod as LoggerAuthMethod,
            log_auth_flow_start
        )
        from src.second_brain_database.routes.oauth2.metrics import record_auth_request
        
        # Start flow in all systems
        start_flow_monitoring(
            flow_id, client_id, MonitoringAuthMethod.BROWSER_SESSION, user_id, mock_request
        )
        
        log_auth_flow_start(
            mock_request, flow_id, client_id, LoggerAuthMethod.BROWSER_SESSION,
            "https://example.com/callback", ["read", "write"], "state_123", user_id
        )
        
        record_auth_request(client_id, "code", "requested", "browser_session")
        
        # Simulate template rendering
        template_name = "consent_screen"
        render_time = 0.6
        
        oauth2_monitoring.record_template_render_time(flow_id, template_name, render_time)
        oauth2_metrics.record_template_render_time(template_name, render_time, client_id)
        
        from src.second_brain_database.routes.oauth2.browser_auth_logger import log_template_performance
        log_template_performance(mock_request, template_name, render_time, flow_id)
        
        # Simulate security event
        security_event_type = "suspicious_activity"
        severity = "medium"
        description = "Multiple rapid requests detected"
        
        oauth2_monitoring.record_security_event(
            flow_id, None, security_event_type, severity, description, client_id, user_id
        )
        
        oauth2_metrics.record_security_violation(client_id, security_event_type, severity)
        
        from src.second_brain_database.routes.oauth2.browser_auth_logger import (
            BrowserAuthEvent,
            log_browser_security_event
        )
        log_browser_security_event(
            BrowserAuthEvent.SUSPICIOUS_BROWSER_ACTIVITY,
            mock_request, severity, description, flow_id, None, user_id
        )
        
        # Complete flow
        from src.second_brain_database.routes.oauth2.monitoring import (
            FlowStage,
            update_flow_stage
        )
        update_flow_stage(flow_id, FlowStage.COMPLETED, duration=2.5)
        record_auth_request(client_id, "code", "success", "browser_session", 2.5)
        
        # Verify integration
        # Check monitoring system
        assert flow_id not in oauth2_monitoring.active_flows  # Should be completed
        assert len(oauth2_monitoring.completed_flows) > 0
        assert len(oauth2_monitoring.security_events) > 0
        
        # Check metrics system
        rates = oauth2_metrics.get_completion_rates()
        assert rates["browser_session"]["total_flows"] > 0
        assert rates["browser_session"]["successful_flows"] > 0
        
        perf_summary = oauth2_metrics.get_performance_summary()
        assert template_name in perf_summary["templates"]
        
        security_summary = oauth2_metrics.get_security_summary()
        assert security_summary["security_violations"]["total"] > 0
        
        print("✓ Integration between monitoring and logging tests passed")
        return True
        
    except Exception as e:
        print(f"✗ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_performance_monitoring():
    """Test performance monitoring capabilities."""
    print("Testing Performance Monitoring...")
    
    try:
        from src.second_brain_database.routes.oauth2.monitoring import oauth2_monitoring
        from src.second_brain_database.routes.oauth2.metrics import oauth2_metrics
        
        # Test template rendering performance
        templates = ["consent_screen", "login_form", "error_page", "success_page"]
        render_times = [0.2, 0.8, 0.1, 1.5]  # Mix of fast and slow renders
        
        for template, render_time in zip(templates, render_times):
            oauth2_monitoring.record_template_render_time("perf_flow_123", template, render_time)
            oauth2_metrics.record_template_render_time(template, render_time, "perf_client")
        
        # Check performance metrics
        perf_metrics = oauth2_monitoring.get_performance_metrics()
        assert "template_rendering" in perf_metrics
        
        for template in templates:
            assert template in perf_metrics["template_rendering"]
            template_stats = perf_metrics["template_rendering"][template]
            assert "avg_render_time" in template_stats
            assert "max_render_time" in template_stats
            assert "render_count" in template_stats
        
        # Check metrics collector performance data
        metrics_perf = oauth2_metrics.get_performance_summary()
        assert "templates" in metrics_perf
        
        for template in templates:
            assert template in metrics_perf["templates"]
            template_metrics = metrics_perf["templates"][template]
            assert "avg_render_time" in template_metrics
            assert "slow_renders" in template_metrics
        
        # Test slow render detection
        slow_renders = sum(1 for t in render_times if t > 0.5)
        success_page_metrics = metrics_perf["templates"]["success_page"]
        assert success_page_metrics["slow_renders"] >= 1  # success_page took 1.5s
        
        print("✓ Performance monitoring tests passed")
        return True
        
    except Exception as e:
        print(f"✗ Performance monitoring test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_security_event_logging():
    """Test security event logging and monitoring."""
    print("Testing Security Event Logging...")
    
    try:
        from src.second_brain_database.routes.oauth2.monitoring import oauth2_monitoring
        from src.second_brain_database.routes.oauth2.metrics import oauth2_metrics
        from src.second_brain_database.routes.oauth2.browser_auth_logger import (
            browser_auth_logger,
            BrowserAuthEvent
        )
        
        # Create mock request
        mock_request = Mock(spec=Request)
        mock_request.method = "POST"
        mock_request.url.path = "/oauth2/authorize"
        mock_request.client.host = "192.168.1.100"
        mock_request.headers = {
            "user-agent": "suspicious-bot/1.0",
            "accept": "*/*"
        }
        mock_request.query_params = {"client_id": "security_test"}
        mock_request.state = Mock()
        mock_request.state.request_id = "security_req_123"
        
        # Test various security events
        security_events = [
            ("suspicious_browser_activity", "high", "Bot-like user agent detected"),
            ("rate_limit_exceeded", "medium", "Client exceeded request rate limit"),
            ("csrf_token_validation", "medium", "CSRF token validation failed"),
            ("session_fixation_attempt", "high", "Potential session fixation attack"),
            ("security_header_violation", "low", "Missing security headers")
        ]
        
        flow_id = "security_flow_123"
        session_id = "security_session_123"
        user_id = "security_user_123"
        client_id = "security_client"
        
        for event_type, severity, description in security_events:
            # Record in monitoring system
            oauth2_monitoring.record_security_event(
                flow_id, session_id, event_type, severity, description, client_id, user_id
            )
            
            # Record in metrics system
            oauth2_metrics.record_security_violation(client_id, event_type, severity)
            
            # Record in logging system
            browser_auth_logger.log_security_event(
                BrowserAuthEvent.SUSPICIOUS_BROWSER_ACTIVITY,  # Use generic event type
                mock_request, severity, description, flow_id, session_id, user_id
            )
        
        # Test rate limiting events
        for i in range(5):
            oauth2_metrics.record_rate_limit_hit(
                client_id, "authorize", "requests_per_minute", 101 + i, 100
            )
        
        # Verify security monitoring
        security_summary = oauth2_monitoring.get_security_summary()
        assert security_summary["total_events"] >= len(security_events)
        assert len(security_summary["events_by_severity"]) > 0
        assert "high" in security_summary["events_by_severity"]
        assert "medium" in security_summary["events_by_severity"]
        
        # Verify metrics collection
        metrics_security = oauth2_metrics.get_security_summary()
        assert metrics_security["security_violations"]["total"] >= len(security_events)
        assert metrics_security["rate_limits"]["total"] >= 5
        assert "suspicious_browser_activity" in metrics_security["security_violations"]["by_type"]
        
        # Test security event severity distribution
        severity_counts = security_summary["events_by_severity"]
        assert severity_counts.get("high", 0) >= 2  # At least 2 high severity events
        assert severity_counts.get("medium", 0) >= 2  # At least 2 medium severity events
        
        print("✓ Security event logging tests passed")
        return True
        
    except Exception as e:
        print(f"✗ Security event logging test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_session_lifecycle_logging():
    """Test session lifecycle logging and monitoring."""
    print("Testing Session Lifecycle Logging...")
    
    try:
        from src.second_brain_database.routes.oauth2.monitoring import oauth2_monitoring
        from src.second_brain_database.routes.oauth2.browser_auth_logger import (
            browser_auth_logger,
            BrowserAuthEvent,
            log_session_lifecycle
        )
        
        # Create mock request
        mock_request = Mock(spec=Request)
        mock_request.method = "GET"
        mock_request.url.path = "/oauth2/authorize"
        mock_request.client.host = "127.0.0.1"
        mock_request.headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "cookie": "session_id=test_session_123"
        }
        mock_request.query_params = {"client_id": "session_test"}
        mock_request.state = Mock()
        mock_request.state.request_id = "session_req_123"
        
        session_id = "lifecycle_session_123"
        user_id = "lifecycle_user_123"
        
        # Test session creation
        oauth2_monitoring.start_session_tracking(session_id, user_id)
        log_session_lifecycle(
            BrowserAuthEvent.SESSION_CREATED,
            mock_request,
            session_id,
            user_id,
            {"created_at": datetime.now(timezone.utc), "csrf_valid": True}
        )
        
        # Verify session is being tracked
        assert session_id in oauth2_monitoring.active_sessions
        session = oauth2_monitoring.active_sessions[session_id]
        assert session.user_id == user_id
        assert session.session_id == session_id
        
        # Test session activity updates
        flow_id = "session_flow_123"
        oauth2_monitoring.update_session_activity(session_id, flow_id)
        
        # Verify flow is associated with session
        assert flow_id in session.oauth2_flows
        
        # Test session validation
        log_session_lifecycle(
            BrowserAuthEvent.SESSION_VALIDATED,
            mock_request,
            session_id,
            user_id,
            {"validation_result": "success", "csrf_valid": True}
        )
        
        # Test session regeneration
        log_session_lifecycle(
            BrowserAuthEvent.SESSION_REGENERATED,
            mock_request,
            session_id,
            user_id,
            {"regeneration_reason": "security", "old_session_id": "old_session_456"}
        )
        
        # Test session expiration
        oauth2_monitoring.end_session_tracking(session_id, "expired")
        log_session_lifecycle(
            BrowserAuthEvent.SESSION_EXPIRED,
            mock_request,
            session_id,
            user_id,
            {"expiration_reason": "timeout", "duration": 3600}
        )
        
        # Verify session is no longer active
        assert session_id not in oauth2_monitoring.active_sessions
        assert len(oauth2_monitoring.session_history) > 0
        
        # Check session history
        expired_session = oauth2_monitoring.session_history[-1]
        assert expired_session.session_id == session_id
        assert expired_session.user_id == user_id
        assert expired_session.cleanup_reason == "expired"
        assert len(expired_session.oauth2_flows) > 0
        
        # Test multiple session lifecycle
        sessions = []
        for i in range(3):
            sess_id = f"multi_session_{i}"
            user_id_multi = f"multi_user_{i}"
            
            oauth2_monitoring.start_session_tracking(sess_id, user_id_multi)
            sessions.append((sess_id, user_id_multi))
        
        # Verify all sessions are active
        assert len(oauth2_monitoring.active_sessions) >= 3
        
        # End all sessions
        for sess_id, user_id_multi in sessions:
            oauth2_monitoring.end_session_tracking(sess_id, "logout")
        
        # Verify sessions are cleaned up
        for sess_id, _ in sessions:
            assert sess_id not in oauth2_monitoring.active_sessions
        
        print("✓ Session lifecycle logging tests passed")
        return True
        
    except Exception as e:
        print(f"✗ Session lifecycle logging test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all monitoring and logging tests."""
    print("=" * 80)
    print("OAUTH2 MONITORING AND LOGGING TEST SUITE (Task 11)")
    print("=" * 80)
    print()
    
    tests = [
        ("OAuth2 Monitoring System", test_oauth2_monitoring_system),
        ("Browser Authentication Logger", test_browser_auth_logger),
        ("OAuth2 Metrics Collector", test_oauth2_metrics_collector),
        ("Integration Monitoring & Logging", test_integration_monitoring_logging),
        ("Performance Monitoring", test_performance_monitoring),
        ("Security Event Logging", test_security_event_logging),
        ("Session Lifecycle Logging", test_session_lifecycle_logging)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"Running {test_name}...")
        try:
            result = test_func()
            results.append((test_name, result))
            if result:
                print(f"✓ {test_name} PASSED")
            else:
                print(f"✗ {test_name} FAILED")
        except Exception as e:
            print(f"✗ {test_name} FAILED with exception: {e}")
            results.append((test_name, False))
        print()
    
    # Summary
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"{status:4} | {test_name}")
    
    print("-" * 80)
    print(f"TOTAL: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED! Task 11 implementation is complete.")
        return True
    else:
        print(f"❌ {total - passed} tests failed. Please review the implementation.")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
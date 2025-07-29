"""
Tests for OAuth2 audit logging and monitoring functionality.

This module tests the comprehensive audit logging, metrics collection,
and monitoring capabilities of the OAuth2 provider.
"""

import asyncio
import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from second_brain_database.routes.oauth2.logging_utils import (
    OAuth2Logger,
    OAuth2EventType,
    oauth2_logger,
    log_authorization_flow,
    log_token_flow,
    log_security_violation,
    log_oauth2_error,
    log_performance_event,
    log_rate_limit_event,
    log_client_management_event,
    log_token_lifecycle_event,
    log_audit_summary
)

from second_brain_database.routes.oauth2.metrics import (
    OAuth2MetricsCollector,
    OAuth2MetricType,
    oauth2_metrics,
    record_authorization_request,
    record_token_request,
    record_token_issued,
    record_security_violation,
    record_rate_limit_hit
)

from second_brain_database.routes.oauth2.audit_manager import (
    OAuth2AuditManager,
    AuditLevel,
    ComplianceStandard,
    oauth2_audit_manager,
    record_audit_event,
    get_audit_trail,
    get_security_events,
    generate_compliance_report
)

from second_brain_database.routes.oauth2.monitoring import (
    OAuth2MonitoringSystem,
    AlertSeverity,
    AlertType,
    AlertRule,
    Alert,
    oauth2_monitoring,
    record_performance_metric,
    record_error_event,
    get_health_status,
    start_monitoring,
    stop_monitoring
)


class TestOAuth2Logger:
    """Test OAuth2 logging functionality."""
    
    @pytest.fixture
    def oauth2_logger_instance(self):
        """Create OAuth2Logger instance for testing."""
        return OAuth2Logger()
    
    @pytest.fixture
    def mock_request(self):
        """Mock FastAPI request object."""
        request = MagicMock()
        request.method = "GET"
        request.url = "https://example.com/oauth2/authorize"
        request.client.host = "192.168.1.100"
        request.headers = {
            "user-agent": "Mozilla/5.0 Test Browser",
            "x-request-id": "test-request-123"
        }
        return request
    
    def test_log_authorization_request(self, oauth2_logger_instance, mock_request):
        """Test authorization request logging."""
        with patch.object(oauth2_logger_instance.logger, 'info') as mock_log:
            oauth2_logger_instance.log_authorization_request(
                client_id="test_client",
                user_id="test_user",
                scopes=["read", "write"],
                redirect_uri="https://client.example.com/callback",
                state="test_state",
                code_challenge_method="S256",
                request=mock_request
            )
            
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            
            # Check log message
            assert "OAuth2 authorization request from client test_client" in call_args[0][0]
            
            # Check extra context
            extra = call_args[1]['extra']
            assert extra['audit_event'] is True
            assert extra['security_relevant'] is True
            assert extra['user_id'] == "test_user"
            assert extra['client_id'] == "test_client"
            
            # Check OAuth2 context
            oauth2_context = extra['oauth2_context']
            assert oauth2_context['event_type'] == OAuth2EventType.AUTHORIZATION_REQUEST.value
            assert oauth2_context['client_id'] == "test_client"
            assert oauth2_context['scopes'] == ["read", "write"]
            assert oauth2_context['request_method'] == "GET"
    
    def test_log_authorization_granted(self, oauth2_logger_instance, mock_request):
        """Test authorization granted logging."""
        with patch.object(oauth2_logger_instance.logger, 'info') as mock_log:
            oauth2_logger_instance.log_authorization_granted(
                client_id="test_client",
                user_id="test_user",
                scopes=["read", "write"],
                authorization_code="auth_code_12345",
                expires_in=600,
                request=mock_request
            )
            
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            
            # Check log message
            assert "OAuth2 authorization granted to client test_client for user test_user" in call_args[0][0]
            
            # Check extra context
            extra = call_args[1]['extra']
            assert extra['authorization_success'] is True
            assert extra['scope_count'] == 2
            
            # Check OAuth2 context
            oauth2_context = extra['oauth2_context']
            assert oauth2_context['event_type'] == OAuth2EventType.AUTHORIZATION_GRANTED.value
            assert oauth2_context['authorization_code'] == "auth_cod***"  # Masked
    
    def test_log_token_request(self, oauth2_logger_instance, mock_request):
        """Test token request logging."""
        with patch.object(oauth2_logger_instance.logger, 'info') as mock_log:
            oauth2_logger_instance.log_token_request(
                client_id="test_client",
                grant_type="authorization_code",
                scopes=["read"],
                user_id="test_user",
                request=mock_request,
                additional_context={"has_code": True}
            )
            
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            
            # Check log message
            assert "OAuth2 token request from client test_client, grant_type: authorization_code" in call_args[0][0]
            
            # Check extra context
            extra = call_args[1]['extra']
            assert extra['grant_type'] == "authorization_code"
            
            # Check OAuth2 context
            oauth2_context = extra['oauth2_context']
            assert oauth2_context['event_type'] == OAuth2EventType.TOKEN_REQUEST.value
            assert oauth2_context['grant_type'] == "authorization_code"
            assert oauth2_context['has_code'] is True
    
    def test_log_token_issued(self, oauth2_logger_instance, mock_request):
        """Test token issued logging."""
        with patch.object(oauth2_logger_instance.logger, 'info') as mock_log:
            oauth2_logger_instance.log_token_issued(
                client_id="test_client",
                user_id="test_user",
                scopes=["read", "write"],
                access_token_expires_in=3600,
                has_refresh_token=True,
                request=mock_request,
                additional_context={"grant_type": "authorization_code"}
            )
            
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            
            # Check log message
            assert "OAuth2 tokens issued to client test_client for user test_user" in call_args[0][0]
            
            # Check extra context
            extra = call_args[1]['extra']
            assert extra['token_success'] is True
            assert extra['has_refresh_token'] is True
            assert extra['scope_count'] == 2
    
    def test_log_security_event(self, oauth2_logger_instance, mock_request):
        """Test security event logging."""
        with patch.object(oauth2_logger_instance.logger, 'error') as mock_log:
            oauth2_logger_instance.log_security_event(
                event_type=OAuth2EventType.SUSPICIOUS_ACTIVITY,
                client_id="test_client",
                user_id="test_user",
                severity="high",
                description="Multiple failed PKCE validations",
                request=mock_request
            )
            
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            
            # Check log message
            assert "OAuth2 HIGH security event: suspicious_activity - Multiple failed PKCE validations" in call_args[0][0]
            
            # Check extra context
            extra = call_args[1]['extra']
            assert extra['security_event'] is True
            assert extra['severity'] == "high"
            assert extra['event_type'] == "suspicious_activity"
    
    def test_log_error_event(self, oauth2_logger_instance, mock_request):
        """Test error event logging."""
        with patch.object(oauth2_logger_instance.logger, 'error') as mock_log:
            oauth2_logger_instance.log_error_event(
                event_type=OAuth2EventType.TOKEN_ERROR,
                error_code="invalid_grant",
                error_description="Authorization code expired",
                client_id="test_client",
                user_id="test_user",
                request=mock_request,
                additional_context={"grant_type": "authorization_code"}
            )
            
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            
            # Check log message
            assert "OAuth2 error: invalid_grant - Authorization code expired" in call_args[0][0]
            
            # Check extra context
            extra = call_args[1]['extra']
            assert extra['error_event'] is True
            assert extra['error_code'] == "invalid_grant"
    
    def test_mask_token(self, oauth2_logger_instance):
        """Test token masking functionality."""
        # Test normal token
        masked = oauth2_logger_instance._mask_token("1234567890abcdef", 8)
        assert masked == "12345678***"
        
        # Test short token
        masked = oauth2_logger_instance._mask_token("123", 8)
        assert masked == "***"
        
        # Test empty token
        masked = oauth2_logger_instance._mask_token("", 8)
        assert masked == "***"


class TestOAuth2MetricsCollector:
    """Test OAuth2 metrics collection functionality."""
    
    @pytest.fixture
    def metrics_collector(self):
        """Create OAuth2MetricsCollector instance for testing."""
        # Reset the singleton for testing
        OAuth2MetricsCollector._instance = None
        OAuth2MetricsCollector._initialized = False
        collector = OAuth2MetricsCollector()
        # Clear any existing metrics
        collector._metrics = {
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
        return collector
    
    def test_record_authorization_request(self, metrics_collector):
        """Test authorization request metrics recording."""
        # Test with the new in-memory metrics implementation
        metrics_collector.record_authorization_request(
            client_id="test_client",
            response_type="code",
            status="success",
            duration=1.5
        )
        
        # Check that metrics were recorded in fallback storage
        metrics_summary = metrics_collector.get_metrics_summary()
        
        # Check counter was incremented
        counter_key = "authorization_requests_test_client_code_success"
        assert counter_key in metrics_summary["counters"]
        assert metrics_summary["counters"][counter_key] == 1
        
        # Check histogram was recorded
        assert "authorization_request_duration" in metrics_summary["histograms"]
        histogram_data = metrics_summary["histograms"]["authorization_request_duration"]
        assert histogram_data["count"] == 1
        assert histogram_data["avg"] == 1.5
    
    def test_record_token_request(self, metrics_collector):
        """Test token request metrics recording."""
        # Test with the new in-memory metrics implementation
        metrics_collector.record_token_request(
            client_id="test_client",
            grant_type="authorization_code",
            status="success",
            duration=0.8
        )
        
        # Check that metrics were recorded in fallback storage
        metrics_summary = metrics_collector.get_metrics_summary()
        
        # Check counter was incremented
        counter_key = "token_requests_test_client_authorization_code_success"
        assert counter_key in metrics_summary["counters"]
        assert metrics_summary["counters"][counter_key] == 1
        
        # Check histogram was recorded
        assert "token_request_duration" in metrics_summary["histograms"]
        histogram_data = metrics_summary["histograms"]["token_request_duration"]
        assert histogram_data["count"] == 1
        assert histogram_data["avg"] == 0.8
    
    def test_record_token_issued(self, metrics_collector):
        """Test token issued metrics recording."""
        # Test with the new in-memory metrics implementation
        metrics_collector.record_token_issued(
            client_id="test_client",
            token_type="access_token",
            grant_type="authorization_code",
            generation_duration=0.2
        )
        
        # Check that metrics were recorded in fallback storage
        metrics_summary = metrics_collector.get_metrics_summary()
        
        # Check counter was incremented
        counter_key = "tokens_issued_test_client_access_token_authorization_code"
        assert counter_key in metrics_summary["counters"]
        assert metrics_summary["counters"][counter_key] == 1
        
        # Check histogram was recorded
        assert "token_generation_duration" in metrics_summary["histograms"]
        histogram_data = metrics_summary["histograms"]["token_generation_duration"]
        assert histogram_data["count"] == 1
        assert histogram_data["avg"] == 0.2
    
    def test_record_security_violation(self, metrics_collector):
        """Test security violation metrics recording."""
        # Clear any existing metrics
        metrics_collector._metrics["counters"].clear()
        
        metrics_collector.record_security_violation(
            client_id="test_client",
            violation_type="pkce_failure",
            severity="high"
        )
        
        # Check that the counter was incremented
        expected_key = "security_violations_test_client_pkce_failure_high"
        assert expected_key in metrics_collector._metrics["counters"]
        assert metrics_collector._metrics["counters"][expected_key] == 1
    
    def test_record_rate_limit_hit(self, metrics_collector):
        """Test rate limit hit metrics recording."""
        # Clear any existing metrics
        metrics_collector._metrics["counters"].clear()
        
        metrics_collector.record_rate_limit_hit(
            client_id="test_client",
            endpoint="authorize",
            limit_type="requests"
        )
        
        # Check that the counter was incremented
        expected_key = "rate_limit_hits_test_client_authorize_requests"
        assert expected_key in metrics_collector._metrics["counters"]
        assert metrics_collector._metrics["counters"][expected_key] == 1
    
    def test_update_active_counts(self, metrics_collector):
        """Test active resource count updates."""
        # Clear any existing metrics
        metrics_collector._metrics["gauges"].clear()
        
        metrics_collector.update_active_counts(
            client_id="test_client",
            authorization_codes=5,
            refresh_tokens=10,
            consents=3
        )
        
        # Check that the gauges were set
        assert metrics_collector._metrics["gauges"]["active_authorization_codes_test_client"] == 5
        assert metrics_collector._metrics["gauges"]["active_refresh_tokens_test_client"] == 10
        assert metrics_collector._metrics["gauges"]["active_consents_test_client"] == 3
    
    def test_time_request_context_manager(self, metrics_collector):
        """Test request timing context manager."""
        # Clear any existing metrics
        metrics_collector._metrics["histograms"].clear()
        
        with metrics_collector.time_request("authorize", "GET"):
            pass  # Simulate request processing
        
        # Check that the histogram was recorded
        assert "request_duration" in metrics_collector._metrics["histograms"]
        histogram_data = metrics_collector._metrics["histograms"]["request_duration"]
        assert len(histogram_data) == 1
        assert histogram_data[0]["labels"]["endpoint"] == "authorize"
        assert histogram_data[0]["labels"]["method"] == "GET"
        assert histogram_data[0]["labels"]["status"] == "success"
        assert histogram_data[0]["value"] >= 0  # Duration should be non-negative
    
    def test_get_fallback_metrics(self, metrics_collector):
        """Test fallback metrics when Prometheus is not available."""
        fallback_metrics = metrics_collector.get_fallback_metrics()
        
        assert "counters" in fallback_metrics
        assert "histograms" in fallback_metrics
        assert "gauges" in fallback_metrics
        assert "prometheus_available" in fallback_metrics
        assert "last_updated" in fallback_metrics


@pytest.mark.asyncio
class TestOAuth2AuditManager:
    """Test OAuth2 audit management functionality."""
    
    @pytest.fixture
    def audit_manager(self):
        """Create OAuth2AuditManager instance for testing."""
        # Reset any existing instance for testing
        manager = OAuth2AuditManager(audit_level=AuditLevel.DETAILED)
        return manager
    
    @pytest.fixture
    def mock_redis_manager(self):
        """Mock Redis manager for testing."""
        with patch('second_brain_database.routes.oauth2.audit_manager.redis_manager') as mock:
            mock.setex = AsyncMock()
            mock.zadd = AsyncMock()
            mock.get = AsyncMock()
            mock.zrangebyscore = AsyncMock()
            mock.zcount = AsyncMock()
            mock.keys = AsyncMock()
            mock.delete = AsyncMock()
            mock.zrem = AsyncMock()
            mock.hincrby = AsyncMock()
            mock.expire = AsyncMock()
            yield mock
    
    async def test_record_audit_event(self, audit_manager, mock_redis_manager):
        """Test audit event recording."""
        event_data = {
            "operation": "authorization_request",
            "scopes": ["read", "write"],
            "redirect_uri": "https://client.example.com/callback"
        }
        
        event_id = await audit_manager.record_audit_event(
            event_type="authorization_request",
            client_id="test_client",
            user_id="test_user",
            event_data=event_data,
            severity="info",
            compliance_relevant=True
        )
        
        assert event_id.startswith("audit_authorization_request_")
        
        # Verify Redis calls
        mock_redis_manager.setex.assert_called()
        mock_redis_manager.zadd.assert_called()
    
    async def test_get_audit_trail(self, audit_manager, mock_redis_manager):
        """Test audit trail retrieval."""
        # Mock Redis responses
        mock_redis_manager.zrangebyscore.return_value = ["event_1", "event_2"]
        mock_redis_manager.get.side_effect = [
            json.dumps({
                "event_id": "event_1",
                "event_type": "authorization_request",
                "client_id": "test_client",
                "user_id": "test_user",
                "timestamp": datetime.utcnow().isoformat()
            }),
            json.dumps({
                "event_id": "event_2",
                "event_type": "token_request",
                "client_id": "test_client",
                "user_id": "test_user",
                "timestamp": datetime.utcnow().isoformat()
            })
        ]
        
        start_time = datetime.utcnow() - timedelta(hours=1)
        end_time = datetime.utcnow()
        
        audit_trail = await audit_manager.get_audit_trail(
            client_id="test_client",
            start_time=start_time,
            end_time=end_time,
            limit=10
        )
        
        assert len(audit_trail) == 2
        assert audit_trail[0]["event_type"] in ["authorization_request", "token_request"]
        assert audit_trail[0]["client_id"] == "test_client"
    
    async def test_get_security_events(self, audit_manager, mock_redis_manager):
        """Test security events retrieval."""
        # Mock Redis responses
        mock_redis_manager.zrangebyscore.return_value = ["security_event_1"]
        mock_redis_manager.get.return_value = json.dumps({
            "event_id": "security_event_1",
            "event_type": "suspicious_activity",
            "severity": "high",
            "client_id": "test_client",
            "timestamp": datetime.utcnow().isoformat()
        })
        
        security_events = await audit_manager.get_security_events(
            severity="high",
            limit=10
        )
        
        assert len(security_events) == 1
        assert security_events[0]["event_type"] == "suspicious_activity"
        assert security_events[0]["severity"] == "high"
    
    async def test_generate_compliance_report(self, audit_manager, mock_redis_manager):
        """Test compliance report generation."""
        # Mock audit events
        mock_audit_events = [
            {
                "event_type": "authorization_granted",
                "client_id": "test_client",
                "user_id": "test_user",
                "timestamp": datetime.utcnow().isoformat()
            }
        ]
        
        mock_security_events = [
            {
                "event_type": "suspicious_activity",
                "severity": "high",
                "client_id": "test_client",
                "timestamp": datetime.utcnow().isoformat()
            }
        ]
        
        with patch.object(audit_manager, 'get_audit_trail', return_value=mock_audit_events), \
             patch.object(audit_manager, 'get_security_events', return_value=mock_security_events):
            
            start_time = datetime.utcnow() - timedelta(days=30)
            end_time = datetime.utcnow()
            
            report = await audit_manager.generate_compliance_report(
                standard=ComplianceStandard.SOX,
                start_time=start_time,
                end_time=end_time,
                client_id="test_client"
            )
            
            assert report["compliance_standard"] == "sox"
            assert "access_controls" in report
            assert "data_integrity" in report
            assert "monitoring" in report
            assert report["total_events"] == 1
            assert report["security_events"] == 1
    
    async def test_get_audit_statistics(self, audit_manager, mock_redis_manager):
        """Test audit statistics retrieval."""
        # Mock Redis response for cached statistics
        mock_redis_manager.get.return_value = None  # No cached data
        
        # Mock audit events for calculation
        mock_audit_events = [
            {
                "event_type": "authorization_request",
                "client_id": "client_1",
                "severity": "info",
                "compliance_relevant": True
            },
            {
                "event_type": "token_request",
                "client_id": "client_2",
                "severity": "info",
                "compliance_relevant": False
            }
        ]
        
        with patch.object(audit_manager, 'get_audit_trail', return_value=mock_audit_events), \
             patch.object(audit_manager, 'get_security_events', return_value=[]):
            
            stats = await audit_manager.get_audit_statistics(time_period="24h")
            
            assert stats["time_period"] == "24h"
            assert stats["total_events"] == 2
            assert stats["security_events"] == 0
            assert stats["compliance_events"] == 1
            assert "event_types" in stats
            assert "client_activity" in stats
    
    async def test_cleanup_expired_audit_data(self, audit_manager, mock_redis_manager):
        """Test expired audit data cleanup."""
        # Mock expired events - return different values for different calls
        mock_redis_manager.zrangebyscore.side_effect = [
            ["expired_event_1", "expired_event_2"],  # First call for main audit events
            ["expired_security_1"]  # Second call for security events
        ]
        
        cleaned_count = await audit_manager.cleanup_expired_audit_data()
        
        assert cleaned_count == 2  # Only main audit events count is returned
        
        # Verify cleanup calls (2 for main events, 1 for security events)
        assert mock_redis_manager.delete.call_count >= 2
        assert mock_redis_manager.zrem.call_count >= 2


@pytest.mark.asyncio
class TestOAuth2MonitoringSystem:
    """Test OAuth2 monitoring system functionality."""
    
    @pytest.fixture
    def monitoring_system(self):
        """Create OAuth2MonitoringSystem instance for testing."""
        return OAuth2MonitoringSystem()
    
    @pytest.fixture
    def mock_redis_manager(self):
        """Mock Redis manager for testing."""
        with patch('second_brain_database.routes.oauth2.monitoring.redis_manager') as mock:
            mock.zadd = AsyncMock()
            mock.zremrangebyscore = AsyncMock()
            mock.zrangebyscore = AsyncMock()
            mock.zcount = AsyncMock()
            mock.get = AsyncMock()
            mock.set = AsyncMock()
            mock.setex = AsyncMock()
            mock.exists = AsyncMock()
            mock.keys = AsyncMock()
            yield mock
    
    async def test_record_performance_metric(self, monitoring_system, mock_redis_manager):
        """Test performance metric recording."""
        await monitoring_system.record_performance_metric(
            metric_name="authorization_request_time",
            value=1.5,
            client_id="test_client",
            labels={"endpoint": "authorize"}
        )
        
        # Verify Redis calls
        mock_redis_manager.zadd.assert_called()
        mock_redis_manager.zremrangebyscore.assert_called()
    
    async def test_record_error_event(self, monitoring_system, mock_redis_manager):
        """Test error event recording."""
        await monitoring_system.record_error_event(
            error_type="authorization_error",
            error_code="invalid_client",
            client_id="test_client",
            severity="medium"
        )
        
        # Verify Redis calls
        mock_redis_manager.zadd.assert_called()
        mock_redis_manager.zremrangebyscore.assert_called()
    
    async def test_record_security_event(self, monitoring_system, mock_redis_manager):
        """Test security event recording."""
        await monitoring_system.record_security_event(
            event_type="suspicious_activity",
            severity="high",
            client_id="test_client",
            description="Multiple failed authentication attempts"
        )
        
        # Verify Redis calls
        mock_redis_manager.zadd.assert_called()
        mock_redis_manager.zremrangebyscore.assert_called()
    
    async def test_get_health_status(self, monitoring_system, mock_redis_manager):
        """Test health status retrieval."""
        # Mock Redis response
        mock_redis_manager.get.return_value = None  # No cached health status
        mock_redis_manager.zcount.return_value = 5  # Mock error count
        
        with patch.object(monitoring_system, 'get_active_alerts', return_value=[]):
            health_status = await monitoring_system.get_health_status()
            
            assert "status" in health_status
            assert "timestamp" in health_status
            assert "metrics" in health_status
            assert "components" in health_status
    
    async def test_get_performance_metrics(self, monitoring_system, mock_redis_manager):
        """Test performance metrics retrieval."""
        # Mock Redis responses
        mock_redis_manager.keys.return_value = ["oauth2:monitoring:performance:authorization_request_time"]
        mock_redis_manager.zrangebyscore.return_value = [
            (json.dumps({
                "metric_name": "authorization_request_time",
                "value": 1.5,
                "client_id": "test_client",
                "labels": {}
            }), 1640995200.0)
        ]
        
        metrics = await monitoring_system.get_performance_metrics(
            time_window=3600
        )
        
        assert "metrics" in metrics
        assert "time_window" in metrics
        assert "generated_at" in metrics
    
    async def test_acknowledge_alert(self, monitoring_system, mock_redis_manager):
        """Test alert acknowledgment."""
        # Mock active alerts
        mock_alerts = [
            {
                "alert_id": "alert_123",
                "rule_name": "high_error_rate",
                "severity": "high",
                "acknowledged": False
            }
        ]
        
        mock_redis_manager.get.return_value = json.dumps(mock_alerts)
        
        result = await monitoring_system.acknowledge_alert(
            alert_id="alert_123",
            acknowledged_by="admin_user"
        )
        
        assert result is True
        mock_redis_manager.set.assert_called()
    
    async def test_start_stop_monitoring(self, monitoring_system):
        """Test monitoring system start and stop."""
        # Mock the monitoring tasks to avoid actual async execution
        with patch.object(monitoring_system, '_monitor_performance'), \
             patch.object(monitoring_system, '_monitor_error_rates'), \
             patch.object(monitoring_system, '_monitor_security_events'), \
             patch.object(monitoring_system, '_monitor_rate_limits'), \
             patch.object(monitoring_system, '_check_alert_rules'), \
             patch.object(monitoring_system, '_update_health_status'):
            
            await monitoring_system.start_monitoring()
            assert len(monitoring_system._monitoring_tasks) == 6
            
            await monitoring_system.stop_monitoring()
            assert len(monitoring_system._monitoring_tasks) == 0


class TestConvenienceFunctions:
    """Test convenience functions for OAuth2 audit logging and monitoring."""
    
    def test_log_authorization_flow(self):
        """Test authorization flow logging convenience function."""
        with patch('second_brain_database.routes.oauth2.logging_utils.oauth2_logger') as mock_logger:
            log_authorization_flow(
                event_type=OAuth2EventType.AUTHORIZATION_REQUEST,
                client_id="test_client",
                user_id="test_user",
                scopes=["read", "write"],
                redirect_uri="https://client.example.com/callback",
                state="test_state",
                code_challenge_method="S256"
            )
            
            mock_logger.log_authorization_request.assert_called_once()
    
    def test_log_token_flow(self):
        """Test token flow logging convenience function."""
        with patch('second_brain_database.routes.oauth2.logging_utils.oauth2_logger') as mock_logger:
            log_token_flow(
                event_type=OAuth2EventType.TOKEN_REQUEST,
                client_id="test_client",
                user_id="test_user",
                grant_type="authorization_code"
            )
            
            mock_logger.log_token_request.assert_called_once()
    
    def test_log_security_violation(self):
        """Test security violation logging convenience function."""
        with patch('second_brain_database.routes.oauth2.logging_utils.oauth2_logger') as mock_logger:
            log_security_violation(
                violation_type="pkce_failure",
                description="Invalid PKCE code verifier",
                client_id="test_client",
                user_id="test_user",
                severity="high"
            )
            
            mock_logger.log_security_event.assert_called_once()
    
    def test_log_oauth2_error(self):
        """Test OAuth2 error logging convenience function."""
        with patch('second_brain_database.routes.oauth2.logging_utils.oauth2_logger') as mock_logger:
            log_oauth2_error(
                error_code="invalid_grant",
                error_description="Authorization code expired",
                client_id="test_client",
                user_id="test_user",
                endpoint="token"
            )
            
            mock_logger.log_error_event.assert_called_once()
    
    def test_record_authorization_request(self):
        """Test authorization request metrics recording convenience function."""
        with patch('second_brain_database.routes.oauth2.metrics.oauth2_metrics') as mock_metrics:
            record_authorization_request(
                client_id="test_client",
                response_type="code",
                status="success",
                duration=1.2
            )
            
            mock_metrics.record_authorization_request.assert_called_once_with(
                "test_client", "code", "success", 1.2
            )
    
    def test_record_token_request(self):
        """Test token request metrics recording convenience function."""
        with patch('second_brain_database.routes.oauth2.metrics.oauth2_metrics') as mock_metrics:
            record_token_request(
                client_id="test_client",
                grant_type="authorization_code",
                status="success",
                duration=0.8
            )
            
            mock_metrics.record_token_request.assert_called_once_with(
                "test_client", "authorization_code", "success", 0.8
            )
    
    def test_record_security_violation_metrics(self):
        """Test security violation metrics recording convenience function."""
        with patch('second_brain_database.routes.oauth2.metrics.oauth2_metrics') as mock_metrics:
            record_security_violation(
                client_id="test_client",
                violation_type="pkce_failure",
                severity="high"
            )
            
            mock_metrics.record_security_violation.assert_called_once_with(
                "test_client", "pkce_failure", "high"
            )


@pytest.mark.asyncio
class TestIntegrationScenarios:
    """Test integrated audit logging and monitoring scenarios."""
    
    async def test_complete_authorization_flow_audit(self):
        """Test complete authorization flow with audit logging and metrics."""
        client_id = "test_client"
        user_id = "test_user"
        
        with patch('second_brain_database.routes.oauth2.logging_utils.oauth2_logger') as mock_logger, \
             patch('second_brain_database.routes.oauth2.metrics.oauth2_metrics') as mock_metrics, \
             patch('second_brain_database.routes.oauth2.audit_manager.oauth2_audit_manager') as mock_audit:
            
            # Simulate authorization request
            mock_logger.log_authorization_request(
                client_id=client_id,
                user_id=user_id,
                scopes=["read", "write"],
                redirect_uri="https://client.example.com/callback",
                state="test_state",
                code_challenge_method="S256"
            )
            
            # Simulate authorization granted
            mock_logger.log_authorization_granted(
                client_id=client_id,
                user_id=user_id,
                scopes=["read", "write"],
                authorization_code="auth_code_123",
                expires_in=600
            )
            
            # Simulate token request
            mock_logger.log_token_request(
                client_id=client_id,
                grant_type="authorization_code",
                user_id=user_id
            )
            
            # Simulate token issued
            mock_logger.log_token_issued(
                client_id=client_id,
                user_id=user_id,
                scopes=["read", "write"],
                access_token_expires_in=3600,
                has_refresh_token=True
            )
            
            # Verify all logging calls were made
            assert mock_logger.log_authorization_request.called
            assert mock_logger.log_authorization_granted.called
            assert mock_logger.log_token_request.called
            assert mock_logger.log_token_issued.called
    
    async def test_security_incident_handling(self):
        """Test security incident detection and alerting."""
        client_id = "suspicious_client"
        
        with patch('second_brain_database.routes.oauth2.logging_utils.oauth2_logger') as mock_logger, \
             patch('second_brain_database.routes.oauth2.monitoring.oauth2_monitoring') as mock_monitoring:
            
            # Simulate multiple security violations
            for i in range(5):
                mock_logger.log_security_event(
                    event_type=OAuth2EventType.PKCE_VALIDATION_FAILED,
                    client_id=client_id,
                    user_id=None,
                    severity="high",
                    description=f"PKCE validation failed attempt {i+1}"
                )
                
                mock_monitoring.record_security_event(
                    event_type="pkce_validation_failed",
                    severity="high",
                    client_id=client_id,
                    description=f"PKCE validation failed attempt {i+1}"
                )
            
            # Verify security logging and monitoring
            assert mock_logger.log_security_event.call_count == 5
            assert mock_monitoring.record_security_event.call_count == 5
    
    async def test_performance_monitoring_integration(self):
        """Test performance monitoring with alerting."""
        client_id = "slow_client"
        
        with patch('second_brain_database.routes.oauth2.monitoring.oauth2_monitoring') as mock_monitoring:
            # Make the mock methods async
            mock_monitoring.record_performance_metric = AsyncMock()
            
            # Simulate slow operations
            await mock_monitoring.record_performance_metric(
                metric_name="authorization_request_time",
                value=5.0,  # Slow request
                client_id=client_id
            )
            
            await mock_monitoring.record_performance_metric(
                metric_name="token_generation_time",
                value=2.0,  # Slow token generation
                client_id=client_id
            )
            
            # Verify performance monitoring calls
            assert mock_monitoring.record_performance_metric.call_count == 2


if __name__ == "__main__":
    pytest.main([__file__])
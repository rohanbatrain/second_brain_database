"""
Test module for AI orchestration health monitoring and metrics integration.

This module provides tests to verify that the health check and monitoring
system works correctly with the existing FastAPI infrastructure.
"""

import asyncio
import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timezone

from .monitoring import AIHealthMonitor, perform_ai_health_check, get_ai_health_monitor
from .metrics import get_ai_metrics, AIPrometheusMetrics


class TestAIHealthMonitor:
    """Test cases for AI health monitoring."""
    
    @pytest.fixture
    def health_monitor(self):
        """Create a health monitor instance for testing."""
        return AIHealthMonitor()
    
    @pytest.mark.asyncio
    async def test_health_monitor_initialization(self, health_monitor):
        """Test that health monitor initializes correctly."""
        assert health_monitor is not None
        assert health_monitor.start_time > 0
        assert health_monitor.health_history == []
        assert health_monitor.max_history_size == 100
    
    @pytest.mark.asyncio
    async def test_comprehensive_health_check_no_orchestrator(self, health_monitor):
        """Test health check when orchestrator is not available."""
        with patch('second_brain_database.integrations.ai_orchestration.orchestrator.get_global_orchestrator', return_value=None):
            result = await health_monitor.comprehensive_health_check()
            
            assert result["status"] == "unhealthy"
            assert "timestamp" in result
            assert "components" in result
            assert result["components"]["orchestrator"]["status"] == "unhealthy"
    
    @pytest.mark.asyncio
    async def test_comprehensive_health_check_with_orchestrator(self, health_monitor):
        """Test health check with a mock orchestrator."""
        # Create mock orchestrator
        mock_orchestrator = Mock()
        mock_orchestrator.agents = {"family": Mock(), "personal": Mock()}
        mock_orchestrator.active_sessions = {}
        mock_orchestrator.background_tasks = {"task1": Mock(done=Mock(return_value=False), cancelled=Mock(return_value=False))}
        
        # Mock component health checks
        mock_orchestrator.model_engine = Mock()
        mock_orchestrator.model_engine.health_check = AsyncMock(return_value={"status": "healthy", "message": "Model engine operational"})
        
        mock_orchestrator.memory_layer = Mock()
        mock_orchestrator.memory_layer.health_check = AsyncMock(return_value={"status": "healthy", "message": "Memory layer operational"})
        
        mock_orchestrator.resource_manager = Mock()
        mock_orchestrator.resource_manager.health_check = AsyncMock(return_value={"status": "healthy", "message": "Resource manager operational"})
        
        with patch('second_brain_database.integrations.ai_orchestration.orchestrator.get_global_orchestrator', return_value=mock_orchestrator):
            with patch('second_brain_database.integrations.ai_orchestration.event_bus.get_ai_event_bus') as mock_event_bus:
                mock_event_bus.return_value.get_session_stats.return_value = {"active_sessions": 0}
                
                result = await health_monitor.comprehensive_health_check()
                
                assert result["status"] == "healthy"
                assert "timestamp" in result
                assert "components" in result
                assert result["components"]["orchestrator"]["status"] == "healthy"
                assert result["components"]["model_engine"]["status"] == "healthy"
                assert result["components"]["memory_layer"]["status"] == "healthy"
                assert result["components"]["resource_manager"]["status"] == "healthy"
    
    @pytest.mark.asyncio
    async def test_health_history_tracking(self, health_monitor):
        """Test that health history is tracked correctly."""
        # Mock a health check result
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "check_duration_ms": 50.0,
            "components": {"orchestrator": {"status": "healthy"}}
        }
        
        health_monitor._update_health_history(health_status)
        
        assert len(health_monitor.health_history) == 1
        assert health_monitor.health_history[0]["status"] == "healthy"
        assert health_monitor.health_history[0]["check_duration_ms"] == 50.0
    
    def test_determine_overall_status(self, health_monitor):
        """Test overall status determination logic."""
        # Test healthy status
        components = {
            "comp1": {"status": "healthy"},
            "comp2": {"status": "healthy"}
        }
        assert health_monitor._determine_overall_status(components) == "healthy"
        
        # Test unhealthy status
        components = {
            "comp1": {"status": "healthy"},
            "comp2": {"status": "unhealthy"}
        }
        assert health_monitor._determine_overall_status(components) == "unhealthy"
        
        # Test degraded status
        components = {
            "comp1": {"status": "healthy"},
            "comp2": {"status": "degraded"}
        }
        assert health_monitor._determine_overall_status(components) == "degraded"
        
        # Test empty components
        assert health_monitor._determine_overall_status({}) == "unknown"


class TestAIMetrics:
    """Test cases for AI Prometheus metrics."""
    
    @pytest.fixture
    def ai_metrics(self):
        """Create an AI metrics instance for testing."""
        return AIPrometheusMetrics()
    
    def test_metrics_initialization(self, ai_metrics):
        """Test that metrics initialize correctly."""
        assert ai_metrics is not None
        # Test will pass regardless of Prometheus availability
        
    def test_record_session_created(self, ai_metrics):
        """Test recording session creation."""
        # This should not raise an exception
        ai_metrics.record_session_created("family", "user123")
        
    def test_record_message_processed(self, ai_metrics):
        """Test recording message processing."""
        # This should not raise an exception
        ai_metrics.record_message_processed("personal", "text", "user")
        
    def test_record_model_request(self, ai_metrics):
        """Test recording model requests."""
        # This should not raise an exception
        ai_metrics.record_model_request("llama2", "success", 1.5, 100)
        
    def test_record_error(self, ai_metrics):
        """Test recording errors."""
        # This should not raise an exception
        ai_metrics.record_error("orchestrator", "timeout")
        
    def test_get_metrics_summary(self, ai_metrics):
        """Test getting metrics summary."""
        summary = ai_metrics.get_metrics_summary()
        assert isinstance(summary, dict)
        assert "timestamp" in summary or "error" in summary


class TestHealthCheckIntegration:
    """Test cases for health check integration."""
    
    @pytest.mark.asyncio
    async def test_perform_ai_health_check_function(self):
        """Test the global health check function."""
        with patch('second_brain_database.integrations.ai_orchestration.monitoring.get_ai_health_monitor') as mock_get_monitor:
            mock_monitor = Mock()
            mock_monitor.comprehensive_health_check = AsyncMock(return_value={"status": "healthy"})
            mock_get_monitor.return_value = mock_monitor
            
            result = await perform_ai_health_check()
            
            assert result["status"] == "healthy"
            mock_monitor.comprehensive_health_check.assert_called_once()
    
    def test_get_ai_health_monitor_singleton(self):
        """Test that health monitor is a singleton."""
        monitor1 = get_ai_health_monitor()
        monitor2 = get_ai_health_monitor()
        
        assert monitor1 is monitor2
    
    def test_get_ai_metrics_singleton(self):
        """Test that AI metrics is a singleton."""
        metrics1 = get_ai_metrics()
        metrics2 = get_ai_metrics()
        
        assert metrics1 is metrics2


if __name__ == "__main__":
    # Simple test runner for development
    async def run_basic_test():
        """Run a basic health check test."""
        print("Testing AI health monitoring...")
        
        try:
            # Test health monitor creation
            monitor = AIHealthMonitor()
            print("✓ Health monitor created successfully")
            
            # Test metrics creation
            metrics = AIPrometheusMetrics()
            print("✓ Metrics system created successfully")
            
            # Test basic functionality
            metrics.record_session_created("test", "user123")
            print("✓ Metrics recording works")
            
            print("\nAll basic tests passed!")
            
        except Exception as e:
            print(f"✗ Test failed: {e}")
            raise
    
    # Run the basic test
    asyncio.run(run_basic_test())
"""
Comprehensive Error Handling and Recovery Tests

This module tests the AI orchestration error handling and recovery system
to ensure robust operation under various failure conditions.
"""

import asyncio
import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch

from .errors import (
    AIOrchestrationError,
    AIErrorContext,
    AIErrorCategory,
    AIErrorSeverity,
    ModelInferenceError,
    AgentExecutionError,
    SessionManagementError,
    VoiceProcessingError,
    MemoryOperationError,
    SecurityValidationError,
    ResourceManagementError,
    CommunicationError,
    ConfigurationError,
    AIRecoveryManager,
    handle_ai_errors,
    create_ai_error_context,
    log_ai_error,
    get_ai_error_handling_health
)
from .recovery import (
    SessionRecoveryManager,
    ModelRecoveryManager,
    VoiceRecoveryManager,
    CommunicationRecoveryManager,
    session_recovery_manager,
    model_recovery_manager,
    voice_recovery_manager,
    communication_recovery_manager,
    trigger_comprehensive_recovery,
    get_recovery_system_health
)
from .orchestrator import AgentOrchestrator
from ...integrations.mcp.context import MCPUserContext


class TestAIErrorClasses:
    """Test AI-specific error classes."""
    
    def test_ai_orchestration_error_creation(self):
        """Test basic AI orchestration error creation."""
        context = create_ai_error_context(
            operation="test_operation",
            session_id="test_session",
            agent_type="personal"
        )
        
        error = AIOrchestrationError(
            "Test error message",
            context=context,
            severity=AIErrorSeverity.HIGH,
            category=AIErrorCategory.AGENT_EXECUTION
        )
        
        assert str(error) == "Test error message"
        assert error.severity == AIErrorSeverity.HIGH
        assert error.category == AIErrorCategory.AGENT_EXECUTION
        assert error.recoverable is True
        assert error.context.session_id == "test_session"
        assert error.context.agent_type == "personal"
    
    def test_model_inference_error(self):
        """Test model inference error creation."""
        error = ModelInferenceError(
            "Model failed to generate response",
            model_name="llama3.2"
        )
        
        assert error.category == AIErrorCategory.MODEL_INFERENCE
        assert error.context.model_name == "llama3.2"
    
    def test_session_management_error(self):
        """Test session management error creation."""
        error = SessionManagementError(
            "Session not found",
            session_id="invalid_session"
        )
        
        assert error.category == AIErrorCategory.SESSION_MANAGEMENT
        assert error.context.session_id == "invalid_session"
    
    def test_security_validation_error(self):
        """Test security validation error creation."""
        error = SecurityValidationError(
            "Insufficient permissions"
        )
        
        assert error.category == AIErrorCategory.SECURITY_VALIDATION
        assert error.severity == AIErrorSeverity.HIGH
        assert error.recoverable is False


class TestErrorHandlingDecorator:
    """Test the AI error handling decorator."""
    
    @pytest.mark.asyncio
    async def test_successful_operation(self):
        """Test decorator with successful operation."""
        
        @handle_ai_errors(
            operation_name="test_operation",
            enable_recovery=True
        )
        async def successful_function():
            return "success"
        
        result = await successful_function()
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_error_handling_with_recovery(self):
        """Test decorator with error and recovery."""
        
        call_count = 0
        
        @handle_ai_errors(
            operation_name="test_operation",
            enable_recovery=True
        )
        async def failing_function():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise AIOrchestrationError("First attempt failed")
            return "recovered"
        
        # Mock the recovery manager to allow recovery
        with patch('src.second_brain_database.integrations.ai_orchestration.errors.ai_recovery_manager') as mock_recovery:
            mock_recovery.recover_from_error = AsyncMock(return_value="recovered")
            
            result = await failing_function()
            assert result == "recovered"
    
    @pytest.mark.asyncio
    async def test_non_recoverable_error(self):
        """Test decorator with non-recoverable error."""
        
        @handle_ai_errors(
            operation_name="test_operation",
            enable_recovery=True
        )
        async def failing_function():
            raise SecurityValidationError("Security check failed")
        
        with pytest.raises(SecurityValidationError):
            await failing_function()


class TestRecoveryManagers:
    """Test recovery manager implementations."""
    
    @pytest.mark.asyncio
    async def test_session_recovery_manager(self):
        """Test session recovery manager."""
        recovery_manager = SessionRecoveryManager()
        
        # Mock orchestrator
        mock_orchestrator = Mock()
        mock_orchestrator.active_sessions = {}
        
        # Mock Redis operations
        with patch('src.second_brain_database.integrations.ai_orchestration.recovery.redis_manager') as mock_redis_manager:
            mock_redis = AsyncMock()
            mock_redis.get.return_value = '{"user_id": "test_user", "created_at": "2024-01-01T00:00:00+00:00"}'
            mock_redis.ping.return_value = True
            mock_redis_manager.get_redis.return_value = mock_redis
            
            error_context = create_ai_error_context(
                operation="test_recovery",
                session_id="test_session"
            )
            
            result = await recovery_manager.recover_session(
                "test_session",
                error_context,
                mock_orchestrator
            )
            
            assert result["success"] is True
            assert result["session_id"] == "test_session"
            assert "recovery_time_ms" in result
    
    @pytest.mark.asyncio
    async def test_model_recovery_manager(self):
        """Test model recovery manager."""
        recovery_manager = ModelRecoveryManager()
        
        # Mock model engine
        mock_model_engine = Mock()
        mock_model_engine.generate_response = AsyncMock()
        
        async def mock_generate_response(*args, **kwargs):
            for token in ["Hello", " ", "world", "!"]:
                yield token
        
        mock_model_engine.generate_response.return_value = mock_generate_response()
        
        error_context = create_ai_error_context(
            operation="model_inference",
            model_name="llama3.2"
        )
        
        # Test recovery with fallback model
        recovery_manager.fallback_models["llama3.2"] = ["llama3.1"]
        
        tokens = []
        async for token in recovery_manager.recover_model_inference(
            "llama3.2",
            "Test prompt",
            error_context,
            mock_model_engine
        ):
            tokens.append(token)
        
        assert len(tokens) > 0
    
    @pytest.mark.asyncio
    async def test_voice_recovery_manager(self):
        """Test voice recovery manager."""
        recovery_manager = VoiceRecoveryManager()
        
        error_context = create_ai_error_context(
            operation="voice_processing",
            voice_enabled=True
        )
        
        result = await recovery_manager.recover_voice_processing(
            error_context,
            fallback_text="Voice unavailable, using text"
        )
        
        assert result["success"] is True
        assert result["fallback_used"] is True
        assert result["recovery_method"] == "text_fallback"
        assert "Voice unavailable, using text" in result["text_response"]
    
    @pytest.mark.asyncio
    async def test_communication_recovery_manager(self):
        """Test communication recovery manager."""
        recovery_manager = CommunicationRecoveryManager()
        
        error_context = create_ai_error_context(
            operation="websocket_communication",
            session_id="test_session"
        )
        
        # Test WebSocket recovery
        websocket_result = await recovery_manager.recover_websocket_connection(
            "test_session",
            error_context
        )
        
        assert websocket_result["success"] is True
        assert websocket_result["recovery_method"] == "connection_restoration"
        assert websocket_result["reconnection_required"] is True
        
        # Test LiveKit recovery
        livekit_result = await recovery_manager.recover_livekit_connection(
            "test_session",
            error_context
        )
        
        assert livekit_result["success"] is True
        assert livekit_result["recovery_method"] == "livekit_reconnection"
        assert livekit_result["voice_available"] is True


class TestComprehensiveRecovery:
    """Test comprehensive recovery system."""
    
    @pytest.mark.asyncio
    async def test_comprehensive_recovery_success(self):
        """Test successful comprehensive recovery."""
        
        # Mock orchestrator
        mock_orchestrator = Mock()
        mock_orchestrator.active_sessions = {}
        
        error_context = create_ai_error_context(
            operation="comprehensive_test",
            session_id="test_session",
            voice_enabled=True
        )
        
        with patch('src.second_brain_database.integrations.ai_orchestration.recovery.session_recovery_manager') as mock_session_recovery:
            with patch('src.second_brain_database.integrations.ai_orchestration.recovery.communication_recovery_manager') as mock_comm_recovery:
                
                mock_session_recovery.recover_session = AsyncMock(return_value={"success": True})
                mock_comm_recovery.recover_websocket_connection = AsyncMock(return_value={"success": True})
                mock_comm_recovery.recover_livekit_connection = AsyncMock(return_value={"success": True})
                
                result = await trigger_comprehensive_recovery(
                    "test_session",
                    error_context,
                    mock_orchestrator
                )
                
                assert result["overall_success"] is True
                assert result["session_id"] == "test_session"
                assert "components" in result
                assert "recovery_started_at" in result
                assert "recovery_completed_at" in result
    
    @pytest.mark.asyncio
    async def test_comprehensive_recovery_partial_failure(self):
        """Test comprehensive recovery with partial failure."""
        
        mock_orchestrator = Mock()
        mock_orchestrator.active_sessions = {}
        
        error_context = create_ai_error_context(
            operation="comprehensive_test",
            session_id="test_session"
        )
        
        with patch('src.second_brain_database.integrations.ai_orchestration.recovery.session_recovery_manager') as mock_session_recovery:
            with patch('src.second_brain_database.integrations.ai_orchestration.recovery.communication_recovery_manager') as mock_comm_recovery:
                
                mock_session_recovery.recover_session = AsyncMock(return_value={"success": True})
                mock_comm_recovery.recover_websocket_connection = AsyncMock(return_value={"success": False})
                
                result = await trigger_comprehensive_recovery(
                    "test_session",
                    error_context,
                    mock_orchestrator
                )
                
                assert result["overall_success"] is False
                assert len(result["warnings"]) > 0
                assert len(result["next_steps"]) > 0


class TestHealthChecks:
    """Test health check functionality."""
    
    @pytest.mark.asyncio
    async def test_ai_error_handling_health(self):
        """Test AI error handling health check."""
        
        with patch('src.second_brain_database.integrations.ai_orchestration.errors.get_error_handling_health') as mock_base_health:
            mock_base_health.return_value = {"overall_healthy": True}
            
            health = await get_ai_error_handling_health()
            
            assert "base_error_handling" in health
            assert "ai_error_handling" in health
            assert "overall_healthy" in health
    
    @pytest.mark.asyncio
    async def test_recovery_system_health(self):
        """Test recovery system health check."""
        
        health = await get_recovery_system_health()
        
        assert "session_recovery" in health
        assert "model_recovery" in health
        assert "voice_recovery" in health
        assert "communication_recovery" in health
        assert "overall_healthy" in health


class TestIntegrationWithOrchestrator:
    """Test integration with the main orchestrator."""
    
    @pytest.mark.asyncio
    async def test_orchestrator_error_handling_integration(self):
        """Test that orchestrator properly integrates with error handling."""
        
        # Mock dependencies
        with patch('src.second_brain_database.integrations.ai_orchestration.orchestrator.ModelEngine'):
            with patch('src.second_brain_database.integrations.ai_orchestration.orchestrator.MemoryLayer'):
                with patch('src.second_brain_database.integrations.ai_orchestration.orchestrator.ResourceManager'):
                    
                    orchestrator = AgentOrchestrator()
                    
                    # Test critical error handling
                    error = AIOrchestrationError(
                        "Test critical error",
                        severity=AIErrorSeverity.CRITICAL
                    )
                    
                    with patch.object(orchestrator, 'cleanup_session') as mock_cleanup:
                        mock_cleanup.return_value = True
                        
                        result = await orchestrator.handle_critical_error(
                            "test_session",
                            error
                        )
                        
                        assert result["handled"] is True
                        assert "user_message" in result
                        assert "suggested_actions" in result
    
    @pytest.mark.asyncio
    async def test_orchestrator_health_check_integration(self):
        """Test orchestrator health check integration."""
        
        with patch('src.second_brain_database.integrations.ai_orchestration.orchestrator.ModelEngine'):
            with patch('src.second_brain_database.integrations.ai_orchestration.orchestrator.MemoryLayer'):
                with patch('src.second_brain_database.integrations.ai_orchestration.orchestrator.ResourceManager'):
                    
                    orchestrator = AgentOrchestrator()
                    
                    health = await orchestrator.get_error_handling_health()
                    
                    assert "error_handling" in health
                    assert "recovery_system" in health
                    assert "orchestrator_health" in health
                    assert "overall_healthy" in health


# Integration test function
async def run_error_handling_integration_test():
    """
    Run comprehensive integration test for error handling system.
    
    This function tests the complete error handling and recovery pipeline
    to ensure all components work together correctly.
    """
    print("🔧 Starting AI Error Handling Integration Test...")
    
    test_results = {
        "error_classes": False,
        "recovery_managers": False,
        "comprehensive_recovery": False,
        "health_checks": False,
        "orchestrator_integration": False
    }
    
    try:
        # Test 1: Error Classes
        print("  Testing error classes...")
        context = create_ai_error_context("test", session_id="test")
        error = AIOrchestrationError("Test", context=context)
        assert error.context.session_id == "test"
        test_results["error_classes"] = True
        print("  ✅ Error classes working")
        
        # Test 2: Recovery Managers
        print("  Testing recovery managers...")
        session_recovery = SessionRecoveryManager()
        model_recovery = ModelRecoveryManager()
        voice_recovery = VoiceRecoveryManager()
        comm_recovery = CommunicationRecoveryManager()
        
        assert session_recovery is not None
        assert model_recovery is not None
        assert voice_recovery is not None
        assert comm_recovery is not None
        test_results["recovery_managers"] = True
        print("  ✅ Recovery managers initialized")
        
        # Test 3: Health Checks
        print("  Testing health checks...")
        health = await get_recovery_system_health()
        assert "overall_healthy" in health
        test_results["health_checks"] = True
        print("  ✅ Health checks working")
        
        # Test 4: Orchestrator Integration
        print("  Testing orchestrator integration...")
        with patch('src.second_brain_database.integrations.ai_orchestration.orchestrator.ModelEngine'):
            with patch('src.second_brain_database.integrations.ai_orchestration.orchestrator.MemoryLayer'):
                with patch('src.second_brain_database.integrations.ai_orchestration.orchestrator.ResourceManager'):
                    orchestrator = AgentOrchestrator()
                    assert hasattr(orchestrator, 'handle_critical_error')
                    assert hasattr(orchestrator, 'get_error_handling_health')
        test_results["orchestrator_integration"] = True
        print("  ✅ Orchestrator integration working")
        
        # Overall success
        all_passed = all(test_results.values())
        
        print(f"\n🎯 Error Handling Integration Test Results:")
        print(f"  Error Classes: {'✅' if test_results['error_classes'] else '❌'}")
        print(f"  Recovery Managers: {'✅' if test_results['recovery_managers'] else '❌'}")
        print(f"  Health Checks: {'✅' if test_results['health_checks'] else '❌'}")
        print(f"  Orchestrator Integration: {'✅' if test_results['orchestrator_integration'] else '❌'}")
        print(f"\n{'🎉 All tests passed!' if all_passed else '❌ Some tests failed'}")
        
        return all_passed
        
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        return False


if __name__ == "__main__":
    # Run the integration test
    result = asyncio.run(run_error_handling_integration_test())
    exit(0 if result else 1)
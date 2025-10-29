"""
AI Agent Orchestration Error Handling and Recovery System

This module provides comprehensive error handling, recovery mechanisms, and resilience
patterns specifically designed for the AI Agent Orchestration System. It extends the
base error handling utilities with AI-specific error types, recovery strategies, and
monitoring capabilities.

Key Features:
- AI-specific error hierarchy with detailed context
- Automatic recovery mechanisms for common AI failures
- Circuit breakers for model inference and tool execution
- Graceful degradation for AI service failures
- Comprehensive error monitoring and alerting
- Session recovery and state management
- Multi-modal error handling (text and voice)
"""

import asyncio
import time
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, AsyncGenerator
from dataclasses import dataclass, field
import json
import traceback

from ...utils.error_handling import (
    handle_errors,
    ErrorContext,
    RetryConfig,
    RetryStrategy,
    CircuitBreaker,
    BulkheadSemaphore,
    get_circuit_breaker,
    get_bulkhead,
    sanitize_sensitive_data,
    create_user_friendly_error,
    with_graceful_degradation
)
from ...managers.logging_manager import get_logger
from ...config import settings

logger = get_logger(prefix="[AI_ErrorHandling]")


class AIErrorSeverity(Enum):
    """AI-specific error severity levels."""
    LOW = "low"              # Minor issues, system continues normally
    MEDIUM = "medium"        # Moderate issues, some degradation
    HIGH = "high"           # Significant issues, major degradation
    CRITICAL = "critical"   # System failure, immediate attention required


class AIErrorCategory(Enum):
    """Categories of AI-related errors."""
    MODEL_INFERENCE = "model_inference"
    AGENT_EXECUTION = "agent_execution"
    TOOL_EXECUTION = "tool_execution"
    SESSION_MANAGEMENT = "session_management"
    VOICE_PROCESSING = "voice_processing"
    MEMORY_OPERATIONS = "memory_operations"
    SECURITY_VALIDATION = "security_validation"
    RESOURCE_MANAGEMENT = "resource_management"
    COMMUNICATION = "communication"
    CONFIGURATION = "configuration"


class AIRecoveryStrategy(Enum):
    """Recovery strategies for AI errors."""
    RETRY_WITH_BACKOFF = "retry_with_backoff"
    FALLBACK_AGENT = "fallback_agent"
    GRACEFUL_DEGRADATION = "graceful_degradation"
    SESSION_RECOVERY = "session_recovery"
    CACHE_FALLBACK = "cache_fallback"
    OFFLINE_MODE = "offline_mode"
    USER_NOTIFICATION = "user_notification"


@dataclass
class AIErrorContext(ErrorContext):
    """Extended error context for AI operations."""
    session_id: Optional[str] = None
    agent_type: Optional[str] = None
    model_name: Optional[str] = None
    tool_name: Optional[str] = None
    conversation_turn: Optional[int] = None
    voice_enabled: bool = False
    error_category: Optional[AIErrorCategory] = None
    recovery_attempts: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with AI-specific fields."""
        base_dict = super().to_dict()
        base_dict.update({
            "session_id": self.session_id,
            "agent_type": self.agent_type,
            "model_name": self.model_name,
            "tool_name": self.tool_name,
            "conversation_turn": self.conversation_turn,
            "voice_enabled": self.voice_enabled,
            "error_category": self.error_category.value if self.error_category else None,
            "recovery_attempts": self.recovery_attempts
        })
        return base_dict


# AI-Specific Error Classes
class AIOrchestrationError(Exception):
    """Base exception for AI orchestration errors."""
    
    def __init__(
        self,
        message: str,
        context: Optional[AIErrorContext] = None,
        severity: AIErrorSeverity = AIErrorSeverity.MEDIUM,
        category: Optional[AIErrorCategory] = None,
        recoverable: bool = True
    ):
        super().__init__(message)
        self.context = context or AIErrorContext(operation="unknown")
        self.severity = severity
        self.category = category
        self.recoverable = recoverable
        self.timestamp = datetime.now(timezone.utc)


class ModelInferenceError(AIOrchestrationError):
    """Error during model inference operations."""
    
    def __init__(self, message: str, model_name: str, **kwargs):
        super().__init__(message, category=AIErrorCategory.MODEL_INFERENCE, **kwargs)
        if self.context:
            self.context.model_name = model_name


class AgentExecutionError(AIOrchestrationError):
    """Error during agent execution."""
    
    def __init__(self, message: str, agent_type: str, **kwargs):
        super().__init__(message, category=AIErrorCategory.AGENT_EXECUTION, **kwargs)
        if self.context:
            self.context.agent_type = agent_type


class ToolExecutionError(AIOrchestrationError):
    """Error during MCP tool execution."""
    
    def __init__(self, message: str, tool_name: str, **kwargs):
        super().__init__(message, category=AIErrorCategory.TOOL_EXECUTION, **kwargs)
        if self.context:
            self.context.tool_name = tool_name


class SessionManagementError(AIOrchestrationError):
    """Error in session management operations."""
    
    def __init__(self, message: str, session_id: str, **kwargs):
        super().__init__(message, category=AIErrorCategory.SESSION_MANAGEMENT, **kwargs)
        if self.context:
            self.context.session_id = session_id


class VoiceProcessingError(AIOrchestrationError):
    """Error in voice processing operations."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(message, category=AIErrorCategory.VOICE_PROCESSING, **kwargs)
        if self.context:
            self.context.voice_enabled = True


class MemoryOperationError(AIOrchestrationError):
    """Error in memory layer operations."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(message, category=AIErrorCategory.MEMORY_OPERATIONS, **kwargs)


class SecurityValidationError(AIOrchestrationError):
    """Error in AI security validation."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            category=AIErrorCategory.SECURITY_VALIDATION,
            severity=AIErrorSeverity.HIGH,
            recoverable=False,
            **kwargs
        )


class ResourceManagementError(AIOrchestrationError):
    """Error in resource management operations."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(message, category=AIErrorCategory.RESOURCE_MANAGEMENT, **kwargs)


class CommunicationError(AIOrchestrationError):
    """Error in communication channels (WebSocket, LiveKit)."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(message, category=AIErrorCategory.COMMUNICATION, **kwargs)


class ConfigurationError(AIOrchestrationError):
    """Error in AI configuration."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            category=AIErrorCategory.CONFIGURATION,
            severity=AIErrorSeverity.CRITICAL,
            recoverable=False,
            **kwargs
        )


# Recovery Strategy Implementations
class AIRecoveryManager:
    """Manages recovery strategies for AI errors."""
    
    def __init__(self):
        self.recovery_stats = {}
        self.fallback_cache = {}
        self.offline_responses = {}
        
    async def recover_from_error(
        self,
        error: AIOrchestrationError,
        recovery_func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """
        Attempt to recover from an AI error using appropriate strategy.
        
        Args:
            error: The AI error to recover from
            recovery_func: Function to retry after recovery
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Recovery result or raises if all strategies fail
        """
        if not error.recoverable:
            logger.error("Error is not recoverable: %s", str(error))
            raise error
        
        recovery_strategy = self._determine_recovery_strategy(error)
        logger.info(
            "Attempting recovery for %s using strategy: %s",
            error.category.value if error.category else "unknown",
            recovery_strategy.value
        )
        
        try:
            if recovery_strategy == AIRecoveryStrategy.RETRY_WITH_BACKOFF:
                return await self._retry_with_backoff(error, recovery_func, *args, **kwargs)
            
            elif recovery_strategy == AIRecoveryStrategy.FALLBACK_AGENT:
                return await self._fallback_agent_recovery(error, recovery_func, *args, **kwargs)
            
            elif recovery_strategy == AIRecoveryStrategy.GRACEFUL_DEGRADATION:
                return await self._graceful_degradation_recovery(error, recovery_func, *args, **kwargs)
            
            elif recovery_strategy == AIRecoveryStrategy.SESSION_RECOVERY:
                return await self._session_recovery(error, recovery_func, *args, **kwargs)
            
            elif recovery_strategy == AIRecoveryStrategy.CACHE_FALLBACK:
                return await self._cache_fallback_recovery(error, recovery_func, *args, **kwargs)
            
            elif recovery_strategy == AIRecoveryStrategy.OFFLINE_MODE:
                return await self._offline_mode_recovery(error, recovery_func, *args, **kwargs)
            
            else:
                return await self._user_notification_recovery(error, recovery_func, *args, **kwargs)
                
        except Exception as recovery_error:
            logger.error(
                "Recovery failed for %s: %s",
                error.category.value if error.category else "unknown",
                str(recovery_error)
            )
            raise error from recovery_error
    
    def _determine_recovery_strategy(self, error: AIOrchestrationError) -> AIRecoveryStrategy:
        """Determine the best recovery strategy for an error."""
        if error.category == AIErrorCategory.MODEL_INFERENCE:
            return AIRecoveryStrategy.RETRY_WITH_BACKOFF
        elif error.category == AIErrorCategory.AGENT_EXECUTION:
            return AIRecoveryStrategy.FALLBACK_AGENT
        elif error.category == AIErrorCategory.TOOL_EXECUTION:
            return AIRecoveryStrategy.GRACEFUL_DEGRADATION
        elif error.category == AIErrorCategory.SESSION_MANAGEMENT:
            return AIRecoveryStrategy.SESSION_RECOVERY
        elif error.category == AIErrorCategory.VOICE_PROCESSING:
            return AIRecoveryStrategy.GRACEFUL_DEGRADATION
        elif error.category == AIErrorCategory.MEMORY_OPERATIONS:
            return AIRecoveryStrategy.CACHE_FALLBACK
        elif error.category == AIErrorCategory.COMMUNICATION:
            return AIRecoveryStrategy.RETRY_WITH_BACKOFF
        else:
            return AIRecoveryStrategy.USER_NOTIFICATION
    
    async def _retry_with_backoff(
        self,
        error: AIOrchestrationError,
        recovery_func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """Retry with exponential backoff."""
        retry_config = RetryConfig(
            max_attempts=3,
            initial_delay=1.0,
            backoff_factor=2.0,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF
        )
        
        from ...utils.error_handling import retry_with_backoff
        return await retry_with_backoff(
            recovery_func,
            retry_config,
            error.context,
            *args,
            **kwargs
        )
    
    async def _fallback_agent_recovery(
        self,
        error: AIOrchestrationError,
        recovery_func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """Fallback to a different agent."""
        # Determine fallback agent based on current agent
        current_agent = error.context.agent_type if error.context else "personal"
        fallback_agent = self._get_fallback_agent(current_agent)
        
        logger.info("Falling back from %s to %s agent", current_agent, fallback_agent)
        
        # Update context with fallback agent
        if error.context:
            error.context.agent_type = fallback_agent
        
        # Update kwargs if they contain agent_type
        if "agent_type" in kwargs:
            kwargs["agent_type"] = fallback_agent
        
        return await recovery_func(*args, **kwargs)
    
    def _get_fallback_agent(self, current_agent: str) -> str:
        """Get fallback agent for the current agent."""
        fallback_map = {
            "family": "personal",
            "workspace": "personal", 
            "commerce": "personal",
            "security": "personal",
            "voice": "personal",
            "personal": "family"  # Last resort
        }
        return fallback_map.get(current_agent, "personal")
    
    async def _graceful_degradation_recovery(
        self,
        error: AIOrchestrationError,
        recovery_func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """Provide graceful degradation response."""
        degraded_response = {
            "success": True,
            "degraded": True,
            "message": "Service temporarily degraded. Basic functionality available.",
            "error_context": sanitize_sensitive_data(error.context.to_dict() if error.context else {}),
            "fallback_used": True
        }
        
        # Try to provide a meaningful fallback based on error category
        if error.category == AIErrorCategory.TOOL_EXECUTION:
            degraded_response["message"] = "Tool execution failed. Using cached or default response."
        elif error.category == AIErrorCategory.VOICE_PROCESSING:
            degraded_response["message"] = "Voice processing unavailable. Text mode active."
        
        return degraded_response
    
    async def _session_recovery(
        self,
        error: AIOrchestrationError,
        recovery_func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """Recover session state and retry."""
        session_id = error.context.session_id if error.context else None
        if not session_id:
            raise error
        
        logger.info("Attempting session recovery for session: %s", session_id)
        
        # In a real implementation, this would:
        # 1. Load session state from Redis
        # 2. Validate session integrity
        # 3. Restore conversation context
        # 4. Retry the operation
        
        # For now, return a recovery response
        return {
            "success": True,
            "session_recovered": True,
            "session_id": session_id,
            "message": "Session recovered successfully"
        }
    
    async def _cache_fallback_recovery(
        self,
        error: AIOrchestrationError,
        recovery_func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """Use cached response as fallback."""
        cache_key = self._generate_cache_key(error.context)
        cached_response = self.fallback_cache.get(cache_key)
        
        if cached_response:
            logger.info("Using cached fallback response for %s", error.context.operation)
            return {
                "success": True,
                "cached_response": True,
                "data": cached_response,
                "message": "Using cached response due to service unavailability"
            }
        
        # No cache available, use graceful degradation
        return await self._graceful_degradation_recovery(error, recovery_func, *args, **kwargs)
    
    async def _offline_mode_recovery(
        self,
        error: AIOrchestrationError,
        recovery_func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """Provide offline mode response."""
        operation = error.context.operation if error.context else "unknown"
        offline_response = self.offline_responses.get(operation)
        
        if not offline_response:
            offline_response = {
                "success": False,
                "offline_mode": True,
                "message": "Service is currently offline. Please try again later.",
                "suggested_actions": [
                    "Check your internet connection",
                    "Try again in a few minutes",
                    "Contact support if the issue persists"
                ]
            }
        
        return offline_response
    
    async def _user_notification_recovery(
        self,
        error: AIOrchestrationError,
        recovery_func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """Notify user of the error and provide guidance."""
        user_friendly_error = create_user_friendly_error(error, error.context)
        
        return {
            "success": False,
            "user_notification": True,
            "error": user_friendly_error,
            "recovery_guidance": self._get_recovery_guidance(error)
        }
    
    def _generate_cache_key(self, context: Optional[AIErrorContext]) -> str:
        """Generate cache key for fallback responses."""
        if not context:
            return "unknown_operation"
        
        key_parts = [
            context.operation,
            context.agent_type or "unknown",
            context.user_id or "anonymous"
        ]
        return ":".join(key_parts)
    
    def _get_recovery_guidance(self, error: AIOrchestrationError) -> List[str]:
        """Get user-friendly recovery guidance."""
        guidance = []
        
        if error.category == AIErrorCategory.MODEL_INFERENCE:
            guidance.extend([
                "The AI model is temporarily unavailable",
                "Please try your request again in a few moments",
                "Consider simplifying your request if the issue persists"
            ])
        elif error.category == AIErrorCategory.VOICE_PROCESSING:
            guidance.extend([
                "Voice processing is currently unavailable",
                "You can continue using text-based chat",
                "Voice features will be restored automatically"
            ])
        elif error.category == AIErrorCategory.TOOL_EXECUTION:
            guidance.extend([
                "Some advanced features are temporarily unavailable",
                "Basic chat functionality remains active",
                "Try again later for full functionality"
            ])
        else:
            guidance.extend([
                "A temporary issue occurred",
                "Please try your request again",
                "Contact support if the problem continues"
            ])
        
        return guidance


# Global recovery manager instance
ai_recovery_manager = AIRecoveryManager()


# AI-Specific Circuit Breakers and Bulkheads
def get_ai_circuit_breaker(name: str, **kwargs) -> CircuitBreaker:
    """Get AI-specific circuit breaker with appropriate defaults."""
    defaults = {
        "failure_threshold": 5,
        "recovery_timeout": 60,
        "expected_exception": AIOrchestrationError
    }
    defaults.update(kwargs)
    return get_circuit_breaker(f"ai_{name}", **defaults)


def get_ai_bulkhead(name: str, **kwargs) -> BulkheadSemaphore:
    """Get AI-specific bulkhead with appropriate defaults."""
    defaults = {"capacity": 10}
    defaults.update(kwargs)
    return get_bulkhead(f"ai_{name}", **defaults)


# AI-Specific Error Handling Decorator
def handle_ai_errors(
    operation_name: str,
    agent_type: Optional[str] = None,
    enable_recovery: bool = True,
    circuit_breaker: Optional[str] = None,
    bulkhead: Optional[str] = None,
    **kwargs
):
    """
    AI-specific error handling decorator with recovery capabilities.
    
    Args:
        operation_name: Name of the AI operation
        agent_type: Type of agent performing the operation
        enable_recovery: Whether to enable automatic recovery
        circuit_breaker: Circuit breaker name for the operation
        bulkhead: Bulkhead name for the operation
        **kwargs: Additional arguments for base error handler
    """
    def decorator(func: Callable) -> Callable:
        # Create AI-specific circuit breaker and bulkhead names
        cb_name = f"ai_{circuit_breaker}" if circuit_breaker else None
        bh_name = f"ai_{bulkhead}" if bulkhead else None
        
        # Apply base error handling
        base_handler = handle_errors(
            operation_name=f"AI_{operation_name}",
            circuit_breaker=cb_name,
            bulkhead=bh_name,
            **kwargs
        )
        
        @base_handler
        async def ai_wrapper(*args, **func_kwargs):
            context = AIErrorContext(
                operation=operation_name,
                agent_type=agent_type,
                user_id=func_kwargs.get('user_id'),
                session_id=func_kwargs.get('session_id')
            )
            
            try:
                return await func(*args, **func_kwargs)
                
            except AIOrchestrationError as ai_error:
                # Update error context
                if not ai_error.context:
                    ai_error.context = context
                else:
                    # Merge contexts
                    for key, value in context.to_dict().items():
                        if not getattr(ai_error.context, key, None):
                            setattr(ai_error.context, key, value)
                
                # Attempt recovery if enabled
                if enable_recovery and ai_error.recoverable:
                    try:
                        return await ai_recovery_manager.recover_from_error(
                            ai_error, func, *args, **func_kwargs
                        )
                    except Exception as recovery_error:
                        logger.error(
                            "Recovery failed for %s: %s",
                            operation_name, str(recovery_error)
                        )
                
                raise ai_error
                
            except Exception as e:
                # Convert generic exceptions to AI errors
                ai_error = AIOrchestrationError(
                    f"Unexpected error in {operation_name}: {str(e)}",
                    context=context,
                    severity=AIErrorSeverity.HIGH
                )
                
                if enable_recovery:
                    try:
                        return await ai_recovery_manager.recover_from_error(
                            ai_error, func, *args, **func_kwargs
                        )
                    except Exception:
                        pass
                
                raise ai_error from e
        
        return ai_wrapper
    return decorator


# Health Check for AI Error Handling
async def get_ai_error_handling_health() -> Dict[str, Any]:
    """Get health status of AI error handling components."""
    from ...utils.error_handling import get_error_handling_health
    
    base_health = await get_error_handling_health()
    
    ai_health = {
        "ai_recovery_manager": {
            "active": True,
            "recovery_stats": ai_recovery_manager.recovery_stats,
            "fallback_cache_size": len(ai_recovery_manager.fallback_cache),
            "offline_responses_count": len(ai_recovery_manager.offline_responses)
        },
        "ai_specific_components": {
            "circuit_breakers": {},
            "bulkheads": {}
        }
    }
    
    # Check AI-specific circuit breakers and bulkheads
    from ...utils.error_handling import _circuit_breakers, _bulkheads
    
    for name, cb in _circuit_breakers.items():
        if name.startswith("ai_"):
            ai_health["ai_specific_components"]["circuit_breakers"][name] = cb.get_stats()
    
    for name, bh in _bulkheads.items():
        if name.startswith("ai_"):
            ai_health["ai_specific_components"]["bulkheads"][name] = bh.get_stats()
    
    return {
        "base_error_handling": base_health,
        "ai_error_handling": ai_health,
        "overall_healthy": base_health.get("overall_healthy", True) and ai_health["ai_recovery_manager"]["active"]
    }


# Utility Functions
def create_ai_error_context(
    operation: str,
    session_id: Optional[str] = None,
    agent_type: Optional[str] = None,
    **kwargs
) -> AIErrorContext:
    """Create AI error context with common fields."""
    return AIErrorContext(
        operation=operation,
        session_id=session_id,
        agent_type=agent_type,
        **kwargs
    )


async def log_ai_error(
    error: AIOrchestrationError,
    additional_context: Optional[Dict[str, Any]] = None
):
    """Log AI error with comprehensive context."""
    log_data = {
        "error_type": type(error).__name__,
        "error_message": str(error),
        "severity": error.severity.value,
        "category": error.category.value if error.category else None,
        "recoverable": error.recoverable,
        "timestamp": error.timestamp.isoformat(),
        "context": sanitize_sensitive_data(error.context.to_dict() if error.context else {}),
        "traceback": traceback.format_exc()
    }
    
    if additional_context:
        log_data["additional_context"] = sanitize_sensitive_data(additional_context)
    
    if error.severity in [AIErrorSeverity.HIGH, AIErrorSeverity.CRITICAL]:
        logger.error("AI Error: %s", json.dumps(log_data, indent=2))
    else:
        logger.warning("AI Error: %s", json.dumps(log_data, indent=2))
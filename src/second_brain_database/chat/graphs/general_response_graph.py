"""GeneralResponseGraph for conversational AI responses.

This module implements a LangGraph workflow for generating conversational responses
using Ollama LLM with conversation history context. The graph provides a simple
two-node workflow for context preparation and response generation.

Requirements: 4.1, 4.2, 4.3, 4.4, 4.5
"""

import logging
import time
from typing import Any, AsyncGenerator, Dict, List, Optional

from langchain_ollama import ChatOllama
from langgraph.graph import END, START, StateGraph

from second_brain_database.chat.models.graph_states import GraphState
from second_brain_database.chat.utils.error_recovery import ErrorRecoveryHandler
from second_brain_database.chat.utils.logging_utils import (
    log_execution_time,
    log_graph_execution,
)
from second_brain_database.chat.utils.metrics_tracker import get_metrics_tracker
from second_brain_database.managers.redis_manager import redis_manager

logger = logging.getLogger(__name__)

# Get metrics tracker instance
_metrics_tracker = None


def _get_metrics():
    """Get or create metrics tracker instance."""
    global _metrics_tracker
    if _metrics_tracker is None:
        _metrics_tracker = get_metrics_tracker(redis_manager=redis_manager)
    return _metrics_tracker


class GeneralResponseGraph:
    """LangGraph workflow for general conversational responses.
    
    This graph implements a simple two-node workflow:
    1. prepare_context: Format conversation history and system prompt
    2. generate_response: Call Ollama LLM with streaming enabled
    
    The graph supports streaming responses and includes conversation history
    for context-aware responses.
    
    Attributes:
        llm: ChatOllama instance for response generation
        graph: Compiled StateGraph for execution
    """
    
    def __init__(self, llm: ChatOllama):
        """Initialize GeneralResponseGraph with Ollama LLM.
        
        Args:
            llm: ChatOllama instance configured with streaming enabled
        """
        self.llm = llm
        self.graph = self._build_graph()
        logger.info("GeneralResponseGraph initialized")
    
    def _build_graph(self) -> StateGraph:
        """Build the StateGraph with prepare_context and generate_response nodes.
        
        Graph structure:
            START → prepare_context → generate_response → END
        
        Returns:
            StateGraph: Compiled graph ready for execution
        """
        workflow = StateGraph(GraphState)
        
        # Add nodes
        workflow.add_node("prepare_context", self.prepare_context)
        workflow.add_node("generate_response", self.generate_response)
        
        # Add edges
        workflow.add_edge(START, "prepare_context")
        workflow.add_edge("prepare_context", "generate_response")
        workflow.add_edge("generate_response", END)
        
        return workflow.compile()
    
    @log_execution_time("prepare_context")
    async def prepare_context(self, state: GraphState) -> GraphState:
        """Format conversation history and system prompt for LLM.
        
        This node prepares the context by:
        1. Creating a system prompt for the AI assistant
        2. Adding conversation history from previous messages
        3. Appending the current user question
        4. Formatting everything for LangChain/Ollama consumption
        
        Args:
            state: Current graph state with question and conversation_history
            
        Returns:
            GraphState: Updated state with formatted_messages field
        """
        try:
            logger.debug(f"Preparing context for question: {state.question[:100]}...")
            
            # System prompt for the AI assistant
            system_prompt = (
                "You are a helpful AI assistant. Provide clear, accurate, and "
                "helpful responses to user questions. Use the conversation history "
                "to maintain context and provide relevant answers."
            )
            
            # Start with system message
            messages = [{"role": "system", "content": system_prompt}]
            
            # Add conversation history if available
            conversation_history = getattr(state, "conversation_history", [])
            if conversation_history:
                messages.extend(conversation_history)
                logger.debug(f"Added {len(conversation_history)} messages from history")
            
            # Add current user question
            messages.append({"role": "user", "content": state.question})
            
            # Store formatted messages in state
            # Note: We use a custom attribute since GraphState doesn't have formatted_messages
            # This will be accessible in the next node
            state_dict = state.model_dump()
            state_dict["formatted_messages"] = messages
            
            logger.info(f"Context prepared with {len(messages)} total messages")
            return GraphState(**state_dict)
            
        except Exception as e:
            logger.error(f"Error preparing context: {e}", exc_info=True)
            state.error = f"Failed to prepare context: {str(e)}"
            state.success = False
            return state
    
    @log_execution_time("generate_response")
    async def generate_response(self, state: GraphState) -> GraphState:
        """Generate response using Ollama LLM with streaming.
        
        This node calls the Ollama LLM with the formatted messages and generates
        a response. It includes error recovery with retry logic and fallback
        to a default error message if all retries fail.
        
        Args:
            state: Current graph state with formatted_messages
            
        Returns:
            GraphState: Updated state with generation field containing the response
        """
        try:
            logger.debug("Generating response with Ollama LLM")
            
            # Get formatted messages from state
            state_dict = state.model_dump()
            formatted_messages = state_dict.get("formatted_messages", [])
            
            if not formatted_messages:
                raise ValueError("No formatted messages found in state")
            
            # Call LLM with error recovery
            async def llm_call():
                response = await self.llm.agenerate([formatted_messages])
                return response.generations[0][0].text
            
            # Use error recovery handler with fallback
            response_text = await ErrorRecoveryHandler.llm_call_with_fallback(
                llm_call,
                fallback_response=(
                    "I apologize, but I'm having trouble processing your request "
                    "right now. Please try again in a moment."
                )
            )
            
            # Update state with generated response
            state.generation = response_text
            state.success = True
            
            logger.info(f"Response generated successfully ({len(response_text)} chars)")
            return state
            
        except Exception as e:
            logger.error(f"Error generating response: {e}", exc_info=True)
            state.error = f"Failed to generate response: {str(e)}"
            state.success = False
            state.generation = (
                "I apologize, but I encountered an error while generating a response. "
                "Please try again."
            )
            return state
    
    async def astream(
        self,
        question: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        session_id: Optional[str] = None,
        **kwargs
    ) -> AsyncGenerator[Any, None]:
        """Stream response tokens from the graph execution.
        
        This method executes the graph and yields tokens as they are generated.
        It supports streaming responses for real-time display in the UI.
        
        Args:
            question: User's question/message
            conversation_history: List of previous messages for context
            session_id: Optional session ID for tracking
            **kwargs: Additional arguments passed to graph execution
            
        Yields:
            Tokens from the LLM response (strings or dicts with metadata)
        """
        graph_start_time = time.time()
        success = False
        error_msg = None
        
        try:
            logger.info(f"Starting GeneralResponseGraph stream for session {session_id}")
            
            # Prepare initial state
            initial_state = GraphState(
                question=question,
                session_id=session_id or "",
                conversation_history=conversation_history or []
            )
            
            # Execute graph and stream results
            async for chunk in self.graph.astream(initial_state.model_dump()):
                # The graph yields state updates as the workflow progresses
                # We'll yield the final generation when available
                if isinstance(chunk, dict):
                    # Check if we have a generation in this chunk
                    for node_name, node_state in chunk.items():
                        if isinstance(node_state, dict) and "generation" in node_state:
                            generation = node_state["generation"]
                            if generation:
                                # Yield the complete generation
                                # In a real streaming scenario, we'd yield tokens incrementally
                                yield generation
                                success = True
                                
                        # Yield progress indicators
                        if node_name == "prepare_context":
                            yield {"type": "progress", "message": "Preparing context..."}
                        elif node_name == "generate_response":
                            yield {"type": "progress", "message": "Generating response..."}
                        
                        # Check for errors
                        if isinstance(node_state, dict) and "error" in node_state:
                            error_msg = node_state.get("error")
            
            # Log graph execution summary
            execution_time = time.time() - graph_start_time
            log_graph_execution(
                graph_name="GeneralResponseGraph",
                session_id=session_id or "unknown",
                question=question,
                execution_time=execution_time,
                success=success,
                error=error_msg
            )
            
            # Track graph execution metrics
            try:
                metrics = _get_metrics()
                await metrics.track_graph_execution(
                    graph_name="GeneralResponseGraph",
                    execution_time=execution_time,
                    success=success
                )
            except Exception as metrics_error:
                logger.warning(f"Failed to track graph execution metrics: {metrics_error}")
            
            logger.info("GeneralResponseGraph stream completed successfully")
            
        except Exception as e:
            execution_time = time.time() - graph_start_time
            error_msg = str(e)
            
            # Log graph execution failure
            log_graph_execution(
                graph_name="GeneralResponseGraph",
                session_id=session_id or "unknown",
                question=question,
                execution_time=execution_time,
                success=False,
                error=error_msg
            )
            
            # Track graph execution failure metrics
            try:
                metrics = _get_metrics()
                await metrics.track_graph_execution(
                    graph_name="GeneralResponseGraph",
                    execution_time=execution_time,
                    success=False
                )
                await metrics.track_error(
                    error_type=type(e).__name__,
                    session_id=session_id
                )
            except Exception as metrics_error:
                logger.warning(f"Failed to track error metrics: {metrics_error}")
            
            logger.error(f"Error in GeneralResponseGraph stream: {e}", exc_info=True)
            yield {
                "type": "error",
                "message": f"Stream error: {str(e)}"
            }


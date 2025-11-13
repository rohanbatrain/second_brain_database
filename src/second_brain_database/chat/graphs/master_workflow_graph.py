"""MasterWorkflowGraph for intelligent routing between workflows.

This module implements the master orchestrator that routes queries between
VectorRAG and General Chat workflows based on intent detection and knowledge
base availability. It includes query caching for performance optimization.

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5
"""

import logging
import time
from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict, List, Optional

from langgraph.graph import END, START, StateGraph

from second_brain_database.chat.graphs.general_response_graph import GeneralResponseGraph
from second_brain_database.chat.graphs.vector_rag_graph import VectorRAGGraph
from second_brain_database.chat.models.graph_states import MasterGraphState
from second_brain_database.chat.utils.logging_utils import (
    log_cache_operation,
    log_execution_time,
    log_graph_execution,
)
from second_brain_database.chat.utils.metrics_tracker import get_metrics_tracker
from second_brain_database.managers.redis_manager import redis_manager

if TYPE_CHECKING:
    from second_brain_database.chat.services.cache_manager import QueryCacheManager

logger = logging.getLogger(__name__)

# Get metrics tracker instance
_metrics_tracker = None


def _get_metrics():
    """Get or create metrics tracker instance."""
    global _metrics_tracker
    if _metrics_tracker is None:
        _metrics_tracker = get_metrics_tracker(redis_manager=redis_manager)
    return _metrics_tracker


class MasterWorkflowGraph:
    """Master orchestrator for routing between VectorRAG and General Chat workflows.
    
    This graph implements intelligent routing logic:
    1. check_cache: Check Redis for cached response
    2. detect_intent: Determine if query requires vector search or general chat
    3. route_decision: Conditional routing based on knowledge_base_id and intent
    4. vector_workflow: Execute VectorRAGGraph for document queries
    5. general_response: Execute GeneralResponseGraph for conversational queries
    6. cache_result: Store response in Redis for future queries
    
    The graph passes conversation history to all subgraphs for contextual responses
    and supports query caching to reduce redundant LLM calls.
    
    Attributes:
        vector_rag_graph: VectorRAGGraph instance for document queries
        general_response_graph: GeneralResponseGraph instance for general chat
        cache_manager: QueryCacheManager for response caching
        graph: Compiled StateGraph for execution
    """
    
    def __init__(
        self,
        vector_rag_graph: VectorRAGGraph,
        general_response_graph: GeneralResponseGraph,
        cache_manager: Optional["QueryCacheManager"] = None
    ):
        """Initialize MasterWorkflowGraph with subgraphs and cache manager.
        
        Args:
            vector_rag_graph: VectorRAGGraph instance for document queries
            general_response_graph: GeneralResponseGraph instance for general chat
            cache_manager: Optional QueryCacheManager for response caching
        """
        self.vector_rag_graph = vector_rag_graph
        self.general_response_graph = general_response_graph
        self.cache_manager = cache_manager
        self.graph = self._build_graph()
        logger.info("MasterWorkflowGraph initialized")
    
    def _build_graph(self) -> StateGraph:
        """Build the StateGraph with routing and caching nodes.
        
        Graph structure:
            START → check_cache → [cache_hit?]
                        ├→ YES: return_cached_response → END
                        └→ NO: detect_intent → route_decision
                                                  ├→ vector_workflow → cache_result → END
                                                  └→ general_response → cache_result → END
        
        Returns:
            StateGraph: Compiled graph ready for execution
        """
        workflow = StateGraph(MasterGraphState)
        
        # Add nodes
        workflow.add_node("check_cache", self.check_cache)
        workflow.add_node("return_cached_response", self.return_cached_response)
        workflow.add_node("detect_intent", self.detect_intent)
        workflow.add_node("vector_workflow", self.vector_workflow)
        workflow.add_node("general_response", self.general_response)
        workflow.add_node("cache_result", self.cache_result)
        
        # Add edges
        workflow.add_edge(START, "check_cache")
        
        # Conditional routing based on cache hit
        workflow.add_conditional_edges(
            "check_cache",
            self._route_cache_decision,
            {
                "cached": "return_cached_response",
                "not_cached": "detect_intent"
            }
        )
        
        workflow.add_edge("return_cached_response", END)
        
        # Conditional routing based on intent detection
        workflow.add_conditional_edges(
            "detect_intent",
            self._route_workflow_decision,
            {
                "vector": "vector_workflow",
                "general": "general_response"
            }
        )
        
        workflow.add_edge("vector_workflow", "cache_result")
        workflow.add_edge("general_response", "cache_result")
        workflow.add_edge("cache_result", END)
        
        return workflow.compile()
    
    def _route_cache_decision(self, state: MasterGraphState) -> str:
        """Determine routing based on cache hit/miss.
        
        Args:
            state: Current graph state with cache_hit field
            
        Returns:
            str: "cached" or "not_cached" routing decision
        """
        state_dict = state.model_dump()
        cache_hit = state_dict.get("cache_hit", False)
        
        logger.debug(f"Cache routing: {'cached' if cache_hit else 'not_cached'}")
        return "cached" if cache_hit else "not_cached"
    
    def _route_workflow_decision(self, state: MasterGraphState) -> str:
        """Determine routing based on intent detection and knowledge base availability.
        
        Args:
            state: Current graph state with route_decision field
            
        Returns:
            str: "vector" or "general" routing decision
        """
        state_dict = state.model_dump()
        route_decision = state_dict.get("route_decision", "general")
        
        logger.debug(f"Workflow routing: {route_decision}")
        return route_decision
    
    @log_execution_time("check_cache")
    async def check_cache(self, state: MasterGraphState) -> MasterGraphState:
        """Check Redis cache for previously answered query.
        
        This node checks if the query has been answered recently and returns
        the cached response if available. Caching is based on query hash and
        knowledge base ID.
        
        Args:
            state: Current graph state with question and knowledge_base_id
            
        Returns:
            MasterGraphState: Updated state with cache_hit and cached_response fields
        """
        try:
            # Skip cache check if cache manager not available
            if not self.cache_manager:
                logger.debug("Cache manager not available, skipping cache check")
                state_dict = state.model_dump()
                state_dict["cache_hit"] = False
                return MasterGraphState(**state_dict)
            
            logger.debug(f"Checking cache for query: {state.question[:100]}...")
            
            # Get cached response
            cached_response = await self.cache_manager.get_cached_response(
                query=state.question,
                kb_id=state.knowledge_base_id
            )
            
            state_dict = state.model_dump()
            session_id = state_dict.get("session_id", "unknown")
            
            if cached_response:
                logger.info("Cache hit! Returning cached response")
                log_cache_operation(
                    operation="hit",
                    session_id=session_id,
                    hit=True
                )
                # Track cache hit metric
                try:
                    metrics = _get_metrics()
                    await metrics.track_cache_hit(session_id)
                except Exception as metrics_error:
                    logger.warning(f"Failed to track cache hit metric: {metrics_error}")
                
                state_dict["cache_hit"] = True
                state_dict["cached_response"] = cached_response
                state_dict["generation"] = cached_response.get("generation", "")
                state_dict["success"] = True
            else:
                logger.debug("Cache miss, proceeding with workflow execution")
                log_cache_operation(
                    operation="miss",
                    session_id=session_id,
                    hit=False
                )
                # Track cache miss metric
                try:
                    metrics = _get_metrics()
                    await metrics.track_cache_miss(session_id)
                except Exception as metrics_error:
                    logger.warning(f"Failed to track cache miss metric: {metrics_error}")
                
                state_dict["cache_hit"] = False
            
            return MasterGraphState(**state_dict)
            
        except Exception as e:
            logger.error(f"Error checking cache: {e}", exc_info=True)
            # On cache error, proceed without cache
            state_dict = state.model_dump()
            state_dict["cache_hit"] = False
            return MasterGraphState(**state_dict)
    
    async def return_cached_response(self, state: MasterGraphState) -> MasterGraphState:
        """Return cached response without executing workflows.
        
        This node simply returns the cached response that was retrieved in
        the check_cache node.
        
        Args:
            state: Current graph state with cached_response
            
        Returns:
            MasterGraphState: State with cached response
        """
        logger.info("Returning cached response")
        return state
    
    @log_execution_time("detect_intent")
    async def detect_intent(self, state: MasterGraphState) -> MasterGraphState:
        """Detect intent to determine vector vs. general chat routing.
        
        This node determines the appropriate workflow based on:
        1. Explicit knowledge_base_id provided → vector workflow
        2. Query content analysis → vector or general
        3. State override field → explicit routing
        
        Args:
            state: Current graph state with question and knowledge_base_id
            
        Returns:
            MasterGraphState: Updated state with route_decision field
        """
        try:
            logger.debug("Detecting intent for routing decision")
            
            state_dict = state.model_dump()
            
            # Check for explicit state override
            explicit_state = state_dict.get("state", "normal")
            if explicit_state in ["vector", "rag"]:
                logger.info(f"Explicit state override: {explicit_state} → vector workflow")
                state_dict["route_decision"] = "vector"
                return MasterGraphState(**state_dict)
            
            # Check if knowledge_base_id is provided
            knowledge_base_id = state_dict.get("knowledge_base_id")
            if knowledge_base_id:
                logger.info("Knowledge base ID provided → vector workflow")
                state_dict["route_decision"] = "vector"
                return MasterGraphState(**state_dict)
            
            # Analyze query content for vector search indicators
            question = state.question.lower()
            vector_keywords = [
                "document", "paper", "research", "article", "file",
                "what does", "according to", "in the", "from the",
                "search", "find", "look up", "retrieve"
            ]
            
            has_vector_keywords = any(keyword in question for keyword in vector_keywords)
            
            if has_vector_keywords:
                logger.info("Vector keywords detected → vector workflow")
                state_dict["route_decision"] = "vector"
            else:
                logger.info("No vector indicators → general workflow")
                state_dict["route_decision"] = "general"
            
            return MasterGraphState(**state_dict)
            
        except Exception as e:
            logger.error(f"Error detecting intent: {e}", exc_info=True)
            # Default to general response on error
            state_dict = state.model_dump()
            state_dict["route_decision"] = "general"
            return MasterGraphState(**state_dict)
    
    @log_execution_time("vector_workflow")
    async def vector_workflow(self, state: MasterGraphState) -> MasterGraphState:
        """Execute VectorRAGGraph workflow for document queries.
        
        This node calls the VectorRAGGraph.astream() method and collects the
        generated response. It passes conversation history for contextual responses.
        
        Args:
            state: Current graph state with question, knowledge_base_id, and conversation_history
            
        Returns:
            MasterGraphState: Updated state with generation from vector workflow
        """
        try:
            logger.info("Executing vector workflow")
            
            state_dict = state.model_dump()
            
            # Collect response from vector workflow
            response_parts = []
            
            async for chunk in self.vector_rag_graph.astream(
                question=state.question,
                knowledge_base_id=state.knowledge_base_id,
                conversation_history=state.conversation_history,
                session_id=state.session_id,
                user_id=state_dict.get("user_id")
            ):
                # Collect text chunks
                if isinstance(chunk, str):
                    response_parts.append(chunk)
                elif isinstance(chunk, dict):
                    # Handle progress indicators and errors
                    if chunk.get("type") == "progress":
                        logger.debug(f"Progress: {chunk.get('message')}")
                    elif chunk.get("type") == "error":
                        logger.error(f"Vector workflow error: {chunk.get('message')}")
                        state_dict["error"] = chunk.get("message")
            
            # Combine response parts
            generation = "".join(response_parts) if response_parts else ""
            
            state_dict["generation"] = generation
            state_dict["success"] = bool(generation)
            
            logger.info(f"Vector workflow completed ({len(generation)} chars)")
            return MasterGraphState(**state_dict)
            
        except Exception as e:
            logger.error(f"Error in vector workflow: {e}", exc_info=True)
            state_dict = state.model_dump()
            state_dict["error"] = f"Vector workflow failed: {str(e)}"
            state_dict["success"] = False
            state_dict["generation"] = (
                "I apologize, but I encountered an error while searching the documents. "
                "Please try again."
            )
            return MasterGraphState(**state_dict)
    
    @log_execution_time("general_response")
    async def general_response(self, state: MasterGraphState) -> MasterGraphState:
        """Execute GeneralResponseGraph workflow for conversational queries.
        
        This node calls the GeneralResponseGraph.astream() method and collects
        the generated response. It passes conversation history for contextual responses.
        
        Args:
            state: Current graph state with question and conversation_history
            
        Returns:
            MasterGraphState: Updated state with generation from general workflow
        """
        try:
            logger.info("Executing general response workflow")
            
            state_dict = state.model_dump()
            
            # Collect response from general workflow
            response_parts = []
            
            async for chunk in self.general_response_graph.astream(
                question=state.question,
                conversation_history=state.conversation_history,
                session_id=state.session_id
            ):
                # Collect text chunks
                if isinstance(chunk, str):
                    response_parts.append(chunk)
                elif isinstance(chunk, dict):
                    # Handle progress indicators and errors
                    if chunk.get("type") == "progress":
                        logger.debug(f"Progress: {chunk.get('message')}")
                    elif chunk.get("type") == "error":
                        logger.error(f"General workflow error: {chunk.get('message')}")
                        state_dict["error"] = chunk.get("message")
            
            # Combine response parts
            generation = "".join(response_parts) if response_parts else ""
            
            state_dict["generation"] = generation
            state_dict["success"] = bool(generation)
            
            logger.info(f"General workflow completed ({len(generation)} chars)")
            return MasterGraphState(**state_dict)
            
        except Exception as e:
            logger.error(f"Error in general workflow: {e}", exc_info=True)
            state_dict = state.model_dump()
            state_dict["error"] = f"General workflow failed: {str(e)}"
            state_dict["success"] = False
            state_dict["generation"] = (
                "I apologize, but I encountered an error while generating a response. "
                "Please try again."
            )
            return MasterGraphState(**state_dict)
    
    @log_execution_time("cache_result")
    async def cache_result(self, state: MasterGraphState) -> MasterGraphState:
        """Cache the generated response in Redis for future queries.
        
        This node stores the response in Redis with a 1-hour TTL to reduce
        redundant LLM calls for identical queries.
        
        Args:
            state: Current graph state with generation
            
        Returns:
            MasterGraphState: Unchanged state
        """
        try:
            # Skip caching if cache manager not available
            if not self.cache_manager:
                logger.debug("Cache manager not available, skipping cache storage")
                return state
            
            # Skip caching if generation failed
            if not state.success or not state.generation:
                logger.debug("Skipping cache storage for failed generation")
                return state
            
            logger.debug("Caching response for future queries")
            
            state_dict = state.model_dump()
            session_id = state_dict.get("session_id", "unknown")
            
            # Prepare response data for caching
            response_data = {
                "generation": state.generation,
                "success": state.success,
                "contexts": state.contexts,
                "sources": getattr(state, "sources", [])
            }
            
            # Cache the response
            await self.cache_manager.cache_response(
                query=state.question,
                response=response_data,
                kb_id=state.knowledge_base_id
            )
            
            # Log cache operation
            log_cache_operation(
                operation="store",
                session_id=session_id,
                ttl=3600  # 1 hour
            )
            
            logger.info("Response cached successfully")
            return state
            
        except Exception as e:
            logger.error(f"Error caching result: {e}", exc_info=True)
            # Don't fail the request if caching fails
            return state
    
    async def astream(
        self,
        question: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        knowledge_base_id: Optional[str] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        state_override: Optional[str] = None,
        **kwargs
    ) -> AsyncGenerator[Any, None]:
        """Stream response tokens from the appropriate subgraph.
        
        This method executes the master workflow and yields tokens as they are
        generated by the selected subgraph (VectorRAG or General Chat). It handles
        caching, routing, and conversation history injection.
        
        Args:
            question: User's question/message
            conversation_history: List of previous messages for context
            knowledge_base_id: Optional knowledge base/document ID to search
            session_id: Optional session ID for tracking
            user_id: Optional user ID for scoping
            state_override: Optional explicit routing ("vector", "general", "rag")
            **kwargs: Additional arguments passed to graph execution
            
        Yields:
            Tokens from the LLM response, progress indicators, or metadata
        """
        graph_start_time = time.time()
        success = False
        error_msg = None
        
        try:
            logger.info(f"Starting MasterWorkflowGraph stream for session {session_id}")
            
            # Prepare initial state
            initial_state = MasterGraphState(
                question=question,
                session_id=session_id or "",
                conversation_history=conversation_history or [],
                knowledge_base_id=knowledge_base_id,
                state=state_override or "normal",
                user_id=user_id
            )
            
            # Execute graph and stream results
            async for chunk in self.graph.astream(initial_state.model_dump()):
                # The graph yields state updates as the workflow progresses
                if isinstance(chunk, dict):
                    for node_name, node_state in chunk.items():
                        if isinstance(node_state, dict):
                            # Yield progress indicators
                            if "progress" in node_state:
                                progress = node_state["progress"]
                                yield {"type": "progress", "message": progress}
                            
                            # Yield generation when available
                            if "generation" in node_state:
                                generation = node_state["generation"]
                                if generation:
                                    yield generation
                                    success = True
                            
                            # Yield error if present
                            if "error" in node_state and node_state.get("error"):
                                error_msg = node_state["error"]
                                yield {
                                    "type": "error",
                                    "message": error_msg
                                }
            
            # Log graph execution summary
            execution_time = time.time() - graph_start_time
            log_graph_execution(
                graph_name="MasterWorkflowGraph",
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
                    graph_name="MasterWorkflowGraph",
                    execution_time=execution_time,
                    success=success
                )
            except Exception as metrics_error:
                logger.warning(f"Failed to track graph execution metrics: {metrics_error}")
            
            logger.info("MasterWorkflowGraph stream completed successfully")
            
        except Exception as e:
            execution_time = time.time() - graph_start_time
            error_msg = str(e)
            
            # Log graph execution failure
            log_graph_execution(
                graph_name="MasterWorkflowGraph",
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
                    graph_name="MasterWorkflowGraph",
                    execution_time=execution_time,
                    success=False
                )
                await metrics.track_error(
                    error_type=type(e).__name__,
                    session_id=session_id
                )
            except Exception as metrics_error:
                logger.warning(f"Failed to track error metrics: {metrics_error}")
            
            logger.error(f"Error in MasterWorkflowGraph stream: {e}", exc_info=True)
            yield {
                "type": "error",
                "message": f"Stream error: {str(e)}"
            }

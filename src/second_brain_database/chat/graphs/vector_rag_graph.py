"""VectorRAGGraph for document querying with semantic search.

This module implements a LangGraph workflow for querying vector knowledge bases
using semantic search and generating contextual responses with citations. The graph
integrates with Second Brain's existing RAG infrastructure (Qdrant, Ollama).

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 11.1
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
    log_vector_search,
)
from second_brain_database.chat.utils.metrics_tracker import get_metrics_tracker
from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.services.rag_service import rag_service

logger = logging.getLogger(__name__)

# Get metrics tracker instance
_metrics_tracker = None


def _get_metrics():
    """Get or create metrics tracker instance."""
    global _metrics_tracker
    if _metrics_tracker is None:
        _metrics_tracker = get_metrics_tracker(redis_manager=redis_manager)
    return _metrics_tracker


class VectorRAGGraph:
    """LangGraph workflow for vector RAG (Retrieval Augmented Generation).
    
    This graph implements a workflow for querying vector knowledge bases:
    1. detect_vector_intent: Determine if query requires vector search
    2. retrieve_contexts: Query vector KB and retrieve relevant chunks
    3. generate_response: Format contexts and generate answer with citations
    4. handle_non_vector_intent: Handle queries not suitable for vector search
    
    The graph integrates with Second Brain's existing RAGService and supports
    streaming responses with progress indicators.
    
    Attributes:
        llm: ChatOllama instance for intent detection and response generation
        graph: Compiled StateGraph for execution
    """
    
    def __init__(self, llm: ChatOllama):
        """Initialize VectorRAGGraph with Ollama LLM.
        
        Args:
            llm: ChatOllama instance configured with streaming enabled
        """
        self.llm = llm
        self.graph = self._build_graph()
        logger.info("VectorRAGGraph initialized")
    
    def _build_graph(self) -> StateGraph:
        """Build the StateGraph with vector RAG nodes and conditional routing.
        
        Graph structure:
            START → detect_vector_intent → [is_vector_query?]
                                              ├→ YES: retrieve_contexts → generate_response → END
                                              └→ NO: handle_non_vector_intent → END
        
        Returns:
            StateGraph: Compiled graph ready for execution
        """
        workflow = StateGraph(GraphState)
        
        # Add nodes
        workflow.add_node("detect_vector_intent", self.detect_vector_intent)
        workflow.add_node("retrieve_contexts", self.retrieve_contexts)
        workflow.add_node("generate_response", self.generate_response)
        workflow.add_node("handle_non_vector_intent", self.handle_non_vector_intent)
        
        # Add edges
        workflow.add_edge(START, "detect_vector_intent")
        
        # Conditional routing based on intent detection
        workflow.add_conditional_edges(
            "detect_vector_intent",
            self._route_based_on_intent,
            {
                "vector": "retrieve_contexts",
                "non_vector": "handle_non_vector_intent"
            }
        )
        
        workflow.add_edge("retrieve_contexts", "generate_response")
        workflow.add_edge("generate_response", END)
        workflow.add_edge("handle_non_vector_intent", END)
        
        return workflow.compile()
    
    def _route_based_on_intent(self, state: GraphState) -> str:
        """Determine routing based on intent detection result.
        
        Args:
            state: Current graph state with route_decision field
            
        Returns:
            str: "vector" or "non_vector" routing decision
        """
        state_dict = state.model_dump()
        route_decision = state_dict.get("route_decision", "vector")
        
        logger.debug(f"Routing decision: {route_decision}")
        return route_decision
    
    @log_execution_time("detect_vector_intent")
    async def detect_vector_intent(self, state: GraphState) -> GraphState:
        """Determine if query requires vector search using LLM.
        
        This node uses the LLM to analyze the user's query and determine if it
        requires searching through documents (vector search) or if it's a general
        question that doesn't need document context.
        
        Args:
            state: Current graph state with question
            
        Returns:
            GraphState: Updated state with route_decision field
        """
        try:
            logger.debug(f"Detecting vector intent for question: {state.question[:100]}...")
            
            # Check if knowledge_base_id is provided - if so, always use vector search
            state_dict = state.model_dump()
            knowledge_base_id = state_dict.get("knowledge_base_id")
            
            if knowledge_base_id:
                logger.info("Knowledge base ID provided, routing to vector search")
                state_dict["route_decision"] = "vector"
                state_dict["is_vector_query"] = True
                return GraphState(**state_dict)
            
            # Use LLM to detect intent
            intent_prompt = f"""Analyze the following question and determine if it requires searching through documents or knowledge bases.

Question: {state.question}

Answer with ONLY "YES" if the question:
- Asks about specific information that would be in documents
- Requests facts, data, or details that need to be looked up
- Mentions documents, papers, research, or specific content
- Asks "what does the document say" or similar

Answer with ONLY "NO" if the question:
- Is a general knowledge question
- Asks for opinions or creative responses
- Is a greeting or casual conversation
- Doesn't require specific document content

Answer (YES or NO):"""
            
            async def intent_detection():
                response = await self.llm.agenerate([[{"role": "user", "content": intent_prompt}]])
                return response.generations[0][0].text.strip().upper()
            
            # Call LLM with error recovery
            intent_response = await ErrorRecoveryHandler.llm_call_with_fallback(
                intent_detection,
                fallback_response="YES"  # Default to vector search on error
            )
            
            # Determine routing
            is_vector_query = "YES" in intent_response
            route_decision = "vector" if is_vector_query else "non_vector"
            
            state_dict["route_decision"] = route_decision
            state_dict["is_vector_query"] = is_vector_query
            
            logger.info(f"Intent detected: {route_decision} (response: {intent_response})")
            return GraphState(**state_dict)
            
        except Exception as e:
            logger.error(f"Error detecting vector intent: {e}", exc_info=True)
            # Default to vector search on error
            state_dict = state.model_dump()
            state_dict["route_decision"] = "vector"
            state_dict["is_vector_query"] = True
            return GraphState(**state_dict)
    
    @log_execution_time("retrieve_contexts")
    async def retrieve_contexts(self, state: GraphState) -> GraphState:
        """Retrieve relevant contexts from vector knowledge base.
        
        This node calls the existing RAGService to query the vector database
        (Qdrant) and retrieve the top-k most relevant document chunks. It includes
        error recovery with fallback to general response if vector search fails.
        
        Args:
            state: Current graph state with question and knowledge_base_id
            
        Returns:
            GraphState: Updated state with contexts and documents fields
        """
        search_start_time = time.time()
        try:
            logger.debug("Retrieving contexts from vector knowledge base")
            
            state_dict = state.model_dump()
            knowledge_base_id = state_dict.get("knowledge_base_id")
            user_id = state_dict.get("user_id")
            session_id = state_dict.get("session_id", "unknown")
            
            # Yield progress indicator
            state_dict["progress"] = "Searching vector database..."
            
            # Call RAGService with error recovery
            async def vector_search():
                result = await rag_service.query_document(
                    query=state.question,
                    document_id=knowledge_base_id,
                    user_id=user_id,
                    top_k=5,
                    use_llm=False  # We'll generate response separately
                )
                return result
            
            # Use error recovery handler
            result = await ErrorRecoveryHandler.vector_search_with_fallback(
                vector_search,
                fallback_to_general=True
            )
            
            # Check if fallback was triggered
            if isinstance(result, dict) and result.get("fallback"):
                logger.warning(f"Vector search failed, fallback triggered: {result.get('error')}")
                state_dict["error"] = result["error"]
                state_dict["fallback_to_general"] = True
                state_dict["success"] = False
                return GraphState(**state_dict)
            
            # Extract chunks and format contexts
            chunks = result.get("chunks", [])
            sources = result.get("sources", [])
            
            # Update progress
            state_dict["progress"] = f"Found {len(chunks)} relevant chunks"
            logger.info(f"Retrieved {len(chunks)} chunks from vector search")
            
            # Format contexts as strings
            contexts = []
            documents = []
            
            for i, chunk in enumerate(chunks, 1):
                text = chunk.get("text", "")
                score = chunk.get("score", 0.0)
                metadata = chunk.get("metadata", {})
                
                # Add to contexts list
                context_str = f"[Source {i}, Relevance: {score:.2f}]\n{text}"
                contexts.append(context_str)
                
                # Add to documents list (for state tracking)
                from second_brain_database.chat.models.graph_states import Document
                doc = Document(
                    id=metadata.get("document_id", f"doc_{i}"),
                    content=text,
                    metadata=metadata,
                    score=score
                )
                documents.append(doc)
            
            # Update state
            state_dict["contexts"] = contexts
            state_dict["documents"] = documents
            state_dict["sources"] = sources
            state_dict["success"] = True
            
            # Log vector search operation
            search_time = time.time() - search_start_time
            log_vector_search(
                session_id=session_id,
                knowledge_base_id=knowledge_base_id or "unknown",
                query=state.question,
                chunks_found=len(contexts),
                execution_time=search_time,
                success=True
            )
            
            # Track vector search metrics
            try:
                metrics = _get_metrics()
                await metrics.track_vector_search(
                    session_id=session_id,
                    execution_time=search_time,
                    chunks_found=len(contexts)
                )
            except Exception as metrics_error:
                logger.warning(f"Failed to track vector search metrics: {metrics_error}")
            
            logger.info(f"Contexts retrieved successfully: {len(contexts)} chunks")
            return GraphState(**state_dict)
            
        except Exception as e:
            logger.error(f"Error retrieving contexts: {e}", exc_info=True)
            state_dict = state.model_dump()
            state_dict["error"] = f"Failed to retrieve contexts: {str(e)}"
            state_dict["success"] = False
            state_dict["fallback_to_general"] = True
            return GraphState(**state_dict)
    
    @log_execution_time("generate_response")
    async def generate_response(self, state: GraphState) -> GraphState:
        """Generate response with citations using retrieved contexts.
        
        This node formats the retrieved contexts and uses the LLM to generate
        a comprehensive answer with proper citations. It includes error recovery
        and fallback to a default error message if generation fails.
        
        Args:
            state: Current graph state with contexts and question
            
        Returns:
            GraphState: Updated state with generation field containing the answer
        """
        try:
            logger.debug("Generating response with contexts")
            
            state_dict = state.model_dump()
            contexts = state_dict.get("contexts", [])
            
            # Check if we have contexts
            if not contexts:
                logger.warning("No contexts available for response generation")
                state.generation = (
                    "I couldn't find relevant information in the documents to answer "
                    "your question. Please try rephrasing or ask a different question."
                )
                state.success = False
                return state
            
            # Yield progress indicator
            state_dict["progress"] = "Generating response..."
            
            # Build context string
            context_str = "\n\n".join(contexts)
            
            # Build prompt with contexts
            prompt = f"""Based on the following context from documents, please answer the question. 
Include citations by referencing the source numbers (e.g., [Source 1]).
If the context doesn't contain enough information, say so clearly.

Context:
{context_str}

Question: {state.question}

Answer (with citations):"""
            
            # Format messages for LLM
            messages = [
                {"role": "system", "content": "You are a helpful assistant that answers questions based on provided document context. Always cite your sources using [Source N] notation."},
                {"role": "user", "content": prompt}
            ]
            
            # Add conversation history if available
            conversation_history = state_dict.get("conversation_history", [])
            if conversation_history:
                # Insert history before the current question
                messages = [messages[0]] + conversation_history + [messages[1]]
            
            # Call LLM with error recovery
            async def llm_call():
                response = await self.llm.agenerate([messages])
                return response.generations[0][0].text
            
            response_text = await ErrorRecoveryHandler.llm_call_with_fallback(
                llm_call,
                fallback_response=(
                    "I apologize, but I'm having trouble generating a response "
                    "right now. Please try again in a moment."
                )
            )
            
            # Update state
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
    
    @log_execution_time("handle_non_vector_intent")
    async def handle_non_vector_intent(self, state: GraphState) -> GraphState:
        """Handle queries that don't require vector search.
        
        This node provides a message indicating that the query doesn't require
        searching through documents and suggests using general chat instead.
        
        Args:
            state: Current graph state
            
        Returns:
            GraphState: Updated state with generation field
        """
        try:
            logger.info("Handling non-vector intent query")
            
            state.generation = (
                "This question doesn't seem to require searching through documents. "
                "I can answer general questions directly. How can I help you?"
            )
            state.success = True
            
            return state
            
        except Exception as e:
            logger.error(f"Error handling non-vector intent: {e}", exc_info=True)
            state.error = f"Failed to handle query: {str(e)}"
            state.success = False
            return state
    
    async def astream(
        self,
        question: str,
        knowledge_base_id: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        **kwargs
    ) -> AsyncGenerator[Any, None]:
        """Stream response tokens and metadata from graph execution.
        
        This method executes the graph and yields tokens, progress indicators,
        and metadata as they are generated. It supports streaming responses for
        real-time display in the UI.
        
        Args:
            question: User's question/message
            knowledge_base_id: Optional knowledge base/document ID to search
            conversation_history: List of previous messages for context
            session_id: Optional session ID for tracking
            user_id: Optional user ID for scoping
            **kwargs: Additional arguments passed to graph execution
            
        Yields:
            Tokens from the LLM response, progress indicators, or metadata
        """
        graph_start_time = time.time()
        success = False
        error_msg = None
        
        try:
            logger.info(f"Starting VectorRAGGraph stream for session {session_id}")
            
            # Prepare initial state
            initial_state = GraphState(
                question=question,
                session_id=session_id or "",
                knowledge_base_id=knowledge_base_id,
                user_id=user_id,
                conversation_history=conversation_history or []
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
                graph_name="VectorRAGGraph",
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
                    graph_name="VectorRAGGraph",
                    execution_time=execution_time,
                    success=success
                )
            except Exception as metrics_error:
                logger.warning(f"Failed to track graph execution metrics: {metrics_error}")
            
            logger.info("VectorRAGGraph stream completed successfully")
            
        except Exception as e:
            execution_time = time.time() - graph_start_time
            error_msg = str(e)
            
            # Log graph execution failure
            log_graph_execution(
                graph_name="VectorRAGGraph",
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
                    graph_name="VectorRAGGraph",
                    execution_time=execution_time,
                    success=False
                )
                await metrics.track_error(
                    error_type=type(e).__name__,
                    session_id=session_id
                )
            except Exception as metrics_error:
                logger.warning(f"Failed to track error metrics: {metrics_error}")
            
            logger.error(f"Error in VectorRAGGraph stream: {e}", exc_info=True)
            yield {
                "type": "error",
                "message": f"Stream error: {str(e)}"
            }

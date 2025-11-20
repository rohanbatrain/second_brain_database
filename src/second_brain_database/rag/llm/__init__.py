"""
RAG LLM Integration Framework

Flexible LLM integration layer that supports multiple providers and leverages
existing Ollama integration in the codebase for AI-powered query processing.
"""

from enum import Enum
import json
import time
from typing import Any, AsyncIterator, Dict, List, Optional, Union

from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.rag.core.config import LLMConfig
from second_brain_database.rag.core.exceptions import LLMError
from second_brain_database.rag.core.types import ChatMessage, Conversation, QueryRequest, QueryResponse

logger = get_logger()


class LLMProvider(Enum):
    """Supported LLM providers."""
    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class RAGLLMService:
    """
    RAG LLM Service.
    
    Provides a unified interface for LLM operations in the RAG system,
    leveraging existing Ollama integration and supporting multiple providers.
    """
    
    def __init__(self, config: LLMConfig):
        """
        Initialize RAG LLM service.
        
        Args:
            config: LLM configuration
        """
        self.config = config
        self.provider = config.provider
        
        # Initialize based on provider
        try:
            if self.provider == LLMProvider.OLLAMA:
                self._init_ollama()
            elif self.provider == LLMProvider.OPENAI:
                self._init_openai()
            elif self.provider == LLMProvider.ANTHROPIC:
                self._init_anthropic()
            else:
                logger.warning(f"Unsupported LLM provider: {self.provider}, service will be unavailable")
                self.ollama_manager = None
                self.openai_client = None
                self.anthropic_client = None
                return
            
            logger.info(f"Initialized RAG LLM Service with {self.provider.value} provider")
        except Exception as e:
            logger.error(f"Failed to initialize LLM service with {self.provider}: {e}")
            self.ollama_manager = None
            self.openai_client = None 
            self.anthropic_client = None
    
    def _init_ollama(self):
        """Initialize Ollama integration using existing codebase components."""
        try:
            # Import existing Ollama manager
            from second_brain_database.managers.ollama_manager import OllamaManager
            
            self.ollama_manager = OllamaManager()
            
            if not self.ollama_manager.is_available():
                logger.warning("Ollama service is not available")
            else:
                logger.info(f"Ollama integration initialized with model: {self.config.model_name}")
                
        except ImportError as e:
            raise LLMError(f"Failed to import Ollama integration: {e}")
    
    def _init_openai(self):
        """Initialize OpenAI integration."""
        try:
            import openai

            from second_brain_database.config import settings

            # Use API key from settings
            api_key = getattr(settings, 'OPENAI_API_KEY', None)
            if api_key:
                if hasattr(api_key, 'get_secret_value'):
                    api_key = api_key.get_secret_value()
                
                self.openai_client = openai.AsyncOpenAI(api_key=api_key)
                logger.info("OpenAI client initialized")
            else:
                raise LLMError("OpenAI API key not configured")
                
        except ImportError:
            raise LLMError("OpenAI package not available. Install with: pip install openai")
        except Exception as e:
            raise LLMError(f"Failed to initialize OpenAI: {e}")
    
    def _init_anthropic(self):
        """Initialize Anthropic integration."""
        try:
            import anthropic

            from second_brain_database.config import settings

            # Use API key from settings
            api_key = getattr(settings, 'ANTHROPIC_API_KEY', None)
            if api_key:
                if hasattr(api_key, 'get_secret_value'):
                    api_key = api_key.get_secret_value()
                
                self.anthropic_client = anthropic.AsyncAnthropic(api_key=api_key)
                logger.info("Anthropic client initialized")
            else:
                raise LLMError("Anthropic API key not configured")
                
        except ImportError:
            raise LLMError("Anthropic package not available. Install with: pip install anthropic")
        except Exception as e:
            raise LLMError(f"Failed to initialize Anthropic: {e}")
    
    def is_available(self) -> bool:
        """Check if LLM service is available."""
        if self.provider == LLMProvider.OLLAMA:
            return hasattr(self, 'ollama_manager') and self.ollama_manager.is_available()
        elif self.provider == LLMProvider.OPENAI:
            return hasattr(self, 'openai_client')
        elif self.provider == LLMProvider.ANTHROPIC:
            return hasattr(self, 'anthropic_client')
        return False
    
    async def generate_response(
        self,
        query: str,
        context_chunks: List[Dict[str, Any]],
        conversation_history: Optional[List[ChatMessage]] = None,
        **kwargs
    ) -> QueryResponse:
        """
        Generate AI response for RAG query.
        
        Args:
            query: User query
            context_chunks: Relevant document chunks from vector search
            conversation_history: Previous conversation messages
            **kwargs: Additional generation options
            
        Returns:
            QueryResponse with AI-generated answer
            
        Raises:
            LLMError: If generation fails
        """
        if not self.is_available():
            raise LLMError("LLM service is not available")
        
        start_time = time.time()
        logger.info(f"Generating response for query with {len(context_chunks)} context chunks")
        
        try:
            # Build context from chunks
            context = self._build_context(context_chunks)
            
            # Build prompt with RAG template
            prompt = self._build_rag_prompt(query, context, conversation_history)
            
            # Generate response based on provider
            if self.provider == LLMProvider.OLLAMA:
                response = await self._generate_ollama_response(prompt, **kwargs)
            elif self.provider == LLMProvider.OPENAI:
                response = await self._generate_openai_response(prompt, **kwargs)
            elif self.provider == LLMProvider.ANTHROPIC:
                response = await self._generate_anthropic_response(prompt, **kwargs)
            else:
                raise LLMError(f"Provider not implemented: {self.provider}")
            
            processing_time = time.time() - start_time
            
            # Create QueryResponse
            query_response = QueryResponse(
                query=query,
                answer=response["text"],
                context_chunks=context_chunks,
                sources=self._extract_sources(context_chunks),
                confidence_score=response.get("confidence", 0.8),
                processing_time=processing_time,
                model_used=response.get("model", self.config.model_name),
                provider=self.provider.value,
                metadata={
                    "context_length": len(context),
                    "prompt_length": len(prompt),
                    "response_tokens": response.get("tokens", 0),
                    "temperature": kwargs.get("temperature", self.config.temperature),
                }
            )
            
            logger.info(f"Generated response in {processing_time:.2f}s using {self.provider.value}")
            return query_response
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Failed to generate response after {processing_time:.2f}s: {e}")
            raise LLMError(f"Response generation failed: {e}")
    
    async def generate_streaming_response(
        self,
        query: str,
        context_chunks: List[Dict[str, Any]],
        conversation_history: Optional[List[ChatMessage]] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """
        Generate streaming AI response.
        
        Args:
            query: User query
            context_chunks: Relevant document chunks
            conversation_history: Previous conversation messages
            **kwargs: Additional generation options
            
        Yields:
            Streaming response text chunks
            
        Raises:
            LLMError: If streaming generation fails
        """
        if not self.is_available():
            raise LLMError("LLM service is not available")
        
        logger.info(f"Starting streaming response generation for query with {len(context_chunks)} chunks")
        
        try:
            # Build context and prompt
            context = self._build_context(context_chunks)
            prompt = self._build_rag_prompt(query, context, conversation_history)
            
            # Stream based on provider
            if self.provider == LLMProvider.OLLAMA:
                async for chunk in self._stream_ollama_response(prompt, **kwargs):
                    yield chunk
            elif self.provider == LLMProvider.OPENAI:
                async for chunk in self._stream_openai_response(prompt, **kwargs):
                    yield chunk
            elif self.provider == LLMProvider.ANTHROPIC:
                async for chunk in self._stream_anthropic_response(prompt, **kwargs):
                    yield chunk
            else:
                raise LLMError(f"Streaming not implemented for provider: {self.provider}")
                
        except Exception as e:
            logger.error(f"Streaming response failed: {e}")
            raise LLMError(f"Streaming generation failed: {e}")
    
    def _build_context(self, context_chunks: List[Dict[str, Any]]) -> str:
        """Build context string from document chunks."""
        if not context_chunks:
            return ""
        
        context_parts = []
        for i, chunk in enumerate(context_chunks):
            # Include source information
            source_info = f"Source {i+1}"
            if chunk.get("document_filename"):
                source_info += f" ({chunk['document_filename']})"
            
            chunk_text = chunk.get("text", "")
            
            context_parts.append(f"--- {source_info} ---\n{chunk_text}")
        
        return "\n\n".join(context_parts)
    
    def _build_rag_prompt(
        self,
        query: str,
        context: str,
        conversation_history: Optional[List[ChatMessage]] = None
    ) -> str:
        """Build RAG prompt template."""
        # Use configured prompt template or default
        template = getattr(self.config, 'prompt_template', None) or self._get_default_rag_template()
        
        # Build conversation context if provided
        conversation_context = ""
        if conversation_history:
            conv_parts = []
            for msg in conversation_history[-5:]:  # Last 5 messages for context
                role = "Human" if msg.role == "user" else "Assistant"
                conv_parts.append(f"{role}: {msg.content}")
            
            if conv_parts:
                conversation_context = "\n\nPrevious Conversation:\n" + "\n".join(conv_parts) + "\n"
        
        # Fill template
        prompt = template.format(
            context=context,
            query=query,
            conversation_context=conversation_context
        )
        
        return prompt
    
    def _get_default_rag_template(self) -> str:
        """Get default RAG prompt template."""
        return """You are a helpful AI assistant with access to relevant document context. Use the provided context to answer the user's question accurately and comprehensively.

Context from documents:
{context}
{conversation_context}
User Question: {query}

Instructions:
1. Answer based primarily on the provided context
2. If the context doesn't contain enough information, say so clearly
3. Cite specific sources when possible
4. Be concise but comprehensive
5. Maintain conversation continuity if there's previous context

Answer:"""
    
    def _extract_sources(self, context_chunks: List[Dict[str, Any]]) -> List[str]:
        """Extract source information from context chunks."""
        sources = []
        seen_docs = set()
        
        for chunk in context_chunks:
            doc_id = chunk.get("document_id")
            filename = chunk.get("document_filename") or chunk.get("filename")
            
            if filename and filename not in seen_docs:
                sources.append(filename)
                seen_docs.add(filename)
            elif doc_id and doc_id not in seen_docs:
                sources.append(f"Document {doc_id}")
                seen_docs.add(doc_id)
        
        return sources
    
    async def _generate_ollama_response(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Generate response using Ollama."""
        try:
            # Use existing Ollama manager
            response = await self.ollama_manager.generate_response(
                prompt=prompt,
                model=self.config.model_name,
                temperature=kwargs.get("temperature", self.config.temperature),
                max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
                **kwargs
            )
            
            return {
                "text": response.get("response", ""),
                "model": response.get("model", self.config.model_name),
                "tokens": response.get("eval_count", 0),
                "confidence": 0.8  # Default confidence for Ollama
            }
            
        except Exception as e:
            raise LLMError(f"Ollama generation failed: {e}")
    
    async def _stream_ollama_response(self, prompt: str, **kwargs) -> AsyncIterator[str]:
        """Stream response using Ollama."""
        try:
            # Use existing Ollama streaming
            async for chunk in self.ollama_manager.stream_response(
                prompt=prompt,
                model=self.config.model_name,
                temperature=kwargs.get("temperature", self.config.temperature),
                **kwargs
            ):
                if chunk and "response" in chunk:
                    yield chunk["response"]
                    
        except Exception as e:
            raise LLMError(f"Ollama streaming failed: {e}")
    
    async def _generate_openai_response(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Generate response using OpenAI."""
        try:
            response = await self.openai_client.chat.completions.create(
                model=self.config.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=kwargs.get("temperature", self.config.temperature),
                max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
            )
            
            return {
                "text": response.choices[0].message.content,
                "model": response.model,
                "tokens": response.usage.completion_tokens if response.usage else 0,
                "confidence": 0.9  # Default confidence for OpenAI
            }
            
        except Exception as e:
            raise LLMError(f"OpenAI generation failed: {e}")
    
    async def _stream_openai_response(self, prompt: str, **kwargs) -> AsyncIterator[str]:
        """Stream response using OpenAI."""
        try:
            stream = await self.openai_client.chat.completions.create(
                model=self.config.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=kwargs.get("temperature", self.config.temperature),
                stream=True,
            )
            
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            raise LLMError(f"OpenAI streaming failed: {e}")
    
    async def _generate_anthropic_response(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Generate response using Anthropic."""
        try:
            response = await self.anthropic_client.messages.create(
                model=self.config.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=kwargs.get("temperature", self.config.temperature),
                max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
            )
            
            return {
                "text": response.content[0].text,
                "model": response.model,
                "tokens": response.usage.output_tokens if hasattr(response, 'usage') else 0,
                "confidence": 0.9  # Default confidence for Anthropic
            }
            
        except Exception as e:
            raise LLMError(f"Anthropic generation failed: {e}")
    
    async def _stream_anthropic_response(self, prompt: str, **kwargs) -> AsyncIterator[str]:
        """Stream response using Anthropic."""
        try:
            async with self.anthropic_client.messages.stream(
                model=self.config.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=kwargs.get("temperature", self.config.temperature),
                max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
            ) as stream:
                async for text in stream.text_stream:
                    yield text
                    
        except Exception as e:
            raise LLMError(f"Anthropic streaming failed: {e}")
    
    async def get_service_info(self) -> Dict[str, Any]:
        """Get information about the LLM service."""
        return {
            "name": "RAGLLMService",
            "provider": self.provider.value,
            "model": self.config.model_name,
            "available": self.is_available(),
            "configuration": {
                "temperature": self.config.temperature,
                "max_tokens": self.config.max_tokens,
                "streaming_enabled": self.config.streaming_enabled,
            },
            "features": {
                "text_generation": True,
                "streaming_generation": True,
                "conversation_memory": True,
                "context_awareness": True,
                "source_citation": True,
            },
            "supported_providers": [provider.value for provider in LLMProvider]
        }
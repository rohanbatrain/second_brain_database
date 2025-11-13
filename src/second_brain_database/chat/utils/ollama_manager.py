"""Ollama LLM Manager for chat system.

This module provides the OllamaLLMManager class for managing Ollama LLM instances,
token counting, and cost estimation for the chat system.
"""

from typing import List, Optional

import tiktoken
from langchain_ollama import ChatOllama

from second_brain_database.config import Settings


class OllamaLLMManager:
    """Manager for Ollama LLM initialization and token tracking.
    
    This class handles:
    - Ollama LLM instance creation with streaming support
    - Token counting using tiktoken (since Ollama doesn't provide counts)
    - Cost estimation (returns 0.0 for Ollama but tracks usage for monitoring)
    
    Attributes:
        host: Ollama API host URL
        model: Default model name for chat operations
        tokenizer: tiktoken encoding for token estimation
    """
    
    def __init__(self, settings: Optional[Settings] = None):
        """Initialize OllamaLLMManager with settings.
        
        Args:
            settings: Application settings instance. If None, creates new Settings instance.
        """
        if settings is None:
            settings = Settings()
            
        self.host = settings.OLLAMA_HOST
        self.model = settings.OLLAMA_CHAT_MODEL
        self.tokenizer = self._init_tokenizer()
    
    def _init_tokenizer(self) -> tiktoken.Encoding:
        """Initialize tiktoken tokenizer for token counting.
        
        Ollama doesn't provide token counts, so we use tiktoken with cl100k_base
        encoding (GPT-4 tokenizer) as an approximation. This is close enough for
        Llama models and provides consistent token tracking.
        
        Returns:
            tiktoken.Encoding: Initialized tokenizer
        """
        return tiktoken.get_encoding("cl100k_base")
    
    def create_llm(
        self,
        model: Optional[str] = None,
        callbacks: Optional[List] = None,
        temperature: float = 0.7,
        streaming: bool = True
    ) -> ChatOllama:
        """Create ChatOllama instance with streaming enabled.
        
        Args:
            model: Model name override. If None, uses default from settings.
            callbacks: List of callback handlers for token tracking and monitoring.
            temperature: Sampling temperature (0.0-1.0). Default 0.7.
            streaming: Enable streaming responses. Default True.
            
        Returns:
            ChatOllama: Configured Ollama LLM instance
        """
        return ChatOllama(
            base_url=self.host,
            model=model or self.model,
            streaming=streaming,
            callbacks=callbacks or [],
            temperature=temperature
        )
    
    def count_tokens(self, text: str) -> int:
        """Estimate token count for text using tiktoken.
        
        Args:
            text: Input text to count tokens for
            
        Returns:
            int: Estimated token count
        """
        return len(self.tokenizer.encode(text))
    
    def estimate_cost(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        model: str
    ) -> float:
        """Estimate cost for token usage.
        
        Ollama is free/local, so this returns 0.0. However, we track token usage
        for monitoring and observability purposes. This method exists to support
        future migration to paid LLM providers.
        
        Args:
            prompt_tokens: Number of tokens in the prompt
            completion_tokens: Number of tokens in the completion
            model: Model name (for future cost calculation)
            
        Returns:
            float: Estimated cost (always 0.0 for Ollama)
        """
        # Ollama is free/local, but we track tokens for monitoring
        return 0.0

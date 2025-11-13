"""Token usage callback handler for LangChain LLM calls.

This module provides a callback handler that tracks token usage during LLM
interactions, using tiktoken for estimation since Ollama doesn't provide
token counts directly.
"""

from typing import Any, Dict, List, Optional

import tiktoken
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult


class TokenUsageCallbackHandler(BaseCallbackHandler):
    """Callback handler for tracking token usage in LLM calls.
    
    This handler captures token usage during LLM interactions by:
    - Estimating prompt tokens when LLM starts
    - Estimating completion tokens when LLM ends
    - Tracking streaming tokens as they're generated
    
    Since Ollama doesn't provide token counts, we use tiktoken for estimation.
    
    Attributes:
        tokenizer: tiktoken encoding for token estimation
        prompt_tokens: Number of tokens in the prompt
        completion_tokens: Number of tokens in the completion
        total_tokens: Total tokens used (prompt + completion)
        streaming_tokens: List of tokens received during streaming
    """
    
    def __init__(self, encoding: str = "cl100k_base"):
        """Initialize TokenUsageCallbackHandler.
        
        Args:
            encoding: tiktoken encoding name. Default "cl100k_base" (GPT-4 tokenizer).
        """
        super().__init__()
        self.tokenizer = tiktoken.get_encoding(encoding)
        self.prompt_tokens: int = 0
        self.completion_tokens: int = 0
        self.total_tokens: int = 0
        self.streaming_tokens: List[str] = []
    
    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        **kwargs: Any
    ) -> None:
        """Capture prompt tokens when LLM starts.
        
        Args:
            serialized: Serialized LLM configuration
            prompts: List of prompt strings
            **kwargs: Additional keyword arguments
        """
        # Estimate tokens for all prompts
        total_prompt_text = " ".join(prompts)
        self.prompt_tokens = len(self.tokenizer.encode(total_prompt_text))
    
    def on_llm_end(
        self,
        response: LLMResult,
        **kwargs: Any
    ) -> None:
        """Capture completion tokens when LLM ends.
        
        Args:
            response: LLM result containing generations
            **kwargs: Additional keyword arguments
        """
        # If we have streaming tokens, use those for completion count
        if self.streaming_tokens:
            completion_text = "".join(self.streaming_tokens)
            self.completion_tokens = len(self.tokenizer.encode(completion_text))
        else:
            # Otherwise, estimate from the response generations
            completion_text = ""
            for generation_list in response.generations:
                for generation in generation_list:
                    completion_text += generation.text
            
            self.completion_tokens = len(self.tokenizer.encode(completion_text))
        
        # Calculate total tokens
        self.total_tokens = self.prompt_tokens + self.completion_tokens
    
    def on_llm_new_token(
        self,
        token: str,
        **kwargs: Any
    ) -> None:
        """Track streaming tokens as they're generated.
        
        Args:
            token: New token string
            **kwargs: Additional keyword arguments
        """
        self.streaming_tokens.append(token)
    
    def get_token_usage(self) -> Dict[str, int]:
        """Get token usage statistics.
        
        Returns:
            Dict containing prompt_tokens, completion_tokens, and total_tokens
        """
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens
        }
    
    def reset(self) -> None:
        """Reset token counters for reuse."""
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0
        self.streaming_tokens = []

"""Unit tests for OllamaLLMManager."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from second_brain_database.chat.utils.ollama_manager import OllamaLLMManager


class TestOllamaLLMManager:
    """Test OllamaLLMManager functionality."""

    @patch("second_brain_database.chat.utils.ollama_manager.Settings")
    def test_initialization(self, mock_settings_class):
        """Test OllamaLLMManager initialization."""
        mock_settings = Mock()
        mock_settings.OLLAMA_HOST = "http://localhost:11434"
        mock_settings.OLLAMA_CHAT_MODEL = "llama3.2"
        mock_settings_class.return_value = mock_settings
        
        manager = OllamaLLMManager()
        
        assert manager.host == "http://localhost:11434"
        assert manager.model == "llama3.2"
        assert manager.tokenizer is not None

    @patch("second_brain_database.chat.utils.ollama_manager.ChatOllama")
    def test_create_llm_default_model(self, mock_chat_ollama):
        """Test creating LLM with default model."""
        mock_settings = Mock()
        mock_settings.OLLAMA_HOST = "http://localhost:11434"
        mock_settings.OLLAMA_CHAT_MODEL = "llama3.2"
        
        manager = OllamaLLMManager(settings=mock_settings)
        llm = manager.create_llm()
        
        mock_chat_ollama.assert_called_once()
        call_kwargs = mock_chat_ollama.call_args[1]
        assert call_kwargs["base_url"] == "http://localhost:11434"
        assert call_kwargs["model"] == "llama3.2"
        assert call_kwargs["streaming"] is True

    @patch("second_brain_database.chat.utils.ollama_manager.ChatOllama")
    def test_create_llm_custom_model(self, mock_chat_ollama):
        """Test creating LLM with custom model."""
        mock_settings = Mock()
        mock_settings.OLLAMA_HOST = "http://localhost:11434"
        mock_settings.OLLAMA_CHAT_MODEL = "llama3.2"
        
        manager = OllamaLLMManager(settings=mock_settings)
        llm = manager.create_llm(model="custom-model")
        
        call_kwargs = mock_chat_ollama.call_args[1]
        assert call_kwargs["model"] == "custom-model"

    @patch("second_brain_database.chat.utils.ollama_manager.ChatOllama")
    def test_create_llm_with_callbacks(self, mock_chat_ollama):
        """Test creating LLM with callbacks."""
        mock_settings = Mock()
        mock_settings.OLLAMA_HOST = "http://localhost:11434"
        mock_settings.OLLAMA_CHAT_MODEL = "llama3.2"
        
        mock_callback = Mock()
        manager = OllamaLLMManager(settings=mock_settings)
        llm = manager.create_llm(callbacks=[mock_callback])
        
        call_kwargs = mock_chat_ollama.call_args[1]
        assert mock_callback in call_kwargs["callbacks"]

    def test_count_tokens(self):
        """Test token counting with sample text."""
        mock_settings = Mock()
        mock_settings.OLLAMA_HOST = "http://localhost:11434"
        mock_settings.OLLAMA_CHAT_MODEL = "llama3.2"
        
        manager = OllamaLLMManager(settings=mock_settings)
        
        # Test with simple text
        text = "Hello, world!"
        token_count = manager.count_tokens(text)
        
        assert isinstance(token_count, int)
        assert token_count > 0
        
        # Longer text should have more tokens
        longer_text = "This is a much longer piece of text that should have more tokens."
        longer_count = manager.count_tokens(longer_text)
        
        assert longer_count > token_count

    def test_count_tokens_empty_string(self):
        """Test token counting with empty string."""
        mock_settings = Mock()
        mock_settings.OLLAMA_HOST = "http://localhost:11434"
        mock_settings.OLLAMA_CHAT_MODEL = "llama3.2"
        
        manager = OllamaLLMManager(settings=mock_settings)
        token_count = manager.count_tokens("")
        
        assert token_count == 0

    def test_estimate_cost_ollama(self):
        """Test cost estimation for Ollama (should return 0.0)."""
        mock_settings = Mock()
        mock_settings.OLLAMA_HOST = "http://localhost:11434"
        mock_settings.OLLAMA_CHAT_MODEL = "llama3.2"
        
        manager = OllamaLLMManager(settings=mock_settings)
        cost = manager.estimate_cost(100, 50, "llama3.2")
        
        # Ollama is free/local, so cost should be 0.0
        assert cost == 0.0

    def test_estimate_cost_different_models(self):
        """Test cost estimation with different models."""
        mock_settings = Mock()
        mock_settings.OLLAMA_HOST = "http://localhost:11434"
        mock_settings.OLLAMA_CHAT_MODEL = "llama3.2"
        
        manager = OllamaLLMManager(settings=mock_settings)
        
        # All Ollama models should return 0.0 cost
        cost1 = manager.estimate_cost(100, 50, "llama3.2")
        cost2 = manager.estimate_cost(200, 100, "mistral")
        cost3 = manager.estimate_cost(500, 250, "codellama")
        
        assert cost1 == 0.0
        assert cost2 == 0.0
        assert cost3 == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""Unit tests for InputSanitizer."""

import pytest
from pydantic import ValidationError

from second_brain_database.chat.utils.input_sanitizer import InputSanitizer


class TestInputSanitizer:
    """Test InputSanitizer functionality."""

    def test_sanitize_query_basic(self):
        """Test basic query sanitization."""
        query = "  Hello, world!  "
        sanitized = InputSanitizer.sanitize_query(query)
        
        assert sanitized == "Hello, world!"
        assert not sanitized.startswith(" ")
        assert not sanitized.endswith(" ")

    def test_sanitize_query_removes_null_bytes(self):
        """Test that null bytes are removed."""
        query = "Hello\x00world"
        sanitized = InputSanitizer.sanitize_query(query)
        
        assert "\x00" not in sanitized
        assert sanitized == "Helloworld"

    def test_sanitize_query_normalizes_unicode(self):
        """Test unicode normalization."""
        # Using composed vs decomposed unicode
        query = "café"  # é as single character
        sanitized = InputSanitizer.sanitize_query(query)
        
        # Should be normalized to NFC form
        assert sanitized == "café"
        assert isinstance(sanitized, str)

    def test_sanitize_query_length_limit(self):
        """Test query length limit enforcement."""
        # Create a query longer than MAX_QUERY_LENGTH (10,000 chars)
        long_query = "a" * 15000
        
        with pytest.raises(ValueError) as exc_info:
            InputSanitizer.sanitize_query(long_query)
        
        assert "exceeds maximum length" in str(exc_info.value).lower()

    def test_sanitize_query_empty_string(self):
        """Test sanitizing empty string."""
        query = "   "
        sanitized = InputSanitizer.sanitize_query(query)
        
        assert sanitized == ""

    def test_sanitize_query_special_characters(self):
        """Test that special characters are preserved."""
        query = "What is 2+2? Tell me about <html> & \"quotes\""
        sanitized = InputSanitizer.sanitize_query(query)
        
        # Special characters should be preserved
        assert "?" in sanitized
        assert "<" in sanitized
        assert ">" in sanitized
        assert "&" in sanitized
        assert '"' in sanitized

    def test_sanitize_message_content_basic(self):
        """Test basic message content sanitization."""
        content = "  This is a message  "
        sanitized = InputSanitizer.sanitize_message_content(content)
        
        assert sanitized == "This is a message"

    def test_sanitize_message_content_length_limit(self):
        """Test message content length limit (50,000 chars)."""
        # Create content longer than MAX_MESSAGE_LENGTH
        long_content = "a" * 60000
        
        with pytest.raises(ValueError) as exc_info:
            InputSanitizer.sanitize_message_content(long_content)
        
        assert "exceeds maximum length" in str(exc_info.value).lower()

    def test_sanitize_message_content_multiline(self):
        """Test multiline message content."""
        content = """
        Line 1
        Line 2
        Line 3
        """
        sanitized = InputSanitizer.sanitize_message_content(content)
        
        # Should preserve line breaks but trim outer whitespace
        assert "Line 1" in sanitized
        assert "Line 2" in sanitized
        assert "Line 3" in sanitized

    def test_validate_session_id_valid_uuid(self):
        """Test validating valid UUID session ID."""
        session_id = "550e8400-e29b-41d4-a716-446655440000"
        
        # Should not raise exception
        InputSanitizer.validate_session_id(session_id)

    def test_validate_session_id_invalid_format(self):
        """Test validating invalid UUID format."""
        invalid_ids = [
            "not-a-uuid",
            "12345",
            "550e8400-e29b-41d4-a716",  # Incomplete
            "550e8400-e29b-41d4-a716-446655440000-extra",  # Too long
        ]
        
        for invalid_id in invalid_ids:
            result = InputSanitizer.validate_session_id(invalid_id)
            assert result is False, f"Expected {invalid_id} to be invalid"

    def test_validate_knowledge_base_id_valid(self):
        """Test validating valid knowledge base ID."""
        valid_ids = [
            "kb_123",
            "knowledge-base-456",
            "KB789",
            "kb_test_123",
        ]
        
        for kb_id in valid_ids:
            result = InputSanitizer.validate_knowledge_base_id(kb_id)
            assert result is True, f"Expected {kb_id} to be valid"

    def test_validate_knowledge_base_id_invalid(self):
        """Test validating invalid knowledge base ID."""
        invalid_ids = [
            "kb with spaces",
            "kb@special",
            "kb#123",
            "",
            "   ",
        ]
        
        for invalid_id in invalid_ids:
            result = InputSanitizer.validate_knowledge_base_id(invalid_id)
            assert result is False, f"Expected {invalid_id} to be invalid"

    def test_sanitize_query_preserves_meaning(self):
        """Test that sanitization preserves query meaning."""
        queries = [
            "What is the capital of France?",
            "How do I install Python?",
            "Tell me about machine learning",
            "2 + 2 = ?",
        ]
        
        for query in queries:
            sanitized = InputSanitizer.sanitize_query(query)
            # Core content should be preserved
            assert len(sanitized) > 0
            # Should be similar to original (allowing for whitespace changes)
            assert sanitized.replace(" ", "") == query.replace(" ", "")

    def test_sanitize_handles_none(self):
        """Test handling None input."""
        with pytest.raises((ValueError, TypeError, AttributeError)):
            InputSanitizer.sanitize_query(None)

    def test_validate_session_id_with_hyphens(self):
        """Test UUID validation with different hyphen patterns."""
        # Standard UUID format
        valid_uuid = "123e4567-e89b-12d3-a456-426614174000"
        result = InputSanitizer.validate_session_id(valid_uuid)
        assert result is True
        
        # UUID without hyphens should fail
        result = InputSanitizer.validate_session_id("123e4567e89b12d3a456426614174000")
        assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

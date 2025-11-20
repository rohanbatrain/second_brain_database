"""Input sanitization utilities for chat system.

This module provides comprehensive input validation and sanitization for the chat system,
protecting against injection attacks, malformed data, and excessive input lengths.

Key Features:
- Query and message content sanitization
- Length limit enforcement
- Null byte removal
- Unicode normalization
- UUID format validation
- Alphanumeric ID validation

Security Considerations:
- All user inputs should be sanitized before processing
- Length limits prevent resource exhaustion attacks
- Unicode normalization prevents homograph attacks
- Null byte removal prevents string termination attacks
"""

import re
import unicodedata
from typing import Optional

from second_brain_database.config import Settings

# Initialize settings instance
_settings = Settings()


class InputSanitizer:
    """Sanitize and validate user inputs for the chat system.
    
    This class provides static methods for sanitizing queries, messages, and validating
    various ID formats to ensure data integrity and security.
    """

    # Maximum lengths from configuration
    MAX_QUERY_LENGTH: int = _settings.CHAT_MAX_QUERY_LENGTH  # 10,000 characters
    MAX_MESSAGE_LENGTH: int = _settings.CHAT_MAX_MESSAGE_LENGTH  # 50,000 characters

    # Validation patterns
    UUID_PATTERN: re.Pattern = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        re.IGNORECASE
    )
    KNOWLEDGE_BASE_ID_PATTERN: re.Pattern = re.compile(r"^[a-zA-Z0-9\-_]+$")

    @staticmethod
    def sanitize_query(query: str) -> str:
        """Sanitize user query before processing.
        
        Performs the following operations:
        1. Strip leading/trailing whitespace
        2. Enforce maximum length limit
        3. Remove null bytes
        4. Normalize unicode characters
        
        Args:
            query: Raw user query string
            
        Returns:
            Sanitized query string
            
        Raises:
            ValueError: If query exceeds maximum length
            
        Example:
            >>> sanitizer = InputSanitizer()
            >>> sanitizer.sanitize_query("  Hello world!  ")
            'Hello world!'
        """
        if not isinstance(query, str):
            raise TypeError(f"Query must be a string, got {type(query).__name__}")

        # Strip leading/trailing whitespace
        query = query.strip()

        # Check length limit
        if len(query) > InputSanitizer.MAX_QUERY_LENGTH:
            raise ValueError(
                f"Query exceeds maximum length of {InputSanitizer.MAX_QUERY_LENGTH} characters "
                f"(got {len(query)} characters)"
            )

        # Remove null bytes (prevent string termination attacks)
        query = query.replace("\x00", "")

        # Normalize unicode (prevent homograph attacks)
        # NFKC: Compatibility decomposition followed by canonical composition
        query = unicodedata.normalize("NFKC", query)

        return query

    @staticmethod
    def sanitize_message_content(content: str) -> str:
        """Sanitize message content before storage.
        
        Similar to sanitize_query but with a higher length limit for message content.
        
        Performs the following operations:
        1. Strip leading/trailing whitespace
        2. Enforce maximum message length limit
        3. Remove null bytes
        4. Normalize unicode characters
        
        Args:
            content: Raw message content string
            
        Returns:
            Sanitized message content string
            
        Raises:
            ValueError: If content exceeds maximum length
            
        Example:
            >>> sanitizer = InputSanitizer()
            >>> sanitizer.sanitize_message_content("  Long message...  ")
            'Long message...'
        """
        if not isinstance(content, str):
            raise TypeError(f"Content must be a string, got {type(content).__name__}")

        # Strip leading/trailing whitespace
        content = content.strip()

        # Check length limit (higher than query limit)
        if len(content) > InputSanitizer.MAX_MESSAGE_LENGTH:
            raise ValueError(
                f"Message content exceeds maximum length of {InputSanitizer.MAX_MESSAGE_LENGTH} characters "
                f"(got {len(content)} characters)"
            )

        # Remove null bytes
        content = content.replace("\x00", "")

        # Normalize unicode
        content = unicodedata.normalize("NFKC", content)

        return content

    @staticmethod
    def validate_session_id(session_id: str) -> bool:
        """Validate session ID format (UUID).
        
        Ensures the session ID is a valid UUID v4 format.
        
        Args:
            session_id: Session ID to validate
            
        Returns:
            True if valid UUID format, False otherwise
            
        Example:
            >>> sanitizer = InputSanitizer()
            >>> sanitizer.validate_session_id("550e8400-e29b-41d4-a716-446655440000")
            True
            >>> sanitizer.validate_session_id("invalid-id")
            False
        """
        if not isinstance(session_id, str):
            return False

        # Check UUID format (case-insensitive)
        return bool(InputSanitizer.UUID_PATTERN.match(session_id.lower()))

    @staticmethod
    def validate_knowledge_base_id(kb_id: str) -> bool:
        """Validate knowledge base ID format.
        
        Ensures the knowledge base ID contains only alphanumeric characters,
        hyphens, and underscores.
        
        Args:
            kb_id: Knowledge base ID to validate
            
        Returns:
            True if valid format, False otherwise
            
        Example:
            >>> sanitizer = InputSanitizer()
            >>> sanitizer.validate_knowledge_base_id("kb_123-abc")
            True
            >>> sanitizer.validate_knowledge_base_id("kb@123")
            False
        """
        if not isinstance(kb_id, str):
            return False

        # Check alphanumeric + hyphens + underscores only
        return bool(InputSanitizer.KNOWLEDGE_BASE_ID_PATTERN.match(kb_id))

    @staticmethod
    def sanitize_and_validate_session_id(session_id: str) -> str:
        """Sanitize and validate session ID in one operation.
        
        Combines sanitization and validation for convenience.
        
        Args:
            session_id: Session ID to sanitize and validate
            
        Returns:
            Sanitized session ID
            
        Raises:
            ValueError: If session ID is invalid format
            
        Example:
            >>> sanitizer = InputSanitizer()
            >>> sanitizer.sanitize_and_validate_session_id("  550e8400-e29b-41d4-a716-446655440000  ")
            '550e8400-e29b-41d4-a716-446655440000'
        """
        if not isinstance(session_id, str):
            raise TypeError(f"Session ID must be a string, got {type(session_id).__name__}")

        # Strip whitespace
        session_id = session_id.strip()

        # Validate format
        if not InputSanitizer.validate_session_id(session_id):
            raise ValueError(f"Invalid session ID format: {session_id}")

        return session_id.lower()

    @staticmethod
    def sanitize_and_validate_knowledge_base_id(kb_id: str) -> str:
        """Sanitize and validate knowledge base ID in one operation.
        
        Combines sanitization and validation for convenience.
        
        Args:
            kb_id: Knowledge base ID to sanitize and validate
            
        Returns:
            Sanitized knowledge base ID
            
        Raises:
            ValueError: If knowledge base ID is invalid format
            
        Example:
            >>> sanitizer = InputSanitizer()
            >>> sanitizer.sanitize_and_validate_knowledge_base_id("  kb_123  ")
            'kb_123'
        """
        if not isinstance(kb_id, str):
            raise TypeError(f"Knowledge base ID must be a string, got {type(kb_id).__name__}")

        # Strip whitespace
        kb_id = kb_id.strip()

        # Validate format
        if not InputSanitizer.validate_knowledge_base_id(kb_id):
            raise ValueError(
                f"Invalid knowledge base ID format: {kb_id}. "
                "Must contain only alphanumeric characters, hyphens, and underscores."
            )

        return kb_id

    @staticmethod
    def sanitize_title(title: Optional[str], max_length: int = 100) -> Optional[str]:
        """Sanitize session or message title.
        
        Args:
            title: Title to sanitize (can be None)
            max_length: Maximum allowed length
            
        Returns:
            Sanitized title or None if input was None
            
        Example:
            >>> sanitizer = InputSanitizer()
            >>> sanitizer.sanitize_title("  My Chat Session  ", max_length=50)
            'My Chat Session'
        """
        if title is None:
            return None

        if not isinstance(title, str):
            raise TypeError(f"Title must be a string or None, got {type(title).__name__}")

        # Strip whitespace
        title = title.strip()

        # Return None if empty after stripping
        if not title:
            return None

        # Enforce length limit
        if len(title) > max_length:
            title = title[:max_length].strip()

        # Remove null bytes
        title = title.replace("\x00", "")

        # Normalize unicode
        title = unicodedata.normalize("NFKC", title)

        return title

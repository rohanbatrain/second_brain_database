"""
RAG System Exceptions

Custom exception classes for the RAG system providing detailed error information
and proper error handling hierarchy.
"""

from typing import Any, Dict, Optional


class RAGError(Exception):
    """Base exception for all RAG system errors."""
    
    def __init__(
        self, 
        message: str, 
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        """
        Initialize RAG error.
        
        Args:
            message: Human-readable error message
            error_code: Optional error code for programmatic handling
            details: Optional additional error details
            original_error: Optional original exception that caused this error
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.original_error = original_error
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for API responses."""
        result = {
            "error": self.__class__.__name__,
            "message": self.message,
        }
        
        if self.error_code:
            result["error_code"] = self.error_code
            
        if self.details:
            result["details"] = self.details
            
        if self.original_error:
            result["original_error"] = str(self.original_error)
            
        return result


class DocumentProcessingError(RAGError):
    """Errors related to document processing and parsing."""
    
    def __init__(
        self,
        message: str,
        file_path: Optional[str] = None,
        file_type: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize document processing error.
        
        Args:
            message: Error message
            file_path: Path to the problematic file
            file_type: Type of the problematic file
            **kwargs: Additional arguments for RAGError
        """
        details = kwargs.get('details', {})
        if file_path:
            details['file_path'] = file_path
        if file_type:
            details['file_type'] = file_type
            
        kwargs['details'] = details
        super().__init__(message, **kwargs)


class DocumentParsingError(DocumentProcessingError):
    """Specific error for document parsing failures."""
    pass


class DocumentExtractionError(DocumentProcessingError):
    """Specific error for content extraction failures."""
    pass


class UnsupportedDocumentFormatError(DocumentProcessingError):
    """Error for unsupported document formats."""
    
    def __init__(self, file_type: str, supported_formats: list = None, **kwargs):
        message = f"Unsupported document format: {file_type}"
        if supported_formats:
            message += f". Supported formats: {', '.join(supported_formats)}"
            
        super().__init__(
            message=message,
            file_type=file_type,
            error_code="UNSUPPORTED_FORMAT",
            **kwargs
        )


class VectorStoreError(RAGError):
    """Errors related to vector store operations."""
    
    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        operation: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize vector store error.
        
        Args:
            message: Error message
            provider: Vector store provider name
            operation: Operation that failed
            **kwargs: Additional arguments for RAGError
        """
        details = kwargs.get('details', {})
        if provider:
            details['provider'] = provider
        if operation:
            details['operation'] = operation
            
        kwargs['details'] = details
        super().__init__(message, **kwargs)


class VectorStoreConnectionError(VectorStoreError):
    """Error for vector store connection failures."""
    pass


class VectorStoreIndexError(VectorStoreError):
    """Error for vector indexing failures."""
    pass


class VectorStoreSearchError(VectorStoreError):
    """Error for vector search failures."""
    pass


class LLMError(RAGError):
    """Errors related to language model operations."""
    
    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize LLM error.
        
        Args:
            message: Error message
            provider: LLM provider name
            model_name: Name of the model
            **kwargs: Additional arguments for RAGError
        """
        details = kwargs.get('details', {})
        if provider:
            details['provider'] = provider
        if model_name:
            details['model_name'] = model_name
            
        kwargs['details'] = details
        super().__init__(message, **kwargs)


class LLMConnectionError(LLMError):
    """Error for LLM connection failures."""
    pass


class LLMGenerationError(LLMError):
    """Error for text generation failures."""
    pass


class LLMRateLimitError(LLMError):
    """Error for rate limit exceeded."""
    pass


class EmbeddingError(RAGError):
    """Errors related to embedding operations."""
    
    def __init__(
        self,
        message: str,
        model_name: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize embedding error.
        
        Args:
            message: Error message
            model_name: Name of the embedding model
            **kwargs: Additional arguments for RAGError
        """
        details = kwargs.get('details', {})
        if model_name:
            details['model_name'] = model_name
            
        kwargs['details'] = details
        super().__init__(message, **kwargs)


class QueryEngineError(RAGError):
    """Errors related to query engine operations."""
    
    def __init__(
        self,
        message: str,
        query: Optional[str] = None,
        operation: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize query engine error.
        
        Args:
            message: Error message
            query: The query that failed
            operation: Operation that failed
            **kwargs: Additional arguments for RAGError
        """
        details = kwargs.get('details', {})
        if query:
            details['query'] = query
        if operation:
            details['operation'] = operation
            
        kwargs['details'] = details
        super().__init__(message, **kwargs)


class QueryRetrievalError(QueryEngineError):
    """Error for document retrieval failures."""
    pass


class QueryRerankingError(QueryEngineError):
    """Error for result reranking failures."""
    pass


class ContextBuildingError(QueryEngineError):
    """Error for context building failures."""
    pass


class AnswerGenerationError(QueryEngineError):
    """Error for answer generation failures."""
    pass


class ConfigurationError(RAGError):
    """Errors related to system configuration."""
    
    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        config_value: Optional[Any] = None,
        **kwargs
    ):
        """
        Initialize configuration error.
        
        Args:
            message: Error message
            config_key: Configuration key that failed
            config_value: Configuration value that failed
            **kwargs: Additional arguments for RAGError
        """
        details = kwargs.get('details', {})
        if config_key:
            details['config_key'] = config_key
        if config_value is not None:
            details['config_value'] = str(config_value)
            
        kwargs['details'] = details
        super().__init__(message, **kwargs)


class ValidationError(RAGError):
    """Errors related to input validation."""
    
    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        **kwargs
    ):
        """
        Initialize validation error.
        
        Args:
            message: Error message
            field: Field that failed validation
            value: Value that failed validation
            **kwargs: Additional arguments for RAGError
        """
        details = kwargs.get('details', {})
        if field:
            details['field'] = field
        if value is not None:
            details['value'] = str(value)
            
        kwargs['details'] = details
        super().__init__(message, **kwargs)


class AuthenticationError(RAGError):
    """Errors related to authentication and authorization."""
    pass


class PermissionError(RAGError):
    """Errors related to permissions and access control."""
    
    def __init__(
        self,
        message: str,
        user_id: Optional[str] = None,
        resource: Optional[str] = None,
        action: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize permission error.
        
        Args:
            message: Error message
            user_id: ID of the user
            resource: Resource being accessed
            action: Action being performed
            **kwargs: Additional arguments for RAGError
        """
        details = kwargs.get('details', {})
        if user_id:
            details['user_id'] = user_id
        if resource:
            details['resource'] = resource
        if action:
            details['action'] = action
            
        kwargs['details'] = details
        super().__init__(message, **kwargs)


class RateLimitError(RAGError):
    """Errors related to rate limiting."""
    
    def __init__(
        self,
        message: str,
        limit: Optional[int] = None,
        window: Optional[int] = None,
        retry_after: Optional[int] = None,
        **kwargs
    ):
        """
        Initialize rate limit error.
        
        Args:
            message: Error message
            limit: Rate limit that was exceeded
            window: Time window for the limit
            retry_after: Seconds to wait before retrying
            **kwargs: Additional arguments for RAGError
        """
        details = kwargs.get('details', {})
        if limit:
            details['limit'] = limit
        if window:
            details['window'] = window
        if retry_after:
            details['retry_after'] = retry_after
            
        kwargs['details'] = details
        super().__init__(message, **kwargs)


# Exception mapping for HTTP status codes
EXCEPTION_STATUS_MAP = {
    ValidationError: 400,
    UnsupportedDocumentFormatError: 400,
    AuthenticationError: 401,
    PermissionError: 403,
    RateLimitError: 429,
    VectorStoreConnectionError: 503,
    LLMConnectionError: 503,
    RAGError: 500,  # Default for unspecified errors
}


def get_http_status_code(exception: Exception) -> int:
    """
    Get HTTP status code for an exception.
    
    Args:
        exception: The exception to get status code for
        
    Returns:
        HTTP status code
    """
    for exc_type, status_code in EXCEPTION_STATUS_MAP.items():
        if isinstance(exception, exc_type):
            return status_code
    return 500  # Default server error


def format_error_response(exception: Exception) -> Dict[str, Any]:
    """
    Format an exception into a standard error response.
    
    Args:
        exception: The exception to format
        
    Returns:
        Formatted error response dictionary
    """
    if isinstance(exception, RAGError):
        return exception.to_dict()
    
    return {
        "error": exception.__class__.__name__,
        "message": str(exception),
    }
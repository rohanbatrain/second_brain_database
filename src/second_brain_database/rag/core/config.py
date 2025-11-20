"""
RAG Core Configuration

Comprehensive configuration management for the RAG system.
Provides settings for all components including document processing, vector stores,
LLM providers, and query engine parameters.
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, ConfigDict

from second_brain_database.config import settings


class VectorStoreProvider(str, Enum):
    """Supported vector store providers."""
    QDRANT = "qdrant"
    CHROMA = "chroma"
    PINECONE = "pinecone"
    ELASTICSEARCH = "elasticsearch"


class LLMProvider(str, Enum):
    """Supported LLM providers."""
    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    HUGGINGFACE = "huggingface"


class DocumentFormat(str, Enum):
    """Supported document formats."""
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    MD = "md"
    HTML = "html"
    JSON = "json"


class EmbeddingModel(str, Enum):
    """Supported embedding models."""
    BGE_LARGE = "BAAI/bge-large-en-v1.5"
    BGE_BASE = "BAAI/bge-base-en-v1.5"
    OPENAI_SMALL = "text-embedding-3-small"
    OPENAI_LARGE = "text-embedding-3-large"
    SENTENCE_TRANSFORMERS = "sentence-transformers/all-mpnet-base-v2"


class DocumentProcessingConfig(BaseModel):
    """Configuration for document processing."""
    
    # Parser settings
    use_docling: bool = True
    extract_images: bool = True
    extract_tables: bool = True
    extract_metadata: bool = True
    
    # Chunking settings
    chunk_size: int = 1024
    chunk_overlap: int = 200
    chunk_strategy: str = "recursive"  # recursive, semantic, fixed
    
    # Processing options
    clean_text: bool = True
    normalize_text: bool = True
    extract_entities: bool = False
    
    # File handling
    max_file_size_mb: int = 100
    supported_formats: List[DocumentFormat] = Field(default_factory=lambda: [
        DocumentFormat.PDF,
        DocumentFormat.DOCX, 
        DocumentFormat.TXT,
        DocumentFormat.MD,
        DocumentFormat.HTML,
    ])
    
    # Temporary storage
    temp_dir: Optional[str] = None
    cleanup_temp_files: bool = True


class VectorStoreConfig(BaseModel):
    """Configuration for vector stores."""
    
    provider: VectorStoreProvider = VectorStoreProvider.QDRANT
    
    # Connection settings
    url: Optional[str] = None
    api_key: Optional[str] = None
    collection_name: str = "rag_documents"
    
    # Embedding settings
    embedding_model: EmbeddingModel = EmbeddingModel.BGE_LARGE
    embedding_dimension: int = 1024
    
    # Search settings
    similarity_threshold: float = 0.7
    max_results: int = 10
    default_top_k: int = 5
    
    # Index settings
    index_settings: Dict[str, Any] = Field(default_factory=dict)
    
    @field_validator('url')
    @classmethod
    def set_default_url(cls, v, info):
        """Set default URL based on provider."""
        if v is None:
            provider = info.data.get('provider')
            if provider == VectorStoreProvider.QDRANT:
                return getattr(settings, 'QDRANT_URL', 'http://localhost:6333')
            elif provider == VectorStoreProvider.CHROMA:
                return "http://localhost:8000"
        return v


class LLMConfig(BaseModel):
    """Configuration for LLM providers."""
    
    provider: LLMProvider = LLMProvider.OLLAMA
    
    # Model settings
    model_name: str = "llama3.2"
    max_tokens: int = 2048
    temperature: float = 0.7
    
    # Connection settings
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    timeout: float = 120.0
    
    # Streaming settings
    streaming: bool = True
    streaming_enabled: bool = True  # Alias for compatibility
    stream_chunk_size: int = 1024
    
    # Prompt settings
    system_prompt: Optional[str] = None
    custom_prompts: Dict[str, str] = Field(default_factory=dict)
    
    @field_validator('base_url')
    @classmethod
    def set_default_base_url(cls, v, info):
        """Set default base URL based on provider."""
        if v is None:
            provider = info.data.get('provider')
            if provider == LLMProvider.OLLAMA:
                return getattr(settings, 'OLLAMA_HOST', 'http://localhost:11434')
            elif provider == LLMProvider.OPENAI:
                return "https://api.openai.com/v1"
        return v


class QueryEngineConfig(BaseModel):
    """Configuration for query engine."""
    
    # Retrieval settings
    retrieval_strategy: str = "hybrid"  # vector, keyword, hybrid
    top_k: int = 5
    rerank_results: bool = True
    
    # Context building
    max_context_length: int = 4000
    context_overlap: int = 100
    include_metadata: bool = True
    
    # Answer generation
    use_llm: bool = True
    citation_style: str = "numbered"  # numbered, inline, none
    
    # Performance settings
    cache_results: bool = True
    cache_ttl_seconds: int = 3600
    parallel_processing: bool = True
    
    # Quality settings
    min_confidence_score: float = 0.5
    max_answer_length: int = 1000


class MonitoringConfig(BaseModel):
    """Configuration for monitoring and observability."""
    
    # Logging settings
    log_level: str = "INFO"
    log_queries: bool = True
    log_responses: bool = False  # May contain sensitive data
    
    # Metrics settings
    collect_metrics: bool = True
    metrics_namespace: str = "rag"
    
    # Performance tracking
    track_response_times: bool = True
    track_token_usage: bool = True
    
    # Health checks
    health_check_interval: int = 60
    vector_store_health_check: bool = True
    llm_health_check: bool = True


class RAGConfig(BaseModel):
    """Main RAG system configuration."""
    
    # Component configurations
    document_processing: DocumentProcessingConfig = Field(default_factory=DocumentProcessingConfig)
    vector_store: VectorStoreConfig = Field(default_factory=VectorStoreConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    query_engine: QueryEngineConfig = Field(default_factory=QueryEngineConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    
    # Global settings
    debug_mode: bool = False
    async_processing: bool = True
    max_concurrent_operations: int = 10
    
    # Feature flags
    enable_streaming: bool = True
    enable_caching: bool = True
    enable_monitoring: bool = True
    enable_docling: bool = True
    
    # Integration settings
    llamaindex_enabled: bool = True
    mcp_integration: bool = True
    
    model_config = ConfigDict(
        use_enum_values=True,
        validate_assignment=True
    )
        
    @classmethod
    def from_settings(cls, custom_config: Optional[Dict[str, Any]] = None) -> 'RAGConfig':
        """
        Create RAG config from application settings.
        
        Args:
            custom_config: Optional custom configuration overrides
            
        Returns:
            RAG configuration instance
        """
        config_data = {}
        
        # Extract relevant settings
        if hasattr(settings, 'QDRANT_URL'):
            config_data.setdefault('vector_store', {})['url'] = settings.QDRANT_URL
            
        if hasattr(settings, 'OLLAMA_HOST'):
            config_data.setdefault('llm', {})['base_url'] = settings.OLLAMA_HOST
            
        if hasattr(settings, 'DEBUG') and settings.DEBUG:
            config_data['debug_mode'] = True
            config_data.setdefault('monitoring', {})['log_level'] = 'DEBUG'
        
        # Apply custom overrides
        if custom_config:
            config_data.update(custom_config)
            
        return cls(**config_data)
    
    def get_vector_store_url(self) -> str:
        """Get the vector store URL with fallbacks."""
        if self.vector_store.url:
            return self.vector_store.url
            
        # Fallback to settings
        if self.vector_store.provider == VectorStoreProvider.QDRANT:
            return getattr(settings, 'QDRANT_URL', 'http://localhost:6333')
        
        return 'http://localhost:8000'
    
    def get_llm_base_url(self) -> str:
        """Get the LLM base URL with fallbacks."""
        if self.llm.base_url:
            return self.llm.base_url
            
        # Fallback to settings
        if self.llm.provider == LLMProvider.OLLAMA:
            return getattr(settings, 'OLLAMA_HOST', 'http://localhost:11434')
        
        return 'http://localhost:11434'
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return self.dict()
    
    def update(self, **kwargs) -> None:
        """Update configuration with new values."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
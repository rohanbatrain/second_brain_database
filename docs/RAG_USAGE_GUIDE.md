# RAG (Retrieval-Augmented Generation) Usage Guide

## Overview
Your Second Brain Database includes a powerful RAG system that allows you to query your documents using natural language and get AI-powered responses. The system combines vector search, LLM generation, and document processing for intelligent document interaction.

## System Architecture

### Core Components

1. **RAGService** (`src/second_brain_database/services/rag_service.py`)
   - Main entry point for RAG functionality
   - Handles query processing, context building, and answer generation
   - Integrates with both LlamaIndex and fallback vector search

2. **LlamaIndex Integration** (`src/second_brain_database/managers/llamaindex_vector_manager.py`)
   - Advanced RAG with hybrid search capabilities
   - Uses Qdrant for vector storage
   - Supports embedding models and sparse retrieval

3. **Vector Search Manager** (`src/second_brain_database/managers/vector_search_manager.py`)
   - Fallback vector search system
   - Direct Qdrant integration with sentence transformers
   - Semantic search capabilities

4. **Document Service** (`src/second_brain_database/services/document_service.py`)
   - Document processing and indexing
   - Chunking for RAG optimization
   - Metadata extraction

## Setup and Configuration

### 1. Environment Configuration

Copy and customize your configuration file:
```bash
cp .sbd-example .sbd
```

Key RAG-related settings in `.sbd`:
```bash
# Vector Search & RAG Configuration
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_API_KEY=
QDRANT_HTTPS=False
QDRANT_COLLECTION_NAME=document_embeddings
QDRANT_VECTOR_SIZE=768
QDRANT_DISTANCE_METRIC=Cosine

# LlamaIndex Configuration
LLAMAINDEX_ENABLED=True
LLAMAINDEX_EMBED_MODEL=local:BAAI/bge-small-en-v1.5
LLAMAINDEX_CHUNK_SIZE=1024
LLAMAINDEX_CHUNK_OVERLAP=200
LLAMAINDEX_TOP_K=5
LLAMAINDEX_SIMILARITY_CUTOFF=0.7
LLAMAINDEX_HYBRID_SEARCH_ENABLED=True

# RAG Settings
RAG_TOP_K=5
RAG_SIMILARITY_THRESHOLD=0.7
RAG_MAX_CONTEXT_LENGTH=8000
RAG_ENABLE_RERANKING=False

# Ollama Integration
OLLAMA_ENABLED=True
OLLAMA_HOST=http://localhost:11434
OLLAMA_DEFAULT_MODEL=llama3.2:3b
```

### 2. Required Services

Start the required services:

```bash
# Qdrant Vector Database
docker run -p 6333:6333 qdrant/qdrant

# Ollama (for LLM generation)
ollama serve
ollama pull llama3.2:3b  # or your preferred model

# Redis (for caching)
redis-server

# MongoDB (for document storage)
mongod
```

## Usage Methods

### 1. Direct Python Usage

```python
from second_brain_database.services.rag_service import rag_service

# Basic query with LLM
result = await rag_service.query_document(
    query="What are the key features of machine learning?",
    user_id="user_123",
    use_llm=True
)

print(f"Answer: {result['answer']}")
print(f"Sources: {len(result['sources'])} documents")

# Vector search only (no LLM)
result = await rag_service.query_document(
    query="machine learning algorithms",
    user_id="user_123", 
    use_llm=False
)

print(f"Found {result['chunk_count']} relevant chunks")
for chunk in result['chunks']:
    print(f"- {chunk['text'][:100]}... (score: {chunk['score']})")
```

### 2. API Endpoints (Document Management)

Currently available document endpoints:

#### Upload and Process Documents
```bash
# Upload a document
curl -X POST "http://localhost:8000/api/documents/upload" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "file=@document.pdf" \
  -F "extract_images=true" \
  -F "output_format=markdown" \
  -F "async_processing=true"
```

#### Chunk Documents for RAG
```bash
# Chunk a document for RAG/vector search
curl -X POST "http://localhost:8000/api/documents/{document_id}/chunk" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "chunk_size": 1000,
    "chunk_overlap": 200
  }'
```

#### List Your Documents
```bash
# List your processed documents
curl -X GET "http://localhost:8000/api/documents/list?limit=20&skip=0" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### 3. MCP (Model Context Protocol) Integration

The RAG system integrates with MCP tools for AI agents:

```python
# Available via MCP server
from second_brain_database.integrations.mcp.tools.rag_tools import query_documents

# MCP tool for document querying (used by AI agents)
result = await query_documents(
    query="Explain the concept of neural networks",
    user_id="user_123",
    max_results=5
)
```

### 4. Create RAG API Endpoints (Recommended)

To create dedicated RAG endpoints, add this to your routes:

```python
# Create: src/second_brain_database/routes/rag.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from ..services.rag_service import rag_service
from .auth.services.auth.login import get_current_user

router = APIRouter(prefix="/rag", tags=["RAG"])

class RAGQueryRequest(BaseModel):
    query: str
    use_llm: bool = True
    max_results: int = 5
    similarity_threshold: float = 0.7

class RAGQueryResponse(BaseModel):
    query: str
    answer: Optional[str] = None
    chunks: List[dict]
    sources: List[dict]
    chunk_count: int
    timestamp: str

@router.post("/query", response_model=RAGQueryResponse)
async def query_documents(
    request: RAGQueryRequest,
    current_user: dict = Depends(get_current_user)
):
    """Query your documents using RAG."""
    try:
        user_id = str(current_user["_id"])
        
        result = await rag_service.query_document(
            query=request.query,
            user_id=user_id,
            use_llm=request.use_llm,
            top_k=request.max_results,
            similarity_threshold=request.similarity_threshold
        )
        
        return RAGQueryResponse(**result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
async def rag_status():
    """Get RAG system status."""
    return {
        "status": "operational",
        "llamaindex_enabled": rag_service.llamaindex_enabled,
        "vector_search_available": rag_service.vector_search_available,
        "ollama_available": rag_service.ollama_available
    }
```

Then register the router in your main app:
```python
# In src/second_brain_database/main.py
from .routes import rag
app.include_router(rag.router, prefix="/api")
```

## Advanced Usage Examples

### 1. Custom RAG Parameters

```python
# Custom similarity threshold and context length
result = await rag_service.query_document(
    query="Deep learning frameworks comparison",
    user_id="user_123",
    use_llm=True,
    top_k=10,
    similarity_threshold=0.8,
    model="llama3.2:7b",
    temperature=0.3
)
```

### 2. Batch Document Processing

```python
from second_brain_database.services.document_service import document_service

# Process multiple documents for RAG
document_ids = ["doc1", "doc2", "doc3"]

for doc_id in document_ids:
    # Chunk and index each document
    chunks = await document_service.chunk_document_for_rag(
        document_id=doc_id,
        chunk_size=1000,
        chunk_overlap=200,
        index_chunks=True
    )
    print(f"Document {doc_id}: {len(chunks)} chunks created")
```

### 3. Vector Search with Metadata Filtering

```python
# Search with specific metadata filters
from second_brain_database.managers.vector_search_manager import vector_search_manager

results = await vector_search_manager.semantic_search(
    query="machine learning algorithms",
    user_id="user_123",
    top_k=5,
    metadata_filter={
        "document_type": "research_paper",
        "year": {"$gte": 2020}
    }
)
```

## Integration with Different Use Cases

### 1. Personal Knowledge Base
- Upload PDFs, documents, and notes
- Query your personal knowledge with natural language
- Get AI-powered summaries and insights

### 2. Research Assistant
- Index research papers and articles
- Ask complex questions across multiple documents
- Generate literature reviews and comparisons

### 3. Business Documentation
- Process company handbooks, policies, and procedures
- Enable employee self-service through document Q&A
- Create intelligent help systems

### 4. Educational Content
- Index textbooks, lecture notes, and educational materials
- Create interactive learning experiences
- Generate quizzes and study materials

## Performance Optimization

### 1. Document Chunking Strategy
```python
# Optimize chunk size based on content type
CHUNK_CONFIGS = {
    "research_paper": {"size": 1500, "overlap": 300},
    "handbook": {"size": 800, "overlap": 150}, 
    "code_docs": {"size": 1200, "overlap": 200}
}

# Use appropriate chunking for your content
await document_service.chunk_document_for_rag(
    document_id=doc_id,
    chunk_size=CHUNK_CONFIGS["research_paper"]["size"],
    chunk_overlap=CHUNK_CONFIGS["research_paper"]["overlap"]
)
```

### 2. Caching and Performance
```python
# Enable Redis caching for improved performance
RAG_CACHE_ENABLED=True
RAG_CACHE_TTL=3600  # 1 hour cache

# Use async processing for large documents
async_processing=True
```

### 3. Embedding Model Selection
```python
# Local models (faster, private)
LLAMAINDEX_EMBED_MODEL=local:BAAI/bge-small-en-v1.5

# Cloud models (higher quality)
LLAMAINDEX_EMBED_MODEL=openai:text-embedding-3-large

# Multilingual models
LLAMAINDEX_EMBED_MODEL=local:BAAI/bge-m3
```

## Testing Your RAG System

Run the comprehensive test suite:
```bash
# Run RAG-specific tests
pytest tests/test_rag_simple.py -v

# Test with your own documents
python scripts/test_rag_upload.py
```

## Troubleshooting

### Common Issues

1. **Qdrant Connection Failed**
   ```bash
   # Check if Qdrant is running
   curl http://localhost:6333/health
   
   # Restart Qdrant
   docker restart qdrant-container
   ```

2. **Ollama Model Not Available**
   ```bash
   # List available models
   ollama list
   
   # Pull required model
   ollama pull llama3.2:3b
   ```

3. **No Documents Found**
   - Ensure documents are properly indexed
   - Check user_id matches between upload and query
   - Verify chunk creation completed successfully

4. **Poor Search Results**
   - Adjust similarity threshold (try 0.5-0.8)
   - Increase chunk overlap for better context
   - Use more specific queries

## Next Steps

1. **Create RAG API Endpoints**: Implement the suggested API routes above
2. **Integrate with Frontend**: Connect your frontend application to RAG endpoints  
3. **Customize Prompts**: Modify RAG prompts for your specific domain
4. **Add Reranking**: Implement semantic reranking for better results
5. **Monitor Performance**: Add metrics and monitoring for production use

## API Reference

### RAGService Methods

- `query_document(query, user_id, use_llm, **kwargs)` - Main query interface
- `_vector_search(query, user_id, **kwargs)` - Vector search only
- `_generate_answer(query, context, **kwargs)` - LLM answer generation
- `_build_context(chunks)` - Context preparation

### Configuration Options

See `.sbd-example` for all available configuration options including:
- Vector database settings (Qdrant)
- LLM configuration (Ollama)
- Embedding model selection
- Performance tuning parameters
- Security and rate limiting settings

---

**Ready to use!** Your RAG system is fully functional and tested. Start by uploading some documents and querying them using the methods above. 🚀
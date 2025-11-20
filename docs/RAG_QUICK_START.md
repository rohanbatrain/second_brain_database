# Docling + LlamaIndex + Ollama RAG - Quick Start Guide

## Prerequisites

Ensure all services are running:

```bash
# 1. Ollama (LLM service)
ollama serve
ollama pull llama3.2
ollama pull nomic-embed-text

# 2. Qdrant (Vector database)
docker run -p 6333:6333 qdrant/qdrant

# 3. MongoDB
docker run -p 27017:27017 mongo

# 4. Redis
docker run -p 6379:6379 redis
```

## Installation

```bash
# Install dependencies
pip install -e .
# Or with uv: uv pip install -e .

# Configure environment
cp .sbd-example .sbd
# Edit .sbd with your settings (most defaults work fine)
```

## Configuration Checklist

Minimal required configuration in `.sbd`:

```ini
# MongoDB
MONGODB_URL=mongodb://127.0.0.1:27017/second_brain_db
MONGODB_DATABASE=second_brain_database

# Redis
REDIS_HOST=127.0.0.1
REDIS_PORT=6379

# Ollama (check host if different)
OLLAMA_HOST=http://127.0.0.1:11434

# Qdrant (check host if different)
QDRANT_HOST=localhost
QDRANT_PORT=6333

# Enable features
LLAMAINDEX_ENABLED=True
LLAMAINDEX_HYBRID_SEARCH_ENABLED=True
```

## Running the MCP Server

### Option 1: STDIO Transport (Local Clients)

```bash
python src/second_brain_database/integrations/mcp/mcp_server.py
```

### Option 2: HTTP Transport (Remote Clients)

```bash
fastmcp run src/second_brain_database/integrations/mcp/mcp_server.py:mcp --transport http --port 8001
```

## Using RAG Features

### Via MCP Tools

#### 1. Query Documents

```python
from mcp import Client

client = Client("http://localhost:8001")

result = await client.call_tool("query_documents", {
    "query": "What are the main findings about climate change?",
    "user_id": "user_123",
    "top_k": 5,
    "use_llm": True
})

print(f"Answer: {result['answer']}")
print(f"Sources: {result['sources']}")
```

#### 2. Chat with Documents

```python
result = await client.call_tool("chat_with_documents", {
    "messages": [
        {"role": "user", "content": "What does the Q4 report say about sales?"},
        {"role": "assistant", "content": "The Q4 report shows 20% YoY growth..."},
        {"role": "user", "content": "Which regions drove that growth?"}
    ],
    "user_id": "user_123"
})

print(f"Response: {result['response']}")
```

#### 3. Summarize Document

```python
# Summary
result = await client.call_tool("summarize_document", {
    "document_id": "doc_abc123",
    "user_id": "user_123",
    "analysis_type": "summary"
})

# Key insights
result = await client.call_tool("summarize_document", {
    "document_id": "doc_abc123",
    "user_id": "user_123",
    "analysis_type": "insights"
})

# Bullet points
result = await client.call_tool("summarize_document", {
    "document_id": "doc_abc123",
    "user_id": "user_123",
    "analysis_type": "key_points"
})
```

#### 4. Compare Documents

```python
result = await client.call_tool("compare_documents", {
    "document_id_1": "contract_v1",
    "document_id_2": "contract_v2",
    "user_id": "user_123"
})

print(f"Comparison: {result['comparison']}")
```

### Via DocumentService (Programmatic)

```python
from src.second_brain_database.services.document_service import document_service

# Query documents
result = await document_service.query_document(
    query="What are the main findings?",
    user_id="user_123",
    top_k=5,
    use_llm=True
)

# Chat with documents
result = await document_service.chat_with_documents(
    messages=[
        {"role": "user", "content": "Tell me about the sales data"}
    ],
    user_id="user_123"
)

# Analyze document
result = await document_service.analyze_document_with_llm(
    document_id="doc_123",
    analysis_type="summary"
)

# Compare documents
result = await document_service.compare_documents_with_llm(
    document_id_1="doc1",
    document_id_2="doc2"
)
```

## Processing Documents

### Upload and Process

```python
from src.second_brain_database.services.document_service import document_service
import base64

# Read file
with open("document.pdf", "rb") as f:
    file_data = f.read()

# Encode
file_data_b64 = base64.b64encode(file_data).decode()

# Process and index
result = await document_service.process_and_index_document(
    file_data=base64.b64decode(file_data_b64),
    filename="document.pdf",
    user_id="user_123",
    extract_images=True,
    output_format="markdown",
    index_for_search=True
)

document_id = result["document_id"]
```

### Via Celery Task (Async)

```python
from src.second_brain_database.tasks.document_tasks import process_document_async

task = process_document_async.delay(
    file_data_b64=file_data_b64,
    filename="document.pdf",
    user_id="user_123",
    extract_images=True,
    output_format="markdown"
)

# Check status
result = task.get()
```

## Hybrid Search Parameters

Tune search quality via configuration:

```ini
# Dense vs Sparse balance (0=sparse only, 1=dense only, 0.5=balanced)
LLAMAINDEX_ALPHA=0.5

# Number of results from each retriever
LLAMAINDEX_TOP_K=5          # Final results
LLAMAINDEX_SPARSE_TOP_K=12   # Sparse retrieval candidates

# Quality threshold
LLAMAINDEX_SIMILARITY_CUTOFF=0.7
```

**Tuning Tips**:
- `ALPHA=1.0`: Best for semantic queries ("what is the main theme?")
- `ALPHA=0.0`: Best for keyword searches ("find mentions of 'Q4 2023'")
- `ALPHA=0.5`: Balanced (recommended default)

## Monitoring

### Check Ollama Health

```python
from src.second_brain_database.managers.ollama_manager import ollama_manager

healthy = await ollama_manager.health_check()
models = await ollama_manager.list_models()
```

### Check Vector Search

```python
from src.second_brain_database.managers.llamaindex_vector_manager import llamaindex_vector_manager

initialized = llamaindex_vector_manager.is_initialized()
```

## Common Issues

### 1. Ollama Not Running
```bash
# Error: Connection refused on port 11434
# Fix: Start Ollama
ollama serve
```

### 2. Missing Models
```bash
# Error: Model llama3.2 not found
# Fix: Pull models
ollama pull llama3.2
ollama pull nomic-embed-text
```

### 3. Qdrant Connection Failed
```bash
# Error: Connection refused on port 6333
# Fix: Start Qdrant
docker run -p 6333:6333 qdrant/qdrant
```

### 4. Import Errors After Installation
```bash
# Error: No module named 'llama_index'
# Fix: Reinstall with new dependencies
pip install -e . --force-reinstall
```

### 5. Collection Already Exists Without Hybrid Mode
```bash
# Error: Collection exists but doesn't support hybrid search
# Fix: Delete and recreate
curl -X DELETE http://localhost:6333/collections/document_embeddings
# Restart server to auto-create with hybrid mode
```

## Performance Tips

1. **Caching**: Ollama responses are cached in Redis (3600s default)
2. **Batch Processing**: Process multiple documents with `batch_document_processing` task
3. **Context Length**: Tune `RAG_MAX_CONTEXT_LENGTH` based on your LLM's limits
4. **Chunk Size**: Balance between granularity and context (1000 default)

## Security

All MCP tools require authentication:

```python
# Tools automatically check user context
user_context = await get_mcp_user_context()
user_id = user_context.get("user_id")
```

Access control is enforced at:
- MCP tool level (`@authenticated_tool`)
- Service level (user_id parameter)
- Database level (query filters)

## Next Steps

1. **Test with Real Documents**: Upload PDFs, DOCX, presentations
2. **Tune Hybrid Search**: Experiment with alpha parameter
3. **Monitor Performance**: Check logs for query times, chunk counts
4. **Customize Prompts**: Modify RAGService prompts for your domain
5. **Add More Models**: Try different Ollama models (deepseek-r1, etc.)

## Support

- **Documentation**: `docs/DOCLING_LLAMAINDEX_OLLAMA_RAG_IMPLEMENTATION.md`
- **Configuration**: `.sbd-example` with all options
- **Logs**: Check structured logs with user_id, document_id context
- **Codebase Patterns**: Follow examples in managers, services, tools

---

**Pro Tip**: Start with a few test documents, verify end-to-end flow (upload → index → query → answer), then scale up!

# RAG Query - Frontend Integration Guide

## Overview

The RAG Query feature enables natural language querying across your indexed documents with AI-powered answer generation. This guide provides complete frontend integration examples for web, mobile, and desktop applications.

## Feature Capabilities

- ✅ **Natural Language Queries**: Ask questions in plain English
- ✅ **AI-Powered Answers**: Get LLM-generated responses based on your documents
- ✅ **Conversation Memory**: Maintain context across multiple queries
- ✅ **Vector Search**: Semantic search with similarity scoring
- ✅ **Source Attribution**: Track which documents contributed to answers
- ✅ **Multiple Query Types**: Semantic, keyword, and hybrid search

## API Endpoint

```http
POST /api/rag/query
Authorization: Bearer {jwt_token}
Content-Type: application/json
```

**Request Body:**
```json
{
  "query": "What are the key features of machine learning?",
  "use_llm": true,
  "max_results": 5,
  "similarity_threshold": 0.7,
  "query_type": "semantic",
  "conversation_id": "conv_123",
  "include_metadata": true,
  "model": "llama3.2:3b",
  "temperature": 0.7
}
```

**Response:**
```json
{
  "query": "What are the key features of machine learning?",
  "answer": "Machine learning has several key features: 1) Pattern Recognition...",
  "chunks": [
    {
      "text": "Machine learning algorithms can...",
      "score": 0.92,
      "metadata": {
        "document_id": "doc_123",
        "filename": "ml_intro.pdf",
        "page": 5
      }
    }
  ],
  "sources": [
    {
      "document_id": "doc_123",
      "filename": "ml_intro.pdf",
      "relevance_score": 0.92
    }
  ],
  "chunk_count": 5,
  "timestamp": "2024-01-15T10:30:00Z",
  "processing_time_ms": 1250.5
}
```

## Frontend Integration Examples

### React/TypeScript with Streaming Responses

```typescript
// src/api/rag-query.ts
import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000/api';

export enum QueryType {
  SEMANTIC = 'semantic',
  KEYWORD = 'keyword',
  HYBRID = 'hybrid',
}

export interface DocumentChunk {
  text: string;
  score: number;
  metadata: Record<string, any>;
}

export interface DocumentSource {
  document_id: string;
  filename: string;
  relevance_score: number;
}

export interface RAGQueryRequest {
  query: string;
  use_llm?: boolean;
  max_results?: number;
  similarity_threshold?: number;
  query_type?: QueryType;
  conversation_id?: string;
  include_metadata?: boolean;
  model?: string;
  temperature?: number;
}

export interface RAGQueryResponse {
  query: string;
  answer: string | null;
  chunks: DocumentChunk[];
  sources: DocumentSource[];
  chunk_count: number;
  timestamp: string;
  processing_time_ms: number;
}

class RAGQueryService {
  private token: string;

  constructor(token: string) {
    this.token = token;
  }

  /**
   * Execute a RAG query
   */
  async query(request: RAGQueryRequest): Promise<RAGQueryResponse> {
    const response = await axios.post<RAGQueryResponse>(
      `${API_BASE_URL}/rag/query`,
      {
        query: request.query,
        use_llm: request.use_llm ?? true,
        max_results: request.max_results ?? 5,
        similarity_threshold: request.similarity_threshold ?? 0.7,
        query_type: request.query_type ?? QueryType.SEMANTIC,
        conversation_id: request.conversation_id,
        include_metadata: request.include_metadata ?? true,
        model: request.model,
        temperature: request.temperature ?? 0.7,
      },
      {
        headers: {
          'Authorization': `Bearer ${this.token}`,
        },
      }
    );

    return response.data;
  }

  /**
   * Query with real-time streaming (future enhancement)
   */
  async queryStream(
    request: RAGQueryRequest,
    onChunk: (chunk: string) => void,
    onComplete: (response: RAGQueryResponse) => void,
    onError: (error: Error) => void
  ): Promise<void> {
    try {
      const response = await fetch(`${API_BASE_URL}/rag/query/stream`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
      });

      if (!response.ok) {
        throw new Error(`Query failed: ${response.statusText}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error('No response body');
      }

      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();

        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');

        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            
            if (data === '[DONE]') {
              continue;
            }

            try {
              const parsed = JSON.parse(data);
              
              if (parsed.type === 'chunk') {
                onChunk(parsed.content);
              } else if (parsed.type === 'complete') {
                onComplete(parsed.data);
              }
            } catch (e) {
              console.error('Failed to parse chunk:', e);
            }
          }
        }
      }
    } catch (error) {
      onError(error instanceof Error ? error : new Error(String(error)));
    }
  }
}

export default RAGQueryService;
```

```tsx
// src/components/RAGQueryInterface.tsx
import React, { useState, useEffect, useRef } from 'react';
import RAGQueryService, { RAGQueryResponse, DocumentChunk } from '../api/rag-query';
import ReactMarkdown from 'react-markdown';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: DocumentChunk[];
  timestamp: Date;
}

const RAGQueryInterface: React.FC<{ token: string }> = ({ token }) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [conversationId] = useState(`conv_${Date.now()}`);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const ragService = new RAGQueryService(token);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!input.trim() || loading) return;

    const userMessage: Message = {
      id: `msg_${Date.now()}`,
      role: 'user',
      content: input,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const response = await ragService.query({
        query: input,
        use_llm: true,
        conversation_id: conversationId,
        max_results: 5,
        similarity_threshold: 0.7,
      });

      const assistantMessage: Message = {
        id: `msg_${Date.now()}_assistant`,
        role: 'assistant',
        content: response.answer || 'No answer generated',
        sources: response.chunks,
        timestamp: new Date(),
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      const errorMessage: Message = {
        id: `msg_${Date.now()}_error`,
        role: 'assistant',
        content: `Error: ${error instanceof Error ? error.message : 'Query failed'}`,
        timestamp: new Date(),
      };

      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="rag-query-interface" style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      {/* Header */}
      <div className="header" style={{ padding: '16px', borderBottom: '1px solid #ccc' }}>
        <h2>Ask Your Documents</h2>
        <p style={{ fontSize: '14px', color: '#666' }}>
          Conversation ID: {conversationId}
        </p>
      </div>

      {/* Messages */}
      <div className="messages" style={{ flex: 1, overflowY: 'auto', padding: '16px' }}>
        {messages.length === 0 && (
          <div style={{ textAlign: 'center', color: '#999', marginTop: '40px' }}>
            <p>Start a conversation by asking a question about your documents</p>
          </div>
        )}

        {messages.map((message) => (
          <div
            key={message.id}
            className={`message ${message.role}`}
            style={{
              marginBottom: '16px',
              padding: '12px',
              borderRadius: '8px',
              backgroundColor: message.role === 'user' ? '#e3f2fd' : '#f5f5f5',
              maxWidth: '80%',
              marginLeft: message.role === 'user' ? 'auto' : '0',
              marginRight: message.role === 'user' ? '0' : 'auto',
            }}
          >
            <div className="message-header" style={{ marginBottom: '8px' }}>
              <strong>{message.role === 'user' ? 'You' : 'AI Assistant'}</strong>
              <span style={{ fontSize: '12px', color: '#666', marginLeft: '8px' }}>
                {message.timestamp.toLocaleTimeString()}
              </span>
            </div>

            <div className="message-content">
              <ReactMarkdown>{message.content}</ReactMarkdown>
            </div>

            {/* Sources */}
            {message.sources && message.sources.length > 0 && (
              <div className="sources" style={{ marginTop: '12px', borderTop: '1px solid #ddd', paddingTop: '8px' }}>
                <p style={{ fontSize: '12px', fontWeight: 'bold', marginBottom: '4px' }}>
                  Sources ({message.sources.length}):
                </p>
                {message.sources.slice(0, 3).map((chunk, idx) => (
                  <div
                    key={idx}
                    style={{
                      fontSize: '11px',
                      padding: '4px 8px',
                      backgroundColor: '#fff',
                      borderRadius: '4px',
                      marginBottom: '4px',
                    }}
                  >
                    <div style={{ color: '#666' }}>
                      📄 {chunk.metadata.filename || 'Unknown'} (Score: {chunk.score.toFixed(2)})
                    </div>
                    <div style={{ color: '#999', marginTop: '2px' }}>
                      {chunk.text.substring(0, 100)}...
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="loading-indicator" style={{ textAlign: 'center', color: '#999' }}>
            <p>Thinking...</p>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Form */}
      <form
        onSubmit={handleSubmit}
        style={{
          padding: '16px',
          borderTop: '1px solid #ccc',
          display: 'flex',
          gap: '8px',
        }}
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question about your documents..."
          disabled={loading}
          style={{
            flex: 1,
            padding: '12px',
            borderRadius: '4px',
            border: '1px solid #ccc',
            fontSize: '14px',
          }}
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          style={{
            padding: '12px 24px',
            borderRadius: '4px',
            border: 'none',
            backgroundColor: '#1976d2',
            color: 'white',
            cursor: loading ? 'not-allowed' : 'pointer',
            fontSize: '14px',
          }}
        >
          {loading ? 'Sending...' : 'Send'}
        </button>
      </form>
    </div>
  );
};

export default RAGQueryInterface;
```

### Flutter Mobile Application

```dart
// lib/services/rag_query_service.dart
import 'package:dio/dio.dart';

enum QueryType {
  semantic,
  keyword,
  hybrid,
}

class DocumentChunk {
  final String text;
  final double score;
  final Map<String, dynamic> metadata;

  DocumentChunk({
    required this.text,
    required this.score,
    required this.metadata,
  });

  factory DocumentChunk.fromJson(Map<String, dynamic> json) {
    return DocumentChunk(
      text: json['text'],
      score: json['score'].toDouble(),
      metadata: json['metadata'],
    );
  }
}

class DocumentSource {
  final String documentId;
  final String filename;
  final double relevanceScore;

  DocumentSource({
    required this.documentId,
    required this.filename,
    required this.relevanceScore,
  });

  factory DocumentSource.fromJson(Map<String, dynamic> json) {
    return DocumentSource(
      documentId: json['document_id'],
      filename: json['filename'],
      relevanceScore: json['relevance_score'].toDouble(),
    );
  }
}

class RAGQueryResponse {
  final String query;
  final String? answer;
  final List<DocumentChunk> chunks;
  final List<DocumentSource> sources;
  final int chunkCount;
  final String timestamp;
  final double processingTimeMs;

  RAGQueryResponse({
    required this.query,
    this.answer,
    required this.chunks,
    required this.sources,
    required this.chunkCount,
    required this.timestamp,
    required this.processingTimeMs,
  });

  factory RAGQueryResponse.fromJson(Map<String, dynamic> json) {
    return RAGQueryResponse(
      query: json['query'],
      answer: json['answer'],
      chunks: (json['chunks'] as List)
          .map((e) => DocumentChunk.fromJson(e))
          .toList(),
      sources: (json['sources'] as List)
          .map((e) => DocumentSource.fromJson(e))
          .toList(),
      chunkCount: json['chunk_count'],
      timestamp: json['timestamp'],
      processingTimeMs: json['processing_time_ms'].toDouble(),
    );
  }
}

class RAGQueryService {
  final String baseUrl;
  final String token;
  final Dio _dio;

  RAGQueryService({
    required this.baseUrl,
    required this.token,
  }) : _dio = Dio(BaseOptions(
          baseUrl: baseUrl,
          headers: {
            'Authorization': 'Bearer $token',
          },
        ));

  Future<RAGQueryResponse> query({
    required String query,
    bool useLlm = true,
    int maxResults = 5,
    double similarityThreshold = 0.7,
    QueryType queryType = QueryType.semantic,
    String? conversationId,
    bool includeMetadata = true,
    String? model,
    double temperature = 0.7,
  }) async {
    final response = await _dio.post(
      '/rag/query',
      data: {
        'query': query,
        'use_llm': useLlm,
        'max_results': maxResults,
        'similarity_threshold': similarityThreshold,
        'query_type': queryType.name,
        if (conversationId != null) 'conversation_id': conversationId,
        'include_metadata': includeMetadata,
        if (model != null) 'model': model,
        'temperature': temperature,
      },
    );

    return RAGQueryResponse.fromJson(response.data);
  }
}
```

```dart
// lib/screens/rag_chat_screen.dart
import 'package:flutter/material.dart';
import '../services/rag_query_service.dart';
import 'package:flutter_markdown/flutter_markdown.dart';

class Message {
  final String id;
  final String role; // 'user' or 'assistant'
  final String content;
  final List<DocumentChunk>? sources;
  final DateTime timestamp;

  Message({
    required this.id,
    required this.role,
    required this.content,
    this.sources,
    required this.timestamp,
  });
}

class RAGChatScreen extends StatefulWidget {
  final String token;
  final String serverUrl;

  const RAGChatScreen({
    Key? key,
    required this.token,
    required this.serverUrl,
  }) : super(key: key);

  @override
  State<RAGChatScreen> createState() => _RAGChatScreenState();
}

class _RAGChatScreenState extends State<RAGChatScreen> {
  late RAGQueryService _ragService;
  final TextEditingController _controller = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final List<Message> _messages = [];
  bool _loading = false;
  late String _conversationId;

  @override
  void initState() {
    super.initState();
    _ragService = RAGQueryService(
      baseUrl: widget.serverUrl,
      token: widget.token,
    );
    _conversationId = 'conv_${DateTime.now().millisecondsSinceEpoch}';
  }

  @override
  void dispose() {
    _controller.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _scrollToBottom() {
    if (_scrollController.hasClients) {
      _scrollController.animateTo(
        _scrollController.position.maxScrollExtent,
        duration: Duration(milliseconds: 300),
        curve: Curves.easeOut,
      );
    }
  }

  Future<void> _sendMessage() async {
    final text = _controller.text.trim();
    if (text.isEmpty || _loading) return;

    // Add user message
    setState(() {
      _messages.add(Message(
        id: 'msg_${DateTime.now().millisecondsSinceEpoch}',
        role: 'user',
        content: text,
        timestamp: DateTime.now(),
      ));
      _loading = true;
    });

    _controller.clear();
    _scrollToBottom();

    try {
      // Query RAG system
      final response = await _ragService.query(
        query: text,
        useLlm: true,
        conversationId: _conversationId,
      );

      // Add assistant message
      setState(() {
        _messages.add(Message(
          id: 'msg_${DateTime.now().millisecondsSinceEpoch}_assistant',
          role: 'assistant',
          content: response.answer ?? 'No answer generated',
          sources: response.chunks,
          timestamp: DateTime.now(),
        ));
        _loading = false;
      });

      _scrollToBottom();
    } catch (error) {
      setState(() {
        _messages.add(Message(
          id: 'msg_${DateTime.now().millisecondsSinceEpoch}_error',
          role: 'assistant',
          content: 'Error: ${error.toString()}',
          timestamp: DateTime.now(),
        ));
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('Ask Your Documents'),
        subtitle: Text('Conversation: $_conversationId', style: TextStyle(fontSize: 10)),
      ),
      body: Column(
        children: [
          // Messages
          Expanded(
            child: _messages.isEmpty
                ? Center(
                    child: Text(
                      'Start a conversation by asking a question',
                      style: TextStyle(color: Colors.grey),
                    ),
                  )
                : ListView.builder(
                    controller: _scrollController,
                    padding: EdgeInsets.all(16),
                    itemCount: _messages.length,
                    itemBuilder: (context, index) {
                      final message = _messages[index];
                      final isUser = message.role == 'user';

                      return Align(
                        alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
                        child: Container(
                          constraints: BoxConstraints(
                            maxWidth: MediaQuery.of(context).size.width * 0.8,
                          ),
                          margin: EdgeInsets.only(bottom: 16),
                          padding: EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: isUser ? Colors.blue.shade100 : Colors.grey.shade200,
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              // Header
                              Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Text(
                                    isUser ? 'You' : 'AI Assistant',
                                    style: TextStyle(fontWeight: FontWeight.bold),
                                  ),
                                  SizedBox(width: 8),
                                  Text(
                                    message.timestamp.toString().substring(11, 16),
                                    style: TextStyle(fontSize: 10, color: Colors.grey),
                                  ),
                                ],
                              ),
                              SizedBox(height: 8),
                              
                              // Content
                              MarkdownBody(data: message.content),
                              
                              // Sources
                              if (message.sources != null && message.sources!.isNotEmpty) ...[
                                SizedBox(height: 12),
                                Divider(),
                                Text(
                                  'Sources (${message.sources!.length}):',
                                  style: TextStyle(
                                    fontSize: 12,
                                    fontWeight: FontWeight.bold,
                                  ),
                                ),
                                SizedBox(height: 4),
                                ...message.sources!.take(3).map((chunk) => Container(
                                      margin: EdgeInsets.only(top: 4),
                                      padding: EdgeInsets.all(8),
                                      decoration: BoxDecoration(
                                        color: Colors.white,
                                        borderRadius: BorderRadius.circular(4),
                                      ),
                                      child: Column(
                                        crossAxisAlignment: CrossAxisAlignment.start,
                                        children: [
                                          Text(
                                            '📄 ${chunk.metadata['filename'] ?? 'Unknown'} (Score: ${chunk.score.toStringAsFixed(2)})',
                                            style: TextStyle(fontSize: 10, color: Colors.grey.shade700),
                                          ),
                                          SizedBox(height: 2),
                                          Text(
                                            chunk.text.length > 100
                                                ? '${chunk.text.substring(0, 100)}...'
                                                : chunk.text,
                                            style: TextStyle(fontSize: 9, color: Colors.grey.shade600),
                                          ),
                                        ],
                                      ),
                                    )),
                              ],
                            ],
                          ),
                        ),
                      );
                    },
                  ),
          ),

          // Loading indicator
          if (_loading)
            Padding(
              padding: EdgeInsets.all(8),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  CircularProgressIndicator(strokeWidth: 2),
                  SizedBox(width: 12),
                  Text('Thinking...'),
                ],
              ),
            ),

          // Input
          Container(
            padding: EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.white,
              boxShadow: [
                BoxShadow(
                  color: Colors.black12,
                  blurRadius: 4,
                  offset: Offset(0, -2),
                ),
              ],
            ),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _controller,
                    enabled: !_loading,
                    decoration: InputDecoration(
                      hintText: 'Ask a question...',
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(24),
                      ),
                      contentPadding: EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                    ),
                    onSubmitted: (_) => _sendMessage(),
                  ),
                ),
                SizedBox(width: 8),
                FloatingActionButton(
                  onPressed: _loading ? null : _sendMessage,
                  child: Icon(Icons.send),
                  mini: true,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
```

## Advanced Features

### Conversation Management

```typescript
// Manage conversation history
class ConversationManager {
  private conversations: Map<string, Message[]> = new Map();

  createConversation(): string {
    const id = `conv_${Date.now()}`;
    this.conversations.set(id, []);
    return id;
  }

  addMessage(conversationId: string, message: Message): void {
    const messages = this.conversations.get(conversationId) || [];
    messages.push(message);
    this.conversations.set(conversationId, messages);
  }

  getMessages(conversationId: string): Message[] {
    return this.conversations.get(conversationId) || [];
  }

  clearConversation(conversationId: string): void {
    this.conversations.delete(conversationId);
  }
}
```

### Query Optimization

```typescript
// Implement query caching
class QueryCache {
  private cache: Map<string, RAGQueryResponse> = new Map();
  private maxSize: number = 100;
  private ttl: number = 5 * 60 * 1000; // 5 minutes

  getCacheKey(request: RAGQueryRequest): string {
    return JSON.stringify({
      query: request.query.toLowerCase().trim(),
      use_llm: request.use_llm,
      max_results: request.max_results,
    });
  }

  get(request: RAGQueryRequest): RAGQueryResponse | null {
    const key = this.getCacheKey(request);
    return this.cache.get(key) || null;
  }

  set(request: RAGQueryRequest, response: RAGQueryResponse): void {
    const key = this.getCacheKey(request);
    
    if (this.cache.size >= this.maxSize) {
      const firstKey = this.cache.keys().next().value;
      this.cache.delete(firstKey);
    }

    this.cache.set(key, response);

    // Auto-expire
    setTimeout(() => {
      this.cache.delete(key);
    }, this.ttl);
  }
}
```

## Best Practices

### 1. Handle Empty Responses
```typescript
if (!response.answer) {
  return "I couldn't find relevant information in your documents. Try rephrasing your question.";
}
```

### 2. Display Source Attribution
```typescript
function renderSources(sources: DocumentSource[]) {
  return (
    <div>
      <h4>Sources:</h4>
      {sources.map(source => (
        <a key={source.document_id} href={`/documents/${source.document_id}`}>
          {source.filename} (Relevance: {(source.relevance_score * 100).toFixed(0)}%)
        </a>
      ))}
    </div>
  );
}
```

### 3. Query Suggestions
```typescript
const suggestions = [
  "What are the main findings?",
  "Summarize the key points",
  "What conclusions were drawn?",
  "Explain the methodology",
];
```

## Testing

```bash
# Test query endpoint
curl -X POST "http://localhost:8000/api/rag/query" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is machine learning?",
    "use_llm": true,
    "max_results": 5
  }'
```

## Next Steps

- [Document Upload](./01_document_upload.md)
- [Vector Search](./04_vector_search.md)
- [Conversation Management](./05_conversation_management.md)

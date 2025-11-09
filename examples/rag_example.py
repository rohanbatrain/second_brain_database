#!/usr/bin/env python3
"""
RAG Usage Example Script

This script demonstrates how to use the RAG (Retrieval-Augmented Generation) 
system in the Second Brain Database application.

Usage:
    python examples/rag_example.py

Requirements:
    - Second Brain Database application running
    - Documents uploaded and indexed
    - Required services (Qdrant, Ollama, MongoDB, Redis) running
"""

import asyncio
import sys
import os
from pathlib import Path

# Add src to path to import the modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from second_brain_database.services.rag_service import rag_service
from second_brain_database.services.document_service import document_service
from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[RAGExample]")


async def demonstrate_rag_usage():
    """Demonstrate various RAG usage patterns."""
    
    # Connect to database
    await db_manager.connect()
    
    # Sample user ID (replace with real user ID)
    user_id = "example_user_123"
    
    print("🚀 Second Brain Database - RAG Usage Examples")
    print("=" * 50)
    
    # Example 1: Basic RAG Query with LLM
    print("\n1. Basic RAG Query with LLM Generation")
    print("-" * 40)
    
    try:
        result = await rag_service.query_document(
            query="What are the key concepts in machine learning?",
            user_id=user_id,
            use_llm=True,
            top_k=5
        )
        
        print(f"Query: {result['query']}")
        print(f"Answer: {result['answer']}")
        print(f"Sources: {len(result['sources'])} documents")
        print(f"Chunks found: {result['chunk_count']}")
        
        # Show source details
        if result['sources']:
            print("\nTop Sources:")
            for i, source in enumerate(result['sources'][:3], 1):
                print(f"  {i}. {source.get('filename', 'Unknown')} (ID: {source.get('document_id', 'N/A')})")
        
    except Exception as e:
        print(f"Error in basic RAG query: {e}")
    
    # Example 2: Vector Search Only (No LLM)
    print("\n\n2. Vector Search Only (No LLM Generation)")
    print("-" * 45)
    
    try:
        result = await rag_service.query_document(
            query="neural networks deep learning",
            user_id=user_id,
            use_llm=False,
            top_k=3
        )
        
        print(f"Query: {result['query']}")
        print(f"Found {result['chunk_count']} relevant chunks")
        
        if result['chunks']:
            print("\nRelevant Chunks:")
            for i, chunk in enumerate(result['chunks'], 1):
                text_preview = chunk['text'][:150] + "..." if len(chunk['text']) > 150 else chunk['text']
                print(f"  {i}. Score: {chunk['score']:.3f}")
                print(f"     Text: {text_preview}")
                print(f"     Source: {chunk.get('metadata', {}).get('filename', 'Unknown')}\n")
    
    except Exception as e:
        print(f"Error in vector search: {e}")
    
    # Example 3: Custom Parameters
    print("\n3. Advanced Query with Custom Parameters")
    print("-" * 42)
    
    try:
        result = await rag_service.query_document(
            query="Compare different programming languages for data science",
            user_id=user_id,
            use_llm=True,
            top_k=8,
            similarity_threshold=0.6,
            model="llama3.2:3b",  # Specify model
            temperature=0.3       # Lower temperature for more focused answers
        )
        
        print(f"Query: {result['query']}")
        print(f"Answer: {result['answer']}")
        print(f"Similarity threshold: 0.6")
        print(f"Results found: {result['chunk_count']} chunks")
        
    except Exception as e:
        print(f"Error in advanced query: {e}")
    
    # Example 4: System Status Check
    print("\n\n4. RAG System Status")
    print("-" * 25)
    
    try:
        # Check if RAG service is properly initialized
        print(f"RAG Service initialized: ✅")
        print(f"Top K setting: {rag_service.top_k}")
        print(f"Similarity threshold: {rag_service.similarity_threshold}")
        print(f"Max context length: {rag_service.max_context_length}")
        
        # Check available documents for user
        documents = await document_service.get_document_list(
            user_id=user_id,
            limit=5,
            include_content=False
        )
        
        print(f"\nAvailable documents: {len(documents)}")
        if documents:
            print("Recent documents:")
            for doc in documents[:3]:
                print(f"  - {doc.get('filename', 'Unknown')} ({doc.get('document_id', 'N/A')})")
        
    except Exception as e:
        print(f"Error checking system status: {e}")
    
    # Example 5: Document Processing for RAG
    print("\n\n5. Document Processing Example")
    print("-" * 32)
    
    try:
        # Get a document to demonstrate chunking
        documents = await document_service.get_document_list(
            user_id=user_id,
            limit=1,
            include_content=False
        )
        
        if documents:
            document_id = documents[0].get('document_id')
            print(f"Processing document: {documents[0].get('filename', 'Unknown')}")
            
            # Chunk document for RAG (if not already done)
            chunks = await document_service.chunk_document_for_rag(
                document_id=document_id,
                chunk_size=1000,
                chunk_overlap=200,
                index_chunks=True  # This will index the chunks for search
            )
            
            print(f"Created {len(chunks)} chunks for RAG")
            if chunks:
                print(f"First chunk preview: {chunks[0]['text'][:100]}...")
        else:
            print("No documents available for processing")
            print("Upload documents using: POST /api/documents/upload")
    
    except Exception as e:
        print(f"Error in document processing: {e}")
    
    # Cleanup
    await db_manager.disconnect()
    print("\n\n✅ RAG Examples Complete!")
    print("\nNext Steps:")
    print("1. Upload your own documents via API endpoints")
    print("2. Try queries related to your document content")
    print("3. Experiment with different similarity thresholds")
    print("4. Integrate RAG into your applications")


async def interactive_rag_session():
    """Interactive RAG session for testing."""
    
    await db_manager.connect()
    
    print("🤖 Interactive RAG Session")
    print("Type 'quit' to exit, 'help' for commands")
    print("=" * 40)
    
    user_id = input("Enter user ID (or press Enter for default): ").strip() or "example_user_123"
    
    while True:
        try:
            query = input("\n🔍 Your question: ").strip()
            
            if query.lower() in ['quit', 'exit', 'q']:
                break
            elif query.lower() == 'help':
                print("\nCommands:")
                print("  help - Show this help")
                print("  quit - Exit session")
                print("  status - Show system status")
                print("  Just type your question to search!")
                continue
            elif query.lower() == 'status':
                documents = await document_service.get_document_list(user_id=user_id, limit=10)
                print(f"\nSystem Status:")
                print(f"  Documents available: {len(documents)}")
                print(f"  RAG service ready: ✅")
                continue
            elif not query:
                continue
            
            print("🔄 Searching...")
            
            # Use LLM by default, but allow vector-only search with special prefix
            use_llm = not query.startswith("search:")
            if query.startswith("search:"):
                query = query[7:].strip()
            
            result = await rag_service.query_document(
                query=query,
                user_id=user_id,
                use_llm=use_llm,
                top_k=5
            )
            
            if use_llm and result.get('answer'):
                print(f"\n🤖 Answer: {result['answer']}")
            
            print(f"\n📊 Found {result['chunk_count']} relevant chunks")
            
            if result['chunks']:
                print("\n📄 Top results:")
                for i, chunk in enumerate(result['chunks'][:3], 1):
                    text_preview = chunk['text'][:100] + "..." if len(chunk['text']) > 100 else chunk['text']
                    print(f"  {i}. Score: {chunk['score']:.3f}")
                    print(f"     {text_preview}")
                    if chunk.get('metadata', {}).get('filename'):
                        print(f"     Source: {chunk['metadata']['filename']}")
                    print()
        
        except KeyboardInterrupt:
            print("\n\nSession interrupted. Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
    
    await db_manager.disconnect()
    print("👋 RAG session ended!")


async def main():
    """Main function to run examples."""
    
    if len(sys.argv) > 1 and sys.argv[1] == '--interactive':
        await interactive_rag_session()
    else:
        await demonstrate_rag_usage()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nExiting...")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)
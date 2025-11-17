#!/usr/bin/env python3
"""
Test script for the simplified RAG system using existing DocumentProcessor.

This script demonstrates how the RAG system leverages the existing comprehensive
DocumentProcessor instead of creating redundant parsers.
"""

import asyncio
import sys
import tempfile
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from second_brain_database.rag import RAGSystem
from second_brain_database.rag.core.config import RAGConfig, DocumentProcessingConfig


async def test_rag_system():
    """Test the RAG system with a simple document."""
    
    print("🚀 Testing RAG System with Existing DocumentProcessor")
    print("=" * 60)
    
    # Initialize RAG system
    config = RAGConfig()
    rag = RAGSystem(config)
    
    # Get system info
    system_info = await rag.get_system_info()
    print(f"📊 RAG System Info:")
    print(f"   Version: {system_info['rag_system']['version']}")
    print(f"   Architecture: {system_info['rag_system']['architecture']}")
    print(f"   Document Processor: {system_info['document_processing']['name']}")
    
    # Get supported formats
    formats = await rag.get_supported_formats()
    print(f"   Supported Formats: {', '.join(formats)}")
    print()
    
    # Test with a simple text document
    test_content = """
# Test Document

This is a test document for the RAG system.

## Introduction

The Second Brain Database application now includes a comprehensive RAG (Retrieval-Augmented Generation) system that leverages the existing DocumentProcessor with Docling integration.

## Key Features

1. **Multi-format Support**: PDF, DOCX, PPTX, HTML, XLSX, MD, CSV
2. **Advanced OCR**: Configurable OCR with multiple language support
3. **Table Extraction**: Automatic table detection and extraction
4. **Image Processing**: Image detection and metadata extraction
5. **Layout Analysis**: Advanced document layout understanding

## Architecture Benefits

By leveraging the existing DocumentProcessor, we avoid redundancy and ensure:
- Consistent document processing across the application
- Proven reliability and performance
- Comprehensive format support
- Advanced features like OCR and table extraction

## Conclusion

This approach demonstrates the importance of leveraging existing, well-tested components rather than creating redundant implementations.
    """.strip()
    
    # Create temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write(test_content)
        temp_path = f.name
    
    try:
        # Test document processing
        print("📄 Processing test document...")
        
        with open(temp_path, 'rb') as file_data:
            result = await rag.process_document(
                file_data=file_data,
                filename="test_document.md",
                user_id="test_user_123",
                output_format="markdown"
            )
        
        document = result["document"]
        
        print(f"✅ Document processed successfully!")
        print(f"   Filename: {document.filename}")
        print(f"   Content Length: {len(document.content)} characters")
        print(f"   Number of Chunks: {len(document.chunks)}")
        print(f"   Word Count: {document.metadata.word_count}")
        print(f"   Page Count: {document.metadata.page_count}")
        print()
        
        # Show first few chunks
        print("📝 Sample Chunks:")
        for i, chunk in enumerate(document.chunks[:3]):
            print(f"   Chunk {i + 1}:")
            print(f"     Content: {chunk.content[:100]}...")
            print(f"     Tokens: {chunk.token_count}")
            print(f"     Range: {chunk.start_char}-{chunk.end_char}")
            print()
        
        # Test table extraction (won't find any in markdown, but tests the method)
        print("🔍 Testing table extraction...")
        with open(temp_path, 'rb') as file_data:
            tables = await rag.extract_tables(file_data, "test_document.md")
        
        print(f"   Tables found: {len(tables)}")
        print()
        
        # Show metadata
        print("📊 Document Metadata:")
        metadata = document.metadata
        print(f"   Title: {metadata.title}")
        print(f"   MIME Type: {metadata.mime_type}")
        print(f"   File Size: {metadata.file_size} bytes")
        print(f"   Processing Time: {metadata.processing_time:.3f}s")
        print(f"   Extracted Tables: {metadata.extracted_tables}")
        print(f"   Extracted Images: {metadata.extracted_images}")
        
        # Show custom fields
        custom = metadata.custom_fields
        print(f"   Processor: {custom.get('processor', 'unknown')}")
        print(f"   Format: {custom.get('format', 'unknown')}")
        print(f"   Has Tables: {custom.get('has_tables', False)}")
        print(f"   Has Images: {custom.get('has_images', False)}")
        
        print("\n🎉 RAG System test completed successfully!")
        print("✨ The system successfully leverages the existing DocumentProcessor")
        print("   without any redundant parser implementations.")
        
    finally:
        # Clean up temp file
        Path(temp_path).unlink(missing_ok=True)


async def test_unsupported_format():
    """Test handling of unsupported formats."""
    
    print("\n🧪 Testing unsupported format handling...")
    
    rag = RAGSystem()
    
    # Create a fake file with unsupported extension
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xyz', delete=False) as f:
        f.write("This is an unsupported format")
        temp_path = f.name
    
    try:
        with open(temp_path, 'rb') as file_data:
            result = await rag.process_document(
                file_data=file_data,
                filename="test_document.xyz",
                user_id="test_user_123"
            )
        
        print("❌ Expected error for unsupported format!")
        
    except Exception as e:
        print(f"✅ Correctly handled unsupported format: {type(e).__name__}")
        print(f"   Error: {str(e)[:100]}...")
        
    finally:
        Path(temp_path).unlink(missing_ok=True)


if __name__ == "__main__":
    print("Testing RAG System Integration with Existing DocumentProcessor")
    print("This demonstrates why we don't need separate parsers!")
    print()
    
    asyncio.run(test_rag_system())
    asyncio.run(test_unsupported_format())
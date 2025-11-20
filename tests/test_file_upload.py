#!/usr/bin/env python3
"""
Test the file upload endpoint
"""

import requests
from pathlib import Path

# Load token
token = Path("rag_token.txt").read_text().strip()
headers = {"Authorization": f"Bearer {token}"}

# Create a simple markdown test file (supported format)
test_content = """
# Test Document for RAG System

This is a test document for the RAG system.
It contains some sample text that will be processed and indexed.

## Machine Learning Overview

Machine learning is a subset of artificial intelligence that focuses on
enabling systems to learn from data and improve their performance over time.

## Key Concepts

- Supervised Learning
- Unsupervised Learning
- Reinforcement Learning
"""

# Save to a temp file with .md extension (supported format)
test_file = Path("/tmp/test_upload.md")
test_file.write_text(test_content)

print("=" * 70)
print("Testing RAG File Upload Endpoint")
print("=" * 70)
print()

# Test the upload endpoint
print("Uploading test file...")
try:
    with open(test_file, 'rb') as f:
        files = {"file": ("test_upload.md", f, "text/markdown")}
        data = {"async_processing": "false"}
        
        response = requests.post(
            "http://localhost:8000/rag/upload",
            headers=headers,
            files=files,
            data=data,
            timeout=30
        )
        
    print(f"Status Code: {response.status_code}")
    print()
    
    if response.status_code == 200:
        result = response.json()
        print("✅ Upload successful!")
        print(f"   Document ID: {result.get('document_id')}")
        print(f"   Status: {result.get('status')}")
        print(f"   Chunks Created: {result.get('chunks_created')}")
        print(f"   Processing Time: {result.get('processing_time', 0):.3f}s")
        print(f"   Message: {result.get('message')}")
    else:
        print(f"❌ Upload failed!")
        print(f"   Response: {response.text}")
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 70)

# Cleanup
test_file.unlink()

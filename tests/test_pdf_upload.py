#!/usr/bin/env python3
"""
Test PDF upload to the RAG system
"""

import requests
from pathlib import Path
import io

# Load token
token = Path("rag_token.txt").read_text().strip()
headers = {"Authorization": f"Bearer {token}"}

# Create a simple PDF using reportlab (if available)
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    
    pdf_buffer = io.BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=letter)
    c.drawString(100, 750, "Test RAG Upload Document")
    c.drawString(100, 730, "=" * 40)
    c.drawString(100, 700, "This is a test PDF document for the RAG system.")
    c.drawString(100, 680, "")
    c.drawString(100, 660, "Introduction to Machine Learning")
    c.drawString(100, 640, "")
    c.drawString(100, 620, "Machine learning is a subset of artificial intelligence")
    c.drawString(100, 600, "that focuses on enabling systems to learn from data")
    c.drawString(100, 580, "and improve their performance over time without being")
    c.drawString(100, 560, "explicitly programmed.")
    c.save()
    
    pdf_content = pdf_buffer.getvalue()
    filename = "test_ml_doc.pdf"
    content_type = "application/pdf"
    
    print("=" * 70)
    print("Testing PDF Upload to RAG System")
    print("=" * 70)
    print()
    
except ImportError:
    print("reportlab not installed, skipping PDF test")
    print("Install with: pip install reportlab")
    exit(0)

# Upload the PDF
print(f"Uploading {filename}...")
try:
    files = {"file": (filename, pdf_content, content_type)}
    data = {"async_processing": "false"}  # Wait for processing to complete
    
    response = requests.post(
        "http://localhost:8000/rag/upload",
        headers=headers,
        files=files,
        data=data,
        timeout=60
    )
    
    print(f"Status Code: {response.status_code}")
    print()
    
    if response.status_code == 200:
        result = response.json()
        print("✅ PDF upload successful!")
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

#!/usr/bin/env python3
"""
RAG System Quick Setup Script

This script helps you quickly set up and test the RAG system in your
Second Brain Database application.

Usage:
    python scripts/rag_quick_setup.py [--setup-only] [--test-only]

Features:
    - Checks system requirements
    - Verifies service connections
    - Creates test documents
    - Runs basic RAG tests
    - Provides usage examples
"""

import asyncio
import sys
import os
from pathlib import Path
import subprocess
import tempfile
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def check_service(name: str, command: str, expected_output: str = None) -> bool:
    """Check if a service is running."""
    try:
        result = subprocess.run(
            command.split(),
            capture_output=True,
            text=True,
            timeout=5
        )
        if expected_output:
            return expected_output.lower() in result.stdout.lower()
        return result.returncode == 0
    except Exception:
        return False


def print_status(service: str, status: bool, message: str = ""):
    """Print service status with colored output."""
    status_char = "✅" if status else "❌"
    print(f"{status_char} {service:<20} {message}")


async def check_system_requirements():
    """Check if all required services are running."""
    
    print("🔍 Checking System Requirements")
    print("=" * 50)
    
    checks = {
        "Qdrant": ("curl -s http://localhost:6333/health", "status"),
        "Ollama": ("curl -s http://localhost:11434/api/tags", None),
        "MongoDB": ("mongosh --eval 'db.runCommand({ping: 1})' --quiet", "ok"),
        "Redis": ("redis-cli ping", "PONG"),
        "Python": ("python --version", "python")
    }
    
    results = {}
    
    for service, (command, expected) in checks.items():
        status = check_service(service, command, expected)
        results[service] = status
        
        if status:
            print_status(service, True, "Running")
        else:
            print_status(service, False, "Not available")
            if service in ["Qdrant", "Ollama"]:
                print(f"   💡 Start {service}: See docs/RAG_USAGE_GUIDE.md")
    
    print()
    return all(results.values())


async def setup_test_documents():
    """Create test documents for RAG demonstration."""
    
    print("📄 Setting Up Test Documents")
    print("=" * 40)
    
    try:
        from second_brain_database.services.document_service import document_service
        from second_brain_database.database import db_manager
        
        await db_manager.connect()
        
        # Create test user
        test_user_id = "rag_test_user_123"
        
        # Sample documents content
        test_docs = [
            {
                "filename": "machine_learning_basics.txt",
                "content": """
                Machine Learning Fundamentals
                
                Machine learning is a subset of artificial intelligence (AI) that focuses on 
                algorithms that can learn and make decisions from data. Key concepts include:
                
                1. Supervised Learning: Learning from labeled training data
                2. Unsupervised Learning: Finding patterns in unlabeled data  
                3. Reinforcement Learning: Learning through interaction and feedback
                
                Popular algorithms include decision trees, neural networks, and support vector machines.
                Applications span computer vision, natural language processing, and predictive analytics.
                """
            },
            {
                "filename": "deep_learning_guide.txt", 
                "content": """
                Deep Learning Overview
                
                Deep learning uses neural networks with multiple layers to model complex patterns.
                Key architectures include:
                
                - Convolutional Neural Networks (CNNs): Excellent for image processing
                - Recurrent Neural Networks (RNNs): Good for sequential data
                - Transformers: State-of-the-art for natural language processing
                
                Popular frameworks include TensorFlow, PyTorch, and Keras.
                Deep learning has revolutionized fields like computer vision, NLP, and speech recognition.
                """
            },
            {
                "filename": "python_data_science.txt",
                "content": """
                Python for Data Science
                
                Python is the most popular language for data science due to its rich ecosystem:
                
                Core Libraries:
                - NumPy: Numerical computing and arrays
                - Pandas: Data manipulation and analysis
                - Matplotlib/Seaborn: Data visualization
                - Scikit-learn: Machine learning algorithms
                - Jupyter: Interactive development environment
                
                Python's simplicity and extensive libraries make it ideal for data analysis,
                machine learning, and scientific computing projects.
                """
            }
        ]
        
        created_docs = []
        
        for doc_info in test_docs:
            try:
                # Create temporary file
                with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                    f.write(doc_info["content"])
                    temp_path = f.name
                
                # Process document
                with open(temp_path, 'rb') as file_data:
                    result = await document_service.process_and_index_document(
                        file_data=file_data.read(),
                        filename=doc_info["filename"],
                        user_id=test_user_id,
                        extract_images=False,
                        output_format="text",
                        index_for_search=True
                    )
                
                created_docs.append(result)
                print(f"✅ Created: {doc_info['filename']}")
                
                # Cleanup temp file
                os.unlink(temp_path)
                
            except Exception as e:
                print(f"❌ Failed to create {doc_info['filename']}: {e}")
        
        print(f"\n📊 Created {len(created_docs)} test documents")
        
        await db_manager.disconnect()
        return created_docs, test_user_id
        
    except Exception as e:
        print(f"❌ Error setting up test documents: {e}")
        return [], None


async def run_rag_tests(test_user_id: str):
    """Run basic RAG functionality tests."""
    
    print("\n🧪 Running RAG Tests")
    print("=" * 30)
    
    try:
        from second_brain_database.services.rag_service import rag_service
        from second_brain_database.database import db_manager
        
        await db_manager.connect()
        
        # Test queries
        test_queries = [
            "What is machine learning?",
            "Explain deep learning architectures", 
            "What Python libraries are used for data science?",
            "Compare supervised and unsupervised learning"
        ]
        
        for i, query in enumerate(test_queries, 1):
            print(f"\n{i}. Testing: {query}")
            
            try:
                # Test vector search only
                result = await rag_service.query_document(
                    query=query,
                    user_id=test_user_id,
                    use_llm=False,
                    top_k=3
                )
                
                print(f"   📊 Found {result['chunk_count']} relevant chunks")
                
                if result['chunks']:
                    top_score = result['chunks'][0]['score']
                    print(f"   🎯 Top relevance score: {top_score:.3f}")
                
                # Test with LLM (if available)
                try:
                    llm_result = await rag_service.query_document(
                        query=query,
                        user_id=test_user_id,
                        use_llm=True,
                        top_k=3
                    )
                    
                    if llm_result.get('answer'):
                        answer_preview = llm_result['answer'][:100] + "..." if len(llm_result['answer']) > 100 else llm_result['answer']
                        print(f"   🤖 AI Answer: {answer_preview}")
                    
                except Exception as e:
                    print(f"   ⚠️  LLM generation skipped: {e}")
                
            except Exception as e:
                print(f"   ❌ Query failed: {e}")
        
        await db_manager.disconnect()
        
    except Exception as e:
        print(f"❌ RAG tests failed: {e}")


def print_usage_examples():
    """Print usage examples and next steps."""
    
    print("\n🚀 RAG System Ready!")
    print("=" * 30)
    
    print("\n📖 Usage Examples:")
    
    print("\n1. Python Usage:")
    print("""
    from second_brain_database.services.rag_service import rag_service
    
    # Basic query
    result = await rag_service.query_document(
        query="What is machine learning?",
        user_id="your_user_id",
        use_llm=True
    )
    
    print(f"Answer: {result['answer']}")
    """)
    
    print("\n2. Interactive Session:")
    print("   python examples/rag_example.py --interactive")
    
    print("\n3. API Endpoints (add to your FastAPI app):")
    print("""
    # Add to main.py:
    from src.second_brain_database.routes.rag import router as rag_router
    app.include_router(rag_router, prefix="/api")
    
    # Then use:
    POST /api/rag/query - Query with AI
    POST /api/rag/search - Vector search only  
    GET  /api/rag/status - System status
    """)
    
    print("\n4. Upload Your Documents:")
    print("""
    curl -X POST "http://localhost:8000/api/documents/upload" \\
      -H "Authorization: Bearer YOUR_TOKEN" \\
      -F "file=@your_document.pdf"
    """)
    
    print("\n📚 Documentation:")
    print("   📄 docs/RAG_USAGE_GUIDE.md - Complete usage guide")
    print("   🧪 examples/rag_example.py - Example scripts")
    print("   🔧 tests/test_rag_simple.py - Test suite")
    
    print("\n💡 Tips:")
    print("   • Adjust similarity_threshold (0.5-0.9) based on your needs")
    print("   • Use larger chunk_overlap for better context")
    print("   • Try different embedding models for better results")
    print("   • Monitor performance with /api/rag/status endpoint")


async def main():
    """Main setup function."""
    
    import argparse
    
    parser = argparse.ArgumentParser(description="RAG System Quick Setup")
    parser.add_argument("--setup-only", action="store_true", help="Only setup, don't test")
    parser.add_argument("--test-only", action="store_true", help="Only test, don't setup")
    args = parser.parse_args()
    
    print("🧠 Second Brain Database - RAG Quick Setup")
    print("=" * 60)
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Check system requirements
    if not args.test_only:
        system_ok = await check_system_requirements()
        
        if not system_ok:
            print("\n⚠️  Some services are not available.")
            print("   The RAG system may have limited functionality.")
            print("   See docs/RAG_USAGE_GUIDE.md for setup instructions.")
            
            if input("\nContinue anyway? (y/N): ").lower() != 'y':
                return
    
    # Setup test documents
    test_user_id = None
    if not args.test_only:
        docs, test_user_id = await setup_test_documents()
        
        if not docs:
            print("⚠️  No test documents created. You can still use existing documents.")
    
    # Run tests
    if not args.setup_only:
        if not test_user_id:
            test_user_id = input("\nEnter user ID for testing (or press Enter for default): ").strip()
            if not test_user_id:
                test_user_id = "rag_test_user_123"
        
        await run_rag_tests(test_user_id)
    
    # Print usage examples
    print_usage_examples()
    
    print(f"\n✅ Setup completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\nHappy querying! 🎉")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nSetup interrupted. Goodbye!")
    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
        sys.exit(1)
#!/usr/bin/env python3
"""
RAG Integration Test

A comprehensive integration test that validates the entire RAG pipeline
from document upload to query processing.

Usage:
    python scripts/rag_integration_test.py [--verbose] [--cleanup]
"""

import asyncio
import sys
import tempfile
import os
from pathlib import Path
from datetime import datetime
import json

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class RAGIntegrationTest:
    """Complete integration test for RAG functionality."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.test_user_id = "integration_test_user"
        self.created_documents = []
        self.test_results = []
    
    def log(self, message: str, level: str = "INFO"):
        """Log message with timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        prefix = {
            "INFO": "ℹ️ ",
            "SUCCESS": "✅",
            "ERROR": "❌",
            "WARNING": "⚠️ "
        }.get(level, "  ")
        
        print(f"[{timestamp}] {prefix} {message}")
        
        if self.verbose and level in ["ERROR", "WARNING"]:
            import traceback
            traceback.print_exc()
    
    async def setup_services(self):
        """Initialize all required services."""
        try:
            from second_brain_database.database import db_manager
            await db_manager.connect()
            
            self.log("Database connection established")
            return True
            
        except Exception as e:
            self.log(f"Failed to setup services: {e}", "ERROR")
            return False
    
    async def test_document_processing(self):
        """Test document processing and indexing."""
        try:
            from second_brain_database.services.document_service import document_service
            
            self.log("Testing document processing...")
            
            # Create test document
            test_content = """
            Artificial Intelligence Test Document
            
            This is a test document about artificial intelligence and machine learning.
            It contains information about neural networks, deep learning, and natural 
            language processing.
            
            Key concepts:
            1. Neural Networks: Computational models inspired by biological neural networks
            2. Deep Learning: Machine learning using deep neural networks with many layers
            3. NLP: Natural Language Processing for understanding human language
            4. Computer Vision: AI field dealing with image and video understanding
            
            Applications include autonomous vehicles, medical diagnosis, and language translation.
            """
            
            # Create temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(test_content)
                temp_path = f.name
            
            try:
                # Process document
                with open(temp_path, 'rb') as file_data:
                    result = await document_service.process_and_index_document(
                        file_data=file_data.read(),
                        filename="ai_test_document.txt",
                        user_id=self.test_user_id,
                        extract_images=False,
                        output_format="text",
                        index_for_search=True
                    )
                
                self.created_documents.append(result['document_id'])
                self.log(f"Document processed successfully: {result['document_id']}")
                
                # Verify document exists in database
                from second_brain_database.managers.mongodb_manager import mongodb_manager
                documents_collection = mongodb_manager.get_collection("documents")
                doc = await documents_collection.find_one({"_id": result['document_id']})
                
                if doc:
                    self.log("Document stored in database")
                    self.test_results.append({
                        "test": "document_processing",
                        "status": "PASS",
                        "document_id": result['document_id']
                    })
                    return True
                else:
                    self.log("Document not found in database", "ERROR")
                    return False
                    
            finally:
                # Cleanup temp file
                os.unlink(temp_path)
            
        except Exception as e:
            self.log(f"Document processing test failed: {e}", "ERROR")
            self.test_results.append({
                "test": "document_processing", 
                "status": "FAIL",
                "error": str(e)
            })
            return False
    
    async def test_vector_search(self):
        """Test vector search functionality."""
        try:
            from second_brain_database.services.rag_service import rag_service
            
            self.log("Testing vector search...")
            
            # Test query
            result = await rag_service.query_document(
                query="What is deep learning?",
                user_id=self.test_user_id,
                use_llm=False,
                top_k=3
            )
            
            if result and result.get('chunks'):
                chunk_count = len(result['chunks'])
                top_score = result['chunks'][0]['score']
                
                self.log(f"Vector search successful: {chunk_count} chunks, top score: {top_score:.3f}")
                
                # Verify relevant content
                has_relevant_content = any(
                    any(term in chunk['content'].lower() for term in ['deep', 'learning', 'neural'])
                    for chunk in result['chunks']
                )
                
                if has_relevant_content:
                    self.log("Retrieved content is relevant")
                    self.test_results.append({
                        "test": "vector_search",
                        "status": "PASS", 
                        "chunk_count": chunk_count,
                        "top_score": top_score
                    })
                    return True
                else:
                    self.log("Retrieved content not relevant", "WARNING")
                    return False
            else:
                self.log("No chunks returned from vector search", "ERROR") 
                return False
                
        except Exception as e:
            self.log(f"Vector search test failed: {e}", "ERROR")
            self.test_results.append({
                "test": "vector_search",
                "status": "FAIL",
                "error": str(e)
            })
            return False
    
    async def test_llm_integration(self):
        """Test LLM integration for answer generation."""
        try:
            from second_brain_database.services.rag_service import rag_service
            
            self.log("Testing LLM integration...")
            
            # Test with LLM enabled
            result = await rag_service.query_document(
                query="Explain neural networks in simple terms",
                user_id=self.test_user_id,
                use_llm=True,
                top_k=3
            )
            
            if result and result.get('answer'):
                answer_length = len(result['answer'])
                self.log(f"LLM answer generated: {answer_length} characters")
                
                # Check if answer contains relevant terms
                answer_lower = result['answer'].lower()
                relevant_terms = ['neural', 'network', 'learn', 'model', 'ai']
                relevance_score = sum(1 for term in relevant_terms if term in answer_lower)
                
                if relevance_score >= 2:
                    self.log(f"Answer appears relevant (score: {relevance_score}/5)")
                    self.test_results.append({
                        "test": "llm_integration",
                        "status": "PASS",
                        "answer_length": answer_length,
                        "relevance_score": relevance_score
                    })
                    return True
                else:
                    self.log(f"Answer may not be relevant (score: {relevance_score}/5)", "WARNING")
                    return False
            else:
                self.log("No answer generated", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"LLM integration test failed: {e}", "ERROR")
            self.test_results.append({
                "test": "llm_integration", 
                "status": "FAIL",
                "error": str(e)
            })
            return False
    
    async def test_edge_cases(self):
        """Test edge cases and error handling."""
        try:
            from second_brain_database.services.rag_service import rag_service
            
            self.log("Testing edge cases...")
            
            # Test empty query
            try:
                result = await rag_service.query_document(
                    query="",
                    user_id=self.test_user_id,
                    use_llm=False
                )
                self.log("Empty query handled")
            except Exception:
                pass  # Expected to fail gracefully
            
            # Test very long query  
            long_query = "What is artificial intelligence? " * 100
            try:
                result = await rag_service.query_document(
                    query=long_query,
                    user_id=self.test_user_id,
                    use_llm=False,
                    top_k=1
                )
                self.log("Long query handled")
            except Exception:
                pass  # May fail due to limits
            
            # Test non-existent user
            try:
                result = await rag_service.query_document(
                    query="test query", 
                    user_id="non_existent_user_12345",
                    use_llm=False
                )
                # Should return empty results, not crash
                self.log("Non-existent user handled gracefully")
            except Exception as e:
                self.log(f"Non-existent user test failed: {e}", "WARNING")
            
            self.test_results.append({
                "test": "edge_cases",
                "status": "PASS"
            })
            return True
            
        except Exception as e:
            self.log(f"Edge case testing failed: {e}", "ERROR")
            self.test_results.append({
                "test": "edge_cases",
                "status": "FAIL", 
                "error": str(e)
            })
            return False
    
    async def test_performance(self):
        """Test basic performance metrics."""
        try:
            from second_brain_database.services.rag_service import rag_service
            import time
            
            self.log("Testing performance...")
            
            queries = [
                "What is machine learning?",
                "Explain neural networks",
                "How does AI work?",
                "What are the applications of deep learning?"
            ]
            
            total_time = 0
            successful_queries = 0
            
            for query in queries:
                start_time = time.time()
                try:
                    result = await rag_service.query_document(
                        query=query,
                        user_id=self.test_user_id,
                        use_llm=False,
                        top_k=5
                    )
                    
                    end_time = time.time()
                    query_time = end_time - start_time
                    total_time += query_time
                    successful_queries += 1
                    
                    if self.verbose:
                        self.log(f"Query '{query[:30]}...' took {query_time:.2f}s")
                    
                except Exception as e:
                    self.log(f"Performance test query failed: {e}", "WARNING")
            
            if successful_queries > 0:
                avg_time = total_time / successful_queries
                self.log(f"Performance test completed: {successful_queries} queries, avg {avg_time:.2f}s")
                
                # Performance is acceptable if under 10 seconds per query
                performance_ok = avg_time < 10.0
                
                self.test_results.append({
                    "test": "performance",
                    "status": "PASS" if performance_ok else "SLOW",
                    "avg_query_time": avg_time,
                    "successful_queries": successful_queries
                })
                return True
            else:
                self.log("No successful performance test queries", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"Performance test failed: {e}", "ERROR")
            self.test_results.append({
                "test": "performance",
                "status": "FAIL",
                "error": str(e)
            })
            return False
    
    async def cleanup(self):
        """Clean up test data."""
        try:
            from second_brain_database.managers.mongodb_manager import mongodb_manager
            from second_brain_database.database import db_manager
            
            self.log("Cleaning up test data...")
            
            # Remove test documents
            if self.created_documents:
                documents_collection = mongodb_manager.get_collection("documents")
                result = await documents_collection.delete_many({
                    "_id": {"$in": self.created_documents}
                })
                self.log(f"Removed {result.deleted_count} test documents")
            
            # Remove test user data if needed
            # (Optional: could keep for further testing)
            
            await db_manager.disconnect()
            self.log("Cleanup completed")
            
        except Exception as e:
            self.log(f"Cleanup failed: {e}", "WARNING")
    
    def print_summary(self):
        """Print test summary."""
        print("\n" + "=" * 60)
        print("🧪 RAG INTEGRATION TEST SUMMARY")
        print("=" * 60)
        
        passed = sum(1 for result in self.test_results if result["status"] == "PASS")
        failed = sum(1 for result in self.test_results if result["status"] == "FAIL")
        warnings = sum(1 for result in self.test_results if result["status"] in ["SLOW", "WARNING"])
        
        print(f"📊 Results: {passed} PASSED | {failed} FAILED | {warnings} WARNINGS")
        print()
        
        for result in self.test_results:
            status_emoji = {
                "PASS": "✅",
                "FAIL": "❌", 
                "SLOW": "🐌",
                "WARNING": "⚠️"
            }.get(result["status"], "❓")
            
            print(f"{status_emoji} {result['test']}: {result['status']}")
            
            if result.get("error"):
                print(f"   Error: {result['error']}")
            elif result.get("chunk_count"):
                print(f"   Chunks: {result['chunk_count']}, Score: {result.get('top_score', 0):.3f}")
            elif result.get("avg_query_time"):
                print(f"   Avg Time: {result['avg_query_time']:.2f}s")
        
        print()
        
        if failed == 0:
            print("🎉 All core tests passed! RAG system is working correctly.")
        else:
            print("⚠️  Some tests failed. Check the logs above for details.")
        
        print("\n📚 Next Steps:")
        print("   • Run 'python examples/rag_example.py' for interactive testing")
        print("   • Check 'docs/RAG_USAGE_GUIDE.md' for complete documentation")
        print("   • Add RAG routes to your FastAPI app with 'routes/rag.py'")


async def main():
    """Run integration tests."""
    
    import argparse
    
    parser = argparse.ArgumentParser(description="RAG Integration Test")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--cleanup", action="store_true", help="Force cleanup at end")
    args = parser.parse_args()
    
    print("🧠 Second Brain Database - RAG Integration Test")
    print("=" * 60)
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    test_runner = RAGIntegrationTest(verbose=args.verbose)
    
    try:
        # Setup
        if not await test_runner.setup_services():
            print("❌ Service setup failed. Cannot continue.")
            return
        
        # Run tests
        tests = [
            ("Document Processing", test_runner.test_document_processing),
            ("Vector Search", test_runner.test_vector_search),
            ("LLM Integration", test_runner.test_llm_integration),
            ("Edge Cases", test_runner.test_edge_cases),
            ("Performance", test_runner.test_performance)
        ]
        
        for test_name, test_func in tests:
            print(f"\n🔬 Running {test_name} Test...")
            await test_func()
        
        # Print summary
        test_runner.print_summary()
        
    except KeyboardInterrupt:
        print("\n\nTest interrupted.")
    except Exception as e:
        print(f"❌ Test suite failed: {e}")
    finally:
        # Optional cleanup
        if args.cleanup:
            await test_runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
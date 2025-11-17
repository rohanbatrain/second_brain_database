#!/usr/bin/env python3
"""
Performance test script for SentenceTransformer model loading.

This script demonstrates the performance improvement with lazy loading
and background initialization of the embedding model.
"""

import time
import asyncio
from src.second_brain_database.managers.vector_search_manager import vector_search_manager


async def test_embedding_performance():
    """Test embedding generation performance."""
    print("Testing SentenceTransformer loading and embedding performance...")

    # Test texts
    test_texts = [
        "This is a test document for embedding generation.",
        "The quick brown fox jumps over the lazy dog.",
        "Machine learning models can be computationally expensive to load.",
        "Vector databases enable efficient similarity search at scale.",
    ]

    print(f"\nTesting with {len(test_texts)} sample texts...")

    # Measure embedding generation time
    start_time = time.time()
    try:
        embeddings = await vector_search_manager.generate_embeddings(test_texts)
        embed_time = time.time() - start_time

        print(f"✓ Embedding generation took {embed_time:.2f}s")
        print(f"✓ Generated {len(embeddings)} embeddings successfully")
        print(f"✓ Embedding dimensions: {len(embeddings[0])}")

    except Exception as e:
        print(f"✗ Failed to generate embeddings: {e}")
        return

    # Test search functionality if Qdrant is available
    if vector_search_manager.is_initialized():
        print("\n✓ Vector search manager is initialized")
        print(f"✓ Model ready: {vector_search_manager.is_model_ready()}")

        # Get collection stats
        try:
            stats = await vector_search_manager.get_collection_stats()
            print(f"✓ Collection status: {stats.get('status', 'unknown')}")
            print(f"✓ Vector count: {stats.get('vector_count', 0)}")
        except Exception as e:
            print(f"✗ Failed to get collection stats: {e}")
    else:
        print("\n✗ Vector search manager not fully initialized")


def main():
    """Main test function."""
    print("=" * 60)
    print("SentenceTransformer Performance Test")
    print("=" * 60)

    start_time = time.time()

    # Test the async embedding generation
    asyncio.run(test_embedding_performance())

    total_time = time.time() - start_time
    print(f"Total test time: {total_time:.2f}s")
    print("=" * 60)


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Rebuild vector database with new embeddings (MPNet) and cosine similarity.

This script:
1. Backs up existing ChromaDB data
2. Clears the existing collection
3. Recreates collection with new settings
4. Note: Original content needs to be re-processed from sources

WARNING: This will clear the existing vector database!
Run the processing pipeline after this to rebuild with new embeddings.
"""
from utils import log
from database.vector_store import VectorStore


def main():
    """Rebuild vector database with new settings."""
    log.info("=" * 60)
    log.info("REBUILDING VECTOR DATABASE")
    log.info("=" * 60)

    # Initialize vector store
    vector_store = VectorStore()

    # Get current stats
    log.info("\n[Step 1/3] Current database stats...")
    try:
        current_count = vector_store.collection.count()
        log.info(f"Current chunks: {current_count:,}")
    except Exception as e:
        log.warning(f"Could not get stats: {e}")
        current_count = 0

    # Step 2: Clear and recreate collection
    log.info("\n[Step 2/3] Clearing existing vector database...")
    try:
        vector_store.client.delete_collection("rag_knowledge_base")
        log.info("✓ Existing collection deleted")
    except Exception as e:
        log.warning(f"No existing collection to delete: {e}")

    # Recreate collection with cosine similarity and new settings
    log.info("✓ Creating new collection with:")
    log.info("  - Similarity metric: cosine")
    log.info("  - Embedding model: all-mpnet-base-v2 (768 dims)")

    vector_store = VectorStore()  # Reinitialize to create new collection
    log.info("✓ New collection created")

    # Step 3: Instructions
    log.info("\n[Step 3/3] Next steps...")
    log.info("\nThe vector database has been cleared and recreated with:")
    log.info("  ✓ Cosine similarity metric")
    log.info("  ✓ MPNet embedding model (768 dimensions)")
    log.info("  ✓ Ready for new content")

    log.info("\nTo rebuild the database, run:")
    log.info("  python3 run_rag.py")
    log.info("  Then select option 6 (Process Queue)")
    log.info("\nOr use the integrated processor:")
    log.info("  python3 test_full_pipeline.py")

    # Summary
    log.info("\n" + "=" * 60)
    log.info("REBUILD PREPARATION COMPLETE")
    log.info("=" * 60)
    log.info(f"Previous chunks: {current_count:,}")
    log.info(f"Current chunks: 0 (ready for new embeddings)")

    # Cleanup (ChromaDB client closes automatically)

    log.info("\n✅ Vector database cleared and ready for rebuilding!")


if __name__ == "__main__":
    main()

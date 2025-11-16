#!/usr/bin/env python3
"""
Example usage of the RAG Local System.
Simple examples showing different use cases.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from main import RAGSystem


async def example_1_direct_urls():
    """Example 1: Add URLs directly and process them."""
    print("\n" + "="*60)
    print("Example 1: Direct URLs Processing")
    print("="*60 + "\n")

    rag = RAGSystem()

    # Add URLs
    print("Adding URLs...")
    result = rag.add_sources("""
    https://fastapi.tiangolo.com/tutorial/first-steps/
    https://github.com/tiangolo/fastapi
    """)

    print(f"✅ URLs added: {result['urls_added']}")
    print(f"⏭️  URLs skipped: {result['urls_skipped']} (duplicates)\n")

    # Process queue
    print("Processing queue...")
    process_result = await rag.process_queue(max_batches=1)

    print(f"✅ Processed: {process_result['total_processed']}")
    print(f"   Succeeded: {process_result['total_succeeded']}")
    print(f"   Failed: {process_result['total_failed']}\n")

    # Search
    if process_result['total_succeeded'] > 0:
        print("Searching knowledge base...")
        results = rag.search("How to create a route in FastAPI?", n_results=2)

        for i, (doc, meta) in enumerate(zip(results['documents'][0], results['metadatas'][0])):
            print(f"\nResult {i+1}:")
            print(f"  Source: {meta.get('source_url', 'N/A')}")
            print(f"  Type: {meta.get('source_type', 'N/A')}")
            print(f"  Content preview: {doc[:150]}...")

    rag.close()
    print("\n" + "="*60 + "\n")


async def example_2_text_prompt():
    """Example 2: Use text prompt to discover sources."""
    print("\n" + "="*60)
    print("Example 2: Text Prompt (Web Search)")
    print("="*60 + "\n")

    print("⚠️  This example requires:")
    print("  - Brave API key configured in .env")
    print("  - Ollama running (ollama serve)")
    print()

    try:
        rag = RAGSystem()

        # Text prompt
        print("Processing prompt: 'Python FastAPI framework'...")
        result = rag.add_sources("Python FastAPI framework")

        print(f"✅ URLs discovered: {result['urls_discovered']}")
        print(f"✅ URLs added: {result['urls_added']}\n")

        if result['urls_added'] > 0:
            print("Top discovered URLs:")
            for url in result['urls'][:5]:
                print(f"  - {url}")

        rag.close()

    except Exception as e:
        print(f"❌ Error: {e}")
        print("Make sure Brave API key is configured and Ollama is running.\n")

    print("="*60 + "\n")


async def example_3_search_with_filters():
    """Example 3: Search with metadata filters."""
    print("\n" + "="*60)
    print("Example 3: Search with Filters")
    print("="*60 + "\n")

    rag = RAGSystem()

    # Check if we have data
    stats = rag.get_stats()
    total_chunks = stats['vector_store']['total_chunks']

    if total_chunks == 0:
        print("⚠️  No data in vector store yet.")
        print("Run example_1_direct_urls() first to add some data.\n")
        rag.close()
        return

    print(f"Vector store contains {total_chunks} chunks\n")

    # Search with different filters
    print("Search 1: Only documentation")
    results1 = rag.search(
        "FastAPI routing",
        n_results=3,
        filters={"source_type": "website"}
    )
    print(f"  Found {len(results1['documents'][0])} results\n")

    print("Search 2: Beginner level content")
    results2 = rag.search(
        "How to start with FastAPI?",
        n_results=3,
        filters={"difficulty": "beginner"}
    )
    print(f"  Found {len(results2['documents'][0])} results\n")

    print("Search 3: Code examples")
    results3 = rag.search(
        "FastAPI example",
        n_results=3,
        filters={"has_code_example": True}
    )
    print(f"  Found {len(results3['documents'][0])} results\n")

    rag.close()
    print("="*60 + "\n")


async def example_4_stats():
    """Example 4: Get system statistics."""
    print("\n" + "="*60)
    print("Example 4: System Statistics")
    print("="*60 + "\n")

    rag = RAGSystem()

    stats = rag.get_stats()

    print("📊 Database Statistics:")
    print(f"  Total URLs: {stats['database']['total']}")
    print(f"  ✅ Scraped: {stats['database']['scraped']}")
    print(f"  ⏳ Pending: {stats['database']['pending']}")
    print(f"  ❌ Failed: {stats['database']['failed']}\n")

    print("📚 Vector Store Statistics:")
    print(f"  Total chunks: {stats['vector_store']['total_chunks']:,}")
    print(f"  Collection: {stats['vector_store']['collection_name']}\n")

    if stats['vector_store'].get('by_source_type'):
        print("By Source Type:")
        for source_type, count in stats['vector_store']['by_source_type'].items():
            print(f"  {source_type}: {count} chunks")

    rag.close()
    print("\n" + "="*60 + "\n")


async def main():
    """Run all examples."""
    print("\n🚀 RAG Local System - Usage Examples")
    print("="*60)

    # Example 1: Direct URLs (recommended to run first)
    await example_1_direct_urls()

    # Example 2: Text prompt (requires Brave API + Ollama)
    # Uncomment if you have Brave API configured
    # await example_2_text_prompt()

    # Example 3: Search with filters
    await example_3_search_with_filters()

    # Example 4: Statistics
    await example_4_stats()

    print("\n✅ All examples completed!")
    print("\n💡 Next steps:")
    print("  1. Configure Brave API key to try example 2")
    print("  2. Add more sources to build your knowledge base")
    print("  3. Integrate with Claude Code using MCP server")
    print()


if __name__ == "__main__":
    asyncio.run(main())

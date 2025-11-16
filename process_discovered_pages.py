#!/usr/bin/env python3
"""
Process all discovered web pages from website crawl
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from main import RAGSystem


async def process_discovered_pages():
    """Process all pending discovered pages."""

    print("\n" + "="*70)
    print("🌐 PROCESSING DISCOVERED WEB PAGES")
    print("="*70 + "\n")

    # Initialize RAG system
    rag = RAGSystem()

    # Check initial stats
    stats = rag.get_stats()
    print(f"📊 Initial Status:")
    print(f"   - Total URLs: {stats['database']['total']}")
    print(f"   - Pending: {stats['database']['pending']}")
    print(f"   - Scraped: {stats['database']['scraped']}")
    print()

    if stats['database']['pending'] == 0:
        print("⚠️  No pending URLs to process")
        rag.close()
        return

    print(f"🚀 Starting to process {stats['database']['pending']} pages...")
    print(f"   (This will scrape, chunk, and embed all discovered pages)")
    print()

    # Process all batches
    batch_num = 0
    total_processed = 0
    total_succeeded = 0

    while True:
        batch_num += 1
        print(f"\n{'='*70}")
        print(f"📦 BATCH {batch_num}")
        print(f"{'='*70}\n")

        # Process one batch (3 URLs based on BATCH_SIZE)
        result = await rag.process_queue(max_batches=1)

        total_processed += result['total_processed']
        total_succeeded += result['total_succeeded']

        print(f"\n✅ Batch {batch_num} complete:")
        print(f"   - Processed: {result['total_processed']}")
        print(f"   - Succeeded: {result['total_succeeded']}")
        print(f"   - Failed: {result['total_failed']}")

        # Check if there are more pending
        stats = rag.get_stats()
        remaining = stats['database']['pending']

        print(f"\n📊 Overall Progress:")
        print(f"   - Total processed so far: {total_processed}")
        print(f"   - Total succeeded: {total_succeeded}")
        print(f"   - Remaining: {remaining}")

        if remaining == 0:
            print(f"\n🎉 All pages processed!")
            break

        print(f"\n⏳ Continuing to next batch...")

    # Final stats
    print(f"\n\n{'='*70}")
    print("📊 FINAL STATISTICS")
    print(f"{'='*70}\n")

    final_stats = rag.get_stats()

    print(f"📦 Database:")
    print(f"   - Total URLs: {final_stats['database']['total']}")
    print(f"   - Scraped: {final_stats['database']['scraped']}")
    print(f"   - Failed: {final_stats['database']['failed']}")
    print()

    print(f"🗄️  Vector Store:")
    print(f"   - Total chunks: {final_stats['vector_store']['total_chunks']}")
    print()

    if final_stats['vector_store'].get('by_source_type'):
        print(f"📚 By source type:")
        for source_type, count in final_stats['vector_store']['by_source_type'].items():
            print(f"   - {source_type}: {count} chunks")
        print()

    # Test search on documentation
    if final_stats['vector_store']['total_chunks'] > 0:
        print(f"\n{'='*70}")
        print("🔍 TESTING SEARCH ON DOCUMENTATION")
        print(f"{'='*70}\n")

        queries = [
            "How to create a path parameter in FastAPI?",
            "What is dependency injection?",
            "How to use query parameters?"
        ]

        for query in queries:
            print(f"\n📝 Query: '{query}'")
            print("-" * 60)

            results = rag.search(query, n_results=3)

            if results['documents'] and results['documents'][0]:
                for i, (doc, meta, distance) in enumerate(zip(
                    results['documents'][0],
                    results['metadatas'][0],
                    results.get('distances', [[0]*len(results['documents'][0])])[0]
                ), 1):
                    score = 1 - distance if distance else 1.0
                    url = meta.get('source_url', 'N/A')

                    print(f"\nResult {i} (Score: {score:.3f}):")
                    print(f"URL: {url}")
                    print(f"Content: {doc[:200]}...")
            else:
                print("No results found")

    print(f"\n\n{'='*70}")
    print("✅ ALL DISCOVERED PAGES PROCESSED!")
    print(f"{'='*70}\n")

    # Cleanup
    rag.close()


if __name__ == "__main__":
    asyncio.run(process_discovered_pages())

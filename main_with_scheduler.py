#!/usr/bin/env python3
"""
Main entry point with optional refresh scheduler.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from orchestrator import Orchestrator
from queue_processor.integrated_processor import IntegratedProcessor
from database import VectorStore
from scheduler import RefreshScheduler
from utils import log


class RAGSystemWithScheduler:
    """RAG system with automatic refresh scheduler."""

    def __init__(self, enable_scheduler: bool = True):
        """
        Initialize RAG system.

        Args:
            enable_scheduler: Whether to enable automatic refresh scheduler
        """
        self.orchestrator = Orchestrator()
        self.processor = IntegratedProcessor()
        self.vector_store = VectorStore()
        self.scheduler = None

        if enable_scheduler:
            self.scheduler = RefreshScheduler()
            self.scheduler.start()
            log.info("✅ Refresh scheduler enabled")
        else:
            log.info("⏭️  Refresh scheduler disabled")

        log.info("RAG System initialized")

    def add_sources(self, user_input: str) -> dict:
        """Add sources to the system."""
        return self.orchestrator.process_input(user_input)

    async def process_queue(self, max_batches: int = None):
        """Process all pending URLs in queue."""
        return await self.processor.process_all(max_batches=max_batches)

    def search(self, query: str, n_results: int = 5, filters: dict = None):
        """Search the knowledge base."""
        from processing import Embedder

        embedder = Embedder()
        query_embedding = embedder.embed_single(query)

        results = self.vector_store.search(
            query_embedding=query_embedding,
            n_results=n_results,
            where=filters
        )

        return results

    def get_stats(self) -> dict:
        """Get system statistics."""
        db_stats = self.orchestrator.get_stats()
        vector_stats = self.vector_store.get_stats()

        return {
            'database': db_stats['database'],
            'vector_store': vector_stats,
            'scheduler': {
                'enabled': self.scheduler is not None,
                'running': self.scheduler.scheduler.running if self.scheduler else False
            }
        }

    async def manual_refresh(self):
        """Manually trigger a refresh job."""
        if not self.scheduler:
            log.warning("Scheduler not enabled")
            return

        await self.scheduler.run_refresh_now()

    def close(self):
        """Clean up resources."""
        self.orchestrator.close()
        self.processor.close()
        if self.scheduler:
            self.scheduler.close()
        log.info("RAG System closed")


async def main():
    """Example usage with scheduler."""
    print("\n" + "="*60)
    print("RAG Local System - With Automatic Refresh")
    print("="*60 + "\n")

    # Initialize with scheduler
    rag = RAGSystemWithScheduler(enable_scheduler=True)

    # Example: Add sources
    print("Adding sources...")
    result = rag.add_sources("https://fastapi.tiangolo.com/tutorial/first-steps/")
    print(f"✅ Added {result['urls_added']} URLs\n")

    # Process
    print("Processing queue...")
    process_result = await rag.process_queue(max_batches=1)
    print(f"✅ Processed: {process_result['total_processed']}\n")

    # Stats
    stats = rag.get_stats()
    print("📊 System Status:")
    print(f"   Database: {stats['database']}")
    print(f"   Vector Store: {stats['vector_store']['total_chunks']} chunks")
    print(f"   Scheduler: {'✅ Running' if stats['scheduler']['running'] else '❌ Stopped'}\n")

    print("="*60)
    print("✅ System is running with automatic refresh")
    print("   Refresh schedule: Every Monday at 3:00 AM")
    print("   Press Ctrl+C to stop")
    print("="*60 + "\n")

    # Keep running
    try:
        while True:
            await asyncio.sleep(3600)  # Sleep 1 hour
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        rag.close()


if __name__ == "__main__":
    asyncio.run(main())

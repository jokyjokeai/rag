#!/usr/bin/env python3
"""
Run the refresh scheduler as a background service.
"""
import asyncio
import signal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from scheduler import RefreshScheduler
from utils import log


# Global scheduler instance
scheduler = None


def signal_handler(sig, frame):
    """Handle shutdown signals gracefully."""
    log.info("Received shutdown signal")
    if scheduler:
        scheduler.close()
    sys.exit(0)


async def main():
    """Run the scheduler."""
    global scheduler

    log.info("="*60)
    log.info("RAG System - Refresh Scheduler Service")
    log.info("="*60)

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Initialize scheduler
    scheduler = RefreshScheduler()

    # Start scheduler
    scheduler.start()

    log.info("\n📅 Scheduler is running...")
    log.info(f"   Schedule: {scheduler.scheduler.get_jobs()[0].trigger if scheduler.scheduler.get_jobs() else 'N/A'}")
    log.info(f"   Press Ctrl+C to stop\n")

    # Keep running
    try:
        while True:
            await asyncio.sleep(60)  # Check every minute
    except KeyboardInterrupt:
        log.info("\nShutting down...")
        scheduler.close()


if __name__ == "__main__":
    asyncio.run(main())

"""
Queue manager for processing URLs with prioritization and batch processing.
"""
import asyncio
from typing import List, Dict, Any
from datetime import datetime
from database import URLDatabase, DiscoveredURL
from scrapers import YouTubeScraper, GitHubScraper, WebScraper
from config import settings
from utils import log, detect_url_type


class QueueManager:
    """Manages the processing queue for discovered URLs."""

    def __init__(self, url_db: URLDatabase):
        """
        Initialize queue manager.

        Args:
            url_db: URLDatabase instance
        """
        self.url_db = url_db
        self.batch_size = settings.batch_size
        self.concurrent_workers = settings.concurrent_workers

        # Initialize scrapers
        self.scrapers = {
            'youtube_video': YouTubeScraper(),
            'youtube_channel': YouTubeScraper(),  # Channel uses same scraper
            'github': GitHubScraper(),
            'website': WebScraper()
        }

        log.info(f"QueueManager initialized (batch_size={self.batch_size}, workers={self.concurrent_workers})")

    def get_queue_size(self) -> int:
        """
        Get current queue size (pending URLs).

        Returns:
            Number of pending URLs
        """
        pending_urls = self.url_db.get_pending_urls(limit=10000)
        return len(pending_urls)

    async def process_batch(self) -> Dict[str, Any]:
        """
        Process one batch of URLs from the queue.

        Returns:
            Dictionary with processing results
        """
        # Get next batch of URLs
        pending_urls = self.url_db.get_pending_urls(limit=self.batch_size)

        if not pending_urls:
            log.info("No pending URLs in queue")
            return {
                'processed': 0,
                'succeeded': 0,
                'failed': 0
            }

        log.info(f"Processing batch of {len(pending_urls)} URLs")

        # Process URLs concurrently
        tasks = []
        for url_obj in pending_urls:
            task = self._process_url(url_obj)
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Count successes and failures
        succeeded = sum(1 for r in results if isinstance(r, dict) and r.get('success'))
        failed = len(results) - succeeded

        log.info(f"Batch complete: {succeeded} succeeded, {failed} failed")

        return {
            'processed': len(results),
            'succeeded': succeeded,
            'failed': failed,
            'results': results
        }

    async def _process_url(self, url_obj: DiscoveredURL) -> Dict[str, Any]:
        """
        Process a single URL.

        Args:
            url_obj: DiscoveredURL object to process

        Returns:
            Dictionary with processing result
        """
        url = url_obj.url
        source_type = url_obj.source_type

        log.info(f"Processing URL: {url} (type: {source_type})")

        try:
            # Get appropriate scraper
            scraper = self.scrapers.get(source_type)
            if not scraper:
                log.error(f"No scraper found for type: {source_type}")
                self.url_db.update_url_status(
                    url_obj.url_hash,
                    status='failed',
                    error_message=f"No scraper for type {source_type}"
                )
                return {'success': False, 'url': url, 'error': 'No scraper'}

            # Scrape content
            result = await asyncio.to_thread(scraper.scrape, url)

            if result and result.get('success'):
                # Update database status
                self.url_db.update_url_status(
                    url_obj.url_hash,
                    status='scraped'
                )

                log.info(f"✅ Successfully scraped: {url}")
                return {
                    'success': True,
                    'url': url,
                    'content_length': len(result.get('content', '')),
                    'metadata': result.get('metadata', {})
                }
            else:
                # Scraping failed
                error_msg = result.get('error', 'Unknown error') if result else 'Scraper returned None'
                self.url_db.update_url_status(
                    url_obj.url_hash,
                    status='failed',
                    error_message=error_msg
                )

                log.warning(f"❌ Failed to scrape: {url} - {error_msg}")
                return {
                    'success': False,
                    'url': url,
                    'error': error_msg
                }

        except Exception as e:
            log.error(f"Error processing {url}: {e}")
            self.url_db.update_url_status(
                url_obj.url_hash,
                status='failed',
                error_message=str(e)
            )
            return {
                'success': False,
                'url': url,
                'error': str(e)
            }

    async def process_all(self, max_batches: int = None) -> Dict[str, Any]:
        """
        Process all pending URLs in batches.

        Args:
            max_batches: Maximum number of batches to process (None = all)

        Returns:
            Dictionary with overall processing statistics
        """
        total_processed = 0
        total_succeeded = 0
        total_failed = 0
        batches_processed = 0

        log.info("Starting to process all pending URLs")

        while True:
            # Check if we've reached max batches
            if max_batches and batches_processed >= max_batches:
                log.info(f"Reached max batches limit: {max_batches}")
                break

            # Process one batch
            result = await self.process_batch()

            if result['processed'] == 0:
                # No more URLs to process
                break

            # Update totals
            total_processed += result['processed']
            total_succeeded += result['succeeded']
            total_failed += result['failed']
            batches_processed += 1

            # Delay between batches (politeness)
            if settings.delay_between_batches > 0:
                log.debug(f"Waiting {settings.delay_between_batches}s before next batch")
                await asyncio.sleep(settings.delay_between_batches)

        log.info(f"Processing complete: {total_processed} URLs ({total_succeeded} succeeded, {total_failed} failed)")

        return {
            'total_processed': total_processed,
            'total_succeeded': total_succeeded,
            'total_failed': total_failed,
            'batches': batches_processed
        }

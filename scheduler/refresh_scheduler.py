"""
Automatic refresh scheduler for maintaining the knowledge base up-to-date.
"""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import hashlib
import aiohttp
from database import URLDatabase, VectorStore, DiscoveredURL
from scrapers import YouTubeScraper, GitHubScraper, WebScraper
from processing import ContentProcessor
from config import settings
from utils import log


class RefreshScheduler:
    """Automatic refresh scheduler for knowledge base maintenance."""

    def __init__(self):
        """Initialize refresh scheduler."""
        self.url_db = URLDatabase()
        self.vector_store = VectorStore()
        self.processor = ContentProcessor(self.vector_store)

        # Initialize scrapers
        self.scrapers = {
            'youtube_video': YouTubeScraper(),
            'youtube_channel': YouTubeScraper(),
            'github': GitHubScraper(),
            'website': WebScraper()
        }

        # Initialize scheduler
        self.scheduler = AsyncIOScheduler()
        self.is_running = False

        log.info("RefreshScheduler initialized")

    def start(self):
        """Start the refresh scheduler."""
        # Check state manager for runtime toggle
        try:
            from utils.state_manager import StateManager
            state = StateManager()
            enabled = state.get_auto_refresh_status()
        except:
            # Fallback to settings
            enabled = settings.enable_auto_refresh

        if not enabled:
            log.info("Auto-refresh disabled")
            self.is_running = False
            return

        # Get schedule from state or settings
        try:
            from utils.state_manager import StateManager
            state = StateManager()
            schedule = state.get_refresh_schedule()
        except:
            schedule = settings.refresh_schedule

        # Parse cron schedule (default: "0 3 * * 1" = Monday 3 AM)
        parts = schedule.split()
        if len(parts) != 5:
            log.error(f"Invalid cron schedule: {schedule}")
            return

        # Add refresh job
        self.scheduler.add_job(
            self._refresh_job,
            trigger=CronTrigger(
                minute=parts[0],
                hour=parts[1],
                day=parts[2],
                month=parts[3],
                day_of_week=parts[4]
            ),
            id='refresh_knowledge_base',
            name='Refresh Knowledge Base',
            replace_existing=True
        )

        # Start scheduler
        if not self.scheduler.running:
            self.scheduler.start()

        self.is_running = True
        log.info(f"Refresh scheduler started (schedule: {schedule})")

    async def _refresh_job(self):
        """Main refresh job executed on schedule."""
        log.info("="*60)
        log.info("Starting scheduled refresh job")
        log.info("="*60)

        try:
            # Get URLs that need refresh
            urls_to_refresh = self._get_urls_needing_refresh()

            if not urls_to_refresh:
                log.info("No URLs need refreshing")
                return

            log.info(f"Found {len(urls_to_refresh)} URLs to refresh")

            # Process each URL
            stats = {
                'processed': 0,
                'updated': 0,
                'unchanged': 0,
                'failed': 0
            }

            for url_obj in urls_to_refresh:
                result = await self._refresh_url(url_obj)

                stats['processed'] += 1
                if result['success']:
                    if result['updated']:
                        stats['updated'] += 1
                    else:
                        stats['unchanged'] += 1
                else:
                    stats['failed'] += 1

                # Small delay between refreshes
                await asyncio.sleep(2)

            log.info("="*60)
            log.info(f"Refresh job complete: {stats}")
            log.info("="*60)

        except Exception as e:
            log.error(f"Error in refresh job: {e}")

    def _get_urls_needing_refresh(self) -> list:
        """
        Get URLs that need refreshing.

        Returns:
            List of DiscoveredURL objects
        """
        import sqlite3

        cursor = self.url_db.conn.cursor()

        # Get URLs where:
        # - status = 'scraped' (successfully scraped before)
        # - refresh_frequency != 'never'
        # - next_refresh_at is NULL or <= NOW
        cursor.execute("""
            SELECT * FROM discovered_urls
            WHERE status = 'scraped'
              AND refresh_frequency != 'never'
              AND (next_refresh_at IS NULL OR next_refresh_at <= datetime('now'))
            ORDER BY priority DESC, last_crawled_at ASC
            LIMIT 100
        """)

        rows = cursor.fetchall()
        urls = [self.url_db._row_to_url(row) for row in rows]

        log.info(f"Found {len(urls)} URLs needing refresh")
        return urls

    async def _refresh_url(self, url_obj: DiscoveredURL) -> Dict[str, Any]:
        """
        Refresh a single URL.

        Args:
            url_obj: DiscoveredURL object to refresh

        Returns:
            Dictionary with refresh result
        """
        url = url_obj.url
        source_type = url_obj.source_type

        log.info(f"Refreshing: {url} (type: {source_type})")

        try:
            # Step 1: Check HTTP headers first (for websites only)
            if source_type == 'website':
                # Get old chunks to compare headers
                old_chunks = self.vector_store.get_by_source_url(url)
                should_scrape = await self._check_http_headers(url, old_chunks)

                if not should_scrape:
                    log.info(f"Website unchanged (HTTP headers) - skipping scrape")
                    # Update next_refresh_at and return
                    next_refresh = self._calculate_next_refresh(url_obj.refresh_frequency)
                    cursor = self.url_db.conn.cursor()
                    cursor.execute("""
                        UPDATE discovered_urls
                        SET next_refresh_at = ?
                        WHERE url_hash = ?
                    """, (next_refresh, url_obj.url_hash))
                    self.url_db.conn.commit()

                    return {
                        'success': True,
                        'updated': False,
                        'url': url,
                        'skipped_reason': 'unchanged_http_headers'
                    }

            # Step 2: Scrape new content
            scraper = self.scrapers.get(source_type)
            if not scraper:
                log.error(f"No scraper for type: {source_type}")
                return {'success': False, 'updated': False}

            scrape_result = await asyncio.to_thread(scraper.scrape, url)

            if not scrape_result or not scrape_result.get('success'):
                log.warning(f"Failed to scrape {url} during refresh")
                return {'success': False, 'updated': False}

            # Step 2: Check if content has changed
            new_content = scrape_result['content']
            new_metadata = scrape_result.get('metadata', {})

            # Get old metadata from vector store
            old_chunks = self.vector_store.get_by_source_url(url)
            old_metadata = {}

            if old_chunks['metadatas'] and len(old_chunks['metadatas']) > 0:
                old_metadata = old_chunks['metadatas'][0]

            # Determine if content changed
            content_changed = False
            updated = False

            # For GitHub repos: check commit hash first (faster than content hash)
            if source_type == 'github':
                new_commit = new_metadata.get('commit_hash')
                old_commit = old_metadata.get('commit_hash')

                if new_commit and old_commit and new_commit == old_commit:
                    log.info(f"GitHub repo unchanged (commit: {new_commit[:8]}) - skipping update")
                    content_changed = False
                else:
                    log.info(f"GitHub repo changed (old: {old_commit[:8] if old_commit else 'none'}, new: {new_commit[:8] if new_commit else 'none'})")
                    content_changed = True
            else:
                # For other sources: use content hash
                new_hash = hashlib.md5(new_content.encode('utf-8')).hexdigest()
                old_hash = old_metadata.get('content_hash')
                content_changed = (new_hash != old_hash)

            # Step 3: Update if content changed
            if content_changed:
                log.info(f"Content changed for {url} - updating...")

                # Delete old chunks
                deleted = self.vector_store.delete_by_source_url(url)
                log.info(f"Deleted {deleted} old chunks")

                # Process new content
                # Prepare metadata with content hash (for non-GitHub) or commit hash (for GitHub)
                process_metadata = {**scrape_result['metadata']}
                if source_type != 'github':
                    # Add content hash for non-GitHub sources
                    process_metadata['content_hash'] = new_hash

                process_result = await asyncio.to_thread(
                    self.processor.process,
                    url=url,
                    content=new_content,
                    metadata=process_metadata,
                    source_type=source_type
                )

                if process_result.get('success'):
                    log.info(f"✅ Updated {url}: {process_result['chunks_created']} new chunks")
                    updated = True
                else:
                    log.error(f"Failed to process updated content for {url}")
                    updated = False
            else:
                log.info(f"Content unchanged for {url}")
                updated = False

            # Step 4: Update next_refresh_at
            next_refresh = self._calculate_next_refresh(url_obj.refresh_frequency)

            cursor = self.url_db.conn.cursor()
            cursor.execute("""
                UPDATE discovered_urls
                SET last_crawled_at = ?,
                    next_refresh_at = ?
                WHERE url_hash = ?
            """, (datetime.now(), next_refresh, url_obj.url_hash))
            self.url_db.conn.commit()

            log.info(f"Next refresh scheduled for {next_refresh}")

            return {
                'success': True,
                'updated': updated,
                'url': url,
                'next_refresh': next_refresh
            }

        except Exception as e:
            log.error(f"Error refreshing {url}: {e}")
            return {'success': False, 'updated': False}

    def _calculate_next_refresh(self, frequency: str) -> datetime:
        """
        Calculate next refresh datetime based on frequency.

        Args:
            frequency: 'weekly', 'monthly', or 'never'

        Returns:
            Next refresh datetime
        """
        now = datetime.now()

        if frequency == 'weekly':
            return now + timedelta(days=7)
        elif frequency == 'monthly':
            return now + timedelta(days=30)
        else:
            # 'never' - but set far future just in case
            return now + timedelta(days=365*10)

    def stop(self):
        """Stop the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            log.info("Refresh scheduler stopped")

    async def run_refresh_now(self):
        """Manually trigger a refresh job (for testing)."""
        log.info("Manually triggering refresh job...")
        await self._refresh_job()

    async def _check_http_headers(self, url: str, old_chunks: Dict[str, Any]) -> bool:
        """
        Check HTTP headers (Last-Modified, ETag) to see if content changed.

        Args:
            url: URL to check
            old_chunks: Old chunks from vector store (contains metadata)

        Returns:
            True if should scrape (content changed or headers unavailable)
            False if can skip scraping (content unchanged)
        """
        try:
            # Get old headers from metadata
            old_metadata = {}
            if old_chunks.get('metadatas') and len(old_chunks['metadatas']) > 0:
                old_metadata = old_chunks['metadatas'][0]

            old_last_modified = old_metadata.get('http_last_modified')
            old_etag = old_metadata.get('http_etag')

            # Make HEAD request to get headers
            async with aiohttp.ClientSession() as session:
                async with session.head(url, timeout=aiohttp.ClientTimeout(total=10), allow_redirects=True) as response:
                    # Get new headers
                    new_last_modified = response.headers.get('Last-Modified')
                    new_etag = response.headers.get('ETag')

                    # If we have Last-Modified header
                    if new_last_modified and old_last_modified:
                        if new_last_modified == old_last_modified:
                            log.debug(f"Last-Modified unchanged: {new_last_modified}")
                            return False  # Skip scraping
                        else:
                            log.debug(f"Last-Modified changed: {old_last_modified} → {new_last_modified}")
                            return True  # Need to scrape

                    # If we have ETag header
                    if new_etag and old_etag:
                        if new_etag == old_etag:
                            log.debug(f"ETag unchanged: {new_etag}")
                            return False  # Skip scraping
                        else:
                            log.debug(f"ETag changed: {old_etag} → {new_etag}")
                            return True  # Need to scrape

                    # No useful headers - need to scrape to check content
                    log.debug("No Last-Modified or ETag headers available")
                    return True

        except asyncio.TimeoutError:
            log.warning(f"Timeout checking HTTP headers for {url}")
            return True  # On error, scrape anyway

        except Exception as e:
            log.warning(f"Error checking HTTP headers for {url}: {e}")
            return True  # On error, scrape anyway

    def toggle(self) -> bool:
        """
        Toggle scheduler on/off at runtime.

        Returns:
            True if now enabled, False if now disabled
        """
        try:
            from utils.state_manager import StateManager
            state = StateManager()

            # Toggle state
            new_state = state.toggle_auto_refresh()

            if new_state:
                # Enable: start scheduler
                self.start()
                log.info("Auto-refresh enabled (toggled)")
            else:
                # Disable: stop scheduler
                self.stop()
                log.info("Auto-refresh disabled (toggled)")

            return new_state

        except Exception as e:
            log.error(f"Error toggling scheduler: {e}")
            return self.is_running

    def get_next_run_time(self) -> str:
        """
        Get next scheduled refresh time.

        Returns:
            Datetime string or "Not scheduled"
        """
        try:
            job = self.scheduler.get_job('refresh_knowledge_base')
            if job and job.next_run_time:
                return job.next_run_time.strftime('%Y-%m-%d %H:%M:%S')
            return "Not scheduled"
        except:
            return "Not scheduled"

    def close(self):
        """Clean up resources."""
        self.stop()
        self.url_db.close()
        log.info("RefreshScheduler closed")

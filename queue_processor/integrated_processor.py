"""
Integrated processor that combines scraping and processing.
"""
import asyncio
from typing import Dict, Any
from database import URLDatabase, VectorStore, DiscoveredURL
from scrapers import YouTubeScraper, GitHubScraper, WebScraper
from scrapers.youtube_channel_crawler import YouTubeChannelCrawler
from scrapers.web_crawler import WebCrawler
from processing import ContentProcessor
from config import settings
from utils import log, normalize_url, compute_url_hash, detect_url_type


class IntegratedProcessor:
    """Integrated scraping and processing pipeline."""

    def __init__(self):
        """Initialize integrated processor."""
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

        # Initialize crawlers
        self.youtube_crawler = YouTubeChannelCrawler()
        self.web_crawler = WebCrawler()

        log.info("IntegratedProcessor initialized")

    def _handle_scrape_error(self, url_obj: DiscoveredURL, error_msg: str, is_temporary: bool):
        """
        Handle scraping errors with retry logic for temporary failures.

        Args:
            url_obj: DiscoveredURL object
            error_msg: Error message
            is_temporary: True if error is temporary (retriable)
        """
        MAX_RETRIES = 3

        if is_temporary and url_obj.retry_count < MAX_RETRIES:
            # Temporary error - retry with backoff
            new_retry_count = url_obj.retry_count + 1

            # Calculate backoff delay (exponential: 60s, 300s, 900s)
            backoff_seconds = 60 * (5 ** (new_retry_count - 1))

            log.warning(
                f"⏳ Temporary error for {url_obj.url} (retry {new_retry_count}/{MAX_RETRIES}). "
                f"Will retry in {backoff_seconds}s. Error: {error_msg}"
            )

            # Reset to pending with incremented retry count
            cursor = self.url_db.conn.cursor()
            cursor.execute("""
                UPDATE discovered_urls
                SET status = 'pending',
                    retry_count = ?,
                    error_message = ?
                WHERE url_hash = ?
            """, (new_retry_count, f"Retry {new_retry_count}/{MAX_RETRIES}: {error_msg}", url_obj.url_hash))
            self.url_db.conn.commit()
        else:
            # Permanent error OR max retries reached
            if url_obj.retry_count >= MAX_RETRIES:
                final_msg = f"Failed after {MAX_RETRIES} retries: {error_msg}"
                log.error(f"❌ {url_obj.url}: {final_msg}")
            else:
                final_msg = f"Permanent error: {error_msg}"
                log.error(f"❌ {url_obj.url}: {final_msg}")

            self.url_db.update_url_status(url_obj.url_hash, 'failed', final_msg)

    async def process_url(self, url_obj: DiscoveredURL) -> Dict[str, Any]:
        """
        Process a single URL through full pipeline.

        Args:
            url_obj: DiscoveredURL object

        Returns:
            Processing result dictionary
        """
        url = url_obj.url
        source_type = url_obj.source_type

        log.info(f"Processing URL: {url} (type: {source_type})")

        try:
            # Special handling for YouTube channels
            if source_type == 'youtube_channel':
                return await self._process_youtube_channel(url, url_obj)

            # Special handling for websites that should be crawled
            # Only crawl if it's a user-added URL (not discovered from another crawl)
            is_discovered = url_obj.discovered_from and 'website_crawl:' in url_obj.discovered_from
            if source_type == 'website' and not is_discovered and self.web_crawler.should_crawl_domain(url):
                return await self._process_website_crawl(url, url_obj)

            # Inform user when scraping a website (single page) instead of crawling
            if source_type == 'website' and not is_discovered:
                log.info(f"ℹ️  Single page scrape (not detected as documentation site)")
                log.info(f"   💡 Crawling triggers for: docs.*, wiki, tutorial, blog, readthedocs, etc.")

            # Step 1: Scrape content
            scraper = self.scrapers.get(source_type)
            if not scraper:
                error_msg = f"No scraper for type {source_type}"
                self.url_db.update_url_status(url_obj.url_hash, 'failed', error_msg)
                return {'success': False, 'url': url, 'error': error_msg}

            scrape_result = await asyncio.to_thread(scraper.scrape, url)

            if not scrape_result or not scrape_result.get('success'):
                error_msg = scrape_result.get('error', 'Scraping failed') if scrape_result else 'Scraper returned None'
                is_temporary = scrape_result.get('is_temporary_error', False) if scrape_result else False

                # Handle retry logic for temporary errors
                self._handle_scrape_error(url_obj, error_msg, is_temporary)
                return {'success': False, 'url': url, 'error': error_msg, 'will_retry': is_temporary and url_obj.retry_count < 3}

            # Step 2: Process content (chunk + embed + store)
            process_result = await asyncio.to_thread(
                self.processor.process,
                url=url,
                content=scrape_result['content'],
                metadata=scrape_result['metadata'],
                source_type=source_type
            )

            if process_result.get('success'):
                # Update database status
                self.url_db.update_url_status(url_obj.url_hash, 'scraped')

                log.info(f"✅ Successfully processed {url}: {process_result['chunks_created']} chunks")

                return {
                    'success': True,
                    'url': url,
                    'chunks_created': process_result['chunks_created'],
                    'document_id': process_result['document_id']
                }
            else:
                error_msg = process_result.get('error', 'Processing failed')
                self.url_db.update_url_status(url_obj.url_hash, 'failed', error_msg)
                return {'success': False, 'url': url, 'error': error_msg}

        except Exception as e:
            error_msg = str(e)
            log.error(f"Error processing {url}: {error_msg}")

            # For YouTube scrapers, check if error is temporary
            is_temporary = False
            if source_type in ['youtube_video', 'youtube_channel']:
                from scrapers.youtube_scraper import YouTubeScraper
                is_temporary = YouTubeScraper.is_temporary_error(error_msg)

            self._handle_scrape_error(url_obj, error_msg, is_temporary)
            return {'success': False, 'url': url, 'error': error_msg, 'will_retry': is_temporary and url_obj.retry_count < 3}

    async def process_batch(self, batch_size: int = None) -> Dict[str, Any]:
        """
        Process a batch of pending URLs.

        Args:
            batch_size: Number of URLs to process (defaults to config)

        Returns:
            Batch processing results
        """
        batch_size = batch_size or settings.batch_size

        # Get pending URLs
        pending_urls = self.url_db.get_pending_urls(limit=batch_size)

        if not pending_urls:
            log.info("No pending URLs")
            return {'processed': 0, 'succeeded': 0, 'failed': 0}

        log.info(f"Processing batch of {len(pending_urls)} URLs")

        # Check if batch contains YouTube videos (need rate limiting)
        youtube_urls = [u for u in pending_urls if u.source_type == 'youtube_video']
        has_youtube = len(youtube_urls) > 0

        if has_youtube:
            # YouTube-specific rate limiting to avoid IP bans
            semaphore = asyncio.Semaphore(settings.youtube_concurrent_workers)
            log.debug(f"Using YouTube rate limiting: {settings.youtube_concurrent_workers} concurrent, "
                     f"{settings.youtube_delay_between_requests}s delay")

            async def rate_limited_process(url_obj):
                """Process with rate limiting for YouTube."""
                async with semaphore:
                    result = await self.process_url(url_obj)
                    # Add delay after processing to avoid burst requests
                    if url_obj.source_type == 'youtube_video':
                        await asyncio.sleep(settings.youtube_delay_between_requests)
                    return result

            tasks = [rate_limited_process(url_obj) for url_obj in pending_urls]
        else:
            # Normal processing for other sources (website, GitHub)
            tasks = [self.process_url(url_obj) for url_obj in pending_urls]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Count results
        succeeded = sum(1 for r in results if isinstance(r, dict) and r.get('success'))
        failed = len(results) - succeeded

        log.info(f"Batch complete: {succeeded} succeeded, {failed} failed")

        return {
            'processed': len(results),
            'succeeded': succeeded,
            'failed': failed
        }

    async def process_all(self, max_batches: int = None) -> Dict[str, Any]:
        """
        Process all pending URLs.

        Args:
            max_batches: Maximum number of batches (None = all)

        Returns:
            Overall processing stats
        """
        total_processed = 0
        total_succeeded = 0
        total_failed = 0
        batches = 0

        log.info("Starting to process all pending URLs")

        while True:
            if max_batches and batches >= max_batches:
                break

            result = await self.process_batch()

            if result['processed'] == 0:
                break

            total_processed += result['processed']
            total_succeeded += result['succeeded']
            total_failed += result['failed']
            batches += 1

            # Delay between batches
            if settings.delay_between_batches > 0:
                await asyncio.sleep(settings.delay_between_batches)

        log.info(f"Processing complete: {total_processed} URLs, {total_succeeded} succeeded, {total_failed} failed")

        return {
            'total_processed': total_processed,
            'total_succeeded': total_succeeded,
            'total_failed': total_failed,
            'batches': batches
        }

    async def _process_website_crawl(self, website_url: str, url_obj: DiscoveredURL) -> Dict[str, Any]:
        """
        Process website by crawling pages and adding them to queue.

        Args:
            website_url: Website URL to crawl
            url_obj: DiscoveredURL object for the website

        Returns:
            Processing result dictionary
        """
        try:
            # Crawl website to discover pages
            log.info(f"🔗 Starting website crawl (max: 1000 pages)...")
            crawl_result = await self.web_crawler.crawl_website(
                website_url,
                max_pages=1000  # Limit to 1000 pages per website
            )

            if not crawl_result['success']:
                error_msg = crawl_result.get('error', 'Website crawl failed')
                self.url_db.update_url_status(url_obj.url_hash, 'failed', error_msg)
                return {'success': False, 'url': website_url, 'error': error_msg}

            discovered_pages = crawl_result['discovered_urls']

            # Add discovered pages to database
            log.info(f"💾 Adding {len(discovered_pages)} discovered pages to database...")
            added_count = 0
            duplicate_count = 0

            for i, page_url in enumerate(discovered_pages, 1):
                normalized_url = normalize_url(page_url)
                url_hash = compute_url_hash(normalized_url)

                # Check if already exists
                if self.url_db.url_exists(url_hash):
                    duplicate_count += 1
                    continue

                # Insert page URL
                url_obj_new = DiscoveredURL(
                    url=normalized_url,
                    url_hash=url_hash,
                    source_type='website',
                    status='pending',
                    discovered_from=f'website_crawl:{website_url}',
                    refresh_frequency=30,  # Monthly for discovered pages
                    priority=50  # Medium priority
                )

                self.url_db.insert_url(url_obj_new)
                added_count += 1

                # Progress update every 25 pages
                if i % 25 == 0:
                    log.info(f"   [{i}/{len(discovered_pages)}] Added {added_count} new, skipped {duplicate_count} duplicates")

            # Mark website as processed
            self.url_db.update_url_status(url_obj.url_hash, 'scraped')

            log.info(f"✅ Website crawled successfully!")
            log.info(f"   Total discovered: {len(discovered_pages)} | Added: {added_count} | Duplicates: {duplicate_count}")

            return {
                'success': True,
                'url': website_url,
                'pages_discovered': len(discovered_pages),
                'pages_added': added_count,
                'base_domain': crawl_result.get('base_domain', '')
            }

        except Exception as e:
            log.error(f"Error processing website crawl {website_url}: {e}")
            self.url_db.update_url_status(url_obj.url_hash, 'failed', str(e))
            return {'success': False, 'url': website_url, 'error': str(e)}

    async def _process_youtube_channel(self, channel_url: str, url_obj: DiscoveredURL) -> Dict[str, Any]:
        """
        Process YouTube channel by crawling videos and adding them to queue.

        Args:
            channel_url: YouTube channel URL
            url_obj: DiscoveredURL object for the channel

        Returns:
            Processing result dictionary
        """
        log.info(f"Crawling YouTube channel: {channel_url}")

        try:
            # Crawl channel to discover videos
            crawl_result = await asyncio.to_thread(
                self.youtube_crawler.crawl_channel,
                channel_url,
                max_videos=50  # Limit to 50 most recent videos
            )

            if not crawl_result['success']:
                error_msg = crawl_result.get('error', 'Channel crawl failed')
                self.url_db.update_url_status(url_obj.url_hash, 'failed', error_msg)
                return {'success': False, 'url': channel_url, 'error': error_msg}

            video_urls = crawl_result['video_urls']
            channel_info = crawl_result.get('channel_info', {})

            log.info(f"Discovered {len(video_urls)} videos from channel: {channel_info.get('title', 'Unknown')}")

            # Add discovered videos to database
            added_count = 0
            for video_url in video_urls:
                normalized_url = normalize_url(video_url)
                url_hash = compute_url_hash(normalized_url)

                # Check if already exists
                if self.url_db.url_exists(url_hash):
                    continue

                # Insert video URL
                url_obj_new = DiscoveredURL(
                    url=normalized_url,
                    url_hash=url_hash,
                    source_type='youtube_video',
                    status='pending',
                    discovered_from=f'channel:{channel_url}',
                    refresh_frequency='never',  # Videos don't change once published
                    priority=50  # Medium priority (discovered from channel)
                )

                self.url_db.insert_url(url_obj_new)
                added_count += 1

            # Mark channel as processed
            self.url_db.update_url_status(url_obj.url_hash, 'scraped')

            log.info(f"✅ Channel processed: added {added_count} videos to queue")

            return {
                'success': True,
                'url': channel_url,
                'videos_discovered': len(video_urls),
                'videos_added': added_count,
                'channel_info': channel_info
            }

        except Exception as e:
            log.error(f"Error processing YouTube channel {channel_url}: {e}")
            self.url_db.update_url_status(url_obj.url_hash, 'failed', str(e))
            return {'success': False, 'url': channel_url, 'error': str(e)}

    def close(self):
        """Clean up resources."""
        self.url_db.close()
        log.info("IntegratedProcessor closed")

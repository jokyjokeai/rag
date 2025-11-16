"""
Web crawler to discover URLs from websites.
"""
from typing import List, Dict, Any, Set
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import asyncio
from playwright.async_api import async_playwright
from utils import log, normalize_url


class WebCrawler:
    """Crawler for discovering URLs from websites."""

    def __init__(self):
        """Initialize web crawler."""
        self.visited = set()
        self.to_visit = set()

    async def crawl_website(
        self,
        start_url: str,
        max_pages: int = 1000,
        same_domain_only: bool = True
    ) -> Dict[str, Any]:
        """
        Crawl a website and discover all linked pages.

        Args:
            start_url: Starting URL
            max_pages: Maximum number of pages to discover
            same_domain_only: Only crawl pages from the same domain

        Returns:
            Dictionary with discovered URLs
        """
        from datetime import datetime

        log.info(f"🕷️  Crawling website: {start_url} (max: {max_pages} pages)")

        # Parse base URL
        parsed_start = urlparse(start_url)
        base_domain = parsed_start.netloc
        base_path = '/'.join(parsed_start.path.split('/')[:-1])  # Get directory path

        discovered_urls = []
        self.visited = set()
        self.to_visit = {normalize_url(start_url)}

        # Time tracking for ETA
        start_time = datetime.now()
        error_count = 0

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context()

                while self.to_visit and len(discovered_urls) < max_pages:
                    # Get next URL to visit
                    current_url = self.to_visit.pop()

                    # Skip if already visited
                    if current_url in self.visited:
                        continue

                    self.visited.add(current_url)

                    try:
                        # Load page
                        page = await context.new_page()
                        await page.goto(current_url, wait_until='domcontentloaded', timeout=10000)
                        await asyncio.sleep(0.5)  # Let JS render

                        # Get HTML
                        html = await page.content()
                        await page.close()

                        # Parse HTML
                        soup = BeautifulSoup(html, 'html.parser')

                        # Add current URL to discovered
                        discovered_urls.append(current_url)

                        # Find all links
                        links = soup.find_all('a', href=True)

                        for link in links:
                            href = link['href']

                            # Convert relative URLs to absolute
                            absolute_url = urljoin(current_url, href)

                            # Normalize
                            normalized = normalize_url(absolute_url)

                            # Skip if already visited
                            if normalized in self.visited:
                                continue

                            # Parse URL
                            parsed = urlparse(normalized)

                            # Filter based on criteria
                            if same_domain_only:
                                # Same domain check
                                if parsed.netloc != base_domain:
                                    continue

                            # Skip non-http(s) links
                            if parsed.scheme not in ['http', 'https']:
                                continue

                            # Skip files (images, videos, downloads)
                            path_lower = parsed.path.lower()
                            skip_extensions = [
                                '.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp',
                                '.mp4', '.avi', '.mov', '.pdf', '.zip', '.tar',
                                '.gz', '.rar', '.exe', '.dmg', '.iso'
                            ]
                            if any(path_lower.endswith(ext) for ext in skip_extensions):
                                continue

                            # Skip common non-content paths
                            skip_patterns = [
                                '/search', '/login', '/signup', '/cart',
                                '/checkout', '/account', '/admin', '/api/'
                            ]
                            if any(pattern in path_lower for pattern in skip_patterns):
                                continue

                            # Add to queue
                            self.to_visit.add(normalized)

                        # Progress feedback with visual indicators
                        current_count = len(discovered_urls)
                        log.info(f"📄 [{current_count}/{max_pages}] {current_url[:70]}...")
                        log.info(f"   → {len(links)} links found | Queue: {len(self.to_visit)} | Visited: {len(self.visited)}")

                        # Periodic summary every 10 pages
                        if current_count % 10 == 0 and current_count > 0:
                            elapsed = (datetime.now() - start_time).total_seconds()
                            avg_time_per_page = elapsed / current_count
                            remaining_pages = max_pages - current_count
                            eta_seconds = avg_time_per_page * remaining_pages
                            eta_minutes = int(eta_seconds / 60)

                            log.info(f"🔄 Progress: {current_count}/{max_pages} pages | Queue: {len(self.to_visit)} | "
                                   f"Elapsed: {int(elapsed)}s | ETA: ~{eta_minutes}min")

                    except Exception as e:
                        error_count += 1
                        log.warning(f"⚠️  Error crawling {current_url}: {e}")
                        continue

                await browser.close()

            # Final summary
            total_time = (datetime.now() - start_time).total_seconds()
            minutes = int(total_time / 60)
            seconds = int(total_time % 60)

            log.info(f"✅ Crawling complete: discovered {len(discovered_urls)} pages in {minutes}m {seconds}s")
            if error_count > 0:
                log.info(f"   ⚠️  Encountered {error_count} errors during crawling")

            return {
                'success': True,
                'discovered_urls': discovered_urls,
                'total_discovered': len(discovered_urls),
                'base_url': start_url,
                'base_domain': base_domain
            }

        except Exception as e:
            log.error(f"Error during website crawl: {e}")
            return {
                'success': False,
                'error': str(e),
                'discovered_urls': discovered_urls,
                'total_discovered': len(discovered_urls)
            }

    def should_crawl_domain(self, url: str) -> bool:
        """
        Determine if a URL should be crawled based on domain patterns.

        Args:
            url: URL to check

        Returns:
            True if URL should be crawled for multiple pages
        """
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        path = parsed.path.lower()

        # Documentation sites - always crawl
        doc_patterns = [
            'docs.', 'doc.', 'documentation',
            'wiki', 'confluence',
            'readthedocs', 'gitbook',
            'guide', 'tutorial', 'learn'
        ]

        if any(pattern in domain or pattern in path for pattern in doc_patterns):
            return True

        # Known documentation platforms
        doc_domains = [
            'github.com/*/wiki',
            'notion.site',
            'gitbook.io',
            'readme.io'
        ]

        for pattern in doc_domains:
            if pattern.split('/')[0] in domain:
                return True

        # Blog patterns - crawl if it looks like a blog
        blog_patterns = [
            '/blog', '/article', '/post', '/news'
        ]

        if any(pattern in path for pattern in blog_patterns):
            return True

        # Default: don't crawl unless it looks like documentation
        return False

"""
Web scraper for documentation and article websites.
"""
from typing import Dict, Any, Optional
from datetime import datetime
import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from urllib.parse import urlparse
from utils import log
from .base_scraper import BaseScraper


class WebScraper(BaseScraper):
    """Scraper for general web pages and documentation sites."""

    def __init__(self):
        """Initialize web scraper."""
        super().__init__()

    def scrape(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Scrape web page content (synchronous wrapper).

        Args:
            url: URL to scrape

        Returns:
            Dictionary with page content and metadata
        """
        return asyncio.run(self._scrape_async(url))

    async def _scrape_async(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Scrape web page content using Playwright.

        Args:
            url: URL to scrape

        Returns:
            Dictionary with page content and metadata
        """
        log.info(f"Scraping web page: {url}")

        try:
            async with async_playwright() as p:
                # Launch browser
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()

                # Set user agent
                await page.set_extra_http_headers({
                    'User-Agent': 'RAGBot/1.0 (Educational purposes; Knowledge base builder)',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9,fr;q=0.8',
                })

                # Navigate to page and wait for content to load
                await page.goto(url, wait_until='networkidle', timeout=30000)

                # Extra wait for dynamic content (JavaScript rendering)
                await asyncio.sleep(2)

                # Get HTML content
                html = await page.content()

                # Close browser
                await browser.close()

            # Parse HTML
            soup = BeautifulSoup(html, 'lxml')

            # Extract metadata
            metadata = self._extract_metadata(soup, url)

            # Extract main content
            content = self._extract_content(soup)

            # Convert to markdown
            markdown_content = self._html_to_markdown(content, soup)

            full_metadata = {
                **metadata,
                'source_type': 'website',
                'scraped_at': datetime.now().isoformat(),
                'content_length': len(markdown_content),
            }

            log.info(f"Scraped {len(markdown_content)} characters from {url}")

            return self._create_result(
                url=url,
                content=markdown_content,
                metadata=full_metadata,
                success=True
            )

        except asyncio.TimeoutError:
            log.error(f"Timeout while scraping {url}")
            return self._create_result(
                url=url,
                content="",
                metadata={},
                success=False,
                error="Request timeout"
            )

        except Exception as e:
            log.error(f"Error scraping {url}: {e}")
            return self._create_result(
                url=url,
                content="",
                metadata={},
                success=False,
                error=str(e)
            )

    def _extract_metadata(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """
        Extract metadata from HTML.

        Args:
            soup: BeautifulSoup object
            url: Source URL

        Returns:
            Dictionary with metadata
        """
        metadata = {}

        # Title
        title_tag = soup.find('title')
        metadata['title'] = title_tag.get_text().strip() if title_tag else ''

        # Meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if not meta_desc:
            meta_desc = soup.find('meta', attrs={'property': 'og:description'})
        metadata['description'] = meta_desc.get('content', '').strip() if meta_desc else ''

        # Author
        author_meta = soup.find('meta', attrs={'name': 'author'})
        metadata['author'] = author_meta.get('content', '').strip() if author_meta else ''

        # Published date
        date_meta = soup.find('meta', attrs={'property': 'article:published_time'})
        if not date_meta:
            date_meta = soup.find('meta', attrs={'name': 'publish-date'})
        metadata['published_at'] = date_meta.get('content', '').strip() if date_meta else ''

        # Domain
        parsed = urlparse(url)
        metadata['domain'] = parsed.netloc

        # Language
        html_tag = soup.find('html')
        metadata['language'] = html_tag.get('lang', 'en') if html_tag else 'en'

        return metadata

    def _extract_content(self, soup: BeautifulSoup) -> BeautifulSoup:
        """
        Extract main content from HTML, removing navigation, footer, etc.

        Args:
            soup: BeautifulSoup object

        Returns:
            BeautifulSoup object with main content only
        """
        import re

        # Remove unwanted elements by tag
        for element in soup(['script', 'style', 'nav', 'header', 'footer',
                            'aside', 'iframe', 'noscript']):
            element.decompose()

        # Remove elements with specific classes/IDs (more precise patterns)
        # Use word boundaries to avoid false matches like 'gradient' matching 'ad'
        unwanted_patterns = [
            r'\bnav\b', r'\bmenu\b', r'\bsidebar\b',
            r'\badvertisement\b', r'\bcookie\b',
            r'\bfooter\b', r'\bheader\b',
            r'\bsocial\b', r'\bshare\b', r'\bcomment\b'
        ]

        for pattern in unwanted_patterns:
            regex = re.compile(pattern, re.IGNORECASE)
            for element in soup.find_all(class_=lambda x: x and any(regex.search(cls) for cls in (x if isinstance(x, list) else [x]))):
                element.decompose()
            for element in soup.find_all(id=lambda x: x and regex.search(x)):
                element.decompose()

        # Try to find main content area
        main_content = (
            soup.find('main') or
            soup.find('article') or
            soup.find('div', class_=lambda x: x and 'content' in x.lower()) or
            soup.find('div', id=lambda x: x and 'content' in x.lower()) or
            soup.find('body')
        )

        # If main content is too small (< 500 chars), fall back to body
        if main_content and len(main_content.get_text()) < 500:
            body = soup.find('body')
            if body and len(body.get_text()) > len(main_content.get_text()):
                main_content = body

        return main_content if main_content else soup

    def _html_to_markdown(self, content: BeautifulSoup, soup: BeautifulSoup) -> str:
        """
        Convert HTML content to Markdown.

        Args:
            content: BeautifulSoup object with content
            soup: Original soup (for fallback)

        Returns:
            Markdown formatted string
        """
        if not content:
            content = soup

        # Convert to markdown
        markdown = md(str(content), heading_style="ATX", bullets="-")

        # Clean up excessive newlines
        import re
        markdown = re.sub(r'\n{3,}', '\n\n', markdown)

        # Remove excessive whitespace
        markdown = re.sub(r' +', ' ', markdown)

        return markdown.strip()

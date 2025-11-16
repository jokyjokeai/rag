"""
Web scraper for documentation and article websites.
"""
from typing import Dict, Any, Optional
from datetime import datetime
import requests
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
        self.headers = {
            'User-Agent': 'RAGBot/1.0 (Educational purposes; Knowledge base builder)',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,fr;q=0.8',
        }

    def scrape(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Scrape web page content.

        Args:
            url: URL to scrape

        Returns:
            Dictionary with page content and metadata
        """
        log.info(f"Scraping web page: {url}")

        try:
            # Fetch page
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()

            # Parse HTML
            soup = BeautifulSoup(response.content, 'lxml')

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
                'status_code': response.status_code,
                'content_type': response.headers.get('content-type', ''),
                'content_length': len(markdown_content),
                # HTTP headers for refresh detection
                'http_last_modified': response.headers.get('Last-Modified'),
                'http_etag': response.headers.get('ETag')
            }

            log.info(f"Scraped {len(markdown_content)} characters from {url}")

            return self._create_result(
                url=url,
                content=markdown_content,
                metadata=full_metadata,
                success=True
            )

        except requests.exceptions.Timeout:
            log.error(f"Timeout while scraping {url}")
            return self._create_result(
                url=url,
                content="",
                metadata={},
                success=False,
                error="Request timeout"
            )

        except requests.exceptions.RequestException as e:
            log.error(f"Request error for {url}: {e}")
            return self._create_result(
                url=url,
                content="",
                metadata={},
                success=False,
                error=str(e)
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
        # Remove unwanted elements
        for element in soup(['script', 'style', 'nav', 'header', 'footer',
                            'aside', 'iframe', 'noscript']):
            element.decompose()

        # Remove elements with specific classes/IDs (common patterns)
        unwanted_patterns = [
            'nav', 'menu', 'sidebar', 'advertisement', 'ad', 'cookie',
            'footer', 'header', 'social', 'share', 'comment'
        ]

        for pattern in unwanted_patterns:
            for element in soup.find_all(class_=lambda x: x and pattern in x.lower()):
                element.decompose()
            for element in soup.find_all(id=lambda x: x and pattern in x.lower()):
                element.decompose()

        # Try to find main content area
        main_content = (
            soup.find('main') or
            soup.find('article') or
            soup.find('div', class_=lambda x: x and 'content' in x.lower()) or
            soup.find('div', id=lambda x: x and 'content' in x.lower()) or
            soup.find('body')
        )

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

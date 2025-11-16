"""
Base scraper class for all specialized scrapers.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from utils import log


class BaseScraper(ABC):
    """Abstract base class for all scrapers."""

    def __init__(self):
        """Initialize base scraper."""
        self.name = self.__class__.__name__
        log.info(f"{self.name} initialized")

    @abstractmethod
    def scrape(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Scrape content from a URL.

        Args:
            url: URL to scrape

        Returns:
            Dictionary with scraped content and metadata, or None if failed
            {
                'url': str,
                'content': str,
                'metadata': dict,
                'success': bool,
                'error': str (if failed)
            }
        """
        pass

    def _create_result(
        self,
        url: str,
        content: str,
        metadata: Dict[str, Any],
        success: bool = True,
        error: Optional[str] = None,
        is_temporary_error: bool = False
    ) -> Dict[str, Any]:
        """
        Create standardized result dictionary.

        Args:
            url: Source URL
            content: Scraped content
            metadata: Metadata dictionary
            success: Whether scraping succeeded
            error: Error message if failed
            is_temporary_error: True if error is temporary (retriable)

        Returns:
            Standardized result dictionary
        """
        return {
            'url': url,
            'content': content,
            'metadata': metadata,
            'success': success,
            'error': error,
            'is_temporary_error': is_temporary_error
        }

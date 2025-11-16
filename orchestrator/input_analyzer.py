"""
Input analyzer that detects whether user input contains URLs or is a text prompt.
"""
from typing import Dict, List, Any
from utils import extract_urls, is_valid_url, log


class InputAnalyzer:
    """Analyzes user input to determine processing strategy."""

    @staticmethod
    def analyze(user_input: str) -> Dict[str, Any]:
        """
        Analyze user input and determine if it contains URLs or is a text prompt.

        Args:
            user_input: Raw user input string

        Returns:
            Dictionary with:
                - type: 'urls' or 'prompt'
                - urls: List of extracted URLs (if any)
                - text: Remaining text after URL extraction (if any)
                - needs_web_search: Boolean indicating if web search is needed
        """
        # Extract all URLs from input
        extracted_urls = extract_urls(user_input)

        # Validate URLs
        valid_urls = [url for url in extracted_urls if is_valid_url(url)]

        if valid_urls:
            # URLs found - this is a URL-based input
            # Remove URLs from text to see if there's remaining text
            remaining_text = user_input
            for url in valid_urls:
                remaining_text = remaining_text.replace(url, '').strip()

            log.info(f"Detected {len(valid_urls)} URLs in input")

            return {
                'type': 'urls',
                'urls': valid_urls,
                'text': remaining_text if remaining_text else None,
                'needs_web_search': False,  # Skip web search, go directly to crawling
                'skip_orchestration': True   # URLs already provided, no need for LLM analysis
            }
        else:
            # No URLs - this is a text prompt
            log.info("No URLs detected, treating as text prompt")

            return {
                'type': 'prompt',
                'urls': [],
                'text': user_input.strip(),
                'needs_web_search': True,   # Need to search web for relevant URLs
                'skip_orchestration': False  # Need LLM to analyze and generate search queries
            }

    @staticmethod
    def categorize_urls(urls: List[str]) -> Dict[str, List[str]]:
        """
        Categorize URLs by their type.

        Args:
            urls: List of URLs to categorize

        Returns:
            Dictionary with URLs grouped by type
        """
        from utils import detect_url_type

        categorized = {
            'youtube_channel': [],
            'youtube_video': [],
            'github': [],
            'website': []
        }

        for url in urls:
            url_type = detect_url_type(url)
            categorized[url_type].append(url)

        # Log summary
        summary = {k: len(v) for k, v in categorized.items() if v}
        log.info(f"URL categorization: {summary}")

        return categorized

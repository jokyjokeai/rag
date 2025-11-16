"""
Main orchestrator that coordinates input analysis, web search, and URL discovery.
"""
from typing import Dict, List, Any
from .input_analyzer import InputAnalyzer
from .query_analyzer import QueryAnalyzer
from .web_search import BraveSearchClient
from database import URLDatabase, DiscoveredURL
from utils import log, normalize_url, compute_url_hash, detect_url_type


class Orchestrator:
    """Main orchestrator for the RAG ingestion system."""

    def __init__(self):
        """Initialize orchestrator with all components."""
        self.input_analyzer = InputAnalyzer()
        self.query_analyzer = QueryAnalyzer()
        self.search_client = BraveSearchClient()
        self.url_db = URLDatabase()
        log.info("Orchestrator initialized")

    def process_input(
        self,
        user_input: str,
        priority: int = 100  # User inputs get highest priority
    ) -> Dict[str, Any]:
        """
        Process user input and add discovered URLs to the database.

        Args:
            user_input: Raw user input (URLs or text prompt)
            priority: Priority level for discovered URLs

        Returns:
            Dictionary with processing results
        """
        # Step 1: Analyze input
        analysis = self.input_analyzer.analyze(user_input)
        log.info(f"Input type: {analysis['type']}")

        discovered_urls = []

        if analysis['type'] == 'urls':
            # Direct URLs provided - skip web search
            discovered_urls = analysis['urls']
            log.info(f"Processing {len(discovered_urls)} direct URLs")

        elif analysis['type'] == 'prompt':
            # Text prompt - need to search web
            if not analysis['text']:
                log.warning("Empty prompt provided")
                return {
                    'success': False,
                    'error': 'Empty prompt',
                    'urls_added': 0
                }

            # Step 2: Use Ollama to generate search strategy
            strategy = self.query_analyzer.analyze_prompt(analysis['text'])

            # Step 3: Execute web searches
            # Adaptive URL count: more queries = fewer per query, fewer queries = more per query
            num_queries = len(strategy.get('search_queries', []))

            # Target total URLs: 40-60 unique URLs
            # If 10 queries: 5 per query = 50 total
            # If 20 queries: 3 per query = 60 total
            # If 25 queries: 2 per query = 50 total
            if num_queries <= 10:
                count_per_query = 5
            elif num_queries <= 15:
                count_per_query = 4
            else:
                count_per_query = 3

            log.info(f"Searching with {num_queries} queries, {count_per_query} results per query (target: ~{num_queries * count_per_query} URLs)")

            search_results = self.search_client.multi_search(
                queries=strategy.get('search_queries', []),
                count_per_query=count_per_query
            )

            # Step 4: Extract URLs from search results
            discovered_urls = self.search_client.extract_urls(search_results)
            log.info(f"Discovered {len(discovered_urls)} unique URLs from web search (after filtering)")

        # Step 5: Add URLs to database
        added_count = 0
        skipped_count = 0

        for url in discovered_urls:
            # Normalize URL
            normalized_url = normalize_url(url)
            url_hash = compute_url_hash(normalized_url)

            # Check if already exists
            if self.url_db.url_exists(url_hash):
                skipped_count += 1
                log.debug(f"URL already exists: {url}")
                continue

            # Detect URL type
            source_type = detect_url_type(normalized_url)

            # Determine refresh frequency based on type
            refresh_freq = self._get_refresh_frequency(source_type)

            # Create DiscoveredURL object
            url_obj = DiscoveredURL(
                url=normalized_url,
                url_hash=url_hash,
                source_type=source_type,
                status='pending',
                discovered_from='user_input' if analysis['type'] == 'urls' else 'web_search',
                refresh_frequency=refresh_freq,
                priority=priority,
                metadata={
                    'original_input': user_input[:200]  # Store snippet of original input
                }
            )

            # Insert into database
            url_id = self.url_db.insert_url(url_obj)
            if url_id:
                added_count += 1

        # Step 6: Return summary
        result = {
            'success': True,
            'input_type': analysis['type'],
            'urls_discovered': len(discovered_urls),
            'urls_added': added_count,
            'urls_skipped': skipped_count,
            'urls': discovered_urls
        }

        log.info(f"Processing complete: {added_count} URLs added, {skipped_count} skipped")
        return result

    def analyze_input(self, user_input: str) -> Dict[str, Any]:
        """
        Analyze input and discover URLs WITHOUT adding them to database.
        Used for interactive mode where user can select which URLs to add.

        Args:
            user_input: Raw user input (URLs or text prompt)

        Returns:
            Dictionary with discovered URLs (not added to DB)
        """
        # Step 1: Analyze input
        analysis = self.input_analyzer.analyze(user_input)
        log.info(f"Input type: {analysis['type']}")

        discovered_urls = []

        if analysis['type'] == 'urls':
            # Direct URLs provided
            discovered_urls = analysis['urls']
            log.info(f"Found {len(discovered_urls)} direct URLs")

        elif analysis['type'] == 'prompt':
            # Text prompt - search web
            if not analysis['text']:
                return {
                    'success': False,
                    'error': 'Empty prompt',
                    'urls': []
                }

            # Use Ollama to generate search strategy
            strategy = self.query_analyzer.analyze_prompt(analysis['text'])

            # Execute web searches
            search_results = self.search_client.multi_search(
                queries=strategy.get('search_queries', []),
                count_per_query=3
            )

            # Extract URLs from search results
            discovered_urls = self.search_client.extract_urls(search_results)
            log.info(f"Discovered {len(discovered_urls)} URLs from web search")

        return {
            'success': True,
            'input_type': analysis['type'],
            'urls': discovered_urls
        }

    def _get_refresh_frequency(self, source_type: str) -> str:
        """
        Determine refresh frequency based on source type.

        Args:
            source_type: Type of source

        Returns:
            Refresh frequency string
        """
        frequency_map = {
            'website': 'weekly',
            'github': 'weekly',
            'youtube_channel': 'weekly',
            'youtube_video': 'never'  # Videos don't change
        }

        return frequency_map.get(source_type, 'never')

    def get_stats(self) -> Dict[str, Any]:
        """
        Get orchestrator statistics.

        Returns:
            Dictionary with statistics
        """
        db_stats = self.url_db.get_stats()

        return {
            'database': db_stats,
            'orchestrator': 'ready'
        }

    def close(self):
        """Clean up resources."""
        self.url_db.close()
        log.info("Orchestrator shut down")

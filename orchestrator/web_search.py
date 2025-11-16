"""
Web search integration using Brave Search API.
"""
import requests
import time
from typing import List, Dict, Any, Optional
from config import settings
from utils import log


class BraveSearchClient:
    """Client for Brave Search API."""

    BASE_URL = "https://api.search.brave.com/res/v1/web/search"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Brave Search client.

        Args:
            api_key: Brave API key (defaults to settings)
        """
        self.api_key = api_key or settings.brave_api_key
        if not self.api_key:
            log.warning("Brave API key not configured")

    def search(
        self,
        query: str,
        count: int = 10,
        country: str = "US"
    ) -> List[Dict[str, Any]]:
        """
        Execute a web search using Brave Search API.

        Args:
            query: Search query string
            count: Number of results to return (max 20)
            country: Country code for search results

        Returns:
            List of search results with url, title, description
        """
        if not self.api_key:
            log.error("Cannot perform search: Brave API key not configured")
            return []

        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": self.api_key
        }

        params = {
            "q": query,
            "count": min(count, 20),  # API limit is 20
            "country": country
        }

        try:
            log.info(f"Searching Brave: '{query}' (count={count})")
            start_time = time.time()

            response = requests.get(
                self.BASE_URL,
                headers=headers,
                params=params,
                timeout=10
            )

            response_time_ms = int((time.time() - start_time) * 1000)
            response.raise_for_status()
            data = response.json()

            # Extract relevant information
            results = []
            if 'web' in data and 'results' in data['web']:
                for item in data['web']['results']:
                    results.append({
                        'url': item.get('url', ''),
                        'title': item.get('title', ''),
                        'description': item.get('description', ''),
                        'age': item.get('age', '')  # How recent the page is
                    })

            log.info(f"Found {len(results)} results for query: '{query}'")

            # Log API usage for rate limit tracking
            try:
                from utils.rate_limit_tracker import RateLimitTracker
                tracker = RateLimitTracker()
                tracker.log_query(query, success=True, response_time_ms=response_time_ms)
            except Exception as tracker_error:
                log.debug(f"Could not log rate limit: {tracker_error}")

            return results

        except requests.exceptions.RequestException as e:
            log.error(f"Brave Search API error: {e}")

            # Log failed query
            try:
                from utils.rate_limit_tracker import RateLimitTracker
                tracker = RateLimitTracker()
                tracker.log_query(query, success=False, response_time_ms=0)
            except:
                pass

            return []

        except Exception as e:
            log.error(f"Unexpected error during search: {e}")
            return []

    def multi_search(
        self,
        queries: List[str],
        count_per_query: int = 5
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Execute multiple searches and aggregate results.

        Args:
            queries: List of search queries
            count_per_query: Number of results per query

        Returns:
            Dictionary mapping query to list of results
        """
        all_results = {}

        for query in queries:
            results = self.search(query, count=count_per_query)
            all_results[query] = results

        return all_results

    def extract_urls(self, search_results: Dict[str, List[Dict[str, Any]]]) -> List[str]:
        """
        Extract unique URLs from search results with quality filtering.

        Args:
            search_results: Dictionary of search results from multi_search

        Returns:
            List of unique, high-quality URLs
        """
        import re

        # Blocklist patterns for low-quality or generic URLs
        blocklist_patterns = [
            # Generic course/tutorial listings
            r'best.*courses', r'top.*courses', r'best.*tutorial',
            r'.*content.*on.*youtube', r'best.*youtube.*channel',
            r'learn.*online', r'tutorial.*list',

            # Ads and promotional
            r'udemy\.com', r'coursera\.org', r'skillshare\.com',
            r'educative\.io', r'pluralsight\.com',

            # Low-quality aggregators
            r'nbshare\.io', r'coursetakers\.com',

            # Generic "how to choose" or "comparison" articles
            r'how.*to.*choose', r'comparison', r'vs\.',
            r'best.*practices.*for.*beginners',

            # Non-technical content
            r'/news/', r'press-release', r'announcement',

            # Too generic/beginner content
            r'beginners.*guide.*to.*(?:vue|react).*lifecycle',
            r'introduction.*for.*dummies',
            r'getting.*started.*for.*complete.*beginners',

            # Irrelevant platforms
            r'pinterest\.com', r'instagram\.com', r'facebook\.com',
        ]

        # Prioritize patterns (good signals) - Higher priority = better quality
        prioritize_patterns = [
            # TRÈS HAUTE PRIORITÉ (5 pts) - Chaînes YouTube complètes
            (r'youtube\.com/@', 5),  # YouTube channels (@handle format)
            (r'youtube\.com/c/', 5),  # YouTube channels (custom URL)
            (r'youtube\.com/channel/', 5),  # YouTube channels (channel ID)
            (r'youtube\.com/user/', 5),  # YouTube channels (legacy username)

            # HAUTE PRIORITÉ (4 pts) - Playlists et contenu structuré
            (r'youtube\.com/playlist', 4),  # YouTube playlists

            # PRIORITÉ ÉLEVÉE (3 pts) - Vidéos, GitHub, Docs
            (r'youtube\.com/watch', 3),  # YouTube videos
            (r'github\.com/(?!topics)', 3),  # GitHub repos (not topic pages)
            (r'readthedocs\.io', 3),  # ReadTheDocs
            (r'docs\..*\.(?:com|org|io)', 3),  # Official docs

            # PRIORITÉ MOYENNE (2 pts) - StackOverflow
            (r'stackoverflow\.com/questions', 2),  # StackOverflow

            # PRIORITÉ BASSE (1 pt) - Keywords génériques
            (r'tutorial', 1),  # Tutorial keyword
            (r'guide', 1),  # Guide keyword
            (r'example', 1),  # Example keyword
        ]

        urls_data = []

        for query, results in search_results.items():
            for result in results:
                url = result.get('url')
                if not url:
                    continue

                # Check if URL matches blocklist
                is_blocked = any(re.search(pattern, url, re.IGNORECASE)
                               for pattern in blocklist_patterns)

                if is_blocked:
                    log.debug(f"Blocked low-quality URL: {url}")
                    continue

                # Check if URL is prioritized (using weighted scoring)
                priority_score = sum(score for pattern, score in prioritize_patterns
                                    if re.search(pattern, url, re.IGNORECASE))

                urls_data.append({
                    'url': url,
                    'priority': priority_score
                })

        # Remove duplicates and sort by priority
        seen = set()
        unique_urls_data = []
        for item in urls_data:
            if item['url'] not in seen:
                seen.add(item['url'])
                unique_urls_data.append(item)

        # Sort by priority (highest first)
        unique_urls_data.sort(key=lambda x: x['priority'], reverse=True)

        # Extract just the URLs
        unique_urls = [item['url'] for item in unique_urls_data]

        # Count by priority level for better logging
        priority_5_count = sum(1 for item in unique_urls_data if item['priority'] >= 5)
        priority_4_count = sum(1 for item in unique_urls_data if item['priority'] == 4)
        priority_3_count = sum(1 for item in unique_urls_data if item['priority'] == 3)
        prioritized_count = sum(1 for item in unique_urls_data if item['priority'] > 0)

        log.info(f"Extracted {len(unique_urls)} unique URLs from search results")
        log.info(f"  YouTube Channels (5 pts):  {priority_5_count}")
        log.info(f"  YouTube Playlists (4 pts): {priority_4_count}")
        log.info(f"  Videos/Docs/GitHub (3 pts): {priority_3_count}")
        log.info(f"  Other prioritized: {prioritized_count - priority_5_count - priority_4_count - priority_3_count}")
        log.info(f"  Normal: {len(unique_urls) - prioritized_count}")

        return unique_urls

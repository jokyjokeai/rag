"""
Brave Search API Rate Limit Tracker.
"""
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from utils import log
import sqlite3


class RateLimitTracker:
    """Track Brave Search API usage and quota."""

    def __init__(self, db_path: str = "data/discovered_urls.db"):
        """Initialize rate limit tracker."""
        self.db_path = Path(db_path)
        self._ensure_table()

    def _ensure_table(self):
        """Create api_usage_log table if not exists."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_usage_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                api_name TEXT NOT NULL,
                query TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                success BOOLEAN,
                response_time_ms INTEGER,
                remaining_quota INTEGER
            )
        """)

        conn.commit()
        conn.close()

    def log_query(
        self,
        query: str,
        success: bool = True,
        response_time_ms: int = 0,
        remaining_quota: Optional[int] = None
    ):
        """
        Log a Brave Search API query.

        Args:
            query: Search query text
            success: Whether query succeeded
            response_time_ms: Response time in milliseconds
            remaining_quota: Remaining quota if available
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO api_usage_log (
                    api_name, query, success, response_time_ms, remaining_quota
                ) VALUES (?, ?, ?, ?, ?)
            """, ("brave_search", query, success, response_time_ms, remaining_quota))

            conn.commit()
            conn.close()

            log.debug(f"Logged Brave Search query: {query[:50]}...")

        except Exception as e:
            log.error(f"Error logging API usage: {e}")

    def get_daily_usage(self, date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Get usage statistics for a specific day.

        Args:
            date: Date to check (default: today)

        Returns:
            Dictionary with usage statistics
        """
        if date is None:
            date = datetime.now()

        start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Count queries for the day
            cursor.execute("""
                SELECT COUNT(*) FROM api_usage_log
                WHERE api_name = 'brave_search'
                AND timestamp >= ?
                AND timestamp < ?
            """, (start_of_day.strftime('%Y-%m-%d %H:%M:%S'), end_of_day.strftime('%Y-%m-%d %H:%M:%S')))

            queries_used = cursor.fetchone()[0]

            # Get successful queries
            cursor.execute("""
                SELECT COUNT(*) FROM api_usage_log
                WHERE api_name = 'brave_search'
                AND timestamp >= ?
                AND timestamp < ?
                AND success = 1
            """, (start_of_day.strftime('%Y-%m-%d %H:%M:%S'), end_of_day.strftime('%Y-%m-%d %H:%M:%S')))

            queries_success = cursor.fetchone()[0]

            # Get average response time
            cursor.execute("""
                SELECT AVG(response_time_ms) FROM api_usage_log
                WHERE api_name = 'brave_search'
                AND timestamp >= ?
                AND timestamp < ?
                AND success = 1
            """, (start_of_day.strftime('%Y-%m-%d %H:%M:%S'), end_of_day.strftime('%Y-%m-%d %H:%M:%S')))

            avg_response_time = cursor.fetchone()[0] or 0

            conn.close()

            return {
                'queries_used': queries_used,
                'queries_success': queries_success,
                'queries_failed': queries_used - queries_success,
                'avg_response_time_ms': int(avg_response_time),
                'date': date.strftime('%Y-%m-%d')
            }

        except Exception as e:
            log.error(f"Error getting daily usage: {e}")
            return {
                'queries_used': 0,
                'queries_success': 0,
                'queries_failed': 0,
                'avg_response_time_ms': 0,
                'date': date.strftime('%Y-%m-%d')
            }

    def get_rate_limit_status(self, daily_quota: int = 2000) -> Dict[str, Any]:
        """
        Get current rate limit status.

        Args:
            daily_quota: Daily API quota (default: 2000 for free tier)

        Returns:
            Dictionary with rate limit information
        """
        usage = self.get_daily_usage()

        queries_used = usage['queries_used']
        queries_remaining = max(0, daily_quota - queries_used)
        usage_percent = (queries_used / daily_quota * 100) if daily_quota > 0 else 0

        # Calculate time until reset (midnight)
        now = datetime.now()
        midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        time_until_reset = midnight - now

        hours = int(time_until_reset.total_seconds() // 3600)
        minutes = int((time_until_reset.total_seconds() % 3600) // 60)

        return {
            'daily_quota': daily_quota,
            'queries_used': queries_used,
            'queries_remaining': queries_remaining,
            'usage_percent': usage_percent,
            'queries_success': usage['queries_success'],
            'queries_failed': usage['queries_failed'],
            'avg_response_time_ms': usage['avg_response_time_ms'],
            'reset_in_hours': hours,
            'reset_in_minutes': minutes,
            'quota_exceeded': queries_used >= daily_quota
        }

    def get_recent_queries(self, limit: int = 5) -> list:
        """
        Get recent API queries.

        Args:
            limit: Number of queries to retrieve

        Returns:
            List of recent queries with metadata
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT query, timestamp, success, response_time_ms
                FROM api_usage_log
                WHERE api_name = 'brave_search'
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))

            rows = cursor.fetchall()
            conn.close()

            queries = []
            for row in rows:
                queries.append({
                    'query': row[0],
                    'timestamp': row[1],
                    'success': bool(row[2]),
                    'response_time_ms': row[3]
                })

            return queries

        except Exception as e:
            log.error(f"Error getting recent queries: {e}")
            return []

    def is_quota_exceeded(self, daily_quota: int = 2000) -> bool:
        """
        Check if daily quota has been exceeded.

        Args:
            daily_quota: Daily API quota

        Returns:
            True if quota exceeded
        """
        usage = self.get_daily_usage()
        return usage['queries_used'] >= daily_quota

    def get_warning_threshold(self, daily_quota: int = 2000, threshold: float = 0.8) -> bool:
        """
        Check if usage is above warning threshold.

        Args:
            daily_quota: Daily API quota
            threshold: Warning threshold (default: 0.8 = 80%)

        Returns:
            True if above threshold
        """
        usage = self.get_daily_usage()
        return usage['queries_used'] >= (daily_quota * threshold)

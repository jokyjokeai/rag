"""
SQLite database models and schema for discovered URLs.
"""
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any
from config import settings
from utils import log


class DiscoveredURL:
    """Model representing a discovered URL in the database."""

    def __init__(
        self,
        id: Optional[int] = None,
        url: str = "",
        url_hash: str = "",
        source_type: str = "",
        status: str = "pending",
        discovered_at: Optional[datetime] = None,
        discovered_from: str = "user_input",
        last_crawled_at: Optional[datetime] = None,
        next_refresh_at: Optional[datetime] = None,
        refresh_frequency: str = "never",
        retry_count: int = 0,
        error_message: Optional[str] = None,
        priority: int = 0,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.id = id
        self.url = url
        self.url_hash = url_hash
        self.source_type = source_type
        self.status = status
        self.discovered_at = discovered_at or datetime.now()
        self.discovered_from = discovered_from
        self.last_crawled_at = last_crawled_at
        self.next_refresh_at = next_refresh_at
        self.refresh_frequency = refresh_frequency
        self.retry_count = retry_count
        self.error_message = error_message
        self.priority = priority
        self.metadata = metadata or {}


class URLDatabase:
    """SQLite database manager for discovered URLs."""

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path or settings.sqlite_db_path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn: Optional[sqlite3.Connection] = None
        self._connect()
        self._create_tables()

    def _connect(self):
        """Establish database connection."""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Enable column access by name
        log.info(f"Connected to SQLite database at {self.db_path}")

    def _create_tables(self):
        """Create tables if they don't exist."""
        cursor = self.conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS discovered_urls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                url_hash TEXT UNIQUE NOT NULL,
                source_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                discovered_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                discovered_from TEXT NOT NULL,
                last_crawled_at TIMESTAMP,
                next_refresh_at TIMESTAMP,
                refresh_frequency TEXT DEFAULT 'never',
                retry_count INTEGER DEFAULT 0,
                error_message TEXT,
                priority INTEGER DEFAULT 0,
                metadata TEXT
            )
        """)

        # Create indexes for performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_url_hash
            ON discovered_urls(url_hash)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_status
            ON discovered_urls(status)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_priority
            ON discovered_urls(priority DESC)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_next_refresh
            ON discovered_urls(next_refresh_at)
        """)

        self.conn.commit()
        log.info("Database tables created/verified")

    def url_exists(self, url_hash: str) -> bool:
        """
        Check if URL already exists in database.

        Args:
            url_hash: MD5 hash of the URL

        Returns:
            True if URL exists, False otherwise
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM discovered_urls WHERE url_hash = ?",
            (url_hash,)
        )
        count = cursor.fetchone()[0]
        return count > 0

    def insert_url(self, url_obj: DiscoveredURL) -> Optional[int]:
        """
        Insert a new URL into the database.

        Args:
            url_obj: DiscoveredURL object to insert

        Returns:
            ID of inserted row or None if already exists
        """
        if self.url_exists(url_obj.url_hash):
            log.debug(f"URL already exists: {url_obj.url}")
            return None

        cursor = self.conn.cursor()
        import json

        cursor.execute("""
            INSERT INTO discovered_urls (
                url, url_hash, source_type, status, discovered_at,
                discovered_from, refresh_frequency, priority, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            url_obj.url,
            url_obj.url_hash,
            url_obj.source_type,
            url_obj.status,
            url_obj.discovered_at,
            url_obj.discovered_from,
            url_obj.refresh_frequency,
            url_obj.priority,
            json.dumps(url_obj.metadata)
        ))

        self.conn.commit()
        url_id = cursor.lastrowid
        log.info(f"Inserted URL: {url_obj.url} (ID: {url_id}, Type: {url_obj.source_type})")
        return url_id

    def get_pending_urls(self, limit: int = 10) -> List[DiscoveredURL]:
        """
        Get URLs pending for scraping, ordered by priority.

        Args:
            limit: Maximum number of URLs to return

        Returns:
            List of DiscoveredURL objects
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM discovered_urls
            WHERE status IN ('pending', 'failed')
              AND retry_count < ?
            ORDER BY priority DESC, discovered_at ASC
            LIMIT ?
        """, (settings.max_retries, limit))

        return [self._row_to_url(row) for row in cursor.fetchall()]

    def update_url_status(
        self,
        url_hash: str,
        status: str,
        error_message: Optional[str] = None
    ):
        """
        Update the status of a URL.

        Args:
            url_hash: Hash of the URL to update
            status: New status ('pending', 'scraped', 'failed')
            error_message: Optional error message if failed
        """
        cursor = self.conn.cursor()

        if status == 'scraped':
            cursor.execute("""
                UPDATE discovered_urls
                SET status = ?,
                    last_crawled_at = ?,
                    retry_count = 0,
                    error_message = NULL
                WHERE url_hash = ?
            """, (status, datetime.now(), url_hash))
        elif status == 'failed':
            cursor.execute("""
                UPDATE discovered_urls
                SET status = ?,
                    retry_count = retry_count + 1,
                    error_message = ?
                WHERE url_hash = ?
            """, (status, error_message, url_hash))
        else:
            cursor.execute("""
                UPDATE discovered_urls
                SET status = ?
                WHERE url_hash = ?
            """, (status, url_hash))

        self.conn.commit()
        log.debug(f"Updated URL status to '{status}' for hash: {url_hash}")

    def get_stats(self) -> Dict[str, int]:
        """
        Get database statistics.

        Returns:
            Dictionary with statistics
        """
        cursor = self.conn.cursor()

        stats = {}
        cursor.execute("SELECT COUNT(*) FROM discovered_urls")
        stats['total'] = cursor.fetchone()[0]

        for status in ['pending', 'scraped', 'failed']:
            cursor.execute(
                "SELECT COUNT(*) FROM discovered_urls WHERE status = ?",
                (status,)
            )
            stats[status] = cursor.fetchone()[0]

        return stats

    def _row_to_url(self, row: sqlite3.Row) -> DiscoveredURL:
        """Convert database row to DiscoveredURL object."""
        import json

        return DiscoveredURL(
            id=row['id'],
            url=row['url'],
            url_hash=row['url_hash'],
            source_type=row['source_type'],
            status=row['status'],
            discovered_at=datetime.fromisoformat(row['discovered_at']) if row['discovered_at'] else None,
            discovered_from=row['discovered_from'],
            last_crawled_at=datetime.fromisoformat(row['last_crawled_at']) if row['last_crawled_at'] else None,
            next_refresh_at=datetime.fromisoformat(row['next_refresh_at']) if row['next_refresh_at'] else None,
            refresh_frequency=row['refresh_frequency'],
            retry_count=row['retry_count'],
            error_message=row['error_message'],
            priority=row['priority'],
            metadata=json.loads(row['metadata']) if row['metadata'] else {}
        )

    def clear_queue(self, status_filter: str = "pending") -> int:
        """
        Clear URLs from queue by status.

        Args:
            status_filter: Status to delete ('pending', 'failed', or 'all')

        Returns:
            Number of URLs deleted
        """
        cursor = self.conn.cursor()

        if status_filter == "all":
            cursor.execute("SELECT COUNT(*) FROM discovered_urls WHERE status IN ('pending', 'failed')")
            count = cursor.fetchone()[0]

            cursor.execute("DELETE FROM discovered_urls WHERE status IN ('pending', 'failed')")
        else:
            cursor.execute("SELECT COUNT(*) FROM discovered_urls WHERE status = ?", (status_filter,))
            count = cursor.fetchone()[0]

            cursor.execute("DELETE FROM discovered_urls WHERE status = ?", (status_filter,))

        self.conn.commit()
        log.info(f"Cleared {count} URLs with status={status_filter} from queue")

        return count

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            log.info("Database connection closed")

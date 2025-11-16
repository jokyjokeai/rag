"""
Database Reset Manager with backup and restore capabilities.
"""
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
import sqlite3
import shutil
import tarfile
from utils import log


class ResetManager:
    """Manage safe database reset with automatic backups."""

    def __init__(
        self,
        sqlite_db_path: str = "data/discovered_urls.db",
        chroma_db_path: str = "data/chroma_db",
        backup_dir: str = "data/backups"
    ):
        """
        Initialize reset manager.

        Args:
            sqlite_db_path: Path to SQLite database
            chroma_db_path: Path to ChromaDB directory
            backup_dir: Directory for backups
        """
        self.sqlite_db_path = Path(sqlite_db_path)
        self.chroma_db_path = Path(chroma_db_path)
        self.backup_dir = Path(backup_dir)

        # Create backup directory if not exists
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def get_database_sizes(self) -> Dict[str, Any]:
        """
        Get sizes of databases.

        Returns:
            Dictionary with database sizes and counts
        """
        sizes = {}

        # SQLite size and URL count
        if self.sqlite_db_path.exists():
            sizes['sqlite_size_mb'] = self.sqlite_db_path.stat().st_size / (1024 * 1024)

            try:
                conn = sqlite3.connect(self.sqlite_db_path)
                cursor = conn.cursor()

                cursor.execute("SELECT COUNT(*) FROM discovered_urls")
                sizes['sqlite_url_count'] = cursor.fetchone()[0]

                conn.close()
            except Exception as e:
                log.error(f"Error counting URLs: {e}")
                sizes['sqlite_url_count'] = 0
        else:
            sizes['sqlite_size_mb'] = 0
            sizes['sqlite_url_count'] = 0

        # ChromaDB size and chunk count
        if self.chroma_db_path.exists():
            # Calculate directory size
            total_size = sum(
                f.stat().st_size
                for f in self.chroma_db_path.rglob('*')
                if f.is_file()
            )
            sizes['chroma_size_mb'] = total_size / (1024 * 1024)

            # Get chunk count from ChromaDB
            try:
                from database import VectorStore
                vector_store = VectorStore()
                stats = vector_store.get_stats()
                sizes['chroma_chunk_count'] = stats.get('total_chunks', 0)
            except Exception as e:
                log.error(f"Error getting chunk count: {e}")
                sizes['chroma_chunk_count'] = 0
        else:
            sizes['chroma_size_mb'] = 0
            sizes['chroma_chunk_count'] = 0

        sizes['total_size_mb'] = sizes['sqlite_size_mb'] + sizes['chroma_size_mb']

        return sizes

    def create_backup(self) -> Optional[Path]:
        """
        Create backup of databases.

        Returns:
            Path to backup file or None if failed
        """
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        backup_file = self.backup_dir / f"backup_{timestamp}.tar.gz"

        try:
            log.info(f"Creating backup: {backup_file}")

            with tarfile.open(backup_file, "w:gz") as tar:
                # Backup SQLite database
                if self.sqlite_db_path.exists():
                    tar.add(
                        self.sqlite_db_path,
                        arcname=self.sqlite_db_path.name
                    )
                    log.debug(f"Added SQLite DB to backup")

                # Backup ChromaDB directory
                if self.chroma_db_path.exists():
                    tar.add(
                        self.chroma_db_path,
                        arcname=self.chroma_db_path.name
                    )
                    log.debug(f"Added ChromaDB to backup")

                # Add metadata
                metadata = {
                    'timestamp': timestamp,
                    'sqlite_path': str(self.sqlite_db_path),
                    'chroma_path': str(self.chroma_db_path),
                    'sizes': self.get_database_sizes()
                }

                import json
                metadata_file = self.backup_dir / f"metadata_{timestamp}.json"
                with open(metadata_file, 'w') as f:
                    json.dump(metadata, f, indent=2)

                tar.add(metadata_file, arcname=metadata_file.name)
                metadata_file.unlink()  # Remove temp metadata file

            log.info(f"Backup created successfully: {backup_file}")
            self._cleanup_old_backups(keep_count=3)

            return backup_file

        except Exception as e:
            log.error(f"Error creating backup: {e}")
            return None

    def _cleanup_old_backups(self, keep_count: int = 3):
        """
        Keep only the N most recent backups.

        Args:
            keep_count: Number of backups to keep
        """
        try:
            backups = sorted(
                self.backup_dir.glob("backup_*.tar.gz"),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )

            # Delete old backups
            for backup in backups[keep_count:]:
                backup.unlink()
                log.debug(f"Deleted old backup: {backup.name}")

                # Delete corresponding metadata
                metadata_file = backup.parent / backup.name.replace('backup_', 'metadata_').replace('.tar.gz', '.json')
                if metadata_file.exists():
                    metadata_file.unlink()

        except Exception as e:
            log.error(f"Error cleaning up old backups: {e}")

    def reset_sqlite(self) -> bool:
        """
        Reset SQLite database (delete all URLs).

        Returns:
            True if successful
        """
        try:
            # Check if database file exists
            if not self.sqlite_db_path.exists():
                log.warning(f"SQLite database not found: {self.sqlite_db_path}")
                log.info("Database doesn't exist - nothing to reset")
                return True  # Not an error, just nothing to do

            conn = sqlite3.connect(self.sqlite_db_path)
            cursor = conn.cursor()

            # Check if tables exist before deleting
            try:
                cursor.execute("DELETE FROM discovered_urls")
                deleted_count = cursor.rowcount
                log.info(f"Deleted {deleted_count} URLs from discovered_urls")
            except sqlite3.OperationalError as e:
                if "no such table" in str(e).lower():
                    log.warning("Table 'discovered_urls' does not exist")
                else:
                    raise

            try:
                cursor.execute("DELETE FROM api_usage_log")
                log.info(f"Deleted {cursor.rowcount} entries from api_usage_log")
            except sqlite3.OperationalError as e:
                if "no such table" in str(e).lower():
                    log.warning("Table 'api_usage_log' does not exist")
                else:
                    raise

            # Vacuum to reclaim space
            cursor.execute("VACUUM")

            conn.commit()
            conn.close()

            log.info("SQLite reset completed successfully")
            return True

        except Exception as e:
            log.error(f"Error resetting SQLite: {e}")
            return False

    def reset_chromadb(self) -> bool:
        """
        Reset ChromaDB (delete all chunks).

        Returns:
            True if successful
        """
        try:
            from database import VectorStore

            vector_store = VectorStore()
            vector_store.reset()

            log.info("ChromaDB reset successfully")
            return True

        except Exception as e:
            log.error(f"Error resetting ChromaDB: {e}")
            return False

    def reset_all(self, create_backup: bool = True) -> Dict[str, Any]:
        """
        Reset all databases with optional backup.

        Args:
            create_backup: Whether to create backup before reset

        Returns:
            Dictionary with reset results
        """
        result = {
            'success': False,
            'backup_created': False,
            'backup_path': None,
            'sqlite_reset': False,
            'chromadb_reset': False,
            'error': None
        }

        try:
            # Get sizes before reset
            sizes_before = self.get_database_sizes()
            log.info(f"Databases before reset: {sizes_before}")

            # Create backup
            if create_backup:
                backup_path = self.create_backup()
                if backup_path:
                    result['backup_created'] = True
                    result['backup_path'] = str(backup_path)
                    log.info(f"Backup created: {backup_path}")
                else:
                    result['error'] = "Backup creation failed"
                    log.error("Backup failed - aborting reset")
                    return result

            # Reset SQLite
            sqlite_success = self.reset_sqlite()
            result['sqlite_reset'] = sqlite_success

            if not sqlite_success:
                result['error'] = "SQLite reset failed"
                log.error("SQLite reset failed")
                # Try to restore from backup
                if result['backup_created']:
                    log.warning("Attempting to restore from backup...")
                    self.restore_from_backup(Path(result['backup_path']))
                return result

            # Reset ChromaDB
            chroma_success = self.reset_chromadb()
            result['chromadb_reset'] = chroma_success

            if not chroma_success:
                result['error'] = "ChromaDB reset failed"
                log.error("ChromaDB reset failed")
                # Try to restore from backup
                if result['backup_created']:
                    log.warning("Attempting to restore from backup...")
                    self.restore_from_backup(Path(result['backup_path']))
                return result

            # Success
            result['success'] = True
            sizes_after = self.get_database_sizes()
            log.info(f"Reset successful! Databases after reset: {sizes_after}")

            return result

        except Exception as e:
            result['error'] = str(e)
            log.error(f"Error during reset: {e}")
            return result

    def restore_from_backup(self, backup_path: Path) -> bool:
        """
        Restore databases from backup.

        Args:
            backup_path: Path to backup tar.gz file

        Returns:
            True if successful
        """
        try:
            log.info(f"Restoring from backup: {backup_path}")

            if not backup_path.exists():
                log.error(f"Backup file not found: {backup_path}")
                return False

            # Extract backup
            with tarfile.open(backup_path, "r:gz") as tar:
                # Extract to temporary directory
                temp_dir = self.backup_dir / "temp_restore"
                temp_dir.mkdir(exist_ok=True)

                tar.extractall(temp_dir)

                # Restore SQLite
                sqlite_backup = temp_dir / self.sqlite_db_path.name
                if sqlite_backup.exists():
                    shutil.copy(sqlite_backup, self.sqlite_db_path)
                    log.debug("SQLite restored")

                # Restore ChromaDB
                chroma_backup = temp_dir / self.chroma_db_path.name
                if chroma_backup.exists():
                    if self.chroma_db_path.exists():
                        shutil.rmtree(self.chroma_db_path)
                    shutil.copytree(chroma_backup, self.chroma_db_path)
                    log.debug("ChromaDB restored")

                # Cleanup temp directory
                shutil.rmtree(temp_dir)

            log.info("Restore completed successfully")
            return True

        except Exception as e:
            log.error(f"Error restoring from backup: {e}")
            return False

    def list_backups(self) -> list:
        """
        List available backups.

        Returns:
            List of backup information dictionaries
        """
        backups = []

        try:
            for backup_file in sorted(
                self.backup_dir.glob("backup_*.tar.gz"),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            ):
                backup_info = {
                    'filename': backup_file.name,
                    'path': str(backup_file),
                    'size_mb': backup_file.stat().st_size / (1024 * 1024),
                    'created': datetime.fromtimestamp(backup_file.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                }
                backups.append(backup_info)

        except Exception as e:
            log.error(f"Error listing backups: {e}")

        return backups

    def check_disk_space(self, required_mb: float = 100) -> bool:
        """
        Check if enough disk space is available.

        Args:
            required_mb: Required space in MB

        Returns:
            True if enough space available
        """
        try:
            stat = shutil.disk_usage(self.backup_dir.parent)
            free_mb = stat.free / (1024 * 1024)

            if free_mb < required_mb:
                log.warning(f"Low disk space: {free_mb:.1f} MB available, {required_mb:.1f} MB required")
                return False

            return True

        except Exception as e:
            log.error(f"Error checking disk space: {e}")
            return False

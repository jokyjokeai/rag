"""
Central configuration management using Pydantic Settings.
"""
from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Keys
    brave_api_key: str = ""
    youtube_api_key: str = ""
    github_token: str = ""

    # YouTube Configuration
    youtube_channel_max_videos_default: int = 50  # Default crawl limit per channel
    youtube_channel_max_videos_full: int = 500  # Full crawl limit (when user chooses "All")
    youtube_prioritize_channels: bool = True  # Prioritize channels over individual videos
    youtube_search_masterclass: bool = True  # Include masterclass/long videos in searches

    # Ollama Configuration
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "mistral:7b"  # For query analysis - better quality
    ollama_metadata_model: str = "mistral:7b"  # For metadata enrichment - better quality

    # Query Analysis Configuration
    enable_competitor_queries: bool = True  # Include competitor technologies in web search

    # Database Paths
    chroma_db_path: str = "./data/chroma_db"
    sqlite_db_path: str = "./data/discovered_urls.db"

    # Processing Configuration
    batch_size: int = 10
    concurrent_workers: int = 3
    max_retries: int = 3
    delay_between_batches: int = 30  # seconds

    # Chunking Configuration
    max_chunk_size: int = 512  # tokens
    min_chunk_size: int = 100  # tokens
    chunk_overlap: int = 50    # tokens

    # Embeddings Configuration
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_device: str = "cpu"  # or 'cuda' for GPU

    # Refresh Scheduler Configuration
    enable_auto_refresh: bool = True
    refresh_schedule: str = "0 3 * * 1"  # Cron format: Monday 3AM

    # Logging Configuration
    log_level: str = "INFO"
    log_file: str = "./data/logs/rag_system.log"

    # Rate Limiting
    rate_limit_per_domain: float = 1.0  # requests per second

    # Brave Search API Rate Limit
    brave_daily_quota: int = 2000  # Free tier daily limit
    track_brave_usage: bool = True  # Track API usage for quota monitoring

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()


# Helper function to get project root
def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent


def get_absolute_path(relative_path: str) -> Path:
    """Convert relative path to absolute path from project root."""
    return get_project_root() / relative_path

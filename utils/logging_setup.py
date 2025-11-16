"""
Logging configuration using loguru.
"""
import sys
from pathlib import Path
from loguru import logger
from config import settings


def setup_logging():
    """Configure loguru logger with file and console output."""

    # Remove default handler
    logger.remove()

    # Add console handler with colors
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | <level>{message}</level>",
        level=settings.log_level,
        colorize=True
    )

    # Ensure log directory exists
    log_file_path = Path(settings.log_file)
    log_file_path.parent.mkdir(parents=True, exist_ok=True)

    # Add file handler with rotation
    logger.add(
        settings.log_file,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        level=settings.log_level,
        rotation="100 MB",
        retention="30 days",
        compression="zip",
        enqueue=True  # Thread-safe
    )

    logger.info("Logging initialized")
    return logger


# Initialize logger on import
log = setup_logging()

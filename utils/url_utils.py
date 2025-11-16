"""
Utilities for URL handling, normalization, and detection.
"""
import hashlib
import re
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from typing import List, Tuple


def extract_urls(text: str) -> List[str]:
    """
    Extract all URLs from a given text.

    Args:
        text: Input text that may contain URLs

    Returns:
        List of extracted URLs
    """
    # Regex pattern for URLs
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    urls = re.findall(url_pattern, text)
    return urls


def normalize_url(url: str) -> str:
    """
    Normalize URL by removing unnecessary parameters and fragments.

    Args:
        url: URL to normalize

    Returns:
        Normalized URL
    """
    parsed = urlparse(url)

    # Remove fragment
    parsed = parsed._replace(fragment='')

    # For YouTube, keep only essential params
    if 'youtube.com' in parsed.netloc or 'youtu.be' in parsed.netloc:
        if '/watch' in parsed.path:
            query_params = parse_qs(parsed.query)
            # Keep only 'v' parameter for video ID
            if 'v' in query_params:
                new_query = urlencode({'v': query_params['v'][0]})
                parsed = parsed._replace(query=new_query)
        else:
            # For channels, remove query params
            parsed = parsed._replace(query='')

    # Remove trailing slash from path
    path = parsed.path.rstrip('/')
    parsed = parsed._replace(path=path)

    # Ensure lowercase scheme and netloc
    parsed = parsed._replace(scheme=parsed.scheme.lower(), netloc=parsed.netloc.lower())

    return urlunparse(parsed)


def compute_url_hash(url: str) -> str:
    """
    Compute MD5 hash of a normalized URL.

    Args:
        url: URL to hash

    Returns:
        MD5 hash as hexadecimal string
    """
    normalized = normalize_url(url)
    return hashlib.md5(normalized.encode('utf-8')).hexdigest()


def detect_url_type(url: str) -> str:
    """
    Detect the type of source from URL.

    Args:
        url: URL to analyze

    Returns:
        Source type: 'github', 'youtube_channel', 'youtube_video', or 'website'
    """
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    path = parsed.path.lower()

    # GitHub detection
    if 'github.com' in domain:
        return 'github'

    # YouTube detection
    elif 'youtube.com' in domain or 'youtu.be' in domain:
        # Channel patterns
        if any(pattern in path for pattern in ['/channel/', '/c/', '/@']):
            return 'youtube_channel'
        # Video patterns
        elif '/watch' in path or 'youtu.be' in domain:
            return 'youtube_video'
        # Shorts
        elif '/shorts/' in path:
            return 'youtube_video'
        # Default to video for other YouTube URLs
        else:
            return 'youtube_video'

    # Default to website
    else:
        return 'website'


def extract_youtube_video_id(url: str) -> str:
    """
    Extract video ID from YouTube URL.

    Args:
        url: YouTube video URL

    Returns:
        Video ID or empty string if not found
    """
    parsed = urlparse(url)

    # youtu.be format
    if 'youtu.be' in parsed.netloc:
        return parsed.path.lstrip('/')

    # youtube.com/watch?v= format
    elif 'youtube.com' in parsed.netloc:
        if '/watch' in parsed.path:
            query_params = parse_qs(parsed.query)
            return query_params.get('v', [''])[0]
        elif '/shorts/' in parsed.path:
            # Extract from path: /shorts/VIDEO_ID
            return parsed.path.split('/shorts/')[-1]

    return ''


def extract_github_repo_info(url: str) -> Tuple[str, str]:
    """
    Extract owner and repo name from GitHub URL.

    Args:
        url: GitHub repository URL

    Returns:
        Tuple of (owner, repo_name)
    """
    parsed = urlparse(url)
    path_parts = [p for p in parsed.path.split('/') if p]

    if len(path_parts) >= 2:
        owner = path_parts[0]
        repo = path_parts[1]
        return owner, repo

    return '', ''


def is_valid_url(url: str) -> bool:
    """
    Check if a string is a valid URL.

    Args:
        url: String to validate

    Returns:
        True if valid URL, False otherwise
    """
    try:
        result = urlparse(url)
        return all([result.scheme in ['http', 'https'], result.netloc])
    except Exception:
        return False

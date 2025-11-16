"""
YouTube scraper for video transcriptions and metadata.
"""
from typing import Dict, Any, Optional
from datetime import datetime
import random
import time
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from config import settings
from utils import log, extract_youtube_video_id
from .base_scraper import BaseScraper
import requests


class YouTubeScraper(BaseScraper):
    """Scraper for YouTube video transcriptions and metadata."""

    def __init__(self):
        """Initialize YouTube scraper."""
        super().__init__()
        self.api_key = settings.youtube_api_key
        if self.api_key:
            self.youtube = build('youtube', 'v3', developerKey=self.api_key)
        else:
            self.youtube = None
            log.warning("YouTube API key not configured - metadata will be limited")

    @staticmethod
    def is_temporary_error(error_message: str) -> bool:
        """
        Determine if an error is temporary (retriable) or permanent.

        Args:
            error_message: The error message string

        Returns:
            True if error is temporary (should retry), False if permanent
        """
        error_lower = error_message.lower()

        # Temporary errors (retriable)
        temporary_indicators = [
            'rate limit',
            'quota',
            'too many requests',
            'blocked',
            'ip',
            'timeout',
            'timed out',
            'connection',
            'network',
            '429',  # Too Many Requests
            '503',  # Service Unavailable
            '502',  # Bad Gateway
            '504',  # Gateway Timeout
            'server error',
            'temporarily unavailable',
            'try again later'
        ]

        # Permanent errors (not retriable)
        permanent_indicators = [
            'video unavailable',
            'private video',
            'deleted',
            'removed',
            '404',  # Not Found
            'no transcript',
            'transcripts disabled',
            'invalid',
            'not found',
            'copyright'
        ]

        # Check for permanent errors first (higher priority)
        if any(indicator in error_lower for indicator in permanent_indicators):
            return False

        # Check for temporary errors
        if any(indicator in error_lower for indicator in temporary_indicators):
            return True

        # Default: treat unknown errors as temporary (safer to retry)
        return True

    def scrape(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Scrape YouTube video transcript and metadata.

        Args:
            url: YouTube video URL

        Returns:
            Dictionary with transcript and metadata
        """
        video_id = extract_youtube_video_id(url)
        if not video_id:
            log.error(f"Could not extract video ID from URL: {url}")
            return self._create_result(
                url=url,
                content="",
                metadata={},
                success=False,
                error="Invalid YouTube URL"
            )

        log.info(f"Scraping YouTube video: {video_id}")

        try:
            # Add random delay to simulate human behavior and avoid rate limiting
            # Varies the delay to appear more natural (80-120% of configured delay)
            base_delay = settings.youtube_delay_between_requests
            random_delay = base_delay * random.uniform(0.8, 1.2)
            time.sleep(random_delay)

            # Get transcript
            transcript_result = self._get_transcript(video_id)

            # Get metadata from API if available
            metadata = self._get_metadata(video_id)

            if transcript_result['success']:
                # Combine transcript and metadata
                full_metadata = {
                    **metadata,
                    'video_id': video_id,
                    'source_type': 'youtube_video',
                    'scraped_at': datetime.now().isoformat(),
                    'has_transcript': True,
                    'transcript_segments': transcript_result.get('segments', [])
                }

                return self._create_result(
                    url=url,
                    content=transcript_result['content'],
                    metadata=full_metadata,
                    success=True
                )
            else:
                # Transcript failed - use description as fallback
                description = metadata.get('description', '')
                full_metadata = {
                    **metadata,
                    'video_id': video_id,
                    'source_type': 'youtube_video',
                    'scraped_at': datetime.now().isoformat(),
                    'has_transcript': False,
                    'fallback': 'description'
                }

                content = f"# {metadata.get('title', 'YouTube Video')}\n\n{description}"

                return self._create_result(
                    url=url,
                    content=content,
                    metadata=full_metadata,
                    success=True  # Still successful, just using fallback
                )

        except Exception as e:
            error_msg = str(e)
            log.error(f"Error scraping YouTube video {video_id}: {error_msg}")

            # Determine if error is temporary
            is_temp = self.is_temporary_error(error_msg)

            return self._create_result(
                url=url,
                content="",
                metadata={},
                success=False,
                error=error_msg,
                is_temporary_error=is_temp
            )

    def _get_transcript(self, video_id: str) -> Dict[str, Any]:
        """
        Get video transcript.

        Args:
            video_id: YouTube video ID

        Returns:
            Dictionary with transcript content and segments
        """
        try:
            # Try to get transcript in different languages
            languages_to_try = ['fr', 'en', 'es', 'de', 'it']

            segments = None
            language_used = None

            for lang in languages_to_try:
                try:
                    segments = YouTubeTranscriptApi().fetch(video_id, languages=[lang])
                    language_used = lang
                    break
                except:
                    continue

            # If no language worked, try without specifying language
            if segments is None:
                segments = YouTubeTranscriptApi().fetch(video_id)
                language_used = 'auto'

            # Combine all segments into full text
            full_text = "\n".join([segment.text for segment in segments])

            # Store segment information for chunking
            segment_info = [
                {
                    'start': self._format_timestamp(segment.start),
                    'duration': segment.duration,
                    'text': segment.text
                }
                for segment in segments
            ]

            log.info(f"Retrieved transcript with {len(segments)} segments (language: {language_used})")

            return {
                'success': True,
                'content': full_text,
                'segments': segment_info,
                'language': language_used
            }

        except (TranscriptsDisabled, NoTranscriptFound) as e:
            log.warning(f"No transcript available for video {video_id}: {e}")
            return {
                'success': False,
                'content': "",
                'error': str(e)
            }

        except Exception as e:
            log.error(f"Error getting transcript for {video_id}: {e}")
            return {
                'success': False,
                'content': "",
                'error': str(e)
            }

    def _get_metadata(self, video_id: str) -> Dict[str, Any]:
        """
        Get video metadata from YouTube API.

        Args:
            video_id: YouTube video ID

        Returns:
            Dictionary with video metadata
        """
        if not self.youtube:
            return {}

        try:
            request = self.youtube.videos().list(
                part='snippet,contentDetails,statistics',
                id=video_id
            )
            response = request.execute()

            if not response.get('items'):
                log.warning(f"No metadata found for video {video_id}")
                return {}

            item = response['items'][0]
            snippet = item.get('snippet', {})
            statistics = item.get('statistics', {})
            content_details = item.get('contentDetails', {})

            metadata = {
                'title': snippet.get('title', ''),
                'description': snippet.get('description', ''),
                'channel': snippet.get('channelTitle', ''),
                'channel_id': snippet.get('channelId', ''),
                'published_at': snippet.get('publishedAt', ''),
                'duration': content_details.get('duration', ''),
                'view_count': int(statistics.get('viewCount', 0)),
                'like_count': int(statistics.get('likeCount', 0)),
                'comment_count': int(statistics.get('commentCount', 0)),
                'tags': snippet.get('tags', [])
            }

            log.info(f"Retrieved metadata for: {metadata['title']}")
            return metadata

        except HttpError as e:
            log.error(f"YouTube API error for {video_id}: {e}")
            return {}

        except Exception as e:
            log.error(f"Error getting metadata for {video_id}: {e}")
            return {}

    @staticmethod
    def _format_timestamp(seconds: float) -> str:
        """
        Format seconds to HH:MM:SS timestamp.

        Args:
            seconds: Time in seconds

        Returns:
            Formatted timestamp string
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"

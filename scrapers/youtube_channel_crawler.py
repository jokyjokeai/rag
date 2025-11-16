"""
YouTube channel crawler to discover video URLs.
"""
from typing import List, Optional, Dict, Any
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from config import settings
from utils import log
import re


class YouTubeChannelCrawler:
    """Crawler for discovering videos from YouTube channels."""

    def __init__(self):
        """Initialize YouTube channel crawler."""
        self.api_key = settings.youtube_api_key
        if self.api_key:
            self.youtube = build('youtube', 'v3', developerKey=self.api_key)
        else:
            self.youtube = None
            log.warning("YouTube API key not configured - channel crawling disabled")

    def crawl_channel(
        self,
        channel_url: str,
        max_videos: int = 50,
        crawl_all: bool = False
    ) -> Dict[str, Any]:
        """
        Crawl a YouTube channel and discover video URLs.

        Args:
            channel_url: YouTube channel URL
            max_videos: Maximum number of videos to retrieve (ignored if crawl_all=True)
            crawl_all: If True, crawl up to 500 videos (safety limit)

        Returns:
            Dictionary with discovered video URLs and metadata
        """
        # Override max_videos if crawl_all is requested
        if crawl_all:
            from config import settings
            max_videos = settings.youtube_channel_max_videos_full
            log.info(f"Crawl all requested: will fetch up to {max_videos} videos")
        if not self.youtube:
            log.error("Cannot crawl channel without YouTube API key")
            return {
                'success': False,
                'error': 'YouTube API key not configured',
                'video_urls': []
            }

        # Extract channel ID from URL
        channel_id = self._extract_channel_id(channel_url)

        if not channel_id:
            log.error(f"Could not extract channel ID from: {channel_url}")
            return {
                'success': False,
                'error': 'Invalid channel URL',
                'video_urls': []
            }

        log.info(f"Crawling YouTube channel: {channel_id}")

        try:
            # Get channel info first
            channel_info = self._get_channel_info(channel_id)

            if not channel_info:
                return {
                    'success': False,
                    'error': 'Channel not found',
                    'video_urls': []
                }

            # Get uploads playlist ID
            uploads_playlist_id = channel_info.get('uploads_playlist_id')

            if not uploads_playlist_id:
                log.error("Could not find uploads playlist")
                return {
                    'success': False,
                    'error': 'Uploads playlist not found',
                    'video_urls': []
                }

            # Get video IDs from uploads playlist
            video_ids = self._get_playlist_videos(uploads_playlist_id, max_videos)

            # Convert to full URLs
            video_urls = [f"https://www.youtube.com/watch?v={vid}" for vid in video_ids]

            log.info(f"Discovered {len(video_urls)} videos from channel {channel_info.get('title', 'Unknown')}")

            return {
                'success': True,
                'video_urls': video_urls,
                'channel_info': channel_info,
                'total_videos': len(video_urls)
            }

        except HttpError as e:
            log.error(f"YouTube API error: {e}")
            return {
                'success': False,
                'error': f'API error: {str(e)}',
                'video_urls': []
            }
        except Exception as e:
            log.error(f"Error crawling channel: {e}")
            return {
                'success': False,
                'error': str(e),
                'video_urls': []
            }

    def _extract_channel_id(self, channel_url: str) -> Optional[str]:
        """
        Extract channel ID from various YouTube channel URL formats.

        Args:
            channel_url: YouTube channel URL

        Returns:
            Channel ID or None
        """
        # Pattern 1: /channel/CHANNEL_ID
        match = re.search(r'/channel/([^/?]+)', channel_url)
        if match:
            return match.group(1)

        # Pattern 2: /c/CHANNEL_NAME or /@CHANNEL_HANDLE
        # Need to resolve via API
        match = re.search(r'/(?:c|@)([^/?]+)', channel_url)
        if match:
            channel_identifier = match.group(1)
            return self._resolve_channel_handle(channel_identifier)

        # Pattern 3: /user/USERNAME (legacy)
        match = re.search(r'/user/([^/?]+)', channel_url)
        if match:
            username = match.group(1)
            return self._resolve_username(username)

        return None

    def _resolve_channel_handle(self, handle: str) -> Optional[str]:
        """
        Resolve @handle or custom URL to channel ID.

        Args:
            handle: Channel handle or custom name

        Returns:
            Channel ID or None
        """
        if not self.youtube:
            return None

        try:
            # Search for channel
            request = self.youtube.search().list(
                part='snippet',
                q=handle,
                type='channel',
                maxResults=1
            )
            response = request.execute()

            if response.get('items'):
                return response['items'][0]['snippet']['channelId']

        except Exception as e:
            log.error(f"Error resolving channel handle {handle}: {e}")

        return None

    def _resolve_username(self, username: str) -> Optional[str]:
        """
        Resolve legacy username to channel ID.

        Args:
            username: YouTube username

        Returns:
            Channel ID or None
        """
        if not self.youtube:
            return None

        try:
            request = self.youtube.channels().list(
                part='id',
                forUsername=username
            )
            response = request.execute()

            if response.get('items'):
                return response['items'][0]['id']

        except Exception as e:
            log.error(f"Error resolving username {username}: {e}")

        return None

    def _get_channel_info(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """
        Get channel information.

        Args:
            channel_id: YouTube channel ID

        Returns:
            Channel metadata
        """
        try:
            request = self.youtube.channels().list(
                part='snippet,contentDetails,statistics',
                id=channel_id
            )
            response = request.execute()

            if not response.get('items'):
                return None

            item = response['items'][0]
            snippet = item.get('snippet', {})
            content_details = item.get('contentDetails', {})
            statistics = item.get('statistics', {})

            return {
                'channel_id': channel_id,
                'title': snippet.get('title', ''),
                'description': snippet.get('description', ''),
                'uploads_playlist_id': content_details.get('relatedPlaylists', {}).get('uploads'),
                'subscriber_count': int(statistics.get('subscriberCount', 0)),
                'video_count': int(statistics.get('videoCount', 0)),
                'view_count': int(statistics.get('viewCount', 0))
            }

        except Exception as e:
            log.error(f"Error getting channel info for {channel_id}: {e}")
            return None

    def _get_playlist_videos(self, playlist_id: str, max_results: int = 50) -> List[str]:
        """
        Get all video IDs from a playlist.

        Args:
            playlist_id: YouTube playlist ID
            max_results: Maximum videos to retrieve

        Returns:
            List of video IDs
        """
        video_ids = []
        next_page_token = None

        try:
            while len(video_ids) < max_results:
                request = self.youtube.playlistItems().list(
                    part='contentDetails',
                    playlistId=playlist_id,
                    maxResults=min(50, max_results - len(video_ids)),
                    pageToken=next_page_token
                )
                response = request.execute()

                for item in response.get('items', []):
                    video_id = item['contentDetails']['videoId']
                    video_ids.append(video_id)

                next_page_token = response.get('nextPageToken')
                if not next_page_token:
                    break

        except Exception as e:
            log.error(f"Error getting playlist videos: {e}")

        return video_ids

    def _get_channel_url_from_video(self, video_url: str) -> Optional[str]:
        """
        Extract channel URL from a video URL using YouTube API.

        Args:
            video_url: YouTube video URL

        Returns:
            Channel URL (@handle format) or None
        """
        if not self.youtube:
            return None

        # Extract video ID
        video_id_match = re.search(r'(?:v=|/)([0-9A-Za-z_-]{11})(?:[&?]|$)', video_url)
        if not video_id_match:
            return None

        video_id = video_id_match.group(1)

        try:
            # Get video details to find channel ID
            request = self.youtube.videos().list(
                part='snippet',
                id=video_id
            )
            response = request.execute()

            if not response.get('items'):
                return None

            channel_id = response['items'][0]['snippet']['channelId']
            channel_title = response['items'][0]['snippet']['channelTitle']

            # Try to get custom URL/handle
            channel_request = self.youtube.channels().list(
                part='snippet',
                id=channel_id
            )
            channel_response = channel_request.execute()

            if channel_response.get('items'):
                custom_url = channel_response['items'][0]['snippet'].get('customUrl')
                if custom_url:
                    # Return @handle format
                    return f"https://youtube.com/@{custom_url}"

            # Fallback to channel ID format
            return f"https://youtube.com/channel/{channel_id}"

        except Exception as e:
            log.debug(f"Could not extract channel from video {video_id}: {e}")
            return None

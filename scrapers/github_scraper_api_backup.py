"""
GitHub scraper for repository code and documentation.
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from github import Github, GithubException, RateLimitExceededException
from config import settings
from utils import log, extract_github_repo_info
from .base_scraper import BaseScraper


class GitHubScraper(BaseScraper):
    """Scraper for GitHub repository code and documentation."""

    # File extensions to scrape
    SUPPORTED_EXTENSIONS = {
        '.py', '.md', '.rst', '.txt', '.yaml', '.yml',
        '.json', '.toml', '.cfg', '.ini', '.sh'
    }

    # Directories to ignore
    IGNORED_DIRS = {
        '.git', '__pycache__', 'node_modules', '.venv', 'venv',
        'dist', 'build', '.pytest_cache', '.tox', 'htmlcov'
    }

    def __init__(self):
        """Initialize GitHub scraper."""
        super().__init__()
        self.token = settings.github_token
        if self.token:
            self.github = Github(self.token)
        else:
            self.github = Github()  # Anonymous access (lower rate limit)
            log.warning("GitHub token not configured - using anonymous access with lower rate limits")

    def scrape(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Scrape GitHub repository content.

        Args:
            url: GitHub repository URL

        Returns:
            Dictionary with repository content and metadata
        """
        owner, repo_name = extract_github_repo_info(url)
        if not owner or not repo_name:
            log.error(f"Could not extract repo info from URL: {url}")
            return self._create_result(
                url=url,
                content="",
                metadata={},
                success=False,
                error="Invalid GitHub URL"
            )

        log.info(f"Scraping GitHub repo: {owner}/{repo_name}")

        try:
            # Get repository
            repo = self.github.get_repo(f"{owner}/{repo_name}")

            # Get repository metadata
            metadata = self._get_repo_metadata(repo)

            # Get README content (priority)
            readme_content = self._get_readme(repo)

            # Get code and documentation files
            files_content = self._get_files(repo)

            # Combine all content
            all_content = []

            if readme_content:
                all_content.append(f"# README\n\n{readme_content}\n\n")

            for file_info in files_content:
                all_content.append(
                    f"# File: {file_info['path']}\n\n{file_info['content']}\n\n"
                )

            combined_content = "\n".join(all_content)

            full_metadata = {
                **metadata,
                'source_type': 'github',
                'scraped_at': datetime.now().isoformat(),
                'files_scraped': len(files_content),
                'has_readme': bool(readme_content)
            }

            log.info(f"Scraped {len(files_content)} files from {owner}/{repo_name}")

            return self._create_result(
                url=url,
                content=combined_content,
                metadata=full_metadata,
                success=True
            )

        except RateLimitExceededException:
            log.error("GitHub rate limit exceeded")
            return self._create_result(
                url=url,
                content="",
                metadata={},
                success=False,
                error="Rate limit exceeded"
            )

        except GithubException as e:
            log.error(f"GitHub API error for {owner}/{repo_name}: {e}")
            return self._create_result(
                url=url,
                content="",
                metadata={},
                success=False,
                error=str(e)
            )

        except Exception as e:
            log.error(f"Error scraping {owner}/{repo_name}: {e}")
            return self._create_result(
                url=url,
                content="",
                metadata={},
                success=False,
                error=str(e)
            )

    def _get_repo_metadata(self, repo) -> Dict[str, Any]:
        """
        Get repository metadata.

        Args:
            repo: PyGithub repository object

        Returns:
            Dictionary with repository metadata
        """
        return {
            'repo_name': repo.full_name,
            'description': repo.description or '',
            'language': repo.language or 'Unknown',
            'stars': repo.stargazers_count,
            'forks': repo.forks_count,
            'open_issues': repo.open_issues_count,
            'created_at': repo.created_at.isoformat() if repo.created_at else '',
            'updated_at': repo.updated_at.isoformat() if repo.updated_at else '',
            'topics': repo.get_topics(),
            'license': repo.license.name if repo.license else None,
            'default_branch': repo.default_branch
        }

    def _get_readme(self, repo) -> str:
        """
        Get README content.

        Args:
            repo: PyGithub repository object

        Returns:
            README content as string
        """
        try:
            readme = repo.get_readme()
            content = readme.decoded_content.decode('utf-8')
            log.info(f"Retrieved README ({len(content)} chars)")
            return content
        except Exception as e:
            log.warning(f"Could not get README: {e}")
            return ""

    def _get_files(self, repo, max_files: int = 50) -> List[Dict[str, Any]]:
        """
        Get code and documentation files from repository.

        Args:
            repo: PyGithub repository object
            max_files: Maximum number of files to retrieve

        Returns:
            List of dictionaries with file path and content
        """
        files = []
        count = 0

        try:
            contents = repo.get_contents("")

            while contents and count < max_files:
                file_content = contents.pop(0)

                # Skip directories in ignore list
                if file_content.type == "dir":
                    if file_content.name not in self.IGNORED_DIRS:
                        try:
                            contents.extend(repo.get_contents(file_content.path))
                        except Exception as e:
                            log.warning(f"Could not access directory {file_content.path}: {e}")
                    continue

                # Check if file extension is supported
                if not any(file_content.name.endswith(ext) for ext in self.SUPPORTED_EXTENSIONS):
                    continue

                # Get file content
                try:
                    content = file_content.decoded_content.decode('utf-8')

                    # Skip very large files
                    if len(content) > 100000:  # 100KB limit
                        log.debug(f"Skipping large file: {file_content.path}")
                        continue

                    files.append({
                        'path': file_content.path,
                        'content': content,
                        'size': file_content.size,
                        'sha': file_content.sha
                    })

                    count += 1
                    log.debug(f"Retrieved file: {file_content.path} ({count}/{max_files})")

                except Exception as e:
                    log.warning(f"Could not decode file {file_content.path}: {e}")
                    continue

        except Exception as e:
            log.error(f"Error listing repository files: {e}")

        return files

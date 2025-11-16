"""
GitHub scraper using git clone (no API required).
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
import tempfile
import shutil
import subprocess
from utils import log, extract_github_repo_info
from .base_scraper import BaseScraper


class GitHubScraper(BaseScraper):
    """Scraper for GitHub repository using git clone."""

    # File extensions to scrape
    SUPPORTED_EXTENSIONS = {
        '.py', '.md', '.rst', '.txt', '.yaml', '.yml',
        '.json', '.toml', '.cfg', '.ini', '.sh', '.js', '.ts'
    }

    # Directories to ignore
    IGNORED_DIRS = {
        '.git', '__pycache__', 'node_modules', '.venv', 'venv',
        'dist', 'build', '.pytest_cache', '.tox', 'htmlcov',
        'coverage', '.mypy_cache', '.eggs', '*.egg-info'
    }

    # Directories to include in sparse checkout
    SPARSE_CHECKOUT_DIRS = {
        'docs', 'doc', 'documentation',
        'examples', 'example', 'samples',
        'src', 'lib', 'source',
        'scripts', 'bin',
        'notebooks',  # Jupyter notebooks
        'tests', 'test',  # Test files often contain good examples
    }

    # Timeout configuration (seconds)
    SPARSE_CLONE_TIMEOUT = 60  # 1 minute for sparse checkout
    SHALLOW_CLONE_TIMEOUT = 120  # 2 minutes for fallback shallow clone
    TOTAL_TIMEOUT = 180  # 3 minutes overall cap

    def __init__(self):
        """Initialize GitHub scraper."""
        super().__init__()
        log.info("GitHub scraper initialized (using git clone)")

    def scrape(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Scrape GitHub repository by cloning it.

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

        log.info(f"Cloning GitHub repo: {owner}/{repo_name}")

        # Create temporary directory for cloning
        temp_dir = tempfile.mkdtemp(prefix=f"github_{repo_name}_")

        try:
            # Clone repository
            clone_url = f"https://github.com/{owner}/{repo_name}.git"
            if not self._clone_repo(clone_url, temp_dir):
                return self._create_result(
                    url=url,
                    content="",
                    metadata={},
                    success=False,
                    error="Failed to clone repository"
                )

            # Get repository metadata
            metadata = self._get_repo_metadata(Path(temp_dir), owner, repo_name)

            # Get README content
            readme_content = self._get_readme(Path(temp_dir))

            # Get code and documentation files
            files_content = self._get_files(Path(temp_dir))

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

        except Exception as e:
            log.error(f"Error scraping {owner}/{repo_name}: {e}")
            return self._create_result(
                url=url,
                content="",
                metadata={},
                success=False,
                error=str(e)
            )

        finally:
            # Clean up temporary directory
            try:
                shutil.rmtree(temp_dir)
                log.debug(f"Cleaned up temp directory: {temp_dir}")
            except Exception as e:
                log.warning(f"Could not clean up temp directory {temp_dir}: {e}")

    def _get_sparse_checkout_patterns(self) -> list:
        """
        Generate sparse checkout patterns for git.

        Returns:
            List of patterns for .git/info/sparse-checkout
        """
        patterns = [
            '/*',  # Include root level files (README, LICENSE, etc.)
            '!.*',  # Exclude hidden directories (except those explicitly included)
        ]

        # Include specific directories
        for directory in self.SPARSE_CHECKOUT_DIRS:
            patterns.append(f'/{directory}/')
            patterns.append(f'/{directory}/**')

        # Exclude ignored directories explicitly
        for ignored in self.IGNORED_DIRS:
            if not ignored.startswith('.'):
                patterns.append(f'!/{ignored}/')

        return patterns

    def _setup_sparse_checkout(self, repo_path: Path) -> bool:
        """
        Configure sparse checkout for a git repository.

        Args:
            repo_path: Path to cloned repository

        Returns:
            True if successful, False otherwise
        """
        try:
            # Enable sparse checkout
            result = subprocess.run(
                ['git', 'config', 'core.sparseCheckout', 'true'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode != 0:
                log.warning(f"Failed to enable sparse checkout: {result.stderr}")
                return False

            # Create sparse-checkout file
            sparse_checkout_file = repo_path / '.git' / 'info' / 'sparse-checkout'
            sparse_checkout_file.parent.mkdir(parents=True, exist_ok=True)

            patterns = self._get_sparse_checkout_patterns()
            sparse_checkout_file.write_text('\n'.join(patterns))

            log.debug(f"Created sparse-checkout with {len(patterns)} patterns")
            return True

        except Exception as e:
            log.warning(f"Error setting up sparse checkout: {e}")
            return False

    def _try_sparse_checkout(self, clone_url: str, target_dir: str, timeout: int = None) -> bool:
        """
        Attempt to clone repository using sparse checkout.

        Args:
            clone_url: Git clone URL
            target_dir: Target directory
            timeout: Timeout in seconds (default: SPARSE_CLONE_TIMEOUT)

        Returns:
            True if successful, False otherwise
        """
        if timeout is None:
            timeout = self.SPARSE_CLONE_TIMEOUT

        try:
            import time
            start_time = time.time()

            # Step 1: Clone without checkout
            log.debug(f"Attempting sparse checkout for {clone_url}")
            result = subprocess.run(
                ['git', 'clone', '--no-checkout', '--depth', '1', clone_url, target_dir],
                capture_output=True,
                text=True,
                timeout=timeout
            )

            if result.returncode != 0:
                log.debug(f"Initial clone failed: {result.stderr}")
                return False

            # Step 2: Setup sparse checkout
            repo_path = Path(target_dir)
            if not self._setup_sparse_checkout(repo_path):
                log.debug("Sparse checkout setup failed")
                return False

            # Step 3: Checkout with sparse patterns
            result = subprocess.run(
                ['git', 'checkout'],
                cwd=target_dir,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            if result.returncode != 0:
                log.debug(f"Sparse checkout failed: {result.stderr}")
                return False

            elapsed = time.time() - start_time
            log.info(f"Successfully sparse cloned repository in {elapsed:.1f}s")
            return True

        except subprocess.TimeoutExpired:
            log.debug(f"Sparse checkout timed out (>{timeout}s)")
            return False
        except Exception as e:
            log.debug(f"Sparse checkout failed with error: {e}")
            return False

    def _clone_repo(self, clone_url: str, target_dir: str, use_sparse: bool = True) -> bool:
        """
        Clone a git repository with optional sparse checkout optimization.

        Strategy:
        1. Try sparse checkout first (fast for large repos)
        2. Fall back to shallow clone if sparse fails

        Args:
            clone_url: Git clone URL
            target_dir: Target directory
            use_sparse: Whether to attempt sparse checkout (default: True)

        Returns:
            True if successful, False otherwise
        """
        import time
        start_time = time.time()

        # Strategy 1: Try sparse checkout first
        if use_sparse:
            log.debug("Attempting sparse checkout...")
            if self._try_sparse_checkout(clone_url, target_dir, timeout=self.SPARSE_CLONE_TIMEOUT):
                elapsed = time.time() - start_time
                log.info(f"Sparse checkout successful in {elapsed:.1f}s")
                return True
            else:
                log.debug("Sparse checkout failed, falling back to shallow clone")
                # Clean up failed sparse checkout attempt
                try:
                    if Path(target_dir).exists():
                        shutil.rmtree(target_dir)
                except Exception as e:
                    log.debug(f"Could not clean up failed sparse checkout: {e}")

        # Strategy 2: Fallback to shallow clone
        try:
            log.debug(f"Attempting shallow clone (timeout: {self.SHALLOW_CLONE_TIMEOUT}s)...")
            result = subprocess.run(
                ['git', 'clone', '--depth', '1', clone_url, target_dir],
                capture_output=True,
                text=True,
                timeout=self.SHALLOW_CLONE_TIMEOUT
            )

            if result.returncode == 0:
                elapsed = time.time() - start_time
                log.info(f"Successfully shallow cloned repository in {elapsed:.1f}s")
                return True
            else:
                log.error(f"Git clone failed: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            log.error(f"Git clone timed out (>{self.SHALLOW_CLONE_TIMEOUT}s)")
            return False

        except FileNotFoundError:
            log.error("Git command not found. Please install git.")
            return False

        except Exception as e:
            log.error(f"Error cloning repository: {e}")
            return False

    def _get_repo_metadata(self, repo_path: Path, owner: str, repo_name: str) -> Dict[str, Any]:
        """
        Get repository metadata from cloned repo.

        Args:
            repo_path: Path to cloned repository
            owner: Repository owner
            repo_name: Repository name

        Returns:
            Dictionary with repository metadata
        """
        metadata = {
            'repo_name': f"{owner}/{repo_name}",
            'owner': owner,
            'name': repo_name
        }

        # Get commit hash for change detection
        try:
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                capture_output=True,
                text=True,
                cwd=repo_path,
                timeout=10
            )
            if result.returncode == 0:
                metadata['commit_hash'] = result.stdout.strip()
                log.debug(f"Captured commit hash: {metadata['commit_hash'][:8]}")
        except Exception as e:
            log.warning(f"Could not get commit hash: {e}")
            metadata['commit_hash'] = None

        # Try to get language from files
        languages = set()
        for ext in ['.py', '.js', '.ts', '.java', '.go', '.rs']:
            if list(repo_path.rglob(f"*{ext}")):
                lang_map = {
                    '.py': 'Python',
                    '.js': 'JavaScript',
                    '.ts': 'TypeScript',
                    '.java': 'Java',
                    '.go': 'Go',
                    '.rs': 'Rust'
                }
                languages.add(lang_map.get(ext, 'Unknown'))

        metadata['language'] = ', '.join(languages) if languages else 'Unknown'

        # Get description from README if available
        readme_path = self._find_readme(repo_path)
        if readme_path:
            try:
                with open(readme_path, 'r', encoding='utf-8') as f:
                    first_lines = [f.readline().strip() for _ in range(5)]
                    # Try to extract description from first non-title lines
                    for line in first_lines[1:]:
                        if line and not line.startswith('#'):
                            metadata['description'] = line[:200]
                            break
            except:
                pass

        return metadata

    def _find_readme(self, repo_path: Path) -> Optional[Path]:
        """
        Find README file in repository.

        Args:
            repo_path: Path to repository

        Returns:
            Path to README or None
        """
        readme_patterns = ['README.md', 'README.rst', 'README.txt', 'README', 'readme.md']

        for pattern in readme_patterns:
            readme_path = repo_path / pattern
            if readme_path.exists():
                return readme_path

        return None

    def _get_readme(self, repo_path: Path) -> str:
        """
        Get README content.

        Args:
            repo_path: Path to repository

        Returns:
            README content as string
        """
        readme_path = self._find_readme(repo_path)

        if not readme_path:
            log.warning("No README found")
            return ""

        try:
            with open(readme_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            log.info(f"Retrieved README ({len(content)} chars)")
            return content
        except Exception as e:
            log.warning(f"Could not read README: {e}")
            return ""

    def _get_files(self, repo_path: Path, max_files: int = 50) -> List[Dict[str, Any]]:
        """
        Get code and documentation files from repository.

        Args:
            repo_path: Path to cloned repository
            max_files: Maximum number of files to retrieve

        Returns:
            List of dictionaries with file path and content
        """
        files = []
        count = 0

        # Walk through repository
        for file_path in repo_path.rglob('*'):
            # Skip if max files reached
            if count >= max_files:
                break

            # Skip directories
            if not file_path.is_file():
                continue

            # Skip ignored directories
            if any(ignored in file_path.parts for ignored in self.IGNORED_DIRS):
                continue

            # Check if file extension is supported
            if file_path.suffix not in self.SUPPORTED_EXTENSIONS:
                continue

            # Skip very large files
            try:
                file_size = file_path.stat().st_size
                if file_size > 100000:  # 100KB limit
                    log.debug(f"Skipping large file: {file_path}")
                    continue
            except:
                continue

            # Read file content
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()

                # Get relative path from repo root
                rel_path = file_path.relative_to(repo_path)

                files.append({
                    'path': str(rel_path),
                    'content': content,
                    'size': file_size
                })

                count += 1
                log.debug(f"Retrieved file: {rel_path} ({count}/{max_files})")

            except Exception as e:
                log.warning(f"Could not read file {file_path}: {e}")
                continue

        return files

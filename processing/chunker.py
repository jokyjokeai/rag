"""
Intelligent chunking for different content types.
"""
from typing import List, Dict, Any
from langchain_text_splitters import RecursiveCharacterTextSplitter, Language
import tiktoken
from config import settings
from utils import log


class IntelligentChunker:
    """Intelligent chunking based on content type."""

    def __init__(self):
        """Initialize chunker with configuration."""
        self.max_chunk_size = settings.max_chunk_size
        self.min_chunk_size = settings.min_chunk_size
        self.chunk_overlap = settings.chunk_overlap

        # Initialize tokenizer for token counting
        try:
            self.encoding = tiktoken.get_encoding("cl100k_base")
        except:
            log.warning("Could not load tiktoken encoding, using approximate token count")
            self.encoding = None

        log.info(f"Chunker initialized (max={self.max_chunk_size}, min={self.min_chunk_size}, overlap={self.chunk_overlap})")

    def chunk(
        self,
        content: str,
        source_type: str,
        metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Chunk content based on source type.

        Args:
            content: Text content to chunk
            source_type: Type of source ('youtube_video', 'github', 'website')
            metadata: Metadata dictionary

        Returns:
            List of chunk dictionaries
        """
        if not content or not content.strip():
            log.warning("Empty content provided for chunking")
            return []

        # Choose chunking strategy based on source type
        if source_type == 'youtube_video':
            chunks = self._chunk_youtube(content, metadata)
        elif source_type == 'github':
            chunks = self._chunk_code(content, metadata)
        elif source_type == 'website':
            chunks = self._chunk_documentation(content, metadata)
        else:
            # Default to documentation chunking
            chunks = self._chunk_documentation(content, metadata)

        log.info(f"Created {len(chunks)} chunks from {source_type} content")
        return chunks

    def _chunk_youtube(self, content: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Chunk YouTube transcript by temporal segments.

        Args:
            content: Transcript text
            metadata: Video metadata with segments

        Returns:
            List of chunks
        """
        chunks = []

        # Check if we have segment information
        segments = metadata.get('transcript_segments', [])

        if segments:
            # Use segments with timestamps
            current_chunk = []
            current_text = []
            current_start = None

            for segment in segments:
                current_text.append(segment['text'])

                if current_start is None:
                    current_start = segment['start']

                # Check if we've reached a good chunk size
                combined_text = " ".join(current_text)
                token_count = self._count_tokens(combined_text)

                if token_count >= self.max_chunk_size:
                    # Save current chunk
                    chunks.append({
                        'content': combined_text,
                        'timestamp_start': current_start,
                        'timestamp_end': segment['start'],
                        'token_count': token_count
                    })

                    # Start new chunk with overlap (keep last few segments)
                    overlap_segments = current_text[-3:] if len(current_text) > 3 else current_text
                    current_text = overlap_segments
                    current_start = segment['start']

            # Add remaining text as last chunk
            if current_text:
                combined_text = " ".join(current_text)
                chunks.append({
                    'content': combined_text,
                    'timestamp_start': current_start,
                    'timestamp_end': segments[-1]['start'] if segments else None,
                    'token_count': self._count_tokens(combined_text)
                })
        else:
            # No segments - fall back to simple chunking
            chunks = self._chunk_documentation(content, metadata)

        return chunks

    def _chunk_code(self, content: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Chunk code content by logical units.

        Args:
            content: Code and documentation text
            metadata: Repository metadata

        Returns:
            List of chunks
        """
        language = metadata.get('language', '').lower()

        # Map languages to LangChain Language enum
        language_map = {
            'python': Language.PYTHON,
            'javascript': Language.JS,
            'typescript': Language.TS,
            'java': Language.JAVA,
            'go': Language.GO,
            'rust': Language.RUST,
            'cpp': Language.CPP,
            'c': Language.CPP,
        }

        # Choose splitter based on language
        if language in language_map:
            splitter = RecursiveCharacterTextSplitter.from_language(
                language=language_map[language],
                chunk_size=self.max_chunk_size * 4,  # Approximate chars per tokens
                chunk_overlap=self.chunk_overlap * 4
            )
        else:
            # Use markdown splitter for .md files
            splitter = RecursiveCharacterTextSplitter.from_language(
                language=Language.MARKDOWN,
                chunk_size=self.max_chunk_size * 4,
                chunk_overlap=self.chunk_overlap * 4
            )

        # Split content
        text_chunks = splitter.split_text(content)

        # Convert to chunk dictionaries
        chunks = []
        for i, chunk_text in enumerate(text_chunks):
            chunks.append({
                'content': chunk_text,
                'chunk_index': i,
                'code_type': language,
                'token_count': self._count_tokens(chunk_text)
            })

        return chunks

    def _chunk_documentation(self, content: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Chunk documentation by sections/paragraphs.

        Args:
            content: Documentation text (markdown)
            metadata: Page metadata

        Returns:
            List of chunks
        """
        # Use markdown-aware splitter
        splitter = RecursiveCharacterTextSplitter.from_language(
            language=Language.MARKDOWN,
            chunk_size=self.max_chunk_size * 4,  # Approximate chars per token
            chunk_overlap=self.chunk_overlap * 4
        )

        # Split content
        text_chunks = splitter.split_text(content)

        # Convert to chunk dictionaries
        chunks = []
        for i, chunk_text in enumerate(text_chunks):
            # Try to extract heading from chunk
            lines = chunk_text.split('\n')
            heading = None
            for line in lines[:5]:  # Check first 5 lines
                if line.startswith('#'):
                    heading = line.lstrip('#').strip()
                    break

            chunks.append({
                'content': chunk_text,
                'chunk_index': i,
                'heading': heading,
                'token_count': self._count_tokens(chunk_text)
            })

        return chunks

    def _count_tokens(self, text: str) -> int:
        """
        Count tokens in text.

        Args:
            text: Text to count

        Returns:
            Number of tokens
        """
        if self.encoding:
            return len(self.encoding.encode(text))
        else:
            # Approximate: 1 token ≈ 4 characters
            return len(text) // 4

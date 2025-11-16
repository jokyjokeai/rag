"""
Main processing pipeline coordinator.
"""
import hashlib
import uuid
from typing import List, Dict, Any
from datetime import datetime
from .chunker import IntelligentChunker
from .embedder import Embedder
from .metadata_enricher import MetadataEnricher
from database import VectorStore
from utils import log, compute_url_hash


class ContentProcessor:
    """Main processing pipeline for scraped content."""

    def __init__(self, vector_store: VectorStore):
        """
        Initialize content processor.

        Args:
            vector_store: VectorStore instance for storing chunks
        """
        self.vector_store = vector_store
        self.chunker = IntelligentChunker()
        self.embedder = Embedder()
        self.enricher = MetadataEnricher()

        log.info("ContentProcessor initialized")

    def process(
        self,
        url: str,
        content: str,
        metadata: Dict[str, Any],
        source_type: str
    ) -> Dict[str, Any]:
        """
        Process scraped content through full pipeline.

        Args:
            url: Source URL
            content: Scraped content
            metadata: Source metadata
            source_type: Type of source

        Returns:
            Dictionary with processing results
        """
        log.info(f"Processing content from {url}")

        # Step 1: Chunk content
        chunks = self.chunker.chunk(content, source_type, metadata)

        if not chunks:
            log.warning(f"No chunks created for {url}")
            return {
                'success': False,
                'url': url,
                'chunks_created': 0,
                'error': 'No chunks created'
            }

        # Step 2: Generate document ID (same for all chunks from this URL)
        document_id = compute_url_hash(url)

        # Step 3: Process each chunk
        processed_chunks = []

        for i, chunk in enumerate(chunks):
            try:
                # Generate unique chunk ID
                chunk_id = str(uuid.uuid4())

                # Enrich metadata with LLM
                enriched_meta = self.enricher.enrich(chunk['content'])

                # Generate embedding
                embedding = self.embedder.embed_single(chunk['content'])

                # Combine all metadata (raw)
                raw_metadata = {
                    # Identifiers
                    'document_id': document_id,
                    'chunk_index': i,
                    'total_chunks': len(chunks),

                    # Source info
                    'source_url': url,
                    'source_type': source_type,
                    'domain': metadata.get('domain') or '',

                    # Content info
                    'content_length': len(chunk['content']),
                    'token_count': chunk.get('token_count', 0),

                    # Enriched metadata from LLM
                    **enriched_meta,

                    # Source-specific metadata
                    **self._extract_source_metadata(chunk, metadata, source_type),

                    # Temporal info
                    'processed_at': datetime.now().isoformat(),
                    'published_at': metadata.get('published_at') or '',

                    # Flags
                    'has_code_example': self._has_code(chunk['content']),
                    'language': metadata.get('language') or 'en'
                }

                # Normalize ALL metadata for ChromaDB (convert lists, remove None)
                full_metadata = self._normalize_metadata(raw_metadata)

                processed_chunks.append({
                    'chunk_id': chunk_id,
                    'content': chunk['content'],
                    'embedding': embedding,
                    'metadata': full_metadata
                })

                log.debug(f"Processed chunk {i+1}/{len(chunks)}")

            except Exception as e:
                log.error(f"Error processing chunk {i}: {e}")
                continue

        # Step 4: Store in vector database
        if processed_chunks:
            try:
                self.vector_store.add_chunks(processed_chunks)
                log.info(f"✅ Stored {len(processed_chunks)} chunks for {url}")
            except Exception as e:
                log.error(f"Error storing chunks: {e}")
                return {
                    'success': False,
                    'url': url,
                    'chunks_created': len(processed_chunks),
                    'error': f'Storage error: {str(e)}'
                }

        return {
            'success': True,
            'url': url,
            'chunks_created': len(processed_chunks),
            'document_id': document_id
        }

    def _extract_source_metadata(
        self,
        chunk: Dict[str, Any],
        source_metadata: Dict[str, Any],
        source_type: str
    ) -> Dict[str, Any]:
        """
        Extract source-specific metadata.

        Args:
            chunk: Chunk dictionary
            source_metadata: Original source metadata
            source_type: Type of source

        Returns:
            Source-specific metadata
        """
        meta = {}

        if source_type == 'youtube_video':
            meta['channel'] = source_metadata.get('channel', '')
            meta['video_title'] = source_metadata.get('title', '')
            meta['duration'] = source_metadata.get('duration', '')
            meta['timestamp_start'] = chunk.get('timestamp_start', '')
            meta['timestamp_end'] = chunk.get('timestamp_end', '')

        elif source_type == 'github':
            meta['repo_name'] = source_metadata.get('repo_name', '')
            meta['stars'] = source_metadata.get('stars', 0)
            meta['code_type'] = chunk.get('code_type', '')

        elif source_type == 'website':
            meta['page_title'] = source_metadata.get('title', '')
            meta['heading'] = chunk.get('heading', '')

        return meta

    def _normalize_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize metadata for ChromaDB compatibility.
        Converts lists to comma-separated strings and filters out None values.

        Args:
            metadata: Raw metadata dictionary

        Returns:
            Normalized metadata dictionary
        """
        normalized = {}

        for key, value in metadata.items():
            # Skip None values - ChromaDB doesn't accept them for some fields
            if value is None:
                continue

            if isinstance(value, list):
                # Convert list to comma-separated string
                if value:  # Only if list is not empty
                    normalized[key] = ', '.join(str(v) for v in value if v)
            elif isinstance(value, (str, int, float, bool)):
                # Keep primitives as-is (but not None, already filtered above)
                normalized[key] = value
            else:
                # Convert other types to string
                normalized[key] = str(value)

        return normalized

    def _has_code(self, content: str) -> bool:
        """
        Check if content contains code examples.

        Args:
            content: Text content

        Returns:
            True if code detected
        """
        code_indicators = ['```', 'def ', 'class ', 'function ', 'import ', 'const ', 'let ', 'var ']
        return any(indicator in content for indicator in code_indicators)

"""
Hybrid search combining semantic and keyword-based retrieval.

Uses Reciprocal Rank Fusion (RRF) to merge results from different retrieval methods,
improving both precision and recall.
"""
from typing import List, Dict, Any, Tuple
from utils import log


class HybridSearcher:
    """Hybrid search using semantic + keyword retrieval with RRF fusion."""

    def __init__(self):
        """Initialize hybrid searcher."""
        log.info("HybridSearcher initialized")

    def fuse_results(
        self,
        semantic_docs: List[str],
        semantic_metas: List[Dict[str, Any]],
        semantic_scores: List[float],
        keyword_docs: List[str],
        keyword_metas: List[Dict[str, Any]],
        keyword_scores: List[float],
        top_k: int = 5,
        semantic_weight: float = 0.7,
        keyword_weight: float = 0.3
    ) -> Tuple[List[str], List[Dict[str, Any]], List[float]]:
        """
        Fuse semantic and keyword search results using Reciprocal Rank Fusion (RRF).

        RRF formula: score(d) = Σ 1 / (k + rank(d))
        where k is a constant (typically 60), rank(d) is the rank of document d

        Args:
            semantic_docs: Documents from semantic search
            semantic_metas: Metadata from semantic search
            semantic_scores: Scores from semantic search
            keyword_docs: Documents from keyword search
            keyword_metas: Metadata from keyword search
            keyword_scores: Scores from keyword search
            top_k: Number of final results
            semantic_weight: Weight for semantic results (0-1)
            keyword_weight: Weight for keyword results (0-1)

        Returns:
            Tuple of (fused_documents, fused_metadatas, fused_scores)
        """
        # RRF constant (from literature)
        k = 60

        # Build doc_id -> (doc, meta) mapping
        doc_map = {}

        # Add semantic results with RRF scores
        for rank, (doc, meta, score) in enumerate(zip(semantic_docs, semantic_metas, semantic_scores), 1):
            doc_id = self._get_doc_id(meta)
            rrf_score = semantic_weight / (k + rank)

            if doc_id not in doc_map:
                doc_map[doc_id] = {
                    'doc': doc,
                    'meta': meta,
                    'rrf_score': 0.0,
                    'semantic_rank': rank,
                    'keyword_rank': None
                }

            doc_map[doc_id]['rrf_score'] += rrf_score
            doc_map[doc_id]['semantic_rank'] = rank

        # Add keyword results with RRF scores
        for rank, (doc, meta, score) in enumerate(zip(keyword_docs, keyword_metas, keyword_scores), 1):
            doc_id = self._get_doc_id(meta)
            rrf_score = keyword_weight / (k + rank)

            if doc_id not in doc_map:
                doc_map[doc_id] = {
                    'doc': doc,
                    'meta': meta,
                    'rrf_score': 0.0,
                    'semantic_rank': None,
                    'keyword_rank': rank
                }

            doc_map[doc_id]['rrf_score'] += rrf_score
            doc_map[doc_id]['keyword_rank'] = rank

        # Sort by RRF score (descending)
        sorted_results = sorted(
            doc_map.values(),
            key=lambda x: x['rrf_score'],
            reverse=True
        )

        # Take top_k
        sorted_results = sorted_results[:top_k]

        # Extract final results
        fused_docs = [r['doc'] for r in sorted_results]
        fused_metas = [r['meta'] for r in sorted_results]
        fused_scores = [r['rrf_score'] for r in sorted_results]

        log.debug(f"Fused {len(semantic_docs)} semantic + {len(keyword_docs)} keyword "
                 f"results into {len(fused_docs)} final results")

        return fused_docs, fused_metas, fused_scores

    def _get_doc_id(self, metadata: Dict[str, Any]) -> str:
        """
        Get unique document ID from metadata.

        Uses chunk_id if available, otherwise constructs from source_url + chunk_index.

        Args:
            metadata: Document metadata

        Returns:
            Unique document identifier
        """
        # Prefer chunk_id if available
        if 'chunk_id' in metadata:
            return metadata['chunk_id']

        # Fallback: construct from source_url + chunk_index
        source_url = metadata.get('source_url', 'unknown')
        chunk_index = metadata.get('chunk_index', 0)
        return f"{source_url}#{chunk_index}"

    def close(self):
        """Clean up resources."""
        # No resources to clean up
        pass

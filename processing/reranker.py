"""
Cross-Encoder reranker for improving search result relevance.

Reranking provides a second-stage scoring of results using a cross-encoder model
that directly compares the query with each document, providing much more accurate
relevance scores than embedding-based similarity alone.
"""
from typing import List, Dict, Any, Tuple
from sentence_transformers import CrossEncoder
from utils import log


class Reranker:
    """Cross-encoder reranker for search results."""

    def __init__(self, model_name: str = 'cross-encoder/ms-marco-MiniLM-L-6-v2'):
        """
        Initialize the reranker.

        Args:
            model_name: HuggingFace model name for cross-encoder
                       Default: ms-marco-MiniLM-L-6-v2 (fast, good quality)
                       Alternative: ms-marco-MiniLM-L-12-v2 (slower, better quality)
        """
        log.info(f"Loading cross-encoder reranker: {model_name}")
        self.model = CrossEncoder(model_name)
        log.info(f"Reranker loaded successfully")

    def rerank(
        self,
        query: str,
        documents: List[str],
        metadatas: List[Dict[str, Any]],
        top_k: int = 5
    ) -> Tuple[List[str], List[Dict[str, Any]], List[float]]:
        """
        Rerank documents based on query-document relevance.

        Args:
            query: Search query
            documents: List of document texts
            metadatas: List of metadata dicts (same order as documents)
            top_k: Number of top results to return

        Returns:
            Tuple of (reranked_documents, reranked_metadatas, rerank_scores)
        """
        if not documents:
            return [], [], []

        log.debug(f"Reranking {len(documents)} documents for query: '{query[:50]}...'")

        # Prepare query-document pairs for cross-encoder
        pairs = [[query, doc] for doc in documents]

        # Get relevance scores from cross-encoder
        # Scores are logits (higher = more relevant), typically range from -10 to 10
        scores = self.model.predict(pairs)

        # Create (score, index) pairs and sort by score (descending)
        scored_indices = [(score, idx) for idx, score in enumerate(scores)]
        scored_indices.sort(reverse=True, key=lambda x: x[0])

        # Take top_k results
        scored_indices = scored_indices[:top_k]

        # Extract reranked results
        reranked_documents = [documents[idx] for _, idx in scored_indices]
        reranked_metadatas = [metadatas[idx] for _, idx in scored_indices]
        rerank_scores = [score for score, _ in scored_indices]

        log.debug(f"Reranked to top {len(reranked_documents)} results. "
                 f"Top score: {rerank_scores[0]:.4f}, Bottom score: {rerank_scores[-1]:.4f}")

        return reranked_documents, reranked_metadatas, rerank_scores

    def normalize_scores(self, scores: List[float]) -> List[float]:
        """
        Normalize cross-encoder scores to 0-1 range using sigmoid.

        Cross-encoder scores are logits (can be negative or very large).
        Sigmoid converts them to probabilities: sigmoid(x) = 1 / (1 + e^(-x))

        Args:
            scores: List of raw cross-encoder scores

        Returns:
            List of normalized scores (0-1 range)
        """
        import math
        return [1 / (1 + math.exp(-score)) for score in scores]

    def close(self):
        """Clean up resources."""
        # CrossEncoder doesn't need explicit cleanup
        pass

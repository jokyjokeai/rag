"""
BM25-based keyword search for hybrid retrieval.

Complements semantic search with traditional keyword matching,
improving recall for exact term matches.
"""
from typing import List, Dict, Any, Tuple
from rank_bm25 import BM25Okapi
import numpy as np
from utils import log


class KeywordSearcher:
    """BM25 keyword search engine."""

    def __init__(self):
        """Initialize keyword searcher."""
        self.bm25 = None
        self.documents = []
        self.metadatas = []
        self.tokenized_docs = []
        log.info("KeywordSearcher initialized")

    def index(self, documents: List[str], metadatas: List[Dict[str, Any]]):
        """
        Index documents for keyword search.

        Args:
            documents: List of document texts
            metadatas: List of metadata dicts (same order)
        """
        if not documents:
            log.warning("No documents to index for keyword search")
            return

        log.info(f"Indexing {len(documents)} documents for keyword search...")

        self.documents = documents
        self.metadatas = metadatas

        # Tokenize documents (simple whitespace + lowercase)
        self.tokenized_docs = [self._tokenize(doc) for doc in documents]

        # Build BM25 index
        self.bm25 = BM25Okapi(self.tokenized_docs)

        log.info(f"Keyword search index built successfully")

    def search(self, query: str, top_k: int = 20) -> Tuple[List[str], List[Dict[str, Any]], List[float]]:
        """
        Search using BM25 keyword matching.

        Args:
            query: Search query
            top_k: Number of results to return

        Returns:
            Tuple of (documents, metadatas, scores)
        """
        if self.bm25 is None or not self.documents:
            log.warning("Keyword search index not built, returning empty results")
            return [], [], []

        # Tokenize query
        tokenized_query = self._tokenize(query)

        # Get BM25 scores
        scores = self.bm25.get_scores(tokenized_query)

        # Get top-k indices
        top_indices = np.argsort(scores)[::-1][:top_k]

        # Extract results
        result_docs = [self.documents[i] for i in top_indices]
        result_metas = [self.metadatas[i] for i in top_indices]
        result_scores = [scores[i] for i in top_indices]

        # Filter out zero-score results
        filtered_results = [
            (doc, meta, score)
            for doc, meta, score in zip(result_docs, result_metas, result_scores)
            if score > 0
        ]

        if filtered_results:
            result_docs, result_metas, result_scores = zip(*filtered_results)
            return list(result_docs), list(result_metas), list(result_scores)
        else:
            return [], [], []

    def _tokenize(self, text: str) -> List[str]:
        """
        Simple tokenization: lowercase + split on whitespace.

        Args:
            text: Text to tokenize

        Returns:
            List of tokens
        """
        # Simple tokenization - can be improved with proper NLP tokenizer
        return text.lower().split()

    def close(self):
        """Clean up resources."""
        self.bm25 = None
        self.documents = []
        self.metadatas = []
        self.tokenized_docs = []

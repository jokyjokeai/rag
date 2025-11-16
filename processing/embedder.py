"""
Embedding generation using sentence-transformers.
"""
from typing import List
import numpy as np
from sentence_transformers import SentenceTransformer
from config import settings
from utils import log


class Embedder:
    """Generate embeddings using local sentence-transformers model."""

    def __init__(self):
        """Initialize embedding model."""
        self.model_name = settings.embedding_model
        self.device = settings.embedding_device

        log.info(f"Loading embedding model: {self.model_name}")

        try:
            self.model = SentenceTransformer(
                self.model_name,
                device=self.device
            )
            log.info(f"Embedding model loaded on {self.device}")
        except Exception as e:
            log.error(f"Failed to load embedding model: {e}")
            raise

    def embed(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        """
        Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed
            batch_size: Batch size for encoding

        Returns:
            Numpy array of embeddings
        """
        if not texts:
            return np.array([])

        log.info(f"Generating embeddings for {len(texts)} texts")

        try:
            embeddings = self.model.encode(
                texts,
                batch_size=batch_size,
                show_progress_bar=len(texts) > 100,  # Show progress for large batches
                convert_to_numpy=True,
                normalize_embeddings=True  # Normalize for cosine similarity
            )

            log.info(f"Generated {len(embeddings)} embeddings (dim={embeddings.shape[1]})")
            return embeddings

        except Exception as e:
            log.error(f"Error generating embeddings: {e}")
            raise

    def embed_single(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text string to embed

        Returns:
            List of floats representing the embedding
        """
        embeddings = self.embed([text])
        return embeddings[0].tolist()

    def get_embedding_dim(self) -> int:
        """
        Get the dimension of embeddings produced by this model.

        Returns:
            Embedding dimension
        """
        return self.model.get_sentence_embedding_dimension()

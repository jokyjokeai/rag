"""
ChromaDB vector store interface for RAG system.
"""
from typing import List, Dict, Any, Optional
from pathlib import Path
import chromadb
from chromadb.config import Settings
from config import settings as app_settings
from utils import log


class VectorStore:
    """ChromaDB vector database interface."""

    def __init__(self, collection_name: str = "knowledge_base"):
        """
        Initialize ChromaDB client and collection.

        Args:
            collection_name: Name of the collection to use
        """
        self.collection_name = collection_name

        # Ensure database directory exists
        db_path = Path(app_settings.chroma_db_path)
        db_path.mkdir(parents=True, exist_ok=True)

        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=str(db_path),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )

        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "Technical knowledge base for RAG"}
        )

        log.info(f"ChromaDB initialized at {db_path} with collection '{collection_name}'")

    def add_chunks(
        self,
        chunks: List[Dict[str, Any]]
    ) -> int:
        """
        Add chunks to the vector database.

        Args:
            chunks: List of chunk dictionaries with keys:
                - chunk_id: Unique identifier
                - content: Text content
                - embedding: Vector embedding (list of floats)
                - metadata: Dictionary of metadata

        Returns:
            Number of chunks added
        """
        if not chunks:
            return 0

        chunk_ids = [chunk['chunk_id'] for chunk in chunks]
        contents = [chunk['content'] for chunk in chunks]
        embeddings = [chunk['embedding'] for chunk in chunks]
        metadatas = [chunk['metadata'] for chunk in chunks]

        try:
            self.collection.add(
                ids=chunk_ids,
                embeddings=embeddings,
                documents=contents,
                metadatas=metadatas
            )

            log.info(f"Added {len(chunks)} chunks to vector database")
            return len(chunks)

        except Exception as e:
            # Auto-recovery: if collection was deleted (e.g., by reset), recreate it
            if "does not exist" in str(e).lower():
                log.warning(f"Collection '{self.collection_name}' not found, recreating...")

                # Recreate the collection (same as __init__)
                self.collection = self.client.get_or_create_collection(
                    name=self.collection_name,
                    metadata={"description": "Technical knowledge base for RAG"}
                )
                log.info(f"Collection '{self.collection_name}' recreated successfully")

                # Retry the add operation
                self.collection.add(
                    ids=chunk_ids,
                    embeddings=embeddings,
                    documents=contents,
                    metadatas=metadatas
                )

                log.info(f"Added {len(chunks)} chunks to vector database (after recovery)")
                return len(chunks)
            else:
                # Other error, re-raise
                raise

    def search(
        self,
        query_embedding: List[float],
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Search for similar chunks using vector similarity.

        Args:
            query_embedding: Query vector embedding
            n_results: Number of results to return
            where: Optional metadata filters

        Returns:
            Dictionary with 'documents', 'metadatas', and 'distances'
        """
        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where
            )

            log.debug(f"Search returned {len(results['documents'][0])} results")
            return results

        except Exception as e:
            # Auto-recovery: if collection was deleted, recreate and return empty results
            if "does not exist" in str(e).lower():
                log.warning(f"Collection '{self.collection_name}' not found during search(), recreating...")
                self.collection = self.client.get_or_create_collection(
                    name=self.collection_name,
                    metadata={"description": "Technical knowledge base for RAG"}
                )
                log.info(f"Collection '{self.collection_name}' recreated successfully")
                # Return empty results
                return {'documents': [[]], 'metadatas': [[]], 'distances': [[]]}
            else:
                raise

    def get_by_source_url(self, source_url: str) -> Dict[str, Any]:
        """
        Get all chunks from a specific source URL.

        Args:
            source_url: URL of the source

        Returns:
            Dictionary with matching chunks
        """
        results = self.collection.get(
            where={"source_url": source_url}
        )

        log.debug(f"Found {len(results['ids'])} chunks for URL: {source_url}")
        return results

    def get_by_document_id(self, document_id: str) -> Dict[str, Any]:
        """
        Get all chunks belonging to a specific document.

        Args:
            document_id: Document identifier

        Returns:
            Dictionary with matching chunks ordered by chunk_index
        """
        results = self.collection.get(
            where={"document_id": document_id}
        )

        # Sort by chunk_index if available
        if results['metadatas']:
            sorted_results = sorted(
                zip(results['ids'], results['documents'], results['metadatas']),
                key=lambda x: x[2].get('chunk_index', 0)
            )
            results['ids'], results['documents'], results['metadatas'] = zip(*sorted_results)

        log.debug(f"Found {len(results['ids'])} chunks for document: {document_id}")
        return results

    def delete_by_source_url(self, source_url: str) -> int:
        """
        Delete all chunks from a specific source URL.

        Args:
            source_url: URL of the source to delete

        Returns:
            Number of chunks deleted
        """
        # Get IDs first
        results = self.collection.get(
            where={"source_url": source_url}
        )

        if results['ids']:
            self.collection.delete(ids=results['ids'])
            log.info(f"Deleted {len(results['ids'])} chunks from {source_url}")
            return len(results['ids'])

        return 0

    def count(self) -> int:
        """
        Get total number of chunks in the database.

        Returns:
            Total count of chunks
        """
        try:
            return self.collection.count()
        except Exception as e:
            # Auto-recovery: if collection was deleted, recreate and return 0
            if "does not exist" in str(e).lower():
                log.warning(f"Collection '{self.collection_name}' not found during count(), recreating...")
                self.collection = self.client.get_or_create_collection(
                    name=self.collection_name,
                    metadata={"description": "Technical knowledge base for RAG"}
                )
                log.info(f"Collection '{self.collection_name}' recreated successfully")
                return 0
            else:
                raise

    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the vector database.

        Returns:
            Dictionary with statistics
        """
        try:
            total_count = self.count()

            # Get unique source types
            all_data = self.collection.get()
            source_types = {}

            if all_data['metadatas']:
                for metadata in all_data['metadatas']:
                    source_type = metadata.get('source_type', 'unknown')
                    source_types[source_type] = source_types.get(source_type, 0) + 1

            stats = {
                'total_chunks': total_count,
                'by_source_type': source_types,
                'collection_name': self.collection_name
            }

            return stats

        except Exception as e:
            # Collection might not exist (e.g., after reset from another instance)
            # Return empty stats gracefully instead of crashing
            log.warning(f"Error getting stats (collection may not exist): {e}")
            return {
                'total_chunks': 0,
                'by_source_type': {},
                'collection_name': self.collection_name
            }

    def reset(self):
        """
        Delete all data from the collection.
        WARNING: This is irreversible!
        """
        self.client.delete_collection(name=self.collection_name)
        self.collection = self.client.create_collection(
            name=self.collection_name,
            metadata={"description": "Technical knowledge base for RAG"}
        )
        log.warning(f"Collection '{self.collection_name}' has been reset")

"""Semantic search using sentence transformers."""

import logging
from typing import List, Dict

import numpy as np
from sentence_transformers import SentenceTransformer

from docmine.storage.duckdb_backend import DuckDBBackend

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SemanticSearch:
    """Generate embeddings and perform semantic search."""

    def __init__(self, storage: DuckDBBackend, model_name: str = "sentence-transformers/all-mpnet-base-v2"):
        """
        Initialize semantic search with embedding model.

        Args:
            storage: DuckDB storage backend instance
            model_name: Name of the sentence transformer model to use
        """
        self.storage = storage
        self.model = SentenceTransformer(model_name)
        logger.info(f"Loaded embedding model: {model_name}")

    def generate_embeddings(self, texts: List[str]) -> np.ndarray:
        """
        Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed

        Returns:
            Numpy array of embeddings with shape (len(texts), 768)
        """
        embeddings = self.model.encode(
            texts,
            show_progress_bar=True,
            convert_to_numpy=True
        )
        return embeddings

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        Search for chunks semantically similar to the query.

        Args:
            query: Search query string
            top_k: Number of top results to return

        Returns:
            List of result dictionaries with id, source_pdf, page_num, content, and score
        """
        # Generate query embedding
        query_embedding = self.generate_embeddings([query])[0]

        # Search in storage
        results = self.storage.search(query_embedding, top_k)

        return results

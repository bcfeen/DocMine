"""DuckDB storage backend for document chunks and embeddings."""

import logging
from pathlib import Path
from typing import List, Dict, Any

import duckdb
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DuckDBBackend:
    """Store and retrieve document chunks with embeddings in DuckDB."""

    def __init__(self, db_path: str = "knowledge.duckdb"):
        """
        Initialize DuckDB connection and create schema.

        Args:
            db_path: Path to the DuckDB database file
        """
        self.db_path = db_path
        self.conn = duckdb.connect(db_path)

        # Create chunks table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY,
                source_pdf VARCHAR,
                page_num INTEGER,
                chunk_index INTEGER,
                location VARCHAR,
                content VARCHAR,
                embedding FLOAT[768]
            )
        """)

        # Create index for faster lookups
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_source ON chunks(source_pdf)
        """)

        logger.info(f"DuckDB backend initialized at {db_path}")

    def add_document(self, source_pdf: str, chunks: List[Dict], embeddings: np.ndarray):
        """
        Add a document's chunks and embeddings to the database.

        Args:
            source_pdf: Path to the source PDF file
            chunks: List of chunk dictionaries
            embeddings: Numpy array of embeddings (shape: [num_chunks, 768])
        """
        for chunk, embedding in zip(chunks, embeddings):
            self.conn.execute("""
                INSERT INTO chunks (source_pdf, page_num, chunk_index, location, content, embedding)
                VALUES (?, ?, ?, ?, ?, ?)
            """, [
                source_pdf,
                chunk["page_num"],
                chunk["chunk_index"],
                chunk["location"],
                chunk["content"],
                embedding.tolist()
            ])

        self.conn.commit()
        logger.info(f"Stored {len(chunks)} chunks from {source_pdf}")

    def search(self, query_embedding: np.ndarray, top_k: int = 5) -> List[Dict]:
        """
        Search for chunks similar to the query embedding.

        Args:
            query_embedding: Query embedding vector (shape: [768])
            top_k: Number of top results to return

        Returns:
            List of result dictionaries with id, source_pdf, page_num, content, and score
        """
        # Fetch all chunks
        result = self.conn.execute("""
            SELECT id, source_pdf, page_num, content, embedding
            FROM chunks
        """).fetchall()

        if not result:
            logger.warning("No chunks found in database")
            return []

        # Compute cosine similarities
        similarities = []
        for row in result:
            chunk_id, source_pdf, page_num, content, embedding = row
            embedding_array = np.array(embedding)

            # Cosine similarity
            dot_product = np.dot(query_embedding, embedding_array)
            norm_query = np.linalg.norm(query_embedding)
            norm_embedding = np.linalg.norm(embedding_array)
            similarity = dot_product / (norm_query * norm_embedding)

            similarities.append({
                "id": chunk_id,
                "source_pdf": source_pdf,
                "page_num": page_num,
                "content": content,
                "score": float(similarity)
            })

        # Sort by similarity descending and return top_k
        similarities.sort(key=lambda x: x["score"], reverse=True)
        return similarities[:top_k]

    def count_chunks(self) -> int:
        """
        Get the total number of chunks in the database.

        Returns:
            Total number of chunks
        """
        result = self.conn.execute("SELECT COUNT(*) FROM chunks").fetchone()
        return result[0] if result else 0

    def close(self):
        """Close the database connection."""
        self.conn.close()
        logger.info("DuckDB connection closed")

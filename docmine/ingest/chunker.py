"""Semantic text chunking using Chonkie."""

import logging
from typing import List, Dict, Any

from chonkie import SemanticChunker as ChonkieSemanticChunker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SemanticChunker:
    """Chunk text into semantic segments using Chonkie."""

    def __init__(self, chunk_size: int = 400, chunk_overlap: int = 50):
        """
        Initialize the semantic chunker.

        Args:
            chunk_size: Target size for each chunk in tokens
            chunk_overlap: Number of overlapping tokens between chunks
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.chunker = ChonkieSemanticChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        logger.info(f"SemanticChunker initialized (size={chunk_size}, overlap={chunk_overlap})")

    def chunk_pages(self, pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Chunk text from multiple pages into semantic segments.

        Args:
            pages: List of page dictionaries with 'page_num' and 'text' keys

        Returns:
            List of chunk dictionaries with content, page_num, chunk_index, and location
        """
        all_chunks = []

        for page in pages:
            page_num = page["page_num"]
            text = page["text"]

            # Chunk the page text
            chunks = self.chunker.chunk(text)

            # Process each chunk
            for idx, chunk in enumerate(chunks):
                chunk_dict = {
                    "content": chunk.text,
                    "page_num": page_num,
                    "chunk_index": idx,
                    "location": f"page_{page_num}_chunk_{idx}"
                }
                all_chunks.append(chunk_dict)

        logger.info(f"Created {len(all_chunks)} chunks from {len(pages)} pages")
        return all_chunks

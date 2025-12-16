"""Main pipeline for PDF knowledge extraction."""

import logging
from pathlib import Path
from typing import List, Dict

from tqdm import tqdm

from docmine.ingest.pdf_extractor import PDFExtractor
from docmine.ingest.chunker import SemanticChunker
from docmine.storage.duckdb_backend import DuckDBBackend
from docmine.search.semantic_search import SemanticSearch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PDFPipeline:
    """Main user-facing API for PDF knowledge extraction and search."""

    def __init__(
        self,
        storage_path: str = "knowledge.duckdb",
        chunk_size: int = 400,
        chunk_overlap: int = 50,
        embedding_model: str = "sentence-transformers/all-mpnet-base-v2"
    ):
        """
        Initialize the PDF processing pipeline.

        Args:
            storage_path: Path to DuckDB database file
            chunk_size: Target size for text chunks
            chunk_overlap: Overlap between consecutive chunks
            embedding_model: Name of the sentence transformer model
        """
        self.extractor = PDFExtractor()
        self.chunker = SemanticChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        self.storage = DuckDBBackend(db_path=storage_path)
        self.search_engine = SemanticSearch(self.storage, model_name=embedding_model)

        logger.info(f"PDFPipeline initialized with storage at {storage_path}")

    def ingest_file(self, pdf_path: str) -> int:
        """
        Ingest a single PDF file into the knowledge base.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Number of chunks processed

        Raises:
            FileNotFoundError: If the PDF file doesn't exist
        """
        pdf_file = Path(pdf_path)

        if not pdf_file.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        try:
            # Extract pages
            pages = self.extractor.extract(pdf_file)

            if not pages:
                logger.warning(f"No content extracted from {pdf_path}")
                return 0

            # Chunk pages
            chunks = self.chunker.chunk_pages(pages)

            if not chunks:
                logger.warning(f"No chunks created from {pdf_path}")
                return 0

            # Generate embeddings
            logger.info(f"Generating embeddings for {len(chunks)} chunks...")
            embeddings = self.search_engine.generate_embeddings([c["content"] for c in chunks])

            # Store in database
            self.storage.add_document(str(pdf_file), chunks, embeddings)

            logger.info(f"Successfully ingested {pdf_path}: {len(chunks)} chunks")
            return len(chunks)

        except Exception as e:
            logger.error(f"Error ingesting {pdf_path}: {e}")
            raise

    def ingest_directory(self, directory: str, pattern: str = "*.pdf") -> int:
        """
        Ingest all PDF files from a directory.

        Args:
            directory: Path to directory containing PDFs
            pattern: Glob pattern to match PDF files (default: "*.pdf")

        Returns:
            Total number of chunks ingested across all files
        """
        dir_path = Path(directory)
        pdf_files = list(dir_path.rglob(pattern))

        if not pdf_files:
            logger.warning(f"No PDF files found in {directory} matching pattern {pattern}")
            return 0

        logger.info(f"Found {len(pdf_files)} PDF files to ingest")

        total_chunks = 0
        for pdf_path in tqdm(pdf_files, desc="Ingesting PDFs"):
            try:
                chunks = self.ingest_file(str(pdf_path))
                total_chunks += chunks
            except Exception as e:
                logger.error(f"Failed to ingest {pdf_path}: {e}")
                continue

        logger.info(f"Ingested {total_chunks} chunks from {len(pdf_files)} PDFs")
        return total_chunks

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        Search the knowledge base for relevant chunks.

        Args:
            query: Search query string
            top_k: Number of top results to return

        Returns:
            List of result dictionaries with source_pdf, page_num, content, and score
        """
        results = self.search_engine.search(query, top_k=top_k)
        return results

    def __del__(self):
        """Cleanup: close storage connection."""
        try:
            self.storage.close()
        except Exception:
            pass

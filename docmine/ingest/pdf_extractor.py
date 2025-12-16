"""PDF text extraction using PyMuPDF."""

import logging
from pathlib import Path
from typing import List, Dict, Any

import fitz  # PyMuPDF

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PDFExtractor:
    """Extract text content from PDF files."""

    def extract(self, pdf_path: Path) -> List[Dict[str, Any]]:
        """
        Extract text from a PDF file page by page.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            List of dictionaries containing page number and text content.
            Pages with less than 50 characters are filtered out.
        """
        pages = []

        try:
            doc = fitz.open(pdf_path)
            logger.info(f"Extracting text from {pdf_path} ({len(doc)} pages)")

            for page_num, page in enumerate(doc, start=1):
                text = page.get_text("text")

                # Filter out empty or near-empty pages
                if len(text) >= 50:
                    pages.append({
                        "page_num": page_num,
                        "text": text
                    })
                else:
                    logger.debug(f"Skipping page {page_num} (too short: {len(text)} chars)")

            doc.close()
            logger.info(f"Extracted {len(pages)} pages with content from {pdf_path}")

        except Exception as e:
            logger.error(f"Error extracting PDF {pdf_path}: {e}")
            return []

        return pages

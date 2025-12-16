"""Deterministic text segmentation with provenance tracking."""

import logging
import re
from typing import List, Dict, Any

from docmine.models import ResourceSegment, generate_segment_id, generate_text_hash

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DeterministicSegmenter:
    """
    Create deterministic, stable segments from text with provenance.

    Unlike the old SemanticChunker, this segmenter:
    1. Produces deterministic segment IDs (stable across re-ingestion)
    2. Preserves precise provenance (page, sentence position)
    3. Segments by sentences (not by token count)
    4. Generates stable IDs based on content + location
    """

    def __init__(self, sentences_per_segment: int = 3):
        """
        Initialize segmenter.

        Args:
            sentences_per_segment: Number of sentences per segment (default: 3)
        """
        self.sentences_per_segment = sentences_per_segment
        logger.info(f"DeterministicSegmenter initialized (sentences={sentences_per_segment})")

    def segment_pages(
        self,
        pages: List[Dict[str, Any]],
        ir_id: str,
        namespace: str,
        source_uri: str
    ) -> List[ResourceSegment]:
        """
        Segment text from pages into ResourceSegments.

        Args:
            pages: List of page dicts with 'page_num' and 'text'
            ir_id: InformationResource ID
            namespace: Namespace for ID generation
            source_uri: Source URI for ID generation

        Returns:
            List of ResourceSegments with stable IDs and provenance
        """
        all_segments = []
        global_index = 0

        for page in pages:
            page_num = page["page_num"]
            text = page["text"]

            # Split into sentences
            sentences = self._split_sentences(text)

            if not sentences:
                continue

            # Group sentences into segments
            for sent_idx in range(0, len(sentences), self.sentences_per_segment):
                batch = sentences[sent_idx:sent_idx + self.sentences_per_segment]
                segment_text = " ".join(batch)

                # Skip empty segments
                if not segment_text.strip():
                    continue

                # Build provenance
                provenance = {
                    "page": page_num,
                    "sentence": sent_idx,
                    "sentence_count": len(batch)
                }

                # Generate deterministic ID
                provenance_key = f"{page_num}:{sent_idx}"
                segment_id = generate_segment_id(
                    namespace=namespace,
                    source_uri=source_uri,
                    provenance_key=provenance_key,
                    text=segment_text
                )

                # Create segment
                segment = ResourceSegment(
                    id=segment_id,
                    ir_id=ir_id,
                    segment_index=global_index,
                    text=segment_text,
                    provenance=provenance,
                    text_hash=generate_text_hash(segment_text)
                )

                all_segments.append(segment)
                global_index += 1

        logger.info(f"Created {len(all_segments)} segments from {len(pages)} pages")
        return all_segments

    def _split_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences.

        Uses a simple regex-based approach. For production, consider
        using a more sophisticated sentence tokenizer (e.g., spaCy).

        Args:
            text: Input text

        Returns:
            List of sentences
        """
        # Simple sentence splitting regex
        # Splits on ., !, ? followed by whitespace and capital letter
        pattern = r'(?<=[.!?])\s+(?=[A-Z])'
        sentences = re.split(pattern, text)

        # Clean and filter
        sentences = [s.strip() for s in sentences if s.strip()]

        # Filter out very short "sentences" (likely artifacts)
        sentences = [s for s in sentences if len(s) >= 20]

        return sentences

    def segment_markdown(
        self,
        text: str,
        ir_id: str,
        namespace: str,
        source_uri: str
    ) -> List[ResourceSegment]:
        """
        Segment markdown text with heading-based provenance.

        Args:
            text: Markdown text
            ir_id: InformationResource ID
            namespace: Namespace for ID generation
            source_uri: Source URI for ID generation

        Returns:
            List of ResourceSegments
        """
        segments = []
        global_index = 0

        # Split by headings
        lines = text.split('\n')
        current_heading = "root"
        current_para = []
        para_index = 0

        for line in lines:
            # Check if heading
            if line.startswith('#'):
                # Process accumulated paragraph
                if current_para:
                    segments.extend(self._segment_paragraph(
                        current_para,
                        current_heading,
                        para_index,
                        ir_id,
                        namespace,
                        source_uri,
                        global_index
                    ))
                    global_index += len(segments)
                    para_index += 1
                    current_para = []

                # Update heading
                current_heading = line.lstrip('#').strip()

            elif line.strip():
                current_para.append(line)

        # Process final paragraph
        if current_para:
            segments.extend(self._segment_paragraph(
                current_para,
                current_heading,
                para_index,
                ir_id,
                namespace,
                source_uri,
                global_index
            ))

        logger.info(f"Created {len(segments)} segments from markdown")
        return segments

    def _segment_paragraph(
        self,
        para_lines: List[str],
        heading: str,
        para_index: int,
        ir_id: str,
        namespace: str,
        source_uri: str,
        start_index: int
    ) -> List[ResourceSegment]:
        """Segment a markdown paragraph."""
        text = " ".join(para_lines)
        sentences = self._split_sentences(text)

        segments = []
        for sent_idx in range(0, len(sentences), self.sentences_per_segment):
            batch = sentences[sent_idx:sent_idx + self.sentences_per_segment]
            segment_text = " ".join(batch)

            if not segment_text.strip():
                continue

            provenance = {
                "heading_path": heading,
                "para": para_index,
                "sentence": sent_idx,
                "sentence_count": len(batch)
            }

            provenance_key = f"{heading}:{para_index}:{sent_idx}"
            segment_id = generate_segment_id(
                namespace=namespace,
                source_uri=source_uri,
                provenance_key=provenance_key,
                text=segment_text
            )

            segment = ResourceSegment(
                id=segment_id,
                ir_id=ir_id,
                segment_index=start_index + len(segments),
                text=segment_text,
                provenance=provenance,
                text_hash=generate_text_hash(segment_text)
            )

            segments.append(segment)

        return segments

    def segment_text(
        self,
        text: str,
        ir_id: str,
        namespace: str,
        source_uri: str
    ) -> List[ResourceSegment]:
        """
        Segment plain text with line-based provenance.

        Args:
            text: Plain text
            ir_id: InformationResource ID
            namespace: Namespace for ID generation
            source_uri: Source URI for ID generation

        Returns:
            List of ResourceSegments
        """
        segments = []
        sentences = self._split_sentences(text)

        for sent_idx in range(0, len(sentences), self.sentences_per_segment):
            batch = sentences[sent_idx:sent_idx + self.sentences_per_segment]
            segment_text = " ".join(batch)

            if not segment_text.strip():
                continue

            provenance = {
                "sentence": sent_idx,
                "sentence_count": len(batch)
            }

            provenance_key = f"{sent_idx}"
            segment_id = generate_segment_id(
                namespace=namespace,
                source_uri=source_uri,
                provenance_key=provenance_key,
                text=segment_text
            )

            segment = ResourceSegment(
                id=segment_id,
                ir_id=ir_id,
                segment_index=len(segments),
                text=segment_text,
                provenance=provenance,
                text_hash=generate_text_hash(segment_text)
            )

            segments.append(segment)

        logger.info(f"Created {len(segments)} segments from plain text")
        return segments

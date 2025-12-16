"""Knowledge-centric ingestion pipeline."""

import logging
from pathlib import Path
from typing import List, Optional

from docmine.models import (
    InformationResource,
    ResourceSegment,
    Entity,
    EntityLink,
    generate_ir_id,
    generate_entity_id,
    generate_content_hash,
)
from docmine.storage.knowledge_store import KnowledgeStore
from docmine.ingest.pdf_extractor import PDFExtractor
from docmine.ingest.segmenter import DeterministicSegmenter
from docmine.extraction import BaseEntityExtractor, RegexEntityExtractor, ExtractedEntity

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class KnowledgeIngestionPipeline:
    """
    Knowledge-centric ingestion pipeline.

    Replaces the old chunk-based ingestion with:
    1. register_information_resource
    2. segment_resource (deterministic)
    3. extract_entities (NER)
    4. link_entities (store relationships)
    """

    def __init__(
        self,
        store: KnowledgeStore,
        entity_extractor: Optional[BaseEntityExtractor] = None,
        sentences_per_segment: int = 3
    ):
        """
        Initialize ingestion pipeline.

        Args:
            store: KnowledgeStore instance
            entity_extractor: Entity extractor (default: RegexEntityExtractor)
            sentences_per_segment: Sentences per segment (default: 3)
        """
        self.store = store
        self.pdf_extractor = PDFExtractor()
        self.segmenter = DeterministicSegmenter(sentences_per_segment=sentences_per_segment)

        # Default to regex extractor if not provided
        self.entity_extractor = entity_extractor or RegexEntityExtractor()

        logger.info("KnowledgeIngestionPipeline initialized")

    def ingest_pdf(
        self,
        pdf_path: Path,
        namespace: str,
        metadata: Optional[dict] = None
    ) -> tuple[InformationResource, List[ResourceSegment], List[Entity]]:
        """
        Ingest a PDF file into the knowledge store.

        Args:
            pdf_path: Path to PDF file
            namespace: Namespace for multi-corpus support
            metadata: Optional metadata dict

        Returns:
            Tuple of (InformationResource, segments, entities)
        """
        logger.info(f"Ingesting PDF: {pdf_path}")

        # 1. Register InformationResource
        ir = self._register_ir(pdf_path, namespace, "pdf", metadata)

        # 2. Extract text from PDF
        pages = self.pdf_extractor.extract(pdf_path)
        if not pages:
            logger.warning(f"No content extracted from {pdf_path}")
            return ir, [], []

        # 3. Segment resource
        segments = self._segment_resource(ir, pages)
        if not segments:
            logger.warning(f"No segments created from {pdf_path}")
            return ir, [], []

        # 4. Store segments (idempotent)
        self.store.bulk_upsert_segments(segments)

        # 5. Extract entities
        entities = self._extract_and_link_entities(segments, namespace)

        logger.info(f"Ingested {pdf_path}: {len(segments)} segments, {len(entities)} entities")
        return ir, segments, entities

    def ingest_markdown(
        self,
        md_path: Path,
        namespace: str,
        metadata: Optional[dict] = None
    ) -> tuple[InformationResource, List[ResourceSegment], List[Entity]]:
        """
        Ingest a Markdown file into the knowledge store.

        Args:
            md_path: Path to Markdown file
            namespace: Namespace for multi-corpus support
            metadata: Optional metadata dict

        Returns:
            Tuple of (InformationResource, segments, entities)
        """
        logger.info(f"Ingesting Markdown: {md_path}")

        # 1. Register InformationResource
        ir = self._register_ir(md_path, namespace, "md", metadata)

        # 2. Read markdown
        with open(md_path, 'r', encoding='utf-8') as f:
            text = f.read()

        if not text.strip():
            logger.warning(f"No content in {md_path}")
            return ir, [], []

        # 3. Segment markdown
        segments = self.segmenter.segment_markdown(
            text=text,
            ir_id=ir.id,
            namespace=namespace,
            source_uri=ir.source_uri
        )

        if not segments:
            logger.warning(f"No segments created from {md_path}")
            return ir, [], []

        # 4. Store segments
        self.store.bulk_upsert_segments(segments)

        # 5. Extract entities
        entities = self._extract_and_link_entities(segments, namespace)

        logger.info(f"Ingested {md_path}: {len(segments)} segments, {len(entities)} entities")
        return ir, segments, entities

    def ingest_text(
        self,
        txt_path: Path,
        namespace: str,
        metadata: Optional[dict] = None
    ) -> tuple[InformationResource, List[ResourceSegment], List[Entity]]:
        """
        Ingest a plain text file into the knowledge store.

        Args:
            txt_path: Path to text file
            namespace: Namespace for multi-corpus support
            metadata: Optional metadata dict

        Returns:
            Tuple of (InformationResource, segments, entities)
        """
        logger.info(f"Ingesting text: {txt_path}")

        # 1. Register InformationResource
        ir = self._register_ir(txt_path, namespace, "txt", metadata)

        # 2. Read text
        with open(txt_path, 'r', encoding='utf-8') as f:
            text = f.read()

        if not text.strip():
            logger.warning(f"No content in {txt_path}")
            return ir, [], []

        # 3. Segment text
        segments = self.segmenter.segment_text(
            text=text,
            ir_id=ir.id,
            namespace=namespace,
            source_uri=ir.source_uri
        )

        if not segments:
            logger.warning(f"No segments created from {txt_path}")
            return ir, [], []

        # 4. Store segments
        self.store.bulk_upsert_segments(segments)

        # 5. Extract entities
        entities = self._extract_and_link_entities(segments, namespace)

        logger.info(f"Ingested {txt_path}: {len(segments)} segments, {len(entities)} entities")
        return ir, segments, entities

    def _register_ir(
        self,
        file_path: Path,
        namespace: str,
        source_type: str,
        metadata: Optional[dict]
    ) -> InformationResource:
        """
        Register an InformationResource (idempotent).

        Args:
            file_path: Path to source file
            namespace: Namespace
            source_type: Source type (pdf, md, txt)
            metadata: Optional metadata

        Returns:
            InformationResource (existing or new)
        """
        # Build canonical source URI
        source_uri = f"file://{file_path.absolute()}"

        # Calculate content hash
        with open(file_path, 'rb') as f:
            content = f.read()
        content_hash = generate_content_hash(content)

        # Check if already exists
        existing = self.store.get_ir_by_uri(namespace, source_uri)

        if existing:
            # Check if content changed
            if existing.content_hash != content_hash:
                logger.info(f"Content changed for {source_uri}, updating...")
                existing.content_hash = content_hash
                if metadata:
                    existing.metadata.update(metadata)
                return self.store.upsert_information_resource(existing)
            else:
                logger.info(f"IR already exists: {source_uri}")
                return existing

        # Create new IR
        ir = InformationResource(
            id=generate_ir_id(),
            namespace=namespace,
            source_type=source_type,
            source_uri=source_uri,
            content_hash=content_hash,
            metadata=metadata or {}
        )

        return self.store.upsert_information_resource(ir)

    def _segment_resource(
        self,
        ir: InformationResource,
        pages: List[dict]
    ) -> List[ResourceSegment]:
        """
        Segment an InformationResource into ResourceSegments.

        Args:
            ir: InformationResource
            pages: List of page dicts (from PDFExtractor)

        Returns:
            List of ResourceSegments
        """
        return self.segmenter.segment_pages(
            pages=pages,
            ir_id=ir.id,
            namespace=ir.namespace,
            source_uri=ir.source_uri
        )

    def _extract_and_link_entities(
        self,
        segments: List[ResourceSegment],
        namespace: str
    ) -> List[Entity]:
        """
        Extract entities from segments and create links.

        Args:
            segments: List of ResourceSegments
            namespace: Namespace

        Returns:
            List of unique Entities created
        """
        all_entities = []
        all_links = []

        for segment in segments:
            # Extract entities from segment text
            extracted = self.entity_extractor.extract(segment.text)

            for ext_entity in extracted:
                # Get or create entity
                entity = self.store.get_entity_by_name(
                    namespace=namespace,
                    entity_type=ext_entity.type,
                    name=ext_entity.name
                )

                if not entity:
                    # Create new entity
                    entity = Entity(
                        id=generate_entity_id(),
                        namespace=namespace,
                        type=ext_entity.type,
                        name=ext_entity.name,
                        aliases=ext_entity.aliases,
                        metadata=ext_entity.metadata
                    )
                    entity = self.store.upsert_entity(entity)
                    all_entities.append(entity)

                # Create link
                link = EntityLink(
                    segment_id=segment.id,
                    entity_id=entity.id,
                    link_type="mentions",
                    confidence=ext_entity.confidence
                )
                all_links.append(link)

        # Bulk add links
        if all_links:
            self.store.bulk_add_entity_links(all_links)
            logger.info(f"Created {len(all_links)} entity links")

        return all_entities

    def reingest_changed(self, namespace: str) -> int:
        """
        Re-ingest only changed resources in a namespace.

        Checks content_hash to detect changes.

        Args:
            namespace: Namespace to scan

        Returns:
            Number of resources re-ingested
        """
        irs = self.store.list_irs(namespace=namespace)
        reingested = 0

        for ir in irs:
            # Extract file path from source_uri
            if not ir.source_uri.startswith("file://"):
                continue

            file_path = Path(ir.source_uri.replace("file://", ""))

            if not file_path.exists():
                logger.warning(f"File not found: {file_path}")
                continue

            # Check content hash
            with open(file_path, 'rb') as f:
                content = f.read()
            current_hash = generate_content_hash(content)

            if current_hash != ir.content_hash:
                logger.info(f"Content changed, re-ingesting: {file_path}")

                # Determine source type
                suffix = file_path.suffix.lower()
                if suffix == '.pdf':
                    self.ingest_pdf(file_path, namespace, ir.metadata)
                elif suffix == '.md':
                    self.ingest_markdown(file_path, namespace, ir.metadata)
                elif suffix == '.txt':
                    self.ingest_text(file_path, namespace, ir.metadata)

                reingested += 1

        logger.info(f"Re-ingested {reingested} changed resources")
        return reingested

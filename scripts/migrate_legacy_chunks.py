"""
Migration script: Convert old chunk-based storage to knowledge-centric KOS.

This script reads the old `chunks` table from DuckDBBackend and converts
it into the new KOS structure with InformationResources, ResourceSegments,
and Entities.

Usage:
    python scripts/migrate_legacy_chunks.py --old-db knowledge.duckdb --new-db knowledge_kos.duckdb --namespace legacy
"""

import argparse
import logging
from pathlib import Path
from datetime import datetime

import duckdb

from docmine.models import (
    InformationResource,
    ResourceSegment,
    generate_ir_id,
    generate_segment_id,
    generate_text_hash,
    generate_content_hash,
)
from docmine.storage.knowledge_store import KnowledgeStore
from docmine.extraction import RegexEntityExtractor
from docmine.models import Entity, EntityLink, generate_entity_id

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class LegacyMigrator:
    """Migrate old chunk-based data to knowledge-centric KOS."""

    def __init__(
        self,
        old_db_path: str,
        new_db_path: str,
        namespace: str = "legacy"
    ):
        """
        Initialize migrator.

        Args:
            old_db_path: Path to old DuckDB database
            new_db_path: Path to new KOS database
            namespace: Namespace for migrated data
        """
        self.old_db_path = old_db_path
        self.new_db_path = new_db_path
        self.namespace = namespace

        self.old_conn = None
        self.new_store = None
        self.entity_extractor = RegexEntityExtractor()

    def connect(self):
        """Connect to both databases."""
        logger.info(f"Connecting to old DB: {self.old_db_path}")
        self.old_conn = duckdb.connect(self.old_db_path, read_only=True)

        logger.info(f"Connecting to new DB: {self.new_db_path}")
        self.new_store = KnowledgeStore(db_path=self.new_db_path)

    def close(self):
        """Close connections."""
        if self.old_conn:
            self.old_conn.close()
        if self.new_store:
            self.new_store.close()

    def migrate(self):
        """Run the full migration."""
        logger.info("Starting migration...")

        # 1. Get all unique source PDFs from old chunks
        sources = self._get_unique_sources()
        logger.info(f"Found {len(sources)} unique sources")

        # 2. For each source, create IR and migrate chunks to segments
        total_segments = 0
        total_entities = 0

        for source_pdf in sources:
            ir_id, seg_count, entity_count = self._migrate_source(source_pdf)
            total_segments += seg_count
            total_entities += entity_count

        logger.info(f"Migration complete!")
        logger.info(f"  - {len(sources)} Information Resources")
        logger.info(f"  - {total_segments} Segments")
        logger.info(f"  - {total_entities} Entities")

    def _get_unique_sources(self):
        """Get all unique source PDFs from old chunks table."""
        result = self.old_conn.execute("""
            SELECT DISTINCT source_pdf
            FROM chunks
            ORDER BY source_pdf
        """).fetchall()

        return [row[0] for row in result]

    def _migrate_source(self, source_pdf: str):
        """
        Migrate all chunks from a single source to KOS.

        Args:
            source_pdf: Path to source PDF

        Returns:
            Tuple of (ir_id, segment_count, entity_count)
        """
        logger.info(f"Migrating: {source_pdf}")

        # 1. Create InformationResource
        ir = self._create_ir_from_source(source_pdf)

        # 2. Get all chunks for this source
        chunks = self._get_chunks_for_source(source_pdf)
        logger.info(f"  Found {len(chunks)} legacy chunks")

        # 3. Convert chunks to segments
        segments = []
        for idx, chunk in enumerate(chunks):
            segment = self._chunk_to_segment(chunk, ir, idx)
            segments.append(segment)

        # 4. Store segments
        self.new_store.bulk_upsert_segments(segments)
        logger.info(f"  Migrated {len(segments)} segments")

        # 5. Extract and link entities
        entities = self._extract_and_link_entities(segments)
        logger.info(f"  Extracted {len(entities)} entities")

        return ir.id, len(segments), len(entities)

    def _create_ir_from_source(self, source_pdf: str) -> InformationResource:
        """
        Create an InformationResource from a source PDF path.

        Args:
            source_pdf: Path to source PDF

        Returns:
            InformationResource
        """
        # Build canonical source URI
        source_uri = f"file://{Path(source_pdf).absolute()}"

        # Calculate content hash (use dummy if file doesn't exist)
        if Path(source_pdf).exists():
            with open(source_pdf, 'rb') as f:
                content = f.read()
            content_hash = generate_content_hash(content)
        else:
            # File no longer exists, use placeholder hash
            content_hash = "legacy_" + source_pdf.replace("/", "_")

        # Create IR
        ir = InformationResource(
            id=generate_ir_id(),
            namespace=self.namespace,
            source_type="pdf",
            source_uri=source_uri,
            content_hash=content_hash,
            metadata={"migrated_from": "legacy_chunks", "original_path": source_pdf}
        )

        # Store IR
        return self.new_store.upsert_information_resource(ir)

    def _get_chunks_for_source(self, source_pdf: str):
        """
        Get all chunks for a source PDF.

        Args:
            source_pdf: Path to source PDF

        Returns:
            List of chunk dicts
        """
        result = self.old_conn.execute("""
            SELECT id, source_pdf, page_num, chunk_index, location, content
            FROM chunks
            WHERE source_pdf = ?
            ORDER BY page_num, chunk_index
        """, [source_pdf]).fetchall()

        return [
            {
                "id": row[0],
                "source_pdf": row[1],
                "page_num": row[2],
                "chunk_index": row[3],
                "location": row[4],
                "content": row[5],
            }
            for row in result
        ]

    def _chunk_to_segment(
        self,
        chunk: dict,
        ir: InformationResource,
        segment_index: int
    ) -> ResourceSegment:
        """
        Convert a legacy chunk to a ResourceSegment.

        Args:
            chunk: Legacy chunk dict
            ir: Parent InformationResource
            segment_index: Segment index

        Returns:
            ResourceSegment
        """
        # Build provenance from legacy chunk metadata
        provenance = {
            "page": chunk["page_num"],
            "chunk_index": chunk["chunk_index"],
            "location": chunk["location"],
            "legacy": True,
        }

        # Generate deterministic ID
        # For legacy data, we use page:chunk_index as provenance key
        provenance_key = f"{chunk['page_num']}:{chunk['chunk_index']}"
        segment_id = generate_segment_id(
            namespace=self.namespace,
            source_uri=ir.source_uri,
            provenance_key=provenance_key,
            text=chunk["content"]
        )

        # Create segment
        segment = ResourceSegment(
            id=segment_id,
            ir_id=ir.id,
            segment_index=segment_index,
            text=chunk["content"],
            provenance=provenance,
            text_hash=generate_text_hash(chunk["content"])
        )

        return segment

    def _extract_and_link_entities(self, segments):
        """
        Extract entities from segments and create links.

        Args:
            segments: List of ResourceSegments

        Returns:
            List of unique Entities
        """
        all_entities = []
        all_links = []

        for segment in segments:
            # Extract entities
            extracted = self.entity_extractor.extract(segment.text)

            for ext_entity in extracted:
                # Get or create entity
                entity = self.new_store.get_entity_by_name(
                    namespace=self.namespace,
                    entity_type=ext_entity.type,
                    name=ext_entity.name
                )

                if not entity:
                    entity = Entity(
                        id=generate_entity_id(),
                        namespace=self.namespace,
                        type=ext_entity.type,
                        name=ext_entity.name,
                        aliases=ext_entity.aliases,
                        metadata=ext_entity.metadata
                    )
                    entity = self.new_store.upsert_entity(entity)
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
            self.new_store.bulk_add_entity_links(all_links)

        return all_entities


def main():
    parser = argparse.ArgumentParser(
        description="Migrate legacy chunk-based data to knowledge-centric KOS"
    )
    parser.add_argument(
        "--old-db",
        required=True,
        help="Path to old DuckDB database with chunks table"
    )
    parser.add_argument(
        "--new-db",
        required=True,
        help="Path to new KOS database (will be created if doesn't exist)"
    )
    parser.add_argument(
        "--namespace",
        default="legacy",
        help="Namespace for migrated data (default: legacy)"
    )

    args = parser.parse_args()

    # Validate old DB exists
    if not Path(args.old_db).exists():
        logger.error(f"Old database not found: {args.old_db}")
        return 1

    # Run migration
    migrator = LegacyMigrator(
        old_db_path=args.old_db,
        new_db_path=args.new_db,
        namespace=args.namespace
    )

    try:
        migrator.connect()
        migrator.migrate()
        logger.info("Migration successful!")
        return 0

    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        return 1

    finally:
        migrator.close()


if __name__ == "__main__":
    exit(main())

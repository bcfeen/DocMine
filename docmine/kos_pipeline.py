"""Knowledge-centric pipeline (KOS) - new main API."""

import logging
from pathlib import Path
from typing import List, Dict, Optional, Any

import numpy as np
from tqdm import tqdm
from sentence_transformers import SentenceTransformer

from docmine.storage.knowledge_store import KnowledgeStore
from docmine.ingest.knowledge_pipeline import KnowledgeIngestionPipeline
from docmine.search.exact_recall import ExactRecall
from docmine.extraction import RegexEntityExtractor, BaseEntityExtractor
from docmine.models import Entity

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class KOSPipeline:
    """
    Knowledge Organization System (KOS) Pipeline.

    This is the new knowledge-centric API that replaces the old chunk-based
    PDFPipeline. It provides:

    1. Stable IDs (idempotent ingestion)
    2. Provenance tracking
    3. Entity extraction and linking
    4. Exact recall (find ALL mentions of an entity)
    5. Semantic search (with provenance)
    6. Multi-corpus support (namespaces)
    """

    def __init__(
        self,
        storage_path: str = "knowledge_kos.duckdb",
        namespace: str = "default",
        embedding_model: str = "sentence-transformers/all-mpnet-base-v2",
        entity_extractor: Optional[BaseEntityExtractor] = None,
        sentences_per_segment: int = 3
    ):
        """
        Initialize the KOS pipeline.

        Args:
            storage_path: Path to DuckDB database file
            namespace: Default namespace for operations
            embedding_model: Name of the sentence transformer model
            entity_extractor: Custom entity extractor (default: RegexEntityExtractor)
            sentences_per_segment: Sentences per segment (default: 3)
        """
        self.namespace = namespace
        self.store = KnowledgeStore(db_path=storage_path)

        # Initialize embedding model
        self.embedding_model = SentenceTransformer(embedding_model)
        self.embedding_model_name = embedding_model

        # Initialize ingestion pipeline
        extractor = entity_extractor or RegexEntityExtractor()
        self.ingestion = KnowledgeIngestionPipeline(
            store=self.store,
            entity_extractor=extractor,
            sentences_per_segment=sentences_per_segment
        )

        # Initialize exact recall
        self.exact_recall = ExactRecall(store=self.store)

        logger.info(f"KOSPipeline initialized (namespace='{namespace}', storage={storage_path})")

    # ============================================================================
    # Ingestion methods
    # ============================================================================

    def ingest_file(
        self,
        file_path: str,
        namespace: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> int:
        """
        Ingest a file into the knowledge base.

        Supports PDF, Markdown, and plain text files.
        Idempotent: re-ingesting the same file won't create duplicates.

        Args:
            file_path: Path to the file
            namespace: Namespace (uses default if not specified)
            metadata: Optional metadata dict

        Returns:
            Number of segments created

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file type is not supported
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        ns = namespace or self.namespace
        suffix = path.suffix.lower()

        try:
            if suffix == '.pdf':
                ir, segments, entities = self.ingestion.ingest_pdf(path, ns, metadata)
            elif suffix == '.md':
                ir, segments, entities = self.ingestion.ingest_markdown(path, ns, metadata)
            elif suffix == '.txt':
                ir, segments, entities = self.ingestion.ingest_text(path, ns, metadata)
            else:
                raise ValueError(f"Unsupported file type: {suffix}")

            # Generate embeddings for new segments
            if segments:
                self._embed_segments(segments)

            logger.info(f"Ingested {file_path}: {len(segments)} segments, {len(entities)} entities")
            return len(segments)

        except Exception as e:
            logger.error(f"Error ingesting {file_path}: {e}")
            raise

    def ingest_directory(
        self,
        directory: str,
        pattern: str = "*.pdf",
        namespace: Optional[str] = None,
        recursive: bool = True
    ) -> int:
        """
        Ingest all matching files from a directory.

        Args:
            directory: Path to directory
            pattern: Glob pattern (default: "*.pdf")
            namespace: Namespace (uses default if not specified)
            recursive: Recursive search (default: True)

        Returns:
            Total number of segments ingested
        """
        dir_path = Path(directory)
        files = list(dir_path.rglob(pattern)) if recursive else list(dir_path.glob(pattern))

        if not files:
            logger.warning(f"No files found in {directory} matching {pattern}")
            return 0

        logger.info(f"Found {len(files)} files to ingest")

        ns = namespace or self.namespace
        total_segments = 0

        for file_path in tqdm(files, desc="Ingesting files"):
            try:
                count = self.ingest_file(str(file_path), namespace=ns)
                total_segments += count
            except Exception as e:
                logger.error(f"Failed to ingest {file_path}: {e}")
                continue

        logger.info(f"Ingested {total_segments} total segments from {len(files)} files")
        return total_segments

    def reingest_changed(self, namespace: Optional[str] = None) -> int:
        """
        Re-ingest only files that have changed (based on content hash).

        Args:
            namespace: Namespace (uses default if not specified)

        Returns:
            Number of files re-ingested
        """
        ns = namespace or self.namespace
        return self.ingestion.reingest_changed(ns)

    def _embed_segments(self, segments: List[Any]):
        """
        Generate and store embeddings for segments.

        Args:
            segments: List of ResourceSegments
        """
        # Check which segments already have embeddings
        to_embed = []
        for seg in segments:
            if not self.store.get_embedding(seg.id):
                to_embed.append(seg)

        if not to_embed:
            logger.info("All segments already have embeddings")
            return

        # Generate embeddings
        logger.info(f"Generating embeddings for {len(to_embed)} segments...")
        texts = [seg.text for seg in to_embed]
        embeddings = self.embedding_model.encode(
            texts,
            show_progress_bar=True,
            convert_to_numpy=True
        )

        # Store embeddings
        segment_ids = [seg.id for seg in to_embed]
        self.store.bulk_add_embeddings(segment_ids, self.embedding_model_name, embeddings)
        logger.info(f"Stored {len(to_embed)} embeddings")

    # ============================================================================
    # Search methods
    # ============================================================================

    def search(
        self,
        query: str,
        top_k: int = 5,
        namespace: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Semantic search for relevant segments.

        Returns segments with full provenance information.

        Args:
            query: Search query string
            top_k: Number of results to return
            namespace: Namespace filter (uses default if not specified)

        Returns:
            List of result dicts with text, provenance, source_uri, score
        """
        ns = namespace or self.namespace

        # Generate query embedding
        query_embedding = self.embedding_model.encode([query], convert_to_numpy=True)[0]

        # Search
        results = self.store.search_by_embedding(
            query_embedding=query_embedding,
            top_k=top_k,
            namespace=ns
        )

        return results

    def search_entity(
        self,
        entity_name: str,
        entity_type: Optional[str] = None,
        namespace: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Exact recall: find ALL segments mentioning an entity.

        Unlike semantic search, this is guaranteed to be complete.

        Args:
            entity_name: Entity name to search for
            entity_type: Optional entity type filter
            namespace: Namespace (uses default if not specified)

        Returns:
            List of all segments mentioning the entity
        """
        ns = namespace or self.namespace
        return self.exact_recall.search_entity_by_name(entity_name, ns, entity_type)

    # ============================================================================
    # Entity methods
    # ============================================================================

    def get_entity(
        self,
        name: str,
        entity_type: Optional[str] = None,
        namespace: Optional[str] = None
    ) -> Optional[Entity]:
        """
        Get an entity by name.

        Args:
            name: Entity name
            entity_type: Optional type filter
            namespace: Namespace (uses default if not specified)

        Returns:
            Entity if found, None otherwise
        """
        ns = namespace or self.namespace
        return self.exact_recall.get_entity(name, ns, entity_type)

    def list_entities(
        self,
        entity_type: Optional[str] = None,
        namespace: Optional[str] = None,
        min_mentions: int = 1
    ) -> List[Dict[str, Any]]:
        """
        List all entities with mention counts.

        Args:
            entity_type: Optional type filter
            namespace: Namespace (uses default if not specified)
            min_mentions: Minimum mention count filter

        Returns:
            List of entity dicts sorted by mention count
        """
        ns = namespace or self.namespace
        return self.exact_recall.list_entities(ns, entity_type, min_mentions)

    def get_segments_for_entity(
        self,
        entity_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get all segments linked to an entity.

        Args:
            entity_id: Entity ID

        Returns:
            List of segments with metadata
        """
        return self.exact_recall.get_all_segments_for_entity(entity_id)

    # ============================================================================
    # Information Resource methods
    # ============================================================================

    def list_sources(self, namespace: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all information resources (sources).

        Args:
            namespace: Namespace filter (uses default if not specified)

        Returns:
            List of IR dicts
        """
        ns = namespace or self.namespace
        irs = self.store.list_irs(namespace=ns)

        return [
            {
                "id": ir.id,
                "source_uri": ir.source_uri,
                "source_type": ir.source_type,
                "content_hash": ir.content_hash,
                "metadata": ir.metadata,
                "created_at": ir.created_at.isoformat() if ir.created_at else None,
            }
            for ir in irs
        ]

    def get_segments_for_source(self, source_uri: str, namespace: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all segments for a source.

        Args:
            source_uri: Source URI (e.g., "file:///path/doc.pdf")
            namespace: Namespace (uses default if not specified)

        Returns:
            List of segments
        """
        ns = namespace or self.namespace
        ir = self.store.get_ir_by_uri(ns, source_uri)

        if not ir:
            logger.warning(f"Source not found: {source_uri}")
            return []

        return self.exact_recall.get_segments_for_ir(ir.id)

    # ============================================================================
    # Statistics methods
    # ============================================================================

    def count_segments(self, namespace: Optional[str] = None) -> int:
        """
        Count total segments.

        Args:
            namespace: Namespace filter (uses default if not specified)

        Returns:
            Total segment count
        """
        ns = namespace or self.namespace
        return self.store.count_segments(namespace=ns)

    def stats(self, namespace: Optional[str] = None) -> Dict[str, Any]:
        """
        Get statistics for the knowledge base.

        Args:
            namespace: Namespace filter (uses default if not specified)

        Returns:
            Stats dict
        """
        ns = namespace or self.namespace

        irs = self.store.list_irs(namespace=ns)
        entities = self.store.list_entities(namespace=ns)
        segment_count = self.store.count_segments(namespace=ns)

        return {
            "namespace": ns,
            "information_resources": len(irs),
            "segments": segment_count,
            "entities": len(entities),
            "entity_types": len(set(e.type for e in entities)),
        }

    # ============================================================================
    # Cleanup
    # ============================================================================

    def close(self):
        """Close database connection."""
        self.store.close()

    def __del__(self):
        """Cleanup: close connection."""
        try:
            self.close()
        except Exception:
            pass

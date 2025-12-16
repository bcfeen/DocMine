"""Knowledge-centric storage backend using SQLite/DuckDB."""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

import duckdb
import numpy as np

from docmine.models import (
    InformationResource,
    ResourceSegment,
    Entity,
    EntityLink,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class KnowledgeStore:
    """
    Knowledge-centric storage for InformationResources, ResourceSegments,
    Entities, and their relationships.

    This replaces the old chunk-based storage with a proper relational model
    that supports stable IDs, provenance tracking, entity extraction, and
    exact recall.
    """

    def __init__(self, db_path: str = "knowledge.duckdb"):
        """
        Initialize DuckDB connection and create schema.

        Args:
            db_path: Path to the DuckDB database file
        """
        self.db_path = db_path
        self.conn = duckdb.connect(db_path)
        self._create_schema()
        logger.info(f"KnowledgeStore initialized at {db_path}")

    def _create_schema(self):
        """Create database schema with all tables and indices."""

        # Information Resources table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS information_resources (
                id VARCHAR PRIMARY KEY,
                namespace VARCHAR NOT NULL,
                source_type VARCHAR NOT NULL,
                source_uri VARCHAR NOT NULL,
                content_hash VARCHAR NOT NULL,
                metadata_json VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(namespace, source_uri)
            )
        """)

        # Resource Segments table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS resource_segments (
                id VARCHAR PRIMARY KEY,
                ir_id VARCHAR NOT NULL,
                segment_index INTEGER NOT NULL,
                text VARCHAR NOT NULL,
                provenance_json VARCHAR NOT NULL,
                text_hash VARCHAR NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Entities table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS entities (
                id VARCHAR PRIMARY KEY,
                namespace VARCHAR NOT NULL,
                type VARCHAR NOT NULL,
                name VARCHAR NOT NULL,
                aliases_json VARCHAR,
                metadata_json VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(namespace, type, name)
            )
        """)

        # Segment-Entity Links table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS segment_entity_links (
                segment_id VARCHAR NOT NULL,
                entity_id VARCHAR NOT NULL,
                link_type VARCHAR NOT NULL,
                confidence REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(segment_id, entity_id, link_type)
            )
        """)

        # Embeddings table (separate for efficiency)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS embeddings (
                segment_id VARCHAR PRIMARY KEY,
                model VARCHAR NOT NULL,
                vector FLOAT[] NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create indices for performance
        indices = [
            "CREATE INDEX IF NOT EXISTS idx_ir_namespace ON information_resources(namespace)",
            "CREATE INDEX IF NOT EXISTS idx_ir_source_uri ON information_resources(source_uri)",
            "CREATE INDEX IF NOT EXISTS idx_segments_ir ON resource_segments(ir_id)",
            "CREATE INDEX IF NOT EXISTS idx_segments_text_hash ON resource_segments(text_hash)",
            "CREATE INDEX IF NOT EXISTS idx_entities_namespace ON entities(namespace)",
            "CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type)",
            "CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name)",
            "CREATE INDEX IF NOT EXISTS idx_links_segment ON segment_entity_links(segment_id)",
            "CREATE INDEX IF NOT EXISTS idx_links_entity ON segment_entity_links(entity_id)",
        ]

        for idx_sql in indices:
            self.conn.execute(idx_sql)

        self.conn.commit()
        logger.info("Database schema created successfully")

    # ============================================================================
    # InformationResource operations
    # ============================================================================

    def upsert_information_resource(self, ir: InformationResource) -> InformationResource:
        """
        Insert or update an InformationResource.

        If an IR with the same (namespace, source_uri) exists, update it.
        Otherwise, insert a new one.

        Args:
            ir: InformationResource to upsert

        Returns:
            The upserted InformationResource (with updated updated_at)
        """
        # Check if exists
        existing = self.get_ir_by_uri(ir.namespace, ir.source_uri)

        if existing:
            # Update existing
            ir.updated_at = datetime.utcnow()
            self.conn.execute("""
                UPDATE information_resources
                SET content_hash = ?,
                    metadata_json = ?,
                    updated_at = ?
                WHERE id = ?
            """, [ir.content_hash, ir.metadata_json, ir.updated_at, existing.id])
            ir.id = existing.id
            ir.created_at = existing.created_at
            logger.info(f"Updated IR: {ir.source_uri}")
        else:
            # Insert new
            self.conn.execute("""
                INSERT INTO information_resources
                (id, namespace, source_type, source_uri, content_hash, metadata_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                ir.id,
                ir.namespace,
                ir.source_type,
                ir.source_uri,
                ir.content_hash,
                ir.metadata_json,
                ir.created_at,
                ir.updated_at
            ])
            logger.info(f"Inserted new IR: {ir.source_uri}")

        self.conn.commit()
        return ir

    def get_ir_by_id(self, ir_id: str) -> Optional[InformationResource]:
        """Get InformationResource by ID."""
        result = self.conn.execute("""
            SELECT id, namespace, source_type, source_uri, content_hash,
                   metadata_json, created_at, updated_at
            FROM information_resources
            WHERE id = ?
        """, [ir_id]).fetchone()

        if not result:
            return None

        return InformationResource.from_metadata_json(
            metadata_json=result[5],
            id=result[0],
            namespace=result[1],
            source_type=result[2],
            source_uri=result[3],
            content_hash=result[4],
            created_at=result[6],
            updated_at=result[7]
        )

    def get_ir_by_uri(self, namespace: str, source_uri: str) -> Optional[InformationResource]:
        """Get InformationResource by namespace and source URI."""
        result = self.conn.execute("""
            SELECT id, namespace, source_type, source_uri, content_hash,
                   metadata_json, created_at, updated_at
            FROM information_resources
            WHERE namespace = ? AND source_uri = ?
        """, [namespace, source_uri]).fetchone()

        if not result:
            return None

        return InformationResource.from_metadata_json(
            metadata_json=result[5],
            id=result[0],
            namespace=result[1],
            source_type=result[2],
            source_uri=result[3],
            content_hash=result[4],
            created_at=result[6],
            updated_at=result[7]
        )

    def list_irs(self, namespace: Optional[str] = None) -> List[InformationResource]:
        """
        List all InformationResources, optionally filtered by namespace.

        Args:
            namespace: Optional namespace filter

        Returns:
            List of InformationResources
        """
        if namespace:
            results = self.conn.execute("""
                SELECT id, namespace, source_type, source_uri, content_hash,
                       metadata_json, created_at, updated_at
                FROM information_resources
                WHERE namespace = ?
                ORDER BY created_at DESC
            """, [namespace]).fetchall()
        else:
            results = self.conn.execute("""
                SELECT id, namespace, source_type, source_uri, content_hash,
                       metadata_json, created_at, updated_at
                FROM information_resources
                ORDER BY created_at DESC
            """).fetchall()

        return [
            InformationResource.from_metadata_json(
                metadata_json=row[5],
                id=row[0],
                namespace=row[1],
                source_type=row[2],
                source_uri=row[3],
                content_hash=row[4],
                created_at=row[6],
                updated_at=row[7]
            )
            for row in results
        ]

    # ============================================================================
    # ResourceSegment operations
    # ============================================================================

    def upsert_segment(self, segment: ResourceSegment) -> ResourceSegment:
        """
        Insert or update a ResourceSegment.

        Segments are idempotent by ID (deterministic hash).

        Args:
            segment: ResourceSegment to upsert

        Returns:
            The upserted ResourceSegment
        """
        # Check if exists
        existing = self.get_segment_by_id(segment.id)

        if existing:
            # Update existing
            self.conn.execute("""
                UPDATE resource_segments
                SET text = ?,
                    provenance_json = ?,
                    text_hash = ?
                WHERE id = ?
            """, [segment.text, segment.provenance_json, segment.text_hash, segment.id])
            segment.created_at = existing.created_at
        else:
            # Insert new
            self.conn.execute("""
                INSERT INTO resource_segments
                (id, ir_id, segment_index, text, provenance_json, text_hash, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, [
                segment.id,
                segment.ir_id,
                segment.segment_index,
                segment.text,
                segment.provenance_json,
                segment.text_hash,
                segment.created_at
            ])

        self.conn.commit()
        return segment

    def bulk_upsert_segments(self, segments: List[ResourceSegment]) -> int:
        """
        Bulk upsert segments (more efficient than one-by-one).

        Args:
            segments: List of ResourceSegments

        Returns:
            Number of segments upserted
        """
        for segment in segments:
            self.upsert_segment(segment)
        return len(segments)

    def get_segment_by_id(self, segment_id: str) -> Optional[ResourceSegment]:
        """Get ResourceSegment by ID."""
        result = self.conn.execute("""
            SELECT id, ir_id, segment_index, text, provenance_json, text_hash, created_at
            FROM resource_segments
            WHERE id = ?
        """, [segment_id]).fetchone()

        if not result:
            return None

        return ResourceSegment.from_provenance_json(
            provenance_json=result[4],
            id=result[0],
            ir_id=result[1],
            segment_index=result[2],
            text=result[3],
            text_hash=result[5],
            created_at=result[6]
        )

    def get_segments_for_ir(self, ir_id: str) -> List[ResourceSegment]:
        """Get all segments for an InformationResource."""
        results = self.conn.execute("""
            SELECT id, ir_id, segment_index, text, provenance_json, text_hash, created_at
            FROM resource_segments
            WHERE ir_id = ?
            ORDER BY segment_index
        """, [ir_id]).fetchall()

        return [
            ResourceSegment.from_provenance_json(
                provenance_json=row[4],
                id=row[0],
                ir_id=row[1],
                segment_index=row[2],
                text=row[3],
                text_hash=row[5],
                created_at=row[6]
            )
            for row in results
        ]

    def count_segments(self, namespace: Optional[str] = None) -> int:
        """
        Count total segments, optionally filtered by namespace.

        Args:
            namespace: Optional namespace filter

        Returns:
            Total segment count
        """
        if namespace:
            result = self.conn.execute("""
                SELECT COUNT(*)
                FROM resource_segments rs
                JOIN information_resources ir ON rs.ir_id = ir.id
                WHERE ir.namespace = ?
            """, [namespace]).fetchone()
        else:
            result = self.conn.execute("""
                SELECT COUNT(*) FROM resource_segments
            """).fetchone()

        return result[0] if result else 0

    # ============================================================================
    # Entity operations
    # ============================================================================

    def upsert_entity(self, entity: Entity) -> Entity:
        """
        Insert or update an Entity.

        If an entity with the same (namespace, type, name) exists, update it.

        Args:
            entity: Entity to upsert

        Returns:
            The upserted Entity
        """
        # Check if exists
        existing = self.get_entity_by_name(entity.namespace, entity.type, entity.name)

        if existing:
            # Update existing
            entity.updated_at = datetime.utcnow()
            self.conn.execute("""
                UPDATE entities
                SET aliases_json = ?,
                    metadata_json = ?,
                    updated_at = ?
                WHERE id = ?
            """, [entity.aliases_json, entity.metadata_json, entity.updated_at, existing.id])
            entity.id = existing.id
            entity.created_at = existing.created_at
        else:
            # Insert new
            self.conn.execute("""
                INSERT INTO entities
                (id, namespace, type, name, aliases_json, metadata_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                entity.id,
                entity.namespace,
                entity.type,
                entity.name,
                entity.aliases_json,
                entity.metadata_json,
                entity.created_at,
                entity.updated_at
            ])

        self.conn.commit()
        return entity

    def get_entity_by_id(self, entity_id: str) -> Optional[Entity]:
        """Get Entity by ID."""
        result = self.conn.execute("""
            SELECT id, namespace, type, name, aliases_json, metadata_json, created_at, updated_at
            FROM entities
            WHERE id = ?
        """, [entity_id]).fetchone()

        if not result:
            return None

        return Entity.from_json(
            aliases_json=result[4],
            metadata_json=result[5],
            id=result[0],
            namespace=result[1],
            type=result[2],
            name=result[3],
            created_at=result[6],
            updated_at=result[7]
        )

    def get_entity_by_name(
        self,
        namespace: str,
        entity_type: str,
        name: str
    ) -> Optional[Entity]:
        """Get Entity by namespace, type, and name."""
        result = self.conn.execute("""
            SELECT id, namespace, type, name, aliases_json, metadata_json, created_at, updated_at
            FROM entities
            WHERE namespace = ? AND type = ? AND name = ?
        """, [namespace, entity_type, name]).fetchone()

        if not result:
            return None

        return Entity.from_json(
            aliases_json=result[4],
            metadata_json=result[5],
            id=result[0],
            namespace=result[1],
            type=result[2],
            name=result[3],
            created_at=result[6],
            updated_at=result[7]
        )

    def list_entities(
        self,
        namespace: Optional[str] = None,
        entity_type: Optional[str] = None
    ) -> List[Entity]:
        """
        List entities, optionally filtered by namespace and/or type.

        Args:
            namespace: Optional namespace filter
            entity_type: Optional type filter

        Returns:
            List of Entities
        """
        query = """
            SELECT id, namespace, type, name, aliases_json, metadata_json, created_at, updated_at
            FROM entities
            WHERE 1=1
        """
        params = []

        if namespace:
            query += " AND namespace = ?"
            params.append(namespace)

        if entity_type:
            query += " AND type = ?"
            params.append(entity_type)

        query += " ORDER BY name"

        results = self.conn.execute(query, params).fetchall()

        return [
            Entity.from_json(
                aliases_json=row[4],
                metadata_json=row[5],
                id=row[0],
                namespace=row[1],
                type=row[2],
                name=row[3],
                created_at=row[6],
                updated_at=row[7]
            )
            for row in results
        ]

    # ============================================================================
    # EntityLink operations
    # ============================================================================

    def add_entity_link(self, link: EntityLink) -> EntityLink:
        """
        Add a segment-entity link.

        Uses INSERT OR REPLACE to handle duplicates.

        Args:
            link: EntityLink to add

        Returns:
            The added EntityLink
        """
        self.conn.execute("""
            INSERT OR REPLACE INTO segment_entity_links
            (segment_id, entity_id, link_type, confidence, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, [
            link.segment_id,
            link.entity_id,
            link.link_type,
            link.confidence,
            link.created_at
        ])
        self.conn.commit()
        return link

    def bulk_add_entity_links(self, links: List[EntityLink]) -> int:
        """
        Bulk add entity links.

        Args:
            links: List of EntityLinks

        Returns:
            Number of links added
        """
        for link in links:
            self.add_entity_link(link)
        return len(links)

    def get_entities_for_segment(self, segment_id: str) -> List[Tuple[Entity, EntityLink]]:
        """
        Get all entities linked to a segment.

        Args:
            segment_id: Segment ID

        Returns:
            List of (Entity, EntityLink) tuples
        """
        results = self.conn.execute("""
            SELECT e.id, e.namespace, e.type, e.name, e.aliases_json, e.metadata_json,
                   e.created_at, e.updated_at,
                   sel.link_type, sel.confidence, sel.created_at
            FROM entities e
            JOIN segment_entity_links sel ON e.id = sel.entity_id
            WHERE sel.segment_id = ?
        """, [segment_id]).fetchall()

        return [
            (
                Entity.from_json(
                    aliases_json=row[4],
                    metadata_json=row[5],
                    id=row[0],
                    namespace=row[1],
                    type=row[2],
                    name=row[3],
                    created_at=row[6],
                    updated_at=row[7]
                ),
                EntityLink(
                    segment_id=segment_id,
                    entity_id=row[0],
                    link_type=row[8],
                    confidence=row[9],
                    created_at=row[10]
                )
            )
            for row in results
        ]

    def get_segments_for_entity(self, entity_id: str) -> List[Tuple[ResourceSegment, EntityLink]]:
        """
        Get all segments linked to an entity.

        This is the EXACT RECALL mechanism.

        Args:
            entity_id: Entity ID

        Returns:
            List of (ResourceSegment, EntityLink) tuples
        """
        results = self.conn.execute("""
            SELECT rs.id, rs.ir_id, rs.segment_index, rs.text, rs.provenance_json,
                   rs.text_hash, rs.created_at,
                   sel.link_type, sel.confidence, sel.created_at
            FROM resource_segments rs
            JOIN segment_entity_links sel ON rs.id = sel.segment_id
            WHERE sel.entity_id = ?
            ORDER BY rs.created_at
        """, [entity_id]).fetchall()

        return [
            (
                ResourceSegment.from_provenance_json(
                    provenance_json=row[4],
                    id=row[0],
                    ir_id=row[1],
                    segment_index=row[2],
                    text=row[3],
                    text_hash=row[5],
                    created_at=row[6]
                ),
                EntityLink(
                    segment_id=row[0],
                    entity_id=entity_id,
                    link_type=row[7],
                    confidence=row[8],
                    created_at=row[9]
                )
            )
            for row in results
        ]

    # ============================================================================
    # Embedding operations
    # ============================================================================

    def add_embedding(self, segment_id: str, model: str, vector: np.ndarray):
        """
        Add an embedding for a segment.

        Args:
            segment_id: Segment ID
            model: Model name/version
            vector: Embedding vector
        """
        self.conn.execute("""
            INSERT OR REPLACE INTO embeddings
            (segment_id, model, vector, created_at)
            VALUES (?, ?, ?, ?)
        """, [segment_id, model, vector.tolist(), datetime.utcnow()])
        self.conn.commit()

    def bulk_add_embeddings(
        self,
        segment_ids: List[str],
        model: str,
        vectors: np.ndarray
    ):
        """
        Bulk add embeddings.

        Args:
            segment_ids: List of segment IDs
            model: Model name/version
            vectors: Numpy array of embeddings
        """
        for seg_id, vec in zip(segment_ids, vectors):
            self.add_embedding(seg_id, model, vec)

    def get_embedding(self, segment_id: str) -> Optional[Tuple[str, np.ndarray]]:
        """
        Get embedding for a segment.

        Args:
            segment_id: Segment ID

        Returns:
            (model, vector) tuple, or None if not found
        """
        result = self.conn.execute("""
            SELECT model, vector
            FROM embeddings
            WHERE segment_id = ?
        """, [segment_id]).fetchone()

        if not result:
            return None

        return (result[0], np.array(result[1]))

    def search_by_embedding(
        self,
        query_embedding: np.ndarray,
        top_k: int = 5,
        namespace: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for segments by embedding similarity.

        Args:
            query_embedding: Query embedding vector
            top_k: Number of results to return
            namespace: Optional namespace filter

        Returns:
            List of result dictionaries with segment, score, and metadata
        """
        # Fetch all embeddings (with optional namespace filter)
        if namespace:
            query = """
                SELECT e.segment_id, e.vector, rs.text, rs.provenance_json,
                       ir.source_uri, ir.namespace
                FROM embeddings e
                JOIN resource_segments rs ON e.segment_id = rs.id
                JOIN information_resources ir ON rs.ir_id = ir.id
                WHERE ir.namespace = ?
            """
            results = self.conn.execute(query, [namespace]).fetchall()
        else:
            query = """
                SELECT e.segment_id, e.vector, rs.text, rs.provenance_json,
                       ir.source_uri, ir.namespace
                FROM embeddings e
                JOIN resource_segments rs ON e.segment_id = rs.id
                JOIN information_resources ir ON rs.ir_id = ir.id
            """
            results = self.conn.execute(query).fetchall()

        if not results:
            return []

        # Compute cosine similarities
        similarities = []
        for row in results:
            segment_id, vector, text, provenance_json, source_uri, ns = row
            vector_array = np.array(vector)

            # Cosine similarity
            dot_product = np.dot(query_embedding, vector_array)
            norm_query = np.linalg.norm(query_embedding)
            norm_vector = np.linalg.norm(vector_array)
            similarity = dot_product / (norm_query * norm_vector)

            similarities.append({
                "segment_id": segment_id,
                "text": text,
                "provenance": provenance_json,
                "source_uri": source_uri,
                "namespace": ns,
                "score": float(similarity)
            })

        # Sort by similarity descending
        similarities.sort(key=lambda x: x["score"], reverse=True)
        return similarities[:top_k]

    # ============================================================================
    # Utility methods
    # ============================================================================

    def close(self):
        """Close the database connection."""
        self.conn.close()
        logger.info("KnowledgeStore connection closed")

    def __del__(self):
        """Cleanup: close connection."""
        try:
            self.close()
        except Exception:
            pass

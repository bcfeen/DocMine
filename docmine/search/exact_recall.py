"""Exact recall retrieval for entity-based queries."""

import logging
from typing import List, Dict, Any, Optional, Tuple

from docmine.storage.knowledge_store import KnowledgeStore
from docmine.models import Entity, ResourceSegment, EntityLink

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ExactRecall:
    """
    Exact recall retrieval system.

    Unlike semantic search (which is fuzzy and incomplete), exact recall
    guarantees finding ALL segments linked to an entity.

    This is critical for:
    - Regulatory compliance (find all mentions)
    - Complete provenance tracking
    - Verification that semantic search didn't miss anything
    """

    def __init__(self, store: KnowledgeStore):
        """
        Initialize exact recall system.

        Args:
            store: KnowledgeStore instance
        """
        self.store = store
        logger.info("ExactRecall initialized")

    def get_entity(
        self,
        name: str,
        namespace: str,
        entity_type: Optional[str] = None
    ) -> Optional[Entity]:
        """
        Get an entity by name.

        Args:
            name: Entity name
            namespace: Namespace
            entity_type: Optional type filter

        Returns:
            Entity if found, None otherwise
        """
        if entity_type:
            return self.store.get_entity_by_name(namespace, entity_type, name)
        else:
            # Search across all types
            entities = self.store.list_entities(namespace=namespace)
            for entity in entities:
                if entity.name == name or name in entity.aliases:
                    return entity
            return None

    def get_all_segments_for_entity(
        self,
        entity_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get ALL segments that mention an entity.

        This is the core exact recall operation. It returns every segment
        linked to the entity, regardless of semantic similarity.

        Args:
            entity_id: Entity ID

        Returns:
            List of segment dicts with full metadata
        """
        results = self.store.get_segments_for_entity(entity_id)

        segments_with_metadata = []
        for segment, link in results:
            # Get the parent IR
            ir = self.store.get_ir_by_id(segment.ir_id)

            segments_with_metadata.append({
                "segment_id": segment.id,
                "text": segment.text,
                "provenance": segment.provenance,
                "source_uri": ir.source_uri if ir else None,
                "namespace": ir.namespace if ir else None,
                "link_type": link.link_type,
                "confidence": link.confidence,
            })

        logger.info(f"Exact recall found {len(segments_with_metadata)} segments for entity {entity_id}")
        return segments_with_metadata

    def search_entity_by_name(
        self,
        name: str,
        namespace: str,
        entity_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Find all segments mentioning an entity (by name).

        High-level wrapper that combines entity lookup + segment retrieval.

        Args:
            name: Entity name
            namespace: Namespace
            entity_type: Optional type filter

        Returns:
            List of segment dicts

        Example:
            >>> recall = ExactRecall(store)
            >>> segments = recall.search_entity_by_name("CCNA001", "lab_alpha", "strain")
            >>> print(f"Found {len(segments)} segments mentioning CCNA001")
        """
        entity = self.get_entity(name, namespace, entity_type)

        if not entity:
            logger.warning(f"Entity not found: {name} (namespace={namespace}, type={entity_type})")
            return []

        return self.get_all_segments_for_entity(entity.id)

    def list_entities(
        self,
        namespace: str,
        entity_type: Optional[str] = None,
        min_mentions: int = 1
    ) -> List[Dict[str, Any]]:
        """
        List all entities in a namespace with mention counts.

        Args:
            namespace: Namespace
            entity_type: Optional type filter
            min_mentions: Minimum mention count filter

        Returns:
            List of entity dicts with metadata
        """
        entities = self.store.list_entities(namespace=namespace, entity_type=entity_type)

        entity_stats = []
        for entity in entities:
            segments = self.store.get_segments_for_entity(entity.id)
            mention_count = len(segments)

            if mention_count >= min_mentions:
                entity_stats.append({
                    "id": entity.id,
                    "type": entity.type,
                    "name": entity.name,
                    "aliases": entity.aliases,
                    "mention_count": mention_count,
                    "metadata": entity.metadata,
                })

        # Sort by mention count descending
        entity_stats.sort(key=lambda x: x["mention_count"], reverse=True)

        logger.info(f"Found {len(entity_stats)} entities in namespace '{namespace}'")
        return entity_stats

    def get_entities_for_segment(
        self,
        segment_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get all entities mentioned in a segment.

        Args:
            segment_id: Segment ID

        Returns:
            List of entity dicts with link metadata
        """
        results = self.store.get_entities_for_segment(segment_id)

        entities_with_links = []
        for entity, link in results:
            entities_with_links.append({
                "entity_id": entity.id,
                "type": entity.type,
                "name": entity.name,
                "aliases": entity.aliases,
                "link_type": link.link_type,
                "confidence": link.confidence,
            })

        return entities_with_links

    def get_segments_for_ir(
        self,
        ir_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get all segments for an InformationResource.

        Args:
            ir_id: InformationResource ID

        Returns:
            List of segment dicts
        """
        segments = self.store.get_segments_for_ir(ir_id)
        ir = self.store.get_ir_by_id(ir_id)

        return [
            {
                "segment_id": seg.id,
                "text": seg.text,
                "provenance": seg.provenance,
                "source_uri": ir.source_uri if ir else None,
                "segment_index": seg.segment_index,
            }
            for seg in segments
        ]

    def compare_with_semantic_search(
        self,
        entity_name: str,
        namespace: str,
        semantic_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Compare exact recall with semantic search results.

        Useful for debugging and validation.

        Args:
            entity_name: Entity to search for
            namespace: Namespace
            semantic_results: Results from semantic search

        Returns:
            Comparison dict with statistics
        """
        # Get exact recall results
        exact_results = self.search_entity_by_name(entity_name, namespace)

        # Extract segment IDs
        exact_ids = {r["segment_id"] for r in exact_results}
        semantic_ids = {r.get("segment_id") for r in semantic_results if "segment_id" in r}

        # Calculate overlap
        overlap = exact_ids & semantic_ids
        missed_by_semantic = exact_ids - semantic_ids
        false_positives = semantic_ids - exact_ids

        return {
            "entity_name": entity_name,
            "exact_count": len(exact_ids),
            "semantic_count": len(semantic_ids),
            "overlap_count": len(overlap),
            "missed_by_semantic_count": len(missed_by_semantic),
            "false_positive_count": len(false_positives),
            "recall": len(overlap) / len(exact_ids) if exact_ids else 0.0,
            "precision": len(overlap) / len(semantic_ids) if semantic_ids else 0.0,
            "missed_segments": list(missed_by_semantic)[:10],  # Show first 10
        }

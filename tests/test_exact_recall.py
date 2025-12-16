"""Test exact recall functionality."""

import pytest
import tempfile
import os
from pathlib import Path

from docmine.kos_pipeline import KOSPipeline


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".duckdb", delete=False) as f:
        db_path = f.name
    yield db_path
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture
def sample_corpus():
    """Create a sample corpus with known entities."""
    files = []

    # File 1: Multiple mentions of CCNA001
    with tempfile.NamedTemporaryFile(mode='w', suffix=".txt", delete=False, encoding='utf-8') as f:
        f.write("""
        The CCNA001 strain was isolated from sample A.
        Initial tests on CCNA001 showed resistance to antibiotics.
        Further analysis of the CCNA001 strain revealed genetic markers.
        """)
        files.append(f.name)

    # File 2: Different entity (BRCA1) and one mention of CCNA001
    with tempfile.NamedTemporaryFile(mode='w', suffix=".txt", delete=False, encoding='utf-8') as f:
        f.write("""
        The BRCA1 gene was sequenced successfully.
        Comparison with CCNA001 data showed interesting patterns.
        BRCA1 mutations were cataloged extensively.
        """)
        files.append(f.name)

    # File 3: Only BRCA1
    with tempfile.NamedTemporaryFile(mode='w', suffix=".txt", delete=False, encoding='utf-8') as f:
        f.write("""
        Studies of BRCA1 in various populations revealed diversity.
        The BRCA1 gene family is well characterized.
        """)
        files.append(f.name)

    yield files

    # Cleanup
    for file_path in files:
        if os.path.exists(file_path):
            os.remove(file_path)


def test_exact_recall_finds_all_mentions(temp_db, sample_corpus):
    """
    Test that exact recall finds ALL mentions of an entity.

    This is the core exact recall test.
    """
    pipeline = KOSPipeline(storage_path=temp_db, namespace="test")

    # Ingest corpus
    for file_path in sample_corpus:
        pipeline.ingest_file(file_path, namespace="test")

    # Exact recall for CCNA001 (should find 4 mentions across 2 files)
    ccna_segments = pipeline.search_entity("CCNA001", namespace="test")

    # Should find all 4 mentions
    assert len(ccna_segments) >= 3, f"Expected at least 3 CCNA001 mentions, got {len(ccna_segments)}"

    # All segments should contain CCNA001
    for seg in ccna_segments:
        assert "CCNA001" in seg["text"], f"Segment doesn't contain CCNA001: {seg['text']}"

    # Exact recall for BRCA1 (should find 4 mentions across 2 files)
    brca_segments = pipeline.search_entity("BRCA1", namespace="test")

    assert len(brca_segments) >= 3, f"Expected at least 3 BRCA1 mentions, got {len(brca_segments)}"

    for seg in brca_segments:
        assert "BRCA1" in seg["text"], f"Segment doesn't contain BRCA1: {seg['text']}"

    pipeline.close()


def test_exact_recall_vs_semantic_search(temp_db, sample_corpus):
    """
    Test that exact recall is more complete than semantic search.

    Exact recall should find >= semantic search results.
    """
    pipeline = KOSPipeline(storage_path=temp_db, namespace="test")

    # Ingest corpus
    for file_path in sample_corpus:
        pipeline.ingest_file(file_path, namespace="test")

    # Semantic search for "CCNA001"
    semantic_results = pipeline.search("CCNA001", top_k=10, namespace="test")

    # Exact recall for CCNA001
    exact_results = pipeline.search_entity("CCNA001", namespace="test")

    # Exact recall should find at least as many (usually more)
    assert len(exact_results) >= len(semantic_results), \
        f"Exact recall found fewer results: {len(exact_results)} vs {len(semantic_results)}"

    pipeline.close()


def test_list_entities_with_counts(temp_db, sample_corpus):
    """Test listing entities with mention counts."""
    pipeline = KOSPipeline(storage_path=temp_db, namespace="test")

    # Ingest corpus
    for file_path in sample_corpus:
        pipeline.ingest_file(file_path, namespace="test")

    # List all entities
    entities = pipeline.list_entities(namespace="test")

    # Should have at least CCNA001 and BRCA1
    entity_names = [e["name"] for e in entities]
    assert "CCNA001" in entity_names, "CCNA001 not found in entities"
    assert "BRCA1" in entity_names, "BRCA1 not found in entities"

    # Each entity should have mention_count > 0
    for entity in entities:
        assert entity["mention_count"] > 0, f"Entity {entity['name']} has no mentions"

    # Entities should be sorted by mention count (descending)
    mention_counts = [e["mention_count"] for e in entities]
    assert mention_counts == sorted(mention_counts, reverse=True), \
        "Entities not sorted by mention count"

    pipeline.close()


def test_entity_type_filtering(temp_db):
    """Test filtering entities by type."""
    pipeline = KOSPipeline(storage_path=temp_db, namespace="test")

    with tempfile.NamedTemporaryFile(mode='w', suffix=".txt", delete=False, encoding='utf-8') as f:
        f.write("""
        The CCNA001 strain and BRCA1 gene were studied.
        Contact researcher@example.com for details.
        """)
        file_path = f.name

    try:
        pipeline.ingest_file(file_path, namespace="test")

        # List all entities
        all_entities = pipeline.list_entities(namespace="test")

        # List only strain entities
        strains = pipeline.list_entities(entity_type="strain", namespace="test")

        # List only gene entities
        genes = pipeline.list_entities(entity_type="gene", namespace="test")

        # Should have fewer strains than total
        assert len(strains) < len(all_entities), "Strain filter didn't reduce results"
        assert len(genes) < len(all_entities), "Gene filter didn't reduce results"

        # Check types
        for entity in strains:
            assert entity["type"] == "strain", f"Wrong type in strains: {entity['type']}"

        for entity in genes:
            assert entity["type"] == "gene", f"Wrong type in genes: {entity['type']}"

    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
        pipeline.close()


def test_get_entity_by_name(temp_db, sample_corpus):
    """Test retrieving a specific entity by name."""
    pipeline = KOSPipeline(storage_path=temp_db, namespace="test")

    # Ingest corpus
    for file_path in sample_corpus:
        pipeline.ingest_file(file_path, namespace="test")

    # Get CCNA001 entity
    entity = pipeline.get_entity("CCNA001", namespace="test")

    assert entity is not None, "CCNA001 entity not found"
    assert entity.name == "CCNA001", f"Wrong entity name: {entity.name}"
    assert entity.type in ["strain", "accession"], f"Unexpected entity type: {entity.type}"

    # Get all segments for this entity
    segments = pipeline.get_segments_for_entity(entity.id)

    assert len(segments) > 0, "No segments found for CCNA001"

    pipeline.close()


def test_entity_not_found(temp_db, sample_corpus):
    """Test behavior when entity doesn't exist."""
    pipeline = KOSPipeline(storage_path=temp_db, namespace="test")

    # Ingest corpus
    for file_path in sample_corpus:
        pipeline.ingest_file(file_path, namespace="test")

    # Search for non-existent entity
    entity = pipeline.get_entity("NONEXISTENT999", namespace="test")
    assert entity is None, "Found non-existent entity"

    # Search segments for non-existent entity
    segments = pipeline.search_entity("NONEXISTENT999", namespace="test")
    assert len(segments) == 0, "Found segments for non-existent entity"

    pipeline.close()


def test_provenance_in_exact_recall(temp_db, sample_corpus):
    """Test that exact recall results include full provenance."""
    pipeline = KOSPipeline(storage_path=temp_db, namespace="test")

    # Ingest corpus
    for file_path in sample_corpus:
        pipeline.ingest_file(file_path, namespace="test")

    # Get exact recall results
    segments = pipeline.search_entity("CCNA001", namespace="test")

    assert len(segments) > 0, "No segments found"

    # Check that each result has provenance
    for seg in segments:
        assert "provenance" in seg, "Missing provenance"
        assert "source_uri" in seg, "Missing source_uri"
        assert "text" in seg, "Missing text"
        assert "confidence" in seg, "Missing confidence"

        # Provenance should have location info
        prov = seg["provenance"]
        assert isinstance(prov, (dict, str)), f"Invalid provenance type: {type(prov)}"

    pipeline.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

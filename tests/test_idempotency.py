"""Test idempotent ingestion behavior."""

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
    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture
def sample_text_file():
    """Create a sample text file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix=".txt", delete=False, encoding='utf-8') as f:
        f.write("""
        The CCNA001 strain was tested under various conditions.
        Results showed significant growth in media A.
        The BRCA1 gene was also analyzed for mutations.
        No significant findings were observed in the control group.
        """)
        file_path = f.name
    yield file_path
    # Cleanup
    if os.path.exists(file_path):
        os.remove(file_path)


def test_double_ingestion_no_duplicates(temp_db, sample_text_file):
    """
    Test that ingesting the same file twice doesn't create duplicate segments.

    This is the CRITICAL idempotency test.
    """
    pipeline = KOSPipeline(storage_path=temp_db, namespace="test")

    # First ingestion
    count1 = pipeline.ingest_file(sample_text_file, namespace="test")
    total1 = pipeline.count_segments(namespace="test")

    # Second ingestion (should be idempotent)
    count2 = pipeline.ingest_file(sample_text_file, namespace="test")
    total2 = pipeline.count_segments(namespace="test")

    # Assert no duplicates created
    assert count1 == count2, f"Second ingestion returned different count: {count1} vs {count2}"
    assert total1 == total2, f"Total segment count increased: {total1} -> {total2}"
    assert total1 == count1, f"Total doesn't match individual count: {total1} vs {count1}"

    pipeline.close()


def test_triple_ingestion_stability(temp_db, sample_text_file):
    """Test that even 3 ingestions produce the same result."""
    pipeline = KOSPipeline(storage_path=temp_db, namespace="test")

    counts = []
    totals = []

    for i in range(3):
        count = pipeline.ingest_file(sample_text_file, namespace="test")
        total = pipeline.count_segments(namespace="test")
        counts.append(count)
        totals.append(total)

    # All counts should be identical
    assert len(set(counts)) == 1, f"Counts varied across ingestions: {counts}"
    assert len(set(totals)) == 1, f"Totals varied across ingestions: {totals}"

    pipeline.close()


def test_namespace_isolation(temp_db, sample_text_file):
    """Test that different namespaces are isolated."""
    pipeline = KOSPipeline(storage_path=temp_db, namespace="default")

    # Ingest into two different namespaces
    count_ns1 = pipeline.ingest_file(sample_text_file, namespace="namespace1")
    count_ns2 = pipeline.ingest_file(sample_text_file, namespace="namespace2")

    # Each namespace should have its own segments
    total_ns1 = pipeline.count_segments(namespace="namespace1")
    total_ns2 = pipeline.count_segments(namespace="namespace2")
    total_all = pipeline.store.count_segments(namespace=None)

    assert total_ns1 == count_ns1
    assert total_ns2 == count_ns2
    assert total_all == count_ns1 + count_ns2

    pipeline.close()


def test_modified_file_reingest(temp_db):
    """Test that modifying a file triggers re-segmentation."""
    pipeline = KOSPipeline(storage_path=temp_db, namespace="test")

    # Create initial file
    with tempfile.NamedTemporaryFile(mode='w', suffix=".txt", delete=False, encoding='utf-8') as f:
        f.write("The CCNA001 strain showed resistance.")
        file_path = f.name

    try:
        # First ingestion
        count1 = pipeline.ingest_file(file_path, namespace="test")

        # Modify file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("The CCNA001 strain showed resistance. Additional findings were documented.")

        # Re-ingest (should detect change via content_hash)
        count2 = pipeline.ingest_file(file_path, namespace="test")

        # Count should be different (more content = more segments)
        assert count2 > count1, f"Modified file should have more segments: {count1} vs {count2}"

    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
        pipeline.close()


def test_entity_linking_idempotency(temp_db, sample_text_file):
    """Test that entity links are not duplicated on re-ingestion."""
    pipeline = KOSPipeline(storage_path=temp_db, namespace="test")

    # Ingest twice
    pipeline.ingest_file(sample_text_file, namespace="test")
    pipeline.ingest_file(sample_text_file, namespace="test")

    # Check entities
    entities = pipeline.list_entities(namespace="test")

    # Should have unique entities (CCNA001, BRCA1)
    entity_names = [e["name"] for e in entities]
    assert len(entity_names) == len(set(entity_names)), "Duplicate entities found"

    # Check mentions for each entity
    for entity in entities:
        segments = pipeline.get_segments_for_entity(entity["id"])
        # Each entity should have consistent mention count
        assert len(segments) > 0, f"Entity {entity['name']} has no segments"

    pipeline.close()


def test_segment_id_determinism(temp_db):
    """Test that segment IDs are deterministic across separate databases."""
    # Create first database
    pipeline1 = KOSPipeline(storage_path=temp_db, namespace="test")

    with tempfile.NamedTemporaryFile(mode='w', suffix=".txt", delete=False, encoding='utf-8') as f:
        f.write("The CCNA001 strain was tested. Results were positive.")
        file_path = f.name

    try:
        # Ingest in first database
        pipeline1.ingest_file(file_path, namespace="test")

        # Get segment IDs
        segments1 = pipeline1.store.get_segments_for_ir(
            pipeline1.store.list_irs(namespace="test")[0].id
        )
        ids1 = [seg.id for seg in segments1]

        pipeline1.close()

        # Create second database
        with tempfile.NamedTemporaryFile(suffix=".duckdb", delete=False) as f:
            db_path2 = f.name

        pipeline2 = KOSPipeline(storage_path=db_path2, namespace="test")

        # Ingest same file in second database
        pipeline2.ingest_file(file_path, namespace="test")

        # Get segment IDs
        segments2 = pipeline2.store.get_segments_for_ir(
            pipeline2.store.list_irs(namespace="test")[0].id
        )
        ids2 = [seg.id for seg in segments2]

        # IDs should be identical
        assert ids1 == ids2, "Segment IDs are not deterministic across databases"

        pipeline2.close()
        if os.path.exists(db_path2):
            os.remove(db_path2)

    finally:
        if os.path.exists(file_path):
            os.remove(file_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

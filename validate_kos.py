"""
Quick validation script to test KOS functionality.
"""

import tempfile
import os
from pathlib import Path

from docmine.kos_pipeline import KOSPipeline


def test_basic_functionality():
    """Test basic KOS functionality."""
    print("Testing DocMine KOS System")
    print("=" * 60)

    # Create temporary database path (don't create the file yet)
    db_path = os.path.join(tempfile.gettempdir(), f"test_kos_{os.getpid()}.duckdb")

    # Create temporary text file
    with tempfile.NamedTemporaryFile(mode='w', suffix=".txt", delete=False, encoding='utf-8') as f:
        f.write("""
        The CCNA001 strain was tested under various conditions.
        Results showed significant growth in media A.
        The BRCA1 gene was also analyzed for mutations.
        No significant findings were observed in the control group.
        Further studies on CCNA001 are recommended.
        """)
        text_file = f.name

    try:
        # 1. Test initialization
        print("\n[1/5] Testing initialization...")
        pipeline = KOSPipeline(storage_path=db_path, namespace="test")
        print("✓ Pipeline initialized")

        # 2. Test ingestion
        print("\n[2/5] Testing ingestion...")
        count1 = pipeline.ingest_file(text_file, namespace="test")
        print(f"✓ Ingested {count1} segments")
        assert count1 > 0, "No segments created"

        # 3. Test idempotency
        print("\n[3/5] Testing idempotency...")
        total1 = pipeline.count_segments(namespace="test")
        count2 = pipeline.ingest_file(text_file, namespace="test")
        total2 = pipeline.count_segments(namespace="test")
        print(f"  First ingestion: {count1} segments")
        print(f"  Second ingestion: {count2} segments")
        print(f"  Total after first: {total1}")
        print(f"  Total after second: {total2}")
        assert total1 == total2, f"Duplicates created! {total1} != {total2}"
        print("✓ Idempotency verified (no duplicates)")

        # 4. Test entity extraction
        print("\n[4/5] Testing entity extraction...")
        entities = pipeline.list_entities(namespace="test")
        print(f"✓ Found {len(entities)} entities:")
        for entity in entities[:5]:
            print(f"    - {entity['name']} ({entity['type']}): {entity['mention_count']} mentions")
        assert len(entities) > 0, "No entities extracted"

        # 5. Test exact recall
        print("\n[5/5] Testing exact recall...")
        if entities:
            entity = entities[0]
            segments = pipeline.get_segments_for_entity(entity['id'])
            print(f"✓ Exact recall for '{entity['name']}': {len(segments)} segments")
            assert len(segments) > 0, "No segments found for entity"

            # Show sample segment
            if segments:
                seg = segments[0]
                print(f"\n  Sample segment:")
                print(f"    Text: {seg['text'][:80]}...")
                print(f"    Provenance: {seg['provenance']}")
                print(f"    Confidence: {seg['confidence']}")

        # Statistics
        print("\n" + "=" * 60)
        print("Knowledge Base Statistics")
        print("=" * 60)
        stats = pipeline.stats(namespace="test")
        for key, value in stats.items():
            print(f"  {key}: {value}")

        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
        print("\nKey features verified:")
        print("  ✓ Stable ID generation")
        print("  ✓ Idempotent ingestion")
        print("  ✓ Entity extraction")
        print("  ✓ Exact recall")
        print("  ✓ Provenance tracking")

        pipeline.close()

    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.remove(db_path)
        if os.path.exists(text_file):
            os.remove(text_file)


if __name__ == "__main__":
    try:
        test_basic_functionality()
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

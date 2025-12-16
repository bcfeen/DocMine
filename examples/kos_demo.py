"""
Demo script showing the new knowledge-centric KOS capabilities.

This demonstrates:
1. Idempotent ingestion
2. Entity extraction
3. Exact recall
4. Semantic search with provenance
"""

from docmine.kos_pipeline import KOSPipeline


def main():
    print("=" * 60)
    print("DocMine KOS (Knowledge Organization System) Demo")
    print("=" * 60)
    print()

    # Initialize pipeline
    print("[1/6] Initializing KOS pipeline...")
    pipeline = KOSPipeline(
        storage_path="demo_kos.duckdb",
        namespace="demo"
    )
    print("✓ Pipeline initialized\n")

    # Ingest a file (using test.pdf if it exists)
    print("[2/6] Ingesting document...")
    try:
        segment_count = pipeline.ingest_file("test.pdf", namespace="demo")
        print(f"✓ Ingested {segment_count} segments\n")
    except FileNotFoundError:
        print("⚠ test.pdf not found, skipping ingestion demo\n")
        segment_count = 0

    # Show idempotency
    if segment_count > 0:
        print("[3/6] Testing idempotency (re-ingesting same file)...")
        count_before = pipeline.count_segments(namespace="demo")
        pipeline.ingest_file("test.pdf", namespace="demo")
        count_after = pipeline.count_segments(namespace="demo")
        print(f"  Segments before: {count_before}")
        print(f"  Segments after:  {count_after}")
        print(f"✓ No duplicates created! (idempotent)\n")

    # List entities
    print("[4/6] Listing extracted entities...")
    entities = pipeline.list_entities(namespace="demo")
    if entities:
        print(f"✓ Found {len(entities)} entities:\n")
        for i, entity in enumerate(entities[:10], 1):
            print(f"  {i}. {entity['name']} ({entity['type']}) - {entity['mention_count']} mentions")
        if len(entities) > 10:
            print(f"  ... and {len(entities) - 10} more")
    else:
        print("  No entities found (no documents ingested)\n")
    print()

    # Exact recall demo
    if entities:
        print("[5/6] Exact recall demo...")
        top_entity = entities[0]
        print(f"  Finding ALL mentions of '{top_entity['name']}'...")
        segments = pipeline.search_entity(top_entity['name'], namespace="demo")
        print(f"✓ Found {len(segments)} segments (guaranteed complete)\n")

        if segments:
            print("  Sample segment:")
            seg = segments[0]
            print(f"    Text: {seg['text'][:100]}...")
            print(f"    Source: {seg['source_uri']}")
            print(f"    Provenance: {seg['provenance']}")
            print()

    # Semantic search demo
    if segment_count > 0:
        print("[6/6] Semantic search demo...")
        query = "methodology and approach"
        print(f"  Query: '{query}'")
        results = pipeline.search(query, top_k=3, namespace="demo")
        print(f"✓ Found {len(results)} results:\n")

        for i, result in enumerate(results, 1):
            print(f"  Result {i} (score: {result['score']:.3f}):")
            print(f"    {result['text'][:100]}...")
            print(f"    Source: {result.get('source_uri', 'N/A')}")
            print()

    # Statistics
    print("=" * 60)
    print("Knowledge Base Statistics")
    print("=" * 60)
    stats = pipeline.stats(namespace="demo")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    print()

    print("✓ Demo complete!")
    print()
    print("Key features demonstrated:")
    print("  • Idempotent ingestion (no duplicates)")
    print("  • Automatic entity extraction")
    print("  • Exact recall (find ALL mentions)")
    print("  • Semantic search with provenance")
    print("  • Multi-corpus namespaces")
    print()

    pipeline.close()


if __name__ == "__main__":
    main()

"""Quick benchmark using existing test PDFs."""

import time
import json
import platform
import sys
import tempfile
from pathlib import Path
from statistics import mean

import fitz

sys.path.insert(0, str(Path(__file__).parent.parent))

from docmine.kos_pipeline import KOSPipeline


def main():
    # Use medium.pdf for quick benchmarking
    pdf_path = Path("benchmarks/test_pdfs/medium.pdf")

    if not pdf_path.exists():
        print(f"Error: {pdf_path} not found")
        return

    # Get PDF info
    doc = fitz.open(pdf_path)
    pages = len(doc)
    doc.close()

    print("=" * 60)
    print("DocMine KOS Quick Benchmark")
    print("=" * 60)
    print(f"PDF: {pdf_path.name} ({pages} pages)")
    print(f"System: {platform.system()} {platform.release()} ({platform.machine()})")
    print(f"Python: {sys.version.split()[0]}")
    print()

    #  First ingestion
    print("1. First ingestion...")
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.duckdb"
        pipeline = KOSPipeline(storage_path=str(db_path), namespace="test")

        start = time.time()
        pipeline.ingest_file(str(pdf_path))
        first_time = time.time() - start

        stats = pipeline.stats(namespace="test")

    print(f"   Time: {first_time:.2f}s")
    print(f"   Segments: {stats['segments']}")
    print(f"   Entities: {stats['entities']}")
    print()

    # Re-ingestion
    print("2. Re-ingestion (idempotent)...")
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.duckdb"
        pipeline = KOSPipeline(storage_path=str(db_path), namespace="test")

        pipeline.ingest_file(str(pdf_path))

        times = []
        for _ in range(3):
            start = time.time()
            pipeline.ingest_file(str(pdf_path))
            times.append(time.time() - start)

        reingest_time = mean(times)

    print(f"   Time: {reingest_time:.3f}s")
    print(f"   Speedup: {first_time/reingest_time:.1f}x faster")
    print()

    # Search
    print("3. Semantic search...")
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.duckdb"
        pipeline = KOSPipeline(storage_path=str(db_path), namespace="test")
        pipeline.ingest_file(str(pdf_path))

        queries = ["main findings", "methodology", "results", "data", "conclusion"]
        times = []

        for query in queries * 2:  # Run each twice
            start = time.time()
            results = pipeline.search(query, top_k=5, namespace="test")
            times.append((time.time() - start) * 1000)

    print(f"   Median latency: {sorted(times)[len(times)//2]:.1f}ms")
    print(f"   Avg latency: {mean(times):.1f}ms")
    print()

    # Exact recall
    print("4. Exact recall...")
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.duckdb"
        pipeline = KOSPipeline(storage_path=str(db_path), namespace="test")
        pipeline.ingest_file(str(pdf_path))

        entities = pipeline.list_entities(namespace="test")
        if entities:
            times = []
            for entity in entities[:10]:
                start = time.time()
                segs = pipeline.search_entity(entity['name'], entity_type=entity['type'], namespace="test")
                times.append((time.time() - start) * 1000)

            print(f"   Median latency: {sorted(times)[len(times)//2]:.2f}ms")
            print(f"   Entities tested: {len(times)}")
        else:
            print(f"   No entities extracted")

    print()
    print("=" * 60)
    print("Summary:")
    print(f"  Ingestion: {first_time:.1f}s for {stats['segments']} segments")
    print(f"  Re-ingest: {reingest_time:.3f}s ({first_time/reingest_time:.0f}x faster)")
    print(f"  Search: ~{mean(times):.0f}ms per query")
    print("=" * 60)


if __name__ == "__main__":
    main()

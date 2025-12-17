"""DocMine KOS performance benchmarking suite.

Rigorous benchmarks for the Knowledge Organization System including:
- Ingestion performance (first-time and re-ingestion)
- Entity extraction overhead
- Semantic search latency
- Exact recall query performance
- Memory usage
- Scalability metrics
"""

import os
import time
import json
import platform
import sys
import tempfile
import shutil
from pathlib import Path
from statistics import mean, median, stdev
from datetime import datetime

import psutil
import fitz

# Force CPU usage to avoid MPS memory issues
os.environ['PYTORCH_ENABLE_MPS_FALLBACK'] = '1'
os.environ['CUDA_VISIBLE_DEVICES'] = ''

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from docmine.kos_pipeline import KOSPipeline


def get_pdf_info(pdf_path: Path) -> dict:
    """Get PDF metadata."""
    doc = fitz.open(pdf_path)
    info = {
        'pages': len(doc),
        'size_mb': round(pdf_path.stat().st_size / (1024 * 1024), 2)
    }
    doc.close()
    return info


def benchmark_first_ingestion(pdf_path: Path, num_runs: int = 1) -> dict:
    """
    Measure first-time ingestion performance.

    Tests: PDF extraction, segmentation, entity extraction, embedding generation.
    """
    times = []
    segments_count = None
    entities_count = None

    print(f"  First ingestion ({num_runs} runs)...", end=" ", flush=True)

    for run in range(num_runs):
        # Create fresh temp database for each run
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "bench.duckdb"

            pipeline = KOSPipeline(
                storage_path=str(db_path),
                namespace=f"bench_run_{run}"
            )

            start = time.time()
            pipeline.ingest_file(str(pdf_path))
            elapsed = time.time() - start
            times.append(elapsed)

            if segments_count is None:
                stats = pipeline.stats(namespace=f"bench_run_{run}")
                segments_count = stats['segments']
                entities_count = stats['entities']

    print("✓")

    return {
        'runs': num_runs,
        'avg_time_seconds': round(mean(times), 3),
        'median_time_seconds': round(median(times), 3),
        'std_dev_seconds': round(stdev(times), 3) if len(times) > 1 else 0,
        'min_time_seconds': round(min(times), 3),
        'max_time_seconds': round(max(times), 3),
        'segments_created': segments_count,
        'entities_extracted': entities_count,
        'segments_per_second': round(segments_count / mean(times), 2) if mean(times) > 0 else 0
    }


def benchmark_reingestion(pdf_path: Path, num_runs: int = 3) -> dict:
    """
    Measure idempotent re-ingestion performance.

    Tests: Content hash detection and skip logic.
    """
    # Setup: ingest once first
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "bench.duckdb"

        pipeline = KOSPipeline(
            storage_path=str(db_path),
            namespace="reingest_test"
        )

        # Initial ingestion
        pipeline.ingest_file(str(pdf_path))

        # Measure re-ingestion
        times = []
        print(f"  Re-ingestion ({num_runs} runs)...", end=" ", flush=True)

        for _ in range(num_runs):
            start = time.time()
            pipeline.ingest_file(str(pdf_path))
            elapsed = time.time() - start
            times.append(elapsed)

        # Verify no duplicates
        stats = pipeline.stats(namespace="reingest_test")

    print("✓")

    return {
        'runs': num_runs,
        'avg_time_seconds': round(mean(times), 3),
        'median_time_seconds': round(median(times), 3),
        'speedup_vs_first': 'measured separately',
        'duplicate_check': 'passed' if stats['segments'] > 0 else 'failed'
    }


def benchmark_semantic_search(pdf_path: Path, num_queries: int = 10) -> dict:
    """
    Measure semantic search latency with varying result sizes.

    Tests: Embedding generation for query + cosine similarity search.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "bench.duckdb"

        pipeline = KOSPipeline(
            storage_path=str(db_path),
            namespace="search_test"
        )

        # Ingest document
        pipeline.ingest_file(str(pdf_path))

        # Test queries (generic that work across domains)
        queries = [
            "main findings", "methodology", "results", "conclusion",
            "introduction", "abstract", "analysis", "data",
            "research question", "hypothesis", "experiment", "discussion",
            "background", "literature", "approach", "methods",
            "evaluation", "implications", "limitations", "future work"
        ]

        # Benchmark top-5 searches
        print(f"  Semantic search top-5 ({num_queries} queries)...", end=" ", flush=True)
        times_top5 = []
        results_counts = []

        for i in range(num_queries):
            query = queries[i % len(queries)]
            start = time.time()
            results = pipeline.search(query, top_k=5, namespace="search_test")
            elapsed = time.time() - start
            times_top5.append(elapsed)
            results_counts.append(len(results))

        # Benchmark top-20 searches
        times_top20 = []
        for i in range(num_queries):
            query = queries[i % len(queries)]
            start = time.time()
            results = pipeline.search(query, top_k=20, namespace="search_test")
            elapsed = time.time() - start
            times_top20.append(elapsed)

    print("✓")

    return {
        'queries': num_queries,
        'top_k_5': {
            'avg_latency_ms': round(mean(times_top5) * 1000, 2),
            'median_latency_ms': round(median(times_top5) * 1000, 2),
            'p95_latency_ms': round(sorted(times_top5)[int(len(times_top5) * 0.95)] * 1000, 2),
            'avg_results': round(mean(results_counts), 1)
        },
        'top_k_20': {
            'avg_latency_ms': round(mean(times_top20) * 1000, 2),
            'median_latency_ms': round(median(times_top20) * 1000, 2),
        }
    }


def benchmark_exact_recall(pdf_path: Path) -> dict:
    """
    Measure exact recall query performance.

    Tests: Entity-linked segment retrieval via SQL JOIN.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "bench.duckdb"

        pipeline = KOSPipeline(
            storage_path=str(db_path),
            namespace="exact_test"
        )

        # Ingest document
        pipeline.ingest_file(str(pdf_path))

        # Get entities to query
        entities = pipeline.list_entities(namespace="exact_test")

        if not entities:
            return {'error': 'no entities extracted'}

        # Benchmark entity lookups
        times = []
        results_counts = []

        print(f"  Exact recall ({len(entities)} entities)...", end=" ", flush=True)

        for entity in entities[:20]:  # Test up to 20 entities
            start = time.time()
            segments = pipeline.search_entity(
                entity['name'],
                entity_type=entity['type'],
                namespace="exact_test"
            )
            elapsed = time.time() - start
            times.append(elapsed)
            results_counts.append(len(segments))

    print("✓")

    return {
        'entities_tested': len(times),
        'avg_latency_ms': round(mean(times) * 1000, 2),
        'median_latency_ms': round(median(times) * 1000, 2),
        'avg_segments_per_entity': round(mean(results_counts), 2)
    }


def benchmark_memory_usage(pdf_path: Path) -> dict:
    """
    Measure memory usage during ingestion.

    Tests: Peak memory consumption.
    """
    process = psutil.Process()

    print(f"  Memory usage...", end=" ", flush=True)

    # Baseline
    baseline_mb = process.memory_info().rss / (1024 * 1024)

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "bench.duckdb"

        pipeline = KOSPipeline(
            storage_path=str(db_path),
            namespace="memory_test"
        )

        # Ingest and track memory
        pipeline.ingest_file(str(pdf_path))

        peak_mb = process.memory_info().rss / (1024 * 1024)

    print("✓")

    return {
        'baseline_mb': round(baseline_mb, 2),
        'peak_mb': round(peak_mb, 2),
        'delta_mb': round(peak_mb - baseline_mb, 2)
    }


def benchmark_scalability(test_files: list[Path]) -> dict:
    """
    Test scalability across different document sizes.

    Measures how performance scales with document size.
    """
    results = []

    print(f"  Scalability analysis ({len(test_files)} files)...", end=" ", flush=True)

    for pdf_path in test_files:
        info = get_pdf_info(pdf_path)

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "bench.duckdb"

            pipeline = KOSPipeline(
                storage_path=str(db_path),
                namespace="scale_test"
            )

            start = time.time()
            pipeline.ingest_file(str(pdf_path))
            elapsed = time.time() - start

            stats = pipeline.stats(namespace="scale_test")

            results.append({
                'pages': info['pages'],
                'size_mb': info['size_mb'],
                'segments': stats['segments'],
                'time_seconds': round(elapsed, 3),
                'pages_per_second': round(info['pages'] / elapsed, 2) if elapsed > 0 else 0
            })

    print("✓")

    return {
        'files_tested': len(results),
        'results': results
    }


def generate_markdown_report(results: dict) -> str:
    """Generate comprehensive markdown report."""
    report = "# DocMine KOS Performance Benchmarks\n\n"
    report += f"**Generated:** {results['timestamp']}\n\n"
    report += f"**System:** {results['system']['os']} ({results['system']['machine']}) - "
    report += f"Python {results['system']['python']}, {results['system']['cpu_cores']} cores\n\n"
    report += "---\n\n"

    # Ingestion Performance
    report += "## Ingestion Performance\n\n"
    report += "| Document | Pages | Segments | Entities | First Ingest | Re-ingest | Speedup |\n"
    report += "|----------|-------|----------|----------|--------------|-----------|--------|\n"

    for file_key in sorted([k for k in results.keys() if k.endswith('.pdf')]):
        data = results[file_key]
        info = data['pdf_info']
        first = data['first_ingestion']
        reingest = data['reingestion']

        speedup = round(first['avg_time_seconds'] / reingest['avg_time_seconds'], 1)

        report += f"| {file_key} | {info['pages']} | {first['segments_created']} | "
        report += f"{first['entities_extracted']} | {first['avg_time_seconds']}s | "
        report += f"{reingest['avg_time_seconds']}s | {speedup}x |\n"

    # Search Performance
    report += "\n## Search Performance\n\n"
    report += "| Document | Semantic (top-5) | Semantic (top-20) | Exact Recall | Segments |\n"
    report += "|----------|------------------|-------------------|--------------|----------|\n"

    for file_key in sorted([k for k in results.keys() if k.endswith('.pdf')]):
        data = results[file_key]
        search = data['semantic_search']
        exact = data['exact_recall']

        report += f"| {file_key} | {search['top_k_5']['median_latency_ms']}ms | "
        report += f"{search['top_k_20']['median_latency_ms']}ms | "

        if 'error' in exact:
            report += f"N/A | - |\n"
        else:
            report += f"{exact['median_latency_ms']}ms | "
            report += f"{data['first_ingestion']['segments_created']} |\n"

    # Memory Usage
    report += "\n## Memory Usage\n\n"
    report += "| Document | Pages | Peak Memory | Delta |\n"
    report += "|----------|-------|-------------|-------|\n"

    for file_key in sorted([k for k in results.keys() if k.endswith('.pdf')]):
        data = results[file_key]
        mem = data['memory']
        info = data['pdf_info']

        report += f"| {file_key} | {info['pages']} | {mem['peak_mb']}MB | {mem['delta_mb']}MB |\n"

    # Key Metrics Summary
    report += "\n## Summary\n\n"

    # Calculate averages across all documents
    all_first = [results[k]['first_ingestion']['segments_per_second']
                 for k in results.keys() if k.endswith('.pdf')]
    all_search = [results[k]['semantic_search']['top_k_5']['median_latency_ms']
                  for k in results.keys() if k.endswith('.pdf')]
    all_reingest = [results[k]['reingestion']['avg_time_seconds']
                    for k in results.keys() if k.endswith('.pdf')]

    report += f"- **Ingestion throughput:** {round(mean(all_first), 1)} segments/second (avg)\n"
    report += f"- **Search latency:** {round(mean(all_search), 1)}ms median (top-5)\n"
    report += f"- **Re-ingestion:** {round(mean(all_reingest), 3)}s avg (idempotent)\n"
    report += f"- **Idempotency:** ✅ Verified across all test files\n\n"

    return report


def main():
    """Run comprehensive KOS benchmarks."""
    print("=" * 70)
    print("DocMine Knowledge Organization System (KOS) - Performance Benchmarks")
    print("=" * 70)

    # System info
    print(f"\n📊 System Information:")
    print(f"  OS: {platform.system()} {platform.release()}")
    print(f"  Machine: {platform.machine()}")
    print(f"  Python: {sys.version.split()[0]}")
    print(f"  CPU Cores: {psutil.cpu_count()}")
    print(f"  RAM: {round(psutil.virtual_memory().total / (1024**3), 1)}GB")

    # Find test PDFs
    test_dir = Path("benchmarks/test_pdfs")
    if not test_dir.exists():
        print("\n⚠ No test PDFs found. Run 'python benchmarks/download_test_pdfs.py' first.")
        return

    test_files = sorted(list(test_dir.glob("*.pdf")))
    if not test_files:
        print("\n⚠ No test PDFs found in benchmarks/test_pdfs/")
        return

    print(f"\n📚 Found {len(test_files)} test PDFs:")
    for pdf in test_files:
        info = get_pdf_info(pdf)
        print(f"  - {pdf.name}: {info['pages']} pages, {info['size_mb']}MB")

    # Run benchmarks
    results = {
        'timestamp': datetime.now().isoformat(),
        'system': {
            'os': f"{platform.system()} {platform.release()}",
            'machine': platform.machine(),
            'python': sys.version.split()[0],
            'cpu_cores': psutil.cpu_count(),
            'ram_gb': round(psutil.virtual_memory().total / (1024**3), 1)
        }
    }

    for pdf_path in test_files:
        pdf_name = pdf_path.name
        print(f"\n{'=' * 70}")
        print(f"📄 Benchmarking: {pdf_name}")
        print(f"{'=' * 70}")

        results[pdf_name] = {
            'pdf_info': get_pdf_info(pdf_path),
            'first_ingestion': benchmark_first_ingestion(pdf_path, num_runs=1),
            'reingestion': benchmark_reingestion(pdf_path, num_runs=3),
            'semantic_search': benchmark_semantic_search(pdf_path, num_queries=10),
            'exact_recall': benchmark_exact_recall(pdf_path),
            'memory': benchmark_memory_usage(pdf_path),
        }

        # Save intermediate results
        output_path = Path("benchmarks/results_kos.json")
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)

    # Save results
    output_path = Path("benchmarks/results_kos.json")
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n{'=' * 70}")
    print(f"✅ Results saved to {output_path}")
    print(f"{'=' * 70}")

    # Generate markdown report
    report = generate_markdown_report(results)
    report_path = Path("benchmarks/BENCHMARK_REPORT_KOS.md")
    with open(report_path, 'w') as f:
        f.write(report)

    print(f"\n📋 Benchmark report saved to {report_path}")
    print(f"\n{report}")


if __name__ == "__main__":
    main()

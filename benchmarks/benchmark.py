"""DocMine performance benchmarking suite."""

import time
import json
import platform
import sys
from pathlib import Path
from statistics import mean, stdev
from datetime import datetime

import psutil
import fitz

# Add parent directory to path to import docmine
sys.path.insert(0, str(Path(__file__).parent.parent))

from docmine.pipeline import PDFPipeline
from docmine.ingest.pdf_extractor import PDFExtractor
from docmine.ingest.chunker import SemanticChunker


def get_pdf_page_count(pdf_path: Path) -> int:
    """Get the number of pages in a PDF."""
    doc = fitz.open(pdf_path)
    count = len(doc)
    doc.close()
    return count


def benchmark_extraction(pdf_path: Path, num_runs: int = 3) -> dict:
    """
    Measure PDF extraction speed.

    Args:
        pdf_path: Path to PDF file
        num_runs: Number of benchmark runs

    Returns:
        Dictionary with benchmark results
    """
    extractor = PDFExtractor()
    times = []
    pages_count = None

    print(f"  Benchmarking extraction ({num_runs} runs)...", end=" ")

    for _ in range(num_runs):
        start = time.time()
        pages = extractor.extract(pdf_path)
        elapsed = time.time() - start
        times.append(elapsed)
        if pages_count is None:
            pages_count = len(pages)

    avg_time = mean(times)
    print(f"✓")

    return {
        'pages': pages_count,
        'avg_time_seconds': round(avg_time, 3),
        'pages_per_second': round(pages_count / avg_time, 2) if avg_time > 0 else 0,
    }


def benchmark_chunking(pdf_path: Path, num_runs: int = 3) -> dict:
    """
    Measure chunking speed.

    Args:
        pdf_path: Path to PDF file
        num_runs: Number of benchmark runs

    Returns:
        Dictionary with benchmark results
    """
    extractor = PDFExtractor()
    chunker = SemanticChunker()
    pages = extractor.extract(pdf_path)

    times = []
    chunks_count = None

    print(f"  Benchmarking chunking ({num_runs} runs)...", end=" ")

    for _ in range(num_runs):
        start = time.time()
        chunks = chunker.chunk_pages(pages)
        elapsed = time.time() - start
        times.append(elapsed)
        if chunks_count is None:
            chunks_count = len(chunks)

    avg_time = mean(times)
    print(f"✓")

    return {
        'chunks': chunks_count,
        'avg_time_seconds': round(avg_time, 3),
        'chunks_per_second': round(chunks_count / avg_time, 2) if avg_time > 0 else 0,
    }


def benchmark_embedding(pdf_path: Path, num_runs: int = 1) -> dict:
    """
    Measure embedding generation speed.

    Args:
        pdf_path: Path to PDF file
        num_runs: Number of benchmark runs (default 1 due to high cost)

    Returns:
        Dictionary with benchmark results
    """
    # Use a temporary database
    db_path = "benchmarks/temp_benchmark.duckdb"
    Path(db_path).unlink(missing_ok=True)

    pipeline = PDFPipeline(storage_path=db_path)

    # Extract and chunk
    pages = pipeline.extractor.extract(pdf_path)
    chunks = pipeline.chunker.chunk_pages(pages)
    chunk_texts = [c["content"] for c in chunks]

    times = []

    print(f"  Benchmarking embedding ({num_runs} run)...", end=" ")

    for _ in range(num_runs):
        start = time.time()
        embeddings = pipeline.search_engine.generate_embeddings(chunk_texts)
        elapsed = time.time() - start
        times.append(elapsed)

    avg_time = mean(times)
    print(f"✓")

    # Cleanup
    Path(db_path).unlink(missing_ok=True)

    return {
        'chunks': len(chunks),
        'avg_time_seconds': round(avg_time, 3),
        'chunks_per_second': round(len(chunks) / avg_time, 2) if avg_time > 0 else 0,
    }


def benchmark_end_to_end(pdf_path: Path) -> dict:
    """
    Full pipeline benchmark.

    Args:
        pdf_path: Path to PDF file

    Returns:
        Dictionary with benchmark results
    """
    db_path = "benchmarks/temp_benchmark.duckdb"
    Path(db_path).unlink(missing_ok=True)

    pipeline = PDFPipeline(storage_path=db_path)

    print(f"  Benchmarking end-to-end...", end=" ")

    start = time.time()
    chunks_created = pipeline.ingest_file(str(pdf_path))
    total_time = time.time() - start

    print(f"✓")

    # Cleanup
    Path(db_path).unlink(missing_ok=True)

    return {
        'total_chunks': chunks_created,
        'total_time_seconds': round(total_time, 3),
    }


def benchmark_search(num_runs: int = 10) -> dict:
    """
    Measure search latency.

    Args:
        num_runs: Number of search queries to run

    Returns:
        Dictionary with benchmark results
    """
    # Use test.pdf if available
    test_pdf = Path("test.pdf")
    if not test_pdf.exists():
        return {'error': 'test.pdf not found'}

    db_path = "benchmarks/temp_search_benchmark.duckdb"
    Path(db_path).unlink(missing_ok=True)

    pipeline = PDFPipeline(storage_path=db_path)
    pipeline.ingest_file(str(test_pdf))

    times = []
    queries = [
        "main topic",
        "methodology",
        "results",
        "conclusion",
        "introduction",
        "abstract",
        "data analysis",
        "experiment",
        "discussion",
        "future work"
    ]

    print(f"  Benchmarking search ({num_runs} queries)...", end=" ")

    for i in range(num_runs):
        query = queries[i % len(queries)]
        start = time.time()
        results = pipeline.search(query, top_k=5)
        elapsed = time.time() - start
        times.append(elapsed)

    avg_time_ms = mean(times) * 1000
    print(f"✓")

    # Cleanup
    Path(db_path).unlink(missing_ok=True)

    return {
        'queries': num_runs,
        'avg_latency_ms': round(avg_time_ms, 2),
    }


def benchmark_memory(pdf_path: Path) -> dict:
    """
    Measure memory usage during ingestion.

    Args:
        pdf_path: Path to PDF file

    Returns:
        Dictionary with memory statistics
    """
    db_path = "benchmarks/temp_memory_benchmark.duckdb"
    Path(db_path).unlink(missing_ok=True)

    process = psutil.Process()
    initial_memory = process.memory_info().rss / (1024 * 1024)  # MB

    print(f"  Benchmarking memory usage...", end=" ")

    pipeline = PDFPipeline(storage_path=db_path)
    pipeline.ingest_file(str(pdf_path))

    peak_memory = process.memory_info().rss / (1024 * 1024)  # MB
    memory_used = peak_memory - initial_memory

    print(f"✓")

    # Cleanup
    Path(db_path).unlink(missing_ok=True)

    return {
        'peak_memory_mb': round(peak_memory, 2),
        'memory_used_mb': round(memory_used, 2),
    }


def generate_readme_table(results: dict) -> str:
    """Generate markdown table for README."""
    # Get the different PDF sizes
    pdf_names = sorted([k for k in results.keys() if k.endswith('.pdf')])

    table = "### Performance Benchmarks\n\n"
    table += f"*Measured on {results['system']['os']} ({results['system']['machine']}) "
    table += f"with Python {results['system']['python']}*\n\n"

    # Extraction table
    table += "| PDF Size | Pages | Extraction Time | Chunks Created | Chunking Time | Embedding Time | **Total Time** |\n"
    table += "|----------|-------|-----------------|----------------|---------------|----------------|----------------|\n"

    for pdf_name in pdf_names:
        pdf_data = results[pdf_name]
        pages = pdf_data['extraction']['pages']
        ext_time = pdf_data['extraction']['avg_time_seconds']
        chunks = pdf_data['chunking']['chunks']
        chunk_time = pdf_data['chunking']['avg_time_seconds']
        emb_time = pdf_data['embedding']['avg_time_seconds']
        total_time = pdf_data['end_to_end']['total_time_seconds']

        size_label = pdf_name.replace('.pdf', '').replace('_', ' ').title()
        table += f"| {size_label} | {pages} | {ext_time}s | {chunks} | {chunk_time}s | {emb_time}s | **{total_time}s** |\n"

    # Search performance
    if 'search' in results and 'error' not in results['search']:
        search = results['search']
        table += f"\n**Search Performance:**\n"
        table += f"- Average query latency: {search['avg_latency_ms']}ms\n"
        table += f"- Measured over {search['queries']} queries\n"

    return table


def main():
    """Run all benchmarks."""
    print("=" * 60)
    print("DocMine Performance Benchmarks")
    print("=" * 60)

    # System info
    print(f"\nSystem Information:")
    print(f"  OS: {platform.system()} {platform.release()}")
    print(f"  Machine: {platform.machine()}")
    print(f"  Python: {sys.version.split()[0]}")
    print(f"  CPU Cores: {psutil.cpu_count()}")

    # Find test PDFs
    test_dir = Path("benchmarks/test_pdfs")
    if not test_dir.exists():
        print("\n⚠ No test PDFs found. Run 'python benchmarks/download_test_pdfs.py' first.")
        return

    test_files = sorted(list(test_dir.glob("*.pdf")))
    if not test_files:
        print("\n⚠ No test PDFs found. Run 'python benchmarks/download_test_pdfs.py' first.")
        return

    print(f"\nFound {len(test_files)} test PDFs")

    # Run benchmarks
    results = {
        'timestamp': datetime.now().isoformat(),
        'system': {
            'os': f"{platform.system()} {platform.release()}",
            'machine': platform.machine(),
            'python': sys.version.split()[0],
            'cpu_cores': psutil.cpu_count(),
        }
    }

    for pdf_path in test_files:
        pdf_name = pdf_path.name
        print(f"\n{'=' * 60}")
        print(f"Benchmarking: {pdf_name}")
        print(f"{'=' * 60}")

        results[pdf_name] = {
            'extraction': benchmark_extraction(pdf_path),
            'chunking': benchmark_chunking(pdf_path),
            'embedding': benchmark_embedding(pdf_path),
            'end_to_end': benchmark_end_to_end(pdf_path),
            'memory': benchmark_memory(pdf_path),
        }

    # Search benchmarks
    print(f"\n{'=' * 60}")
    print(f"Benchmarking: Search Performance")
    print(f"{'=' * 60}")
    results['search'] = benchmark_search()

    # Save results
    output_path = Path("benchmarks/results.json")
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n{'=' * 60}")
    print(f"Results saved to {output_path}")
    print(f"{'=' * 60}")

    # Generate README table
    readme_table = generate_readme_table(results)
    readme_path = Path("benchmarks/README_benchmark_table.md")
    with open(readme_path, 'w') as f:
        f.write(readme_table)

    print(f"\nREADME table saved to {readme_path}")
    print("\nCopy the contents to update the README.md Performance section")

    # Print summary
    print(f"\n{'=' * 60}")
    print("Benchmark Summary")
    print(f"{'=' * 60}")
    print(readme_table)


if __name__ == "__main__":
    main()

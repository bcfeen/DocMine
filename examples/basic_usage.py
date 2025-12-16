"""
Basic usage example for DocMine.

This script demonstrates how to:
1. Initialize the pipeline
2. Ingest PDF documents
3. Search the knowledge base
"""

from docmine.pipeline import PDFPipeline
from pathlib import Path


def main():
    # Initialize the pipeline
    print("Initializing DocMine pipeline...")
    pipeline = PDFPipeline(
        storage_path="examples_knowledge.duckdb",
        chunk_size=400,
        chunk_overlap=50
    )

    # Example 1: Ingest a single PDF
    pdf_path = "sample.pdf"
    if Path(pdf_path).exists():
        print(f"\nIngesting {pdf_path}...")
        chunks = pipeline.ingest_file(pdf_path)
        print(f"✓ Indexed {chunks} chunks")
    else:
        print(f"\nSkipping {pdf_path} - file not found")

    # Example 2: Ingest a directory
    pdf_dir = "./documents"
    if Path(pdf_dir).exists():
        print(f"\nIngesting all PDFs from {pdf_dir}...")
        total = pipeline.ingest_directory(pdf_dir)
        print(f"✓ Indexed {total} total chunks")

    # Example 3: Search
    print("\n" + "="*60)
    print("SEARCH EXAMPLES")
    print("="*60)

    queries = [
        "What is the main topic?",
        "methodology and approach",
        "conclusions and future work"
    ]

    for query in queries:
        print(f"\nQuery: '{query}'")
        results = pipeline.search(query, top_k=3)

        if results:
            for i, result in enumerate(results, 1):
                print(f"\n  [{i}] {Path(result['source_pdf']).name} (page {result['page_num']})")
                print(f"      Score: {result['score']:.4f}")
                print(f"      {result['content'][:150]}...")
        else:
            print("  No results found")


if __name__ == "__main__":
    main()

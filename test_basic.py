"""Basic test script for DocMine."""

from pathlib import Path
from docmine.pipeline import PDFPipeline


def main():
    """Test the DocMine pipeline with a sample PDF."""
    print("=" * 60)
    print("DocMine - PDF Knowledge Extraction Test")
    print("=" * 60)

    # Initialize pipeline
    print("\n[1/3] Initializing pipeline...")
    pipeline = PDFPipeline(storage_path="test_knowledge.duckdb")
    print("✓ Pipeline initialized")

    # Check for test PDF
    test_pdf = Path("test.pdf")

    if not test_pdf.exists():
        print("\n" + "=" * 60)
        print("SETUP REQUIRED")
        print("=" * 60)
        print("\nTo test DocMine, follow these steps:")
        print("\n1. Place a PDF file in this directory")
        print("2. Rename it to 'test.pdf'")
        print("3. Run this script again: python test_basic.py")
        print("\nThe PDF can be any document - research paper, book, manual, etc.")
        print("=" * 60)
        return

    # Ingest the PDF
    print(f"\n[2/3] Ingesting {test_pdf}...")
    try:
        count = pipeline.ingest_file("test.pdf")
        print(f"✓ Ingested {count} chunks")
    except Exception as e:
        print(f"✗ Error ingesting PDF: {e}")
        return

    # Search for content
    print("\n[3/3] Testing semantic search...")
    query = "main topic"
    print(f"Query: '{query}'")

    try:
        results = pipeline.search(query, top_k=3)

        if not results:
            print("✗ No results found")
            return

        print(f"\n✓ Found {len(results)} results:\n")

        for i, result in enumerate(results, 1):
            print(f"Result {i}: {Path(result['source_pdf']).name} (page {result['page_num']})")

            # Truncate content for display
            content = result['content']
            if len(content) > 200:
                content = content[:200] + "..."

            print(f"Content: {content}")
            print(f"Score: {result['score']:.4f}")
            print()

        print("=" * 60)
        print("SUCCESS - DocMine is working correctly!")
        print("=" * 60)
        print("\nYou can now use DocMine in your own code:")
        print("\nfrom docmine.pipeline import PDFPipeline")
        print("pipeline = PDFPipeline()")
        print("pipeline.ingest_file('your_document.pdf')")
        print("results = pipeline.search('your query')")

    except Exception as e:
        print(f"✗ Error during search: {e}")
        return


if __name__ == "__main__":
    main()

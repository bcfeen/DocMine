"""Download test PDFs for benchmarking."""

import urllib.request
from pathlib import Path
import sys


def download_arxiv_pdf(arxiv_id: str, output_name: str) -> Path:
    """
    Download a PDF from arXiv.

    Args:
        arxiv_id: arXiv paper ID
        output_name: Output filename

    Returns:
        Path to downloaded PDF
    """
    url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    output_path = Path("benchmarks/test_pdfs") / output_name
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.exists():
        print(f"✓ {output_name} already exists")
        return output_path

    try:
        print(f"Downloading {output_name} from arXiv...")
        urllib.request.urlretrieve(url, output_path)
        print(f"✓ Downloaded to {output_path}")
        return output_path
    except Exception as e:
        print(f"✗ Failed to download {output_name}: {e}")
        return None


def prepare_test_suite():
    """Download a set of test PDFs of different sizes."""
    print("=" * 60)
    print("DocMine Benchmark PDF Downloader")
    print("=" * 60)
    print("\nDownloading test PDFs from arXiv...\n")

    test_pdfs = {
        'small_8pages.pdf': '1706.03762',      # Attention is All You Need (8 pages)
        'medium_13pages.pdf': '2103.00020',    # CLIP paper (13 pages)
        'large_34pages.pdf': '1810.04805',     # BERT paper (34 pages)
    }

    downloaded = {}
    for name, arxiv_id in test_pdfs.items():
        path = download_arxiv_pdf(arxiv_id, name)
        if path:
            downloaded[name] = path

    print(f"\n{'=' * 60}")
    print(f"Downloaded {len(downloaded)}/{len(test_pdfs)} test PDFs")
    print(f"{'=' * 60}")

    return downloaded


if __name__ == "__main__":
    prepare_test_suite()

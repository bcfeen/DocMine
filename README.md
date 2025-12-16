# DocMine

> **Semantic PDF knowledge extraction made simple**

Transform your PDF documents into a searchable knowledge base using state-of-the-art semantic embeddings. DocMine extracts, chunks, and indexes your documents so you can find exactly what you're looking for with natural language queries.

<div align="center">

[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

</div>

---

## Features

- **Semantic Search** - Find content by meaning, not just keywords
- **PDF Text Extraction** - Powered by PyMuPDF for reliable extraction
- **Smart Chunking** - Semantic chunking via Chonkie for context-aware segments
- **Embedded Database** - DuckDB backend with vector similarity search
- **Simple API** - Three lines of code to go from PDF to searchable knowledge
- **Progress Tracking** - Built-in progress bars for long operations
- **Robust Error Handling** - Gracefully handles malformed PDFs

---

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/bcfeen/DocMine.git
cd DocMine

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install DocMine
pip install -e .
```

### Basic Usage

```python
from docmine.pipeline import PDFPipeline

# Initialize the pipeline
pipeline = PDFPipeline()

# Ingest a PDF document
chunks = pipeline.ingest_file("research_paper.pdf")
print(f"Indexed {chunks} chunks")

# Search with natural language
results = pipeline.search("What are the main findings?", top_k=5)

for result in results:
    print(f"📄 {result['source_pdf']} (page {result['page_num']})")
    print(f"💬 {result['content'][:200]}...")
    print(f"⭐ Score: {result['score']:.3f}\n")
```

---

## Examples

### Ingest a Single Document

```python
from docmine.pipeline import PDFPipeline

pipeline = PDFPipeline(storage_path="my_knowledge.duckdb")
count = pipeline.ingest_file("manual.pdf")
print(f"✓ Processed {count} chunks")
```

### Ingest an Entire Directory

```python
# Process all PDFs in a folder
total = pipeline.ingest_directory("./research_papers", pattern="*.pdf")
print(f"✓ Indexed {total} total chunks")
```

### Custom Configuration

```python
pipeline = PDFPipeline(
    storage_path="custom.duckdb",
    chunk_size=512,              # Larger chunks
    chunk_overlap=100,           # More overlap for context
    embedding_model="sentence-transformers/all-MiniLM-L6-v2"  # Faster model
)
```

### Search and Analyze

```python
# Find relevant passages
results = pipeline.search("methodology and approach", top_k=10)

# Group results by document
from collections import defaultdict

by_doc = defaultdict(list)
for r in results:
    by_doc[r['source_pdf']].append(r)

for doc, chunks in by_doc.items():
    print(f"\n{doc}: {len(chunks)} relevant sections")
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       PDFPipeline                           │
│                    (Main Entry Point)                       │
└──────────────┬──────────────────────────┬───────────────────┘
               │                          │
       ┌───────▼────────┐        ┌────────▼─────────┐
       │  PDFExtractor  │        │  SemanticSearch  │
       │   (PyMuPDF)    │        │ (Transformers)   │
       └───────┬────────┘        └────────┬─────────┘
               │                          │
       ┌───────▼────────┐        ┌────────▼─────────┐
       │SemanticChunker │        │  DuckDBBackend   │
       │   (Chonkie)    │        │  (Vector Store)  │
       └────────────────┘        └──────────────────┘
```

### Components

| Component | Purpose | Technology |
|-----------|---------|------------|
| **PDFExtractor** | Extract text from PDFs | PyMuPDF (fitz) |
| **SemanticChunker** | Split text into semantic segments | Chonkie |
| **DuckDBBackend** | Store chunks with embeddings | DuckDB |
| **SemanticSearch** | Generate embeddings & search | sentence-transformers |
| **PDFPipeline** | Orchestrate the full workflow | Python |

---

## Configuration Options

### Pipeline Parameters

```python
PDFPipeline(
    storage_path="knowledge.duckdb",  # Database file location
    chunk_size=400,                   # Target chunk size (tokens)
    chunk_overlap=50,                 # Overlap between chunks
    embedding_model="sentence-transformers/all-mpnet-base-v2"
)
```

### Embedding Models

Choose from any [sentence-transformers](https://www.sbert.net/docs/pretrained_models.html) model:

| Model | Dimensions | Speed | Quality |
|-------|-----------|-------|---------|
| `all-mpnet-base-v2` | 768 | Medium | Best |
| `all-MiniLM-L6-v2` | 384 | Fast | Good |
| `multi-qa-mpnet-base-dot-v1` | 768 | Medium | Q&A Optimized |

---

## Performance

DocMine is designed for efficiency:

- **Fast Extraction**: PyMuPDF processes pages in milliseconds
- **Smart Chunking**: Semantic boundaries preserve context
- **Batch Embeddings**: Progress bars show real-time status
- **Efficient Storage**: DuckDB with vector similarity search
- **Scalable**: Handles single documents or entire libraries

### Benchmarks

*Measured on macOS (Apple Silicon M1) with Python 3.13*

| PDF | Pages | Extraction | Chunks | Chunking | Embedding | **Total** |
|-----|-------|-----------|--------|----------|-----------|-----------|
| 15-page paper | 15 | 0.11s | 233 | 0.81s | 11.26s | **24.9s** |
| 16-page paper | 16 | 0.07s | 517 | 1.41s | 4.45s | **32.1s** |
| 48-page paper | 48 | 0.37s | 1582 | 3.33s | 14.45s | **106.1s** |

**Search Performance:**
- Average query latency: **145ms**
- Measured over 10 queries on indexed corpus

*Note: Benchmark PDFs are academic papers from arXiv. Performance varies by document structure and content density.*

---

## Testing

Run the included test script:

```bash
# Place a PDF named test.pdf in the project directory
python test_basic.py
```

Expected output:
```
============================================================
DocMine - PDF Knowledge Extraction Test
============================================================

[1/3] Initializing pipeline...
✓ Pipeline initialized

[2/3] Ingesting test.pdf...
✓ Ingested 142 chunks

[3/3] Testing semantic search...
Query: 'main topic'

✓ Found 3 results:

Result 1: test.pdf (page 3)
Content: The primary focus of this research is...
Score: 0.8234
```

---

## Development

### Project Structure

```
docmine/
├── docmine/
│   ├── __init__.py
│   ├── pipeline.py              # Main API
│   ├── ingest/
│   │   ├── pdf_extractor.py     # PDF → Text
│   │   └── chunker.py           # Text → Chunks
│   ├── storage/
│   │   └── duckdb_backend.py    # Storage & Retrieval
│   └── search/
│       └── semantic_search.py   # Embeddings & Search
├── test_basic.py                # Test script
├── setup.py                     # Package setup
├── requirements.txt             # Dependencies
└── README.md                    # This file
```

### Dependencies

- **pymupdf** - PDF text extraction
- **chonkie** - Semantic text chunking
- **sentence-transformers** - Embedding generation
- **duckdb** - Embedded vector database
- **numpy** - Numerical operations
- **tqdm** - Progress bars

---

## Use Cases

- **Research**: Index academic papers and find relevant citations
- **Documentation**: Make technical manuals searchable
- **Legal**: Search contracts and legal documents by concept
- **Enterprise**: Build internal knowledge bases from reports
- **Education**: Create study aids from textbooks
- **Journalism**: Analyze and search document collections

---

## Contributing

Contributions are welcome! Here's how you can help:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Code Style

- Follow PEP 8
- Add docstrings to all functions
- Include type hints
- Write descriptive commit messages

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Acknowledgments

Built with these amazing open-source projects:

- [PyMuPDF](https://pymupdf.readthedocs.io/) - PDF processing
- [Chonkie](https://github.com/bhavnicksm/chonkie) - Semantic chunking
- [sentence-transformers](https://www.sbert.net/) - State-of-the-art embeddings
- [DuckDB](https://duckdb.org/) - Blazing fast analytics database

---

## Contact

Questions? Suggestions? Open an issue or reach out!

---

<div align="center">

**Made with care for the open-source community**

Star this repo if you find it useful!

</div>

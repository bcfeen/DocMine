# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-12-16

### Added
- Initial release of DocMine
- PDF text extraction using PyMuPDF
- Semantic chunking with Chonkie
- Vector storage with DuckDB
- Semantic search using sentence-transformers
- `PDFPipeline` main API class
- Support for single file and directory ingestion
- Natural language search functionality
- Comprehensive documentation and README
- Test suite (`test_basic.py`)

### Features
- Batch embedding generation with progress bars
- Cosine similarity search
- Configurable chunk size and overlap
- Support for any sentence-transformers model
- Robust error handling for malformed PDFs

[0.1.0]: https://github.com/bcfeen/DocMine/releases/tag/v0.1.0

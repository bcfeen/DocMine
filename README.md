# DocMine

> Knowledge-centric document ingestion with stable IDs, provenance tracking, entity extraction, and exact recall

DocMine transforms documents (PDF, Markdown, text) into a queryable knowledge base with first-class support for entities, provenance, and deterministic re-ingestion.

---

## What Makes This Different

Traditional RAG systems treat chunks as disposable retrieval units. DocMine treats **knowledge objects as stable, identifiable, and traceable primitives**.

**Core guarantees:**

1. **Idempotent ingestion** — Re-ingesting the same file creates zero duplicates
2. **Deterministic segment IDs** — Same content + location = same ID across runs
3. **Exact recall** — Find ALL segments linked to an entity (independent of embeddings)
4. **Full provenance** — Every segment tracks its source location (page, sentence, offsets)
5. **Multi-corpus isolation** — Separate projects via namespaces

**Important:** Exact recall is guaranteed over extracted entity links. Corpus-level recall depends on extractor quality.

---

## Quick Start

### Install

```bash
git clone https://github.com/bcfeen/DocMine.git
cd DocMine
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

### Basic Usage

```python
from docmine.kos_pipeline import KOSPipeline

# Initialize
pipeline = KOSPipeline(namespace="research")

# Ingest (idempotent - safe to repeat)
pipeline.ingest_file("paper.pdf")
pipeline.ingest_file("paper.pdf")  # No duplicates created

# Semantic search
results = pipeline.search("BRCA1 function", top_k=5)
for r in results:
    print(f"{r['text'][:100]}... (score: {r['score']:.2f})")

# Exact recall (find ALL mentions)
segments = pipeline.search_entity("BRCA1", entity_type="gene")
print(f"Found {len(segments)} segments (complete)")

# List entities
entities = pipeline.list_entities()
for e in entities[:5]:
    print(f"{e['name']}: {e['mention_count']} mentions")
```

### Validate Installation

```bash
python validate_kos.py  # Should show: ✅ ALL TESTS PASSED
```

---

## Architecture

```
InformationResource (IR)
  └─ source_uri: "file:///path/doc.pdf" (canonical, stable)
  └─ content_hash: SHA256 (change detection)
  └─ namespace: "project_name"

ResourceSegment
  └─ id: SHA256(namespace + uri + provenance + text)  [deterministic]
  └─ text: "The BRCA1 gene encodes..."
  └─ provenance: {page: 5, sentence: 3}
  └─ embedding: [0.123, -0.456, ...]

Entity
  └─ name: "BRCA1"
  └─ type: "gene"
  └─ aliases: ["breast cancer 1"]

Segment ↔ Entity Links
  └─ segment_id → entity_id
  └─ link_type: mentions | about | primary
  └─ confidence: 0.95
```

**Storage:** DuckDB with relational schema (5 tables). Embeddings stored as `FLOAT[]` arrays. Semantic search uses brute-force cosine similarity (suitable for <100k segments; use HNSW/Faiss for larger corpora).

---

## Key Features

### Idempotent Ingestion

```python
pipeline.ingest_file("doc.pdf")  # 142 segments
pipeline.ingest_file("doc.pdf")  # Still 142 segments ✓
```

Segment IDs are deterministic: `SHA256(namespace + source_uri + provenance_key + normalized_text)`.

### Entity Extraction

Automatic extraction during ingestion. Default regex patterns support:
- Gene symbols (BRCA1, TP53)
- Protein identifiers (p53, HER2)
- Strain IDs (BY4741, YPH499)
- DOIs, PubMed IDs, emails

Extensible for custom patterns.

### Exact Recall

```python
# Semantic search (may miss mentions if similarity is low)
semantic = pipeline.search("BRCA1", top_k=10)

# Exact recall (guaranteed complete over extracted links)
exact = pipeline.search_entity("BRCA1", entity_type="gene")

# exact >= semantic
```

### Provenance

```python
{
  "page": 5,
  "sentence": 3,
  "sentence_count": 3,
  "source_uri": "file:///path/paper.pdf"
}
```

### Multi-Corpus Namespaces

```python
pipeline.ingest_file("alpha.pdf", namespace="lab_alpha")
pipeline.ingest_file("beta.pdf", namespace="lab_beta")

# Search within namespace
results = pipeline.search("growth rate", namespace="lab_alpha")
```

---

## Documentation

- **[Architecture & Migration Guide](docs/knowledge_centric_migration.md)** — Design decisions, object model, migration from old system
- **[Quick Start Guide](QUICK_START_KOS.md)** — 5-minute tutorial
- **[Migration from Legacy](MIGRATION_COMPLETE.md)** — Summary of changes from chunk-based system

---

## Testing

```bash
# Quick validation
python validate_kos.py

# Full test suite
pip install pytest
pytest tests/ -v
```

Tests validate:
- Idempotency (no duplicates on re-ingest)
- Deterministic IDs (stable across runs)
- Exact recall completeness
- Namespace isolation

---

## Examples

### Re-ingest Only Changed Files

```python
# Only processes files with different content_hash
pipeline.reingest_changed(namespace="project")
```

### Custom Entity Patterns

```python
from docmine.extraction import RegexEntityExtractor

extractor = RegexEntityExtractor()
extractor.add_pattern("experiment_id", r"\bEXP-\d{4}\b")

pipeline = KOSPipeline(entity_extractor=extractor)
```

### Browse Entity Mentions

```python
entity = pipeline.get_entity("BRCA1", entity_type="gene")
segments = pipeline.get_segments_for_entity(entity.id)

for seg in segments:
    print(f"Page {seg['provenance']['page']}: {seg['text']}")
```

---

## Limitations & Caveats

- **Corpus size:** Brute-force semantic search suitable for <100k segments. Use approximate nearest neighbor (HNSW/Faiss) for larger corpora.
- **Extractor quality:** Exact recall is complete over extracted links, but extraction quality varies by domain. Improve extractors for better coverage.
- **No entity disambiguation:** "BRCA1" as gene vs. protein are separate entities. Manual merging or LLM-based disambiguation needed.
- **Single-process:** No concurrent writes. Use file locking or separate namespaces for parallel ingestion.

---

## Migration from Legacy System

If you have data from the old chunk-based DocMine:

```bash
python scripts/migrate_legacy_chunks.py \
    --old-db knowledge.duckdb \
    --new-db knowledge_kos.duckdb \
    --namespace legacy
```

Old API (`PDFPipeline`) still exists for backward compatibility. See [README_OLD.md](README_OLD.md).

---

## Contributing

Contributions welcome. Priority areas:
- Domain-specific entity extractors (biomedical, legal, etc.)
- LLM-based entity extraction for higher recall
- Approximate nearest neighbor search integration
- Entity disambiguation strategies

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## License

MIT — see [LICENSE](LICENSE)

---

## Acknowledgments

Built with: [PyMuPDF](https://pymupdf.readthedocs.io/), [sentence-transformers](https://www.sbert.net/), [DuckDB](https://duckdb.org/)

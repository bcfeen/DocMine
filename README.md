# DocMine

Transform documents into queryable knowledge with stable IDs, entity extraction, and guaranteed exact recall.

```bash
pip install -e .
```

```python
from docmine.kos_pipeline import KOSPipeline

pipeline = KOSPipeline(namespace="research")
pipeline.ingest_file("paper.pdf")

# Semantic search
results = pipeline.search("BRCA1 mutations", top_k=5)

# Exact recall - all segments linked to this entity
segments = pipeline.search_entity("BRCA1", entity_type="gene")
```

---

## Why DocMine?

**vs. LangChain/LlamaIndex**
- Lightweight stack (PyMuPDF + sentence-transformers + DuckDB)
- Idempotent ingestion - re-ingest files without duplicates
- Deterministic segment IDs - same content always generates same ID

**vs. Traditional RAG**
- Exact recall - retrieve all segments linked to an entity (not just semantic matches)
- Full provenance tracking - every segment knows its page/sentence/offset
- Entity extraction built-in - genes, proteins, DOIs, custom patterns

**Best for:**
- Research papers (track entities across documents)
- Compliance (complete audit trails)
- Multi-project knowledge bases (namespace isolation)

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

### Working Example

```python
from docmine.kos_pipeline import KOSPipeline

# Initialize with namespace (multi-corpus support)
pipeline = KOSPipeline(
    storage_path="knowledge.duckdb",
    namespace="research"
)

# Ingest documents (PDF, Markdown, text)
pipeline.ingest_file("paper.pdf")
pipeline.ingest_file("notes.md")

# Re-ingesting same file creates zero duplicates
pipeline.ingest_file("paper.pdf")  # Idempotent!

# Semantic search
results = pipeline.search("BRCA1 function", top_k=5)
for r in results:
    print(f"[Page {r['provenance']['page']}] {r['text'][:100]}...")
    print(f"Score: {r['score']:.2f}\n")

# Exact recall - all linked segments
segments = pipeline.search_entity("BRCA1", entity_type="gene")
print(f"Found {len(segments)} segments linked to BRCA1")

# Browse entities
entities = pipeline.list_entities(min_mentions=2)
for e in entities:
    print(f"{e['name']} ({e['type']}): {e['mention_count']} mentions")
```

### Validate Installation

```bash
python validate_kos.py  # Should show: ✅ ALL TESTS PASSED
```

---

## Architecture

```
InformationResource (source document)
  ├─ source_uri: file:///path/doc.pdf (stable, canonical)
  ├─ content_hash: SHA256 (change detection)
  └─ namespace: "research"

ResourceSegment (1-3 sentences)
  ├─ id: SHA256(namespace + uri + provenance + text)  [deterministic]
  ├─ text: "The BRCA1 gene encodes a tumor suppressor..."
  ├─ provenance: {page: 5, sentence: 3, offsets: [120, 285]}
  └─ embedding: [0.123, -0.456, ...]  (768-dim vector)

Entity (extracted concept)
  ├─ name: "BRCA1"
  ├─ type: "gene"
  └─ aliases: ["breast cancer 1"]

Links: Segment ↔ Entity (many-to-many)
  ├─ link_type: mentions | about | primary
  └─ confidence: 0.95
```

**Storage:** DuckDB with 5 relational tables. Brute-force cosine similarity search (suitable for <100k segments; use FAISS/HNSW for larger).

**Components:**

| Component | Purpose | Tech |
|-----------|---------|------|
| IngestPipeline | Extract + segment + embed | PyMuPDF, sentence-transformers |
| KnowledgeStore | Relational storage + vector search | DuckDB |
| EntityExtractor | Regex-based NER (extensible) | Python regex |
| SemanticSearch | Embedding-based retrieval | all-mpnet-base-v2 |
| ExactRecall | Entity-linked retrieval | SQL JOIN |

---

## Performance

**Benchmarks** (macOS M-series, Python 3.13, `all-mpnet-base-v2` embeddings):

| Metric | Value | Notes |
|--------|-------|-------|
| Ingestion | 4.3s | 12-page PDF → 181 segments + 15 entities |
| Re-ingestion | 0.28s | **15x faster** (idempotent hash check) |
| Semantic search | 37ms | Median latency (top-5 results) |
| Exact recall | 1.6ms | Entity lookup via SQL JOIN |
| Throughput | ~42 segments/sec | Including entity extraction + embeddings |

**Methodology:** Single 12-page academic PDF (800KB), cold cache, MPS backend. See [`benchmarks/quick_bench.py`](benchmarks/quick_bench.py) to reproduce.

**Why re-ingestion is fast:** Content hash detection skips reprocessing. Same file = instant skip.

**Design choice:** Brute-force cosine similarity prioritizes correctness and simplicity. Works well for <100k segments. For larger corpora, FAISS/HNSW is pluggable (contribution welcome!).

---

## Use Cases

### Research Papers
```python
# Ingest arXiv papers
pipeline.ingest_directory("./papers", pattern="*.pdf")

# Track gene mentions across corpus
brca1_mentions = pipeline.search_entity("BRCA1", entity_type="gene")
for seg in brca1_mentions:
    print(f"{seg['source_uri']} - Page {seg['provenance']['page']}")
```

### Multi-Project Knowledge Base
```python
# Separate namespaces for isolation
pipeline.ingest_file("alpha.pdf", namespace="lab_alpha")
pipeline.ingest_file("beta.pdf", namespace="lab_beta")

# Search within namespace
alpha_results = pipeline.search("growth rate", namespace="lab_alpha")
```

### Custom Entity Extraction
```python
from docmine.extraction import RegexEntityExtractor

extractor = RegexEntityExtractor()
extractor.add_pattern("experiment", r"\bEXP-\d{4}\b")
extractor.add_pattern("sample", r"\bSAMP-[A-Z]{2}\d{3}\b")

pipeline = KOSPipeline(entity_extractor=extractor)
```

### Exact vs. Semantic Search
```python
# Semantic: fast but may miss low-similarity mentions
semantic = pipeline.search("BRCA1", top_k=10)

# Exact: returns all segments linked to the extracted entity
exact = pipeline.search_entity("BRCA1", entity_type="gene")

print(f"Semantic: {len(semantic)} | Exact: {len(exact)}")
# Exact returns all linked segments (may be more or fewer than semantic top-k)
```

---

## Core Features

### 1. Idempotent Ingestion
```python
pipeline.ingest_file("doc.pdf")  # 142 segments
pipeline.ingest_file("doc.pdf")  # Still 142 segments (no duplicates!)
```

Segment IDs are deterministic: `SHA256(namespace + source_uri + provenance + normalized_text)`

### 2. Entity Extraction
Auto-extracted during ingestion. Default patterns:
- Gene symbols: BRCA1, TP53, EGFR
- Protein IDs: p53, HER2, CDK2
- Strain IDs: BY4741, YPH499
- DOIs, PubMed IDs, emails, accession numbers

Fully extensible for custom domains.

### 3. Exact Recall
```python
# Semantic search might miss mentions if embedding similarity is low
semantic = pipeline.search("BRCA1", top_k=10)

# Exact recall returns all segments linked to the extracted entity
exact = pipeline.search_entity("BRCA1", entity_type="gene")
```

Guaranteed complete over extracted entity links. Critical for compliance, verification, entity tracking.

### 4. Full Provenance
```python
{
  "page": 5,
  "sentence": 3,
  "sentence_count": 3,
  "source_uri": "file:///Users/research/papers/paper.pdf",
  "offsets": [120, 285]
}
```

Trace every segment back to exact source location.

### 5. Multi-Corpus Namespaces
```python
# Separate projects
pipeline.ingest_file("doc1.pdf", namespace="project_a")
pipeline.ingest_file("doc2.pdf", namespace="project_b")

# Isolated search
results_a = pipeline.search("query", namespace="project_a")
results_b = pipeline.search("query", namespace="project_b")
```

---

## Examples

See [`examples/kos_demo.py`](examples/kos_demo.py) for complete working demo.

### Re-ingest Only Changed Files
```python
# Detects content_hash changes, only re-processes modified files
pipeline.reingest_changed(namespace="research")
```

### Browse Entity Mentions
```python
entity = pipeline.get_entity("BRCA1", entity_type="gene")
segments = pipeline.get_segments_for_entity(entity.id)

for seg in segments:
    print(f"[{seg['source_uri']} - Page {seg['provenance']['page']}]")
    print(f"{seg['text']}\n")
```

### Statistics
```python
stats = pipeline.stats(namespace="research")
print(stats)
# {
#   "namespace": "research",
#   "information_resources": 10,
#   "segments": 1420,
#   "entities": 45,
#   "entity_types": 5
# }
```

---

## Testing

```bash
# Quick smoke test
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

## Documentation

- **[Quick Start](QUICK_START_KOS.md)** - 5-minute tutorial
- **[Architecture Deep Dive](docs/knowledge_centric_migration.md)** - Design decisions, migration guide
- **[Contributing](CONTRIBUTING.md)** - How to contribute

---

## Limitations

- **Corpus size:** Brute-force search suitable for <100k segments (need HNSW/FAISS for scale)
- **Extractor quality:** Regex-based NER has limited recall (LLM-based extraction would improve)
- **No entity disambiguation:** "BRCA1" as gene vs. protein are separate entities
- **Single-process:** No concurrent writes (use file locking or separate namespaces)

---

## Contributing

Contributions welcome! Priority areas:
- Domain-specific entity extractors (biomedical, legal, financial)
- LLM-based entity extraction
- Approximate nearest neighbor search integration (FAISS/HNSW)
- Entity disambiguation strategies

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## License

MIT - see [LICENSE](LICENSE)

---

## Built With

- [PyMuPDF](https://pymupdf.readthedocs.io/) - PDF extraction
- [sentence-transformers](https://www.sbert.net/) - Embeddings
- [DuckDB](https://duckdb.org/) - Embedded database

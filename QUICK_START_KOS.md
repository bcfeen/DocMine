# DocMine KOS: Quick Start Guide

## 5-Minute Quick Start

### 1. Install

```bash
git clone https://github.com/bcfeen/DocMine.git
cd DocMine
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

### 2. Validate Installation

```bash
python validate_kos.py
```

Expected output: `✅ ALL TESTS PASSED`

### 3. Basic Usage

```python
from docmine.kos_pipeline import KOSPipeline

# Initialize
pipeline = KOSPipeline(namespace="demo")

# Ingest (supports PDF, MD, TXT)
pipeline.ingest_file("document.pdf")

# Semantic search
results = pipeline.search("your query", top_k=5)
for r in results:
    print(f"{r['text']} (score: {r['score']:.2f})")

# Exact recall (find ALL mentions)
segments = pipeline.search_entity("CCNA001")
print(f"Found {len(segments)} segments (complete)")

# List entities
entities = pipeline.list_entities()
for e in entities[:5]:
    print(f"{e['name']}: {e['mention_count']} mentions")
```

## Key Differences from Old System

| Task | Old Way | New Way (KOS) |
|------|---------|---------------|
| Import | `from docmine.pipeline import PDFPipeline` | `from docmine.kos_pipeline import KOSPipeline` |
| Initialize | `PDFPipeline()` | `KOSPipeline(namespace="project")` |
| Ingest | `ingest_file("doc.pdf")` | Same, but idempotent! |
| Search | `search("query")` | Same, returns provenance |
| Exact recall | ❌ Not available | `search_entity("CCNA001")` ✅ |
| Entities | ❌ Not available | `list_entities()` ✅ |

## Common Tasks

### Ingest a Directory

```python
pipeline.ingest_directory("./papers", pattern="*.pdf")
```

### Re-ingest Only Changed Files

```python
# Only re-processes files with different content_hash
pipeline.reingest_changed(namespace="project")
```

### Exact Recall for an Entity

```python
# Find ALL mentions (semantic search can miss some)
entity = pipeline.get_entity("BRCA1", entity_type="gene")
if entity:
    segments = pipeline.get_segments_for_entity(entity.id)
    for seg in segments:
        print(f"Source: {seg['source_uri']}")
        print(f"Page: {seg['provenance']['page']}")
        print(f"Text: {seg['text']}\n")
```

### Compare Semantic vs. Exact

```python
# Semantic (fuzzy, incomplete)
semantic = pipeline.search("CCNA001", top_k=10)

# Exact (complete, guaranteed)
exact = pipeline.search_entity("CCNA001")

print(f"Semantic found: {len(semantic)}")
print(f"Exact found: {len(exact)}")  # Usually >= semantic
```

### Multi-Corpus

```python
# Separate namespaces
pipeline.ingest_file("alpha.pdf", namespace="lab_alpha")
pipeline.ingest_file("beta.pdf", namespace="lab_beta")

# Search within namespace
results_alpha = pipeline.search("query", namespace="lab_alpha")
results_beta = pipeline.search("query", namespace="lab_beta")
```

### Custom Entity Patterns

```python
from docmine.extraction import RegexEntityExtractor

extractor = RegexEntityExtractor()
extractor.add_pattern("custom", r"\bCUST-\d{4}\b")

pipeline = KOSPipeline(entity_extractor=extractor)
```

### Statistics

```python
stats = pipeline.stats(namespace="project")
print(stats)
# {
#   "namespace": "project",
#   "information_resources": 10,
#   "segments": 1420,
#   "entities": 45,
#   "entity_types": 5
# }
```

## Testing

### Quick Smoke Test

```bash
python validate_kos.py
```

### Full Test Suite

```bash
pip install pytest
pytest tests/ -v
```

### Specific Tests

```bash
# Idempotency tests
pytest tests/test_idempotency.py -v

# Exact recall tests
pytest tests/test_exact_recall.py -v
```

## Migration from Old System

If you have existing chunk data:

```bash
python scripts/migrate_legacy_chunks.py \
    --old-db knowledge.duckdb \
    --new-db knowledge_kos.duckdb \
    --namespace legacy
```

## Troubleshooting

### "No duplicates but count seems wrong"

Check namespace isolation:
```python
# Wrong: mixing namespaces
pipeline.ingest_file("doc.pdf", namespace="ns1")
pipeline.count_segments(namespace="ns2")  # Returns 0!

# Right: use same namespace
pipeline.ingest_file("doc.pdf", namespace="ns1")
pipeline.count_segments(namespace="ns1")  # Correct
```

### "No entities extracted"

Check your entity extractor patterns:
```python
entities = pipeline.list_entities()
if not entities:
    # Try with default patterns
    from docmine.extraction import RegexEntityExtractor
    extractor = RegexEntityExtractor()
    print(extractor.list_patterns())  # See what patterns are active
```

### "Semantic search returns nothing"

Ensure embeddings were generated:
```python
# Embeddings are created automatically during ingest
# But you can verify:
pipeline.ingest_file("doc.pdf")
results = pipeline.search("test query")
if not results:
    # Check segment count
    count = pipeline.count_segments()
    print(f"Segments: {count}")
```

## Examples

### Run the Demo

```bash
python examples/kos_demo.py
```

### Read the Docs

- Quick: `README_KOS.md`
- Deep: `docs/knowledge_centric_migration.md`

## What's Different?

### Idempotency

```python
# Old system: creates duplicates
old_pipeline.ingest_file("doc.pdf")  # 100 chunks
old_pipeline.ingest_file("doc.pdf")  # 200 chunks (duplicates!)

# New system: idempotent
pipeline.ingest_file("doc.pdf")  # 100 segments
pipeline.ingest_file("doc.pdf")  # Still 100 segments ✓
```

### Stable IDs

```python
# Old system: auto-increment IDs (not stable)
# chunk_id = 1, 2, 3... (changes on re-ingest)

# New system: deterministic hashes
# segment_id = sha256(namespace + uri + provenance + text)
# Same document → same IDs, always
```

### Provenance

```python
# Old system: basic page info
{"page_num": 5, "chunk_index": 3}

# New system: full provenance
{
    "page": 5,
    "sentence": 3,
    "sentence_count": 3,
    "source_uri": "file:///path/doc.pdf"
}
```

## Next Steps

1. **Read the full README**: `README_KOS.md`
2. **Understand the architecture**: `docs/knowledge_centric_migration.md`
3. **Run examples**: `python examples/kos_demo.py`
4. **Write your own code**: Use the API examples above

## Support

- Documentation: `README_KOS.md`, `docs/`
- Tests: `tests/`
- Examples: `examples/`
- Issues: https://github.com/bcfeen/DocMine/issues

---

**DocMine KOS: Production-ready knowledge extraction**

✅ Idempotent • ✅ Stable IDs • ✅ Entity Tracking • ✅ Exact Recall • ✅ Multi-Corpus

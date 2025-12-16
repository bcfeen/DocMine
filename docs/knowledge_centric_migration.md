# Knowledge-Centric Migration: From Document RAG to KOS

## Executive Summary

This document outlines the architectural migration of DocMine from a **document-centric RAG system** to a **knowledge-centric Knowledge Organization System (KOS)**. The fundamental shift is from treating "chunks" as ephemeral retrieval units to treating **stable knowledge objects** (Information Resources, Segments, Entities) as first-class primitives.

## The Problem: Why Chunks Are Insufficient

### Current Document-Centric Flow

```
PDF → Pages → Chunks → Embeddings → Database
                ↓
         Search Query → Retrieve Chunks
```

**Issues:**

1. **No Stable Identity**: Re-ingesting the same document creates duplicate chunks
2. **No Provenance**: Chunks lose their source location details
3. **No Entity Tracking**: Cannot recall "all mentions of CCNA001"
4. **No De-duplication**: Same content from different sources creates duplicates
5. **Query-Only**: No exact recall mechanism; everything depends on semantic similarity
6. **No Multi-Corpus Support**: Cannot separate different projects/namespaces

### What Happens When You Re-Ingest

Current behavior:
```python
pipeline.ingest_file("paper.pdf")  # Creates 142 chunks
pipeline.ingest_file("paper.pdf")  # Creates ANOTHER 142 chunks (284 total!)
```

This is unacceptable for a production system.

## The Solution: Knowledge-Centric Architecture

### New Knowledge-Centric Flow

```
Source File → InformationResource (IR)
                      ↓
            ResourceSegments (deterministic)
                      ↓
            Entity Extraction (NER)
                      ↓
            Link Segments ↔ Entities
                      ↓
    Semantic Search + Exact Recall
```

### Core Primitives

#### 1. InformationResource (IR)

A **stable object** representing a source document.

**Properties:**
- `id`: UUID/ULID primary key
- `namespace`: Multi-corpus support (e.g., "lab_alpha", "project_beta")
- `source_type`: pdf, md, txt, web, etc.
- `source_uri`: **Canonical stable identity** (e.g., `file:///abs/path/doc.pdf`)
- `content_hash`: SHA256 of content for change detection
- `metadata_json`: Arbitrary metadata (author, title, date, etc.)
- `created_at`, `updated_at`: Timestamps

**Invariant:** Same `source_uri` → Same IR (idempotent upsert)

#### 2. ResourceSegment (Segment)

A **stable, re-ingestable, de-duplicatable** unit of knowledge.

**Properties:**
- `id`: **Deterministic hash** (see Stable Identity section)
- `ir_id`: Foreign key to InformationResource
- `segment_index`: Order within the IR
- `text`: The actual content (1-3 sentences, normalized)
- `provenance_json`: **Precise location** (page, offsets, bounding boxes, heading path, etc.)
- `text_hash`: SHA256 of normalized text
- `embedding`: Optional embedding vector (stored separately)
- `created_at`: Timestamp

**Invariant:** Same (IR + provenance + normalized text) → Same segment ID

#### 3. Entity

A **stable object** representing a real-world concept.

**Properties:**
- `id`: UUID primary key
- `namespace`: Same as IR namespace
- `type`: gene, protein, experiment, condition, strain, reagent, person, paper, etc.
- `name`: Canonical name
- `aliases_json`: Alternative names, abbreviations
- `metadata_json`: Type-specific attributes
- `created_at`, `updated_at`: Timestamps

**Examples:**
- `{type: "strain", name: "CCNA001", aliases: ["CCN-A-001"]}`
- `{type: "gene", name: "BRCA1", aliases: ["breast cancer 1"]}`
- `{type: "person", name: "Albert Einstein"}`

#### 4. Segment-Entity Links

Many-to-many relationship between segments and entities.

**Properties:**
- `segment_id`: Foreign key
- `entity_id`: Foreign key
- `link_type`: mentions, about, primary_subject
- `confidence`: 0.0-1.0 (extraction confidence)

**Composite unique constraint:** (segment_id, entity_id, link_type)

### Stable Identity Rules

#### IR Identity

**Rule:** `source_uri` must be canonical and stable.

**Examples:**
- Local file: `file:///Users/alice/docs/paper.pdf`
- Web snapshot: `web://example.com/article?snapshot=20250101`
- Git blob: `git://repo/commit123/path/file.md`

**Idempotency:**
```python
register_ir("file:///doc.pdf")  # Creates IR
register_ir("file:///doc.pdf")  # Returns existing IR (upsert by source_uri)
```

**Change Detection:**
```python
content_hash_old = "abc123..."
content_hash_new = "def456..."  # Content changed
# System detects change and re-segments
```

#### Segment Identity

**Rule:** Segments must be deterministic across re-ingestions.

**Formula:**
```python
segment_id = sha256(
    namespace +
    ir_source_uri +
    provenance_key +
    normalized_text
)
```

**Provenance Keys by Source Type:**

| Source Type | Provenance Key | Example |
|-------------|----------------|---------|
| PDF | `page:sentence_index` | `3:5` (page 3, sentence 5) |
| Markdown | `heading_path:para:sentence` | `intro/background:2:1` |
| CSV/Table | `table:row:col` | `results:42:strain_id` |
| Plain Text | `line_number:sentence` | `150:3` |

**Text Normalization:**
```python
def normalize_text(text: str) -> str:
    return " ".join(text.strip().split())
```

**Example:**
```python
# PDF page 5, sentence 3
segment_id = sha256(
    "lab_alpha" +                     # namespace
    "file:///paper.pdf" +             # IR source_uri
    "5:3" +                           # provenance_key
    "The CCNA001 strain showed..."   # normalized text
)
```

**Idempotency:**
```python
ingest("paper.pdf")  # Creates segment abc123...
ingest("paper.pdf")  # Finds existing segment abc123... (no duplicate!)
```

## Migration Phases

### Phase 1: Core Infrastructure (CURRENT)

**Goal:** Implement data models and storage without breaking existing code.

**Deliverables:**
1. New schema (information_resources, resource_segments, entities, links)
2. Stable ID generation utilities
3. New `KnowledgeStore` class (parallel to `DuckDBBackend`)
4. Entity extraction baseline (regex)

**Status:** Can run side-by-side with old system

### Phase 2: Ingestion Rewrite

**Goal:** Replace chunk-based ingestion with knowledge-centric pipeline.

**Deliverables:**
1. `register_information_resource(source_uri, source_type, namespace)`
2. `segment_resource(ir)` - deterministic segmentation
3. `extract_entities(segments)` - NER pipeline
4. `link_entities(segments, entities)` - store relationships
5. CLI: `docmine ingest --namespace X --path ./docs`

**Backward Compatibility:** Old `ingest_file()` wraps new pipeline

### Phase 3: Retrieval & Query

**Goal:** Replace "retrieve chunks" with knowledge-centric APIs.

**Deliverables:**
1. Semantic search returns segments with provenance
2. Exact recall: `get_segments_for_entity(entity_id)`
3. Entity browser: `list_entities(namespace, type=None)`
4. IR browser: `get_segments_for_ir(ir_id)`
5. Updated `search()` API with citation support

**Example:**
```python
# Semantic search (old behavior still works)
results = pipeline.search("CCNA001 growth rate")

# NEW: Exact recall
entity = pipeline.get_entity("CCNA001", type="strain")
segments = pipeline.get_segments_for_entity(entity.id)
# Guaranteed to return ALL mentions, even if embedding missed them
```

### Phase 4: Migration & Cleanup

**Goal:** Migrate old chunk data and deprecate old schema.

**Deliverables:**
1. Migration script: old chunks → segments (marked legacy)
2. Tests for idempotency
3. Tests for exact recall
4. Documentation updates
5. Remove old `chunks` table (optional, can keep for rollback)

## Object Model and Invariants

### Invariants

1. **IR Uniqueness:** `(namespace, source_uri)` is unique
2. **Segment Determinism:** Same (IR + provenance + text) → Same segment_id
3. **Entity Uniqueness:** `(namespace, type, name)` is unique
4. **No Orphan Segments:** Every segment must have a valid `ir_id`
5. **Provenance Preservation:** Every segment must have `provenance_json`
6. **Namespace Isolation:** Entities in namespace A cannot link to segments in namespace B

### Database Schema

```sql
-- Information Resources
CREATE TABLE information_resources (
    id TEXT PRIMARY KEY,                    -- UUID
    namespace TEXT NOT NULL,
    source_type TEXT NOT NULL,              -- pdf, md, txt, web
    source_uri TEXT NOT NULL,               -- Canonical URI
    content_hash TEXT NOT NULL,             -- SHA256 of content
    metadata_json TEXT,                     -- JSON metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(namespace, source_uri)
);

-- Resource Segments
CREATE TABLE resource_segments (
    id TEXT PRIMARY KEY,                    -- Deterministic hash
    ir_id TEXT NOT NULL,
    segment_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    provenance_json TEXT NOT NULL,          -- JSON with page/offset/etc
    text_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ir_id) REFERENCES information_resources(id) ON DELETE CASCADE
);

-- Entities
CREATE TABLE entities (
    id TEXT PRIMARY KEY,                    -- UUID
    namespace TEXT NOT NULL,
    type TEXT NOT NULL,                     -- gene, protein, strain, etc
    name TEXT NOT NULL,                     -- Canonical name
    aliases_json TEXT,                      -- JSON array
    metadata_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(namespace, type, name)
);

-- Segment-Entity Links
CREATE TABLE segment_entity_links (
    segment_id TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    link_type TEXT NOT NULL,                -- mentions, about, primary
    confidence REAL NOT NULL,               -- 0.0 - 1.0
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (segment_id) REFERENCES resource_segments(id) ON DELETE CASCADE,
    FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE CASCADE,
    UNIQUE(segment_id, entity_id, link_type)
);

-- Embeddings (separate table for efficiency)
CREATE TABLE embeddings (
    segment_id TEXT PRIMARY KEY,
    model TEXT NOT NULL,                    -- Model name/version
    vector FLOAT[] NOT NULL,                -- Embedding vector
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (segment_id) REFERENCES resource_segments(id) ON DELETE CASCADE
);

-- Indices
CREATE INDEX idx_ir_namespace ON information_resources(namespace);
CREATE INDEX idx_segments_ir ON resource_segments(ir_id);
CREATE INDEX idx_entities_namespace ON entities(namespace);
CREATE INDEX idx_entities_type ON entities(type);
CREATE INDEX idx_entities_name ON entities(name);
CREATE INDEX idx_links_segment ON segment_entity_links(segment_id);
CREATE INDEX idx_links_entity ON segment_entity_links(entity_id);
```

## Entity Extraction Strategy

### Pragmatic Hybrid Approach

We need entity extraction to be:
1. **Cheap:** No expensive API calls per segment
2. **Deterministic:** Same input → Same output (temperature=0)
3. **Extensible:** Easy to add domain-specific extractors

### Implementation Plan

#### Baseline: Regex Extractor

Start with simple pattern matching:

```python
class RegexEntityExtractor:
    patterns = {
        "strain": r"\b[A-Z]{2,4}[A-Z0-9]{3,6}\b",  # e.g., CCNA001
        "gene": r"\b[A-Z]{2,5}[0-9]{1,2}\b",       # e.g., BRCA1
        "email": r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b",
        # ... more patterns
    }
```

**Pros:** Fast, free, deterministic
**Cons:** Low recall, brittle

#### Optional: LLM Extractor

For higher-quality extraction (when configured):

```python
class LLMEntityExtractor:
    def extract(self, text: str) -> List[Entity]:
        prompt = f"""Extract entities from this text.
        Return JSON: [{{"type": "strain", "name": "CCNA001", "confidence": 0.95}}, ...]

        Text: {text}
        """
        response = llm.complete(prompt, temperature=0.0)
        return parse_json(response)
```

**Configuration:**
```python
# Use regex (default)
pipeline = PDFPipeline(entity_extractor="regex")

# Use LLM (requires API key)
pipeline = PDFPipeline(entity_extractor="llm", llm_model="gpt-4")
```

## Retrieval & Query Changes

### Old API (Semantic Only)

```python
results = pipeline.search("CCNA001 experiments", top_k=5)
# Returns chunks, but might miss mentions if embedding similarity is low
```

### New API (Semantic + Exact Recall)

```python
# Semantic search (improved with provenance)
results = pipeline.search("CCNA001 experiments", top_k=5)
for r in results:
    print(f"📄 {r['source_uri']} (page {r['page_num']})")
    print(f"💬 {r['text']}")
    print(f"📍 Provenance: {r['provenance']}")
    print(f"⭐ Score: {r['score']:.3f}")

# NEW: Exact recall (guaranteed complete)
entity = pipeline.get_entity("CCNA001", type="strain")
if entity:
    segments = pipeline.get_segments_for_entity(entity.id)
    print(f"Found {len(segments)} segments mentioning CCNA001")
    for seg in segments:
        print(f"  - {seg.ir.source_uri} @ {seg.provenance}")

# NEW: Entity browsing
strains = pipeline.list_entities(namespace="lab_alpha", type="strain")
for strain in strains:
    print(f"{strain.name}: {len(strain.segments)} mentions")

# NEW: IR browsing
ir = pipeline.get_ir_by_uri("file:///paper.pdf")
segments = pipeline.get_segments_for_ir(ir.id)
print(f"Document has {len(segments)} segments")
```

## Success Criteria

After migration, these operations must work:

### 1. Idempotent Ingestion

```python
pipeline.ingest_file("paper.pdf", namespace="test")
count1 = pipeline.count_segments(namespace="test")

pipeline.ingest_file("paper.pdf", namespace="test")
count2 = pipeline.count_segments(namespace="test")

assert count1 == count2, "Re-ingestion created duplicates!"
```

### 2. Exact Recall

```python
# Semantic search might miss some mentions
semantic_results = pipeline.search("CCNA001")
print(f"Semantic search found: {len(semantic_results)}")

# Exact recall finds ALL mentions
entity = pipeline.get_entity("CCNA001")
exact_results = pipeline.get_segments_for_entity(entity.id)
print(f"Exact recall found: {len(exact_results)}")

assert len(exact_results) >= len(semantic_results)
```

### 3. Provenance Tracking

```python
results = pipeline.search("growth rate")
for r in results:
    assert "source_uri" in r
    assert "provenance" in r
    assert r["provenance"]["page"] is not None
```

### 4. Multi-Corpus

```python
pipeline.ingest_file("alpha.pdf", namespace="lab_alpha")
pipeline.ingest_file("beta.pdf", namespace="lab_beta")

alpha_entities = pipeline.list_entities(namespace="lab_alpha")
beta_entities = pipeline.list_entities(namespace="lab_beta")

assert len(alpha_entities) > 0
assert len(beta_entities) > 0
assert set(alpha_entities).isdisjoint(set(beta_entities))
```

## Implementation Notes

### Directory Structure

```
docmine/
├── docs/
│   └── knowledge_centric_migration.md    # This file
├── docmine/
│   ├── models/                           # NEW: Data models
│   │   ├── __init__.py
│   │   ├── information_resource.py
│   │   ├── resource_segment.py
│   │   ├── entity.py
│   │   └── stable_id.py                  # ID generation utilities
│   ├── storage/
│   │   ├── duckdb_backend.py            # OLD: Keep for migration
│   │   └── knowledge_store.py            # NEW: KOS storage
│   ├── extraction/                       # NEW: Entity extraction
│   │   ├── __init__.py
│   │   ├── base_extractor.py
│   │   ├── regex_extractor.py
│   │   └── llm_extractor.py
│   ├── ingest/
│   │   ├── pdf_extractor.py             # Keep, enhance with provenance
│   │   ├── chunker.py                    # REPLACE with segmenter
│   │   └── segmenter.py                  # NEW: Deterministic segmentation
│   ├── search/
│   │   ├── semantic_search.py            # Update for new schema
│   │   └── exact_recall.py               # NEW: Entity-based retrieval
│   └── pipeline.py                       # Update for KOS
├── tests/                                 # NEW: Comprehensive tests
│   ├── test_stable_ids.py
│   ├── test_idempotency.py
│   ├── test_exact_recall.py
│   └── test_migration.py
└── scripts/
    └── migrate_legacy_chunks.py          # Migration script
```

### Key Design Decisions

1. **SQLite for simplicity:** Avoid overengineering with graph DBs
2. **Deterministic IDs:** SHA256 hashing ensures reproducibility
3. **Namespace isolation:** Support multiple projects/corpora
4. **Provenance-first:** Every segment knows its exact source
5. **Incremental migration:** Old and new systems coexist during transition
6. **Entity extraction at ingestion:** Not at query-time
7. **Hybrid search:** Semantic (fuzzy) + Exact (complete)

## Conclusion

This migration transforms DocMine from a simple document chunker into a true knowledge organization system. The key insight is that **knowledge objects must be stable, identifiable, and traceable**—not ephemeral query-time constructs.

The end result is a system where:
- Re-ingesting documents doesn't create duplicates
- Every piece of information has provenance
- Exact recall guarantees completeness
- Entities are first-class objects
- Multi-corpus operation is natural

This is what production RAG systems should be.

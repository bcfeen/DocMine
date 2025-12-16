### Performance Benchmarks

*Measured on Darwin 24.3.0 (arm64) with Python 3.13.5*

| PDF Size | Pages | Extraction Time | Chunks Created | Chunking Time | Embedding Time | **Total Time** |
|----------|-------|-----------------|----------------|---------------|----------------|----------------|
| Large | 48 | 0.358s | 1582 | 3.423s | 13.45s | **104.178s** |
| Medium | 12 | 0.092s | 457 | 0.987s | 5.091s | **30.325s** |
| Small | 15 | 0.119s | 233 | 0.676s | 3.747s | **17.27s** |

**Search Performance:**
- Average query latency: 424.66ms
- Measured over 10 queries

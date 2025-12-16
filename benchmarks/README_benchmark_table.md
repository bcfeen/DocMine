### Performance Benchmarks

*Measured on Darwin 24.3.0 (arm64) with Python 3.13.5*

| PDF Size | Pages | Extraction Time | Chunks Created | Chunking Time | Embedding Time | **Total Time** |
|----------|-------|-----------------|----------------|---------------|----------------|----------------|
| Large 34Pages | 16 | 0.074s | 517 | 1.407s | 4.448s | **32.09s** |
| Medium 13Pages | 48 | 0.373s | 1582 | 3.33s | 14.453s | **106.116s** |
| Small 8Pages | 15 | 0.111s | 233 | 0.806s | 11.26s | **24.872s** |

**Search Performance:**
- Average query latency: 144.6ms
- Measured over 10 queries

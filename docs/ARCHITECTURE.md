# Architecture — 0.2.0

## Primary browser path

1. **PDF.js 5.6.205** renders in the browser using the original bytes. Its PDFViewer rendering queue and bounded canvas settings retain only a limited working set of page canvases. Text/search/selection and navigation do not wait for AI indexing. Thumbnails render lazily.
2. **Flask + Waitress** exposes a single-owner local API. Loopback is the default. Network binding requires an access key; cookie authentication, same-origin mutation checks and a Host allow-list guard private document endpoints. No CORS or external-AI endpoint configuration is exposed.
3. **PyMuPDF process adapter (`document.py`)** inspects PDFs, extracts layout blocks and tables, performs selective Tesseract OCR and renders requested evidence images. A two-worker spawned process pool isolates document work from HTTP threads.
4. **Managed snapshots + atomic JSON library metadata** preserve old library IDs during migration and use content-derived IDs for new imports. Full SHA-256 revisions disambiguate content versions. Original user files are never modified.
5. **SQLite/WAL evidence index (`evidence.py`)** stores each page and passage with document ID, content revision, physical page, exact extracted text and normalized rotated-page bounds. Index writes are progressive. FTS5 is normalized independently from source text. OCR warnings accompany page records.
6. **Retrieval** first enforces an explicit document-ID scope, then combines BM25 candidates, heading/coverage relevance and optionally local embedding similarity. Embeddings are cached per immutable chunk ID and model. A character budget limits returned context. Reranking is a deterministic heuristic, not an untested cross-encoder.
7. **Generation boundary** receives untrusted document excerpts and source IDs. The model never creates authoritative citation metadata. Strict responses must parse as the expected JSON and every claim must be an exact contiguous span in each cited retrieved source. Unknown IDs, malformed responses and unsupported claims cause refusal. Without a model, the UI explicitly shows retrieved excerpts.
8. **Evidence navigation** resolves each citation again from the index before opening its PDF/page and highlighting normalized coordinates. A changed managed file or missing old chunk produces an explicit error instead of redirecting the citation to new content.
9. **PWA** caches application assets only. Documents, images and API responses are deliberately excluded. Offline local-file reading is possible after the shell has loaded, but indexing/AI remain server-dependent.

## Existing desktop path

`core.py`, `ui.py`, `pdf_jobs.py`, and `qt_jobs.py` remain compatible with the prior Windows reader. Its repaired setup, isolation and tests are retained. Desktop Q&A/summary generation now goes through exact-excerpt validation, and document identity survives change detection. `--migrate-desktop` copies its library to the browser store, preserving IDs and titles while rebuilding the evidence index.

## Boundaries and limits

- Library JSON is single-process metadata; do not run concurrent web servers on the same state directory. The process pool never writes library metadata.
- Citation identity validation proves where retrieved text came from; it does not prove OCR correctness, retrieval completeness or semantic entailment of non-strict paraphrases.
- Table rows/columns are heuristic extraction results. The UI provides the original page for verification.
- A summary is a bounded evidence review, with explicit partial-coverage wording. A comparison is an aligned text comparison, not a complete contract redline.
- Browser-native OCR, browser-native embeddings, user accounts, synchronization and cloud collaboration were not added.

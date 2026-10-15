# Audit — LocalPDF Insight 0.2.0

Audited the repaired 0.1.1 desktop project supplied in this workspace before modifying it. No matching PDF project repository was returned by the connected GitHub repository search. A local Git history was initialized; no unrelated repository was used.

| Classification | Finding | Treatment |
|---|---|---|
| Keep | PyMuPDF engine; loopback-only Ollama transport; isolated PDF worker processes; atomic metadata writes; repaired desktop tests and launchers | Retained and adapted |
| Fix | IDs changed with file timestamps; stale indexes; hidden OCR failures; unnormalized Arabic search | Stable identity/revision separation, explicit failures and search normalization/aliases |
| Replace | One QLabel raster image per page; no native selection or proper reader search | Browser PDF.js viewer with bounded rendering, text layer, search, layouts and reading state |
| Replace | Model-generated filenames/page numbers in prose | Model supplies only retrieval IDs; code resolves authoritative document/page/coordinates; strict mode validates exact text |
| Missing | Structured chunks, embeddings, real multi-document scopes, browser storage model, tables and comparison | SQLite passage/FTS index, optional local embedding adapter, enforced scopes, managed snapshots and evidence-linked workflows |
| Missing | Mobile/RTL/PWA | Responsive bilingual web UI; static-only service worker; server-side OCR/AI clearly separated |

The original "HybridIndex" was page-level BM25 with optional vision reranking, not a vector hybrid index. Every page was raster-cached during indexing. The new primary web path creates images only when needed and combines lexical/structural retrieval with optional cached local embeddings and a deterministic coverage/heading reranker.

The previous implementation had no continuous reader, page thumbnails, outline, selectable PDF text, search highlighting, persistent reading position, library collections/tags, explicit selected-document scope, deterministic claim validation, structured table workflow, or browser/PWA entry point. Arabic OCR was hardcoded to English, with failures swallowed.

No application framework rewrite was required for the document engine. PySide6 cannot itself serve as a browser interface, so only the primary presentation layer was replaced. Flask/Waitress were added as a small local service boundary; a second frontend framework/build system was not introduced.

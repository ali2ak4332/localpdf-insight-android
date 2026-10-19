# LocalPDF Insight 0.2.0


Release remediation: **BLOCKED — no release candidate or production approval**. See [current remediation operations](docs/REMEDIATION_OPERATIONS.md) and `RELEASE_REMEDIATION_REPORT.md`. The prior reports are historical evidence, retained unchanged.

A private PDF reader for **Open → Read → Search → Ask → Verify → Compare**.
The new primary interface runs in a browser. The previous PySide6 desktop interface remains available.

## Source conveniences

Use **Sources** to choose the active PDF set, **Chat** for suggested questions and grounded Q&A, and **Studio** to create or reopen briefings, study exercises and comparisons. Studio reuses the existing evidence pipeline and saves each output as a new local snapshot. Citation clicks continue to open the original PDF/page, including after a server restart or document rename.

Select a passage for Explain, Summarize, Define, Translate, Ask or **Save note**. Strict mode requires exact candidate excerpts. Assisted mode currently falls back to complete source extracts; unverified interpretations and translations are withheld. Unmatched selections may be saved as explicitly unverified personal notes, but are never used as AI evidence.

Reports disclose sampled coverage. Flashcards and quizzes are simple exact-source recall exercises with cited answers. Sources with detected broken text are excluded from suggestions/study prompts. Generated outputs and notes live in the existing local `evidence.sqlite3`; back up the complete data directory to retain PDFs and source links. These tools require the local server and add no cloud service.

See [workflow proof and limitations](docs/convenience-validation/README.md). The controlled matrix passed, but a stronger adversarial relevance test still fails B1. Live-model reliability and external platform gates remain unverified.

## Android reader (no Ollama)

Current Android source is **0.2.7-print-pdf (code 9)**, including Share PDF,
Print PDF, the compact toolbar and reading tools. See
[source reconciliation and current validation](docs/SOURCE_RECONCILIATION_2026-10-19.md).

An installable personal Android reader is available separately. It works locally on Android 10+ with a current WebView, and supports reading, search, notes, handwritten signing, highlights, added Arabic/English text, supported form fields and saving edited PDF copies. It contains no AI or OCR. Originals and their note links remain unchanged. See [Android installation and build instructions](android/README.md) and [editing validation](docs/android-editing-validation/README.md).

## Run the browser application

Use 64-bit Python 3.11–3.13. Extract the entire project folder, then run these commands inside it.

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -c requirements-validation.lock -e ".[web]"
.\.venv\Scripts\python.exe -m localpdf_insight.web
```

Linux / macOS:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -c requirements-validation.lock -e '.[web]'
.venv/bin/python -m localpdf_insight.web
```

Open **http://127.0.0.1:8765**. Keep the terminal/server running.
`SETUP_WEB_WINDOWS.bat` also installs and starts the browser version using the existing Python detection and optional local-AI setup.

No Node build or CDN is required to run the application: PDF.js 5.6.205 and its worker, character maps, fonts and decoders are bundled.

### Enable local AI and optional embeddings

Without a model, Ask returns clearly labelled retrieved excerpts with clickable sources. It does not pretend those excerpts are a generated answer.

Install and run Ollama separately, download a model you want to use, and set its installed model name before starting the server. For example, if `qwen2.5:3b` is already installed:

```powershell
$env:LOCALPDF_MODEL = "qwen2.5:3b"
.\.venv\Scripts\python.exe -m localpdf_insight.web
```

```bash
LOCALPDF_MODEL=qwen2.5:3b .venv/bin/python -m localpdf_insight.web
```

Optional semantic search: set `LOCALPDF_EMBED_MODEL` to an installed Ollama embedding model and reindex the documents. The app does not download models implicitly. Without that setting, retrieval uses SQLite FTS5/BM25, heading relevance and query coverage. Embedding errors fall back explicitly to lexical search. Ollama requests go only to `127.0.0.1:11434`; proxies and redirects are disabled.

**Strict Evidence Mode** requires exact candidate spans, followed by a question/evidence
review for generated Q&A. The review must cover the question without omissions and assess
subject, entity, period, metric, intent, qualifications and conflicts. Unsupported parts
are withheld. The review uses local Ollama and still needs live reliability validation.
Both modes release server-copied source passages, retaining qualifications; model-written
amounts, obligations and other factual prose do not pass merely because IDs are valid.
Assisted paraphrases currently fall back to extracts. Report sampling remains disclosed.
The release gate target and exact digest are in the remediation operations guide; no
current Ollama runtime or passing live gate is claimed.

### OCR, including Arabic

Install Tesseract and the language packs your documents need. The OCR integration uses PyMuPDF's local Tesseract support.

Ubuntu / Debian:

```bash
sudo apt-get install tesseract-ocr tesseract-ocr-eng tesseract-ocr-ara
LOCALPDF_OCR_LANGS=eng+ara .venv/bin/python -m localpdf_insight.web
```

Windows: install Tesseract with English and Arabic trained data. If the data is not discovered automatically, set `TESSDATA_PREFIX` to the directory containing `eng.traineddata` and `ara.traineddata`. Then:

```powershell
$env:LOCALPDF_OCR_LANGS = "eng+ara"
.\.venv\Scripts\python.exe -m localpdf_insight.web
```

Reindex documents after installing a missing language. Native text is preferred. Missing/unusable text triggers full-page OCR; large image regions on mixed pages trigger partial OCR. OCR errors and Arabic extraction-order warnings are visible. OCR text is not guaranteed exact: inspect the cited page, especially names and numbers.

### Bring over the old desktop library

Stop any browser server using the same data directory, then:

```powershell
.\.venv\Scripts\python.exe -m localpdf_insight.web --migrate-desktop
```

```bash
.venv/bin/python -m localpdf_insight.web --migrate-desktop
```

Migration copies readable PDFs into managed snapshots and **preserves existing document IDs and titles**. It leaves the desktop library and original files untouched. It reports unavailable/locked files. Choose **Warnings / reindex → Reindex** for migrated documents to build the new passage index. Repeated migration does not create duplicates. Old free-text model citations cannot be retroactively verified.

### Android / another device on your private network

The browser reader does not require Windows. PDF rendering occurs on the phone; storage, indexing, OCR and Ollama run on your computer/server. That computer must remain on and reachable. `localhost` on your phone means the phone itself: use the server computer's actual LAN address.

Example PowerShell configuration; replace `192.168.1.42` with your computer's LAN address and the access-key value with a long random secret:

```powershell
$env:LOCALPDF_TOKEN = "replace-with-a-long-random-access-key"
$env:LOCALPDF_HOSTS = "localhost,127.0.0.1,192.168.1.42"
.\.venv\Scripts\python.exe -m localpdf_insight.web --host 0.0.0.0 --port 8765
```

Open `http://192.168.1.42:8765` in Android Chrome and enter the key. Allow TCP 8765 on the computer's firewall for your private network if required. This is a single-owner application, not a multi-tenant public hosting service.

An installed PWA/service worker requires **HTTPS** on the phone; ordinary LAN HTTP supports browser reading but does not establish PWA installability. Use a trusted HTTPS reverse proxy for installed-phone access, include its hostname in `LOCALPDF_HOSTS`, and set `LOCALPDF_HTTPS=1` so session cookies are Secure. HTTPS also protects documents and the access key in transit. A desktop localhost connection is treated as a secure context by supporting browsers.

The PWA caches only the application shell/static dependencies. **It does not cache PDFs, API responses or evidence.** Once the shell is installed, an offline browser can open a local PDF; library access, indexing, OCR and AI require the server. It is not a standalone offline Android AI application.

## Reader workflow

- Import one or more PDFs or drag them onto the app. The first page becomes readable before indexing completes. The import limit is 200 MB per PDF.
- Use continuous, single-page or two-page mode; fit width/page; numeric zoom; touch pinch; page navigation; outline and lazy thumbnails.
- Native search highlights text with previous/next navigation. **OCR results** searches indexed passages, including successful OCR and Arabic search aliases, and opens highlighted source regions.
- Reading position and zoom are saved per document in browser local storage. Recent documents, original filenames, titles, collections, tags, dates and indexing state persist on the server.
- Choose **Ask this PDF**, **Ask selected documents** or **Ask library**. The actual document names appear beneath the scope selector.
- Click a citation to reopen its document/revision, navigate to its physical PDF page and highlight the source region. Printed page labels may differ from physical PDF page numbers.
- Expand **Sources / Evidence** for exact extracted text and optional page image. Add `?debug=1` to the reader URL for passage IDs and retrieval scores.
- Select a passage for Explain, Summarize, Define, Translate or Ask. The server checks the selection against indexed text; cross-page or mismatched selections are rejected.
- **Tables on this page** offers a cell grid, tab-separated copy, Markdown copy, CSV export and Ask. Spreadsheet formula prefixes are escaped on CSV export.
- Select two to four PDFs and choose Compare. Aligned textual differences cite each document. Identical aligned text is omitted. Unmatched passages are not classified: the comparison is not an exhaustive legal redline.
- Switch the interface between Arabic and English. Numbers, source labels and mixed-script content remain isolated from the interface direction.

Shortcuts: `Ctrl/Cmd+O` open, `Ctrl/Cmd+F` search, `Ctrl/Cmd+K` ask; arrows/Page Up/Page Down navigate when not typing. Native text can be selected and copied with the operating system's normal clipboard controls.

## Data and privacy

By default, web state lives in a `web` directory beneath the existing LocalPDF application-data directory. Set `LOCALPDF_DATA` to an absolute directory to choose a different location.

- `library.json`: managed PDF identities and library metadata; atomic replacement.
- `documents/`: immutable imported PDF snapshots, separate from original user files.
- `evidence.sqlite3`: revisioned page records, structured passages, FTS5 index and optional embedding cache.
- `images/`: page images created only when requested.
- Browser storage: reading preferences and static PWA shell; no persistent PDF cache.

Copies are detected by full SHA-256, not partial file samples. Renaming a title does not change identity. Replacing PDF bytes creates a new imported revision; stale sources are rejected. Exported/password-unlocked copies are stored locally, and passwords are not retained. Back up the complete web data directory while the server is stopped. Do not run multiple server processes against the same data directory.

## Validation

```bash
python -m pip install -c requirements-validation.lock -e '.[web,desktop,test]'
QT_QPA_PLATFORM=offscreen python -m pytest
```

On Windows, omit `QT_QPA_PLATFORM=offscreen`. Arabic OCR's test is skipped if its language pack is missing; install it for the complete suite.

Browser tests (Node is only required for testing):

```bash
npm ci
npx playwright install chromium
npm run test:browser
```

If necessary set `LOCALPDF_TEST_PYTHON` to your virtual environment's Python and `CHROMIUM_EXECUTABLE` to an existing compatible Chromium binary. The browser test launches its own server and temporary synthetic documents, exercises a 150-page reader flow and checks citations, scopes, comparison, RTL/mobile layout, touch zoom and offline shell behavior. It does not contact Ollama.

See `docs/AUDIT.md`, `docs/ARCHITECTURE.md`, `docs/VALIDATION.md`, and `PROJECT_STATE.md` for the audited scope and remaining limits.

## Remaining limits

- Live Ollama generation, embeddings and vision require installed models and were not validated against a running model in this environment. Deterministic validation and provider boundaries are tested independently.
- Strict mode is evidence extraction, not a guaranteed complete answer to every question. Non-strict model interpretations require human checking.
- Heuristic structure/table extraction is not a comprehensive layout model. Footnotes, repeating headers/footers, reading order, charts and complex tables remain challenging. XLSX export is not included.
- Summary modes sample/retrieve a bounded set of passages and explicitly disclose partial coverage. They must not be treated as exhaustive lists of risks or obligations.
- Comparisons identify aligned text changes; additions/deletions and layout-only changes are not exhaustively classified.
- Arabic native-search aliases preserve source text; they cannot repair a broken font's Unicode map. Some Arabic PDFs and OCR output still have imperfect word order. Review the page image.
- No on-device embedding model or OCR engine is bundled in the browser. OCR, indexes and AI require the local server. There is no GitHub Pages-only full-function deployment.
- The previous desktop UI is retained as a compatibility path. The new reading experience is the browser UI.

## Technical references

Implementation references: [Mozilla PDF.js](https://mozilla.github.io/pdf.js/), [PyMuPDF OCR](https://pymupdf.readthedocs.io/en/latest/recipes-ocr.html), [PyMuPDF page/table APIs](https://pymupdf.readthedocs.io/en/latest/page.html), [SQLite FTS5](https://www.sqlite.org/fts5.html), [Ollama embed API](https://docs.ollama.com/api/embed), [MDN service workers](https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API).

## Included Git history

The release archive also contains `LocalPDF_Insight.history.bundle`. To restore the complete authoritative repository, run this from the directory containing the bundle:

```bash
git clone LocalPDF_Insight.history.bundle LocalPDF_Insight_Git
```

The extracted `LocalPDF_Insight_Project` folder is ready to run without this optional Git restoration step. No external remote is configured.

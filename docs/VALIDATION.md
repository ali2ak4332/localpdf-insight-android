# Historical foundation validation — 0.2.0

Current live-model release decision: **FIX BEFORE USE**. See [the validation-only release pass](validation-release/REPORT.md). The figures and unverified gates below describe the earlier foundation build.

Validated on Linux with Python 3.12.14, PyMuPDF 1.26.6, Flask 3.1.3, Waitress 3.0.2, PDF.js 5.6.205, and headless Chromium 153 driven by Playwright 1.62.1.

## Results

- **48 Python tests passed**, including the 18 original desktop/core regression tests.
- **13 browser workflow checks passed**, with no uncaught browser JavaScript errors.
- The final SQLite connection-lifecycle fix was additionally verified with **29 evidence/API tests**; these overlap the 48-test suite rather than representing extra distinct tests.
- An installable Python wheel built successfully; its contents include the web application, PDF.js reader/worker, character maps, fonts and decoder assets.
- Python compilation, JavaScript syntax and `git diff --check` passed.
- Desktop and 390 × 844 mobile screenshots were visually inspected. The mobile screenshot includes the correctly opened page-18 evidence highlight.

Python coverage: original loading/rendering/indexing/export/window-switch regressions; source document/page/text/coordinates; unknown-source and unsupported-claim refusal; selected-document exclusion; full-file revision handling; duplicate imports; friendly-title stability; Arabic normalization/native retrieval/mixed-script text; real English and Arabic scanned-page OCR; OCR-language failure reporting; rotated pages and bounded image rendering; structured tables; comparison provenance; embedding cache/provider-boundary behavior; password/corrupt files; scoped API access; forged text-selection rejection; Host/origin/auth guards; legacy-library migration; summary mode evidence selection.

Browser checks:

1. Open a synthetic 150-page PDF, render its text layer and keep the active canvas count bounded.
2. Navigate by page number and outline.
3. Search native text with highlighted matches on the correct page.
4. Switch single/spread/continuous layouts and persist page/zoom.
5. Ask in strict mode without a model; verify explicitly labelled excerpts and highlighted page-18 citations.
6. Reimport identical bytes without creating a duplicate identity.
7. Follow a citation after switching PDFs; verify it remains at the target page after saved-position restoration would otherwise run.
8. Restrict API retrieval to selected documents.
9. Compare document versions with links to each source.
10. Exercise phone-width RTL controls and two-contact touch zoom without horizontal UI overflow.
11. Open an Arabic PDF and retrieve its source with an Arabic query.
12. Install the service-worker shell; verify no API/document data enters its cache.
13. Reload offline and open a local 150-page PDF without uploading it.

The ordinary Playwright CDN download was unavailable. Browser tests used a separate Chromium binary obtained through the npm package distribution. That binary and the test-only Tesseract language packs are **not bundled in the application**. The included test runner supports either standard Playwright Chromium or an explicit `CHROMIUM_EXECUTABLE`.

## Not established by these tests

- Live Ollama text, embedding or vision output quality/performance. Provider and citation validation were tested with deterministic responses; browser Q&A used explicitly labelled no-model excerpts.
- Physical Android device behavior, Windows installation, or an HTTPS-installed Android PWA. Tested mobile behavior is Chromium emulation with touch input, not a physical-device claim.
- OCR accuracy across all Arabic fonts/scans or all native Arabic reading orders. One native fixture intentionally exercises presentation-form/broken-map warnings; one actual Arabic scan exercises OCR retrieval.
- Exhaustive summary/comparison coverage, every possible malformed PDF, or multi-user/public-server security. Those are outside this release's proven behavior.

Reproduction commands and optional language setup are in the README. Machine-readable test results are in `docs/validation/`.

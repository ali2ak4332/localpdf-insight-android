# Android 0.2.2 focused validation

Implementation commit: `0180782e2be9bf95132fcf17388c87229aa14b86`. Full behavior, primary-source inspiration and limitations are in `../../../ANDROID_CHANGELOG.md`.

- `baseline-reproduction.json`: the added reader check fails on unchanged previous app.js (stale highlights after closing).
- `reader-results.json`: 20 passing offline reader workflows, including all close paths in English/Arabic UI, retained query reuse and pending-search cancellation.
- `editor-results.json`: 17 passing signing/export workflows. The existing Highlight export check now closes a real search over an unsaved PDF highlight before saving.
- `export-inspections.json`: independently extracted PyMuPDF annotation/form/page/pixel evidence for saved PDFs.
- `retained-pdf-highlight.pdf` and PNG: actual exported Highlight survives search closing; visually checked. Only the intended page differs from its original in this fixture.
- `search-closed.png`: visible PDF without temporary match highlights; visually checked.
- `release-checks.json`: signed build/lint, unchanged certificate and app ID, increased code 4, matching assets, no permissions or backup/cleartext/debugging.
- `inspiration.json`: direct upstream source link and scope of review. Upstream tests were reviewed, not executed.

Reproduce browser checks from the repo root with Playwright 1.62.1, Chromium >=140 and PyMuPDF installed:

```sh
mkdir -p validation-artifacts/reader validation-artifacts/editor
LOCALPDF_TEST_ARTIFACTS="$PWD/validation-artifacts/reader" node tests/browser/android.cjs
LOCALPDF_TEST_ARTIFACTS="$PWD/validation-artifacts/editor" node tests/browser/android_editor.cjs
```

Use `NODE_PATH` for externally installed Playwright, `CHROMIUM_EXECUTABLE` for an external browser and `LOCALPDF_TEST_PYTHON` for a Python containing PyMuPDF when needed. The tests route packaged assets locally and block external network/API traffic; there is no app server or Ollama.

Build with JDK 17 (including jlink), SDK 35 / build-tools 35.0.0, and the separate private signing key as described in `../../../android/README.md`.

Physical Android, native Files/keyboard/Back and installed upgrade/data retention remain unverified. No desktop test suite was run. No internet capability or dependencies were added to the product.

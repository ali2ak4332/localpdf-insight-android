# Android signing/editing validation — 2026-10-14

Version `0.2.0-editor` extends reader checkpoint `d2f2fedd9cc4621fcb5b11aa46b9286498143cce`. It reuses bundled PDF.js annotation editing/writing and the existing Android device-storage adapter. Python, SQLite, Ollama, retrieval and deterministic desktop evidence handling are unchanged.

## Execution evidence

The editor runner performs real finger/mouse gestures, operates the actual PDF.js UI and saves actual PDF bytes. Only the narrow Android Files export transport is mocked in Chromium. PyMuPDF independently opens the saved bytes, inspects annotation/page/form metadata and renders before/after images. Signature page 2 and mixed Arabic/English text were visually inspected in those independent renders. Fixtures are synthetic agreements, an intrinsically rotated page and a real AcroForm; this is not validation of arbitrary third-party PDFs or physical hardware.

| Gate | Result |
|---|---|
| Editing browser workflows | 17 passed; no browser errors or external network attempts |
| Existing Android reader workflows | 18 passed; no browser errors or network attempts |
| Existing desktop reader workflows | 13 passed |
| Existing Studio workflows | 8 passed |
| Signed clean release build / Android lint | Passed; 0 lint errors, 4 existing shell advisories |
| APK signer / installation identity | Same certificate/application ID; version code raised from 1 to 2 |
| Binary manifest / assets | Zero permissions; no Internet, backup, cleartext or debugging; all 296 static files match source |
| Physical Android / native Files picker | Not executed; no device/emulator available |

Focused checks cover handwritten signing on the correct page, undo/redo/delete, closing tools restoring scrolling, multi-page and intrinsically rotated annotations, Arabic/English added text and long-token wrapping, native-text highlighting, filled text/checkbox form fields, saved-copy reopening, original bytes/IDs remaining unchanged, original source-note navigation after edits/reload, pending export locking forms, cancelled/failed/missing-channel exports retaining edits, and unsaved document-switch cancellation including active drawing sessions. Detailed results are in the JSON records.

Material defects discovered during implementation were fixed: omitted standalone PDFViewer highlight palette; cancelled loading not stopping import/source identity reassignment; active ink not yet reaching annotationStorage; text insertion not locking its target; long unbroken tokens clipped by a fixed-width canvas; forms accepting changes after the save snapshot; early unlocking before saved-copy reopening; absent native channel falsely reporting a blocked browser download; and dirty-status reflow moving the page under a drawing/highlight pointer. Back cannot dismiss the text dialog during insertion. No model, citation generator or source-index algorithm was replaced.

## Reproduce

Install the existing web/test dependencies including PyMuPDF, then:

```sh
npm ci
npx playwright install chromium
npm run test:android-editor
npm run test:android
npm run test:browser
npm run test:studio
```

Optional `LOCALPDF_TEST_PYTHON`, `CHROMIUM_EXECUTABLE`, `LOCALPDF_TEST_ARTIFACTS` select tooling/diagnostics. The executed environment used Playwright 1.58.2 and Chromium 153 with a 412×915 mobile/touch viewport; the repository retains its existing package lock. Native build commands and the physical-device checklist are in `../../android/README.md`. Diagnostic screenshots/PDF fixtures stay outside release deliverables.

## Limits

- Native WebView/Files-provider success/cancel, touch pressure/stylus, installed upgrade/data retention and process lifecycle require physical verification. Matching signer/version is build evidence, not a performed installation.
- Editing adds PDF annotations and fills supported AcroForm fields. It does not rewrite existing page text, flatten edits, provide certificate signatures or implement XFA forms.
- Arabic typed text is an image annotation with its text retained as alternative text, not selectable/searchable page text. Arabic form values, encrypted-file editing and uncommon font/permission combinations were not separately exercised.
- Save is explicit. Unsaved edits can be lost by forced process death; interrupted native export requires retry. Provider cleanup of a failed/partial file is best effort.
- The original and edited copy remain separate. Original notes still point to the original; no existing citation metadata is regenerated or moved.
- Nothing requires Internet/Ollama. A Files provider chosen by the user may upload the exported copy; app storage itself has backup/cloud transfer disabled.

Historical desktop AI release blockers remain unchanged. This reader-only update makes no AI reliability claim.

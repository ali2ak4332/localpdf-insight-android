# Print PDF: 0.2.7 / code 9

One focused improvement on top of `4150aa2` (0.2.6 Share PDF, the full latest source and history).

## What changed

- **Print PDF** (printer icon after Save copy) sends the open PDF to Android's own print
  screen: installed printers, *Save as PDF*, paper size, copies and page ranges.
- It prints the current bytes, including unsaved signatures, highlights, text and form
  edits. An unedited PDF is passed through byte-for-byte. Printing does not save an app
  copy or clear the unsaved-edits warning.
- Reuses the existing PDF.js `saveDocument`/`getData` path and the same bounded,
  origin-restricted native export channel (new `purpose: "print"`). `PdfPrint` passes the
  exact bytes to `PrintManager` through a `PrintDocumentAdapter`, so text and ink print as
  vectors at printer resolution rather than screen pixels. No permission, provider,
  dependency or network access is added.
- Each print uses its own private cache session (`cache/pdf-prints/<uuid>/`), deleted when
  the print job finishes, fails or is cancelled. Leftovers from a killed process are removed
  at the next launch after 6 hours; recent sessions are kept because the print UI may still
  re-request the document. Share sessions and other cache files are untouched.
- Password-protected PDFs are refused before any bytes leave the reader (Android's print
  preview cannot open encrypted PDFs); the native side also refuses them defensively.
- The second toolbar row grows from 8 to 9 columns; English/Arabic still fit 320/360/412px.

## Executed checks

- Browser (offline mobile Chromium, actual bundled PDF.js and IndexedDB, mocked native
  transport): **26 editor/export** (23 existing + 3 new print), **21 reader**,
  **12 reading-tool** and **13 desktop reader** workflows passed. Zero browser errors and
  zero attempted network requests.
  New print cases: exact original bytes when unedited; unsaved page-2 signature included,
  edits stay unsaved, original identity/revision/notes/bookmark unchanged; native failure,
  password-protected refusal (English and Arabic, no bytes sent) and missing bridge all
  release the busy guard with Save copy/Share/Print still usable.
- PyMuPDF 1.28.2 independently reopened and rendered the printed bytes: one Ink annotation
  on page 2 (remembered blue 4.5 pt pen), pages 1 and 3 pixel-identical to the original.
  The page-2 render was visually inspected. Summaries: `pdf-inspections/`.
- **33 native print-policy checks** (`tests/native/pdf_print_policy.py`): production
  `PdfPrint` compiled against minimal API doubles — Arabic job name, unique private sessions,
  unsafe-name rejection, page count / unknown fallback, protected-PDF refusal, layout info,
  cancelled layout/write, exact byte pass-through (including 0x80–0xff), all-pages report,
  finish-time cleanup of only its own session, stale-only launch cleanup, missing print
  service propagation; plus manifest/resource/controller static checks.
  Existing **26 share-policy** and **18 screen-policy** checks still pass.
- All Android Java (`MainActivity`, controllers, `PdfPrint`, `PdfShare`) compiles with
  `javac -Xlint:all --release 17` against the Android API jar and aapt2-generated `R`, with
  small androidx/BuildConfig stubs: no errors or warnings. aapt2 compiled and linked all
  resources, including the new English/Arabic strings.

## Not done here — please run before installing

- **No Gradle build, lint or APK**: this environment cannot reach Google's Maven/SDK
  servers, and the private signing key is (correctly) not in the source archive. Build with
  the same key as 0.2.6 so the APK updates in place and keeps the library and notes:
  `cd android && ./gradlew assembleRelease lintRelease`.
- The sandbox Chromium (141) predates `Map.getOrInsertComputed` and `Blob.bytes`, which
  the bundled PDF.js uses. Browser suites ran with `tests/browser/legacy_chromium_polyfill.cjs`
  (`node --require …`), which adds only those two methods; on current Chromium omit it.
- Physical Android: the real print preview, printers, Save as PDF, page-range selection and
  rotation during printing are untested. Policy tests use API doubles, not the framework.

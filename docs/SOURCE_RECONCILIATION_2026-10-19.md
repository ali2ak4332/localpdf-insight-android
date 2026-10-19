# Android source reconciliation — 19 October 2026

The repository is reconciled to **LocalPDF Insight Android 0.2.7-print-pdf / code 9**. The desktop/Python package remains version 0.2.0; that separate declaration is not the Android release version.

## Provenance

- Original main: [`d1221f6b6f9c9bca477a4bf69bf48321851baef5`](https://github.com/ali2ak4332/localpdf-insight-android/commit/d1221f6b6f9c9bca477a4bf69bf48321851baef5).
- Recovered source: `LocalPDF_Insight_Android_Source_0.2.7.zip`, SHA-256 `d515adc367a90fac489a3960d65e9f902ee2d2049001af13e2d7cbf21dedb5fc`.
- Its Git bundle was restored separately and confirmed HEAD `0c9658e56a5f694f02bb531e8a55c8966bfac138`, the Print PDF commit. GitHub's existing history is preserved by this reconciliation commit; the bundle and its unrelated test-output corpus are not added to GitHub.
- Existing saved APK: `LocalPDF_Insight_Android_0.2.7_0c9658e.apk`, SHA-256 `56d2da00a92c93d4524e3a2bd0cc56cdb15c4c872400db4ec4f714825bf20607`. Independently verified package `app.localpdf.insight`, name `0.2.7-print-pdf`, code `9`, valid v2 signature; all **298 bundled reader assets** exactly match recovered source.
- The source archive's historical 0.2.7 changelog says no APK had been built at that earlier checkpoint. The subsequently saved APK above exists and verifies. Current checks below independently establish an unsigned source build and lint success; the earlier changelog is retained as historical evidence.

## Confirmed differences

| Area | Original GitHub main | Recovered / reconciled source |
|---|---|---|
| Android version | 0.2.1-page-jump / code 3 | 0.2.7-print-pdf / code 9 |
| Core PDF.js modules | Six `vendor/pdfjs/build/*.mjs` runtime files absent from the tracked tree | Restored all six modules from the complete package; they are executable source assets |
| Search | Page-jump fix present | Search close/Back/Escape clear temporary matches while retaining query/user highlights; whole-word search added |
| Toolbar/text | Earlier toolbar and text-dialog behavior | Compact two-row English/Arabic icon toolbar and Add Text Back-cancel reset |
| Reading | Earlier reader | Remembered pen settings, optional keep-screen-on and per-document bookmarks |
| Share | No native PDF share helper/provider | Current edited/unedited PDF sent through a narrow FileProvider cache and Android chooser |
| Print | No native PDF print helper | Current edited/unedited PDF sent to Android PrintManager through PdfPrint; protected PDFs refused; originals/dirty state preserved |
| Packaging safeguards | Broad build-directory ignore patterns omit PDF.js runtime | Targeted Android-output ignores, explicit vendor-runtime exceptions, six-module Gradle preflight, unsigned-APK asset/class verifier |

Core comparison paths: `android/app/build.gradle`, native `MainActivity.java` and `PdfExportController.java`, new `PdfPrint.java`, `PdfShare.java`, `PdfShareProvider.java`, `ReadingScreenController.java`, `src/localpdf_insight/static/{app.js,app.css,index.html,pdf_editor.js,mobile_toolbar.js,mobile_reading.js}` and `ANDROID_CHANGELOG.md`.

Production reader/native changes come from the recovered source. Reconciliation-specific changes are limited to ignore rules, the missing-runtime build check, build/verifier portability, documentation and current evidence. Existing GitHub workflows and setup instructions are retained.

## Identity, data and signing

Application ID `app.localpdf.insight`, API29 minimum/API35 target, WebView origin `https://appassets.androidplatform.net`, existing IndexedDB/local-storage identity and original-document identity logic are retained. No data-clearing migration is introduced. Original PDFs and source-linked notes remain separate from saved edited copies. Share/print cache cleanup does not target the library. Unsaved editing sessions remain non-persistent drafts.

Verified saved-APK certificate SHA-256:

`f0c38147d5bfe371d7144578b4e952fabad9dd2fe98137ea4be630bb6537a153`

Signing remains externally configured through the existing `LOCALPDF_ANDROID_*` environment variables. The original private key was not present in the source packages; no new key was generated. No private signing material, APKs, toolchains, dependency caches, Git bundle or unrelated desktop test-run dumps are added. A default CI debug signature cannot update the personally signed app. Install future correctly signed updates over the existing app; do not uninstall or clear data to bypass a signature mismatch.

## Checks run now

- Final JDK17 / Gradle8.9 / AGP8.7.3 / API35 `assembleRelease` and `lintRelease` with signing disabled: **passed**, **0 lint errors, 4 warnings**. Warnings: API33-only back attribute, JavaScript-enabled WebView review, obsolete v27 resource qualifier and missing monochrome adaptive icon.
- Missing-runtime regression: temporarily withholding `pdf.sandbox.min.mjs` makes `syncReaderAssets` fail with the intended missing-module error; the module was restored.
- APK verifier: all **298 source assets** match exactly; native print/share/screen classes and AndroidX dependencies are present; no signing is applied. Unsigned APK SHA-256: `402d3947e9761ee5e28838c1d66a9d410bf2f40c5506cb3fbb17e999ddec139a`.
- Current Chrome Headless Shell **155.0.8059.84**, Playwright **1.62.1**, **without the legacy polyfill**: **21 Android reader + 26 editor/export/share/print + 12 reading-tool workflows passed**. No browser errors or unexpected external/API requests. Real PDF.js output bytes are independently inspected with PyMuPDF; native transport is mocked in these browser suites.
- Desktop reader compatibility suite: **13 workflows passed** using the shared reader assets and a local test server. The full Python/Studio suites were not rerun because backend code is unchanged.
- Production helpers compiled with Android API doubles: **33 print + 26 sharing + 18 screen-policy checks passed**. These are not Android framework/device tests.
- Saved signed APK: signature, package/version, runtime assets and class presence verified independently.
- Private-material filename/content checks: no private-key or high-confidence API-token matches in staged deliverables.

Current logs, JSON results and production hashes: [`reconciliation/2026-10-19/`](reconciliation/2026-10-19/). The older `legacy_chromium_polyfill.cjs` is retained as historical harness support and was not loaded.

Reproduce with `bash scripts/android/build_unsigned.sh` after the documented tools are installed, `node tests/browser/android.cjs`, `node tests/browser/android_editor.cjs`, `node tests/browser/android_reading_tools.cjs`, and the three `tests/native/*_policy.py` scripts. `CHROMIUM_EXECUTABLE` and `NODE_PATH` can select an externally installed current browser/Playwright. No signing key is needed for unsigned validation.

## Remaining limits

No physical Android/WebView installation or upgrade was performed. Installed library/notes retention, real Files/Share permission enforcement, recipient handling, Android print preview, printers, Save as PDF, page-range behavior, rotation/Back/keyboard behavior on the user's device and TalkBack remain device checks. Browser/API doubles do not establish these outcomes. The previously saved signed APK is verified, but a new update-compatible signed APK cannot be produced without the original external key.

Android reader remains offline with no internet or broad storage permission and no AI/OCR. The chosen print service or recipient app controls its own work after handoff.

Platform references: [Android app signing](https://developer.android.com/studio/publish/app-signing), [secure file sharing](https://developer.android.com/training/secure-file-sharing), [custom print documents](https://developer.android.com/training/printing/custom-docs).

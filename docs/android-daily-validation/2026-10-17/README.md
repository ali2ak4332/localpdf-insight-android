# Android 0.2.4 focused validation

Implementation commit: `8aa53107c534e4f5deca31cad34c936c183f7f3c`. The only product behavior change is the Android Back path for the Add Text dialog: it calls the existing Cancel action rather than only closing the dialog.

- `baseline-results.json`: the previous app passes the first three editor workflows, then fails the added check because the closed dialog leaves its tool set to Text instead of Read.
- `reader-results.json`: 21 passing offline reader workflows, including compact toolbar, navigation, storage, search and original notes.
- `editor-results.json`: 19 passing signing/export workflows. The new check cancels partially entered English/Arabic text via the Back bridge, confirms Read/icon reset, reopens Add Text, compares document/revision/page/count/annotation hash, and checks unsaved page-2 ink remains. It then uses the existing real export workflow.
- `export-inspections.json`: independent PyMuPDF page/annotation/form/render difference summaries for actual saved PDF bytes. The signature export following cancellation contains the expected page-2 Ink, no other annotations, and no changed pixels on pages 1/3. Its rendered page 2 was visually checked.
- `inspiration.json`: reviewed primary-source PDF.js cleanup, cancellation tests and related issue. Upstream tests were not executed and upstream code was not copied.
- `release-checks.json`: signed build/lint, unchanged certificate/app ID, code increase 5 to 6, exact bundled assets and manifest checks.

Reproduce using Playwright 1.62.1, a Chromium >=140 executable, and PyMuPDF:

```sh
mkdir -p validation-artifacts/reader validation-artifacts/editor
LOCALPDF_TEST_ARTIFACTS="$PWD/validation-artifacts/reader" node tests/browser/android.cjs
LOCALPDF_TEST_ARTIFACTS="$PWD/validation-artifacts/editor" node tests/browser/android_editor.cjs
```

Set `NODE_PATH`, `CHROMIUM_EXECUTABLE` and `LOCALPDF_TEST_PYTHON` if dependencies are installed outside the project. Tests route bundled assets locally and reject external network/API traffic; there is no Python app server or Ollama. Build with JDK 17 (including jlink), Android SDK 35/build-tools 35.0.0 and the separate update key as described in `../../../android/README.md`.

Physical Android/WebView, native Back/Files/menus/keyboard, TalkBack and installed upgrade/data retention remain unverified. Browser tests call the existing Back handler and mock only the narrow native export transport. Desktop suites were not run. Original editor limitations remain.

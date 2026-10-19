# Android compact-toolbar validation

Implementation commit: `3edef8688c78e3bb08d7142e7c9c7623b38d1eff`. Version 0.2.3-compact-toolbar, code 5.

`reader-results.json`: 21 passing offline mobile reader workflows. The new UI check covers branding removal, two-row height, on-screen controls at 320/360/412 pixels, English/Arabic labels, retained icons after translation, library/notes access, and view-options controls/dismissal.

`editor-results.json`: 18 passing signing/export workflows. The new UI check covers per-mode icons, selected ink colour, text cancellation and command labels in both languages. Existing tests continue to cover touch signature, zoom/rotation, selected deletion, highlight, text, forms, safe export/cancel/error handling and original source-note identity.

`export-inspections.json`: independent PyMuPDF page/annotation/form/render difference summaries for actual saved PDF bytes. The actual page-2 signature render was visually inspected. These tests mock only the narrow Android Files transport.

`release-checks.json`: signed build/lint, original certificate/application ID, code increase 4 to 5, exact matching packaged assets, and manifest checks. The full Chrome browser could not start under the current process restrictions; the official Headless Shell ran the tests successfully without requesting elevated permissions.

Reproduce with Playwright 1.62.1, PyMuPDF, and a Chromium >=140 executable that runs in the available environment:

```sh
mkdir -p validation-artifacts/reader validation-artifacts/editor
LOCALPDF_TEST_ARTIFACTS="$PWD/validation-artifacts/reader" node tests/browser/android.cjs
LOCALPDF_TEST_ARTIFACTS="$PWD/validation-artifacts/editor" node tests/browser/android_editor.cjs
```

Set `NODE_PATH`, `CHROMIUM_EXECUTABLE` and `LOCALPDF_TEST_PYTHON` if the test dependencies are installed outside the project. Test requests route bundled assets locally and reject external network/API traffic. Build with JDK 17, SDK 35 / build-tools 35.0.0 and the separate private key using `../../../android/README.md`.

Physical Android, native Files/select/keyboard/Back, TalkBack and installed upgrade/data retention remain unverified. No desktop suite was run. Original app capabilities and privacy limitations remain as documented.

# Android reading tools, 0.2.5 / code 7

Implemented 17 October 2026 from the complete 0.2.4 source/history checkpoint `a5ec43f3afa576c66ecf1680aa9ea42186dbd089` (implementation `8aa53107c534e4f5deca31cad34c936c183f7f3c`).

## Changes

- Whole-word checkbox in native PDF text search uses bundled PDF.js `entireWord`. Query reuse and find-bar close cleanup remain. English and Arabic tests distinguish whole words from substrings. As before, unusable PDF font mappings/missing spaces limit native text search; no OCR or guessed word reconstruction was added.
- Pen colour and thickness are validated and remembered locally. Defaults survive restart and a new document; tool selection still starts in Read. Restored blue 4.5-point ink was drawn, exported, and independently inspected for exact colour/width.
- Keep-screen-on option in View options defaults off. It stores a local preference and requests the Activity flag only with a loaded, visible PDF. Native resumed/focused state independently gates it. Pause, focus loss, navigation/error and close clear it; no wake-lock or new permission.
- Bookmarks live under the existing Contents/Pages panel. Add/remove the current page, list sorted pages and jump. Storage is keyed by original document byte identity. Reimports reuse bookmarks; edited copies are separate. No bookmark is embedded in exported PDF bytes or conflated with source notes.
- Existing two compact primary toolbar rows remain. New secondary checkbox/bookmark action hit areas are 48 CSS px; older compact controls retain their existing dimensions and need on-device accessibility assessment.

## Executed verification

- **21/21 Android reader workflows.** Actual local storage, opening, search-close cleanup, layouts, protected/native/Arabic/broken-font/scanned PDFs, note/source identity and offline behavior.
- **20/20 Android editing/export workflows.** Actual PDF.js Ink/text/highlight/form output, move/undo/redo/delete, Add Text cancellation/Back, export success/failure/cancel/pending/interruption guards, old source-note identity and original bytes. Added persisted pen and bookmark/export separation checks. Native export transport is mocked; exported PDF bytes are real and inspected/rendered with PyMuPDF.
- **12/12 focused reading-tool workflows.** English/Arabic whole words and reopening; keep-screen defaults, no-document state, visibility, preference off, reload and failed PDF; repeated bookmark toggles, sorted jumps, document separation, duplicate import identity, restart, Arabic and narrow/large-font layout; corrupt settings/bookmarks, storage write failure and late outline completion after switching to Bookmarks.
- **18/18 native screen policy assertions.** Production Java controller compiled against minimal Android/WebKit API test doubles: trusted origin/main frame, invalid origin/user-info/port/actions, focus/pause/resume, off switch, reset, destroy and unsupported-feature behavior. This is a policy unit test, not native instrumentation.
- **13/13 desktop reader and 8/8 Studio browser workflows.** Shared desktop reader behavior remains intact; no desktop AI implementation changes.
- **1,196 Python tests passed, one existing Arabic OCR skip.** A first run with the host's older PyMuPDF 1.26.6 failed six existing Arabic layout assertions; installing the project's locked PyMuPDF 1.28.2 resolved them without changing product code or assertions. The isolated environment installs this project for subprocess tests and uses Qt offscreen. Full output is retained. The export-inspection fixture uses the current `pymupdf` import name so a deprecated-alias warning cannot contaminate its JSON output.
- JavaScript parsing and `git diff --check` passed.
- Full Gradle source build, lint and final package checks are recorded in `release-checks.json` and `android-lint-release.txt` after final signing. Every bundled reader asset is compared byte-for-byte against source.

Browser: Google Chrome for Testing Headless Shell 148.0.7778.57, offline mobile emulation at 412×915 and 320×640. Tests made no external network requests. The system Chromium launch was blocked by local socket restrictions; the official headless shell ran within the same sandbox, without changing security settings.

## Reproduce

Use the repository's Python validation requirements/environment, install the project, and set a supported Chromium executable (140+):

```sh
python -m pip install -r requirements-validation.lock
python -m pip install --no-deps -e .
QT_QPA_PLATFORM=offscreen python -m pytest
CHROMIUM_EXECUTABLE=/path/to/chrome-headless-shell npm run test:android
CHROMIUM_EXECUTABLE=/path/to/chrome-headless-shell npm run test:android-editor
CHROMIUM_EXECUTABLE=/path/to/chrome-headless-shell npm run test:android-reading
python tests/native/reading_screen_policy.py
CHROMIUM_EXECUTABLE=/path/to/chrome-headless-shell npm run test:browser
CHROMIUM_EXECUTABLE=/path/to/chrome-headless-shell npm run test:studio
```

Set `LOCALPDF_TEST_PYTHON` to the validation Python for browser suites. The native test accepts `JAVAC` for an alternate compiler. Gradle setup/build steps are in `scripts/android/README.md`; keep the private update key outside source.

## Still unverified

No physical Android device/emulator was attached. Installed upgrade/data retention, actual screen timeout/lock/background/Files picker behavior, native Back/keyboard/select menus, WebView renderer death/process termination, SAF writes/providers, TalkBack and system font scaling need a phone check. Save before leaving a document; unsaved editing sessions still are not persisted drafts. No Play AAB, Console submission, account verification or store approval is claimed. See `docs/ANDROID_RELEASE_PREFLIGHT.md` for API36/toolchain, signing, privacy/listing, accessibility and distribution gates.

Suggested phone smoke: update without uninstalling; confirm old PDFs/notes; bookmark page 2; restart and return; search a whole word in English/Arabic; choose blue/thick pen, restart, sign and Save copy; confirm original bookmarks stay with the original. Enable keep-screen while reading, wait beyond normal timeout, open Files/background/lock, then return and turn it off. Repeat in airplane mode.

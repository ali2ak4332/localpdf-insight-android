# Share PDF: 0.2.6 / code 8

One focused Android handoff improvement, implemented from full latest source/history
`fbe5b3766c4549586a717c6a4ebc96af4184ad46`, not the initial 0.2.0 checkpoint.
Implementation: `7b111bd18fe5d31d671e646c704c1a21840fe472`.

## Executed checks

- 21 reader, 23 editor/export and 12 reading-tool browser workflows passed.
  Actual bundled PDF.js, local IndexedDB and offline mobile Chromium were used;
  the narrow Android export transport was mocked. Zero browser errors or attempted
  external requests. New share cases prove exact original bytes when unedited,
  edited signature bytes on page 2, retained original identity/revision/notes and
  bookmark, dirty state retained, failure/missing bridge recovery, and subsequent
  Save copy. English/Arabic icons fit two rows at 320/360/412px.
- Independent PyMuPDF 1.26.6 reopened and rendered actual shared/saved PDF bytes.
  Shared signature is an Ink annotation on page 2, with pages 1/3 pixel-identical
  to the original. The page-2 render and an additional Poppler render were visually inspected. Existing separate
  copy ink, rotation, deletion, Arabic/English text, wrapped text, Highlight and
  form export assertions passed. Inspection JSON summaries are retained; new
  browser screenshots are not packaged.
- 26 native share helper/manifest checks and 18 existing screen-policy checks
  passed with production Java compiled against minimal API doubles. Intent action,
  MIME, stream/ClipData URI, read-only grants, chooser, Arabic filename, unique
  private sessions, byte preservation, failure propagation, recent-file retention,
  expired-only cleanup, narrow nonexported provider and no permissions were checked.
  These are policy checks, not Android framework or recipient integration tests.
- Full signed Gradle 8.9 / AGP 8.7.3 / JDK 17 source build and lint passed (2m24s).
  APK signature/certificate comparison, application ID/version increment, 298 exact
  reader assets, native classes and packaged manifest checked. Four lint warnings:
  UnusedAttribute, SetJavaScriptEnabled, ObsoleteSdkInt, MonochromeLauncherIcon;
  none introduced by the new share code. No lint errors.
- `git diff --check` passed; full history retains the original checkpoint and
  latest 0.2.5. Source archive excludes build caches and all private signing material.

## Inspiration and scope

Reviewed 18 October 2026: [Acrobat Send a copy](https://helpx.adobe.com/acrobat/mobile/share-files/send-shared-copy.html)
(page dated 18 August 2026) informs an explicit attachment handoff, not cloud-link
sharing. [PDF.js downloadOrSave](https://github.com/mozilla/pdf.js/blob/master/web/app.js)
commits current editing and chooses saved bytes when annotation storage is populated;
the existing LocalPDF pipeline already follows that pattern and is reused.
[PDF.js scripting tests](https://github.com/mozilla/pdf.js/blob/master/test/integration/scripting_spec.mjs)
were briefly reviewed for form blur/save behavior, not executed. Android's
[secure file sharing](https://developer.android.com/training/secure-file-sharing/share-file),
[provider setup](https://developer.android.com/training/secure-file-sharing/setup-sharing)
and [FileProvider reference](https://developer.android.com/reference/androidx/core/content/FileProvider)
informed content URIs, narrow cache scope and temporary read grants. No code copy,
new dependency or license change. The staged print/share proposal was not treated
as verified source; only sharing was adapted to this complete current project.

## Reproduce

Use Playwright with Chromium 140+ and PyMuPDF available to Python:

```sh
node tests/browser/android.cjs
node tests/browser/android_editor.cjs
node tests/browser/android_reading_tools.cjs
python3 tests/native/pdf_share_policy.py
python3 tests/native/reading_screen_policy.py
```

Set `NODE_PATH`, `CHROMIUM_EXECUTABLE`, `LOCALPDF_TEST_ARTIFACTS` and optionally
`LOCALPDF_TEST_PYTHON` / `JAVAC` for the installed environment. Build with SDK 35,
Build Tools 35.0.0, JDK 17, Gradle 8.9 and the externally supplied private update
key: `gradle -p android assembleRelease lintRelease`. No signing key is included.

## Limits and device smoke still needed

No device/emulator, installed upgrade, native chooser, real URI access/permissions,
email app/delivery, delayed draft read, native picker/keyboard/Back, TalkBack or
process-death test ran. Do not infer these from API doubles or screenshots.
Desktop/Python suites were not rerun for this Android-only change.

Install over the previous version without uninstalling. Check old PDFs/notes,
share an original via email, sign page 2 and share again, open the received
attachment in another reader, cancel/retry and then Save copy. Check Arabic names,
rotation/backgrounding and returning to unsaved edits. Cache may be evicted by
Android; copies older than 24 hours are removed at a subsequent controller launch,
so old email drafts may need a fresh attachment. Printing remains unchanged.

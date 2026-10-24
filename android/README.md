# LocalPDF Insight — Android reader and signing

**Apt Reader branch:** Android development version `0.3.0-apt-dev`, code 10,
display name Apt Reader, same package/data identity as this reader. Optional
Gemma analysis is implemented through **View options → Analyze PDF**, but the
current model failed quality diagnostics and this is not an approved release.
See [`../docs/apt/README.md`](../docs/apt/README.md) and the
[current validation report](../docs/apt/VALIDATION.md). The inherited instructions
below describe the previous LocalPDF release.

Personal Android reader, version `0.2.7-print-pdf` (version code 9), extending `0.2.6-share-pdf`, `0.2.5-reading-tools` and signing checkpoint `4320b11c01fbb50b5f883c37a5314f6bf76486f2`. Cumulative updates are in `../ANDROID_CHANGELOG.md`.

## Install and use

1. Download `LocalPDF_Insight_Android.apk` to the phone and open it.
2. If Android asks, allow this source to install the APK, then install.
3. Open **LocalPDF Insight** and tap **Open PDF**. The Android document picker lets you choose one or more PDFs.
4. The branding strip is removed. Two compact icon rows contain the filename, library, view options, notes/language, page navigation, search, signing and save. Tap the sliders icon beside the filename for zoom, page layout and rotation. Buttons retain English/Arabic accessibility labels and tooltips.
5. Read, zoom, search, use Contents/Pages, or select a passage and choose **Save note**.
   Enter a page number and press the keyboard's **Go / Enter** action to jump and release keyboard focus.
   Close search with its toolbar button, Back or Escape to clear temporary match highlights; the query remains available for reuse. User-created PDF highlights remain intact.
6. In search, tick **Whole words** to exclude substrings in native PDF text. It uses PDF.js word boundaries; missing spaces or broken font mappings in a PDF can limit results. Closing search still clears temporary matches without deleting user highlights. Passage/library searches are separate.
7. **Sign / Draw** remembers the chosen black/blue pen colour and thickness on this phone, including after restarting. It does not auto-select old annotations.
8. In **View options**, **Keep screen on while reading** is off by default. Enable it if wanted; it applies only with a loaded PDF while this app is visible and focused. It releases for backgrounding, dialogs/pickers, navigation and closing. Keeping the display lit uses more battery.
9. In **Contents and thumbnails**, select **Bookmarks**. Bookmark the current page, tap a saved page to jump, or remove a bookmark. These bookmarks stay on this phone, are separate for each PDF identity and are not embedded in Save copy exports. Re-importing identical bytes reuses the same bookmarks.
10. Open the **Notes** speech-bubble icon to reopen saved comments. Tap the source link to return to its original PDF/page.

To sign or annotate:

1. Open the PDF and go to the desired page. Tap the **Edit / Sign** pen-on-page icon.
2. Choose **Sign / Draw** and draw with a finger or stylus. Select a mark to move or resize it. **Undo**, **Redo** and **Delete selected** icons handle changes before saving. Editing-tool and colour menus use icons that reflect the current selection; their native menus keep full text labels.
3. Choose **Add text** to place typed Arabic/English text, or **Highlight** and drag across native text. Return to **Read / select** to scroll normally. Back from the Add Text dialog uses the same cancellation cleanup as Cancel, restoring the Read tool and allowing Add Text to reopen normally. Closing the edit toolbar also returns to reading.
4. Existing supported PDF form fields can be filled directly on the page.
5. Tap the **Save copy** download icon, choose a filename/location in Android's Files picker, and finish saving. The edited copy is also imported and opened in the app. Cancel keeps the unsaved edits available.
6. Tap **Share PDF**, the up-arrow-from-box icon beside View options, to choose an Android email or sharing app. It shares the open PDF, including current signatures, annotations and form edits. An unedited PDF is shared byte-for-byte. Sharing does not save an edited copy in this reader or clear the unsaved-edits warning; use **Save copy** to keep edits. Finish sending in the chosen app. Opening the chooser is not confirmation of delivery.
7. Tap **Print PDF**, the printer icon after Save copy, to open Android's print screen. Choose a printer or **Save as PDF**, then paper size, copies or pages. It prints the open PDF including current signatures, annotations and form edits, at full printer resolution. Printing does not save an edited copy or clear the unsaved-edits warning. Password-protected PDFs cannot be printed this way.

Install this APK over the previous version; **do not uninstall** if you want to keep your library and notes. The same signing key and application ID allow an in-place update. Unsaved editing sessions are not drafts: save before closing the app or leaving the PDF. Ordinary document switches ask before discarding edits; forced process termination can still lose an unsaved session.

Requires **Android 10 or newer** and a current Android System WebView/Chrome (the bundled modern PDF.js needs typed-array APIs introduced in Chromium 140). An old WebView receives an update notice. No Python, PC, server, internet connection or Ollama is required.

The app supports continuous/single/spread reading, fit-width/fit-page, page navigation, touch zoom, selectable/copyable text, highlighted native search, lazy thumbnails, embedded outline, recent PDFs, friendly titles/tags/collections, library passage search and source-linked notes. Reading position and zoom persist on this phone.

This version has **no AI answers, briefings, translation, generated quizzes, comparisons, table extraction or OCR**. Scanned PDFs can be viewed; image-only text is not searchable. Arabic/English rendering, native text search and notes are supported where the PDF font mapping is usable. Broken mappings remain unchanged and carry an extraction warning.

PDF copies, text indexes, notes, page bookmarks, pen/screen preferences and positions are stored in this app's private WebView storage. Imported originals stay unchanged. Each edited PDF receives an identity from its actual saved bytes; original note/source links continue opening the original document/page. Passwords are kept only in memory; reopening a protected PDF asks again. Uninstalling/clearing app data removes its library and notes. Automatic backup/cloud transfer is disabled. Export uses only the location you choose in Files, without broad storage permission. A cloud-backed Files provider may upload a copy you explicitly save there. Printing creates a separate private temporary copy that only Android's print service reads; it is deleted when the print job finishes or is cancelled. Sharing creates a separate private temporary copy and grants the app you choose read access to that PDF only. No network permission is added to LocalPDF; the chosen email/sharing app controls its own sending or upload. Recent temporary copies survive Activity recreation for delayed attachment reads; copies older than 24 hours are cleaned at the next controller launch. Android may evict cache sooner, so do not rely on an old email draft retaining its attachment: share again if needed.

Signing is a handwritten PDF annotation, **not a certificate-based digital signature**. This is annotation and form editing, not replacement of existing page text/layout. Added text uses a high-resolution image annotation to preserve Arabic shaping across readers; it is not searchable/selectable native PDF text. Text annotations are limited to 500 characters/20 lines. PDF permissions are respected; advanced XFA forms are unavailable. Saved annotations remain annotations rather than permanently flattened page pixels. No AI, server or new external JavaScript package is used for editing.

## Build from source

Install JDK 17, Android SDK platform 35 and build-tools 35.0.0. Gradle 8.9 is pinned with its checksum; the wrapper downloads it on first use. Set `ANDROID_HOME`/`JAVA_HOME` or use Android Studio.

Debug build:

```sh
cd android
./gradlew assembleDebug lintDebug
```

For the personal signed release, supply the private keystore **outside Git** (never publish it) using `LOCALPDF_ANDROID_KEYSTORE`. Optional environment variables: `LOCALPDF_ANDROID_STORE_PASSWORD`, `LOCALPDF_ANDROID_KEY_ALIAS`, `LOCALPDF_ANDROID_KEY_PASSWORD`. Keep the same key and increase `versionCode` for updates that retain the installed data. The distributed personal APK uses a development certificate; it is not a Play Store release.

```sh
cd android
./gradlew assembleRelease lintRelease
```

Output: `app/build/outputs/apk/release/app-release.apk`. The build synchronizes the one authoritative `src/localpdf_insight/static` directory into assets; no duplicate reader copy is maintained.

Android uses a small device-storage adapter around the existing PDF.js reader. The Python/SQLite/Ollama/evidence systems remain the desktop/web implementation. AI endpoints are explicitly unavailable on Android.

## Verify on a physical phone

Build/signing and offline mobile-browser tests are recorded in the validation reports. A physical Android device was not available. Before relying on signing, verify: update the installed APK without uninstalling; confirm old library/notes; sign page 2 using a finger/stylus; move/resize/undo/redo; fill a form; add Arabic/English text; highlight; tap Save copy and test Files success/cancel; reopen the external PDF in another viewer and check page/appearance/form values; follow an original note and check it still opens the original PDF; rotate while editing; try Back with unsaved edits; repeat in airplane mode. Also test your usual local/cloud document provider and a protected PDF. Process death while the Files picker is open requires retrying; no successful save is claimed before the write finishes.

See `../docs/android-editing-validation/README.md` for this update and `../docs/android-validation/README.md` for the historical reader-only baseline.

## Release preflight

See `../docs/ANDROID_RELEASE_PREFLIGHT.md` for current SDK/API, AAB/signing, privacy, accessibility and device/Play gaps. This personal APK is not a Play Store approval.

# Android release-readiness preflight

Checked 17 October 2026. Scope: personal LocalPDF Android reader, with the 0.2.5 reading conveniences. This is a technical checklist, not Google Play approval. Final build/test evidence is in `android-reading-tools-validation/2026-10-17/README.md`.

## Decision

Continue distributing an update-compatible personal sideload APK. Google Play preparation is separate work. It is not established ready for the store.

## Source and privacy checks

- Application ID remains `app.localpdf.insight`; minimum API 29 / Android 10, target/compile API 35, AGP 8.7.3, Gradle 8.9, build-tools 35.0.0, Java 17.
- AndroidX WebKit 1.12.1 and bundled PDF.js 5.6.205 are unchanged. No new external package.
- Manifest requests no permissions, including no Internet, broad storage or wake-lock permission. Backups/cloud transfer and cleartext traffic are disabled.
- Reading stays in local WebView storage. No new upload, analytics or AI. Browser network loads and nonlocal navigation are blocked.
- Keep-screen-on uses a narrow origin/main-frame-checked message channel and an Activity window flag. It defaults off; pause, focus loss, navigation/error and destruction clear the flag. It is not a background wake lock.
- Bookmarks use document-byte-derived identity and page numbers in local storage. They are not embedded in exported PDFs and do not change originals, annotations or source-linked notes.
- Release WebView debugging is disabled. Console messages do not log document content. Export uses the selected Files destination; a cloud-backed document provider can upload a copy the user explicitly exports there.
- App-private storage is not proof of application-level encryption. Clearing app data/uninstalling loses library, notes, bookmarks and preferences. Unsaved edits are not crash-recoverable drafts.

These controls are source/binary checks, not penetration-test certification.

## Open Play gates

1. **Target API/toolchain.** Current target 35 is below the API 36 requirement for new phone apps and updates from 31 August 2026. Account-specific extensions must not be assumed. AGP 8.7 supports at most API 35, so migrate the toolchain and test Android 16 behavior rather than changing only a version number. Sources: [Play target API](https://support.google.com/googleplay/android-developer/answer/11926878), [AGP 8.7 compatibility](https://developer.android.com/build/releases/agp-8-7-0-release-notes), [Android 16 changes](https://developer.android.com/about/versions/16/behavior-changes-16).
2. **AAB/signing.** No validated production AAB/Play-generated install path is supplied. New Play apps require App Bundles and Play App Signing. The existing personal update certificate is a development certificate; preserve it for installed sideload updates. A different signing certificate cannot simply replace the same installed application ID. Production signing and migration need a deliberate decision. No credentials or Play uploads were created in this task. Sources: [App Bundles](https://developer.android.com/guide/app-bundle), [App signing](https://developer.android.com/studio/publish/app-signing).
3. **Privacy/publication materials.** The app has short English/Arabic local-data notices but lacks a complete public privacy-policy URL/developer contact policy. Complete policy, retention/deletion explanation, Data Safety, ads declaration, audience/content rating, app-access notes, support details and accurate listing images. No account creation was found. Sources: [User Data policy](https://support.google.com/googleplay/android-developer/answer/10144311), [Prepare review](https://support.google.com/googleplay/android-developer/answer/9859455).
4. **Account eligibility.** Developer verification/production access is unknown. Personal accounts created after 13 November 2023 have a conditional 12-testers/14-days closed-test gate. Source: [Testing requirements](https://support.google.com/googleplay/android-developer/answer/14151465).
5. **Regional sideload distribution.** Android verification protections started in Brazil, Indonesia, Singapore and Thailand on 30 September 2026. Check the appropriate personal/limited distribution path before promising unrestricted installs. Sources: [Developer verification](https://developer.android.com/developer-verification/guides), [Limited distribution](https://developer.android.com/developer-verification/guides/limited-distribution).

## Maintenance, accessibility and device gaps

- AndroidX WebKit 1.12.1 is behind stable 1.17.1. This is maintenance debt, not proof of a security flaw. Review upgrades and renderer-loss recovery; `MainActivity` currently has no `onRenderProcessGone` recovery handler. [WebKit releases](https://developer.android.com/jetpack/androidx/releases/webkit).
- Modern PDF.js needs WebView/Chromium 140+ APIs. Android 10 alone does not establish compatibility. Test both supported WebView and the outdated-WebView notice.
- Baseline compact toolbar targets are usually 40 CSS pixels, some 36 wide on narrow screens. Preserve the requested compact design here, but measure/enlarge hit areas for accessibility before broader release. Android recommends 48 dp. New labels alone are not TalkBack certification. [Accessibility guidance](https://developer.android.com/guide/topics/ui/accessibility/apps).
- Verify TalkBack focus order/announcements, large system fonts/display scaling, contrast, Arabic/RTL, keyboard/native menus, predictive Back, rotation/foldables and landscape.
- Verify actual update installation with existing PDFs/notes/positions; SAF import/export success, cancellation, provider failures and process death; low memory/renderer loss; protected/malformed/large/scanned PDFs; exported appearance in an independent viewer; airplane mode; real screen timeout/background/lock/Files picker behavior.
- No Android ELF shared libraries were found in source; verify the final package, then exercise 16 KB devices. Java-only builds generally already support 16 KB pages. PDF.js WASM is not an Android ELF library. [16 KB guidance](https://developer.android.com/guide/practices/page-sizes).

Browser tests exercise actual PDF.js and actual exported bytes, but mock native transport. The native screen policy test compiles the production controller against API test doubles. Neither replaces physical-device tests, which remain unverified.

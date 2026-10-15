# LocalPDF Insight Android — cumulative updates

## 2026-10-15 — 0.2.1-page-jump (version code 3)

- Improvement: the page-number field advertises Go on supporting keyboards. Enter/Go commits the page jump using existing bounds handling and releases input focus. IME composition is left alone. The change is Android-only.
- Implementation commit: `a124ce7e2106a4ae1c6a6030c0e79e10d03d13be`, continuing from `4320b11c01fbb50b5f883c37a5314f6bf76486f2`.
- Reproduction: the new regression failed against the previous app because the page-number field retained focus after Enter. It passed with the fix, including lower/upper bounds, Arabic mode and composition handling.
- Validation: 19 offline Android reader workflows and 17 signing/export workflows passed in Playwright 1.62.1 / Chromium 155.0.8059.79 mobile emulation. Zero browser errors or external network/API attempts. Existing exported PDFs were independently inspected/rendered with PyMuPDF; signature page 2 and English/Arabic text renders were visually checked.
- Build: signed `assembleRelease` and `lintRelease` passed; zero lint errors and five unchanged baseline warnings. APK signature verified, certificate and application ID match the previous APK, version code is 3, all 296 reader assets match source. No permissions; backup, cleartext and debugging remain disabled.
- Limits: physical Android/WebView, actual keyboard dismissal/Go presentation, native Files picker and installed upgrade/data retention were not tested. Browser checks prove page navigation and DOM focus release; keyboard behavior requires a phone. Desktop suites were not rerun because the new handler is inside the Android-only initialization. Previous editor limitations remain.
- Evidence: `docs/android-daily-validation/2026-10-15/` contains the executed reader/editor results and release checks. The source package includes complete updated Git history in its bundle. No signing key is included.

## 2026-10-14 — 0.2.0-editor (version code 2)

- Signing/editing baseline: ink signatures, highlighting, Arabic/English text stamps, supported forms and separate-copy export; originals and source-linked notes preserved.
- Commit: `4320b11c01fbb50b5f883c37a5314f6bf76486f2`.
- Historical validation: 56 browser workflows and signed build/lint passed; physical Android unverified. See `docs/android-editing-validation/README.md`.

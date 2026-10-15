# Android reader validation

The new Android reader extends checkpoint `5cdc2c6f0eee5a2a274450b4ede7e9ca0799ea58` without replacing the desktop/web reader, SQLite evidence system or Ollama verifier. Android has no model/server dependency and intentionally exposes reading, native-text search and source-linked notes only.

Executed:

| Check | Result |
|---|---|
| Signed APK: `assembleRelease` | PASS |
| Android `lintRelease` | 0 errors; 5 warnings |
| APK signature | Valid v2 signature, RSA 2048 |
| Binary manifest | minSdk 29; targetSdk 35; zero permissions; not debuggable; RTL enabled |
| Privacy controls | No Internet permission; network loads blocked; external links blocked; no JS native bridge; automatic backup/device transfer disabled |
| Bundled reader assets | All 295 assets equal the final source byte-for-byte |
| Standalone Android browser workflows | 18 passed, 0 failed; offline local asset routing; no Python/Ollama server |
| Existing browser reader regressions | 13 passed |
| Existing Studio browser regressions | 8 passed |
| JS syntax and whitespace check | PASS |
| Physical Android / native WebView execution | Not run; no attached device/emulator |

The 18 Android workflows exercise offline launch, 150 pages, navigation/outline/highlighted search, thumbnails/layout/pinch, persisted PDF copies/position/stable IDs, duplicates and friendly titles, notes and cross-document source navigation after rename/reload, scope isolation, native Arabic/English search and RTL notes, malformed-font warnings, image-only pages, passwords, rotated/unusual page sizes, Back handling, storage failure, and absence of network/API/model calls.

Measured on a synthetic host fixture, **not a phone**: first page readable in 0.250 seconds; 150 native pages indexed in 1.767 seconds. These numbers do not establish physical-device performance or native picker/WebView behavior.

Material defects found and fixed: per-item spacing broke Arabic whole-word search; passage rectangles incorrectly used PDF descent instead of the text-layer ascent; duplicate import ignored friendly title; valid provider PDFs without a filename extension were rejected; storage initialization could fail silently. Tests cover these behaviors. Unknown/broken font mappings are not repaired by inventing text.

Remaining limits: modern WebView needed; physical picker/long-press/pinch/lifecycle behavior unverified; no OCR/AI/table extraction/comparison; no cross-device sync/export; app removal clears saved data. Historical AI release blockers are unchanged and irrelevant to claims of model reliability for this reader-only APK—no AI quality claim is made.

APK SHA-256: `cffe39a71ed48bd58a9acd8693eab3795e74d5ca86e25e9b8f219e2c6a387647`.

Run the standalone workflow checks with `npm ci`, `npx playwright install chromium`, and `npm run test:android`. `CHROMIUM_EXECUTABLE`, `LOCALPDF_TEST_PYTHON` and `LOCALPDF_TEST_ARTIFACTS` may select local tooling/results. Browser screenshots are internal test diagnostics, not release deliverables.

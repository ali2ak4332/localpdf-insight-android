# Android source build verification

Validated 2026-10-17T10:47:10.148068+00:00.

## Result

The standard Gradle/Android Gradle Plugin build completed successfully from the final source, including the late outline/bookmark tab-switching race fix. No manual APK reconstruction or dependency reuse from an older APK was needed.

- Tasks: `:app:assembleRelease :app:lintRelease`
- Native Java compilation: passed with JDK 17.
- Android Lint: 0 errors, 5 warnings.
- Every one of 298 packaged reader assets matches the authoritative source byte-for-byte; no missing, stale, or extra reader assets.
- DEX includes `MainActivity`, `PdfExportController`, `ReadingScreenController`, AndroidX WebKit, and the AndroidX component factory.
- All transitive Java/Android dependencies resolved and packaged by AGP; inventory in `android-sdk-dependencies.txt`.
- `zipalign -c -v 4`: passed.
- Final merged manifest has no requested permissions.
- Package: `app.localpdf.insight`, version 7 / `0.2.5-reading-tools`, minimum Android API 29, target/compile API 35.

## APK

`android/app/build/outputs/apk/release/app-release-unsigned.apk`

Size: 6,416,260 bytes.

SHA-256: `ba6d9b74a224b52c307ea224e973c92564839c5e532b7b76c0e77b352d2a82e3`

This output is intentionally unsigned. A signature check correctly rejects it before signing. Signing with the existing private key is a separate step owned by the parent task; this build neither accessed nor created signing credentials.

## Tools and reproduction

- Gradle 8.9, archive SHA-256 `d725d707bfabd4dfdc958c624003b3c80accc03f7037b5122c4b1d0ef15cecab`.
- Temurin JDK 17.0.20.1+1, archive SHA-256 `3808d1d15e3ec6bd5b84057fb5d84c33d8a1536a258146bcea2e603fc726e08e`.
- Android SDK Platform 35 revision 2 and Build Tools 35.0.0.
- Android Gradle Plugin 8.7.3; AndroidX WebKit 1.12.1 and complete resolved transitives.

From the repository root, using a non-login shell in this workspace:

```sh
source /workspace/scratch/19cb5c838a1d/adaptive-work/tools/env.sh
bash scripts/android/setup_build_tools.sh
bash scripts/android/build_unsigned.sh
```

The scripts and `scripts/android/README.md` document isolated build homes, proxy handling, pinned verified downloads, and the build-only `finalizeDsl` override that clears release signing. No application implementation or normal release configuration was edited by the build worker.

## Warnings and limits

- `UnusedAttribute`: predictive-back manifest attribute is only used on API 33+.
- `GradleDependency`: WebKit 1.12.1 is pinned; Lint reports a newer 1.17.1 is available. Upgrading a dependency was outside this build task.
- `SetJavaScriptEnabled`: JavaScript is intentionally needed by the local PDF reader.
- `ObsoleteSdkInt`: an existing values-v27 resource directory is redundant for minSdk 29.
- `MonochromeLauncherIcon`: existing base launcher icon has no monochrome tag.

The newly added controller's `RequiresFeature` warning was resolved by the application's owner and the final build reran afterward. Lint passes with the remaining warnings; this is not a zero-warning claim.

The installed SDK prints a Platform-Tools license/install warning. Compile, packaging, and Lint still complete successfully. No SDK license was accepted by this build task, and no emulator or physical-device test was performed here.

## Evidence

- `android-gradle-build.log`
- `android-lint-release.txt`
- `android-source-build.json`
- `android-sdk-dependencies.txt`
- Full Lint HTML: `android/app/build/reports/lint-results-release.html`

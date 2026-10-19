# Reproduce the Android source build

These scripts compile the complete application and its Maven dependencies with
Gradle 8.9, Android Gradle Plugin 8.7.3, and Temurin JDK 17.0.20.1+1. They do not
read signing credentials and always remove the application's signing variables.

## Prerequisites

- Linux x86_64, Bash, curl, unzip, tar, Python 3, and sha256sum.
- Android SDK Platform 35 revision 2 and Build Tools 35.0.0 installed in a writable
  SDK directory, with `ANDROID_HOME` pointing to it.
- Network access to the public Gradle, Eclipse Adoptium, Google Maven, Maven
  Central, and Gradle Plugin Portal repositories on the first build.

The setup script downloads its two pinned tool archives from the official vendor
distributions and verifies their SHA-256 checksums before extraction. The Gradle
checksum also matches `android/gradle/wrapper/gradle-wrapper.properties`.

## Commands

From the repository root:

```sh
export ANDROID_HOME=/absolute/path/to/android-sdk
bash scripts/android/setup_build_tools.sh
bash scripts/android/build_unsigned.sh
```

Set `LOCALPDF_BUILD_TOOLS_ROOT` consistently for both scripts to change the
default isolated directory, `/tmp/localpdf-build-tools`.

In the prepared workspace, the existing SDK can be selected with:

```sh
source /workspace/scratch/19cb5c838a1d/adaptive-work/tools/env.sh
bash scripts/android/setup_build_tools.sh
bash scripts/android/build_unsigned.sh
```

For shell execution tools, use `login: false` where a login profile replaces the
active managed HTTP proxy with stale connection settings. The build script
derives Java proxy settings from the current `HTTPS_PROXY`, and isolates Gradle,
Android preferences, and the home directory under its writable tools directory.
It uses the existing system Java truststore if available; it does not modify
certificates, firewall rules, credentials, or security settings.

The invoked Gradle tasks are:

```sh
gradle --no-daemon --no-watch-fs --max-workers=2 \
  --init-script ../scripts/android/unsigned.init.gradle \
  :app:assembleRelease :app:lintRelease
```

Gradle may start a single-use worker JVM even with `--no-daemon`; it shuts down
at the end of the invocation. This works in the normal workspace sandbox.
The prepared SDK lacks Platform-Tools and prints a license/install warning.
The compile, packaging, and Lint tasks still succeed; no SDK license was
accepted by these scripts. Platform-Tools are needed separately for `adb` and
device testing, which this build does not claim to perform.

## Outputs and checks

- Unsigned APK: `android/app/build/outputs/apk/release/app-release-unsigned.apk`
- Lint HTML: `android/app/build/reports/lint-results-release.html`
- Lint text: `android/app/build/reports/lint-results-release.txt`
- Asset and class verification: `validation-artifacts/android-source-build.json`

`verify_unsigned_apk.py` compares every packaged reader asset byte-for-byte with
the authoritative `src/localpdf_insight/static` directory, rejects extra or
missing reader assets, and checks that DEX contains the three application
controllers and AndroidX WebKit. It also records the APK SHA-256. The complete
Java dependency graph is packaged by the standard Android Gradle Plugin; no
classes or resources are copied from a previous APK.

The build-only init script uses AGP's `finalizeDsl` hook to clear the release
signing configuration before variants are created. This is necessary because the
normal app build deliberately requires its externally supplied personal key.
The application build files themselves are not changed for this override.

The unsigned APK must be signed separately with the existing private key before
installation as an update. These scripts neither sign nor create a key.

## Official references

- [Gradle 8.9 release](https://docs.gradle.org/8.9/release-notes.html)
- [Gradle daemon behavior](https://docs.gradle.org/current/userguide/gradle_daemon.html)
- [Temurin JDK 17 release](https://github.com/adoptium/temurin17-binaries/releases/tag/jdk-17.0.20.1%2B1)
- [Android command-line build](https://developer.android.com/build/building-cmdline)
- [Android Lint](https://developer.android.com/studio/write/lint)

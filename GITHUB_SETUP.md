# LocalPDF Insight Android source setup

This is a sanitized source export of `0.2.1-page-jump` (version code 3).
It includes the Android Gradle app, the shared PDF.js reader/editor assets,
the Python desktop/web source and tests, and applicable third-party licenses.

Excluded deliberately: Android signing secrets, local credentials, APK build
outputs, historical Git history bundle, and large B1 validation evidence.
Those archives remain in the original uploaded ZIP and are not required to
build the Android app.

To build: `cd android && ./gradlew assembleDebug`. The Android SDK and JDK 17
are required. Release signing requires keys supplied privately via environment.

The GitHub Actions debug build creates a non-production, debug-signed APK only.
It does not produce a release signed with the user's existing private key.

The Android reader currently does NOT include the Python/Ollama desktop AI backend.
See ANDROID_CHANGELOG.md and android/README.md for known limitations.

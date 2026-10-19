#!/usr/bin/env bash
# Install pinned public Linux x86_64 build tools into an isolated directory.
# No credentials are read, generated, or saved by this script.
set -euo pipefail
ROOT="${LOCALPDF_BUILD_TOOLS_ROOT:-/tmp/localpdf-build-tools}"
mkdir -p "$ROOT"
fetch() {
  local url="$1" file="$2" sha="$3"
  if ! test -f "$file" || ! printf '%s  %s\n' "$sha" "$file" | sha256sum -c - >/dev/null 2>&1; then
    curl --fail --location --retry 3 "$url" -o "$file"
  fi
  printf '%s  %s\n' "$sha" "$file" | sha256sum -c -
}
fetch 'https://services.gradle.org/distributions/gradle-8.9-bin.zip' \
  "$ROOT/gradle-8.9-bin.zip" \
  d725d707bfabd4dfdc958c624003b3c80accc03f7037b5122c4b1d0ef15cecab
if ! test -x "$ROOT/gradle-8.9/bin/gradle"; then
  unzip -q "$ROOT/gradle-8.9-bin.zip" -d "$ROOT"
fi
fetch 'https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.20.1%2B1/OpenJDK17U-jdk_x64_linux_hotspot_17.0.20.1_1.tar.gz' \
  "$ROOT/jdk17.tar.gz" \
  3808d1d15e3ec6bd5b84057fb5d84c33d8a1536a258146bcea2e603fc726e08e
if ! test -x "$ROOT/jdk17/bin/javac"; then
  mkdir -p "$ROOT/jdk17"
  tar -xzf "$ROOT/jdk17.tar.gz" --strip-components=1 -C "$ROOT/jdk17"
fi
"$ROOT/jdk17/bin/javac" -version
printf 'Build tools ready in %s\n' "$ROOT"
printf 'Also required: Android SDK Platform 35 revision 2 and Build Tools 35.0.0. Set ANDROID_HOME to that SDK.\n'

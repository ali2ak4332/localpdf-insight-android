#!/usr/bin/env bash
# Compile the complete release from source and run Android Lint without signing.
# Use a non-login shell if its profile overwrites the managed HTTP proxy.
set -euo pipefail
PROJECT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ROOT="${LOCALPDF_BUILD_TOOLS_ROOT:-/tmp/localpdf-build-tools}"
: "${ANDROID_HOME:=${ANDROID_SDK_ROOT:-}}"
: "${ANDROID_HOME:?Set ANDROID_HOME to an SDK containing Platform 35 and Build Tools 35.0.0}"
test -f "$ANDROID_HOME/platforms/android-35/android.jar"
test -x "$ANDROID_HOME/build-tools/35.0.0/aapt2"
test -x "$ROOT/jdk17/bin/javac"
test -x "$ROOT/gradle-8.9/bin/gradle"
export JAVA_HOME="$ROOT/jdk17" ANDROID_HOME ANDROID_SDK_ROOT="$ANDROID_HOME"
export PATH="$JAVA_HOME/bin:$PATH"
LOCALPDF_BUILD_USER_HOME="$ROOT/home"
export GRADLE_USER_HOME="$ROOT/gradle-home"
export ANDROID_USER_HOME="$LOCALPDF_BUILD_USER_HOME/.android" ANDROID_PREFS_ROOT="$LOCALPDF_BUILD_USER_HOME"
export XDG_CONFIG_HOME="$LOCALPDF_BUILD_USER_HOME/.config"
mkdir -p "$ANDROID_USER_HOME" "$XDG_CONFIG_HOME" "$GRADLE_USER_HOME"
# Start from a clean option set: inherited GRADLE_OPTS may name a stale proxy.
export GRADLE_OPTS="-Duser.home=$LOCALPDF_BUILD_USER_HOME -Dorg.gradle.vfs.watch=false -Dorg.gradle.internal.instrumentation.agent=false"
if test -f /etc/ssl/certs/java/cacerts; then
  GRADLE_OPTS+=" -Djavax.net.ssl.trustStore=/etc/ssl/certs/java/cacerts"
fi
if test -n "${HTTPS_PROXY:-}"; then
  proxy="${HTTPS_PROXY#http://}"
  proxy="${proxy#https://}"
  proxy="${proxy%/}"
  if [[ "$proxy" == *@* ]]; then
    printf 'Authenticated proxies need an externally configured Java proxy; refusing to copy credentials.\n' >&2
    exit 2
  fi
  host="${proxy%:*}"; port="${proxy##*:}"
  GRADLE_OPTS+=" -Dhttp.proxyHost=$host -Dhttp.proxyPort=$port -Dhttps.proxyHost=$host -Dhttps.proxyPort=$port"
fi
unset LOCALPDF_ANDROID_KEYSTORE LOCALPDF_ANDROID_STORE_PASSWORD
unset LOCALPDF_ANDROID_KEY_ALIAS LOCALPDF_ANDROID_KEY_PASSWORD
cd "$PROJECT/android"
"$ROOT/gradle-8.9/bin/gradle" --no-daemon --no-watch-fs --max-workers=2 \
  --init-script "$PROJECT/scripts/android/unsigned.init.gradle" \
  :app:assembleRelease :app:lintRelease "$@"
python3 "$PROJECT/scripts/android/verify_unsigned_apk.py"

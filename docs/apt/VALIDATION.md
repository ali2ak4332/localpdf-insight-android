# Apt Reader validation — 24 October 2026

**Follow-up:** use [the Hugging Face candidate report](hf-candidates/REPORT.md)
for the latest model research, native-template diagnostics and the frozen
20-case Qwen3.5 0.8B/2B holdout. Both Qwen variants scored 16/20 there; unsupported
evidence remains a blocker. The earlier [Liquid comparison](liquid-comparison/REPORT.md)
contains the corrected host-test transport and fresh Gemma baseline. Historical
Gemma files below may be affected by newline framing. No Qwen model has been
integrated into the app. App runtime and signing checks below are unchanged.

**Release decision: BLOCKED. The current model fails task-relevance diagnostics.**
No APK or source release package is approved for delivery. A signed internal
candidate exists for development checks only. `main` remains unchanged.

## What is implemented

- Gemma 3 270M instruction-tuned QAT Q4_0 on a pinned native CPU llama.cpp engine.
- Five-function dialog, existing PDF.js/IndexedDB extraction, bounded sections,
  cancellation, per-document state and explicit coverage/omission reporting.
- Independent exact-source verification, unsupported-selection rejection,
  physical-page citations, and separately cited nearby context. Interpretations,
  document completeness and real-world truth are explicitly unverified.
- Digest/size-checked SAF model import, atomic replacement, crash-file cleanup
  on startup, and no Android INTERNET permission or cloud fallback.
- Same package, WebView origin, database and preference identities. No new
  signing key or database migration was introduced.

## Build, integrity and regression checks

| Check | Actual result |
| --- | --- |
| Signed `assembleRelease lintRelease` | Passed, JDK17 / Gradle8.9 / AGP8.7.3 / SDK35 / NDK28.2.13676358 |
| Lint | 0 errors, 6 warnings: two RequiresFeature, UnusedAttribute, SetJavaScriptEnabled, ObsoleteSdkInt, MonochromeLauncherIcon |
| Package/version/name | `app.localpdf.insight`, code 10, `0.3.0-apt-dev`, Apt Reader |
| Signature | Verified using the recovered original LocalPDF key; SHA-256 `f0c38147d5bfe371d7144578b4e952fabad9dd2fe98137ea4be630bb6537a153`, matching the recorded LocalPDF release certificate |
| Packaged reader integrity | All 300 static assets match current source byte-for-byte |
| Independent analysis/transport tests | 19 passed, including malformed/forged selections, altered numbers/periods, stale revisions, cancellation, coverage and wrapped-exception context |
| New offline dialog workflows | 7 passed in Chromium151 mobile emulation; native transport mocked, including clickable pages and stale Verify Findings rejection |
| Existing Android reader browser suite | 21 passed after updating its old no-AI privacy assertion for the new optional on-device feature |
| Existing editor/export/share/print browser suite | 26 passed; native transport mocked |
| Existing reading tools browser suite | 12 passed |
| Existing Java native-policy tests | 33 print + 26 share + 18 screen checks passed using API doubles; not Android framework/device tests |
| Model file tests | Corrupt/cancelled import, old-model retention, pending cleanup, real-model digest and atomic installation passed in host Java |
| Native engine tests | Actual-model inference and missing-file handling passed; pre-start/in-flight cancellation passed |

The browser workflows use actual bundled PDF.js and local IndexedDB without API
servers or external requests. They do not establish Android SAF, WebView/native
integration, printing, upgrade retention or phone behavior. Native smoke tests
establish execution, not correct task answers.

## Measured size and performance

| Measurement | Result and scope |
| --- | --- |
| Model file | 241,410,624 bytes; SHA-256 `3626e245220ca4a1c5911eb4010b3ecb7bdbf5bc53c79403c21355354d1e2dc6` |
| Signed internal universal APK | 19,443,398 bytes; SHA-256 `8782941f7cfc2aecee545213d3096d18c2b51c08ce18f98766f58a64d2bbb0df` |
| APK plus model bytes | 260,854,022 bytes (~260.9 MB decimal). **Not an installed-footprint measurement.** |
| Native library sizes | arm64 6,248,072 bytes; x86_64 6,723,000 bytes, both included in the universal APK |
| Host peak process RAM | 505,860,096 bytes from Linux `getrusage` for a cold engine load and one diagnostic; that request ended with an incomplete-selection error. This is not Android RAM or successful-document analysis RAM. |
| Revised-prompt diagnostic latency | Median 3,998 ms, p95 4,639 ms per short synthetic selection request on x86_64 host; includes failures, not document-level latency |
| Phone installed footprint, peak RAM, cold load, throughput, battery | **Not measured** |

Storage below 400 MB remains unverified. Android code/optimization/runtime caches,
model-import temporary files and user PDF/index growth are not included in the
APK-plus-model sum. Updating a model temporarily needs both old and pending copies.

## Actual model-quality failure

The production engine/model was run on **32 synthetic source-selection diagnostic
cases** covering the four model-driven tasks, with target-position permutations
and obvious irrelevant distractors. These are not 32 representative PDFs and are
not a human-reviewed held-out benchmark.

- Initial prompt: **0/32 exact selections**, relevant-passage recall **50%**.
  The model repeatedly copied the illustrative indices from the prompt.
- Removing that illustration and rerunning: **0/32 exact selections**, relevant
  passage recall **12.5%**. The verifier rejected **28 unsupported selections**
  and released **16 exact extracts** across the cases. Released extracts matched
  their source text/page; this says nothing about task relevance or completeness.
- **No 95% numerical-accuracy claim is justified.** Exact copying cannot substitute
  for identifying the correct entity, metric, unit, period, context and relevant
  numerical findings. Empty output and abstention cannot count as success.
- No fabricated citation was released in these diagnostic cases, but the required
  representative-PDF citation/evidence benchmark has not been completed.

Raw per-case results are in [results/model-baseline-initial.json](results/model-baseline-initial.json)
and [results/model-baseline.json](results/model-baseline.json). Host RAM measurement
is in [results/host-memory.json](results/host-memory.json). A zero/unavailable
`/proc` measurement was corrected to null; no zero-RAM claim is made.

## Remaining release gates

1. **Model/task quality:** investigate and improve the task-specific model. No
   fine-tuning has been performed and no trained checkpoint or verified training
   corpus was produced. Prompt changes are not fine-tuning. This failure does
   not prove that a properly fine-tuned 270M model cannot work.
2. **Representative corpus:** assemble 30–50 financial, technical and contractual
   English PDFs with independently reviewed numerical/semantic gold data,
   document-disjoint training/test splits, usefulness/recall/abstention measures
   and completeness/exception checks. The required benchmark was not run; the
   failing basic diagnostic is not being presented as its replacement.
3. **Android validation:** test the actual signed build/model offline after cold
   starts and over a populated LocalPDF installation; verify data retention,
   cancellation, process death, source navigation and existing reader features.
   No physical device/emulator validation is claimed.
4. **Measurements:** obtain actual installed storage, phone RAM and end-to-end
   document latency. Recheck the exact final quantized model and signed artifact
   after any training or changes.

The original signing backup has been recovered privately and the certificate
matches. Signing/toolchain availability is **no longer a blocker**. No key,
password, model weights, APK or toolchain is committed to this branch.

## Review

A separate reviewer identified three Important bugs: stale verification results,
wrapped-clause context loss, and persistent crash-import files. They were fixed
with regression checks for stale verification/context and host model cleanup.
Context remains bounded and explicitly not exhaustive. Source-level highlighting
is retained as a documented precision limit. No merge or release was performed.

Technical sources: [Google Gemma 3 270M](https://developers.googleblog.com/introducing-gemma-3-270m/),
[runtime/model publisher](https://huggingface.co/ggml-org/gemma-3-270m-it-qat-GGUF),
[llama.cpp Android guidance](https://github.com/ggml-org/llama.cpp/blob/df9beac7153166550571c70cc667f270b745da49/docs/android.md),
[Android signing](https://developer.android.com/studio/publish/app-signing).
These sources establish platform capabilities; the measured results above come
from this session and do not inherit model marketing benchmarks.

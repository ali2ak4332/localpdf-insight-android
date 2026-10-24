# Apt Reader — development preflight

**Historical initial preflight.** Development continued after this checkpoint.
The signing backup has now been recovered and matched to the existing certificate;
the toolchain has been installed and a signed internal build/lint passes.
The current blocker is model quality plus uncompleted representative-PDF/device
validation. See [`apt/VALIDATION.md`](apt/VALIDATION.md) for authoritative current
results. The original preflight below is retained as history, not current status.

Date: 24 October 2026 (Asia/Dubai). **BLOCKED: no Apt Reader release candidate.**

## Branch and compatibility

`apt-reader` was created from `main` at
`301e078eed6d863ca8c082a5dc0462978e375972` (reconciled Android
`0.2.7-print-pdf`, version code 9). This checkpoint adds documentation only:
no reader, manifest, build configuration, database, branding or signing changes.
The existing LocalPDF release remains unchanged.

Required compatibility boundaries for implementation:

- Keep application ID `app.localpdf.insight`, WebView origin
  `https://appassets.androidplatform.net`, IndexedDB
  `localpdf-android-reader-v1`, document revision hashes and existing storage keys.
- Use Apt Reader as the development branch/display name; do not introduce a new
  application ID. With the same package, a future signed Apt Reader APK updates
  the existing installation; it is not a second app installed alongside LocalPDF.
- Use the original external signing key and a version code higher than 9.
  Verify the signed APK certificate against the previously recorded SHA-256
  `f0c38147d5bfe371d7144578b4e952fabad9dd2fe98137ea4be630bb6537a153`.
  Independently verify that fingerprint against the installed/released APK before
  delivery. Never generate a replacement key or uninstall to bypass a mismatch.
- Test an upgrade of a populated installation, including library, notes,
  bookmarks, reading position, editing, save, share and print.

## Actual checks and blockers

| Check | Result in this session |
| --- | --- |
| Separate remote branch | Created from the reconciled source commit above |
| Source inspection | Android PDF.js extraction and IndexedDB page/source indexes exist in `src/localpdf_insight/static/mobile_backend.js`; Android AI routes currently reject requests |
| Network policy | Current Android manifest has no INTERNET permission; no runtime changes made |
| Original signing key | `LOCALPDF_ANDROID_KEYSTORE` and associated signing variables absent; no keystore found among tracked source files |
| Android tools | No configured SDK (`ANDROID_HOME`/`ANDROID_SDK_ROOT` absent), `adb`, emulator or `javac` on PATH; Java 17 runtime is present |
| Native regression attempts | `pdf_print_policy.py`, `pdf_share_policy.py`, `reading_screen_policy.py` each stopped with `FileNotFoundError: javac`; zero assertions executed, no test pass claimed |
| Model access probe | One unauthenticated request to `https://huggingface.co/api/models/google/gemma-3-270m-it-qat-q4_0-gguf` returned HTTP 401; this does not establish that other official model artifacts are unavailable |
| Model integration / five functions | Not implemented |
| Fine-tuning | Not performed; no training examples, adapter or trained checkpoint produced |
| 30–50 PDF benchmark | Not performed; no approved corpus or independently reviewed gold answers assembled |
| Android build/lint | Not run; no Apt Reader APK produced |
| Offline operation / upgrade retention | Not tested on Android; no connected-device evidence |
| Model bytes / installed footprint / RAM / latency | Not measured; below 400 MB is a target, not a result |

The original signing key and actual Android upgrade/offline validation are
critical delivery blockers. Missing toolchains are environment setup work, not
evidence that the design is infeasible. Stop before distributing any APK until
every required gate below passes. Historical LocalPDF test results do not count
as validation of new AI features.

## Implementation specification retained for continuation

The user has authorized implementation of the following scope. This is a
proposed technical approach, not completed functionality.

1. **Offline runtime and setup.** Evaluate the official instruction-tuned Gemma
   3 270M INT4/QAT model with an Android CPU runtime before choosing a backend.
   Compare compatible LiteRT and llama.cpp artifacts for actual size, RAM,
   correctness and speed; pin runtime/model revisions and SHA-256. Do not assume
   a particular download format is available or small enough. Prefer a model
   imported through Android's document picker, with one private persisted copy,
   retaining no INTERNET permission. Initial download can be external to the
   app. Validate model provenance, format, digest and license requirements.
   Corrupt/missing models must produce a setup error without cloud fallback.

2. **Reader integration.** Reuse existing per-page text, source IDs, document
   hashes and bounding boxes. Add one compact analysis panel containing
   Summarize, Extract Insights, Extract Key Figures, Identify Risks & Obligations,
   and Verify Findings. Keep analysis cancellable and off the UI thread; cap
   context, output, queues and caches. Native bridge messages must be scoped to
   the existing trusted origin, validate request IDs/lengths, and cancel on
   document changes. Verify Findings invokes an independent deterministic
   evidence check; another model answer is not verification.

3. **Evidence before prose.** Treat PDF text and model output as untrusted input.
   Let the model propose bounded source-span selections and structured findings.
   A separate deterministic verifier resolves only current-revision source IDs,
   checks physical pages and exact character spans, and copies evidence from the
   index. No model-authored quote or page number becomes evidence by itself.
   Reject stale revisions and fabricated/out-of-range spans. Clickable citations
   must open the original PDF and physical page with the quoted span highlighted.

4. **What verification can establish.** Exact textual support is not proof of a
   paraphrase's meaning. Number presence alone does not verify the entity,
   currency, scale, period, metric, negation, conditional language or relationship.
   Use source-copied statements for verified factual output; label interpretations
   separately as unverified and flag unsupported claims. Any derived figure must
   expose cited operands, units, periods, formula and deterministic arithmetic.
   Ambiguous tables or conflicting passages require abstention/page review.
   Risk/obligation labels may be interpretation; verify the quoted clause and
   preserve actors, conditions, exceptions, dates and modality without claiming
   legal completeness or semantic certainty.

5. **Coverage.** Process bounded sections sequentially and preserve a coverage
   ledger across reduction steps. Report total pages, pages with usable text,
   pages/sections analyzed, omitted/failed pages and truncation. Cite original
   spans through every stage rather than citing an intermediate model summary.
   Image-only pages require an explicit unsupported/OCR-needed result. No
   unrequested OCR engine or embedding model is implied. Never describe a
   sampled analysis as exhaustive, particularly for risks and obligations.

6. **Fine-tuning only on evidence.** Establish a base-model baseline first.
   Assemble rights-cleared, independently reviewed examples for all five tasks,
   including abstentions, numerical distractors, prompt injection, conflicting
   periods, exclusions and malformed citations. Split training/development/test
   by document and organization/template to avoid leakage. Train only if a
   measured deficiency justifies it; preserve data provenance, configuration,
   seeds, checkpoint hashes and base-versus-tuned comparisons. Quantize and
   re-evaluate the exact deployed artifact. A prompt or verification rule change
   is not fine-tuning.

7. **Evaluation.** Assemble 40 representative English PDFs (14 financial,
   13 technical, 13 contractual), varied in length/layout and including scans,
   complex tables and long-document traps. Keep held-out benchmark documents
   out of training. Human-reviewed gold data must include source spans, document
   hashes, physical pages, values/units/periods/entities and important clauses.
   Run all five tasks and retain every raw output, rejection and citation.
   Require at least 95% correct released numerical findings, counting wrong
   scale/unit/entity/period as incorrect; disclose counts, per-category results,
   uncertainty and abstention/coverage rates. Also report numerical recall and
   task usefulness against the gold data so empty output cannot pass. Require
   zero fabricated citations, check citation correctness/relevance and all
   clickable destinations, and report risk/obligation omissions separately.
   A finite benchmark result is not a universal guarantee.

8. **Device and release gates.** Restore a full JDK17/Android SDK35/build-tools
   35.0.0 environment; run release build/lint and current reader/browser/native
   regression suites. On a representative physical Android device, install with
   the original key over a populated LocalPDF installation and test all existing
   features plus all five AI functions. After initial model import, cold-start
   and repeat with networking disabled, including cancellation, restart,
   malformed model, incomplete indexing, missing text and document switching.
   Check manifest and runtime network activity. Measure actual signed APK bytes,
   model bytes, installed code/native libraries, model/data copies and generated
   runtime cache separately; report baseline and post-analysis storage, excluding
   user PDFs only with explicit disclosure. Measure peak process RAM, cold model
   load, time to first result and end-to-end latency by document size, including
   device/OS/WebView/thermal state. Under 400,000,000 installed bytes is a goal,
   subject to measured accuracy and usefulness. User documents/index growth is
   separate and cannot have a fixed complete-app ceiling.

## Delivery policy

Deliver a signed update-compatible APK, complete source and concise measured
validation report only after the required checks pass. If a gate fails, report
its evidence and remaining work; do not publish an unverified or differently
signed APK as a substitute. This document is the blocker record, not a completed
implementation, fine-tuning result or validation certificate.

## Evidence and technical sources

- Current source: `android/app/build.gradle`,
  `android/app/src/main/AndroidManifest.xml`,
  `src/localpdf_insight/static/mobile_backend.js`, `android/README.md`.
- Prior reconciliation and recorded certificate (historical evidence):
  [`SOURCE_RECONCILIATION_2026-10-19.md`](SOURCE_RECONCILIATION_2026-10-19.md).
- Google, [Introducing Gemma 3 270M](https://developers.googleblog.com/introducing-gemma-3-270m/),
  14 August 2025: task specialization and INT4/QAT support; no Apt Reader quality
  or installed-size result follows from this announcement.
- Android, [App signing](https://developer.android.com/studio/publish/app-signing):
  signing and update identity requirements.

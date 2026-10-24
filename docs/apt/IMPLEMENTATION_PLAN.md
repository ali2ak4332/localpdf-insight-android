# Apt Reader implementation

Binding scope: user request and `../APT_READER_STATUS.md`. User authorized
continuation without further design questions on 24 October 2026.

1. Build a tested, independent extractive verifier and bounded section planner.
   Model output may select source IDs only; code produces exact evidence spans,
   tracks coverage and rejects invalid selections. Test forged citations, changed
   numbers, wrong revisions, duplicated IDs, partial/cancelled work and scans.
2. Integrate a pinned CPU llama.cpp runtime and the 241,410,624-byte Gemma 3
   270M instruction-tuned QAT Q4_0 artifact. Test host model inference and native
   error paths; import model through SAF with digest verification and atomic
   replacement. Keep Android network permission absent and storage identity fixed.
3. Add the five-task compact panel, linked evidence, coverage, cancellation and
   explicit extractive/interpretation limitations. Run current browser regressions
   and added offline analysis workflows with controlled model responses.
4. Build/lint Android, run host/native regressions, measure actual artifacts and
   run the real model on representative PDFs where available. Keep a separate
   held-out benchmark and human-reviewed gold requirements; no synthetic or
   automatically generated corpus is represented as human-validated evaluation.
5. Independently review the branch, save measured results and all unpassed gates.
   Preserve main. No APK/source release until required quality, original-key
   signing and Android offline/upgrade validation pass.

Interfaces: snapshot = current document + pages + immutable source records;
model = JSON array of local candidate indices; evidence = source-copied text,
document ID/revision, physical page, source ID and span offsets. Native transport
accepts only bounded prompts from the trusted main WebView origin.

Review focus: prompt injection, source-context loss, Unicode/index offsets,
cross-document stale state, native cancellation/lifetime, interrupted model import,
empty-output numerical metrics and incomplete long-document coverage.

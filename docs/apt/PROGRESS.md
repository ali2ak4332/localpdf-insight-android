# Apt Reader implementation ledger

Plan: `IMPLEMENTATION_PLAN.md`; baseline commit `39ac160`.

- Preflight: remote branch exists; local checkout synchronized. Main unchanged.
- Ruling: proceed with development despite unavailable signing/device gates;
  withhold release. User explicitly requested continuation.
- Ruling: native CPU llama.cpp with digest-pinned GGUF; LiteRT 270M INT4 mobile
  artifact not assumed available. Cost: native dependency and Android build work.
- Model downloaded from ggml-org conversion of Google's QAT instruction model:
  revision `7dba9faa7cdb58c7dc44b238c7dbb00e391fbf65`, bytes 241410624,
  expected SHA-256 `3626e245220ca4a1c5911eb4010b3ecb7bdbf5bc53c79403c21355354d1e2dc6`.
- Toolchain setup underway. System package installation failed due to container
  package-manager restrictions; use tools extracted into the isolated workspace.
- Task 1: evidence boundary and planner complete; initial 13 tests passed. Final
  analysis/transport suite 19 passed after review fixes.
- Task 2: native runtime, verified model import and Android integration complete
  as development implementation. Host real-model, cancellation and file checks
  passed. Signed internal assembleRelease/lintRelease passed with 0 errors.
- Task 3: five-task panel, independent verification, source/page links and
  coverage implemented. Seven added offline browser workflows passed with
  mocked native transport; existing browser and native-policy results retained.
- Ruling: tiny-model relevance failure stops release, rather than counting exact
  copying as numerical accuracy. Verified extract integrity alone is insufficient.
- Task 4: host diagnostic completed and failed quality gate; representative-PDF
  benchmark, training and actual Android/device footprint validation uncompleted.
- Signing blocker resolved: recovered the user's LocalPDF signing backup and
  confirmed certificate equality; private key remains outside Git.
- Final review: separate reviewer found stale verification, missing adjoining
  clause context and interrupted-import cleanup. Fixed with corresponding
  regression checks. Full source/page highlighting is retained, with the
  documented limit that it does not select exact character offsets.
- Final: no merge, APK delivery, source-release archive or quality-success claim.
  Current measured state and next gates are in VALIDATION.md.

# Five-function evaluation protocol — 24 October 2026

This follow-up replaces passage-choice screening with actual outputs for
Summarize, Extract Insights, Extract Key Figures, and Identify Risks &
Obligations. Verify Findings is tested through the existing independent
deterministic implementation, including real reader citation navigation.

The frozen corpus contains 30 complete public English PDFs, ten each financial,
technical and contractual, with 76 physical pages. It is a convenience sample
of short documents, not a statistical representation of all English PDFs.
Financial issuers recur; technical material includes official fact sheets;
contracts include unfilled templates. No private user PDFs are used. Downloads
and setup precede offline local inference.

Corpus SHA-256: `a566a2bc17c137880d559b70a392a4881e69771111c14ebfe0729c0e5241454f`.
Pre-inference source-annotation SHA-256:
`e20c5678071ed6ca8c1c42155e0df26da689cf263073f0a4a7b95debfe1599d3`.
There are 207 source-checked reference anchors. They were authored and reviewed
by agents, not human domain experts. They identify important content rather
than exhaustively enumerating every acceptable finding.

Both Qwen3.5 0.8B and 2B use their pinned Q4_K_M artifacts, the same llama.cpp
revision, CPU four threads, native Jinja template, thinking disabled, temperature
zero, seed zero, context 8192, maximum 512 output tokens and two findings per
task. The text cap is 20,000 characters; all 30 PDFs fit completely. Context
shifting is disabled. This is a test adapter, distinct from the existing Android
4096-context source-index adapter; no app/model integration is implied.

A preliminary 0.8B run with unbounded schema strings was stopped after exposing
overlong quotations and output truncation. Its partial results are retained as
pilot evidence. The final run applies the same string-length constraints to both
models: claim 240, quote 160, metric/entity/party 80, value/unit 48, period 64,
obligation 200, deadline 100 and exception 160 characters. Prompt instructions
also retain the 25-word quote limit. This is a versioned protocol correction,
not fine-tuning or an independent holdout claim.

During the bounded run, external memory monitoring found the stock server's
separate auxiliary RAM cache growing despite prompt caching being disabled.
The 0.8B run was paused after 75 completed requests; those responses were
preserved. Remaining 0.8B requests and all 2B requests disable that cache with
`--cache-ram 0`. Resume validates identical corpus, model, prompts and schemas.
Cache phases are kept separate for memory/performance interpretation.

After disabling the auxiliary cache, model tests can overlap with four CPU
threads per model on the eight-CPU host budget. Generation-quality results are
compared with identical inputs/settings. Mixed/concurrent request timings are
not used as isolated per-model latency claims; a separate fresh-process,
single-model timing check is retained for that purpose.

Each model runs 120 generations: four tasks for every PDF. Responses preserve
claims/fields, exact quoted evidence and physical page numbers. Failures,
truncation, empty results and unsupported quotes are retained. Source text uses
the existing Android PDF.js and IndexedDB extraction/indexing pipeline.

Review records these dimensions separately:

- Technical completion: successful API call, complete parse and expected schema.
- Factual correctness: every generated statement/field follows from the source;
  metric, entity, value, units, period, party, deadline and exceptions stay aligned.
- Relevance: outputs perform the requested task; unfilled placeholders and
  publication metadata do not substitute for substantive findings.
- Coverage: at least an important reference anchor or justified equivalent is
  represented. A summary should describe purpose/main content and an important
  result or condition when one is present. Two findings cannot be exhaustive.
- Evidence: quoted text occurs on the cited physical page and actually supports
  the claim when its surrounding context is read. Literal presence and semantic
  support are separate judgments.

A strict document/task pass requires technical completion, factual correctness,
task relevance, adequate core-content coverage and valid supporting citations.
When no substantive task finding exists, an empty array is appropriate. A valid
finding outside the reference anchors can be accepted with an explicit source
reason; an annotation disagreement must not be silently called a hallucination.
Numerical accuracy is additionally reported per emitted figure record including
its metric/entity/unit/period, rather than inferred from quote copying or valid
JSON. Missing figures affect coverage, not the precision denominator.

Content-only passes (technical completion, factual correctness, relevance and
coverage) are also reported separately from strict usable passes, so a literal
quote-format mismatch is not mislabeled a false claim. Whitespace-only quote
differences still fail the existing exact-text citation contract. Conventional
rounding after correct unit conversion can be faithful in prose summaries if
exactness is not claimed; extracted figure records retain source precision and
explicit metric/entity/unit/period alignment. These review clarifications apply
uniformly to both blinded candidates.

Verify Findings reports exact-source integrity, altered-text rejection, revision/
page/source tamper rejection and real clickable citation checks. Exact text
presence cannot establish a paraphrased claim's meaning or truth. Negation and
omitted-qualifier challenges are reported as semantic limitations, not passes.
It must never receive an invented model-specific quality score just because it
uses no model.

No overall general-model rating is inferred. No fine-tuning is performed. These
host tests do not validate Android JNI integration, device RAM/speed, installed
footprint, upgrade/data retention, long-document synthesis or an APK release.
Raw inputs/results stay in evaluation working files; the report and public
results omit full third-party PDF text and long source excerpts.

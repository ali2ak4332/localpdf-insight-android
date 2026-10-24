# Five-function PDF evaluation — 24 October 2026

**Decision: BLOCKED. Neither tested model meets the requested quality checks.**
Both Qwen3.5 models were tested on all five functions. The earlier 8/10 result
was a small passage-choice screening score; it was not a PDF-analysis rating.

The completed evaluation uses **30 real public English PDFs**: ten financial,
ten technical and ten contractual, totaling 76 pages. Each model produced
actual outputs for the first four functions on every PDF: **240 generations and
240 source-based reviews**. Verify Findings was tested independently using the
existing production verifier and real reader citation navigation. All selectable
text was supplied through the existing Android PDF.js/IndexedDB pipeline.

## Task results

A content pass requires complete output, correct facts and field alignment,
relevance, and adequate core-content coverage. A strict usable pass also needs
exact quotations on the correct physical pages that support the finding.

| Function | 0.8B content passes | 2B content passes | 0.8B strict passes | 2B strict passes |
| --- | ---: | ---: | ---: | ---: |
| Summarize | 12/30 | 15/30 | 0/30 | 0/30 |
| Extract Insights | 13/30 | 17/30 | 0/30 | 0/30 |
| Extract Key Figures | 0/30 | 3/30 | 0/30 | 2/30 |
| Identify Risks & Obligations | 1/30 | 5/30 | 0/30 | 0/30 |

**Verify Findings:** 653/653 exact-source integrity checks and 30/30 real-reader
browser checks passed. Citations opened the correct physical page and
highlighted source text; verification made zero generation calls. However,
**semantic/factual claim verification is not implemented**. Forty context
challenges and two explicit negation probes demonstrate why an exact substring
cannot prove a finding's meaning. This fifth function therefore cannot be
marked as a complete factual-verification pass for either model.

All 240 final generation requests returned HTTP 200, complete JSON and a `stop`
finish reason. Valid JSON did not establish correct analysis. Neither model
returned an empty findings array in this experiment, including tasks whose
reference annotations expected no substantive finding.

## Numerical accuracy and attribution

| Measure | 0.8B Q4_K_M | 2B Q4_K_M |
| --- | ---: | ---: |
| Generated figure records | 58 | 60 |
| Correct value for the stated metric | 24/58 (41.4%) | 35/60 (58.3%) |
| Fully aligned metric/entity/value/unit/period or trigger | **0/58 (0%)** | **11/60 (18.3%)** |
| Figure records with correct unit | 10/58 | 19/60 |
| Figure records with correct period | 4/58 | 29/60 |
| Strict usable document/task results, all four functions | 0/120 | 2/120 |

These rates count emitted records; missing coverage and irrelevant/empty
results are tracked separately. Value correctness is not mere digit presence:
metric associations, bounds and ranges matter. Static specifications and
normative limits need no artificial measurement interval; dated financial
results require the correct period. Faithful prose rounding is accepted;
extracted figures retain source precision. The requested ≥95% numerical
accuracy is not demonstrated and the complete-record requirement fails badly.

On the financial subset, 2B copied all 20 raw values correctly, but only six
complete records had the right entity, unit and period. This is why reading a
number somewhere in the PDF is insufficient verification.

Actual-output checks through the original paragraph index accepted quotations
on the model-requested page for **49/232** 0.8B findings and **33/238** 2B findings.
There were three wrong-page matches across both models and 385 rejected quotes.
Some failures are spacing/line-wrap differences; others change wording, omit
words, or cite unrelated passages. Whitespace-normalized diagnostics and
semantic content judgments are separate. No source-boundary-only rejection was
found in the final recheck; two whole-page-exact rejections were below the
production verifier's 12-character minimum.

Examples from the source reviews:

- 0.8B scaled Apple's million-denominated results 1,000 times too small in a
  summary and confused quarterly versus annual columns.
- 2B confused Apple's net tax charge with the separate amount payable to
  Ireland and reversed a Berkshire comparative loss into a positive result.
- Both models converted forecasts/recommendations or unfilled template details
  into asserted facts or duties, and misplaced conditions or responsible parties.
- Some correct claims still received nonliteral or unrelated supporting quotes.

The per-case judgments, counts and source references are in
[results.json](results.json); [the manifest](corpus-manifest.json) contains the
30 source URLs and file hashes, including the issuer financial statements,
government technical sheets and contract templates.

## Size, RAM and processing time

| Measurement | Qwen3.5 0.8B | Qwen3.5 2B |
| --- | ---: | ---: |
| Verified model-file bytes | 532,517,120 | 1,280,835,840 |
| Optimized observed host peak RSS, approximately | 1.13 GB | 2.23 GB |
| Isolated four-task control median request | 23.2 seconds | 40.8 seconds |

The timing control used Apple's four-page Q4 financial statements, one request
per function, a fresh server per model and no concurrent model. It is a small
four-request control, not phone or document-wide latency validation. All eight
repeated outputs matched their original task outputs byte-for-byte. See
[timing-check.json](timing-check.json).

The main runs use CPU four threads, context 8192, native Jinja templates,
thinking disabled, greedy sampling, maximum 512 output tokens and two findings
per function. Some main requests overlapped across models; their mixed timings
are not isolated latency comparisons. An auxiliary server cache initially grew
the 0.8B process above 7 GB. It was disabled with `--cache-ram 0`; completed
outputs were retained and matching prompts/schemas validated before resume.
Old and optimized PID measurements remain distinct in the results. This is
server configuration, not intrinsic model storage or RAM requirements.

Weights, runtime RAM and actual installed Android footprint are different.
Installed footprint and phone performance remain unmeasured. The host adapter
is experimental and differs from the current Android 4096-context source-index
adapter. No Qwen model has been integrated into the APK.

## Limits and release blocker

This is an agent-reviewed, short-document convenience sample, not independent
human-expert validation. Financial issuers recur; contracts include templates;
technical material includes fact sheets. It does not validate long-document
synthesis, scans or OCR. Complete selectable text omits some visual meaning:
Intel's direction arrows, for example, were not preserved by extraction.

No additional fine-tuning was performed. The existing reader, package identity,
signing compatibility and release branch were not changed by this test-only
work. No new APK is approved or delivered. Numerical/field accuracy, reliable
evidence attribution and semantic verification remain blockers, alongside
uncompleted Android integration/device/upgrade/installed-footprint checks.

2B improves content accuracy in this adapter, but these results do not support
shipping either model. Further work needs source-grounded field extraction,
claim-level verification and calibrated abstention, followed by fresh tests.
A larger weight file alone has not met the requirements.

## Validation and reproducibility

[Protocol](PROTOCOL.md), corpus/model hashes, runtime revision, full paired
request fingerprint, grade hashes and raw-output hashes are retained. Public
results omit full third-party PDF text, prompts and long quotations. Local
source-review annotations were prepared before inference and were not used for
training or in prompts; review clarifications were applied to both blinded
candidates. The pilot and cache corrections are documented in the protocol.

The 19 analysis/transport regressions, framing regression, and 16 focused
aggregation tests passed. Real PDF import/indexing was offline with no external
browser requests. A broad desktop pytest collection attempt was blocked by
missing inherited Flask/PySide6 dependencies; it is not reported as a passing
suite. No Android build/device validation is newly claimed here.

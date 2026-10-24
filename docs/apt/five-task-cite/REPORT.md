# Cited-line five-task rerun — 24 October 2026

The paired rerun is complete. **Copying evidence preserves literal text, but neither pipeline demonstrates reliable PDF analysis. The earlier BLOCKED release status is unchanged.** No Android code, model weights, APK, package identity, signing configuration or release-branch changes were made.

## Preregistered comparison

Counts below compare the [original five-task run](../five-task/REPORT.md) with `cite-v1`. Both used the same 30 PDFs, model artifacts, runtime and rubric. See the preserved [preregistration](PREREGISTRATION.md), [machine-readable results](results.json), and [validation/provenance](VALIDATION.json).

| Measure | 0.8B: original → cite-v1 | 2B: original → cite-v1 |
| --- | ---: | ---: |
| Content passes | 26/120 → **22/120** | 40/120 → **38/120** |
| Strict passes (page evidence) | 0/120 → **17/120** | 2/120 → **30/120** |
| Fully aligned figure records | 0/58 → **2/10** | 11/60 → **14/22** |
| Figure values correct for stated metric | 24/58 → **6/10** | 35/60 → **17/22** |
| Figure units correct | 10/58 → **8/10** | 19/60 → **22/22** |
| Figure periods/triggers correct | 4/58 → **6/10** | 29/60 → **15/22** |
| Correct substantive abstentions | 0/14 → **7/14** | 0/14 → **7/14** |
| Rejected materialization attempts | Not applied → **122** | Not applied → **70** |

There were 2 failed generation requests under the unchanged 60-second request budget. These cases remain in the denominator, receive no technical/content/strict credit and were not retried. Only subsequent cases were resumed after checking frozen modules, model/runtime hashes and identical plans; prior response hashes were preserved. Evaluation completion means all cases were attempted and reviewed, not that every generation succeeded.

**Existing-reader compatibility remains a separate blocker:** 125 page-exact quotes cross original paragraph-source boundaries and nine are below the verifier minimum. In total, the original verifier rejects 134/247 retained quotes; only 113/247 are accepted at the requested page. These mechanical source-contract failures are distinct from semantic errors. The application would need individual cited-line sources/citations before this host protocol could be adopted.

Figure fractions count **retained emitted records**, not all requested figures. Dropping outputs can improve precision while losing coverage. A value is correct only for its stated metric; mere digit presence is insufficient. Duplicate findings remain in the registered record denominator and add no coverage.

## Task results

| Function | 0.8B content | 0.8B strict | 2B content | 2B strict |
| --- | ---: | ---: | ---: | ---: |
| Summarize | 5/30 | 3/30 | 7/30 | 4/30 |
| Extract Insights | 9/30 | 6/30 | 14/30 | 11/30 |
| Extract Key Figures | 8/30 | 8/30 | 14/30 | 14/30 |
| Identify Risks & Obligations | 0/30 | 0/30 | 3/30 | 1/30 |

Content requires technical completion, factual and field correctness, relevance and adequate core coverage. Strict passes additionally require page-exact evidence that supports the finding under cite-v1. They do not establish acceptance by the existing paragraph-source verifier. An exact quotation is not semantic verification.

## What copying and filtering did

| Output accounting | 0.8B | 2B |
| --- | ---: | ---: |
| Actual generation calls | 111 | 111 |
| Automatic figure skips | 9 | 9 |
| Model-selected findings | 220 | 217 |
| Retained findings | 98 | 149 |
| Materialization rejection entries (includes malformed outputs) | 122 | 70 |
| Retained quotes exact on cited page | 98 | 149 |
| Malformed response-container errors | 0 | 2 |
| Filtered empty cases (all attempts rejected) | 48 | 26 |
| Of those, source correctly expects no finding | 6 | 2 |

As a separate visible-output diagnostic, counting correctly filtered empty answers as successes yields content passes 28/120 and 40/120, and page-evidence strict passes 23/120 and 32/120 (0.8B, 2B). These are separate from the preregistered abstention-credit rule.

**Seven of nine automatic figure skips per model are correct; two are false skips.** The inherited footnote heuristic suppresses deadlines written as thirty (30) and ten (10), omitting substantive figures in `contractual-08` and `contractual-23`. These remain failures in the frozen run.

Rejected attempts are reported separately, not labeled hallucinations. Under the preregistered conservative rule, an all-rejected answer receives no deliberate/automatic abstention credit; the table separately identifies filtered empty cases, including those that correctly display no finding. Reviewers saw only materialized findings, source context and non-exhaustive frozen anchors; rejected/raw selections were hidden.

Copied fields still require source checking. Observed failures include quarter/year confusion, forecast EPS presented as realized performance, missing return-period end dates, missing concentration units, unsupported risk fields and omitted contractual exceptions. Narrow exact citations can fail to support an otherwise source-true claim.

## Verify Findings: fifth function

| Original paragraph-index recheck | 0.8B | 2B |
| --- | ---: | ---: |
| Retained findings checked | 98 | 149 |
| Accepted at requested page | 27 | 86 |
| Rejected by original verifier | 71 | 63 |
| Page-exact but crossed source boundary | 65 | 60 |
| Below verifier minimum length | 6 | 3 |

The independent rerun passed **653/653 source-integrity checks** and **30/30 real-reader citation checks**, with zero generation calls. Its 40 context challenges and two negation probes still show that **semantic/factual verification is not implemented**. It receives no model-quality pass score.

Actual-output checks against the original reader paragraph index are retained separately from page-literal matching in `results.json`. A copied multiline span may be exact on its page yet fail the original paragraph-source contract; this protocol would need separate line citations in an app integration.

## Method, audit and limits

This is a development benchmark of 30 public English PDFs (10 financial, 10 technical, 10 contractual; 76 physical pages), using the original PDF.js/IndexedDB text. Corpus and frozen gold are byte-identical to the baseline. Both Qwen3.5 Q4_K_M artifacts and the inference binary match the baseline hashes. CPU four threads, context 8,192, greedy/seed 0, thinking off, 512 output tokens and at most two findings were retained; no fine-tuning was used. All 111 rendered prompts per model fit (maximum 5,823 + 512 tokens).

The real-corpus audit preceded inference and added ten extractor regressions: split date/return headers, share and per-share scaling, stale headers, identifiers, dotted leaders, percent metadata and duplicate-value rejection. Extractor fixes were informed by this corpus, so this is not an independent holdout test. The three production/materialization module hashes were frozen before generation and remained unchanged.

Further discovered defects were scored rather than repaired mid-run: the two false skips, par-value scaling, percentage-point/basis-point conflation, duration-only return periods and incomplete infographic/complex table metadata. Parser errors and model errors both affect these pipeline scores. A separate deterministic replay regenerated all plans, materialized findings and rejection records and checked frozen hashes before publication.

Reviews were performed by blinded agents, not independent human domain experts. A technical grader was replaced before any technical grades were produced after an inadvertent model-label disclosure; included technical grades come from the fresh blinded grader. Source anchors are non-exhaustive; equivalent important findings were accepted with reasons.

The sample is short and issuer-heavy, and selectable text omits some visual meaning. It does not validate long documents, scans/OCR, Android integration, phone RAM/speed, upgrade/data retention or installed footprint. The app uses a 4,096-token context, so adopting this host protocol would require section-level tests. Main-run timings overlap and include materialization overhead; no direct speed comparison or device claim is made.

## Checks and next step

45 Node tests, 26 aggregation tests, the fake-server harness, 51 checks on eight synthetic PDFs, seven deliberate extractor mutations, seven panel checks and 21 Android browser checks passed. Fresh review found and fixed null-usage reporting and false abstention credit; the final replay/aggregation checks passed. Public results omit full PDF text, prompts, quotations and raw model outputs. Sources and PDF hashes remain in the [original corpus manifest](../five-task/corpus-manifest.json).

The next useful test is to repair deterministic omissions and use one enumerated source/figure-candidate ID per finding, then evaluate a fresh held-out corpus. Increasing model size alone cannot repair extractor errors or establish claim support. The independent support-filter patch was not applied in this comparison.

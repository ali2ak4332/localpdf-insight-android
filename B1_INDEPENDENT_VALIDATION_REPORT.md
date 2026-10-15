# B1 fresh adversarial validation — engineering handoff, not a release

**Disposition: further correction and live validation required. No RC or production GO.**
Starting commit: `161d8b627bd9a84a936fcf73d0d0d960f0e943b3`, initially clean.
The new commit and handoff checksums are recorded in the accompanying handoff after
the evidence is committed. This review and the repairs were performed by the coding
assistant. Source-based expectations were derived separately from generator output;
this is **not human review, external organizational independence, or live-model evidence**.
Repairs require subsequent independent re-review.

## Verified starting state

`docs/b1-independent/baseline-verification.json` records the starting commit/status,
complete-history bundle verification, six matching handoff artifact hashes and the
historical baseline logs. Engineering bundle SHA-256:
`78f4b49514177f3e0f95fc9c78b702380b9a0e4853e6414a41df48f95c8dd633`.
The historical Python result is 872 passed/1 skipped, browser 21 excerpt workflows,
and 540 controlled matrix executions. These totals were checked against the files;
they were not treated as semantic reliability or rerun unchanged before repairs.

The original operating-profit/net-profit counterexample and the separate available,
deliberately approving verifier both passed focused reproduction. The latter records
`metric_mismatch`; refusal did not depend on a missing Ollama service. Their fixture,
question, compromised response and assertions are unchanged. All assertions in the
three older matrix test modules remain AST-identical; see `assertion-preservation.json`.

## Findings and corrections

| Finding | Cause | Correction / disposition |
|---|---|---|
| A supported witness released unrelated neighboring facts, including reports, selected text and saved outputs | Review bound sentence witnesses, but `safe_answer` promoted a source ID into authorization for the entire larger source | Render only server-defined approved spans. Recheck each unit/offset against resolved source text. Preserve original source/document/page IDs and exact quoted bytes. No generated factual prose is rendered. |
| Same-source and explicit legal conflicts were not reliably disclosed | Conflict representation required different source IDs; the numeric accumulator overwrote some accepted sides; legal opposition was not represented | Permit distinct witnesses in one source; collect all explicit same-proposition opposing values; compare bounded actor/action/condition signatures. Different conditions and permission/obligation alone are not conflated. |
| Substitution of standalone/group scope, fiscal/calendar year, target/forecast, recommendation/obligation and accounting sign | Explicit distinctions were not represented in the veto layer | Add bounded contradiction dimensions; currency-bound accounting parentheses retain their negative comparison value. Raw source text is never rewritten. |
| Lowercase named entity mismatch escaped checks | Entity binding relied largely on capitalization | Bind explicit `of NAME for PERIOD` syntax; restrict it after a demonstrated false refusal on a verbal paraphrase. This is not a general entity resolver. |
| Material qualification crossed a native PDF layout block | Retrieval admitted the leading block but not an adjacent dependent continuation | Preserve raw extraction/PDF; identify an explicit immediate same-page continuation from SQLite and withhold the incomplete final witness. Six API regressions cover both modes/scopes. Cross-page and implicit dependencies remain unverified. |
| Minimum/maximum substituted in previously unseen wording | Extremum was not a comparison dimension | Add explicit extremum opposition, with inverse/alternate-attribute regressions. |
| Supported Arabic paraphrase refused | `غير` inside an attributive noun phrase was treated as clausal negation | Do not use this ambiguous adjective as a deterministic clausal veto. Explicit clausal negators still veto; adjective scope remains a semantic-verifier responsibility. |
| Previously saved version-2 answers could re-release whole-source quotations | Old saved snapshots satisfied the old version check | New server release-policy stamp; older generated snapshots are withheld without modifying their stored bytes. Notes/excerpts and newly saved valid outputs retain their behavior. |

The generation callback remains separate from the verifier transport and cannot
provide final approval. Server resolution, coverage offsets, contradiction vetoes,
failure handling and source-only rendering remain authoritative. The default verifier
uses the same configured local model weights: correlated error remains a risk.
Schema-valid review JSON is not entailment proof.

## Frozen corpus and measured results

First corpus: 48 language-specific scenarios / 24 families, each executed in two modes
and three scopes: **288 executions**. Before application edits, corpus SHA-256 was frozen:
`5319d924b80419bcd284f6da96baa5d98e542cb78c454e569c52752a18191414`.
Expected passages/classifications did not change. Early runs exposed two harness
issues: narrow Arabic layout violated the intended single-source precondition, and
one checker unnecessarily required a separate claim per sentence. Both original
runs and the narrow PDF remain preserved. The corrected pre-repair baseline is
`frozen-baseline-run`; all adjustments are disclosed in `harness-adjustment-final.json`.

| Evidence set | Before repair | After repair |
|---|---:|---:|
| First corpus, actual output/citation/coverage checks | 144 passed / 144 failed | 288 passed / 0 failed |
| Wholly unsupported cases accepted | 60 / 120 | 0 / 120 |
| Supported/partial/conflict cases with extra or wrong released material | 84 / 168 | 0 / 168 |
| Positive cases completely refused | 0 / 168 | 0 / 168 |
| Second corpus: 6 scenarios, 36 executions | 6 passed / 30 failed | 24 passed / **12 failed** |
| Second corpus unsupported acceptance | 24 / 24 | **12 / 24** |
| Second corpus positive refusal | 6 / 12 | 0 / 12 |

The second corpus was frozen before querying. Its minimum/maximum and Arabic
paraphrase cases guided repairs and are now regressions, not untouched holdouts.
It deliberately measures the dependency on semantic review; it is an executable
diagnostic returning **exit 1** when expectations fail, separate from the Python
regression suite. No failure is xfailed, relabelled as a pass or merged into a rerun.

**Remaining counterexample:** a question about the invoice rejection rate receives
an authentic customer-churn-rate quotation for the same named company and period.
The available separate verifier deliberately approves it. Both English and Arabic
cases fail in both modes and all three scopes: **2 unique scenarios / 12 executions**.
Citation authenticity and the new renderer do not distinguish these unfamiliar
metrics; no applicable deterministic metric label exists. Adding those two labels
would memorize this challenge, not demonstrate general entailment. A real semantic
verifier may distinguish them, but that has not been tested here. This remains a
High finding and prevents semantic release assurance. No universal impossibility
claim is made, and no model-independence claim is made.

The passing first corpus and failing diagnostic must be reported together. Across
their final runs: 312/324 pass, 12/144 wholly unsupported executions are accepted,
0/180 positive executions are fully refused, and 0/180 positive executions contain
unapproved extra material. These are dependent controlled executions, not independent
observations, population error estimates or confidence bounds.

The preserved narrow Arabic layout is additionally **answerable on the full page**,
although the server cannot safely bind its split qualification. All six mode/scope
executions safely abstain. Count these as **6/6 end-to-end false refusals** for
usefulness, not semantic successes. The diagnostic `narrow-layout-run` preserves
all six actual outputs and returns exit 1; the corresponding six safety regressions
pass because they require withholding incomplete evidence. Including this case:
**55 unique scenarios / 330 executions; 312 pass / 18 fail; 12 false acceptances /
144 unsupported executions; 6 false refusals / 186 positive executions**. Two
language-specific scenarios account for the remaining false acceptances; one
Arabic layout scenario accounts for these refusals.

## Evidence completeness

Historical reconciliation confirms **432/444** main records, with exactly the 12
unavailable-verifier cases missing and separately recaptured. The exact historical
cause cannot be reconstructed: the optional append exporter had no mandatory case
inventory, run ID, terminal outcomes or reconciliation. Available logs cannot prove
which path/environment/interruption caused the omission. See `collector-investigation.json`.

New collection uses exclusive UTF-8/fsynced files per run/case, an inventory fixed
at collection, independent pytest phase outcomes, explicit write-error records,
and finalized JUnit reconciliation. Missing, duplicate, foreign-run, malformed,
contradictory and interrupted records prevent a complete result. Reusing an output
directory is rejected. Sixteen recorder fault tests pass, including an actual child
process killed before its terminal outcome and a passing test forced to fail its
run for omitting mandatory evidence. Parallel pytest workers are not a validated
collection configuration.

An intermediate new console log also truncated at 48%, despite complete case/JUnit
records. It is preserved; its cause is not established. `run_tests.py` now collects
the raw process output and writes it once at completion, then requires final console
totals to match JUnit and terminal records. The successful repeated full run is
`complete-python`: **1,197/1,197 terminals; 984/984 mandatory matrix records; complete
JUnit and console reconciliation**. An interruption without `completion.json` is
not complete. Earlier failed/incomplete runs remain separately identifiable.

## Verification

| Gate | Observed result |
|---|---|
| Full Python regression suite | **1,196 passed, 0 failed, 1 skipped**; `complete-python/pytest.txt`, JUnit and completion manifest |
| Original/boundary/older-variation/new corpus matrix records | 156 + 444 + 96 + 288 = **984**, all regression records pass |
| Separate semantic stress diagnostic | **24 passed, 12 failed**, 36/36 records/terminals; not a passing gate |
| Narrow-layout usefulness diagnostic | **0 passed, 6 refused**, 6/6 records; safe withholding succeeds but the page is answerable |
| Browser reader + Studio | **13 + 8 = 21 passed**, Chromium 153.0.8010.0, excerpt mode |
| Unicode/recovery | **6 passed** within full suite; UTF-8, actual C locale, cp1252 simulation, original bytes, same-path/relocated restoration |
| Arabic OCR | Skipped: `Arabic Tesseract language pack is not installed`; installed packs are eng/osd; attempted pinned official language-data download failed DNS resolution |
| Live release model | **UNVERIFIED**; loopback service connection refused, no Ollama executable/recorded manifest; no substituted model/excerpts |
| Windows / physical Android / trusted HTTPS-PWA | **UNVERIFIED**; no corresponding real environment; browser mobile/PWA shell tests do not qualify |
| Clean dependency installation | **FAILED/INCOMPLETE**: locked PyMuPDF 1.28.2 cannot be resolved from the accessible index; isolated download reports no matching distribution. Direct endpoint probes also fail DNS. Dependencies were not loosened. |
| Clean-checkout wheel build and extracted smoke | **Passed using existing dependencies**: two byte-identical wheels from clean engineering commit `6a5ca62ec1497ae2a54a8e558f1d745e426d9782`; all package members inspected against source; fresh extraction/import/index/excerpt/citation/PDF-byte smoke passed. Clean installation remains incomplete. |

Live target remains `qwen2.5:3b`, expected digest
`357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b`.
Actual runtime version/digest: **unavailable / null**. No live answer/report or human
page review occurred. Generation/verifier parameters and the exact connection failure
are in `live-model.json`. Fixtures/procedure are in `docs/b1-independent/EXTERNAL_VALIDATION.md`.

### Engineering package evidence

`package-build-summary.json` records both exact build commands and the clean
checkout status; `package-members.json` records every member/hash. Both wheels have
SHA-256 `f7e0cea82aed628bf0fcdb2f90a659a11454087f058c980e3fa47ade46524a3b`.
`package-smoke.json` confirms code imported from the fresh extracted wheel while
using the previously installed dependency environment. The wheel contains production
code/assets and distribution metadata only, with no validation documents, user
PDFs or storage databases. These are engineering build results, **not release
candidates or successful clean dependency installation**. The final handoff also
records a post-commit build/smoke check against its exact reported commit; its
sidecar evidence is outside the repository to avoid a self-referential commit hash.

## Exact execution commands

Run from the repository with its installed validation environment; use new output
directories for reruns. Commands below correspond to the retained attempts.

```bash
git rev-parse HEAD
git status --porcelain=v1
.venv/bin/python -m pytest -ra tests/test_grounding_remediation.py::test_same_period_wrong_metric_must_not_pass_a_compromised_review tests/test_verification_boundary.py::test_retained_counterexample_is_vetoed_even_with_available_lying_verifier
.venv/bin/python scripts/validation/run_tests.py --output docs/b1-independent/complete-python
.venv/bin/python scripts/validation/semantic_stress.py --run docs/b1-independent/semantic-stress-after-run
.venv/bin/python scripts/validation/narrow_layout.py --run docs/b1-independent/narrow-layout-run
LOCALPDF_TEST_PYTHON="$PWD/.venv/bin/python" CHROMIUM_EXECUTABLE=/workspace/scratch/bdd32fb43c2c/browser-runtime-153/chromium LOCALPDF_TEST_ARTIFACTS="$PWD/docs/b1-independent/browser-reader" npm run test:browser
LOCALPDF_TEST_PYTHON="$PWD/.venv/bin/python" CHROMIUM_EXECUTABLE=/workspace/scratch/bdd32fb43c2c/browser-runtime-153/chromium LOCALPDF_TEST_ARTIFACTS="$PWD/docs/b1-independent/browser-studio" npm run test:studio
.venv/bin/python scripts/validation/live_grounding.py --suite boundary --output docs/b1-independent/live-model.json
```

The clean-install and pinned-distribution probe commands, interpreter/checkout paths
and return codes are recorded verbatim in `clean-install-attempt.json` and
`clean-install-pin-probe.json`. No prior release evidence was overwritten.

## Changed files and remaining findings

Application: `verification.py`, `constraints.py`, `grounding.py`, `evidence.py`,
`web.py`. No dependency lock, PDF.js, persistence schema or generation-model parameter
change. Validation: new frozen corpus/boundary/stress/recorder tests, recorder plugin,
reconciliation/run/stress/package-smoke scripts, and the live harness's citation-span
check. Older matrix exporters were routed through the mandatory recorder; existing
assertions remain identical. New reports/procedure and evidence are under
`docs/b1-independent`; the current release/operations findings are updated without
removing historical evidence. Review the committed diff before accepting any repair.

- **High:** unfamiliar-metric false approval remains possible; live pinned-model
  reliability has no evidence; cross-unit semantic dependence and arbitrary
  coreference cannot be guaranteed by the bounded parser.
- **Medium:** clean dependency installation/reproducibility incomplete; actual
  Windows, physical Android and trusted HTTPS/PWA unverified; Arabic OCR pack absent;
  conservative refusal on the split-layout answerable page; historical export omission and intermediate console truncation causes unresolved
  (new completion controls independently tested).
- **Low:** no newly demonstrated Low blocker; bounded parser coverage and existing
  sampled-report/layout limits remain documented limitations, not certifications.

Next: review these repairs and remaining unfamiliar-metric examples independently,
then run the exact pinned local model on the full boundary and representative-page
corpus in an environment with verified dependencies. Retain every false acceptance
and refusal. No release candidate is justified by the current evidence.

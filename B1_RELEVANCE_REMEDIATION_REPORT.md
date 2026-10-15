# B1 evidence-support engineering remediation

**Engineering correction implemented and tested. Release validation remains incomplete. No RC ZIP or production GO.**

Starting commit: `6c3821bfea2c10657f198c40a9136bc167c1d8dd`, initially clean. The exact new commit and source-bundle checksum are recorded in the post-commit engineering handoff. This report cannot contain its own commit hash. Prior reports are preserved byte-for-byte under `docs/b1-engineering/prior-*`; all earlier evidence directories and Git history remain intact.

## Reproduction and trust boundary

Before edits, the retained regression again released “The net profit of Atlas for 2025 was AED 100 million.” for “What was the operating profit of Atlas for 2025?” `before-counterexample.json` and `.txt` record the failing response and assertion. The earlier verified full baseline was reused: 289 passed, 1 failed, 1 skipped; 21 browser workflows in excerpt mode.

The old path was `web → evidence.answer → grounding.safe_answer → review_question`. Candidate generation and semantic approval used the same supplied generator callable. Server-side source resolution authenticated the quotation, but affirmative model-controlled `checks` authorized relevance. Authenticity did not establish metric equivalence.

The original regression function is byte-identical to the starting commit. It now withholds the answer because its compromised generator cannot also provide verification. In this environment that separate runtime is unavailable. **That alone is not evidence that a wrong metric is detected.** An additional test executes the same unchanged regression with a separate, available verifier deliberately approving every unit. It still withholds the answer, records `metric_mismatch`, and has no verifier/runtime failure. See `current-original-b1.json`, `current-lying-verifier-b1.json`, and `test-preservation.json`.

## Application control

- `verification.py` defines immutable question/source requests, server-defined question parts and evidence unit identifiers, and a distinct verification callable. The production verifier has its own loopback Ollama `/api/chat` transport; it never invokes or aliases the answer generator. Its input excludes candidate prose, candidate reasoning, generated flags and conversation history. PDF text is supplied as data. Redirects/proxies are disabled; timeouts, incomplete/malformed responses and unavailable verification withhold generated answers.
- `grounding.py` resolves source IDs against retrieved server evidence, validates complete question coverage and bound source-unit witnesses, and owns the final decision. Legacy Boolean approvals grant no access. Classifications are `SUPPORTED`, `PARTIAL`, `CONFLICTING`, `ABSENT`, `UNVERIFIED`; absence is explicitly limited to retrieved passages. Numeric conflicts with matching parsed attributes are checked across retrieved sources even when the verifier omits a side.
- `constraints.py` applies negative vetoes to individual passages: identifiable metrics, entities/roles, reporting periods and dates, decimal quantities/scales, percentages, units/currencies, actual/forecast intent, legal modality, polarity, comparisons and explicit qualifications. It never uses shared-keyword overlap as sufficient support. Shared subjects/periods in coordinated questions remain bound to each requested part. Ambiguous cross-sentence or multi-entity combinations cannot assemble support from unrelated facts.
- B2 remains source-only: generated claims are never rendered. The server copies complete original source units, preserving qualifications and deterministic citation metadata. Partial responses identify unanswered question parts; conflicts disclose cited sides. Reports now traverse the same support boundary instead of bypassing review. Previously saved version-1 AI approvals are withheld on read, without altering original SQLite snapshots, notes or source links.
- `web.py` supplies a separate verifier dependency. A generated question with zero lexical matches can use the existing bounded scoped sampling utility; it warns that coverage is partial. This corrects a measured false refusal for a supported paraphrase. Sampling does not authorize release. Excerpt mode, source scope identities, PDF.js, SQLite schema, migration and recovery remain intact.
- `evidence.py` supplies verification separately and records `UNVERIFIED` for malformed or unavailable generation. No unsafe generated-answer fallback is introduced.

This is application interface isolation, **not** a sandbox against arbitrary Python execution or proof of model independence. By default both transports use the configured local model; correlated errors remain possible. Audit metadata states that identity is based on configured tags, not an observed digest, and makes no semantic-independence claim. Deterministic vetoes override false semantic approval for covered contradictions; unrecognized meanings still require probabilistic semantic review.

## Tests and results

| Check | Actual result | Evidence / limits |
|---|---|---|
| Complete Python suite | **872 passed, 0 failed, 1 skipped**; 873 collected | `complete-python.txt`, `.xml`; Linux Python 3.12.14 |
| Existing grounding tests | **203 passed** | Retained regression plus original matrix, schema and B2 tests; included in full total |
| New main matrix | **444 passed** | 37 scenarios × 2 languages × 2 modes × 3 scopes |
| Unseen variations | **96 passed** | New entity, metric, year, value and wording combinations after first implementation snapshot; not independent live-model validation |
| False acceptance | **0 / 342 negative cases** | Main matrix 0/294; unseen variations 0/48 |
| False refusal | **0 / 198 positive cases** | Main matrix 0/150; unseen variations 0/48; answers include extracts supporting paraphrased questions |
| Browser reader / Studio | **13 + 8 passed** | Chromium 153.0.8010.0, Playwright 1.62.1; excerpt mode |
| Unicode/recovery | **6 passed** | Included in full suite; genuine C locale, UTF-8, labelled cp1252 simulation; same-path/relocated recovery, citations and Studio |
| Arabic OCR | **1 explicit skip** | `tests/test_evidence.py:186`: Arabic Tesseract language pack is not installed (`ara.traineddata` unavailable) |
| Live release model | **UNVERIFIED** | Loopback connection refused; actual digest null, zero live answers or reports reviewed |
| Windows / physical Android / trusted HTTPS-PWA | **UNVERIFIED** | No corresponding host, physical device or trusted installation exercised |

The 156 existing matrix rows also pass but are reported separately: their verifier receives controlled fixture labels. None of these controlled tests measures real semantic model accuracy. Test totals overlap; do not add focused suites to the full suite. Each new matrix record retains question, evidence, expected classification, actual output, verifier requests/responses, citation checks, false-acceptance/refusal flags and result before asserting. Main matrix covers partial/conflict, substitutions, injected claims, exact quotes, English/Arabic/multilingual paraphrases, prompt injection, false approvals and verifier failures. Separate tests cover immutable requests, independent transport, malformed witnesses, old cached approvals, neutral yes/no negation, compound questions and runtime failures.

The final collector initially retained 432 of 444 main matrix rows although JUnit recorded all 444 passing. The 12 unavailable-verifier cases were rerun unchanged and all 12 records were captured in `unavailable-recapture.jsonl`. The cause of the first export omission is unestablished; neither export nor test log was overwritten. `grounding-matrix.jsonl` combines those explicit runs and the 96 variation records with per-row recording provenance. This evidence-recording limitation is disclosed rather than filling missing rows from expectations.

Citation checks resolve the source/document/page and fetch the corresponding PDF. Browser workflows separately exercise actual citation clicks. The matrices are not 540 manually clicked live answers. Arabic fixture text is synthetic; it does not certify OCR or arbitrary PDF font extraction.

Failed engineering attempts remain recorded: the initial year parser confused “2025 was AED…” with a monetary amount; an Arabic role pattern did not match normalized `على`; zero-overlap paraphrases retrieved no sources; a named Arabic date was also parsed as a quantity; coordinated questions initially lost trailing shared context. These were corrected without changing existing assertions. `development-matrix-1.*`, `additional-boundaries-1.txt`, `compound-before.json` and earlier logs remain. Initial browser launches found a missing temporary executable; the available cached Chromium 153 was restored, and unchanged workflows passed.

The unseen-variation first run passed 96 cases before subsequent general date/compound/audit work. `pre-holdout-implementation.json` and `holdout-first.*` preserve that chronology; later reruns are regressions, not a fresh blinded evaluation. No independent human semantic labelling or live semantic guarantee is claimed.

## Files and existing-test setup changes

Production: new `src/localpdf_insight/{verification,constraints}.py`; modified `grounding.py`, `evidence.py`, `web.py`. No new production dependency, cloud service, agent or UI feature.

New tests: `tests/{verification_support,relevance_matrix_support,test_verification_boundary,test_verification_holdout}.py`.

Existing tests changed only at dependency setup/logging: `test_convenience.model_reply` injects a separately defined verifier; `test_grounding_remediation` injects independent matrix/B2 verifiers and records their calls. Documents, questions, expected results and all 72 existing assertions in those two files are unchanged. `test-preservation.json` records AST assertion equality and byte equality of the original failing function. A verifier fixture does not read an expected result from generator output.

Other changes: `scripts/validation/live_grounding.py` records the new verification transport and actual fixture PDFs; this report, the release report, project state, operations guide, external procedure, and `docs/b1-engineering/` evidence.

## Exact verification commands

Commands run from the repository root. Use fresh output paths on repeats because JSONL collectors append.

```bash
git rev-parse HEAD
git status --porcelain=v1
# Before application changes:
LOCALPDF_OPEN_BLOCKER=docs/b1-engineering/before-counterexample.json .venv/bin/python -m pytest -q tests/test_grounding_remediation.py::test_same_period_wrong_metric_must_not_pass_a_compromised_review

# Recapture the 12 missing matrix records (separate output, unchanged tests):
LOCALPDF_BOUNDARY_MATRIX=docs/b1-engineering/unavailable-recapture.jsonl .venv/bin/python -m pytest -q tests/test_verification_boundary.py -k 'test_independent_verifier_matrix and unavailable' > docs/b1-engineering/unavailable-recapture.txt 2>&1

# Complete final implementation:
.venv/bin/python -m pytest -ra --junitxml=docs/b1-engineering/complete-python.xml > docs/b1-engineering/complete-python.txt 2>&1

# Full grounding / Unicode evidence, same final application:
LOCALPDF_BOUNDARY_MATRIX=docs/b1-engineering/current-boundary.jsonl \
LOCALPDF_HOLDOUT_MATRIX=docs/b1-engineering/current-holdout.jsonl \
LOCALPDF_GROUNDING_MATRIX=docs/b1-engineering/current-prior-matrix.jsonl \
LOCALPDF_UNICODE_LOG=docs/b1-engineering/current-unicode.jsonl \
LOCALPDF_OPEN_BLOCKER=docs/b1-engineering/current-original-b1.json \
LOCALPDF_BOUND_B1=docs/b1-engineering/current-lying-verifier-b1.json \
.venv/bin/python -m pytest -ra tests/test_grounding_remediation.py tests/test_verification_boundary.py tests/test_verification_holdout.py tests/test_unicode_remediation.py --junitxml=docs/b1-engineering/grounding-unicode.xml > docs/b1-engineering/grounding-unicode.txt 2>&1

LOCALPDF_TEST_PYTHON="$PWD/.venv/bin/python" CHROMIUM_EXECUTABLE=/tmp/localpdf-chromium-b1-engineering LOCALPDF_TEST_ARTIFACTS=docs/b1-engineering/browser npm run test:browser
LOCALPDF_TEST_PYTHON="$PWD/.venv/bin/python" CHROMIUM_EXECUTABLE=/tmp/localpdf-chromium-b1-engineering LOCALPDF_TEST_ARTIFACTS=docs/b1-engineering/browser npm run test:studio

.venv/bin/python scripts/validation/live_grounding.py --suite boundary --output docs/b1-engineering/live-model-final.json > docs/b1-engineering/live-model-final.txt 2>&1
```

The final live command exited 3 with `URLError: <urlopen error [Errno 111] Connection refused>`. Target: `qwen2.5:3b`, expected digest `357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b`. Neither actual digest nor runtime version could be observed. Generation parameters are temperature 0.1 / 1,024 tokens; verification parameters are temperature 0 / 2,048 tokens / 30-second timeout. The external procedure requires actual model responses and manual page review; no substitute model or excerpt gate was used.

## Remaining findings and decision

**High / release gates:** live English/Arabic semantic reliability, false-refusal and false-acceptance rates, report adequacy and latency remain unmeasured. The parser has finite vocabulary and syntax coverage. For example, unfamiliar metrics, paraphrased legal relationships, transliterated entities, spelled-out quantities and implicit qualifications still depend on the separate semantic verifier. A wrong verifier judgment outside deterministic coverage can remain wrong. No universal semantic proof is claimed. Actual Windows, physical Android, trusted HTTPS/PWA and Arabic OCR remain unverified.

**Medium:** ambiguous units or complex coordinated questions may fail closed; the positive-control matrix is finite. Bounded sampling can miss a requested fact and cannot prove document-wide absence. General nonnumeric conflicts depend on semantic review. Source-only assisted output preserves earlier limitations on free-form interpretation/translation. Clean installation/build reproducibility, a complete rollback drill, large-document performance and real-device recovery remain unverified. No RC build or archive smoke test was represented as complete.

**Low:** no new Low finding established; this is not a fresh security audit.

There are no remaining failures in the executed regression matrix. This does not clear the open live/platform release gates. Engineering changes are retained, with the missing environments documented rather than used to block local work. Next: independent review of the boundary and retained counterexamples, then run the pinned model with `docs/b1-engineering/EXTERNAL_VALIDATION.md` and manually review every answer/report against its cited page. Only the independent gatekeeper may decide release readiness. **No RC ZIP, RC checksum or production GO is issued.**

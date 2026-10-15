# Current fresh B1 validation disposition

**Release blocked; no RC.** See [B1_INDEPENDENT_VALIDATION_REPORT.md](B1_INDEPENDENT_VALIDATION_REPORT.md) and `docs/b1-independent/results-summary.json`.

Starting commit `161d8b627bd9a84a936fcf73d0d0d960f0e943b3` was verified clean. Approved evidence now renders only server-owned witness spans, with bounded qualification/conflict/scope corrections. The unchanged original B1 counterexample passes. Full Python: **1,196 passed, 0 failed, 1 Arabic OCR skip**. Browser: **21 passed in excerpt mode**. The mandatory recorder reconciles **984/984** matrix records and **1,197/1,197** terminal cases with JUnit and a complete raw console log.

The 288 fresh regression executions pass after repairs, but a separate frozen semantic stress diagnostic still has **12 false acceptances / 24 unsupported executions**, spanning two unfamiliar-metric scenarios in both modes/scopes; **0 false refusals / 12 positive executions**. Its 36/36 records are preserved, including all failures. A separate narrow-layout diagnostic counts **6/6 safe abstentions as end-to-end false refusals** because the complete page is answerable. Across all new final probes: **12 false acceptances / 144 unsupported executions and 6 false refusals / 186 positive executions**. Controlled passes do not establish semantic reliability. The exact cause of the previous 432/444 export omission remains unestablished; mandatory completion checks and fault tests now fail incomplete runs.

Live pinned `qwen2.5:3b` remains **UNVERIFIED** (connection refused, actual digest unavailable). Windows, physical Android and trusted HTTPS/PWA remain **UNVERIFIED**. Clean dependency installation cannot resolve locked PyMuPDF 1.28.2. Two engineering wheels from a clean checkout were byte-identical and the isolated extracted-code smoke test passed using existing dependencies; clean installation remains incomplete. No release candidate was created. All changes still require independent re-review.

The previous report below is retained as historical evidence, not a statement of current completeness.

---

# Current B1 engineering result — 2026-09-18

Starting commit: `6c3821bfea2c10657f198c40a9136bc167c1d8dd`. **Application remediation implemented; release gates remain incomplete. No RC ZIP or production GO.** The previous report below is preserved as historical evidence, not the current implementation status.

B1's shared generator/reviewer callable has been replaced with a separate verification interface and loopback transport. Server-owned proposition checks veto identifiable contradictions, including the retained wrong-metric example under a deliberately approving independent verifier. B2 source-only rendering and deterministic citations remain; B3 Linux locale/recovery regressions continue to pass. No existing assertion was removed or weakened.

Final Python: **872 passed, 0 failed, 1 skipped**. Browser: **21 passed in excerpt mode**. New main/unseen matrices: **444 + 96 passed**, with **0/342 false acceptances** and **0/198 false refusals** under controlled responses. Existing matrix: 156 passed separately. Unicode/recovery: 6 passed, included in full totals. Arabic OCR skips because the Arabic Tesseract language pack is missing.

Live `qwen2.5:3b` is **UNVERIFIED**, connection refused; no actual digest or live answer/report was measured. Same underlying model weights remain a correlated-error risk. Deterministic parsers have bounded coverage and do not prove arbitrary semantic entailment. Real Windows, physical Android and trusted HTTPS/PWA remain **UNVERIFIED**. Clean build/release packaging is not certified.

See `B1_RELEVANCE_REMEDIATION_REPORT.md`, `docs/b1-engineering/results-summary.json`, final raw logs/matrices and `docs/b1-engineering/EXTERNAL_VALIDATION.md`. Copies of both prior reports are retained in that evidence directory; prior evidence directories and history are unchanged. The post-commit handoff records the new SHA and source-bundle checksum. The bundle is an engineering handoff, not an installable release candidate.

Next: independent engineering review and actual pinned-model evaluation with manual cited-page review, followed by the outstanding external platform/reproducible-build gates. No production GO is self-issued.

---

# LocalPDF Insight — release remediation stopped at an open blocker

**Status: BLOCKED. No release-candidate ZIP and no production GO.**
Starting commit: `4ab12f918c90779a0d566affbb720fbc0ce30fb8`; starting status clean.
The new commit is supplied with the handoff bundle and its checksum. The repository
retains all prior history, all 12 original test files and prior release evidence.

## Baseline and root causes

The authoritative ZIP SHA-256 is
`b6f104b73d002f74a6fefd8b1fbb25c467db20f2a1be48533b7741cf3a7ece9c`.
All 357 tracked files matched the ZIP. The Git bundle restored the exact requested
commit. The gatekeeper report was read and copied unchanged into the baseline evidence.

| Blocker | Reproduced cause | Remediation and disposition |
|---|---|---|
| B1: strict relevance | `validated_claims` received no question and accepted an exact historical-profit quotation for a missing 2030 forecast. | Added complete-question semantic review, source-ID resolution, explicit-period constraints, partial/conflict handling and source-only rendering. The original example is now refused. **NOT RESOLVED:** a controlled compromised review marks all checks true and admits net profit for a same-year operating-profit question. Boolean attestations from the model are not semantic proof. The failing regression is retained without skip/xfail. |
| B2: citation laundering | Assisted candidates with any valid retrieved ID bypassed textual support checks, so an invented AED 999 million forecast reached the API. | The release boundary now copies complete server-owned source units and never releases candidate prose. This retains negations/qualifications and prevents new model-written amounts, dates, entities, comparisons or obligations from being laundered through valid IDs. Forty adversarial injection cases passed across Q&A/report operations. Assisted paraphrases fall back to extracts. Old saved unvalidated AI answers are withheld on read while original SQLite snapshots remain intact. **Mechanical defect addressed; live behavior unverified and B1 still prevents release.** |
| B3: Unicode restart | `web.py` wrote UTF-8 but read using the locale; migration also used implicit codecs. Actual C-locale restart raised `UnicodeDecodeError`. | Added explicit UTF-8 JSON IO, atomic/fsynced writes, byte-preserving recovery on invalid metadata, explicit legacy conversion, UTF-8 CLI/PowerShell diagnostics. Original restart reproduction now passes. Six Unicode/recovery tests passed, including genuine ASCII-locale subprocesses and a labelled cp1252 simulation. **Observed Linux defect fixed; clean Windows and arbitrary non-UTF-8 filesystem paths remain unverified.** |

The B1 counterexample is a stronger test than the original 2030 case. It deliberately
compromises generation **and** semantic review. The returned claim is an authentic
source quotation but does not answer the requested financial metric. It demonstrates
why the passing oracle-controlled matrix cannot establish semantic reliability.
Do not repair this by special-casing operating/net profit or refusing every question.

## Verification actually performed

| Check | Result |
|---|---|
| Original Python baseline | 81 passed, 1 skipped. |
| Original browser baseline | Reader 13 + Studio 8 passed using unchanged `4ab12f9` worktree and Chromium 153.0.8010.0. Excerpt mode, not live AI. |
| Three original reproductions | Both unsafe answers admitted; Arabic import HTTP 200 followed by actual C-locale restart exit 1. Raw before/after evidence retained. |
| Final complete Python suite | **289 passed, 1 failed, 1 skipped** (291 collected). The failure is the retained open B1 counterexample. |
| Grounding tests | 203 cases: 202 passed, 1 failed. Includes 156-row English/Arabic × strict/assisted × current/selected/library matrix, schema/period checks, 40 material-claim injection cases and legacy-output protection. |
| Final browser suites | **21 passed**: reader 13 and Studio 8. Real headless Chromium; excerpt mode. |
| Unicode/recovery | 6 passed. Three configurations each exercised 10 separate subprocess lifecycle steps: import/index, two restarts, rename, migration, backup, same-path restore, relocated restore and repeated reopening with source/Studio checks. Genuine C locale had UTF-8 mode disabled. cp1252 was simulated, not Windows. |
| Actual release Ollama | **UNVERIFIED**. Loopback API connection refused; no installed runtime/model digest measured and zero live answers reviewed. No controlled response was counted as live evidence. |
| Arabic OCR | **Skipped**: `ara.traineddata` missing. Attempt to obtain the official Tesseract fast 4.1.0 pack timed out. Existing test/assertions were not changed. |
| Clean install/build/fresh release extraction | **Not performed after the stop condition.** A version lock and commands were prepared, but no reproducible-build claim or new RC artifact is made. |
| Windows / physical Android / trusted HTTPS PWA | **UNVERIFIED**; required hardware/runtime unavailable. Scripts, non-sensitive PDFs and checklist supplied. |

The first cached Chromium executable was truncated; browser launch failed before any
workflow ran. A Chromium 143 diagnostic attempt also failed because bundled PDF.js
uses `Map.getOrInsertComputed`. Fresh Chromium 153 restored the original 21 passes.
All failed infrastructure/test logs remain alongside the successful ones. No browser
assertion or production PDF.js asset was changed to make these runs pass.

The matrix checks each emitted citation through the server for matching document,
page, exact passage and readable PDF. The browser suites separately exercise actual
source clicks. This is not a claim that all 156 rows were manually clicked or that
any live answer/report was manually verified. Arabic matrix PDFs use standard
ActualText matching their visible synthetic text; they do not certify arbitrary
Arabic font extraction, scans or OCR. The retained historical corpus is still needed.

## Changes and bounded findings

Application changes: `src/localpdf_insight/{evidence,grounding,metadata,web,migrate}.py`
and two reader help strings in `static/app.js`. PDF.js, SQLite schema, local-only
Ollama transport, scope identities, document IDs and deterministic citation metadata
remain in place. No cloud service, autonomous agent or new product feature was added.

Validation: `tests/{grounding_support,test_grounding_remediation,test_unicode_remediation}.py`;
`scripts/validation/{reproduce_release_blockers,locale_roundtrip,live_grounding}.py`;
Windows gate script; `docs/release-remediation/` raw JSON/JSONL, JUnit, logs and PDFs.
All original tests are unchanged. Documentation: README, PROJECT_STATE,
`docs/REMEDIATION_OPERATIONS.md`, this report and `requirements-validation.lock`.
Windows setup now uses the captured constraints; diagnostics explicitly use UTF-8.

- **Release blocker:** B1 remains an observed failure. The attempted semantic review
  is not a protected or validated semantic trust boundary. Promotion stopped.
- **High:** live release-model reliability/latency, clean Windows, physical Android,
  trusted HTTPS/PWA and Arabic OCR remain open. Source-only fallback withholds free-form
  interpretations/translations; their quality is not claimed.
- **Medium:** M1 relocation is fixed in local tests: only matching PDF digests permit
  path rebasing; old metadata is preserved, IDs/Studio/citations remain stable, and
  missing/changed snapshots cannot fall back to old external paths. Real-device
  recovery is unverified. Dependency versions are captured but clean-install/build
  reproducibility is unverified. Larger-document performance, comparison alignment,
  sampled report coverage and a complete version rollback drill remain limitations.
- **Low:** no additional Low finding established. No fresh vulnerability audit or
  penetration test was performed.

## Exact reproduction and verification commands

Run in the repository with the recorded Python environment. Installation and external
steps are documented in `docs/REMEDIATION_OPERATIONS.md`.

```bash
# On the untouched starting worktree, reproduces all three original blockers:
.venv/bin/python scripts/validation/reproduce_release_blockers.py before.json
# Same script on remediation code captures the changed original cases:
.venv/bin/python scripts/validation/reproduce_release_blockers.py after.json

# Complete final suite; expected to FAIL on the retained B1 regression:
LOCALPDF_OPEN_BLOCKER=open-b1.json .venv/bin/python -m pytest -ra --junitxml=python.xml
# Focused blocker:
.venv/bin/python -m pytest -ra tests/test_grounding_remediation.py::test_same_period_wrong_metric_must_not_pass_a_compromised_review
# Focused Unicode and recovery:
.venv/bin/python -m pytest -ra tests/test_unicode_remediation.py
# Controlled matrix record:
LOCALPDF_GROUNDING_MATRIX=matrix.jsonl .venv/bin/python -m pytest -ra tests/test_grounding_remediation.py

LOCALPDF_TEST_PYTHON="$PWD/.venv/bin/python" CHROMIUM_EXECUTABLE=/absolute/path/to/chromium npm run test:browser
LOCALPDF_TEST_PYTHON="$PWD/.venv/bin/python" CHROMIUM_EXECUTABLE=/absolute/path/to/chromium npm run test:studio
# Actual release model only; exits 3 if unavailable:
.venv/bin/python scripts/validation/live_grounding.py --output live-model.json
```

The reproduction script is new in the remediation commit. To run against `4ab12f9`,
invoke this script by absolute path with `PYTHONPATH=/path/to/unchanged-worktree/src`;
do not imply it existed in the original commit. Baseline invocation used the unchanged
code before application edits. Original browser verification was repeated in a separate
unchanged worktree after repairing the browser runtime.

## Decision and next action

The required stop condition was reached. **No RC ZIP or RC checksum exists.**
The Git bundle is a blocked engineering handoff, not an installable release candidate.
It preserves the code, failing assertion, evidence and complete history for inspection.

Next: resolve B1 without treating model assertions as proof or rejecting legitimate
paraphrases indiscriminately. Then execute the named live model and manually review
question relevance, claims, conflicts, reports and selected-text actions against pages.
Only after blocker gates pass should clean-build/installation and external platform
verification advance to an RC and independent release re-review. This report does not
self-issue production approval.

## Continuation from 270b9ae — verification blocked, no application correction

The requested continuation reproduced the exact starting checkpoint with a clean
working tree and verified the supplied bundle/report hashes. All 418 tracked files
matched `270b9aef2821e362fe64c4e54b19fbb13caf7ea7` before documentation edits.

Fresh results: complete Python **289 passed, 1 failed, 1 skipped**; focused grounding
**202 passed, 1 failed**, including 156 passing controlled matrix rows; browser
**21 passed** in excerpt mode with Chromium 153.0.8010.0; Unicode/recovery **6 passed**.
The unchanged failure still releases net profit for an operating-profit question
after a compromised review marks every check true. The source release boundary
still trusts model-issued semantic authorization from the same generator callable.

The actual release-model harness again returned **UNVERIFIED: connection refused**.
No installed Ollama executable or model was found in the checked locations, and no
actual model digest or live answer/report was obtained. Arabic OCR still skips for
missing `ara.traineddata`. Windows, physical Android, and trusted HTTPS/PWA remain
unverified. The expanded independent-verifier/metamorphic matrix was not completed.

No relevance correction was established in this pass. Under the user's stop
conditions, application edits and release packaging stopped. This is an evidence
and documentation checkpoint only; production code, tests, and validation scripts
are unchanged. No new RC ZIP or production approval is issued.

See `B1_RELEVANCE_REMEDIATION_REPORT.md` for the exact call-path analysis, commands,
results and limitations; `docs/b1-remediation/` contains fresh raw evidence and the
external validation checklist. Prior release evidence is retained unchanged.

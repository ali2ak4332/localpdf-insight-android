# Remediation validation and operations

Status: remediation worktree, **not a release candidate or production-approved build**.
The independent gatekeeper must review the new commit. Historical evidence is retained.
The B1 interface/span corrections have passing regression coverage: 1,196 Python
passes and one disclosed Arabic OCR skip, plus 21 excerpt-mode browser workflows.
A separate semantic stress diagnostic still has 12 false acceptances; **B1 semantic
reliability is not established**. See `B1_INDEPENDENT_VALIDATION_REPORT.md` and
`docs/b1-independent/EXTERNAL_VALIDATION.md`. Live and actual platform gates remain
incomplete. A clean dependency attempt cannot resolve the locked PyMuPDF version;
reusing installed dependencies is not proof of clean installation.

## Reproduce the environment

Tested: Linux x86-64, Python 3.12, Chromium 153.0.8010.0 (record the executable's actual
`--version`), Playwright 1.62.1. Python 3.11–3.13 remains the declared compatibility
range, not a claim that each version/platform passed. Chromium 143 failed to open
bundled PDF.js 5.6.205 because `Map.getOrInsertComputed` is unavailable. Use the
verified current browser build; other browsers remain unverified.

Create a clean Python 3.12 virtual environment. Install with:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -c requirements-validation.lock -e '.[web,test,desktop]'
.venv/bin/python -m pytest -ra
npm ci
# Install/provide Chromium 153 and record its exact version.
LOCALPDF_TEST_PYTHON="$PWD/.venv/bin/python" CHROMIUM_EXECUTABLE=/absolute/path/to/chromium npm run test:browser
LOCALPDF_TEST_PYTHON="$PWD/.venv/bin/python" CHROMIUM_EXECUTABLE=/absolute/path/to/chromium npm run test:studio
```

The lock records tested dependency versions, including test/desktop dependencies;
it is not a verified Windows lock or a current vulnerability audit. Existing browser
suites explicitly use excerpt mode and do not clear live AI gates. Never remove
failures or skips from the saved logs. Arabic OCR needs `ara.traineddata`, with its
source and SHA-256 recorded, plus English data. The acquisition attempt and exact
skip reason are retained in this remediation evidence.

## Release-model gate

The gate target remains `qwen2.5:3b`, digest
`357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b`,
from the historical release record. **Its current runtime is unavailable here.**
No Ollama runtime version can be certified by this pass. Start an actual local
Ollama service, install/verify this model digest, then run:

```bash
LOCALPDF_VERIFY_MODEL=qwen2.5:3b .venv/bin/python scripts/validation/live_grounding.py --suite boundary --output external-results/live-model.json
```

The harness refuses missing/mismatched models and never substitutes excerpts or
controlled replies. It captures runtime/digest, parameters, fixture, question,
answer, citations and automated status. The model runs at temperature 0.1 with JSON
output and a 1,024-token output cap per generation call. Verification uses a distinct
loopback `/api/chat` interface, temperature 0, a 2,048-token cap and a 30-second timeout.
It receives the original question and server-owned passages without candidate prose.
`LOCALPDF_VERIFY_MODEL` defaults to `LOCALPDF_MODEL`; the same model weights create
correlated-error risk, not model independence. Both must use the pinned model for
this release gate. Failed verification withholds generated answers. Latency and
semantic false-refusal rates are unverified. `--case` is diagnostic, not a full gate.

Manually compare **each claim and each reported conflict/omission** with the fixture
pages and question; record reviewer identity, time and pass/fail. Click citations
in the real browser. Also run the retained `tests/manual/live_validation.cjs`
workflow on its documented native/scanned/table/bilingual corpus, including selected
text actions and generated reports. The new small matrix does not replace that
representative corpus. A completed automated run remains PENDING_MANUAL_PAGE_REVIEW.

Both modes retain their API identities. Until paraphrase support can be certified,
assisted mode releases server-approved source spans instead of model-written factual
prose. Explicit attached qualifications are retained; a detected qualification crossing
a native layout block causes that incomplete witness to be withheld. General semantic
relationships and implicit/cross-page qualifications remain unverified. Interpretations/translations may be withheld. Strict mode still requires
exact candidate spans. A separate semantic adjudication assesses question coverage;
its judgments are **not** proven correct by a valid JSON schema or controlled tests.
The renderer prevents novel model-written amounts/obligations reaching the user;
source correctness, extraction accuracy and semantic relevance remain separate concerns.

## Windows, Android and trusted HTTPS

Use a real clean Windows host/VM, not Wine or code-page simulation:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\validation\windows_gate.ps1 -RunLive
```

Review the recorded actual code page and `utf8_mode=0`. Repeat startup from a path
containing Arabic and spaces, file import/rename/migration, two shutdown/restarts,
backup/restore and source clicks. The C-locale automated lifecycle uses an ASCII
storage path with Arabic metadata/filenames; it does not certify arbitrary
non-UTF-8 POSIX filesystem paths or a Windows installation.

The supplied `docs/release-remediation/fixtures` PDFs contain invented, non-sensitive
facts. For a **physical Android** phone, record device/Android/Chrome versions and
perform import, search, question/refusal, source click after switching PDFs, Studio
reopen, rotation and host disconnect/reconnect. Use the fuller retained checklist in
`docs/validation-release/EXTERNAL_CHECKLIST.md` for larger documents and offline cases.

For **HTTPS/PWA**, configure your local trusted TLS reverse proxy, an actual valid
certificate trusted by the phone, `LOCALPDF_HOSTS` with the exact hostname,
`LOCALPDF_TOKEN` and `LOCALPDF_HTTPS=1`. Never place the token in evidence files.
Record secure-context/service-worker status, actual install prompt and standalone
launch on the physical device. Localhost service-worker tests do not prove this gate.

## Storage, backup, migration and rollback

`LOCALPDF_DATA` selects the web data directory. Otherwise it is `APP_HOME/web`
under the existing platform-specific LocalPDF directory (`core.APP_HOME`). Keep
PDFs, `library.json`, SQLite evidence, any WAL files and recovery copies together.
Stop the application before copying the **entire** directory. Keep code commit,
dependency lock, model digest and backup as one recovery set. Do not copy an active
SQLite database and assume the backup is consistent.

Same-path restore: stop the server, preserve the failed directory, restore the
backup in full, start the matching code and check PDFs, Studio and citations.
Relocated restore: start against the copied directory. Paths are rebased only if
the managed PDF hash matches its recorded revision. IDs, notes and source snapshots
stay stable; the old metadata is retained in a `before-rebase` file. Missing/changed
PDFs fail closed; the old absolute path is never used as a fallback.

Desktop migration remains `python -m localpdf_insight.web --migrate-desktop`. It uses
explicit UTF-8 metadata, preserves IDs and copies originals. Reindex after migration.
Invalid UTF-8/JSON metadata produces an actionable error and a byte-exact recovery
copy rather than an empty replacement library. For a known legacy encoding only,
stop the app and explicitly invoke `localpdf_insight.metadata.convert_legacy(path,
encoding)`; it validates JSON and preserves the original. Never guess the codec.

Rollback: stop the new code, retain its data, restore the **matching pre-change
backup** into a separate directory and run the recorded prior code/dependencies.
Do not point old code at newly changed data and assume rollback compatibility.
The previous unsafe AI release must not be represented as an approved fallback.

## Logs and limitations

Keep stdout/stderr, pytest JUnit files, browser logs, JSON matrices and fixture hashes.
Web CLI streams and metadata are explicit UTF-8; PowerShell diagnostic file IO is
explicit UTF-8. Diagnostics may contain document text—use these synthetic fixtures.
Old saved generated answers without version-2 grounding metadata are withheld on API reads;
their original SQLite snapshots are retained, and source links/notes remain available.

Unverified: live semantic reliability and latency, clean Windows, physical Android,
trusted-HTTPS installation, complete Arabic OCR gate, free-form paraphrase/translation
quality, larger workload performance, dependency vulnerability status, and a full
code/dependency/data rollback drill. Comparison and reports retain their disclosed
alignment/sampling limitations. These are not removed by passing unit tests.

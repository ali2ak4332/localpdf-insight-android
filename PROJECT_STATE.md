# Android page-jump checkpoint — 2026-10-15

Version `0.2.1-page-jump` (code 3) adds one Android-only improvement: Enter/Go in the page-number field jumps to the requested page and releases keyboard focus. It continues from the signing checkpoint below. See `ANDROID_CHANGELOG.md` for commits, focused reproduction, executed tests and limitations. Physical Android keyboard behavior remains unverified.

---

# Android editing checkpoint — 2026-10-14

Version `0.2.0-editor` extends the existing Android reader with PDF.js Ink signing, highlighting, Arabic/English text stamps, supported AcroForm editing and SAF export of a new PDF copy. Imported originals and note/source identities are preserved. On-device storage, no Internet permission and no Ollama/server dependency remain. Editing is annotation/form editing, not page-text replacement or certificate signing. Validation is in `docs/android-editing-validation/README.md`; physical Android remains unverified. Historical desktop AI release blockers below are unchanged.

---

# Android reader checkpoint — 2026-10-14 (historical)

A personal Android reader now wraps the existing PDF.js interface with on-device PDF/index/note storage. It has no Ollama, Python server, AI or OCR dependency. See `android/README.md` and `docs/android-validation/README.md` for installation, builds and evidence. Signed APK and offline mobile browser tests passed; physical Android remains unverified. The desktop/web AI release gate below is unchanged.

---

# Current engineering checkpoint — 2026-09-18

Continuation from `6c3821bfea2c10657f198c40a9136bc167c1d8dd`. B1 now has a separate verifier transport and deterministic contradiction vetoes. The unchanged counterexample also passes with a separate lying verifier, recording `metric_mismatch`. Full suite: 872 passed, 1 Arabic OCR skip; browser: 21 excerpt workflows. Controlled matrix: 540 new cases with zero observed false acceptances/refusals; this is not live semantic validation.

**Release remains blocked. No RC ZIP or production GO.** Live pinned Ollama, real Windows, physical Android, trusted HTTPS/PWA, Arabic OCR and reproducible clean release build remain unverified. Read the current `B1_RELEVANCE_REMEDIATION_REPORT.md` and `docs/b1-engineering/EXTERNAL_VALIDATION.md`. The older checkpoints below are historical.

---

# Current remediation checkpoint — 2026-09-17

Starting commit: `4ab12f918c90779a0d566affbb720fbc0ce30fb8`.
**BLOCKED. No release-candidate ZIP and no production approval.**

Read `RELEASE_REMEDIATION_REPORT.md` and `docs/REMEDIATION_OPERATIONS.md` first.
B1 remains demonstrably OPEN: a compromised semantic review admits net profit for an operating-profit question in the same year. Its permanent regression test intentionally retains the failing assertion. The new controls and regression matrix are engineering evidence. Actual release Ollama
is unavailable; semantic relevance/reliability is not certified. Windows, physical
Android and trusted HTTPS/PWA installation remain unverified. Prior tests and evidence
are unchanged. Source-only output deliberately withholds unverified interpretations.

The earlier state below is retained as history; current gate decisions supersede it.

---

# LocalPDF Insight — current state

Version: 0.2.0. Primary target: browser reader, with local Python OCR/index/AI service.

Authoritative code: this Git repository. No external PDF-reader repository was found/configured. The original repaired desktop project was preserved in the root commit along with the bundled PDF.js assets available at audit time.

Keep: PyMuPDF, local-only Ollama transport, spawned PDF processing, desktop compatibility.
New: `document.py`, `evidence.py`, `web.py`, `migrate.py`, bundled `static/` reader.

Read `docs/AUDIT.md` for the initial Keep/Fix/Replace/Missing assessment. Read `docs/validation-release/REPORT.md` for the current live validation results and release blockers; `docs/VALIDATION.md` retains the earlier foundation record. Do not infer full semantic reliability from citation-ID validation.

Release gate: **FIX BEFORE USE** as a trustworthy AI reader. Live tests found irrelevant exact excerpts in strict mode, unsupported assisted wording, and Arabic extraction/OCR errors. Citation mapping passed. The validation-only changes fix import worker starvation, local-model JSON/span handling, and spurious comparison alignment. No new product features were added. Windows, physical Android and trusted-HTTPS installation remain unverified.

No internet-research, agents, workflow automation, external-provider upload, generic chatbot, collaboration or document-generation features were introduced.

Current convenience extension: source-derived suggestions, shared briefing/study templates, selected-text actions, append-only Studio snapshots and source-linked personal notes, with Sources / Chat / Studio navigation. See `docs/convenience-validation/README.md` for tests and limits. The underlying strict/assisted evidence rules are unchanged. No live-model quality validation was rerun in this pass.

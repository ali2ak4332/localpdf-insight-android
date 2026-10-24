# Cited-line rerun — preregistration and progress

This is a test-only branch based on `b450876df564148913c2f3183063daa64946febd`.
The independent support-filter patch is deliberately not applied. No Android,
model, APK, package identity, data or release decision change is part of this work.

## Preregistered comparison (before any inference)

Compare both Qwen3.5 Q4_K_M models against the frozen five-task baseline, using
counts per model: strict passes; content passes; fully aligned figure records;
unit-correct and period-correct figure records; correct abstentions; rejected
citations. The baseline counts are respectively 0/120 and 2/120 strict passes,
26/120 and 40/120 content passes, 0/58 and 11/60 fully aligned figures,
10/58 and 19/60 correct units, 4/58 and 29/60 correct periods, and 0/14 correct
abstentions for each model. Rejections are reported separately, not labeled
hallucinations and not silently counted as correct abstentions.

Expected direction: exact quotes should increase strict passes toward content
passes; code-derived figure fields should improve alignment when table detection
works. These are hypotheses, not measured results or upper bounds: numbered-line
prompts and code-selected metrics may also change content accuracy. If content
remains near 22–33%, copying citations has not resolved the model-quality limit.

## Audit before freezing

Reused the exact original 30-PDF extracted-text corpus and frozen gold from the
previous workspace; no source host download or replacement corpus was needed.
The pre-patch real-corpus audit found split date headers in Apple statements,
per-share amounts incorrectly scaled in Berkshire tables, table columns leaking
into later prose, wrapped inception/return headers in Vanguard and iShares,
missing percent/row scale metadata, false numeric references, first cells lost
after dotted leaders, and ambiguous repeated values resolved to the first cell.

Added regression tests before fixes. Header metadata is reconstructed separately
from evidence: the numbered lines and quotations remain the original PDF text.
Table matching requires cell-shaped rows and the current header; per-share and
share-count exceptions retain their source scale; duplicate value matches are
rejected. Ten new regressions cover these faults, including preserving wrapped
sentence-initial durations after excluding clause numbers.

Known remaining audit limits: Apple's six-column GAAP/non-GAAP reconciliation,
ETF non-date comparison headers and infographic layouts are not fully reconstructed.
Some prose figures have missing units or periods, and identifiers can remain
candidates. Missing fields are not completed by the grader. Page-level factsheet
dates and duration-only return columns are heuristic metadata; a copied value
is not sufficient to pass complete-record grading. No claim of an exhaustive
extractor-accuracy audit is made.

The final hashes and prompt-fit check will be recorded before inference. After
the first model generation, the extractor and cite harness are frozen.

## Frozen preflight

- 0.8b: 111 prompts checked; maximum 5823 tokens + 512 output tokens fits the 8,192 context. No generation calls used.
- 2b: 111 prompts checked; maximum 5823 tokens + 512 output tokens fits the 8,192 context. No generation calls used.

Frozen module SHA-256:

- `apt_lines.mjs`: `e865b4d7814ec60c8ba3e021fa97bf0949a6d3d3ffffbcaa75447996a3fd8702`
- `apt_figures.mjs`: `80f6fef65833aed841fb17ee2a4ca02a8fbc7841660d546e801cb5822775230c`
- `five_task_cite.mjs`: `8e7517b1b39cecc594163f46c931ce8e4ced83a18256c93d080cb9dcea383723`

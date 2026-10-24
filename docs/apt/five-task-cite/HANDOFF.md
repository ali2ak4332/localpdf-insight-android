# Cited-line rerun of the five-task evaluation — handoff (24 October 2026)

Branch `apt-cite-eval`, based on `apt-reader` at `b450876`. Test-harness and pure
modules only: no Android code, model, APK or release decision changes. Prepared by
Claude (Anthropic). Read `../five-task/REPORT.md` first.

## 1. Why

In the five-task run the model typed its own quotes, numbers, units, periods and page
numbers. Recomputed from `../five-task/results.json`:

| | 0.8B | 2B |
| --- | --- | --- |
| Content pass (claims judged correct) | 26/120 | 40/120 |
| Strict pass | 0/120 | 2/120 |
| Literal quotes in content-pass cases that failed strict | 3 of 49 (26 cases) | 4 of 76 (38 cases) |
| Figure records: value / unit / period correct | 24 / 10 / 4 of 58 | 35 / 19 / 29 of 60 |
| Correct abstentions (gold expects none) | 0/14 | 0/14 |

Almost the whole strict-pass gap is quotation copying, and figure failures concentrate in
fields the model wrote. The Android app already avoids both: its model selects source
IDs and code copies text. This rerun tests that design on the same 30 PDFs.

## 2. Protocol `cite-v1`: what changes and what does not

Unchanged from `five_task_eval.py`: corpus, whole-document input, server flags (context
8192, `--cache-ram 0`, no context shift, Jinja, thinking off), greedy/seed 0, 512 output
tokens, at most 2 findings, task instructions (figures instruction shortened, see below).

Changed:

| Task | Model writes | Code copies from the PDF text |
| --- | --- | --- |
| Summarize, Insights | `claim`, `from`, `to` (line numbers) | `quote` = exact page text of lines from..to (one page, ≤4 lines), `page` |
| Risks | `obligation`, `party`, `deadline`, `exception`, `from`, `to` | `quote`, `page` |
| Key Figures | `line`, `value` (must occur as a figure on that line), `metric`, `entity` | `value` exactly as printed, `unit` (currency + scale note + unit word), `period` (table column, else a single date in the line, else a single page-heading date for money/percent), table row label as `metric`, `quote`, `page` |

The prompt shows numbered lines (`[PAGE n]`, `[id] text`, the app's own line units) and,
for figures, the table columns code detected. A document with no numeric line gets **no
figures request** and an empty result (`deterministicSkip`). Findings that cite a missing
or invalid range, or a value not on the cited line, are dropped and recorded in
`materializationRejected`.

Rows keep the true model output in `rawContent`/`parsedContent` and the code-built
findings, in the **original five-task fields**, in `materialized`, so the same rubric,
blind review, verifier and aggregator apply.

## 3. Files

| File | Purpose |
| --- | --- |
| `src/.../static/apt_lines.mjs` (new) | Line units from page text, prompt rendering, exact span evidence. Pure, app-reusable |
| `src/.../static/apt_figures.mjs` (new) | Deterministic figure candidates: numbers with sign/parentheses, currency, scale suffixes and page scale notes (incl. share-count and per-share exceptions), unit words, table column periods (two-level span + date/year/duration headers, placeholder dashes), row labels with group prefixes; skips dates, clause numbers, references, page numbers, phones, index names, legal citations, blanks; forward-looking/preliminary/untested flags |
| `tests/apt/five_task_cite.mjs` (new) | Prompts, schemas, materialization; CLI `prepare`, `materialize`, `candidates` |
| `tests/apt/five_task_cite_eval.py` (new) | Runner; same server handling as `five_task_eval.py`; records rendered prompt token counts |
| `five_task_summarize.py`, `five_task_blind.py`, `five_task_verify.mjs` | Cite-aware: findings come from `materialized`; deterministic figure abstentions validated; every code-built quote must be on its cited page. Legacy reports behave as before |
| Tests (new) | `figures.test.mjs` (16), `test_five_task_cite_summarize.py` (6), `five_task_cite_harness_test.py`, `figures_pdf_check.py` |

## 4. Verified here, and what was not

| Check | Result |
| --- | --- |
| `node --test tests/apt/*.test.mjs` | 35 passed (19 existing + 16 new) |
| Mutation check of figure tests | Each of 7 deliberate extractor breakages fails 1–3 tests |
| `pytest tests/test_five_task_summarize.py tests/test_five_task_cite_summarize.py` | 22 passed (16 existing + 6 new; tamper cases assert their specific error) |
| `five_task_cite_harness_test.py` (fake server) | Skip, materialization, rejections and quotes correct |
| `figures_pdf_check.py` | 51 checks on 8 synthetic PDFs extracted by the app's PDF.js pipeline (statements, earnings release, fund/ETF sheets, fact sheet, contract, infographic, regulation sheet) |
| `panel.cjs`, `android.cjs` | 7 and 21 passed (app unchanged) |

**Not run:** any model; the real 30 PDFs (their hosts were unreachable from this
environment), so the extractor has **not** been audited on the actual corpus.

## 5. Steps, in order

1. Apply the patch on a branch from `apt-reader` and run the commands in section 4
   (`CHROMIUM_EXECUTABLE` for the PDF and browser checks).
2. **Audit the extractor on the real corpus before any model run.** Build
   `[{"doc": {id, title, pages}}]` from `corpus.json`, then
   `node tests/apt/five_task_cite.mjs candidates < docs.json > candidates.json`. Check the
   tables in the Apple, Berkshire, Vanguard and iShares PDFs and the infographics: row
   label, value, unit, period. Fix problems with a regression test each, then record
   `productionModulesSha256` from a `--prepare-only` run as frozen. Do not change the
   extractor after the first model run.
3. Make a separate work directory (for example `work-cite/`) with copies of the frozen
   `corpus.json` and `gold-frozen.json`. Run `--prepare-only` and confirm prompts fit:
   the largest legacy prompt was 4,118 tokens; line numbers add some.
4. Run both models, writing `work-cite/qwen35-2b.json` and `work-cite/qwen35-0.8b.json`:
   `python3 tests/apt/five_task_cite_eval.py SERVER work-cite/corpus.json META.json work-cite/qwen35-2b.json`
5. Fifth function: run `five_task_verify.mjs` as in the five-task protocol into
   `work-cite/verify-findings.json`, then its `--models-only` recheck with both cite
   reports (it now checks `materialized`).
6. Blind review with `five_task_blind.py work-cite`, same rubric and grade format.
   Graders judge `materialized` findings against the source; `materializationRejected`
   items were never shown, so report them separately rather than as hallucinations.
7. Aggregate: `python3 tests/apt/five_task_summarize.py --workdir work-cite --outputdir docs/apt/five-task-cite`.

## 6. Pre-registered comparison (write into the report before step 4)

Compare per model with the five-task results, as counts: strict pass, content pass,
figure records fully aligned and unit/period correct, correct abstentions, rejected
citations. Expected if the diagnosis is right: strict pass rises toward content pass
(at most 26 and 40, minus cited lines that do not support the claim), and figure
unit/period alignment rises wherever a table was detected. If strict rises but content
stays near 22–33%, the remaining limit is model quality: consider extractive-only
summaries/insights in the UI, the support filter from the earlier patch, or fine-tuning.

## 7. Known limits

- English heuristics; tables are line based (a row maps to columns only when its cell
  count equals the header's); text extraction can still lose layout.
- Dates are periods, never figure values, by design.
- Multi-line quotes contain `\n`; they are exact page substrings (the page-level verifier
  accepts them). In the app, each cited line would be its own source citation.
- The model still writes claims, obligation fields, entity and prose metrics; those can
  still be wrong. A copied quote proves presence, not support.
- The app uses a 4,096-token context; adopting this protocol in Android means applying it
  per section. `apt_lines.mjs` and `apt_figures.mjs` are pure and ready for that.

The earlier support-filter patch is independent; it applies before or after this one.

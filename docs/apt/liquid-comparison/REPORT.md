# Liquid model comparison — 24 October 2026

**Both Liquid models were downloaded, checksum-verified and tested locally.
Neither passes the existing Apt Reader selection task.** LFM2.5 is the more
promising next candidate because it finds more relevant passages and completes
all requests, but false positives remain frequent. No model was integrated into
the Android app, fine-tuned further, or approved for APK delivery in this test.

## Same-task results

All three models were run on the same 32 synthetic cases used for the previous
Gemma diagnostic: four tasks, eight variants/target positions each. These include
repeated templates/content, not 32 independent PDFs. The independent Verify
Findings function is model-free and is covered by the 19 existing regression
tests, which still pass.

**Screening score = exact correct selections / 32 × 10.** This is an objective
score for the app's existing source-index selection protocol, not a general model
rating or release-readiness score. Errors and abstentions count as unsuccessful.

| Model/artifact | Exact cases | Screening score | Relevant-passage recall | Accepted-passage precision | Valid JSON arrays |
| --- | ---: | ---: | ---: | ---: | ---: |
| LFM2-350M-Extract Q4_K_M | 4/32 | **1.25/10** | 12.5% | 66.7% | 22/32 |
| LFM2.5-350M Q4_K_M | 4/32 | **1.25/10** | 68.75% | 38.6% | 32/32 |
| Gemma 3 270M IT QAT Q4_0, fresh rerun | 0/32 | **0/10** | 12.5% | 25.0% | 4/32 |

Recall asks whether the target passage was found. Precision is measured among
accepted in-range deduplicated passages; rejected indices are recorded separately
and are not in that precision denominator. Exact selection requires precisely
the expected raw array, without extra/invalid/duplicate indices. Selecting every
passage therefore cannot earn a high exact score.

Extract produced 10 incomplete responses and many empty arrays. LFM2.5 completed
all requests but frequently selected extra or wrong passages. Gemma produced 28
incomplete responses. All accepted extracts were copied exactly from existing
sources/pages; no invented source/page was released in these cases. That is
evidence-boundary behavior, **not model numerical accuracy or citation relevance**.

| Task | Extract exact | LFM2.5 exact | Gemma exact |
| --- | ---: | ---: | ---: |
| Extract Key Figures | 0/8 | 0/8 | 0/8 |
| Identify Risks & Obligations | 0/8 | 2/8 | 0/8 |
| Extract Insights | 2/8 | 2/8 | 0/8 |
| Summarize (passage selection) | 2/8 | 0/8 | 0/8 |

## Size, speed and memory

| Artifact | Model bytes | Median request | p95 request | Peak native-process RAM |
| --- | ---: | ---: | ---: | ---: |
| Extract Q4_K_M | 229,310,080 | 420 ms | 2,371 ms | 482,611,200 bytes |
| LFM2.5 Q4_K_M | 229,312,224 | 436 ms | 565 ms | 476,520,448 bytes |
| Gemma Q4_0 | 241,410,624 | 3,883 ms | 4,335 ms | 510,541,824 bytes |

These are x86_64 host measurements on small synthetic prompts, not Android
document-level performance or installed footprint. Models ran sequentially to
avoid competing for CPU. Weights stay loaded across cases, but text/KV/recurrent
memory is cleared between requests. Median timing is mostly warm-model work;
first requests (881/688/4,335 ms respectively) include model initialization, but
the digest read warms filesystem cache, so these are not cold-disk tests. Peak
RAM uses fresh-process `getrusage` for each native child. RAM and model storage
are different quantities.

## Fairness and transport correction

Before running this comparison, review found that the old host test runner
printed raw model output as newline-delimited records even though the grammar
allows multiline JSON. This could split a response and corrupt its attribution.
The **test-only** runner now emits one JSON-escaped envelope per response with a
checked sequence ID, preserving complete raw output and errors. The framing
regression covers multiline arrays, empty arrays, escaped errors and sequence IDs.
The app's JNI interface did not use that defective host transport.

Gemma was rerun with both Liquid models under the corrected transport; historical
Gemma JSON files are retained but must not be used as the comparison reference.
All three reports have the same fixture/prompt SHA-256:

`d34a864de2220a1e33e3c07e7a61fa89a36f0c1542ea6ac6bec6032b6f4ce267`

The engine is unchanged: llama.cpp commit
`df9beac7153166550571c70cc667f270b745da49`, CPU up to 4 threads, context4096,
batch256/ubatch128, greedy sampling, production index-array grammar, 96-token
output limit, and each model's own embedded chat template. Liquid quantization
is Q4_K_M; Gemma is the existing QAT Q4_0 artifact. This compares deployable
4-bit artifacts, not identical quantization algorithms. No additional training
or per-model prompt tuning was performed.

A separate review found no apparent template/tokenizer mismatch for these
single-user prompts. Nevertheless, a specialized extraction model's native
JSON-object/schema task is different from selecting index arrays. These results
show poor **drop-in compatibility with our current adapter**, not that the Liquid
models are generally incapable of extraction or summarization.

## Provenance and reproducibility

- [LiquidAI/LFM2-350M-Extract-GGUF](https://huggingface.co/LiquidAI/LFM2-350M-Extract-GGUF),
  revision `b8f758b9ff37b0cad9bedfc5223cb71e31aebe9c`,
  SHA-256 `687a31c3e7864647aa181e1feb156e4e5da33978c174d7dbf0d289f6014a5621`.
- [LiquidAI/LFM2.5-350M-GGUF](https://huggingface.co/LiquidAI/LFM2.5-350M-GGUF),
  revision `657e078c94084481950a2d555a941481f715536b`,
  SHA-256 `7e6f72643caafc9a68256686638c4d7916f2cec76d1df478d4c3ddcd95a6aed4`.
- Gemma's pinned artifact/hash is retained in the existing validation report and
  fresh [gemma-rerun.scored.json](gemma-rerun.scored.json).

Per-case raw outputs, errors, timings, provenance and computed metrics:
[Extract](liquid-extract.scored.json), [LFM2.5](liquid-25.scored.json),
[Gemma](gemma-rerun.scored.json), [summary](summary.json).

To reproduce, build host target `apt-compare`, run
`python tests/apt/comparison_framing.py /path/to/apt-compare`, generate fixtures
with `node tests/apt/comparison_cases.mjs > /tmp/cases.json`, and run
`run_comparison.py BINARY CASES_JSON MODEL_META_JSON OUTPUT_JSON` once per model.
Metadata JSON contains `repo`, `revision`, `filename`, `bytes`, `sha256`,
`quantization` and local `path`. Then run `score_comparison.mjs` with the fixture
and output paths. Model files, local paths/toolchains and signing material are
not committed. The 30–50 representative-PDF benchmark, actual numerical accuracy,
phone validation, fine-tuning and final installed footprint remain uncompleted.

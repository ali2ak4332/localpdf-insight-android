# Hugging Face candidate evaluation — 24 October 2026

**Qwen3.5 0.8B is the preferred next development candidate found in this screening, when used
through its native Jinja chat template with thinking disabled and a finite answer
schema.** Its Q4_K_M weights are 532,517,120 bytes (533 MB decimal). The user has
relaxed the earlier 400 MB goal within reason. Model size remains a tradeoff to
measure alongside accuracy, memory and speed. Both it and the larger 2B model
scored 16/20 on the harder synthetic holdout; neither passed the unsupported-
evidence requirement. The larger model did not improve the overall result.

This is local CPU inference research, not an Android release validation. No new
model has been integrated into Apt Reader or approved for APK delivery. No
additional fine-tuning was performed.

## What was downloaded and tested

Connected Hugging Face discovery and primary model cards were used to shortlist
Granite 4.0 350M, SmolLM2 360M Instruct, Qwen2.5 0.5B Instruct and Qwen3.5 0.8B.
Public GGUF files were downloaded at pinned revisions and verified against Hub
LFS SHA-256 digests and byte sizes. Prior Gemma and Liquid artifacts were retained
for controls. Each saved result contains the exact artifact provenance.

| Model | Quantization | Model bytes | Existing adapter exact / 32 | Native-template diagnostic exact / 8 |
| --- | --- | ---: | ---: | ---: |
| Qwen3.5 0.8B | Q4_K_M | 532,517,120 | 2 | **8** |
| Qwen3.5 2B | Q4_K_M | 1,280,835,840 | Not run | **8** |
| Liquid LFM2.5 350M | Q4_K_M | 229,312,224 | 4 | 4 |
| Granite 4.0 350M | Q4_K_M | 236,986,144 | 0 | 2 |
| SmolLM2 360M Instruct | Q4_K_M | 270,590,880 | 0 | 2 |
| Qwen2.5 0.5B Instruct | Q4_0 | 352,972,352 | 0 | 2 |
| Liquid LFM2 350M Extract | Q4_K_M | 229,310,080 | 4 | 2 |
| Gemma 3 270M IT QAT | Q4_0 | 241,410,624 | 0 | 0 |

All eight models passed all four literal-output controls in the native-template
diagnostic. All 96 diagnostic requests completed with HTTP 200, valid parsed
content and a `stop` finish reason. All rendered prompts were captured.

The two columns are **different experiments**. They must not be combined into a
single score or interpreted as an isolated causal improvement from one setting.
Eight easy synthetic choices cannot establish reliable PDF analysis, numerical
accuracy, or a general 10/10 model rating.

## Why the adapter matters

The first experiment repeats the earlier 32 synthetic cases with the unchanged
production engine, prompt and index-array grammar. It evaluates drop-in
compatibility. The fixture repeats four content templates/target positions; it
is not 32 independent PDFs. The fixture also flattens production prompt newlines
to spaces. The four new artifacts in this experiment completed all 32 requests, but often selected
irrelevant extra passages or abstained.

Review found several limitations in this adapter:

- Its grammar permits unbounded whitespace/list length, duplicates, out-of-range
  indices and leading-zero number forms; the prompt asks for at most three.
- Generation stops after 96 tokens. Earlier Gemma/Extract token-limit errors discard
  partial generation, so those errors cannot be classified as semantic mistakes.
- `llama_chat_apply_template` is a heuristic formatter rather than a Jinja
  interpreter. For example, its ChatML path omits the default system instructions
  in the published SmolLM2 and Qwen2.5 templates. Qwen3.5's native non-thinking
  template also includes an empty thinking block before the answer.

The second experiment uses the same llama.cpp revision through its stock server, local files,
CPU threads (4), context (4096), batch (256) and ubatch (128), but changes the
prompt, cardinality, schema and template implementation together. It uses full
Jinja rendering, thinking disabled, greedy sampling, no prompt cache, and a JSON
object whose `choice` field is limited to 0–3. It tests cases
`[0,5,10,15,16,21,26,31]` plus four literal controls. Tasks and target positions
are each balanced, but are confounded: figures always has target 0, risks 1,
insights 2 and summarize 3. Content also repeats. No per-model tuning or
training was performed. This is a **composite compatibility diagnostic**.

The server binds only to loopback, uses `--offline`, loads verified local weights
and is terminated after each model. No remote inference was used. This proves
local host execution after setup; Android airplane-mode operation remains a
separate uncompleted check.

## Host performance

| Model | Existing-adapter median request | Existing-adapter peak child RAM | Native-diagnostic median selection request |
| --- | ---: | ---: | ---: |
| Qwen3.5 0.8B | 1,229 ms | 936,448,000 bytes | 1,096 ms |
| Liquid LFM2.5 350M | 436 ms | 476,520,448 bytes | 388 ms |
| Granite 4.0 350M | 429 ms | 545,579,008 bytes | 388 ms |
| SmolLM2 360M Instruct | 1,166 ms | 508,129,280 bytes | 769 ms |
| Qwen2.5 0.5B Instruct | 747 ms | 696,127,488 bytes | 646 ms |

These are x86_64 host measurements on short synthetic inputs. The existing
adapter uses the median convention in `score_comparison.mjs` (upper middle for
32 samples); the separate native diagnostic uses the conventional median of
eight selection requests. Model loading/template inspection are excluded from
the native request timing. Checksum reads warm filesystem cache. RAM comes from
a fresh native child in the existing-adapter experiment and is not an Android
RAM prediction. Model weights, RAM and complete installed footprint are distinct.

## Larger-model follow-up

Qwen3.5 2B Q4_K_M has 1,280,835,840 bytes of weights (1.281 GB decimal), with its
vision projector omitted for extracted PDF text, as for 0.8B. Both were tested
sequentially on a separate 20-case frozen holdout. Cases were authored by an
agent and their gold labels/abstentions independently checked by the primary
agent and another agent before either model ran. There was no human expert
annotation. The fixture covers financial metric/unit/period distinctions,
contractual exceptions and superseded drafts, technical limitations, qualified
summaries and missing evidence. Each task has one answer at every position 0–3
and one unsupported case, removing the earlier task/position confound.

Frozen fixture SHA-256:
`500101192f7819a50d08693a344182922bb79667bf77a47be2b964d635dd1fd2`.

| Holdout measure | Qwen3.5 0.8B Q4_K_M | Qwen3.5 2B Q4_K_M |
| --- | ---: | ---: |
| Exact choices, including abstentions | **16/20 (80%)** | **16/20 (80%)** |
| Supported cases selected correctly | 15/16 | 16/16 |
| Unsupported cases correctly rejected | **1/4** | **0/4** |
| Figures / risks / insights / summary | 5/5, 4/5, 4/5, 3/5 | 4/5, 4/5, 4/5, 4/5 |
| Median request (upper middle of 20) | 1,404 ms | 2,614 ms |
| p95 request | 1,959 ms | 3,231 ms |
| Peak stock-server child RAM | 2,043,953,152 bytes | 3,139,043,328 bytes |

All 40 requests completed with valid choice objects and `stop` finish reasons.
Models used identical native-template settings with a finite choice of
`[-1,0,1,2,3]`; `-1` denotes absent supporting evidence. Gold labels, case IDs and
gold explanations were kept out of model inputs. No prompt was adjusted or case
changed after inspecting these results. **A derived 8/10 exact-selection test
score would describe this particular holdout only, not overall model quality or
release readiness.**

Abstention is the main blocker. The 2B model found every supported passage, but
selected a passage even on all four questions with no positive support. Some
selected passages actually contradict the proposition in the question; that is
not support for it under the frozen convention. These are selection-protocol
errors, not measured rates of fabricated free-text claims: models generated only
a choice number. The 0.8B model also selected an incomplete summary passage in
one supported case. Raw answers and expected labels are retained in
[0.8B results](qwen35-0.8b.holdout.json) and [2B results](qwen35-2b.holdout.json).

These 20 short source-text cases are still synthetic. They do not measure exact
numeric-value generation, calculation accuracy, document synthesis, page
citations or coverage. They cannot establish the requested ≥95% numerical
accuracy or replace 30–50 representative PDFs. Their simple explicit wording
also makes them easier than many real documents.

The p95 convention is sorted index `floor(n × 0.95)`, which is the maximum
of the 20 requests here. RAM above uses `getrusage` after termination in a fresh runner/server process,
including a small `--version` child. It is the stock x86_64 server's peak, not
the current custom Android engine or a phone measurement. Both were run with
context 4096, CPU 4 threads and no GPU. The 2B model is about 2.4 times larger and
was about 1.9 times slower on this holdout, without an overall accuracy gain.

## Limits and next decision

The current evidence supports continuing with Qwen3.5 0.8B as the smaller,
faster candidate while improving support/contradiction/abstention handling and
testing independent source verification. The 2B model's perfect supported-case
result is promising, but its extra size did not resolve unsupported selections.
The adapter needs the native template and a bounded output contract. This
screening does not support shipping the
unchanged current adapter with a weight-file swap. The original 30–50
representative-PDF benchmark, measured numerical accuracy, long-document
completeness, phone performance, actual installed footprint, upgrade/data
retention and Android offline checks remain uncompleted. No verified APK is
being delivered from this screening.

Other researched options include a small extractive QA model plus a MiniLM
reranker. Those could return source spans with a lower weight budget, but they
need a different Android runtime/export path and do not provide general
summaries. They have not been tested in this app.

## Sources and reproduction

- [Qwen3.5 0.8B primary model card](https://huggingface.co/Qwen/Qwen3.5-0.8B)
  and [quantizations](https://huggingface.co/unsloth/Qwen3.5-0.8B-GGUF).
- [Qwen3.5 2B primary model card](https://huggingface.co/Qwen/Qwen3.5-2B)
  and [quantizations](https://huggingface.co/unsloth/Qwen3.5-2B-GGUF).
- [IBM Granite 4.0 350M](https://huggingface.co/ibm-granite/granite-4.0-350m)
  and [quantizations](https://huggingface.co/unsloth/granite-4.0-350m-GGUF).
- [SmolLM2 360M Instruct](https://huggingface.co/HuggingFaceTB/SmolLM2-360M-Instruct)
  and [tested quantizations](https://huggingface.co/bartowski/SmolLM2-360M-Instruct-GGUF).
- [Qwen2.5 0.5B Instruct](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct)
  and [tested quantizations](https://huggingface.co/bartowski/Qwen2.5-0.5B-Instruct-GGUF).
- [Extractive QA](https://huggingface.co/deepset/minilm-uncased-squad2)
  and [MiniLM reranker](https://huggingface.co/cross-encoder/ms-marco-MiniLM-L6-v2).

[Summary and artifact sizes](summary.json), individual `*.scored.json` files and
`*.native.json` files contain per-case results, raw answer text, prompts,
renderings, timings, runtime and artifact provenance. Native files retain full
API response objects but omit redundant raw HTTP copies. The earlier
[Liquid comparison](../liquid-comparison/REPORT.md) contains baseline details.

For the existing-adapter run, use the same `comparison_cases.mjs`, `apt-compare`,
`run_comparison.py` and `score_comparison.mjs` commands documented there. For the
separate diagnostic, run:

```sh
python tests/apt/hf_native_diagnostic.py SERVER_BINARY CASES_JSON MODEL_META_JSON OUTPUT_JSON
python tests/apt/hf_evidence_holdout.py SERVER_BINARY tests/apt/hf_evidence_holdout.json MODEL_META_JSON OUTPUT_JSON
```

`MODEL_META_JSON` contains the public provenance fields plus local `path`; model
files/local paths are not committed. Both experiments use llama.cpp commit
`df9beac7153166550571c70cc667f270b745da49`. The 19 independent analysis/transport
regression tests and framing regression passed again during this evaluation.

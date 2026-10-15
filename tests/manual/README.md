# Reproduce live validation

Use a separate empty `LOCALPDF_DATA` directory. This harness asks the **actual** running
application and selected local model; it never substitutes expected answers. It records
answers and evidence for human relevance/entailment review and clicks each displayed claim
citation in Chromium. A zero exit code is not a claim that model answers are correct.

1. Install the existing project web/test dependencies and browser tooling from the main README.
2. Download the six original PDFs from `docs/validation-release/CORPUS.md` into a directory,
   using exactly the filenames in that table. Keep the originals unchanged.
3. Run `python tests/manual/prepare_corpus.py /absolute/path/to/inputs` once to create labelled
   stress, scanned and comparison derivatives. Do not import while preparation is writing files.
4. Start Ollama; `ollama pull qwen2.5:3b` (or the model under test). Record `ollama --version`,
   `ollama list` and `ollama show MODEL`. Gemma 3 4B timed out in the recorded CPU run.
5. Set `LOCALPDF_MODEL=qwen2.5:3b`, `LOCALPDF_DATA` to the empty test directory,
   `LOCALPDF_OCR_LANGS=eng+ara`, and `TESSDATA_PREFIX` to installed English/Arabic packs.
   Unset `LOCALPDF_TOKEN` for this disposable localhost-only server. Start `python -m localpdf_insight.web` in one terminal. Embeddings were disabled in this pass.
6. In another terminal set `LOCALPDF_VALIDATION_INPUTS` to the prepared input directory,
   optionally `LOCALPDF_VALIDATION_ARTIFACTS` to a writable output directory, then run
   `node tests/manual/live_validation.cjs`. `LOCALPDF_TEST_BASE_URL` defaults to
   `http://127.0.0.1:8765`; `CHROMIUM_EXECUTABLE` can select an existing Chromium binary.
7. Inspect `final-results.json`, claim text, retrieved passages, clicked source IDs/pages and
   screenshots. Check every material claim against the publisher's original page. In particular
   check the absent 2030 forecast, multi-page synthesis, and Arabic questions; refusal or a genuine
   but irrelevant quote is a failure on an answerable question. Check comparison coverage separately.

Use the external Windows/Android checklist for physical-device and installability gates.
Full local harness outputs contain document passages; keep them local when using private PDFs.

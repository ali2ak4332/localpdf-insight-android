"""Cited-line ("cite-v1") rerun of the five-task host evaluation.

Usage: python tests/apt/five_task_cite_eval.py SERVER CORPUS_JSON META_JSON OUTPUT_JSON [--prepare-only] [--resume]

Same corpus, server flags, context, sampling, output budget and two-finding limit as
five_task_eval.py. One thing changes: the model no longer writes quotations, pages or
figure units/periods.
  - Summarize, Insights, Risks: the model writes the claim (or obligation fields) and cites
    a numbered line range; code copies the exact page text of those lines as the quote.
  - Key Figures: the model names a line and the number in it, plus metric and entity; code
    copies value, unit (currency, scale, unit word), period (table column or same line),
    quote and page from the PDF text (src/localpdf_insight/static/apt_figures.mjs).
    A document with no numeric line abstains without a model call.
Rows keep the true model output in rawContent/parsedContent and the code-built findings,
in the original five-task fields, in `materialized`. Grading uses the same rubric.
"""

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

import hf_native_diagnostic as native
import five_task_eval as base
import five_task_summarize as agg

ROOT = Path(__file__).resolve().parents[2]
CITE = ROOT / "tests/apt/five_task_cite.mjs"
PRODUCTION = [ROOT / "src/localpdf_insight/static/apt_lines.mjs", ROOT / "src/localpdf_insight/static/apt_figures.mjs", CITE]
TASKS = base.TASKS
FIELDS = {task: list(fields) for task, fields in base.FIELDS.items()}
MODEL_FIELDS = {"summarize": ["claim", "from", "to"], "insights": ["claim", "from", "to"],
                "figures": ["line", "value", "metric", "entity"],
                "risks": ["obligation", "party", "deadline", "exception", "from", "to"]}


def node(mode, items):
    result = subprocess.run(["node", str(CITE), mode], input=json.dumps(items, ensure_ascii=False),
                            capture_output=True, text=True, check=True, timeout=300)
    out = json.loads(result.stdout)
    if len(out) != len(items):
        raise ValueError(f"{mode} returned {len(out)} items for {len(items)}")
    return out


def make_request(prepared, task):
    return {
        "model": "five-task-eval", "messages": [{"role": "user", "content": prepared["prompt"]}],
        "temperature": 0, "seed": 0, "max_tokens": base.MAX_OUTPUT_TOKENS,
        "stream": False, "cache_prompt": False, "chat_template_kwargs": {"enable_thinking": False},
        "response_format": {"type": "json_schema", "json_schema": {
            "name": task + "_cited", "strict": True, "schema": prepared["schema"]}},
    }


def assess(parsed, schema, materialized, pages, finish_reason, http_status, model_called=True):
    source = {page["page"]: page["text"] for page in pages}
    findings = materialized["findings"]
    exact = [bool(f["quote"].strip()) and f["page"] in source and f["quote"] in source[f["page"]] for f in findings]
    model_findings = parsed.get("findings") if isinstance(parsed, dict) and isinstance(parsed.get("findings"), list) else []
    return {"deterministicSkip": not model_called,
            "schemaValid": True if not model_called else agg.schema_matches(parsed, schema),
            "httpSuccessful": http_status == 200, "completedWithinBudget": finish_reason == "stop",
            "modelFindingsCount": len(model_findings), "findingsCount": len(findings),
            "rejectedFindings": len(materialized["rejected"]),
            "exactQuoteCount": sum(exact),
            "evidence": [{"findingIndex": i, "validRecord": True, "exactQuoteOnCitedPage": ok,
                          "quoteSource": "copied by code from cited lines"} for i, ok in enumerate(exact)],
            "semanticAccuracy": "unscored; requires comparison with frozen gold and source context",
            "coverageAccuracy": "unscored; empty output and exact quotes alone do not establish task success"}


def summarize(rows, planned):
    called = [row for row in rows if not row.get("deterministicSkip")]
    times = sorted(row["milliseconds"] for row in called)
    return {"plannedGenerations": planned, "receivedGenerations": len(rows),
            "modelCalls": len(called), "deterministicSkips": len(rows) - len(called),
            "schemaValid": sum(row["assessment"]["schemaValid"] for row in called),
            "finishedStop": sum(row["finish_reason"] == "stop" for row in called),
            "http200": sum(row["api"].get("httpStatus") == 200 for row in called),
            "modelFindings": sum(row["assessment"]["modelFindingsCount"] for row in rows),
            "materializedFindings": sum(row["assessment"]["findingsCount"] for row in rows),
            "rejectedFindings": sum(row["assessment"]["rejectedFindings"] for row in rows),
            "exactQuotesOnCitedPages": sum(row["assessment"]["exactQuoteCount"] for row in rows),
            "medianRequestMilliseconds": (times[(len(times)-1)//2] + times[len(times)//2]) / 2 if times else None,
            "interpretation": "Exact quotes are guaranteed by construction; they say nothing about whether the cited lines support the claim."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("server_binary", "corpus_json", "meta_json", "output_json"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--doc-id", action="append", default=[])
    parser.add_argument("--max-docs", type=int)
    parser.add_argument("--tasks", nargs="+", choices=TASKS, default=list(TASKS))
    parser.add_argument("--max-input-chars", type=int, default=base.MAX_INPUT_CHARS)
    parser.add_argument("--request-timeout", type=int, default=native.REQUEST_TIMEOUT)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    existing = json.loads(args.output_json.read_text()) if args.output_json.exists() else None
    if existing and existing.get("status") in ("starting", "running", "completed") and not args.resume:
        print(f"Preserving existing {existing['status']} report at {args.output_json}; nothing started", flush=True)
        return 0
    raw = args.corpus_json.read_bytes()
    docs = base.load_documents(raw, args.doc_id)
    if args.max_docs is not None:
        docs = docs[:args.max_docs]
    documents, items, keys = [], [], []
    for doc in docs:
        sections = base.selected_sections(doc, args.max_input_chars, [])
        documents.append({"id": doc["id"], "title": doc["title"],
                          "sourcePages": [{"page": p["page"], "characters": len(p["text"]), "sha256": base.sha_text(p["text"])} for p in doc["pages"]],
                          "sections": sections})
        for section in sections:
            for task in args.tasks:
                items.append({"doc": {"id": doc["id"], "title": doc["title"], "pages": section["pages"]},
                              "task": task, "coverage": section["coverage"]})
                keys.append((doc["id"], section, task))
    prepared = node("prepare", items)
    plan = []
    for (doc_id, section, task), prep in zip(keys, prepared):
        request = None if prep["skip"] else make_request(prep, task)
        plan.append({"documentId": doc_id, "sectionId": section["id"], "task": task,
                     "coverage": section["coverage"], "inputSha256": section["inputSha256"],
                     "promptSha256": None if request is None else base.sha_text(prep["prompt"]),
                     "request": request, "deterministicSkip": prep["skip"], "skipReason": prep.get("skipReason"),
                     "protocolInfo": {k: prep[k] for k in ("lineCount", "figureCandidateCount", "figureLineCount", "tables")}})
    output = args.output_json.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "scope": "Five-task host evaluation, cited-line protocol: model cites numbered lines; code copies quotations and figure fields",
        "limitations": "Same limits as five_task_eval.py. Code-copied quotes are exact by construction; support, relevance and coverage still need source review.",
        "createdAt": base.utc_now(), "corpusSha256": hashlib.sha256(raw).hexdigest(),
        "goldUsedInPromptsOrAutomaticEvidenceScoring": False,
        "productionModulesSha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in PRODUCTION},
        "documents": documents, "plan": plan, "responses": [], "status": "prepared",
        "protocol": {"name": "cite-v1", "evidence": "cited-lines", "tasks": list(args.tasks), "fields": FIELDS,
                     "modelFields": MODEL_FIELDS, "maximumFindings": 2, "maximumSpanLines": 4,
                     "maximumOutputTokens": base.MAX_OUTPUT_TOKENS, "contextTokens": base.CONTEXT_TOKENS,
                     "maximumInputCharacters": args.max_input_chars, "requestTimeoutSeconds": args.request_timeout,
                     "temperature": 0, "seed": 0,
                     "network": "Local 127.0.0.1 HTTP only; --offline; verified local model; no cloud compute or downloader"},
    }
    if args.resume:
        if existing is None or existing.get("corpusSha256") != report["corpusSha256"]:
            raise ValueError("Resume requires a report from the identical frozen corpus")
        old = existing.get("responses", [])
        for o, n in zip(old, plan):
            if any(o.get(k) != n.get(k) for k in ("documentId", "sectionId", "task", "promptSha256", "request")):
                raise ValueError("Resume would change an existing prompt or schema")
        report["responses"] = old
    native.save_report(output, report)
    if args.prepare_only:
        skips = sum(p["deterministicSkip"] for p in plan)
        print(f"Prepared {len(plan)} cases ({skips} deterministic figure abstentions) at {output}; no model executed", flush=True)
        return 0
    binary = args.server_binary.resolve(strict=True)
    meta = json.loads(args.meta_json.read_text())
    model = Path(meta["path"]).resolve(strict=True)
    digest = native.digest(model)
    if digest != meta["sha256"].lower() or ("bytes" in meta and model.stat().st_size != meta["bytes"]):
        raise ValueError("Model checksum or byte size does not match metadata")
    environment = {k: v for k, v in os.environ.items() if not k.startswith("LLAMA_ARG_") and k != "LLAMA_API_KEY"}
    version = subprocess.run([str(binary), "--version"], capture_output=True, text=True, check=True, timeout=10, env=environment)
    port = native.free_port()
    arguments = ["--model", str(model), "--alias", "five-task-eval", "--host", "127.0.0.1", "--port", str(port),
                 "--offline", "--jinja", "--threads", "4", "--threads-batch", "4", "--ctx-size", str(base.CONTEXT_TOKENS),
                 "--batch-size", "256", "--ubatch-size", "128", "--parallel", "1", "--device", "none",
                 "--gpu-layers", "0", "--no-kv-offload", "--fit", "off", "--no-cache-prompt", "--cache-ram", "0",
                 "--reasoning", "off", "--no-context-shift", "--no-webui", "--no-slots", "--timeout", str(args.request_timeout)]
    public_arguments = arguments.copy()
    public_arguments[public_arguments.index("--model") + 1] = "<verified-local-model>"
    log_path = output.with_suffix(".stderr.log")
    report.update({"model": {k: v for k, v in meta.items() if k != "path"}, "verifiedModelSha256": digest,
                   "serverBinarySha256": native.digest(binary), "expectedRuntimeCommit": native.RUNTIME_COMMIT,
                   "serverVersion": (version.stdout + version.stderr).strip(),
                   "host": {"machine": platform.machine(), "system": platform.system()},
                   "additionalFineTuningPerformed": False, "serverArguments": public_arguments,
                   "serverLog": log_path.name, "status": "starting"})
    native.save_report(output, report)
    sections = {(d["id"], s["id"]): s for d in documents for s in d["sections"]}
    process, exit_code = None, 0
    try:
        with log_path.open("w") as log:
            process = subprocess.Popen([str(binary), *arguments], stdin=subprocess.DEVNULL,
                                       stdout=log, stderr=subprocess.STDOUT, env=environment)
            started = time.perf_counter()
            report["health"] = native.wait_ready(process, port)
            report["startupMilliseconds"] = round((time.perf_counter() - started) * 1000, 3)
            report["serverMemoryAfterStartup"] = base.server_memory(process.pid)
            report["status"] = "running"
            for item in plan[len(report["responses"]):]:
                section = sections[(item["documentId"], item["sectionId"])]
                doc = {"id": item["documentId"], "title": next(d["title"] for d in documents if d["id"] == item["documentId"]),
                       "pages": section["pages"]}
                if item["deterministicSkip"]:
                    materialized = {"findings": [], "rejected": [], "details": []}
                    row = {**item, "prompt": None, "renderedPrompt": None, "rawContent": "", "parsedContent": None,
                           "finish_reason": None, "milliseconds": 0, "api": {}, "tokenUsage": None,
                           "materialized": {"findings": []}, "materializationRejected": [], "materializationDetails": [],
                           "assessment": assess(None, None, materialized, section["pages"], None, None, model_called=False)}
                else:
                    if process.poll() is not None:
                        raise RuntimeError("Server exited before all generation requests completed")
                    body = item["request"]
                    template = native.request_json(port, "POST", "/apply-template", body, native.TEMPLATE_TIMEOUT)
                    rendered = template.get("response")
                    rendered_prompt = rendered.get("prompt") if isinstance(rendered, dict) else None
                    tokens = native.request_json(port, "POST", "/tokenize", {"content": rendered_prompt or ""}, native.TEMPLATE_TIMEOUT)
                    prompt_tokens = len(tokens["response"]["tokens"]) if isinstance(tokens.get("response"), dict) and isinstance(tokens["response"].get("tokens"), list) else None
                    before = base.server_memory(process.pid)
                    started = time.perf_counter()
                    result = native.request_json(port, "POST", "/v1/chat/completions", body, args.request_timeout)
                    fields = native.capture_completion(result)
                    materialized = node("materialize", [{"doc": doc, "task": item["task"], "parsed": fields["parsedContent"]}])[0]
                    row = {**item, "prompt": body["messages"][0]["content"], "renderedPrompt": rendered_prompt,
                           "renderedPromptTokens": prompt_tokens, "templateInspection": template,
                           "milliseconds": round((time.perf_counter() - started) * 1000, 3),
                           "serverMemoryBefore": before, "serverMemoryAfter": base.server_memory(process.pid),
                           "api": result, "tokenUsage": result.get("response", {}).get("usage") if isinstance(result.get("response"), dict) else None,
                           **fields, "materialized": {"findings": materialized["findings"]},
                           "materializationRejected": materialized["rejected"], "materializationDetails": materialized["details"]}
                    row["assessment"] = assess(fields["parsedContent"], body["response_format"]["json_schema"]["schema"],
                                               materialized, section["pages"], fields["finish_reason"], result["httpStatus"])
                    if "transportError" in result:
                        report["responses"].append(row)
                        raise RuntimeError("Completion failed or timed out; raw and partial response preserved")
                report["responses"].append(row)
                report["summary"] = summarize(report["responses"], len(plan))
                native.save_report(output, report)
                a = row["assessment"]
                print(f"{meta.get('filename', model.name)} {len(report['responses'])}/{len(plan)} {item['documentId']} {item['task']}: "
                      f"{'skip' if a['deterministicSkip'] else 'HTTP ' + str(row['api'].get('httpStatus'))}, "
                      f"findings {a['findingsCount']}/{a['modelFindingsCount']} kept, rejected {a['rejectedFindings']}", flush=True)
            called = [r for r in report["responses"] if not r.get("deterministicSkip")]
            report["status"] = "completed" if all(r["api"].get("httpStatus") == 200 for r in called) else "failed"
            exit_code = 0 if report["status"] == "completed" else 1
    except (Exception, KeyboardInterrupt) as error:
        report["status"] = "failed"
        report["error"] = f"{type(error).__name__}: {error}"
        exit_code = 1
    finally:
        if process is not None:
            report["serverMemoryBeforeStop"] = base.server_memory(process.pid)
            peaks = [s.get("peakRssBytes") for s in [report.get("serverMemoryAfterStartup", {}), report["serverMemoryBeforeStop"],
                     *(r.get("serverMemoryAfter", {}) for r in report["responses"])] if s and s.get("peakRssBytes") is not None]
            report["peakServerRssBytes"] = max(peaks) if peaks else None
            report["serverExitCode"] = native.stop_server(process)
        report["summary"] = summarize(report["responses"], len(plan))
        report["finishedAt"] = base.utc_now()
        native.save_report(output, report)
    print(f"Saved {output} ({report['status']})", flush=True)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())

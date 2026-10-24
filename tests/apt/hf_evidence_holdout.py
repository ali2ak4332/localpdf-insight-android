"""Run the frozen text-only holdout through one local stock llama-server.

Usage: python tests/apt/hf_evidence_holdout.py SERVER HOLDOUT_JSON META_JSON OUTPUT_JSON
This is synthetic source-selection accuracy, not a PDF or calculation benchmark.
"""

import argparse
from collections import Counter
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import subprocess
import sys
import time

import hf_native_diagnostic as native


CHOICE_SCHEMA = {
    "type": "object",
    "properties": {"choice": {"type": "integer", "enum": [-1, 0, 1, 2, 3]}},
    "required": ["choice"],
    "additionalProperties": False,
}


def load_holdout(raw):
    fixture = json.loads(raw)
    cases = fixture["cases"]
    tasks = ["figures", "risks", "insights", "summarize"]
    if len(cases) != 20 or len({case["id"] for case in cases}) != 20:
        raise ValueError("Expected twenty uniquely identified holdout cases")
    for task in tasks:
        answers = [case["expected"] for case in cases if case["task"] == task]
        if Counter(answers) != Counter([-1, 0, 1, 2, 3]):
            raise ValueError(f"Task {task} must contain each answer position and -1 once")
    for case in cases:
        if (type(case["expected"]) is not int or not case["question"]
                or [p["number"] for p in case["passages"]] != [0, 1, 2, 3]
                or not all(isinstance(p["text"], str) and p["text"] for p in case["passages"])):
            raise ValueError(f"Invalid holdout case {case['id']}")
    return fixture


def make_request(case):
    prompt = (
        "Read the question and choose the single numbered passage that supplies the requested evidence."
        " Use only the supplied text. If no passage supplies the requested evidence, choose -1."
        '\nReturn only a JSON object with the key "choice" and an integer: -1, 0, 1, 2, or 3.'
        + "\n\nQUESTION:\n" + case["question"]
        + "\n\nPASSAGES:\n"
        + "\n\n".join(f"{p['number']}: {p['text']}" for p in case["passages"])
    )
    body = native.chat_request(prompt)
    body["response_format"]["json_schema"]["schema"] = CHOICE_SCHEMA
    return body


def summarize(rows, total):
    supported = [row for row in rows if row["expected"] != -1]
    unsupported = [row for row in rows if row["expected"] == -1]
    exact = sum(row["exact"] for row in rows)
    times = sorted(row["milliseconds"] for row in rows)
    return {
        "definition": "Exact means HTTP 200 with a parsed object containing only an integer choice equal to the frozen gold; failed or missing responses count as unsuccessful",
        "exactCases": exact, "totalCases": total, "responsesReceived": len(rows),
        "exactSelectionRate": exact / total,
        "supportedCases": 16, "supportedExactCases": sum(row["exact"] for row in supported),
        "abstention": {
            "expectedCases": 4,
            "correctAbstentions": sum(row["exact"] for row in unsupported),
            "falseAbstentions": sum(row["choice"] == -1 for row in supported),
            "unsupportedSelections": sum(row["choice"] in range(4) for row in unsupported),
        },
        "validChoiceObjects": sum(row["validChoiceObject"] for row in rows),
        "byTask": {task: {"exactCases": sum(row["exact"] for row in rows if row["task"] == task), "totalCases": 5}
                   for task in ["figures", "risks", "insights", "summarize"]},
        "medianRequestMs": times[len(times) // 2] if times else None,
        "p95RequestMs": times[min(int(len(times) * .95), len(times) - 1)] if times else None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["server_binary", "holdout_json", "meta_json", "output_json"]:
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    raw = args.holdout_json.read_bytes()
    fixture = load_holdout(raw)
    meta = json.loads(args.meta_json.read_text())
    binary = args.server_binary.resolve(strict=True)
    model = Path(meta["path"]).resolve(strict=True)
    model_digest = native.digest(model)
    if model_digest != meta["sha256"].lower() or ("bytes" in meta and model.stat().st_size != meta["bytes"]):
        raise ValueError("Model checksum or byte size does not match metadata")
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith("LLAMA_ARG_") and key != "LLAMA_API_KEY"}
    version = subprocess.run([str(binary), "--version"], capture_output=True, text=True,
                             check=True, timeout=10, env=environment)
    output = args.output_json.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    log_path = output.with_suffix(".stderr.log")
    port = native.free_port()
    arguments = [
        "--model", str(model), "--alias", "native-diagnostic", "--host", "127.0.0.1", "--port", str(port),
        "--offline", "--jinja", "--threads", "4", "--threads-batch", "4", "--ctx-size", "4096",
        "--batch-size", "256", "--ubatch-size", "128", "--parallel", "1", "--device", "none",
        "--gpu-layers", "0", "--no-kv-offload", "--fit", "off", "--no-cache-prompt",
        "--reasoning", "off", "--no-webui", "--no-slots", "--timeout", str(native.REQUEST_TIMEOUT),
    ]
    public_arguments = arguments.copy()
    public_arguments[public_arguments.index("--model") + 1] = "<verified-local-model>"
    report = {
        "scope": "Twenty frozen synthetic English source-evidence cases; selection and abstention only",
        "limitations": "Not a representative-PDF benchmark, numerical-calculation test, or real-world verification; prompt/schema/Jinja path differ from production adapter",
        "createdAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "fixtureSha256": hashlib.sha256(raw).hexdigest(), "fixtureProvenance": fixture["provenance"],
        "model": {key: value for key, value in meta.items() if key != "path"},
        "verifiedModelSha256": model_digest, "additionalFineTuningPerformed": False,
        "expectedRuntimeCommit": native.RUNTIME_COMMIT,
        "serverVersion": (version.stdout + version.stderr).strip(), "serverBinarySha256": native.digest(binary),
        "host": {"machine": platform.machine(), "system": platform.system()},
        "parameters": {
            "serverArguments": public_arguments, "contextTokens": 4096, "cpuThreads": 4,
            "batchTokens": 256, "ubatchTokens": 128, "parallel": 1, "temperature": 0, "seed": 0,
            "maximumOutputTokens": 96, "chatTemplateKwargs": {"enable_thinking": False},
            "reasoning": "off", "choiceSchema": CHOICE_SCHEMA, "promptCaching": False,
            "startupTimeoutSeconds": native.STARTUP_TIMEOUT, "requestTimeoutSeconds": native.REQUEST_TIMEOUT,
            "templateTimeoutSeconds": native.TEMPLATE_TIMEOUT,
            "network": "Local 127.0.0.1 HTTP; --offline; verified local model; no downloader or remote API",
            "timingScope": "API wall time excludes template inspection and startup; checksum read warms filesystem cache",
        },
        "memoryScope": "Fresh runner/server process; getrusage(RUSAGE_CHILDREN).ru_maxrss after server termination, Linux KiB multiplied by 1024; includes small --version child; host, not Android",
        "serverLog": log_path.name, "responses": [], "status": "starting",
    }
    native.save_report(output, report)
    process = None
    exit_code = 0
    try:
        with log_path.open("w") as log:
            process = subprocess.Popen([str(binary), *arguments], stdin=subprocess.DEVNULL,
                                       stdout=log, stderr=subprocess.STDOUT, env=environment)
            startup = time.perf_counter()
            report["health"] = native.wait_ready(process, port)
            report["startupMilliseconds"] = round((time.perf_counter() - startup) * 1000, 3)
            report["status"] = "running"
            for case in fixture["cases"]:
                if process.poll() is not None:
                    raise RuntimeError("Server exited before all twenty responses were received")
                body = make_request(case)
                template = native.request_json(port, "POST", "/apply-template", body, native.TEMPLATE_TIMEOUT)
                rendered = template.get("response")
                started = time.perf_counter()
                result = native.request_json(port, "POST", "/v1/chat/completions", body)
                row = {"id": case["id"], "task": case["task"], "expected": case["expected"],
                       "prompt": body["messages"][0]["content"], "request": body,
                       "templateInspection": template,
                       "renderedPrompt": rendered.get("prompt") if isinstance(rendered, dict) else None,
                       "milliseconds": round((time.perf_counter() - started) * 1000, 3),
                       "api": result, **native.capture_completion(result)}
                parsed = row["parsedContent"]
                valid = (result["httpStatus"] == 200 and isinstance(parsed, dict) and set(parsed) == {"choice"}
                         and type(parsed["choice"]) is int and parsed["choice"] in [-1, 0, 1, 2, 3])
                row.update({"validChoiceObject": valid, "choice": parsed["choice"] if valid else None,
                            "exact": valid and parsed["choice"] == case["expected"]})
                report["responses"].append(row)
                native.save_report(output, report)
                print(f"{meta.get('filename', model.name)} {len(report['responses'])}/20 {case['id']}: HTTP {result['httpStatus']}, finish={row['finish_reason']}", flush=True)
                if "transportError" in result:
                    raise RuntimeError("Completion request failed or timed out; partial report preserved")
            if len(report["responses"]) != 20 or any(row["api"]["httpStatus"] != 200 for row in report["responses"]):
                raise RuntimeError("Twenty successful API responses were not received")
            report["status"] = "completed"
    except (Exception, KeyboardInterrupt) as error:
        report["status"] = "failed"
        report["error"] = f"{type(error).__name__}: {error}"
        exit_code = 1
    finally:
        if process is not None:
            report["serverExitCode"] = native.stop_server(process)
            rss = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
            report["peakProcessRssBytes"] = int(rss * 1024) if sys.platform.startswith("linux") else None
        report["summary"] = summarize(report["responses"], 20)
        report["finishedAt"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        native.save_report(output, report)
    print(f"Saved {output} ({report['status']})", flush=True)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())

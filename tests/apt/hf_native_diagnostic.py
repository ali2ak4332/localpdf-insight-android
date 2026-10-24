"""Separate stock-server compatibility diagnostic; never an app/model score.

Usage: python tests/apt/hf_native_diagnostic.py SERVER CASES_JSON META_JSON OUTPUT_JSON

Uses eight existing synthetic cases and four literal-output controls. This changes
the prompt, output schema, and chat-template implementation together; its results
are not an apples-to-apples improvement over the production adapter comparison.
Only Python's standard library is required. One invocation runs one local model.
"""

import argparse
import datetime
import hashlib
import http.client
import json
import os
from pathlib import Path
import platform
import socket
import subprocess
import sys
import time


CASE_IDS = [0, 5, 10, 15, 16, 21, 26, 31]
RUNTIME_COMMIT = "df9beac7153166550571c70cc667f270b745da49"
STARTUP_TIMEOUT = 120
REQUEST_TIMEOUT = 60
TEMPLATE_TIMEOUT = 15
CHOICE_SCHEMA = {
    "type": "object",
    "properties": {"choice": {"type": "integer", "enum": [0, 1, 2, 3]}},
    "required": ["choice"],
    "additionalProperties": False,
}
INSTRUCTIONS = {
    "figures": "Choose the passage with the most important numerical result or amount.",
    "risks": "Choose the passage stating a risk, duty, payment requirement, or deadline.",
    "insights": "Choose the passage stating an important finding, cause, or implication.",
    "summarize": "Choose the passage that best states the document's main purpose and conclusions.",
}


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def save_report(path, report):
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    temporary.replace(path)


def free_port():
    # The reservation must close before llama-server binds. A collision fails
    # startup rather than falling back to another service or remote endpoint.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as reservation:
        reservation.bind(("127.0.0.1", 0))
        return reservation.getsockname()[1]


def request_json(port, method, route, body=None, timeout=REQUEST_TIMEOUT):
    """Local-only HTTP with an absolute deadline, preserving raw/error bodies."""
    deadline = time.monotonic() + timeout
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    chunks = []
    result = {"httpStatus": None, "rawResponse": "", "response": None}

    def remaining():
        value = deadline - time.monotonic()
        if value <= 0:
            raise TimeoutError("HTTP request deadline exceeded")
        return value

    try:
        connection.connect()
        transport = connection.sock
        transport.settimeout(remaining())
        encoded = None if body is None else json.dumps(body).encode("utf-8")
        headers = {} if body is None else {"Content-Type": "application/json"}
        connection.request(method, route, body=encoded, headers=headers)
        transport.settimeout(remaining())
        response = connection.getresponse()
        result["httpStatus"] = response.status
        while not response.isclosed():
            transport.settimeout(remaining())
            chunk = response.read1(65536)
            if not chunk:
                break
            chunks.append(chunk)
        result["rawResponse"] = b"".join(chunks).decode("utf-8", errors="replace")
        try:
            result["response"] = json.loads(result["rawResponse"])
        except (ValueError, TypeError) as error:
            result["parseError"] = str(error)
    except (OSError, TimeoutError, http.client.HTTPException) as error:
        result["rawResponse"] = b"".join(chunks).decode("utf-8", errors="replace")
        result["transportError"] = f"{type(error).__name__}: {error}"
    finally:
        connection.close()
    return result


def wait_ready(process, port):
    deadline = time.monotonic() + STARTUP_TIMEOUT
    last = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Server exited during startup with code {process.returncode}")
        last = request_json(port, "GET", "/health", timeout=min(2, deadline - time.monotonic()))
        parsed = last.get("response")
        if last["httpStatus"] == 200 and isinstance(parsed, dict) and parsed.get("status") == "ok":
            return last
        time.sleep(min(0.1, max(0, deadline - time.monotonic())))
    raise TimeoutError(f"Server readiness deadline exceeded; last health result: {last}")


def stop_server(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
    return process.returncode


def diagnostic_cases(cases):
    if not isinstance(cases, list) or len(cases) != 32:
        raise ValueError("Expected the existing 32-case comparison fixture")
    indexed = {case["case"]: case for case in cases}
    if len(indexed) != len(cases):
        raise ValueError("Fixture contains duplicate case IDs")
    selected = []
    for case_id in CASE_IDS:
        case = indexed[case_id]
        candidates = case["section"]["candidates"]
        expected = case["expected"]
        if (len(candidates) != 4 or len(expected) != 1
                or type(expected[0]) is not int or expected[0] not in range(4)):
            raise ValueError(f"Case {case_id} must have four passages and one in-range gold choice")
        prompt = (
            INSTRUCTIONS[case["task"]]
            + "\nSelect exactly one best passage from the numbered passages below."
            + '\nReturn only a JSON object with the key "choice" and the passage number (0, 1, 2, or 3).'
            + "\n\nPASSAGES:\n"
            + "\n\n".join(f"{i}: {candidate['text']}" for i, candidate in enumerate(candidates))
        )
        selected.append({
            "kind": "source-selection", "case": case_id, "task": case["task"],
            "expected": {"choice": expected[0]}, "fixtureExpected": expected,
            "prompt": prompt,
        })
    for choice in range(4):
        selected.append({
            "kind": "literal-output-control", "case": f"control-{choice}", "task": "control",
            "expected": {"choice": choice},
            "prompt": f'Return the number {choice} in "choice". Return only a JSON object with the key "choice".',
        })
    return selected


def chat_request(prompt):
    return {
        "model": "native-diagnostic",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "seed": 0,
        "max_tokens": 96,
        "stream": False,
        "cache_prompt": False,
        "chat_template_kwargs": {"enable_thinking": False},
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "passage_choice", "strict": True, "schema": CHOICE_SCHEMA},
        },
    }


def capture_completion(result):
    """Extract convenience fields without replacing or discarding the API reply."""
    fields = {"rawContent": None, "finish_reason": None, "parsedContent": None}
    response = result.get("response")
    choices = response.get("choices") if isinstance(response, dict) else None
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        fields["contentError"] = "API response has no first choice"
        return fields
    first = choices[0]
    fields["finish_reason"] = first.get("finish_reason")
    message = first.get("message")
    if not isinstance(message, dict):
        fields["contentError"] = "API response has no message object"
        return fields
    fields["rawContent"] = message.get("content")
    if "reasoning_content" in message:
        fields["reasoningContent"] = message["reasoning_content"]
    try:
        fields["parsedContent"] = json.loads(fields["rawContent"])
    except (ValueError, TypeError) as error:
        fields["contentError"] = f"{type(error).__name__}: {error}"
    return fields


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("server_binary", type=Path)
    parser.add_argument("cases_json", type=Path)
    parser.add_argument("meta_json", type=Path)
    parser.add_argument("output_json", type=Path)
    args = parser.parse_args()
    binary = args.server_binary.resolve(strict=True)
    fixture_bytes = args.cases_json.read_bytes()
    cases = diagnostic_cases(json.loads(fixture_bytes))
    meta = json.loads(args.meta_json.read_text())
    model = Path(meta["path"]).resolve(strict=True)
    model_digest = digest(model)
    if model_digest != meta["sha256"].lower():
        raise ValueError("Model checksum does not match metadata")
    if "bytes" in meta and model.stat().st_size != meta["bytes"]:
        raise ValueError("Model byte size does not match metadata")
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith("LLAMA_ARG_") and key != "LLAMA_API_KEY"}
    version = subprocess.run([str(binary), "--version"], capture_output=True, text=True,
                             check=True, timeout=10, env=environment)
    output = args.output_json.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    log_path = output.with_suffix(".stderr.log")
    port = free_port()
    arguments = [
        "--model", str(model), "--alias", "native-diagnostic",
        "--host", "127.0.0.1", "--port", str(port), "--offline", "--jinja",
        "--threads", "4", "--threads-batch", "4", "--ctx-size", "4096",
        "--batch-size", "256", "--ubatch-size", "128", "--parallel", "1",
        "--device", "none", "--gpu-layers", "0", "--no-kv-offload", "--fit", "off",
        "--no-cache-prompt", "--reasoning", "off", "--no-webui", "--no-slots",
        "--timeout", str(REQUEST_TIMEOUT),
    ]
    public_arguments = arguments.copy()
    public_arguments[public_arguments.index("--model") + 1] = "<verified-local-model>"
    report = {
        "scope": "Separate 8-case synthetic compatibility diagnostic plus 4 literal-output controls",
        "interpretation": "Prompt, schema and native Jinja template path change together; not an apples-to-apples improvement or whole-model score",
        "createdAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "model": {key: value for key, value in meta.items() if key != "path"},
        "verifiedModelSha256": model_digest,
        "additionalFineTuningPerformed": False,
        "expectedRuntimeCommit": RUNTIME_COMMIT,
        "serverVersion": (version.stdout + version.stderr).strip(),
        "serverBinarySha256": digest(binary),
        "host": {"machine": platform.machine(), "system": platform.system()},
        "fixtureSha256": hashlib.sha256(fixture_bytes).hexdigest(),
        "sourceCaseIds": CASE_IDS,
        "parameters": {
            "serverArguments": public_arguments,
            "contextTokens": 4096, "cpuThreads": 4, "batchTokens": 256, "ubatchTokens": 128,
            "parallel": 1, "temperature": 0, "seed": 0, "maximumOutputTokens": 96,
            "chatTemplateKwargs": {"enable_thinking": False}, "reasoning": "off",
            "choiceSchema": CHOICE_SCHEMA, "promptCaching": False,
            "startupTimeoutSeconds": STARTUP_TIMEOUT, "requestTimeoutSeconds": REQUEST_TIMEOUT,
            "templateTimeoutSeconds": TEMPLATE_TIMEOUT,
            "network": "127.0.0.1 HTTP only; server --offline; local verified model; no downloader or remote API",
            "memoryScope": "One fresh server per invocation; separate requests with prompt caching disabled",
            "timingScope": "API request wall time, excluding template inspection and startup; checksum reads warm filesystem cache",
        },
        "serverLog": log_path.name,
        "responses": [], "status": "starting",
    }
    save_report(output, report)
    process = None
    exit_code = 0
    try:
        with log_path.open("w") as log:
            process = subprocess.Popen([str(binary), *arguments], stdin=subprocess.DEVNULL,
                                       stdout=log, stderr=subprocess.STDOUT, env=environment)
            startup = time.perf_counter()
            report["health"] = wait_ready(process, port)
            report["startupMilliseconds"] = round((time.perf_counter() - startup) * 1000, 3)
            report["status"] = "running"
            for case in cases:
                if process.poll() is not None:
                    raise RuntimeError(f"Server exited before case {case['case']}")
                body = chat_request(case["prompt"])
                template = request_json(port, "POST", "/apply-template", body, TEMPLATE_TIMEOUT)
                rendered = template.get("response")
                row = {**case, "request": body, "templateInspection": template,
                       "renderedPrompt": rendered.get("prompt") if isinstance(rendered, dict) else None}
                started = time.perf_counter()
                result = request_json(port, "POST", "/v1/chat/completions", body)
                row.update({"milliseconds": round((time.perf_counter() - started) * 1000, 3),
                            "api": result, **capture_completion(result)})
                report["responses"].append(row)
                save_report(output, report)
                print(f"{meta.get('filename', model.name)} {case['case']}: HTTP {result['httpStatus']}, finish={row['finish_reason']}", flush=True)
                if "transportError" in result:
                    raise RuntimeError(f"Request failed or timed out for case {case['case']}; response preserved")
            report["status"] = "completed"
    except (Exception, KeyboardInterrupt) as error:
        report["status"] = "failed"
        report["error"] = f"{type(error).__name__}: {error}"
        exit_code = 1
    finally:
        if process is not None:
            report["serverExitCode"] = stop_server(process)
        report["finishedAt"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        save_report(output, report)
    print(f"Saved {output} ({report['status']})", flush=True)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())

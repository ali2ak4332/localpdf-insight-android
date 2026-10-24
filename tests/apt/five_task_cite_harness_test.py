"""Plumbing test for five_task_cite_eval.py with a scripted fake llama-server. No model is run.

Usage: python tests/apt/five_task_cite_harness_test.py
Checks: prompts carry numbered lines; figures with no numeric line abstain without a call;
cited ranges become exact page quotes; invalid ranges and absent values are rejected;
figure value/unit/period come from code. Says nothing about model quality.
"""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
FAKE_SERVER = r'''#!/usr/bin/env python3
import json, re, sys
from http.server import BaseHTTPRequestHandler, HTTPServer
if "--version" in sys.argv:
    print("fake-llama-server 0"); sys.exit(0)
port = int(sys.argv[sys.argv.index("--port") + 1])
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def reply(self, body):
        data = json.dumps(body).encode(); self.send_response(200)
        self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(data)))
        self.end_headers(); self.wfile.write(data)
    def do_GET(self): self.reply({"status": "ok"})
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path == "/tokenize":
            return self.reply({"tokens": list(range(len(body["content"]) // 4))})
        prompt = body["messages"][0]["content"]
        if self.path == "/apply-template":
            return self.reply({"prompt": "<|im_start|>user\n" + prompt + "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"})
        schema = body["response_format"]["json_schema"]["schema"]["properties"]["findings"]["items"]["properties"]
        lines = dict(re.findall(r"^\[(\d+)\] (.*)$", prompt, re.M))
        if "line" in schema:
            line = schema["line"]["enum"][0]
            value = re.search(r"\d[\d,]*(?:\.\d+)?", lines[str(line)]).group(0)
            findings = [{"line": line, "value": value, "metric": "fake metric", "entity": "Fake entity"},
                        {"line": line, "value": "999,999,999", "metric": "absent", "entity": "Fake entity"}]
        else:
            ids = schema["from"]["enum"]
            first = ids[1] if len(ids) > 1 else ids[0]
            extra = {k: "x" for k in schema if k not in ("from", "to")}
            findings = [{**extra, "from": first, "to": first}, {**extra, "from": ids[0], "to": ids[-1]}]
        content = json.dumps({"findings": findings})
        self.reply({"choices": [{"message": {"content": content}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120}})
HTTPServer(("127.0.0.1", port), H).serve_forever()
'''
DOCS = [
    {"id": "fin", "title": "Northwind Devices Q4 FY24 Condensed Consolidated Statements", "pages": [
        {"page": 1, "text": "Northwind Devices Inc.\n(In millions, except per-share amounts)\nThree Months Ended Twelve Months Ended\n"
                             "September 28, 2024 September 30, 2023 September 28, 2024 September 30, 2023\n"
                             "Products $ 61,250 $ 58,410 $ 250,118 $ 247,903\nNet income $ 16,742 $ 19,530 $ 81,996 $ 79,412"},
        {"page": 2, "text": "Notes\nThe company repurchased shares during the year."}]},
    {"id": "nda", "title": "Example Nondisclosure Agreement", "pages": [
        {"page": 1, "text": "MUTUAL NONDISCLOSURE AGREEMENT\n1. Definitions\nThe Recipient shall keep Confidential Information secret.\n"
                             "The Recipient shall not disclose it to any third party\nunless required by law."}]},
]


def main():
    with tempfile.TemporaryDirectory(prefix="apt-cite-harness-") as directory:
        root = Path(directory)
        server = root / "fake-llama-server"; server.write_text(FAKE_SERVER); server.chmod(0o755)
        model = root / "model.gguf"; model.write_bytes(b"not a model")
        (root / "meta.json").write_text(json.dumps({"path": str(model), "filename": "fake.gguf", "bytes": model.stat().st_size,
                                                    "sha256": hashlib.sha256(model.read_bytes()).hexdigest()}))
        (root / "corpus.json").write_text(json.dumps({"documents": DOCS}))
        out = root / "report.json"
        run = subprocess.run([sys.executable, str(HERE / "five_task_cite_eval.py"), str(server), str(root / "corpus.json"),
                              str(root / "meta.json"), str(out)], capture_output=True, text=True, timeout=300)
        report = json.loads(out.read_text())
        assert run.returncode == 0 and report["status"] == "completed", run.stdout[-3000:] + run.stderr[-3000:] + str(report.get("error"))
        rows = {(r["documentId"], r["task"]): r for r in report["responses"]}
        assert len(rows) == 8 and report["protocol"]["evidence"] == "cited-lines"
        pages = {d["id"]: {p["page"]: p["text"] for p in d["pages"]} for d in DOCS}
        # Every materialized quote is an exact substring of its cited page.
        for (doc_id, task), row in rows.items():
            for f in row["materialized"]["findings"]:
                assert f["quote"] in pages[doc_id][f["page"]], (doc_id, task)
                assert set(f) == set(report["protocol"]["fields"][task])
        # Figures in a document without numbers: no model call, empty findings.
        skip = rows[("nda", "figures")]
        assert skip["deterministicSkip"] is True and skip["request"] is None and skip["materialized"] == {"findings": []}
        assert skip["assessment"]["deterministicSkip"] is True
        # Prompt carries numbered lines and the detected table columns.
        fig = rows[("fin", "figures")]
        assert "[5] Products $ 61,250" in fig["prompt"] and "TABLE COLUMNS DETECTED BY THE APP" in fig["prompt"]
        rec = fig["materialized"]["findings"]
        assert len(rec) == 1 and rec[0]["value"] == "61,250" and rec[0]["unit"] == "$ millions"
        assert rec[0]["period"] == "Three Months Ended September 28, 2024" and rec[0]["metric"] == "Products"
        assert [r["reason"] for r in fig["materializationRejected"]] == ["Value does not occur as a figure on the cited line."]
        # Line ranges: one valid single-line citation, one over-long or cross-page range rejected.
        for key in [("nda", "risks"), ("fin", "summarize")]:
            row = rows[key]
            assert row["assessment"]["modelFindingsCount"] == 2 and row["assessment"]["findingsCount"] == 1, key
            assert row["materializationRejected"][0]["reason"] in ("Cited range exceeds 4 lines.", "Cited lines span more than one page."), key
        assert rows[("nda", "risks")]["materialized"]["findings"][0]["quote"] == "1. Definitions"
        summary = report["summary"]
        assert summary["modelCalls"] == 7 and summary["deterministicSkips"] == 1
        print(json.dumps({"passed": True, "cases": len(rows), "modelCalls": summary["modelCalls"],
                          "materializedFindings": summary["materializedFindings"], "rejectedFindings": summary["rejectedFindings"],
                          "scope": "Fake server; protocol plumbing only, no model"}))


if __name__ == "__main__":
    main()

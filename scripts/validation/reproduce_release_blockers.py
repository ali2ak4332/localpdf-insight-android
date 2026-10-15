"""Observe the gatekeeper cases; controlled model output is not live validation."""
import io
import json
import locale
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from concurrent.futures import Future
import fitz
from localpdf_insight import core
from localpdf_insight.web import create_app

class InlineExecutor:
    def submit(self, fn, *args):
        future = Future()
        try: future.set_result(fn(*args))
        except Exception as exc: future.set_exception(exc)
        return future

def observe():
    results = []
    with tempfile.TemporaryDirectory(prefix='localpdf-blockers-') as tmp:
        root = Path(tmp)
        os.environ['LOCALPDF_MODEL'] = 'controlled-adversarial-response-NOT-live'
        os.environ.pop('LOCALPDF_TOKEN', None)
        os.environ.pop('LOCALPDF_EMBED_MODEL', None)
        app = create_app(root, executor=InlineExecutor())
        client = app.test_client()
        with fitz.open() as pdf:
            pdf.new_page().insert_text((60, 80), 'The net profit for 2025 was AED 100 million.')
            data = pdf.tobytes()
        imported = client.post('/api/import', data={'file': (io.BytesIO(data), '\u0645\u0644\u0641.pdf')}, headers={'X-LocalPDF': '1'})
        doc = imported.json['document']
        source = app.extensions['insight']['index'].all_chunks([doc['id']])[0]
        original = core.ollama_generate
        try:
            for strict, text, case in [(True, 'The net profit for 2025 was AED 100 million.', 'strict_irrelevant'),
                                       (False, 'The net profit forecast for 2030 is AED 999 million.', 'assisted_fabricated')]:
                core.ollama_generate = lambda *args, **kwargs: json.dumps({'claims': [{'text': text, 'source_ids': [source['id']]}]})
                response = client.post('/api/ask', json={'scope': 'current', 'current_id': doc['id'], 'question': 'What is the net profit forecast for 2030?', 'strict': strict}, headers={'X-LocalPDF': '1'})
                results.append({'case': case, 'http_status': response.status_code, 'response': response.json, 'unsafe_claim_released': bool(response.json.get('claims'))})
        finally: core.ollama_generate = original
        env = dict(os.environ, LC_ALL='C', LANG='C', PYTHONUTF8='0', PYTHONCOERCECLOCALE='0')
        code = "import locale; from localpdf_insight.web import create_app; print('encoding:',locale.getencoding()); create_app(__import__('sys').argv[1]); print('restart OK')"
        process = subprocess.run([sys.executable, '-c', code, str(root)], env=env, capture_output=True)
        results.append({'case': 'arabic_restart', 'import_http': imported.status_code, 'restart_exit': process.returncode, 'stdout': process.stdout.decode('utf-8', errors='backslashreplace'), 'stderr': process.stderr.decode('utf-8', errors='backslashreplace'), 'actual_platform': sys.platform})
    return results

if __name__ == '__main__':
    Path(sys.argv[1]).write_text(json.dumps(observe(), indent=2, ensure_ascii=True)+'\n', encoding='utf-8')

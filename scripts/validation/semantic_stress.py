"""Held-out diagnostic of semantic-verifier dependency; never a live-model gate.

Expected meanings are frozen separately. Failures remain failures in the evidence
and process exit status, even when the engineered contradiction vetoes are bounded.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tests'))
from evidence_capture import EvidenceRun, inspect_run, exclusive
from test_independent_b1 import import_frozen_case, norm
from test_web import InlineExecutor, post
from localpdf_insight.web import create_app
from localpdf_insight import core
from verification_support import approving_verifier


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--run', type=Path, required=True)
    args = parser.parse_args()
    path = ROOT/'tests/fixtures/b1-independent/semantic-stress.json'
    manifest = json.loads(path.with_name('semantic-stress-manifest.json').read_text(encoding='utf-8'))
    assert hashlib.sha256(path.read_bytes()).hexdigest() == manifest['sha256']
    cases = json.loads(path.read_text(encoding='utf-8'))
    inventory = [(f"{c['id']}::{scope}::{mode}", c, scope, mode) for c in cases
                 for scope in ('current','selected','library') for mode in ('strict','assisted')]
    run = EvidenceRun(args.run, [i[0] for i in inventory], {i[0]:'fresh' for i in inventory}, manifest)
    old_generate = core.ollama_generate; old_model = os.environ.get('LOCALPDF_MODEL')
    try:
        os.environ['LOCALPDF_MODEL'] = 'controlled-false-verifier-NOT-live'
        def generate(prompt, model, **kwargs):
            sources = json.loads(prompt.split('EVIDENCE JSON:\n',1)[1])
            return json.dumps({'claims':[{'text':s['text'],'source_ids':[s['id']]} for s in sources]})
        core.ollama_generate = generate
        for node, case, scope, mode in inventory:
            started = time.monotonic(); calls = []
            def verify(request):
                result = approving_verifier(request)
                calls.append({'request':request.payload(),'response':result})
                return result
            with tempfile.TemporaryDirectory(prefix='localpdf-semantic-stress-') as tmp:
                app = create_app(tmp, executor=InlineExecutor(), verifier=verify); client = app.test_client()
                docs = import_frozen_case(client, case, combine=scope=='current')
                response = post(client, '/api/ask', {'scope':scope, 'current_id':docs[0]['id'],
                    'document_ids':[d['id'] for d in docs], 'question':case['question'], 'strict':mode=='strict'})
                answer = response.json
                actual = norm(' '.join(c['text'] for c in answer.get('claims',[])))
                expected = norm(' '.join(case['allowed_passages']))
                citations = []
                for claim in answer.get('claims',[]):
                    for sid in claim['source_ids']:
                        source = client.get('/api/sources/'+sid).json
                        span = claim['source_span']
                        ok = source['text'][span['start']:span['end']] == claim['text'] and source['document_id'] in [d['id'] for d in docs] and source['page']==1
                        citations.append({'id':sid,'source':source,'passed':ok})
                passed = response.status_code==200 and actual==expected and all(c['passed'] for c in citations)
                run.record(node, 'fresh', {'case':case, 'scope':scope, 'mode':mode, 'actual_answer':answer,
                    'verifier_type':'available_deliberately_false_approver','verifier_calls':calls,
                    'citation_checks':citations, 'seconds':time.monotonic()-started,
                    'false_acceptance':bool(actual and actual!=expected),'false_refusal':bool(expected and not actual),
                    'passed':passed,'controlled':True,'live_model_evidence':False})
                run.terminal(node, [{'when':'setup','outcome':'passed'},
                    {'when':'call','outcome':'passed' if passed else 'failed'}, {'when':'teardown','outcome':'passed'}])
    finally:
        core.ollama_generate = old_generate
        if old_model is None: os.environ.pop('LOCALPDF_MODEL',None)
        else: os.environ['LOCALPDF_MODEL'] = old_model
    summary = inspect_run(args.run); exclusive(args.run/'summary.json',summary)
    print(json.dumps(summary)); return 0 if summary['validation_passed'] else 1


if __name__ == '__main__': raise SystemExit(main())

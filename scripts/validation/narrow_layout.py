"""Record end-to-end usability cost of conservatively withholding split context."""
import argparse
import io
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tests'))
from evidence_capture import EvidenceRun, inspect_run, exclusive
from test_web import InlineExecutor, post
from verification_support import approving_verifier
from localpdf_insight.web import create_app
from localpdf_insight import core


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',type=Path,required=True);args=parser.parse_args()
    nodes=[(scope,strict) for scope in ('current','selected','library') for strict in (True,False)]
    ids=[f'{s}::{m}' for s,m in nodes]
    run=EvidenceRun(args.run,ids,{i:'fresh' for i in ids},{'purpose':'Safety withholding passes its regression but counts as end-to-end false refusal when the full page is answerable.'})
    def generate(prompt,model,**kwargs):
        sources=json.loads(prompt.split('EVIDENCE JSON:\n',1)[1])
        return json.dumps({'claims':[{'text':s['text'],'source_ids':[s['id']]} for s in sources]})
    old=core.ollama_generate;old_model=os.environ.get('LOCALPDF_MODEL')
    try:
        core.ollama_generate=generate;os.environ['LOCALPDF_MODEL']='controlled-NOT-live'
        for (scope,strict),node in zip(nodes,ids):
            with tempfile.TemporaryDirectory(prefix='localpdf-narrow-probe-') as data:
                client=create_app(data,executor=InlineExecutor(),verifier=approving_verifier).test_client()
                raw=(ROOT/'docs/b1-independent/arabic-qualification-original.pdf').read_bytes()
                document=client.post('/api/import',data={'file':(io.BytesIO(raw),'تأهيل.pdf')},headers={'X-LocalPDF':'1'}).json['document']
                question='كم بلغ صافي ربح ليريك لعام 2037؟'
                answer=post(client,'/api/ask',{'scope':scope,'current_id':document['id'],'document_ids':[document['id']],
                    'strict':strict,'question':question}).json
                safety=not answer['claims'] and any('qualification_crosses_source_boundary' in v['reasons'] for p in answer['grounding']['parts'] for v in p['vetoes'])
                passed=bool(answer['claims'])  # End-to-end answerability, not just safe abstention.
                run.record(node,'fresh',{'question':question,'scope':scope,'strict':strict,'full_page_answerable':True,
                    'actual_answer':answer,'safe_withholding_passed':safety,'false_refusal':not passed,
                    'false_acceptance':False,'passed':passed,'live_model_evidence':False})
                run.terminal(node,[{'when':'setup','outcome':'passed'},{'when':'call','outcome':'passed' if passed else 'failed'},{'when':'teardown','outcome':'passed'}])
    finally:
        core.ollama_generate=old
        if old_model is None:os.environ.pop('LOCALPDF_MODEL',None)
        else:os.environ['LOCALPDF_MODEL']=old_model
    summary=inspect_run(args.run);exclusive(args.run/'summary.json',summary);print(json.dumps(summary))
    return 0 if summary['validation_passed'] else 1


if __name__=='__main__':raise SystemExit(main())

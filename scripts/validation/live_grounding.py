"""Actual loopback Ollama gate; never substitutes controlled/excerpt responses."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import tempfile
import time
import urllib.request
from dataclasses import dataclass, field

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tests'))
from grounding_support import CASES,case_data,import_case
from relevance_matrix_support import NAMES,scenario
from test_web import InlineExecutor,post
from localpdf_insight.web import create_app
from localpdf_insight.core import _LocalOnlyRedirect
from localpdf_insight.verification import OllamaVerifier

EXPECTED='357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b'
LIVE_CASES=[n for n in NAMES if n not in {'invented_amount','invented_date','compromised_generation',
    'false_verifier_approval','timeout','malformed','unavailable'}]


@dataclass(frozen=True)
class RecordingVerifier(OllamaVerifier):
    records: list = field(default_factory=list,compare=False)

    def __call__(self,request):
        entry={'request':request.payload(),'request_sha256':request.fingerprint()}
        self.records.append(entry)
        try:
            result=super().__call__(request);entry['raw_response']=result;return result
        except Exception as exc:
            entry['failure']=type(exc).__name__;raise


def preserve_pdfs(client,documents,directory):
    directory.mkdir(parents=True,exist_ok=True)
    files=[]
    for doc in documents:
        response=client.get('/api/documents/'+doc['id']+'/pdf')
        if response.status_code!=200:raise RuntimeError('Cannot preserve cited fixture PDF')
        digest=hashlib.sha256(response.data).hexdigest()
        path=directory/(digest+'.pdf');path.write_bytes(response.data)
        files.append({'document_id':doc['id'],'sha256':digest,'path':str(path)})
    return files

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--model',default='qwen2.5:3b');parser.add_argument('--digest',default=EXPECTED)
    parser.add_argument('--case',choices=NAMES,action='append')
    parser.add_argument('--suite',choices=['baseline','boundary'],default='boundary');args=parser.parse_args()
    permitted=LIVE_CASES if args.suite=='boundary' else CASES
    if args.case and any(name not in permitted for name in args.case):
        parser.error('Selected case requires a controlled response or belongs to another suite; it is not a live data case in this suite')
    report={'status':'UNVERIFIED','model':args.model,'expected_digest':args.digest,
        'actual_model_digest':None,'parameters':{'temperature':0.1,'num_predict':1024,'format':'json','stream':False},
        'platform':platform.platform(),'controlled_responses':False,'manual_page_review':'NOT_PERFORMED',
        'full_matrix_requested':not bool(args.case),'suite':args.suite,'cases':[],
        'verifier':{'model':os.environ.get('LOCALPDF_VERIFY_MODEL',args.model),'actual_model_digest':None,
            'transport':'loopback /api/chat; independent of generation callback',
            'parameters':{'temperature':0,'num_predict':2048,'format':'json','stream':False,'timeout_seconds':30},
            'same_model_weights':True,'semantic_independence_claimed':False}}
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),_LocalOnlyRedirect())
    try:
        def fetch(endpoint):
            with opener.open('http://127.0.0.1:11434'+endpoint,timeout=5) as response:
                return json.loads(response.read().decode('utf-8'))
        report['runtime']=fetch('/api/version');tags=fetch('/api/tags')
        model=next(m for m in tags['models'] if m['name']==args.model)
        report['actual_model_digest']=model['digest']
        if model['digest']!=args.digest:raise ValueError('Installed model digest differs from the release gate target')
        if report['verifier']['model']!=args.model:
            raise ValueError('This release gate targets the pinned model for both transports; a different verifier requires a separately recorded model gate')
        report['verifier']['actual_model_digest']=model['digest']
    except Exception as exc:
        report['reason']=f'{type(exc).__name__}: {exc}'
        write(args.output,report);print('UNVERIFIED: actual release Ollama runtime/model unavailable or mismatched.');return 3
    os.environ['LOCALPDF_MODEL']=args.model
    for name in (args.case or (LIVE_CASES if args.suite=='boundary' else CASES)):
        for language in ['en','ar']:
            for scope in ['current','selected','library']:
                for strict in [True,False]:
                    case=scenario(name,language,strict) if args.suite=='boundary' else case_data(name,language)
                    with tempfile.TemporaryDirectory(prefix='localpdf-live-gate-') as tmp:
                        verifier=RecordingVerifier(args.model)
                        app=create_app(tmp,executor=InlineExecutor(),verifier=verifier);client=app.test_client()
                        docs=import_case(client,case,combine=scope=='current')
                        fixtures=preserve_pdfs(client,docs,args.output.parent/'live-fixtures')
                        started=time.monotonic()
                        response=post(client,'/api/ask',{'scope':scope,'current_id':docs[0]['id'],'document_ids':[d['id'] for d in docs],
                            'question':case['question'],'strict':strict})
                        answer=response.json
                        absent=(case['expected'] not in {'SUPPORTED','PARTIAL','CONFLICTING'} if args.suite=='boundary'
                                else name in {'absent','nonresponsive','invented_obligation'})
                        provisional=(response.status_code==200 and bool(answer.get('claims'))!=absent
                                     and answer.get('mode')!='error'
                                     and answer.get('grounding',{}).get('status')!='review_failed')
                        citations=[]
                        for claim in answer.get('claims',[]):
                            for source_id in claim['source_ids']:
                                resolved=client.get('/api/sources/'+source_id)
                                span=claim.get('source_span',{})
                                a,b=span.get('start'),span.get('end')
                                ok=(resolved.status_code==200 and type(a) is int and type(b) is int
                                    and 0<=a<b<=len(resolved.json['text'])
                                    and resolved.json['text'][a:b]==claim['text']
                                    and resolved.json['document_id'] in [d['id'] for d in docs]
                                    and 1<=resolved.json['page']<=len(case['documents'])
                                    and client.get('/api/documents/'+resolved.json['document_id']+'/pdf').status_code==200)
                                provisional &= ok
                                citations.append({'id':source_id,'resolved':resolved.json,'server_mapping_passed':ok})
                        if name in {'partial','mixed_claims'}:provisional &= answer.get('grounding',{}).get('status')=='partial'
                        if name=='conflict':provisional &= answer.get('grounding',{}).get('status')=='conflict'
                        record={'case':name,'language':language,'scope':scope,'strict':strict,'fixture':case,
                            'pdf_revisions':[d['revision'] for d in docs],'question':case['question'],'expected':'refusal' if absent else 'supported answer',
                            'actual_answer':answer,'cited_evidence':citations,'seconds':time.monotonic()-started,
                            'fixture_files':fixtures,'verifier_calls':verifier.records,
                            'false_acceptance':bool(answer.get('claims')) and absent,
                            'false_refusal':not bool(answer.get('claims')) and not absent,
                            'automated_contract_passed':bool(provisional),'manual_fact_page_review':'PENDING'}
                        report['cases'].append(record);write(args.output,report)
    # Reports and selected-text actions share the release boundary; separately
    # record their real output for manual review rather than infer a pass.
    with tempfile.TemporaryDirectory(prefix='localpdf-live-report-') as tmp:
        verifier=RecordingVerifier(args.model)
        app=create_app(tmp,executor=InlineExecutor(),verifier=verifier);client=app.test_client();case=case_data('answerable','en');docs=import_case(client,case)
        fixtures=preserve_pdfs(client,docs,args.output.parent/'live-fixtures')
        report['generated_reports']=[]
        for operation in ['Executive summary','Key numbers','Obligations']:
            verifier.records.clear()
            result=post(client,'/api/ask',{'scope':'current','current_id':docs[0]['id'],'question':operation,'operation':operation,'strict':False}).json
            report['generated_reports'].append({'operation':operation,'actual_answer':result,
                'fixture_files':fixtures,'verifier_calls':list(verifier.records),
                'expected':'refusal: no obligation in fixture' if operation=='Obligations' else 'supported source extracts',
                'manual_fact_page_review':'PENDING'})
    report['status']='FAILED' if any(not c['automated_contract_passed'] for c in report['cases']) else 'PENDING_MANUAL_PAGE_REVIEW'
    write(args.output,report);print(report['status']);return 1 if report['status']=='FAILED' else 2

if __name__=='__main__':raise SystemExit(main())

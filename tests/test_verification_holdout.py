"""Unseen value/name/wording variations first run after the recorded code freeze.

This is controlled falsification, not independent model accuracy measurement.
"""
import hashlib
import json
import os
from pathlib import Path
import random
import pytest
from test_web import app,post
from grounding_support import import_case
from verification_support import approving_verifier


@pytest.mark.parametrize('scope',['current','selected','library'])
@pytest.mark.parametrize('strict',[True,False])
@pytest.mark.parametrize('language',['en','ar'])
@pytest.mark.parametrize('variant',range(8))
def test_held_out_variations(app,monkeypatch,scope,strict,language,variant):
    import localpdf_insight.core as core
    ar=language=='ar';rng=random.Random(918706+variant)
    name=(['سديم','واحة','منار','نخيل','مدار'] if ar else ['Kestrel','Lyra','Meridian','Sequoia','Cedar'])[variant%5]
    other='سارية' if ar else 'Vela'
    year=rng.choice([2027,2028,2029,2032,2033,2035,2037])
    amount=rng.randrange(17,971)
    q=f'كم بلغ صافي ربح {name} لعام {year}؟' if ar else f'What was the net profit of {name} for {year}?'
    text=f'بلغ صافي ربح {name} لعام {year} مبلغ {amount} مليون درهم.' if ar else f'The net profit of {name} for {year} was AED {amount} million.'
    expected=variant%2==0
    if variant==0:
        q=f'كم كسبت {name} في عام {year}؟' if ar else f'How much money did {name} earn in {year}?'
    if variant==1:q=q.replace('net profit','operating profit').replace('صافي ربح','الربح التشغيلي')
    if variant==2:q=f'ما مقدار الدخل الصافي لشركة {name} عام {year}؟' if ar else f'How large were {name}\'s net earnings in {year}?'
    if variant==3:q=q.replace(name,other)
    if variant==4:
        q=f'ما الدخل الإجمالي لشركة {name} لعام {year}؟' if ar else f'What were the gross earnings of {name} for {year}?'
        text=text.replace('net profit','gross profit').replace('صافي ربح','إجمالي ربح')
    if variant==5:q=q.replace(str(year),str(year+1))
    if variant in {6,7}:
        value=(amount if variant==6 else amount+4)*1000000
        q=f'اشرح صافي ربح {name} لعام {year} البالغ {value} درهم.' if ar else f'Explain the net profit of {name} for {year} of AED {value}.'
    case={'case':'holdout-'+str(variant),'language':language,'question':q,'documents':[text]}
    client=app.test_client();docs=import_case(client,case)
    calls=[]
    def generate(prompt,model,**kw):
        sources=json.loads(prompt.split('EVIDENCE JSON:\n',1)[1])
        return json.dumps({'claims':[{'text':s['text'],'source_ids':[s['id']]} for s in sources]})
    def approve(request):
        response=approving_verifier(request);calls.append({'request':request.payload(),'response':response})
        return response
    monkeypatch.setenv('LOCALPDF_MODEL','holdout-controlled-NOT-live')
    monkeypatch.setattr(core,'ollama_generate',generate);app.extensions['insight']['verifier']=approve
    response=post(client,'/api/ask',{'scope':scope,'current_id':docs[0]['id'],'document_ids':[d['id'] for d in docs],
        'question':q,'strict':strict});result=response.json
    cited=[]
    for claim in result.get('claims',[]):
        s=client.get('/api/sources/'+claim['source_ids'][0]).json
        cited.append(s['text']==claim['text'] and s['document_id']==docs[0]['id'] and s['page']==1)
    released=bool(result.get('claims'));passed=response.status_code==200 and released==expected and all(cited)
    record={'case':case,'scope':scope,'strict':strict,'expected_release':expected,'actual_answer':result,
        'verifier_calls':calls,'citation_checks':cited,'passed':bool(passed),'controlled':True,'live_model_evidence':False,
        'false_acceptance':released and not expected,'false_refusal':not released and expected,
        'implementation_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__).parents[1]/'src/localpdf_insight').glob('*.py') if p.name in {'constraints.py','verification.py','grounding.py','evidence.py','web.py'}}}
    from evidence_capture import capture
    capture('variations', record)
    assert passed,record

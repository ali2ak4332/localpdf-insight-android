"""Frozen counterexamples labelled before fixes; controlled, not live evidence."""
import hashlib
import html
import io
import json
import re
from pathlib import Path
import pytest
import fitz
from test_web import app,post
from localpdf_insight.verification import question_spans,units
from evidence_capture import capture

ROOT=Path(__file__).parent/'fixtures/b1-independent'
CORPUS=json.loads((ROOT/'corpus.json').read_text(encoding='utf-8'))
MANIFEST=json.loads((ROOT/'manifest.json').read_text(encoding='utf-8'))

def norm(text):
    # PDF glyph runs may put whitespace immediately before terminal punctuation.
    # Do not normalize words, numbers, internal decimals or factual qualifiers.
    return re.sub(r'\s+([.!?؟؛;])$',r'\1',re.sub(r'\s+',' ',text).strip())


def import_frozen_case(client,case,combine):
    # These cases explicitly test multiple facts within ONE source chunk.
    # A wide page avoids Arabic layout splitting that changes that precondition.
    # All frozen text and expected outcomes remain unchanged; assert the actual
    # PDF layer equals the fixture and is one layout block before importing it.
    docs=[]
    for n,paragraphs in enumerate([case['documents']] if combine else [[t] for t in case['documents']]):
        with fitz.open() as pdf:
            for text in paragraphs:
                page=pdf.new_page(width=2000,height=400)
                if case['language']=='ar':
                    page.insert_htmlbox(fitz.Rect(30,30,1950,260),'<p dir="rtl">'+html.escape(text)+'</p>',css='* {font-size:18px;}')
                    for xref in page.get_contents():
                        pdf.update_stream(xref,b'/Span << /ActualText <FEFF'+text.encode('utf-16-be').hex().encode()+b'> >> BDC\n'+pdf.xref_stream(xref)+b'\nEMC')
                else:page.insert_textbox(fitz.Rect(30,30,1950,260),text,fontsize=12)
                assert norm(page.get_text())==norm(text)
                assert len(page.get_text('blocks'))==1
            data=pdf.tobytes()
        response=client.post('/api/import',data={'file':(io.BytesIO(data),f'frozen-{n}.pdf')},headers={'X-LocalPDF':'1'})
        assert response.status_code==200,response.json
        docs.append(response.json['document'])
    return docs


def test_corpus_is_frozen():
    assert hashlib.sha256((ROOT/'corpus.json').read_bytes()).hexdigest()==MANIFEST['corpus_sha256']
    assert len(CORPUS)==MANIFEST['unique_scenarios']==48


@pytest.mark.parametrize('case',CORPUS,ids=lambda c:c['id'])
@pytest.mark.parametrize('strict',[True,False])
@pytest.mark.parametrize('scope',['current','selected','library'])
def test_frozen_adversarial_corpus(app,monkeypatch,case,strict,scope):
    import localpdf_insight.core as core
    client=app.test_client()
    try:docs=import_frozen_case(client,case,combine=scope=='current')
    except Exception as exc:
        capture('fresh',{'case':case,'scope':scope,'strict':strict,'passed':False,
                        'application_executed':False,'fixture_error':str(exc),
                        'actual_answer':None,'false_acceptance':False,'false_refusal':False,
                        'live_model_evidence':False})
        raise
    exchanges=[];generation=[]
    def generate(prompt,model,**kwargs):
        evidence=json.loads(prompt.split('EVIDENCE JSON:\n',1)[1]);generation.append(evidence)
        return json.dumps({'claims':[{'text':e['text'],'source_ids':[e['id']]} for e in evidence],
                           'checks':{'all':True},'grounding':{'classification':'SUPPORTED'}})
    def verify(request):
        sources=request.sources
        target=norm(case['documents'][0]);ordered=sorted(sources,key=lambda s:0 if norm(s.text)==target else 1)
        refs=[{'source_id':s.id,'unit':n} for s in ordered for n,_ in enumerate(units(s.text))]
        if case['verifier']=='first':refs=refs[:1]
        if case['verifier']=='absent':refs=[]
        ids=list(dict.fromkeys(r['source_id'] for r in refs))
        result=json.dumps({'parts':[{'start':a,'end':b,'status':'absent' if case['verifier']=='absent' else 'supported',
                                    'source_ids':ids,'witnesses':refs} for a,b in question_spans(request.question)]})
        exchanges.append({'request':request.payload(),'response':result});return result
    app.extensions['insight']['verifier']=verify
    monkeypatch.setattr(core,'ollama_generate',generate)
    monkeypatch.setenv('LOCALPDF_MODEL','independent-review-controlled-NOT-live')
    body={'scope':scope,'current_id':docs[0]['id'],'document_ids':[d['id'] for d in docs],
          'question':case['question'],'operation':case['operation'],'strict':strict}
    if case['family']=='selected_passage':
        body['selection']={'document_id':docs[0]['id'],'page':1,'text':case['allowed_passages'][0]}
    response=post(client,'/api/ask',body);actual=response.json
    allowed=[norm(t) for t in case['allowed_passages']]
    claims=[norm(c['text']) for c in actual.get('claims',[])]
    citation_checks=[]
    for claim in actual.get('claims',[]):
        for sid in claim['source_ids']:
            resolved=client.get('/api/sources/'+sid)
            s=resolved.json if resolved.status_code==200 else {}
            valid=(resolved.status_code==200 and norm(claim['text']) in norm(s.get('text','')) and
                   s.get('document_id') in [d['id'] for d in docs] and 1<=s.get('page',0)<=len(case['documents'])
                   and client.get('/api/documents/'+s['document_id']+'/pdf').status_code==200)
            citation_checks.append({'source_id':sid,'passed':bool(valid),'resolved':s})
    reopened=None;reopen_ok=True
    if actual.get('saved_id'):
        saved=client.get('/api/studio/'+actual['saved_id']);reopened=saved.json
        reopen_ok=saved.status_code==200 and reopened['content']['claims']==actual['claims']
        for claim in actual['claims']:
            for sid in claim['source_ids']:
                rr=client.get('/api/studio/'+actual['saved_id']+'/sources/'+sid)
                reopen_ok &= rr.status_code==200 and norm(claim['text']) in norm(rr.json['text'])
    # Grouped or separate quotes are equivalent only when their complete text
    # equals the ordered permitted evidence. No extra fact or lost qualification.
    actual_text=norm(' '.join(claims));expected_text=norm(' '.join(allowed))
    unexpected=[actual_text] if actual_text and actual_text!=expected_text else []
    missing=[expected_text] if expected_text and actual_text!=expected_text else []
    false_accept=bool(unexpected or claims and not allowed or case['expected']=='CONFLICTING' and claims and actual.get('grounding',{}).get('classification')!='CONFLICTING')
    false_refusal=bool(allowed and not claims)
    passed=(response.status_code==200 and not unexpected and not missing and
            actual.get('grounding',{}).get('classification')==case['expected'] and all(x['passed'] for x in citation_checks) and reopen_ok)
    record={'case':case,'scope':scope,'strict':strict,'actual_answer':actual,'verifier_type':case['verifier'],
            'generation_calls':generation,'verifier_calls':exchanges,'citation_checks':citation_checks,'reopened':reopened,
            'unexpected_passages':unexpected,'missing_passages':missing,'false_acceptance':false_accept,
            'false_refusal':false_refusal,'passed':bool(passed),'live_model_evidence':False}
    capture('fresh',record)
    assert passed,record

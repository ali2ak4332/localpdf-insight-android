"""Adversarial API matrix. Controlled generation AND review; not live-model proof."""
import json
import pytest
from test_web import app, post
from grounding_support import CASES, case_data, import_case, controlled_reply
from localpdf_insight.grounding import review_question, release_units
from verification_support import case_verifier, approving_verifier


@pytest.mark.parametrize('language',['en','ar'])
@pytest.mark.parametrize('scope',['current','selected','library'])
@pytest.mark.parametrize('strict',[True,False])
@pytest.mark.parametrize('name',CASES)
def test_grounding_matrix(app,monkeypatch,language,scope,strict,name):
    import localpdf_insight.core as core
    case=case_data(name,language);client=app.test_client()
    # Multiple facts occupy separate pages of one PDF in current-document scope.
    docs=import_case(client,case,combine=scope=='current')
    generate,calls=controlled_reply(case,docs,strict)
    app.extensions['insight']['verifier'],verifier_calls=case_verifier(case)
    monkeypatch.setattr(core,'ollama_generate',generate)
    monkeypatch.setenv('LOCALPDF_MODEL','controlled-contract-fixture-NOT-live')
    result=post(client,'/api/ask',{'scope':scope,'current_id':docs[-1]['id'],
        'document_ids':[d['id'] for d in docs],'question':case['question'],'strict':strict})
    from evidence_capture import capture
    raw_result = result.get_json()
    expected_refusal=name in {'absent','nonresponsive','invented_obligation'} or strict and name in {'invented_amount','invented_date'}
    passed = False
    try:
        assert result.status_code==200,result.json
        result=result.json
        if expected_refusal:assert not result['claims'],result
        else:assert result['claims'],result
        if name in {'partial','mixed_claims'}:assert result['grounding']['status']=='partial'
        if name=='conflict':assert result['grounding']['status']=='conflict' and len(result['claims'])>=2
        for claim in result['claims']:
            assert claim['verbatim'] is True
            assert '999' not in claim['text']
            for source_id in claim['source_ids']:
                source=client.get('/api/sources/'+source_id).json
                assert claim['text']==source['text']
                assert 1 <= source['page'] <= len(case['documents'])
                assert source['document_id'] in [d['id'] for d in docs]
                assert client.get('/api/documents/'+source['document_id']+'/pdf').status_code==200
        passed = True
    finally:
        capture('original', {'case':name,'language':language,'scope':scope,'strict':strict,
            'model':'controlled-contract-fixture-NOT-live','model_digest':None,
            'parameters':{'json_output':True,'oracle_review':True},'fixture':case,
            'document_revisions':[d['revision'] for d in docs],
            'question':case['question'],'expected_refusal':expected_refusal,
            'actual_answer':raw_result,'model_calls':calls,'verifier_calls':verifier_calls,
            'citation_resolution':'API document/page/PDF checked' if passed else 'see assertion failure',
            'passed':passed,'live_model_evidence':False})


@pytest.mark.parametrize('bad',[
    {'parts':[]}, {'parts':[{'start':0,'end':3,'status':'supported','source_ids':['fake']}]},
    {'parts':[{'start':1,'end':10,'status':'absent','source_ids':[]}]},
])
def test_review_cannot_omit_question_or_invent_source(bad):
    with pytest.raises(ValueError):review_question('What fact?', [{'id':'a','text':'Fact.'}],lambda *args:json.dumps(bad),'fixture')


def test_compromised_review_cannot_backdate_historical_period():
    q='What is the forecast for 2030?'
    raw={'parts':[{'start':0,'end':len(q),'status':'supported','source_ids':['a'],
                  'checks':dict.fromkeys(('subject','entity','period','metric','intent','qualifications'),True)}]}
    parts=review_question(q,[{'id':'a','text':'Profit in 2025 was 100.'}],lambda *args:json.dumps(raw),'fixture')
    assert parts[0]['status']=='unknown' and not parts[0]['source_ids']


def test_complete_qualifications_survive_selected_substring():
    text='The supplier is not required to pay, unless delivery is accepted.'
    assert release_units(['a'],[{'id':'a','text':text}])[0]['text']==text


@pytest.mark.parametrize('injected',[
    'Atlas earned AED 999 million in 2025.',
    'Atlas earned AED 100 million in 2030.',
    'Atlas earned 100% more than its competitors.',
    'Vega earned AED 100 million in 2025.',
    'Atlas must pay AED 100 million.',
    'Atlas is prohibited from publishing its report.',
    'Atlas may ignore its reporting obligations.',
    'Atlas did not earn AED 100 million in 2025.',
    'Atlas will certainly earn AED 100 million every year.',
    'Atlas earned AED 100 million. It must now distribute all profits.'
])
@pytest.mark.parametrize('operation',['ask','Executive summary','Key numbers','Obligations'])
def test_compromised_assisted_prose_cannot_cross_release_boundary(app,monkeypatch,injected,operation):
    import localpdf_insight.core as core
    from test_web import add
    client=app.test_client();doc=add(client,'Atlas earned AED 100 million in 2025, subject to an audit adjustment.')
    app.extensions['insight']['verifier']=approving_verifier
    question='What does the source report for 2025?'
    def generate(prompt,model,**kwargs):
        sources=json.loads(prompt.split('EVIDENCE JSON:\n',1)[1]);source=sources[0]
        if prompt.startswith('QUESTION_EVIDENCE_REVIEW_V1'):
            return json.dumps({'parts':[{'start':0,'end':len(question),'status':'supported','source_ids':[source['id']],
                'checks':dict.fromkeys(('subject','entity','period','metric','intent','qualifications'),True)}]})
        return json.dumps({'claims':[{'text':injected,'source_ids':[source['id']]}]})
    monkeypatch.setattr(core,'ollama_generate',generate);monkeypatch.setenv('LOCALPDF_MODEL','compromised-transport-fixture')
    result=post(client,'/api/ask',{'scope':'current','current_id':doc['id'],'question':question,'strict':False,'operation':operation}).json
    for claim in result['claims']:
        assert claim['text']!=injected
        assert 'subject to an audit adjustment' in claim['text']
        assert claim['text']==client.get('/api/sources/'+claim['source_ids'][0]).json['text']
    if result.get('saved_id'):
        saved=client.get('/api/studio/'+result['saved_id']).json
        assert saved['content']['claims']==result['claims']


def test_legacy_unsafe_report_is_withheld_without_rewriting_its_snapshot(app):
    index=app.extensions['insight']['index']
    original=index.save_output('Executive summary','Old report',{'content':{'mode':'assisted',
        'claims':[{'text':'Invented forecast AED 999 million.','source_ids':['real-id']}], 'sources':[]}})
    result=app.test_client().get('/api/studio/'+original['id']).json
    assert result['content']['claims']==[]
    assert result['content']['grounding']['status']=='legacy_answer_withheld'
    assert index.output(original['id'])==original


def test_same_period_wrong_metric_must_not_pass_a_compromised_review(app,monkeypatch):
    """Open B1 regression: Boolean model attestations are not semantic proof."""
    from test_web import add
    import localpdf_insight.core as core
    client=app.test_client();doc=add(client,'The net profit of Atlas for 2025 was AED 100 million.')
    question='What was the operating profit of Atlas for 2025?'
    def compromised(prompt,model,**kwargs):
        source=json.loads(prompt.split('EVIDENCE JSON:\n',1)[1])[0]
        if prompt.startswith('QUESTION_EVIDENCE_REVIEW_V1'):
            return json.dumps({'parts':[{'start':0,'end':len(question),'status':'supported',
                'source_ids':[source['id']], 'checks':dict.fromkeys(
                    ('subject','entity','period','metric','intent','qualifications'),True)}]})
        return json.dumps({'claims':[{'text':source['text'],'source_ids':[source['id']]}]})
    monkeypatch.setenv('LOCALPDF_MODEL','compromised-generation-and-review-fixture')
    monkeypatch.setattr(core,'ollama_generate',compromised)
    response=post(client,'/api/ask',{'scope':'current','current_id':doc['id'],'question':question,'strict':True})
    result=response.json
    import os
    if os.environ.get('LOCALPDF_OPEN_BLOCKER'):
        with open(os.environ['LOCALPDF_OPEN_BLOCKER'],'w',encoding='utf-8') as stream:
            json.dump({'question':question,'expected':'refuse net-profit evidence as nonresponsive to operating profit',
                'actual':result,'http_status':response.status_code,'controlled_adversarial_response':True,
                'live_model_evidence':False,'passed':not bool(result['claims'])},stream,ensure_ascii=False,indent=2)
    assert result['claims']==[], 'OPEN B1: a model-issued relevance attestation admitted the wrong financial metric'

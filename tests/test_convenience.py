"""Scope, persistence and grounding contracts; model doubles are labelled explicitly."""
import json
from pathlib import Path
import pytest
from test_web import app, add, post, InlineExecutor, pdf_bytes
from localpdf_insight.web import create_app
from localpdf_insight.convenience import TEMPLATES, suggested_questions


def body(doc, **extra):
    return {'scope':'current','current_id':doc['id'],'question':'Executive summary',**extra}


def model_reply(monkeypatch, factory):
    """An adversarial transport double, never presented as live Ollama validation."""
    import localpdf_insight.core as core
    monkeypatch.setenv('LOCALPDF_MODEL','test-double')
    def generate(prompt, model, **kwargs):
        assert kwargs['json_output'] is True
        evidence=json.loads(prompt.split('EVIDENCE JSON:\n',1)[1])
        return json.dumps(factory(evidence,prompt),ensure_ascii=False)
    monkeypatch.setattr(core,'ollama_generate',generate)
    # Independent verifier injection; the generator factory cannot issue approval.
    import localpdf_insight.verification as verification
    from verification_support import approving_verifier
    monkeypatch.setattr(verification,'configured_verifier',lambda model: approving_verifier)


def test_suggestions_content_scope_and_no_generic_padding(app):
    client=app.test_client()
    a=add(client,'Supplier payment obligations require 30 days notice.\n\nInsurance coverage protects equipment against damage.')
    b=add(client,'Secret pineapple shipment requires refrigeration.','secret.pdf')
    result=post(client,'/api/suggestions',body(a)).json
    assert result['questions'] and result['scope']==[a['id']]
    assert 'Supplier' in str(result) and 'pineapple' not in str(result)
    for suggestion in result['questions']:
        for source_id in suggestion['source_ids']:
            assert client.get('/api/sources/'+source_id).json['document_id']==a['id']
    assert len(result['questions'])<=6
    assert post(client,'/api/suggestions',{'scope':'selected','document_ids':[]}).status_code==400
    selected=post(client,'/api/suggestions',{'scope':'selected','document_ids':[b['id']]}).json
    assert 'pineapple' in str(selected) and 'Supplier' not in str(selected)
    library=post(client,'/api/suggestions',{'scope':'library'}).json
    assert set(library['scope'])=={a['id'],b['id']}
    assert 'Supplier' in str(library) and 'pineapple' in str(library)


def test_six_distinct_arabic_source_questions_and_mixed_text():
    chunks=[{'id':str(n),'document_id':'arabic','text':text,'heading':''} for n,text in enumerate([
        'يلتزم المورد بتسليم المعدات في الموعد المحدد.', 'تبلغ قيمة العقد ٢٥٠٠٠ درهم.',
        'تغطي وثيقة التأمين أضرار المعدات.', 'يُرسل إشعار الإنهاء قبل ثلاثين يوماً.',
        'تعني الخدمة توفير دعم فني متواصل.', 'يجب حفظ بيانات API داخل الشركة.'
    ])]
    suggestions=suggested_questions(chunks,['arabic'])
    assert len(suggestions)==6
    assert all(q['question'].startswith('ماذا يوضح') for q in suggestions)
    assert '٢٥٠٠٠' in str(suggestions) and 'API' in str(suggestions)
    assert {q['source_ids'][0] for q in suggestions}=={str(i) for i in range(6)}


@pytest.mark.parametrize('operation', list(TEMPLATES))
def test_templates_use_same_validated_evidence_and_save(app,monkeypatch,operation):
    client=app.test_client();a=add(client,'The supplier must pay AED 25000 on 12 January 2027. Risk of delay carries a penalty. Supplier means the service provider.')
    add(client,'Secret pineapple costs 900000 dollars.','unselected.pdf')
    seen=[]
    def reply(evidence,prompt):
        seen.append(prompt)
        return {'claims':[{'text':evidence[0]['text'],'source_ids':[evidence[0]['id']]}]} if evidence else {'claims':[]}
    model_reply(monkeypatch,reply)
    response=post(client,'/api/ask',body(a,operation=operation)).json
    assert response['claims'] and response['saved_id']
    assert 'pineapple' not in seen[0]
    saved=client.get('/api/studio/'+response['saved_id']).json
    assert saved['kind']==operation and saved['scope']['documents'][0]['id']==a['id']
    for claim in saved['content']['claims']:
        for source_id in claim['source_ids']:
            source=client.get(f"/api/studio/{saved['id']}/sources/{source_id}").json
            assert source['document_id']==a['id'] and source['page']==1 and claim['text'] in source['text']
    assert response['coverage']['partial']


@pytest.mark.parametrize('bad', ['invented_text','invented_id','out_of_scope'])
def test_reports_and_study_refuse_unsupported_claims(app,monkeypatch,bad):
    client=app.test_client();a=add(client,'The supplier must pay AED 25000 within 30 days.')
    b=add(client,'The secret contract costs AED 900000.','secret.pdf')
    secret=app.extensions['insight']['index'].all_chunks([b['id']])[0]
    def reply(evidence,prompt):
        text='The supplier must pay AED 999999.' if bad=='invented_text' else evidence[0]['text']
        source_id='made-up' if bad=='invented_id' else secret['id'] if bad=='out_of_scope' else evidence[0]['id']
        return {'claims':[{'text':text,'source_ids':[source_id]}]}
    model_reply(monkeypatch,reply)
    for operation in ('Executive summary','Quiz','Flashcards'):
        # Study exercises require exact source answers even if assisted is requested.
        result=post(client,'/api/ask',body(a,operation=operation,strict=operation=='Executive summary')).json
        assert result['claims']==[] and not result.get('cards')
        assert 'sufficient evidence' in result['message']


def test_saved_snapshot_survives_restart_rename_reindex_and_new_version(app,tmp_path):
    client=app.test_client();a=add(client,'Termination requires thirty days written notice.')
    result=post(client,'/api/ask',body(a,operation='Executive summary')).json
    saved=client.get('/api/studio/'+result['saved_id']).json
    source=saved['content']['sources'][0]
    client.patch('/api/documents/'+a['id'],json={'title':'New title'},headers={'X-LocalPDF':'1'})
    # The old source is deliberately removed from the live index; the PDF is unchanged.
    index=app.extensions['insight']['index'];index.begin(a['id'],a['revision'],1);index.finish(a['id'])
    restarted=create_app(tmp_path,executor=InlineExecutor()).test_client()
    assert restarted.get('/api/studio/'+saved['id']).json==saved
    assert restarted.get(f"/api/studio/{saved['id']}/sources/{source['id']}").json==source
    post(restarted,'/api/documents/'+a['id']+'/index',{})
    newer=post(restarted,'/api/ask',body(a,operation='Executive summary')).json
    assert newer['saved_id']!=saved['id']
    assert restarted.get('/api/studio/'+saved['id']).json==saved
    path=Path(app.extensions['insight']['library'][a['id']]['path']);path.write_bytes(pdf_bytes('Changed PDF.'))
    assert restarted.get(f"/api/studio/{saved['id']}/sources/{source['id']}").status_code==409
    assert restarted.get('/api/studio/'+saved['id']).json==saved


def test_selection_and_notes_preserve_provenance_and_optional_comment(app,tmp_path):
    client=app.test_client();a=add(client,'Termination requires thirty days written notice.')
    selection={'document_id':a['id'],'page':1,'text':'thirty days written notice.','bbox':[.1,.1,.8,.2]}
    response=post(client,'/api/ask',body(a,question='Explain',operation='Explain',selection=selection)).json
    assert response['selection']['text']==selection['text'] and response['selection']['bbox']==selection['bbox']
    assert response['selection']['source_ids']
    saved=post(client,'/api/notes',body(a,selection=selection,comment='Check notice date / تحقّق من التاريخ')).json
    reopened=create_app(tmp_path,executor=InlineExecutor()).test_client().get('/api/studio/'+saved['id']).json
    assert reopened['content']['selection']==response['selection']
    assert reopened['content']['comment'].endswith('تحقّق من التاريخ')
    source=reopened['content']['sources'][0]
    citation=client.get(f"/api/studio/{saved['id']}/sources/{source['id']}").json
    assert citation['document_id']==a['id'] and citation['page']==1
    assert client.get(f"/api/studio/{saved['id']}/sources/not-in-output").status_code==404


@pytest.mark.parametrize('change', [{'text':''},{'page':0},{'page':True},{'bbox':[0,0,2,1]},{'bbox':[.8,.2,.1,.4]}])
def test_note_invalid_selections_rejected(app,change):
    client=app.test_client();a=add(client,'Supplier must pay within 30 days.')
    selection={'document_id':a['id'],'page':1,'text':'Supplier must pay',**change}
    assert post(client,'/api/notes',body(a,selection=selection)).status_code in (400,409)
    assert not client.get('/api/studio').json['outputs']


def test_arabic_report_language_and_study_grounding(app,monkeypatch):
    client=app.test_client();a=add(client,'Placeholder Arabic document.')
    index=app.extensions['insight']['index'];index.begin(a['id'],a['revision'],1)
    text='يلتزم المورد بدفع ٢٥٠٠٠ درهم مقابل خدمة API خلال ثلاثين يوماً.'
    index.put_page(a['id'],a['revision'],{'page':1,'units':[{'ordinal':0,'kind':'paragraph','text':text,'bbox':[.1,.1,.8,.2]}]})
    index.finish(a['id']);prompts=[]
    def reply(evidence,prompt):
        prompts.append(prompt);return {'claims':[{'text':text,'source_ids':[evidence[0]['id']]}]}
    model_reply(monkeypatch,reply)
    result=post(client,'/api/ask',body(a,operation='Quiz')).json
    assert 'Use Arabic.' in prompts[0] and result['cards']
    card=result['cards'][0]
    assert card['front'].startswith('أكمل النص') and card['back']=='٢٥٠٠٠'
    assert card['front'].split(': ',1)[1].replace('____',card['back'],1)==card['explanation']
    assert card['explanation'] in text and 'API' in card['explanation']


def test_large_document_coverage_and_saved_comparison(app):
    client=app.test_client();a=add(client,'Termination requires 30 days notice.');b=add(client,'Termination requires 60 days notice.','revision.pdf')
    app.extensions['insight']['library'][a['id']]['page_count']=150
    result=post(client,'/api/ask',body(a,operation='Executive summary')).json
    assert result['coverage']=={'pages':1,'passages':1,'total_pages':150,'partial':True}
    assert any('not a verified exhaustive review' in w for w in result['warnings'])
    comparison=post(client,'/api/compare',{'scope':'selected','document_ids':[a['id'],b['id']]}).json
    saved=client.get('/api/studio/'+comparison['saved_id']).json
    assert saved['kind']=='Comparison'
    for side,doc in [('a',a),('b',b)]:
        source=saved['content']['rows'][0][side]
        assert client.get(f"/api/studio/{saved['id']}/sources/{source['id']}").json['document_id']==doc['id']


def test_unmatched_user_note_never_enters_ai_evidence(app):
    client=app.test_client();a=add(client,'Text with a broken font mapping.')
    selection={'document_id':a['id'],'page':1,'text':'User-selected text / نص محدد','bbox':[.1,.1,.8,.2]}
    note=post(client,'/api/notes',body(a,selection=selection)).json
    assert note['content']['selection']['verified'] is False
    source=note['content']['sources'][0]
    assert source['kind']=='user-selection'
    assert client.get(f"/api/studio/{note['id']}/sources/{source['id']}").json['page']==1
    assert post(client,'/api/ask',body(a,selection=selection)).status_code==409
    assert all(c['id']!=source['id'] for c in app.extensions['insight']['index'].all_chunks([a['id']]))
    assert post(client,'/api/notes',body(a,selection=selection|{'page':99})).status_code==400


def test_glossary_without_definitions_refuses_in_excerpt_mode(app):
    client=app.test_client();a=add(client,'The supplier pays 300 dollars tomorrow.')
    result=post(client,'/api/ask',body(a,operation='Glossary')).json
    assert result['claims']==[] and 'sufficient evidence' in result['message']


def test_garbled_extraction_does_not_become_study_or_suggestion():
    from localpdf_insight.convenience import study_cards
    source={'id':'bad','document_id':'a','heading':'','text':'ﺀﺎﻬﻧﺇContract ABC-123 AED 500 and more garbled text'}
    assert suggested_questions([source],['a'])==[]
    assert study_cards([{'text':source['text'],'source_ids':['bad']}],[source],'ar')==[]

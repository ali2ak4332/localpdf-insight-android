"""Permanent regressions for defects found during the fresh review."""
import io
import json
from pathlib import Path
import pytest
from test_web import app, post
from verification_support import approving_verifier
from localpdf_insight.grounding import release_witnesses, review_question, safe_answer
from localpdf_insight.verification import units


@pytest.mark.parametrize('strict', [True, False])
@pytest.mark.parametrize('scope', ['current', 'selected', 'library'])
def test_narrow_arabic_qualification_cannot_be_lost_at_layout_boundary(app, monkeypatch, strict, scope):
    import localpdf_insight.core as core
    path = Path(__file__).parents[1]/'docs/b1-independent/arabic-qualification-original.pdf'
    client = app.test_client()
    response = client.post('/api/import', data={'file': (io.BytesIO(path.read_bytes()), 'تأهيل.pdf')}, headers={'X-LocalPDF':'1'})
    assert response.status_code == 200
    doc = response.json['document']
    index = app.extensions['insight']['index']
    chunks = index.all_chunks([doc['id']])
    assert len(chunks) == 2 and 'ويستثني' in chunks[1]['text']
    original = [dict(c) for c in chunks]
    def generate(prompt, model, **kwargs):
        sources = json.loads(prompt.split('EVIDENCE JSON:\n')[1])
        return json.dumps({'claims': [{'text':s['text'], 'source_ids':[s['id']]} for s in sources]})
    monkeypatch.setattr(core, 'ollama_generate', generate)
    monkeypatch.setenv('LOCALPDF_MODEL', 'controlled-NOT-live')
    app.extensions['insight']['verifier'] = approving_verifier
    result = post(client, '/api/ask', {'scope':scope, 'current_id':doc['id'], 'document_ids':[doc['id']],
                  'question':'كم بلغ صافي ربح ليريك لعام 2037؟', 'strict':strict}).json
    assert not result['claims'], result
    assert any('qualification_crosses_source_boundary' in v['reasons'] for p in result['grounding']['parts'] for v in p['vetoes'])
    assert index.all_chunks([doc['id']]) == original  # Raw extraction/IDs are untouched.
    assert client.get('/api/documents/'+doc['id']+'/pdf').data == path.read_bytes()


@pytest.mark.parametrize('mode', ['strict', 'assisted'])
def test_old_version_two_saved_answer_is_withheld_without_rewriting(app, mode):
    index = app.extensions['insight']['index']
    output = index.save_output('Key numbers', 'Prior correction', {'content': {'mode':mode,
        'claims':[{'text':'Authentic but non-responsive whole source.', 'source_ids':['original']}],
        'grounding':{'version':2, 'classification':'SUPPORTED'}, 'sources':[]}})
    result = app.test_client().get('/api/studio/'+output['id']).json
    assert not result['content']['claims']
    assert result['content']['grounding']['status'] == 'legacy_answer_withheld'
    assert index.output(output['id']) == output


def test_release_offsets_are_owned_by_server_not_verifier():
    source = {'id':'s', 'text':'A useful answer. An unrelated statement.'}
    first = units(source['text'])[0]
    good = {'status':'supported', 'witnesses':[{'source_id':'s', 'unit':0, 'start':first[0], 'end':first[1]}]}
    assert release_witnesses([good], [source])[0]['text'] == 'A useful answer.'
    forged = {'status':'supported', 'witnesses':[{'source_id':'s', 'unit':0, 'start':0, 'end':len(source['text'])}]}
    with pytest.raises(ValueError): release_witnesses([forged], [source])


@pytest.mark.parametrize('text', [
    'The contractor must submit the plan if the permit is granted. The contractor must not submit the plan if the permit is denied.',
    'يجب على المقاول تقديم الخطة إذا صدرت الموافقة. يحظر على المقاول تقديم الخطة إذا رفضت الموافقة.',
])
def test_different_conditions_are_not_collapsed_into_legal_conflict(text):
    q = 'What are the submission conditions?' if text.startswith('The') else 'ما شروط تقديم الخطة؟'
    parts = review_question(q, [{'id':'s', 'text':text}], approving_verifier)
    assert parts[0]['status'] == 'supported'
    assert len(parts[0]['witnesses']) == 2


def test_same_source_semantic_conflict_can_show_both_distinct_sides():
    text = 'The agreement is renewable. The agreement is not renewable.'
    result = safe_answer('Is the agreement renewable?', [{'id':'s','text':text}],
                        [{'text':text,'source_ids':['s']}], True, approving_verifier, 'controlled', 'ask', 'No evidence')
    assert result['grounding']['classification'] == 'CONFLICTING'
    assert ''.join(c['text'] for c in result['claims']) == text


@pytest.mark.parametrize('status', ['supported', 'conflict'])
def test_duplicate_witness_does_not_create_a_second_conflict_side(status):
    text = 'The licence is renewable.'; q = 'Is the licence renewable?'
    def verify(request):
        ref = {'source_id':'s','unit':0}
        return json.dumps({'parts':[{'start':0,'end':len(q),'status':status,'source_ids':['s'],'witnesses':[ref,ref]}]})
    result = review_question(q, [{'id':'s','text':text}], verify)
    assert result[0]['status'] == ('supported' if status == 'supported' else 'unknown')

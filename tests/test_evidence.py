import json
from pathlib import Path
import fitz
import pytest
from localpdf_insight.evidence import EvidenceIndex, normalize, digest, validated_claims, answer, compare, REFUSAL
from localpdf_insight.document import index_document, extract_page, inspect_pdf, page_image


def make_pdf(path,texts):
    with fitz.open() as doc:
        for text in texts:doc.new_page().insert_text((60,70),text)
        doc.save(path)
    return path


def index_pdf(tmp_path,texts,name='contract.pdf',doc_id='doc-a'):
    path=make_pdf(tmp_path/name,texts)
    index=EvidenceIndex(tmp_path/'index.sqlite3')
    revision=digest(path)
    index_document(str(path),doc_id,revision,str(index.path))
    return index,path,revision


def test_correct_doc_page_passage_and_coordinates(tmp_path):
    index,path,rev=index_pdf(tmp_path,['Annual report and company introduction.','Termination requires 30 days written notice.'])
    results=index.retrieve('termination notice',['doc-a'])
    assert results[0]['document_id']=='doc-a' and results[0]['page']==2
    assert '30 days' in results[0]['text'] and results[0]['revision']==rev
    assert all(0<=n<=1 for n in results[0]['bbox'])
    assert index.source(results[0]['id'],['doc-a'])['text']==results[0]['text']


def test_scope_no_leakage_empty_scope_fails_closed(tmp_path):
    index,_,_=index_pdf(tmp_path,['Public information concerning the company.'])
    path=make_pdf(tmp_path/'secret.pdf',['Secret access code is pineapple zebra.'])
    index_document(str(path),'secret',digest(path),str(index.path))
    assert not index.retrieve('pineapple',['doc-a'])
    assert not index.retrieve('pineapple',[])
    assert index.retrieve('pineapple',['secret'])[0]['document_id']=='secret'
    assert not index.source(index.retrieve('pineapple',['secret'])[0]['id'],['doc-a'])


def test_strict_rejects_fabricated_page_and_unsupported_claim():
    evidence=[{'id':'known','text':'The notice period is 30 days.'}]
    assert not validated_claims(json.dumps({'claims':[{'text':'The notice period is 90 days.','source_ids':['known']}]}),evidence)
    assert not validated_claims(json.dumps({'claims':[{'text':'The notice period is 30 days.','source_ids':['invented']}]}),evidence)
    assert not validated_claims(json.dumps({'claims':[{'text':'The notice period is 30 days. [p.99]','source_ids':['known']}]}),evidence)
    valid=validated_claims(json.dumps({'claims':[{'text':'The notice period is 30 days.','source_ids':['known']}]}),evidence)
    assert valid and valid[0]['verbatim']


def test_strict_insufficient_answer_refuses():
    sources=[{'id':'known','text':'The notice period is 30 days.'}]
    result=answer('What is the price?',sources,generate=lambda *a:'{"claims":[{"text":"AED 50","source_ids":["known"]}]}')
    assert not result['claims'] and result['message']==REFUSAL
    assert answer('price',[])['message']==REFUSAL


def test_no_model_is_explicitly_excerpts_not_fabricated_answer():
    result=answer('notice',[{'id':'a','text':'Notice is required.'}])
    assert result['mode']=='excerpts' and result['claims'][0]['text']=='Notice is required.'


def test_arabic_native_pdf_search_and_mixed_numbers(tmp_path):
    path=tmp_path/'arabic.pdf'
    with fitz.open() as doc:
        page=doc.new_page()
        page.insert_htmlbox(fitz.Rect(40,40,550,200),'<p dir="rtl">إنهاء العقد بإشعار كتابي خلال ٣٠ يوماً. Contract ABC-123 AED 500</p>',css='* {font-size:18px;}')
        doc.save(path)
    index=EvidenceIndex(tmp_path/'arabic.sqlite3');index_document(str(path),'arabic',digest(path),str(index.path))
    results=index.retrieve('انهاء العقد',['arabic'])
    assert results and 'ABC-123' in results[0]['text']
    assert normalize('إِنْهَاءُ العَقْدِ ٣٠')=='انهاء العقد 30'
    assert index.retrieve('ABC 123',['arabic'])


def test_ocr_fallback_real_image_pdf(tmp_path):
    source=make_pdf(tmp_path/'native.pdf',['SCANNED INVOICE NUMBER 73491','Other readable document page.'])
    with fitz.open(source) as native:
        image=native[0].get_pixmap(matrix=fitz.Matrix(3,3)).tobytes('png')
    scanned=tmp_path/'scan.pdf'
    with fitz.open() as doc:
        page=doc.new_page();page.insert_image(page.rect,stream=image);doc.save(scanned)
    index=EvidenceIndex(tmp_path/'scan.sqlite3');index_document(str(scanned),'scan',digest(scanned),str(index.path),'eng')
    page=index.page('scan',1)
    assert page['method']=='ocr',page['warnings']
    assert index.retrieve('73491',['scan'])[0]['page']==1


def test_missing_ocr_language_is_visible(tmp_path):
    with fitz.open() as doc:
        page=doc.new_page()
        result=extract_page(page,languages='language_that_is_not_installed')
    assert result['warnings'] and any('OCR unavailable' in w for w in result['warnings'])


def test_reindex_removes_old_sources_and_preserves_document_id(tmp_path):
    index,path,revision=index_pdf(tmp_path,['Original termination notice is 30 days.'])
    source=index.retrieve('termination',['doc-a'])[0]
    path.unlink();make_pdf(path,['Replacement termination notice is 60 days.'])
    index_document(str(path),'doc-a',digest(path),str(index.path))
    assert not index.source(source['id'],['doc-a'])
    current=index.retrieve('termination',['doc-a'])[0]
    assert current['document_id']=='doc-a' and current['revision']!=revision and '60 days' in current['text']


def test_comparison_links_both_versions(tmp_path):
    index,_,_=index_pdf(tmp_path,['Termination requires 30 days written notice.'])
    path=make_pdf(tmp_path/'revision.pdf',['Termination requires 60 days written notice.'])
    index_document(str(path),'doc-b',digest(path),str(index.path))
    result=compare(index,['doc-a','doc-b'])
    assert result['rows']
    row=result['rows'][0]
    assert row['a']['document_id']=='doc-a' and row['b']['document_id']=='doc-b'
    assert row['a']['page']==row['b']['page']==1
    assert index.source(row['a']['id'],['doc-a']) and index.source(row['b']['id'],['doc-b'])


def test_structure_reranks_heading_passage(tmp_path):
    index=EvidenceIndex(tmp_path/'s.sqlite3');index.begin('a','v1',2)
    for n,heading in [(1,''),(2,'Termination provisions')]:
        index.put_page('a','v1',{'page':n,'units':[{'text':'Termination may occur following notice.','heading':heading,'kind':'paragraph','ordinal':0,'bbox':[0,.1,1,.2]}]})
    index.finish('a')
    assert index.retrieve('termination provisions',['a'])[0]['page']==2


def test_embeddings_cache_and_scope(tmp_path):
    index,_,_=index_pdf(tmp_path,['A turbine generates electricity.'])
    class Provider:
        model='test-semantic';calls=0
        def embed(self,texts):self.calls+=1;return [[1,0] for _ in texts]
    provider=Provider();index.cache_embeddings(['doc-a'],provider);calls=provider.calls
    index.cache_embeddings(['doc-a'],provider);assert provider.calls==calls
    results=index.retrieve('power generator',['doc-a'],embedder=provider)
    assert results and 'local embeddings' in results[0]['retrieval_method']
    assert not index.retrieve('power generator',[],embedder=provider)


def test_rotated_page_coordinates_and_bounded_render(tmp_path):
    path=tmp_path/'rotated.pdf'
    with fitz.open() as doc:
        p=doc.new_page(width=400,height=900);p.insert_text((50,70),'Rotated termination clause');p.set_rotation(90);doc.save(path)
    with fitz.open(path) as doc:
        result=extract_page(doc[0]);assert result['rotation']==90
        assert all(0<=n<=1 for n in result['units'][0]['bbox'])
    image=page_image(str(path),1,1800);pix=fitz.Pixmap(image);assert pix.width*pix.height<=6_000_000


def test_password_and_corrupt_pdf(tmp_path):
    path=tmp_path/'locked.pdf'
    with fitz.open() as doc:
        doc.new_page().insert_text((50,70),'Private document')
        doc.save(path,encryption=fitz.PDF_ENCRYPT_AES_256,owner_pw='owner',user_pw='reader')
    with pytest.raises(ValueError,match='password'):inspect_pdf(str(path))
    assert inspect_pdf(str(path),'reader')['page_count']==1
    broken=tmp_path/'broken.pdf';broken.write_bytes(b'not a pdf')
    with pytest.raises(Exception):inspect_pdf(str(broken))


def test_tables_preserve_cells_and_source_coordinates(tmp_path):
    path=tmp_path/'table.pdf'
    with fitz.open() as doc:
        page=doc.new_page()
        for x in (50,200,350):page.draw_line((x,50),(x,150))
        for y in (50,100,150):page.draw_line((50,y),(350,y))
        for x,y,text in [(60,75,'Item'),(210,75,'Amount'),(60,125,'Services'),(210,125,'25000')]:page.insert_text((x,y),text)
        doc.save(path)
    with fitz.open(path) as doc:
        result=extract_page(doc[0])
    assert result['tables'][0]['rows']==[['Item','Amount'],['Services','25000']]
    assert any(u['kind']=='table' and '25000' in u['text'] for u in result['units'])


def test_arabic_search_alias_preserves_original_text():
    from localpdf_insight.evidence import index_tokens
    visual='ﺀﺎﻬﻧﺇContract ABC-123 ٣٠'
    assert 'انهاء' in index_tokens(visual)
    assert '30' in index_tokens(visual) and '03' not in index_tokens(visual)
    assert visual=='ﺀﺎﻬﻧﺇContract ABC-123 ٣٠'


def test_arabic_ocr_retrieval_when_language_installed(tmp_path):
    import os
    import subprocess
    langs=subprocess.run(['tesseract','--list-langs'],capture_output=True,text=True)
    if 'ara' not in langs.stdout.split():pytest.skip('Arabic Tesseract language pack is not installed')
    with fitz.open() as native:
        page=native.new_page();page.insert_htmlbox(fitz.Rect(40,40,550,200),'<p dir="rtl">إنهاء العقد بإشعار كتابي خلال ثلاثين يوماً</p>',css='*{font-size:24px;}')
        pixels=page.get_pixmap(matrix=fitz.Matrix(3,3)).tobytes('png')
    path=tmp_path/'arabic-scan.pdf'
    with fitz.open() as scanned:
        p=scanned.new_page();p.insert_image(p.rect,stream=pixels);scanned.save(path)
    index=EvidenceIndex(tmp_path/'ar-scan.sqlite3');index_document(str(path),'arabic-scan',digest(path),str(index.path),'ara+eng')
    assert index.page('arabic-scan',1)['method']=='ocr'
    results=index.retrieve('إنهاء العقد',['arabic-scan'])
    assert results and results[0]['document_id']=='arabic-scan' and results[0]['page']==1


def test_model_json_fence_does_not_bypass_evidence_validation():
    evidence=[{'id':'a','text':'Reported value is 7.1.\nThe forecast is not provided.'},
              {'id':'b','text':'A separate passage with different wording.'}]
    def fenced(text,ids):
        return '```json\n'+json.dumps({'claims':[{'text':text,'source_ids':ids}]})+'\n```'
    assert validated_claims(fenced('Reported value is 7.1.',['a']),evidence)
    assert not validated_claims(fenced('Reported value is 9.1.',['a']),evidence)
    assert not validated_claims(fenced('Reported value is 7.1.',['invented']),evidence)
    assert not validated_claims(fenced('Reported value is 7.1.',['a','b']),evidence)
    assert not validated_claims('Extra unsupported prose\n'+fenced('Reported value is 7.1.',['a']),evidence)


def test_strict_allows_separate_exact_excerpts_not_invented_synthesis():
    evidence=[{'id':'a','text':'Part A costs 12.'},{'id':'b','text':'Part B costs 13.'}]
    claims={'claims':[{'text':e['text'],'source_ids':[e['id']]} for e in evidence]}
    assert len(validated_claims(json.dumps(claims),evidence))==2
    assert not validated_claims(json.dumps({'claims':[{'text':'Together they cost 25.','source_ids':['a','b']}]}),evidence)


def test_comparison_does_not_align_unrelated_clause_headings(tmp_path):
    index,_,_=index_pdf(tmp_path,['3. Confidentiality','Termination requires 30 days written notice.'])
    index_pdf(tmp_path,['4. Notices','Termination requires 60 days written notice.'],name='other.pdf',doc_id='doc-b')
    rows=compare(index,['doc-a','doc-b'])['rows']
    assert len(rows)==1
    assert 'Termination' in rows[0]['a']['text'] and '60 days' in rows[0]['b']['text']


def test_strict_formatting_is_resolved_to_original_span_only():
    original='\uf077 Net profit was AED 7.1 billion,\nup 16%.'
    evidence=[{'id':'a','text':original}]
    def validate(text):return validated_claims(json.dumps({'claims':[{'text':text,'source_ids':['a']}]}),evidence)
    accepted=validate('• Net profit was AED 7.1 billion, up 16%.')
    assert accepted and accepted[0]['text'] in original
    assert '\n' in accepted[0]['text']
    assert not validate('• Net profit was AED 9.1 billion, up 16%.')
    assert not validate('Net profit increased to AED 7.1 billion, up 16%.')
    assert not validate('Net profit was AED 7.1 billion, up 16%. This will continue.')

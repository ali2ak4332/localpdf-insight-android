import io
import json
from concurrent.futures import Future
from pathlib import Path
import fitz
import pytest
from localpdf_insight.web import create_app


class InlineExecutor:
    def submit(self,fn,*args):
        future=Future()
        try:future.set_result(fn(*args))
        except Exception as e:future.set_exception(e)
        return future


@pytest.fixture
def app(tmp_path,monkeypatch):
    monkeypatch.delenv('LOCALPDF_TOKEN',raising=False)
    monkeypatch.delenv('LOCALPDF_MODEL',raising=False)
    monkeypatch.delenv('LOCALPDF_EMBED_MODEL',raising=False)
    return create_app(tmp_path,executor=InlineExecutor())


def pdf_bytes(text):
    with fitz.open() as doc:
        doc.new_page().insert_text((60,80),text)
        return doc.tobytes()


def add(client,text,name='contract.pdf'):
    response=client.post('/api/import',data={'file':(io.BytesIO(pdf_bytes(text)),name)},headers={'X-LocalPDF':'1'})
    assert response.status_code==200,response.json
    return response.json['document']


def post(client,path,body):return client.post(path,json=body,headers={'X-LocalPDF':'1'})


def test_import_load_range_and_duplicate(app):
    client=app.test_client();data=pdf_bytes('Termination requires thirty days written notice.')
    first=client.post('/api/import',data={'file':(io.BytesIO(data),'first.pdf')},headers={'X-LocalPDF':'1'}).json
    second=client.post('/api/import',data={'file':(io.BytesIO(data),'renamed.pdf')},headers={'X-LocalPDF':'1'}).json
    assert second['duplicate'] and first['document']['id']==second['document']['id']
    item=first['document'];assert client.get(f"/api/documents/{item['id']}/pdf").data.startswith(b'%PDF')
    assert client.get(f"/api/documents/{item['id']}/pdf",headers={'Range':'bytes=0-99'}).status_code==206
    assert client.get(f"/api/documents/{item['id']}/pages/2").status_code==404


def test_api_scope_and_source_resolves_correct_document(app):
    client=app.test_client();a=add(client,'Termination requires thirty days written notice.');b=add(client,'Classified pineapple zebra secret.','secret.pdf')
    response=post(client,'/api/ask',{'scope':'selected','document_ids':[a['id']],'question':'pineapple'})
    assert response.status_code==200 and not response.json['claims'] and response.json['sources']==[]
    search=post(client,'/api/search',{'scope':'current','current_id':a['id'],'question':'termination'})
    source=search.json['sources'][0];resolved=client.get('/api/sources/'+source['id']).json
    assert resolved['document_id']==a['id'] and resolved['page']==1
    assert post(client,'/api/search',{'scope':'selected','document_ids':[],'question':'pineapple'}).status_code==400
    assert post(client,'/api/search',{'scope':'current','current_id':'bad','question':'pineapple'}).status_code==404


def test_cross_origin_and_rebinding_rejected(app):
    client=app.test_client()
    assert client.post('/api/ask',json={}).status_code==403
    assert client.post('/api/ask',json={},headers={'X-LocalPDF':'1','Origin':'https://evil.example'}).status_code==403
    assert client.get('/api/documents',headers={'Host':'evil.example'}).status_code==400


def test_network_session_gate(tmp_path,monkeypatch):
    monkeypatch.setenv('LOCALPDF_TOKEN','test-only-key')
    app=create_app(tmp_path,executor=InlineExecutor());client=app.test_client()
    assert client.get('/api/documents').status_code==401
    assert post(client,'/api/login',{'token':'incorrect'}).status_code==401
    assert post(client,'/api/login',{'token':'test-only-key'}).status_code==200
    assert client.get('/api/documents').status_code==200


def test_selection_spoofing_rejected(app):
    client=app.test_client();a=add(client,'Termination requires thirty days written notice.')
    result=post(client,'/api/ask',{'scope':'current','current_id':a['id'],'question':'termination',
      'selection':{'document_id':a['id'],'page':1,'text':'The price is ten million.'}})
    assert result.status_code==409


def test_changed_document_rejects_stale_citation(app):
    client=app.test_client();a=add(client,'Termination requires thirty days written notice.')
    source=post(client,'/api/search',{'scope':'current','current_id':a['id'],'question':'termination'}).json['sources'][0]
    path=Path(app.extensions['insight']['library'][a['id']]['path']);path.write_bytes(pdf_bytes('Replacement document.'))
    assert client.get('/api/sources/'+source['id']).status_code==409


def test_privacy_headers_and_service_worker_no_document_cache(app):
    client=app.test_client()
    assert client.get('/api/documents').headers['Cache-Control']=='no-store'
    assert "frame-ancestors 'none'" in client.get('/').headers['Content-Security-Policy']
    assert "url.pathname.startsWith('/api/')" in client.get('/sw.js').text


def test_friendly_title_does_not_change_citation_identity(app):
    client=app.test_client();a=add(client,'Termination requires thirty days written notice.')
    source=post(client,'/api/search',{'scope':'current','current_id':a['id'],'question':'termination'}).json['sources'][0]
    result=client.patch('/api/documents/'+a['id'],json={'title':'Friendly title','collection':'Contracts','tags':['legal']},headers={'X-LocalPDF':'1'})
    assert result.status_code==200
    new=client.get('/api/sources/'+source['id']).json
    assert new['document_name']=='Friendly title' and new['id']==source['id'] and new['revision']==source['revision']


def test_comparison_api_provenance(app):
    client=app.test_client();a=add(client,'Termination requires 30 days written notice.');b=add(client,'Termination requires 60 days written notice.','revised.pdf')
    result=post(client,'/api/compare',{'scope':'selected','document_ids':[a['id'],b['id']]})
    assert result.status_code==200
    assert result.json['rows'][0]['a']['document_name']=='contract.pdf'
    assert result.json['rows'][0]['b']['document_name']=='revised.pdf'


def test_migration_preserves_old_document_id(tmp_path):
    from localpdf_insight.core import LibraryItem
    from localpdf_insight.migrate import migrate_desktop
    source=tmp_path/'old.pdf';source.write_bytes(pdf_bytes('Old desktop contract document.'))
    stat=source.stat();old=LibraryItem('0123456789abcdef0123',str(source),'Old title',stat.st_size,stat.st_mtime_ns)
    store=type('Store',(),{'items':[old],'warnings':[]})()
    root=tmp_path/'migrated';count,warnings=migrate_desktop(root,store)
    assert count==1 and not warnings
    data=json.loads((root/'library.json').read_text())
    assert old.id in data and data[old.id]['title']=='Old title'
    assert Path(data[old.id]['path']).read_bytes()==source.read_bytes()
    assert migrate_desktop(root,store)[0]==0


def test_corrupt_import_message(app):
    response=app.test_client().post('/api/import',data={'file':(io.BytesIO(b'not a pdf'),'bad.pdf')},headers={'X-LocalPDF':'1'})
    assert response.status_code==400 and 'PDF' in response.json['error']


def test_key_numbers_and_obligations_use_source_content(app):
    client=app.test_client();a=add(client,'The supplier must pay AED 25000 within 30 days.')
    for operation in ('Key numbers','Obligations','Action items'):
        result=post(client,'/api/ask',{'scope':'current','current_id':a['id'],'question':operation,'operation':operation})
        assert result.status_code==200 and result.json['claims']
        assert all(c['text'] in result.json['sources'][0]['text'] for c in result.json['claims'])
        assert 'not a verified exhaustive review' in result.json['warnings'][0]


def test_import_and_page_images_remain_available_while_indexing(tmp_path, monkeypatch):
    """A blocked index must not consume workers needed to inspect the next PDF."""
    import threading
    from concurrent.futures import ThreadPoolExecutor
    import localpdf_insight.web as web
    started=threading.Event(); release=threading.Event(); pools=[]
    def pool_factory(**kwargs):
        pool=ThreadPoolExecutor(max_workers=kwargs['max_workers']);pools.append(pool);return pool
    def blocked_index(*args):
        started.set()
        assert release.wait(10), 'test failed to release indexing'
    monkeypatch.setattr(web,'ProcessPoolExecutor',pool_factory)
    monkeypatch.setattr(web,'index_document',blocked_index)
    monkeypatch.delenv('LOCALPDF_TOKEN',raising=False)
    app=web.create_app(tmp_path)
    try:
        client=app.test_client()
        first=add(client,'First readable PDF.')
        assert started.wait(2)
        add(client,'Second readable PDF.','second.pdf')
        # With the old shared pool, these two indexing jobs exhaust both workers.
        with ThreadPoolExecutor(max_workers=1) as caller:
            future=caller.submit(lambda: add(app.test_client(),'Third readable PDF.','third.pdf'))
            try:
                assert future.result(timeout=3)['page_count']==1
                assert client.get(f"/api/documents/{first['id']}/pages/1/image").status_code==200
            finally:release.set()
    finally:
        release.set()
        for pool in pools:pool.shutdown(wait=True)

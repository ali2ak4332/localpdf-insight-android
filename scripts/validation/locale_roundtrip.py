"""One real process per lifecycle step. cp1252 is explicitly a simulation."""
import io
import json
import locale
import os
from pathlib import Path
import sys
from concurrent.futures import Future
from types import SimpleNamespace

ROOT = Path(sys.argv[1]); ACTION = sys.argv[2]
SIMULATED = os.environ.get('LOCALPDF_SIMULATE_CP1252') == '1'
if SIMULATED:
    original_open = io.open
    def codepage_open(file, mode='r', buffering=-1, encoding=None, errors=None, newline=None, closefd=True, opener=None):
        if encoding is None and 'b' not in mode: encoding='cp1252'
        return original_open(file,mode,buffering,encoding,errors,newline,closefd,opener)
    io.open = codepage_open

import fitz
from localpdf_insight.web import create_app
from localpdf_insight.metadata import read_json, write_json
from localpdf_insight.migrate import migrate_desktop

class Inline:
    def submit(self,fn,*args):
        f=Future()
        try:f.set_result(fn(*args))
        except Exception as e:f.set_exception(e)
        return f

NAME='ملف مالي.pdf'; TITLE='تقرير أطلس – مُراجَع 2025'; state_path=ROOT/'probe-state.json'
for key in ('LOCALPDF_MODEL','LOCALPDF_EMBED_MODEL','LOCALPDF_TOKEN'):os.environ.pop(key,None)
app=create_app(ROOT,executor=Inline());client=app.test_client();headers={'X-LocalPDF':'1'}
if ACTION=='init':
    with fitz.open() as pdf:
        pdf.new_page().insert_text((60,80),'The net profit for 2025 was AED 100 million.')
        response=client.post('/api/import',data={'file':(io.BytesIO(pdf.tobytes()),NAME)},headers=headers)
    assert response.status_code==200,response.json
    doc=response.json['document'];assert doc['filename']==NAME and doc['index']['status']=='ready'
    result=client.post('/api/ask',json={'scope':'current','current_id':doc['id'],'question':'Executive summary','operation':'Executive summary'},headers=headers).json
    source=result['sources'][0]
    state={'id':doc['id'],'revision':doc['revision'],'source_id':source['id'],'page':source['page'],'output_id':result['saved_id'],'title':NAME,'filename':NAME}
    write_json(state_path,state)
else:
    state=read_json(state_path)
    if ACTION=='rename':
        response=client.patch('/api/documents/'+state['id'],json={'title':TITLE,'tags':['مراجعة','Finance']},headers=headers)
        assert response.status_code==200,response.json
        state['title']=TITLE;write_json(state_path,state)
    elif ACTION=='migrate':
        source=ROOT/'desktop-source.pdf'
        with fitz.open() as pdf:
            pdf.new_page().insert_text((60,80),'Migrated desktop source preserves document identity and evidence.')
            pdf.save(source)
        old=SimpleNamespace(id='a'*20,path=str(source),name='مكتبة قديمة – العربية',indexed_at=0)
        added,warnings=migrate_desktop(ROOT,SimpleNamespace(items=[old],warnings=[]))
        assert added==1 and not warnings,(added,warnings)
        app=create_app(ROOT,executor=Inline());client=app.test_client()
        assert app.extensions['insight']['library'][old.id]['title']==old.name
        assert client.post('/api/documents/'+old.id+'/index',json={},headers=headers).status_code==200
item=app.extensions['insight']['library'][state['id']]
assert item['title']==state['title'] and item['filename']==NAME and item['revision']==state['revision']
assert read_json(ROOT/'library.json')[state['id']]['filename']==NAME
source=client.get('/api/sources/'+state['source_id']);assert source.status_code==200,source.json
assert source.json['document_id']==state['id'] and source.json['page']==state['page']
assert client.get('/api/documents/'+state['id']+'/pdf').data.startswith(b'%PDF')
saved=client.get('/api/studio/'+state['output_id']);assert saved.status_code==200
citation=client.get('/api/studio/'+state['output_id']+'/sources/'+state['source_id']);assert citation.status_code==200,citation.json
assert citation.json['revision']==state['revision'] and citation.json['page']==state['page']
with app.extensions['insight']['index'].connect() as db:
    assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
print(json.dumps({'action':ACTION,'locale_encoding':locale.getencoding(),'filesystem_encoding':sys.getfilesystemencoding(),'utf8_mode':sys.flags.utf8_mode,'cp1252_simulation':SIMULATED,'unicode_roundtrip':True,'citation_and_studio_roundtrip':True,'platform':sys.platform},ensure_ascii=True))

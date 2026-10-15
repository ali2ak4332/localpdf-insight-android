import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import pytest
from localpdf_insight.metadata import read_json, convert_legacy

WORKER=Path(__file__).resolve().parents[1]/'scripts/validation/locale_roundtrip.py'

@pytest.mark.parametrize('configuration',['utf8','genuine_c','cp1252_simulation'])
def test_unicode_complete_lifecycle(tmp_path,configuration):
    root=tmp_path/'original';logs=[]
    env=dict(os.environ,PYTHONUTF8='0',PYTHONCOERCECLOCALE='0',LC_ALL='C' if configuration=='genuine_c' else 'C.UTF-8',LANG='C' if configuration=='genuine_c' else 'C.UTF-8')
    if configuration=='cp1252_simulation':env['LOCALPDF_SIMULATE_CP1252']='1'
    else:env.pop('LOCALPDF_SIMULATE_CP1252',None)
    def invoke(path,action):
        result=subprocess.run([sys.executable,str(WORKER),str(path),action],env=env,capture_output=True)
        assert result.returncode==0,result.stderr.decode('utf-8',errors='backslashreplace')
        record=json.loads(result.stdout.decode('utf-8').splitlines()[-1]);logs.append(record)
        if configuration=='genuine_c':
            assert record['utf8_mode']==0 and record['locale_encoding'] not in {'UTF-8','utf-8'}
    for action in ['init','restart','restart','rename','restart','migrate','restart']:invoke(root,action)
    backup=tmp_path/'backup';shutil.copytree(root,backup)
    original=(root/'library.json').read_bytes()
    shutil.rmtree(root);shutil.copytree(backup,root);invoke(root,'restart')
    assert (root/'library.json').read_bytes()==original
    moved=tmp_path/'relocated';shutil.copytree(backup,moved);shutil.rmtree(root)
    invoke(moved,'restart');invoke(moved,'restart')
    assert (moved/'library.json').read_bytes()!=original
    assert next(moved.glob('library.json.before-rebase-*')).read_bytes()==original
    if os.environ.get('LOCALPDF_UNICODE_LOG'):
        with open(os.environ['LOCALPDF_UNICODE_LOG'],'a',encoding='utf-8') as stream:
            stream.write(json.dumps({'configuration':configuration,'steps':logs})+'\n')


def test_invalid_or_legacy_metadata_keeps_original_bytes(tmp_path):
    path=tmp_path/'library.json';raw='{"title":"caf\u00e9"}'.encode('cp1252');path.write_bytes(raw)
    with pytest.raises(ValueError,match='UTF-8'):read_json(path)
    assert path.read_bytes()==raw and next(tmp_path.glob('*.recovery-*')).read_bytes()==raw
    backup=convert_legacy(path,'cp1252')
    assert backup.read_bytes()==raw and read_json(path)['title']=='café'


def test_failed_legacy_conversion_is_non_destructive(tmp_path):
    path=tmp_path/'library.json';raw=b'{broken';path.write_bytes(raw)
    with pytest.raises(ValueError):convert_legacy(path,'cp1252')
    assert path.read_bytes()==raw


def test_relocation_does_not_accept_changed_pdf_or_old_external_path(tmp_path,monkeypatch):
    from test_web import InlineExecutor,add
    from localpdf_insight.web import create_app
    monkeypatch.delenv('LOCALPDF_MODEL',raising=False)
    original=tmp_path/'original';app=create_app(original,executor=InlineExecutor());doc=add(app.test_client(),'Original document content must remain verifiable.')
    moved=tmp_path/'moved';shutil.copytree(original,moved)
    (moved/'documents'/(doc['id']+'.pdf')).write_bytes(b'changed')
    restored=create_app(moved,executor=InlineExecutor()).test_client()
    assert restored.get('/api/documents/'+doc['id']+'/pdf').status_code==409
    # The old original still exists; the restored app must not read outside itself.
    assert (original/'documents'/(doc['id']+'.pdf')).exists()

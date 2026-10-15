"""Isolated extracted-wheel smoke using an already installed dependency runtime.

This does not certify clean dependency installation, a live model, or an RC.
"""
import argparse
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from concurrent.futures import Future


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--extracted', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True); args = parser.parse_args()
    root = args.extracted.resolve(); sys.path.insert(0, str(root))
    os.environ['LOCALPDF_MODEL']=''; os.environ['LOCALPDF_EMBED_MODEL']=''; os.environ.pop('LOCALPDF_TOKEN',None)
    import localpdf_insight
    import fitz
    from localpdf_insight.web import create_app
    assert Path(localpdf_insight.__file__).resolve().is_relative_to(root)
    class Inline:
        def submit(self, function, *values):
            future = Future()
            try: future.set_result(function(*values))
            except Exception as exc: future.set_exception(exc)
            return future
    with tempfile.TemporaryDirectory(prefix='localpdf-wheel-smoke-') as data:
        client = create_app(data, executor=Inline()).test_client()
        assert client.get('/').status_code == 200
        with fitz.open() as pdf:
            pdf.new_page().insert_text((60,70),'The agreement requires thirty days written notice.')
            raw=pdf.tobytes()
        result = client.post('/api/import', data={'file':(io.BytesIO(raw),'اتفاقية.pdf')}, headers={'X-LocalPDF':'1'})
        assert result.status_code == 200, result.json
        doc = result.json['document']
        body = {'scope':'current','current_id':doc['id'],'question':'written notice','strict':True}
        answer = client.post('/api/ask',json=body,headers={'X-LocalPDF':'1'}).json
        assert answer['mode']=='excerpts' and answer['claims']
        for claim in answer['claims']:
            for sid in claim['source_ids']:
                source=client.get('/api/sources/'+sid).json
                assert source['document_id']==doc['id'] and source['page']==1
        assert client.get('/api/documents/'+doc['id']+'/pdf').data==raw
    result={'passed':True,'module_path':str(Path(localpdf_insight.__file__).resolve()),
            'isolated_code':True,'dependencies':'pre-existing interpreter environment; NOT clean-install evidence',
            'checks':['HTML shell','synthetic Arabic filename import/index','excerpt query','source document/page resolution','original PDF bytes'],
            'live_model':False,'release_candidate':False}
    with args.output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(result))


if __name__=='__main__':main()

"""One local web interface; PDF and model processing stay behind bounded adapters."""
from __future__ import annotations
import argparse
import atexit
import base64
import csv
import io
import json
import multiprocessing
import math
import os
import re
import secrets
import threading
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from functools import partial
from pathlib import Path
from urllib.parse import urlsplit

from flask import Flask, abort, jsonify, request, send_file, send_from_directory, session
from werkzeug.exceptions import HTTPException
from . import core
from .document import inspect_pdf, index_document, page_image
from .evidence import EvidenceIndex, OllamaEmbeddings, answer, compare, digest, query_tokens, tokens
from .metadata import read_json, write_json, managed_pdf, rebase_verified

from .convenience import TEMPLATES, STUDY, source_language, sampled_sources, suggested_questions, study_cards, usable_prompt_text

SUMMARY_MODES = {'Executive summary','Detailed summary','Section-by-section summary','Key facts','Key numbers',
                 'Risks','Obligations','Timeline','People / companies / entities','Action items'} | set(TEMPLATES)


def create_app(data_dir=None, executor=None, verifier=None):
    app=Flask(__name__,static_url_path='/static')
    root=Path(data_dir or os.environ.get('LOCALPDF_DATA',core.APP_HOME/'web')).expanduser().resolve()
    root.mkdir(parents=True,exist_ok=True)
    library_path=root/'library.json'
    index=EvidenceIndex(root/'evidence.sqlite3')
    library=read_json(library_path)
    rebase_verified(root,library)
    lock=threading.RLock(); jobs={}
    pool=executor or ProcessPoolExecutor(max_workers=2,mp_context=multiprocessing.get_context('spawn'))
    # Long indexing jobs must not queue ahead of import inspection and page images.
    index_pool=executor or ProcessPoolExecutor(max_workers=1,mp_context=multiprocessing.get_context('spawn'))
    if executor is None:
        atexit.register(pool.shutdown,wait=False,cancel_futures=True)
        atexit.register(index_pool.shutdown,wait=False,cancel_futures=True)
    token=os.environ.get('LOCALPDF_TOKEN','')
    app.secret_key=token or secrets.token_hex(32)
    app.config.update(MAX_CONTENT_LENGTH=220*1024*1024, SESSION_COOKIE_HTTPONLY=True,
                      SESSION_COOKIE_SAMESITE='Strict', SESSION_COOKIE_SECURE=os.environ.get('LOCALPDF_HTTPS')=='1',
                      TRUSTED_HOSTS=os.environ.get('LOCALPDF_HOSTS','localhost,127.0.0.1,[::1]').split(','))
    app.extensions['insight']={'index':index,'library':library,'jobs':jobs,'pool':pool,'verifier':verifier}

    def save():
        write_json(library_path,library)

    def valid_item(doc_id):
        with lock:item=library.get(doc_id)
        if not item:abort(404,description='Document not found')
        path=Path(item['path'])
        if path.resolve()!=managed_pdf(root,doc_id):
            abort(409,description='Managed PDF was not restored with its recorded revision. Restore the complete backup.')
        if not path.is_file():abort(409,description='This PDF is unavailable. Restore or reimport it.')
        stat=path.stat()
        if stat.st_size!=item['size'] or stat.st_mtime_ns!=item['mtime_ns']:
            abort(409,description='This PDF changed. Its old citations are not valid for the replacement. Reimport it.')
        return item

    def public(item):
        return {k:v for k,v in item.items() if k!='path'} | {'index':index.status(item['id'])}

    def scope(body):
        mode=body.get('scope','current')
        if mode=='library':ids=list(library)
        elif mode=='current':ids=[body.get('current_id')]
        elif mode=='selected':ids=body.get('document_ids',[])
        else:abort(400,description='Choose current PDF, selected documents, or library.')
        if not isinstance(ids,list) or not ids or len(ids)>100 or not all(isinstance(i,str) for i in ids):
            abort(400,description='Select at least one document (up to 100).')
        for i in ids:valid_item(i)
        return list(dict.fromkeys(ids))

    def enrich(source):
        item=valid_item(source['document_id'])
        if source['revision']!=item['revision']:abort(409,description='Evidence belongs to a different PDF revision.')
        page_data=index.page(source['document_id'],source['page']) or {}
        return source | {'document_name':item['title'],'filename':item['filename'],
                         'extraction_method':page_data.get('method','native'),
                         'extraction_warnings':page_data.get('warnings',[])}

    @app.before_request
    def protect():
        # Host allow-list prevents DNS rebinding; no cross-origin API access or CORS.
        if request.path=='/api/login':return
        if request.method not in ('GET','HEAD','OPTIONS'):
            if request.headers.get('X-LocalPDF')!='1':abort(403,description='Same-origin client header required.')
            origin=request.headers.get('Origin')
            if origin and urlsplit(origin).netloc!=request.host:abort(403,description='Cross-origin request refused.')
        if token and request.path.startswith('/api/') and not session.get('authenticated'):
            abort(401,description='Enter the access key for this LocalPDF server.')

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='no-referrer'
        response.headers['X-Frame-Options']='DENY'
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:; font-src 'self' blob: data:; worker-src 'self' blob:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
        if request.path.startswith('/api/'):response.headers['Cache-Control']='no-store'
        return response

    @app.errorhandler(Exception)
    def errors(exc):
        if isinstance(exc,HTTPException):return jsonify(error=exc.description),exc.code
        if isinstance(exc,(ValueError,TypeError)):return jsonify(error=str(exc)),400
        app.logger.exception('LocalPDF operation failed')
        return jsonify(error='The operation failed. Check the local server log and try again.'),500

    @app.post('/api/login')
    def login():
        if request.headers.get('X-LocalPDF')!='1':abort(403)
        origin=request.headers.get('Origin')
        if origin and urlsplit(origin).netloc!=request.host:abort(403)
        supplied=(request.get_json(silent=True) or {}).get('token','')
        if token and (not isinstance(supplied,str) or not secrets.compare_digest(supplied,token)):abort(401)
        session['authenticated']=True
        return jsonify(ok=True)

    @app.get('/')
    def home():return send_from_directory(app.static_folder,'index.html')

    @app.get('/sw.js')
    def sw():return send_from_directory(app.static_folder,'sw.js')

    @app.get('/api/config')
    def config():
        return jsonify(model=os.environ.get('LOCALPDF_MODEL',''),embedding_model=os.environ.get('LOCALPDF_EMBED_MODEL',''),
                       languages=os.environ.get('LOCALPDF_OCR_LANGS','eng'),summary_modes=sorted(SUMMARY_MODES),
                       templates=[{'id':k,'en':k.title(),'ar':v[0]} for k,v in TEMPLATES.items()],
                       privacy='PDFs, extracted text, indexes and page images stay on this server. Reading occurs in your browser. Only selected evidence reaches local Ollama; no external AI providers are configured.')

    @app.get('/api/documents')
    def documents():
        with lock:return jsonify(documents=[public(i) for i in sorted(library.values(),key=lambda i:i.get('opened_at',i['imported_at']),reverse=True)])

    @app.post('/api/import')
    def import_pdf():
        upload=request.files.get('file')
        if upload is None:abort(400,description='Choose a PDF file.')
        name=Path((upload.filename or 'document.pdf').replace('\\','/')).name[:200]
        temp=root/(secrets.token_hex(12)+'.upload')
        try:
            upload.save(temp)
            try:
                meta=pool.submit(inspect_pdf,str(temp),request.form.get('password','')).result(timeout=90)
            except ValueError:
                raise
            except Exception as exc:
                raise ValueError('Could not read this PDF. It may be corrupted or use an unsupported format: '+str(exc)[:160]) from exc
            # Protected originals are stored as originals: browser asks for password separately.
            # Indexing requires an unlocked snapshot; decrypt only after successful authentication.
            password=request.form.get('password','')
            if password:
                unlocked=temp.with_suffix('.unlocked')
                pool.submit(unlock_pdf,str(temp),str(unlocked),password).result(timeout=90)
                temp.unlink();temp=unlocked
            revision=digest(temp)
            with lock:
                duplicate=next((i for i in library.values() if i['revision']==revision),None)
                if duplicate:return jsonify(document=public(duplicate),duplicate=True)
                doc_id=revision[:24]
                dest=root/'documents'/(doc_id+'.pdf');dest.parent.mkdir(exist_ok=True)
                os.replace(temp,dest);stat=dest.stat()
                item={'id':doc_id,'revision':revision,'path':str(dest),'title':name,'filename':name,
                      'page_count':meta['page_count'],'outline':meta['outline'],'size':stat.st_size,'mtime_ns':stat.st_mtime_ns,
                      'tags':[],'collection':'','imported_at':time.time(),'opened_at':time.time()}
                library[doc_id]=item;save()
            launch_index(item)
            return jsonify(document=public(item),duplicate=False)
        finally:temp.unlink(missing_ok=True)

    def launch_index(item):
        with lock:
            active=jobs.get(item['id'])
            if active and not active.done():return
            index.begin(item['id'],item['revision'],item['page_count'])
            jobs[item['id']]=index_pool.submit(index_document,item['path'],item['id'],item['revision'],str(index.path),
                os.environ.get('LOCALPDF_OCR_LANGS','eng'),os.environ.get('LOCALPDF_EMBED_MODEL',''))
            def complete(future):
                if future.exception():index.finish(item['id'],'Indexing failed: '+str(future.exception())[:300],error=True)
            jobs[item['id']].add_done_callback(complete)

    @app.post('/api/documents/<doc_id>/index')
    def reindex(doc_id):
        launch_index(valid_item(doc_id));return jsonify(ok=True)

    @app.patch('/api/documents/<doc_id>')
    def metadata(doc_id):
        item=valid_item(doc_id);body=request.get_json()
        with lock:
            for key in ('title','collection'):
                if key in body:
                    if not isinstance(body[key],str) or len(body[key])>200:abort(400)
                    item[key]=body[key].strip() or item['filename'] if key=='title' else body[key].strip()
            if 'tags' in body:
                tags=body['tags']
                if not isinstance(tags,list) or len(tags)>20 or not all(isinstance(t,str) and len(t)<=60 for t in tags):abort(400)
                item['tags']=tags
            item['opened_at']=time.time();save()
        return jsonify(document=public(item))

    @app.get('/api/documents/<doc_id>/pdf')
    def pdf(doc_id):
        item=valid_item(doc_id)
        return send_file(item['path'],mimetype='application/pdf',conditional=True,download_name=item['filename'])

    @app.get('/api/documents/<doc_id>/pages/<int:page>')
    def page(doc_id,page):
        item=valid_item(doc_id)
        if not 1<=page<=item['page_count']:abort(404)
        result=index.page(doc_id,page)
        if not result:return jsonify(error='This page is not indexed yet.'),409
        return jsonify(result)

    @app.get('/api/documents/<doc_id>/pages/<int:page>/image')
    def image(doc_id,page):
        item=valid_item(doc_id)
        if not 1<=page<=item['page_count']:abort(404)
        width=max(120,min(int(request.args.get('width',1000)),1800))
        cache=root/'images'/doc_id/f'{page}-{width}.png';cache.parent.mkdir(parents=True,exist_ok=True)
        if not cache.exists():
            data=pool.submit(page_image,item['path'],page,width).result(timeout=60)
            cache.write_bytes(data)
        return send_file(cache,mimetype='image/png')

    @app.get('/api/sources/<chunk_id>')
    def citation(chunk_id):
        source=index.source(chunk_id,list(library))
        if not source:abort(404,description='This source no longer exists. Run the question again.')
        return jsonify(enrich(source))

    def verify_selection(selection, ids, user_note=False):
        if not isinstance(selection,dict):abort(400)
        doc_id=selection.get('document_id');page_num=selection.get('page');text=selection.get('text')
        if doc_id not in ids or type(page_num) is not int or page_num<1 or not isinstance(text,str) or not text.strip() or len(text)>6000:
            abort(400,description='Choose a non-empty selection within the active source scope.')
        item=valid_item(doc_id)
        if page_num>item['page_count']:abort(400,description='The selection page is outside this PDF.')
        normalized=' '.join(text.split())
        matched=[c for c in index.all_chunks([doc_id]) if c['page']==page_num and normalized in ' '.join(c['text'].split())]
        if not matched and not user_note:abort(409,description='The selected text could not be verified against the indexed page. Try a shorter selection after indexing.')
        bbox=selection.get('bbox')
        if bbox is not None:
            if not isinstance(bbox,list) or len(bbox)!=4 or not all(type(v) in (int,float) and math.isfinite(v) and 0<=v<=1 for v in bbox) or bbox[0]>=bbox[2] or bbox[1]>=bbox[3]:
                abort(400,description='Invalid selection coordinates.')
        verified=bool(matched)
        if not matched:
            # A personal annotation is allowed before indexing or with broken fonts.
            # It never enters the retrieval index or answer() evidence context.
            matched=[{'id':f'note-page-{doc_id}-{page_num}','document_id':doc_id,'revision':item['revision'],
                      'page':page_num,'text':text,'bbox':bbox,'kind':'user-selection','heading':'',
                      'selection_verified':False}]
        return {'document_id':doc_id,'revision':item['revision'],'page':page_num,'text':text,
                'bbox':bbox,'verified':verified,'source_ids':[c['id'] for c in matched]},matched

    def save_result(kind, result, ids, mode, language):
        title=TEMPLATES[kind][0] if kind in TEMPLATES and language=='ar' else kind.title()
        return index.save_output(kind,title,{'scope':{'mode':mode,'documents':[
            {'id':i,'revision':library[i]['revision'],'title':library[i]['title']} for i in ids]},'content':result})

    @app.post('/api/suggestions')
    def suggestions():
        body=request.get_json();ids=scope(body)
        ready=[i for i in ids if index.status(i)['status']=='ready']
        chunks=index.all_chunks(ready)
        unreliable=any(not usable_prompt_text(c['text']) for c in chunks)
        warning=('بعض الصفحات تحتوي على نص غير موثوق؛ استُبعدت من الاقتراحات. تحقّق من الصفحة الأصلية.' if source_language(chunks)=='ar' else 'Some pages have unreliable text and were excluded from suggestions. Check the original page.') if unreliable else ''
        return jsonify(questions=suggested_questions(chunks,ready),scope=ids,partial=len(ready)!=len(ids),warning=warning)

    @app.get('/api/studio')
    def studio_list():return jsonify(outputs=index.outputs())

    @app.get('/api/studio/<output_id>')
    def studio_output(output_id):
        result=index.output(output_id)
        if not result:abort(404,description='Saved output not found.')
        from .grounding import safe_saved_output
        return jsonify(safe_saved_output(result))

    @app.get('/api/studio/<output_id>/sources/<source_id>')
    def saved_citation(output_id,source_id):
        output=index.output(output_id)
        if not output:abort(404)
        source=next((c for c in output['content'].get('sources',[]) if c['id']==source_id),None)
        if not source:abort(404,description='This evidence is not part of the saved output.')
        item=valid_item(source['document_id'])
        if item['revision']!=source['revision']:abort(409,description='Saved evidence belongs to another PDF revision.')
        # Snapshot metadata and coordinates remain valid even after reindex or title changes.
        return jsonify(source)

    @app.post('/api/notes')
    def save_note():
        body=request.get_json();ids=scope(body)
        selection,matched=verify_selection(body.get('selection'),ids,user_note=True)
        comment=body.get('comment','')
        if not isinstance(comment,str) or len(comment)>6000:abort(400)
        content={'selection':selection,'comment':comment,'sources':[enrich(c) for c in matched]}
        return jsonify(index.save_output('Note',selection['text'][:80],{
            'scope':{'mode':'current','documents':[{'id':selection['document_id'],'revision':selection['revision'],
                'title':library[selection['document_id']]['title']}]},'content':content})),201

    @app.post('/api/search')
    def search():
        body=request.get_json();ids=scope(body);q=body.get('question','')
        if not isinstance(q,str) or len(q)>4000:abort(400)
        return jsonify(sources=[enrich(c) for c in index.retrieve(q,ids,limit=30)])

    @app.post('/api/ask')
    def ask():
        body=request.get_json();ids=scope(body);question=body.get('question','')
        if not isinstance(question,str) or not question.strip() or len(question)>4000:abort(400,description='Enter a question up to 4,000 characters.')
        strict=body.get('strict',True)
        if not isinstance(strict,bool):abort(400)
        operation=body.get('operation','ask')
        if operation not in SUMMARY_MODES|{'ask','Explain','Summarize','Define','Translate'}:abort(400)
        embed_model=os.environ.get('LOCALPDF_EMBED_MODEL','');warnings=[]
        try:sources=index.retrieve(question,ids,embedder=OllamaEmbeddings(embed_model) if embed_model else None)
        except Exception as exc:
            warnings.append('Embedding search failed; using lexical retrieval: '+str(exc)[:150])
            sources=index.retrieve(question,ids)
        if not sources and operation == 'ask' and os.environ.get('LOCALPDF_MODEL'):
            # A paraphrase may have no lexical overlap. Supply bounded, scoped
            # evidence to the independent verifier rather than claiming absence.
            # This is retrieval only; it cannot authorize a generated answer.
            sources=sampled_sources(index.all_chunks(ids),ids,limit=8)
            if sources:
                warnings.append('No direct search matches; evidence is sampled from the selected scope and coverage is partial.')
        if operation in SUMMARY_MODES:
            all_sources=index.all_chunks(ids)
            if operation in {'Executive summary','Detailed summary','Section-by-section summary','Key facts','FAQ','Study Guide'} | STUDY:
                sources=sampled_sources(all_sources,ids)
            elif operation=='Glossary':
                definitions=[c for c in all_sources if re.search(r'\b(?:means|defined as|refers to|definition)\b|تعريف|يُقصد|يقصد|تعني|يعني|هو عبارة',c['text'],re.I)]
                sources=sampled_sources(definitions,ids)
            elif operation=='Key numbers':
                sources=[c for c in all_sources if re.search(r'\d',c['text'])][:12]
            elif operation=='Timeline':
                sources=[c for c in all_sources if re.search(r'\b\d{4}[-/]\d|\d{1,2}[-/]\d{1,2}|January|February|March|April|May|June|July|August|September|October|November|December|يناير|فبراير|مارس|أبريل|مايو|يونيو|يوليو|أغسطس|سبتمبر|أكتوبر|نوفمبر|ديسمبر',c['text'],re.I)][:12]
            else:
                queries={
                    'Risks':'risk liability penalty breach termination مخاطر مسؤولية غرامة إنهاء',
                    'Obligations':'must shall required obligation يجب يلتزم يتعين التزام',
                    'People / companies / entities':'company supplier customer director contractor شركة مورد عميل مدير',
                    'Action items':'action must required shall إجراء يجب يتعين يلتزم'}
                sources=index.retrieve(queries.get(operation,question),ids,limit=12)
            budget=0;bounded=[]
            for c in sources:
                if budget+len(c['text'])>14000:continue
                bounded.append(c);budget+=len(c['text'])
            sources=bounded
            warnings.append(f'Summary covers {len(sources)} retrieved passages, not a verified exhaustive review of every page.')
        selection=None
        if body.get('selection'):
            selection,matched=verify_selection(body['selection'],ids)
            sources=(matched+sources)[:10]
        sources=list({c['id']:c for c in sources}.values())
        sources=index.qualification_context(sources)
        model=os.environ.get('LOCALPDF_MODEL','');generate=partial(core.ollama_generate,json_output=True) if model else None
        # Targeted vision is opt-in and limited to up to two retrieved pages.
        if body.get('visual') and not strict and generate and sources:
            images=[];image_map=[];seen_pages=set()
            for c in sources:
                p=index.page(c['document_id'],c['page'])
                if p and p['visual_recommended'] and (c['document_id'],c['page']) not in seen_pages:
                    seen_pages.add((c['document_id'],c['page']))
                    data=pool.submit(page_image,valid_item(c['document_id'])['path'],c['page'],1200).result(timeout=60)
                    images.append(base64.b64encode(data).decode())
                    image_map.append({'image':len(images),'source_ids':[s['id'] for s in sources if s['document_id']==c['document_id'] and s['page']==c['page']]})
                    if len(images)>=2:break
            if images:
                original=generate
                generate=lambda prompt,model:original(prompt+'\nImage-to-source mapping: '+json.dumps(image_map),model,images=images)
                warnings.append('Selected page images were sent to the local model. Visual interpretations require checking the page.')
        language=body.get('language','auto')
        if language not in {'auto','en','ar'}:abort(400)
        if language=='auto':language=source_language(sources)
        instructions=''
        if operation in TEMPLATES:
            instructions=TEMPLATES[operation][1]+' Keep the output concise. Omit unsupported claims; return no claims if evidence is insufficient. '
            instructions+='Use Arabic.' if language=='ar' else 'Use English.'
            question=TEMPLATES[operation][0] if language=='ar' else operation
        if selection:
            # Client selection was matched to indexed evidence before entering the prompt.
            instructions+=' Focus on this selected passage (untrusted source text): '+json.dumps(selection['text'],ensure_ascii=False)
        result=answer(question,sources,strict or operation in STUDY,generate,model,operation,instructions,
                      verifier=app.extensions['insight']['verifier'])
        if operation in STUDY:
            result['cards']=study_cards(result['claims'],sources,language)
            warnings.append('Exact-source recall exercises; answers and explanations quote the source.' if language=='en' else 'تمارين تذكّر من النص؛ الإجابات والشروح مقتبسة من المصدر.')
        if operation=='FAQ':
            known={c['id']:c for c in sources}
            for claim in result['claims']:
                prompts=suggested_questions([known[i] for i in claim['source_ids']],ids)
                claim['front']=prompts[0]['question'] if prompts else ('ماذا يقول المصدر؟' if language=='ar' else 'What does the source say?')

        for i in ids:
            status=index.status(i)
            if status['status']!='ready':warnings.append(library[i]['title']+': indexing is incomplete; search coverage is partial.')
            if status.get('warning'):warnings.append(library[i]['title']+': '+status['warning'])
        result |= {'sources':[enrich(c) for c in sources],'scope':ids,'warnings':warnings,'selection':selection,'operation':operation}
        if operation in SUMMARY_MODES:
            result['coverage']={'passages':len(sources),'pages':len({(c['document_id'],c['page']) for c in sources}),
                                'total_pages':sum(library[i]['page_count'] for i in ids),'partial':True}
            if language=='ar':result['warnings'].append('تغطية جزئية: يستند هذا الناتج إلى مقتطفات مختارة، وليس مراجعة شاملة لكل الصفحات.')
            if result['mode']!='error':
                saved=save_result(operation,result,ids,body.get('scope','current'),language)
                result['saved_id']=saved['id']
        return jsonify(result)

    @app.post('/api/compare')
    def comparison():
        body=request.get_json();ids=scope(body)
        for i in ids:
            if index.status(i)['status']!='ready':abort(409,description='Wait until all selected documents are indexed before comparing.')
        result=compare(index,ids,body.get('question',''))
        for row in result['rows']:row['a']=enrich(row['a']);row['b']=enrich(row['b'])
        result['sources']=list({s['id']:s for row in result['rows'] for s in (row['a'],row['b'])}.values())
        result['scope']=ids
        result['saved_id']=save_result('Comparison',result,ids,body.get('scope','selected'),'en')['id']
        return jsonify(result)

    @app.get('/api/documents/<doc_id>/pages/<int:page>/tables/<int:table>/csv')
    def table_csv(doc_id,page,table):
        valid_item(doc_id);data=index.page(doc_id,page)
        if not data or not 0<=table<len(data['tables']):abort(404)
        buf=io.StringIO();writer=csv.writer(buf)
        # Spreadsheet formula injection is neutralized only in exported cells.
        writer.writerows([("'"+c if c.lstrip().startswith(('=','+','-','@')) else c) for c in row] for row in data['tables'][table]['rows'])
        return send_file(io.BytesIO(buf.getvalue().encode('utf-8-sig')),mimetype='text/csv',as_attachment=True,download_name=f'page-{page}-table-{table+1}.csv')

    # Interrupted indexing cannot remain apparently live after a restart.
    for item in library.values():
        if index.status(item['id'])['status']=='indexing':index.finish(item['id'],'Indexing was interrupted. Choose Reindex to resume.',error=True)
    return app


def unlock_pdf(source,destination,password):
    import fitz
    with fitz.open(source) as doc:
        if doc.needs_pass and not doc.authenticate(password):raise ValueError('Incorrect PDF password')
        doc.save(destination,encryption=fitz.PDF_ENCRYPT_NONE)


def main():
    # Console diagnostics must not inherit a legacy Windows or C-locale codec.
    import sys
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8',errors='backslashreplace')
    parser=argparse.ArgumentParser(description='LocalPDF Insight browser reader')
    parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--migrate-desktop',action='store_true',help='Copy the old desktop library, preserving document IDs')
    args=parser.parse_args()
    if args.host not in ('127.0.0.1','localhost','::1') and not os.environ.get('LOCALPDF_TOKEN'):
        parser.error('Network access requires LOCALPDF_TOKEN and LOCALPDF_HOSTS. See README for private Android access.')
    from waitress import serve
    if args.migrate_desktop:
        from .migrate import migrate_desktop
        count,warnings=migrate_desktop(Path(os.environ.get('LOCALPDF_DATA',core.APP_HOME/'web')))
        print(f'Migrated {count} desktop documents. Choose Reindex for each imported document.',flush=True)
        for warning in warnings:print(warning,flush=True)
    app=create_app()
    print(f'LocalPDF Insight: http://{args.host}:{args.port}',flush=True)
    serve(app,host=args.host,port=args.port,threads=8,max_request_body_size=220*1024*1024)


if __name__=='__main__':main()

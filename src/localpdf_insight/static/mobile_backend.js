/* Android reader adapter. No server, model, network request or AI answer path.
 * PDF.js is the existing renderer/extractor; IndexedDB holds this device's copies.
 * Desktop SQLite/retrieval/verification are deliberately untouched.
 */
const DB_NAME='localpdf-android-reader-v1';
const clamp=n=>Math.max(0,Math.min(1,n));
const normal=text=>text.normalize('NFKC').toLocaleLowerCase().replace(/[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed\u0640]/g,'')
 .replace(/[أإآٱ]/g,'ا').replace(/ى/g,'ي').replace(/[٠-٩]/g,c=>String(c.charCodeAt(0)-0x660));
const terms=text=>[...new Set(normal(text).match(/[\p{L}\p{N}]+/gu)||[])];
const hash=async data=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',data)),b=>b.toString(16).padStart(2,'0')).join('');
const now=()=>Date.now()/1000;
const pause=()=>new Promise(resolve=>setTimeout(resolve,0));
const PDF_OPTIONS={cMapUrl:'/static/vendor/pdfjs/cmaps/',cMapPacked:true,
 standardFontDataUrl:'/static/vendor/pdfjs/standard_fonts/',wasmUrl:'/static/vendor/pdfjs/wasm/',
 iccUrl:'/static/vendor/pdfjs/iccs/',isEvalSupported:false,enableXfa:false};

function openStore(){return new Promise((resolve,reject)=>{
 const request=indexedDB.open(DB_NAME,1);
 request.onupgradeneeded=()=>{
  const db=request.result;
  db.createObjectStore('documents',{keyPath:'id'});db.createObjectStore('pdfs',{keyPath:'id'});
  for(const name of ['pages','sources'])db.createObjectStore(name,{keyPath:'id'}).createIndex('document_id','document_id');
  db.createObjectStore('outputs',{keyPath:'id'});
 };
 request.onsuccess=()=>resolve(request.result);
 request.onerror=()=>reject(Error('Could not open private phone storage. Close and reopen the app.'));
 request.onblocked=()=>reject(Error('Close other LocalPDF windows to upgrade storage.'));
});}

export async function createMobileBackend(pdfjs){
 const db=await openStore(),jobs=new Map(),urls=new Map();
 const write=(names,action)=>new Promise((resolve,reject)=>{
  const tx=db.transaction(names,'readwrite');
  tx.oncomplete=()=>resolve();tx.onerror=tx.onabort=()=>reject(Error(tx.error?.name==='QuotaExceededError'?
   'Phone storage is full. This file was not saved. Free some space and retry.':'Could not save to phone storage. Please retry.'));
  try{action(tx);}catch(e){tx.abort();reject(e);}
 });
 const read=(store,key,indexName)=>new Promise((resolve,reject)=>{
  const tx=db.transaction(store),table=indexName?tx.objectStore(store).index(indexName):tx.objectStore(store);
  const request=key===undefined?table.getAll():indexName?table.getAll(key):table.get(key);
  request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(Error('Could not read phone storage.'));
 });
 const modify=(id,fn)=>write(['documents'],tx=>{
  const table=tx.objectStore('documents'),request=table.get(id);
  request.onsuccess=()=>{if(request.result)table.put(fn(request.result));};
 });
 async function item(id){const doc=await read('documents',id);if(!doc)throw Error('Document is no longer available on this phone.');return doc;}
 async function scope(body){
  let ids=body.scope==='library'?(await read('documents')).map(d=>d.id):body.scope==='selected'?body.document_ids:body.scope==='current'||!body.scope?[body.current_id]:null;
  if(!Array.isArray(ids)||!ids.length||ids.length>100||ids.some(id=>typeof id!=='string'))throw Error('Open or select at least one document.');
  ids=[...new Set(ids)];await Promise.all(ids.map(item));return ids;
 }
 async function enrich(source){const doc=await item(source.document_id);if(doc.revision!==source.revision)throw Error('The source belongs to another PDF revision.');
  return {...source,document_name:doc.title,filename:doc.filename,extraction_method:'native',extraction_warnings:[]};}
 async function clearIndex(id){await write(['pages','sources'],tx=>{
  for(const name of ['pages','sources']){const table=tx.objectStore(name),cursor=table.index('document_id').openCursor(id);
   cursor.onsuccess=()=>{const row=cursor.result;if(row){row.delete();row.continue();}};}
 });}

 function pageUnits(page,content){
  const view=page.getViewport({scale:1}),units=[];let text=[],boxes=[],previous=null,space=false;
  function flush(){if(!text.length)return;units.push({ordinal:units.length,kind:'paragraph',heading:'',text:text.join(''),
   bbox:[Math.min(...boxes.map(b=>b[0])),Math.min(...boxes.map(b=>b[1])),Math.max(...boxes.map(b=>b[2])),Math.max(...boxes.map(b=>b[3]))]});text=[];boxes=[];previous=null;space=false;}
  for(const token of content.items){
   if(typeof token.str!=='string')continue;
   // Arabic PDFs often emit one shaped glyph per item. Whitespace is data;
   // inserting a space between every item destroys Arabic word searches.
   if(!token.str.trim()){if(token.str)space=true;if(token.hasEOL)flush();continue;}
   // Follow the text layer's font ascent and baseline directions, including
   // intrinsic page rotation and rotated text. PDF coordinates point upward.
   const transform=pdfjs.Util.transform(view.transform,token.transform),font=content.styles[token.fontName]||{};
   const height=Math.max(Math.hypot(transform[2],transform[3]),1),width=Math.max(token.width||1,1)*view.scale;
   const angle=Math.atan2(transform[1],transform[0])+(font.vertical?Math.PI/2:0),ascent=(font.ascent??.8)*height;
   const x=transform[4]+ascent*Math.sin(angle),y=transform[5]-ascent*Math.cos(angle);
   const dx=Math.cos(angle)*width,dy=Math.sin(angle)*width,hx=-Math.sin(angle)*height,hy=Math.cos(angle)*height;
   const xs=[x,x+dx,x+hx,x+dx+hx],ys=[y,y+dy,y+hy,y+dy+hy];
   const box=[clamp(Math.min(...xs)/view.width),clamp(Math.min(...ys)/view.height),clamp(Math.max(...xs)/view.width),clamp(Math.max(...ys)/view.height)];
   const projection=transform[4]*Math.cos(angle)+transform[5]*Math.sin(angle);
   if(text.join('').length+token.str.length>1800)flush();
   const gap=previous?Math.max(previous.start-(projection+width),projection-previous.end,0):0;
   const separator=text.length&&(space||gap>Math.min(height,previous?.height||height)*.12)?' ':'';
   text.push(separator+token.str);boxes.push(box);previous={start:projection,end:projection+width,height};space=false;if(token.hasEOL)flush();
  }
  flush();return {units,width:view.width,height:view.height,rotation:page.rotate};
 }

 async function buildIndex(doc,password=''){
  let task;let emptyPages=0;let arabicWarning=false;
  try{
   await clearIndex(doc.id);
   await modify(doc.id,d=>({...d,index:{status:'indexing',done:0,total:d.page_count,warning:''}}));
   const stored=await read('pdfs',doc.id);if(!stored)throw Error('The stored PDF could not be found.');
   task=pdfjs.getDocument({...PDF_OPTIONS,data:new Uint8Array(await stored.blob.arrayBuffer()),password});
   const pdf=await task.promise;
   for(let n=1;n<=pdf.numPages;n++){
    const page=await pdf.getPage(n),content=await page.getTextContent(),data=pageUnits(page,content);
    const sources=[];
    for(const unit of data.units){const id=(await hash(new TextEncoder().encode(`${doc.id}|${doc.revision}|${n}|${unit.ordinal}|${unit.text}`))).slice(0,32);
     sources.push({...unit,id,document_id:doc.id,revision:doc.revision,page:n});}
    if(!sources.length)emptyPages++;
    const pageWarning=/[\ufb50-\ufdff\ufe70-\ufeff\ufffd]/.test(data.units.map(u=>u.text).join(''));
    arabicWarning=arabicWarning||pageWarning;
    const warning=[emptyPages?`${emptyPages} page(s) have no selectable text. Scans can be read, but OCR is not included in this Android version.`:'',
     arabicWarning?'Font mappings or shaped Arabic text need verification against the original page; some word searches may be incomplete.':''].filter(Boolean).join('\n');
    await write(['pages','sources'],tx=>{
     tx.objectStore('pages').put({id:doc.id+':'+n,document_id:doc.id,page:n,text:data.units.map(u=>u.text).join('\n'),
      ...data,method:'native',tables:[],visual_recommended:false,warnings:[...(!sources.length?['Image-only page; OCR is not available.']:[]),
       ...(pageWarning?['Font mappings or shaped Arabic text need verification against the original page.']:[])]});
     for(const source of sources)tx.objectStore('sources').put(source);
    });
    await modify(doc.id,d=>({...d,index:{status:'indexing',done:n,total:doc.page_count,warning}}));
    page.cleanup();await pause();
   }
   await modify(doc.id,d=>({...d,index:{...d.index,status:'ready'}}));
  }catch(error){await modify(doc.id,d=>({...d,index:{...d.index,status:'error',warning:/password/i.test(error.message)?
   'Reopen this PDF with its password, then retry indexing. Passwords are not stored.':`Text indexing failed: ${error.message}`}}));}
  finally{try{if(task)await task.destroy();}finally{jobs.delete(doc.id);}}
 }
 function launchIndex(doc,password){if(!jobs.has(doc.id)){const job=buildIndex(doc,password);jobs.set(doc.id,job);}}

 async function importPdf(form){
  const file=form.get('file');if(!(file instanceof Blob)||!file.size)throw Error('Choose a PDF file.');
  if(file.size>200*1024*1024)throw Error('This file exceeds the 200 MB import limit.');
  const bytes=await file.arrayBuffer(),revision=await hash(bytes),id=revision.slice(0,24),duplicate=await read('documents',id);
  if(duplicate){await modify(id,d=>({...d,opened_at:now()}));return {document:await item(id),duplicate:true};}
  let task;
  try{
   const password=String(form.get('password')||'');
   task=pdfjs.getDocument({...PDF_OPTIONS,data:new Uint8Array(bytes),password});
   const pdf=await task.promise,outline=await pdf.getOutline();
   const filename=(file.name||'document.pdf').split(/[\\/]/).at(-1).slice(0,200);
   const doc={id,revision,title:filename,filename,page_count:pdf.numPages,outline:outline||[],size:file.size,
    tags:[],collection:'',imported_at:now(),opened_at:now(),index:{status:'indexing',done:0,total:pdf.numPages,warning:''}};
   await write(['documents','pdfs'],tx=>{tx.objectStore('documents').add(doc);tx.objectStore('pdfs').add({id,blob:new Blob([file],{type:'application/pdf'})});});
   launchIndex(doc,password);return {document:doc,duplicate:false};
  }catch(e){throw Error(/password/i.test(e.message)?'PDF password required or incorrect.':`Could not import PDF: ${e.message}`);}
  finally{if(task)await task.destroy();}
 }

 async function saveNote(body){
  const ids=await scope(body),selection=body.selection;
  if(!selection||!ids.includes(selection.document_id)||!Number.isInteger(selection.page)||selection.page<1||typeof selection.text!=='string'||!selection.text.trim()||selection.text.length>6000)throw Error('Select text within an open PDF.');
  const doc=await item(selection.document_id);if(selection.page>doc.page_count)throw Error('The note page is outside this PDF.');
  const bbox=selection.bbox??null;
  if(bbox!==null&&(!Array.isArray(bbox)||bbox.length!==4||bbox.some(v=>typeof v!=='number'||!Number.isFinite(v)||v<0||v>1)||bbox[0]>=bbox[2]||bbox[1]>=bbox[3]))throw Error('Invalid selection coordinates.');
  const comment=body.comment||'';if(typeof comment!=='string'||comment.length>6000)throw Error('Keep the note within 6,000 characters.');
  const source={id:(await hash(new TextEncoder().encode(`note|${doc.id}|${doc.revision}|${selection.page}|${selection.text}`))).slice(0,32),
   document_id:doc.id,revision:doc.revision,page:selection.page,text:selection.text,bbox,kind:'user-selection',heading:'',
   document_name:doc.title,filename:doc.filename};
  const note={id:crypto.randomUUID().replaceAll('-',''),kind:'Note',title:selection.text.slice(0,80),created_at:now(),
   scope:{mode:'current',documents:[{id:doc.id,revision:doc.revision,title:doc.title}]},
   content:{selection:{...selection,revision:doc.revision,verified:false,source_ids:[source.id]},comment,sources:[source]}};
  await write(['outputs'],tx=>tx.objectStore('outputs').add(note));return note;
 }

 async function search(body){
  const ids=await scope(body);if(typeof body.question!=='string'||body.question.length>4000)throw Error('Enter a search term up to 4,000 characters.');
  const query=terms(body.question);if(!query.length)return {sources:[]};
  const groups=await Promise.all(ids.map(id=>read('sources',id,'document_id'))),ranked=[];
  for(const source of groups.flat()){const words=new Set(terms(source.text)),matches=query.filter(t=>words.has(t)).length;
   if(matches)ranked.push({...source,score:matches/query.length+(normal(source.text).includes(normal(body.question))?1:0)});}
  ranked.sort((a,b)=>b.score-a.score||a.document_id.localeCompare(b.document_id)||a.page-b.page);
  return {sources:await Promise.all(ranked.slice(0,30).map(enrich))};
 }

 async function request(path,options={}){
  const method=options.method||'GET',body=options.body||{};let match;
  if(path==='/api/config')return {model:'',embedding_model:'',languages:'native text only',templates:[],summary_modes:[],platform:'android'};
  if(path==='/api/documents')return {documents:(await read('documents')).sort((a,b)=>b.opened_at-a.opened_at)};
  if(path==='/api/import'&&method==='POST')return importPdf(body);
  if(path==='/api/suggestions')return {questions:[],scope:await scope(body),partial:false};
  if(path==='/api/ask'||path==='/api/compare')throw Error('AI and comparisons are not included in this Android reader.');
  if(path==='/api/search')return search(body);
  if(path==='/api/notes'&&method==='POST')return saveNote(body);
  if(path==='/api/studio')return {outputs:(await read('outputs')).sort((a,b)=>b.created_at-a.created_at).map(({id,kind,title,created_at})=>({id,kind,title,created_at}))};
  if((match=path.match(/^\/api\/studio\/([^/]+)(?:\/sources\/([^/]+))?$/))){
   const output=await read('outputs',decodeURIComponent(match[1]));if(!output)throw Error('Note not found.');
   if(!match[2])return output;
   const source=output.content.sources.find(s=>s.id===decodeURIComponent(match[2]));if(!source)throw Error('This source is not part of this note.');
   const doc=await item(source.document_id);if(doc.revision!==source.revision)throw Error('This note belongs to another PDF revision.');return source;
  }
  if((match=path.match(/^\/api\/sources\/([^/]+)$/))){const source=await read('sources',decodeURIComponent(match[1]));if(!source)throw Error('This passage is not indexed yet.');return enrich(source);}
  if((match=path.match(/^\/api\/documents\/([^/]+)(?:\/(index|pages\/\d+))?$/))){
   const doc=await item(decodeURIComponent(match[1]));
   if(method==='PATCH'){
    for(const k of ['title','collection'])if(k in body&&(typeof body[k]!=='string'||body[k].length>200))throw Error('Invalid document title or collection.');
    if(body.tags&&(!Array.isArray(body.tags)||body.tags.length>20||body.tags.some(t=>typeof t!=='string'||t.length>60)))throw Error('Invalid tags.');
    await modify(doc.id,d=>({...d,...('title'in body?{title:body.title.trim()||d.filename}:{}),...('collection'in body?{collection:body.collection.trim()}:{}),...('tags'in body?{tags:body.tags}:{}),opened_at:now()}));return {document:await item(doc.id)};
   }
   if(match[2]==='index'){launchIndex(doc,body.password||'');return {ok:true};}
   if(match[2]?.startsWith('pages/')){const n=Number(match[2].split('/')[1]);if(n<1||n>doc.page_count)throw Error('Page not found.');const page=await read('pages',doc.id+':'+n);if(!page)throw Error('This page is not indexed yet.');return page;}
  }
  throw Error('This operation is not available in the Android reader.');
 }
 async function documentUrl(id){
  await item(id);
  if(!urls.has(id)){const stored=await read('pdfs',id);if(!stored)throw Error('The PDF copy is missing.');urls.set(id,URL.createObjectURL(stored.blob));}
  return urls.get(id);
 }
 // Never silently leave interrupted work looking live after a process restart.
 for(const doc of await read('documents'))if(doc.index.status==='indexing')await modify(doc.id,d=>({...d,index:{...d.index,status:'error',warning:'Text indexing was interrupted. Reopen the PDF and choose Retry indexing.'}}));
 async function analysisSnapshot(id){
  const document=await item(id);if(document.index.status!=='ready')throw Error('Wait for this PDF to finish indexing.');
  const sources=await read('sources',id,'document_id');
  return {document,sources};
 }
 return {request,documentUrl,analysisSnapshot,resume:async(id,password='')=>{const doc=await item(id);if(doc.index.status!=='ready')launchIndex(doc,password);}};
}

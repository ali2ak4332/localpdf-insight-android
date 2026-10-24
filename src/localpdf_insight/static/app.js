import * as pdfjsLib from './vendor/pdfjs/build/pdf.mjs';
const {EventBus,PDFViewer,PDFLinkService,PDFFindController} = await import('./vendor/pdfjs/web/pdf_viewer.mjs');
pdfjsLib.GlobalWorkerOptions.workerSrc='/static/vendor/pdfjs/build/pdf.worker.mjs';
const androidMode=new URLSearchParams(location.search).get('platform')==='android';
let mobileBackend=null;
if(androidMode){try{mobileBackend=await (await import('./mobile_backend.js')).createMobileBackend(pdfjsLib);}catch(error){
 const empty=document.getElementById('emptyState');empty.replaceChildren();const title=document.createElement('h2'),detail=document.createElement('p');title.textContent='Phone storage is unavailable';detail.textContent=error.message;empty.append(title,detail);for(const control of document.querySelectorAll('button,input,select'))control.disabled=true;throw error;
}}
const $=id=>document.getElementById(id);
const state={documents:[],selected:new Set(),current:null,pdf:null,loading:null,generation:0,selection:null,highlight:null,
  config:{},lang:localStorage.getItem('insight-language')||'en',searchSources:[],searchIndex:0,online:true,askGeneration:0};
const translations={
 ar:{tagline:'اقرأ بتمعّن. تحقّق من الدليل.',private:'معالجة محلية',install:'تثبيت',ask:'اسأل وتحقّق',workspace:'مساحتك الخاصة',library:'المكتبة',open:'+ فتح مستند',dropHint:'اسحب ملفات PDF هنا أو اختر ملفاً.',filter:'العنوان أو الوسم أو المجموعة',searchAll:'البحث في نصوص المكتبة',compare:'مقارنة المستندات المحددة',privacy:'الخصوصية والمعالجة',privacyDetail:'تجري القراءة في متصفحك. تبقى الملفات المستوردة والفهارس على خادم LocalPDF الخاص بك. تُرسل الأدلة المطلوبة فقط إلى Ollama المحلي. لا توجد خدمة ذكاء اصطناعي خارجية. لا يحفظ وضع عدم الاتصال ملفاتك.',noDocument:'لم يُفتح أي مستند',fitWidth:'ملاءمة العرض',fitPage:'ملاءمة الصفحة',continuous:'متتابع',single:'صفحة واحدة',spread:'صفحتان',searchPdf:'البحث في هذا المستند…',ocrSearch:'نتائج الفهرس',contents:'المحتويات',pages:'الصفحات',readerFirst:'القراءة أولاً',emptyTitle:'مساحة لقراءة<br>أكثر تمعّناً.',emptyBody:'افتح مستنداً. اعثر على النص.<br>اطرح سؤالك. تحقّق من الدليل.',choose:'اختر ملف PDF',localNote:'مستنداتك. مساحتك المحلية.',shortcuts:'Ctrl+O فتح · Ctrl+F بحث · Ctrl+K سؤال',tables:'جداول هذه الصفحة',grounded:'الإجابة من مستنداتك',scope:'نطاق البحث',thisPdf:'اسأل هذا المستند',selected:'اسأل المستندات المحددة',allLibrary:'اسأل المكتبة',strict:'وضع الأدلة الصارم',strictDetail:'اقتباسات مطابقة للمصدر فقط. تُرفض الادعاءات المولدة غير المدعومة.',visual:'فحص صور الصفحات ذات الصلة بالذكاء المحلي',question:'ماذا يقول المستند عن…؟',questionMode:'سؤال',askButton:'اسأل',evidenceTitle:'إجابة تستطيع التحقّق منها.',evidenceBody:'يفتح كل مصدر الصفحة الأصلية. ابدأ بسؤالك أعلاه.',unlock:'الاتصال بالقارئ',accessDetail:'أدخل مفتاح الوصول الذي أعددته على خادم LocalPDF.',connect:'اتصال',editDetails:'تفاصيل المستند',save:'حفظ',cancel:'إلغاء'},
 en:{tagline:'Read closely. Answer with evidence.',private:'Local processing',install:'Install app',ask:'Ask & verify',workspace:'YOUR WORKSPACE',library:'Library',open:'+ Open PDF',dropHint:'Drop PDFs here, or choose a file.',filter:'Title, tag or collection',searchAll:'Search text across library',compare:'Compare selected PDFs',privacy:'Privacy & processing',privacyDetail:'Reading runs in this browser. Imported files and indexes stay on your LocalPDF server. Only relevant evidence is sent to local Ollama. No external AI is configured. Offline mode does not store your PDFs.',noDocument:'No document open',fitWidth:'Fit width',fitPage:'Fit page',continuous:'Continuous',single:'Single page',spread:'Two pages',searchPdf:'Search this PDF…',ocrSearch:'OCR results',contents:'Contents',pages:'Pages',readerFirst:'A READER, FIRST.',emptyTitle:'Make room for<br>closer reading.',emptyBody:'Open a document. Find the passage.<br>Ask a question. Check the evidence.',choose:'Choose a PDF',localNote:'Your documents. Your local workspace.',shortcuts:'Ctrl+O open · Ctrl+F search · Ctrl+K ask',tables:'Tables on this page',grounded:'GROUNDED IN YOUR DOCUMENTS',scope:'Search scope',thisPdf:'Ask this PDF',selected:'Ask selected documents',allLibrary:'Ask library',strict:'Strict Evidence Mode',strictDetail:'Exact source excerpts only. Unsupported generated claims are rejected.',visual:'Inspect relevant page images with local AI',question:'What does the document say about…?',questionMode:'Question',askButton:'Ask',evidenceTitle:'An answer you can inspect.',evidenceBody:'Every source opens the original page. Start with a question above.',unlock:'Connect to your reader',accessDetail:'Enter the access key configured on your LocalPDF server.',connect:'Connect',editDetails:'Document details',save:'Save',cancel:'Cancel'}
};
Object.assign(translations.en,{sources:'Sources',chat:'Chat',studio:'Studio',chooseSources:'Choose sources',studioHint:'Create from the active sources. Each output is saved as a new snapshot.',create:'Create',savedOutputs:'Saved outputs & notes',allOutputs:'All outputs',notes:'Notes',saveNote:'Save note',comment:'Your comment (optional)'});
Object.assign(translations.ar,{sources:'المصادر',chat:'المحادثة',studio:'الاستوديو',chooseSources:'اختيار المصادر',studioHint:'أنشئ من المصادر النشطة. يُحفظ كل ناتج كنسخة جديدة.',create:'إنشاء',savedOutputs:'النواتج والملاحظات المحفوظة',allOutputs:'كل النواتج',notes:'الملاحظات',saveNote:'حفظ ملاحظة',comment:'تعليقك (اختياري)'});
if(androidMode){
 Object.assign(translations.en,{tagline:'Your private PDF reader.',private:'On this phone',ask:'Search results',studio:'Notes',chat:'Passages',grounded:'YOUR PDF SOURCES',scope:'Search scope',thisPdf:'This PDF',selected:'Selected PDFs',allLibrary:'All PDFs',studioHint:'Notes stay on this phone. Tap a source to return to its page.',savedOutputs:'Saved notes',allOutputs:'All notes',privacyDetail:'PDF copies, extracted text, reading positions and notes stay in this app on your phone. Optional Gemma analysis runs on this phone after model import. There is no upload, computer server or OCR. Removing the app removes its saved data.',ocrSearch:'Passage results',shortcuts:'Read · Search · Save a note',localNote:'Private. Works without a computer.',emptyBody:'Open a PDF. Search its text.<br>Save a note. Return to its page.',evidenceTitle:'Search your PDFs.',evidenceBody:'Search results link to the original page. No AI answers are generated.'});
 Object.assign(translations.ar,{tagline:'قارئ مستنداتك الخاص.',private:'على هذا الهاتف',ask:'نتائج البحث',studio:'الملاحظات',chat:'المقتطفات',grounded:'مصادر مستنداتك',scope:'نطاق البحث',thisPdf:'هذا المستند',selected:'المستندات المحددة',allLibrary:'كل المستندات',studioHint:'تُحفظ الملاحظات على هاتفك. اضغط المصدر للعودة إلى صفحته.',savedOutputs:'الملاحظات المحفوظة',allOutputs:'كل الملاحظات',privacyDetail:'تبقى نسخ المستندات والنصوص ومواضع القراءة والملاحظات في هذا التطبيق على هاتفك. يعمل تحليل Gemma الاختياري على هذا الهاتف بعد استيراد النموذج. لا يوجد رفع ملفات أو خادم حاسوب أو تعرّف بصري. حذف التطبيق يحذف بياناته.',ocrSearch:'نتائج المقتطفات',shortcuts:'اقرأ · ابحث · احفظ ملاحظة',localNote:'خاص. يعمل دون حاسوب.',emptyBody:'افتح مستنداً. ابحث في نصه.<br>احفظ ملاحظة. عُد إلى صفحتها.',evidenceTitle:'ابحث في مستنداتك.',evidenceBody:'تفتح نتائج البحث الصفحة الأصلية. لا تُولَّد إجابات بالذكاء الاصطناعي.'});
}
const t=key=>translations[state.lang][key]||key;
const el=(tag,cls,text)=>{const node=document.createElement(tag);if(cls)node.className=cls;if(text!==undefined)node.textContent=text;return node;};
function toast(text){$('toast').textContent=text;$('toast').hidden=false;clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('toast').hidden=true,6500);}
async function api(path,options={}){
 if(mobileBackend){if(path.endsWith('/index')&&state.current&&path.includes(state.current.id))options.body={...options.body,password:state.openedPassword||''};return mobileBackend.request(path,options);}
 const headers={'X-LocalPDF':'1',...options.headers};
 if(options.body && !(options.body instanceof FormData)){headers['Content-Type']='application/json';options.body=JSON.stringify(options.body);}
 const response=await fetch(path,{...options,headers});
 if(response.status===401){if(!$('loginDialog').open)$('loginDialog').showModal();throw Error(state.lang==='ar'?'مفتاح الوصول مطلوب.':'Access key required.');}
 const data=await response.json();if(!response.ok)throw Error(data.error||`Request failed (${response.status})`);return data;
}
function handle(fn){return (...args)=>Promise.resolve(fn(...args)).catch(e=>toast(e.message));}
const eventBus=new EventBus();
const linkService=new PDFLinkService({eventBus,externalLinkTarget:2,externalLinkRel:'noopener noreferrer'});
const findController=new PDFFindController({eventBus,linkService});
const viewer=new PDFViewer({container:$('viewerContainer'),viewer:$('viewer'),eventBus,linkService,findController,
 textLayerMode:1,annotationMode:androidMode?pdfjsLib.AnnotationMode.ENABLE_FORMS:pdfjsLib.AnnotationMode.ENABLE,maxCanvasPixels:8_000_000,maxCanvasDim:4096,enableDetailCanvas:true,
 supportsPinchToZoom:true,enableAutoLinking:false,enablePermissions:true,
 ...(androidMode?{annotationEditorHighlightColors:'yellow=#FFFF98'}:{})});
linkService.setViewer(viewer);
let mobileToolbar=null,mobileReading=null,aptPanel=null;
const editor=androidMode?(await import('./pdf_editor.js')).createPdfEditor({viewer,eventBus,pdfjs:pdfjsLib,state,backend:mobileBackend,openDocument,refreshDocuments,toast,language:()=>state.lang}):null;
function readPosition(id){try{return JSON.parse(localStorage.getItem('insight-read-'+id)||'null');}catch{return null;}}
function savePosition(){if(!state.current||!state.pdf)return;try{localStorage.setItem('insight-read-'+state.current.id,JSON.stringify({page:viewer.currentPageNumber,zoom:viewer.currentScaleValue,mode:$('viewMode').value,rotation:viewer.pagesRotation,top:$('viewerContainer').scrollTop,left:$('viewerContainer').scrollLeft}));localStorage.setItem('insight-zoom',viewer.currentScaleValue);}catch{}}
function gotoPage(page){clearTimeout(state.restoreTimer);if(!state.pdf)return;viewer.currentPageNumber=Math.max(1,Math.min(state.pdf.numPages,Number(page)||1));$('pageNumber').value=viewer.currentPageNumber;}
function setLayout(mode){viewer.spreadMode=mode==='spread'?1:0;viewer.scrollMode=mode==='single'?3:0;$('viewMode').value=mode;}
function zoomBy(factor){if(!state.pdf)return;viewer.currentScale=Math.max(.25,Math.min(5,viewer.currentScale*factor));$('zoom').value='custom';savePosition();}
eventBus.on('pagechanging',({pageNumber})=>{$('pageNumber').value=pageNumber;savePosition();});
eventBus.on('scalechanging',()=>{const scale=String(viewer.currentScaleValue);$('zoom').value=[...$('zoom').options].some(o=>o.value===scale)?scale:'custom';});
eventBus.on('updateviewarea',()=>{clearTimeout(savePosition.timer);savePosition.timer=setTimeout(savePosition,250);});
eventBus.on('pagerendered',()=>highlightEvidence());
eventBus.on('updatefindmatchescount',({matchesCount})=>{$('findCount').textContent=`${matchesCount.current} / ${matchesCount.total}`;});
eventBus.on('updatefindcontrolstate',({state:findState,matchesCount})=>{if(findState===1)$('findCount').textContent=state.lang==='ar'?'لا توجد نتائج':'No matches';else if(matchesCount)$('findCount').textContent=`${matchesCount.current} / ${matchesCount.total}`;});
async function loadPdf(source,title,current=null,password='',editorReplacement=false){
 if(editor&&!editor.beforeLoad(editorReplacement))return false;
 savePosition();aptPanel?.documentChanged();clearTimeout(state.restoreTimer);state.openedPassword=password;const generation=++state.generation;state.highlight=null;clearSelection();state.searchSources=[];
 const previous=state.loading;state.loading=null;if(previous)await previous.destroy();
 if(generation!==state.generation)return;
 viewer.setDocument(null);linkService.setDocument(null);state.pdf=null;state.current=current;mobileReading?.screen(false);mobileReading?.documentChanged();
 $('documentTitle').textContent=title;$('emptyState').hidden=true;$('indexStatus').textContent=state.lang==='ar'?'جارٍ الفتح…':'Opening…';
 const loading=pdfjsLib.getDocument({...(typeof source==='string'?{url:source}:{data:source}),
  password,cMapUrl:'/static/vendor/pdfjs/cmaps/',cMapPacked:true,standardFontDataUrl:'/static/vendor/pdfjs/standard_fonts/',
  wasmUrl:'/static/vendor/pdfjs/wasm/',iccUrl:'/static/vendor/pdfjs/iccs/',isEvalSupported:false,enableXfa:false});
 state.loading=loading;
 loading.onPassword=(updatePassword,reason)=>{const value=prompt(reason===2?'Incorrect password. Try again:':'PDF password:');if(value===null){loading.destroy();return;}state.openedPassword=value;updatePassword(value);};
 try{
 const pdf=await loading.promise;if(generation!==state.generation)return;
 state.pdf=pdf;const position=current?readPosition(current.id):null;
 const ready=new Promise(resolve=>{const listener=()=>{eventBus.off('pagesinit',listener);resolve();};eventBus.on('pagesinit',listener);});
 viewer.setDocument(pdf);linkService.setDocument(pdf);await ready;
 if(generation!==state.generation)return;
 setLayout(position?.mode||'continuous');viewer.pagesRotation=position?.rotation||0;
 viewer.currentScaleValue=position?.zoom||localStorage.getItem('insight-zoom')||'page-width';
 gotoPage(position?.page||1);$('pageNumber').max=pdf.numPages;$('pageTotal').textContent='/ '+pdf.numPages;
 if(position?.top && position.mode!=='single')state.restoreTimer=setTimeout(()=>{if(generation===state.generation&&!state.highlight){$('viewerContainer').scrollTop=position.top;$('viewerContainer').scrollLeft=position.left||0;}},250);
 $('indexStatus').textContent=current?statusLabel(current.index):state.lang==='ar'?'قراءة محلية':'Local reading';
 if(mobileReading?.showingBookmarks)mobileReading.documentChanged();else renderOutline();mobileReading?.screen();updateScope();renderLibrary();document.body.classList.remove('library-open');if(editor)await editor.documentLoaded(pdf);return true;
 }catch(error){if(generation===state.generation){state.pdf=null;mobileReading?.screen(false);mobileReading?.documentChanged();$('indexStatus').textContent='Could not open PDF';$('emptyState').hidden=false;throw Error('Could not open PDF: '+error.message);}}
}
async function openDocument(item,{editorReplacement=false}={}){const opened=await loadPdf(mobileBackend?await mobileBackend.documentUrl(item.id):`/api/documents/${item.id}/pdf`,item.title,item,'',editorReplacement);if(opened===false)return false;if(mobileBackend)await mobileBackend.resume(item.id,state.openedPassword||'');api(`/api/documents/${item.id}`,{method:'PATCH',body:{}}).catch(()=>{});}
let importQueue=Promise.resolve();
function queueImport(files){const batch=Array.from(files);importQueue=importQueue.then(()=>importFiles(batch));return importQueue.catch(error=>{toast(error.message);importQueue=Promise.resolve();});}
async function importFiles(files){
 state.importing=true;
 try { for(const file of files){
  if(!file.name.toLowerCase().endsWith('.pdf')&&!(androidMode&&file.type==='application/pdf')){toast('Choose a PDF file.');continue;}
  if(file.size>200*1024*1024){toast('This file exceeds the 200 MB import limit.');continue;}
  if(await loadPdf(new Uint8Array(await file.arrayBuffer()),file.name)===false)continue;
  if(!state.online){toast('Offline: reading works; indexing and AI require your LocalPDF server.');continue;}
  const generation=state.generation;const form=new FormData();form.append('file',file);if(mobileBackend&&state.openedPassword)form.append('password',state.openedPassword);
  let result;
  try{result=await api('/api/import',{method:'POST',body:form});}
  catch(error){if(/password/i.test(error.message)){const password=prompt('Enter this PDF’s password to create a readable local copy:');if(password===null)continue;form.append('password',password);result=await api('/api/import',{method:'POST',body:form});}else{toast(error.message);continue;}}
  if(generation!==state.generation)continue;
  state.current=result.document;mobileReading?.documentChanged();if(androidMode)$('documentTitle').textContent=result.document.title;$('indexStatus').textContent=statusLabel(result.document.index);
  await refreshDocuments();savePosition();updateScope();toast(result.duplicate?'Already in your library.':'Ready to read. Indexing in the background.');
 } } finally {state.importing=false;}
}
function statusLabel(status){if(!status)return '';const ar=state.lang==='ar';if(status.status==='ready')return status.warning?(ar?'مفهرس مع ملاحظات':'Indexed · check warnings'):(ar?'جاهز للبحث':'Ready to search');if(status.status==='indexing')return `${ar?'فهرسة':'Indexing'} ${status.done}/${status.total}`;if(status.status==='error')return ar?'تعذرت الفهرسة':'Indexing failed';return ar?'لم يُفهرس بعد':'Not indexed';}
async function refreshDocuments(){const data=await api('/api/documents');state.documents=data.documents;if(state.current){const item=state.documents.find(d=>d.id===state.current.id);if(item){state.current=item;$('indexStatus').textContent=statusLabel(item.index);}}renderLibrary();updateScope();}
function renderLibrary(){
 const target=$('documentList');target.replaceChildren();const q=$('libraryFilter').value.toLocaleLowerCase();
 const documents=state.documents.filter(d=>[d.title,d.filename,d.collection,...d.tags].join(' ').toLocaleLowerCase().includes(q));
 $('docCount').textContent=state.documents.length;
 for(const item of documents){const card=el('div','doc-card'+(item.id===state.current?.id?' active':''));
  const checkbox=el('input');checkbox.type='checkbox';checkbox.checked=state.selected.has(item.id);checkbox.setAttribute('aria-label','Select '+item.title);checkbox.onchange=()=>{checkbox.checked?state.selected.add(item.id):state.selected.delete(item.id);updateScope();};
  const button=el('button','doc-open');button.append(el('span','doc-title',item.title));button.dir='auto';
  button.append(el('span','doc-meta',`${item.page_count} ${state.lang==='ar'?'صفحة':'pages'} · ${new Date(item.imported_at*1000).toLocaleDateString()}`));
  button.append(el('span','doc-meta',statusLabel(item.index)));if(item.collection||item.tags.length)button.append(el('span','doc-tags',[item.collection,...item.tags].filter(Boolean).join(' · ')));
  button.onclick=handle(()=>openDocument(item));const more=el('button','doc-actions','⋯');more.setAttribute('aria-label','Edit '+item.title);more.onclick=()=>editMetadata(item);
  card.append(checkbox,button,more);if(item.index?.status==='error'||item.index?.status==='not_indexed'||item.index?.warning){const retry=el('button','text-button',state.lang==='ar'?'ملاحظات / إعادة الفهرسة':'Warnings / reindex');retry.style.gridColumn='2 / 4';retry.onclick=()=>{showInspector();$('answer').replaceChildren(el('p','warning',item.index.warning||'Indexing failed.'));const reindex=el('button','',state.lang==='ar'?'إعادة الفهرسة':'Reindex');reindex.onclick=handle(async()=>{await api(`/api/documents/${item.id}/index`,{method:'POST',body:{}});await refreshDocuments();});$('answer').append(reindex);};card.append(retry);}
  target.append(card);
 }
 if(!documents.length)target.append(el('p','small',state.documents.length?'No matching documents.':state.lang==='ar'?'تظهر هنا مستنداتك الأخيرة.':'Your recent documents will appear here.'));
 updateScope();
}
function updateScope(){const count=state.selected.size;$('selectionCount').textContent=state.lang==='ar'?`${count} مستندات محددة`:`${count} selected`;
 const ids=activeIds();const activeKey=JSON.stringify(ids);if(state.activeKey!==activeKey){state.activeKey=activeKey;state.askGeneration++;$('submitAsk').disabled=false;if(state.selection&&!ids.includes(state.selection.document_id))clearSelection();}$('scopeDescription').textContent=ids.map(id=>state.documents.find(d=>d.id===id)?.title||state.current?.title).filter(Boolean).join(' · ')||(state.lang==='ar'?'افتح أو حدد مستنداً.':'Open or select a document.');renderScopePicker();refreshSuggestions();}
function activeIds(){const scope=$('scope').value;return scope==='current'?(state.current?[state.current.id]:[]):scope==='selected'?[...state.selected]:state.documents.map(d=>d.id);}
function scopeBody(){return {scope:$('scope').value,current_id:state.current?.id,document_ids:[...state.selected]};}
function showInspector(){$('inspector').hidden=false;setPanel('chat');}
function editMetadata(item){$('metadataDialog').dataset.id=item.id;$('editTitle').value=item.title;$('editCollection').value=item.collection;$('editTags').value=item.tags.join(', ');$('metadataDialog').showModal();}
async function renderOutline(){const pdf=state.pdf;if(!pdf)return;const outline=await pdf.getOutline();if(state.pdf!==pdf||mobileReading?.showingBookmarks)return;const target=$('contentsList');target.replaceChildren();
 if(!outline?.length){target.append(el('p','small',state.lang==='ar'?'لا توجد محتويات مضمّنة.':'No embedded outline. Use Pages to navigate.'));return;}
 function add(items,depth=0){for(const item of items){const button=el('button','',item.title);button.dir='auto';button.style.paddingInlineStart=(8+depth*10)+'px';button.onclick=handle(()=>linkService.goToDestination(item.dest));target.append(button);if(item.items?.length)add(item.items,depth+1);}}add(outline);
}
let thumbnailObserver;
function renderThumbnails(){if(!state.pdf)return;thumbnailObserver?.disconnect();const pdf=state.pdf;const target=$('contentsList');target.replaceChildren();
 thumbnailObserver=new IntersectionObserver(entries=>{for(const entry of entries){if(!entry.isIntersecting)continue;thumbnailObserver.unobserve(entry.target);const button=entry.target;const n=Number(button.dataset.page);
  pdf.getPage(n).then(async page=>{if(pdf!==state.pdf)return;const viewport=page.getViewport({scale:128/page.getViewport({scale:1}).width});const canvas=el('canvas');canvas.width=viewport.width;canvas.height=viewport.height;button.prepend(canvas);await page.render({canvasContext:canvas.getContext('2d'),viewport}).promise;}).catch(e=>{button.append(el('span','small',e.message));});}},{root:$('contents'),rootMargin:'160px'});
 for(let n=1;n<=pdf.numPages;n++){const button=el('button','',String(n));button.dataset.page=n;button.style.minHeight='175px';button.setAttribute('aria-label','Go to page '+n);button.onclick=()=>gotoPage(n);target.append(button);thumbnailObserver.observe(button);}
}
// Android search follows PDF.js's findbarclose lifecycle; keep the query for reuse.
function closeFindBar(){if($('findBar').hidden)return;$('findBar').hidden=true;if(androidMode)eventBus.dispatch('findbarclose',{source:window});}
function find(previous=false,type=''){if(!state.pdf)return;eventBus.dispatch('find',{source:window,type,query:$('findInput').value,caseSensitive:false,entireWord:androidMode&&!!$('findWholeWord')?.checked,highlightAll:true,findPrevious:previous,matchDiacritics:false});}
function citationButton(source,savedId=null){const button=el('button','citation',`${source.document_name||source.filename} · ${state.lang==='ar'?'ص.':'p.'} ${source.page}`);button.dir='auto';button.dataset.sourceId=source.id;button.onclick=handle(()=>openSource(source.id,savedId));return button;}
async function openSource(id,savedId=null){const source=await api(savedId?`/api/studio/${encodeURIComponent(savedId)}/sources/${encodeURIComponent(id)}`:'/api/sources/'+encodeURIComponent(id));let item=state.documents.find(d=>d.id===source.document_id);if(!item){await refreshDocuments();item=state.documents.find(d=>d.id===source.document_id);}if(!item)throw Error('Document unavailable');
 if(state.current?.id!==item.id&&await openDocument(item)===false)return;
 state.highlight=source;gotoPage(source.page);highlightEvidence();
 if(innerWidth<=860)$('inspector').hidden=true;
}
function highlightEvidence(){const source=state.highlight;if(!source||state.current?.id!==source.document_id)return;
 for(const region of document.querySelectorAll('.evidence-region'))region.remove();
 const page=$('viewer').querySelector(`.page[data-page-number="${source.page}"]`);if(!page||!source.bbox)return;
 const [x0,y0,x1,y1]=source.bbox;const box=el('div','evidence-region');box.dataset.sourceId=source.id;
 // Coordinates are normalized in the PDF's intrinsic rotated view. Account for reader rotation.
 let x=x0,y=y0,w=x1-x0,h=y1-y0;const rotation=((viewer.pagesRotation%360)+360)%360;
 if(rotation===90)[x,y,w,h]=[1-y1,x0,h,w];else if(rotation===180)[x,y]=[1-x1,1-y1];else if(rotation===270)[x,y,w,h]=[y0,1-x1,h,w];
 Object.assign(box.style,{left:x*100+'%',top:y*100+'%',width:w*100+'%',height:h*100+'%'});page.append(box);
}
function renderSources(sources,target=$('answer'),savedId=null){const label=el('h3','',state.lang==='ar'?'المصادر والأدلة':'Sources / Evidence');target.append(label);
 for(const source of sources){const card=el('details','source-card');const summary=el('summary','',`${source.document_name} · ${state.lang==='ar'?'ص.':'p.'} ${source.page}`);summary.dir='auto';card.append(summary);if(source.extraction_method?.includes('ocr'))card.append(el('p','small',state.lang==='ar'?'نص مستخرج بالتعرّف البصري؛ تحقّق من الصفحة.':'OCR text — verify against the original page.'));
  const text=el('blockquote','',source.text);text.dir='auto';card.append(text,citationButton(source,savedId));
  const visual=el('button','text-button',state.lang==='ar'?'عرض صورة الصفحة':'Inspect page image');visual.onclick=()=>{if(card.querySelector('img'))return;const image=el('img');image.loading='lazy';image.alt=`${source.document_name}, page ${source.page}`;image.src=`/api/documents/${source.document_id}/pages/${source.page}/image?width=800`;card.append(image);};if(!androidMode)card.append(visual);
  if(new URLSearchParams(location.search).has('debug')){const debug=el('details');debug.append(el('summary','','Retrieval details'),el('pre','',JSON.stringify({chunk_id:source.id,revision:source.revision,retrieval_score:source.retrieval_score,reranking_score:source.reranking_score,method:source.retrieval_method},null,2)));card.append(debug);}
  target.append(card);
 }
}
async function ask(operationOverride){
 const generation=++state.askGeneration;const operation=operationOverride||$('operation').value;let question=$('question').value.trim();
 if(!question && operation!=='ask')question=operation;
 if(!question){$('question').focus();return;}if(!activeIds().length)throw Error('Open or select documents first.');
 $('submitAsk').disabled=true;$('answer').replaceChildren(el('p','answer-message',state.lang==='ar'?'البحث في الأدلة المحددة…':'Reading selected evidence…'));
 try{const data=await api('/api/ask',{method:'POST',body:{...scopeBody(),question,operation,strict:$('strict').checked,visual:$('visual').checked,selection:state.selection}});
 if(generation!==state.askGeneration)return;
 renderAnswer(data,$('answer'));
 }finally{if(generation===state.askGeneration)$('submitAsk').disabled=false;}
}
function clearSelection(){state.selection=null;$('selectionContext').hidden=true;$('selectionMenu').hidden=true;}
function captureSelection(){const selection=getSelection();if(!selection||selection.isCollapsed||!selection.rangeCount){$('selectionMenu').hidden=true;return;}
 const start=selection.anchorNode?.parentElement?.closest('.page');const end=selection.focusNode?.parentElement?.closest('.page');
 if(!start||start!==end||!$('viewer').contains(start)||!state.current){$('selectionMenu').hidden=true;return;}
 const text=selection.toString().trim();if(!text)return;const rect=selection.getRangeAt(0).getBoundingClientRect();
 const pageRect=start.getBoundingClientRect();
 let x0=(rect.left-pageRect.left)/pageRect.width,y0=(rect.top-pageRect.top)/pageRect.height,x1=(rect.right-pageRect.left)/pageRect.width,y1=(rect.bottom-pageRect.top)/pageRect.height;
 const rotation=((viewer.pagesRotation%360)+360)%360;
 if(rotation===90)[x0,y0,x1,y1]=[y0,1-x1,y1,1-x0];else if(rotation===180)[x0,y0,x1,y1]=[1-x1,1-y1,1-x0,1-y0];else if(rotation===270)[x0,y0,x1,y1]=[1-y1,x0,1-y0,x1];
 state.selection={document_id:state.current.id,page:Number(start.dataset.pageNumber),text:text.slice(0,6000),bbox:[x0,y0,x1,y1].map(v=>Math.max(0,Math.min(1,v)))};
 $('selectionMenu').hidden=false;$('selectionMenu').style.left=Math.max(8,Math.min(innerWidth-$('selectionMenu').offsetWidth-8,rect.left))+'px';$('selectionMenu').style.top=Math.max(70,Math.min(innerHeight-55,rect.top-43))+'px';
}
async function showTables(){if(!state.current)throw Error('Open an indexed document first.');const docId=state.current.id;const page=viewer.currentPageNumber;const data=await api(`/api/documents/${docId}/pages/${page}`);showInspector();const target=$('answer');target.replaceChildren();
 target.append(el('h3','',`${t('tables')} · ${page}`));if(!data.tables.length){target.append(el('p','answer-message','No structured table detected. Inspect the page image if the layout is ambiguous.'));return;}
 data.tables.forEach((table,n)=>{target.append(el('p','small',table.confidence));const wrap=el('div','table-wrap'),grid=el('table');
 for(const row of table.rows){const tr=el('tr');for(const cell of row){const td=el('td','',cell);td.dir='auto';tr.append(td);}grid.append(tr);}wrap.append(grid);target.append(wrap);
 const actions=el('div','ask-actions');const markdown=()=>{const rows=table.rows.map(row=>'| '+row.map(c=>c.replaceAll('|','\\|').replaceAll('\n',' ')).join(' | ')+' |');rows.splice(1,0,'| '+table.rows[0].map(()=>'---').join(' | ')+' |');return rows.join('\n');};
 const copy=el('button','','Copy table');copy.onclick=handle(()=>copyText(table.rows.map(r=>r.join('\t')).join('\n')));
 const md=el('button','','Markdown');md.onclick=handle(()=>copyText(markdown()));const csv=el('a','','CSV');csv.href=`/api/documents/${docId}/pages/${page}/tables/${n}/csv`;csv.className='text-button';
 const askTable=el('button','','Ask');askTable.onclick=()=>{$('scope').value='current';$('question').value=`Explain the table on page ${page}.`;state.selection={document_id:docId,page,text:table.rows[0].join(' | ')};$('selectionText').textContent=state.selection.text;$('selectionContext').hidden=false;$('question').focus();};
 actions.append(copy,md,csv,askTable);target.append(actions);
 });
}
async function copyText(text){if(navigator.clipboard?.writeText){await navigator.clipboard.writeText(text);toast('Copied.');return;}const input=el('textarea');input.value=text;document.body.append(input);input.select();const ok=document.execCommand('copy');input.remove();if(!ok)throw Error('Clipboard unavailable. Select and copy the displayed text.');toast('Copied.');}
async function compareDocuments(){if(state.selected.size<2)throw Error('Select at least two documents to compare.');showInspector();$('scope').value='selected';updateScope();$('answer').replaceChildren(el('p','answer-message','Comparing source passages…'));
 const data=await api('/api/compare',{method:'POST',body:{scope:'selected',document_ids:[...state.selected],question:''}});renderComparison(data,$('answer'),data.saved_id);
}
function renderComparison(data,target,savedId){
 target.replaceChildren(el('p','answer-message',data.message));
 if(!data.rows.length)target.append(el('p','warning','No aligned textual differences found. This does not establish that the documents are identical.'));
 for(const row of data.rows){const block=el('div','comparison-row');block.append(el('h3','',row.topic));
 for(const side of ['a','b']){const passage=el('p','',row[side].text);passage.dir='auto';block.append(passage,citationButton(row[side],savedId));}
 block.append(el('p','small',row.change));target.append(block);}
 if(data.saved_id)target.prepend(savedButton(data.saved_id));
}

function translate(){document.documentElement.lang=state.lang;document.documentElement.dir=state.lang==='ar'?'rtl':'ltr';for(const node of document.querySelectorAll('[data-i18n]')){const value=t(node.dataset.i18n);if(node.dataset.i18n==='emptyTitle'||node.dataset.i18n==='emptyBody')node.innerHTML=value;else if(node.id!=='documentTitle'||!state.current)node.textContent=value;}for(const node of document.querySelectorAll('[data-placeholder]'))node.placeholder=t(node.dataset.placeholder);$('language').textContent=state.lang==='ar'?'English':'العربية';renderTemplateOptions();for(const b of $('selectionMenu').querySelectorAll('button'))b.textContent=selectionLabels[b.dataset.action][state.lang];renderLibrary();editor?.translate();mobileToolbar?.translate();mobileReading?.translate();}
$('language').onclick=()=>{state.lang=state.lang==='en'?'ar':'en';localStorage.setItem('insight-language',state.lang);translate();$('strict').dispatchEvent(new Event('change'));if(state.current)$('indexStatus').textContent=statusLabel(state.current.index);};
$('libraryToggle').onclick=()=>document.body.classList.toggle('library-open');$('askToggle').onclick=()=>{$('inspector').hidden=!$('inspector').hidden;setPanel('chat');};$('studioToggle').onclick=()=>{showInspector();setPanel('studio');};$('closeInspector').onclick=()=>$('inspector').hidden=true;
$('fileInput').onchange=handle(e=>queueImport(e.target.files));$('emptyInput').onchange=handle(e=>queueImport(e.target.files));
$('previousPage').onclick=()=>gotoPage(viewer.currentPageNumber-1);$('nextPage').onclick=()=>gotoPage(viewer.currentPageNumber+1);$('pageNumber').onchange=e=>gotoPage(e.target.value);
$('zoomIn').onclick=()=>zoomBy(1.2);$('zoomOut').onclick=()=>zoomBy(1/1.2);$('zoom').onchange=e=>{if(e.target.value!=='custom')viewer.currentScaleValue=e.target.value;savePosition();};$('viewMode').onchange=e=>{setLayout(e.target.value);savePosition();};$('rotate').onclick=()=>{if(state.pdf)viewer.pagesRotation=(viewer.pagesRotation+90)%360;};
$('outlineToggle').onclick=()=>{$('contents').hidden=!$('contents').hidden;};$('showOutline').onclick=handle(renderOutline);$('showThumbs').onclick=renderThumbnails;
$('findToggle').onclick=()=>{if(!$('findBar').hidden)closeFindBar();else{$('findBar').hidden=false;$('findInput').focus();}};$('findInput').oninput=()=>{state.searchSources=[];find();};
$('findInput').onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();find(e.shiftKey,'again');}};
$('findPrevious').onclick=()=>{if(state.searchSources.length){state.searchIndex=(state.searchIndex+state.searchSources.length-1)%state.searchSources.length;handle(()=>openSource(state.searchSources[state.searchIndex].id))();}else find(true,'again');};
$('findNext').onclick=()=>{if(state.searchSources.length){state.searchIndex=(state.searchIndex+1)%state.searchSources.length;handle(()=>openSource(state.searchSources[state.searchIndex].id))();}else find(false,'again');};
$('indexedSearch').onclick=handle(async()=>{if(!state.current)throw Error('Open a document first.');const data=await api('/api/search',{method:'POST',body:{scope:'current',current_id:state.current.id,question:$('findInput').value}});state.searchSources=data.sources;state.searchIndex=0;showInspector();$('answer').replaceChildren(el('p','answer-message','Indexed passage matches (includes successful OCR).'));renderSources(data.sources);if(data.sources.length)await openSource(data.sources[0].id);else toast('No indexed matches. Check indexing status.');});
$('libraryFilter').oninput=renderLibrary;$('librarySearch').onclick=handle(async()=>{const query=$('libraryFilter').value.trim();if(!query)throw Error('Enter a search term in the library filter.');const data=await api('/api/search',{method:'POST',body:{scope:'library',question:query}});showInspector();$('answer').replaceChildren(el('p','answer-message','Library-wide passage search'));renderSources(data.sources);});
$('scope').onchange=()=>{state.askGeneration++;$('submitAsk').disabled=false;clearSelection();updateScope();};$('strict').onchange=()=>{$('strictDescription').textContent=$('strict').checked?t('strictDetail'):state.lang==='ar'?'يستخدم الوضع المساعد مقتطفات المصدر عندما يتعذر التحقق من الصياغة المولدة.':'Assisted matching uses source excerpts when generated wording cannot be verified.';$('visual').disabled=$('strict').checked;};$('strict').dispatchEvent(new Event('change'));
$('submitAsk').onclick=handle(()=>ask());$('question').onkeydown=e=>{if(e.key==='Enter'&&(e.ctrlKey||e.metaKey)){e.preventDefault();handle(()=>ask())();}};
$('compare').onclick=handle(compareDocuments);$('tables').onclick=handle(showTables);$('clearSelection').onclick=clearSelection;
const selectionLabels={Explain:{en:'Explain',ar:'اشرح'},Summarize:{en:'Summarize',ar:'لخّص'},Define:{en:'Define',ar:'عرّف'},Translate:{en:'Translate',ar:'ترجم'},ask:{en:'Ask',ar:'اسأل'},note:{en:'Save note',ar:'حفظ ملاحظة'}};
$('selectionMenu').onpointerdown=e=>e.preventDefault();$('selectionMenu').onclick=e=>{const action=e.target.dataset.action;if(!action||!state.selection)return;$('selectionMenu').hidden=true;
 if(action==='note'){state.pendingNote=structuredClone(state.selection);$('noteSelection').textContent=state.pendingNote.text;$('noteComment').value='';$('noteDialog').showModal();return;}
 showInspector();$('scope').value='current';updateScope();$('selectionText').textContent=state.selection.text;$('selectionContext').hidden=false;
 const ar=state.lang==='ar';$('question').value=action==='Translate'?(ar?'ترجم النص المحدد إلى العربية.':'Translate the selected passage to English.'):action==='ask'?'':ar?`${selectionLabels[action].ar} النص المحدد.`:`${action} this selected passage.`;
 if(action!=='ask'){if($('strict').checked)toast(ar?'يعرض الوضع الصارم اقتباسات؛ يُحجب التفسير أو الترجمة إذا تعذر التحقق منهما.':'Strict mode returns excerpts. Unverified interpretations and translations are withheld.');handle(()=>ask(action))();}else $('question').focus();};
$('noteForm').onsubmit=handle(async e=>{e.preventDefault();const selection=state.pendingNote;const item=await api('/api/notes',{method:'POST',body:{scope:'current',current_id:selection.document_id,selection,comment:$('noteComment').value}});$('noteDialog').close();showInspector();setPanel('studio');await openSaved(item.id);});
$('cancelNote').onclick=()=>$('noteDialog').close();
$('viewerContainer').addEventListener('pointerup',()=>setTimeout(captureSelection,50));document.addEventListener('selectionchange',()=>{clearTimeout(captureSelection.timer);if(getSelection()?.isCollapsed)$('selectionMenu').hidden=true;else captureSelection.timer=setTimeout(captureSelection,120);});
$('metadataForm').onsubmit=handle(async e=>{e.preventDefault();await api(`/api/documents/${$('metadataDialog').dataset.id}`,{method:'PATCH',body:{title:$('editTitle').value,collection:$('editCollection').value,tags:$('editTags').value.split(/[,،]/).map(s=>s.trim()).filter(Boolean)}});$('metadataDialog').close();await refreshDocuments();if(state.current)$('documentTitle').textContent=state.current.title;});$('cancelMetadata').onclick=()=>$('metadataDialog').close();
$('loginForm').onsubmit=handle(async e=>{e.preventDefault();try{await api('/api/login',{method:'POST',body:{token:$('accessKey').value}});$('accessKey').value='';$('loginDialog').close();await start();}catch(error){$('loginError').textContent=error.message;}});
document.addEventListener('keydown',e=>{const typing=/INPUT|TEXTAREA|SELECT/.test(e.target.tagName);if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='o'){e.preventDefault();$('fileInput').click();}else if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='f'){e.preventDefault();$('findBar').hidden=false;$('findInput').focus();}else if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();showInspector();$('question').focus();}else if(!typing&&['ArrowRight','PageDown'].includes(e.key)){e.preventDefault();gotoPage(viewer.currentPageNumber+1);}else if(!typing&&['ArrowLeft','PageUp'].includes(e.key)){e.preventDefault();gotoPage(viewer.currentPageNumber-1);}else if(!typing&&e.key==='Home'){gotoPage(1);}else if(!typing&&e.key==='End'){gotoPage(state.pdf?.numPages||1);}else if(e.key==='Escape'){if(androidMode&&!$('findBar').hidden)e.preventDefault();$('selectionMenu').hidden=true;closeFindBar();document.body.classList.remove('library-open');}});
$('viewerContainer').addEventListener('wheel',e=>{if(e.ctrlKey&&state.pdf){e.preventDefault();zoomBy(e.deltaY<0?1.06:1/1.06);}},{passive:false});
let pinch=null;
$('viewerContainer').addEventListener('touchstart',e=>{if(e.touches.length===2){pinch={distance:Math.hypot(e.touches[0].clientX-e.touches[1].clientX,e.touches[0].clientY-e.touches[1].clientY),scale:viewer.currentScale};}},{passive:true});
$('viewerContainer').addEventListener('touchmove',e=>{if(pinch&&e.touches.length===2&&state.pdf){e.preventDefault();const d=Math.hypot(e.touches[0].clientX-e.touches[1].clientX,e.touches[0].clientY-e.touches[1].clientY);viewer.currentScale=Math.min(5,Math.max(.25,pinch.scale*d/pinch.distance));}},{passive:false});$('viewerContainer').addEventListener('touchend',()=>{pinch=null;savePosition();});
let dragDepth=0;document.addEventListener('dragenter',e=>{if([...e.dataTransfer.types].includes('Files')){e.preventDefault();dragDepth++;document.body.classList.add('dragging');}});document.addEventListener('dragleave',()=>{if(--dragDepth<=0)document.body.classList.remove('dragging');});document.addEventListener('dragover',e=>e.preventDefault());document.addEventListener('drop',handle(async e=>{e.preventDefault();dragDepth=0;document.body.classList.remove('dragging');await queueImport(e.dataTransfer.files);}));
window.addEventListener('beforeunload',savePosition);
let installPrompt;window.addEventListener('beforeinstallprompt',e=>{e.preventDefault();installPrompt=e;$('install').hidden=false;});$('install').onclick=async()=>{if(installPrompt){await installPrompt.prompt();installPrompt=null;$('install').hidden=true;}};
if(!androidMode && 'serviceWorker' in navigator && window.isSecureContext)navigator.serviceWorker.register('/sw.js').catch(()=>toast('Offline app shell could not be installed. Browser reading is still available.'));

function setPanel(panel){if(panel==='studio'){$('selectionMenu').hidden=true;getSelection()?.removeAllRanges();}$('chatPanel').hidden=panel!=='chat';$('studioPanel').hidden=panel!=='studio';$('chatTab').setAttribute('aria-pressed',panel==='chat');$('studioTab').setAttribute('aria-pressed',panel==='studio');if(panel==='studio')handle(refreshStudio)();}
$('chatTab').onclick=()=>setPanel('chat');$('studioTab').onclick=()=>setPanel('studio');
function renderScopePicker(){const target=$('scopeDocuments');target.replaceChildren();const ids=activeIds();
 for(const doc of state.documents){const row=el('label','check-row');const check=el('input');check.type='checkbox';check.checked=ids.includes(doc.id);check.setAttribute('aria-label',doc.title);
 check.onchange=()=>{state.selected=new Set(activeIds());check.checked?state.selected.add(doc.id):state.selected.delete(doc.id);$('scope').value='selected';state.askGeneration++;$('submitAsk').disabled=false;clearSelection();renderLibrary();};
 const name=el('bdi','',doc.title);row.append(check,name);target.append(row);}}
async function refreshSuggestions(){const ids=activeIds();const key=JSON.stringify(ids.map(id=>[id,state.documents.find(d=>d.id===id)?.index]));
 if(key===state.suggestionKey)return;state.suggestionKey=key;const target=$('suggestions');target.replaceChildren();if(!ids.length||!state.online)return;
 try{const data=await api('/api/suggestions',{method:'POST',body:scopeBody()});if(key!==state.suggestionKey)return;
 for(const item of data.questions){const b=el('button','suggestion',item.question);b.dir='auto';b.onclick=handle(async()=>{clearSelection();$('operation').value='ask';$('question').value=item.question;await ask('ask');});target.append(b);}
 if(data.warning)target.append(el('p','warning',data.warning));
 if(data.partial)target.append(el('p','small',state.lang==='ar'?'ستتحدث الاقتراحات بعد اكتمال الفهرسة.':'Suggestions update as indexing completes.'));
 }catch(error){if(key===state.suggestionKey){target.append(el('p','small',error.message));state.suggestionKey=null;}}}
function availableTemplates(){const formats=state.config.templates||[];return [...formats,...(state.config.summary_modes||[]).filter(id=>!formats.some(f=>f.id===id)).map(id=>({id,en:id,ar:({'Detailed summary':'ملخص مفصل','Section-by-section summary':'ملخص الأقسام','People / companies / entities':'الأشخاص والشركات والجهات','Action items':'الإجراءات المذكورة'})[id]||id}))];}
function renderTemplateOptions(){if(androidMode){$('studioFilter').replaceChildren();const option=el('option','',t('allOutputs'));option.value='all';$('studioFilter').append(option);return;}const selected=$('studioType').value;const filter=$('studioFilter').value;const target=$('studioType');target.replaceChildren();
 for(const format of availableTemplates()){const option=el('option','',format[state.lang]);option.value=format.id;target.append(option);}
 const comparison=el('option','',state.lang==='ar'?'مقارنة':'Comparison');comparison.value='Comparison';target.append(comparison);
 if([...target.options].some(o=>o.value===selected))target.value=selected;
 $('studioFilter').replaceChildren();for(const [id,label] of [['all',t('allOutputs')],['Note',t('notes')],...availableTemplates().map(f=>[f.id,f[state.lang]]),['Comparison',comparison.textContent]]){const option=el('option','',label);option.value=id;$('studioFilter').append(option);}$('studioFilter').value=filter||'all';}
function savedButton(id){const button=el('button','text-button',state.lang==='ar'?'محفوظ في الاستوديو ↗':'Saved in Studio ↗');button.onclick=handle(async()=>{setPanel('studio');await openSaved(id);});return button;}
function renderAnswer(data,target,savedId=data.saved_id){target.replaceChildren(el('p','answer-message',data.message));
 if(data.saved_id)target.prepend(savedButton(data.saved_id));
 const origin=el('p','small',(state.lang==='ar'?'مصادر هذا الناتج: ':'Sources for this output: ')+[...new Set(data.sources.map(s=>s.document_name))].join(' · '));origin.dir='auto';target.append(origin);
 for(const warning of data.warnings||[])target.append(el('p','warning',warning));
 if(data.selection){const selected=el('blockquote','',data.selection.text);selected.dir='auto';target.append(selected);}
 const sources=new Map(data.sources.map(s=>[s.id,s]));
 if(data.cards){if(!data.cards.length)target.append(el('p','warning',state.lang==='ar'?'لا توجد أدلة كافية لإنشاء تمرين واضح.':'Insufficient evidence for an unambiguous study exercise.'));
 for(const card of data.cards){const block=el('div','study-card');const front=el('p','',card.front);front.dir='auto';const reveal=el('details');reveal.append(el('summary','',state.lang==='ar'?'إظهار الإجابة والدليل':'Reveal answer & evidence'));const back=el('strong','',card.back);back.dir='auto';const explanation=el('p','',card.explanation);explanation.dir='auto';reveal.append(back,explanation);for(const id of card.source_ids)if(sources.has(id))reveal.append(citationButton(sources.get(id),savedId));block.append(front,reveal);target.append(block);}}
 else for(const claim of data.claims){const block=el('div','claim');if(claim.front){const front=el('h3','',claim.front);front.dir='auto';block.append(front);}const text=el('p','',claim.text);text.dir='auto';block.append(text);for(const id of claim.source_ids)if(sources.has(id))block.append(citationButton(sources.get(id),savedId));target.append(block);}
 renderSources(data.sources,target,savedId);
}
async function refreshStudio(){const data=await api('/api/studio');const target=$('studioList');target.replaceChildren();const filter=$('studioFilter').value;
 for(const item of data.outputs.filter(o=>filter==='all'||o.kind===filter)){const button=el('button','saved-output');button.dir='auto';button.append(el('span','',item.title),el('small','',new Date(item.created_at*1000).toLocaleString()));button.onclick=handle(()=>openSaved(item.id));target.append(button);}
 if(!target.children.length)target.append(el('p','small',state.lang==='ar'?'لا توجد نواتج محفوظة بعد.':'No saved outputs yet.'));}
$('studioFilter').onchange=handle(refreshStudio);
let savedGeneration=0;
async function openSaved(id){const generation=++savedGeneration;const item=await api('/api/studio/'+id);if(generation!==savedGeneration)return;const target=$('studioOutput');target.replaceChildren();
 const title=el('h3','',item.title);title.dir='auto';const metadata=el('p','small',new Date(item.created_at*1000).toLocaleString()+' · '+item.scope.documents.map(d=>d.title).join(' · '));metadata.dir='auto';target.append(title,metadata);const content=el('div');target.append(content);
 if(item.kind==='Note'){if(!androidMode&&!item.content.selection.verified)content.append(el('p','warning',state.lang==='ar'?'ملاحظة شخصية: لم يُطابَق النص مع الفهرس. تحقّق من الصفحة الأصلية. لا يُستخدم هذا النص كدليل للذكاء الاصطناعي.':'Personal note: text could not be matched to the index. Verify the original page. This text is not used as AI evidence.'));const quote=el('blockquote','',item.content.selection.text);quote.dir='auto';const comment=el('p','',item.content.comment);comment.dir='auto';content.append(quote,comment);for(const source of item.content.sources)content.append(citationButton(source,id));}
 else if(item.kind==='Comparison')renderComparison(item.content,content,id);else renderAnswer(item.content,content,id);
 target.dataset.outputId=id;
}
$('createOutput').onclick=handle(async()=>{const operation=$('studioType').value;if(!activeIds().length)throw Error('Open or select documents first.');const body={...scopeBody(),operation,question:operation,strict:$('strict').checked};$('createOutput').disabled=true;$('studioOutput').replaceChildren(el('p','small',state.lang==='ar'?'جارٍ قراءة المصادر…':'Reading sources…'));
 try{const data=await api(operation==='Comparison'?'/api/compare':'/api/ask',{method:'POST',body});if(data.saved_id){await refreshStudio();await openSaved(data.saved_id);}else renderAnswer(data,$('studioOutput'));}finally{$('createOutput').disabled=false;}});
async function start(){try{state.config=await api('/api/config');renderTemplateOptions();await refreshDocuments();state.online=true;}catch(error){if(!/Access key|مفتاح/.test(error.message)){state.online=false;toast('Server unavailable. You can still open local PDFs; indexing and AI are offline.');}}}
if(androidMode){
 document.body.classList.add('android-reader');
 mobileToolbar=(await import('./mobile_toolbar.js')).createMobileToolbar({language:()=>state.lang});
 mobileReading=(await import('./mobile_reading.js')).createMobileReading({state,viewer,eventBus,gotoPage,find,toast,language:()=>state.lang});
 aptPanel=(await import('./apt_panel.mjs')).createAptPanel({backend:mobileBackend,state,openSource,closeOptions:()=>mobileToolbar.closeOptions()});
 $('pageNumber').setAttribute('enterkeyhint','go');
 $('pageNumber').onkeydown=e=>{if(e.key==='Enter'&&!e.isComposing&&state.pdf){e.preventDefault();gotoPage(e.currentTarget.value);e.currentTarget.blur();}};
 for(const id of ['askToggle','install','compare','tables','chatTab','suggestions','question','operation','submitAsk','studioType','createOutput','studioFilter','strictDescription','selectionCount'])$(id).hidden=true;
 $('strict').closest('label').hidden=true;$('visual').closest('label').hidden=true;
 $('studioType').parentElement.hidden=true;$('operation').parentElement.hidden=true;
 $('question').previousElementSibling.hidden=true;
 for(const button of $('selectionMenu').querySelectorAll('[data-action]'))if(button.dataset.action!=='note')button.hidden=true;
 document.querySelector('label[for="studioFilter"]').hidden=true;
 document.querySelector('#inspector .panel-heading h2').dataset.i18n='studio';
 $('inspector').setAttribute('aria-label','Notes and source passages');
 window.addEventListener('pagehide',savePosition);
 document.addEventListener('visibilitychange',()=>{if(document.hidden)savePosition();});
 window.localPDFHasUnsavedEdits=()=>editor?.dirty||false;
 window.localPDFBack=()=>{
  if(editor?.busy){toast(state.lang==='ar'?'أكمل العملية الحالية أولاً.':'Finish the current PDF operation first.');return true;}
  const dialog=document.querySelector('dialog[open]');if(dialog){if(dialog.id==='textDialog')$('cancelEditText').click();else dialog.close();return true;}
  if(mobileToolbar.closeOptions(true))return true;
  if(!$('editBar').hidden){editor.chooseTool('read').catch(e=>toast(e.message));$('editBar').hidden=true;return true;}
  for(const id of ['selectionMenu','inspector','contents','findBar'])if(!$(id).hidden){if(id==='findBar')closeFindBar();else $(id).hidden=true;return true;}
  if(document.body.classList.contains('library-open')){document.body.classList.remove('library-open');return true;}
  savePosition();return false;
 };
}
translate();await start();setInterval(()=>{if(state.online&&state.documents.some(d=>d.index?.status==='indexing'))refreshDocuments().catch(()=>{});},1800);
// Small deterministic seam for browser regression checks, enabled only explicitly.
if(new URLSearchParams(location.search).has('test'))window.__reader={state,viewer,openSource,loadPdf,find,refreshDocuments,editor,mobileReading};

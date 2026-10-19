// Actual PDF.js edit/export workflow, with independent inspection by PyMuPDF.
// NODE_PATH=<Playwright modules> CHROMIUM_EXECUTABLE=<Chromium> node tests/browser/android_editor.cjs
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const {chromium} = require('playwright');
const root = path.resolve(__dirname, '../..'), staticRoot = path.join(root, 'src/localpdf_insight/static');
const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'localpdf-editor-'));
const artifacts = process.env.LOCALPDF_TEST_ARTIFACTS || path.join(root, 'validation-artifacts', 'editor');
const python = process.env.LOCALPDF_TEST_PYTHON || 'python3';
const helper = path.join(__dirname, 'android_editor_fixtures.py');
const base = 'https://appassets.androidplatform.net', appUrl = base + '/?platform=android&test=1';
const generated = spawnSync(python, [helper, 'fixtures', temp], {encoding: 'utf8'});
if (generated.status !== 0) throw Error(generated.stderr);
fs.mkdirSync(artifacts, {recursive: true});
const results = [], network = [], errors = [];
let browser, context, page, originalId, editedId, noteId, originalRevision;
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
async function check(name, run) {
  const start = performance.now();
  try { await run(); results.push({name, status:'passed', seconds:+((performance.now()-start)/1000).toFixed(3)}); console.log('PASS', name); }
  catch(error) { results.push({name, status:'failed', error:error.message}); throw error; }
}
async function ready(filename) {
  await page.waitForFunction(name => window.__reader?.state.current?.filename === name && !window.__reader.state.importing && !!window.__reader.state.pdf,
    filename, {timeout:60000});
  await page.locator('.pdfViewer canvas').first().waitFor();
}
async function viewOption(id, value) {
  if (!await page.locator('#readerOptions').isVisible()) await page.locator('#readerOptionsToggle').click();
  await page.locator('#' + id).selectOption(value);
  await page.locator('#readerOptionsToggle').click();
}
async function indexed() {
  await page.waitForFunction(() => window.__reader.state.documents.every(d => d.index.status === 'ready'), null, {timeout:60000});
}
async function goto(number) {
  await page.locator('#pageNumber').fill(String(number)); await page.locator('#pageNumber').dispatchEvent('change');
  await page.waitForFunction(n => window.__reader.viewer.currentPageNumber === n, number);
  await page.locator(`.page[data-page-number="${number}"] .canvasWrapper canvas`).waitFor();
}
async function backend(url, body, method='POST') {
  return page.evaluate(async ({url, body, method}) => {
    if(!window.editorBackend) {
      const pdfjs = await import('/static/vendor/pdfjs/build/pdf.mjs');
      window.editorBackend = await (await import('/static/mobile_backend.js')).createMobileBackend(pdfjs);
    }
    return window.editorBackend.request(url,{method,body});
  }, {url,body,method});
}
async function openLibrary(id) {
  if(!await page.evaluate(() => document.body.classList.contains('library-open'))) await page.locator('#libraryToggle').click();
  const title = await page.evaluate(id => window.__reader.state.documents.find(d=>d.id===id).title,id);
  await page.locator('.doc-card').filter({has:page.getByRole('checkbox',{name:'Select '+title,exact:true})}).locator('.doc-open').click();
  await page.waitForFunction(id => window.__reader.state.current?.id===id&&!!window.__reader.state.pdf&&window.__reader.viewer.pagesCount===window.__reader.state.pdf.numPages&&document.getElementById('pageTotal').textContent==='/ '+window.__reader.state.pdf.numPages,id);
}
async function tool(name) {
  if(!await page.locator('#editBar').isVisible()) await page.locator('#editToggle').click();
  await page.locator('#editTool').selectOption(name); await delay(150);
}
async function ink(number, touch=false) {
  await goto(number); await tool('ink');
  const layer = page.locator(`.page[data-page-number="${number}"] .annotationEditorLayer`);
  await layer.waitFor();
  const before = await page.locator('.inkEditor').count();
  const box = await layer.boundingBox();
  assert(box && box.width>100 && box.height>100);
  const points = [[.20,.40],[.24,.31],[.30,.43],[.34,.28],[.36,.42],[.40,.36],[.44,.42],[.50,.33],[.54,.40],[.61,.37]]
    .map(([x,y])=>({x:box.x+box.width*x,y:box.y+box.height*y}));
  if(touch) {
    const cdp=await context.newCDPSession(page);
    await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[points[0]]});
    for(const point of points.slice(1)) await cdp.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[point]});
    await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]}); await cdp.detach();
  } else {
    await page.mouse.move(points[0].x,points[0].y); await page.mouse.down();
    for(const point of points.slice(1)) await page.mouse.move(point.x,point.y,{steps:3}); await page.mouse.up();
  }
  await tool('read');
  await page.waitForFunction(before => document.querySelectorAll('.inkEditor').length>before,before);
}
async function nativeExport(status='saved') {
  const previous=await page.evaluate(()=>({id:window.__reader.state.current.id,count:window.__reader.state.documents.length}));
  await page.evaluate(status => {window.editorExportNextStatus=status;window.editorExportResult=null;},status);
  await page.locator('#saveEdited').click();
  await page.waitForFunction(() => !!window.editorExportResult, null, {timeout:60000});
  if(status==='saved')await page.waitForFunction(id=>window.__reader.state.current?.id!==id&&!!window.__reader.state.pdf&&!document.getElementById('saveEdited').disabled,previous.id,{timeout:60000});
  else {await delay(150);assert.equal(await page.evaluate(()=>window.__reader.state.documents.length),previous.count);assert.equal(await page.evaluate(()=>window.__reader.state.current.id),previous.id);}
  const captured=await page.evaluate(()=>window.editorExportResult);
  const bytes=Buffer.from(captured.data,'base64');
  assert.equal(bytes.length,captured.size,'Native export chunks must exactly match advertised byte count');
  assert(bytes.subarray(0,1024).includes(Buffer.from('%PDF-')));
  return {captured,bytes};
}
function inspect(originalFilename, bytes, label) {
  const directory=path.join(artifacts,label);fs.mkdirSync(directory,{recursive:true});
  const exported=path.join(directory,'exported.pdf');fs.writeFileSync(exported,bytes);
  const result=spawnSync(python,[helper,'inspect',path.join(temp,originalFilename),exported,directory],{encoding:'utf8'});
  assert.equal(result.status,0,result.stderr);
  const report=JSON.parse(result.stdout);fs.writeFileSync(path.join(directory,'inspection.json'),JSON.stringify(report,null,2));return report;
}
async function installExportMock() {
  await context.addInitScript(() => {
    let current=null;
    const reply=body=>setTimeout(()=>window.LocalPDFExport.onmessage?.({data:JSON.stringify(body)}),2);
    window.LocalPDFExport={onmessage:null,postMessage(raw) {
      const message=JSON.parse(raw),{id,action}=message;
      if(action==='begin') {current={id,size:message.size,filename:message.filename,purpose:message.purpose||'save',chunks:[],next:0};reply({id,status:'ready'});}
      else if(action==='chunk') {
        if(!current||current.id!==id||message.index!==current.next) throw Error('Invalid native chunk sequence');
        current.chunks.push(message.data);current.next++;reply({id,status:'chunk',index:message.index});
      } else if(action==='finish') {
        const combined=current.chunks.map(encoded=>atob(encoded)).join('');
        // Preserve bytes including 0x80..0xff; no UTF-8 text conversion.
        const status=window.editorExportNextStatus||(current.purpose==='save'?'saved':'opened');
        window.editorExportResult={...current,data:btoa(combined),status};
        reply({id,status:'choosing'});
        if(window.editorExportNextStatus==='pending')window.editorCompletePendingExport=status=>reply({id,status});
        else setTimeout(()=>reply({id,status}),15);
        current=null;
      } else if(action==='cancel') {current=null;reply({id,status:'cancelled'});}
      else throw Error('Unexpected native export action');
    }};
  });
}
(async()=>{
 try {
  browser=await chromium.launch({headless:true,...(process.env.CHROMIUM_EXECUTABLE?{executablePath:process.env.CHROMIUM_EXECUTABLE,args:['--no-sandbox','--disable-gpu','--disable-dev-shm-usage']}:{})});
  context=await browser.newContext({viewport:{width:412,height:915},deviceScaleFactor:2.625,hasTouch:true,isMobile:true,serviceWorkers:'block'});
  await context.setOffline(true);await installExportMock();
  const mime={'.html':'text/html','.js':'text/javascript','.mjs':'text/javascript','.css':'text/css','.svg':'image/svg+xml','.png':'image/png','.wasm':'application/wasm'};
  await context.route('**/*',async route=>{
    const url=new URL(route.request().url());if(url.protocol==='blob:'||url.protocol==='data:')return route.continue();
    if(url.origin!==base||url.pathname.startsWith('/api/')){network.push(url.href);return route.abort();}
    const file=path.resolve(staticRoot,url.pathname==='/'?'index.html':url.pathname.replace(/^\/static\//,''));
    if(!file.startsWith(staticRoot+path.sep)||!fs.existsSync(file)||!fs.statSync(file).isFile()){network.push(url.href);return route.abort();}
    return route.fulfill({status:200,contentType:mime[path.extname(file)]||'application/octet-stream',body:fs.readFileSync(file)});
  });
  page=await context.newPage();page.on('pageerror',e=>{errors.push(e.message);console.error('BROWSER_ERROR',e.stack);});await page.goto(appUrl);
  await page.waitForFunction(()=>!!window.__reader);
  await check('Original PDF and source-linked note are retained before editing',async()=>{
    assert(await page.locator('#sharePdf').isDisabled());assert(await page.locator('#printPdf').isDisabled());
    await page.locator('#fileInput').setInputFiles(path.join(temp,'editable.pdf'));await ready('editable.pdf');await indexed();
    ({id:originalId,revision:originalRevision}=await page.evaluate(()=>window.__reader.state.current));
    const note=await backend('/api/notes',{scope:'current',current_id:originalId,selection:{document_id:originalId,page:2,text:'Original source passage remains linked to this document.',bbox:[.08,.1,.9,.16]},comment:'Pre-signature source note'});
    noteId=note.id;assert.equal(note.content.selection.document_id,originalId);assert.equal(note.content.selection.page,2);
  });
  await check('Icon editing controls expose current tool and pen colour through language changes and text cancellation',async()=>{
    for(const lang of ['en','ar']){
      if(await page.locator('html').getAttribute('lang')!==lang)await page.locator('#language').click();
      for(const [mode,icon] of [['ink','editorInk'],['highlight','editorHighlight'],['read','handTool']]){
        await tool(mode);
        await page.waitForFunction(icon=>document.querySelector('#editTool').parentElement.querySelector('.toolbar-glyph').style.getPropertyValue('--toolbar-image').includes(icon),icon);
      }
      await page.locator('#editorColour').selectOption('#163c82');
      assert.equal(await page.locator('#editorColour').evaluate(node=>getComputedStyle(node.parentElement.querySelector('.toolbar-glyph')).color),'rgb(22, 60, 130)');
      await page.locator('#editorColour').selectOption('#111111');
      await tool('text');await page.locator('#cancelEditText').click();
      await page.waitForFunction(()=>document.querySelector('#editTool').value==='read'&&document.querySelector('#editTool').parentElement.querySelector('.toolbar-glyph').style.getPropertyValue('--toolbar-image').includes('handTool'));
      for(const id of ['editToggle','saveEdited','sharePdf','printPdf','editorUndo','editorRedo','editorDelete']){
        const button=page.locator('#'+id);assert.equal((await button.textContent()).trim(),'');assert(await button.getAttribute('aria-label'));
      }
      assert.equal(await page.locator('#sharePdf').getAttribute('aria-label'),lang==='ar'?'مشاركة PDF':'Share PDF');
      assert.equal(await page.locator('#printPdf').getAttribute('aria-label'),lang==='ar'?'طباعة PDF':'Print PDF');
      assert.equal(await page.evaluate(()=>window.__reader.editor.dirty),false);
      await page.screenshot({path:path.join(artifacts,'compact-editor-'+lang+'.png')});
      await page.locator('#editToggle').click();
    }
    await page.locator('#language').click();
  });
  await check('Share unedited PDF transfers exact original bytes without a new document or save claim',async()=>{
    const before=await page.evaluate(()=>({id:window.__reader.state.current.id,revision:window.__reader.state.current.revision,count:window.__reader.state.documents.length}));
    await page.evaluate(()=>{window.editorExportNextStatus=null;window.editorExportResult=null;});
    await page.locator('#sharePdf').click();
    await page.waitForFunction(()=>window.editorExportResult&&!window.__reader.editor.busy);
    const capture=await page.evaluate(()=>window.editorExportResult);
    assert.equal(capture.purpose,'share');assert.equal(capture.filename,'editable.pdf');assert.equal(capture.status,'opened');
    assert.deepEqual(Buffer.from(capture.data,'base64'),fs.readFileSync(path.join(temp,'editable.pdf')));
    assert.deepEqual(await page.evaluate(()=>({id:window.__reader.state.current.id,revision:window.__reader.state.current.revision,count:window.__reader.state.documents.length})),before);
    assert.equal(await page.evaluate(()=>window.__reader.editor.dirty),false);
    assert.match(await page.locator('#toast').textContent(),/Choose an app/);
  });
  await check('Print unedited PDF hands exact original bytes to Android printing without a new document or save claim',async()=>{
    const before=await page.evaluate(()=>({id:window.__reader.state.current.id,revision:window.__reader.state.current.revision,count:window.__reader.state.documents.length}));
    await page.evaluate(()=>{window.editorExportNextStatus=null;window.editorExportResult=null;});
    await page.locator('#printPdf').click();
    await page.waitForFunction(()=>window.editorExportResult&&!window.__reader.editor.busy);
    const capture=await page.evaluate(()=>window.editorExportResult);
    assert.equal(capture.purpose,'print');assert.equal(capture.filename,'editable.pdf');assert.equal(capture.status,'opened');
    assert.deepEqual(Buffer.from(capture.data,'base64'),fs.readFileSync(path.join(temp,'editable.pdf')));
    assert.deepEqual(await page.evaluate(()=>({id:window.__reader.state.current.id,revision:window.__reader.state.current.revision,count:window.__reader.state.documents.length})),before);
    assert.equal(await page.evaluate(()=>window.__reader.editor.dirty),false);
    assert.match(await page.locator('#toast').textContent(),/Choose a printer/);
  });
  await check('Restored pen defaults and original page bookmark remain independent of PDF annotations',async()=>{
    await tool('read');await page.locator('#editorColour').selectOption('#163c82');
    await page.locator('#editorWidth').fill('4.5');await page.locator('#editorWidth').dispatchEvent('input');
    await page.reload();await page.waitForFunction(()=>!!window.__reader);await openLibrary(originalId);await goto(2);
    assert.equal(await page.locator('#editorColour').inputValue(),'#163c82');assert.equal(await page.locator('#editorWidth').inputValue(),'4.5');
    await page.locator('#outlineToggle').click();await page.locator('#showBookmarks').click();await page.locator('#bookmarkCurrent').click();
    assert.equal(await page.locator('[data-bookmark-page="2"]').count(),1);await page.locator('#outlineToggle').click();
    assert.equal(await page.evaluate(()=>window.__reader.editor.dirty),false);
  });
  await check('Finger-drawn signature belongs to page 2; undo and redo restore the edit',async()=>{
    await ink(2,true);assert.equal(await page.locator('.page[data-page-number="2"] .inkEditor').count(),1);
    await page.locator('#editorUndo').click();await page.waitForFunction(()=>!document.querySelector('.inkEditor'));
    await page.locator('#editorRedo').click();await page.waitForFunction(()=>!!document.querySelector('.page[data-page-number="2"] .inkEditor'));
    await page.screenshot({path:path.join(artifacts,'android-signature-page2.png')});
  });
  await check('Back cancels Add Text through the existing Cancel action and preserves unsaved ink in English and Arabic',async()=>{
    for(const lang of ['en','ar']){
      if(await page.locator('html').getAttribute('lang')!==lang)await page.locator('#language').click();
      await tool('text');await page.locator('#textDialog').waitFor();
      await page.locator('#editTextInput').fill(lang==='ar'?'نص لم تتم إضافته':'Text not inserted');
      const before=await page.evaluate(()=>({id:window.__reader.state.current.id,revision:window.__reader.state.current.revision,page:window.__reader.viewer.currentPageNumber,count:window.__reader.state.documents.length,hash:window.__reader.state.pdf.annotationStorage.serializable.hash}));
      assert.equal(await page.evaluate(()=>window.localPDFBack()),true);
      assert(!await page.locator('#textDialog').isVisible());
      assert.equal(await page.locator('#editTool').inputValue(),'read');
      assert.match(await page.locator('#editTool').evaluate(node=>node.parentElement.querySelector('.toolbar-glyph').style.getPropertyValue('--toolbar-image')),/handTool/);
      assert.deepEqual(await page.evaluate(()=>({id:window.__reader.state.current.id,revision:window.__reader.state.current.revision,page:window.__reader.viewer.currentPageNumber,count:window.__reader.state.documents.length,hash:window.__reader.state.pdf.annotationStorage.serializable.hash})),before);
      assert(await page.evaluate(()=>window.__reader.editor.dirty));
      assert.equal(await page.locator('.page[data-page-number="2"] .inkEditor').count(),1);
      assert.equal(await page.locator('.stampEditor').count(),0);
      await tool('text');await page.locator('#textDialog').waitFor();
      assert.equal(await page.locator('#editTextInput').inputValue(),'');
      await page.locator('#cancelEditText').click();
      assert.equal(await page.locator('#editTool').inputValue(),'read');
    }
    await page.locator('#language').click();
  });
  await check('Share includes unsaved signature and retains dirty state, original identity, notes and bookmark',async()=>{
    const before=await page.evaluate(()=>({id:window.__reader.state.current.id,revision:window.__reader.state.current.revision,count:window.__reader.state.documents.length}));
    await page.evaluate(()=>{window.editorExportNextStatus=null;window.editorExportResult=null;});
    await page.locator('#sharePdf').click();await page.waitForFunction(()=>window.editorExportResult&&!window.__reader.editor.busy);
    const capture=await page.evaluate(()=>window.editorExportResult);
    assert.equal(capture.purpose,'share');assert.equal(capture.filename,'editable-edited.pdf');
    const bytes=Buffer.from(capture.data,'base64');assert.equal(bytes.length,capture.size);
    const report=inspect('editable.pdf',bytes,'shared-signature-page2');
    assert.equal(report.page_count,3);assert.equal(report.pages[1].annotations[0].type,'Ink');
    assert.equal(report.pages[0].changed_channels,0);assert.equal(report.pages[2].changed_channels,0);assert(report.pages[1].changed_channels>0);
    assert.deepEqual(await page.evaluate(()=>({id:window.__reader.state.current.id,revision:window.__reader.state.current.revision,count:window.__reader.state.documents.length})),before);
    assert(await page.evaluate(()=>window.__reader.editor.dirty));
    const note=await backend('/api/studio/'+noteId,null,'GET');assert.equal(note.content.selection.document_id,originalId);assert.equal(note.content.selection.page,2);
    await page.locator('#outlineToggle').click();await page.locator('#showBookmarks').click();assert.equal(await page.locator('[data-bookmark-page="2"]').count(),1);await page.locator('#outlineToggle').click();
  });
  await check('Share failure and missing bridge preserve edits and release the busy guard for Save copy',async()=>{
    await page.evaluate(()=>{window.editorExportNextStatus='error';window.editorExportResult=null;});
    await page.locator('#sharePdf').click();await page.waitForFunction(()=>window.editorExportResult&&!window.__reader.editor.busy);
    assert(await page.evaluate(()=>window.__reader.editor.dirty));assert.equal(await page.locator('#saveEdited').isDisabled(),false);
    assert.equal(await page.locator('#sharePdf').isDisabled(),false);assert.equal(await page.locator('main').getAttribute('inert'),null);
    assert.equal(await page.evaluate(()=>window.__reader.state.current.id),originalId);
    const unavailable=await page.evaluate(async()=>{
      const channel=window.LocalPDFExport;delete window.LocalPDFExport;
      try{await window.__reader.editor.sharePdf();return false;}catch{return true;}finally{window.LocalPDFExport=channel;}
    });
    assert(unavailable);assert(await page.evaluate(()=>window.__reader.editor.dirty&&!window.__reader.editor.busy));
    assert.equal(await page.locator('#saveEdited').isDisabled(),false);
  });
  await check('Print includes unsaved signature and keeps edits unsaved, original identity, notes and bookmark',async()=>{
    const before=await page.evaluate(()=>({id:window.__reader.state.current.id,revision:window.__reader.state.current.revision,count:window.__reader.state.documents.length}));
    await page.evaluate(()=>{window.editorExportNextStatus=null;window.editorExportResult=null;});
    await page.locator('#printPdf').click();await page.waitForFunction(()=>window.editorExportResult&&!window.__reader.editor.busy);
    const capture=await page.evaluate(()=>window.editorExportResult);
    assert.equal(capture.purpose,'print');assert.equal(capture.filename,'editable-edited.pdf');
    const bytes=Buffer.from(capture.data,'base64');assert.equal(bytes.length,capture.size);
    const report=inspect('editable.pdf',bytes,'printed-signature-page2');
    assert.equal(report.page_count,3);assert.equal(report.pages[1].annotations[0].type,'Ink');
    assert.equal(report.pages[0].changed_channels,0);assert.equal(report.pages[2].changed_channels,0);assert(report.pages[1].changed_channels>0);
    assert.deepEqual(await page.evaluate(()=>({id:window.__reader.state.current.id,revision:window.__reader.state.current.revision,count:window.__reader.state.documents.length})),before);
    assert(await page.evaluate(()=>window.__reader.editor.dirty));
    assert.match(await page.locator('#toast').textContent(),/Choose a printer/);
    const note=await backend('/api/studio/'+noteId,null,'GET');assert.equal(note.content.selection.document_id,originalId);assert.equal(note.content.selection.page,2);
    await page.locator('#outlineToggle').click();await page.locator('#showBookmarks').click();assert.equal(await page.locator('[data-bookmark-page="2"]').count(),1);await page.locator('#outlineToggle').click();
  });
  await check('Print failure, password-protected PDF and missing bridge preserve edits and release the busy guard',async()=>{
    for(const lang of ['en','ar']){
      if(await page.locator('html').getAttribute('lang')!==lang)await page.locator('#language').click();
      await page.evaluate(()=>{window.editorExportNextStatus='error';window.editorExportResult=null;});
      await page.locator('#printPdf').click();await page.waitForFunction(()=>window.editorExportResult&&!window.__reader.editor.busy);
      assert(await page.evaluate(()=>window.__reader.editor.dirty));
      for(const id of ['saveEdited','sharePdf','printPdf'])assert.equal(await page.locator('#'+id).isDisabled(),false);
      assert.equal(await page.locator('main').getAttribute('inert'),null);
      // Protected PDFs are refused before any bytes leave the reader.
      await page.evaluate(()=>{window.editorExportNextStatus=null;window.editorExportResult=null;window.__reader.state.openedPassword='secret';});
      await page.locator('#printPdf').click();await delay(200);
      assert.equal(await page.evaluate(()=>window.editorExportResult),null);
      assert.match(await page.locator('#toast').textContent(),lang==='ar'?/المحمية بكلمة مرور/:/Password-protected/);
      assert(await page.evaluate(()=>window.__reader.editor.dirty&&!window.__reader.editor.busy));
      await page.evaluate(()=>{delete window.__reader.state.openedPassword;});
    }
    await page.locator('#language').click();
    const unavailable=await page.evaluate(async()=>{
      const channel=window.LocalPDFExport;delete window.LocalPDFExport;
      try{await window.__reader.editor.printPdf();return false;}catch{return true;}finally{window.LocalPDFExport=channel;}
    });
    assert(unavailable);assert(await page.evaluate(()=>window.__reader.editor.dirty&&!window.__reader.editor.busy));
    assert.equal(await page.evaluate(()=>window.__reader.state.current.id),originalId);
  });
  await check('Save copy produces a new PDF identity, real exported ink and unchanged original bytes',async()=>{
    const {bytes}=await nativeExport();
    editedId=await page.evaluate(()=>window.__reader.state.current.id);await indexed();
    assert.notEqual(editedId,originalId);assert.equal(await page.evaluate(()=>window.__reader.state.documents.length),2);
    const report=inspect('editable.pdf',bytes,'signature-page2');
    assert.equal(editedId,report.exported_sha.slice(0,24));
    assert.equal(await page.evaluate(()=>window.__reader.state.current.revision),report.exported_sha);
    assert.equal(report.page_count,3);assert.equal(report.pages[0].annotations.length,0);assert.equal(report.pages[2].annotations.length,0);
    const inkAnnotations=report.pages[1].annotations.filter(a=>a.type==='Ink');assert.equal(inkAnnotations.length,1);
    assert(Math.abs(inkAnnotations[0].width-4.5)<0.01);assert.deepEqual(inkAnnotations[0].colour.stroke.map(x=>Math.round(x*255)),[22,60,130]);
    assert(inkAnnotations[0].vertices[0].length>=4);assert(report.pages[1].changed_channels>100);
    assert.equal(report.pages[0].changed_channels,0);assert.equal(report.pages[2].changed_channels,0);
    assert.equal(report.original_sha,originalRevision);
    assert.deepEqual(await page.evaluate(id=>JSON.parse(localStorage.getItem('insight-bookmarks-v1-'+id)),originalId),[2]);
    assert.equal(await page.evaluate(id=>localStorage.getItem('insight-bookmarks-v1-'+id),editedId),null);
    await page.locator('#outlineToggle').click();await page.locator('#showBookmarks').click();assert.equal(await page.locator('[data-bookmark-page]').count(),0);await page.locator('#outlineToggle').click();
    const originalBlob=await page.evaluate(async id=>{
      const db=await new Promise((resolve,reject)=>{const request=indexedDB.open('localpdf-android-reader-v1',1);request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error);});
      const stored=await new Promise((resolve,reject)=>{const request=db.transaction('pdfs').objectStore('pdfs').get(id);request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error);});
      const sha=await crypto.subtle.digest('SHA-256',await stored.blob.arrayBuffer());db.close();return Array.from(new Uint8Array(sha),b=>b.toString(16).padStart(2,'0')).join('');
    },originalId);assert.equal(originalBlob,originalRevision);
  });
  await check('Saved annotation survives reload and original note reopens original PDF/page',async()=>{
    await page.reload();await page.waitForFunction(()=>!!window.__reader&&window.__reader.state.documents.length===2);
    await openLibrary(editedId);await goto(2);
    const annotations=await page.evaluate(async()=> (await (await window.__reader.state.pdf.getPage(2)).getAnnotations()).map(a=>a.subtype));assert(annotations.includes('Ink'));
    await page.locator('#studioToggle').click();await page.locator('#studioList .saved-output').first().click();
    await page.waitForFunction(id=>document.getElementById('studioOutput').dataset.outputId===id,noteId);
    await page.locator('#studioOutput .citation').click();
    await page.waitForFunction(id=>window.__reader.state.current?.id===id&&window.__reader.viewer.currentPageNumber===2,originalId);
    assert.equal(await page.evaluate(()=>window.__reader.state.current.revision),originalRevision);await page.locator('.evidence-region').waitFor();
  });
  await check('Closing editing tools restores ordinary one-finger PDF scrolling',async()=>{
    await goto(1);await tool('ink');await page.locator('#editToggle').click();
    assert(!await page.locator('#editBar').isVisible());
    await page.waitForFunction(()=>window.__reader.viewer.annotationEditorMode===0&&!document.body.classList.contains('pdf-drawing'));
    const before=await page.evaluate(()=>document.getElementById('viewerContainer').scrollTop);
    const cdp=await context.newCDPSession(page);
    await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:200,y:700}]});
    for(const y of [660,620,560,500,430])await cdp.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:200,y}]});
    await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});await cdp.detach();
    await page.waitForFunction(before=>document.getElementById('viewerContainer').scrollTop>before+30,before);
    // Let the browser finish the fling before the next test jumps to a page.
    await delay(700);
  });
  await check('Edits on separate pages survive zoom and viewport rotation; delete removes only selected edit',async()=>{
    await ink(1);await ink(3);
    await page.setViewportSize({width:915,height:412});await viewOption('zoom','page-fit');await delay(200);
    await page.setViewportSize({width:412,height:915});await viewOption('zoom','page-width');
    await goto(3);
    await tool('ink');
    const editor=page.locator('.page[data-page-number="3"] .inkEditor');await editor.click();
    await page.locator('#editorDelete').click();await page.waitForFunction(()=>!document.querySelector('.page[data-page-number="3"] .inkEditor'));
    const {bytes}=await nativeExport(),report=inspect('editable.pdf',bytes,'multi-page-delete');
    assert.equal(report.pages[0].annotations.filter(a=>a.type==='Ink').length,1);assert.equal(report.pages[2].annotations.length,0);
  });
  await check('Intrinsic page rotation maps exported ink onto the correct visible region',async()=>{
    await page.locator('#fileInput').setInputFiles(path.join(temp,'rotated-editable.pdf'));await ready('rotated-editable.pdf');await indexed();
    await ink(1);const {bytes}=await nativeExport(),report=inspect('rotated-editable.pdf',bytes,'rotated-signature');
    assert.equal(report.pages[0].rotation,90);assert.equal(report.pages[0].annotations.filter(a=>a.type==='Ink').length,1);assert(report.pages[0].changed_channels>100);
    const bounds=report.pages[0].annotations[0].rect;assert(bounds.every(Number.isFinite));assert(bounds[0]>=0&&bounds[1]>=0&&bounds[2]<=700&&bounds[3]<=400);
  });
  await check('English and Arabic added text retain visible appearances in the actual saved PDF',async()=>{
    await openLibrary(originalId);
    for(const [number,text] of [[1,'Approved by Ali 2026'],[3,'تم التوقيع علي ٢٠٢٦ ABC-123']]) {
      await goto(number);await tool('text');
      await page.locator('#textDialog').waitFor();await page.locator('#editTextInput').fill(text);await page.locator('#insertText').click();
      await page.waitForFunction(n=>!!document.querySelector(`.page[data-page-number="${n}"] .stampEditor`),number);
      await page.waitForFunction(()=>!window.__reader.editor.busy&&!document.getElementById('textDialog').open);
    }
    const {bytes}=await nativeExport(),report=inspect('editable.pdf',bytes,'bilingual-added-text');
    assert(report.pages[0].annotations.length>0&&report.pages[2].annotations.length>0);
    assert(report.pages[0].changed_channels>100&&report.pages[2].changed_channels>100);
    assert.equal(report.pages[1].changed_channels,0);
    // Text is rendered as a PDF image stamp so Arabic shaping does not depend
    // on PDF.js's built-in Helvetica font. Inspect exported-page-3.png visually.
    await page.screenshot({path:path.join(artifacts,'android-added-arabic-text.png')});
  });
  await check('Long English and Arabic tokens wrap without clipping their added-text annotations',async()=>{
    await openLibrary(originalId);
    const tokens=[[1,'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.repeat(6)+'END123'],[3,'المصدر'.repeat(25)+'النهاية']];
    for(const [number,text] of tokens){
      await goto(number);await tool('text');await page.locator('#editTextInput').fill(text);await page.locator('#insertText').click();
      await page.locator(`.page[data-page-number="${number}"] .stampEditor canvas`).waitFor();
      await page.waitForFunction(()=>!window.__reader.editor.busy&&!document.getElementById('textDialog').open);
    }
    const {bytes}=await nativeExport(),report=inspect('editable.pdf',bytes,'wrapped-long-text');
    for(const n of [0,2]){
      const stamps=report.pages[n].annotations.filter(a=>a.type==='Stamp');assert.equal(stamps.length,1);
      const [x0,y0,x1,y1]=stamps[0].rect;
      assert((y1-y0)/(x1-x0)>.25,'Long tokens must occupy multiple rendered lines, rather than a clipped single line');
      assert(report.pages[n].changed_channels>100);
    }
  });
  await check('Pointer-selected text highlighting is retained in the exported PDF',async()=>{
    await openLibrary(originalId);await goto(1);await tool('highlight');
    const text=page.locator('.page[data-page-number="1"] .textLayer span').filter({hasText:'Original source passage'}).first();
    await text.waitFor();const box=await text.boundingBox();assert(box&&box.width>30);
    await page.mouse.move(box.x+2,box.y+box.height/2);await page.mouse.down();
    const afterDown=await text.boundingBox();assert(Math.abs(afterDown.y-box.y)<1,'Starting an edit must not move the source passage under the pointer');
    await page.mouse.move(box.x+box.width-2,box.y+box.height/2,{steps:18});await page.mouse.up();
    await page.locator('.page[data-page-number="1"] .highlightEditor').waitFor();await tool('read');
    // Search highlights are temporary; closing search must preserve the real PDF annotation.
    await page.locator('#findToggle').click(); await page.locator('#findInput').fill('Original source passage');
    await page.locator('.textLayer .highlight').first().waitFor();
    await page.locator('#findToggle').click();
    await page.waitForFunction(()=>!document.querySelector('.textLayer .highlight'));
    assert.equal(await page.locator('.page[data-page-number="1"] .highlightEditor').count(),1);
    assert(await page.evaluate(()=>window.__reader.editor.dirty));
    const {bytes}=await nativeExport(),report=inspect('editable.pdf',bytes,'highlighted-passage');
    assert.equal(report.pages[0].annotations.filter(a=>a.type==='Highlight').length,1);
    assert(report.pages[0].changed_channels>100);assert.equal(report.pages[1].changed_channels,0);assert.equal(report.pages[2].changed_channels,0);
  });
  await check('Form fields export filled values and checkbox state',async()=>{
    await page.locator('#fileInput').setInputFiles(path.join(temp,'form.pdf'));await ready('form.pdf');await indexed();
    await page.locator('.annotationLayer input[type="text"]').fill('Ali Review 2026');await page.locator('.annotationLayer input[type="checkbox"]').check();
    const {bytes}=await nativeExport(),report=inspect('form.pdf',bytes,'filled-form');
    assert.equal(report.pages[0].widgets.find(w=>w.name==='signer_name').value,'Ali Review 2026');
    assert.notEqual(report.pages[0].widgets.find(w=>w.name==='approved').value,'Off');assert(report.pages[0].changed_channels>100);
  });
  await check('Cancelled and failed native exports never claim a successful file save',async()=>{
    await ink(1);assert(await page.evaluate(()=>window.__reader.editor.dirty));
    await nativeExport('cancelled');await delay(100);assert(!/saved to|exported|successfully saved/i.test(await page.locator('#toast').textContent()));
    assert(await page.evaluate(()=>window.__reader.editor.dirty));
    await nativeExport('error');await delay(100);assert(!/saved to|exported|successfully saved/i.test(await page.locator('#toast').textContent()));
    assert(await page.evaluate(()=>window.__reader.editor.dirty));
    await page.locator('#editorUndo').click();await page.waitForFunction(()=>!document.querySelector('.inkEditor'));
    await page.locator('#editorRedo').click();await page.waitForFunction(()=>!!document.querySelector('.inkEditor'));
  });
  await check('Pending native export prevents PDF interaction and retains edits on cancellation',async()=>{
    await page.evaluate(()=>{window.editorExportNextStatus='pending';window.editorExportResult=null;});
    await page.locator('#saveEdited').click();await page.waitForFunction(()=>!!window.editorExportResult&&window.__reader.editor.busy);
    assert(await page.locator('#editTool').isDisabled());assert(await page.locator('#saveEdited').isDisabled());
    const before=await page.evaluate(()=>window.__reader.state.pdf.annotationStorage.serializable.hash);
    const field=page.locator('.annotationLayer input[type="text"]');
    const box=await field.boundingBox();await page.mouse.click(box.x+10,box.y+10);await page.keyboard.type('UNSAVED-WHILE-EXPORTING');
    assert.equal(await page.evaluate(()=>window.__reader.state.pdf.annotationStorage.serializable.hash),before);
    await page.evaluate(()=>window.editorCompletePendingExport('cancelled'));
    await page.waitForFunction(()=>!window.__reader.editor.busy);assert(await page.evaluate(()=>window.__reader.editor.dirty));
  });
  await check('Unavailable Android export channel refuses saving without discarding or importing edits',async()=>{
    const result=await page.evaluate(async()=>{
      const before={id:window.__reader.state.current.id,count:window.__reader.state.documents.length};
      const bridge=window.LocalPDFExport;delete window.LocalPDFExport;let error='';
      try{await window.__reader.editor.saveCopy();}catch(failure){error=failure.message;}finally{window.LocalPDFExport=bridge;}
      return {before,id:window.__reader.state.current.id,count:window.__reader.state.documents.length,error,dirty:window.__reader.editor.dirty,busy:window.__reader.editor.busy,inert:document.querySelector('main').inert};
    });
    assert(result.error,'Missing native export bridge must reject the save operation');
    assert.equal(result.id,result.before.id);assert.equal(result.count,result.before.count);assert(result.dirty);assert(!result.busy&&!result.inert);
  });
  await check('Cancelling an import while edits are unsaved preserves the active PDF and its identity',async()=>{
    const before=await page.evaluate(()=>({id:window.__reader.state.current.id,pages:window.__reader.state.pdf.numPages,count:window.__reader.state.documents.length}));
    let seen=false;page.once('dialog',async dialog=>{seen=true;await dialog.dismiss();});
    await page.locator('#fileInput').setInputFiles(path.join(temp,'rotated-editable.pdf'));
    await page.waitForFunction(()=>!window.__reader.state.importing);assert(seen,'Unsaved changes must be acknowledged before replacing the PDF');
    assert.equal(await page.evaluate(()=>window.__reader.state.current.id),before.id);
    assert.equal(await page.evaluate(()=>window.__reader.state.pdf.numPages),before.pages);
    assert.equal(await page.evaluate(()=>window.__reader.state.documents.length),before.count);
    assert(await page.evaluate(()=>window.__reader.editor.dirty));
  });
  await check('An unfinished ink stroke triggers the document-switch guard',async()=>{
    // Clear previous changes by saving, then start a real stroke without pointerup.
    await nativeExport();await goto(1);await tool('ink');
    const before=await page.evaluate(()=>({id:window.__reader.state.current.id,count:window.__reader.state.documents.length}));
    const box=await page.locator('.page[data-page-number="1"] .annotationEditorLayer').boundingBox();
    await page.mouse.move(box.x+box.width*.2,box.y+box.height*.5);await page.mouse.down();
    await page.mouse.move(box.x+box.width*.5,box.y+box.height*.6,{steps:12});
    assert(await page.evaluate(()=>window.__reader.editor.dirty),'Starting a real ink stroke must mark the page as changed before pointerup');
    let seen=false;page.once('dialog',async dialog=>{seen=true;await dialog.dismiss();});
    await page.locator('#fileInput').setInputFiles(path.join(temp,'editable.pdf'));
    await page.waitForFunction(()=>!window.__reader.state.importing);await page.mouse.up();
    assert(seen,'In-progress ink must not bypass the unsaved-changes prompt');
    assert.equal(await page.evaluate(()=>window.__reader.state.current.id),before.id);
    assert.equal(await page.evaluate(()=>window.__reader.state.documents.length),before.count);assert(await page.evaluate(()=>window.__reader.editor.dirty));
  });
  await check('Editor works without Ollama, server or external network requests',async()=>{assert.deepEqual(network,[]);assert.deepEqual(errors,[]);});
  await page.screenshot({path:path.join(artifacts,'android-editor-mobile.png')});
 }catch(error){console.error(error);process.exitCode=1;if(page){console.error('STATE',await page.evaluate(()=>({current:window.__reader?.state.current,toast:document.getElementById('toast')?.textContent,editor:window.__reader?.editor?Object.keys(window.__reader.editor):null})));await page.screenshot({path:path.join(artifacts,'failure.png')}).catch(()=>{});}}
 finally{const report={environment:'Offline mobile Chromium; actual PDF.js saved bytes, mocked narrow native export transport, independent PyMuPDF export/render inspection; physical Android not tested',passed:results.filter(r=>r.status==='passed').length,failed:results.filter(r=>r.status==='failed').length,results,attemptedNetwork:network,browserErrors:errors,fixtureDirectory:temp};fs.writeFileSync(path.join(artifacts,'editor-browser-results.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));if(browser)await browser.close();}
})();

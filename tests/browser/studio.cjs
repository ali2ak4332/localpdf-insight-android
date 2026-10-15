// Real browser, real PDF extraction, no Ollama configured. API model contracts are tested separately.
const assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {spawn,spawnSync}=require('node:child_process');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'../..'),temp=fs.mkdtempSync(path.join(os.tmpdir(),'localpdf-studio-'));
const python=process.env.LOCALPDF_TEST_PYTHON||'python3',base='http://127.0.0.1:8767';
const env={...process.env,PYTHONPATH:path.join(root,'src'),LOCALPDF_DATA:path.join(temp,'data'),LOCALPDF_MODEL:'',LOCALPDF_EMBED_MODEL:'',LOCALPDF_TOKEN:'',LOCALPDF_HOSTS:'localhost,127.0.0.1'};
const fixture=spawnSync(python,[path.join(__dirname,'fixtures.py'),temp],{env,encoding:'utf8'});assert.equal(fixture.status,0,fixture.stderr);
let server,browser,page;const errors=[],results=[];let serverErrors='';const delay=ms=>new Promise(r=>setTimeout(r,ms));
function launch(){server=spawn(python,['-m','localpdf_insight.web','--port','8767'],{env,detached:process.platform!=='win32'});server.stderr.on('data',b=>serverErrors+=b);}
function stopServer(){try{if(process.platform==='win32')server.kill('SIGTERM');else process.kill(-server.pid,'SIGTERM');}catch(e){if(e.code!=='ESRCH')throw e;}}
async function ready(){for(let n=0;n<100;n++){try{if((await fetch(base+'/')).ok)return;}catch{}await delay(100);}throw Error('Server did not start');}
async function check(name,fn){await fn();results.push(name);console.log('PASS',name);}
async function selectPassage(){await page.locator('#pageNumber').fill('18');await page.locator('#pageNumber').dispatchEvent('change');await page.locator('.page[data-page-number="18"] .textLayer span').first().waitFor();
 return page.evaluate(()=>{const span=[...document.querySelectorAll('.page[data-page-number="18"] .textLayer span')].find(s=>s.textContent.includes('agreement may'));const range=document.createRange();range.selectNodeContents(span);const selection=getSelection();selection.removeAllRanges();selection.addRange(range);document.getElementById('viewerContainer').dispatchEvent(new PointerEvent('pointerup',{bubbles:true}));return span.textContent;});}
(async()=>{try{
 launch();await ready();browser=await chromium.launch({headless:true,...(process.env.CHROMIUM_EXECUTABLE?{executablePath:process.env.CHROMIUM_EXECUTABLE,args:['--no-sandbox','--disable-gpu','--disable-dev-shm-usage']}:{})});
 page=await browser.newPage({viewport:{width:1500,height:1100},hasTouch:true});page.on('pageerror',e=>errors.push(e.message));await page.goto(base+'/?test=1');await page.waitForFunction(()=>!!window.__reader);
 let docId,savedId,noteId,sourceId;
 await check('Suggestions originate in the indexed PDF and run normal cited Q&A',async()=>{
  await page.locator('#fileInput').setInputFiles(path.join(temp,'agreement.pdf'));await page.waitForFunction(()=>window.__reader.state.current?.index.status==='ready',null,{timeout:60000});docId=await page.evaluate(()=>window.__reader.state.current.id);
  await page.locator('#askToggle').click();await page.locator('#suggestions button').first().waitFor();assert((await page.locator('#suggestions button').count())<=6);
  const question=await page.locator('#suggestions button').first().textContent();const request=page.waitForRequest(r=>r.url().endsWith('/api/ask'));
  await page.locator('#suggestions button').first().click();assert.equal((await request).postDataJSON().question,question);await page.locator('#answer .citation').first().waitFor();
 });
 await check('Selected Explain retains text, page, document and coordinates',async()=>{
  const selected=await selectPassage();await page.locator('#selectionMenu').waitFor();const request=page.waitForRequest(r=>r.url().endsWith('/api/ask'));
  await page.locator('[data-action="Explain"]').click();const body=(await request).postDataJSON();assert.equal(body.selection.text,selected);assert.equal(body.selection.document_id,docId);assert.equal(body.selection.page,18);assert.equal(body.selection.bbox.length,4);
  await page.locator('#answer .claim .citation').first().waitFor();await page.locator('#answer .claim .citation').first().click();assert.equal(await page.evaluate(()=>window.__reader.viewer.currentPageNumber),18);
 });
 await check('Executive Summary saves automatically and reopens with stable citations',async()=>{
  await page.locator('#studioTab').click();await page.locator('#studioType').selectOption('Executive summary');await page.locator('#createOutput').click();await page.locator('#studioOutput .claim').first().waitFor();savedId=await page.locator('#studioOutput').getAttribute('data-output-id');assert(savedId);
  sourceId=await page.locator('#studioOutput .claim .citation').first().getAttribute('data-source-id');const item=await (await page.request.get(base+'/api/studio/'+savedId)).json();assert.equal(item.scope.documents[0].id,docId);assert(item.content.coverage.partial);
  await page.screenshot({path:path.join(temp,'studio-desktop.png')});
 });
 await check('Source-linked note preserves the passage and optional Arabic comment',async()=>{
  await page.locator('#closeInspector').click();await selectPassage();await page.locator('[data-action="note"]').click();await page.locator('#noteComment').fill('Verify notice period / تحقّق من مدة الإشعار');await page.locator('#noteForm button[type=submit], #noteForm button.primary').click();
  await page.locator('#studioOutput').filter({hasText:'تحقّق من مدة الإشعار'}).waitFor();noteId=await page.locator('#studioOutput').getAttribute('data-output-id');const note=await (await page.request.get(base+'/api/studio/'+noteId)).json();assert.equal(note.content.selection.page,18);assert.equal(note.content.selection.document_id,docId);assert(note.content.selection.bbox);
  await page.locator('#studioOutput .citation').first().click();assert.equal(await page.evaluate(()=>window.__reader.viewer.currentPageNumber),18);
 });
 await check('Saved output survives server restart and opens the original PDF after switching documents',async()=>{
  await new Promise(resolve=>{server.once('exit',resolve);stopServer();});launch();await ready();await page.reload();await page.waitForFunction(()=>!!window.__reader);
  await page.locator('#fileInput').setInputFiles(path.join(temp,'revision.pdf'));await page.waitForFunction(()=>window.__reader.state.current?.filename==='revision.pdf'&&window.__reader.state.current.index.status==='ready',null,{timeout:60000});
  await page.locator('#studioToggle').click();await page.locator('#studioList .saved-output').filter({hasText:'Executive Summary'}).click();await page.locator('#studioOutput .claim .citation').first().click();
  await page.waitForFunction(id=>window.__reader.state.current?.id===id,docId);const source=await (await page.request.get(`${base}/api/studio/${savedId}/sources/${sourceId}`)).json();assert.equal(await page.evaluate(()=>window.__reader.viewer.currentPageNumber),source.page);await page.locator('.evidence-region').waitFor();
 });
 await check('Quiz is a cited source exercise with a revealable answer key',async()=>{
  await page.locator('#studioType').selectOption('Quiz');await page.locator('#createOutput').click();await page.locator('#studioOutput .study-card').first().waitFor();await page.locator('#studioOutput .study-card summary').first().click();await page.locator('#studioOutput .study-card .citation').first().waitFor();
  const quizId=await page.locator('#studioOutput').getAttribute('data-output-id');const quiz=await (await page.request.get(base+'/api/studio/'+quizId)).json();for(const card of quiz.content.cards){assert(card.explanation.includes(card.back));assert(card.source_ids.every(id=>quiz.content.sources.some(s=>s.id===id&&s.document_id===docId)));}
 });
 await check('Source picker visibly narrows selected documents and does not leak suggestions',async()=>{
  await page.locator('#scope').selectOption('library');await page.locator('#scopePicker summary').click();const checks=page.locator('#scopeDocuments input');assert.equal(await checks.count(),2);assert(await checks.nth(0).isChecked()&&await checks.nth(1).isChecked());
  await page.locator('#scopeDocuments input[aria-label="revision.pdf"]').uncheck();assert.equal(await page.locator('#scope').inputValue(),'selected');assert.equal(await page.locator('#scopeDescription').textContent(),'agreement.pdf');
  await page.locator('#chatTab').click();await page.locator('#suggestions button').first().waitFor();const response=await page.request.post(base+'/api/suggestions',{headers:{'X-LocalPDF':'1'},data:{scope:'selected',document_ids:[docId]}});for(const q of (await response.json()).questions)for(const id of q.source_ids)assert.equal((await (await page.request.get(base+'/api/sources/'+id)).json()).document_id,docId);
 });
 await check('Mobile RTL refuses garbled study prompts and preserves mixed-text notes',async()=>{
  await page.setViewportSize({width:390,height:844});await page.locator('#closeInspector').click();await page.locator('#language').click();await page.locator('#fileInput').setInputFiles(path.join(temp,'arabic.pdf'));await page.waitForFunction(()=>window.__reader.state.current?.filename==='arabic.pdf'&&window.__reader.state.current.index.status==='ready',null,{timeout:60000});
  await page.locator('#askToggle').click();await page.locator('#scope').selectOption('current');await page.locator('#suggestions .warning').waitFor();assert.equal(await page.locator('#suggestions button').count(),0);assert.equal(await page.locator('html').getAttribute('dir'),'rtl');
  if(await page.locator('#scopePicker').getAttribute('open')!==null)await page.locator('#scopePicker summary').click();await page.locator('#studioTab').click();await page.locator('#studioType').selectOption('Quiz');await page.locator('#createOutput').click();await page.locator('#studioOutput').filter({hasText:'لا توجد أدلة كافية لإنشاء تمرين واضح.'}).waitFor();const arabicQuiz=await (await page.request.get(base+'/api/studio/'+await page.locator('#studioOutput').getAttribute('data-output-id'))).json();assert.equal(arabicQuiz.scope.documents[0].id,await page.evaluate(()=>window.__reader.state.current.id));assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.locator('#studioOutput').scrollIntoViewIfNeeded();
  await page.screenshot({path:path.join(temp,'studio-mobile-arabic.png')});
  await page.locator('#closeInspector').click();await page.locator('.textLayer span').first().waitFor();
  await page.evaluate(()=>{const spans=[...document.querySelectorAll('.textLayer span')];const range=document.createRange();range.setStart(spans[0].firstChild,0);range.setEnd(spans.at(-1).firstChild,spans.at(-1).textContent.length);const selection=getSelection();selection.removeAllRanges();selection.addRange(range);document.getElementById('viewerContainer').dispatchEvent(new PointerEvent('pointerup',{bubbles:true}));});
  await page.locator('[data-action="note"]').click();assert.equal(await page.locator('#noteSelection').getAttribute('dir'),'auto');await page.locator('#noteComment').fill('مراجعة العقد ABC-123');await page.locator('#noteForm button.primary').click();await page.locator('#studioOutput').filter({hasText:'مراجعة العقد ABC-123'}).waitFor();
  await page.locator('#studioOutput .citation').first().click();assert.equal(await page.evaluate(()=>window.__reader.viewer.currentPageNumber),1);
 });
 assert.deepEqual(errors,[]);const result={passed:results.length,model:'none — excerpt mode',results};console.log(JSON.stringify(result,null,2));
 const dest=process.env.LOCALPDF_TEST_ARTIFACTS;if(dest){fs.mkdirSync(dest,{recursive:true});for(const name of ['studio-desktop.png','studio-mobile-arabic.png'])fs.copyFileSync(path.join(temp,name),path.join(dest,name));fs.writeFileSync(path.join(dest,'studio-browser-results.json'),JSON.stringify(result,null,2));}
}catch(error){if(page){console.error('UI ERROR',await page.locator('#toast').textContent());await page.screenshot({path:path.join(temp,'failed.png')});console.error('Screenshot',path.join(temp,'failed.png'));}throw error;}finally{if(browser)await browser.close();if(server)stopServer();if(serverErrors.includes('Traceback'))console.error(serverErrors);}})().catch(e=>{console.error(e);process.exitCode=1;});

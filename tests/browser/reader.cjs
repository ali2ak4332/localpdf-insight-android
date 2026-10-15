// Run: npm ci && npx playwright install chromium && npm run test:browser
const assert=require('node:assert/strict');
const fs=require('node:fs');const os=require('node:os');const path=require('node:path');
const {spawn,spawnSync}=require('node:child_process');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'../..');const temp=fs.mkdtempSync(path.join(os.tmpdir(),'localpdf-e2e-'));
const python=process.env.LOCALPDF_TEST_PYTHON||'python3';
const env={...process.env,PYTHONPATH:path.join(root,'src'),LOCALPDF_DATA:path.join(temp,'data'),LOCALPDF_MODEL:'',LOCALPDF_EMBED_MODEL:'',LOCALPDF_TOKEN:'',LOCALPDF_HOSTS:'localhost,127.0.0.1'};
const fixture=spawnSync(python,[path.join(__dirname,'fixtures.py'),temp],{env,encoding:'utf8'});if(fixture.status!==0)throw Error(fixture.stderr);
const server=spawn(python,['-m','localpdf_insight.web','--port','8766'],{env});
let stderr='';server.stderr.on('data',b=>stderr+=String(b));let browser;const results=[];
const base='http://127.0.0.1:8766';
const delay=ms=>new Promise(r=>setTimeout(r,ms));
async function check(name,fn){await fn();results.push(name);console.log('PASS',name);}
(async()=>{try{
 for(let n=0;n<100;n++){try{await fetch(base+'/');break;}catch{await delay(100);}}
 browser=await chromium.launch({headless:true,...(process.env.CHROMIUM_EXECUTABLE?{executablePath:process.env.CHROMIUM_EXECUTABLE,args:['--no-sandbox','--disable-gpu','--disable-dev-shm-usage']}:{})});
 const page=await browser.newPage({viewport:{width:1440,height:1000},hasTouch:true});const errors=[];page.on('pageerror',e=>{errors.push(e.message);console.log('BROWSER ERROR',e.message);});
 await page.goto(base+'/?test=1');await page.waitForFunction(()=>!!window.__reader);let firstId,secondId,sourceId;
 await check('Open 150-page PDF and render selectable text with bounded canvases',async()=>{
  await page.locator('#fileInput').setInputFiles(path.join(temp,'agreement.pdf'));
  await page.waitForFunction(()=>window.__reader.state.pdf?.numPages===150&&window.__reader.state.current);
  await page.locator('.page[data-page-number="1"] .textLayer span').first().waitFor();
  firstId=await page.evaluate(()=>window.__reader.state.current.id);
  assert((await page.locator('.pdfViewer canvas').count())<20);
  assert(await page.locator('.page[data-page-number="1"]').evaluate(p=>p.getBoundingClientRect().width>100));
 });
 await check('Page navigation and PDF outline',async()=>{
  await page.locator('#pageNumber').fill('150');await page.locator('#pageNumber').dispatchEvent('change');
  await page.waitForFunction(()=>window.__reader.viewer.currentPageNumber===150);
  await page.locator('#outlineToggle').click();await page.locator('#contentsList button').filter({hasText:'Termination'}).click();
  await page.waitForFunction(()=>window.__reader.viewer.currentPageNumber===18);await page.locator('#outlineToggle').click();
 });
 await check('Native full-text search highlights and navigates matches',async()=>{
  await page.locator('#findToggle').click();await page.locator('#findInput').fill('written notice');
  await page.waitForFunction(()=>document.getElementById('findCount').textContent.includes('/ 1'));
  await page.locator('.textLayer .highlight').first().waitFor();
  assert.equal(await page.evaluate(()=>window.__reader.viewer.currentPageNumber),18);
 });
 await check('Single/spread layouts, zoom and persistent reading position',async()=>{
  await page.locator('#viewMode').selectOption('single');assert.equal(await page.evaluate(()=>window.__reader.viewer.scrollMode),3);
  await page.locator('#viewMode').selectOption('spread');assert.equal(await page.evaluate(()=>window.__reader.viewer.spreadMode),1);
  await page.locator('#viewMode').selectOption('continuous');await page.locator('#zoom').selectOption('1.5');
  await page.locator('#pageNumber').fill('18');await page.locator('#pageNumber').dispatchEvent('change');await delay(400);
  assert.equal(await page.evaluate(id=>JSON.parse(localStorage.getItem('insight-read-'+id)).page,firstId),18);
 });
 await check('Strict question returns sourced excerpts and citation highlights original page',async()=>{
  await page.waitForFunction(()=>window.__reader.state.current.index?.status==='ready',null,{timeout:60000});
  await page.locator('#askToggle').click();await page.locator('#question').fill('termination written notice');await page.locator('#submitAsk').click();
  await page.locator('#answer .claim .citation').first().waitFor();sourceId=await page.locator('#answer .claim .citation').first().getAttribute('data-source-id');
  await page.locator('#answer .claim .citation').first().click();
  await page.locator('.evidence-region').waitFor();assert.equal(await page.evaluate(()=>window.__reader.viewer.currentPageNumber),18);
 });
 await check('Duplicate file preserves identity',async()=>{
  const payload={name:'copy.pdf',mimeType:'application/pdf',buffer:fs.readFileSync(path.join(temp,'agreement.pdf'))};
  await page.locator('#fileInput').setInputFiles(payload);await page.waitForFunction(id=>window.__reader.state.current?.id===id&&!window.__reader.state.importing,firstId);
  assert.equal(await page.evaluate(()=>window.__reader.state.documents.length),1);
 });
 await check('Citation opens correct PDF after document switch',async()=>{
  await page.locator('#fileInput').setInputFiles(path.join(temp,'revision.pdf'));
  await page.waitForFunction(id=>window.__reader.state.current&&window.__reader.state.current.id!==id,firstId);secondId=await page.evaluate(()=>window.__reader.state.current.id);
  await page.evaluate(id=>window.__reader.openSource(id),sourceId);
  await delay(500);assert.equal(await page.evaluate(()=>window.__reader.state.current.id),firstId);
  assert.equal(await page.evaluate(()=>window.__reader.viewer.currentPageNumber),18);await page.locator('.evidence-region').waitFor();
 });
 await check('Selected-document API excludes unselected evidence',async()=>{
  const response=await page.request.post(base+'/api/search',{headers:{'X-LocalPDF':'1'},data:{scope:'selected',document_ids:[firstId],question:'termination'}});
  assert(response.ok());const data=await response.json();assert(data.sources.length>0&&data.sources.every(s=>s.document_id===firstId));
 });
 await check('Comparison has source links to both documents',async()=>{
  await page.waitForFunction(()=>window.__reader.state.documents.every(d=>d.index.status==='ready'),null,{timeout:60000});
  await page.locator('.doc-card input[type=checkbox]').nth(0).check();await page.locator('.doc-card input[type=checkbox]').nth(1).check();await page.locator('#compare').click();
  await page.locator('.comparison-row .citation').first().waitFor();const links=await page.locator('.comparison-row').filter({hasText:'60 days'}).first().locator('.citation').allTextContents();assert(links.some(s=>s.includes('agreement.pdf'))&&links.some(s=>s.includes('revision.pdf')));
 });
 await check('Mobile viewport and Arabic RTL preserve accessible controls without horizontal overflow',async()=>{
  await page.setViewportSize({width:390,height:844});await page.locator('#closeInspector').click();await page.locator('#language').click();
  assert.equal(await page.locator('html').getAttribute('dir'),'rtl');
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  assert(await page.locator('#askToggle').isVisible());await page.locator('#libraryToggle').click();assert(await page.locator('#library').isVisible());await page.locator('#libraryToggle').click();
  const scale=await page.evaluate(()=>window.__reader.viewer.currentScale);const cdp=await page.context().newCDPSession(page);
  await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:130,y:400},{x:230,y:400}]});
  await cdp.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:100,y:400},{x:260,y:400}]});
  await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
  assert((await page.evaluate(()=>window.__reader.viewer.currentScale))>scale);await page.locator('#zoom').selectOption('page-width');await delay(600);
  await page.screenshot({path:path.join(temp,'mobile.png')});
 });
 await check('Arabic PDF loads and Arabic query retrieves its source',async()=>{
  await page.locator('#fileInput').setInputFiles(path.join(temp,'arabic.pdf'));
  await page.waitForFunction(()=>window.__reader.state.current?.filename==='arabic.pdf'&&window.__reader.state.current.index.status==='ready',null,{timeout:60000});
  const arId=await page.evaluate(()=>window.__reader.state.current.id);
  const response=await page.request.post(base+'/api/search',{headers:{'X-LocalPDF':'1'},data:{scope:'current',current_id:arId,question:'انهاء'}});const data=await response.json();assert(data.sources.length&&data.sources[0].document_id===arId);
  await page.locator('#askToggle').click();await page.locator('#scope').selectOption('current');await page.locator('#question').fill('إنهاء العقد');await page.locator('#submitAsk').click();await page.locator('#answer .claim').first().waitFor();
  await page.screenshot({path:path.join(temp,'arabic.png')});
 });
 await check('PWA shell installed and excludes API data from cache',async()=>{
  await page.evaluate(()=>navigator.serviceWorker.ready);
  assert(await page.evaluate(async()=>{const keys=await caches.keys();if(!keys.length)return false;for(const name of keys){for(const r of await (await caches.open(name)).keys()){if(new URL(r.url).pathname.startsWith('/api/'))return false;}}return true;}));
  const manifest=await (await page.request.get(base+'/static/manifest.webmanifest')).json();assert.equal(manifest.display,'standalone');
 });
 await check('Offline shell opens a local PDF without uploading',async()=>{
  await page.context().setOffline(true);await page.reload();await page.waitForFunction(()=>!!window.__reader);await page.locator('#fileInput').setInputFiles(path.join(temp,'agreement.pdf'));
  await page.waitForFunction(()=>window.__reader.state.pdf?.numPages===150);assert.equal(await page.evaluate(()=>window.__reader.state.current),null);await page.context().setOffline(false);
 });
 assert.deepEqual(errors,[]);console.log(JSON.stringify({passed:results.length,results,artifacts:temp},null,2));
 if(process.env.LOCALPDF_TEST_ARTIFACTS){fs.mkdirSync(process.env.LOCALPDF_TEST_ARTIFACTS,{recursive:true});for(const name of ['mobile.png','arabic.png'])fs.copyFileSync(path.join(temp,name),path.join(process.env.LOCALPDF_TEST_ARTIFACTS,name));fs.writeFileSync(path.join(process.env.LOCALPDF_TEST_ARTIFACTS,'browser-results.json'),JSON.stringify({passed:results.length,results},null,2));}
}catch(error){if(browser){const pages=browser.contexts()[0]?.pages();if(pages?.length){console.log('FAIL STATE',await pages[0].evaluate(()=>({title:document.getElementById('documentTitle').textContent,toast:document.getElementById('toast').textContent,current:window.__reader?.state.current?.filename,importing:window.__reader?.state.importing})));await pages[0].screenshot({path:path.join(temp,'failed.png')});console.log('FAIL SCREENSHOT',path.join(temp,'failed.png'));}}throw error;}finally{if(browser)await browser.close();server.kill('SIGINT');await delay(300);server.kill('SIGKILL');if(stderr.includes('Traceback'))console.error(stderr);}})().catch(error=>{console.error(error);process.exitCode=1;});

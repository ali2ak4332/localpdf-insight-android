// Offline browser integration. Native model transport is explicitly mocked here.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const {spawnSync}=require('node:child_process');const {chromium}=require('playwright');
const root=path.resolve(__dirname,'../..'),staticRoot=path.join(root,'src/localpdf_insight/static');
const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'apt-panel-'));
const fixtures=spawnSync('python3',[path.join(root,'tests/browser/android_fixtures.py'),tmp],{encoding:'utf8'});
if(fixtures.status)throw Error(fixtures.stderr);
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_EXECUTABLE,args:['--no-sandbox','--disable-dev-shm-usage']});
 const context=await browser.newContext({viewport:{width:412,height:915},isMobile:true,hasTouch:true,serviceWorkers:'block'});
 const network=[],errors=[];await context.setOffline(true);
 await context.route('**/*',async route=>{
  const url=new URL(route.request().url());if(['blob:','data:'].includes(url.protocol))return route.continue();
  if(url.origin!=='https://appassets.androidplatform.net'||url.pathname.startsWith('/api/')){network.push(url.href);return route.abort();}
  const f=path.resolve(staticRoot,url.pathname==='/'?'index.html':url.pathname.replace(/^\/static\//,''));
  if(!f.startsWith(staticRoot+path.sep)||!fs.existsSync(f))return route.abort();
  const mime={'.mjs':'text/javascript','.js':'text/javascript','.html':'text/html','.css':'text/css','.svg':'image/svg+xml','.wasm':'application/wasm'};
  await route.fulfill({body:fs.readFileSync(f),contentType:mime[path.extname(f)]||'application/octet-stream'});
 });
 await context.addInitScript(()=>{
  window.mockSelection='[0,999]';window.nativeCalls=[];
  window.AptOfflineAI={postMessage(raw){const r=JSON.parse(raw);window.nativeCalls.push(r);
   const data=r.action==='generate'?{text:window.mockSelection}:{present:true,modelBytes:241410624};
   queueMicrotask(()=>window.AptOfflineAI.onmessage?.({data:JSON.stringify({id:r.id,ok:true,data})}));
  }};
 });
 const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
 try{
  await page.goto('https://appassets.androidplatform.net/?platform=android&test=1');await page.waitForFunction(()=>!!window.__reader);
  const pdf=fs.readdirSync(tmp).find(f=>f.endsWith('.pdf')&&/english/i.test(f))||fs.readdirSync(tmp).find(f=>f.endsWith('.pdf'));
  await page.locator('#fileInput').setInputFiles(path.join(tmp,pdf));
  await page.waitForFunction(()=>window.__reader.state.current&&window.__reader.state.documents.every(d=>d.index.status==='ready'));
  await page.locator('#readerOptionsToggle').click();await page.locator('#aptAnalyze').click();
  assert.equal(await page.locator('#aptTask option').count(),5);
  await page.locator('#aptRun').click();await page.waitForFunction(()=>document.querySelector('#aptResults .apt-finding'));
  assert.match(await page.locator('#aptCoverage').textContent(),/pages|sections/i);
  assert.match(await page.locator('#aptResults').textContent(),/unsupported|rejected/i);
  const quote=await page.locator('#aptResults blockquote').first().textContent();assert.ok(quote.length>5);
  const sourcePage=await page.locator('#aptResults .citation').first().getAttribute('data-page');
  await page.locator('#aptResults .citation').first().click();
  await page.waitForFunction(()=>!document.querySelector('#aptAnalysisDialog').open);
  await page.waitForFunction(n=>window.__reader.viewer.currentPageNumber===Number(n),sourcePage);
  assert.equal(await page.locator('#aptAnalysisDialog').evaluate(d=>d.open),false);
  await page.locator('#readerOptionsToggle').click();await page.locator('#aptAnalyze').click();
  await page.locator('#aptTask').selectOption('verify');await page.locator('#aptVerifyText').fill('Revenue was USD 999999999 million in 2025.');
  const before=await page.evaluate(()=>window.nativeCalls.filter(c=>c.action==='generate').length);
  await page.locator('#aptRun').click();await page.waitForFunction(()=>document.querySelector('#aptResults').textContent.includes('unsupported'));
  assert.equal(await page.evaluate(()=>window.nativeCalls.filter(c=>c.action==='generate').length),before);
  await page.locator('#aptVerifyText').fill(quote);await page.locator('#aptRun').click();
  await page.waitForFunction(()=>document.querySelector('#aptResults').textContent.includes('Exact text'));
  assert.equal(await page.locator('#aptResults .citation').count()>0,true);
  const stale=await context.newPage();
  await stale.route('**/minimal',r=>r.fulfill({contentType:'text/html',body:'<!doctype html><div id="readerOptions"></div>'}));
  await stale.goto('https://appassets.androidplatform.net/minimal');
  await stale.evaluate(async()=>{
   const {createAptPanel}=await import('/static/apt_panel.mjs');
   const document={id:'A',revision:'rA',page_count:1,title:'Old document',index:{status:'ready'}};
   const source={id:'old-source',document_id:'A',revision:'rA',page:1,ordinal:0,text:'Old document contains USD 123 million.'};
   window.staleState={current:document};window.stalePanel=createAptPanel({state:window.staleState,backend:{analysisSnapshot:()=>new Promise(resolve=>{window.finishStale=()=>resolve({document,sources:[source]});})},openSource:async()=>{},closeOptions:()=>{},transport:async()=>({present:true})});
  });
  await stale.locator('#aptAnalyze').click();await stale.locator('#aptTask').selectOption('verify');await stale.locator('#aptVerifyText').fill('Old document contains USD 123 million.');await stale.locator('#aptRun').click();
  await stale.evaluate(()=>{window.staleState.current={id:'B',revision:'rB'};window.stalePanel.documentChanged();window.finishStale();});
  await stale.waitForTimeout(50);
  assert.equal(await stale.locator('#aptResults .apt-finding').count(),0);
  assert.match(await stale.locator('#aptCoverage').textContent(),/Document changed/);
  await stale.close();
  assert.deepEqual(network,[]);assert.deepEqual(errors,[]);
  console.log(JSON.stringify({passed:7,checks:['five tasks','offline evidence and unsupported selection','coverage','clickable physical page','independent wrong-number rejection','exact-text verification','stale verification discarded'],nativeTransport:'mocked',network,errors},null,2));
 }finally{await browser.close();fs.rmSync(tmp,{recursive:true,force:true});}
})().catch(e=>{console.error(e);process.exitCode=1;});

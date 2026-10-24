// Read-only evaluation setup: use the actual Android PDF.js/indexing pipeline.
const fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');
const [manifestPath,outputPath]=process.argv.slice(2);
const root=path.resolve(__dirname,'../..'),staticRoot=path.join(root,'src/localpdf_insight/static');
const raw=JSON.parse(fs.readFileSync(manifestPath));
const manifest=Array.isArray(raw)?raw:(raw.documents||raw.entries||[]);
const prior=fs.existsSync(outputPath)?JSON.parse(fs.readFileSync(outputPath)):{documents:[]};
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
  return route.fulfill({body:fs.readFileSync(f),contentType:mime[path.extname(f)]||'application/octet-stream'});
 });
 const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
 try{
  await page.goto('https://appassets.androidplatform.net/?platform=android&test=1');await page.waitForFunction(()=>!!window.__reader);
  for(const entry of manifest){
   if(prior.documents.some(d=>d.id===entry.id&&d.sha256===entry.sha256))continue;
   const pdfPath=entry.pdfPath||entry.localPath;
   await page.locator('#fileInput').setInputFiles(pdfPath);
   await page.waitForFunction(hash=>window.__reader.state.current?.revision===hash&&window.__reader.state.documents.find(d=>d.revision===hash)?.index.status==='ready',entry.sha256,{timeout:120000});
   const snapshot=await page.evaluate(async()=>{
    const document=window.__reader.state.current;
    const db=await new Promise((res,rej)=>{const r=indexedDB.open('localpdf-android-reader-v1',1);r.onsuccess=()=>res(r.result);r.onerror=()=>rej(r.error);});
    const all=store=>new Promise((res,rej)=>{const r=db.transaction(store).objectStore(store).index('document_id').getAll(document.id);r.onsuccess=()=>res(r.result);r.onerror=()=>rej(r.error);});
    const [pages,sources]=await Promise.all([all('pages'),all('sources')]);db.close();
    return {document,pages:pages.sort((a,b)=>a.page-b.page),sources};
   });
   const record={...entry,pdfPath,pageCount:snapshot.document.page_count,pages:snapshot.pages.map(p=>({page:p.page,text:p.text})),snapshot:{document:snapshot.document,sources:snapshot.sources},extraction:'existing Android mobile_backend.js PDF.js and IndexedDB pipeline',extractionWarnings:snapshot.document.index.warning||''};
   delete record.localPath;
   prior.documents=prior.documents.filter(d=>d.id!==entry.id);prior.documents.push(record);
   prior.extractionNetworkRequests=network;prior.extractionBrowserErrors=errors;
   fs.writeFileSync(outputPath,JSON.stringify(prior,null,2)+'\n');
   console.log(JSON.stringify({id:record.id,pages:record.pages.length,chars:record.pages.reduce((n,p)=>n+p.text.length,0),warnings:record.extractionWarnings}));
  }
  if(network.length||errors.length)throw Error(JSON.stringify({network,errors}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});

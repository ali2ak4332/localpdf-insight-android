// Manual live-model validation. Requires the running application and real model; no generated answers are mocked.
const fs=require('fs');const {chromium}=require('playwright');const path=require('path');const b=path.resolve(process.env.LOCALPDF_VALIDATION_ARTIFACTS||'validation-artifacts');fs.mkdirSync(b,{recursive:true});const inputs=process.env.LOCALPDF_VALIDATION_INPUTS;if(!inputs)throw Error('Set LOCALPDF_VALIDATION_INPUTS to the prepared public corpus directory.');const base=process.env.LOCALPDF_TEST_BASE_URL||'http://127.0.0.1:8765';const delay=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
for(const file of ['tracemonkey.pdf','adib-results-en.pdf','adib-results-ar.pdf','adib2025-ar.pdf','scan-en.pdf','scan-ar.pdf','modified-for-validation.pdf','reordered-paper.pdf']){const f=new FormData();f.append('file',new Blob([fs.readFileSync(inputs+'/'+file)]),file);const r=await fetch(base+'/api/import',{method:'POST',headers:{'X-LocalPDF':'1'},body:f});if(!r.ok)throw Error('Import '+file+' '+r.status)}
let docs;for(let i=0;i<1800;i++){docs=(await(await fetch(base+'/api/documents')).json()).documents;if(docs.every(d=>d.index.status==='ready'))break;await delay(1000)}if(docs.some(d=>d.index.status!=='ready'))throw Error('Indexing did not complete; inspect indexing status before validating answers.');const id=name=>docs.find(x=>x.filename===name)?.id;
let cases=[
['present','adib-results-en.pdf','What was the full-year net profit after tax for 2025?',true],
['multi-page','adib-results-en.pdf','What were the proposed cash dividend and the eligible liquid asset ratio in 2025?',true],
['quote-multi','adib-results-en.pdf','Quote exact source excerpts about the proposed cash dividend and eligible liquid asset ratio.',true],
['absent-overlap','adib-results-en.pdf','What exact net profit after tax is forecast for 2030?',true],
['partial','adib-results-en.pdf','What was net profit after tax in 2025 and what is the exact forecast for 2030?',true],
['absent','tracemonkey.pdf','What notice period applies to contract termination?',true],
['paper','tracemonkey.pdf','How does the compiler handle nested loops?',true],
['arabic','adib-results-ar.pdf','كم بلغ صافي الربح بعد الضريبة في عام 2025؟',true],
['arabic-diacritics','adib-results-ar.pdf','ما صَافِي الرِّبْح بَعْد الضَّرِيبَة في ٢٠٢٥؟',true],
['mixed','adib-results-ar.pdf','كم بلغ net profit بعد الضريبة في 2025؟',true],
['ocr-en','scan-en.pdf','What was the proposed cash dividend per share?',true],
['ocr-ar','scan-ar.pdf','ما هي توزيعات الأرباح المقترحة للسهم؟',true],
['table','adib-results-en.pdf','What were total operating expenses before impairment charge in FY 2025 and FY 2024?',true],
['assisted-synthesis','adib-results-en.pdf','Summarize the proposed cash dividend and eligible liquid asset ratio in 2025.',false],
['selected','adib-results-en.pdf','What does each document say about full-year net profit after tax for 2025?',true,'selected',['adib-results-en.pdf','adib-results-ar.pdf']],
['library','tracemonkey.pdf','What does TraceMonkey do with nested loops?',true,'library'],
['scope-no-leak','tracemonkey.pdf','What was ADIB net profit after tax for 2025?',true,'selected',['tracemonkey.pdf']],
['conflict','adib-results-en.pdf','What full-year net profit after tax for 2025 do these documents state?',true,'selected',['adib-results-en.pdf','modified-for-validation.pdf']],
['ar-annual','adib2025-ar.pdf','ما هي الأرباح في عام 2025؟',true],
['table-assisted','adib-results-en.pdf','What were total operating expenses before impairment charge in FY 2025 and FY 2024?',false],
['visual-table','adib-results-en.pdf','What were total operating expenses before impairment charge in FY 2025 and FY 2024?',false,'current',[],true]
];
const browser=await chromium.launch({headless:true,...(process.env.CHROMIUM_EXECUTABLE?{executablePath:process.env.CHROMIUM_EXECUTABLE}:{}),args:['--disable-dev-shm-usage']});const page=await browser.newPage({viewport:{width:1280,height:900},hasTouch:true});page.setDefaultTimeout(20000);await page.goto(base+'/?test=1');await page.waitForFunction(()=>!!window.__reader);const output=[];
try{for(const [name,file,question,strict,scope='current',selected=[],visual=false]of cases){if(!id(file))continue;const item={name,request:{question,strict,scope,current_id:id(file),document_ids:selected.map(id),visual},links:[]};output.push(item);const save=()=>fs.writeFileSync(b+'/final-results.json',JSON.stringify(output,null,2));console.log('START',name);try{
const current=docs.find(d=>d.id===id(file));await page.evaluate(d=>window.__reader.loadPdf('/api/documents/'+d.id+'/pdf',d.title,d),current);await page.evaluate(ids=>{window.__reader.state.selected=new Set(ids)},selected.map(id));
if(['arabic','mixed','ocr-ar'].includes(name)){await page.setViewportSize({width:412,height:915});if(await page.locator('html').getAttribute('dir')!=='rtl')await page.locator('#language').click();}else await page.setViewportSize({width:1280,height:900});
if(!await page.locator('#inspector').isVisible())await page.locator('#askToggle').click();await page.locator('#scope').selectOption(scope);await page.locator('#strict').setChecked(strict);await page.locator('#visual').setChecked(visual);await page.locator('#question').fill(question);
let t=Date.now();const responsePromise=page.waitForResponse(r=>r.url().endsWith('/api/ask')&&r.request().method()==='POST',{timeout:270000});await page.locator('#submitAsk').click();const response=await responsePromise;item.ms=Date.now()-t;item.status=response.status();item.data=await response.json();save();await page.waitForFunction(()=>!document.getElementById('submitAsk').disabled);console.log('RESULT',name,item.ms,item.data.mode,item.data.claims?.length,item.data.message);
for(const sid of [...new Set((item.data.claims||[]).flatMap(c=>c.source_ids))]){const src=item.data.sources.find(s=>s.id===sid);const authority=await(await fetch(base+'/api/sources/'+sid)).json();if(!await page.locator('#inspector').isVisible())await page.locator('#askToggle').click();await page.locator('#answer .claim .citation[data-source-id="'+sid+'"]').first().click();await page.waitForFunction(s=>window.__reader.state.current?.id===s.document_id&&window.__reader.viewer.currentPageNumber===s.page,src);await page.locator('.evidence-region').waitFor();item.links.push({id:sid,document:src.document_id,page:src.page,mapping_equal:authority.document_id===src.document_id&&authority.page===src.page&&authority.text===src.text,highlight:await page.locator('.evidence-region').count()});save();}
if(['present','arabic','assisted-synthesis'].includes(name))await page.screenshot({path:b+'/live-'+name+'.png'});
}catch(e){item.error=String(e);save();console.log('ERROR',name,String(e));}}
// Deterministic comparison still goes through the application's API and citation resolver.
const comparisons=[];for(const [label,files] of [['near-identical-numeric',['adib-results-en.pdf','modified-for-validation.pdf']],['reordered',['tracemonkey.pdf','reordered-paper.pdf']],['bilingual',['adib-results-en.pdf','adib-results-ar.pdf']]]){const r=await fetch(base+'/api/compare',{method:'POST',headers:{'X-LocalPDF':'1','Content-Type':'application/json'},body:JSON.stringify({scope:'selected',document_ids:files.map(id)})});const data=await r.json();const mapped=(data.rows||[]).every(x=>x.a.document_id===id(files[0])&&x.b.document_id===id(files[1]));comparisons.push({label,status:r.status,mapped,data});console.log('COMPARE',label,data.rows?.length,mapped);fs.writeFileSync(b+'/comparison-results.json',JSON.stringify(comparisons,null,2));}
fs.writeFileSync(b+'/server-config.json',JSON.stringify(await(await fetch(base+'/api/config')).json(),null,2));
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});

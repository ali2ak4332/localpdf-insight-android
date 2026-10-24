// Task 5 on extracted public PDFs. This is a test harness, not a semantic verifier.
// Usage: node tests/apt/five_task_verify.mjs CORPUS_JSON OUTPUT_JSON [MODEL_REPORT_JSON ...] [--models-only]
// --models-only appends real-output checks to a completed result for the same frozen corpus.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import {verifyText,verifySnapshot} from '../../src/localpdf_insight/static/apt_analysis.mjs';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const hash=text=>crypto.createHash('sha256').update(text).digest('hex');
const [corpusArg,outputArg,...extraArgs]=process.argv.slice(2),modelsOnly=extraArgs.includes('--models-only');
const modelReportPaths=extraArgs.filter(a=>a!=='--models-only');
if(!corpusArg||!outputArg)throw Error('Usage: node tests/apt/five_task_verify.mjs CORPUS_JSON OUTPUT_JSON');
const corpusPath=path.resolve(corpusArg),outputPath=path.resolve(outputArg);
const corpusRaw=fs.readFileSync(corpusPath,'utf8'),corpus=JSON.parse(corpusRaw);
const documents=Array.isArray(corpus)?corpus:(corpus.documents||corpus.entries||corpus.corpus);
if(!Array.isArray(documents)||!documents.length)throw Error('Corpus must contain documents with {id,title,pages:[{page,text}]}.');
let result={schemaVersion:1,task:'verify',taskName:'Verify Findings',createdAt:new Date().toISOString(),
 corpus:corpusPath,corpusSha256:hash(corpusRaw),productionModule:'src/localpdf_insight/static/apt_analysis.mjs',
 modelCalls:0,documents:[],sourceIntegrity:{passed:0,failed:0,byKind:{}},
 semanticVerification:{implemented:false,score:null,meaning:'No semantic accuracy score is assigned. The production verifier checks exact text and source integrity only.',
  observedContextChallenges:[],limitations:[
   'An exact text match establishes textual presence, not factual truth, entailment, negation scope, interpretation or completeness.',
   'A missing exact string does not prove a claim false: supported paraphrases also receive unsupported.',
   'Removing a qualification or copying a substring from a negated sentence can retain exact textual presence.',
   'Nearby context is shown but contextComplete remains false; displaying context is not a semantic verification decision.',
   'Corpus snapshots use exact PDF-extracted page text as sources; browser checks separately use the real reader paragraph index.'
  ]},browser:{status:'not-run',checks:[],modelCalls:0},modelReportRechecks:[]};
if(modelsOnly){
 if(!modelReportPaths.length)throw Error('--models-only requires at least one actual model report.');
 const previous=JSON.parse(fs.readFileSync(outputPath,'utf8'));
 if(previous.corpusSha256!==hash(corpusRaw)||previous.browser?.status!=='passed'||previous.sourceIntegrity?.failed!==0)
  throw Error('Refusing to reuse a result without passing checks and the identical frozen corpus fingerprint.');
 result=previous;
}

function snapshotFor(doc){
 if(!Array.isArray(doc.pages)||!doc.pages.length)throw Error(`No extracted pages for ${doc.id}`);
 const pages=doc.pages.map((p,i)=>({page:p.page??p.number??i+1,text:String(p.text??'')}));
 const d={id:String(doc.id),title:doc.title||doc.id,revision:'pdf-text-'+hash(JSON.stringify(pages)),
  page_count:Math.max(...pages.map(p=>p.page))};
 if(pages.some(p=>!Number.isInteger(p.page)||p.page<1))throw Error(`Invalid physical page in ${doc.id}`);
 return {document:d,sources:pages.map(p=>({id:`${d.id}:p${p.page}:${hash(p.text).slice(0,16)}`,
  document_id:d.id,revision:d.revision,page:p.page,ordinal:0,text:p.text})),pages};
}
function sampleAt(text,index=0,length=650){
 const start=Math.max(0,index-170),end=Math.min(text.length,Math.max(start+length,index+170));
 const quote=text.slice(start,end).trim();
 return {quote,start:text.indexOf(quote,start)};
}
function evidenceFor(source,quote,snapshot){
 const start=source.text.indexOf(quote);
 if(start<0)throw Error('Test oracle could not locate exact quote.');
 return {source_id:source.id,document_id:snapshot.document.id,revision:snapshot.document.revision,
  page:source.page,start,end:start+quote.length,text:quote};
}
function record(docResult,kind,expected,actual,details={}){
 const passed=expected===actual,entry={kind,expected,actual,passed,...details};
 docResult.checks.push(entry);result.sourceIntegrity[passed?'passed':'failed']++;
 const count=result.sourceIntegrity.byKind[kind]??={passed:0,failed:0};count[passed?'passed':'failed']++;
 return entry;
}
function textCheck(docResult,kind,quote,snapshot,expected,details={}){
 const checked=verifyText(quote,snapshot);
 const entry=record(docResult,kind,expected,checked.status,{query:quote,...details,note:checked.note,
  matches:checked.matches.map(m=>({document_id:m.document_id,source_id:m.source_id,page:m.page,start:m.start,end:m.end,
   exactSlice:snapshot.sources.find(s=>s.id===m.source_id)?.text.slice(m.start,m.end)===m.text,
   contextComplete:m.contextComplete,contextCount:m.context?.length??0}))});
 if(checked.matches.some(m=>snapshot.sources.find(s=>s.id===m.source_id)?.text.slice(m.start,m.end)!==m.text))
  record(docResult,'matched-offset-integrity',true,false,{query:quote});
 return {entry,checked};
}
function mutationCheck(docResult,kind,snapshot,pattern,replacement){
 for(const s of snapshot.sources){
  const match=pattern.exec(s.text);if(!match)continue;
  const {quote}=sampleAt(s.text,match.index),local=quote.indexOf(match[0]);if(local<0)continue;
  const changed=quote.slice(0,local)+replacement+quote.slice(local+match[0].length);
  if(snapshot.sources.some(source=>source.text.includes(changed)))continue;
  textCheck(docResult,kind,changed,snapshot,'unsupported',{sourcePage:s.page,originalQuote:quote,
   mutation:{from:match[0],to:replacement},semanticJudgment:false});return;
 }
 docResult.skipped.push({kind,reason:'No suitable real extracted token found; no synthetic source was substituted.'});
}
function contextChallenge(docResult,kind,snapshot,source,quote,context,claim=null,expectedMeaning='requires-context'){
 if(quote.trim().length<12||quote.length>6000)return;
 const {checked}=textCheck(docResult,kind,quote,snapshot,'exact-text-match',{
  sourcePage:source.page,sourceContext:context,claim,expectedMeaning,
  semanticJudgment:false,interpretation:'This acceptance passes textual presence only. It is not graded as semantic verification.'});
 result.semanticVerification.observedContextChallenges.push({documentId:snapshot.document.id,kind,page:source.page,
  query:quote,sourceContext:context,claim,expectedMeaning,productionStatus:checked.status,
  semanticDecision:'not-provided',contextComplete:checked.matches[0]?.contextComplete??null});
}
for(const doc of modelsOnly?[]:documents){
 const snapshot=snapshotFor(doc),dr={documentId:doc.id,title:doc.title||doc.id,
  sourceUrl:doc.sourceUrl||doc.url||null,pdfSha256:doc.sha256||null,
  physicalPages:snapshot.document.page_count,extractedCharacters:snapshot.sources.reduce((n,s)=>n+s.text.length,0),checks:[],skipped:[]};
 result.documents.push(dr);
 const nonempty=snapshot.sources.filter(s=>s.text.trim().length>=12);
 if(!nonempty.length){dr.skipped.push({kind:'document',reason:'No text passage of at least 12 characters; scan/OCR is outside this verifier.'});continue;}
 // Each physical text page is exercised, not just a single first-page quote.
 for(const s of nonempty){
  const quote=sampleAt(s.text,s.text.search(/\d|\b(?:not|unless|except|shall|must)\b/i)).quote;
  const {checked}=textCheck(dr,'exact-real-passage',quote,snapshot,'exact-text-match',{sourcePage:s.page});
  const original=evidenceFor(s,quote,snapshot);
  record(dr,'snapshot-real-passage',1,verifySnapshot([original],snapshot).supported.length,{sourcePage:s.page});
  record(dr,'citation-physical-page',true,checked.matches.some(m=>m.page===s.page&&m.source_id===s.id),{sourcePage:s.page});
 }
 mutationCheck(dr,'wrong-amount',snapshot,/\b\d{1,3}(?:,\d{3})+(?:\.\d+)?\b|\b\d+(?:\.\d+)?(?=\s*(?:million\b|billion\b|thousand\b|%))|(?<=[$€£])\d+(?:[,.]\d+)*\b/i,'987654321.987');
 mutationCheck(dr,'wrong-year',snapshot,/\b(?:19|20)\d{2}\b/,'2199');
 mutationCheck(dr,'wrong-unit',snapshot,/(?:\b(?:million|billion|percent|kilograms?|kilometres?|kilometers?|hours?|days?|years?|USD|EUR|kg|km|mg)\b|%|°C)/i,'UNSUPPORTED_UNIT');
 textCheck(dr,'unsupported-claim','This PDF guarantees an unconditional reimbursement of USD 987654321 to every reader.',snapshot,'unsupported',
  {semanticJudgment:false,interpretation:'Absent exact text is rejected. This does not classify factual truth.'});
 textCheck(dr,'short-query','30',snapshot,'too-short');
 const first=nonempty[0],quote=sampleAt(first.text).quote,evidence=evidenceFor(first,quote,snapshot);
 for(const [kind,changed] of [
  ['forged-page',{...evidence,page:snapshot.document.page_count+1}],
  ['forged-source',{...evidence,source_id:evidence.source_id+':forged'}],
  ['forged-document',{...evidence,document_id:evidence.document_id+':other'}],
  ['stale-finding-revision',{...evidence,revision:evidence.revision+':stale'}],
  ['forged-offset',{...evidence,start:evidence.start+1}],
  ['tampered-snapshot-text',{...evidence,text:evidence.text+' invented suffix'}],
 ])record(dr,kind,0,verifySnapshot([changed],snapshot).supported.length,{sourcePage:first.page});
 record(dr,'stale-document-revision',0,verifySnapshot([evidence],{...snapshot,document:{...snapshot.document,revision:'new-revision'}}).supported.length);
 const invalidSource={...snapshot.sources[0],revision:'foreign-source-revision'};
 textCheck(dr,'stale-source-revision',quote,{...snapshot,sources:[invalidSource]},'unsupported');
 // A true negation mutation is text-absent, but still receives no semantic label.
 let negationFound=false,qualifierFound=false;
 for(const s of nonempty){
  const negation=/\b(?:not|never|no(?:\s+longer)?)\s+([^.;\n]{18,180})/i.exec(s.text);
  if(negation&&!negationFound){
   const sentenceStart=Math.max(s.text.lastIndexOf('.',negation.index),s.text.lastIndexOf('\n',negation.index))+1;
   const sentenceEnd=s.text.indexOf('.',negation.index),full=s.text.slice(sentenceStart,sentenceEnd<0?Math.min(s.text.length,negation.index+220):sentenceEnd+1).trim();
   const negationToken=/\b(?:not|never|no(?:\s+longer)?)\s+/i.exec(full);
   if(negationToken){const changed=full.slice(0,negationToken.index)+full.slice(negationToken.index+negationToken[0].length);
    if(changed.length>=12&&!snapshot.sources.some(x=>x.text.includes(changed)))textCheck(dr,'negation-removed-string',changed,snapshot,'unsupported',
     {sourcePage:s.page,sourceContext:full,semanticJudgment:false,interpretation:'Exact text changed; the verifier supplies no contradicted/entailed classification.'});}
   const excerpt=negation[1].trim();
   contextChallenge(dr,'copied-substring-inside-negation',snapshot,s,excerpt,full,
    `Treating the copied substring as an affirmative finding requires resolving the surrounding negation.`,'requires-negation-scope-review');
   negationFound=true;
  }
  const qualifier=/\b(?:unless|except(?:\s+that)?|provided\s+that|subject\s+to|only\s+if)\b/i.exec(s.text);
  if(qualifier&&!qualifierFound){
   const start=Math.max(s.text.lastIndexOf('.',qualifier.index),s.text.lastIndexOf('\n',qualifier.index))+1;
   const prefix=s.text.slice(start,qualifier.index).trim().replace(/[,;:]$/,'').trim();
   const context=s.text.slice(start,Math.min(s.text.length,qualifier.index+220)).trim();
   if(prefix.length>=12){contextChallenge(dr,'omitted-qualifier-substring',snapshot,s,prefix,context,
    'Using this prefix alone as an unconditional finding omits the following restriction.','requires-qualification-review');qualifierFound=true;}
  }
  if(negationFound&&qualifierFound)break;
 }
 if(!negationFound)dr.skipped.push({kind:'negation-context',reason:'No suitable real negated passage found.'});
 if(!qualifierFound)dr.skipped.push({kind:'qualifier-context',reason:'No suitable real qualification found.'});
 for(const curated of doc.verifyCases||[]){
  const s=snapshot.sources.find(s=>s.page===curated.page&&s.text.includes(curated.quote));
  if(!s)throw Error(`Curated verifyCase quote is not on the supplied physical page: ${doc.id}/${curated.page}`);
  contextChallenge(dr,curated.kind||'curated-context',snapshot,s,curated.quote,
   curated.context||sampleAt(s.text,s.text.indexOf(curated.quote)).quote,curated.claim||null,curated.expectedMeaning||'requires-context');
 }
 const reports=[...(doc.modelReports||[]),...(Array.isArray(corpus.modelReports)?corpus.modelReports.filter(r=>(r.documentId||r.document_id||r.id)===doc.id):[])];
 for(const report of reports){
  const checked=verifySnapshot(report.findings||[],report.snapshot||snapshot);
  result.modelReportRechecks.push({documentId:doc.id,model:report.model,task:report.task,
   accepted:checked.supported.length,rejected:checked.unsupported.length,
   scope:'Exact source integrity only; no semantic accuracy or relevance grade.',
   warning:report.snapshot?null:'The report must use the same snapshot IDs, revisions and offsets; a mismatch is an integration/schema failure, not a model-meaning score.'});
 }
}

async function browserChecks(){
 const pdfs=documents.map(doc=>({doc,pdf:doc.pdfPath||doc.pdf_path||doc.localPdfPath||doc.filePath}))
  .filter(x=>x.pdf).map(x=>({...x,pdf:path.resolve(path.dirname(corpusPath),x.pdf)}));
 if(!pdfs.length){result.browser={...result.browser,status:'skipped',reason:'No pdfPath was provided. Corpus checks cannot establish clickable viewer navigation.'};return;}
 const require=createRequire(import.meta.url),{chromium}=require('playwright');
 const fallback=path.resolve(root,'../tooling/chrome-headless-shell-linux64/chrome-headless-shell');
 const executablePath=process.env.CHROMIUM_EXECUTABLE||(fs.existsSync(fallback)?fallback:undefined);
 const browser=await chromium.launch({headless:true,...(executablePath?{executablePath}:{}),args:['--no-sandbox','--disable-dev-shm-usage']});
 const network=[],errors=[],staticRoot=path.join(root,'src/localpdf_insight/static');
 result.browser={status:'running',checks:[],modelCalls:0,transport:'Status-only test bridge. Any generate request fails the check.',network,errors};
 try{
  for(const {doc,pdf} of pdfs){
   const check={documentId:doc.id,pdfPath:pdf,passed:false};result.browser.checks.push(check);
   const context=await browser.newContext({viewport:{width:412,height:915},isMobile:true,hasTouch:true,serviceWorkers:'block'});
   try{
    const expectedRevision=hash(fs.readFileSync(pdf));check.pdfSha256=expectedRevision;
    if(doc.sha256&&doc.sha256!==expectedRevision)throw Error('PDF SHA-256 differs from corpus manifest.');
    await context.setOffline(true);
    await context.route('**/*',async route=>{
     const url=new URL(route.request().url());
     if(['blob:','data:'].includes(url.protocol))return route.continue();
     if(url.origin!=='https://appassets.androidplatform.net'||url.pathname.startsWith('/api/')){network.push(url.href);return route.abort();}
     const f=path.resolve(staticRoot,url.pathname==='/'?'index.html':url.pathname.replace(/^\/static\//,''));
     if(!f.startsWith(staticRoot+path.sep)||!fs.existsSync(f))return route.abort();
     const mime={'.mjs':'text/javascript','.js':'text/javascript','.html':'text/html','.css':'text/css','.svg':'image/svg+xml','.wasm':'application/wasm'};
     await route.fulfill({body:fs.readFileSync(f),contentType:mime[path.extname(f)]||'application/octet-stream'});
    });
    await context.addInitScript(()=>{
     window.nativeCalls=[];
     window.AptOfflineAI={postMessage(raw){const r=JSON.parse(raw);window.nativeCalls.push(r);
      queueMicrotask(()=>window.AptOfflineAI.onmessage?.({data:JSON.stringify({id:r.id,ok:r.action!=='generate',
       data:{present:false},error:r.action==='generate'?'Task 5 must not invoke generation.':undefined})}));
     }};
    });
    const page=await context.newPage();page.setDefaultTimeout(30000);page.on('pageerror',e=>errors.push({documentId:doc.id,message:e.message}));
    await page.goto('https://appassets.androidplatform.net/?platform=android&test=1');
    await page.waitForFunction(()=>!!window.__reader);
    await page.locator('#fileInput').setInputFiles(pdf);
    await page.waitForFunction(sha=>window.__reader.state.current?.revision===sha&&window.__reader.state.documents.find(d=>d.revision===sha)?.index.status==='ready',expectedRevision,{timeout:180000});
    // Read the real PDF.js paragraph index, rather than injecting a test snapshot.
    const source=await page.evaluate(async()=>{
     const request=indexedDB.open('localpdf-android-reader-v1',1);
     const db=await new Promise((resolve,reject)=>{request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error);});
     const req=db.transaction('sources').objectStore('sources').index('document_id').getAll(window.__reader.state.current.id);
     const rows=await new Promise((resolve,reject)=>{req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error);});db.close();
     return rows.filter(s=>s.text.trim().length>=30&&s.text.length<=6000).sort((a,b)=>b.page-a.page||(a.ordinal||0)-(b.ordinal||0))[0];
    });
    if(!source)throw Error('PDF has no usable real indexed paragraph.');
    check.indexedSource={id:source.id,page:source.page,text:source.text,revision:source.revision};
    await page.locator('#readerOptionsToggle').click();await page.locator('#aptAnalyze').click();
    check.taskChoices=await page.locator('#aptTask option').count();
    if(check.taskChoices!==5)throw Error('Reader does not expose five tasks.');
    await page.locator('#aptTask').selectOption('verify');await page.locator('#aptVerifyText').fill(source.text);
    await page.locator('#aptRun').click();await page.waitForFunction(()=>document.querySelector('#aptResults').textContent.includes('exact-text-match'));
    check.exactMatchUI=true;check.disclaimer=await page.locator('#aptResults').textContent();
    const citation=page.locator(`#aptResults .citation[data-page="${source.page}"]`).first();
    if(!await citation.count())throw Error('Exact paragraph has no citation for its physical page.');
    // Move away first; merely already being on the cited page is not navigation evidence.
    const away=source.page===1?Math.min(2,await page.evaluate(()=>window.__reader.state.current.page_count)):1;
    await page.evaluate(n=>{window.__reader.viewer.currentPageNumber=n;},away);
    check.beforeCitationPage=await page.evaluate(()=>window.__reader.viewer.currentPageNumber);
    await citation.click();
    await page.waitForFunction(()=>!document.querySelector('#aptAnalysisDialog').open);
    await page.waitForFunction(s=>window.__reader.viewer.currentPageNumber===s.page&&window.__reader.state.current.id===s.document_id,source);
    check.afterCitationPage=await page.evaluate(()=>window.__reader.viewer.currentPageNumber);
    check.citationChangedPhysicalPage=check.beforeCitationPage!==check.afterCitationPage;
    await page.locator('.evidence-region').first().waitFor();
    check.highlightCount=await page.locator('.evidence-region').count();
    check.highlightedSourceId=await page.locator('.evidence-region').first().getAttribute('data-source-id');
    if(check.highlightCount<1)throw Error('Citation did not display a source evidence region.');
    await page.locator('#readerOptionsToggle').click();await page.locator('#aptAnalyze').click();
    await page.locator('#aptVerifyText').fill('This PDF guarantees unconditional reimbursement of USD 987654321 to every reader.');
    await page.locator('#aptRun').click();await page.waitForFunction(()=>document.querySelector('#aptResults').textContent.includes('unsupported'));
    check.unsupportedUI=true;check.unsupportedCitations=await page.locator('#aptResults .citation').count();
    if(check.unsupportedCitations!==0)throw Error('Unsupported text was published with a citation.');
    check.modelCalls=await page.evaluate(()=>window.nativeCalls.filter(c=>c.action==='generate').length);
    result.browser.modelCalls+=check.modelCalls;
    if(check.modelCalls!==0)throw Error('Task 5 invoked native model generation.');
    check.passed=true;
   }catch(error){check.error=String(error.stack||error);}finally{await context.close();}
  }
  result.browser.status=result.browser.checks.every(c=>c.passed)&&!network.length&&!errors.length?'passed':'failed';
 }finally{await browser.close();}
}
if(!modelsOnly)try{await browserChecks();}catch(error){result.browser.status='failed';result.browser.error=String(error.stack||error);}

// Recheck actual generated quotes against ORIGINAL reader paragraph sources.
// Page-level corpus text is only a separate diagnostic and never upgrades acceptance.
if(modelReportPaths.length){
 result.generatedFindingVerification={checkedAt:new Date().toISOString(),productionFunction:'verifyText',
  snapshotAuthority:'Original corpus document.snapshot.sources from real PDF.js reader indexing; no normalization or page-source substitution.',
  semanticDecision:'not-provided',statementCheckMeaning:'A statement/field exact-text result checks literal presence only. Unsupported paraphrases are not thereby false.',
  files:[],summary:{responseRows:0,malformedRows:0,findings:0,exactQuoteAccepted:0,exactQuoteAcceptedAtRequestedPage:0,
   exactQuoteWrongPage:0,quoteRejected:0,quoteTooShort:0,wholePageExactButIndexedSourceRejected:0,
   wholePageExactButTooShort:0,wholePageExactSourceBoundaryRejections:0,statementTextExact:0,statementTextNotExact:0}};
 const gv=result.generatedFindingVerification;
 for(const inputPath of modelReportPaths){
  const reportPath=path.resolve(inputPath),raw=fs.readFileSync(reportPath,'utf8'),report=JSON.parse(raw);
  if(report.corpusSha256&&report.corpusSha256!==hash(corpusRaw))throw Error(`Actual model report uses a different corpus fingerprint: ${reportPath}`);
  const rows=report.responses||report.rows||report.results;
  if(!Array.isArray(rows))throw Error(`No response rows in actual model report ${reportPath}`);
  const file={path:reportPath,sha256:hash(raw),model:report.model??report.modelName??null,
   modelName:report.model?.filename||report.model?.name||report.modelName||(typeof report.model==='string'?report.model:null),
   sourceRunStatus:report.status??null,plannedResponses:Array.isArray(report.plan)?report.plan.length:null,
   receivedResponses:rows.length,generationRunStatus:report.status,
   reportComplete:['completed','failed'].includes(report.status)&&Array.isArray(report.plan)&&rows.length===report.plan.length,
   rows:[],summary:{findings:0,exactQuoteAccepted:0,exactQuoteAcceptedAtRequestedPage:0,
    exactQuoteWrongPage:0,quoteRejected:0,quoteTooShort:0,wholePageExactButIndexedSourceRejected:0,
    wholePageExactButTooShort:0,wholePageExactSourceBoundaryRejections:0}};
  gv.files.push(file);
  const inc=key=>{gv.summary[key]++;if(key in file.summary)file.summary[key]++;};
  for(const [rowIndex,row] of rows.entries()){
   const documentId=row.documentId||row.document_id||row.id,doc=documents.find(d=>d.id===documentId);
   if(!doc)throw Error(`Unknown model response document ${documentId} in ${reportPath}`);
   const snapshot=doc.snapshot;
   if(!snapshot?.document||!Array.isArray(snapshot.sources))throw Error(`Missing ORIGINAL production snapshot for ${documentId}`);
   if(doc.sha256&&snapshot.document.revision!==doc.sha256)throw Error(`Original reader revision does not match frozen PDF for ${documentId}`);
   if(snapshot.sources.some(s=>!doc.pages.some(p=>p.page===s.page&&p.text.includes(s.text))))
    throw Error(`An original indexed source is absent from its authoritative frozen page: ${documentId}`);
   const checkedRow={rowIndex,documentId,sectionId:row.sectionId??null,task:row.task,finishReason:row.finish_reason??row.finishReason??null,findings:[]};
   file.rows.push(checkedRow);inc('responseRows');
   // cite-v1: verify the code-built findings whose quotes were copied from cited lines.
   let parsed=row.materialized??row.parsedContent??row.parsed_content??row.result;
   if(typeof parsed==='string'){try{parsed=JSON.parse(parsed);}catch{parsed=null;}}
   if(!parsed||!Array.isArray(parsed.findings)){checkedRow.parseStatus='missing-or-malformed-findings';inc('malformedRows');continue;}
   checkedRow.parseStatus='findings-array';
   for(const [findingIndex,f] of parsed.findings.entries()){
    inc('findings');
    const quote=typeof f?.quote==='string'?f.quote:'',checked=verifyText(quote,snapshot);
    const exactAccepted=checked.status==='exact-text-match',pageValid=Number.isInteger(f?.page);
    const pageMatched=exactAccepted&&pageValid&&checked.matches.some(m=>m.page===f.page);
    const pageContainsExactQuote=quote.trim().length>0&&doc.pages.some(p=>p.page===f?.page&&p.text.includes(quote.trim()));
    const indexedSourceContainsExactQuote=quote.trim().length>0&&snapshot.sources.some(s=>s.page===f?.page&&s.text.includes(quote.trim()));
    const sourceBoundaryRejection=pageContainsExactQuote&&!indexedSourceContainsExactQuote&&checked.status==='unsupported'&&quote.length<=6000;
    const entry={findingIndex,rawFinding:f,requestedPage:f?.page??null,
     quoteCheck:{status:checked.status,note:checked.note,accepted:exactAccepted,acceptedAtRequestedPage:pageMatched,
      matches:checked.matches.map(m=>({source_id:m.source_id,document_id:m.document_id,revision:m.revision,page:m.page,start:m.start,end:m.end}))},
     pageDiagnostic:{requestedPageHasExactQuote:pageContainsExactQuote,
      requestedPageSingleIndexedSourceHasExactQuote:indexedSourceContainsExactQuote,
      exactOnWholePageButRejectedByOriginalIndexedSources:pageContainsExactQuote&&!exactAccepted,
      wholePageExactRejectionReason:pageContainsExactQuote&&!exactAccepted?checked.status:null,
      sourceBoundaryRejection,
      acceptanceRule:'Diagnostic only; the production paragraph-source result above remains authoritative.'},
     semanticDecision:'not-provided',statementTextCheck:null,structuredFieldTextChecks:[]};
    checkedRow.findings.push(entry);
    if(exactAccepted){inc('exactQuoteAccepted');inc(pageMatched?'exactQuoteAcceptedAtRequestedPage':'exactQuoteWrongPage');}
    else{inc('quoteRejected');if(checked.status==='too-short')inc('quoteTooShort');}
    if(pageContainsExactQuote&&!exactAccepted)inc('wholePageExactButIndexedSourceRejected');
    if(pageContainsExactQuote&&checked.status==='too-short')inc('wholePageExactButTooShort');
    if(sourceBoundaryRejection)inc('wholePageExactSourceBoundaryRejections');
    const statementField=typeof f?.claim==='string'?'claim':typeof f?.obligation==='string'?'obligation':null;
    if(statementField){const statement=verifyText(f[statementField],snapshot);
     entry.statementTextCheck={field:statementField,text:f[statementField],status:statement.status,note:statement.note,
      literalMatchPages:statement.matches.map(m=>m.page),semanticDecision:'not-provided'};
     inc(statement.status==='exact-text-match'?'statementTextExact':'statementTextNotExact');}
    for(const field of ['metric','entity','value','unit','period','party','deadline','exception']){
     if(typeof f?.[field]!=='string'||!f[field])continue;
     const checkedField=verifyText(f[field],snapshot);
     entry.structuredFieldTextChecks.push({field,text:f[field],status:checkedField.status,
      literalMatchPages:checkedField.matches.map(m=>m.page),semanticDecision:'not-provided'});
    }
   }
  }
  file.byTask={};
  for(const row of file.rows){
   const totals=file.byTask[row.task]??={responseRows:0,malformedRows:0,findings:0,exactQuoteAccepted:0,
    exactQuoteAcceptedAtRequestedPage:0,exactQuoteWrongPage:0,quoteRejected:0,quoteTooShort:0,
    wholePageExactButTooShort:0,wholePageExactSourceBoundaryRejections:0};
   totals.responseRows++;if(row.parseStatus!=='findings-array')totals.malformedRows++;
   for(const finding of row.findings){
    totals.findings++;
    if(finding.quoteCheck.accepted){totals.exactQuoteAccepted++;totals[finding.quoteCheck.acceptedAtRequestedPage?'exactQuoteAcceptedAtRequestedPage':'exactQuoteWrongPage']++;}
    else totals.quoteRejected++;
    if(finding.quoteCheck.status==='too-short')totals.quoteTooShort++;
    if(finding.pageDiagnostic.requestedPageHasExactQuote&&finding.quoteCheck.status==='too-short')totals.wholePageExactButTooShort++;
    if(finding.pageDiagnostic.sourceBoundaryRejection)totals.wholePageExactSourceBoundaryRejections++;
   }
  }
 }
 gv.modelReportsComplete=gv.files.every(f=>f.reportComplete);
}
// These complete affirmative clauses are copied from real "No ..." sentences.
// They expose the semantic limit while using the ORIGINAL paragraph index.
result.semanticVerification.explicitNegationProbes=[];
for(const query of ['copies are to be made or retained','license is granted by either party to the other']){
 const doc=documents.find(d=>d.snapshot?.sources?.some(s=>s.text.includes(query)&&/\bNo\b/.test(s.text)));
 if(!doc)continue;
 const source=doc.snapshot.sources.find(s=>s.text.includes(query)&&/\bNo\b/.test(s.text));
 const checked=verifyText(query,doc.snapshot);
 result.semanticVerification.explicitNegationProbes.push({documentId:doc.id,page:source.page,source_id:source.id,
  query,originalIndexedSource:source.text,expectedReading:'The surrounding No negates this affirmative clause.',
  productionStatus:checked.status,productionNote:checked.note,semanticDecision:'not-provided',
  semanticPassAwarded:false,meaning:'Exact acceptance passes textual presence only, including when the copied clause reverses its negated source context.'});
}
result.summary={sourceIntegrityPassed:result.sourceIntegrity.passed,sourceIntegrityFailed:result.sourceIntegrity.failed,
 contextChallengeCount:result.semanticVerification.observedContextChallenges.length,
 semanticVerification:'not-implemented',semanticScore:null,
 browserPassed:result.browser.checks.filter(c=>c.passed).length,browserFailed:result.browser.checks.filter(c=>!c.passed).length,
 nativeModelGenerateCalls:result.browser.modelCalls,
 interpretation:'Source integrity results and clickable citations are separate from semantic/factual claim verification.',
 ...(result.generatedFindingVerification?{actualModelReportsComplete:result.generatedFindingVerification.modelReportsComplete,
  actualGeneratedFindings:result.generatedFindingVerification.summary}:{} )};
fs.mkdirSync(path.dirname(outputPath),{recursive:true});fs.writeFileSync(outputPath,JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify({output:outputPath,...result.summary,browserStatus:result.browser.status},null,2));
if(result.sourceIntegrity.failed||result.browser.status==='failed')process.exitCode=1;

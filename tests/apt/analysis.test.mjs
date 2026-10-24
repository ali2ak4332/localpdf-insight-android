import test from 'node:test';
import assert from 'node:assert/strict';
import {planSections, verifySelection, verifyText, verifySnapshot, analyze, TASKS} from '../../src/localpdf_insight/static/apt_analysis.mjs';

const doc={id:'doc-a',revision:'revision-a',page_count:3,title:'Contract'};
const sources=[
 {id:'s1',document_id:doc.id,revision:doc.revision,page:1,ordinal:0,text:'Revenue was USD 1.25 million in 2025. Revenue was USD 1.10 million in 2024.',bbox:[0,0,1,1]},
 {id:'s2',document_id:doc.id,revision:doc.revision,page:2,ordinal:0,text:'The buyer shall pay within 30 days, unless an invoice is disputed.',bbox:[0,0,1,1]},
 {id:'s3',document_id:doc.id,revision:doc.revision,page:2,ordinal:1,text:'The contract does not guarantee a minimum volume.',bbox:[0,0,1,1]},
];
const snapshot={document:doc,sources,pages:[{page:1,text:sources[0].text},{page:2,text:sources[1].text+'\n'+sources[2].text},{page:3,text:''}]};
test('exactly five tasks, including independent verification',()=>assert.equal(Object.keys(TASKS).length,5));
test('planner preserves complete source text and identifies scans',()=>{
 const p=planSections(snapshot,{maxChars:200,maxSources:2});
 assert.equal(p.totalPages,3);assert.deepEqual(p.emptyPages,[3]);
 assert.deepEqual(p.sections.flatMap(s=>s.candidates.map(c=>c.source_id)),sources.map(s=>s.id));
 assert.equal(p.sections[0].candidates[0].text,sources[0].text);
});
test('long passage splits with exact offsets and no omitted characters',()=>{
 const s={...sources[0],text:'Financial data 123.45. '.repeat(100)};
 const p=planSections({...snapshot,sources:[s]},{maxChars:160});
 const c=p.sections.flatMap(s=>s.candidates);
 assert.equal(c.map(x=>x.text).join(''),s.text);
 assert.ok(c.every(x=>s.text.slice(x.start,x.end)===x.text));
});
test('verification copies numbers, qualifiers and citation from source',()=>{
 const p=planSections(snapshot);const r=verifySelection('[0,1]',p.sections[0],snapshot);
 assert.equal(r.findings.length,2);assert.equal(r.findings[0].text,sources[0].text);
 assert.equal(r.findings[1].page,2);assert.match(r.findings[1].text,/unless/);
 assert.equal(r.findings[0].support,'exact-extract');
});
test('forged, fractional and duplicate source selections cannot become citations',()=>{
 const sec=planSections(snapshot).sections[0];
 const r=verifySelection('[0,999,-1,1.5,0]',sec,snapshot);
 assert.equal(r.findings.length,1);assert.equal(r.rejected.length,4);
});
test('malformed or excessive model output fails closed',()=>{
 const sec=planSections(snapshot).sections[0];
 for(const raw of ['Here are the numbers: [0]','{"page":99,"text":"Revenue 900"}','[0,','[] trailing','x'.repeat(5000)]){
  assert.equal(verifySelection(raw,sec,snapshot).findings.length,0);
  assert.ok(verifySelection(raw,sec,snapshot).rejected.length);
 }
});
test('stale and tampered candidate text is rejected',()=>{
 const sec=structuredClone(planSections(snapshot).sections[0]);
 const changed={...snapshot,document:{...doc,revision:'new-revision'}};
 assert.equal(verifySelection('[0]',sec,changed).findings.length,0);
 sec.candidates[0].text='Revenue was USD 9 million';
 assert.equal(verifySelection('[0]',sec,snapshot).findings.length,0);
});
test('text verification flags wrong amount, period and paraphrase without approval',()=>{
 for(const text of ['Revenue was USD 9 million in 2025.','Revenue was USD 1.25 million in 2024.','The buyer must pay in thirty days.']){
  assert.equal(verifyText(text,snapshot).status,'unsupported');
 }
 const r=verifyText('Revenue was USD 1.25 million in 2025.',snapshot);
 assert.equal(r.status,'exact-text-match');assert.equal(r.matches[0].page,1);
 assert.equal(verifyText('30',snapshot).status,'too-short');
});
test('snapshot verification rechecks original evidence and refuses stale documents',()=>{
 const r=verifySelection('[0]',planSections(snapshot).sections[0],snapshot);
 assert.equal(verifySnapshot(r.findings,snapshot).supported.length,1);
 assert.equal(verifySnapshot([{...r.findings[0],text:'USD 900'}],snapshot).supported.length,0);
 assert.equal(verifySnapshot([{...r.findings[0],page:3}],snapshot).supported.length,0);
});
test('a wrapped exception remains visible as separately cited nearby context',()=>{
 const a={...sources[1],text:'The buyer shall pay USD 50,000 within 30 days,'};
 const b={...sources[2],text:'unless an invoice is disputed in good faith.'};
 const snap={document:doc,sources:[a,b]},section=planSections(snap).sections[0];
 const f=verifySelection('[0]',section,snap).findings[0];
 assert.equal(f.text,a.text);assert.ok(f.context.some(c=>c.text===b.text&&c.source_id===b.id&&c.page===b.page));
 assert.equal(f.contextComplete,false);
});
test('analysis discloses sampled coverage rather than claiming whole PDF',async()=>{
 const report=await analyze(snapshot,'summarize',async()=> '[0]',{maxChars:90,maxSections:1});
 assert.equal(report.coverage.partial,true);assert.equal(report.coverage.completedSections,1);
 assert.equal(report.coverage.emptyPages,1);assert.ok(report.coverage.omittedSections>0);
 assert.equal(report.kind,'extractive');assert.ok(report.findings.length);
});
test('model failures preserve coverage and never use fallback AI claims',async()=>{
 const report=await analyze(snapshot,'figures',async()=>{throw Error('Model unavailable');});
 assert.equal(report.findings.length,0);assert.equal(report.coverage.failedSections,report.coverage.totalSections);
 assert.equal(report.coverage.partial,true);
});
test('cancellation is explicit and cannot publish an apparently complete report',async()=>{
 const c=new AbortController();c.abort();
 const report=await analyze(snapshot,'risks',async()=>assert.fail('must not call'),{signal:c.signal});
 assert.equal(report.cancelled,true);assert.equal(report.coverage.completedSections,0);assert.equal(report.coverage.partial,true);
});
test('unknown tasks and verification cannot accidentally invoke generation',async()=>{
 await assert.rejects(analyze(snapshot,'verify',async()=>assert.fail('must not call')));
 await assert.rejects(analyze(snapshot,'made-up',async()=>assert.fail('must not call')));
});

/* Synthetic, explicitly labelled diagnostic. NOT the required representative-PDF benchmark. */
import {spawn} from 'node:child_process';import {once} from 'node:events';import {createInterface} from 'node:readline';
import fs from 'node:fs';import {selectionPrompt,verifySelection} from '../../src/localpdf_insight/static/apt_analysis.mjs';
const [binary,model,output]=process.argv.slice(2);if(!binary||!model)throw Error('usage: node model_baseline.mjs apt-select model.gguf [results.json]');
const child=spawn(binary,[model],{stdio:['pipe','pipe','pipe']});let diagnostics='';child.stderr.on('data',b=>{diagnostics=(diagnostics+b.toString()).slice(-3000);});
const lines=createInterface({input:child.stdout}),waiting=[];lines.on('line',line=>{waiting.shift()?.(line);});
let peakRssKb=0;const monitor=setInterval(()=>{try{const m=fs.readFileSync(`/proc/${child.pid}/status`,'utf8').match(/VmRSS:\s+(\d+)/);if(m)peakRssKb=Math.max(peakRssKb,+m[1]);}catch{}},10);
const cases=[];
for(let variant=0;variant<8;variant++){
 const revenue=`Revenue for Atlas Ltd was USD ${125+variant}.25 million in 2025, compared with USD 110 million in 2024.`;
 const obligation=`The buyer shall pay the invoice within ${30+variant} days unless the invoice is disputed in writing.`;
 const insight='The report attributes the decline in output to unplanned maintenance, rather than weaker demand.';
 const summary='This report evaluates a battery cooling system. The experiment found that forced airflow reduced peak battery temperature and recommends field trials before deployment.';
 const target={figures:revenue,risks:obligation,insights:insight,summarize:summary};
 for(const [task,text] of Object.entries(target)){
  const distractors=['The appendix contains a list of abbreviations.','This page is intentionally left blank.','The document was formatted in a standard typeface.'];
  const index=variant%4;distractors.splice(index,0,text);
  cases.push({task,index,texts:distractors});
 }
}
const results=[];
try{
 for(let i=0;i<cases.length;i++){
  const c=cases[i],document={id:'synthetic-'+i,revision:'r1',page_count:4,title:'Synthetic diagnostic'};
  const sources=c.texts.map((text,n)=>({id:'source-'+n,document_id:document.id,revision:document.revision,page:n+1,text}));
  const section={candidates:sources.map(s=>({source_id:s.id,document_id:s.document_id,revision:s.revision,page:s.page,start:0,end:s.text.length,text:s.text}))};
  const prompt=selectionPrompt(c.task,section).replaceAll('\n',' '),start=performance.now();
  const line=new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('Model diagnostic timed out')),30000);waiting.push(raw=>{clearTimeout(timer);resolve(raw);});});
  child.stdin.write(prompt+'\n');const raw=await line,checked=verifySelection(raw,section,{document,sources});
  let parsed;try{parsed=JSON.parse(raw);}catch{parsed=[];}
  const selected=Array.isArray(parsed)?parsed:[];
  results.push({case:i,task:c.task,expected:[c.index],selected,exactSelection:JSON.stringify(selected)===JSON.stringify([c.index]),
   relevantSelected:selected.includes(c.index),released:checked.findings.length,rejected:checked.rejected.length,
   correctTextCopies:checked.findings.every(f=>sources.some(s=>s.id===f.source_id&&s.text===f.text&&s.page===f.page)),
   milliseconds:Math.round(performance.now()-start)});
 }
 child.stdin.end();await once(child,'exit');
 const sorted=results.map(r=>r.milliseconds).sort((a,b)=>a-b);
 const report={scope:'32 synthetic source-selection diagnostics with the actual Gemma model; not representative PDFs or a human-reviewed benchmark',
  modelBytes:fs.statSync(model).size,modelFineTuned:false,host:process.arch,peakProcessRssBytes:peakRssKb?peakRssKb*1024:null,
  exactSelectionRate:results.filter(r=>r.exactSelection).length/results.length,
  relevantPassageRecall:results.filter(r=>r.relevantSelected).length/results.length,
  releasedExtracts:results.reduce((n,r)=>n+r.released,0),rejectedSelections:results.reduce((n,r)=>n+r.rejected,0),
  exactCopyIntegrity:results.every(r=>r.correctTextCopies),medianMs:sorted[Math.floor(sorted.length/2)],p95Ms:sorted[Math.floor(sorted.length*.95)],results};
 if(output)fs.writeFileSync(output,JSON.stringify(report,null,2)+'\n');
 console.log(JSON.stringify({...report,results:undefined},null,2));
}finally{clearInterval(monitor);child.kill();}

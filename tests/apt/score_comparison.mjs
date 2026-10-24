import fs from 'node:fs';
import {verifySelection} from '../../src/localpdf_insight/static/apt_analysis.mjs';
const [fixturePath,...paths]=process.argv.slice(2),cases=JSON.parse(fs.readFileSync(fixturePath));
const rows=[];
for(const path of paths){
 const report=JSON.parse(fs.readFileSync(path));let exact=0,truePositives=0,falsePositives=0,validArrays=0,failed=0,rejected=0,quotes=0,invalidCitations=0;
 const byTask={};
 const scored=report.responses.map(r=>{
  const c=cases[r.case];let parsed;
  try{parsed=JSON.parse(r.text);}catch{}
  const valid=r.ok&&Array.isArray(parsed);if(valid)validArrays++;else failed++;
  const raw=r.ok?r.text:'',verified=verifySelection(raw,c.section,{document:c.document,sources:c.sources});
  const selected=verified.findings.map(f=>Number(f.source_id.slice('source-'.length)));
  const tp=selected.filter(i=>c.expected.includes(i)).length,fp=selected.length-tp;
  const isExact=valid&&JSON.stringify(parsed)===JSON.stringify(c.expected);
  exact+=Number(isExact);truePositives+=tp;falsePositives+=fp;quotes+=verified.findings.length;rejected+=verified.rejected.length;
  for(const f of verified.findings){const s=c.sources.find(s=>s.id===f.source_id);if(!s||s.text!==f.text||s.page!==f.page||s.document_id!==f.document_id||s.revision!==f.revision)invalidCitations++;}
  byTask[c.task]??={cases:0,exact:0,truePositives:0,falsePositives:0};const b=byTask[c.task];b.cases++;b.exact+=Number(isExact);b.truePositives+=tp;b.falsePositives+=fp;
  return {...r,parsed:valid?parsed:null,acceptedIndices:selected,exact:isExact,rejected:verified.rejected.length};
 });
 const times=report.responses.map(r=>r.milliseconds).sort((a,b)=>a-b);
 const summary={model:report.model.filename,exactCases:exact,totalCases:cases.length,screeningScoreOutOf10:10*exact/cases.length,
  exactSelectionRate:exact/cases.length,acceptedPassagePrecision:truePositives+falsePositives?truePositives/(truePositives+falsePositives):null,
  relevantPassageRecall:truePositives/cases.length,validArrayResponses:validArrays,failedResponses:failed,acceptedQuotes:quotes,
  rejectedSelections:rejected,invalidAcceptedCitations:invalidCitations,firstRequestMs:report.responses[0].milliseconds,
  medianRequestMs:times[Math.floor(times.length/2)],p95RequestMs:times[Math.floor(times.length*.95)],
  peakProcessRssBytes:report.peakProcessRssBytes,modelBytes:report.model.bytes,byTask};
 const output=path.replace(/\.json$/,'.scored.json');fs.writeFileSync(output,JSON.stringify({...report,responses:scored,summary},null,2)+'\n');rows.push(summary);
}
console.log(JSON.stringify(rows,null,2));

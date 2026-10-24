// Exact cases and production prompt used in the earlier Gemma diagnostic.
import {selectionPrompt} from '../../src/localpdf_insight/static/apt_analysis.mjs';
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
  const i=cases.length,document={id:'synthetic-'+i,revision:'r1',page_count:4,title:'Synthetic diagnostic'};
  const sources=distractors.map((text,n)=>({id:'source-'+n,document_id:document.id,revision:document.revision,page:n+1,text}));
  const section={candidates:sources.map(s=>({source_id:s.id,document_id:s.document_id,revision:s.revision,page:s.page,start:0,end:s.text.length,text:s.text}))};
  cases.push({case:i,variant,task,expected:[index],document,sources,section,prompt:selectionPrompt(task,section).replaceAll('\n',' ')});
 }
}
console.log(JSON.stringify(cases));

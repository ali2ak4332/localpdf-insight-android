import test from 'node:test';
import assert from 'node:assert/strict';
import {lineUnits,renderLines,spanEvidence} from '../../src/localpdf_insight/static/apt_lines.mjs';
import {numericTokens,figureCandidates,materializeFigure,tableNotes} from '../../src/localpdf_insight/static/apt_figures.mjs';
import {prepare,materialize,MODEL_FIELDS,FIELDS} from './five_task_cite.mjs';

const doc=(...pages)=>({id:'d',title:'T',pages:pages.map((text,i)=>({page:i+1,text}))});
const cands=text=>figureCandidates(lineUnits([{page:1,text}])).candidates;
const raws=text=>numericTokens(text).map(t=>t.raw);

test('line units keep exact page offsets and skip blank lines',()=>{
 const pages=[{page:2,text:'b1\n\nb3'},{page:1,text:'a1\na2'}];
 const u=lineUnits(pages);
 assert.deepEqual(u.map(x=>[x.id,x.page,x.text]),[[1,1,'a1'],[2,1,'a2'],[3,2,'b1'],[4,2,'b3']]);
 for(const x of u)assert.equal(pages.find(p=>p.page===x.page).text.slice(x.start,x.end),x.text);
 assert.equal(renderLines(u),'[PAGE 1]\n[1] a1\n[2] a2\n[PAGE 2]\n[3] b1\n[4] b3');
});
test('cited ranges become one exact page substring, including skipped blank lines',()=>{
 const pages=[{page:1,text:'one\n\ntwo\nthree\nfour\nfive'},{page:2,text:'six'}];
 const u=lineUnits(pages),text={1:pages[0].text,2:pages[1].text};
 const e=spanEvidence(u,text,1,2);
 assert.equal(e.quote,'one\n\ntwo');assert.ok(pages[0].text.includes(e.quote));assert.equal(e.page,1);
 assert.equal(spanEvidence(u,text,2,2).quote,'two');
 assert.match(spanEvidence(u,text,1,5).error,/exceeds 4/);
 assert.match(spanEvidence(u,text,5,6).error,/more than one page/);
 assert.match(spanEvidence(u,text,3,2).error,/reversed/);
 assert.match(spanEvidence(u,text,0,1).error,/does not exist/);
 assert.match(spanEvidence(u,text,1.5,2).error,/integers/);
 assert.match(spanEvidence(u,{1:'changed',2:'six'},1,1).error,/offsets/);
});
test('negative amounts, currencies, ranges and percentages are copied as written',()=>{
 assert.deepEqual(raws('Net earnings $ 26,251 $ (12,767) $ 81,900'),['26,251','(12,767)','81,900']);
 assert.deepEqual(numericTokens('Loss ($1,215) and -$5').map(t=>[t.raw,t.currency,t.negative]),[['($1,215)','$',true],['-$5','$',true]]);
 assert.deepEqual(numericTokens('reduce use by 25%-50% overall').map(t=>[t.raw,t.percent,t.negative]),[['25',true,false],['50',true,false]]);
 assert.deepEqual(numericTokens('Total Return 26.24% -18.13%').map(t=>[t.raw,t.negative]),[['26.24',false],['-18.13',true]]);
 assert.deepEqual(numericTokens('Revenue $13.3B and EUR 62 million').map(t=>[t.raw,t.currency,t.scale]),[['13.3','$','billions'],['62','EUR','millions']]);
 assert.deepEqual(numericTokens('MCL of 4.0 parts per trillion and 1,025 kilograms').map(t=>t.unitWord),['parts per trillion','kilograms']);
});
test('dates, references, clause numbers, names, citations and blanks are not figures',()=>{
 for(const line of ['Launch: July 30, 2027, from Florida.','As of 04/26/2024 and 2024-09-30','Comply by 2029 and monitor by 2027.',
  '7.2 Notice is deemed delivered','4. Term. This Agreement applies','See Section 5 and Note 12 and Table 3','Page 1 of 2',
  'Contact: (202) 564-4355','see 40 CFR Part 141','Woodgrove Core S&P 500 ETF','Date: ____/____/20____','COVID-19 response','Q3 2024 results','FY24 summary'])
  assert.deepEqual(raws(line),[],line);
 assert.deepEqual(raws('It sold 2024 units and spent $2023'),['2024','2023'],'year-like values with units or currency remain figures');
 assert.deepEqual(raws('The agreement remains in force for 3 years'),['3']);
});
test('two-level table headers map each value to its exact column period',()=>{
 const c=cands(['(In millions, except per-share amounts)','Three Months Ended Twelve Months Ended',
  'September 28, 2024 September 30, 2023 September 28, 2024 September 30, 2023','Net sales:',
  'Products $ 61,250 $ 58,410 $ 250,118 $ 247,903','Services 22,035 19,872 84,610 76,402','Total net sales 83,285 78,282 334,728 324,305',
  'Diluted earnings per share $ 1.12 $ 1.27 $ 5.40 $ 5.10'].join('\n'));
 const at=(raw)=>c.find(x=>x.raw===raw);
 assert.equal(at('250,118').period,'Twelve Months Ended September 28, 2024');assert.equal(at('58,410').period,'Three Months Ended September 30, 2023');
 assert.equal(at('61,250').rowLabel,'Net sales: Products');assert.equal(at('83,285').rowLabel,'Total net sales');
 assert.equal(at('22,035').unit,'$ millions','table currency and page scale are inherited');assert.equal(at('22,035').currencySource,'table');
 assert.equal(at('1.12').unit,'$ per share','per-share rows are not scaled');
});
test('share-count rows use the scale note exception',()=>{
 const c=cands(['(In millions, except number of shares, which are reflected in thousands, and per-share amounts)','2024 2023',
  'Revenue $ 100 $ 90','Shares used in computing diluted earnings per share 14,950,112 15,320,664'].join('\n'));
 assert.equal(c.find(x=>x.raw==='14,950,112').unit,'thousands of shares');assert.equal(c.find(x=>x.raw==='100').unit,'$ millions');
});
test('year headers combine with quarter and nine-month span labels; placeholders keep alignment',()=>{
 const c=cands(['(dollars in millions)','Third Quarter First Nine Months','2024 2023 2024 2023',
  'Net earnings $ 26,251 $ (12,767) $ 81,900 $ 74,236','Other — 112 — 300'].join('\n'));
 assert.equal(c.find(x=>x.raw==='(12,767)').period,'Third Quarter 2023');assert.equal(c.find(x=>x.raw==='81,900').period,'First Nine Months 2024');
 assert.equal(c.find(x=>x.raw==='300').period,'First Nine Months 2023','dash placeholders keep later columns aligned');
 assert.equal(c.find(x=>x.raw==='300').unit,'$ millions');
});
test('duration headers in fund tables are column labels, not figures',()=>{
 const c=cands(['Fact Sheet as of 09/30/2024','Average Annual Returns','1y 5y 10y Since Inception','NAV 36.31% 15.95% 13.35% 7.98%',
  'Expense Ratio 0.03%','Number of Holdings 504'].join('\n'));
 assert.deepEqual(c.filter(x=>x.line===4).map(x=>x.period),['1y','5y','10y','Since Inception']);
 assert.equal(c.find(x=>x.raw==='0.03').period,'09/30/2024','currency/percent prose takes a single page-heading date');
 assert.equal(c.find(x=>x.raw==='504').period,'','counts without a stated period stay empty');
 assert.equal(c.filter(x=>x.line===3).length,0);
});
test('prose periods: one date in the line is used; several are ambiguous and left empty',()=>{
 const c=cands(['Report','Revenue for fiscal 2025 was JPY 480 million.','Revenue rose to $5 million in 2025 from $4 million in 2024.'].join('\n'));
 assert.equal(c.find(x=>x.raw==='480').period,'fiscal 2025');assert.equal(c.find(x=>x.raw==='480').unit,'JPY millions');
 assert.equal(c.find(x=>x.raw==='5').period,'');assert.equal(c.find(x=>x.raw==='5').periodSource,'ambiguous');
});
test('forward-looking, preliminary and untested statements are flagged for review',()=>{
 const c=cands(['Guidance: Q4 revenue expected between $13.6B and $14.0B','Unaudited revenue was $3 million','The arm could lift 15 kg, but this has not been tested'].join('\n'));
 assert.ok(c.find(x=>x.raw==='13.6').qualifiers.includes('forward-looking'));
 assert.ok(c.find(x=>x.raw==='3').qualifiers.includes('preliminary'));
 assert.ok(c.find(x=>x.raw==='15').qualifiers.includes('unverified'));
});
test('materialized figures copy value, unit, period and quote; the model value must be on the cited line',()=>{
 const u=lineUnits([{page:1,text:'(In millions)\n2024 2023\nNet income $ 16,742 $ (1,215)\nThe lander weighs 1,025 kilograms.'}]),{candidates}=figureCandidates(u);
 const m=materializeFigure({line:3,value:'-1,215',metric:'ignored for tables',entity:'Co'},u,candidates);
 assert.deepEqual(m.record,{metric:'Net income',entity:'Co',value:'(1,215)',unit:'$ millions',period:'2023',quote:'Net income $ 16,742 $ (1,215)',page:1});
 assert.equal(materializeFigure({line:3,value:'$16,742',metric:'',entity:''},u,candidates).record.value,'16,742');
 const prose=materializeFigure({line:4,value:'1,025',metric:'lander mass',entity:'Lander'},u,candidates);
 assert.equal(prose.record.metric,'lander mass');assert.equal(prose.record.unit,'kilograms');assert.equal(prose.candidate.metricSource,'model');
 assert.match(materializeFigure({line:3,value:'16,743',metric:'',entity:''},u,candidates).error,/does not occur/);
 assert.match(materializeFigure({line:2,value:'2024',metric:'',entity:''},u,candidates).error,/no numeric figure/);
 assert.match(materializeFigure({line:9,value:'1',metric:'',entity:''},u,candidates).error,/does not exist/);
});
test('long lines are narrowed to the sentence containing the figure, still an exact substring',()=>{
 const line='This opening sentence is deliberately long and has no figures at all in it whatsoever. '.repeat(2)
  +'Revenue reached $42 million in the year. Another closing sentence follows here.';
 const u=lineUnits([{page:1,text:line}]),{candidates}=figureCandidates(u);
 const m=materializeFigure({line:1,value:'42',metric:'Revenue',entity:'Co'},u,candidates);
 assert.equal(m.record.quote,'Revenue reached $42 million in the year.');assert.ok(line.includes(m.record.quote));
});
test('table notes list detected columns for the prompt',()=>{
 const {tables}=figureCandidates(lineUnits([{page:1,text:'2024 2023\nRevenue $ 5 $ 4'}]));
 assert.equal(tableNotes(tables),'- Lines 2-2 (page 1): columns 1) 2024; 2) 2023');
});
test('cite protocol: figures with no numeric line abstain without a request',()=>{
 const p=prepare({doc:doc('MUTUAL NONDISCLOSURE AGREEMENT\nThe Recipient shall keep information secret.'),task:'figures'});
 assert.equal(p.skip,true);assert.equal(p.prompt,undefined);
 const r=prepare({doc:doc('The Recipient shall keep information secret.'),task:'risks'});
 assert.equal(r.skip,false);assert.match(r.prompt,/\[1\] The Recipient shall keep information secret\.\nEND PDF LINES/);
 assert.deepEqual(r.schema.properties.findings.items.required,MODEL_FIELDS.risks);
 assert.deepEqual(r.schema.properties.findings.items.properties.from.enum,[1]);
});
test('cite protocol: figure schema offers only lines that contain figures',()=>{
 const p=prepare({doc:doc('Title\nRevenue $5 million\nNo figure here\nCost 7%'),task:'figures'});
 assert.deepEqual(p.schema.properties.findings.items.properties.line.enum,[2,4]);
 assert.doesNotMatch(p.prompt,/TABLE COLUMNS/);
});
test('cite protocol: materialize rejects malformed findings and keeps original output fields',()=>{
 const d=doc('Alpha line.\nBeta line.','Gamma line.');
 const r=materialize({doc:d,task:'summarize',parsed:{findings:[{claim:'A',from:1,to:2},{claim:'B',from:2,to:3},{claim:'C',from:1},{claim:7,from:1,to:1}]}});
 assert.deepEqual(r.findings,[{claim:'A',quote:'Alpha line.\nBeta line.',page:1}]);
 assert.deepEqual(r.rejected.map(x=>x.index),[1,2,3]);
 assert.deepEqual(Object.keys(r.findings[0]),FIELDS.summarize);
 assert.equal(materialize({doc:d,task:'insights',parsed:null}).rejected[0].reason,'Missing or malformed findings array.');
});

test('audit: split financial date headers retain four columns and per-share group units',()=>{
 const cs=cands('Co\n(In millions, except number of shares, which are reflected in thousands, and per-share amounts)\nThree Months Ended Twelve Months Ended\nSeptember 28,\n2024\nSeptember 30,\n2023\nSeptember 28,\n2024\nSeptember 30,\n2023\nNet sales:\nProducts $ 69,958 $ 67,184 $ 294,866 $ 298,085\nGross margin 43,879 40,427 180,683 169,148\nEarnings per share:\nBasic $ 0.97 $ 1.47 $ 6.11 $ 6.16\nShares used in computing earnings per share:\nDiluted 15,242,853 15,672,400 15,408,095 15,812,547');
 assert.equal(cs.find(c=>c.raw==='69,958').period,'Three Months Ended September 28, 2024');
 assert.equal(cs.find(c=>c.raw==='180,683').unit,'$ millions');
 assert.equal(cs.find(c=>c.raw==='6.11').unit,'$ per share');
 assert.equal(cs.find(c=>c.raw==='15,812,547').unit,'thousands of shares');
});
test('audit: equivalent Class per-share earnings are not million-denominated',()=>{
 const cs=cands('(Dollar amounts are in millions, except for per share amounts).\nFirst Quarter\n2024 2023\nNet earnings $ 12,702 $ 35,504\nNet earnings per average equivalent Class B Share $ 5.88 $ 16.25');
 assert.equal(cs.find(c=>c.raw==='5.88').unit,'$ per share');
});
test('audit: table headers cannot attach to later prose or footnotes',()=>{
 const cs=cands('(in millions)\nFirst Quarter\n2024 2023\nEarnings $ 12,702 $ 35,504\nGenerally Accepted Accounting Principles require that we include changes.\nsales of investments of $11.2 billion and $1.7 billion.\n* Includes certain businesses in which Berkshire had between a 20% and 50% ownership interest.');
 for(const c of cs.filter(c=>['11.2','1.7','20','50'].includes(c.raw)))assert.equal(c.kind,'prose');
});
test('audit: annualized split inception headers replace calendar-year columns and inherit percent',()=>{
 const cs=cands('CALENDAR YEAR PERFORMANCE (%)\n2021 2022 2023 2024 2025\nNAV 28.66 -18.13 26.27 24.98 17.85\nANNUALIZED PERFORMANCE (%)\n1y 3y 5y 10y Since\nInception\nNAV 22.29 20.58 13.37 15.47 8.41\nNet Assets of Fund (M) : $888,128.94');
 assert.equal(cs.find(c=>c.raw==='22.29').period,'1y');
 assert.equal(cs.find(c=>c.raw==='8.41').period,'Since Inception');
 assert.equal(cs.find(c=>c.raw==='-18.13').unit,'%');
 assert.equal(cs.find(c=>c.raw==='888,128.94').unit,'$ millions');
});
test('audit: wrapped fund return headers include quarter and year-to-date',()=>{
 const cs=cands('As of September 30, 2026\nPerformance history\nTotal returns 2 for period ended September 30, 2026\nVTI (Inception 2001-05-24) Quarter\nYear to\ndate 1 year 3 years 5 years 10 years\nSince\ninception\nNet asset value (NAV) return3 1.36% 12.58% 15.33% 22.32% 12.56% 14.70% 9.44%\nMarket price return4 1.39 12.59 15.35 22.34 12.56 14.70 9.44');
 assert.equal(cs.find(c=>c.raw==='1.36').period,'Quarter');
 assert.equal(cs.find(c=>c.raw==='12.58').period,'Year to date');
 assert.equal(cs.find(c=>c.raw==='9.44').period,'Since inception');
 assert.equal(cs.find(c=>c.raw==='1.39').unit,'%');
});
test('audit: plural clause references, placeholders, identifiers and bare page markers are not figures',()=>{
 for(const line of ['Date: 201[ ]','The undertakings in clauses 2 and 3 above apply.',
  'Standards. 45 C.F.R. § 164.514(e)(2).','Health Information at 45 C.F.R. Parts 160 and 164, as amended',
  'the terms listed above in paragraphs 1 through 7.','1) [Fill in organization] will provide help',
  '4.1 in any way the Council is entitled to return goods','05/2020 Page 1 of 2','CUSIP : 464287200','2','BOD 26-02 requirement'])assert.deepEqual(raws(line),[],line);
});
test('audit: duplicate numeric cells with different columns are rejected as ambiguous',()=>{
 const u=lineUnits([{page:1,text:'2024 2023\nRevenue $5 $5'}]),{candidates}=figureCandidates(u);
 assert.match(materializeFigure({line:2,value:'5',metric:'Revenue',entity:'Co'},u,candidates).error,/ambiguous/i);
});
test('audit: dotted leaders preserve the first cell and complete per-share row label',()=>{
 const cs=cands('(in millions)\nThird Quarter\n2024 2023\nNet earnings (losses) includes:\nNet earnings (losses) per average equivalent Class B Share ........................$ 12.18 $ (5.88)\nAverage equivalent Class A shares outstanding ................................1,436,706 1,446,925');
 assert.equal(cs.find(c=>c.raw==='1,436,706').period,'Third Quarter 2024');
 assert.match(cs.find(c=>c.raw==='12.18').rowLabel,/Class B Share$/);
});
test('audit: bare benchmark rows inherit the explicit return-table percent unit',()=>{
 const cs=cands('1 year 3 years\nFund 15.33% 22.32%\nIndex 15.35 22.34');
 assert.equal(cs.find(c=>c.raw==='15.35').unit,'%');
});
test('audit: a duration at the start of a wrapped sentence is still a figure',()=>{
 assert.deepEqual(raws('72 hours or signed receipt when sent by certified mail.'),['72']);
});

/* Deterministic figure candidates from numbered line units (apt_lines.mjs).
 No runtime, network, storage or DOM dependency.

 Code, not the model, copies a figure's value, currency, scale, unit, table row label and
 column period from the PDF text. The model only says which line and which number matter
 (and names the metric for prose and the entity). Every copied field is a substring of the
 source page, or empty when the text does not state it. Nothing is calculated or converted.
 Heuristics are English-oriented and table detection is line based: a row maps to column
 headers only when its number of values equals the header's number of periods.
*/

const MONTHS='January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept|Sep|Oct|Nov|Dec';
const DATE_PATTERNS=[
 new RegExp(`\\b(?:${MONTHS})\\.?\\s+\\d{1,2},?\\s+\\d{4}\\b`,'gi'),
 new RegExp(`\\b\\d{1,2}\\s+(?:${MONTHS})\\.?,?\\s+\\d{4}\\b`,'gi'),
 new RegExp(`\\b(?:${MONTHS})\\.?\\s+\\d{4}\\b`,'gi'),
 /\b\d{1,2}\/\d{1,2}\/\d{2,4}\b/g,
 /\b\d{1,2}\/\d{4}\b/g,
 /\b\d{4}-\d{2}-\d{2}\b/g,
 /\b(?:first|second|third|fourth|1st|2nd|3rd|4th)\s+quarter(?:\s+(?:of\s+)?(?:fiscal\s+(?:year\s+)?)?\d{4})?/gi,
 /\bQ[1-4](?:\s*(?:FY\s?)?'?\d{2,4}\b)?/g,
 /\b(?:H[12]|[12]H)\s?'?\d{2,4}\b/g,
 /\b(?:FY|fiscal(?:\s+year)?)\s?'?\d{2,4}\b/gi,
 /\b(?:19|20)\d{2}\b/g,
];
const DURATION=/\b\d+\s*-?\s*(?:years?|yrs?|y|months?|mos?|mo|weeks?|wks?|days?)\b|\bsince inception\b|\bYTD\b/gi;
const SPAN_LABEL=/\b(?:(?:three|six|nine|twelve|fifty-two|fifty-three|\d{1,2})[- ](?:months?|weeks?)|years?|quarters?|half[- ]years?|periods?)\s+ended\b|\b(?:(?:first|second|third|fourth)\s+quarter|(?:first|last)\s+(?:three|six|nine|twelve)\s+months|(?:year|quarter)[- ]to[- ]date|full[- ]year)\b/gi;
const SCALE_PHRASE=/\b(?:in|amounts? in|dollars? in|\$ in|figures? in|stated in|expressed in)\s+(thousands|millions|billions)\b|\((?:in\s+)?\$?\s?000s?\)|\(\$000\)/i;
const CURRENCY_SYMBOL=/(?:US\$|C\$|A\$|HK\$|S\$|NZ\$|\$|€|£|¥|₹)\s?$/;
const CURRENCY_CODE=/\b(?:USD|EUR|GBP|JPY|AED|SAR|QAR|KWD|BHD|OMR|CHF|CAD|AUD|INR|CNY|RMB|HKD|SGD|NZD)\s?$/;
const REFERENCE_WORD=/(?:\b(?:sections?|clauses?|articles?|schedules?|exhibits?|annex(?:es)?|appendix|appendices|items?|notes?|rules?|parts?|chapters?|paragraphs?|para|forms?|figures?|fig\.|tables?|steps?|versions?|v\.|no\.|regulations?|title|levels?|phases?|tiers?|grades?|class|ISO|IEC|SP|page|pages|p\.|pp\.|line|lines|room|suite|unit|box|floor|route|highway|interstate|I-)|§)\s*$/i;
// Names and citations that contain numbers but are not figures: "S&P 500", "40 CFR".
const NAME_BEFORE=/\b(?:S&P|FTSE|Russell|Nasdaq|NASDAQ|DAX|CAC|Nikkei|Fortune|Dow Jones|MSCI|STOXX|Stoxx|Hang Seng|ASX|TSX|Nifty|Sensex|Windows|iPhone|Galaxy|Boeing|Airbus|Mars|Apollo|Artemis|Section|Title)\s*$/;
const CITATION_AFTER=/^\s?(?:CFR|C\.F\.R\.|U\.S\.C\.|USC|Fed\.?\s?Reg\.|FR|Stat\.)(?![A-Za-z])/;
const SCALE_WORD=/^\s?(trillions?|billions?|millions?|thousands?|bn|mn|tn)\b/i;
const SCALE_SUFFIX=/^(?:B|bn|M|mn|m|K|k|T|tn)(?![A-Za-z])/;
const PERCENT_WORD=/^\s?(?:%|percent\b|per cent\b|percentage points?\b|pp\b|basis points?\b|bps\b)/i;
const UNITS=['parts per trillion','parts per billion','parts per million','meters per hour','metres per hour','kilometers per hour','kilometres per hour','miles per hour','gallons per flush',
 'degrees Celsius','degrees Fahrenheit','Earth days','Earth years','Mars years','light-years','light years','nautical miles','metric tons',
 'square feet','square meters','square metres','cubic meters','cubic metres','per share',
 'kilograms','kilogram','grams','gram','pounds','tonnes','tons','kilometers','kilometres','meters','metres','centimeters','millimeters',
 'miles','feet','inches','watts','kilowatts','megawatts','gigawatts','volts','amperes','hours','hour','hrs','days','day','weeks','week',
 'months','month','years','year','minutes','minute','seconds','second','degrees','gallons','gallon','liters','litres','employees','people',
 'stocks','holdings','shares','units','vehicles','installations','customers','users','points','workflows','sites','stores','times',
 'kg','lbs','lb','km','mph','kWh','MWh','GWh','kW','MW','GW','gpf','ppm','ppb','ppt','ng/L','mg/L','µg/L','Mbps','Gbps','GB','TB','MB',
 'psi','kPa','MPa','Hz','kHz','MHz','GHz','dB','°C','°F','cm','mm','nm','µm','ft','mi','W','V','L','m','g','x'];
const UNIT_RE=new RegExp('^\\s?(?:'+UNITS.map(u=>u.replace(/[.*+?^${}()|[\]\\/]/g,'\\$&')).join('|')+')(?![A-Za-z])');
const PLACEHOLDER=/(?<=\s)(?:—|–|-|·|n\/a|N\/A|NM|nm)(?=\s|$)/g;
const FORWARD=/\b(?:expects?|expected|guidance|forecasts?|targets?|estimates?|estimated|plans?|planned|projected|projections?|outlook|goal|aims?|budgeted|will|would|could|may)\b/i;
const PRELIMINARY=/\b(?:unaudited|preliminary|draft|proposed|unapproved|pro forma)\b/i;
const UNVERIFIED=/\bnot (?:yet )?(?:been )?(?:tested|verified|audited|approved|confirmed)\b/i;

function spans(text,patterns){
 const found=[];
 for(const pattern of patterns){pattern.lastIndex=0;let m;while((m=pattern.exec(text))){found.push({start:m.index,end:m.index+m[0].length,text:m[0]});if(!m[0].length)pattern.lastIndex++;}}
 found.sort((a,b)=>a.start-b.start||b.end-a.end);
 const kept=[];for(const s of found)if(!kept.some(k=>s.start<k.end&&s.end>k.start))kept.push(s);
 return kept.sort((a,b)=>a.start-b.start);
}
const overlaps=(a,list)=>list.some(s=>a.start<s.end&&a.end>s.start);
const scalePlural=word=>{const w=word.toLowerCase();
 return w.startsWith('tr')||w==='tn'||w==='t'?'trillions':w.startsWith('b')?'billions':w.startsWith('m')?'millions':'thousands';};

/** Date-like period spans; a bare year directly followed by a unit (e.g. "2024 units") is a value, not a period. */
export function periodSpans(text){
 return spans(text,DATE_PATTERNS).filter(s=>{
  if(!/^(?:19|20)\d{2}$/.test(s.text))return true;
  const after=text.slice(s.end);const before=text.slice(0,s.start);
  return !(UNIT_RE.test(after)&&!/^\s?(?:years?|months?|days?)\b/i.test(after))&&!CURRENCY_SYMBOL.test(before)&&!CURRENCY_CODE.test(before);
 });
}

/** Numeric tokens in one line, excluding dates, references, clause numbers and page numbers. */
export function numericTokens(text){
 if(/^\s*\d+\s*$/.test(text)||/\b(?:CUSIP|NIF|Mail Code)\s*(?::|number)/i.test(text))return [];
 const references=spans(text,[/\b(?:clauses?|paragraphs?|parts?|sections?)\s+\d+(?:\.\d+)*(?:\s*(?:,|and|or|through|to)\s*\d+(?:\.\d+)*)*/gi,/\b\d+\s*C\.F\.R\.[^;]*?(?=,|$)/g,/\b(?:BOD|EPA|JPL)\s+\d+[A-Za-z0-9-]*/g,/\b201\[\s*\]/g]);
 const dates=periodSpans(text),pageRefs=spans(text,[/\bpage\s+\d+(?:\s+of\s+\d+)?\b/gi,/\(?\b\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}\b/g]);
 const tokens=[],core=/\d+(?:,\d{3})*(?:\.\d+)?/g;let m;
 while((m=core.exec(text))){
  let start=m.index,end=start+m[0].length;
  const before=text.slice(0,start),prev=text[start-1]||'',prev2=text[start-2]||'';
  if(/[A-Za-z0-9_]/.test(prev)||(prev==='.'&&!/\.\.$/.test(before)))continue;
  if((prev==='-'||prev==='/')&&/[A-Za-z0-9]/.test(prev2))continue;
  let after=text.slice(end);
  if(/^[_]/.test(after))continue;
  if(/^[.,]\d/.test(after))continue;
  const token={start,end,raw:m[0]};
  if(overlaps(token,dates)||overlaps(token,pageRefs)||overlaps(token,references))continue;
  if(REFERENCE_WORD.test(before)||NAME_BEFORE.test(before)||CITATION_AFTER.test(after))continue;
  // Clause/list numbering at line start: "1.", "7.2 Notice", "4. Term", "(3) The".
  if(/^\s*\(?$/.test(before)&&/^(?:\.\d+)*[.)]?\s+["“(\[A-Za-z]/.test(after)&&!m[0].includes(',')&&!UNIT_RE.test(after))continue;
  // Footnote-like "(1)" with no amount meaning.
  if(prev==='('&&/^\)/.test(after)&&/^\d{1,2}$/.test(m[0])&&/[A-Za-z]\s?\($/.test(before))continue;
  // Sign and parentheses (negative only when the parenthesis closes right after the number).
  let negative=false,currency='',scale='',unitWord='',percent=false,suffix='';
  const sfx=after.match(SCALE_SUFFIX);
  if(after[0]==='%'){percent=true;suffix='%';}
  else if(sfx&&!/^\s/.test(after)){suffix=sfx[0];scale=scalePlural(sfx[0]);}
  else if(/^[A-Za-z]/.test(after)&&!UNIT_RE.test(after))continue;
  let rest=after.slice(suffix.length);
  // Prefixes may appear as "$ (1,215)", "($1,215)", "-$5", "$-5" or "(1,215)". Parentheses mean a
  // negative amount only when they close right after the number; a hyphen only after a space or "(".
  let left=before,valueStart=start,valueEnd=end;
  const takeCurrency=()=>{const c=left.match(CURRENCY_SYMBOL)||left.match(CURRENCY_CODE);
   if(c&&!currency){currency=c[0].trim();left=left.slice(0,left.length-c[0].length);if(valueStart>left.length&&!negative)valueStart=start;}};
  takeCurrency();
  if(/\($/.test(left.trimEnd())&&/^\)/.test(rest)){negative=true;left=left.trimEnd().slice(0,-1);valueStart=left.length;valueEnd=end+1;rest=rest.slice(1);}
  else if(/(?:^|[\s($€£¥])[-−–]$/.test(left)){negative=true;left=left.slice(0,-1);valueStart=left.length;}
  takeCurrency();
  if(!percent){const p=rest.match(PERCENT_WORD);if(p){percent=true;rest=rest.slice(p[0].length);}}
  if(!scale&&!percent){const s=rest.match(SCALE_WORD);if(s){scale=scalePlural(s[1]);rest=rest.slice(s[0].length);}}
  if(!percent){const u=(suffix&&!scale?after:rest).match(UNIT_RE);if(u){unitWord=u[0].trim();}}
  if(!percent&&!scale&&!unitWord&&!currency&&/^(?:19|20)\d{2}$/.test(m[0]))continue;
  const labelEnd=left.length;
  tokens.push({start:valueStart,end:valueEnd,labelEnd,raw:text.slice(valueStart,valueEnd).trim(),number:m[0],negative,currency,scale,unitWord,percent,
   display:text.slice(labelEnd,valueEnd+suffix.length).trim()});
 }
 return tokens;
}

function lineInfo(unit){
 const text=unit.text,tokens=numericTokens(text),dates=periodSpans(text);
 const durations=spans(text,[DURATION]),labels=spans(text,[SPAN_LABEL]);
 const labelWords=labels.reduce((s,l)=>s.replace(l.text,' '),text).split(/\s+/).filter(Boolean).length;
 const placeholders=[];PLACEHOLDER.lastIndex=0;let m;while((m=PLACEHOLDER.exec(text)))placeholders.push({start:m.index,end:m.index+m[0].length,placeholder:true});
 const periodTokens=spans(text,[...DATE_PATTERNS,DURATION]).filter(s=>dates.some(d=>d.start===s.start)||durations.some(d=>d.start===s.start));
 const otherWords=periodTokens.reduce((s,p)=>s.replace(p.text,' '),text).replace(/[\d.,%$()€£¥|—–-]/g,' ').split(/\s+/).filter(Boolean).length;
 // Durations are column labels in a header line ("1 year 3 years"), but figures in prose ("for 3 years").
 const header=periodTokens.length>=2&&!tokens.some(t=>!overlaps(t,durations))&&otherWords===0;
 const valueTokens=header?[]:tokens;
 const spanLine=labels.length>=1&&!tokens.filter(t=>!overlaps(t,labels)).length&&!dates.filter(d=>!overlaps(d,labels)).length&&labelWords<=4;
 // A table row: label text then two or more cells (values or placeholders).
 const cells=[...valueTokens,...placeholders.filter(p=>valueTokens.length&&p.start>valueTokens[0].start-40)].sort((a,b)=>a.start-b.start);
 const scale=text.match(SCALE_PHRASE);
 return {unit,text,tokens:valueTokens,cells,periodTokens,dates,labels,header,spanLine,
  scale:scale?{word:scale[1]?scale[1].toLowerCase():'thousands',text:scale[0],line:unit.id,
   countScale:/shares?[^)]*\bthousands\b/i.test(text)?'thousands':/shares?[^)]*\bmillions\b/i.test(text)?'millions':''}:null};
}

const rowKind=label=>{
 const isCount=/^shares?\b|\b(?:shares used|weighted[- ]average (?:number of )?(?:common )?shares|number of|shares outstanding|headcount|employees|stores|units sold|stocks|holdings)\b/i.test(label);
 return {isCount,isPerShare:!isCount&&/per[- ](?:share|unit|ADS)|per average equivalent .*share|\bEPS\b/i.test(label),
  isRatio:/\bratio\b|\brate\b|\byield\b|percent|%|\bbasis points?\b/i.test(label)};
};

// Reconstruct only header metadata; original numbered evidence lines stay untouched.
// Header fragments must reduce entirely to periods and punctuation, never prose.
function joinedHeaders(infos,indexes){
 for(let k=0;k<indexes.length;k++){
  let best=null;
  for(let end=k;end<Math.min(indexes.length,k+12);end++){
   const text=infos.slice(indexes[k],indexes[end]+1).map(i=>i.text).join(' ')
    .replace(/^[A-Z]{2,5} \(Inception [^)]+\) /,'').replace(/\s+/g,' ');
   const labels=spans(text,[SPAN_LABEL]).filter(p=>!/to[- ]date/i.test(p.text));
   const periods=spans(text,[...DATE_PATTERNS,DURATION,/\bQuarter\b/gi,/\bYear to date\b/gi]);
   // Span labels (e.g. Three Months Ended) describe groups, not columns.
   const cols=periods.filter(p=>!overlaps(p,labels));
   let rest=text;for(const p of [...cols,...labels].sort((a,b)=>b.start-a.start))rest=rest.slice(0,p.start)+' '.repeat(p.end-p.start)+rest.slice(p.end);
   if(cols.length>=2&&/^[\s,;:()|.-]*$/.test(rest))best={end,cols,labels};
   // A value row or unrelated prose cannot be swallowed into a header.
   
  }
  if(best){
   for(let j=k;j<=best.end;j++){infos[indexes[j]].header=true;infos[indexes[j]].tokens=[];}
   const h=infos[indexes[best.end]];h.periodTokens=best.cols;h.headerSpans=best.labels;
   k=best.end;
  }
 }
}
// A table row has a label followed solely by cells, symbols and footnote letters.
function tabularRow(info){
 if(!info.tokens.length)return false;
 let tail=info.text.slice(info.tokens[0].start);
 for(const c of [...info.cells].sort((a,b)=>b.start-a.start)){
  const a=c.start-info.tokens[0].start,b=c.end-info.tokens[0].start;
  if(a>=0)tail=tail.slice(0,a)+' '.repeat(b-a)+tail.slice(b);
 }
 return /^[\s$€£¥%()+−–—.,*:|\-]*(?:[a-c][\s)]*)?$/.test(tail.replace(/\([a-c]\)/g,''));
}

/** All figure candidates for a document's line units, plus detected table column notes. */
export function figureCandidates(units){
 const infos=units.map(lineInfo),byPage=new Map();
 infos.forEach((info,i)=>{if(!byPage.has(info.unit.page))byPage.set(info.unit.page,[]);byPage.get(info.unit.page).push(i);});
 const candidates=[],tables=new Map();
 for(const indexes of byPage.values()){
  const headingDates=[];
  for(const i of indexes.slice(0,3)){if(infos[i].tokens.length)break;for(const d of infos[i].dates)if(!headingDates.includes(d.text))headingDates.push(d.text);}
  joinedHeaders(infos,indexes);
  let group=null,lastHeader=null;
  for(let k=0;k<indexes.length;k++){
   const info=infos[indexes[k]];
   if(info.header){lastHeader=indexes[k];group=null;continue;}
   if(!info.tokens.length){
    group=/:\s*$/.test(info.text)&&info.text.length<=80&&lastHeader!==null?info.text.trim().replace(/:\s*$/,''):(info.spanLine?group:null);
    continue;
   }
   // Column header: nearest header above on this page with the same number of cells.
   let header=null;
   if(info.cells.length>=2&&lastHeader!==null&&tabularRow(info)){const j=indexes.indexOf(lastHeader),h=infos[lastHeader];if(h.periodTokens.length===info.cells.length)header={index:j,info:h};}
   if(!tabularRow(info))lastHeader=null;
   let spanInfo=header?.info.headerSpans?.length?{labels:header.info.headerSpans}:null;
   if(header&&!spanInfo)for(let j=header.index-1;j>=0&&j>=header.index-3;j--){const s=infos[indexes[j]];if(s.spanLine&&info.cells.length%s.labels.length===0){spanInfo=s;break;}if(s.tokens.length)break;}
   let scale=null;for(let j=k;j>=0;j--){const s=infos[indexes[j]].scale;if(s){scale=s;break;}}
   const firstCell=info.cells[0]||info.tokens[0];
   let label=info.text.slice(0,firstCell.labelEnd??firstCell.start).replace(/[\s.:$€£¥|·]+$/,'').trim();
   if(!label&&k>0){const prev=infos[indexes[k-1]];if(!prev.tokens.length&&!prev.header&&prev.text.length<=80)label=prev.text.trim();}
   if(header&&group&&label&&!/^total\b/i.test(label)&&(group+': '+label).length<=80)label=group+': '+label;
   if(header&&/^total\b/i.test(label))group=null;
   const kind=rowKind(label),table=header?units[indexes[header.index]].id:null;
   const tableCurrencies=new Set();
   for(const cell of info.cells){
    if(cell.placeholder)continue;
    const column=header?info.cells.indexOf(cell):null;
    let period='',periodSource='none';
    if(header){
     const col=header.info.periodTokens[column].text;
     const span=spanInfo?spanInfo.labels[Math.floor(column/(info.cells.length/spanInfo.labels.length))].text:'';
     period=(span?span+' ':'')+col;periodSource='column';
    }else{
     const lineDates=[...new Set(info.dates.filter(d=>!overlaps(d,[cell])).map(d=>d.text))];
     if(lineDates.length===1){period=lineDates[0];periodSource='line';}
     else if(lineDates.length>1){periodSource='ambiguous';}
     else if(headingDates.length===1&&(cell.currency||cell.percent)){period=headingDates[0];periodSource='page-heading';}
    }
    if(cell.currency)tableCurrencies.add(cell.currency);
    const c={id:candidates.length+1,line:info.unit.id,page:info.unit.page,raw:cell.raw,display:cell.display,start:cell.start,end:cell.end,
     currency:cell.currency,scale:cell.scale,scaleSource:cell.scale?'token':'',unitWord:cell.unitWord,percent:cell.percent,
     kind:header?'table':'prose',table,column,period:period.slice(0,64),periodSource,rowLabel:label.slice(0,80),
     isCount:kind.isCount,isPerShare:kind.isPerShare,isRatio:kind.isRatio,
     qualifiers:[FORWARD.test(info.text)&&'forward-looking',PRELIMINARY.test(info.text)&&'preliminary',UNVERIFIED.test(info.text)&&'unverified'].filter(Boolean),
     scaleNote:scale?scale.text:''};
    if(/Net Assets.*\(M\)/i.test(label)&&!c.scale){c.scale='millions';c.scaleSource='row-label';}
    if(header&&!c.percent&&!c.currency&&!c.unitWord){
     const nearby=infos.slice(Math.max(indexes[0],indexes[header.index]-2),indexes[header.index]+1).map(x=>x.text).join(' ');
     if(/performance.*\(%\)|returns.*\(%\)/i.test(nearby))c.percent=true;
    }
    if(!c.scale&&!c.percent&&!c.isPerShare&&!c.isRatio&&scale&&(header||c.currency)&&(!c.unitWord||c.isCount)){
     const word=c.isCount?scale.countScale:scale.word;
     if(word){c.scale=scalePlural(word);c.scaleSource='page-note';}
    }
    candidates.push(c);
   }
   if(table){if(!tables.has(table))tables.set(table,{header:table,page:info.unit.page,columns:[],first:info.unit.id,last:info.unit.id,currencies:new Set(),scaleNote:scale?scale.text:''});
    const t=tables.get(table);t.last=info.unit.id;tableCurrencies.forEach(x=>t.currencies.add(x));
    if(!t.columns.length)t.columns=info.cells.map((_,j)=>{const span=spanInfo?spanInfo.labels[Math.floor(j/(info.cells.length/spanInfo.labels.length))].text:'';return (span?span+' ':'')+header.info.periodTokens[j].text;});}
  }
 }
 // Inherit a table's single currency for amount rows printed without a symbol.
 for(const c of candidates){
  const t=c.table&&tables.get(c.table);
  if(t&&!c.percent&&!c.currency&&!c.unitWord&&/return|^NAV$|^Benchmark$|^Market Price$|^Index$/i.test(c.rowLabel)&&candidates.some(x=>x.table===c.table&&x.percent))c.percent=true;
  if(t&&!c.currency&&!c.percent&&!c.isCount&&!c.isRatio&&!c.unitWord&&t.currencies.size===1){c.currency=[...t.currencies][0];c.currencySource='table';}
  c.unit=unitText(c);
 }
 return {candidates,tables:[...tables.values()].map(t=>({...t,currencies:[...t.currencies]}))};
}

function unitText(c){
 if(c.percent)return '%';
 const parts=[];
 if(c.currency)parts.push(c.currency);
 if(c.scale&&c.unitWord&&!c.currency)return (`${c.scale} of ${c.unitWord}`).slice(0,48);
 if(c.scale)parts.push(c.scale);
 if(c.unitWord)parts.push(c.unitWord);
 if(c.isPerShare&&c.currency&&!parts.includes('per share'))parts.push('per share');
 if(c.isCount&&!c.unitWord&&!c.currency&&/shares?/i.test(c.rowLabel))return c.scale?`${c.scale} of shares`:'shares';
 return parts.join(' ').slice(0,48);
}

/** Short prompt notes describing detected table columns; empty when no table was detected. */
export function tableNotes(tables){
 return tables.map(t=>`- Lines ${t.first}-${t.last} (page ${t.page}): columns ${t.columns.map((c,i)=>`${i+1}) ${c}`).join('; ')}${t.scaleNote?`; scale note: ${t.scaleNote}`:''}`).join('\n');
}

const normalizeValue=v=>{const s=String(v).replace(/\s+/g,'').replace(/^[+]/,'').replace(/(?:US\$|C\$|A\$|HK\$|S\$|\$|€|£|¥|₹|USD|EUR|GBP|JPY|AED)/g,'')
 .replace(/%$/,'').replace(/(?:bn|mn|tn|[BMKkmT])$/,'');const neg=/^\(.*\)$/.test(s)||/^[-−–]/.test(s);
 return (neg?'-':'')+s.replace(/[()−–-]/g,'');};

/**
 * Turns the model's {line, value, metric, entity} into a record whose value, unit, period,
 * quote and page are copied from the source. Table rows use the copied row label as metric.
 */
export function materializeFigure(output,units,candidates){
 const line=units[output?.line-1];
 if(!line||line.id!==output.line)return {error:'Cited line does not exist.'};
 const onLine=candidates.filter(c=>c.line===line.id);
 if(!onLine.length)return {error:'Cited line has no numeric figure.'};
 const wanted=normalizeValue(output.value||'');
 const matches=onLine.filter(c=>normalizeValue(c.raw)===wanted);
 if(!matches.length)return {error:'Value does not occur as a figure on the cited line.'};
 if(matches.length>1)return {error:'Value is ambiguous across multiple cells on the cited line.'};
 const c=matches[0];
 let quote=line.text,quoteStart=0;
 if(quote.length>160){
  const before=line.text.lastIndexOf('. ',c.start),after=line.text.indexOf('. ',c.end);
  quoteStart=before<0?0:before+2;quote=line.text.slice(quoteStart,after<0?line.text.length:after+1);
 }
 const metric=c.kind==='table'&&c.rowLabel?c.rowLabel:(typeof output.metric==='string'&&output.metric.trim()?output.metric.trim():c.rowLabel);
 return {record:{metric:metric.slice(0,80),entity:typeof output.entity==='string'?output.entity.trim().slice(0,80):'',value:c.raw,unit:c.unit,period:c.period,quote,page:line.page},
  candidate:{id:c.id,kind:c.kind,column:c.column,periodSource:c.periodSource,scaleSource:c.scaleSource,currencySource:c.currencySource||(c.currency?'token':''),
   qualifiers:c.qualifiers,ambiguousValue:matches.length>1,metricSource:c.kind==='table'&&c.rowLabel?'row-label':'model'},
  quoteOffsetInLine:quoteStart};
}

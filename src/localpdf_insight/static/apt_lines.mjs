/* Numbered line evidence. No runtime, network, storage or DOM dependency.

 The model never copies text. It cites numbered lines; code copies the exact page text.
 Page text in the reader index is its line units joined with "\n" (mobile_backend.js),
 so every line here is a verbatim slice of its page and a cited run of lines is one
 contiguous substring of that page.
*/
export const MAX_SPAN_LINES=4;

/** pages: [{page, text}] -> units [{id, page, index, start, end, text}], ids 1..N in reading order. */
export function lineUnits(pages){
 if(!Array.isArray(pages)||!pages.length)throw Error('No pages.');
 const units=[];
 for(const p of [...pages].sort((a,b)=>a.page-b.page)){
  if(!Number.isInteger(p.page)||p.page<1||typeof p.text!=='string')throw Error('Invalid page.');
  let start=0,index=0;
  for(const line of p.text.split('\n')){
   const end=start+line.length;
   if(line.trim())units.push({id:units.length+1,page:p.page,index,start,end,text:line});
   start=end+1;index++;
  }
 }
 return units;
}

/** Prompt block: [PAGE n] headers and "[id] text" lines. */
export function renderLines(units){
 const out=[];let page=null;
 for(const u of units){if(u.page!==page){page=u.page;out.push(`[PAGE ${page}]`);}out.push(`[${u.id}] ${u.text}`);}
 return out.join('\n');
}

/**
 * Exact evidence for a cited run of lines, or a rejection reason.
 * pageText must be the full page text the units were built from.
 */
export function spanEvidence(units,pageTextByNumber,from,to,maxLines=MAX_SPAN_LINES){
 if(!Number.isInteger(from)||!Number.isInteger(to))return {error:'Line numbers must be integers.'};
 const a=units[from-1],b=units[to-1];
 if(!a||!b||a.id!==from||b.id!==to)return {error:'Cited line does not exist.'};
 if(to<from)return {error:'Line range is reversed.'};
 if(a.page!==b.page)return {error:'Cited lines span more than one page.'};
 if(to-from+1>maxLines)return {error:`Cited range exceeds ${maxLines} lines.`};
 const text=pageTextByNumber[a.page];
 if(typeof text!=='string'||text.slice(a.start,a.end)!==a.text||text.slice(b.start,b.end)!==b.text)
  return {error:'Line offsets do not match the page text.'};
 const quote=text.slice(a.start,b.end);
 return {page:a.page,quote,start:a.start,end:b.end,lines:[from,to]};
}

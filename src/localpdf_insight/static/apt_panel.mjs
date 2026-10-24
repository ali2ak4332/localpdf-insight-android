import {TASKS,analyze,verifyText,verifySnapshot} from './apt_analysis.mjs';

function node(tag,text,attrs={}){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;for(const [k,v] of Object.entries(attrs))e.setAttribute(k,v);return e;}
export function nativeTransport(bridge=globalThis.AptOfflineAI){
 const pending=new Map();let serial=0;
 if(bridge)bridge.onmessage=event=>{
  let reply;try{reply=JSON.parse(event.data);}catch{return;}
  const call=pending.get(reply.id);if(!call)return;pending.delete(reply.id);clearTimeout(call.timer);call.cleanup();
  if(reply.ok)call.resolve(reply.data);else call.reject(Error(reply.error||'Offline model request failed.'));
 };
 return (action,data={},options={})=>new Promise((resolve,reject)=>{
  if(!bridge)return reject(Error('Offline model runtime is unavailable. Open the Apt Reader Android build.'));
  const id='apt-'+Date.now()+'-'+(++serial);
  const abort=()=>{const p=pending.get(id);if(!p)return;pending.delete(id);clearTimeout(p.timer);p.cleanup();
   try{bridge.postMessage(JSON.stringify({id:id+'-cancel',action:'cancel'}));}catch{}
   reject(Error('Analysis cancelled.'));
  };
  const cleanup=()=>options.signal?.removeEventListener('abort',abort);
  const timer=setTimeout(()=>{pending.delete(id);cleanup();try{bridge.postMessage(JSON.stringify({id:id+'-cancel',action:'cancel'}));}catch{}reject(Error('Offline model timed out. Results were withheld.'));},action==='import'?600000:180000);
  pending.set(id,{resolve,reject,timer,cleanup});
  options.signal?.addEventListener('abort',abort,{once:true});
  if(options.signal?.aborted){abort();return;}
  try{bridge.postMessage(JSON.stringify({id,action,...data}));}catch(error){pending.delete(id);clearTimeout(timer);cleanup();reject(error);}
 });
}

export function createAptPanel({backend,state,openSource,closeOptions,transport=nativeTransport()}){
 let running=null,lastReport=null,generation=0;
 const button=node('button','Analyze PDF',{id:'aptAnalyze',type:'button'});
 document.getElementById('readerOptions').append(button);
 const dialog=node('dialog',undefined,{id:'aptAnalysisDialog','aria-labelledby':'aptHeading'});
 const heading=node('h2','Apt Reader · offline',{id:'aptHeading'}),intro=node('p','English PDF analysis · Gemma 3 270M. AI selects exact passages; interpretations and completeness are not verified.');
 const modelStatus=node('p','Checking local model…',{id:'aptModelStatus',role:'status'});
 const setup=node('details'),setupTitle=node('summary','Model setup');setup.append(setupTitle,
  node('p','Import gemma-3-270m-it-qat-Q4_0.gguf (241.4 MB). The file is checked against its pinned SHA-256. No downloads or cloud analysis occur in this app. The model has not been fine-tuned for these tasks.'));
 const modelImport=node('button','Import model',{id:'aptImport',type:'button'});setup.append(modelImport);
 const label=node('label','Function',{for:'aptTask'}),task=node('select',undefined,{id:'aptTask'});
 for(const [value,name] of Object.entries(TASKS))task.append(node('option',name,{value}));
 const verifyInput=node('textarea',undefined,{id:'aptVerifyText',rows:'3',maxlength:'6000','aria-label':'Exact finding to verify',placeholder:'Paste an exact finding, or leave empty to recheck the last result.'});verifyInput.hidden=true;
 const run=node('button','Run',{id:'aptRun',type:'button'}),cancel=node('button','Cancel analysis',{id:'aptCancel',type:'button'}),close=node('button','Close',{id:'aptClose',type:'button'});
 const actions=node('div',undefined,{class:'apt-actions'});actions.append(run,cancel,close);cancel.hidden=true;
 const status=node('p','Open an English PDF and wait for indexing.',{id:'aptCoverage',role:'status'}),results=node('div',undefined,{id:'aptResults','aria-live':'polite'});
 dialog.append(heading,intro,setup,modelStatus,label,task,verifyInput,actions,status,results);document.body.append(dialog);
 task.onchange=()=>{verifyInput.hidden=task.value!=='verify';};
 const fail=error=>{status.textContent=error.message||String(error);};
 const stop=()=>{generation++;running?.abort();running=null;run.disabled=false;task.disabled=false;modelImport.disabled=false;cancel.hidden=true;};
 close.onclick=()=>{stop();dialog.close();};cancel.onclick=()=>running?.abort();
 dialog.addEventListener('cancel',stop);dialog.addEventListener('close',()=>{if(running)stop();});
 async function updateModel(){try{const s=await transport('status');modelStatus.textContent=s.present?'Local Gemma model present. Its checksum is rechecked before first inference.':'Model not installed. Open Model setup to import the pinned file.';}catch(error){modelStatus.textContent=error.message;}}
 button.onclick=()=>{closeOptions();dialog.showModal();updateModel();};
 modelImport.onclick=async()=>{modelImport.disabled=true;try{await transport('import');await updateModel();}catch(e){fail(e);}finally{modelImport.disabled=false;}};
 function citation(f){const b=node('button',`${f.document_name} · p. ${f.page}`,{class:'citation','data-page':String(f.page)});
  b.onclick=async()=>{try{const current=await backend.analysisSnapshot(f.document_id);if(current.document.revision!==f.revision)throw Error('This finding belongs to an older PDF revision.');dialog.close();await openSource(f.source_id);}catch(e){fail(e);}};return b;}
 function show(findings,message){results.replaceChildren();if(message)results.append(node('p',message));
  for(const f of findings){const block=node('div',undefined,{class:'apt-finding'});block.append(node('blockquote',f.text),citation(f));
   if(f.context?.length){const context=node('details');context.append(node('summary','Nearby source context · not exhaustive'));
    for(const c of f.context)context.append(node('blockquote',c.text),citation(c));block.append(context);}
   results.append(block);}
  if(!findings.length)results.append(node('p','No supported finding was released. This does not establish that the PDF contains no relevant information.'));
 }
 run.onclick=async()=>{
  const mine=++generation,documentId=state.current?.id,documentRevision=state.current?.revision;
  const controller=new AbortController();running=controller;run.disabled=true;task.disabled=true;modelImport.disabled=true;cancel.hidden=false;
  const current=()=>mine===generation&&!controller.signal.aborted&&state.current?.id===documentId&&state.current?.revision===documentRevision;
  try{
   if(!documentId)throw Error('Open an indexed PDF first.');
   if(state.pdf&&state.current?.index?.status!=='ready')throw Error('Wait for text indexing to finish, then retry.');
   const snapshot=await backend.analysisSnapshot(documentId);
   if(!current())return;
   if(task.value==='verify'){
    if(verifyInput.value.trim()){
     const checked=verifyText(verifyInput.value,snapshot);show(checked.matches,checked.status+': '+checked.note);
     status.textContent='Independent exact-text verification. No model was called.';
    }else{
     if(!lastReport||lastReport.documentId!==documentId||lastReport.revision!==documentRevision)throw Error('Run an analysis first, or paste an exact finding.');
     const checked=verifySnapshot(lastReport.findings,snapshot);
     show(checked.supported,`${checked.supported.length} exact extracts matched; ${checked.unsupported.length} unsupported findings flagged. This checks text, not interpretation or completeness.`);
     status.textContent='Independent evidence recheck. No model was called.';
    }
   }else{
    results.replaceChildren();status.textContent='Analyzing sections locally…';
    const report=await analyze(snapshot,task.value,async(prompt,options)=>(await transport('generate',{prompt},options)).text,
     {signal:controller.signal,onProgress:p=>{if(mine===generation)status.textContent=`Analyzed ${p.done} of ${p.total} sections…`;}});
    if(mine!==generation||state.current?.id!==documentId||state.current?.revision!==documentRevision)return;
    lastReport=report;const c=report.coverage;
    status.textContent=`${report.cancelled?'Cancelled. ':''}${c.analyzedPages.length}/${c.totalPages} pages analyzed; ${c.completedSections}/${c.totalSections} sections; ${c.emptyPages} pages without indexed text; ${c.failedSections} failed and ${c.omittedSections} omitted sections. ${c.partial?'Partial coverage. ':''}${c.omittedFindings} findings omitted by output limit. Processing coverage only; completeness of findings is not verified.`;
    show(report.findings,report.disclaimer);
    if(report.rejected.length)results.append(node('p',`${report.rejected.length} unsupported selections rejected.`,{class:'warning'}));
    for(const error of [...new Set(report.errors)])results.append(node('p',error,{class:'warning'}));
   }
  }catch(e){if(mine===generation)fail(e);}finally{if(running===controller){running=null;run.disabled=false;task.disabled=false;modelImport.disabled=false;cancel.hidden=true;}}
 };
 return {documentChanged(){stop();lastReport=null;results.replaceChildren();status.textContent='Document changed. Run a new analysis.';}};
}

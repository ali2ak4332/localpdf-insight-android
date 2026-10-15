/* Small UI around the already bundled PDF.js annotation editor and PDF writer. */
const $=id=>document.getElementById(id);
const pause=()=>new Promise(resolve=>setTimeout(resolve,30));

export function createPdfEditor({viewer,eventBus,pdfjs,state,backend,openDocument,refreshDocuments,toast,language}){
 const T=pdfjs.AnnotationEditorType,P=pdfjs.AnnotationEditorParamsType;
 let manager=null,dirty=false,busy=false,generation=0,modeRequest=0,textTarget=null,operation='saving',editingState={};
 const words={en:{edit:'Edit / Sign',save:'Save copy',read:'Read / select',ink:'Sign / Draw',text:'Add text',highlight:'Highlight',
  undo:'Undo',redo:'Redo',remove:'Delete selected',hint:'Draw your signature on the page. Use Read to scroll; select a mark to move or resize it.',
  changed:'Unsaved changes',saving:'Preparing PDF copy…',choosing:'Choose where to save the PDF…',saved:'Edited PDF copy saved.',cancelled:'Save cancelled. Your edits are still here.',
  leave:'This PDF has unsaved edits. Leave without saving?',busy:'Finish the current PDF operation first.',unsupported:'This PDF does not permit annotation editing.',
  addText:'Add text to this page',insert:'Add',cancel:'Cancel',textHint:'Text is added as a sharp image annotation so Arabic and English render consistently. Drag or resize it after adding.',
  adding:'Adding text…',tooLong:'Use at most 500 characters per text annotation.',tooManyLines:'Use at most 20 lines per text annotation.',
  exportUnavailable:'PDF export is unavailable. Open this reader in the updated Android app and use a current Android System WebView.',
  colour:'Ink colour',width:'Pen width',black:'Black',blue:'Blue'},
 ar:{edit:'تعديل / توقيع',save:'حفظ نسخة',read:'قراءة / تحديد',ink:'توقيع / رسم',text:'إضافة نص',highlight:'تظليل',
  undo:'تراجع',redo:'إعادة',remove:'حذف المحدد',hint:'ارسم توقيعك على الصفحة. اختر القراءة للتمرير؛ حدّد العلامة لتحريكها أو تغيير حجمها.',
  changed:'تعديلات غير محفوظة',saving:'جارٍ تجهيز نسخة PDF…',choosing:'اختر مكان حفظ المستند…',saved:'حُفظت نسخة المستند المعدلة.',cancelled:'أُلغي الحفظ. تعديلاتك ما زالت موجودة.',
  leave:'توجد تعديلات غير محفوظة. هل تريد المغادرة دون حفظ؟',busy:'أكمل العملية الحالية على المستند أولاً.',unsupported:'لا يسمح هذا المستند بإضافة التعليقات والتوقيعات.',
  addText:'إضافة نص إلى هذه الصفحة',insert:'إضافة',cancel:'إلغاء',textHint:'يُضاف النص كصورة واضحة لضمان ظهور العربية والإنجليزية بصورة متسقة. يمكنك تحريكه أو تغيير حجمه بعد الإضافة.',
  adding:'جارٍ إضافة النص…',tooLong:'استخدم 500 حرف كحد أقصى لكل نص مضاف.',tooManyLines:'استخدم 20 سطراً كحد أقصى لكل نص مضاف.',
  exportUnavailable:'حفظ ملفات PDF غير متاح. افتح القارئ في تطبيق أندرويد المحدّث واستخدم إصداراً حديثاً من Android System WebView.',
  colour:'لون القلم',width:'سُمك القلم',black:'أسود',blue:'أزرق'}};
 const t=k=>words[language()][k];
 function update(){
  $('editToggle').disabled=!state.pdf||busy;$('saveEdited').disabled=!state.pdf||busy;
  $('editStatus').textContent=busy?t(operation):dirty?t('changed'):'';
  $('editTool').disabled=!manager||busy||viewer.annotationEditorMode===T.DISABLE;
  // Freeze reader/forms/source controls from byte snapshot until the saved copy
  // is reopened. Late form input must never be dropped by the automatic switch.
  document.querySelector('main').inert=busy;
  for(const id of ['insertText','cancelEditText','editTextInput','editorColour','editorWidth'])$(id).disabled=busy;
  $('editorUndo').disabled=busy||!editingState.hasSomethingToUndo;
  $('editorRedo').disabled=busy||!editingState.hasSomethingToRedo;
  $('editorDelete').disabled=busy||!editingState.hasSelectedEditor;
  document.body.classList.toggle('pdf-drawing',viewer.annotationEditorMode===T.INK||viewer.annotationEditorMode===T.HIGHLIGHT);
 }
 function translate(){for(const [id,key] of [['editToggle','edit'],['saveEdited','save'],['editorUndo','undo'],['editorRedo','redo'],['editorDelete','remove'],['editorHint','hint'],['textDialogTitle','addText'],['insertText','insert'],['cancelEditText','cancel'],['textHint','textHint']])$(id).textContent=t(key);
  for(const option of $('editTool').options)option.textContent=t(option.value);
  $('editorColour').setAttribute('aria-label',t('colour'));$('editorWidth').setAttribute('aria-label',t('width'));
  $('editorColour').options[0].textContent=t('black');$('editorColour').options[1].textContent=t('blue');update();}
 function modified(){dirty=true;update();}
 eventBus.on('annotationeditoruimanager',({uiManager})=>{manager=uiManager;});
 eventBus.on('editingstateschanged',({details})=>{
  editingState=details;update();
 });
 eventBus.on('annotationeditormodechanged',()=>update());
 $('viewerContainer').addEventListener('pointerdown',event=>{
  // An in-progress multi-stroke Ink session is not in annotationStorage yet.
  if(!busy&&event.target.closest('.page')&&[T.INK,T.HIGHLIGHT].includes(viewer.annotationEditorMode))modified();
 },true);
 // Standalone PDFViewer does not wire these full-viewer toolbar events itself.
 for(const event of ['switchannotationeditormode','showannotationeditorui'])eventBus.on(event,details=>{
  if(!manager||viewer.annotationEditorMode===T.DISABLE)return;
  const mode=details.mode===T.STAMP?T.INK:details.mode;
  viewer.annotationEditorMode={...details,mode};
 });

 async function setMode(mode){
  if(!manager||viewer.annotationEditorMode===T.DISABLE)throw Error(t('unsupported'));
  if(viewer.annotationEditorMode===mode&&manager.getMode()===mode)return;
  const pdf=state.pdf;
  await new Promise((resolve,reject)=>{
   let timer;const done=({mode:current})=>{if(current!==mode)return;clearTimeout(timer);eventBus.off('annotationeditormodechanged',done);resolve();};
   timer=setTimeout(()=>{eventBus.off('annotationeditormodechanged',done);reject(Error('The editor could not switch tools. Try reopening this PDF.'));},15000);
   eventBus.on('annotationeditormodechanged',done);
   try{viewer.annotationEditorMode={mode};}catch(e){clearTimeout(timer);eventBus.off('annotationeditormodechanged',done);reject(e);}
  });
  if(state.pdf!==pdf)throw Error('The open document changed. Try again.');
 }
 function parameters(){eventBus.dispatch('switchannotationeditorparams',{source:viewer,type:P.INK_COLOR,value:$('editorColour').value});
  eventBus.dispatch('switchannotationeditorparams',{source:viewer,type:P.INK_THICKNESS,value:Number($('editorWidth').value)});}
 async function chooseTool(tool){
  if(!state.pdf||busy)return;const request=++modeRequest;
  if(tool==='text'){await setMode(T.NONE);if(request!==modeRequest)return;
   textTarget={pdf:state.pdf,manager,pageNumber:viewer.currentPageNumber,generation};
   $('editTextInput').value='';$('textDialog').showModal();$('editTextInput').focus();return;}
  await setMode(({read:T.NONE,ink:T.INK,highlight:T.HIGHLIGHT})[tool]);if(request!==modeRequest)return;
  $('editTool').value=tool;if(tool==='ink')parameters();update();
 }
 async function action(name){if(!manager||busy)return;
  if(name!=='delete')await setMode(T.NONE);else manager.commitOrRemove();
  eventBus.dispatch('editingaction',{source:viewer,name});modified();$('editTool').value='read';update();
 }

 async function addText(){
  if(busy)return;
  const text=$('editTextInput').value.trim();if(!text)return;
  if(text.length>500)throw Error(t('tooLong'));
  const target=textTarget;if(!target||state.pdf!==target.pdf||manager!==target.manager||generation!==target.generation)throw Error('The open document changed. Choose Add text again.');
  const {pageNumber}=target;
  // FreeText appearance streams in this PDF.js build use WinAnsi fonts. A PNG
  // stamp preserves all rendered Unicode glyphs in independent PDF readers.
  const canvas=document.createElement('canvas'),scale=4,fontSize=20,padding=6,maxWidth=388;
  const context=canvas.getContext('2d');context.font=`${fontSize}px Arial, sans-serif`;
  const lines=[],segmenter=new Intl.Segmenter(undefined,{granularity:'grapheme'});
  for(const paragraph of text.split('\n')){let line='';for(const word of paragraph.split(/\s+/)){
    const next=line?line+' '+word:word;
    if(context.measureText(next).width<=maxWidth){line=next;continue;}
    if(line){lines.push(line);line='';}
    for(const {segment} of segmenter.segment(word)){
     if(line&&context.measureText(line+segment).width>maxWidth){lines.push(line);line='';}line+=segment;
    }
   }lines.push(line);}
  if(lines.length>20)throw Error(t('tooManyLines'));
  const width=Math.max(80,...lines.map(line=>context.measureText(line).width))+padding*2;
  canvas.width=Math.ceil(width*scale);canvas.height=Math.ceil((lines.length*fontSize*1.4+padding*2)*scale);
  context.scale(scale,scale);context.font=`${fontSize}px Arial, sans-serif`;context.fillStyle=$('editorColour').value;context.textBaseline='top';
  const rtl=/^[^a-zA-Z]*[\u0600-\u06ff]/.test(text);context.direction=rtl?'rtl':'ltr';context.textAlign=rtl?'right':'left';
  lines.forEach((line,n)=>context.fillText(line,rtl?width-padding:padding,padding+n*fontSize*1.4));
  busy=true;operation='adding';update();
  try{
  await setMode(T.INK);
  const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/png'));if(!blob)throw Error('Could not prepare text.');
  if(state.pdf!==target.pdf||manager!==target.manager||generation!==target.generation)throw Error('The open document changed. Try again.');
  const existing=new Set([...target.manager.getEditors(pageNumber-1)].map(ed=>ed.id));
  const layer=target.manager.getLayer(pageNumber-1);if(!layer)throw Error('Wait for this page to finish rendering.');
  await layer.pasteEditor({mode:T.STAMP},{bitmapFile:new File([blob],'added-text.png',{type:'image/png'})});
  let added;for(let n=0;n<200;n++){added=[...target.manager.getEditors(pageNumber-1)].find(ed=>!existing.has(ed.id)&&!ed.isEmpty());if(added?.div?.querySelector('canvas'))break;await pause();}
  if(state.pdf!==target.pdf||!added?.div?.querySelector('canvas'))throw Error('Could not add text to this page.');
  added.altTextData={altText:text,decorative:false};
  await setMode(T.NONE);await setMode(T.INK);manager.setSelected(added);
  $('editTool').value='ink';modified();$('textDialog').close();textTarget=null;
  }finally{busy=false;update();}
 }

 async function nativeSave(bytes,filename){
  const channel=window.LocalPDFExport;
  if(!channel)throw Error(t('exportUnavailable'));
  const id=crypto.randomUUID().replaceAll('-','');let waiting=null;
  channel.onmessage=event=>{let result;try{result=JSON.parse(event.data);}catch{return;}if(result.id!==id||!waiting)return;
   if(result.status==='choosing'){$('editStatus').textContent=t('choosing');return;}
   const promise=waiting;waiting=null;clearTimeout(promise.timer);
   if(result.status==='error')promise.reject(Error(result.message||'The PDF could not be saved.'));else promise.resolve(result);};
  const send=(message,timeout=30000)=>new Promise((resolve,reject)=>{
   const timer=timeout?setTimeout(()=>{waiting=null;reject(Error('The save operation stopped responding. Your edits are still here.'));},timeout):null;
   waiting={resolve,reject,timer};try{channel.postMessage(JSON.stringify({...message,id}));}catch(error){clearTimeout(timer);waiting=null;reject(error);}
  });
  try{
   const begin=await send({action:'begin',filename,size:bytes.length});if(begin.status!=='ready')throw Error('The PDF could not be prepared for saving.');
   const chunkSize=196608;for(let offset=0,index=0;offset<bytes.length;offset+=chunkSize,index++){
    const result=await send({action:'chunk',index,data:bytes.subarray(offset,Math.min(bytes.length,offset+chunkSize)).toBase64()});
    if(result.status!=='chunk'||result.index!==index)throw Error('The PDF transfer was interrupted. Retry saving.');
   }
   const result=await send({action:'finish'},0);
   if(!['saved','cancelled'].includes(result.status))throw Error('The PDF could not be saved.');return result.status;
  }catch(error){channel.postMessage(JSON.stringify({action:'cancel',id}));throw error;}
  finally{channel.onmessage=null;}
 }
 async function saveCopy(){
  if(!state.pdf||!state.current)throw Error('Open an imported PDF first.');if(busy)throw Error(t('busy'));
  const pdf=state.pdf,original=state.current,revision=generation;
  document.activeElement?.blur();busy=true;operation='saving';update();
  try{
   if(manager&&viewer.annotationEditorMode!==T.DISABLE){await setMode(T.NONE);manager.commitOrRemove();}
   const bytes=pdf.annotationStorage.size?await pdf.saveDocument():await pdf.getData();
   if(state.pdf!==pdf||revision!==generation)throw Error('The open PDF changed. Retry saving.');
   const filename=original.filename.replace(/\.pdf$/i,'')+'-edited.pdf';
   const status=await nativeSave(bytes,filename);
   if(status==='cancelled'){toast(t('cancelled'));return {status};}
   const form=new FormData();form.append('file',new File([bytes],filename,{type:'application/pdf'}));
   if(state.openedPassword)form.append('password',state.openedPassword);
   let result;try{result=await backend.request('/api/import',{method:'POST',body:form});}
   catch(error){dirty=false;await openDocument(original,{editorReplacement:true});toast('Saved to Files, but could not keep an app copy: '+error.message);return {status,librarySaved:false};}
   dirty=false;await refreshDocuments();await openDocument(result.document,{editorReplacement:true});
   toast(t('saved'));return {status,document:result.document};
  }finally{busy=false;update();}
 }
 async function documentLoaded(pdf){
  generation++;dirty=false;editingState={};textTarget=null;if($('textDialog').open)$('textDialog').close();$('editBar').hidden=true;$('editTool').value='read';
  $('editorUndo').disabled=$('editorRedo').disabled=$('editorDelete').disabled=true;
  const previous=pdf.annotationStorage.onSetModified;pdf.annotationStorage.onSetModified=()=>{previous?.();modified();};update();
 }
 function beforeLoad(editorReplacement=false){if(busy&&!editorReplacement){toast(t('busy'));return false;}return editorReplacement||!dirty||confirm(t('leave'));}
 $('editToggle').hidden=$('saveEdited').hidden=false;
 $('editToggle').onclick=()=>{const closing=!$('editBar').hidden;$('editBar').hidden=closing;if(closing)chooseTool('read').catch(e=>toast(e.message));};
 $('editTool').onchange=()=>chooseTool($('editTool').value).catch(e=>toast(e.message));
 $('editorUndo').onclick=()=>action('undo').catch(e=>toast(e.message));$('editorRedo').onclick=()=>action('redo').catch(e=>toast(e.message));$('editorDelete').onclick=()=>action('delete').catch(e=>toast(e.message));
 for(const id of ['editorUndo','editorRedo','editorDelete'])$(id).onpointerdown=e=>{e.preventDefault();e.stopPropagation();};
 $('editorColour').onchange=parameters;$('editorWidth').oninput=parameters;
 $('textForm').onsubmit=event=>{event.preventDefault();addText().catch(e=>toast(e.message));};$('cancelEditText').onclick=()=>{$('textDialog').close();$('editTool').value='read';};
 $('textDialog').addEventListener('cancel',event=>{if(busy)event.preventDefault();else $('editTool').value='read';});
 $('saveEdited').onclick=()=>saveCopy().catch(e=>toast(e.message));
 translate();
 return {translate,documentLoaded,beforeLoad,chooseTool,saveCopy,get dirty(){return dirty;},get busy(){return busy;}};
}

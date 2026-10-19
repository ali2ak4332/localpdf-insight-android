// Compact Android controls reuse the existing buttons, handlers and native selects.
// Most glyphs are already bundled PDF.js icons (Apache-2.0; see vendor/pdfjs/LICENSE).
const $=id=>document.getElementById(id);
const images='/static/vendor/pdfjs/web/images/';
const icons={
 libraryToggle:['toolbarButton-openFile.svg','Document library','مكتبة المستندات'],
 outlineToggle:['toolbarButton-viewOutline.svg','Contents and thumbnails','المحتويات والصور المصغرة'],
 previousPage:['toolbarButton-pageUp.svg','Previous page','الصفحة السابقة'],
 nextPage:['toolbarButton-pageDown.svg','Next page','الصفحة التالية'],
 findToggle:['toolbarButton-search.svg','Search document','البحث في المستند'],
 studioToggle:['comment-editButton.svg','Notes','الملاحظات'],
 editToggle:['toolbarButton-editorSignature.svg','Edit / Sign','تعديل / توقيع'],
 saveEdited:['toolbarButton-download.svg','Save copy','حفظ نسخة'],
 zoomOut:['toolbarButton-zoomOut.svg','Zoom out','تصغير'],
 zoomIn:['toolbarButton-zoomIn.svg','Zoom in','تكبير'],
 rotate:['secondaryToolbarButton-rotateCw.svg','Rotate pages','تدوير الصفحات'],
 editorDelete:['editor-toolbar-delete.svg','Delete selected','حذف المحدد'],
 findPrevious:['findbarButton-previous.svg','Previous search result','نتيجة البحث السابقة'],
 findNext:['findbarButton-next.svg','Next search result','نتيجة البحث التالية'],
 indexedSearch:['toolbarButton-currentOutlineItem.svg','Passage results','نتائج المقتطفات'],
 showOutline:['toolbarButton-viewOutline.svg','Contents','المحتويات'],
 showThumbs:['toolbarButton-viewThumbnail.svg','Pages','الصفحات'],
 closeInspector:['comment-closeButton.svg','Close notes and passages','إغلاق الملاحظات والمقتطفات'],
};
const drawings={
 sharePdf:'<path d="M12 15V3m-4 4 4-4 4 4M5 12v8a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-8"/>',
 printPdf:'<path d="M7 9V3h10v6M7 17H5a2 2 0 0 1-2-2v-4a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2h-2"/><path d="M7 14h10v7H7z"/>',
 language:'<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c5 5 5 13 0 18-5-5-5-13 0-18Z"/>',
 readerOptionsToggle:'<path d="M4 6h16M4 12h16M4 18h16"/><circle cx="8" cy="6" r="2"/><circle cx="16" cy="12" r="2"/><circle cx="10" cy="18" r="2"/>',
 editorUndo:'<path d="m9 5-5 5 5 5M4 10h10a6 6 0 0 1 0 12"/>',
 editorRedo:'<path d="m15 5 5 5-5 5M20 10h-10a6 6 0 0 0 0 12"/>',
};
function glyph(file,drawing){
 const icon=document.createElement('span');icon.className='toolbar-glyph';icon.setAttribute('aria-hidden','true');
 if(file)icon.style.setProperty('--toolbar-image',`url("${images+file}")`);
 else {icon.classList.add('drawn');icon.innerHTML=`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${drawing}</svg>`;}
 return icon;
}
function decorate(button,file,label,drawing){
 button.classList.add('toolbar-icon');button.removeAttribute('data-i18n');
 button.title=label;button.setAttribute('aria-label',label);button.replaceChildren(glyph(file,drawing));
}
export function createMobileToolbar({language}){
 const heading=document.querySelector('.document-heading'),reader=document.querySelector('.reader'),bar=document.querySelector('.reader-toolbar');
 heading.classList.add('mobile-document-heading');heading.setAttribute('role','toolbar');
 heading.prepend($('libraryToggle'));
 const optionsButton=document.createElement('button');optionsButton.id='readerOptionsToggle';optionsButton.type='button';
 optionsButton.setAttribute('aria-controls','readerOptions');optionsButton.setAttribute('aria-expanded','false');
 heading.append(optionsButton,$('sharePdf'),$('studioToggle'),$('language'));
 // The branding strip is removed. Its working actions now live beside the filename.
 document.querySelector('.app-header').hidden=true;
 const status=$('indexStatus');status.classList.add('sr-only');status.setAttribute('role','status');
 const counter=document.createElement('div');counter.className='mobile-page-counter';counter.dir='ltr';
 $('previousPage').after(counter);counter.append($('pageNumber'),$('pageTotal'));
 const options=document.createElement('div');options.id='readerOptions';options.className='reader-options';options.hidden=true;
 options.setAttribute('role','group');reader.append(options);
 const zoom=document.createElement('div');zoom.className='mobile-zoom-options';zoom.append($('zoomOut'),$('zoom'),$('zoomIn'));
 const layout=document.createElement('div');layout.className='mobile-layout-options';
 const layoutLabel=document.createElement('label');layoutLabel.htmlFor='viewMode';layoutLabel.id='mobileLayoutLabel';
 layout.append(layoutLabel,$('viewMode'),$('rotate'));options.append(zoom,layout);
 bar.querySelector('.separator')?.remove();
 function closeOptions(restoreFocus=false){if(options.hidden)return false;options.hidden=true;optionsButton.setAttribute('aria-expanded','false');if(restoreFocus)optionsButton.focus();return true;}
 optionsButton.onclick=()=>{if(closeOptions())return;options.hidden=false;optionsButton.setAttribute('aria-expanded','true');$('zoom').focus();};
 document.addEventListener('pointerdown',e=>{if(!options.contains(e.target)&&!optionsButton.contains(e.target))closeOptions();});
 document.addEventListener('keydown',e=>{if(e.key==='Escape'&&closeOptions(true))e.preventDefault();});
 // Native selectors keep their standard Android menus and keyboard behavior.
 for(const [id,file] of [['editTool','toolbarButton-editorInk.svg'],['editorColour','toolbarButton-editorHighlight.svg']]){
  const select=$(id),shell=document.createElement('span');shell.className='mobile-select-icon';select.before(shell);shell.append(glyph(file),select);
 }
 function updateEditorIcons(){
  const tool=$('editTool'),colour=$('editorColour');
  const file={read:'secondaryToolbarButton-handTool.svg',ink:'toolbarButton-editorInk.svg',text:'toolbarButton-editorFreeText.svg',highlight:'toolbarButton-editorHighlight.svg'}[tool.value];
  tool.parentElement.querySelector('.toolbar-glyph').style.setProperty('--toolbar-image',`url("${images+file}")`);
  tool.parentElement.title=tool.title+': '+tool.selectedOptions[0].textContent;
  colour.parentElement.querySelector('.toolbar-glyph').style.color=colour.value;
  colour.parentElement.title=colour.getAttribute('aria-label')+': '+colour.selectedOptions[0].textContent;
 }
 document.addEventListener('localpdfeditorupdate',updateEditorIcons);
 $('editTool').addEventListener('change',updateEditorIcons);$('editorColour').addEventListener('change',updateEditorIcons);
 const editBar=$('editBar');
 new MutationObserver(()=>$('editToggle').setAttribute('aria-expanded',String(!editBar.hidden))).observe(editBar,{attributes:true,attributeFilter:['hidden']});
 $('editToggle').setAttribute('aria-controls','editBar');$('editToggle').setAttribute('aria-expanded','false');
 function translate(){
  const ar=language()==='ar';
  for(const [id,[file,en,arabic]] of Object.entries(icons))decorate($(id),file,ar?arabic:en);
  for(const [id,en,arabic] of [['sharePdf','Share PDF','مشاركة PDF'],['printPdf','Print PDF','طباعة PDF'],['language','Switch to Arabic','التبديل إلى الإنجليزية'],['readerOptionsToggle','View options','خيارات العرض'],['editorUndo','Undo','تراجع'],['editorRedo','Redo','إعادة']])decorate($(id),null,ar?arabic:en,drawings[id]);
  $('language').lang=ar?'ar':'en';
  heading.setAttribute('aria-label',ar?'المستند والإجراءات':'Document and actions');
  bar.setAttribute('aria-label',ar?'أدوات القراءة':'Reader controls');
  options.setAttribute('aria-label',ar?'خيارات العرض':'View options');
  $('mobileLayoutLabel').textContent=ar?'تخطيط الصفحات':'Page layout';
  for(const [id,en,arabic] of [['pageNumber','Page number','رقم الصفحة'],['zoom','Zoom','التكبير'],['viewMode','Page layout','تخطيط الصفحات'],['editTool','Edit tool','أداة التعديل']]){$(id).setAttribute('aria-label',ar?arabic:en);$(id).title=ar?arabic:en;}
  updateEditorIcons();
 }
 translate();return {translate,closeOptions};
}

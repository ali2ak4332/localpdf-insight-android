// Small local reading conveniences. PDF bookmarks never modify the PDF bytes.
const $=id=>document.getElementById(id);
export function createMobileReading({state,viewer,eventBus,gotoPage,find,toast,language}){
 const words={en:{whole:'Whole words',keep:'Keep screen on while reading',unavailable:'Keep screen on needs the updated Android app.',bookmarks:'Bookmarks',add:'Bookmark this page',remove:'Remove bookmark',page:'Page',empty:'No bookmarks in this PDF yet.',local:'Bookmarks stay on this phone and are not added to saved PDF copies.',failed:'Could not save this bookmark. Phone storage may be full.'},ar:{whole:'كلمات كاملة',keep:'إبقاء الشاشة مضاءة أثناء القراءة',unavailable:'يتطلب إبقاء الشاشة مضاءة تطبيق أندرويد المحدّث.',bookmarks:'العلامات المرجعية',add:'حفظ علامة لهذه الصفحة',remove:'حذف العلامة المرجعية',page:'الصفحة',empty:'لا توجد علامات مرجعية في هذا المستند بعد.',local:'تبقى العلامات المرجعية على هذا الهاتف ولا تُضاف إلى نسخ PDF المحفوظة.',failed:'تعذّر حفظ العلامة المرجعية. قد تكون مساحة الهاتف ممتلئة.'}};
 const t=k=>words[language()][k];
 const make=(tag,id,text)=>{const node=document.createElement(tag);if(id)node.id=id;if(text)node.textContent=text;return node;};
 const wholeLabel=make('label','wholeWordLabel'),whole=make('input','findWholeWord'),wholeText=make('span');
 whole.type='checkbox';wholeLabel.className='reading-check whole-word-option';wholeLabel.append(whole,wholeText);$('findBar').append(wholeLabel);
 whole.onchange=()=>{state.searchSources=[];find(false,'entirewordchange');};
 const keepLabel=make('label','keepScreenOnLabel'),keep=make('input','keepScreenOn'),keepText=make('span');
 keep.type='checkbox';keepLabel.className='reading-check';keepLabel.append(keep,keepText);$('readerOptions').append(keepLabel);
 try{keep.checked=localStorage.getItem('insight-keep-screen-on')==='true';}catch{}
 keep.disabled=!window.LocalPDFReader;
 let lastKeep=null,bookmarkTab=false;
 function screen(active=!!state.pdf&&!document.hidden){
  const enabled=Boolean(active&&keep.checked&&!keep.disabled);if(lastKeep===enabled)return;
  try{window.LocalPDFReader?.postMessage(enabled?'keep-screen-on':'allow-screen-off');lastKeep=enabled;}catch{keep.disabled=true;keep.title=t('unavailable');}
 }
 keep.onchange=()=>{try{localStorage.setItem('insight-keep-screen-on',String(keep.checked));}catch{}screen();};
 document.addEventListener('visibilitychange',()=>screen());
 window.addEventListener('pagehide',()=>screen(false));
 window.addEventListener('pageshow',()=>screen());
 const tab=make('button','showBookmarks'),add=make('button','bookmarkCurrent');
 tab.type=add.type='button';$('contents').querySelector('.tabs').append(tab);
 function key(){return state.current?.id?'insight-bookmarks-v1-'+state.current.id:null;}
 function pages(){try{const stored=JSON.parse(localStorage.getItem(key())||'[]');return Array.isArray(stored)?[...new Set(stored.filter(n=>Number.isInteger(n)&&n>0&&n<=state.pdf?.numPages))].sort((a,b)=>a-b):[];}catch{return [];}}
 function write(next){try{localStorage.setItem(key(),JSON.stringify(next));return true;}catch{toast(t('failed'));return false;}}
 function refresh(){
  screen();if(!bookmarkTab)return;
  const target=$('contentsList');target.replaceChildren(add);const saved=pages();
  const valid=!!(key()&&state.pdf);add.disabled=!valid;add.textContent=t(saved.includes(viewer.currentPageNumber)?'remove':'add');
  add.setAttribute('aria-pressed',String(valid&&saved.includes(viewer.currentPageNumber)));
  const note=make('p',null,t('local'));note.className='small bookmark-note';target.append(note);
  if(!saved.length){const empty=make('p',null,t('empty'));empty.className='small';target.append(empty);}
  for(const number of saved){const row=make('div');row.className='bookmark-row';
   const jump=make('button',null,`${t('page')} ${number}`),remove=make('button',null,'×');jump.type=remove.type='button';jump.dataset.bookmarkPage=number;
   jump.onclick=()=>{gotoPage(number);$('contents').hidden=true;};
   remove.setAttribute('aria-label',`${t('remove')}: ${t('page')} ${number}`);remove.title=remove.getAttribute('aria-label');
   remove.onclick=()=>{if(write(pages().filter(n=>n!==number)))refresh();};row.append(jump,remove);target.append(row);
  }
 }
 add.onclick=()=>{if(!key()||!state.pdf)return;const saved=pages(),page=viewer.currentPageNumber;
  if(write(saved.includes(page)?saved.filter(n=>n!==page):[...saved,page].sort((a,b)=>a-b)))refresh();};
 function selectBookmarks(){bookmarkTab=true;for(const id of ['showOutline','showThumbs'])$(id).setAttribute('aria-pressed','false');tab.setAttribute('aria-pressed','true');refresh();}
 tab.onclick=selectBookmarks;
 for(const id of ['showOutline','showThumbs'])$(id).addEventListener('click',()=>{bookmarkTab=false;for(const other of ['showOutline','showThumbs','showBookmarks'])$(other).setAttribute('aria-pressed',String(other===id));});
 eventBus.on('pagechanging',()=>{if(bookmarkTab)refresh();});
 function translate(){wholeText.textContent=t('whole');keepText.textContent=t('keep');keep.title=keep.disabled?t('unavailable'):t('keep');tab.textContent=t('bookmarks');refresh();}
 translate();return {refresh,translate,screen,documentChanged(){if(bookmarkTab)refresh();else screen();},get showingBookmarks(){return bookmarkTab;}};
}

const CACHE='localpdf-shell-v2';
const SHELL=['/','/static/app.js','/static/app.css','/static/manifest.webmanifest','/static/icon.svg','/static/icon-192.png','/static/icon-512.png','/static/vendor/pdfjs/build/pdf.mjs','/static/vendor/pdfjs/build/pdf.worker.mjs','/static/vendor/pdfjs/web/pdf_viewer.mjs','/static/vendor/pdfjs/web/pdf_viewer.css'];
self.addEventListener('install',event=>event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(SHELL))));
self.addEventListener('activate',event=>event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(key=>key.startsWith('localpdf-shell-')&&key!==CACHE).map(key=>caches.delete(key)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',event=>{
 const url=new URL(event.request.url);
 // Never store documents, API responses, page images, credentials or evidence in the service worker cache.
 if(event.request.method!=='GET'||url.origin!==location.origin||url.pathname.startsWith('/api/'))return;
 if(url.pathname!=='/'&&!url.pathname.startsWith('/static/'))return;
 event.respondWith(fetch(event.request).then(response=>{if(response.ok){const copy=response.clone();caches.open(CACHE).then(cache=>cache.put(event.request,copy));}return response;}).catch(()=>caches.match(event.request).then(async cached=>cached||(url.pathname==='/'?await caches.match('/'):null)||Response.error())));
});

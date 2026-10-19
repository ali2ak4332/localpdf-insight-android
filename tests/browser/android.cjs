// Standalone Android adapter workflow validation. No Python server or Ollama.
// NODE_PATH=<Playwright modules> CHROMIUM_EXECUTABLE=<Chromium> node tests/browser/android.cjs
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const {chromium} = require('playwright');
const root = path.resolve(__dirname, '../..');
const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'localpdf-android-'));
const staticRoot = path.join(root, 'src/localpdf_insight/static');
const artifacts = process.env.LOCALPDF_TEST_ARTIFACTS || path.join(root, 'validation-artifacts');
const base = 'https://appassets.androidplatform.net';
const appUrl = base + '/?platform=android&test=1';
const generated = spawnSync(process.env.LOCALPDF_TEST_PYTHON || 'python3',
  [path.join(__dirname, 'android_fixtures.py'), temp], {encoding: 'utf8'});
if (generated.status !== 0) throw Error(generated.stderr);
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
const results = [], timings = {}, attemptedNetwork = [], errors = [];
let browser, context, page;
let firstId, secondId, arabicId, noteId, noteText, noteBbox;
async function check(name, run) {
  const start = performance.now();
  try { await run(); results.push({name, status: 'passed', seconds: +(performance.now() - start).toFixed(1) / 1000}); console.log('PASS', name); }
  catch (error) { results.push({name, status: 'failed', error: error.message}); throw error; }
}
async function ready(filename) {
  await page.waitForFunction(name => window.__reader.state.current?.filename === name && !window.__reader.state.importing,
    filename, {timeout: 60000});
}
async function viewOption(id, value) {
  if (!await page.locator('#readerOptions').isVisible()) await page.locator('#readerOptionsToggle').click();
  await page.locator('#' + id).selectOption(value);
  await page.locator('#readerOptionsToggle').click();
}
async function indexed() {
  await page.waitForFunction(() => window.__reader.state.documents.every(d => d.index.status === 'ready'), null, {timeout: 90000});
}
async function goto(number) {
  await page.locator('#pageNumber').fill(String(number));
  await page.locator('#pageNumber').dispatchEvent('change');
  await page.waitForFunction(n => window.__reader.viewer.currentPageNumber === n, number);
}
async function backend(pathname, body, method = 'POST') {
  return page.evaluate(async ({pathname, body, method}) => {
    if (!window.androidTestBackend) {
      const pdfjs = await import('/static/vendor/pdfjs/build/pdf.mjs');
      window.androidTestBackend = await (await import('/static/mobile_backend.js')).createMobileBackend(pdfjs);
    }
    return window.androidTestBackend.request(pathname, {method, body});
  }, {pathname, body, method});
}
async function openLibrary(id) {
  if (!await page.evaluate(() => document.body.classList.contains('library-open'))) await page.locator('#libraryToggle').click();
  await page.locator('.doc-card').filter({has: page.locator(`input[aria-label="Select ${await page.evaluate(id => window.__reader.state.documents.find(d => d.id === id).title, id)}"]`)}).locator('.doc-open').click();
  await page.waitForFunction(id => window.__reader.state.current?.id === id && !!window.__reader.state.pdf, id);
}
async function selectText(pageNumber, contains) {
  await goto(pageNumber);
  const text = contains === '__all_text__'
    ? page.locator(`.page[data-page-number="${pageNumber}"] .textLayer`)
    : page.locator(`.page[data-page-number="${pageNumber}"] .textLayer span`).filter({hasText: contains}).first();
  await text.waitFor();
  await text.evaluate(node => {
    const selection = getSelection(), range = document.createRange();
    range.selectNodeContents(node); selection.removeAllRanges(); selection.addRange(range);
    document.getElementById('viewerContainer').dispatchEvent(new PointerEvent('pointerup', {bubbles: true}));
  });
  await page.locator('#selectionMenu').waitFor();
  return page.evaluate(() => structuredClone(window.__reader.state.selection));
}
async function saveSelected(comment) {
  const previous = await page.locator('#studioOutput').getAttribute('data-output-id');
  await page.locator('#selectionMenu [data-action="note"]').click();
  await page.locator('#noteComment').fill(comment);
  await page.locator('#noteForm .primary').click();
  await page.waitForFunction(previous => {
    const current = document.getElementById('studioOutput').dataset.outputId;
    return !!current && current !== previous;
  }, previous);
  return page.locator('#studioOutput').getAttribute('data-output-id');
}
(async () => {
  try {
    browser = await chromium.launch({headless: true, ...(process.env.CHROMIUM_EXECUTABLE ? {
      executablePath: process.env.CHROMIUM_EXECUTABLE,
      args: ['--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage'],
    } : {})});
    context = await browser.newContext({viewport: {width: 412, height: 915}, deviceScaleFactor: 2.625,
      hasTouch: true, isMobile: true, serviceWorkers: 'block'});
    await context.setOffline(true);
    const mime = {'.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css',
      '.png': 'image/png', '.svg': 'image/svg+xml', '.webmanifest': 'application/manifest+json', '.wasm': 'application/wasm'};
    await context.route('**/*', async route => {
      const url = new URL(route.request().url());
      if (url.protocol === 'blob:' || url.protocol === 'data:') return route.continue();
      if (url.origin !== base || url.pathname.startsWith('/api/')) {
        attemptedNetwork.push(route.request().url()); return route.abort();
      }
      const relative = url.pathname === '/' ? 'index.html' : url.pathname.replace(/^\/static\//, '');
      const file = path.resolve(staticRoot, relative);
      if (!file.startsWith(staticRoot + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
        attemptedNetwork.push(route.request().url()); return route.abort();
      }
      return route.fulfill({status: 200, contentType: mime[path.extname(file)] || 'application/octet-stream', body: fs.readFileSync(file)});
    });
    page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(appUrl);
    await page.waitForFunction(() => !!window.__reader);

    await check('Offline launch offers reader and notes; AI/Ollama controls are absent', async () => {
      for (const id of ['askToggle', 'question', 'operation', 'submitAsk', 'compare', 'createOutput', 'tables']) assert(!await page.locator('#' + id).isVisible(), id);
      assert(await page.locator('#studioToggle').isVisible());
      assert.match(await page.locator('#privacyText').textContent(), /no AI, upload, computer server or OCR/i);
      assert(await page.evaluate(() => window.__reader.state.online));
    });
    await check('150-page PDF becomes readable offline and uses bounded page canvases', async () => {
      const start = performance.now();
      await page.locator('#fileInput').setInputFiles(path.join(temp, 'agreement.pdf'));
      await page.locator('.page[data-page-number="1"] .textLayer span').first().waitFor({timeout: 60000});
      timings.firstReadableSeconds = +((performance.now() - start) / 1000).toFixed(3);
      await ready('agreement.pdf');
      firstId = await page.evaluate(() => window.__reader.state.current.id);
      assert.equal(await page.evaluate(() => window.__reader.state.pdf.numPages), 150);
      assert((await page.locator('.pdfViewer canvas').count()) < 20);
      assert(await page.evaluate(() => [...document.querySelectorAll('.pdfViewer canvas')].every(c => c.width <= 4096 && c.height <= 4096)));
      await indexed(); timings.indexingSeconds = +((performance.now() - start) / 1000).toFixed(3);
    });
    await check('Compact icon toolbar fits two rows at phone widths and retains all actions in English and Arabic', async () => {
      const title = await page.locator('#documentTitle').textContent();
      for (const language of ['en', 'ar']) {
        if (await page.locator('html').getAttribute('lang') !== language) await page.locator('#language').click();
        for (const width of [320, 360, 412]) {
          await page.setViewportSize({width, height:915});
          assert(!await page.locator('.app-header').isVisible());
          const heading = await page.locator('.document-heading').boundingBox();
          const bar = await page.locator('.reader-toolbar').boundingBox();
          assert.equal(heading.y, 0); assert(heading.height + bar.height <= 94);
          assert.equal(await page.locator('#documentTitle').textContent(), title);
          for (const id of ['libraryToggle','readerOptionsToggle','sharePdf','studioToggle','language','outlineToggle','previousPage','pageNumber','nextPage','findToggle','editToggle','saveEdited','printPdf']) {
            const control=page.locator('#'+id),box=await control.boundingBox();
            assert(box && box.x>=-1 && box.x+box.width<=width+1, id+' must be on screen at '+width);
            assert(box.height>=36 && box.width>=28, id+' must remain usable');
            assert(await control.getAttribute('aria-label'),id+' needs an accessible label');
            if(await control.evaluate(node=>node.tagName==='BUTTON')) {
              assert.equal((await control.textContent()).trim(),'');
              assert.equal(await control.locator('.toolbar-glyph').count(),1);
            }
          }
          assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
        }
        await page.locator('#readerOptionsToggle').click();
        assert(await page.locator('#readerOptions').isVisible());
        assert.equal(await page.locator('#readerOptionsToggle').getAttribute('aria-expanded'),'true');
        await page.locator('#zoomIn').click();
        assert(await page.locator('#readerOptions').isVisible());
        await page.evaluate(()=>window.localPDFBack());
        assert(!await page.locator('#readerOptions').isVisible());
        await page.locator('#readerOptionsToggle').click(); await page.keyboard.press('Escape');
        assert(!await page.locator('#readerOptions').isVisible());
        await page.locator('#readerOptionsToggle').click(); await page.locator('#documentTitle').click();
        assert(!await page.locator('#readerOptions').isVisible());
        await viewOption('zoom','page-width');
        await page.locator('#libraryToggle').click();assert(await page.locator('#library').isVisible());
        await page.evaluate(()=>window.localPDFBack());
        await page.locator('#studioToggle').click();assert(await page.locator('#inspector').isVisible());
        await page.locator('#closeInspector').click();
      }
      await page.locator('#language').click();
      await page.setViewportSize({width:412,height:915});
      await page.screenshot({path:path.join(artifacts,'compact-toolbar-en.png')});
      await page.locator('#language').click();
      await page.screenshot({path:path.join(artifacts,'compact-toolbar-ar.png')});
      await page.locator('#language').click();
    });
    await check('Page jump Enter commits and releases keyboard focus in English and Arabic', async () => {
      const input = page.locator('#pageNumber');
      for (const [value, expected] of [['27', 27], ['999', 150], ['0', 1]]) {
        await input.fill(value);
        await input.press('Enter');
        assert.equal(await page.evaluate(() => window.__reader.viewer.currentPageNumber), expected);
        assert.equal(await input.inputValue(), String(expected));
        assert.equal(await input.evaluate(node => node === document.activeElement), false);
      }
      await input.fill('44');
      await input.dispatchEvent('keydown', {key: 'Enter', isComposing: true});
      assert.equal(await page.evaluate(() => window.__reader.viewer.currentPageNumber), 1);
      assert.equal(await input.evaluate(node => node === document.activeElement), true);
      await page.locator('#language').click();
      assert.equal(await page.locator('html').getAttribute('lang'), 'ar');
      await input.fill('18'); await input.press('Enter');
      assert.equal(await page.evaluate(() => window.__reader.viewer.currentPageNumber), 18);
      assert.equal(await input.evaluate(node => node === document.activeElement), false);
      assert.equal(await input.getAttribute('enterkeyhint'), 'go');
      await page.locator('#language').click();
    });
    await check('Page jump, outline and native highlighted search reach page 18', async () => {
      await goto(150);
      await page.locator('#outlineToggle').click();
      await page.locator('#contentsList button').filter({hasText: 'Termination'}).click();
      await page.waitForFunction(() => window.__reader.viewer.currentPageNumber === 18);
      await page.locator('#outlineToggle').click();
      await page.locator('#findToggle').click(); await page.locator('#findInput').fill('written notice');
      await page.waitForFunction(() => document.getElementById('findCount').textContent.includes('/ 1'));
      await page.locator('.textLayer .highlight').first().waitFor();
      assert.equal(await page.evaluate(() => window.__reader.viewer.currentPageNumber), 18);
      await page.evaluate(() => window.localPDFBack());
    });
    await check('Closing search clears temporary highlights and retains the query in English and Arabic', async () => {
      const input = page.locator('#findInput');
      const original = await page.evaluate(() => ({id: window.__reader.state.current.id, revision: window.__reader.state.current.revision}));
      for (const language of ['en', 'ar']) {
        if (await page.locator('html').getAttribute('lang') !== language) await page.locator('#language').click();
        for (const close of ['toggle', 'back', 'escape']) {
          await page.locator('#findToggle').click();
          await input.fill('written notice');
          await input.press('Enter');
          await page.locator('.textLayer .highlight').first().waitFor();
          assert.equal(await page.evaluate(() => window.__reader.viewer.currentPageNumber), 18);
          if (close === 'toggle') await page.locator('#findToggle').click();
          else if (close === 'back') assert.equal(await page.evaluate(() => window.localPDFBack()), true);
          else await input.press('Escape');
          assert(!await page.locator('#findBar').isVisible());
          await page.waitForFunction(() => !document.querySelector('.textLayer .highlight'), null, {timeout: 3000});
          assert.equal(await input.inputValue(), 'written notice');
          assert.equal(await page.evaluate(() => window.__reader.viewer.currentPageNumber), 18);
          assert.equal(await page.evaluate(() => window.__reader.editor.dirty), false);
        }
        // Closing before the debounced search finishes must not paint late highlights.
        await page.locator('#findToggle').click();
        await input.fill('confidential materials');
        await page.evaluate(() => window.localPDFBack());
        await delay(600);
        assert.equal(await page.locator('.textLayer .highlight').count(), 0);
        // The retained query can be searched again using the existing next-result action.
        await page.locator('#findToggle').click();
        assert.equal(await input.inputValue(), 'confidential materials');
        await input.press('Enter');
        await page.locator('.textLayer .highlight').first().waitFor();
        await page.evaluate(() => window.localPDFBack());
        await page.waitForFunction(() => !document.querySelector('.textLayer .highlight'));
      }
      await page.locator('#language').click();
      assert.deepEqual(await page.evaluate(() => ({id: window.__reader.state.current.id, revision: window.__reader.state.current.revision})), original);
      await page.screenshot({path: path.join(artifacts, 'android-search-closed.png')});
    });
    await check('Lazy thumbnails, single/spread layouts and pinch zoom work', async () => {
      await page.locator('#outlineToggle').click(); await page.locator('#showThumbs').click();
      assert.equal(await page.locator('#contentsList button[data-page]').count(), 150);
      await page.locator('#contentsList canvas').first().waitFor();
      assert((await page.locator('#contentsList canvas').count()) < 20);
      await page.locator('#outlineToggle').click();
      await viewOption('viewMode','single'); assert.equal(await page.evaluate(() => window.__reader.viewer.scrollMode), 3);
      await viewOption('viewMode','spread'); assert.equal(await page.evaluate(() => window.__reader.viewer.spreadMode), 1);
      await viewOption('viewMode','continuous');
      const scale = await page.evaluate(() => window.__reader.viewer.currentScale);
      const cdp = await context.newCDPSession(page);
      await cdp.send('Input.dispatchTouchEvent', {type: 'touchStart', touchPoints: [{x: 130, y: 400}, {x: 230, y: 400}]});
      await cdp.send('Input.dispatchTouchEvent', {type: 'touchMove', touchPoints: [{x: 100, y: 400}, {x: 260, y: 400}]});
      await cdp.send('Input.dispatchTouchEvent', {type: 'touchEnd', touchPoints: []});
      assert(await page.evaluate(() => window.__reader.viewer.currentScale) > scale);
      await viewOption('zoom','page-width'); await goto(18); await delay(500);
    });
    await check('Saved PDF Blob, stable identity and reading position survive cold browser reload', async () => {
      await page.reload(); await page.waitForFunction(() => !!window.__reader && window.__reader.state.documents.length === 1);
      await openLibrary(firstId); await delay(500);
      assert.equal(await page.evaluate(() => window.__reader.viewer.currentPageNumber), 18);
      assert.equal(await page.evaluate(() => window.__reader.state.current.id), firstId);
      assert(await page.evaluate(() => window.__reader.state.pdf !== null));
      await page.locator('.page[data-page-number="18"] .textLayer span').first().waitFor();
    });
    await check('Friendly title and duplicate detection retain original document identity', async () => {
      await page.locator('#libraryToggle').click(); await page.locator('.doc-actions').first().click();
      await page.locator('#editTitle').fill('My agreement'); await page.locator('#metadataForm .primary').click();
      await page.waitForFunction(() => window.__reader.state.current.title === 'My agreement');
      await page.locator('#fileInput').setInputFiles({name: 'duplicate.pdf', mimeType: 'application/pdf', buffer: fs.readFileSync(path.join(temp, 'agreement.pdf'))});
      await page.waitForFunction(id => !window.__reader.state.importing && window.__reader.state.current?.id === id, firstId);
      assert.equal(await page.evaluate(() => window.__reader.state.documents.length), 1);
      assert.equal(await page.locator('#documentTitle').textContent(), 'My agreement');
    });
    await check('Android provider PDF MIME is accepted when attachment name lacks .pdf suffix', async () => {
      await page.locator('#fileInput').setInputFiles({name: 'attachment', mimeType: 'application/pdf', buffer: fs.readFileSync(path.join(temp, 'agreement.pdf'))});
      await page.waitForFunction(() => !window.__reader.state.importing);
      assert.notEqual(await page.locator('#toast').textContent(), 'Choose a PDF file.');
      assert.equal(await page.evaluate(() => window.__reader.state.current?.id), firstId);
      assert.equal(await page.evaluate(() => window.__reader.state.documents.length), 1);
      assert.equal(await page.locator('#documentTitle').textContent(), 'My agreement');
    });
    await check('Selected paragraph saves note with exact document, page, text and coordinates', async () => {
      const selection = await selectText(18, 'written notice');
      noteText = selection.text; noteBbox = selection.bbox;
      assert.equal(selection.document_id, firstId); assert.equal(selection.page, 18);
      assert.match(selection.text, /30 days written notice/);
      assert(selection.bbox.every(v => v >= 0 && v <= 1));
      noteId = await saveSelected('My review comment'); await indexed();
      const note = await backend('/api/studio/' + noteId, undefined, 'GET');
      assert.equal(note.content.comment, 'My review comment');
      assert.equal(note.content.selection.document_id, firstId); assert.equal(note.content.selection.page, 18);
      assert.equal(note.content.selection.text, noteText); assert.deepEqual(note.content.selection.bbox, noteBbox);
      assert.equal(note.content.sources[0].revision, await page.evaluate(() => window.__reader.state.current.revision));
      await page.locator('#closeInspector').click();
    });
    await check('Note citation reopens correct PDF/page after switch, rename and cold reload', async () => {
      await page.locator('#fileInput').setInputFiles(path.join(temp, 'revision.pdf')); await ready('revision.pdf'); await indexed();
      secondId = await page.evaluate(() => window.__reader.state.current.id);
      await backend('/api/documents/' + firstId, {title: 'Renamed agreement'}, 'PATCH');
      await page.reload(); await page.waitForFunction(() => !!window.__reader);
      await openLibrary(secondId);
      await page.locator('#studioToggle').click(); await page.locator('#studioList .saved-output').first().click();
      await page.waitForFunction(id => document.getElementById('studioOutput').dataset.outputId === id, noteId);
      assert.match(await page.locator('#studioOutput').textContent(), /My review comment/);
      assert.match(await page.locator('#studioOutput .citation').textContent(), /My agreement/);
      await page.locator('#studioOutput .citation').click();
      await page.waitForFunction(id => window.__reader.state.current?.id === id && window.__reader.viewer.currentPageNumber === 18, firstId);
      await page.locator('.evidence-region').waitFor();
      assert.equal(await page.locator('#documentTitle').textContent(), 'Renamed agreement');
    });
    await check('Scoped passage search cannot leak unselected document evidence', async () => {
      await indexed();
      const selected = await backend('/api/search', {scope: 'selected', document_ids: [firstId], question: 'written notice'});
      assert(selected.sources.length > 0 && selected.sources.every(s => s.document_id === firstId));
      assert(selected.sources.some(s => s.page === 18 && s.text.includes('30 days')));
      const all = await backend('/api/search', {scope: 'library', question: 'written notice'});
      assert(all.sources.some(s => s.document_id === firstId) && all.sources.some(s => s.document_id === secondId));
      const none = await backend('/api/search', {scope: 'selected', document_ids: [], question: 'termination'}).then(() => false, () => true);
      assert(none, 'Empty selected scope must be refused rather than broadened');
    });
    await check('Native mixed Arabic/English search normalization and source-linked RTL note', async () => {
      await page.locator('#fileInput').setInputFiles(path.join(temp, 'arabic.pdf')); await ready('arabic.pdf'); await indexed();
      arabicId = await page.evaluate(() => window.__reader.state.current.id);
      const searched = await backend('/api/search', {scope: 'current', current_id: arabicId, question: 'انهاء العقد'});
      if (!searched.sources.length) console.error('ARABIC EXTRACTION', await backend(`/api/documents/${arabicId}/pages/1`, undefined, 'GET'));
      assert(searched.sources.length && searched.sources.every(s => s.document_id === arabicId && s.page === 1));
      const mixed = await backend('/api/search', {scope: 'current', current_id: arabicId, question: 'ABC ٥٠٠'});
      assert(mixed.sources.length > 0);
      await page.locator('#language').click(); assert.equal(await page.locator('html').getAttribute('dir'), 'rtl');
      const selection = await selectText(1, '__all_text__');
      assert.match(selection.text.normalize('NFKC').replace(/\s/g, ''), /العقد/);
      const saved = await saveSelected('ملاحظة شخصية ABC-123'); await indexed();
      const note = await backend('/api/studio/' + saved, undefined, 'GET');
      assert.equal(note.content.selection.document_id, arabicId); assert.equal(note.content.selection.page, 1);
      assert.equal(note.content.comment, 'ملاحظة شخصية ABC-123');
      assert.equal(await page.locator('#studioOutput blockquote').getAttribute('dir'), 'auto');
      await page.locator('#studioOutput .citation').click();
      assert.equal(await page.evaluate(() => window.__reader.state.current.id), arabicId);
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    });
    await check('Malformed Arabic font remains readable and exposes extraction uncertainty', async () => {
      await page.locator('#fileInput').setInputFiles(path.join(temp, 'broken-arabic-font.pdf'));
      await ready('broken-arabic-font.pdf'); await indexed();
      const id = await page.evaluate(() => window.__reader.state.current.id);
      const extraction = await backend(`/api/documents/${id}/pages/1`, undefined, 'GET');
      assert(extraction.warnings.length > 0 || await page.evaluate(() => !!window.__reader.state.current.index.warning));
      assert.match(extraction.text, /Ǆ|ǂ/); // Preserve source glyphs; never silently guess damaged text.
      await page.locator('.pdfViewer canvas').first().waitFor();
    });
    await check('Image-only scan remains readable with explicit no-OCR status and no invented text', async () => {
      await page.locator('#fileInput').setInputFiles(path.join(temp, 'scan.pdf')); await ready('scan.pdf'); await indexed();
      const scanId = await page.evaluate(() => window.__reader.state.current.id);
      await page.locator('.pdfViewer canvas').first().waitFor();
      const warning = await page.evaluate(() => window.__reader.state.current.index.warning);
      assert.match(warning, /no selectable text.*OCR is not included/i);
      const extraction = await backend(`/api/documents/${scanId}/pages/1`, undefined, 'GET');
      assert.equal(extraction.text, ''); assert.equal(extraction.units.length, 0);
      const matches = await backend('/api/search', {scope: 'current', current_id: scanId, question: 'Scan-only answer'});
      assert.equal(matches.sources.length, 0);
      assert.equal(await page.locator('.textLayer span').count(), 0);
    });
    await check('Protected PDF reads and indexes offline with supplied password', async () => {
      const prompts = []; page.on('dialog', async dialog => {prompts.push(dialog.message()); await dialog.accept('reader-secret');});
      await page.locator('#fileInput').setInputFiles(path.join(temp, 'protected.pdf')); await ready('protected.pdf'); await indexed();
      assert.equal(await page.evaluate(() => window.__reader.state.pdf.numPages), 20); assert(prompts.length >= 1);
      const documents = await backend('/api/documents', undefined, 'GET');
      assert(!JSON.stringify(documents).includes('reader-secret'), 'Document metadata must not persist password');
    });
    await check('Rotated unusual-size PDF search and source highlight remain on the right page', async () => {
      await page.locator('#fileInput').setInputFiles(path.join(temp, 'rotated.pdf')); await ready('rotated.pdf'); await indexed();
      const id = await page.evaluate(() => window.__reader.state.current.id);
      const matched = await backend('/api/search', {scope: 'current', current_id: id, question: 'Rotated evidence'});
      assert(matched.sources.length > 0); const source = matched.sources[0];
      await page.evaluate(id => window.__reader.openSource(id), source.id); await page.locator('.evidence-region').waitFor();
      const box = await page.locator('.evidence-region').evaluate(el => {
        const region = el.getBoundingClientRect(), page = el.parentElement.getBoundingClientRect();
        return {x: (region.left - page.left) / page.width, y: (region.top - page.top) / page.height,
          width: region.width / page.width, height: region.height / page.height};
      });
      assert(Math.abs(box.x - source.bbox[0]) < .01 && Math.abs(box.y - source.bbox[1]) < .01);
      assert(box.width > 0 && box.height > 0 && box.x + box.width <= 1.01 && box.y + box.height <= 1.01);
    });
    await check('Rotation and Android Back close overlays before allowing app exit', async () => {
      await page.setViewportSize({width: 915, height: 412}); await delay(300);
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      await page.setViewportSize({width: 412, height: 915});
      await page.locator('#outlineToggle').click();
      assert.equal(await page.evaluate(() => window.localPDFBack()), true); assert(!await page.locator('#contents').isVisible());
      await page.locator('#findToggle').click();
      assert.equal(await page.evaluate(() => window.localPDFBack()), true); assert(!await page.locator('#findBar').isVisible());
      await page.locator('#studioToggle').click();
      assert.equal(await page.evaluate(() => window.localPDFBack()), true); assert(!await page.locator('#inspector').isVisible());
      await page.locator('#libraryToggle').click();
      assert.equal(await page.evaluate(() => window.localPDFBack()), true);
      assert.equal(await page.evaluate(() => window.localPDFBack()), false);
    });
    await check('Private-storage failure shows actionable notice and disables unsafe imports', async () => {
      const unavailable = await context.newPage();
      await unavailable.addInitScript(() => {indexedDB.open = () => {throw new DOMException('Storage denied', 'SecurityError');};});
      await unavailable.goto(appUrl);
      await unavailable.locator('#emptyState h2').filter({hasText: 'Phone storage is unavailable'}).waitFor();
      assert.match(await unavailable.locator('#emptyState p').textContent(), /Storage denied/);
      assert(await unavailable.locator('#fileInput').isDisabled());
      assert.equal(await unavailable.evaluate(() => !!window.__reader), false);
      await unavailable.close();
    });
    await check('No API server, Ollama or external network attempts occurred', async () => {
      assert.deepEqual(attemptedNetwork, []); assert.deepEqual(errors, []);
    });
    fs.mkdirSync(artifacts, {recursive: true});
    await page.screenshot({path: path.join(artifacts, 'android-reader-browser.png')});
  } catch (error) {
    console.error(error);
    if (page) {console.error('STATE', await page.evaluate(() => ({current: window.__reader?.state.current, importing: window.__reader?.state.importing, toast: document.getElementById('toast').textContent})));}
    process.exitCode = 1;
  } finally {
    fs.mkdirSync(artifacts, {recursive: true});
    const report = {testEnvironment: 'Offline Chromium mobile emulation; packaged WebView assets routed locally; no Python/Ollama server',
      fixtureDirectory: temp, passed: results.filter(r => r.status === 'passed').length,
      failed: results.filter(r => r.status === 'failed').length, results, timings, attemptedNetwork, browserErrors: errors};
    fs.writeFileSync(path.join(artifacts, 'android-browser-results.json'), JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report, null, 2));
    if (browser) await browser.close();
  }
})();

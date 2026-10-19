// Test-harness only (use: node --require ./tests/browser/legacy_chromium_polyfill.cjs <suite>): the sandbox's Chromium 141 predates Map/WeakMap.getOrInsertComputed,
// which the bundled PDF.js uses (current Android WebView ships it). Inject before page scripts.
const pw = require('playwright');
const script = () => {
  if (typeof Blob !== 'undefined' && !Blob.prototype.bytes) Object.defineProperty(Blob.prototype, 'bytes', {configurable: true, writable: true,
    async value() { return new Uint8Array(await this.arrayBuffer()); }});
  for (const C of [Map, WeakMap]) {
    if (!C.prototype.getOrInsertComputed) Object.defineProperty(C.prototype, 'getOrInsertComputed', {configurable: true, writable: true,
      value(key, fn) { if (this.has(key)) return this.get(key); const v = fn(key); this.set(key, v); return v; }});
    if (!C.prototype.getOrInsert) Object.defineProperty(C.prototype, 'getOrInsert', {configurable: true, writable: true,
      value(key, v) { if (this.has(key)) return this.get(key); this.set(key, v); return v; }});
  }
};
const launch = pw.chromium.launch.bind(pw.chromium);
pw.chromium.launch = async (...a) => {
  const browser = await launch(...a);
  const newContext = browser.newContext.bind(browser);
  browser.newContext = async (...b) => {
    const c = await newContext(...b); await c.addInitScript(script);
    // PDF.js saves inside its worker, which init scripts do not reach: prefix the worker module.
    const route = c.route.bind(c);
    c.route = (pattern, handler, ...rest) => route(pattern, r => {
      if (!/pdf\.worker(\.min)?\.mjs$/.test(new URL(r.request().url()).pathname)) return handler(r);
      const proxy = new Proxy(r, {get(t, k) {
        if (k === 'fulfill') return opts => {
          const body = opts.path ? require('fs').readFileSync(opts.path) : opts.body;
          const { path: _p, ...o } = opts;
          return t.fulfill({...o, body: '(' + script.toString() + ')();\n' + body.toString()});
        };
        const v = t[k]; return typeof v === 'function' ? v.bind(t) : v;
      }});
      return handler(proxy);
    }, ...rest);
    return c;
  };
  return browser;
};

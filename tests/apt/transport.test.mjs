import test from 'node:test';import assert from 'node:assert/strict';
import {nativeTransport} from '../../src/localpdf_insight/static/apt_panel.mjs';
test('missing native runtime fails explicitly without a network fallback',async()=>{
 await assert.rejects(nativeTransport(null)('status'),/unavailable/);
});
test('native responses are correlated by request ID',async()=>{
 const bridge={postMessage(raw){const r=JSON.parse(raw);queueMicrotask(()=>{
  bridge.onmessage({data:'not JSON'});bridge.onmessage({data:JSON.stringify({id:'forged',ok:true,data:{text:'invented'}})});
  bridge.onmessage({data:JSON.stringify({id:r.id,ok:true,data:{text:'[0]'}})});
 });}};
 assert.equal((await nativeTransport(bridge)('generate',{prompt:'source text'})).text,'[0]');
});
test('native errors are surfaced',async()=>{
 const bridge={postMessage(raw){const r=JSON.parse(raw);queueMicrotask(()=>bridge.onmessage({data:JSON.stringify({id:r.id,ok:false,error:'Wrong model digest'})}));}};
 await assert.rejects(nativeTransport(bridge)('generate',{prompt:'source'}),/digest/);
});
test('aborting sends cancellation and does not accept a late result',async()=>{
 const messages=[],bridge={postMessage(raw){messages.push(JSON.parse(raw));}};
 const send=nativeTransport(bridge),c=new AbortController(),p=send('generate',{prompt:'source'},{signal:c.signal});c.abort();
 await assert.rejects(p,/cancelled/);assert.equal(messages[1].action,'cancel');
 bridge.onmessage({data:JSON.stringify({id:messages[0].id,ok:true,data:{text:'[0]'}})});
});
test('already-aborted work never reaches generation',async()=>{
 const messages=[],bridge={postMessage(raw){messages.push(JSON.parse(raw));}},c=new AbortController();c.abort();
 await assert.rejects(nativeTransport(bridge)('generate',{}, {signal:c.signal}),/cancelled/);
 assert.ok(messages.every(m=>m.action==='cancel'));
});

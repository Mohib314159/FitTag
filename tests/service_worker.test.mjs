import {test} from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import fs from 'node:fs';
function worker(offline=false){
 const handlers={},stored=new Map(),operations=[],base='https://example.com/FitTag/';
 const cache={addAll:async paths=>{for(const p of paths)stored.set(new URL(p,base).href,{offline:true,path:p});},put:async(req,value)=>stored.set(req.url||String(req),value)};
 const caches={open:async()=>cache,keys:async()=>['fittag-shell-old','unrelated'],delete:async k=>operations.push(k),match:async (req,options)=>{const key=req.url||String(req);if(stored.has(key))return stored.get(key);if(options?.ignoreSearch){const target=new URL(key);target.search='';for(const [url,value] of stored){const candidate=new URL(url);candidate.search='';if(candidate.href===target.href)return value;}}}};
 vm.runInNewContext(fs.readFileSync(new URL('../web/sw.js',import.meta.url),'utf8'),{URL,caches,fetch:async()=>{if(offline)throw Error('offline');return {ok:true,clone(){return this;}};},self:{registration:{scope:base},clients:{claim:async()=>{}},addEventListener:(name,fn)=>handlers[name]=fn}});
 async function event(name,req){const waits=[];let response;handlers[name]({request:req,waitUntil:p=>waits.push(p),respondWith:p=>response=p});await Promise.all(waits);return response?await response:undefined;}
 return {event,stored,operations,base};
}
test('offline shell and example work at a repository subpath',async()=>{
 const w=worker(true);await w.event('install');
 assert.equal((await w.event('fetch',{method:'GET',url:w.base})).offline,true);
 assert.equal((await w.event('fetch',{method:'GET',url:w.base+'demo.json'})).offline,true);
 assert.equal((await w.event('fetch',{method:'GET',url:w.base+'app.js?v=2'})).path,'./app.js');
 assert.equal((await w.event('fetch',{method:'GET',url:w.base+'free.js?v=free-1'})).path,'./free.js');
 assert.equal((await w.event('fetch',{method:'GET',url:w.base+'free-demo.json'})).offline,true);
 assert.equal((await w.event('fetch',{method:'GET',url:w.base+'request.mjs'})).offline,true);
 for(const asset of ['batch.mjs','photo-check.mjs','camera.mjs','studio.css','example-jeans.jpg'])assert.equal((await w.event('fetch',{method:'GET',url:w.base+asset})).offline,true);
});
test('API requests, photos and foreign origins never enter the cache',async()=>{
 const w=worker();await w.event('install');const count=w.stored.size;
 for(const req of [{method:'POST',url:w.base+'measure'},{method:'POST',url:w.base+'measure-free'},{method:'GET',url:w.base+'experiment'},{method:'GET',url:w.base+'measurement-jobs/secret'},{method:'GET',url:w.base+'models/metric-small.onnx'},{method:'GET',url:w.base+'overlays/private.png'},{method:'GET',url:w.base+'health'},{method:'GET',url:'https://foreign.test/app.js'}])assert.equal(await w.event('fetch',req),undefined);
 assert.equal(w.stored.size,count);
});
test('activation removes only this app’s old shell caches',async()=>{
 const w=worker();await w.event('activate');assert.deepEqual(w.operations,['fittag-shell-old']);
});

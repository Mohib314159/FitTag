import {test} from 'node:test';
import assert from 'node:assert/strict';
import {runBatch} from '../web/batch.mjs';
test('parallel photo work obeys configured capacity and isolates failures',async()=>{
 let active=0,peak=0;const items=Array.from({length:5},(_,id)=>({id,status:id===0?'stop':'queued'}));
 await runBatch(items,{concurrency:2,signal:new AbortController().signal,process:async item=>{
  active++;peak=Math.max(peak,active);await new Promise(resolve=>setTimeout(resolve,5));active--;
  if(item.id===2)throw Error('This photo is cropped');return {id:item.id};
 }});
 assert.equal(peak,2);assert.equal(items[0].status,'stop');assert.equal(items[2].status,'failed');assert.equal(items[4].status,'done');
});
test('single-slot mode finishes selected photos sequentially',async()=>{
 let active=0,peak=0;const items=[{status:'queued'},{status:'queued'}];
 await runBatch(items,{concurrency:1,signal:new AbortController().signal,process:async()=>{active++;peak=Math.max(peak,active);await Promise.resolve();active--;return {};}});
 assert.equal(peak,1);assert.ok(items.every(item=>item.status==='done'));
});
test('stopping a selection leaves unstarted photos unsent',async()=>{
 const controller=new AbortController(),items=[{status:'queued'},{status:'queued'},{status:'queued'}];let sent=0;
 await runBatch(items,{signal:controller.signal,process:async()=>{sent++;controller.abort();throw Error('cancelled');}});
 assert.equal(sent,1);assert.ok(items.every(item=>item.status==='cancelled'));assert.equal(items[1].message,'Not sent.');
});

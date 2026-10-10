import {test} from 'node:test';
import assert from 'node:assert/strict';
import {measurePhoto,pause} from '../web/request.mjs';
const url='/measurement-jobs/'+'b'.repeat(32);
const reply=(body,ok=true)=>({ok,json:async()=>body,headers:{get:()=> '1'}});

test('reports actual job stages then returns the result',async()=>{
 const stages=[],calls=[],waits=[],result={ok:true,mode:'shape'};
 const responses=[reply({}),reply({status_url:url}),reply({status:'running',stage:'depth'}),reply({status:'running',stage:'geometry'}),reply({status:'succeeded',result})];
 const value=await measurePhoto(new FormData(),{fetcher:async(path,opts)=>{calls.push({path,opts});return responses.shift();},onStage:s=>stages.push(s),wait:async ms=>waits.push(ms)});
 assert.equal(value,result);assert.deepEqual(stages,['connecting','uploading','depth','geometry']);assert.deepEqual(waits,[1000,1000]);assert.equal(calls.filter(c=>c.opts.method==='POST').length,1);
});
test('busy admission explains the problem and does not retry upload',async()=>{
 let calls=0;
 await assert.rejects(measurePhoto(new FormData(),{fetcher:async()=>++calls===1?reply({}):reply({error:'Another photo is being measured'},false)}),/Another photo/);
 assert.equal(calls,2);
});
test('expired jobs surface a recoverable error',async()=>{
 const responses=[reply({}),reply({status_url:url}),reply({detail:'This result expired or the server restarted'},false)];
 await assert.rejects(measurePhoto(new FormData(),{fetcher:async()=>responses.shift()}),/expired/);
});
test('transient status failures retry reads only with bounded backoff',async()=>{
 let reads=0,posts=0;const delays=[];
 const result=await measurePhoto(new FormData(),{fetcher:async(path,opts)=>{
  if(path==='./health')return reply({});
  if(opts.method==='POST'){posts++;return reply({status_url:url});}
  if(++reads<3)throw Error('network');return reply({status:'succeeded',result:{ok:true}});
 },wait:async ms=>delays.push(ms)});
 assert.equal(result.ok,true);assert.equal(posts,1);assert.deepEqual(delays,[1500,3000]);
});
test('cancel interrupts a polling delay immediately',async()=>{
 const controller=new AbortController(),waiting=pause(10000,controller.signal);controller.abort();
 await assert.rejects(waiting,{name:'AbortError'});
});
test('job URL cannot direct photo status requests to another origin',async()=>{
 const responses=[reply({}),reply({status_url:'https://other.test/private'})];
 await assert.rejects(measurePhoto(new FormData(),{fetcher:async()=>responses.shift()}),/valid measurement job/);
});

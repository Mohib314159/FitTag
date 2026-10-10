import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createCamera,captureFrame} from '../web/camera.mjs';

function fixture(getUserMedia){
 const states=[],events={},track=new EventTarget();let stops=0;
 track.stop=()=>stops++;
 const stream={getTracks:()=>[track]};
 const video={readyState:2,videoWidth:1200,videoHeight:1600,hidden:true,addEventListener:(name,fn)=>events[name]=fn,play:async()=>{},pause(){}};
 const camera=createCamera(video,{mediaDevices:{getUserMedia:getUserMedia|| (async()=>stream)},onState:(name,message)=>states.push({name,message})});
 return {camera,video,stream,track,states,events,stops:()=>stops};
}
test('camera requests rear-facing video without microphone and stops every track',async()=>{
 let constraints;const f=fixture(async options=>{constraints=options;return f.stream;});
 assert.equal(await f.camera.start(),true);assert.equal(constraints.audio,false);assert.equal(constraints.video.facingMode.ideal,'environment');
 assert.equal(f.video.muted,true);assert.equal(f.video.srcObject,f.stream);assert.equal(f.states.at(-1).name,'ready');
 f.camera.stop();assert.equal(f.stops(),1);assert.equal(f.video.srcObject,null);assert.equal(f.camera.ready(),false);
});
test('unanswered permission does not start duplicate requests; late permission is released after leaving',async()=>{
 let grant,requests=0;const f=fixture(()=>{requests++;return new Promise(resolve=>grant=resolve);});
 const first=f.camera.start(),second=f.camera.start();await Promise.resolve();assert.equal(requests,1);
 f.camera.stop();grant(f.stream);assert.equal(await first,false);assert.equal(await second,false);assert.equal(f.stops(),1);assert.equal(f.video.hidden,true);
});
test('denied access is recoverable and a later retry can start',async()=>{
 let denied=true;const f=fixture(async()=>{if(denied)throw Object.assign(Error(),{name:'NotAllowedError'});return f.stream;});
 assert.equal(await f.camera.start(),false);assert.match(f.states.at(-1).message,/site settings/);
 denied=false;assert.equal(await f.camera.start(),true);
});
test('synchronous device failure does not leave a permanently pending request',async()=>{
 let calls=0;const f=fixture(()=>{calls++;throw Object.assign(Error(),{name:'NotReadableError'});});
 await f.camera.start();await f.camera.start();assert.equal(calls,2);assert.match(f.states.at(-1).message,/elsewhere/);
});
test('frames are unavailable until video data arrives and a track ending clears the preview',async()=>{
 const f=fixture();f.video.readyState=1;assert.equal(await f.camera.start(),false);assert.equal(f.camera.ready(),false);
 f.video.readyState=2;f.events.loadeddata();assert.equal(f.states.at(-1).name,'ready');
 f.track.dispatchEvent(new Event('ended'));assert.equal(f.camera.ready(),false);assert.equal(f.video.hidden,true);assert.match(f.states.at(-1).message,/stopped/);
});
test('autoplay failure releases the camera and asks for an explicit retry',async()=>{
 const f=fixture();f.video.play=async()=>{throw Error('gesture required');};
 assert.equal(await f.camera.start(),false);assert.equal(f.stops(),1);assert.match(f.states.at(-1).message,/Tap Open camera/);
});
test('unsupported browser preserves photo fallback instead of throwing',async()=>{
 const f=fixture(),states=[];const camera=createCamera(f.video,{mediaDevices:null,onState:(...state)=>states.push(state)});
 assert.equal(await camera.start(),false);assert.match(states.at(-1)[1],/phone camera or choose/);
});
test('captured JPEG retains the full frame and fits the edge bound without sending anything',async()=>{
 const f=fixture();f.video.videoWidth=4000;f.video.videoHeight=3000;const drawn=[];
 const canvas={getContext:()=>({drawImage:(...args)=>drawn.push(args)}),toBlob:(callback,type,quality)=>{assert.equal(type,'image/jpeg');assert.equal(quality,.92);callback(new Blob(['frame'],{type}));}};
 const file=await captureFrame(f.video,{createCanvas:()=>canvas});assert.equal(canvas.width,1800);assert.equal(canvas.height,1350);
 assert.equal(drawn[0][0],f.video);assert.deepEqual(drawn[0].slice(1),[0,0,1800,1350]);assert.equal(file.type,'image/jpeg');
});
test('no frame, no canvas or failed encoding never creates a photo',async()=>{
 const f=fixture();f.video.readyState=1;await assert.rejects(()=>captureFrame(f.video),/Wait for the camera/);
 f.video.readyState=2;await assert.rejects(()=>captureFrame(f.video,{createCanvas:()=>({getContext:()=>null})}),/could not take/);
 await assert.rejects(()=>captureFrame(f.video,{createCanvas:()=>({getContext:()=>({drawImage(){}}),toBlob:callback=>callback(null)})}),/could not be captured/);
});

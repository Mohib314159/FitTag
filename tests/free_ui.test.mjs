import {test,before} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {parseHTML} from 'linkedom';

let document,window,memory,requests=[],responses=[],jobResult,pendingStatus=null;
const demo=JSON.parse(fs.readFileSync(new URL('../web/free-demo.json',import.meta.url),'utf8'));
const fixture=()=>({...structuredClone(demo),demo:false});
before(async()=>{
 ({document,window}=parseHTML(fs.readFileSync(new URL('../web/index.html',import.meta.url),'utf8')));
 Object.assign(globalThis,{document,window,matchMedia:()=>({matches:false})});
 Object.defineProperty(globalThis,'navigator',{configurable:true,value:{onLine:true}});
 memory=new Map();globalThis.localStorage={getItem:key=>memory.get(key)||null,setItem:(key,value)=>memory.set(key,value),removeItem:key=>memory.delete(key)};
 window.HTMLElement.prototype.scrollIntoView=function(){};
 window.HTMLElement.prototype.focus=function(){};
 window.HTMLInputElement.prototype.checkValidity=function(){return Number.isFinite(Number(this.value))&&Number(this.value)>=Number(this.min)&&Number(this.value)<=Number(this.max);};
 // Linkedom has a getter-only select.value; model the native selection property.
 for(const id of ['kind','method','anchorPoint'])Object.defineProperty(document.getElementById(id),'value',{configurable:true,writable:true,value:id==='kind'?'jeans':id==='method'?'depth':'waist_flat'});
 globalThis.fetch=async(path,options)=>{
  if(path==='./experiment')return {ok:true,json:async()=>({depth_model:true})};
  if(path==='./health')return {ok:true};
  if(path==='./free-demo.json')return {ok:true,json:async()=>structuredClone(demo)};
  requests.push({path,options});
  if(path==='./measure-free-jobs'){jobResult=responses.shift()??fixture();return {ok:true,json:async()=>({ok:true,status_url:'/measurement-jobs/'+ 'a'.repeat(32)})};}
  if(options?.method==='DELETE')return {ok:true,json:async()=>({status:'cancelled'})};
  if(pendingStatus)return pendingStatus(options.signal);
  return {ok:true,json:async()=>({ok:true,status:'succeeded',result:jobResult})};
 };
 await import('../web/free.js');
});
const $=id=>document.getElementById(id);
function choose(size=100){const file=new File(['x'],'test.jpg',{type:'image/jpeg'});Object.defineProperty(file,'size',{value:size});$('upload').onchange({target:{files:[file]}});}

test('model example labels scale failure and never renders NaN',async()=>{
 await $('demo').onclick();assert.equal($('results').hidden,false);assert.match($('confidence').textContent,/Estimated size/);assert.match($('demoTruth').textContent,/41.0 cm/);assert.doesNotMatch($('measurements').textContent,/NaN/);assert.equal($('save').disabled,true);
});
test('anchor, undo, units and line highlight execute real client handlers',()=>{
 $('anchorPoint').value='waist_flat';$('anchorCm').value='41';$('anchorApply').onclick();assert.match($('measurements').textContent,/41.0 cm/);assert.match($('confidence').textContent,/Size set/);$('inches').onclick();assert.match($('measurements').textContent,/16.1 in/);$('cm').onclick();const inseam=[...$('measurements').querySelectorAll('button')].find(b=>b.textContent==='Inseam');inseam.onclick({detail:0});assert.match($('overlayCaption').textContent,/Inseam/);$('anchorReset').onclick();assert.match($('confidence').textContent,/Estimated size/);assert.match($('measurements').textContent,/74.2 cm/);
});
test('endpoint edits require rechecking and can restore the detected line',async()=>{
 await $('demo').onclick();$('confirm').checked=true;$('confirm').onchange();
 const waist=[...$('measurements').querySelectorAll('button')].find(b=>b.textContent==='Waist · flat');waist.onclick({detail:0});
 const before=$('measurements').textContent,handle=$('lines').querySelector('[data-endpoint="p2"]');
 handle.onkeydown({key:'ArrowRight',preventDefault(){}});
 assert.notEqual($('measurements').textContent,before);assert.equal($('confirm').checked,false);assert.equal($('save').disabled,true);assert.match($('confidence').textContent,/Estimated size/);
 $('undoEdits').onclick();assert.equal($('measurements').textContent,before);
});
test('copied listing keeps the caveat attached to a model guess',async()=>{
 let copied='';navigator.clipboard={writeText:async text=>{copied=text;}};await $('copyListing').onclick();assert.match(copied,/Check with a tape/);assert.match(copied,/not body circumference/);assert.match($('copyStatus').textContent,/sizes need checking/);
});
test('photo review precedes upload and real form includes selected mode',async()=>{
 $('again').onclick();choose();assert.equal($('preview').hidden,false);const before=requests.length;$('method').value='shape';$('method').onchange();responses.push({...fixture(),mode:'shape',rows:[{name:'waist_flat',ratio:.5,p1:[1,2],p2:[3,4]},{name:'inseam',ratio:1,p1:[1,2],p2:[3,4]}]});await $('measure').onclick();assert.equal(requests.length,before+2);const req=requests.findLast(r=>r.path==='./measure-free-jobs');assert.equal(req.path,'./measure-free-jobs');assert.equal(req.options.body.get('estimate'),'false');assert.match($('measurements').textContent,/50.0%/);assert.doesNotMatch($('measurements').textContent,/cm|NaN/);assert.equal($('units').hidden,true);
});
test('only acknowledged readouts save, and saved data contains no photo',()=>{
 $('save').onclick();assert.equal(memory.size,0);$('confirm').checked=true;$('confirm').onchange();assert.equal($('save').disabled,false);$('save').onclick();const saved=JSON.parse(memory.get('fittag-lab-saved'));assert.equal(saved[0].mode,'shape');assert.equal('overlay_url'in saved[0],false);assert.equal('photo'in saved[0],false);assert.match($('saveStatus').textContent,/saved on this device/);$('forget').onclick();assert.equal(memory.size,0);
});
test('offline, bad distance and oversized combined photos never upload',async()=>{
 $('again').onclick();choose();const before=requests.length;navigator.onLine=false;await $('measure').onclick();assert.equal(requests.length,before);assert.match($('errorText').textContent,/Connect/);navigator.onLine=true;$('method').value='distance';$('cameraHeight').value='';await $('measure').onclick();assert.equal(requests.length,before);assert.match($('errorText').textContent,/known lens-to-floor/);$('method').value='depth';choose(9*1024*1024);const other=new File(['x'],'second.jpg',{type:'image/jpeg'});Object.defineProperty(other,'size',{value:9*1024*1024});$('secondFile').onchange({target:{files:[other]}});await $('measure').onclick();assert.equal(requests.length,before);assert.match($('errorText').textContent,/combined photos/);
});

test('waiting screen uses the selected photo and cancel preserves it',async()=>{
 $('again').onclick();choose();$('method').value='shape';
 pendingStatus=signal=>new Promise((resolve,reject)=>{signal.addEventListener('abort',()=>reject(new DOMException('Cancelled','AbortError')),{once:true});});
 const run=$('measure').onclick();
 for(let i=0;i<10;i++)await Promise.resolve();
 assert.equal($('processing').hidden,false);
 assert.equal($('processingPhoto').src,$('preview').src);
 assert.match($('processingTitle').textContent,/Sending/);
 assert.equal($('processing').querySelector('[role=progressbar]').hasAttribute('aria-valuenow'),false);
 $('cancel').onclick();await run;pendingStatus=null;
 assert.equal($('capture').hidden,false);assert.equal($('preview').hidden,false);
 assert.equal($('error').hidden,true);
 assert.ok(requests.some(r=>r.options?.method==='DELETE'));
});

test('several selected photos produce separate reviewable results and keep edits on return',async()=>{
 $('method').value='shape';$('kind').value='jeans';
 // Native select.value has a setter; Linkedom's dynamically created selects do not.
 const create=document.createElement.bind(document);
 document.createElement=tag=>{const el=create(tag);if(tag==='select')Object.defineProperty(el,'value',{configurable:true,writable:true,value:'jeans'});return el;};
 $('openBatch').onclick();
 const files=[new File(['a'],'first.jpg',{type:'image/jpeg'}),new File(['b'],'second.jpg',{type:'image/jpeg'})];
 await $('batchFiles').onchange({target:{files}});
 assert.equal($('batch').hidden,false);assert.match($('batchList').textContent,/first.jpg/);
 assert.equal($('batchRead').disabled,false);
 await $('batchRead').onclick();assert.match($('batchStatus').textContent,/2 of 2 ready/);
 assert.equal($('batchRead').hidden,true);
 const open=$('batchList').querySelector('button');open.onclick();
 assert.equal($('results').hidden,false);assert.equal($('returnBatch').hidden,false);
 $('anchorPoint').value='waist_flat';$('anchorCm').value='41';$('anchorApply').onclick();
 $('itemName').value='Everyday pair';$('itemName').oninput();$('inches').onclick();
 $('returnBatch').onclick();$('batchList').querySelector('button').onclick();
 assert.match($('measurements').textContent,/16.1 in/);assert.equal($('itemName').value,'Everyday pair');assert.equal($('inches').getAttribute('aria-pressed'),'true');$('cm').onclick();
 document.createElement=create;
});

test('changing a reviewed photo offers the library and camera and keeps it until replaced',()=>{
 $('again').onclick();choose();const original=$('preview').src,dialog=$('changeDialog');
 dialog.showModal=()=>dialog.open=true;dialog.close=()=>dialog.open=false;
 let opened='';$('camera').click=()=>opened='camera';$('upload').click=()=>opened='library';
 $('take').onclick();assert.equal(dialog.open,true);assert.equal($('preview').src,original);
 $('changeLibrary').onclick();assert.equal(opened,'library');assert.equal(dialog.open,false);assert.equal($('preview').src,original);
 $('take').onclick();$('changeCamera').onclick();assert.equal(opened,'camera');
 $('take').onclick();$('clear').onclick();assert.equal(dialog.open,false);assert.equal($('preview').hidden,true);assert.equal($('measure').hidden,true);
});

test('the example teaches setting a known measurement using the actual correction flow',async()=>{
 await $('demo').onclick();assert.equal($('demoScale').hidden,false);
 $('demoScale').onclick();assert.match($('measurements').textContent,/41.0 cm/);assert.match($('confidence').textContent,/Size set/);
});
test('a local black-photo refusal prevents all measurement uploads',async()=>{
 $('again').onclick();const count=requests.length;
 const create=document.createElement.bind(document);
 document.createElement=tag=>{if(tag==='canvas')return {width:0,height:0,getContext:()=>({drawImage(){},getImageData:()=>({width:8,height:8,data:new Uint8ClampedArray(256)})}),toBlob:fn=>fn(null)};return create(tag);};
 globalThis.createImageBitmap=async()=>({width:8,height:8,close(){}});
 choose();await $('measure').onclick();
 assert.equal(requests.length,count);assert.match($('photoCheck').textContent,/dark/);assert.equal($('measure').disabled,true);
 delete globalThis.createImageBitmap;document.createElement=create;
});

test('the illustrated preview and garment controls work without sending a photo',()=>{
 $('again').onclick();const count=requests.length;
 $('guideLines').onclick();assert.equal($('illustration').classList.contains('is-lines'),true);assert.equal($('guideLines').getAttribute('aria-pressed'),'true');
 $('guidePhoto').onclick();assert.equal($('illustration').classList.contains('is-lines'),false);
 $('kindTop').onclick();assert.equal($('kind').value,'t-shirt');assert.equal($('topDrawing').hasAttribute('hidden'),false);assert.equal($('jeansDrawing').hasAttribute('hidden'),true);assert.match($('layoutGuide').textContent,/sleeves/);
 $('kindJeans').onclick();assert.equal($('kind').value,'jeans');assert.equal($('kindJeans').getAttribute('aria-pressed'),'true');assert.equal(requests.length,count);
});

test('the photo-side measurement picker reflects endpoint edits and unit conversion',async()=>{
 await $('demo').onclick();$('cm').onclick();
 $('linePicker').querySelector('button').onclick({detail:0});
 assert.equal($('linePicker').querySelector('button').getAttribute('aria-pressed'),'true');
 const before=$('linePicker').textContent;
 $('lines').querySelector('[data-endpoint="p2"]').onkeydown({key:'ArrowRight',preventDefault(){}});
 assert.notEqual($('linePicker').textContent,before);assert.match($('overlayCaption').textContent,/Waist/);
 $('inches').onclick();assert.match($('linePicker').textContent,/in/);assert.match($('resultScaleHint').textContent,/Estimated/);
});

test('saved measurements retain units, copy their caveat, and undo removal without photos',async()=>{
 await $('demo').onclick();$('inches').onclick();$('itemName').value='Practice pair';$('confirm').checked=true;$('save').onclick();
 const data=JSON.parse(memory.get('fittag-lab-saved'));assert.equal(data[0].unit,'in');assert.equal('overlay_url'in data[0],false);
 $('openSaved').onclick();assert.equal($('saved').hidden,false);assert.match($('savedList').textContent,/Practice pair/);assert.match($('savedList').textContent,/in/);
 let copied='';navigator.clipboard={writeText:async text=>{copied=text;}};
 const actions=$('savedList').querySelector('.saved-actions');await actions.children[0].onclick();assert.match(copied,/Check with a tape/);assert.match(copied,/in/);
 actions.children[1].onclick();assert.equal(JSON.parse(memory.get('fittag-lab-saved')).length,0);assert.equal($('restoreSaved').hidden,false);
 $('restoreSaved').onclick();assert.equal(JSON.parse(memory.get('fittag-lab-saved'))[0].name,'Practice pair');assert.equal($('restoreSaved').hidden,true);
 $('forget').onclick();assert.equal(memory.size,0);assert.match($('savedList').textContent,/favourite pieces/);$('savedBack').onclick();assert.equal($('capture').hidden,false);
});

test('saving a new item invalidates an old undo rather than overwriting the new measurements',async()=>{
 await $('demo').onclick();$('itemName').value='New example';$('confirm').checked=true;$('save').onclick();assert.equal($('restoreSaved').hidden,true);
 $('restoreSaved').onclick();const data=JSON.parse(memory.get('fittag-lab-saved'));assert.equal(data.length,1);assert.equal(data[0].name,'New example');$('forget').onclick();
});

test('reading the example resets unrelated garment, scale and second-photo choices before upload',async()=>{
 $('again').onclick();choose();$('method').value='distance';$('kindTop').onclick();$('customFov').checked=true;
 $('secondFile').onchange({target:{files:[new File(['x'],'old-second.jpg',{type:'image/jpeg'})]}});
 const original=globalThis.fetch,count=requests.length;$('helpDialog').close=()=>{};
 globalThis.fetch=async(path,options)=>path==='./example-jeans.jpg'?{ok:true,blob:async()=>new Blob(['example'],{type:'image/jpeg'})}:original(path,options);
 await $('helpPhoto').onclick();globalThis.fetch=original;
 assert.equal($('kind').value,'jeans');assert.equal($('method').value,'depth');assert.equal($('customFov').checked,false);assert.equal($('secondClear').hidden,true);assert.equal(requests.length,count);assert.equal($('preview').hidden,false);
});

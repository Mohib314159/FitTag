import {test,before} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {parseHTML} from 'linkedom';

let document,window,memory,requests=[],responses=[];
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
  if(path==='./free-demo.json')return {ok:true,json:async()=>structuredClone(demo)};
  requests.push({path,options});const body=responses.shift();return {ok:true,json:async()=>body??fixture()};
 };
 await import('../web/free.js');
});
const $=id=>document.getElementById(id);
function choose(size=100){const file=new File(['x'],'test.jpg',{type:'image/jpeg'});Object.defineProperty(file,'size',{value:size});$('upload').onchange({target:{files:[file]}});}

test('model example labels scale failure and never renders NaN',async()=>{
 await $('demo').onclick();assert.equal($('results').hidden,false);assert.match($('confidence').textContent,/Research guess/);assert.match($('demoTruth').textContent,/41.0 cm/);assert.doesNotMatch($('measurements').textContent,/NaN/);assert.equal($('save').disabled,true);
});
test('anchor, undo, units and line highlight execute real client handlers',()=>{
 $('anchorPoint').value='waist_flat';$('anchorCm').value='41';$('anchorApply').onclick();assert.match($('measurements').textContent,/41.0 cm/);assert.match($('confidence').textContent,/anchored/);$('inches').onclick();assert.match($('measurements').textContent,/16.1 in/);$('cm').onclick();const inseam=[...$('measurements').querySelectorAll('button')].find(b=>b.textContent==='Inseam');inseam.onclick({detail:0});assert.match($('overlayCaption').textContent,/Inseam/);$('anchorReset').onclick();assert.match($('confidence').textContent,/Research guess/);assert.match($('measurements').textContent,/74.2 cm/);
});
test('endpoint edits require rechecking and can restore the detected line',async()=>{
 await $('demo').onclick();$('confirm').checked=true;$('confirm').onchange();
 const waist=[...$('measurements').querySelectorAll('button')].find(b=>b.textContent==='Waist · flat');waist.onclick({detail:0});
 const before=$('measurements').textContent,handle=$('lines').querySelector('[data-endpoint="p2"]');
 handle.onkeydown({key:'ArrowRight',preventDefault(){}});
 assert.notEqual($('measurements').textContent,before);assert.equal($('confirm').checked,false);assert.equal($('save').disabled,true);assert.match($('confidence').textContent,/Research guess/);
 $('undoEdits').onclick();assert.equal($('measurements').textContent,before);
});
test('copied listing keeps the caveat attached to a model guess',async()=>{
 let copied='';navigator.clipboard={writeText:async text=>{copied=text;}};await $('copyListing').onclick();assert.match(copied,/Unverified model estimates/);assert.match(copied,/not body circumference/);assert.match($('copyStatus').textContent,/limitations included/);
});
test('photo review precedes upload and real form includes selected mode',async()=>{
 $('again').onclick();choose();assert.equal($('preview').hidden,false);const before=requests.length;$('method').value='shape';$('method').onchange();responses.push({...fixture(),mode:'shape',rows:[{name:'waist_flat',ratio:.5,p1:[1,2],p2:[3,4]},{name:'inseam',ratio:1,p1:[1,2],p2:[3,4]}]});await $('measure').onclick();assert.equal(requests.length,before+1);const req=requests.at(-1);assert.equal(req.path,'./measure-free');assert.equal(req.options.body.get('estimate'),'false');assert.match($('measurements').textContent,/50.0%/);assert.doesNotMatch($('measurements').textContent,/cm|NaN/);assert.equal($('units').hidden,true);
});
test('only acknowledged readouts save, and saved data contains no photo',()=>{
 $('save').onclick();assert.equal(memory.size,0);$('confirm').checked=true;$('confirm').onchange();assert.equal($('save').disabled,false);$('save').onclick();const saved=JSON.parse(memory.get('fittag-lab-saved'));assert.equal(saved[0].mode,'shape');assert.equal('overlay_url'in saved[0],false);assert.equal('photo'in saved[0],false);assert.match($('saveStatus').textContent,/saved locally/);$('forget').onclick();assert.equal(memory.size,0);
});
test('offline, bad distance and oversized combined photos never upload',async()=>{
 $('again').onclick();choose();const before=requests.length;navigator.onLine=false;await $('measure').onclick();assert.equal(requests.length,before);assert.match($('errorText').textContent,/Connect/);navigator.onLine=true;$('method').value='distance';$('cameraHeight').value='';await $('measure').onclick();assert.equal(requests.length,before);assert.match($('errorText').textContent,/known lens-to-floor/);$('method').value='depth';choose(9*1024*1024);const other=new File(['x'],'second.jpg',{type:'image/jpeg'});Object.defineProperty(other,'size',{value:9*1024*1024});$('secondFile').onchange({target:{files:[other]}});await $('measure').onclick();assert.equal(requests.length,before);assert.match($('errorText').textContent,/combined photos/);
});

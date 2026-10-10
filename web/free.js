import {labels,validateFile,formatValue} from './client.mjs';
import {anchorResult,rowText,resultMessage,moveEndpoint,listingText} from './free.mjs';
import {measurePhoto,stages} from './request.mjs';
import {checkPhoto} from './photo-check.mjs';
import {runBatch} from './batch.mjs';
const $=id=>document.getElementById(id);
let file=null,second=null,previewURL=null,current=null,baseResult=null,geometry=null,drag=null,unit='cm',active=null,run=0,controller=null,installPrompt=null,backend=null,jobURL=null;
let quality=null,qualityPromise=Promise.resolve(),secondQuality=null,secondPromise=Promise.resolve(),batchItems=[],batchController=null,batchConcurrency=1,fromBatch=false,batchViewing=null,exampleInput=null,removedSaved=null;
const timerController=new AbortController(),healthTimeout=setTimeout(()=>timerController.abort(),10000);
fetch('./experiment',{signal:timerController.signal}).then(async r=>{backend=r.ok;if(!r.ok)$('modeNotice').hidden=false;else {const config=await r.json();batchConcurrency=Math.max(1,Math.min(2,config.parallel_photos||1));}}).catch(()=>{}).finally(()=>clearTimeout(healthTimeout));
function show(name){for(const id of ['capture','processing','results','batch','saved'])$(id).hidden=id!==name;document.body.classList.toggle('is-processing',name==='processing');$('error').hidden=true;window.scrollTo?.({top:0,behavior:'instant'});}
function processingStage(stage){const [title,text]=stages[stage]||stages.finishing;$('processingTitle').textContent=title;$('progressText').textContent=text;$('processing').dataset.stage=stage;for(const step of $('processingSteps').children)step.setAttribute('aria-current',String(step.dataset.phase===(['connecting','uploading'].includes(stage)?'send':stage==='finishing'?'ready':'read')));}
function error(message){$('errorText').textContent=message;$('error').hidden=false;$('error').focus();}
function captureCopy(selected=false){$('captureHeading').innerHTML=selected?'A closer look.':'Your clothes,<br><em>in detail.</em>';$('captureLead').textContent=selected?'Check every edge, then read your photo.':'Take a photo. Find the lines. Check the size.';}
function selected(next){exampleInput=null;const problem=validateFile(next);if(problem)return error(problem);clearSecond();if(previewURL)URL.revokeObjectURL(previewURL);file=next;previewURL=URL.createObjectURL(file);$('preview').src=previewURL;$('preview').hidden=false;$('illustration').hidden=true;$('selectedLabel').hidden=false;$('capture').classList.add('has-photo');$('viewfinder').removeAttribute('role');$('viewfinder').removeAttribute('tabindex');$('captureTitle').textContent='Every edge visible? Read the photo.';quality=null;captureCopy(true);$('measure').disabled=true;$('photoCheck').hidden=false;$('photoCheck').textContent='Checking photo…';qualityPromise=checkPhoto(next).then(result=>{if(file!==next)return;quality=result;$('photoCheck').textContent=result.message;$('photoCheck').dataset.level=result.level;$('measure').disabled=result.level==='stop';});$('measure').hidden=$('clear').hidden=false;$('take').textContent='Change photo';$('choose').textContent='Change photo';$('viewfinder').scrollIntoView({block:'start'});$('measure').focus({preventScroll:true});}
function clear(){if(previewURL)URL.revokeObjectURL(previewURL);file=null;previewURL=null;quality=null;captureCopy();exampleInput=null;$('photoCheck').hidden=true;$('preview').removeAttribute('src');$('preview').hidden=true;$('illustration').hidden=false;$('selectedLabel').hidden=true;$('capture').classList.remove('has-photo');$('viewfinder').setAttribute('role','button');$('viewfinder').tabIndex=0;$('captureTitle').textContent='Flat garment. Clear floor. Straight down.';$('measure').hidden=$('clear').hidden=true;$('camera').value=$('upload').value='';$('take').innerHTML='<span class="camera-symbol" aria-hidden="true"></span>Take photo';$('choose').textContent='Choose photo';clearSecond();}
function clearSecond(){second=null;secondQuality=null;$('secondFile').value='';$('secondStatus').textContent='Optional. Both photos upload only when you tap Read photo.';$('secondClear').hidden=true;}
$('take').onclick=()=>file?$('changeDialog').showModal():$('camera').click();$('closeChange').onclick=()=>$('changeDialog').close();for(const [id,input]of [['changeCamera','camera'],['changeLibrary','upload']])$(id).onclick=()=>{$('changeDialog').close();$(input).value='';$(input).click();};$('choose').onclick=()=>$('upload').click();for(const id of ['camera','upload'])$(id).onchange=e=>{if(e.target.files[0])selected(e.target.files[0]);};$('clear').onclick=()=>{$('changeDialog').close();clear();$('take').focus();};
$('secondChoose').onclick=()=>$('secondFile').click();$('secondClear').onclick=clearSecond;$('secondFile').onchange=e=>{const candidate=e.target.files[0];if(!candidate)return;const problem=validateFile(candidate);if(problem)return error(problem);second=candidate;secondQuality=null;$('secondStatus').textContent='Checking photo…';secondPromise=checkPhoto(candidate).then(result=>{if(second!==candidate)return;secondQuality=result;$('secondStatus').textContent=result.level==='stop'?result.message:'Second photo ready. Make sure it shows the same item.';});$('secondClear').hidden=false;};
$('method').onchange=()=>{$('distanceOptions').hidden=$('method').value!=='distance';$('secondOptions').hidden=$('method').value!=='depth';};
$('customFov').onchange=()=>$('fov').disabled=!$('customFov').checked;
$('kind').onchange=()=>{$('kindJeans').setAttribute('aria-pressed',String($('kind').value==='jeans'));$('kindTop').setAttribute('aria-pressed',String($('kind').value==='t-shirt'));$('jeansDrawing').toggleAttribute('hidden',$('kind').value!=='jeans');$('topDrawing').toggleAttribute('hidden',$('kind').value==='jeans');$('guideSource').textContent=$('kind').value==='jeans'?'Example · computer-made photo':'Illustrated photo guide';$('layoutGuide').textContent=$('kind').value==='jeans'?'Waistband at the top. Separate the legs and include both hems.':'Neckline at the top. Spread both sleeves and include the full hem.';};
for(const [id,value]of [['kindJeans','jeans'],['kindTop','t-shirt']])$(id).onclick=()=>{$('kind').value=value;$('kind').onchange();};
for(const [id,value]of [['guidePhoto',false],['guideLines',true]])$(id).onclick=()=>{$('illustration').classList.toggle('is-lines',value);$('guidePhoto').setAttribute('aria-pressed',String(!value));$('guideLines').setAttribute('aria-pressed',String(value));$('guideCaption').textContent=value?'See where the lines go':'A photo to start with';};
$('measure').onclick=async()=>{
 if(backend===false)return error('This is a static preview. Open the full experimental service; your photo has not been uploaded.');
 if(!navigator.onLine)return error('Connect to read a new photo. Nothing has been uploaded.');
 if(!file)return error('Choose a photo first.');
 const chosen=file;await qualityPromise;if(file!==chosen)return;
 if(quality?.level==='stop')return error(quality.message);
 if(second&&$('method').value==='depth'){await secondPromise;if(secondQuality?.level==='stop')return error(secondQuality.message);}
 if($('method').value==='distance'&&(!$('cameraHeight').value||!$('cameraHeight').checkValidity()))return error('Enter a known lens-to-floor distance between 35 and 350 cm.');
 if(file.size+($('method').value==='depth'&&second?second.size:0)>12*1024*1024)return error('The combined photos must be smaller than 12 MB.');
 if($('customFov').checked&&!$('fov').checkValidity())return error('Enter a diagonal field of view between 40 and 110 degrees.');
 if(controller)return;
 const token=++run,request=new AbortController();controller=request;jobURL=null;let requestJob=null;const timeout=setTimeout(()=>request.abort(),120000),slow=setTimeout(()=>{$('slowHint').hidden=false;},18000);
 const body=new FormData();body.append('file',file);body.append('garment_type',$('kind').value);body.append('fov_deg',$('customFov').checked?$('fov').value:'0');body.append('estimate',String($('method').value==='depth'));body.append('camera_height_cm',$('method').value==='distance'?$('cameraHeight').value:'0');if(second&&$('method').value==='depth')body.append('second',second);
 show('processing');$('processingPhoto').src=previewURL;$('slowHint').hidden=true;processingStage('connecting');$('processingTitle').focus();
 try{const data=await measurePhoto(body,{signal:request.signal,onStage:stage=>{if(token===run)processingStage(stage);},onJob:url=>{requestJob=url;if(token===run)jobURL=url;if(token!==run)fetch(url,{method:'DELETE',keepalive:true}).catch(()=>{});}});if(token===run){if(exampleInput)data.demo=true,data.demo_truth_cm=exampleInput;fromBatch=false;render(data);}}
 catch(e){if(token===run){show('capture');error(e.name==='AbortError'?'The request timed out. Your photo is still selected.':e instanceof TypeError?'The connection was interrupted. Your photo is still selected. Try again when you are connected.':e.message);}}
 finally{clearTimeout(timeout);clearTimeout(slow);if(request.signal.aborted&&requestJob)fetch(requestJob,{method:'DELETE',keepalive:true}).catch(()=>{});if(token===run){controller=null;jobURL=null;}}
};
$('cancel').onclick=()=>{++run;controller?.abort();if(jobURL)fetch(jobURL,{method:'DELETE',keepalive:true}).catch(()=>{});controller=null;jobURL=null;show('capture');$('measure').focus();};$('again').onclick=()=>{fromBatch=false;show('capture');clear();$('take').focus();};
function selectLine(name,scroll=false){active=active===name?null:name;table();lines();if(scroll&&matchMedia('(max-width:680px)').matches)$('overlay').scrollIntoView({block:'center',behavior:matchMedia('(prefers-reduced-motion:reduce)').matches?'auto':'smooth'});}
function table(){
 const focusedLine=document.activeElement?.getAttribute('data-line'),pickerOffset=$('linePicker').scrollLeft||0;$('linePicker').replaceChildren();
 for(const row of current.rows){const button=document.createElement('button'),value=document.createElement('strong');button.textContent=labels[row.name]||row.name;value.textContent=rowText(row,unit);button.append(value);button.setAttribute('aria-pressed',String(active===row.name));button.setAttribute('data-line',row.name);button.onclick=e=>selectLine(row.name,e.detail>0);$('linePicker').append(button);if(focusedLine===row.name)button.focus({preventScroll:true});}$('linePicker').scrollLeft=pickerOffset;
 $('measurements').replaceChildren();$('units').hidden=current.mode==='shape';$('tableTitle').textContent=current.mode==='shape'?'Proportions':current.mode==='anchored'?'Measurements':current.mode==='distance'?'Estimated sizes':'Estimated sizes';$('ratioBasis').textContent=current.mode==='shape'?`${current.garment_type==='jeans'?'Inseam':'Garment length'} = 100%. These are ratios, not centimetres.`:'';
 for(const row of current.rows){const tr=document.createElement('tr'),th=document.createElement('th'),td=document.createElement('td'),button=document.createElement('button');th.scope='row';button.className='measurement-link';button.textContent=labels[row.name]||row.name;button.setAttribute('aria-pressed',String(active===row.name));button.onclick=e=>selectLine(row.name,e.detail>0);th.append(button);td.textContent=rowText(row,unit);if(row.tolerance_cm!==undefined){const small=document.createElement('small');small.textContent=` ±${formatValue(row.tolerance_cm,unit)} ${unit}`;td.append(small);}tr.append(th,td);$('measurements').append(tr);}
}
function lines(){const focusEndpoint=document.activeElement?.getAttribute('data-endpoint');const svg=$('lines');svg.removeAttribute('aria-hidden');svg.setAttribute('role','group');svg.setAttribute('aria-label','Garment measurement lines');$('editHint').hidden=!active;svg.replaceChildren();const [w,h]=current.image_size;svg.setAttribute('viewBox',`0 0 ${w} ${h}`);const make=(tag,attrs)=>{const el=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [key,value]of Object.entries(attrs))el.setAttribute(key,value);return el;};for(const row of current.rows){const color=active===row.name?'#fffefa':'#e3be4b',g=make('g',{opacity:active&&active!==row.name?'.22':'1'});g.append(make('line',{x1:row.p1[0],y1:row.p1[1],x2:row.p2[0],y2:row.p2[1],stroke:color,'stroke-width':active===row.name?'3':'2','vector-effect':'non-scaling-stroke'}));const hit=make('line',{x1:row.p1[0],y1:row.p1[1],x2:row.p2[0],y2:row.p2[1],stroke:'transparent','stroke-width':'24','vector-effect':'non-scaling-stroke','pointer-events':'stroke'});hit.onclick=()=>{active=active===row.name?null:row.name;table();lines();};g.append(hit);for(const [index,p]of [row.p1,row.p2].entries()){const dot=make('circle',{cx:p[0],cy:p[1],r:Math.max(w,h)*.006,fill:color});g.append(dot);if(active===row.name){const handle=make('circle',{cx:p[0],cy:p[1],r:24*w/(svg.getBoundingClientRect?.().width||Math.max(w,h)*.4),fill:'transparent',class:'endpoint','data-endpoint':index===0?'p1':'p2',tabindex:'0',role:'button','aria-label':`${index===0?'Start':'End'} of ${labels[row.name]||row.name}; arrow keys adjust`,'pointer-events':'all'});handle.onkeydown=e=>{const steps={ArrowLeft:[-5,0],ArrowRight:[5,0],ArrowUp:[0,-5],ArrowDown:[0,5]},delta=steps[e.key];if(delta){e.preventDefault();correct(row.name,index===0?'p1':'p2',[p[0]+delta[0],p[1]+delta[1]],geometry);}};g.append(handle);}}svg.append(g);}if(focusEndpoint)svg.querySelector(`[data-endpoint="${focusEndpoint}"]`)?.focus?.({preventScroll:true});const row=current.rows.find(r=>r.name===active);const caption=$('overlayCaption');caption.replaceChildren();if(row){const label=document.createElement('span'),value=document.createElement('strong');label.textContent=labels[row.name]||row.name;value.textContent=rowText(row,unit);caption.append(label,value);}else caption.textContent='Choose a measurement above to adjust its line.';}
function rememberBatchReview(){if(fromBatch&&batchViewing)batchViewing.review={baseResult,geometry,current,active,unit,pickerOffset:$('linePicker').scrollLeft||0,name:$('itemName').value};}
$('itemName').oninput=rememberBatchReview;
function update(){table();lines();rememberBatchReview();$('confidence').textContent=resultMessage(current);$('resultScaleHint').textContent=current.mode==='anchored'?'Size set by you. Check the other lines.':current.mode==='shape'?'No scale yet. These are proportions, not centimetres.':'Estimated sizes. Check with a tape before using them.';$('confirm').checked=false;$('save').disabled=true;$('saveStatus').textContent='';}
function render(data){$('returnBatch').hidden=!fromBatch;$('itemName').value='';$('copyStatus').textContent='';$('demoTruth').hidden=!data.demo;$('demoScale').hidden=!data.demo;$('demoTruth').textContent=data.demo?`Example jeans: waist ${(data.demo_truth_cm?.waist_flat||41).toFixed(1)} cm; estimated waist ${data.rows.find(r=>r.name==='waist_flat')?.value_cm?.toFixed(1)||'withheld'} cm. Check the estimate with a tape or enter a known length.`:'';baseResult=data;geometry=structuredClone(data);current=geometry;active=data.rows[0]?.name||null;$('linePicker').scrollLeft=0;show('results');$('resultTitle').textContent=data.mode==='shape'?'Check the proportions':'Check your measurements';$('resultTitle').focus();$('resultMode').textContent=data.demo?'Example · computer-made photo':'Your garment';$('overlay').src=data.overlay_url;$('anchorPoint').replaceChildren();for(const row of data.rows){const option=document.createElement('option');option.value=row.name;option.textContent=labels[row.name]||row.name;$('anchorPoint').append(option);}$('anchorCm').value='';$('anchorStatus').textContent='';$('anchorReset').hidden=true;$('notes').replaceChildren();for(const original of data.notes){const note=data.demo&&original.startsWith('Simulated garment')?'Example image made on a computer, with no button or reference object.':data.demo&&original.startsWith('Known synthetic flat waist')?'The example has a known size. Use it to practise checking and correcting an estimate.':original;const li=document.createElement('li');li.textContent=note;$('notes').append(li);}$('diagnostics').replaceChildren();const names={focal_source:'Camera focal length',diagonal_fov_deg:'Diagonal field of view',floor_depth_m:'Inferred floor depth (m)',camera_height_cm:'Supplied camera height (cm)',plane_residual_pct:'Floor median residual (%)',plane_p90_pct:'Floor 90th percentile residual (%)',tilt_deg:'Inferred floor tilt (°)',processing_seconds:'Processing time (s)'};for(const [key,label]of Object.entries(names)){if(data.diagnostics[key]===undefined)continue;const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=label;dd.textContent=String(data.diagnostics[key]);$('diagnostics').append(dt,dd);}$('crossCheck').hidden=!data.cross_check;if(data.cross_check)$('crossCheck').textContent=`Two-photo check: ${data.cross_check.difference_pct}% difference. ${data.cross_check.agreed?'They agree, but both estimates could still be wrong.':'They disagree. Showing proportions instead.'}`;update();}
$('anchorApply').onclick=()=>{try{current=anchorResult(geometry,$('anchorPoint').value,parseFloat($('anchorCm').value));update();$('anchorStatus').textContent='Size set from your measurement. Check the other lines too. The allowance beside each size is a guide, not a guarantee.';$('anchorReset').hidden=false;}catch(e){$('anchorStatus').textContent=e.message;}};
$('anchorReset').onclick=()=>{current=geometry;update();$('anchorStatus').textContent='Your measurement was removed.';$('anchorReset').hidden=true;};
$('confirm').onchange=()=>$('save').disabled=!$('confirm').checked;for(const [id,value]of [['cm','cm'],['inches','in']])$(id).onclick=()=>{unit=value;$('cm').setAttribute('aria-pressed',String(unit==='cm'));$('inches').setAttribute('aria-pressed',String(unit==='in'));table();lines();rememberBatchReview();};
$('demo').onclick=async()=>{fromBatch=false;try{const response=await fetch('./free-demo.json');if(!response.ok)throw Error();render(await response.json());}catch{error('The example could not load. Try again when you’re connected.');}};
function saved(){try{const data=JSON.parse(localStorage.getItem('fittag-lab-saved')||'[]');return Array.isArray(data)?data.filter(item=>item&&Array.isArray(item.rows)).slice(0,20):[];}catch{return [];}}
function savedList(){
 const list=$('savedList'),items=saved();list.replaceChildren();$('forget').hidden=!items.length;
 for(const [index,item]of items.entries()){
  const div=document.createElement('div'),name=document.createElement('span'),p=document.createElement('p'),actions=document.createElement('div');div.className='saved-item';actions.className='saved-actions';name.textContent=item.name||(item.demo?'Example garment':'Saved garment');p.textContent=item.rows.map(row=>`${labels[row.name]||row.name}: ${rowText(row,item.unit||'cm')}`).join(' · ');div.append(name,p);
  const meta=document.createElement('p');meta.className='saved-meta';meta.textContent=[item.demo?'Computer-made example':null,item.mode==='anchored'?'Size set by you':item.mode==='shape'?'Proportions':'Estimated sizes'].filter(Boolean).join(' · ');div.append(meta);
  const copy=document.createElement('button'),remove=document.createElement('button');copy.textContent='Copy measurements';remove.textContent='Remove';copy.onclick=async()=>{try{await navigator.clipboard.writeText(listingText(item,item.unit||'cm'));$('savedStatus').textContent='Copied with the size-checking note.';}catch{$('savedStatus').textContent='Copy isn’t available in this browser. Your measurements are still here.';}};
  remove.onclick=()=>{try{removedSaved=items;localStorage.setItem('fittag-lab-saved',JSON.stringify(items.filter((_,i)=>i!==index)));savedList();$('restoreSaved').hidden=false;$('savedStatus').textContent='Removed from this device. You can undo that.';}catch{error('Device storage is unavailable.');}};actions.append(copy,remove);div.append(actions);list.append(div);
 }
 if(!items.length){const empty=document.createElement('div'),title=document.createElement('p'),text=document.createElement('p'),start=document.createElement('button');empty.className='empty-saved';title.textContent='A place for your favourite pieces.';text.textContent='Check an item’s measurements, give it a name and save it here.';start.className='primary';start.textContent='Start with a photo';start.onclick=()=>show('capture');empty.append(title,text,start);list.append(empty);}
}
$('save').onclick=()=>{if(!$('confirm').checked)return;try{localStorage.setItem('fittag-lab-saved',JSON.stringify([{name:$('itemName').value.trim().slice(0,80),date:new Date().toISOString(),mode:current.mode,unit,garment_type:current.garment_type,demo:!!current.demo,rows:current.rows,anchor:current.anchor||null,edited:!!current.edited},...saved()].slice(0,20)));$('saveStatus').textContent='Measurements saved on this device. Photos are not saved.';$('save').disabled=true;removedSaved=null;$('restoreSaved').hidden=true;$('savedStatus').textContent='';savedList();}catch{$('saveStatus').textContent='Device storage is unavailable. Your result remains visible.';}};
$('forget').onclick=()=>{try{removedSaved=saved();localStorage.removeItem('fittag-lab-saved');savedList();$('restoreSaved').hidden=!removedSaved.length;$('savedStatus').textContent='Cleared from this device. You can undo that.';}catch{error('Device storage is unavailable.');}};
window.addEventListener('beforeinstallprompt',event=>{event.preventDefault();installPrompt=event;$('nativeInstall').hidden=false;});$('install').onclick=()=>$('installDialog').showModal();$('closeInstall').onclick=()=>$('installDialog').close();$('nativeInstall').onclick=async()=>{if(installPrompt){await installPrompt.prompt();installPrompt=null;$('nativeInstall').hidden=true;$('installDialog').close();}};
function network(){$('network').hidden=navigator.onLine;}window.addEventListener('online',network);window.addEventListener('offline',network);network();savedList();if('serviceWorker'in navigator)navigator.serviceWorker.register('./sw.js').catch(()=>{});

function correct(name,endpoint,point,source){
 try{const anchor=current.anchor;geometry=moveEndpoint(source,name,endpoint,point);current=anchor?anchorResult(geometry,anchor.name,anchor.cm):geometry;update();$('anchorStatus').textContent='Line adjusted. The estimated size still needs checking.';}
 catch{ /* A coincident endpoint is rejected; preserve the last usable line. */ }
}
$('lines').onpointerdown=e=>{const endpoint=e.target.getAttribute('data-endpoint');if(!endpoint||!active)return;e.preventDefault();drag={name:active,endpoint,source:structuredClone(geometry)};$('lines').setPointerCapture(e.pointerId);};
$('lines').onpointermove=e=>{if(!drag)return;const box=$('lines').getBoundingClientRect(),[w,h]=current.image_size;const p=[(e.clientX-box.left)*w/box.width,(e.clientY-box.top)*h/box.height];correct(drag.name,drag.endpoint,p,drag.source);const zoom=box.width/w*2.5;$('magnifier').hidden=false;$('magnifier').style.backgroundImage=`url(${JSON.stringify(current.overlay_url)})`;$('magnifier').style.backgroundSize=`${w*zoom}px ${h*zoom}px`;$('magnifier').style.backgroundPosition=`${45-p[0]*zoom}px ${45-p[1]*zoom}px`;};
$('lines').onpointerup=$('lines').onpointercancel=()=>{drag=null;$('magnifier').hidden=true;};
$('undoEdits').onclick=()=>{const anchor=current.anchor;geometry=structuredClone(baseResult);current=anchor?anchorResult(geometry,anchor.name,anchor.cm):geometry;update();$('anchorStatus').textContent='Original detected lines restored.';};

$('copyListing').onclick=async()=>{
 const text=listingText(current,unit);
 try{await navigator.clipboard.writeText(text);$('copyStatus').textContent='Copied, including a note that the sizes need checking.';}
 catch{$('copyStatus').textContent='Clipboard unavailable in this browser. Save the measurements on this device instead.';}
};

$('viewfinder').onclick=()=>{if(!file)$('upload').click();};
$('viewfinder').onkeydown=e=>{if(!file&&['Enter',' '].includes(e.key)){e.preventDefault();$('upload').click();}};
$('openSaved').onclick=()=>{savedList();show('saved');$('savedTitle').focus();};$('savedBack').onclick=()=>show('capture');$('restoreSaved').onclick=()=>{if(!removedSaved)return;try{localStorage.setItem('fittag-lab-saved',JSON.stringify(removedSaved));removedSaved=null;$('restoreSaved').hidden=true;$('savedStatus').textContent='Your saved measurements are back.';savedList();}catch{error('Device storage is unavailable.');}};

$('help').onclick=()=>$('helpDialog').showModal();
$('closeHelp').onclick=()=>$('helpDialog').close();
$('helpExample').onclick=()=>{$('helpDialog').close();$('demo').onclick();};
$('openBatch').onclick=()=>{show('batch');drawBatch();};
$('batchBack').onclick=()=>{show('capture');};
$('returnBatch').onclick=()=>{rememberBatchReview();fromBatch=false;show('batch');drawBatch();};
$('batchChoose').onclick=()=>{$('batchFiles').value='';$('batchFiles').click();};
function drawBatch(){
 $('batchList').replaceChildren();
 for(const item of batchItems){
  const row=document.createElement('div');row.className='batch-item';
  if(item.preview){const image=document.createElement('img');image.src=item.preview;image.alt='';row.append(image);}
  const text=document.createElement('div'),name=document.createElement('b'),status=document.createElement('p');
  name.textContent=item.review?.name||item.file.name;status.textContent=item.status==='done'?'Ready to check':item.status==='reading'?(item.message||'Reading photo…'):item.message||'Ready';text.append(name,status);if(!['done','stop'].includes(item.status)){const kind=document.createElement('select');kind.setAttribute('aria-label',`Garment in ${item.file.name}`);for(const [value,label] of [['jeans','Jeans / trousers'],['t-shirt','T-shirt']]){const option=document.createElement('option');option.value=value;option.textContent=label;kind.append(option);}kind.value=item.kind;kind.disabled=!!batchController;kind.onchange=()=>item.kind=kind.value;text.append(kind);}row.append(text);
  const button=document.createElement('button');button.className='quiet';
  if(item.status==='done'){button.textContent='Open';button.onclick=()=>openBatchResult(item);}
  else {button.textContent='Remove';button.disabled=!!batchController;button.onclick=()=>{if(item.preview)URL.revokeObjectURL(item.preview);batchItems=batchItems.filter(other=>other!==item);drawBatch();};}
  row.append(button);$('batchList').append(row);
 }
 $('batchRead').disabled=!!batchController||batchItems.some(item=>item.status==='checking')||!batchItems.some(item=>['queued','failed','cancelled'].includes(item.status));
 $('batchChoose').disabled=!!batchController||batchItems.some(item=>item.status==='checking');$('batchBack').disabled=!!batchController;
 $('batchCancel').hidden=!batchController;$('batchRead').hidden=batchItems.length>0&&batchItems.every(item=>item.status==='done');
}
$('batchFiles').onchange=async event=>{
 if(batchController)return;
 const files=[...event.target.files];if(files.length>6)return error('Choose up to six photos at a time.');
 if(files.reduce((sum,photo)=>sum+photo.size,0)>36*1024*1024)return error('Choose fewer photos. Keep this selection under 36 MB.');
 for(const item of batchItems)if(item.preview)URL.revokeObjectURL(item.preview);
 batchItems=files.map(photo=>({file:photo,status:'checking',message:'Checking photo…',kind:$('kind').value}));drawBatch();
 for(const item of batchItems){
  const problem=validateFile(item.file),check=problem?{level:'stop',message:problem}:await checkPhoto(item.file);
  item.status=check.level==='stop'?'stop':'queued';item.message=check.message;
  if(check.thumbnail)item.preview=URL.createObjectURL(check.thumbnail);
  drawBatch();
 }
 $('batchStatus').textContent='Photos stay on this device until you tap Read photos.';
};
$('batchRead').onclick=async()=>{
 if(batchController)return;if(!navigator.onLine)return error('Connect to read these photos. Nothing has been sent.');
 if(backend===false)return error('This preview cannot read your photos. Open the full app.');
 if($('method').value==='distance'&&(!$('cameraHeight').value||!$('cameraHeight').checkValidity()))return error('Enter the camera distance in Measurement options first.');
 if($('customFov').checked&&!$('fov').checkValidity())return error('Enter a diagonal field of view between 40 and 110 degrees.');
 const settings={method:$('method').value,fov:$('customFov').checked?$('fov').value:'0',height:$('cameraHeight').value};
 const controller=new AbortController();batchController=controller;
 for(const item of batchItems)if(['failed','cancelled'].includes(item.status)){item.status='queued';item.message='Ready';}
 drawBatch();$('batchStatus').textContent='Reading your photos. You can stop at any time.';
 const timeout=setTimeout(()=>controller.abort(),Math.max(120000,batchItems.length*90000));
 await runBatch(batchItems,{signal:controller.signal,concurrency:batchConcurrency,onChange:drawBatch,process:async(item,signal)=>{
  const body=new FormData();body.append('file',item.file);body.append('garment_type',item.kind);body.append('estimate',String(settings.method==='depth'));body.append('fov_deg',settings.fov);body.append('camera_height_cm',settings.method==='distance'?settings.height:'0');
  let url=null;
  try{return await measurePhoto(body,{signal,onJob:next=>{url=next;},onStage:stage=>{item.message=(stages[stage]||stages.finishing)[0];drawBatch();}});}
  finally{if(signal.aborted&&url)fetch(url,{method:'DELETE',keepalive:true}).catch(()=>{});}
 }});
 clearTimeout(timeout);batchController=null;drawBatch();
 const done=batchItems.filter(item=>item.status==='done').length;
 $('batchStatus').textContent=`${done} of ${batchItems.length} ready. Open each result to check the lines.`;
};
$('batchCancel').onclick=()=>batchController?.abort();

function openBatchResult(item){
 const previous=item.review;fromBatch=true;batchViewing=item;render(item.result);
 if(previous){({baseResult,geometry,current,active,unit}=previous);$('itemName').value=previous.name||'';$('linePicker').scrollLeft=previous.pickerOffset||0;$('cm').setAttribute('aria-pressed',String(unit==='cm'));$('inches').setAttribute('aria-pressed',String(unit==='in'));if(current.anchor){$('anchorCm').value=String(current.anchor.cm);$('anchorPoint').value=current.anchor.name;$('anchorReset').hidden=false;}update();}
}

$('demoScale').onclick=()=>{if(!current?.demo)return;$('anchorDetails').open=true;$('anchorPoint').value='waist_flat';$('anchorCm').value=String(current.demo_truth_cm?.waist_flat||41);$('anchorApply').onclick();$('tableTitle').scrollIntoView({block:'center',behavior:matchMedia('(prefers-reduced-motion:reduce)').matches?'auto':'smooth'});};

$('helpPhoto').onclick=async()=>{
 try{const [photo,info]=await Promise.all([fetch('./example-jeans.jpg'),fetch('./free-demo.json')]);if(!photo.ok||!info.ok)throw Error();const raw=await photo.blob(),data=await info.json();$('helpDialog').close();$('kind').value='jeans';$('kind').onchange();$('method').value='depth';$('method').onchange();$('customFov').checked=false;$('customFov').onchange();show('capture');selected(new File([raw],'Example jeans.jpg',{type:'image/jpeg'}));exampleInput=data.demo_truth_cm;}
 catch{error('The example photo could not load. Try again when you’re connected.');}
};

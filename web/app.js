import {labels, formatValue, validateFile, comparisonText} from './client.mjs';
const $ = id => document.getElementById(id);
let file = null, previewURL = null, current = null, unit = 'cm', controller = null, installPrompt = null, run = 0, active = null;
let backendAvailable = null;
const healthAbort = new AbortController(), healthTimeout = setTimeout(()=>healthAbort.abort(),10000);
fetch('./health',{signal:healthAbort.signal}).then(response=>{backendAvailable=response.ok;if(!response.ok)$('modeNotice').hidden=false;}).catch(()=>{}).finally(()=>clearTimeout(healthTimeout));
function show(id) { for (const name of ['capture','processing','results']) $(name).hidden = name !== id; $('error').hidden = true; }
function error(message) { $('errorText').textContent = message; $('error').hidden = false; $('error').focus(); }
function selected(next) {
  if (!next) return;
  const problem = validateFile(next); if (problem) return error(problem);
  if (previewURL) URL.revokeObjectURL(previewURL);
  file = next; previewURL = URL.createObjectURL(file); $('preview').src = previewURL;
  $('capture').classList.add('has-photo'); $('captureTitle').textContent='Check the photo. Then measure.';
  $('preview').hidden = false; $('illustration').hidden = true; $('selectedLabel').hidden = false;
  $('measure').hidden = false; $('clear').hidden = false; $('take').textContent = 'Retake photo'; $('choose').textContent = 'Change photo';
  $('error').hidden = true; $('viewfinder').scrollIntoView({block:'start'}); $('measure').focus({preventScroll:true});
}
function clear() {
  if(previewURL) URL.revokeObjectURL(previewURL);
  previewURL = null; file = null; $('preview').removeAttribute('src'); $('preview').hidden = true; $('illustration').hidden = false;
  $('capture').classList.remove('has-photo'); $('captureTitle').textContent='A little setup. A much better estimate.';
  $('selectedLabel').hidden = true; $('measure').hidden = true; $('clear').hidden = true;
  $('camera').value = ''; $('upload').value = ''; $('take').textContent = 'Take a photo ↗'; $('choose').textContent = 'Choose a photo';
}
$('take').onclick = () => $('camera').click(); $('choose').onclick = () => $('upload').click();
for (const id of ['camera','upload']) $(id).onchange = e => selected(e.target.files[0]);
$('clear').onclick = clear;
$('known').onchange = () => { $('diameter').disabled = !$('known').checked; if (!$('known').checked) $('diameter').value = '17'; };
function referenceChanged() {
  const top=$('kind').value==='t-shirt';if(top&&$('reference').value==='hardware')$('reference').value='a4';
  const ref=$('reference').value, hardware=ref==='hardware';$('buttonOptions').hidden=!hardware;$('fallbackHelp').hidden=hardware;
  $('captureKind').textContent=top?'T-shirt, laid flat':'Jeans, laid flat';
  $('jeansDrawing').toggleAttribute('hidden',top);$('topDrawing').toggleAttribute('hidden',!top);
  $('layoutGuide').textContent=top?'Neckline at the top. Keep both sleeves and the whole hem in view.':'Waistband at the top, both hems in view. Separate the legs.';
  $('scaleGuideTitle').textContent=hardware?'Keep the button clear.':'Include the scale reference.';
  $('scaleGuide').textContent=hardware?'Use a plain, contrasting surface and soft, even light.':ref==='mat'?'Keep the printed markers visible around the garment.':`Place ${ref==='card'?'the card':`a blank ${ref.toUpperCase()} sheet`} flat beside the garment, with every corner visible.`;
  $('frameTag').textContent=hardware?'01 / YOUR BUTTON BECOMES THE RULER':'01 / A KNOWN REFERENCE SETS THE SCALE';
}
$('reference').onchange = referenceChanged;
$('kind').onchange = () => { if ($('kind').value === 't-shirt' && $('reference').value === 'hardware') $('reference').value = 'a4'; referenceChanged(); };
$('measure').onclick = async () => {
  if (backendAvailable === false) return error('This is the static example. Open the full FitTag service to measure a photo. Your photo has not been uploaded.');
  if (!navigator.onLine) return error('You’re offline. Connect to measure this photo; it has not been uploaded.');
  if (!file) return error('Choose a photo first.');
  if ($('reference').value==='hardware'&&!$('diameter').checkValidity()) return error('Enter a button diameter between 10 and 30 mm.');
  const thisRun = ++run, requestController = new AbortController(); controller=requestController; const timeout = setTimeout(() => requestController.abort(), 120000);
  show('processing'); $('processingTitle').focus();
  const body = new FormData(); body.append('file',file); body.append('garment_type',$('kind').value); body.append('reference',$('reference').value);
  const measuredButton=$('reference').value==='hardware'&&$('known').checked;
  body.append('diameter_mm',measuredButton ? $('diameter').value : '17'); body.append('known_diameter',String(measuredButton));
  try {
    const response = await fetch('./measure',{method:'POST',body,signal:controller.signal});
    const data = await response.json().catch(() => { throw new Error('The server did not return a result. It may be waking up; try again shortly.'); });
    if (!response.ok || !data.ok) throw new Error(typeof data.detail === 'string' ? data.detail : data.error || 'Could not measure this image. Check your photo and try again.');
    if(thisRun === run) render(data);
  } catch (e) { if(thisRun === run) { show('capture'); error(e.name === 'AbortError' ? 'The request timed out. Your photo is still selected; try again.' : e.message); } }
  finally { clearTimeout(timeout); if(thisRun === run) controller = null; }
};
$('cancel').onclick = () => { ++run; controller?.abort(); controller = null; show('capture'); $('measure').focus(); };
$('again').onclick = () => { show('capture'); clear(); $('take').focus(); };
function table() {
  $('measurements').replaceChildren();
  for(const row of current.garment.measurements) {
    const tr = document.createElement('tr'), name = document.createElement('th'), value = document.createElement('td'), tolerance = document.createElement('small'), button = document.createElement('button');
    name.scope='row'; button.textContent = labels[row.name] || row.name.replaceAll('_',' '); button.className='measurement-link'; button.setAttribute('aria-pressed',String(active===row.name));
    button.onclick=event=>{active=active===row.name?null:row.name;table();lines();if(active&&event.detail>0&&matchMedia('(max-width:680px)').matches)$('overlay').scrollIntoView({block:'center',behavior:matchMedia('(prefers-reduced-motion:reduce)').matches?'auto':'smooth'});};name.append(button);value.textContent = formatValue(row.value_cm,unit) + ' ';
    tolerance.textContent = `±${formatValue(row.tolerance_cm,unit)} ${unit}`; value.append(tolerance); tr.append(name,value); $('measurements').append(tr);
  }
}
function lines() {
  const svg=$('lines');svg.replaceChildren();if(!current.image_size)return;const [w,h]=current.image_size;svg.setAttribute('viewBox',`0 0 ${w} ${h}`);
  const make=(tag,attrs)=>{const el=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [k,v] of Object.entries(attrs))el.setAttribute(k,v);return el;};
  for(const row of current.garment.measurements){if(!row.p1||!row.p2)continue;const selected=active===row.name,color=selected?'#fffefa':'#e3be4b';const g=make('g',{opacity:active&&!selected?'.22':'1'});
    g.append(make('line',{x1:row.p1[0],y1:row.p1[1],x2:row.p2[0],y2:row.p2[1],stroke:color,'stroke-width':selected?'3':'2','vector-effect':'non-scaling-stroke'}));
    for(const p of [row.p1,row.p2])g.append(make('circle',{cx:p[0],cy:p[1],r:Math.max(w,h)*.004,fill:color,stroke:'#242b29','stroke-width':'1','vector-effect':'non-scaling-stroke'}));svg.append(g);}
  const selected=current.garment.measurements.find(row=>row.name===active);
  $('overlayCaption').textContent=selected?`${labels[active]||active} · ${formatValue(selected.value_cm,unit)} ±${formatValue(selected.tolerance_cm,unit)} ${unit}`:(current.demo?'Simulated garment · tap a measurement to see its line':'Tap a measurement to check its line. Orange marks the detected button.');
}
function render(data) {
  current = data; active=null; show('results'); $('resultTitle').focus(); $('overlay').src = data.overlay_url;
  $('resultMode').textContent = data.demo ? '03 / Example · simulated garment' : '03 / Your measurements';
  $('confidence').textContent = data.demo ? 'Simulated jeans · hardware estimate. Use the example to explore the flow; it does not establish real-world accuracy.' : data.reference === 'hardware' ? 'Provisional hardware estimate · button size is a scale assumption. Check the orange button outline and every line.' : 'Reference-based measurement · perspective corrected. Check that the reference and all garment lines were detected correctly.';
  $('overlayCaption').textContent = data.demo ? 'Synthetic validation image · existing geometry pipeline' : 'Check the button and line endpoints. Zoom the image if needed.';
  $('notes').replaceChildren(); for(const note of data.garment.notes) { const li = document.createElement('li'); li.textContent = note; $('notes').append(li); }
  $('confirm').checked = false; $('confirmWrap').hidden = !!data.demo; $('confirmNote').hidden = !!data.demo;
  $('confirmWrap').lastChild.textContent = data.reference === 'hardware' ? ' The highlighted disc is the tack button, and the lines follow my garment.' : ' The reference and measurement lines follow my garment.';
  $('save').disabled = !data.demo; $('saveStatus').textContent = ''; $('compareWaist').value = ''; $('comparison').textContent = 'Add a measurement to see the difference.'; table();lines();
}
$('confirm').onchange = () => { $('save').disabled = !$('confirm').checked; $('confirmNote').textContent = $('confirm').checked ? 'Visually checked. The calibration uncertainty still applies.' : 'Until checked, these numbers are provisional.'; };
for(const [id,value] of [['cm','cm'],['inches','in']]) $(id).onclick = () => { unit = value; $('cm').setAttribute('aria-pressed',String(unit === 'cm')); $('inches').setAttribute('aria-pressed',String(unit === 'in')); table();lines(); };
$('compareWaist').oninput = () => { $('comparison').textContent = comparisonText(current.garment.measurements.find(r=>r.name==='waist_flat'),parseFloat($('compareWaist').value)); };
$('demo').onclick = async () => { try { const response = await fetch('./demo.json'); if(!response.ok) throw new Error(); render(await response.json()); } catch { error('The example is unavailable. Reconnect once to download it.'); } };
function saved() { try { const items = JSON.parse(localStorage.getItem('fittag-saved') || '[]'); return Array.isArray(items) ? items.slice(0,20) : []; } catch { return []; } }
function savedList() { const list = $('savedList'); list.replaceChildren(); const items = saved(); if(!items.length) {const p=document.createElement('p');p.className='small';p.textContent='No saved measurements yet.';list.append(p);}
  for(const item of items) { const div = document.createElement('div'); div.className = 'saved-item'; div.textContent = `${item.demo ? 'Example' : 'Garment'} · ${new Date(item.date).toLocaleDateString()} · ${item.reference}`; const p=document.createElement('p'); p.textContent=(item.rows||[]).map(r=>`${labels[r.name]||r.name}: ${r.value_cm} ±${r.tolerance_cm} cm`).join(' / '); div.append(p);list.append(div); }
}
$('save').onclick = () => { try { localStorage.setItem('fittag-saved',JSON.stringify([{date:new Date().toISOString(),demo:!!current.demo,reference:current.reference,rows:current.garment.measurements},...saved()].slice(0,20))); $('saveStatus').textContent = 'Saved on this device. Photos are not saved.'; $('save').disabled = true; savedList(); } catch { $('saveStatus').textContent = 'Storage is unavailable or full. Your result is still visible here.'; } };
$('forget').onclick = () => { try {localStorage.removeItem('fittag-saved');savedList();} catch {error('Device storage is unavailable.');} };
window.addEventListener('beforeinstallprompt',event=>{event.preventDefault();installPrompt=event;$('nativeInstall').hidden=false;});
$('install').onclick=()=>$('installDialog').showModal(); $('closeInstall').onclick=()=>$('installDialog').close();
$('nativeInstall').onclick=async()=>{if(installPrompt){await installPrompt.prompt();installPrompt=null;$('nativeInstall').hidden=true;$('installDialog').close();}};
function network(){ $('network').hidden=navigator.onLine; } window.addEventListener('online',network);window.addEventListener('offline',network);network();savedList();
if('serviceWorker' in navigator) navigator.serviceWorker.register('./sw.js').catch(()=>{});

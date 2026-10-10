export function anchorResult(result, name, cm) {
  if (!Number.isFinite(cm) || cm < 5 || cm > 200) throw Error('Enter a measurement between 5 and 200 cm.');
  const base=result.rows.find(row=>row.name===name);
  if(!base) throw Error('Choose the measurement you know.');
  const divisor=base.value_cm ?? base.ratio;
  if(!Number.isFinite(divisor)||divisor<=0) throw Error('This line cannot set a scale.');
  const factor=cm/divisor;
  return {...result,mode:'anchored',anchor:{name,cm},rows:result.rows.map(row=>{
    const value=(row.value_cm??row.ratio)*factor;
    return {...row,value_cm:Math.round(value*10)/10,tolerance_cm:Math.round(Math.max(2.5,value*.20)*10)/10};
  })};
}
export function rowText(row,unit='cm') {
  if(row.value_cm===undefined) return `${(row.ratio*100).toFixed(1)}%`;
  const divisor=unit==='in'?2.54:1;
  return `${(row.value_cm/divisor).toFixed(1)} ${unit}`;
}
export function canCompare(result){return result.mode==='anchored';}
export function resultMessage(result) {
  if(result.mode==='anchored') return 'Size set from your measurement. Check the other lines before using them.';
  if(result.mode==='depth') return 'Estimated size. It can be far off. Check with a tape, or enter a measurement you know.';
  if(result.mode==='distance') return 'Size estimated from the camera distance you entered. The camera must face straight down.';
  return 'These are proportions, not centimetres. Enter a measurement you know to set the size.';
}

export function moveEndpoint(result, name, endpoint, point) {
  const row=result.rows.find(row=>row.name===name);
  if(!row || !['p1','p2'].includes(endpoint)) throw Error('Choose a line endpoint.');
  const [w,h]=result.image_size;
  const p=[Math.max(0,Math.min(w-1,point[0])),Math.max(0,Math.min(h-1,point[1]))];
  if(!p.every(Number.isFinite)) throw Error('Invalid endpoint.');
  const distance=r=>Math.hypot(r.p2[0]-r.p1[0],r.p2[1]-r.p1[1]);
  const old=distance(row),moved={...row,[endpoint]:p},next=distance(moved);
  if(old<1 || next<5) throw Error('Keep the endpoints at least five image pixels apart.');
  if(row.value_cm===undefined)moved.ratio=row.ratio*next/old;
  else {moved.value_cm=Math.round(row.value_cm*next/old*10)/10;if(row.tolerance_cm!==undefined)moved.tolerance_cm=Math.round(Math.max(row.tolerance_cm,moved.value_cm*.20)*10)/10;}
  let rows=result.rows.map(r=>r===row?moved:{...r});
  if(result.mode==='shape'){
    const basis=rows.find(r=>r.name===(result.garment_type==='jeans'?'inseam':'length'));
    if(basis)rows=rows.map(r=>({...r,ratio:r.ratio/basis.ratio}));
  }
  return {...result,edited:true,rows};
}

export function listingText(result) {
  const header=result.mode==='shape'?'Clothing proportions, not centimetres':
    result.mode==='depth'?'Estimated sizes. Check with a tape before listing.':
    'Estimated sizes. Check the lines and size before listing.';
  const lines=result.rows.map(row=>`${row.name.replaceAll('_',' ')}: ${rowText(row)}`);
  if(result.anchor)lines.push(`Scale set from supplied ${result.anchor.name.replaceAll('_',' ')}: ${result.anchor.cm} cm.`);
  if(result.mode==='shape')lines.push(`${result.garment_type==='jeans'?'Inseam':'Garment length'} is the 100% reference.`);
  return [header,...lines,'FitTag · flat garment measurements, not body circumference.'].join('\n');
}

export const stages={
 connecting:['Getting ready','Connecting to the measurement service.'],
 uploading:['Sending your photo','Keep this screen open while your photo uploads.'],
 outline:['Finding the edges','Tracing the garment against the floor.'],
 depth:['Estimating size','Checking the photo for clues to distance.'],
 geometry:['Checking the measurements','Testing the floor and finding measurement points.'],
 'second-photo':['Checking your second photo','Checking its edges and comparing the photos.'],
 finishing:['Preparing your result','Getting the photo and editable lines ready.']
};
export function pause(ms,signal){
 return new Promise((resolve,reject)=>{
  const abort=()=>{clearTimeout(timer);signal.removeEventListener('abort',abort);reject(new DOMException('Aborted','AbortError'));};
  const timer=setTimeout(()=>{signal?.removeEventListener('abort',abort);resolve();},ms);
  if(signal?.aborted)return abort();signal?.addEventListener('abort',abort,{once:true});
 });
}
async function json(response){
 const data=await response.json().catch(()=>{throw Error('The service returned an incomplete response. Your photo is still selected.');});
 if(!response.ok||data.ok===false)throw Error(typeof data.detail==='string'?data.detail:data.error||'The service could not read this photo.');
 return data;
}
export async function measurePhoto(body,{signal,onStage=()=>{},onJob=()=>{},fetcher=fetch,wait=pause}={}){
 // Admission reports availability itself; avoid a separate round trip per photo.
 if(signal?.aborted)throw new DOMException('Aborted','AbortError');
 onStage('uploading');
 // Never retry POST automatically: a lost reply may already have started work.
 const accepted=await json(await fetcher('./measure-free-jobs',{method:'POST',body,signal}));
 if(!/^\/measurement-jobs\/[a-f0-9]{32}$/.test(accepted.status_url||''))throw Error('The service did not return a valid measurement job.');
 const url='.'+accepted.status_url;
 onJob(url);
 let failures=0;
 for(;;){
  if(signal?.aborted)throw new DOMException('Aborted','AbortError');
  let response;
  try{response=await fetcher(url,{signal,cache:'no-store'});failures=0;}
  catch(error){if(error.name==='AbortError'||++failures>2)throw error;await wait(1500*failures,signal);continue;}
  const state=await json(response);
  if(state.status==='succeeded')return state.result;
  if(state.status==='failed')throw Error(state.error||'Could not finish this photo.');
  if(state.status==='cancelled')throw new DOMException('Aborted','AbortError');
  if(state.status!=='running')throw Error('The service returned an unknown processing state.');
  onStage(state.stage);
  const seconds=Number(response.headers?.get('Retry-After'))||1;
  await wait(Math.min(3000,Math.max(1000,seconds*1000)),signal);
 }
}

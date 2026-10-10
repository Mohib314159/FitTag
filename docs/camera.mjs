// Camera frames stay on-device. The measurement client decides when to upload.
export function createCamera(video,{mediaDevices=globalThis.navigator?.mediaDevices,onState=()=>{},canStart=()=>true}={}){
 let stream=null,pending=null,generation=0,pendingGeneration=null;
 const release=source=>source?.getTracks().forEach(track=>track.stop());
 const ready=()=>Boolean(stream&&video.readyState>=2&&video.videoWidth&&video.videoHeight);
 const state=(name,message)=>onState(name,message);
 function stop(){generation++;release(stream);stream=null;video.pause?.();video.srcObject=null;video.hidden=true;state('idle','Open the camera, or choose a photo.');}
 function frame(){if(ready()&&canStart()){video.hidden=false;state('ready','Keep every edge in the frame.');}}
 video.addEventListener('loadeddata',frame);video.addEventListener('playing',frame);
 async function start(){
  if(!canStart())return false;
  if(pending){
   if(pendingGeneration===generation)return pending;
   const restart=generation;
   state('requesting','Allow camera access in the browser prompt.');
   return pending.then(()=>restart===generation&&canStart()?start():false);
  }
  if(!mediaDevices?.getUserMedia){state('unavailable','Live camera isn’t available in this browser. Use your phone camera or choose a photo.');return false;}
  const ticket=++generation;
  pendingGeneration=ticket;
  state('requesting','Allow camera access in the browser prompt.');
  pending=Promise.resolve().then(async()=>{
   try{
    if(!stream){
     const candidate=await mediaDevices.getUserMedia({audio:false,video:{facingMode:{ideal:'environment'},width:{ideal:1600},height:{ideal:1200}}});
     if(ticket!==generation||!canStart()){release(candidate);return false;}
     stream=candidate;video.srcObject=stream;
     for(const track of stream.getTracks())track.addEventListener?.('ended',()=>{if(stream===candidate){stop();state('unavailable','The camera stopped. Open it again, or choose a photo.');}},{once:true});
    }
    video.muted=true;video.hidden=false;
    state('starting','Starting the camera…');
    try{await video.play();}catch{
     if(ticket!==generation)return false;
     release(stream);stream=null;video.srcObject=null;video.hidden=true;
     state('unavailable','Tap Open camera to start the preview, or choose a photo.');return false;
    }
    if(ticket!==generation||!canStart())return false;
    frame();return ready();
   }catch(error){
    if(ticket!==generation)return false;
    release(stream);stream=null;video.srcObject=null;video.hidden=true;
    const message=error?.name==='NotAllowedError'?'Camera access is blocked. Allow it in your browser’s site settings, or choose a photo.':error?.name==='NotFoundError'?'No camera was found. You can choose a photo instead.':error?.name==='NotReadableError'?'The camera is being used elsewhere. Close that app, then try again.':'The camera could not start. Try again, use your phone camera, or choose a photo.';
    state('unavailable',message);return false;
   }finally{pending=null;pendingGeneration=null;}
  });
  return pending;
 }
 return {start,stop,ready};
}

export async function captureFrame(video,{createCanvas=()=>document.createElement('canvas'),maxEdge=1800}={}){
 if(video.readyState<2||!video.videoWidth||!video.videoHeight)throw Error('Wait for the camera picture, then take the photo.');
 const scale=Math.min(1,maxEdge/Math.max(video.videoWidth,video.videoHeight));
 const canvas=createCanvas();canvas.width=Math.max(1,Math.round(video.videoWidth*scale));canvas.height=Math.max(1,Math.round(video.videoHeight*scale));
 const context=canvas.getContext('2d');if(!context)throw Error('This browser could not take a photo. Choose one from your photos instead.');
 context.drawImage(video,0,0,canvas.width,canvas.height);
 const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/jpeg',.92));
 if(!blob)throw Error('The photo could not be captured. Try again or choose a photo.');
 return new File([blob],'Garment photo.jpg',{type:'image/jpeg'});
}

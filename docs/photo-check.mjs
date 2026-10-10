// A quick local check, not a guarantee that the garment can be measured.
export function photoInfo(buffer,type){
 const view=new DataView(buffer),size=view.byteLength;let width,height;
 if(type==='image/png'&&size>=24){width=view.getUint32(16);height=view.getUint32(20);}
 if(type==='image/jpeg'&&size>4){
  for(let p=2;p+4<size;){
   if(view.getUint8(p)!==255)break;
   const marker=view.getUint8(p+1),length=view.getUint16(p+2);if(length<2||p+2+length>size)break;
   if([192,193,194,195,197,198,199,201,202,203,205,206,207].includes(marker)&&length>=7){height=view.getUint16(p+5);width=view.getUint16(p+7);}
   p+=2+length;
  }
 }
 return {width,height}; // No metadata, GPS or identifiers are retained.
}
export function assessPixels({data,width,height},info={}){
 if(info.width&&info.height&&Math.min(info.width,info.height)<400)return {level:'stop',message:'This photo is too small. Choose the original photo, rather than a thumbnail.'};
 const gray=new Float32Array(width*height),hist=new Uint32Array(256),color=[new Uint32Array(256),new Uint32Array(256),new Uint32Array(256)];let dark=0;
 for(let i=0;i<gray.length;i++){const k=i*4,v=.299*data[k]+.587*data[k+1]+.114*data[k+2];gray[i]=v;hist[Math.round(v)]++;for(let channel=0;channel<3;channel++)color[channel][data[k+channel]]++;if(v<8)dark++;}
 const percentile=ratio=>{let n=0;for(let i=0;i<256;i++){n+=hist[i];if(n>=gray.length*ratio)return i;}return 255;};
 const range=percentile(.99)-percentile(.01);
 if(dark/gray.length>.99)return {level:'stop',message:'This photo is too dark to read. Try again in brighter, even light.'};
 if(range<8){
  const span=histogram=>{let n=0,lo=0,hi=255;for(let i=0;i<256;i++){n+=histogram[i];if(n>=gray.length*.01){lo=i;break;}}n=0;for(let i=255;i>=0;i--){n+=histogram[i];if(n>=gray.length*.01){hi=i;break;}}return hi-lo;};
  if(Math.max(...color.map(span))<12)return {level:'stop',message:'There is too little detail to read. Use a plain surface that contrasts with the clothes.'};
  return {level:'unchecked',message:'Check that the edges look sharp and the whole item is visible.'};
 }
 let sum=0,squares=0,count=0;
 for(let y=1;y<height-1;y++)for(let x=1;x<width-1;x++){const i=y*width+x,v=gray[i-1]+gray[i+1]+gray[i-width]+gray[i+width]-4*gray[i];sum+=v;squares+=v*v;count++;}
 const sharpness=squares/count-(sum/count)**2;
 if(sharpness<.12)return {level:'stop',message:'This photo looks very blurry. Hold the camera steady and take another.'};
 if(sharpness<1.2)return {level:'warn',message:'This photo may be blurry. Check that the edges look sharp.'};
 return {level:'ready',message:'Photo ready. Check that every edge is visible.'};
}
export async function checkPhoto(file){
 if(typeof createImageBitmap!=='function')return {level:'unchecked',message:'Check that every edge is visible and the photo is sharp.'};
 let bitmap;
 try{
  const info=photoInfo(await file.slice(0,262144).arrayBuffer(),file.type);
  if(info.width&&info.height&&(info.width*info.height>25000000||Math.min(info.width,info.height)/Math.max(info.width,info.height)<.1))return {level:'stop',message:'Choose a normal camera photo under 25 megapixels.'};
  bitmap=await createImageBitmap(file,{resizeWidth:Math.min(512,info.width||512),imageOrientation:'from-image'});
  const canvas=document.createElement('canvas');canvas.width=bitmap.width;canvas.height=bitmap.height;
  const ctx=canvas.getContext('2d',{willReadFrequently:true});ctx.drawImage(bitmap,0,0);
  const result=assessPixels(ctx.getImageData(0,0,canvas.width,canvas.height),info);
  result.thumbnail=await new Promise(resolve=>canvas.toBlob(resolve,'image/jpeg',.72));
  return result;
 }catch(error){if(['InvalidStateError','EncodingError'].includes(error.name))return {level:'stop',message:'This photo won’t open. Choose another photo.'};return {level:'unchecked',message:'Check that every edge is visible and the photo is sharp.'};}
 finally{bitmap?.close();}
}

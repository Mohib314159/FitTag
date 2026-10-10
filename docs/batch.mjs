// The browser holds a small selection; it sends only as capacity becomes free.
export async function runBatch(items,{concurrency=1,signal,process,onChange=()=>{}}){
 let next=0;
 async function worker(){
  while(!signal.aborted){
   const item=items[next++];if(!item)return;
   if(item.status==='stop'||item.status==='done')continue;
   item.status='reading';item.message='Reading photo…';onChange(item);
   try{
    item.result=await process(item,signal);item.status='done';
   }catch(error){item.status=signal.aborted?'cancelled':'failed';item.message=signal.aborted?'Stopped. Your photo is still here.':error.message;}
   onChange(item);
  }
 }
 await Promise.all(Array.from({length:Math.min(2,Math.max(1,concurrency))},worker));
 for(const item of items)if(item.status==='queued'){item.status='cancelled';item.message='Not sent.';onChange(item);}
}

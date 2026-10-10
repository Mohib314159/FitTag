// Only screen names go into browser history; photos and measurements stay in memory.
export function createNavigation(onChange,{history=globalThis.window?.history,target=globalThis.window}={}) {
 const session=`fittag-${Date.now()}-${Math.random()}`;
 let entries=[{screen:'camera'}],index=0,pending=false;
 const state=()=>({fittagNavigation:session,index});
 history?.replaceState(state(),'');
 const apply=()=>onChange(entries[index],index>0);
 function go(route,{replace=false}={}) {
  pending=false;
  if(replace||JSON.stringify(route)===JSON.stringify(entries[index])) {
   entries[index]=route;history?.replaceState(state(),'');
  } else {
   entries=entries.slice(0,index+1);entries.push(route);index++;
   history?.pushState(state(),'');
  }
  apply();
 }
 function back(){
  if(pending)return;
  if(index>0&&history?.back){pending=true;history.back();}
  else if(index>0){index--;apply();}
 }
 target?.addEventListener('popstate',event=>{
  pending=false;
  if(event.state?.fittagNavigation!==session)return;
  const next=event.state.index;
  if(!Number.isInteger(next)||next<0||next>=entries.length)return;
  index=next;apply();
 });
 return {go,back,current:()=>entries[index],canBack:()=>index>0};
}

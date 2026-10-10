import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createNavigation} from '../web/navigation.mjs';
function fixture(){
 let index=0,listener;const entries=[],seen=[];
 const history={replaceState:s=>entries[index]=s,pushState:s=>{entries.splice(++index);entries[index]=s;},back:()=>{if(index>0)listener({state:entries[--index]});}};
 const nav=createNavigation((route,canBack)=>seen.push({route,canBack}),{history,target:{addEventListener:(_,fn)=>listener=fn}});
 return {nav,seen,history,entries,pop:state=>listener({state})};
}
test('browser Back unwinds sizes, result and photo in order without a reload',()=>{
 const {nav,seen,history}=fixture();nav.go({screen:'photo'});nav.go({screen:'results',resultVersion:1});nav.go({screen:'sizes',resultVersion:1});
 history.back();assert.equal(nav.current().screen,'results');nav.back();assert.equal(nav.current().screen,'photo');nav.back();assert.equal(nav.current().screen,'camera');assert.equal(seen.at(-1).canBack,false);
});
test('Saved and sheets return to the screen they opened from',()=>{
 const {nav}=fixture();nav.go({screen:'results'});nav.go({screen:'saved'});nav.back();assert.equal(nav.current().screen,'results');nav.go({...nav.current(),dialog:'settingsDialog'});nav.back();assert.equal(nav.current().dialog,undefined);
});
test('replacing a sheet with a new screen avoids reopening the sheet on Back',()=>{
 const {nav,entries,pop}=fixture();nav.go({screen:'camera',dialog:'settingsDialog'});nav.go({screen:'batch'},{replace:true});nav.back();assert.equal(nav.current().screen,'camera');assert.equal(entries.length,2);pop({index:1});assert.equal(nav.current().screen,'camera');
});

import {test} from 'node:test';
import assert from 'node:assert/strict';
import {anchorResult,rowText,canCompare,resultMessage,moveEndpoint,listingText} from '../web/free.mjs';
const shape={mode:'shape',rows:[{name:'waist_flat',ratio:.5},{name:'inseam',ratio:1}]};
test('proportions never render as cm',()=>{assert.equal(rowText(shape.rows[0]),'50.0%');assert.equal(canCompare(shape),false);});
test('known length anchors all rows without changing original data',()=>{const anchored=anchorResult(shape,'waist_flat',40);assert.equal(anchored.rows[1].value_cm,80);assert.equal(anchored.rows[1].tolerance_cm,16);assert.equal(anchored.mode,'anchored');assert.equal(shape.rows[1].value_cm,undefined);assert.equal(canCompare(anchored),true);});
test('anchoring model scale cancels shared multiplicative bias',()=>{const data={mode:'depth',rows:[{name:'waist_flat',value_cm:80},{name:'inseam',value_cm:150}]};const fixed=anchorResult(data,'waist_flat',40);assert.equal(fixed.rows[1].value_cm,75);assert.equal(canCompare(data),false);assert.match(resultMessage(data),/far off/);});
test('invalid known lengths do not create bogus measurements',()=>{for(const value of [NaN,Infinity,0,-4,201])assert.throws(()=>anchorResult(shape,'waist_flat',value));assert.throws(()=>anchorResult(shape,'missing',40));});
test('unit conversion preserves shape and scales cm',()=>{assert.equal(rowText({value_cm:25.4},'in'),'10.0 in');assert.equal(rowText({ratio:1},'in'),'100.0%');});
test('endpoint correction changes geometry without claiming a new calibration',()=>{
 const result={mode:'depth',image_size:[300,400],rows:[{name:'waist_flat',value_cm:40,p1:[20,30],p2:[120,30]}]};
 const edited=moveEndpoint(result,'waist_flat','p2',[170,30]);assert.equal(edited.rows[0].value_cm,60);assert.equal(edited.mode,'depth');assert.equal(edited.edited,true);assert.equal(edited.rows[0].tolerance_cm,undefined);assert.equal(result.rows[0].value_cm,40);
});
test('adjusting the basis preserves honest proportional units',()=>{
 const result={mode:'shape',garment_type:'jeans',image_size:[300,400],rows:[{name:'waist_flat',ratio:.5,p1:[20,30],p2:[120,30]},{name:'inseam',ratio:1,p1:[60,80],p2:[60,280]}]};
 const edited=moveEndpoint(result,'inseam','p2',[60,380]);assert.equal(edited.rows[1].ratio,1);assert.ok(Math.abs(edited.rows[0].ratio-1/3)<.001);assert.throws(()=>moveEndpoint(result,'waist_flat','p2',[20,31]));
});
test('listing text carries its scale limitations with the numbers',()=>{
 assert.match(listingText(shape),/not centimetres/);
 const text=listingText({mode:'depth',rows:[{name:'waist_flat',value_cm:40}]});assert.match(text,/Check with a tape/);assert.match(text,/40.0 cm/);assert.match(text,/not body circumference/);
});

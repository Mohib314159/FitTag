import {test} from 'node:test';
import assert from 'node:assert/strict';
import {formatValue,validateFile,comparisonText} from '../web/client.mjs';
test('cm and inch values preserve numeric precision',()=>{
  assert.equal(formatValue(25.4,'in'),'10.0');assert.equal(formatValue(25.4,'cm'),'25.4');
});
test('unsupported and oversized files have useful recovery',()=>{
  assert.match(validateFile({type:'image/heic',size:100}),/JPEG/);
  assert.match(validateFile({type:'image/jpeg',size:13*1024*1024}),/12 MB/);
  assert.equal(validateFile({type:'image/jpeg',size:12*1024*1024}),'');
});
test('fit comparison stays uncertain when error bars cover the difference',()=>{
  const row={value_cm:40,tolerance_cm:6};
  assert.match(comparisonText(row,43),/unreliable/);
  assert.match(comparisonText(row,30),/10.0 cm wider/);
  assert.match(comparisonText(row,55),/15.0 cm narrower/);
  assert.match(comparisonText(row,NaN),/Enter/);
});

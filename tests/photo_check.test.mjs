import {test} from 'node:test';
import assert from 'node:assert/strict';
import {assessPixels,photoInfo,checkPhoto} from '../web/photo-check.mjs';
function pixels(fn){const width=64,height=80,data=new Uint8ClampedArray(width*height*4);for(let y=0;y<height;y++)for(let x=0;x<width;x++){const i=(y*width+x)*4,v=fn(x,y);data.set([v,v,v,255],i);}return {width,height,data};}
test('blank and black images stop before upload',()=>{
 assert.equal(assessPixels(pixels(()=>255)).level,'stop');assert.match(assessPixels(pixels(()=>0)).message,/dark/);
});
test('tiny photos are refused without promising accuracy for larger photos',()=>{
 const photo=pixels((x,y)=>x>15&&x<48&&y>10&&y<70?40:230);
 assert.match(assessPixels(photo,{width:200,height:300}).message,/too small/);
 assert.equal(assessPixels(photo,{width:800,height:1000}).level,'ready');
});
test('very smooth blurred transitions are caught',()=>{
 const photo=pixels(x=>80+x);assert.equal(assessPixels(photo).level,'stop');assert.match(assessPixels(photo).message,/blurry/);
});
test('JPEG dimensions are read without retaining EXIF',()=>{
 const bytes=new Uint8Array([255,216,255,192,0,8,8,3,232,3,32,0]);
 assert.deepEqual(photoInfo(bytes.buffer,'image/jpeg'),{width:800,height:1000});
 assert.deepEqual(photoInfo(new Uint8Array([255,216]).buffer,'image/jpeg'),{width:undefined,height:undefined});
});
test('a browser without bitmap support preserves the manual check route',async()=>{
 assert.equal((await checkPhoto(new File(['x'],'photo.jpg',{type:'image/jpeg'}))).level,'unchecked');
});

test('strong colour contrast at equal brightness is not mistaken for a blank photo',()=>{
 const photo=pixels(()=>76);for(let y=15;y<65;y++)for(let x=20;x<45;x++)photo.data.set([255,0,0,255],(y*photo.width+x)*4);
 assert.notEqual(assessPixels(photo).level,'stop');
});

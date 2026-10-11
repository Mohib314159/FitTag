"""Private local Record3D rear-LiDAR experiment, not a public upload endpoint.

Reads one synchronized RGB/depth/confidence frame without extracting the ZIP.
Never substitutes AI/portrait depth or a guessed focal length for missing data.
"""
import argparse
import io
import json
from pathlib import Path,PurePosixPath
import struct
import zipfile
import cv2
import numpy as np
from PIL import Image
from core.lidar_capture import process

def declared_lzfse_bytes(data,expected):
    """Check the complete stream's declared output length before native decoding.

    Block layouts are documented by Apple's lzfse_internal.h. This is a
    preflight for locally exported files, not a hardened network decoder.
    """
    offset=0;total=0
    while offset+4<=len(data):
        magic=data[offset:offset+4]
        if magic==b'bvx$':
            if offset+4!=len(data) or total!=expected:raise ValueError('Depth stream size does not match camera metadata.')
            return
        if offset+8>len(data):raise ValueError('Truncated depth header.')
        raw=struct.unpack_from('<I',data,offset+4)[0];total+=raw
        if total>expected:raise ValueError('Depth stream expands beyond the expected frame size.')
        if magic==b'bvx-':header,payload=8,raw
        elif magic==b'bvxn':
            if offset+12>len(data):raise ValueError('Truncated LZVN header.')
            header,payload=12,struct.unpack_from('<I',data,offset+8)[0]
        elif magic==b'bvx1':
            if offset+772>len(data):raise ValueError('Truncated LZFSE v1 header.')
            header,payload=772,struct.unpack_from('<I',data,offset+8)[0]
        elif magic==b'bvx2':
            if offset+32>len(data):raise ValueError('Truncated LZFSE v2 header.')
            a,b,c=struct.unpack_from('<QQQ',data,offset+8)
            header=c&0xffffffff;payload=((a>>20)&0xfffff)+((b>>40)&0xfffff)
            if not 32<=header<=752:raise ValueError('Invalid LZFSE header length.')
        else:raise ValueError('Unsupported depth encoding; use raw Record3D export.')
        offset+=header+payload
        if offset>len(data):raise ValueError('Truncated depth payload.')
    raise ValueError('Depth stream has no valid ending.')

def decode(data,expected):
    declared_lzfse_bytes(data,expected)
    try:import liblzfse
    except ImportError:raise ValueError('Install the local decoder: pip install pyliblzfse==0.4.1') from None
    result=liblzfse.decompress(data)
    if len(result)!=expected:raise ValueError('Decoded frame size does not match camera metadata.')
    return result

def dimension(meta,key,max_pixels=4096):
    value=meta.get(key)
    if isinstance(value,bool) or not isinstance(value,int) or not 16<=value<=max_pixels:
        raise ValueError('Missing or invalid image dimensions in Record3D metadata.')
    return value

def camera(meta,frame):
    data=meta.get('K')
    per_frame=meta.get('perFrameIntrinsicCoeffs')
    if per_frame is not None:
        if not isinstance(per_frame,list) or frame>=len(per_frame):raise ValueError('No camera calibration for this frame.')
        values=per_frame[frame]
        if isinstance(values,dict):
            values=[values.get(x) for x in ['fx','fy','cx','cy']]
        if len(values)==4:
            fx,fy,cx,cy=values;data=[fx,0,0,0,fy,0,cx,cy,1]
        elif len(values)==9:data=values
        else:raise ValueError('Unsupported per-frame calibration. Keep the original file for inspection.')
    try:K=np.asarray(data,dtype=np.float64).reshape(3,3).T
    except (TypeError,ValueError):raise ValueError('Missing or invalid Record3D camera calibration.') from None
    if not np.isfinite(K).all() or K[0,0]<=0 or K[1,1]<=0 or not np.allclose(K[2],[0,0,1.]):
        raise ValueError('Record3D camera calibration is invalid.')
    return K

def read_frame(path,frame=0):
    path=Path(path)
    if not 0<=frame<=10000:raise ValueError('Invalid frame number.')
    if path.stat().st_size>512*1024*1024:raise ValueError('Use a shorter clip; this local trial accepts at most 512 MB.')
    with zipfile.ZipFile(path) as archive:
        infos=archive.infolist()
        if len(infos)>10000:raise ValueError('Use a shorter recording.')
        names=set()
        for info in infos:
            name=PurePosixPath(info.filename)
            if name.is_absolute() or '..' in name.parts or '\\' in info.filename or info.filename in names:
                raise ValueError('Unsafe or duplicate archive member.')
            names.add(info.filename)
        def read(name,limit):
            if name not in names:raise ValueError(f'This recording is missing {Path(name).suffix or "metadata"}. Export raw rear-LiDAR data.')
            entry=archive.getinfo(name)
            if entry.file_size>limit or entry.flag_bits&1:raise ValueError('Unsupported or oversized archive member.')
            with archive.open(entry) as source:data=source.read(limit+1)
            if len(data)>limit:raise ValueError('Archive member exceeds its limit.')
            return data
        meta=json.loads(read('metadata',2*1024*1024))
        w,h,dw,dh=[dimension(meta,key) for key in ('w','h','dw','dh')]
        if w*h>25_000_000 or dw*dh>1_000_000:raise ValueError('Camera frame dimensions exceed the trial limits.')
        if abs((w/h)/(dw/dh)-1)>.01:raise ValueError('RGB and depth have different crops. Their alignment needs inspection first.')
        image_raw=read(f'rgbd/{frame}.jpg',12*1024*1024)
        with Image.open(io.BytesIO(image_raw)) as image:
            if image.size!=(w,h) or image.getexif().get(274,1)!=1:
                raise ValueError('RGB orientation or size differs from its calibration. Use the uncropped raw frame.')
            photo=cv2.cvtColor(np.asarray(image.convert('RGB')),cv2.COLOR_RGB2BGR)
        K=camera(meta,frame)
        depth=np.frombuffer(decode(read(f'rgbd/{frame}.depth',8*1024*1024),dw*dh*4),dtype='<f4').reshape(dh,dw)
        confidence=np.frombuffer(decode(read(f'rgbd/{frame}.conf',2*1024*1024),dw*dh),dtype=np.uint8).reshape(dh,dw)
        if np.any(confidence>2):raise ValueError('Unsupported depth confidence values.')
        factor=min(1.,1800/max(w,h))
        if factor<1:
            new=(round(w*factor),round(h*factor));photo=cv2.resize(photo,new,interpolation=cv2.INTER_AREA)
            K[0,:]*=new[0]/w;K[1,:]*=new[1]/h
        # Deliberately return no poses, identity, audio, GPS or full metadata.
        return photo,depth,confidence,K

def main():
    parser=argparse.ArgumentParser();parser.add_argument('recording',type=Path)
    parser.add_argument('--frame',type=int,default=0);parser.add_argument('--kind',choices=['jeans','t-shirt'],default='jeans')
    parser.add_argument('--rear-lidar',action='store_true',help='Confirm recording used the rear LiDAR camera, not FaceID or AI depth.')
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if not args.rear_lidar:parser.error('Confirm rear LiDAR capture with --rear-lidar; no other depth source is supported.')
    if args.output.exists():parser.error('Choose a new private output directory; existing results are not overwritten.')
    photo,depth,confidence,K=read_frame(args.recording,args.frame)
    rect,result=process(photo,depth,confidence,K,args.kind)
    args.output.mkdir(parents=True)
    overlay=rect.copy()
    for row in result['rows']:
        p1,p2=tuple(row['p1']),tuple(row['p2']);cv2.line(overlay,p1,p2,(40,110,240),2,cv2.LINE_AA)
        cv2.putText(overlay,f"{row['name']}: {row['value_cm']} cm",p1,cv2.FONT_HERSHEY_SIMPLEX,.45,(0,0,0),1,cv2.LINE_AA)
    cv2.imwrite(str(args.output/'measurements.jpg'),overlay)
    (args.output/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('Saved private measurements and overlay. Check every line before using the sizes.')

if __name__=='__main__':main()

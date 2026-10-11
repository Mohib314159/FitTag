"""Private local Record3D rear-LiDAR experiment, not a public upload endpoint.

Reads one synchronized RGB/depth/confidence frame without extracting the ZIP.
Never substitutes AI/portrait depth or a guessed focal length for missing data.
"""
import argparse
import io
import json
from pathlib import Path,PurePosixPath
import re
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

def sample_frames(path,max_candidates=5):
    """Bound work on a short local recording; do not score every video frame."""
    if not 1<=max_candidates<=5:raise ValueError('Inspect between one and five frames.')
    if Path(path).stat().st_size>512*1024*1024:raise ValueError('Use a shorter clip; this local trial accepts at most 512 MB.')
    with zipfile.ZipFile(path) as archive:
        names=archive.namelist()
        if len(names)>10000:raise ValueError('Use a shorter recording.')
        frames=sorted({int(match.group(1)) for name in names
                       if (match:=re.fullmatch(r'rgbd/(\d+)\.jpg',name)) and int(match.group(1))<=10000})
        frames=[f for f in frames if f'rgbd/{f}.depth' in names and f'rgbd/{f}.conf' in names]
    if not frames:raise ValueError('No matching RGB, depth and confidence frames. Export a raw rear-LiDAR recording.')
    positions=np.linspace(0,len(frames)-1,min(max_candidates,len(frames)),dtype=int)
    return [frames[int(i)] for i in positions]

def compare_frames(records):
    """Repeatability only. Consistent frames can share the same scale/line error."""
    accepted=[r for r in records if r['accepted']]
    names=sorted({name for r in accepted for name in r['measurements_cm']})
    spans={}
    for name in names:
        values=[r['measurements_cm'][name] for r in accepted if name in r['measurements_cm']]
        if len(values)>1 and min(values)>0:
            spans[name]=round(100*(max(values)-min(values))/float(np.median(values)),2)
    return {'accepted_frames':len(accepted),'attempted_frames':len(records),
            'relative_span_pct':spans,'absolute_accuracy_verified':False,
            'note':'Frame agreement is repeatability, not proof of correct sizes. Check every line against an independent measurement.'}

def select_frame(path,kind,max_candidates=5):
    records=[];best=None;best_rank=None
    for frame in sample_frames(path,max_candidates):
        try:
            photo,depth,confidence,K=read_frame(path,frame)
            rect,result=process(photo,depth,confidence,K,kind)
        except ValueError as error:
            records.append({'frame':frame,'accepted':False,'reason':str(error)})
            continue
        diag=result['diagnostics']
        records.append({'frame':frame,'accepted':True,'diagnostics':diag,
                        'measurements_cm':{r['name']:r['value_cm'] for r in result['rows']}})
        # Rank only sensor-floor quality. Never select against tape ground truth
        # or whichever garment dimensions appear most plausible.
        rank=(diag['high_confidence_floor_fraction'],-diag['plane_p90_pct'],-frame)
        if best_rank is None or rank>best_rank:
            best=(rect,result,frame);best_rank=rank
    if best is None:
        reasons='; '.join(dict.fromkeys(r['reason'] for r in records))
        raise ValueError('No usable sampled frame. '+reasons)
    rect,result,frame=best
    result['selected_frame']=frame
    result['frame_checks']=records
    result['frame_comparison']=compare_frames(records)
    result['notes'].append('Selected by surrounding floor-depth quality from at most five sampled frames; sizes are not fused or verified.')
    return rect,result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('recording',type=Path)
    parser.add_argument('--frame',type=int,help='Use one specific frame; omitted means automatic sampling.')
    parser.add_argument('--kind',choices=['jeans','t-shirt'],default='jeans')
    parser.add_argument('--rear-lidar',action='store_true',help='Confirm recording used the rear LiDAR camera, not FaceID or AI depth.')
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if not args.rear_lidar:parser.error('Confirm rear LiDAR capture with --rear-lidar; no other depth source is supported.')
    if args.output.exists():parser.error('Choose a new private output directory; existing results are not overwritten.')
    try:
        if args.frame is None:
            rect,result=select_frame(args.recording,args.kind)
        else:
            photo,depth,confidence,K=read_frame(args.recording,args.frame)
            rect,result=process(photo,depth,confidence,K,args.kind)
            result['selected_frame']=args.frame
    except (ValueError,OSError,zipfile.BadZipFile) as error:
        parser.exit(2,f'Capture could not be read: {error}\n')
    args.output.mkdir(parents=True)
    overlay=rect.copy()
    for row in result['rows']:
        p1,p2=tuple(row['p1']),tuple(row['p2']);cv2.line(overlay,p1,p2,(40,110,240),2,cv2.LINE_AA)
        cv2.putText(overlay,f"{row['name']}: {row['value_cm']} cm",p1,cv2.FONT_HERSHEY_SIMPLEX,.45,(0,0,0),1,cv2.LINE_AA)
    cv2.imwrite(str(args.output/'measurements.jpg'),overlay)
    (args.output/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('Saved private measurements and overlay. Check every line before using the sizes.')

if __name__=='__main__':main()

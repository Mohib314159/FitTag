"""Experimental MoGe-2 ONNX adapter; not selected by the serving app.

Projection/scale conventions follow Microsoft's MIT-licensed v2 inference.
See third_party/MOGE_NOTICE.md. Camera recovery is a learned geometric prior.
"""
import hashlib
import math
import cv2
import numpy as np

def recover(points,mask,focal=None):
    from scipy.optimize import least_squares
    h,w=points.shape[:2];diagonal=math.hypot(w,h)
    x=(np.arange(w,dtype=np.float32)+.5-w/2)*2/diagonal
    y=(np.arange(h,dtype=np.float32)+.5-h/2)*2/diagonal
    uv=np.stack(np.meshgrid(x,y),axis=-1)
    small=cv2.resize(points,(64,64),interpolation=cv2.INTER_NEAREST)
    rays=cv2.resize(uv,(64,64),interpolation=cv2.INTER_NEAREST)
    valid=cv2.resize(mask.astype(np.uint8),(64,64),interpolation=cv2.INTER_NEAREST)>0
    valid &= np.isfinite(small).all(axis=-1)
    if valid.sum()<100:raise ValueError('Too few valid model points to recover a camera.')
    xy=small[valid,:2].astype(np.float64);z=small[valid,2].astype(np.float64);target=rays[valid].astype(np.float64)
    def projection(shift):
        denominator=z+float(shift[0])
        if np.any(np.abs(denominator)<1e-8):denominator=np.where(np.abs(denominator)<1e-8,1e-8,denominator)
        projected=xy/denominator[:,None]
        f=focal if focal is not None else np.sum(projected*target)/max(1e-12,np.sum(projected**2))
        return (projected*f-target).ravel(),float(f)
    solution=least_squares(lambda s:projection(s)[0],[0.],method='lm',ftol=1e-3)
    shift=float(solution.x[0]);f=projection(solution.x)[1]
    if not solution.success or not math.isfinite(f) or f<=0:raise ValueError('The model camera fit failed.')
    return f,shift

def metric_maps(raw,focal_px=None):
    points=np.asarray(raw['points'])[0];mask=np.asarray(raw['mask'])[0]>.5
    h,w=points.shape[:2]
    focal,shift=recover(points,mask,None if focal_px is None else focal_px*2/math.hypot(w,h))
    scale=float(np.asarray(raw['metric_scale'] if 'metric_scale' in raw else raw['scale']).ravel()[0])
    if not math.isfinite(scale) or scale<=0:raise ValueError('The model metric scale is invalid.')
    depth=(points[...,2]+shift)*scale
    if not np.isfinite(depth).all() or np.any(depth<=0):raise ValueError('The model returned invalid depth.')
    return depth.astype(np.float32),focal*math.hypot(w,h)/2,mask

class Model:
    def __init__(self,path,threads=1):
        from tools.download_moge_model import SHA256
        from pathlib import Path
        with Path(path).open('rb') as source:
            digest=hashlib.file_digest(source,'sha256').hexdigest()
        if digest!=SHA256:raise ValueError('MoGe model does not match the pinned weights.')
        import onnxruntime as ort
        options=ort.SessionOptions();options.intra_op_num_threads=threads;options.inter_op_num_threads=1
        options.enable_cpu_mem_arena=False;options.enable_mem_pattern=False
        options.add_session_config_entry('session.intra_op.allow_spinning','0')
        options.add_session_config_entry('session.inter_op.allow_spinning','0')
        self.runtime=ort.InferenceSession(str(path),sess_options=options,providers=['CPUExecutionProvider'])
    def raw(self,photo,tokens=1200):
        rgb=cv2.cvtColor(photo,cv2.COLOR_BGR2RGB).astype(np.float32)/255.
        image=np.ascontiguousarray(rgb.transpose(2,0,1)[None])
        values=self.runtime.run(None,{'image':image,'num_tokens':np.array(tokens,np.int64)})
        return dict(zip([output.name for output in self.runtime.get_outputs()],values))

"""Opt-in buttonless pilot. Uses camera-aware metric points; never a fit verdict."""
import math
import os
from pathlib import Path
import threading
import time
import cv2
from core.moge_depth import Model,metric_maps
from core.free_capture import outline,depth_measure,focal_from_diagonal_fov
from api.free_capture import camera_fov,_shape_rows
from api.camera_evidence import inspect

_model=None
_lock=threading.Lock()

def available():
    path=os.environ.get('FITTAG_MOGE_MODEL','')
    return bool(path and Path(path).is_file())

def model():
    global _model
    with _lock:
        if _model is None:
            if not available():raise ValueError('The camera-aware pilot model is not configured.')
            _model=Model(os.environ['FITTAG_MOGE_MODEL'])
    return _model

def process(photo,raw,kind,fov_override=0,progress=lambda _:None):
    started=time.perf_counter()
    # Bound output arrays. Token count remains the authors' suggested minimum.
    h,w=photo.shape[:2];factor=min(1,500/max(h,w))
    image=cv2.resize(photo,(max(1,round(w*factor)),max(1,round(h*factor))),interpolation=cv2.INTER_AREA)
    progress('outline');rect,_,rows,mask=outline(image,kind)
    result={'ok':True,'mode':'shape','garment_type':kind,'rows':_shape_rows(rows),
            'notes':['These are proportions until the camera-aware model passes the geometry checks.'],
            'diagnostics':{'camera_evidence':inspect(raw),'metric_model':'MoGe-2 Small'},'cross_check':None}
    try:
        fov=fov_override or camera_fov(raw)
        progress('depth');prediction=model().raw(image,1200)
        depth,fx,valid=metric_maps(prediction,None if fov is None else focal_from_diagonal_fov(image.shape,fov))
        if valid.mean()<.8:raise ValueError('The model has too few usable depth points. Keeping proportions.')
        progress('geometry');rect,metric,diagnostics=depth_measure(image,kind,depth,fx,mask)
        result.update(mode='depth',rows=[{'name':row.name,'value_cm':row.value_cm,'p1':row.p1,'p2':row.p2} for row in metric])
        result['diagnostics'].update(diagnostics,focal_source='manual' if fov_override else 'photo-metadata' if fov else 'model-estimated',
                                     diagonal_fov_deg=round(math.degrees(2*math.atan(math.hypot(*image.shape[:2])/(2*fx))),2))
        result['notes']=['Camera-aware model estimate. It uses photo focal metadata when available, otherwise it estimates the camera.',
                         'The learned metric scale can still be wrong. No real-garment accuracy interval is established; do not use it for a fit verdict.',
                         'A good floor fit does not prove the size. Check the lines and compare with a measurement you know.']
    except ValueError as exc:
        result['notes'].insert(0,str(exc))
    result['diagnostics']['processing_seconds']=round(time.perf_counter()-started,2)
    return rect,result

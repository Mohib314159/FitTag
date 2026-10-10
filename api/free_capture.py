"""Reference-free API, isolated from the existing hardware/reference contract."""
import io
import math
import time
import uuid
import cv2
from PIL import Image
from core import depth_model
from core.free_capture import outline, focal_from_diagonal_fov, depth_measure, disagreement


def camera_fov(raw):
    # Read only focal length. Never return or store EXIF, GPS, serial or device ID.
    try:
        with Image.open(io.BytesIO(raw)) as image:
            exif=image.getexif()
            value=exif.get(41989) or exif.get_ifd(34665).get(41989)
            focal=float(value or 0)
            if 12 <= focal <= 70:
                return math.degrees(2*math.atan(math.hypot(36,24)/(2*focal)))
    except (ValueError,TypeError,KeyError,OSError,ZeroDivisionError):
        pass
    return None


def _shape_rows(rows):
    length=max(float(r.value_cm) for r in rows if r.name in ('inseam','length'))
    return [{"name":r.name,"ratio":round(r.value_cm/length,4),"p1":r.p1,"p2":r.p2} for r in rows]


def process(photo, raw, kind, fov_override, second=None, second_raw=None, estimate=True, camera_height_cm=0, progress=lambda stage: None):
    started=time.perf_counter()
    progress('outline')
    rect,_,shape_rows,mask=outline(photo,kind)
    result={"ok":True,"mode":"shape","garment_type":kind,"rows":_shape_rows(shape_rows),
            "notes":["Proportions are relative to inseam for jeans, or garment length for tops. They are not centimetres.",
                     "Silhouette landmarks can miss overlapped crotch seams. Check every line."],
            "diagnostics":{},"cross_check":None}
    metadata_fov=camera_fov(raw) if not fov_override else None
    fov=fov_override or metadata_fov or 84.
    focal_source='manual' if fov_override else 'photo-metadata' if metadata_fov else 'assumed'
    result['diagnostics'].update(diagonal_fov_deg=round(fov,1),focal_source=focal_source)
    if camera_height_cm:
        progress('geometry')
        scale=camera_height_cm*10/focal_from_diagonal_fov(photo.shape,fov)
        result.update(mode='distance',rows=[{'name':r.name,'value_cm':round(r.value_cm*scale,1),
                                            'tolerance_cm':round(max(2.5,r.value_cm*scale*.20),1),
                                            'p1':r.p1,'p2':r.p2} for r in shape_rows])
        result['diagnostics'].update(camera_height_cm=camera_height_cm,processing_seconds=round(time.perf_counter()-started,2))
        result['notes']=["Scale comes from your supplied lens-to-floor distance and camera field of view, not learned depth.",
                         "Assumes a flat garment and an overhead camera parallel to the floor. There is no perspective correction in this route.",
                         "The ±20% allowance is an engineering guardrail, not a validated accuracy interval. Wrong distance, zoom or field of view changes every result."]+result['notes'][1:]
        return rect,result
    if not estimate:
        result['diagnostics']['processing_seconds']=round(time.perf_counter()-started,2)
        return rect,result
    try:
        second_mask=None
        if second is not None:
            # Validate both captures before loading/running either depth estimate.
            progress('second-photo')
            _,_,_,second_mask=outline(second,kind)
        progress('depth')
        depth=depth_model.predict(photo)
        progress('geometry')
        candidate,rows,diagnostics=depth_measure(photo,kind,depth,focal_from_diagonal_fov(photo.shape,fov),mask)
        if second is not None:
            progress('second-photo')
            fov2=fov_override or camera_fov(second_raw) or 84.
            _,second_rows,_=depth_measure(second,kind,depth_model.predict(second),focal_from_diagonal_fov(second.shape,fov2),second_mask)
            delta=disagreement(rows,second_rows)
            result['cross_check']={"difference_pct":round(delta*100,1),"agreed":delta<=.25}
            if delta>.25:
                raise ValueError("The two photos disagree on scale by more than 25%. Centimetres are withheld; keep the outline or anchor one known length.")
        # No statistical accuracy claim: a deliberately broad engineering guardrail.
        result.update(mode='depth',rows=[{"name":r.name,"value_cm":r.value_cm,
                                         "p1":r.p1,"p2":r.p2} for r in rows])
        result['diagnostics'].update(diagnostics)
        result['notes']=["Experimental metric-depth guess. No error interval is established for real garments; actual error can be large. No fit decision should use these centimetres.",
                         "Camera focal length comes from photo metadata when present, otherwise an explicit field-of-view assumption.",
                         "A consistent floor plane or agreeing photos cannot detect shared model scale bias.",
                         "The garment must be flat. Depth and outline checks cannot prove this."]+result['notes'][1:]
        rect=candidate
    except ValueError as error:
        result['notes'].insert(0,str(error))
    result['diagnostics']['processing_seconds']=round(time.perf_counter()-started,2)
    return rect,result


def persist(rect,result):
    from api.overlay_store import persist_image
    return {**result,**persist_image(rect)}

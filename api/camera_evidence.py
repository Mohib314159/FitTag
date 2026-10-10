"""Inspect a small numeric allowlist. Never return full EXIF or identify a camera owner."""
import io
import math
from PIL import Image

def inspect(raw):
    evidence={'focal_35mm':None,'subject_distance_m':None,'digital_zoom':None,
              'embedded_depth_candidates':0,'absolute_scale_verified':False}
    try:
        with Image.open(io.BytesIO(raw)) as image:
            exif=image.getexif()
            nested=exif.get_ifd(34665)
            for tag,key,lower,upper in [(41989,'focal_35mm',12,200),
                                       (37382,'subject_distance_m',.1,100),
                                       (41988,'digital_zoom',1,100)]:
                value=nested.get(tag,exif.get(tag))
                try: value=float(value)
                except (TypeError,ValueError,ZeroDivisionError): continue
                if math.isfinite(value) and lower<=value<=upper: evidence[key]=value
            evidence['embedded_depth_candidates']=min(8,len(image.info.get('depth_images') or []))
    except (OSError,ValueError,TypeError,KeyError,Image.DecompressionBombError):
        pass
    # A focus distance need not describe the floor, and a depth auxiliary may be
    # relative disparity. Neither is silently relabelled as verified metres.
    return evidence

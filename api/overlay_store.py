"""Small synchronized output store, shared by every measurement route."""
import threading
import time
import uuid
import cv2

_lock = threading.Lock()


def persist_image(rect):
    from api.server import OVERLAYS
    h,w=rect.shape[:2]
    display=cv2.resize(rect,(int(w*min(1,1000/h)),int(h*min(1,1000/h))))
    name=uuid.uuid4().hex+'.png'
    with _lock:
        for old in OVERLAYS.glob('*.png'):
            if time.time()-old.stat().st_mtime>3600:
                old.unlink(missing_ok=True)
        existing=sorted(OVERLAYS.glob('*.png'),key=lambda p:p.stat().st_mtime)
        for old in existing[:-39]:
            old.unlink(missing_ok=True)
        if not cv2.imwrite(str(OVERLAYS/name),display):
            raise ValueError('Could not prepare the result photo. Please try again.')
    return {'overlay_url':'/overlays/'+name,'image_size':[w,h]}

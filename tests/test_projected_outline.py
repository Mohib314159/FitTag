import cv2
import numpy as np
from core import free_capture
from tests.test_phone_api import photo

def test_depth_rectification_keeps_the_projected_garment_mask(monkeypatch):
    image=cv2.imdecode(np.frombuffer(photo(False),np.uint8),cv2.IMREAD_COLOR)
    _,_,_,mask=free_capture.outline(image,'jeans')
    # A warp introduces bright borders. It must not trigger a second colour
    # segmentation that can select the floor instead of the existing garment.
    monkeypatch.setattr(free_capture,'garment_mask',lambda *_: (_ for _ in ()).throw(AssertionError('Discarded the projected mask')))
    depth=np.full(image.shape[:2],1.2,np.float32)
    rect,rows,_=free_capture.depth_measure(image,'jeans',depth,1000.,mask)
    assert len(rows)==5 and rect.ndim==3
    waist=next(row.value_cm for row in rows if row.name=='waist_flat')
    assert 40<waist<55

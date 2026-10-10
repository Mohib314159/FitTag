import math
import numpy as np
from core.moge_depth import recover,metric_maps

def fixture():
    h,w=120,160;diagonal=math.hypot(w,h)
    u,v=np.meshgrid((np.arange(w)+.5-w/2)*2/diagonal,(np.arange(h)+.5-h/2)*2/diagonal)
    z=2.+u*.6+v*.3+u*v*.2;focal=1.6;shift=.3
    points=np.stack([u*z/focal,v*z/focal,z-shift],axis=-1).astype(np.float32)
    return points,z,focal,shift

def test_joint_focal_shift_recovery_matches_a_known_projection():
    points,z,focal,shift=fixture();mask=np.ones(z.shape,bool);mask[::3,::2]=False
    f,s=recover(points,mask)
    assert abs(f-focal)<.002 and abs(s-shift)<.002

def test_known_focal_recovers_shift_and_applies_scale_once():
    points,z,focal,shift=fixture();h,w=z.shape
    raw={'points':points[None],'mask':np.ones((1,h,w),np.float32),'scale':np.array([2.],np.float32)}
    depth,fx,mask=metric_maps(raw,focal*math.hypot(w,h)/2)
    assert np.max(np.abs(depth-z*2))<.002
    assert abs(fx-focal*math.hypot(w,h)/2)<.002 and mask.all()

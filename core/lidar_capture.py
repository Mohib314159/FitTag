"""Supplied metric sensor depth. No learned scale, hardware prior or A4.

Local research path only until real device captures establish alignment and
landmark accuracy. Sensor confidence is not a garment-error probability.
"""
import math
import cv2
import numpy as np
from core.free_capture import camera_inverse,outline,rectify_plane

def fit_sensor_floor(depth,confidence,garment_mask,K):
    if depth.ndim!=2 or confidence.shape!=depth.shape:raise ValueError('Depth and confidence sizes differ.')
    h,w=depth.shape
    small=cv2.resize(garment_mask,(w,h),interpolation=cv2.INTER_NEAREST)
    small=cv2.dilate(small,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(5,5)))
    yy,xx=np.indices((h,w))
    valid=(small==0)&(confidence==2)&np.isfinite(depth)&(depth>=.1)&(depth<=5.)
    valid &= (xx>.025*w)&(xx<.975*w)&(yy>.025*h)&(yy<.975*h)
    if valid.mean()<.15:raise ValueError('Not enough high-confidence floor depth. Use a matte floor and leave a wider margin.')
    ids=np.flatnonzero(valid)[::max(1,int(valid.sum()/6000))]
    x,y,z=xx.flat[ids],yy.flat[ids],depth.flat[ids]
    if np.ptp(x)<.6*w or np.ptp(y)<.6*h:raise ValueError('Reliable depth needs to surround the garment.')
    rays=np.column_stack((x,y,np.ones(len(x))))@camera_inverse(depth.shape,K).T
    inv=1/z;weights=np.ones(len(z))
    for _ in range(7):
        coef=np.linalg.lstsq(rays*weights[:,None],inv*weights,rcond=None)[0]
        residual=np.abs(inv-rays@coef);robust=max(1e-6,1.4826*float(np.median(residual)))
        weights=np.sqrt(np.minimum(1.,1.5*robust/np.maximum(residual,1e-9)))
    predicted=rays@coef
    if np.any(predicted<=0):raise ValueError('The sensor floor plane is invalid.')
    errors=np.abs(1/predicted-z)/z
    p50,p90=float(np.median(errors)),float(np.percentile(errors,90))
    if p50>.02 or p90>.06:raise ValueError('Depth does not support one flat floor. Retake with the garment flat.')
    normal=coef/np.linalg.norm(coef);tilt=math.degrees(math.acos(np.clip(normal[2],-1,1)))
    if tilt>30:raise ValueError('Hold the rear camera more nearly parallel to the garment.')
    distance=1/coef[2]
    if not .35<=distance<=3.5:raise ValueError('The floor is outside the close-up capture range.')
    return coef,{'floor_depth_m':round(float(distance),3),'plane_residual_pct':round(p50*100,2),
                 'plane_p90_pct':round(p90*100,2),'tilt_deg':round(tilt,2),
                 'high_confidence_floor_fraction':round(float(valid.mean()),3)}

def process(photo,depth,confidence,K,kind):
    _,_,_,mask=outline(photo,kind)
    # Record3D depth and RGB share optical geometry at different resolutions.
    scaled=np.asarray(K,np.float64).copy()
    scaled[0,:]*=depth.shape[1]/photo.shape[1]
    scaled[1,:]*=depth.shape[0]/photo.shape[0]
    coef,diagnostics=fit_sensor_floor(depth,confidence,mask,scaled)
    rect,projected,scale=rectify_plane(photo,mask,coef,K)
    rect,_,rows,_=outline(rect,kind,projected)
    for row in rows:row.value_cm=round(row.value_cm*scale,1)
    diagnostics['mm_per_px']=scale
    return rect,{'ok':True,'mode':'lidar','garment_type':kind,
                 'rows':[{'name':r.name,'value_cm':r.value_cm,'p1':r.p1,'p2':r.p2} for r in rows],
                 'diagnostics':diagnostics,'notes':[
                     'Scale comes from the supplied rear-LiDAR depth and camera calibration.',
                     'The garment must be laid flat; the floor fit cannot prove that fabric is flat.',
                     'Check each measurement line. Correct distance cannot fix a misplaced crotch or waistband.',
                     'Sensor confidence and a consistent floor are not a validated centimetre-error interval.',
                     'This import path has not been validated on your iPhone or real garments.']}

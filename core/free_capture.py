"""Reference-free research capture. Learned metres are never verified metres.

Keep silhouette landmarks in core.measure. A model supplies a candidate floor
plane; geometric checks may reject it, in which case only proportions survive.
"""
from __future__ import annotations

import math
import cv2
import numpy as np
from core.flatlay import garment_mask, largest_contour, rotate, waistband_tilt
from core.measure import measure
from core.segment import contrast, contrast_check, touches_border


def outline(photo, kind):
    mask = garment_mask(photo)
    cnt = largest_contour(mask) if mask is not None else None
    if cnt is None or cv2.contourArea(cnt) < photo.shape[0] * photo.shape[1] * .08:
        raise ValueError("Couldn't separate the garment. Use a plain contrasting floor and even light.")
    if touches_border(cnt, photo.shape):
        raise ValueError("An edge is cropped. Leave space around the whole garment and retake.")
    status, message = contrast_check(contrast(photo, mask))
    if status == "refuse":
        raise ValueError(message)
    if kind == "jeans":
        angle = waistband_tilt(mask)
        if abs(angle) > 20:
            raise ValueError("Straighten the waistband across the top of the photo.")
    else:
        angle = 0
    rect, aligned = rotate(photo, angle, (255, 255, 255)), rotate(mask, angle)
    # Same sustained waistband rule as phone.hardware_measure, without hardware.
    if kind == "jeans":
        ys = np.flatnonzero(aligned.any(axis=1))
        top, bottom = int(ys[0]), int(ys[-1])
        widths = []
        for yy in range(top, min(bottom, top + max(10, int((bottom-top)*.08)))):
            xs = np.flatnonzero(aligned[yy])
            widths.append(int(xs[-1]-xs[0]) if xs.size else 0)
        threshold = .85 * float(np.percentile(widths, 75))
        for offset in range(max(0, len(widths)-3)):
            if all(v >= threshold for v in widths[offset:offset+3]):
                aligned[:top+offset] = 0
                break
    cnt = largest_contour(aligned)
    if cnt is None or touches_border(cnt, aligned.shape):
        raise ValueError("Straightening clipped the outline. Leave a larger margin and retake.")
    rows = measure(cnt, kind, 1.)
    if len(rows) < 5:
        raise ValueError("Couldn't identify the garment's landmarks. Separate the legs or smooth the sleeves.")
    if kind == "jeans":
        by = {r.name: r for r in rows}
        if not .60 <= by['waist_flat'].value_cm / max(by['hip_flat'].value_cm, .1) <= 1.25:
            raise ValueError("The waistband outline is unreliable. Smooth it flat and retake.")
    return rect, aligned, rows, mask


def focal_from_diagonal_fov(shape, diagonal_fov=84.):
    if not math.isfinite(diagonal_fov) or not 40 <= diagonal_fov <= 110:
        raise ValueError("Camera field of view must be between 40 and 110 degrees.")
    h, w = shape[:2]
    return math.hypot(w, h) / (2 * math.tan(math.radians(diagonal_fov)/2))


def floor_plane(depth, mask, focal_px):
    """Robust fit: inverse Z = a*x/f + b*y/f + c on background only.

    Good residuals test consistency, NOT absolute accuracy. Repeated model bias
    can fit a perfect plane and still be metres away from the actual floor.
    """
    if depth.shape != mask.shape or not np.isfinite(depth).all() or np.any(depth <= 0):
        raise ValueError("The depth model returned an invalid map; no metric scale is available.")
    h, w = mask.shape
    radius = max(5, int(max(h,w)*.025))
    excluded = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2*radius+1,2*radius+1)))
    yy, xx = np.indices(mask.shape)
    valid = (excluded == 0) & (xx > .025*w) & (xx < .975*w) & (yy > .025*h) & (yy < .975*h)
    if valid.mean() < .15:
        raise ValueError("Not enough floor is visible to check depth. Leave a wider margin.")
    ids = np.flatnonzero(valid)[::max(1, int(valid.sum()/6000))]
    x, y, z = xx.flat[ids], yy.flat[ids], depth.flat[ids]
    if np.ptp(x) < .6*w or np.ptp(y) < .6*h:
        raise ValueError("Floor depth is only visible on one side. Include floor around every edge.")
    rays = np.column_stack(((x-(w-1)/2)/focal_px,(y-(h-1)/2)/focal_px,np.ones(len(x))))
    inv = 1/z
    weights = np.ones(len(z))
    for _ in range(7):
        coef = np.linalg.lstsq(rays*weights[:,None],inv*weights,rcond=None)[0]
        residual = np.abs(inv-rays@coef)
        robust = max(1e-6, 1.4826*float(np.median(residual)))
        weights = np.sqrt(np.minimum(1., 1.5*robust/np.maximum(residual,1e-9)))
    prediction = rays@coef
    if np.any(prediction <= 0):
        raise ValueError("The inferred floor plane folds behind the camera. Retake straight down.")
    relative = np.abs(1/prediction-z)/z
    median, p90 = float(np.median(relative)), float(np.percentile(relative,90))
    normal = coef/np.linalg.norm(coef)
    tilt = math.degrees(math.acos(np.clip(normal[2],-1,1)))
    if median > .04 or p90 > .12:
        raise ValueError("The model cannot explain the floor as a flat plane. Showing proportions instead of guessing centimetres.")
    if tilt > 30:
        raise ValueError("The inferred floor is too tilted. Hold the camera parallel to the floor.")
    centre_depth = float(1/coef[2])
    if not .35 <= centre_depth <= 3.5:
        raise ValueError("The inferred camera distance is outside this close-up experiment. Showing proportions only.")
    return coef, {"floor_depth_m":round(centre_depth,2),"plane_residual_pct":round(median*100,1),
                  "plane_p90_pct":round(p90*100,1),"tilt_deg":round(tilt,1)}


def rectify_plane(photo, mask, coef, focal_px):
    h,w = mask.shape
    normal = coef / np.linalg.norm(coef)
    horizontal = np.array([1.,0.,0.])-normal*normal[0]
    horizontal /= np.linalg.norm(horizontal)
    vertical = np.cross(normal,horizontal)
    intrinsic_inv = np.array([[1/focal_px,0,-(w-1)/(2*focal_px)],
                              [0,1/focal_px,-(h-1)/(2*focal_px)],[0,0,1.]])
    homography = np.stack((horizontal,vertical,coef))@intrinsic_inv
    corners = np.array([[0,0],[w-1,0],[w-1,h-1],[0,h-1]],np.float32)
    projected = cv2.perspectiveTransform(corners[None],homography)[0]
    if not np.isfinite(projected).all():
        raise ValueError("The floor projection is invalid.")
    lo, hi = projected.min(axis=0), projected.max(axis=0)
    extent = hi-lo
    if (extent <= 0).any() or extent.max() > 10:
        raise ValueError("The floor projection is implausible for this capture.")
    mm_per_px = max(1.,float(extent.max()*1000/1700))
    s = 1000/mm_per_px
    target = np.array([[s,0,-lo[0]*s],[0,s,-lo[1]*s],[0,0,1]])@homography
    size = tuple(int(math.ceil(v*s))+1 for v in extent)
    return (cv2.warpPerspective(photo,target,size,borderValue=(255,255,255)),
            cv2.warpPerspective(mask,target,size,flags=cv2.INTER_NEAREST),mm_per_px)


def depth_measure(photo, kind, depth, focal_px):
    _,_,_,mask = outline(photo,kind)
    coef, diagnostics = floor_plane(depth,mask,focal_px)
    rect, projected, scale = rectify_plane(photo,mask,coef,focal_px)
    # Reuse outline rules after the plane warp; do not segment the depth map.
    rect, _, rows, _ = outline(rect,kind)
    for row in rows:
        row.value_cm = round(row.value_cm*scale,1)
        row.tolerance_cm = round(max(3.,row.value_cm*.40),1)
    diagnostics['mm_per_px'] = scale
    return rect,rows,diagnostics


def disagreement(first, second):
    a={r.name:r.value_cm for r in first};b={r.name:r.value_cm for r in second}
    points=('waist_flat','inseam') if 'waist_flat' in a else ('pit_to_pit','length')
    return max(abs(a[p]-b[p])/max((a[p]+b[p])/2,.1) for p in points if p in a and p in b)

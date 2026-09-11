"""Synthetic validation harness.

Builds a metric scene: a calibration mat (4 ArUco markers near the corners) with a
garment polygon of EXACTLY known real-world dimensions laid in the middle. Then applies
a perspective warp to simulate an oblique camera photo. The pipeline must invert this
using only the markers and recover the true measurements.

"Plant hidden ground truth and recover it on a distorted image" — the shield against
"did you tune it to your demo?". The garment is measured independently of the markers.
"""

from __future__ import annotations

import cv2
import numpy as np

from core.calibrate import make_marker, DEFAULT_MAT_LAYOUT, MAT_MM, MAT_MARKER_MM

MM_PER_PX = 0.5


def _mm(v):
    return v / MM_PER_PX


def tshirt_polygon(body_left=240.0, top=320.0, bw=520.0, bl=720.0,
                   sw=200.0, sl=120.0, neck_w=170.0, neck_d=35.0, taper=10.0):
    """Return (polygon_px Nx2, ground_truth_cm dict). All inputs in mm."""
    bx, ty = body_left, top
    verts_mm = [
        (bx,                      ty),
        (bx + (bw - neck_w) / 2,  ty),
        (bx + (bw - neck_w) / 2,  ty + neck_d),
        (bx + (bw + neck_w) / 2,  ty + neck_d),
        (bx + (bw + neck_w) / 2,  ty),
        (bx + bw,                 ty),
        (bx + bw + sl,            ty),
        (bx + bw + sl,            ty + sw),
        (bx + bw,                 ty + sw),       # right armpit
        (bx + bw - taper,         ty + bl),
        (bx + taper,              ty + bl),
        (bx,                      ty + sw),       # left armpit
        (bx - sl,                 ty + sw),
        (bx - sl,                 ty),
    ]
    poly_px = np.array([[_mm(x), _mm(y)] for x, y in verts_mm], dtype=np.int32)
    gt = {
        "length": round(bl / 10.0, 1),
        "pit_to_pit": round(bw / 10.0, 1),
        "hem_width": round((bw - 2 * taper) / 10.0, 1),
        "shoulder_width": round(bw / 10.0, 1),
        "sleeve_length": round(sl / 10.0, 1),
    }
    return poly_px, gt


def build_mat(poly_px) -> np.ndarray:
    """The perfect metric top-down image: garment on a 4-marker calibration mat."""
    w = int(MAT_MM[0] / MM_PER_PX)
    h = int(MAT_MM[1] / MM_PER_PX)
    img = np.full((h, w, 3), 255, np.uint8)

    cv2.fillPoly(img, [poly_px], (40, 40, 220))   # garment: solid red (BGR)

    side = int(MAT_MARKER_MM / MM_PER_PX)
    for mid, (mx, my) in DEFAULT_MAT_LAYOUT.items():
        marker = cv2.cvtColor(make_marker(mid, side), cv2.COLOR_GRAY2BGR)
        x0, y0 = int(mx / MM_PER_PX), int(my / MM_PER_PX)
        img[y0:y0 + side, x0:x0 + side] = marker
    return img


def simulate_photo(rectified: np.ndarray, tilt: float = 0.08, blur: float = 0.6) -> np.ndarray:
    """Perspective warp (oblique camera) + mild blur to make a 'photo'."""
    h, w = rectified.shape[:2]
    t = tilt
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    dst = np.float32([
        [t * w,             0.5 * t * h],
        [(1 - 0.6 * t) * w, 0],
        [w,                 h],
        [0.4 * t * w,       (1 - 0.4 * t) * h],
    ])
    H = cv2.getPerspectiveTransform(src, dst)
    photo = cv2.warpPerspective(rectified, H, (w, h), borderValue=(255, 255, 255))
    if blur > 0:
        photo = cv2.GaussianBlur(photo, (0, 0), blur)
    return photo


def make_tshirt_photo(tilt=0.08, blur=0.6, **poly_kwargs):
    poly, gt = tshirt_polygon(**poly_kwargs)
    mat = build_mat(poly)
    photo = simulate_photo(mat, tilt=tilt, blur=blur)
    return photo, gt


def jeans_polygon(wl=300.0, top=200.0, waist=400.0, rise=300.0, inseam=620.0,
                  leg_open=180.0):
    """Straight-leg jeans laid flat. leg_open drives leg width; the gap between legs is
    derived (= waist - 2*leg_open, so waist must exceed 2*leg_open). Returns
    (polygon_px, ground_truth_cm)."""
    total = rise + inseam
    inner_l = wl + leg_open               # left leg inner edge
    inner_r = wl + waist - leg_open       # right leg inner edge
    verts_mm = [
        (wl,          top),
        (wl + waist,  top),
        (wl + waist,  top + total),     # right outer hem
        (inner_r,     top + total),     # right inner hem
        (inner_r,     top + rise),      # right crotch corner
        (inner_l,     top + rise),      # left crotch corner
        (inner_l,     top + total),     # left inner hem
        (wl,          top + total),     # left outer hem
    ]
    poly_px = np.array([[_mm(x), _mm(y)] for x, y in verts_mm], dtype=np.int32)
    gt = {
        "waist_flat": round(waist / 10.0, 1),
        "hip_flat": round(waist / 10.0, 1),          # straight cut: hip == waist
        "inseam": round(inseam / 10.0, 1),
        "leg_opening": round(leg_open / 10.0, 1),
        "thigh": round(leg_open / 10.0, 1),          # straight leg: thigh == hem
    }
    return poly_px, gt


def make_jeans_photo(tilt=0.08, blur=0.6, **poly_kwargs):
    poly, gt = jeans_polygon(**poly_kwargs)
    mat = build_mat(poly)
    photo = simulate_photo(mat, tilt=tilt, blur=blur)
    return photo, gt

"""Fabric and lighting for the simulated photos.

The scene is built as two layers — albedo (the colour a surface would be under flat light)
and height in millimetres — and then lit once by a single directional light. Doing it that
way is what makes folds, seams and the twill weave read as cloth rather than as a drawing:
every shadow in the photo comes from the same light hitting the same surface.

Used by validation/render_scene.py.
"""

from __future__ import annotations

import math

import cv2
import numpy as np

# indoor light from the top-left, roughly 45 degrees up, plus soft fill from the room
LIGHT = np.array([-0.42, -0.52, 0.74], np.float32)
LIGHT /= np.linalg.norm(LIGHT)
AMBIENT = 0.52


def noise(shape, scale_px, rng, octaves=3):
    """Smooth fractal noise, unit variance."""
    h, w = shape
    out = np.zeros(shape, np.float32)
    amp = 1.0
    for o in range(octaves):
        s = max(2, int(scale_px / (2 ** o)))
        small = rng.standard_normal((h // s + 2, w // s + 2)).astype(np.float32)
        out += amp * cv2.resize(small, (w, h), interpolation=cv2.INTER_CUBIC)
        amp *= 0.5
    out -= out.mean()
    return out / (out.std() + 1e-6)


def ridge_noise(shape, scale_px, rng):
    """Fold-like noise: creases rather than blobs (|noise| inverted)."""
    n = noise(shape, scale_px, rng, octaves=2)
    r = 1.0 - np.abs(n) / (np.abs(n).max() + 1e-6)
    return (r - r.mean()) / (r.std() + 1e-6)


def twill(shape, mm_per_px, period_mm=1.4, angle_deg=63.0):
    """Denim's diagonal rib. Returns a wave in [-1, 1] running at the twill angle."""
    h, w = shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    a = math.radians(angle_deg)
    d = (xx * math.cos(a) + yy * math.sin(a)) * mm_per_px
    return np.sin(2 * math.pi * d / period_mm)


def weave(shape, mm_per_px, rng, period_mm=0.8):
    """Plain weave for jersey/paper: two crossed carrier waves plus yarn noise."""
    h, w = shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    p = period_mm / mm_per_px
    return (np.sin(2 * math.pi * xx / p) * np.sin(2 * math.pi * yy / p) * 0.6
            + noise(shape, 3, rng, octaves=1) * 0.4)


def shade(albedo, height_mm, mm_per_px, spec=0.0, shine=40.0, ambient=AMBIENT, light=LIGHT):
    """Light an albedo map with a height map. Height in mm, pixel pitch in mm."""
    gx = cv2.Sobel(height_mm, cv2.CV_32F, 1, 0, ksize=3) / (8 * mm_per_px)
    gy = cv2.Sobel(height_mm, cv2.CV_32F, 0, 1, ksize=3) / (8 * mm_per_px)
    nz = 1.0 / np.sqrt(gx * gx + gy * gy + 1.0)
    nx, ny = -gx * nz, -gy * nz
    lam = np.clip(nx * light[0] + ny * light[1] + nz * light[2], 0, None)
    lit = ambient + (1.0 - ambient) * lam
    out = albedo * lit[..., None]
    if spec > 0:
        view = np.array([0, 0, 1], np.float32)
        hv = light + view
        hv /= np.linalg.norm(hv)
        ndh = np.clip(nx * hv[0] + ny * hv[1] + nz * hv[2], 0, None)
        out += (spec * np.power(ndh, shine))[..., None] * 255.0
    return out


def ambient_occlusion(mask_f, radius_px, strength=0.35):
    """Darkening in the crease where a raised object meets the surface below it."""
    return 1.0 - strength * cv2.GaussianBlur(mask_f, (0, 0), radius_px) * (1.0 - mask_f)


def cast_shadow(mask_f, height_mm, mm_per_px, light=LIGHT, softness_px=7.0, strength=0.5):
    """Shadow thrown by an object standing `height_mm` above the surface."""
    off = height_mm / mm_per_px * light[:2] / max(light[2], 1e-3)
    M = np.float32([[1, 0, -off[0]], [0, 1, -off[1]]])
    sh = cv2.warpAffine(mask_f, M, (mask_f.shape[1], mask_f.shape[0]))
    sh = cv2.GaussianBlur(sh, (0, 0), softness_px)
    return 1.0 - strength * np.clip(sh - mask_f, 0, 1)


def feathered_mask(poly_px, shape, rng, fuzz_px=1.6):
    """Anti-aliased garment mask whose edge wobbles by a fibre's width, so the silhouette
    doesn't look laser-cut."""
    h, w = shape
    m = np.zeros((h, w), np.uint8)
    cv2.fillPoly(m, [np.round(poly_px * 4).astype(np.int32)], 255, lineType=cv2.LINE_AA, shift=2)
    f = m.astype(np.float32) / 255.0
    f = np.clip(f + noise((h, w), 6, rng, octaves=2) * 0.25 * (f * (1 - f) * 4), 0, 1)
    return cv2.GaussianBlur(f, (0, 0), fuzz_px * 0.5)


def polyline_field(shape, polys_px, width_px, blur_px=0.0):
    """Rasterise polylines into a float field (1 on the line), optionally blurred."""
    f = np.zeros(shape, np.float32)
    for p in polys_px:
        cv2.polylines(f, [np.int32(p)], False, 1.0, int(max(1, width_px)), cv2.LINE_AA)
    if blur_px:
        f = cv2.GaussianBlur(f, (0, 0), blur_px)
        f /= f.max() + 1e-6
    return f

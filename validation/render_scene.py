"""Render realistic *simulated* phone photos of garments on the printed FitTag kit.

The older harness (tests/synth.py) draws a flat red polygon on white paper. That proves the
geometry but says nothing about real photos. This script builds a harder scene:

  - a light bedsheet with wrinkles and uneven lighting as the backdrop
  - the four real A4 corner sheets from print/ laid out as the placement guide says,
    each nudged by a few mm (people don't tape perfectly)
  - a garment with a curved silhouette, fabric texture, seams, fading and a drop shadow
  - a handheld camera: tilted, slightly rotated, lens vignetting, sensor noise, JPEG

Ground truth comes from the garment's design dimensions (in mm), measured the way a person
with a tape measure would. The pipeline only ever sees the photo.

It is still simulated — a real photo of a real garment is the test that matters.

    python -m validation.render_scene        # -> validation/scenes/*.jpg + scenes.json
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import cv2
import numpy as np

from core.calibrate import MAT_MM

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = HERE / "scenes"

PX = 0.5                                  # scene raster: mm per pixel
MARGIN = 700.0                            # backdrop around the mat (mm), wide enough that the camera never sees past it
SCENE_MM = (MAT_MM[0] + 2 * MARGIN, MAT_MM[1] + 2 * MARGIN)
A4 = (210.0, 297.0)
SHEET_ORIGIN = {0: (0.0, 0.0), 1: (MAT_MM[0] - A4[0], 0.0),
                2: (MAT_MM[0] - A4[0], MAT_MM[1] - A4[1]), 3: (0.0, MAT_MM[1] - A4[1])}
SHEET_FILES = {0: "mat_corner_0_top_left.png", 1: "mat_corner_1_top_right.png",
               2: "mat_corner_2_bottom_right.png", 3: "mat_corner_3_bottom_left.png"}


def px(v_mm: float) -> float:
    return v_mm / PX


def mat_to_scene(x_mm, y_mm):
    return px(x_mm + MARGIN), px(y_mm + MARGIN)


def set_margin(mm: float):
    """Smaller backdrop = faster renders (used by the robustness sweep)."""
    global MARGIN, SCENE_MM
    MARGIN = mm
    SCENE_MM = (MAT_MM[0] + 2 * MARGIN, MAT_MM[1] + 2 * MARGIN)


# ---------------------------------------------------------------------------- scene layers

from validation.fabric import (LIGHT, ambient_occlusion, cast_shadow, feathered_mask, noise,
                               polyline_field, ridge_noise, shade, twill, weave)


def smooth_noise(shape, scale_px, rng, octaves=3):        # kept for the sweep's older calls
    return noise(shape, scale_px, rng, octaves)


def backdrop(shape, rng, base=(214, 216, 219)):
    """A cotton sheet: albedo with weave and dye variation, height with soft folds."""
    h, w = shape
    alb = np.ones((h, w, 3), np.float32) * np.array(base, np.float32)
    alb *= (1 + 0.035 * weave(shape, PX, rng, period_mm=1.1))[..., None]
    alb *= (1 + 0.03 * noise(shape, 400, rng))[..., None]
    # a sheet that's been folded and shaken out: a few long, nearly straight creases plus
    # very gentle undulation — not the blobby dunes that plain noise gives
    h_, w_ = shape
    lines = []
    for _ in range(rng.integers(3, 6)):
        if rng.random() < 0.5:
            y0 = rng.uniform(0.1, 0.9) * h_
            lines.append(np.array([[0, y0], [w_, y0 + rng.uniform(-0.04, 0.04) * h_]], np.float32))
        else:
            x0 = rng.uniform(0.1, 0.9) * w_
            lines.append(np.array([[x0, 0], [x0 + rng.uniform(-0.04, 0.04) * w_, h_]], np.float32))
    crease = polyline_field(shape, lines, max(3, px(4.0)), blur_px=px(9.0))
    hgt = crease * 1.7 + noise(shape, 900, rng, octaves=2) * 0.7 + noise(shape, 120, rng, octaves=2) * 0.25
    return alb, hgt


def paste_sheets(alb, hgt, rng, jitter_mm=2.5, missing=()):
    """Lay the real printed A4 sheets on the backdrop. Returns their placement error and a
    mask of paper, which sits ~0.4 mm proud of the sheet and curls slightly at the edges."""
    placed, paper = {}, np.zeros(alb.shape[:2], np.float32)
    H, W = alb.shape[:2]
    for mid, fname in SHEET_FILES.items():
        if mid in missing:          # simulate a sheet that's covered or out of frame
            continue
        sheet = cv2.imread(str(ROOT / "print" / fname), cv2.IMREAD_COLOR)
        sw, sh = int(round(px(A4[0]))), int(round(px(A4[1])))
        sheet = cv2.resize(sheet, (sw, sh), interpolation=cv2.INTER_AREA).astype(np.float32)
        ox, oy = SHEET_ORIGIN[mid]
        dx, dy = rng.uniform(-jitter_mm, jitter_mm, 2)
        rot = rng.uniform(-0.6, 0.6)
        cx, cy = mat_to_scene(ox + A4[0] / 2 + dx, oy + A4[1] / 2 + dy)
        M = cv2.getRotationMatrix2D((sw / 2, sh / 2), rot, 1.0)
        M[0, 2] += cx - sw / 2
        M[1, 2] += cy - sh / 2
        warped = cv2.warpAffine(sheet, M, (W, H), flags=cv2.INTER_LINEAR)
        m = cv2.warpAffine(np.ones((sh, sw), np.float32), M, (W, H), flags=cv2.INTER_LINEAR)
        paper = np.maximum(paper, m)
        paper_tint = np.array([246, 248, 250], np.float32) / 255.0
        alb[:] = alb * (1 - m[..., None]) + warped * paper_tint * m[..., None]
        placed[mid] = (float(dx), float(dy), float(rot))
    if paper.max() > 0:
        d = cv2.distanceTransform((paper > 0.5).astype(np.uint8), cv2.DIST_L2, 5) * PX   # mm
        curl = np.clip(1.0 - d / 30.0, 0, 1) ** 2 * 0.9                                  # edges lift
        hgt += paper * (0.4 + curl)
        hgt += paper * noise(alb.shape[:2], 300, rng) * 0.3                              # not dead flat
    return placed, paper


def garment_layers(shape, outline_mm, details_mm, rng, base_bgr, kind="denim", fades=None, patches_mm=None):
    """Albedo, height (mm) and coverage for one garment laid flat."""
    H, W = shape
    poly = np.array([mat_to_scene(x, y) for x, y in outline_mm], np.float32)
    # a real flat-lay is never perfectly symmetric: wobble the outline by up to ~1.5 mm and
    # lay the garment down a degree or so off straight. Both are far inside the error bars.
    c0 = poly.mean(0)
    nrm = poly - np.roll(poly, 1, 0)
    nrm = np.stack([-nrm[:, 1], nrm[:, 0]], 1)
    nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-6
    wob = np.convolve(rng.standard_normal(len(poly)), np.ones(31) / 31, mode="same")
    poly = poly + nrm * (wob / (np.abs(wob).max() + 1e-6) * px(1.5))[:, None]
    th = math.radians(rng.uniform(-1.5, 1.5))
    rot = np.array([[math.cos(th), -math.sin(th)], [math.sin(th), math.cos(th)]], np.float32)
    poly = (poly - c0) @ rot.T + c0
    cover = feathered_mask(poly, shape, rng)
    hard = (cover > 0.5).astype(np.uint8)
    dist_mm = cv2.distanceTransform(hard, cv2.DIST_L2, 5) * PX

    alb = np.ones((H, W, 3), np.float32) * np.array(base_bgr, np.float32)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)

    if kind == "denim":
        tw = twill(shape, PX)
        # indigo warp over white weft: the diagonal rib is lighter where the weft shows
        alb += (np.clip(tw, 0, None) * 9)[..., None] * np.array([1.05, 1.0, 0.95], np.float32)
        alb -= (np.clip(-tw, 0, None) * 5)[..., None]
        alb *= (1 + 0.05 * noise(shape, 6, rng, octaves=1))[..., None]           # yarn slubs
        alb *= (1 + 0.04 * noise(shape, 500, rng))[..., None]                    # dye variation
        if fades:
            wear = np.zeros(shape, np.float32)
            for (fx, fy, r) in fades:
                sx, sy = mat_to_scene(fx, fy)
                wear += np.exp(-(((xx - sx) ** 2) / (2 * (px(r) * 0.7) ** 2) +
                                 ((yy - sy) ** 2) / (2 * px(r) ** 2)))
            streak = cv2.GaussianBlur(rng.standard_normal(shape).astype(np.float32), (0, 0), 1.5)
            streak = cv2.blur(streak, (int(px(60)), 1))                          # smear sideways
            streak /= np.abs(streak).max() + 1e-6
            wear = np.clip(wear, 0, 1) * np.clip(0.55 + 1.1 * streak, 0, 1)
            alb += wear[..., None] * np.array([26, 21, 15], np.float32)
        micro = twill(shape, PX) * 0.05                                          # rib relief, mm
    else:
        alb *= (1 + 0.05 * weave(shape, PX, rng, period_mm=0.7))[..., None]
        alb *= (1 + 0.04 * noise(shape, 400, rng))[..., None]
        micro = weave(shape, PX, rng, period_mm=0.7) * 0.03

    # height: thickness, edge roll-off, folds and creases
    hgt = np.full(shape, 1.1, np.float32)
    hgt -= np.clip(1.0 - dist_mm / 6.0, 0, 1) ** 1.5 * 1.0                       # edges settle
    # creases run mostly along the garment: smear the fold field vertically so it reads as
    # cloth folded lengthwise, not as camouflage
    folds = ridge_noise(shape, 90, rng)
    folds = cv2.blur(folds, (1, int(px(70))))
    folds /= folds.std() + 1e-6
    hgt += folds * 2.2 + noise(shape, 500, rng, octaves=2) * 1.2 + noise(shape, 25, rng, octaves=1) * 0.25
    hgt += micro

    # raised pieces (waistband, belt loops, coin pocket): another layer of cloth
    patch_edges = []
    for name, quad in (patches_mm or {}).items():
        q = np.array([mat_to_scene(x, y) for x, y in quad], np.float32)
        q = (q - c0) @ rot.T + c0
        pm = np.zeros(shape, np.float32)
        cv2.fillPoly(pm, [np.round(q * 4).astype(np.int32)], 1.0, lineType=cv2.LINE_AA, shift=2)
        pm = cv2.GaussianBlur(pm, (0, 0), 1.2)
        hgt += pm * (1.0 if name == "band" else 0.8)
        alb *= (1 - 0.05 * pm)[..., None]
        patch_edges.append(np.vstack([q, q[:1]]))
    # seams, topstitching and hems: ridges in the height map, thread in the albedo
    seam_polys, hem_polys = [], []
    for name, pts in details_mm.items():
        p = np.array([mat_to_scene(x, y) for x, y in (_smooth_poly(pts, 2) if len(pts) > 2 else pts)], np.float32)
        p = (p - c0) @ rot.T + c0
        (hem_polys if name.startswith("hem") or name == "band" else seam_polys).append(p)
    seam_polys += patch_edges
    seam = polyline_field(shape, seam_polys, max(3, px(1.6)), blur_px=px(0.8))
    hem = polyline_field(shape, hem_polys, max(4, px(3.0)), blur_px=px(1.2))
    hgt += seam * 0.55 + hem * 0.85
    alb *= (1 - 0.16 * seam)[..., None]                                          # seam crease reads darker
    if kind == "denim":
        thread = np.zeros(shape, np.float32)
        for p in seam_polys + hem_polys:
            d = np.diff(p, axis=0)
            n = np.stack([-d[:, 1], d[:, 0]], 1)
            n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-6
            off = np.vstack([p[:-1] + n * px(2.2), p[-1:] + n[-1:] * px(2.2)])
            for a, b in zip(off[:-1], off[1:]):
                steps = max(1, int(np.linalg.norm(b - a) / px(2.5)))
                for k in range(0, steps, 2):                                     # dashed stitches
                    s0 = a + (b - a) * k / steps
                    s1 = a + (b - a) * min(k + 1.2, steps) / steps
                    cv2.line(thread, tuple(np.int32(s0)), tuple(np.int32(s1)), 1.0,
                             int(max(1, px(0.7))), cv2.LINE_AA)
        thread = np.clip(thread, 0, 1)
        alb = alb * (1 - thread)[..., None] + thread[..., None] * np.array([70, 150, 205], np.float32)
        hgt += thread * 0.35
    return alb, hgt, cover


def place_card(alb, hgt, rng, centre_mm, angle_deg=None, card_mm=(85.60, 53.98)):
    """A bank card lying on the garment: ID-1 size (85.60 x 53.98 mm, ISO/IEC 7810), rounded
    corners, matte plastic with a chip. Used by the markerless 'card mode' scenes."""
    H, W = alb.shape[:2]
    ang = rng.uniform(0, 180) if angle_deg is None else angle_deg
    cw, ch = px(card_mm[0]), px(card_mm[1])
    card = np.zeros((int(ch) + 2, int(cw) + 2, 3), np.float32)
    base = np.array(rng.choice([[232, 234, 236], [206, 214, 219], [188, 205, 216],
                                [96, 90, 86]]) if False else
                    [[232, 234, 236], [206, 214, 219], [188, 205, 216]][int(rng.integers(0, 3))],
                    np.float32)
    card[:] = base
    gy = np.linspace(0.85, 1.15, card.shape[0], dtype=np.float32)[:, None, None]
    card *= gy
    cv2.rectangle(card, (int(px(8)), int(px(16))), (int(px(8 + 12)), int(px(16 + 9))),
                  (90, 170, 200), -1)                                   # chip
    cv2.putText(card, "1234 5678", (int(px(8)), int(px(40))), cv2.FONT_HERSHEY_DUPLEX,
                px(0.9) / 10, (70, 70, 75), max(1, int(px(0.5))), cv2.LINE_AA)
    m = np.zeros(card.shape[:2], np.float32)
    r = int(px(3.2))                                                     # corner radius
    cv2.rectangle(m, (r, 0), (m.shape[1] - r, m.shape[0]), 1.0, -1)
    cv2.rectangle(m, (0, r), (m.shape[1], m.shape[0] - r), 1.0, -1)
    for cx0, cy0 in ((r, r), (m.shape[1] - r, r), (r, m.shape[0] - r), (m.shape[1] - r, m.shape[0] - r)):
        cv2.circle(m, (cx0, cy0), r, 1.0, -1)
    M = cv2.getRotationMatrix2D((card.shape[1] / 2, card.shape[0] / 2), ang, 1.0)
    sx, sy = mat_to_scene(*centre_mm)
    M[0, 2] += sx - card.shape[1] / 2
    M[1, 2] += sy - card.shape[0] / 2
    warped = cv2.warpAffine(card, M, (W, H), flags=cv2.INTER_LINEAR)
    wm = cv2.warpAffine(m, M, (W, H), flags=cv2.INTER_LINEAR)
    alb[:] = alb * (1 - wm[..., None]) + warped * wm[..., None]
    hgt += wm * 0.76                                                     # cards are 0.76 mm thick
    return wm


# ---------------------------------------------------------------------------- garments

def _densify(pts, step=12.0):
    p = np.asarray(pts, np.float64)
    out = []
    for a, b in zip(p, np.roll(p, -1, 0)):
        n = max(1, int(np.linalg.norm(b - a) / step))
        out += [a + (b - a) * k / n for k in range(n)]
    return np.array(out)


def _smooth_poly(pts, iters=2):
    """Chaikin corner cutting on a densified outline: corners round off by a few mm
    (like real fabric) without eating whole hems or cuffs."""
    p = _densify(pts)
    for _ in range(iters):
        q = 0.75 * p + 0.25 * np.roll(p, -1, 0)
        r = 0.25 * p + 0.75 * np.roll(p, -1, 0)
        p = np.empty((2 * len(q), 2))
        p[0::2], p[1::2] = q, r
    return p


def jeans_shape(cx, top, waist, hip, rise, inseam, thigh, opening, band=40.0):
    """Five-pocket jeans laid flat, dimensions in mm (all flat measurements).

    Returns (outline pts in mat mm, detail lines, ground truth in cm)."""
    crotch_y = top + rise
    hem_y = crotch_y + inseam
    # legs splay slightly: inner edges part from the crotch point
    gap_hem = 2 * thigh - (hip)            # keeps outer edge roughly straight from hip
    gap_hem = max(40.0, gap_hem + 60.0)
    outer_hem = gap_hem / 2 + opening
    pts = [
        (cx - waist / 2, top), (cx + waist / 2, top),
        (cx + waist / 2 + 2, top + band),
        (cx + hip / 2, top + 0.62 * rise),
        (cx + hip / 2, crotch_y),
        (cx + outer_hem, hem_y), (cx + gap_hem / 2, hem_y),
        (cx + 3, crotch_y + 4), (cx, crotch_y), (cx - 3, crotch_y + 4),
        (cx - gap_hem / 2, hem_y), (cx - outer_hem, hem_y),
        (cx - hip / 2, crotch_y),
        (cx - hip / 2, top + 0.62 * rise),
        (cx - waist / 2 - 2, top + band),
    ]
    # keep waistband and hems crisp, soften the rest
    soft = _smooth_poly(pts, 1)
    # thigh by the usual tape-measure convention: one leg, 25 mm below the crotch
    d = 25.0 / inseam
    thigh_w = (hip / 2 + (outer_hem - hip / 2) * d) - (gap_hem / 2) * d
    gt = {"waist_flat": waist / 10, "hip_flat": hip / 10, "inseam": inseam / 10,
          "leg_opening": opening / 10, "thigh": round(thigh_w / 10, 1)}
    band_y = top + band
    hip_y = top + 0.62 * rise
    details = {
        "band_top": [(cx - waist / 2 + 4, top + 6), (cx + waist / 2 - 4, top + 6)],
        "band_bot": [(cx - waist / 2 - 1, band_y), (cx + waist / 2 + 1, band_y)],
        "fly": [(cx + 14, band_y), (cx + 40, band_y + 34), (cx + 42, top + 0.58 * rise),
                (cx + 14, top + 0.76 * rise), (cx + 2, top + 0.79 * rise)],
        # slash pockets: waistband down to the side seam, the way front pockets actually sit
        "pocket_l": [(cx - waist / 2 + 18, band_y + 3), (cx - waist / 2 + 4, band_y + 60),
                     (cx - hip / 2 + 6, band_y + 125)],
        "pocket_r": [(cx + waist / 2 - 18, band_y + 3), (cx + waist / 2 - 4, band_y + 60),
                     (cx + hip / 2 - 6, band_y + 125)],
        "seam_l": [(cx - hip / 2 + 7, hip_y), (cx - outer_hem + 7, hem_y - 6)],
        "seam_r": [(cx + hip / 2 - 7, hip_y), (cx + outer_hem - 7, hem_y - 6)],
        "inseam_l": [(cx - 6, crotch_y + 8), (cx - gap_hem / 2 - 6, hem_y - 6)],
        "inseam_r": [(cx + 6, crotch_y + 8), (cx + gap_hem / 2 + 6, hem_y - 6)],
        "hem_l": [(cx - outer_hem + 3, hem_y - 24), (cx - gap_hem / 2 - 3, hem_y - 24)],
        "hem_r": [(cx + gap_hem / 2 + 3, hem_y - 24), (cx + outer_hem - 3, hem_y - 24)],
    }
    # raised pieces: the waistband itself, five belt loops, and a coin pocket
    patches = {"band": [(cx - waist / 2, top), (cx + waist / 2, top),
                        (cx + waist / 2, band_y), (cx - waist / 2, band_y)]}
    for i, fx in enumerate((-0.42, -0.2, 0.0, 0.2, 0.42)):
        lx = cx + fx * waist
        patches[f"loop{i}"] = [(lx - 7, top + 2), (lx + 7, top + 2), (lx + 7, band_y + 12), (lx - 7, band_y + 12)]
    patches["coin"] = [(cx + waist / 2 - 150, band_y + 4), (cx + waist / 2 - 95, band_y + 4),
                       (cx + waist / 2 - 95, band_y + 52), (cx + waist / 2 - 150, band_y + 52)]
    return soft, details, patches, gt, (crotch_y, hem_y, gap_hem)


def tee_shape(cx, top, chest, length, sleeve, sleeve_drop=35.0, neck=180.0):
    """T-shirt laid flat with slightly dropped sleeves."""
    half = chest / 2
    sh_y = top + 25                  # shoulder slope: the side seam top sits lower than the neck
    arm_y = top + 230
    pts = [
        (cx - neck / 2, top), (cx - neck / 4, top + 55), (cx + neck / 4, top + 55),
        (cx + neck / 2, top),
        (cx + half, sh_y),
        (cx + half + sleeve, sh_y + sleeve_drop),
        (cx + half + sleeve, sh_y + sleeve_drop + 175),
        (cx + half, arm_y),
        (cx + half - 6, top + length), (cx - half + 6, top + length),
        (cx - half, arm_y),
        (cx - half - sleeve, sh_y + sleeve_drop + 175),
        (cx - half - sleeve, sh_y + sleeve_drop),
        (cx - half, sh_y),
    ]
    soft = _smooth_poly(pts, 1)
    gt = {"length": length / 10, "pit_to_pit": chest / 10, "hem_width": (chest - 12) / 10,
          "sleeve_length": sleeve / 10}
    details = {
        "collar": [(cx - neck / 2 + 8, top + 4), (cx - neck / 4, top + 64), (cx + neck / 4, top + 64),
                   (cx + neck / 2 - 8, top + 4)],
        "hem": [(cx - half + 10, top + length - 22), (cx + half - 10, top + length - 22)],
        "cuff_l": [(cx - half - sleeve + 20, sh_y + sleeve_drop), (cx - half - sleeve + 20, sh_y + sleeve_drop + 175)],
        "cuff_r": [(cx + half + sleeve - 20, sh_y + sleeve_drop), (cx + half + sleeve - 20, sh_y + sleeve_drop + 175)],
    }
    patches = {
        "hem_band": [(cx - half + 8, top + length - 26), (cx + half - 8, top + length - 26),
                     (cx + half - 8, top + length - 2), (cx - half + 8, top + length - 2)],
        "cuff_l": [(cx - half - sleeve + 6, sh_y + sleeve_drop + 8),
                   (cx - half - sleeve + 30, sh_y + sleeve_drop + 8),
                   (cx - half - sleeve + 30, sh_y + sleeve_drop + 168),
                   (cx - half - sleeve + 6, sh_y + sleeve_drop + 168)],
        "cuff_r": [(cx + half + sleeve - 6, sh_y + sleeve_drop + 8),
                   (cx + half + sleeve - 30, sh_y + sleeve_drop + 8),
                   (cx + half + sleeve - 30, sh_y + sleeve_drop + 168),
                   (cx + half + sleeve - 6, sh_y + sleeve_drop + 168)],
    }
    return soft, details, patches, gt, None


# ---------------------------------------------------------------------------- camera

def handheld_photo(scene, rng, out_size=(1512, 2016), pitch_deg=16, roll_deg=3.0, yaw_deg=2.0,
                   height_mm=1650.0, f_px=1650.0, k1=0.0):
    """Project the floor plane through a pinhole camera held at an angle."""
    Hs, Ws = scene.shape[:2]
    ow, oh = out_size
    K = np.array([[f_px, 0, ow / 2], [0, f_px, oh / 2], [0, 0, 1]], np.float64)

    def rot(ax, deg):
        a = math.radians(deg)
        c, s = math.cos(a), math.sin(a)
        if ax == "x": return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
        if ax == "y": return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
        return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])

    # camera looks straight down (+Z into the floor), then tilts
    R = rot("z", roll_deg) @ rot("x", -pitch_deg) @ rot("y", yaw_deg)
    centre = np.array([SCENE_MM[0] / 2, SCENE_MM[1] / 2, 0.0])
    # step back so the tilted optical axis still hits the scene centre
    axis = R.T @ np.array([0, 0, 1.0])
    cam = centre - axis * (height_mm / axis[2])
    t = -R @ cam
    Hplane = K @ np.column_stack([R[:, 0], R[:, 1], t])          # floor mm -> image
    S = np.diag([PX, PX, 1.0])                                    # scene px -> floor mm
    Himg = Hplane @ S
    photo = cv2.warpPerspective(scene, Himg, (ow, oh), flags=cv2.INTER_AREA,
                                borderMode=cv2.BORDER_REPLICATE)

    if k1:
        # barrel distortion the phone did not correct, as a fraction of the half-diagonal
        yy0, xx0 = np.mgrid[0:oh, 0:ow].astype(np.float32)
        nx, ny = (xx0 - ow / 2) / (ow / 2), (yy0 - oh / 2) / (oh / 2)
        r2 = nx * nx + ny * ny
        f = 1 + k1 * r2
        photo = cv2.remap(photo, (nx * f * ow / 2 + ow / 2).astype(np.float32),
                          (ny * f * oh / 2 + oh / 2).astype(np.float32),
                          cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)

    # lens + sensor
    yy, xx = np.mgrid[0:oh, 0:ow].astype(np.float32)
    r2 = ((xx - ow / 2) ** 2 + (yy - oh / 2) ** 2) / ((ow / 2) ** 2 + (oh / 2) ** 2)
    photo *= (1 - 0.28 * r2)[..., None]
    light = cv2.GaussianBlur(rng.standard_normal((6, 5)).astype(np.float32), (0, 0), 1)
    light = cv2.resize(light, (ow, oh), interpolation=cv2.INTER_CUBIC)
    photo *= (1 + 0.05 * light)[..., None]
    photo *= np.array([0.96, 1.0, 1.05], np.float32)            # warm indoor white balance
    photo = cv2.GaussianBlur(photo, (0, 0), 0.7)
    photo += rng.normal(0, 2.4, photo.shape).astype(np.float32)
    photo = np.clip(photo, 0, 255).astype(np.uint8)
    ok, jpg = cv2.imencode(".jpg", photo, [cv2.IMWRITE_JPEG_QUALITY, 86])
    return cv2.imdecode(jpg, cv2.IMREAD_COLOR), jpg


# ---------------------------------------------------------------------------- scenes

SCENES = [
    dict(name="jeans-charcoal", kind="jeans", seed=7, colour=(78, 74, 72),
         dims=dict(waist=410.0, hip=520.0, rise=300.0, inseam=760.0, thigh=300.0, opening=235.0),
         camera=dict(pitch_deg=17, roll_deg=3.5, yaw_deg=2.5),
         caption="Baggy charcoal jeans, shot handheld at an angle"),
    dict(name="jeans-midwash", kind="jeans", seed=11, colour=(140, 96, 58),
         dims=dict(waist=385.0, hip=490.0, rise=280.0, inseam=790.0, thigh=275.0, opening=205.0),
         camera=dict(pitch_deg=12, roll_deg=-4.0, yaw_deg=-3.0),
         caption="Mid-wash straight jeans, camera rotated the other way"),
    dict(name="tee-burgundy", kind="tee", seed=5, colour=(52, 36, 128),
         dims=dict(chest=540.0, length=720.0, sleeve=190.0),
         camera=dict(pitch_deg=14, roll_deg=2.0, yaw_deg=4.0),
         caption="Burgundy tee, sleeves angled down like a real flat-lay"),
]


def render(spec):
    """Build albedo + height for the whole scene, light it once, then photograph it."""
    rng = np.random.default_rng(spec["seed"])
    shape = (int(px(SCENE_MM[1])), int(px(SCENE_MM[0])))
    alb, hgt = backdrop(shape, rng, base=spec.get("backdrop", (214, 216, 219)))
    placed, paper = paste_sheets(alb, hgt, rng, jitter_mm=spec.get("jitter", 2.5),
                                 missing=spec.get("missing", ()))
    cx = MAT_MM[0] / 2
    d = spec["dims"]
    if spec["kind"] == "jeans":
        top = (MAT_MM[1] - d["rise"] - d["inseam"]) / 2
        outline, details, patches, gt, (crotch_y, hem_y, gap) = jeans_shape(cx, top, **d)
        fades = [(cx - d["hip"] / 4, crotch_y + 120, 90), (cx + d["hip"] / 4, crotch_y + 120, 90),
                 (cx - d["hip"] / 4 - 15, crotch_y + d["inseam"] * 0.45, 70),
                 (cx + d["hip"] / 4 + 15, crotch_y + d["inseam"] * 0.45, 70)]
        g_alb, g_hgt, cover = garment_layers(shape, outline, details, rng, spec["colour"], "denim", fades, patches)
        spec_str, shine = 0.020, 26.0
    else:
        top = (MAT_MM[1] - d["length"]) / 2
        outline, details, patches, gt, _ = tee_shape(cx, top, **d)
        g_alb, g_hgt, cover = garment_layers(shape, outline, details, rng, spec["colour"], "jersey", None, patches)
        spec_str, shine = 0.010, 18.0

    c3 = cover[..., None]
    alb = alb * (1 - c3) + g_alb * c3
    hgt = hgt * (1 - cover) + (hgt * 0.25 + g_hgt) * cover     # cloth follows the surface under it

    card = None
    if spec.get("card"):
        cxy = spec.get("card_at", (cx + 60, top + 260))
        card = place_card(alb, hgt, rng, cxy, spec.get("card_angle"))

    lit = shade(alb, hgt, PX, spec=spec_str, shine=shine)
    if card is not None:                      # plastic catches the light more than cloth
        lit = lit * (1 - card[..., None]) + shade(alb, hgt, PX, spec=0.06, shine=60.0) * card[..., None]

    # contact shadows: the garment and the paper both sit above the sheet
    occl = ambient_occlusion(cover, px(6.0), 0.40) * cast_shadow(cover, 1.6, PX, strength=0.45)
    if card is not None:
        occl *= ambient_occlusion(card, px(2.5), 0.30) * cast_shadow(card, 0.8, PX, softness_px=3, strength=0.40)
    occl *= ambient_occlusion(paper, px(3.0), 0.22) * cast_shadow(paper, 0.6, PX, softness_px=4, strength=0.30)
    lit *= occl[..., None]

    photo, jpg = handheld_photo(np.clip(lit, 0, 255), rng, **spec["camera"])
    return photo, jpg, {k: round(v, 1) for k, v in gt.items()}, placed


def main():
    OUT.mkdir(exist_ok=True)
    meta = []
    for spec in SCENES:
        photo, jpg, gt, placed = render(spec)
        (OUT / f"{spec['name']}.jpg").write_bytes(jpg.tobytes())
        meta.append({"name": spec["name"], "kind": spec["kind"], "caption": spec["caption"],
                     "ground_truth_cm": gt, "camera": spec["camera"],
                     "sheet_misplacement": {str(k): {"dx_mm": round(v[0], 1), "dy_mm": round(v[1], 1),
                                                     "rot_deg": round(v[2], 2)} for k, v in placed.items()}})
        print(spec["name"], gt)
    (OUT / "scenes.json").write_text(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()

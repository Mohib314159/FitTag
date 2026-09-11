"""Measurement engine — the rigorous core.

Given a garment silhouette (contour) in a *metric* rectified image, extract real
measurements in centimetres. Landmarks are derived from the silhouette's row-by-row
width profile (robust) rather than single convexity-defect points (fragile): the
armpit is where the width steps down from sleeve-span to body-width; the crotch is the
first row where the silhouette splits into two legs. No model emits a number.

Conventions: contour points (x, y) with y increasing downward; `mm_per_px` scales the
rectified image; outputs are centimetres. `tol_scale` widens tolerances in single-marker
mode where accuracy is lower.
"""

from __future__ import annotations

import cv2
import numpy as np

from .contracts import Measurement


# Honest real-world tolerances (cm), before mode scaling. Secondary landmarks
# (shoulder/sleeve/thigh/leg opening) are intrinsically harder than primary ones.
_SECONDARY = {"shoulder_width", "sleeve_length", "thigh", "leg_opening"}

def _tol(name: str, scale: float = 1.0) -> float:
    base = 1.5 if name in _SECONDARY else 1.0
    return round(base * scale, 1)


def _raster(contour: np.ndarray):
    """Fill the contour into a local binary mask; return (mask, x0, y0, w, h)."""
    x0, y0, w, h = cv2.boundingRect(contour)
    mask = np.zeros((y0 + h + 2, x0 + w + 2), np.uint8)
    cv2.drawContours(mask, [contour], -1, 255, cv2.FILLED)
    return mask, x0, y0, w, h


def _profile(contour: np.ndarray):
    """Row-wise silhouette extents. Returns dict of arrays over occupied rows:
    ys, xL, xR, width (single bounding run per row)."""
    mask, x0, y0, w, h = _raster(contour)
    ys, xL, xR = [], [], []
    for y in range(y0, y0 + h + 1):
        cols = np.where(mask[y] > 0)[0]
        if cols.size:
            ys.append(y); xL.append(int(cols.min())); xR.append(int(cols.max()))
    ys = np.array(ys); xL = np.array(xL); xR = np.array(xR)
    return {"mask": mask, "ys": ys, "xL": xL, "xR": xR, "width": xR - xL}


def _runs(row: np.ndarray, gap: int = 6):
    """Contiguous foreground runs in a mask row: list of (start, end)."""
    cols = np.where(row > 0)[0]
    if cols.size == 0:
        return []
    splits = np.where(np.diff(cols) > gap)[0]
    segs = np.split(cols, splits + 1)
    return [(int(s[0]), int(s[-1])) for s in segs if s.size]


# --- tops -------------------------------------------------------------------------

def measure_tshirt(contour, mm_per_px, tol_scale=1.0) -> list[Measurement]:
    p = _profile(contour)
    ys, xL, xR, width = p["ys"], p["xL"], p["xR"], p["width"]
    if ys.size < 5:
        return []
    s = mm_per_px / 10.0
    ymin, ymax = int(ys[0]), int(ys[-1])
    Hh = ymax - ymin
    out: list[Measurement] = []

    def cm(px):
        return round(px * s, 1)

    # length: shoulder line to hem
    cx = int((np.median(xL) + np.median(xR)) / 2)
    out.append(Measurement("length", cm(Hh), _tol("length", tol_scale), (cx, ymin), (cx, ymax)))

    # body region = lower 55% of rows (definitely below the sleeves)
    body = ys >= ymin + 0.45 * Hh
    body_w = float(np.median(width[body]))

    # armpit row: first row (from top) where width has dropped to ~body width
    # search below the widest row (the sleeve span); above it, the sloping shoulders and
    # neckline are also narrower than the body and used to be mistaken for the armpit
    widest = int(ys[int(np.argmax(width))])
    below = ys[(width <= 1.15 * body_w) & (ys > widest)]
    armpit_y = int(below[0]) if below.size else int(ymin + 0.3 * Hh)

    # pit-to-pit: body width just below the armpit (chest)
    chest_y = min(ymax, int(armpit_y + 0.04 * Hh))
    j = int(np.argmin(np.abs(ys - chest_y)))
    ptp = width[j]
    out.append(Measurement("pit_to_pit", cm(ptp), _tol("pit_to_pit", tol_scale),
                           (int(xL[j]), int(ys[j])), (int(xR[j]), int(ys[j]))))

    # body edges at the chest row (just below the armpit) = widest body point,
    # unaffected by hem taper. Used for shoulder and as the sleeve attachment line.
    body_L, body_R = int(xL[j]), int(xR[j])

    # shoulder: body width at the top of the body (proxy; equals chest for boxy cuts)
    sw = body_R - body_L
    out.append(Measurement("shoulder_width", cm(sw), _tol("shoulder_width", tol_scale),
                           (body_L, int(ys[j])), (body_R, int(ys[j]))))

    # sleeve length: body edge to cuff, averaged over both sides
    max_x = int(xR.max()); min_x = int(xL.min())
    sleeve = ((max_x - body_R) + (body_L - min_x)) / 2.0
    out.append(Measurement("sleeve_length", cm(sleeve), _tol("sleeve_length", tol_scale),
                           (body_R, int(ys[j])), (max_x, int(ys[j]))))

    # hem width: bottom band
    band = (ys >= ymax - 0.05 * Hh) & (ys <= ymax - 0.02 * Hh)
    if not band.any():
        band = ys >= ymax - max(4, 0.03 * Hh)
    hem = float(np.median(width[band]))
    hy = int(np.median(ys[band]))
    out.append(Measurement("hem_width", cm(hem), _tol("hem_width", tol_scale),
                           (int(np.median(xL[band])), hy), (int(np.median(xR[band])), hy)))
    return out


# --- bottoms ----------------------------------------------------------------------

def measure_jeans(contour, mm_per_px, tol_scale=1.0) -> list[Measurement]:
    p = _profile(contour)
    mask, ys, xL, xR, width = p["mask"], p["ys"], p["xL"], p["xR"], p["width"]
    if ys.size < 5:
        return []
    s = mm_per_px / 10.0
    ymin, ymax = int(ys[0]), int(ys[-1])
    Hh = ymax - ymin
    out: list[Measurement] = []

    def cm(px):
        return round(px * s, 1)

    # waist: top band (single waistband run)
    band = ys <= ymin + max(4, 0.03 * Hh)
    waist = float(np.median(width[band]))
    wy = ymin + 2
    out.append(Measurement("waist_flat", cm(waist), _tol("waist_flat", tol_scale),
                           (int(np.median(xL[band])), wy), (int(np.median(xR[band])), wy)))

    # crotch: first row (from top) that splits into two legs
    # first row where the silhouette splits into two legs AND stays split: a single row
    # with two runs is often just a segmentation hole (fly stitching, a fold, a pocket)
    crotch_y = None
    min_leg = 0.04 * Hh
    persist = max(3, int(0.03 * Hh))
    def _split(y):
        r = _runs(mask[y])
        return len(r) >= 2 and sum((b - a) >= min_leg for a, b in r) >= 2
    for y in range(int(ymin + 0.1 * Hh), ymax + 1 - persist):
        if all(_split(y + k) for k in range(0, persist, max(1, persist // 4))):
            crotch_y = y
            break
    if crotch_y is not None:
        inseam = ymax - crotch_y
        gap = _runs(mask[min(ymax, crotch_y + 2)])
        crotch_x = (gap[0][1] + gap[1][0]) // 2 if len(gap) >= 2 else int(xL.mean() + width.mean() / 2)
        out.append(Measurement("inseam", cm(inseam), _tol("inseam", tol_scale),
                               (crotch_x, crotch_y), (crotch_x, ymax)))

        # hip: full width above the crotch (single run)
        hy = int(ymin + 0.22 * Hh)
        jj = int(np.argmin(np.abs(ys - hy)))
        out.append(Measurement("hip_flat", cm(width[jj]), _tol("hip_flat", tol_scale),
                               (int(xL[jj]), int(ys[jj])), (int(xR[jj]), int(ys[jj]))))

        # leg opening: one leg's width at the hem
        # a little above the hem edge: rounded hem corners make the last rows narrow
        ly = max(ymin, ymax - max(2, int(0.02 * Hh)))
        legs = [r for r in _runs(mask[ly]) if (r[1] - r[0]) >= min_leg] or _runs(mask[ly])
        if legs:
            a, b = legs[0]
            out.append(Measurement("leg_opening", cm(b - a), _tol("leg_opening", tol_scale),
                                   (a, ly), (b, ly)))

        # thigh: one leg's width just below the crotch
        ty = min(ymax - 1, crotch_y + int(0.06 * Hh))
        tlegs = _runs(mask[ty])
        if tlegs:
            a, b = tlegs[0]
            out.append(Measurement("thigh", cm(b - a), _tol("thigh", tol_scale),
                                   (a, ty), (b, ty)))
    return out


# --- dispatcher -------------------------------------------------------------------

_BOTTOMS = {"jeans", "trousers", "shorts", "skirt", "pants"}


def measure(contour, garment_type: str, mm_per_px: float, tol_scale: float = 1.0):
    g = garment_type.lower().strip()
    if g in _BOTTOMS:
        return measure_jeans(contour, mm_per_px, tol_scale)
    return measure_tshirt(contour, mm_per_px, tol_scale)

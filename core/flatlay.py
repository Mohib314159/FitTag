"""Measuring a garment that is lying flat, from one photograph.

The calibration module turns a tilted handheld shot into a square-on metric view. This module
does the part after that: find the garment in it, square it up, and read the landmarks off it.

Three things here are not obvious and were each forced by a real photograph failing:

  * Cutting the garment out on **colour, not brightness**. Tan cotton on grey carpet has almost
    no luminance contrast but a large b* difference, so an Otsu split on b* separates them
    cleanly where a grey-level threshold cannot.

  * **Filling holes rather than closing.** A morphological close big enough to seal the pocket
    seams also welds the two legs together at the crotch, which costs several inches of inseam.
    A flood from the border reaches the background; anything it cannot reach is a hole.

  * **Squaring to the waistband.** A garment a few degrees off vertical makes the topmost row a
    corner of the waistband rather than the band itself, and the waist reads a third of its real
    width. Fitting the band's top edge and rotating to it fixes the whole measurement set.

See core.measure for the landmark rules, and validation/ for how the numbers are graded.
"""

from __future__ import annotations

import math

import cv2
import numpy as np


# --- cutting the garment out ------------------------------------------------------

def fill_holes(mask: np.ndarray) -> np.ndarray:
    """Close interior holes without closing the gap between the legs."""
    h, w = mask.shape
    flood = mask.copy()
    cv2.floodFill(flood, np.zeros((h + 2, w + 2), np.uint8), (0, 0), 255)
    return mask | cv2.bitwise_not(flood)


def largest_contour(mask: np.ndarray):
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    return max(cnts, key=cv2.contourArea) if cnts else None


def _biggest(mask):
    n, lbl, stats, _ = cv2.connectedComponentsWithStats(mask)
    if n < 2:
        return None, None, None
    k = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    return (lbl == k).astype(np.uint8) * 255, k, stats


def _split_on(channel_img: np.ndarray, open_px: int):
    """Threshold one channel, decide which side is the garment, clean it, keep the biggest blob.

    Which side is background is settled by the image border, not by which side is smaller: a
    garment photographed close up fills most of the frame, so 'the minority is the object' is
    simply false. The background is whatever touches the edge.
    """
    ch = cv2.GaussianBlur(channel_img, (0, 0), 3)
    _, m = cv2.threshold(ch, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    border = np.concatenate([m[0], m[-1], m[:, 0], m[:, -1]])
    if border.mean() > 127:                       # the border is 'foreground', so the split is inverted
        m = cv2.bitwise_not(m)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((open_px, open_px), np.uint8))
    total = float((m > 0).sum())
    if total < 0.02 * m.size:
        return None, 0.0
    m = fill_holes(m)
    big, k, stats = _biggest(m)
    if big is None:
        return None, 0.0
    # A fixed opening kernel cannot know what counts as thin: 21 px trims lint off a phone photo
    # and nothing off a 4000 px one. Size the second pass to the object actually found, so a strip
    # of light floor along the frame edge goes but a trouser leg — far wider — stays.
    short = min(int(stats[k, cv2.CC_STAT_WIDTH]), int(stats[k, cv2.CC_STAT_HEIGHT]))
    kern = max(9, int(0.035 * short)) | 1
    big = cv2.morphologyEx(big, cv2.MORPH_OPEN,
                           cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kern, kern)))
    big2, k2, stats2 = _biggest(big)
    if big2 is None:
        return None, 0.0
    big, k, stats = fill_holes(big2), k2, stats2
    area = float(stats[k, cv2.CC_STAT_AREA]) / m.size
    if not (0.05 < area < 0.92):                  # not a garment: a wall, or a speck
        return big, 0.0
    # a good split leaves one blob, not confetti: score by how much of the mask it accounts for
    return big, float(stats[k, cv2.CC_STAT_AREA]) / total


def garment_mask(photo: np.ndarray, channel: str = "auto", open_px: int = 21) -> "np.ndarray | None":
    """Silhouette of the garment, split on whichever Lab channel separates it best.

    'auto' tries L, a* and b* and keeps the one whose threshold leaves a single clean blob rather
    than scattered fragments. That is what lets one code path handle tan-on-grey, where lightness
    barely separates the two but b* does, and navy-on-white, where the reverse holds.
    """
    lab = cv2.cvtColor(photo, cv2.COLOR_BGR2LAB)
    options = {"L": lab[:, :, 0], "a": lab[:, :, 1], "b": lab[:, :, 2]}
    if channel != "auto":
        mask, _ = _split_on(options[channel], open_px)
        return mask
    best, best_score = None, -1.0
    for name in ("b", "a", "L"):
        mask, score = _split_on(options[name], open_px)
        if mask is not None and score > best_score:
            best, best_score = mask, score
    return best


# --- squaring up ------------------------------------------------------------------

def waistband_tilt(mask: np.ndarray, rng_seed: int = 0) -> float:
    """Angle, in degrees, of the straight top edge of the garment.

    Trousers laid flat have one long straight edge — the top of the waistband. Fitting it with
    a median-of-slopes estimator ignores belt loops poking above the band and the notch at the fly.
    """
    ys, xs = np.where(mask > 0)
    if xs.size < 100:
        return 0.0
    x0, x1 = int(xs.min()), int(xs.max())
    lo, hi = int(x0 + 0.20 * (x1 - x0)), int(x0 + 0.80 * (x1 - x0))
    px, py = [], []
    for x in range(lo, hi, 3):
        col = np.where(mask[:, x] > 0)[0]
        if col.size:
            px.append(x); py.append(int(col.min()))
    px, py = np.array(px, float), np.array(py, float)
    if px.size < 20:
        return 0.0
    idx = np.random.default_rng(rng_seed).integers(0, px.size, (4000, 2))
    i, j = idx[:, 0], idx[:, 1]
    ok = px[i] != px[j]
    if not ok.any():
        return 0.0
    slope = float(np.median((py[i][ok] - py[j][ok]) / (px[i][ok] - px[j][ok])))
    inter = float(np.median(py - slope * px))
    resid = np.abs(py - (slope * px + inter))
    keep = resid < max(6.0, 2.5 * float(np.median(resid)))
    if keep.sum() > 10:
        slope, inter = np.polyfit(px[keep], py[keep], 1)
    return math.degrees(math.atan(slope))


def rotate(img: np.ndarray, deg: float, border=0):
    m = cv2.getRotationMatrix2D((img.shape[1] / 2, img.shape[0] / 2), deg, 1.0)
    flag = cv2.INTER_NEAREST if img.ndim == 2 else cv2.INTER_LINEAR
    return cv2.warpAffine(img, m, (img.shape[1], img.shape[0]), flags=flag, borderValue=border)


# --- the crotch -------------------------------------------------------------------

def silhouette_split(mask: np.ndarray, gap: int = 6):
    """First row, top down, where the outline separates into two legs. Returns (x, y) or None."""
    ys = np.where(mask.any(1))[0]
    if ys.size == 0:
        return None
    ymin, ymax = int(ys[0]), int(ys[-1])
    for y in range(ymin + int(0.10 * (ymax - ymin)), ymax):
        cols = np.where(mask[y] > 0)[0]
        if cols.size and np.diff(cols).max() > gap:
            k = int(np.argmax(np.diff(cols)))
            return ((int(cols[k]) + int(cols[k + 1])) // 2, y)
    return None


def trace_crease(rectified, mask, apex, max_rise_px, win=28):
    """From the silhouette's split, follow the overlap crease upward to the real crotch.

    Laid flat, one leg lies over the other, so background only shows some way below the crotch —
    measuring the outline alone loses several inches of inseam. The overlapping leg's edge keeps
    going as a thin dark line. Follow it, and stop where it fades.

    Returns ((x, y), path) where path is the traced points with their line contrast.
    """
    grey = cv2.GaussianBlur(cv2.cvtColor(rectified, cv2.COLOR_BGR2GRAY).astype(np.float32), (0, 0), 2)
    high = grey - cv2.GaussianBlur(grey, (0, 0), 14)      # the crease only, not the shading
    x = int(apex[0])
    path = []
    for y in range(int(apex[1]) - 1, int(apex[1]) - max_rise_px, -1):
        if y < 1 or mask[y].sum() == 0:
            break
        lo, hi = max(0, x - win), min(rectified.shape[1], x + win)
        row = high[y, lo:hi]
        j = int(np.argmin(row))
        path.append((lo + j, y, float(np.median(row) - row[j])))
        x = lo + j
    if not path:
        return None, []
    depth = np.convolve([p[2] for p in path], np.ones(15) / 15, "same")
    strong = depth > max(1.2, 0.35 * float(np.percentile(depth, 90)))
    end = len(depth)
    for i in range(len(depth)):
        if not strong[i:i + 25].any():
            end = i
            break
    return path[max(0, end - 1)], path[:end]

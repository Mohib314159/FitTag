"""Calibration: turn a photo containing known ArUco markers into a metric,
perspective-corrected top-down image where every pixel is a known number of mm.

Two modes, chosen automatically:
  - MAT  (preferred): the garment is laid on a printed sheet with markers near the
    corners. We use ALL detected marker corners as point correspondences and fit one
    homography across the whole sheet. Because the correspondences span the garment
    region, there is no extrapolation -> sub-mm-class accuracy.
  - SINGLE (fallback): only one marker is seen (e.g. a single calibration card). We
    still rectify, but accuracy degrades with distance from the marker, so we flag a
    wider tolerance. Sub-pixel corner refinement is always on.

Rigorous core. The marker(s) give point correspondences between the image plane and a
known real-world plane; that recovers the plane homography and warps to a metric view.
Assumption: the garment lies flat in the markers' plane (state it in the pitch).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import cv2
import numpy as np

_DICT = cv2.aruco.DICT_4X4_50


# --- Calibration result ----------------------------------------------------------

@dataclass
class Calibration:
    rectified: np.ndarray        # BGR, metric top-down
    mm_per_px: float
    H: np.ndarray
    ok: bool
    mode: str = "none"           # "mat" | "single" | "none"
    n_markers: int = 0
    tol_scale: float = 1.0       # multiply intrinsic measurement tolerance by this
    marker_size_mm: float = 50.0
    prior: "np.ndarray | None" = None   # rough garment mask (same size as rectified), if known
    exclude: "np.ndarray | None" = None # region the scale reference occupies, not garment


# --- Default calibration mat -----------------------------------------------------
# Markers 0..3 near the four corners of a printed sheet. Garment lies in the middle.
# (id -> top-left of the marker, in mat millimetres). Tune to your printed asset.

MAT_MM = (1000.0, 1400.0)        # sheet size (w, h) — fits trousers/coats
MAT_MARKER_MM = 80.0
MAT_INSET_MM = 30.0
_W, _H, _S, _I = MAT_MM[0], MAT_MM[1], MAT_MARKER_MM, MAT_INSET_MM
DEFAULT_MAT_LAYOUT = {
    0: (_I,            _I),            # top-left
    1: (_W - _I - _S,  _I),            # top-right
    2: (_W - _I - _S,  _H - _I - _S),  # bottom-right
    3: (_I,            _H - _I - _S),  # bottom-left
}


def _marker_corner_metric(top_left, size_mm):
    """Four corners (TL,TR,BR,BL) of a marker in metric mm, matching ArUco's order."""
    x, y = top_left
    return np.array([[x, y], [x + size_mm, y],
                     [x + size_mm, y + size_mm], [x, y + size_mm]], np.float32)


# --- ArUco detection (sub-pixel, API-version tolerant) ---------------------------

def _detector():
    if hasattr(cv2.aruco, "ArucoDetector"):
        dictionary = cv2.aruco.getPredefinedDictionary(_DICT)
        params = cv2.aruco.DetectorParameters()
        params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
        return cv2.aruco.ArucoDetector(dictionary, params), True
    dictionary = cv2.aruco.Dictionary_get(_DICT)
    params = cv2.aruco.DetectorParameters_create()
    params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    return (dictionary, params), False


def _detect_markers(gray: np.ndarray):
    det, new = _detector()
    if new:
        corners, ids, _ = det.detectMarkers(gray)
    else:
        dictionary, params = det
        corners, ids, _ = cv2.aruco.detectMarkers(gray, dictionary, parameters=params)
    return corners, ids


def make_marker(marker_id: int = 0, side_px: int = 600) -> np.ndarray:
    if hasattr(cv2.aruco, "generateImageMarker"):
        dictionary = cv2.aruco.getPredefinedDictionary(_DICT)
        return cv2.aruco.generateImageMarker(dictionary, marker_id, side_px)
    dictionary = cv2.aruco.Dictionary_get(_DICT)
    return cv2.aruco.drawMarker(dictionary, marker_id, side_px)


# --- Calibration -----------------------------------------------------------------

def calibrate(
    photo: np.ndarray,
    marker_size_mm: float = 50.0,
    mm_per_px_out: float = 0.5,
    mat_layout: dict | None = DEFAULT_MAT_LAYOUT,
    mat_marker_mm: float = MAT_MARKER_MM,
    mat_mm: tuple[float, float] = MAT_MM,
    single_margin_mm: float = 60.0,
    single_canvas_mm: tuple[float, float] = (850.0, 1000.0),
) -> Calibration:
    """Detect marker(s) and rectify the plane to metric.

    If two or more layout markers are present -> MAT mode (accurate).
    Else if one marker is present -> SINGLE mode (fallback, wider tolerance).
    """
    gray = cv2.cvtColor(photo, cv2.COLOR_BGR2GRAY) if photo.ndim == 3 else photo
    corners, ids = _detect_markers(gray)

    if ids is None or len(ids) == 0:
        return Calibration(photo, mm_per_px_out, np.eye(3), ok=False)

    id_list = [int(i) for i in ids.flatten()]
    found = {mid: corners[k].reshape(4, 2).astype(np.float32) for k, mid in enumerate(id_list)}

    # --- MAT mode: >=2 known markers -> homography over all corners ----------
    if mat_layout is not None:
        known = [mid for mid in found if mid in mat_layout]
        # One mat sheet is still usable: its marker's position on the mat is known, so its
        # four corners alone give the homography. Less accurate (the fit extrapolates from an
        # 8 cm square across the whole mat), so error bars are widened.
        if len(known) >= 1:
            src_pts, dst_pts = [], []
            for mid in known:
                src_pts.append(found[mid])
                dst_pts.append(_marker_corner_metric(mat_layout[mid], mat_marker_mm) / mm_per_px_out)
            src = np.vstack(src_pts).astype(np.float32)
            dst = np.vstack(dst_pts).astype(np.float32)
            H, _ = cv2.findHomography(src, dst, method=0)  # exact LS over all points
            out_w = int(round(mat_mm[0] / mm_per_px_out))
            out_h = int(round(mat_mm[1] / mm_per_px_out))
            rectified = cv2.warpPerspective(photo, H, (out_w, out_h),
                                            flags=cv2.INTER_LINEAR,
                                            borderMode=cv2.BORDER_CONSTANT,
                                            borderValue=(255, 255, 255))
            return Calibration(rectified, mm_per_px_out, H, ok=True,
                               mode="mat" if len(known) >= 2 else "single-sheet",
                               n_markers=len(known), tol_scale=1.0 if len(known) >= 2 else 4.0,
                               marker_size_mm=mat_marker_mm)

    # --- SINGLE mode: one marker, rectify with a wider tolerance --------------
    src = next(iter(found.values()))
    m = marker_size_mm
    dst_mm = np.array([[single_margin_mm, single_margin_mm],
                       [single_margin_mm + m, single_margin_mm],
                       [single_margin_mm + m, single_margin_mm + m],
                       [single_margin_mm, single_margin_mm + m]], np.float32)
    dst_px = dst_mm / mm_per_px_out
    H = cv2.getPerspectiveTransform(src, dst_px)
    out_w = int(round(single_canvas_mm[0] / mm_per_px_out))
    out_h = int(round(single_canvas_mm[1] / mm_per_px_out))
    rectified = cv2.warpPerspective(photo, H, (out_w, out_h),
                                    flags=cv2.INTER_LINEAR,
                                    borderMode=cv2.BORDER_CONSTANT,
                                    borderValue=(255, 255, 255))
    return Calibration(rectified, mm_per_px_out, H, ok=True, mode="single",
                       n_markers=1, tol_scale=4.0, marker_size_mm=m)


def capture_guidance(photo: np.ndarray) -> dict:
    """Pre-shoot quality check: marker visibility, glare, exposure, framing.
    Returns guidance the seller can act on BEFORE measuring (less garbage-in)."""
    gray = cv2.cvtColor(photo, cv2.COLOR_BGR2GRAY) if photo.ndim == 3 else photo
    corners, ids = _detect_markers(gray)
    n = 0 if ids is None else len(ids)
    glare = float((gray > 250).mean())
    mean_lum = float(gray.mean())
    issues = []
    if n == 0:
        issues.append("No FitTag markers found — lay the garment on the mat (or use a single card).")
    elif n < 2:
        issues.append("Only one marker visible — get all four mat corners in frame for full accuracy.")
    if glare > 0.45:
        issues.append("Strong glare — diffuse the light or turn off the flash.")
    if mean_lum < 55:
        issues.append("Looks dark — add even, brighter lighting.")
    elif mean_lum > 246:
        issues.append("Looks overexposed — reduce the light a little.")
    return {"markers": n, "ready": n >= 1 and glare <= 0.45 and 55 <= mean_lum <= 246,
            "issues": issues}


def _order_quad(pts):
    pts = pts.reshape(4, 2).astype(np.float32)
    s, d = pts.sum(1), np.diff(pts, axis=1).ravel()
    return np.array([pts[np.argmin(s)], pts[np.argmin(d)],
                     pts[np.argmax(s)], pts[np.argmax(d)]], np.float32)  # TL,TR,BR,BL


def calibrate_by_rectangle(photo, ref_mm=(297.0, 210.0), aspect_tol=0.12,
                           mm_per_px_out=0.5, canvas_mm=(1300.0, 1600.0), margin_mm=90.0):
    """EXPERIMENTAL markerless calibration: use any rectangle of known size (A4 paper =
    297x210, a card = 85.6x54) as the scale reference. Lower friction than the mat, but
    wider tolerance — the garment is partly extrapolated from a small reference. Lay the
    garment beside the sheet, both flat in frame.
    """
    gray = cv2.cvtColor(photo, cv2.COLOR_BGR2GRAY) if photo.ndim == 3 else photo
    edges = cv2.dilate(cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 50, 150),
                       np.ones((3, 3), np.uint8))
    cnts, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    ref_aspect = max(ref_mm) / min(ref_mm)
    H, W = gray.shape
    best, best_area = None, 0.0
    for c in cnts:
        area = cv2.contourArea(c)
        if area < 0.02 * H * W:
            continue
        approx = cv2.approxPolyDP(c, 0.02 * cv2.arcLength(c, True), True)
        if len(approx) != 4 or not cv2.isContourConvex(approx):
            continue
        q = _order_quad(approx)
        wlen = (np.linalg.norm(q[1] - q[0]) + np.linalg.norm(q[2] - q[3])) / 2
        hlen = (np.linalg.norm(q[3] - q[0]) + np.linalg.norm(q[2] - q[1])) / 2
        asp = max(wlen, hlen) / max(1.0, min(wlen, hlen))
        if abs(asp - ref_aspect) / ref_aspect > aspect_tol:
            continue
        if area > best_area:
            best, best_area = (q, wlen, hlen), area
    if best is None:
        return Calibration(photo, mm_per_px_out, np.eye(3), ok=False)

    q, wlen, hlen = best
    long_mm, short_mm = max(ref_mm), min(ref_mm)
    rw, rh = (long_mm, short_mm) if wlen >= hlen else (short_mm, long_mm)
    dst = np.array([[margin_mm, margin_mm], [margin_mm + rw, margin_mm],
                    [margin_mm + rw, margin_mm + rh], [margin_mm, margin_mm + rh]], np.float32)
    Hm = cv2.getPerspectiveTransform(q, dst / mm_per_px_out)
    out_w, out_h = int(canvas_mm[0] / mm_per_px_out), int(canvas_mm[1] / mm_per_px_out)
    rect = cv2.warpPerspective(photo, Hm, (out_w, out_h), borderValue=(255, 255, 255))
    return Calibration(rect, mm_per_px_out, Hm, ok=True, mode="rectangle",
                       n_markers=0, tol_scale=3.0, marker_size_mm=0.0)


# --- card mode: markerless, using a bank card as the ruler ------------------------

CARD_MM = (85.60, 53.98)          # ISO/IEC 7810 ID-1, the size of every bank card


def _quad_score(q, ref_aspect):
    """How card-like a quadrilateral is: side ratio, parallel opposite sides, squareness."""
    d = [np.linalg.norm(q[(i + 1) % 4] - q[i]) for i in range(4)]
    if min(d) < 1e-3:
        return 0.0
    w, h = (d[0] + d[2]) / 2, (d[1] + d[3]) / 2
    asp = max(w, h) / min(w, h)
    a_err = abs(asp - ref_aspect) / ref_aspect
    opp = abs(d[0] - d[2]) / max(d[0], d[2]) + abs(d[1] - d[3]) / max(d[1], d[3])
    ang = []
    for i in range(4):
        v1 = q[(i + 1) % 4] - q[i]
        v2 = q[(i - 1) % 4] - q[i]
        c = abs(float(v1 @ v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-6))
        ang.append(c)
    return max(0.0, 1 - 2.2 * a_err) * max(0.0, 1 - 1.5 * opp) * max(0.0, 1 - 1.6 * float(np.mean(ang)))


def find_card(photo, card_mm=CARD_MM, min_frac=0.0003, max_frac=0.06):
    """Locate a card-shaped rectangle in the photo. Returns its four corners (TL,TR,BR,BL)
    in pixels, or None.

    Rounded corners make polygon approximation unreliable, so this works from the rotated
    bounding box of each blob instead: find edges, close them into shapes, and keep the one
    whose box has a card's proportions, is nearly filled, is flat in colour inside, and
    stands out from what surrounds it."""
    img = photo if photo.ndim == 3 else cv2.cvtColor(photo, cv2.COLOR_GRAY2BGR)
    H, W = img.shape[:2]
    scale = min(1.0, 2000.0 / max(H, W))
    small = cv2.resize(img, (int(W * scale), int(H * scale)), interpolation=cv2.INTER_AREA)
    h, w = small.shape[:2]
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    g = cv2.bilateralFilter(gray, 7, 40, 40)

    gx = cv2.Scharr(g, cv2.CV_32F, 1, 0)
    gy = cv2.Scharr(g, cv2.CV_32F, 0, 1)
    mag = cv2.magnitude(gx, gy)
    ref_aspect = max(card_mm) / min(card_mm)
    best, best_score = None, 0.30

    def edge_profile(box):
        """Look across each side of the box. A card gives a step: brightness jumps within a
        pixel or two and stays there. A fold or a shadow gives a ramp, which is what this
        rejects. Returns (mean jump in grey levels, how step-like it is, polarity agreement)."""
        jumps, steps, signs = [], [], []
        cen = box.mean(0)
        for i in range(4):
            p0, p1 = box[i], box[(i + 1) % 4]
            mid = (p0 + p1) / 2
            n = mid - cen
            n /= np.linalg.norm(n) + 1e-6                      # outward normal
            n_samples = max(5, int(np.linalg.norm(p1 - p0) / 6))
            near_in, near_out, far_in, far_out = [], [], [], []
            for t in np.linspace(0.15, 0.85, n_samples):
                q0 = p0 + (p1 - p0) * t
                for d, acc in ((-2.0, near_in), (2.0, near_out), (-7.0, far_in), (7.0, far_out)):
                    x, y = q0 + n * d
                    xi, yi = int(round(x)), int(round(y))
                    if 0 <= xi < w and 0 <= yi < h:
                        acc.append(float(gray[yi, xi]))
            if min(len(near_in), len(near_out), len(far_in), len(far_out)) < 4:
                return 0.0, 0.0, 0.0
            d_near = np.mean(near_in) - np.mean(near_out)
            d_far = np.mean(far_in) - np.mean(far_out)
            jumps.append(abs(d_near))
            steps.append(abs(d_near) / (abs(d_far) + 1e-6))
            signs.append(np.sign(d_near))
        agree = abs(float(np.mean(signs)))
        return float(np.mean(jumps)), float(np.mean(steps)), agree

    # MSER finds regions that stay the same shape as the threshold moves — exactly what a
    # flat card on cloth looks like. Run it on the image and its inverse so a dark card on a
    # light garment is found too.
    mser = cv2.MSER_create()
    mser.setMinArea(int(0.0002 * h * w))
    mser.setMaxArea(int(0.06 * h * w))
    mser.setDelta(6)
    regions = []
    for img_v in (g, 255 - g):
        try:
            regs, _ = mser.detectRegions(img_v)
        except cv2.error:
            continue
        regions += list(regs)

    for r in regions:
        pts = r.reshape(-1, 1, 2).astype(np.float32)
        (rc, (rw, rh), ang) = cv2.minAreaRect(pts)
        if min(rw, rh) < 12:
            continue
        # a card photographed with a whole garment in frame takes up a predictable slice of
        # the picture: a few percent of the long side. Bigger is the garment itself, smaller
        # is a label or a pocket rivet.
        long_frac = max(rw, rh) / max(h, w)
        if not (0.02 <= long_frac <= 0.22):
            continue
        if len(r) / (rw * rh + 1e-6) < 0.80:        # a card fills its own bounding box
            continue
        asp = max(rw, rh) / min(rw, rh)
        a_err = abs(asp - ref_aspect) / ref_aspect
        if a_err > 0.22:
            continue
        box = cv2.boxPoints(((rc), (rw, rh), ang)).astype(np.float32)
        jump, stepness, agree = edge_profile(box)
        if jump < 10.0 or stepness < 0.55 or agree < 0.99:
            continue
        inside = np.zeros((h, w), np.uint8)
        cv2.fillPoly(inside, [np.int32(box)], 255)
        ins = gray[cv2.erode(inside, np.ones((7, 7), np.uint8)) > 0]
        if ins.size < 60:
            continue
        flat = float(np.clip(1.0 - ins.std() / 30.0, 0, 1))
        score = (1 - a_err / 0.22) * min(1.0, jump / 35.0) * min(1.0, stepness) * (0.4 + 0.6 * flat)
        if score > best_score:
            best, best_score = box, score
    if best is None:
        return None
    return _order_quad(best / scale)


def _warp_mm(photo, H0, x0, y0, x1, y1, mm_per_px):
    """Warp the photo into the metric box [x0,x1]x[y0,y1] (mm) at the given pixel pitch."""
    T = np.array([[1, 0, -x0], [0, 1, -y0], [0, 0, 1]], np.float32)
    S = np.diag([1 / mm_per_px, 1 / mm_per_px, 1.0]).astype(np.float32)
    Hm = S @ T @ H0
    out_w = int(np.clip((x1 - x0) / mm_per_px, 8, 6000))
    out_h = int(np.clip((y1 - y0) / mm_per_px, 8, 6000))
    rect = cv2.warpPerspective(photo, Hm, (out_w, out_h), flags=cv2.INTER_LINEAR,
                               borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255))
    return rect, Hm


def _content_mask(coarse, valid, strict=1.0, erode_mm=0.0, mm_per_px=2.0):
    """Rough mask of whatever is lying on the background.

    Flat-field first (divide by a heavily blurred copy) so a vignette or a fold's shading
    doesn't read as an object, then split lightness with Otsu — a garment on a sheet is a
    two-level picture, and Otsu handles that far more reliably than a distance threshold.
    Whichever side is farther from the border's lightness is the object."""
    h, w = coarse.shape[:2]
    vb = cv2.boundingRect((valid > 0.5).astype(np.uint8))
    if vb[2] < 20 or vb[3] < 20:
        return None
    vx, vy, vw, vh = vb
    img = coarse.astype(np.float32) + 1.0
    low = cv2.GaussianBlur(img, (0, 0), max(8.0, 0.06 * min(vw, vh)))
    flat = np.clip(img / low * float(np.median(low)), 0, 255).astype(np.uint8)
    lab = cv2.cvtColor(cv2.GaussianBlur(flat, (0, 0), 2), cv2.COLOR_BGR2LAB)
    L = lab[:, :, 0]
    inside = valid > 0.5

    b = max(3, int(0.05 * min(vw, vh)))
    ring = np.zeros((h, w), bool)
    ring[vy:vy + b, vx:vx + vw] = ring[vy + vh - b:vy + vh, vx:vx + vw] = True
    ring[vy:vy + vh, vx:vx + b] = ring[vy:vy + vh, vx + vw - b:vx + vw] = True
    ring &= inside
    if ring.sum() < 50:
        return None
    # Lightness alone follows the room's shadows. Cloth also has texture — weave, stitching,
    # fabric grain — and a bedsheet or a floor does not, so high-frequency energy separates
    # the garment from a shadow that happens to be the same brightness.
    hp = cv2.absdiff(L, cv2.GaussianBlur(L, (0, 0), 2.0)).astype(np.float32)
    tex = cv2.boxFilter(hp, -1, (9, 9))
    tex8 = np.clip(tex / max(1e-6, np.percentile(tex[inside], 99)) * 255, 0, 255).astype(np.uint8)
    t_thr, _ = cv2.threshold(tex8[inside], 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    textured = (tex8 > t_thr) & inside

    thr, _ = cv2.threshold(L[inside], 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    bg_L = float(np.median(L[ring]))
    dark = (L < thr) & inside
    light = (L >= thr) & inside
    lit_side = dark if abs(float(np.median(L[dark])) - bg_L) > abs(float(np.median(L[light])) - bg_L) else light
    obj = textured & lit_side
    if obj.sum() < 0.002 * inside.sum():          # texture too weak to help (blurry photo)
        obj = lit_side
    m = (obj.astype(np.uint8)) * 255
    k = max(3, int(round(20.0 / mm_per_px)) | 1)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None
    areas = [cv2.contourArea(c) for c in cnts]
    keep = [c for c, a_ in zip(cnts, areas) if a_ > 0.12 * max(areas)]
    out = np.zeros((h, w), np.uint8)
    cv2.drawContours(out, keep, -1, 255, cv2.FILLED)
    if erode_mm > 0:
        k2 = max(3, int(round(erode_mm / mm_per_px)) | 1)
        out = cv2.erode(out, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k2, k2)))
    return out


def _content_frame_mm(coarse, valid, mm_per_px, x0, y0, frame_mm=(1300.0, 1600.0)):
    """Where the garment is and which way it lies, from image moments rather than a
    threshold. Flat-fielding removes the vignette; the colour distance from the background
    is then used as a weight, so shading contributes a little and denim contributes a lot.
    Returns ((cx, cy) in mm, tilt in degrees) for a fixed-size metric frame."""
    h, w = coarse.shape[:2]
    vb = cv2.boundingRect((valid > 0.5).astype(np.uint8))
    if vb[2] < 20 or vb[3] < 20:
        return None, 0.0
    vx, vy, vw, vh = vb
    img = coarse.astype(np.float32) + 1.0
    low = cv2.GaussianBlur(img, (0, 0), max(8.0, 0.06 * min(vw, vh)))
    flat = np.clip(img / low * float(np.median(low)), 0, 255).astype(np.uint8)
    lab = cv2.cvtColor(cv2.GaussianBlur(flat, (0, 0), 2), cv2.COLOR_BGR2LAB).astype(np.float32)

    b = max(3, int(0.05 * min(vw, vh)))
    ring = np.zeros((h, w), bool)
    ring[vy:vy + b, vx:vx + vw] = ring[vy + vh - b:vy + vh, vx:vx + vw] = True
    ring[vy:vy + vh, vx:vx + b] = ring[vy:vy + vh, vx + vw - b:vx + vw] = True
    ring &= valid > 0.5
    if ring.sum() < 50:
        return None, 0.0
    bg = np.median(lab[ring], axis=0)
    dist = np.linalg.norm(lab - bg, axis=2) * (valid > 0.5)
    ring_d = dist[ring]
    mad = float(np.median(np.abs(ring_d - np.median(ring_d)))) * 1.4826
    thr = max(10.0, float(np.median(ring_d)) + 5.0 * mad)
    wgt = np.clip(dist - thr, 0, None) ** 2                     # far-from-background wins
    if wgt.sum() < 1e-6:
        return None, 0.0
    m = cv2.moments(wgt)
    cx, cy = m["m10"] / m["m00"], m["m01"] / m["m00"]
    mu20, mu02, mu11 = m["mu20"] / m["m00"], m["mu02"] / m["m00"], m["mu11"] / m["m00"]
    axis = math.degrees(0.5 * math.atan2(2 * mu11, mu20 - mu02))   # major axis, -90..90
    tilt = 90.0 - axis                                             # turn it upright
    # the major axis is only defined up to 180 degrees: keep whichever choice leaves the
    # garment taller than it is wide, which is true of everything we measure laid flat
    def spread(t):
        """Height/width of the weighted blob after turning it by t degrees."""
        M = cv2.getRotationMatrix2D((cx, cy), t, 1.0)
        r = cv2.warpAffine(wgt, M, (wgt.shape[1], wgt.shape[0]))
        pos = r[r > 0]
        if pos.size < 50:
            return 0.0
        ys, xs = np.nonzero(r > float(np.percentile(pos, 60)))
        if ys.size < 10:
            return 0.0
        return (ys.max() - ys.min() + 1) / float(xs.max() - xs.min() + 1)
    if spread(tilt) < spread(tilt + 90.0):
        tilt += 90.0
    tilt = ((tilt + 90) % 180) - 90
    return (x0 + cx * mm_per_px, y0 + cy * mm_per_px), float(tilt)


def calibrate_by_card(photo, card_mm=CARD_MM, mm_per_px_out=0.5, corners=None,
                      frame_mm=(1300.0, 1600.0), garment_box_px=None):
    """Rectify using a bank card as the only scale reference — no printed sheets.

    Pass `corners` (four points in pixels, clockwise from the card's top-left) to skip
    detection, which is what the app does when the user marks the card by hand.

    The card is 8.5 cm across and a pair of jeans is a metre long, so every measurement is
    extrapolated well beyond the reference: error bars are widened accordingly (see
    validation/sweep.py for what that costs in practice).
    """
    q = np.asarray(corners, np.float32) if corners is not None else find_card(photo, card_mm)
    if q is None:
        return Calibration(photo, mm_per_px_out, np.eye(3), ok=False, mode="none")
    q = _order_quad(np.asarray(q, np.float32))
    d = [np.linalg.norm(q[(i + 1) % 4] - q[i]) for i in range(4)]
    wide = (d[0] + d[2]) / 2 >= (d[1] + d[3]) / 2
    cw, ch = (max(card_mm), min(card_mm)) if wide else (min(card_mm), max(card_mm))
    dst_mm = np.array([[0, 0], [cw, 0], [cw, ch], [0, ch]], np.float32)
    H0 = cv2.getPerspectiveTransform(q, dst_mm)

    # Two passes: a coarse metric view locates the garment and which way it lies, then one
    # tight upright warp at full resolution. Without this the canvas covers everything the
    # camera could see, which is mostly floor.
    coarse_mm, span = 2.0, 1500.0
    ones = np.full(photo.shape[:2], 255, np.uint8)
    coarse, Hc = _warp_mm(photo, H0, -span, -span, span, span, coarse_mm)
    valid = cv2.warpPerspective(ones, Hc, (coarse.shape[1], coarse.shape[0]),
                                flags=cv2.INTER_NEAREST) / 255.0
    if garment_box_px is not None:
        # The user drew a box round the garment (two gestures in an app). That removes the
        # only part of markerless mode that isn't solved — knowing which dark shape is the
        # garment and which way up it lies — so use it when it's offered.
        pts = cv2.perspectiveTransform(np.asarray(garment_box_px, np.float32).reshape(1, -1, 2), Hc)[0]
        rect = cv2.minAreaRect(pts.astype(np.float32))
        (rc, (rw, rh), ang) = rect
        tilt = ang if rw <= rh else ang + 90.0
        tilt = ((tilt + 90) % 180) - 90
        centre = (-span + rc[0] * coarse_mm, -span + rc[1] * coarse_mm)
        span_w = max(rw, rh) * coarse_mm
        frame_mm = (max(frame_mm[0], min(rw, rh) * coarse_mm + 260.0), span_w + 260.0)
        mask = None
    else:
        mask = _content_mask(coarse, valid)
    if garment_box_px is not None:
        pass
    elif mask is None or mask.max() == 0:
        centre_px, tilt = (coarse.shape[1] / 2, coarse.shape[0] / 2), 0.0
        centre = (-span + centre_px[0] * coarse_mm, -span + centre_px[1] * coarse_mm)
    else:
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        pts = np.vstack(cnts)
        (rc, (rw, rh), ang) = cv2.minAreaRect(pts)
        # turn the plane so the garment stands upright: the long side of its bounding box
        # goes vertical. minAreaRect is far steadier than image moments on a shape with legs.
        tilt = ang if rw <= rh else ang + 90.0
        tilt = ((tilt + 90) % 180) - 90
        centre_px = rc
        centre = (-span + centre_px[0] * coarse_mm, -span + centre_px[1] * coarse_mm)

    fw, fh = frame_mm
    x0, y0 = centre[0] - fw / 2, centre[1] - fh / 2
    rect, Hm = _warp_mm(photo, H0, x0, y0, x0 + fw, y0 + fh, mm_per_px_out)

    # a rough garment mask from the coarse pass, to seed segmentation later: without it the
    # segmenter has to guess which of the sheet, the shadow and the garment is the object
    cc, Hc3 = _warp_mm(photo, H0, x0, y0, x0 + fw, y0 + fh, coarse_mm)
    v3 = cv2.warpPerspective(ones, Hc3, (cc.shape[1], cc.shape[0]), flags=cv2.INTER_NEAREST) / 255.0
    # a tighter mask for seeding: the soft shadow around a garment also differs from the
    # background, so ask for a bigger difference and pull the edge in
    prior = _content_mask(cc, v3, strict=2.4, erode_mm=18.0, mm_per_px=coarse_mm)
    if prior is not None:
        prior = cv2.resize(prior, (rect.shape[1], rect.shape[0]), interpolation=cv2.INTER_NEAREST)
    # Straighten in the rectified image rather than in the homography: find the garment's
    # bounding box here and turn the whole picture so it stands upright. Doing it at this
    # stage keeps the sign conventions honest — you can see the result.
    ref_pts = (np.asarray(garment_box_px, np.float32).reshape(1, -1, 2) if garment_box_px is not None
               else None)
    if ref_pts is not None:
        gb = cv2.perspectiveTransform(ref_pts, Hm)[0]
        (grc, (grw, grh), gang) = cv2.minAreaRect(gb.astype(np.float32))
        turn = gang if grw <= grh else gang + 90.0
        turn = ((turn + 90) % 180) - 90
        if abs(turn) > 0.4:
            M = cv2.getRotationMatrix2D((rect.shape[1] / 2, rect.shape[0] / 2), turn, 1.0)
            rect = cv2.warpAffine(rect, M, (rect.shape[1], rect.shape[0]),
                                  flags=cv2.INTER_LINEAR, borderValue=(255, 255, 255))
            M3 = np.vstack([M, [0, 0, 1]]).astype(np.float32)
            Hm = M3 @ Hm
            if prior is not None:
                prior = cv2.warpAffine(prior, M, (prior.shape[1], prior.shape[0]), flags=cv2.INTER_NEAREST)

    # the reference object is in the picture and is not the garment: mark where it landed
    ref_quad = cv2.perspectiveTransform(q.reshape(1, 4, 2).astype(np.float32), Hm)[0]
    exclude = np.zeros(rect.shape[:2], np.uint8)
    cv2.fillPoly(exclude, [np.int32(ref_quad)], 255)
    exclude = cv2.dilate(exclude, np.ones((15, 15), np.uint8))
    if prior is not None:
        prior[exclude > 0] = 0
    return Calibration(rect, mm_per_px_out, Hm, ok=True, mode="card", n_markers=0,
                       tol_scale=3.0, marker_size_mm=float(max(card_mm)), prior=prior,
                       exclude=exclude)


A4_MM = (210.0, 297.0)


def calibrate_by_paper(photo, paper_mm=A4_MM, mm_per_px_out=0.5, corners=None,
                       garment_box_px=None):
    """Rectify using a plain sheet of A4 — the no-printing scale reference.

    A4 is 210 x 297 mm everywhere outside North America (US Letter is 216 x 279 and is a
    different aspect, so pass paper_mm for it). It is big, flat, high-contrast and already in
    the house, which makes it both an accurate ruler and easy to find in a photo.

    Pass `corners` from markerless.find_rectangle, and `garment_box_px` for the four corners
    of a box round the garment — in an app that box is the user's drag, and it is what makes
    this reliable: scale from the paper, framing from the person.
    """
    from core.markerless import find_rectangle
    q = corners if corners is not None else find_rectangle(photo, paper_mm)
    if q is None:
        return Calibration(photo, mm_per_px_out, np.eye(3), ok=False, mode="none")
    cal = calibrate_by_card(photo, card_mm=paper_mm, mm_per_px_out=mm_per_px_out, corners=q,
                            garment_box_px=garment_box_px)
    cal.mode = "paper" if cal.ok else cal.mode
    cal.tol_scale = 2.0 if garment_box_px is not None else 3.0
    return cal

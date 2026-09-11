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
        if len(known) >= 2:
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
            return Calibration(rectified, mm_per_px_out, H, ok=True, mode="mat",
                               n_markers=len(known), tol_scale=1.0,
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

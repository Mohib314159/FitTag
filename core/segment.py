"""Segmentation: from a rectified image, produce a clean garment silhouette
(binary mask + largest contour). The measurement geometry runs on the contour.

Two paths:
  - segment_grabcut : for real flat-lay photos on a plain background.
  - segment_by_color: for controlled inputs where the garment is a distinct colour
                      (used by the synthetic validation harness).

The marker region is blanked first so it can never be mistaken for the garment.
"""

from __future__ import annotations

import cv2
import numpy as np


def _blank_corners(mask: np.ndarray, marker_size_mm: float, mm_per_px: float,
                   pad_mm: float = 55.0) -> np.ndarray:
    """Zero out the four corners where calibration markers sit (mat corners, or the
    single-marker near a corner). Never touches the centre, so an interior region of the
    garment is preserved — important for crotch/leg detection on bottoms."""
    c = int((marker_size_mm + pad_mm) / mm_per_px)
    H, W = mask.shape[:2]
    mask[0:c, 0:c] = 0
    mask[0:c, W - c:W] = 0
    mask[H - c:H, 0:c] = 0
    mask[H - c:H, W - c:W] = 0
    return mask


def largest_contour(mask: np.ndarray) -> np.ndarray | None:
    """Return the largest external contour of a binary mask, or None."""
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cnts:
        return None
    return max(cnts, key=cv2.contourArea)


def segment_by_color(
    rectified: np.ndarray,
    lower: tuple[int, int, int] = (0, 0, 120),     # BGR lower bound (default: red-ish garment)
    upper: tuple[int, int, int] = (110, 110, 255),
    marker_size_mm: float = 50.0,
    mm_per_px: float = 0.5,
) -> np.ndarray:
    """Threshold a distinctly coloured garment. Returns a clean binary mask."""
    mask = cv2.inRange(rectified, np.array(lower), np.array(upper))
    mask = _blank_corners(mask, marker_size_mm, mm_per_px)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    return mask


def segment_grabcut(
    rectified: np.ndarray,
    marker_size_mm: float = 50.0,
    mm_per_px: float = 0.5,
    iters: int = 5,
) -> np.ndarray:
    """Foreground garment on a plain background, via GrabCut seeded by a central rect.

    For real photos. The init rectangle is a generous inset of the canvas; refine the
    inset per your photo framing if needed.
    """
    h, w = rectified.shape[:2]
    gc_mask = np.zeros((h, w), np.uint8)
    bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    rect = (int(0.08 * w), int(0.08 * h), int(0.84 * w), int(0.84 * h))
    cv2.grabCut(rectified, gc_mask, rect, bgd, fgd, iters, cv2.GC_INIT_WITH_RECT)
    mask = np.where((gc_mask == cv2.GC_FGD) | (gc_mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
    mask = _blank_corners(mask, marker_size_mm, mm_per_px)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    return mask


def touches_border(contour: np.ndarray, shape: tuple[int, int], pad: int = 2) -> bool:
    """True if the silhouette reaches the image edge (garment likely exceeds the mat)."""
    x, y, w, h = cv2.boundingRect(contour)
    H, W = shape[:2]
    return x <= pad or y <= pad or (x + w) >= (W - pad) or (y + h) >= (H - pad)


def _auto_fg_rect(rectified, marker_size_mm, mm_per_px):
    """Bounding box of the largest non-background blob (garment), corners excluded.
    Used to seed GrabCut so it works on off-centre / smaller garments, not just centred.

    The background colour is measured from a strip along the image edge (the backdrop
    the garment is lying on) instead of assuming white paper. On a grey bedsheet the old
    "anything darker than 235 is garment" rule marked the whole image as foreground,
    which left GrabCut with no background samples and crashed it."""
    img = rectified if rectified.ndim == 3 else cv2.cvtColor(rectified, cv2.COLOR_GRAY2BGR)
    H, W = img.shape[:2]
    lab = cv2.cvtColor(cv2.GaussianBlur(img, (0, 0), 3), cv2.COLOR_BGR2LAB).astype(np.float32)
    b = max(8, int(0.04 * min(H, W)))
    edge = np.zeros((H, W), bool)
    edge[:b, :] = edge[-b:, :] = True
    edge[:, :b] = edge[:, -b:] = True
    corner = np.zeros((H, W), np.uint8) + 255
    corner = _blank_corners(corner, marker_size_mm, mm_per_px) > 0   # False where markers/papers sit
    samples = lab[edge & corner]
    bg = np.median(samples, axis=0)
    spread = np.percentile(np.linalg.norm(samples - bg, axis=1), 95)
    dist = np.linalg.norm(lab - bg, axis=2)
    fg = (dist > max(18.0, 2.0 * spread)).astype(np.uint8) * 255
    fg = _blank_corners(fg, marker_size_mm, mm_per_px)
    fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
    c = largest_contour(fg)
    if c is None:
        return None
    x, y, w, h = cv2.boundingRect(c)
    pad = int(0.03 * max(H, W))
    x0, y0 = max(1, x - pad), max(1, y - pad)
    x1, y1 = min(W - 1, x + w + pad), min(H - 1, y + h + pad)
    if (x1 - x0) * (y1 - y0) > 0.95 * H * W:      # no usable background left for GrabCut
        return None
    return (x0, y0, x1 - x0, y1 - y0)


def segment_smart_grabcut(rectified, marker_size_mm=80.0, mm_per_px=0.5, iters=5):
    """GrabCut seeded by the auto-detected garment bbox (robust to framing)."""
    H, W = rectified.shape[:2]
    rect = _auto_fg_rect(rectified, marker_size_mm, mm_per_px) or \
        (int(0.08 * W), int(0.08 * H), int(0.84 * W), int(0.84 * H))
    gc = np.zeros((H, W), np.uint8)
    bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    cv2.grabCut(rectified, gc, rect, bgd, fgd, iters, cv2.GC_INIT_WITH_RECT)
    mask = np.where((gc == cv2.GC_FGD) | (gc == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
    mask = _blank_corners(mask, marker_size_mm, mm_per_px)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    return mask


def segment_rembg(rectified, marker_size_mm=80.0, mm_per_px=0.5):
    """Optional: U^2-Net background removal (pip install rembg). Best on busy backgrounds.
    Returns None if rembg isn't installed."""
    try:
        from rembg import remove
        out = remove(rectified)
        if out.ndim != 3 or out.shape[2] != 4:
            return None
        mask = (out[:, :, 3] > 128).astype(np.uint8) * 255
        return _blank_corners(mask, marker_size_mm, mm_per_px)
    except Exception:
        return None


def segment_auto(rectified, marker_size_mm=80.0, mm_per_px=0.5):
    """Best available: rembg if installed, else auto-seeded GrabCut."""
    m = segment_rembg(rectified, marker_size_mm, mm_per_px)
    if m is not None and largest_contour(m) is not None:
        return m
    return segment_smart_grabcut(rectified, marker_size_mm, mm_per_px)

"""Scale from the garment itself — no marker, no card, nothing to print.

Two independent estimates, both from things that are already on a pair of jeans:

  find_button   the tack button is a circle of near-standard size (17 mm is the common
                one). A circle photographed at an angle projects to an ellipse whose long
                axis is still the true diameter, and whose axis ratio gives the tilt. So one
                button gives both the scale and how far off square the camera was.

  stitch_pitch  denim topstitching runs at roughly 7-8 stitches per inch (about 3.2 mm).
                The thread is a periodic signal along every seam, so a Fourier transform of
                the brightness along a seam gives the pitch in pixels, and the pitch in
                millimetres is known to about 15%.

Neither is precise: the garment's real button might be 14, 20 or 22 mm, and its real stitch
pitch might be 2.8 or 3.6 mm. Both errors are systematic, so they do not average away with
more photos. Markerless mode is therefore a size-band estimate (about 5-8%, so 2-4 cm on a
waist), not a measurement. Its value is that when the two disagree, something is wrong, and
when they agree the number is probably usable.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

BUTTON_MM = 17.0            # the common jeans tack button; 14, 20 and 22 also exist
RIVET_MM = 9.0
STITCH_MM = 3.2             # ~8 stitches per inch
STITCH_MM_RANGE = (2.7, 3.7)


@dataclass
class ScaleEstimate:
    mm_per_px: float
    source: str
    rel_error: float          # fractional 1-sigma, dominated by the size prior
    detail: str = ""
    tilt_deg: float = 0.0

    @property
    def as_note(self) -> str:
        pct = self.rel_error * 100
        return f"{self.source}: {self.mm_per_px:.4f} mm/px ±{pct:.0f}% ({self.detail})"


# --- the tack button ---------------------------------------------------------------

def find_button(photo, roi=None, diameter_mm=BUTTON_MM, px_band=None, min_round=0.62):
    """Find the most button-like disc in the photo (or in `roi` = (x, y, w, h)).

    Buttons are small, round, brighter than denim and flat in colour. Returns an OpenCV
    rotated-rect ellipse ((cx, cy), (minor, major), angle) in full-image pixels, or None.
    """
    img = photo if photo.ndim == 3 else cv2.cvtColor(photo, cv2.COLOR_GRAY2BGR)
    x0, y0 = 0, 0
    if roi is not None:
        x0, y0, rw, rh = [int(v) for v in roi]
        img = img[y0:y0 + rh, x0:x0 + rw]
    H, W = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    g = cv2.bilateralFilter(gray, 7, 40, 40)

    # A whole garment in frame means the picture spans roughly 0.8-2 m, so a 17 mm button is
    # between about 0.6% and 3% of the long side. Without that band, every highlight on a
    # fold is a candidate.
    lo_px, hi_px = px_band if px_band else (0.004 * max(H, W), 0.040 * max(H, W))
    best, best_score = None, 0.25
    for frac in (0.012, 0.02, 0.03, 0.045):
        k = int(max(5, round(frac * max(H, W))) | 1)
        top = cv2.morphologyEx(g, cv2.MORPH_TOPHAT, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
        if top.max() < 12:
            continue
        thr = max(12, int(np.percentile(top, 99.5)))
        blobs = cv2.morphologyEx((top >= thr).astype(np.uint8) * 255, cv2.MORPH_CLOSE,
                                 np.ones((3, 3), np.uint8))
        cnts, _ = cv2.findContours(blobs, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        for c in cnts:
            if len(c) < 12:
                continue
            area = cv2.contourArea(c)
            if area < 40:
                continue
            (ecx, ecy), (minor, major), ang = cv2.fitEllipse(c)
            if not (lo_px <= major <= hi_px) or minor < 5:
                continue
            ell_area = np.pi * minor * major / 4
            fill = area / max(ell_area, 1e-6)
            round_ = minor / max(major, 1e-6)            # 1 = square-on, lower = tilted
            if fill < 0.75 or round_ < min_round:
                continue
            mask = np.zeros((H, W), np.uint8)
            cv2.ellipse(mask, ((ecx, ecy), (minor, major), ang), 255, -1)
            ring = cv2.dilate(mask, np.ones((9, 9), np.uint8)) - mask
            ins, out = gray[mask > 0], gray[ring > 0]
            if ins.size < 30 or out.size < 30:
                continue
            contrast = (float(ins.mean()) - float(out.mean())) / 40.0
            score = min(1.0, max(0.0, contrast)) * fill * round_ ** 2
            if score > best_score:
                best, best_score = ((ecx + x0, ecy + y0), (minor, major), ang), score
    return best


def refine_disc(photo, ellipse, rays=72):
    """Re-measure a disc from its edge instead of its highlight.

    The bright blob a button makes is the specular highlight, which is smaller than the metal,
    so scaling off it reads about 13% too small. This walks outward from the centre along
    rays, takes the strongest brightness step on each, and fits an ellipse to those points —
    the physical edge rather than the shine."""
    gray = cv2.cvtColor(photo, cv2.COLOR_BGR2GRAY) if photo.ndim == 3 else photo
    gray = cv2.GaussianBlur(gray, (0, 0), 1.2).astype(np.float32)
    (cx, cy), (minor, major), _ = ellipse
    r_max = major * 1.6
    pts = []
    for th in np.linspace(0, 2 * np.pi, rays, endpoint=False):
        d = np.array([np.cos(th), np.sin(th)], np.float32)
        rs = np.arange(max(2.0, minor * 0.25), r_max, 0.5)
        xs = np.clip((cx + d[0] * rs).astype(int), 0, gray.shape[1] - 1)
        ys = np.clip((cy + d[1] * rs).astype(int), 0, gray.shape[0] - 1)
        prof = gray[ys, xs]
        if prof.size < 8:
            continue
        grad = np.diff(cv2.GaussianBlur(prof.reshape(-1, 1), (0, 0), 1.0).ravel())
        k = int(np.argmin(grad))            # brightest-to-darkest step going outward
        if -grad[k] < 2.0:
            continue
        pts.append((cx + d[0] * rs[k], cy + d[1] * rs[k]))
    if len(pts) < 12:
        return ellipse
    ref = cv2.fitEllipse(np.array(pts, np.float32).reshape(-1, 1, 2))
    # a disc's edge is close to its highlight; if the "edge" came out wildly bigger we found
    # the contact shadow around the button, not the button
    if not (0.75 <= ref[1][1] / max(major, 1e-6) <= 1.35):
        return ellipse
    return ref


def scale_from_button(ellipse, diameter_mm=BUTTON_MM, size_uncertainty=0.14):
    """mm per pixel from a button's ellipse. The long axis of a projected circle is the
    unforeshortened diameter, so it gives scale directly; the axis ratio gives the tilt."""
    (_, (minor, major), _) = ellipse
    mm_per_px = diameter_mm / float(major)
    tilt = float(np.degrees(np.arccos(np.clip(minor / max(major, 1e-6), 0, 1))))
    edge_err = 1.5 / float(major)               # a pixel or so of edge uncertainty
    rel = float(np.hypot(size_uncertainty, edge_err))
    return ScaleEstimate(mm_per_px, "button", rel,
                         f"{diameter_mm:.0f} mm assumed, {major:.0f} px across", tilt)


# --- the topstitching --------------------------------------------------------------

def _profile_along(gray, p0, p1, half_width=3):
    """Mean brightness along a line, averaged across a few pixels either side."""
    p0, p1 = np.asarray(p0, np.float32), np.asarray(p1, np.float32)
    n = int(np.linalg.norm(p1 - p0))
    if n < 32:
        return None
    t = np.linspace(0, 1, n)
    d = (p1 - p0) / (np.linalg.norm(p1 - p0) + 1e-6)
    nrm = np.array([-d[1], d[0]], np.float32)
    acc = []
    for off in range(-half_width, half_width + 1):
        pts = p0[None, :] + t[:, None] * (p1 - p0)[None, :] + nrm[None, :] * off
        xi = np.clip(pts[:, 0].astype(int), 0, gray.shape[1] - 1)
        yi = np.clip(pts[:, 1].astype(int), 0, gray.shape[0] - 1)
        acc.append(gray[yi, xi].astype(np.float32))
    return np.mean(acc, axis=0)


def stitch_pitch(photo, segments, px_range=(2.0, 40.0)):
    """Dominant repeat length (pixels) of the topstitching along the given line segments.

    `segments` is a list of ((x0, y0), (x1, y1)) in pixels, ideally running along seams.
    Returns (pitch_px, agreement) where agreement is how consistent the segments were.
    """
    gray = cv2.cvtColor(photo, cv2.COLOR_BGR2GRAY) if photo.ndim == 3 else photo
    peaks = []
    for p0, p1 in segments:
        prof = _profile_along(gray, p0, p1)
        if prof is None:
            continue
        prof = prof - cv2.GaussianBlur(prof.reshape(-1, 1), (0, 0), 8).ravel()   # detrend
        prof *= np.hanning(len(prof))
        spec = np.abs(np.fft.rfft(prof))
        freqs = np.fft.rfftfreq(len(prof), d=1.0)
        ok = (freqs > 1.0 / px_range[1]) & (freqs < 1.0 / px_range[0])
        if not ok.any() or spec[ok].max() <= 0:
            continue
        f = freqs[ok][int(np.argmax(spec[ok]))]
        snr = float(spec[ok].max() / (np.median(spec[ok]) + 1e-6))
        if snr > 3.0:
            peaks.append(1.0 / f)
    if not peaks:
        return None, 0.0
    peaks = np.array(peaks)
    med = float(np.median(peaks))
    agreement = float(np.mean(np.abs(peaks - med) < 0.2 * med))
    return med, agreement


def scale_from_stitches(pitch_px, stitch_mm=STITCH_MM):
    lo, hi = STITCH_MM_RANGE
    rel = (hi - lo) / 2 / stitch_mm
    return ScaleEstimate(stitch_mm / pitch_px, "stitching", rel,
                         f"{stitch_mm:.1f} mm per stitch assumed, {pitch_px:.1f} px measured")


# --- putting the two together -------------------------------------------------------

def combine(estimates):
    """Inverse-variance weighted mean of independent scale estimates, plus a disagreement
    flag: two independent priors landing in the same place is the only evidence markerless
    mode can offer that it hasn't gone wrong."""
    est = [e for e in estimates if e is not None]
    if not est:
        return None, "no scale reference found"
    if len(est) == 1:
        return est[0], "single estimate, unchecked"
    w = np.array([1.0 / (e.rel_error ** 2) for e in est])
    v = np.array([e.mm_per_px for e in est])
    mm = float((w * v).sum() / w.sum())
    rel = float(1.0 / np.sqrt(w.sum()))
    spread = float(np.max(np.abs(v - mm)) / mm)
    note = (f"button and stitching agree to {spread * 100:.0f}%"
            if spread < 0.15 else
            f"button and stitching disagree by {spread * 100:.0f}% — treat with suspicion")
    return ScaleEstimate(mm, "combined", rel, note), note


# --- recovering the perspective from a field of local scale estimates ----------------

def fit_scale_field(samples, iters=3):
    """Fit millimetres-per-pixel across the whole photo from local estimates.

    A plane seen by a camera gives scale s(x, y) = s0 / (a·x + b·y + 1)^2, three numbers for
    the whole picture. Substituting u = 1/sqrt(s) makes that linear — u = (a·x + b·y + 1)/√s0
    — so it is an ordinary least squares fit, with a couple of reweighting passes to stop one
    bad seam dragging it.

    `samples` is a sequence of (x, y, mm_per_px). Returns a function f(x, y) -> mm_per_px,
    or None if there aren't enough samples. Feed it relative scale (1/stitch pitch) and the
    field shape is still right; multiply by an anchor afterwards.
    """
    pts = np.asarray([(x, y, s) for x, y, s in samples if s > 0], np.float64)
    if len(pts) < 8:
        return None
    x, y, s = pts[:, 0], pts[:, 1], pts[:, 2]
    A = np.column_stack([x, y, np.ones_like(x)])
    u = 1.0 / np.sqrt(s)
    w = np.ones_like(u)
    for _ in range(iters):
        sol, *_ = np.linalg.lstsq(A * w[:, None], u * w, rcond=None)
        r = A @ sol - u
        scale = 1.4826 * np.median(np.abs(r - np.median(r))) + 1e-9
        w = 1.0 / np.sqrt(1.0 + (r / (3 * scale)) ** 2)          # soft robust weights
    alpha, beta, gamma = sol
    if abs(gamma) < 1e-12:
        return None

    def field(px_x, px_y):
        den = alpha * np.asarray(px_x, np.float64) + beta * np.asarray(px_y, np.float64) + gamma
        return 1.0 / np.maximum(den, 1e-9) ** 2

    return field


def anchor_field(field, anchors):
    """Scale a relative field so it matches absolute anchors (button, rivets, waistband).

    `anchors` is a sequence of (x, y, mm_per_px). Returns (field, spread) where spread is how
    much the anchors disagreed once the field's shape is taken out — the honest check on
    whether the size priors were right."""
    vals = [a_mm / field(ax, ay) for ax, ay, a_mm in anchors]
    if not vals:
        return field, None
    k = float(np.median(vals))
    spread = float(np.max(np.abs(np.array(vals) / k - 1))) if len(vals) > 1 else None
    return (lambda px_x, px_y: k * field(px_x, px_y)), spread



# --- a blank sheet of A4, or any rectangle of known size -----------------------------

A4_MM = (210.0, 297.0)


def find_rectangle(photo, ref_mm=A4_MM, frac_band=(0.05, 0.55)):
    """Find a plain rectangle of known proportions — a sheet of A4, a card, a book.

    Same idea as the button: regions that stay stable as the threshold moves (MSER), filtered
    by proportions and by having four real step edges rather than a soft shadow boundary.
    Returns the four corners in pixels (TL, TR, BR, BL) or None."""
    img = photo if photo.ndim == 3 else cv2.cvtColor(photo, cv2.COLOR_GRAY2BGR)
    H, W = img.shape[:2]
    scale = min(1.0, 1600.0 / max(H, W))
    small = cv2.resize(img, (int(W * scale), int(H * scale)), interpolation=cv2.INTER_AREA)
    h, w = small.shape[:2]
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    g = cv2.bilateralFilter(gray, 7, 40, 40)
    ref_aspect = max(ref_mm) / min(ref_mm)

    mser = cv2.MSER_create()
    mser.setMinArea(int(0.004 * h * w))
    mser.setMaxArea(int(0.35 * h * w))
    mser.setDelta(5)
    best, best_score = None, 0.3
    for img_v in (g, 255 - g):
        try:
            regs, _ = mser.detectRegions(img_v)
        except cv2.error:
            continue
        for r in regs:
            pts = r.reshape(-1, 1, 2).astype(np.float32)
            (rc, (rw, rh), ang) = cv2.minAreaRect(pts)
            if min(rw, rh) < 20:
                continue
            long_frac = max(rw, rh) / max(h, w)
            if not (frac_band[0] <= long_frac <= frac_band[1]):
                continue
            asp = max(rw, rh) / min(rw, rh)
            a_err = abs(asp - ref_aspect) / ref_aspect
            if a_err > 0.18:
                continue
            if len(r) / (rw * rh + 1e-6) < 0.82:
                continue
            box = cv2.boxPoints(((rc), (rw, rh), ang)).astype(np.float32)
            inside = np.zeros((h, w), np.uint8)
            cv2.fillPoly(inside, [np.int32(box)], 255)
            inner = cv2.erode(inside, np.ones((9, 9), np.uint8))
            ring = cv2.dilate(inside, np.ones((21, 21), np.uint8)) - inside
            ins, out = gray[inner > 0], gray[ring > 0]
            if ins.size < 200 or out.size < 200:
                continue
            contrast = abs(float(ins.mean()) - float(out.mean())) / 40.0
            flat = float(np.clip(1.0 - ins.std() / 30.0, 0, 1))
            score = (1 - a_err / 0.18) * min(1.0, contrast) * (0.4 + 0.6 * flat)
            if score > best_score:
                best, best_score = box, score
    if best is None:
        return None
    return best / scale


def scale_from_rectangle(corners, ref_mm=A4_MM):
    """mm per pixel from a rectangle of known size, measured on its long sides."""
    q = np.asarray(corners, np.float32)
    sides = [float(np.linalg.norm(q[(i + 1) % 4] - q[i])) for i in range(4)]
    long_px = (sides[1] + sides[3]) / 2 if (sides[1] + sides[3]) > (sides[0] + sides[2]) else (sides[0] + sides[2]) / 2
    short_px = min((sides[0] + sides[2]) / 2, (sides[1] + sides[3]) / 2)
    mm_per_px = max(ref_mm) / long_px
    tilt = float(np.degrees(np.arccos(np.clip((short_px / long_px) / (min(ref_mm) / max(ref_mm)), 0, 1))))
    return ScaleEstimate(mm_per_px, "A4 sheet", 0.02,
                         f"{max(ref_mm):.0f} mm long side, {long_px:.0f} px", tilt)

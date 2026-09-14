"""Grade the markerless scale estimates against the marker mat.

Any photo that has the printed sheets in it comes with ground truth: the mat gives the exact
millimetres-per-pixel at every point. So the same photo can be measured the hard way (markers)
and the cheap way (the garment's own stitching and hardware), and the two compared. That makes
the mat a grader for the thing meant to replace it.

    python -m validation.markerless_probe path/to/photo.jpg [more.jpg ...]

Prints, per photo:
  - how much the true scale varies across the garment (the perspective problem)
  - the error of a single constant scale (what one button alone can do)
  - the error of the fitted scale field from stitch pitch (what the seams add)
  - the button's own estimate, if a button is found
"""

from __future__ import annotations

import sys

import cv2
import numpy as np

from core.calibrate import calibrate
from core.markerless import (BUTTON_MM, _profile_along, find_button, fit_scale_field,
                             scale_from_button)


def true_scale_fn(cal):
    """mm per pixel at a point in the original photo, from the mat calibration."""
    def f(p, d=40):
        pts = np.array([[[p[0], p[1]], [p[0] + d, p[1]], [p[0], p[1] + d]]], np.float32)
        q = cv2.perspectiveTransform(pts, cal.H)[0] * cal.mm_per_px
        return float(np.sqrt(np.linalg.norm(q[1] - q[0]) * np.linalg.norm(q[2] - q[0])) / d)
    return f


def garment_contour(photo):
    """Rough outline of the dark garment in the original photo."""
    gray = cv2.cvtColor(photo, cv2.COLOR_BGR2GRAY)
    thr = float(np.percentile(gray, 25))
    m = (cv2.GaussianBlur(gray, (0, 0), 3) < thr).astype(np.uint8) * 255
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((15, 15), np.uint8))
    cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cnts:
        return None
    return max(cnts, key=cv2.contourArea).reshape(-1, 2).astype(np.float32)


def stitch_samples(photo, contour, step=25, window=80, inset=12, snr_min=5.0):
    """Local stitch frequency along the seams, sampled around the garment outline."""
    gray = cv2.cvtColor(photo, cv2.COLOR_BGR2GRAY)
    centre = contour.mean(0)
    out = []
    for i in range(0, len(contour), step):
        p = contour[i]
        nxt = contour[(i + 20) % len(contour)]
        d = nxt - p
        n = np.linalg.norm(d)
        if n < 5:
            continue
        d = d / n
        inward = centre - p
        inward = inward / (np.linalg.norm(inward) + 1e-6)
        base = p + inward * inset                      # topstitching sits just inside the edge
        prof = _profile_along(gray, base - d * window, base + d * window, 2)
        if prof is None:
            continue
        prof = prof - cv2.GaussianBlur(prof.reshape(-1, 1), (0, 0), 6).ravel()
        prof = prof * np.hanning(len(prof))
        spec = np.abs(np.fft.rfft(prof))
        fr = np.fft.rfftfreq(len(prof))
        ok = (fr > 1 / 14.0) & (fr < 1 / 4.0)
        if not ok.any() or spec[ok].max() / (np.median(spec[ok]) + 1e-9) < snr_min:
            continue
        out.append((float(base[0]), float(base[1]), float(fr[ok][int(np.argmax(spec[ok]))])))
    return out


def probe(path):
    photo = cv2.imread(path)
    if photo is None:
        print(f"{path}: unreadable")
        return
    cal = calibrate(photo, mm_per_px_out=0.5)
    if not cal.ok:
        print(f"{path}: no markers, so no ground truth to grade against")
        return
    truth = true_scale_fn(cal)
    contour = garment_contour(photo)
    if contour is None:
        print(f"{path}: couldn't find the garment")
        return
    samples = stitch_samples(photo, contour)
    print(f"\n{path}  ({photo.shape[1]}x{photo.shape[0]}, {len(samples)} stitch samples)")

    tr = np.array([truth((x, y)) for x, y, _ in samples]) if samples else np.array([])
    if tr.size:
        print(f"  true scale across the garment: {tr.min():.3f}–{tr.max():.3f} mm/px "
              f"({100 * (tr.max() / tr.min() - 1):.0f}% variation)")
        const = np.median(tr)
        print(f"  one constant scale:      median {100 * np.median(np.abs(const / tr - 1)):.1f}%  "
              f"worst {100 * np.max(np.abs(const / tr - 1)):.1f}%")
        field = fit_scale_field(samples)
        if field is not None:
            est = np.array([field(x, y) for x, y, _ in samples])
            k = float(np.median(tr / est))
            err = np.abs(est * k / tr - 1)
            print(f"  fitted from stitching:   median {100 * np.median(err):.1f}%  "
                  f"90th pct {100 * np.percentile(err, 90):.1f}%")

    e = find_button(photo)
    if e is None:
        print("  button: not found")
    else:
        est = scale_from_button(e)
        t = truth(e[0])
        print(f"  button: {est.mm_per_px:.4f} mm/px vs true {t:.4f} "
              f"({100 * (est.mm_per_px / t - 1):+.1f}%), tilt {est.tilt_deg:.0f}°, "
              f"{BUTTON_MM:.0f} mm assumed")


if __name__ == "__main__":
    for p in sys.argv[1:] or ["validation/scenes/jeans-charcoal.jpg"]:
        probe(p)

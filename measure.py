"""Measure a garment lying flat, from one photograph.

    python measure.py photo.jpg --reference a5
    python measure.py photo.jpg --reference card --units in
    python measure.py photo.jpg --reference 148x210 --overlay out.png

The reference is any flat rectangle of known size lying in the same plane as the garment: a
sheet of paper, a bank card. Its four corners fix the plane, which is what turns a handheld
tilted photograph into a view where one pixel is a fixed fraction of a millimetre everywhere.

Nothing is printed and no model is trained. Every number traces back to a rule you can read in
core/measure.py, and the tolerances are the ones measured in validation/sweep.py.
"""

from __future__ import annotations

import argparse
import sys

import cv2
import numpy as np

from core.calibrate import calibrate, calibrate_by_paper
from core.classify import classify
from core.flatlay import (fill_holes, garment_mask, largest_contour, rotate, silhouette_split,
                          trace_crease, waistband_tilt)
from core.markerless import find_rectangle
from core.measure import measure
from core.segment import contrast, contrast_check, segment_auto

REFERENCES = {
    "a4":     (210.0, 297.0),
    "a5":     (148.0, 210.0),
    "a6":     (105.0, 148.0),
    "letter": (215.9, 279.4),
    "card":   (53.98, 85.60),     # ISO/IEC 7810 ID-1 — bank cards, most ID cards
}
INCH = 2.54


def parse_reference(text: str):
    key = text.lower().strip()
    if key in REFERENCES:
        return REFERENCES[key]
    if "x" in key:
        try:
            w, h = (float(v) for v in key.split("x", 1))
            return (min(w, h), max(w, h))
        except ValueError:
            pass
    raise SystemExit(f"unknown reference {text!r}; use one of "
                     f"{', '.join(sorted(REFERENCES))}, 'mat', or WIDTHxHEIGHT in mm")


def flatten(photo, reference):
    """Square-on metric view of the photo, plus the region the reference occupies."""
    if reference == "mat":
        cal = calibrate(photo, mm_per_px_out=0.5)
        if not cal.ok:
            raise SystemExit("no calibration markers found in this photo")
        return cal
    ref_mm = parse_reference(reference)
    corners = find_rectangle(photo, ref_mm)
    if corners is None:
        raise SystemExit(
            f"couldn't find a {ref_mm[0]:.0f}x{ref_mm[1]:.0f} mm rectangle in this photo.\n"
            "The reference has to be fully visible, flat, and clearly lighter or darker than\n"
            "whatever it is lying on.")
    rough = garment_mask(photo)
    if rough is None:
        raise SystemExit("couldn't find the garment in this photo")
    rough = rough.copy()
    cv2.fillPoly(rough, [np.int32(cv2.boxPoints(cv2.minAreaRect(np.asarray(corners, np.float32))))], 0)
    box = cv2.boxPoints(cv2.minAreaRect(largest_contour(rough)))
    cal = calibrate_by_paper(photo, paper_mm=ref_mm, corners=np.asarray(corners, np.float32),
                             garment_box_px=box)
    if not cal.ok:
        raise SystemExit("found the reference but couldn't rectify the plane from it")
    return cal


def silhouette(photo, cal, channel="auto"):
    """The garment's outline in the rectified view.

    Two routes, because they suit different photographs. With the printed mat, the seeded
    GrabCut in core.segment already knows roughly where the garment is and handles the printed
    sheets lying around it. Without it, a colour split in Lab is both faster and steadier — it
    is the only thing that separates tan cotton from grey carpet, where brightness does not.
    """
    if cal.mode == "mat":
        m = segment_auto(cal.rectified, cal.marker_size_mm, cal.mm_per_px,
                         prior=cal.prior, exclude=cal.exclude)
        if m is not None and largest_contour(m) is not None:
            return m
    rough = garment_mask(photo, channel=channel)
    if rough is None:
        raise SystemExit("couldn't find the garment in this photo")
    return cv2.warpPerspective(rough, cal.H, (cal.rectified.shape[1], cal.rectified.shape[0]),
                               flags=cv2.INTER_NEAREST)


def analyse(photo, cal, channel="auto"):
    """Silhouette, squared up, in the rectified view."""
    mask = silhouette(photo, cal, channel)
    if cal.exclude is not None:
        mask[cal.exclude > 0] = 0
    mask = fill_holes(cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8)))
    tilt = waistband_tilt(mask)
    mask, rect = rotate(mask, tilt), rotate(cal.rectified, tilt, (255, 255, 255))
    n, lbl, stats, _ = cv2.connectedComponentsWithStats(mask)
    if n < 2:
        raise SystemExit("lost the garment while squaring the picture up")
    mask = (lbl == 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))).astype(np.uint8) * 255
    return mask, rect, tilt


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("photo")
    ap.add_argument("--reference", default="a4",
                    help="a4, a5, a6, letter, card, mat, or WIDTHxHEIGHT in mm (default: a4)")
    ap.add_argument("--units", choices=("cm", "in"), default="cm")
    ap.add_argument("--channel", default="auto", choices=("auto", "L", "a", "b"),
                    help="Lab channel to cut the garment out on (default: pick automatically)")
    ap.add_argument("--overlay", default=None, help="write an annotated image here")
    args = ap.parse_args(argv)

    photo = cv2.imread(args.photo)
    if photo is None:
        raise SystemExit(f"cannot read {args.photo}")

    cal = flatten(photo, args.reference)
    mask, rect, tilt = analyse(photo, cal, args.channel)
    cnt = largest_contour(mask)

    level = contrast(rect, mask)
    status, message = contrast_check(level)
    if status == "refuse":
        print(f"REFUSED — {message}")
        return 1

    kind, category, how = classify(image_bgr=rect, contour=cnt)
    rows = measure(cnt, kind, cal.mm_per_px, cal.tol_scale)

    # the outline's split is below the real crotch when one leg lies over the other
    apex = silhouette_split(mask)
    crotch = None
    if apex is not None:
        ys = np.where(mask.any(1))[0]
        height = int(ys[-1]) - int(ys[0])
        pt, _ = trace_crease(rect, mask, apex, int(0.45 * height))
        # Only believe the crease when it buys a real correction. On a garment whose legs do not
        # overlap the trace dies almost immediately, and a couple of rows of drift is noise, not
        # a crotch; anything past a third of the garment is the fly seam, not the leg edge.
        gain = (apex[1] - pt[1]) if pt is not None else 0
        if pt is not None and 0.03 * height < gain < 0.30 * height:
            crotch = pt
            inseam = (int(ys[-1]) - pt[1]) * cal.mm_per_px / 10.0
            for r in rows:
                if r.name == "inseam":
                    r.value_cm = round(inseam, 1)
                    r.p1, r.p2 = (pt[0], pt[1]), (pt[0], int(ys[-1]))

    scale = 1.0 if args.units == "cm" else 1 / INCH
    print(f"\n{args.photo}")
    print(f"  {kind} ({how}), {cal.mode} mode, reference {args.reference}, "
          f"camera {abs(tilt):.1f} deg off square")
    print(f"  {'-' * 46}")
    for r in rows:
        print(f"  {r.name:<16}{r.value_cm * scale:>8.1f} {args.units}"
              f"{'  +/- ' + format(r.tolerance_cm * scale, '.1f'):>12}")
    if status == "warn":
        print(f"\n  warning: {message}")

    if args.overlay:
        vis = rect.copy()
        cv2.drawContours(vis, [cnt], -1, (36, 28, 179), 3, cv2.LINE_AA)
        for r in rows:
            cv2.line(vis, tuple(map(int, r.p1)), tuple(map(int, r.p2)), (36, 28, 179), 3, cv2.LINE_AA)
        cv2.imwrite(args.overlay, vis)
        print(f"\n  overlay written to {args.overlay}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

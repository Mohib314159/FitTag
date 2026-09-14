"""Measure with no printing: one sheet of A4, and a box round the garment.

Each scene is rendered twice from the same seed and camera — once with the marker sheets,
which gives the truth, and once with a single blank sheet of A4, which is what a person
would actually have. The box that stands in for the user's drag comes from the *truth* run's
garment outline, because that is what someone dragging a box would produce; faking it with a
brightness threshold would be testing the threshold instead of the method.

    python -m validation.paper_mode        # ~4 min -> docs/data/paper.json
"""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from core.calibrate import calibrate, calibrate_by_paper
from core.markerless import find_rectangle
from core.measure import measure
from core.segment import largest_contour, segment_auto
from validation import render_scene as R

ROOT = Path(__file__).resolve().parent.parent
TILTS = (5, 12, 20, 28)


def run_pair(pitch, seed):
    R.set_margin(450)
    base = dict(R.SCENES[0])
    base["seed"] = seed
    base["camera"] = dict(base["camera"])
    base["camera"].update(out_size=(2268, 3024), height_mm=1700.0, pitch_deg=pitch)

    truth_photo, _, gt, _ = R.render(base)
    paper_spec = dict(base, paper=True, missing=(0, 1, 2, 3))
    paper_photo, _, _, _ = R.render(paper_spec)

    cal = calibrate(truth_photo, mm_per_px_out=0.5)
    if not cal.ok:
        return None
    mask = segment_auto(cal.rectified, cal.marker_size_mm, cal.mm_per_px)
    contour = largest_contour(mask)
    marker_ms = {m.name: m.value_cm for m in measure(contour, "jeans", 0.5)}

    # the garment's extent in the photo, i.e. what a user's drag would enclose
    inv = np.linalg.inv(cal.H)
    pts = cv2.perspectiveTransform(contour.reshape(1, -1, 2).astype(np.float32), inv)[0]
    box = cv2.boxPoints(cv2.minAreaRect(pts.astype(np.float32)))

    corners = find_rectangle(paper_photo)
    if corners is None:
        return {"tilt": pitch, "ok": False, "why": "sheet of A4 not found", "truth": gt}
    cal2 = calibrate_by_paper(paper_photo, corners=corners, garment_box_px=box)
    if not cal2.ok:
        return {"tilt": pitch, "ok": False, "why": "could not rectify from the sheet", "truth": gt}
    m2 = segment_auto(cal2.rectified, marker_size_mm=cal2.marker_size_mm, mm_per_px=0.5,
                      prior=cal2.prior, exclude=cal2.exclude)
    c2 = largest_contour(m2)
    if c2 is None:
        return {"tilt": pitch, "ok": False, "why": "garment not separated", "truth": gt}
    paper_ms = {m.name: m.value_cm for m in measure(c2, "jeans", 0.5, tol_scale=cal2.tol_scale)}
    rows = []
    for k, t in gt.items():
        rows.append({"name": k, "truth": t,
                     "markers": round(marker_ms.get(k, float("nan")), 1),
                     "paper": round(paper_ms.get(k, float("nan")), 1),
                     "err_cm": round(paper_ms.get(k, float("nan")) - t, 1) if k in paper_ms else None})
    return {"tilt": pitch, "ok": True, "truth": gt, "rows": rows}


def main():
    out = []
    for i, pitch in enumerate(TILTS):
        r = run_pair(pitch, 700 + pitch)
        if r is None:
            continue
        out.append(r)
        if r["ok"]:
            errs = [abs(x["err_cm"]) for x in r["rows"] if x["err_cm"] is not None]
            print(f"{pitch:3d}°  " + "  ".join(f'{x["name"].split("_")[0]}:{x["err_cm"]:+.1f}' for x in r["rows"])
                  + f"   worst {max(errs):.1f} cm")
        else:
            print(f"{pitch:3d}°  refused: {r['why']}")
    errs = [abs(x["err_cm"]) for r in out if r["ok"] for x in r["rows"] if x["err_cm"] is not None]
    if errs:
        print(f"\nmedian |error| {np.median(errs):.1f} cm ({np.median(errs) / 2.54:.2f} in), "
              f"worst {max(errs):.1f} cm ({max(errs) / 2.54:.2f} in), n={len(errs)}")
    (ROOT / "docs" / "data" / "paper.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()

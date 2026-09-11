"""Run the engine on every photo in ground_truth.csv and report error vs the
(tape-measured) truth. This produces the accuracy number — the technical-axis winner.

    python -m validation.validate
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

import cv2

from core.calibrate import calibrate
from core.segment import segment_auto, largest_contour
from core.measure import measure

HERE = Path(__file__).resolve().parent


def main():
    rows = list(csv.DictReader(open(HERE / "ground_truth.csv")))
    errs = defaultdict(list)
    within = defaultdict(lambda: [0, 0])
    print(f"{'photo':<10}{'measurement':<15}{'truth':>7}{'pred':>7}{'err':>7}")
    for r in rows:
        img = cv2.imread(str(HERE / "photos" / r["photo"]))
        cal = calibrate(img, mm_per_px_out=0.5)
        if not cal.ok:
            print(f"{r['photo']:<10} NO CALIBRATION"); continue
        mask = segment_auto(cal.rectified, marker_size_mm=cal.marker_size_mm, mm_per_px=cal.mm_per_px)
        contour = largest_contour(mask)
        ms = {m.name: m for m in measure(contour, r["garment_type"], cal.mm_per_px, tol_scale=cal.tol_scale)}
        for name, m in ms.items():
            if not r.get(name):
                continue
            truth = float(r[name]); err = abs(m.value_cm - truth)
            errs[name].append(err)
            within[name][0] += int(err <= m.tolerance_cm); within[name][1] += 1
            print(f"{r['photo']:<10}{name:<15}{truth:>7.1f}{m.value_cm:>7.1f}{err:>7.2f}")

    print("\n=== summary (mean abs error, cm) ===")
    all_err = []
    for name in sorted(errs):
        e = errs[name]; all_err += e
        hit, tot = within[name]
        print(f"  {name:<15} MAE {sum(e)/len(e):.2f}   max {max(e):.2f}   within tol {hit}/{tot}")
    if all_err:
        print(f"\n  OVERALL MAE: {sum(all_err)/len(all_err):.2f} cm  over {len(all_err)} measurements")


if __name__ == "__main__":
    main()

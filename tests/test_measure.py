"""Full pipeline on a simulated oblique photo of a garment on the calibration mat;
checks recovery against known dimensions. Each measurement passes if it lands within
its own stated tolerance (that's what the error bar is for).

Run:  python -m tests.test_measure
"""

from __future__ import annotations

import sys

from core.calibrate import calibrate
from core.segment import segment_by_color, largest_contour
from core.measure import measure
from tests.synth import make_tshirt_photo, MM_PER_PX


def run_case(name: str, tilt=0.08, **poly_kwargs) -> bool:
    photo, gt = make_tshirt_photo(tilt=tilt, **poly_kwargs)
    cal = calibrate(photo, mm_per_px_out=MM_PER_PX)
    if not cal.ok:
        print(f"[{name}] FAIL: no marker detected"); return False
    mask = segment_by_color(cal.rectified, marker_size_mm=cal.marker_size_mm, mm_per_px=cal.mm_per_px)
    contour = largest_contour(mask)
    if contour is None:
        print(f"[{name}] FAIL: garment not segmented"); return False
    from core.segment import touches_border
    if touches_border(contour, cal.rectified.shape):
        print(f"[{name}] WARN: garment touches mat edge (use a larger mat)")

    ms = measure(contour, "t-shirt", cal.mm_per_px, tol_scale=cal.tol_scale)
    got = {m.name: m for m in ms}

    print(f"\n=== {name}  (mode={cal.mode}, {cal.n_markers} markers, tilt={tilt}) ===")
    print(f"{'measurement':<16}{'truth':>8}{'pred':>8}{'err':>8}{'±tol':>7}  status")
    ok = True
    for key, truth in gt.items():
        if key not in got:
            print(f"{key:<16}{truth:>8.1f}{'--':>8}{'MISS':>8}"); ok = False; continue
        m = got[key]; err = abs(m.value_cm - truth)
        within = err <= m.tolerance_cm
        print(f"{key:<16}{truth:>8.1f}{m.value_cm:>8.1f}{err:>8.2f}{m.tolerance_cm:>7.1f}  {'ok' if within else 'OUT'}")
        ok = ok and within
    print(f"result: {'PASS' if ok else 'FAIL'}")
    return ok


def main():
    cases = [
        ("baseline tee",         dict(tilt=0.08)),
        ("slim crop tee",        dict(tilt=0.08, bw=460.0, bl=620.0, sw=180.0, sl=100.0)),
        ("oversized box tee",    dict(tilt=0.06, bw=560.0, bl=740.0, sw=220.0, sl=120.0, taper=4.0)),
        ("steeper camera angle", dict(tilt=0.15)),
    ]
    results = [run_case(n, **kw) for n, kw in cases]
    print("\n" + "=" * 46)
    passed = sum(results)
    print(f"SUITE: {passed}/{len(results)} passed   (max single-measurement error vs ±tol)")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()

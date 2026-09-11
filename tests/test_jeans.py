"""Validate the engine on bottoms: jeans of known dimensions on the mat, recovered
through a simulated oblique photo. Also checks the classifier flags it as a bottom.

Run:  python -m tests.test_jeans
"""

from __future__ import annotations

import sys

from core.calibrate import calibrate
from core.segment import segment_by_color, largest_contour
from core.classify import classify
from core.measure import measure
from tests.synth import make_jeans_photo, MM_PER_PX


def run_case(name: str, tilt=0.08, **poly_kwargs) -> bool:
    photo, gt = make_jeans_photo(tilt=tilt, **poly_kwargs)
    cal = calibrate(photo, mm_per_px_out=MM_PER_PX)
    if not cal.ok:
        print(f"[{name}] FAIL: no marker detected"); return False
    mask = segment_by_color(cal.rectified, marker_size_mm=cal.marker_size_mm, mm_per_px=cal.mm_per_px)
    contour = largest_contour(mask)

    gtype, category, src = classify(image_bgr=cal.rectified, contour=contour)
    ms = measure(contour, "jeans", cal.mm_per_px, tol_scale=cal.tol_scale)
    got = {m.name: m for m in ms}

    print(f"\n=== {name}  (classifier: {gtype}/{category} via {src}, tilt={tilt}) ===")
    print(f"{'measurement':<14}{'truth':>8}{'pred':>8}{'err':>8}{'±tol':>7}  status")
    ok = (category == "bottom")
    if not ok:
        print("  classifier did NOT flag a bottom")
    for key, truth in gt.items():
        if key not in got:
            print(f"{key:<14}{truth:>8.1f}{'--':>8}{'MISS':>8}"); ok = False; continue
        m = got[key]; err = abs(m.value_cm - truth); within = err <= m.tolerance_cm
        print(f"{key:<14}{truth:>8.1f}{m.value_cm:>8.1f}{err:>8.2f}{m.tolerance_cm:>7.1f}  {'ok' if within else 'OUT'}")
        ok = ok and within
    print(f"result: {'PASS' if ok else 'FAIL'}")
    return ok


def main():
    cases = [
        ("straight-leg 501",  dict(tilt=0.08)),
        ("slim crop",         dict(tilt=0.08, waist=360.0, inseam=520.0, leg_open=150.0)),
        ("wide-leg, tilted",  dict(tilt=0.14, waist=520.0, inseam=680.0, leg_open=230.0)),
    ]
    results = [run_case(n, **kw) for n, kw in cases]
    print("\n" + "=" * 46)
    passed = sum(results)
    print(f"JEANS SUITE: {passed}/{len(results)} passed")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()

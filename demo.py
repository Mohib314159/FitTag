"""End-to-end demo: synthetic photo -> calibrate -> segment -> classify -> measure ->
fit. Prints the full GarmentMeasurement and FitReport, and writes an annotated overlay.
Runs anywhere (no API key, no real photo needed): the classifier falls back to the
deterministic silhouette heuristic.

    python demo.py
"""

from __future__ import annotations

import cv2

from core.calibrate import calibrate
from core.segment import segment_by_color, largest_contour, touches_border
from core.classify import classify
from core.measure import measure
from core.fit import compute_fit
from core.contracts import GarmentMeasurement, BodyProfile
from viz.overlay import draw_measurements
from tests.synth import make_tshirt_photo, MM_PER_PX


def build(item_id="demo-tee"):
    photo, gt = make_tshirt_photo(tilt=0.10)
    cal = calibrate(photo, mm_per_px_out=MM_PER_PX)
    assert cal.ok, "marker not found"

    mask = segment_by_color(cal.rectified, marker_size_mm=cal.marker_size_mm, mm_per_px=cal.mm_per_px)
    contour = largest_contour(mask)

    gtype, category, src = classify(image_bgr=cal.rectified, contour=contour)
    measurements = measure(contour, gtype, cal.mm_per_px, tol_scale=cal.tol_scale)

    notes = [f"calibration={cal.mode} ({cal.n_markers} markers)", f"type via {src}"]
    if touches_border(contour, cal.rectified.shape):
        notes.append("garment touches mat edge — use a larger mat")

    g = GarmentMeasurement(
        item_id=item_id, garment_type=gtype, measurements=measurements,
        marker_size_mm=cal.marker_size_mm, mm_per_px=cal.mm_per_px,
        rectification_ok=cal.ok, notes=notes,
    )
    return g, cal, photo


def main():
    g, cal, _ = build()

    print(f"\nGARMENT  id={g.item_id}  type={g.garment_type}  ({cal.mode} mode)")
    print("-" * 52)
    print(f"{'measurement':<16}{'value':>10}{'tolerance':>12}")
    for m in g.measurements:
        print(f"{m.name:<16}{m.value_cm:>8.1f}cm{('+/- '+format(m.tolerance_cm,'.1f')+'cm'):>12}")
    for n in g.notes:
        print(f"  note: {n}")

    # (1) buyer gives body measurements
    body = BodyProfile(source="manual",
                       measurements={"chest": 98.0, "shoulder": 46.0, "length": 70.0},
                       fit_preference="regular")
    fit = compute_fit(g, body)
    print("\nFIT vs your body (chest 98cm, regular fit):")
    for z in fit.zones:
        print(f"  {z.zone:<16} ease {z.ease_cm:+.1f}cm -> {z.verdict}")
    print(f"  => {fit.summary}")
    print(f"  recommendation: {fit.size_recommendation}")

    # (2) buyer compares to a garment they own and love
    ref = BodyProfile(source="reference_garment",
                      measurements={"pit_to_pit": 53.0, "shoulder_width": 47.0, "length": 71.0},
                      fit_preference="regular")
    fit2 = compute_fit(g, ref)
    print("\nFIT vs a tee you own and love (pit-to-pit 53cm):")
    for z in fit2.zones:
        print(f"  {z.zone:<16} diff {z.ease_cm:+.1f}cm -> {z.verdict}")
    print(f"  => {fit2.summary}")

    overlay = draw_measurements(cal.rectified, g)
    out = "/home/claude/fittag/demo_overlay.png"
    cv2.imwrite(out, overlay)
    print(f"\nannotated overlay written: {out}")


if __name__ == "__main__":
    main()

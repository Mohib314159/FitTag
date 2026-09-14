"""Approximate size translation from flat measurements.

Honest by design: secondhand sizing is noisy and labels drift, so we return a best-guess
size + a caveat, never a guarantee. Helps buyers who know "I'm a UK 10" but not their cm.
"""

from __future__ import annotations

# Tops: by pit-to-pit (flat half-chest), cm. Rough unisex bands.
_TOP_BANDS = [("XS", 0, 46), ("S", 46, 50), ("M", 50, 54),
              ("L", 54, 58), ("XL", 58, 62), ("XXL", 62, 999)]

# Bottoms: waist circumference (cm) -> UK size (women's, approx).
_UK_WAIST = [(60, 6), (64, 8), (68, 10), (72, 12), (77, 14), (82, 16), (88, 18), (94, 20)]

_BOTTOMS = {"jeans", "trousers", "shorts", "skirt", "pants"}


def _top_label(ptp_cm: float) -> str:
    for label, lo, hi in _TOP_BANDS:
        if lo <= ptp_cm < hi:
            return label
    return "?"


def estimate_size(garment_type: str, measurements: dict) -> dict | None:
    g = garment_type.lower()
    if g in _BOTTOMS:
        w = measurements.get("waist_flat")
        if w is None:
            return None
        circ = w * 2.0
        waist_in = round(circ / 2.54)
        uk = min(_UK_WAIST, key=lambda t: abs(t[0] - circ))[1]
        return {"system": "waist", "label": f'~{waist_in}" waist',
                "caveat": f"≈ UK women's {uk}"}
    ptp = measurements.get("pit_to_pit")
    if ptp is None:
        return None
    return {"system": "alpha", "label": f"~{_top_label(ptp)}",
            "caveat": "vintage often runs small"}

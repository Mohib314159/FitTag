"""Fit engine — honest arithmetic, no model.

Compares a measured garment to a buyer's target and produces a per-zone fit verdict.
Two comparison modes:
  - manual            : buyer gives body circumferences (chest/waist/hip in cm). A flat
                        garment measurement is doubled to a circumference and compared.
  - reference_garment : buyer measured a garment they own and love (same flat metric).
                        We compare flat-to-flat directly — "does it fit like your favourite?"

Thresholds are heuristic and adjustable by fit preference; they are stated, not hidden.
The try-on image (if any) is attached elsewhere and never drives these verdicts.
"""

from __future__ import annotations

from .contracts import GarmentMeasurement, BodyProfile, FitZone, FitReport

# Garment flat measurement -> (body circumference key, is_circumference_doubled)
_TOP_MAP = {
    "pit_to_pit": ("chest", True),
    "shoulder_width": ("shoulder", False),   # shoulder compared flat-to-flat
    "length": ("length", False),
}
_BOTTOM_MAP = {
    "waist_flat": ("waist", True),
    "hip_flat": ("hip", True),
    "inseam": ("inseam", False),
}

# Circumference-ease verdict bands (cm), regular fit. Shifted by preference.
_BANDS = [
    (-1e9, 0.0, "too_tight"),
    (0.0, 6.0, "snug"),
    (6.0, 14.0, "ideal"),
    (14.0, 22.0, "loose"),
    (22.0, 1e9, "oversized"),
]
_PREF_SHIFT = {"fitted": -4.0, "regular": 0.0, "oversized": 6.0}

# Flat-to-flat (reference garment) bands (cm of ease vs the loved garment).
_REF_BANDS = [
    (-1e9, -1.5, "too_tight"),
    (-1.5, 1.5, "ideal"),
    (1.5, 4.0, "loose"),
    (4.0, 1e9, "oversized"),
]


def _verdict(ease_cm: float, bands) -> str:
    for lo, hi, label in bands:
        if lo <= ease_cm < hi:
            return label
    return "ideal"


def compute_fit(g: GarmentMeasurement, body: BodyProfile) -> FitReport:
    is_bottom = g.garment_type.lower() in {"jeans", "trousers", "shorts", "skirt", "pants"}
    mapping = _BOTTOM_MAP if is_bottom else _TOP_MAP
    shift = _PREF_SHIFT.get(body.fit_preference, 0.0)
    zones: list[FitZone] = []

    for flat_name, (body_key, doubled) in mapping.items():
        m = g.get(flat_name)
        if m is None:
            continue
        # reference mode keys by the garment's own flat name; manual keys by body part
        key = flat_name if body.source == "reference_garment" else body_key
        if key not in body.measurements:
            continue
        target = body.measurements[key]

        if body.source == "reference_garment":
            ease = round(m.value_cm - target, 1)
            etol = m.tolerance_cm
            vfun = lambda e: _verdict(e, _REF_BANDS)
        elif doubled:
            ease = round(m.value_cm * 2.0 - target, 1)   # flat -> circumference
            etol = m.tolerance_cm * 2.0                  # tolerance doubles too
            vfun = lambda e: _verdict(e - shift, _BANDS)
        else:
            ease = round(m.value_cm - target, 1)
            etol = m.tolerance_cm
            vfun = lambda e: _verdict(e, _REF_BANDS)

        verdict = vfun(ease)
        lo, hi = vfun(ease - etol), vfun(ease + etol)
        alts = [v for v in (lo, hi) if v != verdict]
        if alts:
            confidence, note = "near boundary", f"likely {verdict.replace('_',' ')}, possibly {alts[0].replace('_',' ')}"
        else:
            confidence, note = "firm", ""
        zones.append(FitZone(zone=flat_name, ease_cm=ease, verdict=verdict,
                             confidence=confidence, note=note))

    summary, size = _summarise(zones, is_bottom, body)
    return FitReport(zones=zones, size_recommendation=size, summary=summary)


def _summarise(zones, is_bottom, body):
    if not zones:
        return ("Not enough overlapping measurements to assess fit.", "unknown")
    key = "waist_flat" if is_bottom else "pit_to_pit"
    primary = next((z for z in zones if z.zone == key), zones[0])
    words = {
        "too_tight": "will be tight",
        "snug": "will fit snugly",
        "ideal": "should fit well",
        "loose": "will be roomy",
        "oversized": "will be oversized",
    }
    label = words.get(primary.verdict, "should fit")
    region = "through the waist" if is_bottom else "in the chest"
    detail = ", ".join(f"{z.zone.replace('_', ' ')}: {z.verdict.replace('_', ' ')}" for z in zones)
    size_map = {"too_tight": "size up", "snug": "true to size (snug)", "ideal": "true to size",
                "loose": "true to size (relaxed)", "oversized": "consider sizing down"}
    return (f"This {label} {region}. ({detail}.)", size_map.get(primary.verdict, "true to size"))

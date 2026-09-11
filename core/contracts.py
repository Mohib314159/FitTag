"""Internal data contract. Everything in the engine produces or consumes these.

The contract is deliberately small and frozen: the measurement engine reads an
image and emits a GarmentMeasurement; fit is a pure function of a GarmentMeasurement
and a BodyProfile. The generative try-on image is an optional decoration on the
FitReport and carries NO fit claim — the fit verdict comes only from measured geometry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

Point = tuple[float, float]


@dataclass
class Measurement:
    """A single garment measurement, always with an error bar.

    `value_cm` is the real-world length. `tolerance_cm` is our honest uncertainty.
    `p1`/`p2` are the landmark pixel coordinates in the *rectified* (metric) image,
    kept so the UI can draw the measurement line back onto the photo.
    """

    name: str
    value_cm: float
    tolerance_cm: float
    p1: Point
    p2: Point


@dataclass
class GarmentMeasurement:
    item_id: str
    garment_type: str                       # from the VLM classifier (semantics only)
    measurements: list[Measurement]
    marker_size_mm: float
    mm_per_px: float                         # scale of the rectified image
    rectification_ok: bool
    notes: list[str] = field(default_factory=list)   # honest flags, e.g. low-confidence landmarks

    def get(self, name: str) -> Optional[Measurement]:
        for m in self.measurements:
            if m.name == name:
                return m
        return None


@dataclass
class BodyProfile:
    """Buyer's target measurements, in cm.

    `source="manual"`  -> typed body measurements (chest/waist/hip circumferences, etc.)
    `source="reference_garment"` -> derived from a garment the buyer already owns and likes,
                                     measured with the same marker (so the numbers are
                                     directly comparable to the listing).
    Circumference conventions (manual): chest/waist/hip are body circumferences in cm.
    """

    source: str                              # "manual" | "reference_garment"
    measurements: dict[str, float]
    fit_preference: str = "regular"          # "fitted" | "regular" | "oversized"


@dataclass
class FitZone:
    zone: str
    ease_cm: float                           # garment - body (circumference where applicable)
    verdict: str                             # too_tight | snug | ideal | loose | oversized
    confidence: str = "firm"                 # "firm" | "near boundary"
    note: str = ""                           # e.g. "likely ideal, possibly snug"


@dataclass
class FitReport:
    zones: list[FitZone]
    size_recommendation: str
    summary: str
    tryon_image_url: Optional[str] = None    # generative VISUAL only — never a fit claim

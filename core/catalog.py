"""Fit-based search over a catalog of measured listings.

The marketplace feature nobody has: "show me items that actually fit me." Every listing
carries FitTag measurements, so we can rank a catalog by how well each item fits a
buyer's profile. Here it's a small in-memory demo catalog; in production it's the
platform's listings.
"""

from __future__ import annotations

from .contracts import GarmentMeasurement, Measurement, BodyProfile
from .fit import compute_fit


def _g(item_id, gtype, m, meta=None):
    ms = [Measurement(k, float(v), 1.0, (0, 0), (0, 0)) for k, v in m.items()]
    g = GarmentMeasurement(item_id=item_id, garment_type=gtype, measurements=ms,
                           marker_size_mm=80.0, mm_per_px=0.5, rectification_ok=True)
    g.meta = meta or {}
    return g


DEMO_CATALOG = [
    _g("tee-cobalt", "t-shirt", {"pit_to_pit": 52, "shoulder_width": 52, "length": 72},
       {"title": "90s cobalt boxy tee", "price": 18}),
    _g("tee-slim", "t-shirt", {"pit_to_pit": 47, "shoulder_width": 46, "length": 66},
       {"title": "Slim ringer tee", "price": 12}),
    _g("tee-xl", "t-shirt", {"pit_to_pit": 60, "shoulder_width": 60, "length": 76},
       {"title": "Oversized skate tee", "price": 22}),
    _g("jeans-501", "jeans", {"waist_flat": 42, "hip_flat": 52, "inseam": 78},
       {"title": "Levi's 501 straight", "price": 45}),
    _g("jeans-slim", "jeans", {"waist_flat": 38, "hip_flat": 48, "inseam": 74},
       {"title": "Slim tapered jean", "price": 30}),
    _g("jeans-baggy", "jeans", {"waist_flat": 48, "hip_flat": 58, "inseam": 80},
       {"title": "Baggy carpenter jean", "price": 38}),
]

_SCORE = {"ideal": 2, "snug": 1, "loose": 1, "too_tight": -3, "oversized": -2}


def search_fit(body: BodyProfile, catalog=None, top: int = 5) -> list[dict]:
    catalog = catalog if catalog is not None else DEMO_CATALOG
    results = []
    for g in catalog:
        rep = compute_fit(g, body)
        if not rep.zones:
            continue
        score = sum(_SCORE.get(z.verdict, 0) for z in rep.zones)
        results.append({
            "item_id": g.item_id, "type": g.garment_type,
            "title": getattr(g, "meta", {}).get("title", g.item_id),
            "price": getattr(g, "meta", {}).get("price"),
            "score": score, "summary": rep.summary,
            "zones": [{"zone": z.zone, "verdict": z.verdict} for z in rep.zones],
        })
    results.sort(key=lambda d: -d["score"])
    return results[:top]

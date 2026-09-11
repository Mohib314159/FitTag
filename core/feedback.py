"""Fit-feedback flywheel — the resale data moat.

Buyers tell us whether an item fit as predicted. Each record (a) nudges the fit
thresholds, and (b) accumulates into a proprietary measurements->real-fit-outcome
dataset across body types — the asset incumbents have for new retail and nobody has for
secondhand. Append-only JSONL so it's trivially durable.
"""

from __future__ import annotations

import json
import os
import time
from collections import Counter

STORE = os.environ.get("FITTAG_FEEDBACK", "feedback.jsonl")
_VALID = {"accurate", "tighter", "looser"}


def record(item_id: str, predicted_verdict: str, outcome: str,
           zone: str = "chest", profile: dict | None = None) -> dict:
    if outcome not in _VALID:
        raise ValueError(f"outcome must be one of {_VALID}")
    rec = {"ts": time.time(), "item_id": item_id, "zone": zone,
           "predicted": predicted_verdict, "outcome": outcome, "profile": profile}
    with open(STORE, "a") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


def load() -> list[dict]:
    if not os.path.exists(STORE):
        return []
    return [json.loads(l) for l in open(STORE) if l.strip()]


def calibration_signal() -> dict:
    """Aggregate outcomes into a suggested band shift (cm). 'tighter' reality => shift the
    verdict bands looser so future predictions match what buyers actually experience."""
    recs = load()
    n = len(recs)
    pairs = Counter((r["predicted"], r["outcome"]) for r in recs)
    bias = sum(c for (_, o), c in pairs.items() if o == "tighter") \
        - sum(c for (_, o), c in pairs.items() if o == "looser")
    shift = round((bias / n) * 2.0, 1) if n else 0.0
    return {"n": n, "suggested_band_shift_cm": shift,
            "pairs": {f"{p}->{o}": c for (p, o), c in pairs.items()}}

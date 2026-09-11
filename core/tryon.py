"""Generative try-on — the VISUAL layer. STRICTLY illustrative.

Renders what a garment looks like on a buyer. It NEVER produces or influences a fit
verdict — fit comes only from measured geometry (core/fit.py). The image is attached to
FitReport.tryon_image_url purely as a visualisation, and is always labelled.

Backends: FASHN.ai (primary, purpose-built) or Gemini image. Both gated on an API key;
without one, returns None and the UI shows the labelled placeholder. Pre-render demo
cases so a live call can never break a demo.
"""

from __future__ import annotations

import os
import time

TRYON_DISCLAIMER = ("Try-on preview is illustrative — it shows the look. "
                    "The fit verdict is measured; that's the part to trust.")


def try_on(buyer_photo_b64: str, garment_photo_b64: str, backend: str = "fashn") -> str | None:
    """Return a URL/data-URI to an illustrative try-on image, or None if unavailable."""
    if backend == "fashn" and os.getenv("FASHN_API_KEY"):
        return _fashn(buyer_photo_b64, garment_photo_b64)
    if backend == "gemini" and os.getenv("GOOGLE_API_KEY"):
        return _gemini(buyer_photo_b64, garment_photo_b64)
    return None


def _fashn(model_b64: str, garment_b64: str) -> str | None:
    try:
        import httpx
        key = os.environ["FASHN_API_KEY"]
        h = {"Authorization": f"Bearer {key}"}
        run = httpx.post("https://api.fashn.ai/v1/run", headers=h, timeout=30, json={
            "model_name": "tryon-v1.6",
            "inputs": {"model_image": f"data:image/jpeg;base64,{model_b64}",
                       "garment_image": f"data:image/jpeg;base64,{garment_b64}"},
        }).json()
        rid = run.get("id")
        if not rid:
            return None
        for _ in range(20):                       # poll up to ~20s
            time.sleep(1)
            st = httpx.get(f"https://api.fashn.ai/v1/status/{rid}", headers=h, timeout=30).json()
            if st.get("status") == "completed":
                out = st.get("output") or []
                return out[0] if out else None
            if st.get("status") in ("failed", "error"):
                return None
        return None
    except Exception:
        return None


def _gemini(model_b64: str, garment_b64: str) -> str | None:
    try:
        import httpx
        key = os.environ["GOOGLE_API_KEY"]
        url = ("https://generativelanguage.googleapis.com/v1beta/models/"
               "gemini-2.5-flash-image:generateContent?key=" + key)
        body = {"contents": [{"parts": [
            {"text": "Place the second garment realistically on the person in the first image. "
                     "Preserve the person's body and pose. Photorealistic."},
            {"inline_data": {"mime_type": "image/jpeg", "data": model_b64}},
            {"inline_data": {"mime_type": "image/jpeg", "data": garment_b64}},
        ]}]}
        r = httpx.post(url, json=body, timeout=60).json()
        for part in r["candidates"][0]["content"]["parts"]:
            if "inline_data" in part:
                return "data:image/png;base64," + part["inline_data"]["data"]
        return None
    except Exception:
        return None

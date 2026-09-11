"""Garment-type classifier. Semantics only — it picks the garment type (which selects
the measurement set); it never produces a measurement.

Resolution order, so it always returns something:
  1. VLM (Anthropic) if ANTHROPIC_API_KEY is set — best semantics.
  2. CLIP zero-shot if open_clip/torch are installed — reuses the Vinted-finder approach,
     runs offline once weights are cached.
  3. Deterministic silhouette heuristic — no model needed: two runs at the hem => bottoms,
     otherwise a top. Guarantees the demo runs anywhere.
"""

from __future__ import annotations

import json
import os

import numpy as np

from .prompts import CLASSIFY_PROMPT, GARMENT_TYPES
from .measure import _runs, _raster


def classify(image_bgr=None, contour=None, prefer: str = "auto") -> tuple[str, str, str]:
    """Return (garment_type, category, source). category in {"top","bottom"}."""
    if prefer in ("auto", "vlm") and os.getenv("ANTHROPIC_API_KEY") and image_bgr is not None:
        out = _classify_vlm(image_bgr)
        if out:
            return (*out, "vlm")
    if prefer in ("auto", "clip") and image_bgr is not None:
        out = _classify_clip(image_bgr)
        if out:
            return (*out, "clip")
    if contour is not None:
        return (*_classify_heuristic(contour), "heuristic")
    return ("t-shirt", "top", "default")


def _category(garment_type: str) -> str:
    return "bottom" if garment_type in {"jeans", "trousers", "shorts", "skirt"} else "top"


def _classify_heuristic(contour) -> tuple[str, str]:
    """Deterministic: legs (two runs at the hem) => bottoms; else a top.
    Uses the aspect ratio to disambiguate trousers vs shorts/top."""
    mask, x0, y0, w, h = _raster(contour)
    ymax = y0 + h
    # look for two separate legs across the bottom 15%, not just the last row: with a
    # slight tilt one hem ends a few rows above the other and the last row shows one leg
    rows = [int(ymax - f * h) for f in (0.02, 0.05, 0.08, 0.11, 0.14)]
    min_leg = 0.04 * h
    two_legs = sum(sum((b - a) >= min_leg for a, b in _runs(mask[max(y0, r)])) >= 2 for r in rows)
    if two_legs >= 3:
        gtype = "jeans" if h > 1.2 * w else "shorts"
        return gtype, "bottom"
    # single blob -> top; very tall single blob could be a dress
    gtype = "dress" if h > 1.6 * w else "t-shirt"
    return gtype, _category(gtype)


def _classify_vlm(image_bgr) -> tuple[str, str] | None:
    try:
        import base64
        import cv2
        import anthropic
        ok, buf = cv2.imencode(".jpg", image_bgr)
        if not ok:
            return None
        b64 = base64.b64encode(buf).decode()
        client = anthropic.Anthropic()
        msg = client.messages.create(
            model="claude-sonnet-4-6", max_tokens=80,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64",
                 "media_type": "image/jpeg", "data": b64}},
                {"type": "text", "text": CLASSIFY_PROMPT},
            ]}],
        )
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        data = json.loads(text[text.find("{"): text.rfind("}") + 1])
        gt = data.get("garment_type", "t-shirt")
        gt = gt if gt in GARMENT_TYPES else "t-shirt"
        return gt, data.get("category", _category(gt))
    except Exception:
        return None


def _classify_clip(image_bgr) -> tuple[str, str] | None:
    """Zero-shot CLIP over the garment labels (reuses the Vinted-finder CLIP idea)."""
    try:
        import cv2
        import torch
        import open_clip
        from PIL import Image

        model, _, preprocess = open_clip.create_model_and_transforms(
            "ViT-B-32", pretrained="laion2b_s34b_b79k")
        tokenizer = open_clip.get_tokenizer("ViT-B-32")
        img = Image.fromarray(cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB))
        prompts = [f"a photo of a {t} laid flat" for t in GARMENT_TYPES]
        with torch.no_grad():
            im = preprocess(img).unsqueeze(0)
            txt = tokenizer(prompts)
            im_f = model.encode_image(im); im_f /= im_f.norm(dim=-1, keepdim=True)
            tx_f = model.encode_text(txt); tx_f /= tx_f.norm(dim=-1, keepdim=True)
            sims = (im_f @ tx_f.T).softmax(dim=-1)[0]
        gt = GARMENT_TYPES[int(sims.argmax())]
        return gt, _category(gt)
    except Exception:
        return None

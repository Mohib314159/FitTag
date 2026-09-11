"""FitTag API — exposes the full engine and serves the front end as one app.

Run:
    uvicorn api.server:app --reload      # from the repo root; open http://127.0.0.1:8000

Endpoints
    GET  /health                 liveness
    POST /measure (multipart)    photo -> measured garment + overlay + size estimate
    POST /measure-reference      same, for "a garment you own" (used as the fit target)
    POST /fit (json)             garment + body/reference -> per-zone fit (with confidence)
    POST /guidance (multipart)   photo -> capture quality guidance
    POST /search-fit (json)      body profile -> catalog items ranked by how well they fit
    POST /feedback (json)        record a real fit outcome (the feedback flywheel)
    POST /tryon (multipart)      buyer + garment photo -> illustrative try-on (gated on key)
    GET  /overlays/{name}        annotated rectified image
    GET  /                       front end
"""

from __future__ import annotations

import base64
import sys
import tempfile
import uuid
from pathlib import Path

import cv2
import numpy as np
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.calibrate import calibrate, capture_guidance
from core.segment import segment_auto, largest_contour, touches_border, contrast, contrast_check
from core.classify import classify
from core.measure import measure
from core.fit import compute_fit
from core.sizing import estimate_size
from core.catalog import search_fit
from core import feedback as fb
from core.tryon import try_on, TRYON_DISCLAIMER
from core.contracts import GarmentMeasurement, Measurement, BodyProfile
from viz.overlay import draw_measurements

WEB = Path(__file__).resolve().parent.parent / "web"
OVERLAYS = Path(tempfile.mkdtemp(prefix="fittag_overlays_"))
MM_PER_PX = 0.5

app = FastAPI(title="FitTag")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def _measurement_dict(m): return {"name": m.name, "value_cm": round(float(m.value_cm), 1),
                                  "tolerance_cm": round(float(m.tolerance_cm), 1)}
def _garment_dict(g): return {"item_id": g.item_id, "garment_type": g.garment_type,
                              "measurements": [_measurement_dict(m) for m in g.measurements],
                              "mm_per_px": g.mm_per_px, "notes": g.notes}
def _fit_dict(r): return {"zones": [{"zone": z.zone, "ease_cm": round(float(z.ease_cm), 1),
                                     "verdict": z.verdict, "confidence": z.confidence, "note": z.note}
                                    for z in r.zones],
                          "size_recommendation": r.size_recommendation, "summary": r.summary}


async def _decode(file: UploadFile):
    raw = await file.read()
    return cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR), raw


def _run_measure(img, item_prefix="item", garment_type: str | None = None):
    cal = calibrate(img, mm_per_px_out=MM_PER_PX)
    if not cal.ok:
        return {"ok": False, "error": "No calibration markers found. Lay the garment on the "
                "FitTag mat and shoot from roughly above, then try again."}
    mask = segment_auto(cal.rectified, marker_size_mm=cal.marker_size_mm, mm_per_px=cal.mm_per_px)
    contour = largest_contour(mask)
    if contour is None:
        return {"ok": False, "error": "Couldn't separate the garment from the background."}
    filled = np.zeros_like(mask)
    cv2.drawContours(filled, [contour], -1, 255, cv2.FILLED)
    status, msg = contrast_check(contrast(cal.rectified, filled))
    if status == "refuse":
        return {"ok": False, "error": msg}
    if garment_type in ("jeans", "t-shirt"):          # the user said what it is: trust them
        gtype, category, src = garment_type, ("bottom" if garment_type == "jeans" else "top"), "user"
    else:
        gtype, category, src = classify(image_bgr=cal.rectified, contour=contour)
    measurements = measure(contour, gtype, cal.mm_per_px, tol_scale=cal.tol_scale)
    notes = [f"calibration {cal.mode} ({cal.n_markers} markers)", f"type via {src}"]
    if status == "warn":
        notes.append(msg)
    if touches_border(contour, cal.rectified.shape):
        notes.append("garment touches mat edge — use a larger mat")
    g = GarmentMeasurement(item_id=f"{item_prefix}-{uuid.uuid4().hex[:6]}", garment_type=gtype,
                           measurements=measurements, marker_size_mm=cal.marker_size_mm,
                           mm_per_px=cal.mm_per_px, rectification_ok=True, notes=notes)
    overlay = draw_measurements(cal.rectified, g)
    h, w = overlay.shape[:2]
    if w > 820:
        overlay = cv2.resize(overlay, (820, int(h * 820 / w)), interpolation=cv2.INTER_AREA)
    oid = uuid.uuid4().hex[:12] + ".png"
    cv2.imwrite(str(OVERLAYS / oid), overlay)
    size = estimate_size(gtype, {m.name: m.value_cm for m in measurements})
    return {"ok": True, "category": category, "garment": _garment_dict(g),
            "overlay_url": f"/overlays/{oid}", "size": size}


@app.get("/health")
def health(): return {"ok": True, "service": "fittag"}


@app.post("/measure")
async def measure_ep(file: UploadFile = File(...), garment_type: str | None = Form(None)):
    img, _ = await _decode(file)
    if img is None: return JSONResponse({"ok": False, "error": "Unreadable image."}, 400)
    return _run_measure(img, "listing", garment_type)


@app.post("/measure-reference")
async def measure_ref_ep(file: UploadFile = File(...)):
    img, _ = await _decode(file)
    if img is None: return JSONResponse({"ok": False, "error": "Unreadable image."}, 400)
    return _run_measure(img, "owned")


@app.post("/guidance")
async def guidance_ep(file: UploadFile = File(...)):
    img, _ = await _decode(file)
    if img is None: return JSONResponse({"ok": False, "error": "Unreadable image."}, 400)
    return capture_guidance(img)


class FitRequest(BaseModel):
    garment_type: str
    garment: dict
    source: str = "manual"
    measurements: dict
    fit_preference: str = "regular"


def _profile_from(req) -> tuple[GarmentMeasurement, BodyProfile]:
    ms = [Measurement(n, float(v), 1.0, (0, 0), (0, 0)) for n, v in req.garment.items()]
    g = GarmentMeasurement("fit", req.garment_type, ms, 80.0, MM_PER_PX, True)
    body = BodyProfile(source=req.source, measurements={k: float(v) for k, v in req.measurements.items()},
                       fit_preference=req.fit_preference)
    return g, body


@app.post("/fit")
def fit_ep(req: FitRequest):
    g, body = _profile_from(req)
    return _fit_dict(compute_fit(g, body))


class SearchRequest(BaseModel):
    source: str = "manual"
    measurements: dict
    fit_preference: str = "regular"
    top: int = 6


@app.post("/search-fit")
def search_ep(req: SearchRequest):
    body = BodyProfile(source=req.source, measurements={k: float(v) for k, v in req.measurements.items()},
                       fit_preference=req.fit_preference)
    return {"results": search_fit(body, top=req.top)}


class FeedbackRequest(BaseModel):
    item_id: str
    predicted: str
    outcome: str            # accurate | tighter | looser
    zone: str = "chest"
    profile: dict | None = None


@app.post("/feedback")
def feedback_ep(req: FeedbackRequest):
    try:
        fb.record(req.item_id, req.predicted, req.outcome, req.zone, req.profile)
    except ValueError as e:
        return JSONResponse({"ok": False, "error": str(e)}, 400)
    return {"ok": True, "signal": fb.calibration_signal()}


@app.post("/tryon")
async def tryon_ep(buyer_photo: UploadFile = File(...), garment_photo: UploadFile = File(...)):
    _, braw = await _decode(buyer_photo)
    _, graw = await _decode(garment_photo)
    url = try_on(base64.b64encode(braw).decode(), base64.b64encode(graw).decode())
    return {"ok": True, "image_url": url, "disclaimer": TRYON_DISCLAIMER,
            "live": url is not None}


@app.get("/overlays/{name}")
def overlay_ep(name: str):
    p = OVERLAYS / name
    return FileResponse(p, media_type="image/png") if p.exists() else JSONResponse({"error": "not found"}, 404)


@app.get("/sample-{which}.png")
def sample_ep(which: str):
    p = WEB / f"sample-{which}.png"
    return FileResponse(p, media_type="image/png") if p.exists() else JSONResponse({"error": "no sample"}, 404)


@app.get("/", response_class=HTMLResponse)
def index_ep(): return (WEB / "index.html").read_text()

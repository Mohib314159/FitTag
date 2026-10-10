"""FitTag API â€” exposes the full engine and serves the front end as one app.

Run:
    uvicorn api.server:app --reload      # from the repo root; open http://127.0.0.1:8000

Endpoints
    GET  /health                 liveness
    POST /measure (multipart)    photo -> measured garment + overlay + calibration uncertainty
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
import asyncio
import io
import time
from PIL import Image, ImageOps, UnidentifiedImageError
from pathlib import Path

import cv2
import numpy as np
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.calibrate import capture_guidance
from core.segment import largest_contour, touches_border, contrast, contrast_check
from core.measure import measure
from core.fit import compute_fit
from core.catalog import search_fit
from core import feedback as fb
from core.tryon import try_on, TRYON_DISCLAIMER
from core.contracts import GarmentMeasurement, Measurement, BodyProfile

WEB = Path(__file__).resolve().parent.parent / "web"
OVERLAYS = Path(tempfile.mkdtemp(prefix="fittag_overlays_"))
MM_PER_PX = 0.5

app = FastAPI(title="FitTag")
cv2.setNumThreads(1)
from api.capacity import ComputeGate, bounded_env
MEASURE_LOCK = ComputeGate(bounded_env('FITTAG_PARALLEL_PHOTOS', 1, 2))
Image.MAX_IMAGE_PIXELS = 25_000_000


@app.middleware("http")
async def private_responses(request, call_next):
    length = request.headers.get("content-length", "0")
    if length.isdigit() and int(length) > 13 * 1024 * 1024:
        return JSONResponse({"ok": False, "error": "Choose an image smaller than 12 MB."}, 413)
    response = await call_next(request)
    if request.url.path.startswith(("/measure", "/measurement-jobs", "/overlays", "/guidance", "/experiment")):
        response.headers["Cache-Control"] = "no-store"
    if request.url.path in ("/", "/index.html", "/sw.js", "/app.js", "/app.css", "/client.mjs", "/manifest.webmanifest", "/free.js", "/free.mjs", "/free.css", "/request.mjs", "/batch.mjs", "/photo-check.mjs"):
        response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def _measurement_dict(m): return {"name": m.name, "value_cm": round(float(m.value_cm), 1),
                                  "tolerance_cm": round(float(m.tolerance_cm), 1),
                                  "p1": [float(v) for v in m.p1], "p2": [float(v) for v in m.p2]}
def _garment_dict(g): return {"item_id": g.item_id, "garment_type": g.garment_type,
                              "measurements": [_measurement_dict(m) for m in g.measurements],
                              "mm_per_px": g.mm_per_px, "notes": g.notes}
def _fit_dict(r): return {"zones": [{"zone": z.zone, "ease_cm": round(float(z.ease_cm), 1),
                                     "verdict": z.verdict, "confidence": z.confidence, "note": z.note}
                                    for z in r.zones],
                          "size_recommendation": r.size_recommendation, "summary": r.summary}


async def _decode(file: UploadFile):
    raw = await file.read(12 * 1024 * 1024 + 1)
    if len(raw) > 12 * 1024 * 1024:
        raise HTTPException(413, "Choose an image smaller than 12 MB.")
    return await run_in_threadpool(_decode_image, raw), raw


def _decode_image(raw):
    try:
        with Image.open(io.BytesIO(raw)) as source:
            if source.width * source.height > Image.MAX_IMAGE_PIXELS:
                raise HTTPException(413, "Choose an image under 25 megapixels.")
            source = ImageOps.exif_transpose(source).convert("RGB")
            source.thumbnail((1800, 1800))
            img = cv2.cvtColor(np.asarray(source), cv2.COLOR_RGB2BGR)
        return img
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise HTTPException(400, "Unreadable image. Choose a JPEG, PNG or WebP photo; export HEIC as JPEG.")


@app.get("/health")
def health(): return {"ok": True, "service": "fittag"}


@app.post("/measure")
async def measure_ep(file: UploadFile = File(...), garment_type: str = Form("jeans"),
                     reference: str = Form("hardware"), diameter_mm: float = Form(17.0),
                     known_diameter: bool = Form(False)):
    if reference not in ("hardware", "a4", "a5", "card", "mat") or garment_type not in ("jeans", "t-shirt"):
        raise HTTPException(422, "Choose a supported garment and reference.")
    if not np.isfinite(diameter_mm) or not 10 <= diameter_mm <= 30:
        raise HTTPException(422, "Button diameter must be between 10 and 30 mm.")
    if MEASURE_LOCK.locked():
        return JSONResponse({"ok": False, "error": "Another photo is processing. Try again in a moment."}, 429,
                            headers={"Retry-After": "5"})
    async with MEASURE_LOCK:
        img, _ = await _decode(file)
        return await run_in_threadpool(_phone_measure, img, reference, garment_type, diameter_mm, known_diameter)


def _phone_measure(img, reference, garment_type, diameter_mm, known_diameter):
    from core.phone import hardware_measure
    from measure import flatten, analyse
    try:
        if reference == "hardware":
            if garment_type != "jeans":
                raise ValueError("Hardware scale is for jeans with a tack button. Choose a known paper reference for tops.")
            rect, rows, scale, notes = hardware_measure(img, diameter_mm, known_diameter)
        else:
            cal = flatten(img, reference, mm_per_px_out=1.0)
            mask, rect, _ = analyse(img, cal)
            cnt = largest_contour(mask)
            if cnt is None or touches_border(cnt, rect.shape):
                raise ValueError("The garment is missing or cropped. Include every edge and retake.")
            status, message = contrast_check(contrast(rect, mask))
            if status == "refuse":
                raise ValueError(message)
            scale = cal.mm_per_px
            rows = measure(cnt, garment_type, scale, cal.tol_scale)
            notes = [f"Perspective corrected with {reference}. Check every overlay line; reference detection can be wrong."]
            if status == "warn":
                notes.append(message)
        if not rows:
            raise ValueError("No usable measurements. Retake with the whole garment visible.")
        g = GarmentMeasurement(uuid.uuid4().hex, garment_type, rows, 0, scale,
                               reference != "hardware", notes)
        from api.overlay_store import persist_image
        output = persist_image(rect)
        return {"ok": True, "garment": _garment_dict(g), **output, "reference": reference,
                "confidence": "estimate" if reference == "hardware" else "check-overlay"}
    except (ValueError, SystemExit) as error:
        return {"ok": False, "error": str(error)}
    except cv2.error:
        return {"ok": False, "error": "Couldn't analyse this image. Retake with a plain background and the entire garment in view."}


@app.post("/measure-reference")
async def measure_ref_ep(file: UploadFile = File(...)):
    return await measure_ep(file, "jeans", "hardware", 17.0, False)


@app.get("/experiment")
def experiment_status():
    from core.depth_model import available
    return {"button_free":True,"depth_model":available(),"experimental":True,
            "parallel_photos":MEASURE_LOCK.limit}


@app.post("/measure-free")
async def measure_free_ep(file: UploadFile = File(...), garment_type: str = Form("jeans"),
                          fov_deg: float = Form(0), second: UploadFile | None = File(None),
                          estimate: bool = Form(True), camera_height_cm: float = Form(0)):
    if garment_type not in ("jeans","t-shirt") or not np.isfinite(fov_deg) or (fov_deg != 0 and not 40 <= fov_deg <= 110):
        raise HTTPException(422,"Choose a supported garment and a camera field of view between 40 and 110 degrees.")
    if not np.isfinite(camera_height_cm) or (camera_height_cm != 0 and not 35 <= camera_height_cm <= 350):
        raise HTTPException(422,"Camera height must be a known lens-to-floor distance between 35 and 350 cm.")
    if MEASURE_LOCK.locked():
        return JSONResponse({"ok":False,"error":"Another photo is processing. Try again shortly."},429,headers={"Retry-After":"5"})
    async with MEASURE_LOCK:
        photo,raw=await _decode(file)
        other,other_raw=await _decode(second) if second is not None else (None,None)
        def work():
            from api.free_capture import process,persist
            try:
                if other_raw is not None and other_raw == raw:
                    raise ValueError("The second photo is identical. Take a fresh overhead photo from a slightly different height.")
                rect,result=process(photo,raw,garment_type,fov_deg,other,other_raw,estimate,camera_height_cm)
                return persist(rect,result)
            except ValueError as error:
                return {"ok":False,"error":str(error)}
            except Exception:
                # Model failures must not masquerade as measurements or leak paths.
                return {"ok":False,"error":"The experiment could not finish this image. Try a smaller JPEG on a plain floor."}
        return await run_in_threadpool(work)


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
    if not name.endswith(".png") or not name[:-4].isalnum():
        return JSONResponse({"error": "not found"}, 404)
    p = OVERLAYS / name
    return FileResponse(p, media_type="image/png") if p.exists() and time.time() - p.stat().st_mtime < 3600 else JSONResponse({"error": "not found"}, 404)


@app.get("/sample-{which}.png")
def sample_ep(which: str):
    p = WEB / f"sample-{which}.png"
    return FileResponse(p, media_type="image/png") if p.exists() else JSONResponse({"error": "no sample"}, 404)


@app.get("/", response_class=HTMLResponse)
def index_ep(): return (WEB / "index.html").read_text(encoding="utf-8")


from api.jobs import router as jobs_router
app.include_router(jobs_router)
app.mount("/", StaticFiles(directory=WEB, html=True), name="pwa")

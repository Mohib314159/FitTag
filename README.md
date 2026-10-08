# FitTag

A phone-first, installable garment-measurement PWA. Take or choose an ordinary flat-lay photo, check the detected reference and measurement lines, and read centimetres or inches with explicit uncertainty. The intended jeans flow uses the garment’s tack button as a scale reference; no printed mat is required.

**Hardware scale is experimental.** A common tack button is assumed to be 17 mm unless you enter a measured diameter. Buttons vary. The current phone route requires a clear, near-overhead photo and uses the existing button detector, edge refinement, silhouette separation, waistband alignment and landmark geometry. It returns conservative estimates and refuses missing buttons, excessive apparent tilt, cropped garments and inseparable legs. One circular reference cannot recover a full plane homography; the stitch-based scale-field research in `core/markerless.py` is preserved but is not claimed as validated production rectification.

## Run locally

```sh
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements-render.txt
uvicorn api.server:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. Choose **Try an example** for a quick, explicitly labelled synthetic demonstration; choose a photo to exercise the backend. No account, API key or downloaded vision model is needed. The static [GitHub Pages version](https://mohib314159.github.io/FitTag/) shows the app shell and synthetic example; measuring uploads requires the Python service. See [Render deployment](DEPLOYMENT.md) for the full app.

## Phone flow

1. Lay jeans flat on a contrasting plain surface, waistband at the top and both legs separated. Keep the button sharp and the camera parallel to the floor.
2. Take a photo with the phone camera or choose an existing JPEG, PNG or WebP. HEIC needs a JPEG export. Upload happens only after **Measure this garment**.
3. Check the detected button and measurement lines. Tap a result row to highlight its line. Numbers stay provisional until you confirm the overlay.
4. Switch units, compare flat waist with a favourite pair, or save measurements on this device. Photos are not saved locally. Differences within the scale uncertainty do not produce a confident fit claim.

The install control explains Safari/Android installation and uses the native install prompt when available. The offline shell, capture guide and synthetic example work after the first online visit. New measurements require connectivity. The service worker explicitly excludes API responses and personal overlays from its cache.

## Calibration fallbacks

**Reference & garment options** progressively exposes blank A4/A5 paper, experimental card mode and the printed ArUco mat. Tops require a known reference. These routes reuse the existing perspective homography and silhouette engine. The reference must lie flat in the same plane, with every corner visible. Small card references and automatic framing can fail: inspect the result and retake rather than trusting a number.

The old printed mat remains useful for controlled development and validation. `python make_mat.py` generates its four A4 sheets and placement guide. The sheets are taped to form a 1000 × 1400 mm rectangle; print at 100% and check the scale bar. This is a fallback/development path, rather than the main phone onboarding.

## What the evidence supports

The earlier build log reports **17.0 mm tack-button recovery** as an independent cross-check of A5-paper calibration on a real garment. This is a reported historical result; the stored evidence does not independently reproduce that recovery or establish every button’s size.

Two independent real-garment photo result records show absolute differences of **0.1–2.7 cm across seven landmarks**, with a median difference of **1.1 cm**. Those were A5-paper captures. The earlier “all agree to 0.8 cm” statement is not supported by the checked-in numbers. Repeatability is not tape-measured accuracy, and neither result is a hardware-only accuracy guarantee. `docs/data/real.json` preserves only differences and provenance, with personal dimensions and tagged sizes omitted. Public personal-garment photos and sample rows have been removed from the current tree; prior Git history is unchanged.

The synthetic suites below check the existing marker-calibrated geometry against known dimensions. New phone tests check the capture contract, hardware refusal and uncertainty handling, overlays, upload limits and installable assets. A successful synthetic test is not a real-world accuracy claim.

## Architecture

- `core/markerless.py`: button/stitch/rivet priors, edge refinement, experimental scale fields.
- `core/phone.py`: conservative phone orchestration using those helpers and existing flat-lay geometry.
- `core/calibrate.py`, `core/flatlay.py`, `core/measure.py`: reference rectification, colour segmentation, alignment and landmark measurements.
- `api/server.py`: FastAPI measurement routes plus same-origin PWA assets; one measurement at a time.
- `web/`: maintained PWA source. Native file capture, accessible controls, processing/retry states, interactive line overlay, local measurement saving, manifest and offline shell.
- `tools/build_pwa.py`: rebuilds synthetic demo assets and copies the app into `docs/` for Pages. `tools/build_page.py` remains a compatibility entry point.
- `core/fit.py`, catalog, feedback and illustrative try-on: preserved engine capabilities; the focused phone UI uses a conservative local flat-width comparison.

Uploads are limited to 12 MB and 25 megapixels and resized to 1800 pixels on the long edge before analysis. Annotated/processed photo outputs have random URLs, expire after an hour, are capped at 40 files and are never service-worker cached. The server needs temporary disk storage; it does not persist uploaded originals. See deployment notes for limits and verification.

## Tests and asset build

```sh
pip install pytest
python -m tests.test_measure
python -m tests.test_jeans
python -m pytest tests/test_phone_api.py
node --test tests/client.test.mjs
node --test tests/service_worker.test.mjs
python -m tools.build_pwa
```

The source-of-truth UI is `web/`; do not edit generated `docs/index.html` or the old `web_src/app.html` placeholder.

Started at the Fleek × a16z hackathon. The original fiducial calibration approach and JeansFinder ingestion/classifier adapters remain in the engine. MIT licensed (see LICENSE).

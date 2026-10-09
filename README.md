# FitTag Lab — button-free PWA experiment

This branch explores ordinary garment photos with **no button, paper, card or reference object**. It is isolated from the working hardware product on `main`; nothing has been merged.

Open the app → photograph a flat garment → inspect its outline → question the proposed scale. Choose learned metric depth, proportions only, or a known camera height. An optional second photo checks scale consistency. A known length of the garment can anchor or correct scale without placing a reference object in the image.

**The model's unanchored scale is not reliable enough for a fit verdict.** The app makes that failure explicit. Its actual-model simulated example includes the known ground truth, which disagrees substantially with the model. Read [the experiment, measured results and limitations](BUTTON_FREE.md), [user-facing design study](DESIGN.md) and [CV evidence boundaries](CV_EVIDENCE.md).

The PWA supports phone capture/upload and review, processing/cancel, interactive line overlays with drag/keyboard endpoint correction and a magnifier, cm/in or ratios, known-length correction/undo, error and confidence states, explicit acknowledgment before named local saving, copyable listing text, installation and an offline shell/example. Photos are not saved as originals; no photo is sent to an external ML provider. Personal sizes/photos are not included. The prior hardware/reference UI is preserved at `/button.html`.

## Run locally

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-render.txt
.venv\Scripts\python -m tools.download_depth_model
$env:FITTAG_DEPTH_MODEL = (Resolve-Path models/metric-small.onnx).Path
.venv\Scripts\python -m uvicorn api.server:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. Without configured weights, the app still returns proportions and explicitly withholds model centimetres. The distance route does not load the model.

## Test

```sh
python -m tests.test_measure
python -m tests.test_jeans
python -m pytest tests/test_phone_api.py tests/test_free_capture.py -q
npm ci
npm test
python -m tools.probe_button_free
python -m tools.build_pwa
```

The probe needs `FITTAG_DEPTH_MODEL` and uses synthetic data only. Build tools reproduce the static `docs/` preview from the app; GitHub Pages does not process uploads. Node dependencies are for tests only and are not installed in the serving container.

## Isolated Render preview

Select **this experimental branch**, not `main`, in a new Render Blueprint using the root `render.yaml`. Its service is named `fittag-lab`; Docker bundles verified model weights during build. There are no runtime model downloads or API secrets. This branch is ready for a preview, but Linux Docker/Render and physical-device installation are not verified. [Deployment details](DEPLOYMENT.md).

## Existing engine and evidence

The experiment reuses FastAPI, `core.flatlay` segmentation and `core.measure` landmark geometry. `core.free_capture` fits and checks the floor projection; `core.depth_model` runs the pinned CPU model. Older calibration modes (hardware, A4/A5, card and ArUco development mat) remain available through the existing `/measure` API and `/button.html`.

Historical 17.0 mm button recovery was a reported paper-calibration cross-check, not proof of a universal button size. Two independent real-garment paper-reference photos showed landmark agreement of 0.1–2.7 cm. Those are earlier evidence, not validation of reference-free model scale. No personal garment dimensions are published here.

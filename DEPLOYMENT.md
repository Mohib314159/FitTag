# FitTag experimental preview on Render

**Live preview:** [fittag-lab.onrender.com](https://fittag-lab.onrender.com/). Created 10 October 2026 from `codex/fittag-button-free`, as a separate free Docker service managed by the `fittag-button-free` Blueprint. The existing main-branch service is unchanged.

On iPhone, open that URL in Safari and choose Share → Add to Home Screen (Open as Web App if shown). Physical-device capture and OS installation have not yet been verified. New measurements need internet; button-free centimetre estimates remain experimental.

Keep the production hardware service on `main`. For this experiment, create a **separate** Render Blueprint and select `codex/fittag-button-free`, with `render.yaml` at the root. The service name is `fittag-lab`. Do not connect this branch to the existing production Blueprint or merge it into `main` yet.

One Docker service serves FastAPI and the PWA. Docker installs the headless measurement dependencies and ONNX Runtime, then downloads a pinned 99.8 MB metric-depth model and checks its SHA-256. A model-download failure fails the build rather than silently shipping fake scale. The model is read-only in the image; no user-upload-triggered model download or external inference call occurs. No API key, database or paid inference provider is required.

The Blueprint requests the free plan. Confirm current availability/costs in Render. It uses one worker, one model/OpenCV thread and a shared measurement lock. The phone client submits an ephemeral background job, polls real stages and receives a recoverable 429 response when the instance is busy. Completed jobs expire after ten minutes and the registry is capped at twenty. See [SYSTEM_DESIGN.md](SYSTEM_DESIGN.md) for cancellation, retention and restart limits. The service listens on `$PORT` and reports `/health`; `/experiment` reports whether a local model file is configured. It does not imply accuracy or a successful model load.

New uploads are reviewed before transmission. Each image is limited to 12 MB / 25 megapixels, resized to 1800 pixels, and EXIF orientation is corrected. The client caps the combined two-photo upload at 12 MB; the server also caps aggregate request size. Only the numeric focal-length field is inspected for camera calibration; GPS, serial numbers and full metadata are not stored or returned. Annotated outputs are bounded to 40 files and expire after one hour. Original uploads are not persisted.

Local Windows live uploads succeeded in all three modes; measured server resident memory was 205.7 MB and peak working set 289.1 MB. This does **not** verify Linux/container memory or free Render response times. Monitor representative phone photos before relying on the preview. A sleeping instance and first model load can delay the first request; admission reports readiness and the client preserves the selected photo on timeout. Cancelling also marks the job cancelled; an admitted native computation may finish while its slot stays occupied.

```sh
docker build -t fittag-lab .
docker run --rm -p 8000:10000 fittag-lab
```

Docker is not available on the local Windows host. Render successfully built and started the Linux Docker image, verified the pinned model download, and served a real model-backed photo result. See [validation/render_smoke.json](validation/render_smoke.json) and [VERIFICATION.md](VERIFICATION.md). The commands above have not been exercised with a local Docker installation.

After a preview build succeeds, check `/health`, `/experiment`, capture/upload in every mode, the public example and walkthrough, two-photo disagreement, scale correction/undo, saved readouts, Safari/Android installation and offline shell/example behavior. The checked-in `docs/` site is static and cannot run Python or ML uploads. Do not present the preview as validated centimetre measurement or deploy it over the working hardware app.

Official references: [Render Docker](https://render.com/docs/docker), [Blueprint specification](https://render.com/docs/blueprint-spec), [free-service limits](https://render.com/docs/free).


For a service with spare CPU/RAM, set `FITTAG_DEPTH_THREADS=2` or `4` and `FITTAG_PARALLEL_PHOTOS=2`, keeping one Uvicorn worker. The browser selection follows the advertised capacity. These are opt-in settings: the free Blueprint explicitly remains at one thread/one photo. Local parallel tests do not verify Render memory headroom or production latency. Original uploads retain camera metadata for calibration; preview thumbnails stay on-device.

Live check: health/configuration/manifest and every shell asset returned 200. The public generated original completed as a background job with five editable depth-mode measurements; its result image returned `Cache-Control: no-store`. Known-size correction worked in the browser. One test reported 14.69 seconds of server processing, including the measurement path; this is not a latency promise or a real-garment accuracy result. Free-service wake-up delay still applies.

# FitTag on Render

**Main app:** [fittag.onrender.com](https://fittag.onrender.com/), served by the existing free Docker service `fittag` from `main`. The owner authorized merging and deploying the button-free PWA on 10 October 2026. Root `render.yaml` keeps the existing service name and free plan.

The separate [preview](https://fittag-lab.onrender.com/) was created on 10 October 2026 from `codex/fittag-button-free`, managed by the `fittag-button-free` Blueprint. That branch keeps its preview configuration; merging into `main` does not change its service.

On iPhone, open that URL in Safari and choose Share → Add to Home Screen (Open as Web App if shown). Physical-device capture and OS installation have not yet been verified. New measurements need internet; button-free centimetre estimates remain experimental.

The existing main Blueprint selects `main` and the root `render.yaml`; automatic deployment follows pushes. New installations can select the same branch and file. The earlier instruction to keep this experiment unmerged was superseded by the owner's explicit merge/deploy request. The hardware/reference UI and API are retained at `/button.html` and `/measure`.

One Docker service serves FastAPI and the PWA. Docker installs the headless measurement dependencies and ONNX Runtime, then downloads a pinned 99.8 MB metric-depth model and checks its SHA-256. A model-download failure fails the build rather than silently shipping fake scale. The model is read-only in the image; no user-upload-triggered model download or external inference call occurs. No API key, database or paid inference provider is required.

The Blueprint requests the free plan. Confirm current availability/costs in Render. It uses one worker, one model/OpenCV thread and a shared measurement lock. The phone client submits an ephemeral background job, polls real stages and receives a recoverable 429 response when the instance is busy. Completed jobs expire after ten minutes and the registry is capped at twenty. See [SYSTEM_DESIGN.md](SYSTEM_DESIGN.md) for cancellation, retention and restart limits. The service listens on `$PORT` and reports `/health`; `/experiment` reports whether a local model file is configured. It does not imply accuracy or a successful model load.

New uploads are reviewed before transmission. Each image is limited to 12 MB / 25 megapixels, resized to 1800 pixels, and EXIF orientation is corrected. The client caps the combined two-photo upload at 12 MB; the server also caps aggregate request size. Only the numeric focal-length field is inspected for camera calibration; GPS, serial numbers and full metadata are not stored or returned. Annotated outputs are bounded to 40 files and expire after one hour. Original uploads are not persisted.

Local Windows live uploads succeeded in all three modes; measured server resident memory was 205.7 MB and peak working set 289.1 MB. This does **not** verify Linux/container memory or free Render response times. Monitor representative phone photos before relying on the preview. A sleeping instance and first model load can delay the first request; admission reports readiness and the client preserves the selected photo on timeout. Cancelling also marks the job cancelled; an admitted native computation may finish while its slot stays occupied.

```sh
docker build -t fittag-lab .
docker run --rm -p 8000:10000 fittag-lab
```

Docker is not available on the local Windows host. Render successfully built and started the Linux Docker image, verified the pinned model download, and served a real model-backed photo result. See [validation/render_smoke.json](validation/render_smoke.json) and [VERIFICATION.md](VERIFICATION.md). The commands above have not been exercised with a local Docker installation.

After deployment, check `/health`, `/experiment`, capture/upload in every mode, the public example and walkthrough, two-photo disagreement, scale correction/undo, saved readouts, Safari/Android installation and offline shell/example behavior. The checked-in `docs/` site is static and cannot run Python or ML uploads. Publishing on `main` does not validate the model's centimetre estimates: keep the experimental warnings and check sizes with a tape.

Official references: [Render Docker](https://render.com/docs/docker), [Blueprint specification](https://render.com/docs/blueprint-spec), [free-service limits](https://render.com/docs/free).


For a service with spare CPU/RAM, set `FITTAG_DEPTH_THREADS=2` or `4` and `FITTAG_PARALLEL_PHOTOS=2`, keeping one Uvicorn worker. The browser selection follows the advertised capacity. These are opt-in settings: the free Blueprint explicitly remains at one thread/one photo. Local parallel tests do not verify Render memory headroom or production latency. Original uploads retain camera metadata for calibration; preview thumbnails stay on-device.

Live check: health/configuration/manifest and every shell asset returned 200. The public generated original completed as a background job with five editable depth-mode measurements; its result image returned `Cache-Control: no-store`. Known-size correction worked in the browser. One test reported 14.69 seconds of server processing, including the measurement path; this is not a latency promise or a real-garment accuracy result. Free-service wake-up delay still applies.

# Deploy the isolated FitTag Lab preview

Keep the production hardware service on `main`. For this experiment, create a **separate** Render Blueprint and select `codex/fittag-button-free`, with `render.yaml` at the root. The service name is `fittag-lab`. Do not connect this branch to the existing production Blueprint or merge it into `main` yet.

One Docker service serves FastAPI and the PWA. Docker installs the headless measurement dependencies and ONNX Runtime, then downloads a pinned 99.8 MB metric-depth model and checks its SHA-256. A model-download failure fails the build rather than silently shipping fake scale. The model is read-only in the image; no user-upload-triggered model download or external inference call occurs. No API key, database or paid inference provider is required.

The Blueprint requests the free plan. Confirm current availability/costs in Render. It uses one worker, one model/OpenCV thread and a shared measurement lock. The phone client submits an ephemeral background job, polls real stages and receives a recoverable 429 response when the instance is busy. Completed jobs expire after ten minutes and the registry is capped at twenty. See [SYSTEM_DESIGN.md](SYSTEM_DESIGN.md) for cancellation, retention and restart limits. The service listens on `$PORT` and reports `/health`; `/experiment` reports whether a local model file is configured. It does not imply accuracy or a successful model load.

New uploads are reviewed before transmission. Each image is limited to 12 MB / 25 megapixels, resized to 1800 pixels, and EXIF orientation is corrected. The client caps the combined two-photo upload at 12 MB; the server also caps aggregate request size. Only the numeric focal-length field is inspected for camera calibration; GPS, serial numbers and full metadata are not stored or returned. Annotated outputs are bounded to 40 files and expire after one hour. Original uploads are not persisted.

Local Windows live uploads succeeded in all three modes; measured server resident memory was 205.7 MB and peak working set 289.1 MB. This does **not** verify Linux/container memory or free Render response times. Monitor representative phone photos before relying on the preview. A sleeping instance and first model load can delay the first request; the client checks readiness and preserves the selected photo on timeout. Cancelling also marks the job cancelled; an admitted native computation may finish while its slot stays occupied.

```sh
docker build -t fittag-lab .
docker run --rm -p 8000:10000 fittag-lab
```

Docker is not available here; these container commands have not been exercised. Python/local checks are documented in [BUTTON_FREE.md](BUTTON_FREE.md).

After a preview build succeeds, check `/health`, `/experiment`, capture/upload in every mode, the simulated counterexample, two-photo disagreement, scale correction/undo, saved readouts, Safari/Android installation and offline shell/example behavior. The checked-in `docs/` site is static and cannot run Python or ML uploads. Do not present the preview as validated centimetre measurement or deploy it over the working hardware app.

Official references: [Render Docker](https://render.com/docs/docker), [Blueprint specification](https://render.com/docs/blueprint-spec), [free-service limits](https://render.com/docs/free).

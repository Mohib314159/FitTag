# Current branch verification

See [BUTTON_FREE.md](BUTTON_FREE.md) for the new experiment, 61 passing automated checks, live API/resource checks, synthetic model probe and the uncompleted Docker/Render/device checks.

## Earlier hardware build verification

# FitTag PWA verification

Built from upstream commit `8fa4cec` after reviewing README, recent history, markerless calibration helpers, measurement/flat-lay code, FastAPI, both existing UIs and validation data.

## Automated checks

All checks passed with the deployment's headless OpenCV 5.0.0.93 package on Python 3.13 (GUI: NONE).

- `python -m tests.test_measure`: 4/4 original top geometry cases.
- `python -m tests.test_jeans`: 3/3 original bottom geometry cases.
- `python -m pytest tests/test_phone_api.py -q`: 12 passed. Covers hardware upload/overlay, photoreal waistband regression, missing button, crop, tilt refusal, invalid upload/options, size limits, EXIF orientation, resizing, concurrent admission/health, PWA assets, privacy redaction, reference endpoint and successful marker fallback.
- `node --test tests/client.test.mjs tests/service_worker.test.mjs`: 6 passed. Unit conversion, file validation, uncertainty-aware comparisons, offline subpath loading, versioned asset recovery, private API/overlay cache exclusion and app-specific cache cleanup.
- `node --check web/app.js`, `python -m tools.build_pwa`, `git diff --check`: passed.

The test client emits a Starlette deprecation warning about its httpx adapter; tests succeed. Production uses Uvicorn, not that test adapter.

## Browser verification

Tested at 360 × 800, 390 × 844, 430 × 932 and 1280 × 720. No horizontal overflow was observed. Phone capture controls are 50 pixels tall.

Verified photo selection without upload, compact photo review, actual multipart upload through the Python measurement route, processing and results, row-to-line highlighting, cm/in conversion, confirmation before saving, local saving and a comparison that refuses a confident fit verdict inside the measurement uncertainty. The upload used the public synthetic hardware photo, never a personal garment.

Verified that selecting a top changes the illustration and camera guidance and automatically selects a paper reference. Verified installation instructions and manifest/icons. With the local server stopped, the service-worker-controlled page reloaded and its synthetic example still worked. API and personal overlay caching exclusions are also covered by the worker tests. Saved photos are not part of the local storage feature.

Screenshots in the parent outputs directory show the capture and result screens.

## Deployment verification and limits

Pinned deployment dependencies resolve and headless OpenCV is exercised locally. The Dockerfile, Render Blueprint, single-worker/thread settings, upload bounds and bounded temporary outputs are included. Docker is not installed in this environment, so a Linux container build and actual Render deployment have not been run. Physical iPhone/Android camera access and OS-level PWA installation remain post-deployment checks.

Hardware estimates require near-overhead capture and visual checking. Neither the synthetic example nor the historical paper-reference evidence validates general hardware-only accuracy. The experimental stitch scale field is preserved rather than represented as a production full-perspective solution.

Personal real-garment dimensions, tagged sizes and public photo assets have been removed from the current tree. The remaining real validation file contains only differences and provenance. Prior Git history and the remote repository have not been rewritten.

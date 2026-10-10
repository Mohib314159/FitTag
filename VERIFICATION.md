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

Tested at 360 Ã— 800, 390 Ã— 844, 430 Ã— 932 and 1280 Ã— 720. No horizontal overflow was observed. Phone capture controls are 50 pixels tall.

Verified photo selection without upload, compact photo review, actual multipart upload through the Python measurement route, processing and results, row-to-line highlighting, cm/in conversion, confirmation before saving, local saving and a comparison that refuses a confident fit verdict inside the measurement uncertainty. The upload used the public synthetic hardware photo, never a personal garment.

Verified that selecting a top changes the illustration and camera guidance and automatically selects a paper reference. Verified installation instructions and manifest/icons. With the local server stopped, the service-worker-controlled page reloaded and its synthetic example still worked. API and personal overlay caching exclusions are also covered by the worker tests. Saved photos are not part of the local storage feature.

Screenshots in the parent outputs directory show the capture and result screens.

## Deployment verification and limits

Pinned deployment dependencies resolve and headless OpenCV is exercised locally. The Dockerfile, Render Blueprint, single-worker/thread settings, upload bounds and bounded temporary outputs are included. Docker is not installed in this environment, so a Linux container build and actual Render deployment have not been run. Physical iPhone/Android camera access and OS-level PWA installation remain post-deployment checks.

Hardware estimates require near-overhead capture and visual checking. Neither the synthetic example nor the historical paper-reference evidence validates general hardware-only accuracy. The experimental stitch scale field is preserved rather than represented as a production full-perspective solution.

Personal real-garment dimensions, tagged sizes and public photo assets have been removed from the current tree. The remaining real validation file contains only differences and provenance. Prior Git history and the remote repository have not been rewritten.


## Loading, phone and bounded-job revision (2026-10-10)

- Measurement regression: 33 existing pytest cases passed; seven new job tests passed (acceptance/completion, real stages/private results, busy/cancel/health concurrency, decode and unexpected failure, combined-photo limit, retention, real shape processing). Original synthetic harnesses: 4/4 tops and 3/3 jeans.
- Node: 28 checks passed, including the real UI loading/cancel flow and six request lifecycle tests. New service-worker module works offline; job status stays outside the cache. Total across these checks: 75.
- Local live model upload completed through the new 202/status API and rendered five editable rows, retaining explicit model uncertainty. The phone waiting view displayed the actual outline stage. Console error/warning inspection was empty.
- Browser inspection at 360×640, 390×844 and 430×932: neutral capture layout, reachable fixed actions; measured 52 px action heights and 16 px native input text. No horizontal overflow at the inspected 390/430 widths. The 360 view was visually checked. Phone-sized browser testing is not a physical-device camera, Safari or OS installation test.
- Source build, JavaScript syntax and Git whitespace checks passed. A file-chooser call stalled during the final browser pass; no production deployment was performed. Docker/Render and physical-device checks remain outstanding.

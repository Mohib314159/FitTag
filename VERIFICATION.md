# Current branch verification

See [BUTTON_FREE.md](BUTTON_FREE.md) for the experiment and accuracy limits. Render/container verification and the main promotion checks are recorded below; physical-device checks remain outstanding.

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


## Loading, phone and bounded-job revision (2026-10-10)

- Measurement regression: 33 existing pytest cases passed; seven new job tests passed (acceptance/completion, real stages/private results, busy/cancel/health concurrency, decode and unexpected failure, combined-photo limit, retention, real shape processing). Original synthetic harnesses: 4/4 tops and 3/3 jeans.
- Node: 28 checks passed, including the real UI loading/cancel flow and six request lifecycle tests. New service-worker module works offline; job status stays outside the cache. Total across these checks: 75.
- Local live model upload completed through the new 202/status API and rendered five editable rows, retaining explicit model uncertainty. The phone waiting view displayed the actual outline stage. Console error/warning inspection was empty.
- Browser inspection at 360×640, 390×844 and 430×932: neutral capture layout, reachable fixed actions; measured 52 px action heights and 16 px native input text. No horizontal overflow at the inspected 390/430 widths. The 360 view was visually checked. Phone-sized browser testing is not a physical-device camera, Safari or OS installation test.
- Source build, JavaScript syntax and Git whitespace checks passed. A file-chooser call stalled during the final browser pass; no production deployment was performed. Docker/Render and physical-device checks remain outstanding.


## Selected photos, fast checks and parallel experiment (2026-10-10)

Python: 44 cases passed across phone/free/job/parallel tests, including independent two-slot admission, third-job refusal, original API compatibility, model-input numerical equivalence and bad-framing refusal before depth. Original synthetic harnesses still pass 4/4 tops and 3/3 jeans. Node: 40 checks passed, including actual client handlers for multi-photo completion, review/edit retention, local dark-photo refusal before requests, concurrency/cancellation, colour contrast and offline modules. Total: 91 checks.

Re-ran twelve scale probes after optimization. The generated-image evidence remains: five accepted captures/one rejected per focal setup, 48.1% vs 17.7% median unanchored absolute relative error; 19 non-anchor corrected measurements with 2.3% median relative error and about 0.6 cm median absolute error. Worst corrected errors remain about 5.5/5.4 cm. These are correlated generated-image measurements, not real garment/user accuracy.

Recorded 27 warm CPU trials in `validation/parallel_latency.json` (three per case at 1/2/4 model threads). Previous repeated-outline path/one thread: 6.885 s median; optimized/four threads: 3.778 s; two photos together/four threads: 4.605 s. Windows timings vary; this is one generated input, not an SLA or user-time study. Memory peaks there include rendering and model warmup, not serving memory.

Live HTTP smoke: two simultaneous accepted jobs/four threads/two slots finished in 8.47 s including first model load, each returning five rows. Live process RSS was 205.5 MB; peak Windows working set 336.1 MB. See `validation/parallel_api_smoke.json`. Free Render stays at one thread/one slot; parallel settings are opt-in. Linux/Render memory and latency remain unverified.

Fresh browser visual/camera/device verification could not be completed: browser inventory returned no available browsers and the local preview request was queued. The updated service is running at `http://127.0.0.1:8006`. Earlier viewport checks are not a fresh visual check of this revision. Client DOM and real API paths were verified separately. Docker, production deployment and OS installation remain unverified.

## Phone and request-path refinement (2026-10-10)

- Fresh regression suite: 45 pytest cases, 42 Node checks, and the original 4 top/3 jeans geometry cases passed (94 total). Build, JavaScript syntax and Git whitespace checks passed. The Python environment emitted existing test-adapter and Windows pytest-cache warnings; assertions passed.
- Added coverage for a cropped second photo skipping both model calls, no upload after cancellation, the camera/library/remove change dialog, and names/units/scale retained on reopening a batch result. Removed the extra health round trip before each photo submission; no new measured timing claim is made for this change.
- The in-app browser became available. Actual photo review, walkthrough, local quality message, waiting screen, live depth result, two selected photos completing through the HTTP job API, separate results, and names/units surviving return were checked. Photos were public generated examples, never personal garments. The browser file chooser stalled despite its configured timeout before eventually supplying the files; further chooser tests were stopped.
- This supersedes the preceding unavailable-browser note for these checked flows. Fresh checks at 360 x 640, 390 x 844 and 430 x 932 showed no horizontal overflow; fixed capture actions are 52 px high and native inputs are 16 px. Verified the change dialog offers camera/library/removal, known-size demo correction, keyboard endpoint adjustment, and a warning-free browser console. Current screenshots are `../button-free-capture-v5.jpg` and `../button-free-change-v5.jpg`. Physical camera, Safari/Android installation, Docker and Render remain unverified.

## Clothing-tool UI iteration (2026-10-10)

- Fresh visual study: Depop's seller screen and published iPhone screenshots, Photoroom's published iPhone screenshots, and Apple Measure's illustrated camera guide. Vinted's current browser page failed. See `UX_REVIEW.md` for the actual sources, extracted principles, decisions and limits.
- Implemented warm-paper/denim/red identity, new tag/F PWA icons, Photo/Lines illustration, garment buttons, above-photo measurement selection, attached selected-size caption, and a dedicated saved view. Copy/save retain chosen units; removal has undo, and newer saves invalidate stale undo snapshots. Tutorial reading clears unrelated choices; replacing a primary photo clears a stale secondary capture.
- Fresh client suite: 48 Node checks passed. The targeted FastAPI installable-assets/private-dataset regression passed. Build, JavaScript syntax and Git whitespace checks passed. The measurement engine and deployment capacity settings did not change; the preceding 45 Python and 7 original geometry checks belong to the earlier revision and were not all repeated for this UI change.
- Live browser: Photo/Lines switching, actual jeans/T-shirt SVG switching, generated-example correction, saving that example, removal/undo, reading the public original through real HTTP jobs, waiting stages, five-result rendering, measurement selection and keyboard endpoint correction were verified. Sideways measurement-picker position remained at about 253 px across an endpoint correction instead of snapping back. The console had no errors/warnings.
- Phone viewports: 360 x 640, 390 x 844 and 430 x 932; desktop: 1280 x 800. No horizontal overflow in inspected capture/result states. Primary phone actions remain 52 px and native inputs 16 px. The saved/example browser check used `localhost:8006`, separate from the user's `127.0.0.1:8006` storage, with only public generated examples. No personal garment dimensions/photos were used in screenshots.
- Current screenshots: `../button-free-capture-v6.jpg` and `../button-free-result-v6.jpg`. The result screenshot has scale explicitly set from the example's known measurement; it is not evidence of accurate unanchored ML scale.
- No new native file-chooser test was attempted after the earlier automation stalls. Physical camera, Safari/Android OS installation, screen-reader acceptance, Linux/Docker and Render performance/deployment remain unverified.

## Render deployment (2026-10-10)

- Created separate Blueprint `fittag-button-free` and free Docker service `fittag-lab` from `codex/fittag-button-free`, initially at commit `fd29eb8`. Render reported Deploy succeeded / Live after a 1m04s deployment. Existing `main` and its service were not changed.
- Live URL: https://fittag-lab.onrender.com/. The Linux Docker build installed the pinned packages, verified the 99,774,771-byte model and started one Uvicorn worker. This supersedes earlier uncompleted Render/container-build notes for this deployed revision; a local Docker installation is still unavailable.
- Health, experiment configuration and standalone PWA manifest returned 200. All 21 shell URLs returned 200. Configuration reports model present, experimental button-free mode and one-photo capacity. A live generated-result GET returned image/png and Cache-Control: no-store. Its API route does not serve HEAD; the supported GET was verified.
- In the live browser, Read the example photo selected the public original; Read photo submitted it to the server, displayed processing, and returned five editable depth-mode rows plus a new temporary overlay. Server processing reported 14.69 seconds for that single test. It is not a speed guarantee. The source was computer-made, and its large uncorrected scale error remains visible; this does not validate real-garment accuracy.
- Verified supplying the example's known waist measurement through the ordinary correction action. Browser console had no errors/warnings. Phone-sized browser checks and manifest availability are not physical iPhone camera, OS installation or production-offline checks.
- The metadata-only report is `validation/render_smoke.json`; it contains no personal photos, personal sizes or ephemeral job/result URLs. Uploaded originals are not persisted.

## Main promotion checks (2026-10-10)

The owner explicitly authorized merging and deploying the button-free PWA. Fetched remote history through normal Git/GCM and verified the experimental branch contains `origin/main`; the local merge was a fast-forward with no conflicts or overwritten changes. Preserved the existing main Render service name `fittag`, Docker runtime and free plan in root `render.yaml`. The separate preview branch retains its own `fittag-lab` configuration.

Fresh checks before promotion: 45 Python API/geometry/job/parallel tests, 48 Node client/service-worker tests and all seven original geometry cases passed (100 checks). The existing Starlette/httpx test-adapter deprecation warning remains; no assertions failed. Publishing does not establish real-garment accuracy or physical iPhone installation.

Published commit `87a067f745fc42bcfd639b1324a5653f85f83305` to GitHub `main` through normal Git/GCM and re-fetched it to verify the root Blueprint. Render automatically deployed that commit to the existing free `fittag` service and reported Deploy succeeded in 1m09s. The live app is https://fittag.onrender.com/.

Verified all 21 shell assets, `/health`, `/experiment`, the standalone manifest and retained `/button.html` return 200. Configuration reports the model present and one-photo capacity. The live app uploaded the public computer-made example through the real job API, displayed processing and returned five editable depth-mode rows with the accuracy warning intact. It reported 13.71 seconds of server processing for this one test; this is neither a speed guarantee nor real-garment accuracy evidence. The browser console reported no errors or warnings. Physical-device installation remains untested.

## Camera-first correction (2026-10-10)

Reverted the rejected photo-led visual pass and restored the preceding interface. The initial illustration/example controls are hidden; a new rear-camera module requests permission on opening and places the live view in the existing photo area. Capture produces a full-frame bounded JPEG locally; selection stops the stream and preserves the explicit Read photo upload. Navigation/backgrounding releases tracks and invalidates pending captures. Denied, unavailable, busy, interrupted and autoplay-blocked cameras have recovery copy and phone-camera/library paths. The measurement engine, accuracy warnings and Render capacity are unchanged.

Fresh checks: all 59 Node client/camera/service-worker tests passed, including real client shutter/permission handlers with mocked camera streams, late permission, stream release, capture failure, and offline camera-module availability. The targeted FastAPI static-assets/private-dataset check passed (one existing Starlette/httpx deprecation warning). Build, JS syntax and Git whitespace checks passed. The local browser showed the restored heading, camera-permission waiting state and no initial illustration at 360 x 640, 390 x 844 and 430 x 932; no horizontal overflow, 52 px primary actions and no console warnings/errors. The in-app browser did not complete its pending camera permission request; these checks do not establish physical iPhone camera operation or installation. No personal camera frames or garment dimensions were used as evidence.

## Separate camera-studio design branch (2026-10-10)

The owner requested a fresh researched design with no merge. `codex/fittag-camera-studio` implements a camera screen, settings sheet, focused line editor and photo-backed processing view while preserving the existing backend and accuracy warnings. See DESIGN_STUDIO.md for inspected primary visual references, iterations and verification limits. Fresh verification: 64 Node checks and the targeted Python asset/privacy check passed. Real local HTTP photo processing, endpoint correction, known-length correction, sheet navigation and error dismissal were exercised. Capture fits at 360 x 640, 390 x 844 and 430 x 932; desktop was checked at 1280 x 800. No horizontal overflow or console errors/warnings were observed. The public computer-made test image is only UI test evidence. Physical iPhone camera and installation remain unverified. Main and the main Render service are not changed by this branch.

# A small service that behaves well while people wait

The experimental phone client uses one FastAPI service and CPU inference. The architecture is deliberately small: no database, Redis, message broker, account system or second deployment.

## Measurement lifecycle

1. Review the photo locally. Pressing Read photo uploads once to `POST /measure-free-jobs`. Admission reports availability itself, removing one readiness round trip per photo.
2. Admission takes the same compute gate as the existing hardware and synchronous endpoints, before decoding. A configured compute gate allows one or two operations to decode/process at a time. Free Render defaults to one. A busy instance returns 429 and `Retry-After: 5`; there is no growing queue of images in RAM.
3. The accepted operation returns 202 with an opaque random status URL, `Location`, and `Retry-After`. The CPU task runs in the thread pool, keeping the event loop available for health/status requests. Image decoding also runs off the event loop.
4. The client polls roughly once a second. Backend callbacks expose actual outline, depth, geometry, second-photo and finishing stages. The indicator stays indeterminate: stages are not elapsed-time percentages. Connecting and sending describe the client's actual request phase; the animation is decorative activity, not a detection visualization.
5. Results live only in memory. Completed jobs expire after ten minutes and the registry is capped at twenty. Pruning occurs on submission/status access. Existing bounded overlays expire after one hour. Upload handles close after decoding; original photo bytes are retained only for admitted computation, never in a job record.
6. Cancel sends DELETE, clears the result and suppresses future progress. Native ONNX/OpenCV work cannot be interrupted safely in the middle of a call: the slot remains held until that call and the next cancellation check complete. Cancel does not promise an instant stop of CPU use.

The selected image stays available after cancellation, timeout, busy responses, job expiry or connection failure. The client has a two-minute deadline, a delayed slow-service message and at most two retries of failed status **reads**, with bounded backoff. It never automatically retries the upload, because an unanswered POST might already have started computation. Duplicate button presses are guarded while an operation is active.

## Limits and tradeoffs

- This is a single-worker architecture; multiple workers would have separate locks and job registries. Keep the Docker command at one worker. A production move to multiple replicas would need a shared job store and queue with resource limits.
- A restart loses in-flight jobs and results. A missing status returns a clear expiry/restart response; the user explicitly resends the retained photo. There is no promised restart recovery or durable processing.
- The model and geometry assumptions remain unvalidated for accurate reference-free garment scale. Reliability infrastructure does not improve measurement accuracy.
- Client photos total at most 12 MB. The server enforces that combined limit after reading, individual file/decode limits, and a declared aggregate request-body limit. Chunked multipart ingress is not a complete bandwidth/rate-abuse defense; public production hardening would need upstream request/rate limits. The free preview is not claimed to withstand adversarial load.
- Job IDs are random unguessable capabilities, not accounts. Responses use `no-store`; the service worker excludes job status, uploaded photos, results, health and model files. No photo data goes to another inference service.
- Free Render services can spin down and require a startup delay. The configuration request happens once on opening the app; the app does not run keep-alive traffic to evade free-service limits. Local timing is not a Render benchmark.

## Research and decisions

- [Microsoft asynchronous request-reply](https://learn.microsoft.com/en-us/azure/architecture/patterns/asynchronous-request-reply): use 202, an explicit status endpoint, retention and cancellation. Use only real stages; do not manufacture percent completion. A durable queue/idempotency registry would add infrastructure without solving this preview's measurement uncertainty.
- [Microsoft bulkhead pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/bulkhead): apply bounded admission to the costly image path so health and status remain available. This is one limited compute pool, not complete isolation of every endpoint or a claim of high-scale service reliability.
- [Apple progress indicators](https://developer.apple.com/design/human-interface-guidelines/progress-indicators): truthful indeterminate activity, brief context and recovery for delays, with reduced motion support.
- [Render free-service behavior](https://render.com/docs/free): account for sleeping instances and avoid assuming the first request behaves like warm localhost.

Tests cover actual async job acceptance/completion, progress callbacks, busy admission, health responsiveness during a blocked worker, cancellation before overlay persistence, slot retention, invalid/decode failures, redacted unexpected errors, retention, real shape inference, status retry policy and client cancellation with photo retention.


## Photo selection and performance

The first screen still starts with one photo. A separate selection screen holds up to six files in the browser (maximum 36 MB total), with a garment type per photo. Low-resolution thumbnails are generated after local checks; the selection does not decode six full-size photos for display. Files are sent only when the user taps Read photos, and only up to the capacity advertised by `/experiment`. This is a client selection, not an unbounded server queue. Each result can be opened, edited and saved; edits and supplied scale survive returning to the selection. Different items are never used as a same-garment scale cross-check.

Quick local checks inspect a small bitmap for very dark/blank images, tiny originals and severe blur; uncertain blur gives a warning. Unsupported bitmap APIs or failures leave manual review available. These heuristics cannot verify floor geometry, item class, perspective, hidden hems, exact scale or every kind of blur. Server outline/framing checks run before the depth model, so rejected geometry never triggers expensive inference. The original file and focal metadata are preserved; thumbnails do not replace measurement inputs.

The depth path reuses the already detected original mask rather than segmenting that photo twice. Preprocessing resizes floating-point image channels before RGB normalization, avoiding full-size RGB/normalized intermediates while preserving model input within numerical tolerance. ONNX uses one shared model session, configurable intra-op threads (1–4), sequential graph execution and disabled thread spinning. Measurement admission is configurable (1–2); overlay writes/pruning use one short synchronized critical section. We do not duplicate model weights per request or spawn GPU/HPC infrastructure that this deployment does not have.

The reproducible benchmark is `python -m tools.bench_parallel`, with a pinned local model configured. It compares repeated outlining vs mask reuse and concurrent photos at 1/2/4 model threads, with three warm trials per case. The generated input, local timing and peak Windows working set are recorded in `validation/parallel_latency.json`. Optional `psutil` is needed for this developer benchmark, not the serving app. Thread tuning follows [ONNX Runtime's threading guidance](https://onnxruntime.ai/docs/performance/tune-performance/threading.html). Use [Render's current compute specifications](https://render.com/docs/compute-plans) when choosing capacity. A free 0.1-CPU/512-MB service is not equivalent to the multi-core Windows benchmark.

Both images in the optional same-item comparison now pass outline checks before either depth inference runs. The second mask is reused for its depth projection. A bad second photo returns the first photo's proportions and an explanation, without wasting two model calls. Focal metadata is also read only once per capture. These reduce unnecessary work; no additional latency gain is claimed without a dedicated benchmark. Image decoding and CPU work stay off the event loop, as described in [FastAPI's concurrency guidance](https://fastapi.tiangolo.com/async/).

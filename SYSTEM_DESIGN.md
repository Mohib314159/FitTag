# A small service that behaves well while people wait

The experimental phone client uses one FastAPI service and CPU inference. The architecture is deliberately small: no database, Redis, message broker, account system or second deployment.

## Measurement lifecycle

1. Review the photo locally. Pressing Read photo first checks `/health`, then uploads once to `POST /measure-free-jobs`.
2. Admission takes the same lock as the existing hardware and synchronous endpoints, before decoding. One operation can decode/process at a time. A busy instance returns 429 and `Retry-After: 5`; there is no growing queue of images in RAM.
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
- Free Render services can spin down and require a startup delay. The readiness check is user-initiated; the app does not run keep-alive traffic to evade free-service limits. Local timing is not a Render benchmark.

## Research and decisions

- [Microsoft asynchronous request-reply](https://learn.microsoft.com/en-us/azure/architecture/patterns/asynchronous-request-reply): use 202, an explicit status endpoint, retention and cancellation. Use only real stages; do not manufacture percent completion. A durable queue/idempotency registry would add infrastructure without solving this preview's measurement uncertainty.
- [Microsoft bulkhead pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/bulkhead): apply bounded admission to the costly image path so health and status remain available. This is one limited compute pool, not complete isolation of every endpoint or a claim of high-scale service reliability.
- [Apple progress indicators](https://developer.apple.com/design/human-interface-guidelines/progress-indicators): truthful indeterminate activity, brief context and recovery for delays, with reduced motion support.
- [Render free-service behavior](https://render.com/docs/free): account for sleeping instances and avoid assuming the first request behaves like warm localhost.

Tests cover actual async job acceptance/completion, progress callbacks, busy admission, health responsiveness during a blocked worker, cancellation before overlay persistence, slot retention, invalid/decode failures, redacted unexpected errors, retention, real shape inference, status retry policy and client cancellation with photo retention.

# Button-free experiment

This branch is a working PWA experiment, not a replacement for the hardware flow
on `main`. It requires no button, paper, card, printed markers or object placed
in the photo. The original experience is still available at `/button.html`.

Three capture routes share the existing silhouette and landmark engine:

| Route | Physical scale | Limitation |
| --- | --- | --- |
| Metric depth | Small indoor model proposes metres; a fitted floor plane projects the image | Learned scale can be substantially wrong even when the plane fits |
| Proportions | No physical scale; inseam or garment length is 100% | Cannot produce centimetres without additional information |
| Known camera height | Supplied lens-to-floor distance and camera focal length | Requires genuinely known height, a flat garment and an overhead camera; no full perspective correction |

A second overhead photo can check metric-depth scale consistency. Differences
above 25% in primary measurements withhold centimetres. Agreement is **not**
accuracy: both predictions can share the same bias. Identical files are refused
as an independent check. The app does not average correlated predictions into a
misleadingly confident number.

The UI also supports direct endpoint correction with drag/keyboard controls, a magnified view, undo and copying measurement text with its scale limitations.

Optional known-length correction uses one measurement of the garment itself;
there is still no reference object in the photo. It rescales all readouts from
the original result, supports undo, and retains a broad engineering allowance
for geometry error. Neither a visual confirmation nor this allowance establishes
a statistical accuracy interval. Unanchored model guesses have no fabricated
error bars or fit recommendation.

## What was tried

1. Direct model scale: a plausible, nearly flat depth map still gave a large
   scale error on the simulated garment. It remains visible as a counterexample.
2. Camera intrinsics: reading only numeric 35 mm equivalent focal length from
   EXIF, or explicitly supplying diagonal field of view, reduces one source of
   error. Crop, zoom and missing metadata still matter. When missing, 84° is an
   explicit assumption, not detected camera knowledge.
3. Floor geometry: robust inverse-depth plane fitting excludes the garment and
   nearby edges. Invalid/nonfinite depths, nonplanar floor predictions, extreme
   distance or tilt and insufficient background refuse the metric candidate.
4. Cross-capture check: two independently processed photos test changes in scale.
5. Shape fallback: preserves useful line locations and ratios when metric scale
   fails. It never relabels ratios as centimetres.
6. Known-length anchoring: corrects multiplicative scale bias, but cannot repair
   the wrong crotch, outline or perspective.
7. Known camera distance: a geometric alternative with no ML scale prior.

### Synthetic probe, not garment accuracy

`python -m tools.probe_button_free` renders six captures (two jeans designs and
one top, different camera heights, including tilted views), **with all hardware
and reference objects removed**. It runs the pinned model with assumed and
known synthetic intrinsics. Full results are in
`validation/button_free_probe.json`, including failures and provenance.

| Camera setting | Metric candidates accepted | Median absolute landmark error | Maximum |
| --- | --- | --- | --- |
| Assumed 84° | 5 of 6 captures | 48.1% | 81.0% |
| Known synthetic intrinsics | 5 of 6 captures | 17.7% | 43.4% |

Correcting scale with a known primary garment length reduced median absolute
error to 2.3% in both camera settings **on the other measurements in these simulations only**. Maximum
remaining errors were 11.6% / 12.1%. The supplied anchor itself is excluded: 19 other landmark measurements across five accepted simulated captures. Their median absolute error was 0.6 cm, with worst error about 5.5 cm / 5.4 cm. These are correlated measurements of five captures of three synthetic designs, not 19 independent garments or real-user validation. One tilted case was rejected in both settings.

The example's known simulated waist is 41.0 cm. The unanchored model guessed
74.2 cm with assumed intrinsics. A low plane residual did not protect against
that scale error. No model was trained or tuned on these cases.

Existing 17.0 mm hardware recovery and real-photo repeatability evidence belongs
to the earlier paper/hardware work. It does not validate this model route.
No personal sizes or photographs were added.

## Model and runtime

Depth Anything V2 Small indoor metric model, 24.8M parameters, exported by
Kornia as fixed 392 × 392 ONNX. RGB ImageNet normalization; output depth in metres.
The 99,774,771-byte weights are downloaded during Docker build, never during an
upload. Revision and SHA-256 are pinned and checked during download and first
load. Requests call this app's CPU runtime; no user photo goes to a model host.
No Torch, GPU, paid inference API or model key is required.

- [Metric model authors and training](https://github.com/DepthAnything/Depth-Anything-V2/tree/main/metric_depth)
- [Official small model](https://huggingface.co/depth-anything/Depth-Anything-V2-Metric-Hypersim-Small)
- [Pinned Kornia export and checksum](https://huggingface.co/kornia/depth-anything/blob/86f40563e7e87a0839be758988aa804930409a61/depth-anything-v2-metric-small-indoor.onnx)

Single-photo metric depth is a statistical prior, not a resolution of projective
scale ambiguity. Depth Pro/MoGe with focal estimation are worth benchmarking as
larger alternatives; they were not substituted into this small-instance build.
Native ARKit/ARCore visual-inertial capture could provide metric motion/depth,
but those APIs are not a portable capability of this installable web app. A
browser-only two-photo reconstruction also retains a global scale ambiguity.

## Verification

- Original measurement harness: four tops and three jeans cases passed.
- Python API/geometry checks: 33 passed, including 21 button-free checks.
- Node client/service-worker checks: 21 passed, including seven tests executing
  the actual experimental client against a DOM, not just utility functions.
- Six synthetic captures × two camera assumptions exercised the actual model.
- Live local multipart uploads succeeded in shape, depth and distance modes.
- The local server measured 205.7 MB resident / 289.1 MB peak working set after
  those uploads. Model-only inference initially used about 182 MB resident and
  took about 4.8 seconds. These are Windows measurements, not Render guarantees.
- Browser capture and actual-model example inspected at 360 × 800, 390 × 844 and 430 × 932 during development; 50-pixel capture controls and no horizontal overflow. Known-length correction, units and local save were checked in the browser after it recovered from a temporary interruption. Full physical-phone camera and OS-install checks are not claimed.
- Offline shell/client behavior is covered by service-worker tests. A new physical
  offline installation of this branch has not been tested.
- Linux Docker build and Render deployment have not been run here.

## Before considering a merge

Collect tape ground truth for varied real garments with buttons covered, two
uncropped overhead photos per garment and available camera metadata. Evaluate
unanchored errors, refusal rate and known-length correction separately. Include
different floors, lighting, colours and phones. Repeatability alone is insufficient.
The current evidence argues against using this small model's unanchored scale
for shopping or size recommendations. Keep `main` unchanged until real tests
justify a product decision.

# More reliable buttonless measurement: research review

Reviewed 10 October 2026. This is research, not a new accuracy claim or a change
to the deployed estimator. No button, paper, coin or card is proposed as a
required reference. Experimental models remain on the unmerged audit branch.

Follow-up: [completed model trials](BUTTONLESS_MODEL_RESULTS.md) and the
[no-Mac LiDAR trial](LIDAR_TRIAL.md) supersede the untested status of the three
additional RGB candidates below. None was promoted to production.

## Recommendation

For **new captures on an iPhone 15 Pro Max**, investigate a small native depth
capture component that supplies measured distance to the existing FitTag
geometry pipeline. Keep the PWA and FastAPI service for review, editing and
results. This is the strongest engineering hypothesis because it supplies
physical scale rather than relying entirely on a learned size prior.

For **existing uploads**, first distinguish originals containing usable absolute
depth from ordinary RGB photos. Benchmark camera-aware metric models on real
garments before choosing a replacement. No source examined establishes reliable
centimetre measurement from every arbitrary clothing image.

## Options and their actual limits

| Route | Where physical scale comes from | Assessment for FitTag |
| --- | --- | --- |
| LiDAR capture with calibrated RGB | Measured distance plus camera calibration | Highest-priority reliability experiment for the owner's phone; needs native access and physical-device validation. |
| Original HEIC with verified absolute depth | An embedded sensor measurement, if actually present and usable | Potential upload route; inspect accuracy type, units and image alignment. A HEIC extension alone proves nothing. |
| Camera-aware metric depth model | Learned scene/size priors, helped by real intrinsics | Best general RGB-upload experiment; can still produce a very consistent but incorrectly scaled result. |
| Short guided capture with visual-inertial tracking | Camera motion constrained by inertial measurements | A possible non-LiDAR capture path; requires successful initialization and synchronized sensing. Two arbitrary photos alone do not supply metric scale. |
| Exact item/size lookup | A verified catalogue measurement | Useful for identifiable product photos, but dimensions must describe the actual garment, not a body-size chart. Wear and shrinkage remain relevant. |

### 1. Sensor-based capture has directly relevant garment evidence

Apple confirms that the [iPhone 15 Pro Max has a LiDAR scanner](https://support.apple.com/en-gb/111828).
Its [ARKit scene-depth API](https://developer.apple.com/documentation/arkit/arconfiguration/framesemantics-swift.struct/scenedepth?changes=l_5)
provides distance for objects in the captured camera image on supported devices.

The authors of [Automatic Garments Size Measurement](https://github.com/ZinoStudio931/Automatic-Garments-Size-Measurement-using-HRNet-and-Point-Cloud)
used a LiDAR-equipped mobile device, clothing landmarks and point clouds. Their
repository describes 330 RGB/depth/point-cloud sets and reports average relative
errors of 1.59% and 2.08% for its two test conditions. These are the authors'
results, not reproduced FitTag results. The README also says detector weights
require a request and measurement/visualization modules would be released later;
this is evidence for an approach, not a complete drop-in implementation.

Proposed FitTag experiment: capture RGB, matching depth, confidence, calibration
and orientation together. Fit a plane from reliable surrounding floor readings,
then intersect the high-resolution RGB landmark rays with that plane. This
would use the existing landmark/geometry engine while avoiding reliance on
low-resolution depth edges for every clothing endpoint. Reject poor tracking,
missing floor coverage, misalignment and bad depth. Test dark fabric, shadows,
glossy floors, folded garments and capture distance explicitly.

This design is an inference from the available sensor data and garment research.
Neither an iPhone implementation nor its accuracy has been tested here.

### 2. A PWA installation does not unlock native LiDAR

[MDN's maintained browser-compatibility data](https://github.com/mdn/browser-compat-data/blob/main/api/XRSystem.json)
currently records no XRSystem support for Safari/iOS. WebKit's
[Safari 18 announcement](https://webkit.org/blog/15865/webkit-features-in-safari-18-0/)
describes WebXR immersive VR on visionOS, which does not establish iPhone AR
depth access. Do not confuse camera permission or Add to Home Screen with an
ARKit depth stream.

A native capture bridge is an architectural option, not an existing PWA feature.
An [App Clip](https://developer.apple.com/documentation/AppClip) is another
possible distribution approach; it still needs an actual native implementation
and release process. The public PWA can remain usable for imports and results.

### 3. Inspect HEIC depth instead of assuming it is metric

Apple distinguishes [absolute LiDAR depth from relative disparity-based depth](https://developer.apple.com/videos/play/wwdc2022/110429/).
The [AVDepthData accuracy documentation](https://developer.apple.com/documentation/avfoundation/avdepthdata/accuracy/absolute)
also separates data accurate in physical scale from data intended for relative
foreground/background separation. Converting a relative map into a depth format
does not establish that its physical scale is accurate.

FitTag's current camera-evidence scanner only reports numeric EXIF fields and
the number of depth candidates. It does not recover or verify absolute depth.
The next investigation needs an original file: identify the auxiliary type,
accuracy metadata, units, camera calibration, crop/orientation and alignment.
Keep this inspection private; never publish GPS, full Maker Notes, owner fields,
the photograph or personal garment dimensions. Missing metadata stays missing.

### 4. Worthwhile RGB model candidates, with deployment constraints

| Candidate | Why test it | Limitation to check |
| --- | --- | --- |
| [Depth Pro](https://github.com/apple-aiml-research/ml-depth-pro) | Estimates metric depth and focal length; accepts supplied focal length. | The quoted 0.3-second timing is on a GPU, not Render CPU. GitHub says the released reference model differs from the paper model. |
| [UniDepthV2](https://github.com/lpiccinelli-eth/UniDepth) | Predicts camera-aware geometry; supports known cameras and ONNX exports. | Its confidence is not an absolute centimetre-error bound; the repository has a non-commercial license. |
| [DA3Metric-Large](https://huggingface.co/depth-anything/DA3METRIC-LARGE) | A newer metric-depth candidate with an Apache-2.0 model listing. | Requires correct focal conversion; large model, not a small Render replacement. |

[DA3's own documentation](https://github.com/ByteDance-Seed/Depth-Anything-3)
specifies focal-in-pixels conversion for its metric model. Its nested multi-view
model obtains scale from a monocular metric model; additional views are not
independent proof of metric accuracy. The metric model has 0.35B parameters:
float32 weights alone would occupy about 1.4 GB before inference allocations.
Keep this as an offline benchmark until resource measurements justify hosting.

[UniDepthV2's confidence explanation](https://github.com/lpiccinelli-eth/UniDepth/blob/main/assets/docs/V2_README.md)
calls its output a relative ranking within an input based on scale-invariant
error. It cannot justify a statement such as "accurate within 1 cm." Agreement
between models is also only a rejection clue: correlated priors can agree and
all be wrong. Calibrate any acceptance rule against held-out real measurements.

Licenses must be tied to the exact artifact. Apple's
[GitHub code license](https://github.com/apple-aiml-research/ml-depth-pro/blob/main/LICENSE)
and its [Hugging Face checkpoint license](https://huggingface.co/apple/DepthPro/blob/main/LICENSE)
differ; the latter explicitly restricts its grant to research and excludes
product development. Do not treat a permissive code license as permission for
every checkpoint, or quietly deploy research-only weights into the app.

### 5. Garment-specific learning is plausible, but not solved

[MV-Fashion](https://arxiv.org/html/2603.08147v1) provides real garment measurement
annotations and paired imagery. Its direct-image end-to-end size baseline
reports **6.134 cm mean absolute error**. The better **4.279 cm** result uses
ground-truth canonical garment normals, so it must not be presented as ordinary
photo-to-size performance. These are worn-garment experiments, not validation
of flat-lay FitTag. They support testing a garment-specific model while showing
why generic visual plausibility is insufficient.

[FIT](https://johannakarras.github.io/FIT/) provides measurement-labelled data
generated from synthetic garments. It could help pretraining and controlled
stress tests; it cannot replace held-out real phone-photo evaluation.

## Why pixels and extra photos cannot always settle size

For a pinhole camera, an apparent length is approximately `pixels = focal *
physical_length / distance`. Doubling the physical length and distance produces
the same pixels and focal metadata. A model can use scene context to prefer a
likely size, but cannot universally distinguish those observations. Cropping
can additionally invalidate focal-in-pixels conversion unless the crop is known.

Likewise, ordinary monocular multi-view reconstruction has an unknown overall
scale. [Visual-inertial observability research](https://arxiv.org/abs/2103.15215)
explains why inertial excitation matters for metric scale. A browser motion
sensor is not automatically a calibrated, synchronized VIO system. This route
deserves a separate capture experiment rather than an untested "move your phone"
promise or double integration of noisy acceleration.

## What to test next

1. Inspect a privately supplied original HEIC before inferring its capabilities.
2. Benchmark the new RGB candidates offline using identical, correct camera and
   landmark conventions. Include unknown-camera and known-camera variants.
3. Evaluate against independently measured real flat garments. Split by garment
   and camera, not randomly by near-duplicate photo. Generated captures remain
   stress tests, not user accuracy evidence.
4. Separate scale error from endpoint error. Report per-measurement centimetre
   errors, the 90th percentile, serious failures, refusal rate and processing
   time. Report accepted and refused cases together. Any supplied length is
   excluded from the score.
5. For sensor capture, independently test plane distance, RGB-depth alignment
   and final garment dimensions on the actual phone before claiming support.

The existing audit's six generated captures still show **29.36% median error**
for MoGe-2 with inferred camera, compared with **45.90%** for the existing model
with an assumed camera. Those stored results were re-read for this review, not
rerun. No newly researched model was benchmarked in this follow-up, and none was
merged or deployed. See [the audit and reproduction instructions](BUTTONLESS_RESEARCH.md).

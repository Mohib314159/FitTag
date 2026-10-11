# Buttonless scale audit

[Completed additional model trials](BUTTONLESS_MODEL_RESULTS.md) now include
actual UniDepthV2, DA3Metric and Depth Pro runs, geometry controls, HEIC depth
inspection and a local [rear-LiDAR import trial](LIDAR_TRIAL.md).

Follow-up: [more reliable buttonless options](BUTTONLESS_OPTIONS.md) compares
sensor capture, original HEIC depth, newer RGB models and garment-specific
learning, with sources and a proposed real-garment evaluation plan.

The owner reaffirmed buttonless upload on 10 October 2026. The paper experiment
was set aside, unmerged. This branch investigates ordinary photos without
substituting a button, coin, card or paper requirement.

## Concrete problems found

1. The fixed 392-square Depth Anything export stretches the photo. The authors'
   inference preserves aspect ratio. Padding is not the same as their flexible
   input pipeline, so three preprocessing strategies were actually benchmarked.
   Padding was not a consistent improvement and is not promoted as a fix.
2. Perspective correction discarded the projected garment mask and segmented
   again on the warped image. White warp borders can change the colour split.
   The corrected path retains that mask and reuses the existing landmark rules.
   The regression test forbids a second segmentation and checks known geometry.
3. The small indoor depth prior can fit a very consistent floor while returning
   the wrong size. Plane residual and agreement between photos are not proofs
   of absolute scale. A fit verdict cannot be justified by them.
4. The original iPhone picker rejected HEIC. The deployed phone correction
   accepts HEIC/HEIF and decodes them with a pinned native library; Back and
   visible selection/error states were also corrected. Actual iPhone testing
   still requires the device, and the reported original was not supplied.

## What an original file can contribute

`api/camera_evidence.py` inspects only numeric focal length, EXIF subject
distance, digital zoom and a count of depth-layer candidates. It does not
return full EXIF, GPS, owner names, serial numbers or Maker Notes. Invalid and
missing values remain unknown. Evidence is reported without silently turning
focus distance or a depth layer into measured floor distance.

- Focal length helps recover camera rays. It does not supply object distance.
  For a pinhole camera, apparent length depends on physical length multiplied
  by focal length and divided by distance. Scaling both object and distance
  equally leaves the same pixels. A learned model supplies a prior, not a
  universal resolution of that ambiguity.
- The standard subject-distance field may help when present, but the focused
  subject can differ from the floor. It is not automatically used as a ruler.
- Apple explicitly distinguishes **absolute LiDAR depth** from **relative
  disparity-based depth**. A portrait HEIC layer must not automatically be
  interpreted as absolute metres. The original file may contain a useful
  auxiliary; exporting to JPEG or a screenshot can remove it. The scanner
  detects candidates, but verified unit/accuracy/alignment extraction is not
  implemented or claimed.
- Apple Maker Note focus fields are not used as guaranteed distance readings.
  Their presence alone cannot justify metric measurement.

References: [Apple's depth camera explanation](https://developer.apple.com/videos/play/wwdc2022/110429/),
[HEIC depth auxiliaries in Pillow HEIF](https://pillow-heif.readthedocs.io/en/stable/heif-file.html),
[EXIF tags](https://exiftool.org/TagNames/EXIF.html),
[metric ambiguity and camera normalization in Metric3D](https://arxiv.org/abs/2307.10984).

## Model experiments

Depth Anything: `tools.audit_buttonless_depth` runs the actual pinned ONNX
model on six controlled captures of three generated garment designs. The
36 records compare square stretching, constant letterboxing and reflection
padding, each with assumed and known synthetic camera intrinsics. These
initial records use the earlier resegmentation path; see
`validation/buttonless_preprocessing_audit.json`.

MoGe-2: the authors' 35M-parameter Small ONNX export proposes affine point
geometry, validity and a metric scale. It also supports recovery of focal
length, so it is a more relevant hypothesis than applying an 84-degree camera
assumption to every imported file. FitTag's isolated adapter implements the
necessary focal/shift recovery and applies metric scale once. The 141 MB
weights are pinned and verified; they are not bundled into the Render image.
`tools.probe_moge` tests inferred and known camera intrinsics at 400x500.
`tools.probe_depth_baseline` provides the existing model's comparison at the
same image resolution with the corrected mask path. Synthetic outcomes are
counterexamples, not real-garment accuracy or user-impact metrics.

The pre-fix MoGe run is retained separately in
`validation/moge_buttonless_pre_mask_fix.json`. The corrected run is in
`validation/moge_buttonless_probe.json`. It still has substantial errors;
it is not promoted to production on the strength of these six images.

The corrected, same-resolution comparison returned metric candidates for all
six captures in each setting. Across their matched landmarks, the existing
model with an assumed camera had **45.90% median / 81.95% maximum** absolute
percentage error; MoGe with its inferred camera had **29.36% / 46.38%**.
With the true synthetic camera supplied, the existing model gave
**16.62% / 44.47%**, while MoGe gave **29.73% / 46.81%**. Those results do not
justify calling either model dependable, and MoGe is not consistently better.
They are six generated captures of three designs, not independent real users
or a validation of real clothing sizes. No anchor measurement is used in
these scores.

The branch also exposes a working **Camera-aware estimate (lab)** choice in
Photo settings when `FITTAG_MOGE_MODEL` points to the pinned local weights.
It submits a real background job through the existing admission/cancellation
system. This is a local opt-in pilot, with the same explicit review, line
editing and accuracy warnings; it is not a mock result or a production default.
The serving route bounds input to a 500-pixel long edge and 1200 model tokens.
Check resource use before deploying it on a constrained instance. The plain
Render image does not include the research optimizer or these extra weights.

Primary sources: [Depth Anything preprocessing](https://github.com/DepthAnything/Depth-Anything-V2/blob/main/metric_depth/depth_anything_v2/dpt.py),
[Microsoft MoGe](https://github.com/microsoft/MoGe),
[the authors' ONNX limitations](https://github.com/microsoft/MoGe/blob/main/docs/onnx.md),
[Apple Depth Pro](https://github.com/apple-aiml-research/ml-depth-pro).
The completed MoGe run uses ONNXRuntime. At this initial audit, Depth Pro and
MoGe-3 had only been researched. Depth Pro was subsequently benchmarked in the
additional trials linked above; MoGe-3 remains untested here. Neither is a
working Render replacement.

Reproduce locally with the optional `requirements-research.txt`. Download
weights with `python -m tools.download_moge_model /path/to/moge-small.onnx`,
then run `python -m tools.probe_moge /path/to/moge-small.onnx`. Run the existing
model baseline with `FITTAG_DEPTH_MODEL` configured and
`python -m tools.probe_depth_baseline`. No research script downloads weights
during a serving request, modifies a personal photo or uploads an image to a
third-party model service.

Another route for existing product photos is identifying the exact item and
size from a visible label or listing, then retrieving manufacturer garment
dimensions. That would be a catalogue lookup, not geometric recovery from
pixels, and would need an exact match and actual flat-garment measurements.
It is not implemented here and cannot cover arbitrary unlabelled clothes.

## What would justify shipping a different size estimate

Use originals of real flat garments, with independently recorded tape
measurements. Test different cameras, camera heights, crops, lighting,
backgrounds and garment shapes. Keep an evaluation set out of tuning. Report
absolute centimetre error, material worst cases and refusal rate; include the
same-size/different-distance ambiguity. Model swaps, good overlays and passing
tests are not substitutes for those measurements. An original failed photo is
needed to diagnose that specific input and investigate any actual metadata or
depth layer it contains.

Arbitrary screenshots, cropped clothes and garments worn on a person remain
outside any supported accuracy claim. A plausible-looking result is not
proof that hidden dimensions or physical scale were recoverable.

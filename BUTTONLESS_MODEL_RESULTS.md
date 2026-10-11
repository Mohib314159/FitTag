# Completed model trials and the next physical test

The three additional photo candidates were actually run, not just researched:
UniDepthV2 Small, DA3Metric-Large and Depth Pro. All used the same six generated
captures of three garment designs at 400×500, the retained-mask perspective
pipeline and the existing default landmark rules. There are 29 matched landmark
measurements per camera setting. No supplied length was scored as a prediction.

These are controlled failure tests, **not real-garment accuracy**, independent
users, or a basis for a CV claim about reduced returns. The inputs contain no
personal garment photographs or dimensions.

## Results with camera information unavailable

| Model | Camera source | Median absolute percentage error | Maximum error | Accepted captures |
| --- | --- | --- | --- | --- |
| Existing Depth Anything metric export | Assumed 84° diagonal field of view | 45.90% | 81.95% | 6/6 |
| MoGe-2 Small | Model camera estimate | 29.36% | 46.38% | 6/6 |
| UniDepthV2 Small | Model camera estimate | 49.42% | 66.81% | 6/6 |
| DA3Metric-Large | Assumed field of view; author focal-based metric conversion | 33.70% | 46.81% | 6/6 |
| Depth Pro | Model camera estimate | 33.17% | 62.13% | 6/6 |

With the true generated camera supplied, median errors were respectively 16.62%,
29.73%, 40.52%, 33.70% and 33.20%. This is not a finding that correct calibration
is unhelpful in general. It demonstrates failures of these priors and the
current geometry/landmark pipeline on this particular input set.

All five produced metric candidates for every case even when wrong. Floor-plane
residuals cannot serve as an absolute scale-accuracy score. No model was promoted
to the deployed app, and none establishes reliable arbitrary-photo sizing.

## Resources and corrections made during the experiments

The isolated runtime used CPU PyTorch with four threads. UniDepth's model passes
took about 2.4–3.0 seconds, DA3 about 12 seconds, and Depth Pro about 216–217
seconds per generated image. These exclude imports, loading and input generation;
they are not phone or Render timings. Sampled peak process RSS was approximately
905 MB, 2,071 MB and 8,008 MB respectively. None was demonstrated to fit the
current constrained Render instance.

Depth Pro's checkpoint is half precision. A CPU half-precision trial did not
finish its first case within roughly ten minutes and was stopped. A small matrix
probe showed FP32 was much faster on this CPU. The completed run used a streamed,
hash-verified FP32 safetensors conversion of the same weights; no retraining or
architecture changes. Floating values were promoted exactly and original
integer buffers preserved. The cache stays outside Git.

The pinned DA3 source imported one moved utility from its former package path.
The runner aliases the author's existing module. A tiny dropout-schedule
initializer uses CPU scalars during meta-device construction to avoid duplicate
model allocations; inference math and model parameters remain unchanged.

UniDepth conditions its point rays on a supplied camera but still returns its
camera-head prediction in the `intrinsics` output. The known-camera comparison
was corrected to use the supplied camera for FitTag geometry, and all six cases
were rerun. Only those corrected results are included in the table.

## Geometry, segmentation and original-file experiments

A known-depth control, using the generated scene's exact floor plane, produced
2.34% median error and 1.1 cm median absolute error. Its 90th-percentile error was
3.06 cm, but an inseam still missed by 10.7 cm. This is **not a LiDAR test**. It
shows a concrete landmark/mask failure that a better scale source cannot fix.

Three segmentation-cleaning settings were compared with that known depth.
Unblurred cleaning improved the median to 1.70% but worsened the maximum to
47.66%; gentler cleaning reached a 99.23% maximum error. Defaults remain unchanged.
A narrow persistent leg-gap test also showed why bridging six pixels can move
the crotch downward. A smaller gap is now an optional research parameter, not
the default or a claimed real-photo fix.

The HEIC inspector was tested on Pillow HEIF's public depth-bearing fixture. It
found a 768×576 depth layer and numeric focal metadata, while correctly leaving
absolute metric usability unverified. It was also tested on an actual encoded
HEIC without depth. No owner's original file was available, so no claim is made
about the depth stored in their failed photo.

An attempt to obtain independently measured real garments from
[MV-Fashion](https://huggingface.co/datasets/MV-Fashion/MV-Fashion) returned HTTP
401 for the observed measurement filenames. The dataset requires a signed
agreement and reviewed access. Its inventory being visible does not grant file
access. No identity submission, agreement or access request was made on the
owner's behalf.

## Reproduce and inspect

Check out the exact author source commits listed in
`tools/download_candidate_models.py` into an external work directory containing
`unidepth-source`, `da3-source/src` and `depthpro-source/src`. Use a separate local
ML environment; do not replace production requirements or download weights in a
request. The downloader pins model revisions and SHA-256 values.
The tested CPU runtime is recorded in `requirements-model-bench.txt`; it is not
the authors' GPU benchmark environment. Depth Pro's checkpoint has a
[research-only license](https://huggingface.co/apple/DepthPro/blob/main/LICENSE),
which excludes product development. Keep it out of the app and deployment.

```powershell
python -m pip install -r requirements-model-bench.txt
python -m tools.download_candidate_models C:\path\research-work
python -m tools.prepare_depthpro_fp32 C:\path\research-work\research-models\depthpro
python -m tools.probe_candidates unidepth --work C:\path\research-work
python -m tools.probe_candidates da3 --work C:\path\research-work
python -m tools.probe_candidates depthpro --work C:\path\research-work
```

Recorded results are in `validation/unidepth_buttonless_probe.json`,
`da3_buttonless_probe.json` and `depthpro_buttonless_probe.json`; source/model
revisions, hashes, resource use and each refused/accepted case remain visible.
The existing baselines are in `buttonless_baseline_400.json` and
`moge_buttonless_probe.json`. Generated depth/image caches stay outside Git.

The owner's next direction is rear LiDAR, with no Mac available. A locally
tested Record3D importer and camera-matrix geometry path now support a practical
export/import experiment. See [the one-garment trial](LIDAR_TRIAL.md). Actual
iPhone capture, archive compatibility and real garment accuracy remain to be
tested with an original `.r3d` file. A successful generated archive test cannot
stand in for that physical evidence.

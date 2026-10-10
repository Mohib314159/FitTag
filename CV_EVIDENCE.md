# Numbers that explain the user benefit

FitTag's intended benefit is less effort checking the dimensions of second-hand
clothes: capture once, inspect/correct the lines, keep a record, and copy a
measurement description. Actual reductions in listing time, returns or buyer
messages have **not** been measured. Do not claim them from this prototype.

## What can be demonstrated now

| Claim | Why it matters | Evidence and scope |
| --- | --- | --- |
| Five editable jeans measurements from one photo | A single capture produces an inspectable measurement sheet | Working local capture/API/result flow; scale may still need a known length or camera distance |
| No object placed beside the garment in this branch | Removes the printed-sheet/card/button requirement from capture | All three experimental routes; unanchored depth can be badly wrong, so this is a capture feature, not a measurement-accuracy claim |
| One supplied length anchors the other dimensions | Reduces the number of inputs needed to establish scale | Working correction/undo; four other jeans readouts follow from one known length. Does not prove an 80% time saving or remove the need to check the lines |
| About 2 seconds for shape/distance processing locally | Explains waiting after submitting a photo | Five local requests per mode: shape median 1.74 s; supplied-distance median 1.89 s. Excludes photographing, human review, Internet and Render wake-up |
| About 8 seconds for model processing locally | Sets a realistic expectation for the ML experiment | Five local requests: median 7.90 s, range 7.39–10.73 s. It is slower and its absolute scale is less defensible |
| 0.6 cm median error in non-anchor synthetic measurements | Quantifies geometric usefulness after supplying scale | 19 other landmarks across five accepted simulated captures; anchor excluded. Worst error about 5.5 cm. One of six captures was refused. **Not real-garment accuracy** |
| Bad scale can become proportions instead of a confident number | Reduces the risk of an unsupported size decision | Nonplanar/invalid-depth and contradictory-two-photo checks; no calibrated real-world false-accept/refusal rates exist yet |

Raw, reproducible sources: `validation/button_free_probe.json`,
`validation/button_free_latency.json`, `tools/probe_button_free.py`,
`tools/bench_free_capture.py`, and the API/client checks. Landmark errors are
correlated within a garment; 19 landmarks are not 19 independent users/garments.
The synthetic renderer and results contain no personal sizes or photos.

## A credible CV sentence now

Built a mobile garment-measurement PWA that turns a flat-lay photo into five
editable jeans measurements, with scale checks, local saving and copyable listing
text; explored reference-free depth estimation and added proportion-only fallback
when metric scale could not be defended.

If including a numerical evaluation result, retain its qualification:

Benchmarked known-length calibration on five accepted simulated captures,
achieving 0.6 cm median error across 19 non-anchor measurements; documented the
5.5 cm worst case and withheld measurements for unreliable captures.

Do not describe the model route as validated centimetre measurement, claim a
percentage reduction in returns/time, or claim active users that do not exist.
The older paper-reference photo agreement is repeatability, not absolute accuracy.

## How to obtain actual user-impact evidence

Run a paired pilot with consenting users doing the same task: prepare a
second-hand listing's measurements manually, then with FitTag. Randomize order
and use different but comparable garments to limit memory/learning effects.
Time from a laid-out garment to a **correct, checked, copyable** measurement
description. A fast incorrect readout is a failure, not a time saving.

Record completion time, successful correct sheets, retakes, corrections, critical
measurement error against independently checked tape ground truth, and cases
where the app should have refused but did not. Report the participant/garment
count, median paired time difference, error distribution and refusal rate. Keep
photos and personal dimensions private; aggregate only with participant consent.
Do not collect silent product telemetry merely to manufacture CV statistics.


## Local performance experiment

The optimized path reuses the initial outline and allows tuned CPU inference without duplicating model weights. In 27 warm Windows trials on one generated input (three per configuration), the previous repeated-outline path with one model thread had a 6.885 s median; the new path with four threads had a 3.778 s median. Two photos together/four threads had a 4.605 s median. A separate live API test, including first model load, polling and overlays, completed two photos in 8.47 s. These are developer processing benchmarks, not user task time saved or Render results. Do not claim an observed reduction in listing time, messages or returns.

A defensible feature statement: "Added on-device photo checks and a multi-item upload flow with individual editable measurement results; benchmarked CPU threading and bounded parallel inference while retaining conservative defaults for constrained hosting." Keep measurement uncertainty attached to any reference-free claim.

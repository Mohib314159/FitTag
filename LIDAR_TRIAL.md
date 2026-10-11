# One real garment, before a native app

The owner wants an Apple Measure-like capture that returns garment measurements
together. They have an iPhone 15 Pro Max and no Mac. The first step is a private
capture/import trial; no new native app or public service is needed to test it.

## Capture on the phone

Use [Record3D](https://apps.apple.com/gb/app/record3d-3d-videos/id1477716895).
Its listing offers three trial recordings, and the developer documents RGB-D
exports. Some features/export access may require an in-app purchase; availability
has not been checked on the owner's phone. The UK listing currently shows Full
Version at £4.99. Do not buy a Wi-Fi extension for this file-based test.

1. Select the **rear LiDAR** camera, not selfie/FaceID, a depth colour preview,
   or an AI depth mode.
2. Put one pair of jeans flat on a plain matte floor. Smooth the waistband and
   separate the legs. Leave visible floor around every edge.
3. Hold the camera nearly straight down, keep the entire garment visible, and
   record a short steady clip of about three seconds.
4. From the recording library, export the **raw `.r3d` recording** and share that
   file. A screenshot, MP4 or rendered 3D preview does not replace its calibrated
   depth data. The open-source [export reader's instructions](https://github.com/BernieZhu/RGBD-Video-iPhone)
   describe Library → Export → r3d → Share.
5. Independently measure flat waistband width and inseam with a tape. Keep the
   original recording and personal dimensions private; they will not be committed.

This is a test of whether the actual capture can support useful measurement. It
is not a request to create a full scan, walk around the garment or manually tap
every point in Apple's Measure app.

## What the prototype does

`tools.import_record3d` reads one synchronized JPEG, float32 metre-depth map and
confidence map directly from the ZIP container. It does not extract the archive
or read audio, identity fields or camera poses into the result. It checks image
sizes/orientation, confidence values, calibration and stream lengths. The local
decoder is optional; no public HTTP route or Render dependency was added.

`core.lidar_capture` uses the recorded full camera matrix, including separate
horizontal/vertical focal lengths and principal point. It fits a floor plane
only from valid, high-confidence samples surrounding the garment, rejects poor
coverage, an inconsistent plane or excessive tilt, and rectifies the retained
RGB garment mask with the existing geometry engine. Existing landmarks then
produce all supported measurement lines and centimetre values together.

Depth confidence concerns sensor readings, not the accuracy of an inseam or
waist landmark. Folded fabric and misplaced lines still require review. The
archive tests use generated inputs and actual LZFSE compression/decompression;
they do not establish accuracy on the owner's iPhone.

## Run privately on Windows

In a local environment with the existing FitTag dependencies:

```powershell
python -m pip install -r requirements-lidar-trial.txt
python -m tools.import_record3d C:\path\garment.r3d --rear-lidar --frame 0 --kind jeans --output C:\path\new-private-result
```

The output directory must be new. The command writes `result.json` and an actual
measurement overlay `measurements.jpg`. Do not put these private outputs inside
the Git repository. If the initial frame was captured before framing settled,
choose a later frame with `--frame`; it must use matching camera/depth data.

The current reader supports the documented video-frame layout (`metadata`,
`rgbd/<number>.jpg`, `.depth`, `.conf`). The app's newer high-resolution still
layout and other apps' export formats remain unverified. Keep the original file
if any field/layout fails so it can be inspected rather than inventing missing
calibration. This prototype is a local importer, not hardened public archive
ingestion and not a LiDAR capability added to Safari.

## Decide after the real test

Check the overlay endpoints before comparing independently measured lengths.
Record distance/plane failures separately from landmark failures. One capture
can demonstrate a useful path or reveal a blocker; it cannot justify a general
accuracy claim. If the import and primary measurements are useful, implement
the same capture contract in a small native component and reuse the PWA editor.
If they fail, fix that specific failure before spending time on another UI.

Primary format references: [Record3D developer library](https://github.com/marek-simonik/record3d),
[Nerfstudio's column-major camera reader](https://github.com/nerfstudio-project/nerfstudio/blob/main/nerfstudio/process_data/record3d_utils.py),
[Apple's LiDAR capture sample](https://developer.apple.com/documentation/AVFoundation/capturing-depth-using-the-lidar-camera).

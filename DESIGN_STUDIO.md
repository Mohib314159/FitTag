# Camera studio design experiment

Branch: `codex/fittag-camera-studio`, starting from `c4d4ac4`. The owner requested a completely new direction and explicitly said not to merge. This branch does not update the existing Render service or claim to improve measurement accuracy.

## What was actually studied

- [Apple Measure camera guide](https://support.apple.com/en-gb/guide/iphone/iphd8ac2cfea/ios): inspected the illustrated phone screen and manual endpoint interaction. The object occupies the canvas, measurements sit beside the object, and a small set of controls lives near the thumb. FitTag borrows that hierarchy, not Apple's native AR capability. This PWA still uses the existing photo engine.
- [Depop's published iPhone screens](https://apps.apple.com/gb/app/depop-buy-sell-clothes/id518684914) and [listing flow](https://depophelp.zendesk.com/hc/en-gb/articles/360032716413-How-to-list-an-item): inspected the listing screenshot, product photography and compact navigation. Clothing provides the visual interest; a photo starts an ordinary task. No Depop imagery, branding or commerce claims are used in FitTag.
- [Photoroom's published iPhone screens](https://apps.apple.com/gb/app/photoroom-ai-photo-editor/id1455009060): inspected background removal and resize screens, including controls below the canvas. Borrowed the separation between the photo and its immediate tools. Did not copy the purple marketing treatment or introduce image-generation controls.

Published screenshots are visual references, not evidence that the full apps were tested. The earlier Otherwise inspection is not used as a layout template.

## Working design

Capture opens as a camera tool. A short instruction sits above the viewfinder. The live frame or selected photo occupies most of the screen. A 74 px shutter is centred between Photos and Tips; supported garment types use a simple text selector. There is no headline campaign, generated clothing illustration, simulation switch or default example on the opening screen.

Photo settings, calibration mode, optional second photo, batch selection and installation sit in a native dialog sheet. The initial capture screen still says sizes are estimates. Selecting a photo exposes its quick quality check and a deliberate Read photo action. Taking a picture does not upload it.

Review is an editor: the first line is immediately selected, its size is attached to the photo caption, and Previous/Next controls move through the lines without needing to hunt for each endpoint. The full table is available under All measurements. Check size & save leads to the existing confidence, known-length and saving controls. Selecting an already selected measurement keeps it available for editing rather than unexpectedly removing its handles.

The waiting view uses the selected photo and actual backend stages. The old animated scan and decorative progress track are removed from this design; it does not invent completion percentages or imply that an animation is a live detection trace.

## Iteration and limits

1. First draft put the camera and controls on one screen. Phone review exposed clipped bottom copy. Reduced the viewport allocation so shutter, Photos, Tips and uncertainty text fit at 360 x 640, 390 x 844 and 430 x 932 without page scrolling.
2. Review initially required tapping a line before editing. Added first-line selection, bounded arrow navigation, selection-position feedback and scrolling the selected label into view. Kept endpoint keyboard/drag correction and the magnifier.
3. Small-phone review made the garment too small. Increased the photo's height allowance while retaining its original aspect ratio and alignment with the selectable SVG overlay. Results can scroll; the capture controls fit on the initial screen.
4. Returning from a secondary view now restarts an allowed camera when no photo is selected. If an older permission answer is still pending, the new intent waits for it, releases its stale stream and restarts once; leaving again cancels the queued restart. Settings closes before opening Batch. Tests model native dialog methods explicitly because the DOM test library does not supply them.

The permission waiting screen is still the least expressive state. A real camera image should give this interface its character; that is a design judgment, not a verified user preference. The in-app browser initially left the camera request pending and returned blocked access on a later reload. The fallback state was inspected; there is no claim of a physical-device camera pass. No private photos or personal garment sizes are published. Public generated example files are used only for regression checks and remain honestly labelled in the secondary walkthrough.

## Verification

- 64 Node client/camera/job/service-worker checks passed. New checks cover settings-to-batch navigation, ready-to-edit first selection, arrow boundaries, unit synchronization and returning to size review, late-permission restart and cancellation of a queued restart, and dismissing an error without losing the selected photo or uploading it.
- Targeted FastAPI asset/private-dataset check passed; the existing Starlette/httpx test adapter warning remains.
- Build, JavaScript syntax and whitespace checks passed. The offline shell includes the new stylesheet and the camera module.
- Browser: settings/help sheets, local pre-upload review, real HTTP measurement job, actual waiting stages and returned editable measurements, keyboard endpoint adjustment and known-length correction were exercised. No console errors/warnings were observed.
- Phone capture layouts: 360 x 640, 390 x 844 and 430 x 932. The capture controls fit; no horizontal overflow. Result image and SVG bounds agree within rounding. The same workflow was inspected at 1280 x 800 on desktop, with no horizontal overflow.
- Screenshots in the task's output folder use the public computer-made test image, not a personal garment. They are UI evidence only, not accuracy evidence.
- Not verified: physical iPhone camera, Safari OS installation, screen-reader acceptance or a Render deployment of this branch. Backend/model and hosting capacity were not changed.

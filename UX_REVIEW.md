# FitTag UI review · 10 October 2026

## What was actually studied

- [Depop seller page](https://www.depop.com/gb/sell/) and [published iPhone screenshots](https://apps.apple.com/gb/app/depop-buy-sell-clothes/id518684914): inspected at a phone width. The seller page includes a real app listing screen. Clothing imagery, strong type, short actions and a distinct identity make a sparse interface feel alive. FitTag borrows that clarity, not Depop's brand, marketplace feed or claims.
- [Photoroom's published iPhone screens](https://apps.apple.com/us/app/photoroom-ai-photo-editor/id1455009060): inspected visually. The object and editing action remain central; the result is understandable from the image. FitTag keeps its own photo and correction controls central, without copying the purple palette or generating replacement user photos.
- [Apple Measure camera screen and instructions](https://support.apple.com/en-gb/guide/iphone/iphd8ac2cfea/ios): inspected visually. Numbers attach to the measured object, and endpoint placement is an action rather than an illustration. FitTag uses photo-side selection and a selected measurement caption. It does not claim Apple's AR/depth sensing or equivalent accuracy.
- [Vinted's App Store page](https://apps.apple.com/gb/app/vinted-shop-sell-pre-loved/id632064380) failed in the current browser pass. Earlier repository design notes record the previous successful published-screen study. Otherwise's earlier inspection remains relevant to friendliness and feedback, not a fixed layout to copy.

These are public published interfaces and screenshots. This is not a claim to have tested authenticated native seller flows or conducted research with users.

## Problems and changes

| Problem in the previous revision | Current response | What to check |
| --- | --- | --- |
| Grey artwork and equal-weight controls gave little reason to explore | Warm paper, denim stitches, red measuring mark, stronger headline and a coherent tag identity | Clothing should dominate, without decorative gradients or a feature wall |
| The empty photo box asked people to imagine the result | Photo/Lines illustrated preview plus an immediately accessible actual example | No invented measurement numbers in the guide; example remains labelled |
| Garment choice felt like a settings form | Two clear garment buttons; optional geometry/camera settings remain disclosed | Buttons must change both the guidance and real form data |
| Measurement rows were far below the phone photo | A horizontally scrollable measurement picker above the image, with selected size in its caption | Selection, endpoint corrections and unit changes must stay synchronized |
| Saving led to an unstructured list near the footer | Dedicated saved view, names, units, source/scale status, copy and reversible removal | Device-only storage; no images, and no undo that destroys a newer save |
| The completed batch retained a large disabled action | Hide Read once every result is complete; renamed items appear in the list | Errors remain retryable; successful results and edits survive |
| Example reading could inherit unrelated choices | Reset garment/method/FOV for the public jeans input; clear a stale second photo on primary replacement | A tutorial must not accidentally upload a previously selected second item |
| Clothing guide switching looked correct in a DOM simulation but not in a browser | Use the SVG hidden attribute explicitly | T-shirt and jeans artwork now actually switch in the browser |
| Copying always used cm even when inches were selected | Copy and save retain selected units; scale limitations travel with the text | Proportions stay percentages, never fake inches |

## Interactions and scope

The first task remains one photo. Camera/library selection, local quality checks, deliberate upload, real processing stages, cancellation and editable results remain functional. Multiple photos remain a secondary path with configurable server capacity. The waiting view uses the selected photo and actual backend stages; it does not invent a percentage or imply that its scanning animation is a detection trace.

A supplied measurement sets size, but it does not prove the other dimensions. The reference-free scale is still experimental. Improving its interface is not evidence that its estimates are accurate. Public example imagery is computer-made; personal sizes and photos are excluded from screenshots and assets.

## Verification boundaries

Client checks exercise actual handlers for preview switching, garment choice, photo-side selection, endpoint editing, unit conversion, save/copy/remove/undo, stale-state protection and tutorial reset. The browser checks the rendered guides, demo correction, saved example, undo, live example processing and phone layouts. Test counts are engineering evidence, not user-impact statistics.

A browser-sized viewport does not verify Safari, native camera behavior, screen-reader experience or OS installation. Render latency remains unmeasured on that host. No fresh native file chooser is used in this iteration because the available automation previously stalled even with short timeouts.

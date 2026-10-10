# Product design decisions

## Button-free branch iteration

The initial experiment reused too much landing-page structure: a slogan, a large
illustration and several paragraphs before the task. The user rejected that as
generic. The revised UI opens on clothing capture, with a quieter heading,
clickable photo area, short labels and thumb-reachable actions. Optional capture
guidance, a second photo and camera assumptions are disclosed separately.

Otherwise was inspected through its live service, `web/index.html`, shared,
landing and mobile styles at GitHub commit `b92affd`. It is a benchmark for
clarity and task feedback, not a layout or brand to copy.

Additional primary reference study:

- [Vinted's published iPhone screens](https://apps.apple.com/gb/app/vinted-shop-sell-pre-loved/id632064380): clothing/photos first, short fields and a clear seller action. Its image presentation was inspected in the browser; no authenticated sale was created.
- [Depop's seller flow](https://depophelp.zendesk.com/hc/en-gb/articles/360032716413-How-to-list-an-item) and [editable generated listing workflow](https://news.depop.com/depop-launches-ai-powered-listing-from-one-photo/): start with a photo, retain control over generated output, save drafts. The App Store page failed to load, so a current native Depop screen is not claimed as inspected.
- [Google PhotoScan](https://www.google.com/photos/scan/) and [its scan/edit instructions](https://support.google.com/photos/answer/7177983?hl=en-GB): visual guidance for the next capture action and correction after processing. The published demonstration page was inspected.
- [Apple Measure](https://support.apple.com/guide/iphone/measure-dimensions-iphd8ac2cfea/27/ios/27): place/check endpoints, attach numbers to the object. Native AR sensing is not a capability we copy into the PWA.
- [magicplan capture guidance](https://help.magicplan.app/scan-a-room-in-seconds-using-lidar) and [editing](https://help.magicplan.app/magicplan-floor-plan-editor-faq): immediate capture feedback, undo and accessible numeric correction.
- [Saisun's official garment screenshots](https://shopkoyomi.com/app/saisun/?lang=en): actual capture and measurement screens inspected. Photographic evidence dominates; its QR calibration and accuracy marketing are not adopted as FitTag claims.
- [Polycam's measurement interaction](https://learn.poly.cam/hc/en-us/articles/29647317758100-How-to-Measure-Your-Captures): select a point/line and read its value, with mode-specific capability boundaries.

FitTag now supports selecting a line on the photo or table, dragging its
endpoints with a magnified view, keyboard adjustment, restoring original lines,
and rechecking after an edit. Editing never upgrades an unvalidated scale into
validated measurement. A supplied anchor is reapplied to corrected geometry.
Saved clothes are reachable from the header, may have a local name, and never
contain uploaded photos. Copyable listing text carries scale limitations with it.

The typography, spacing and limited green accent support the controls; there is
no borrowed marketplace feed, fake stock, brand imitation or invented social
proof. Research informed task-level changes rather than copying a marketing
page. The new visual direction is implemented and locally checked, not yet
user-accepted or physically tested on a phone.

## Earlier hardware build

Before changing the interface, the existing live FitTag demo and recent repository history were inspected. Its useful identity was the warm paper/ink palette, yellow measuring-tape rule, photo-to-lines-to-results relationship and honest error bars. Those remain.

Reference study: [Linear's product hierarchy](https://linear.app/features), [Stripe's product presentation](https://stripe.com/payments), and [Apple's camera flow](https://support.apple.com/en-gb/guide/iphone/iph263472f78/ios). The borrowed principles are restrained typography, stable alignment, a single strong action, immediate preview, progressive disclosure and short recovery instructions. Brand colours and decorative styles were not copied.

FitTag has three focused states: capture, processing and result. The main screen puts the garment ahead of feature marketing. The phone action area stays within reach; the fallback reference settings live in a disclosure. Native camera capture reduces permission friction. Result rows highlight their corresponding line instead of relying on hover or unreadable labels baked into a photo. Confidence appears beside measurements, before save/compare actions.

Borders and spacing do the grouping. Corner radii are modest. There are no gradients, animated backgrounds or dashboard ornaments. Motion is limited to a processing indicator and respects reduced-motion preferences. Controls have visible keyboard focus, native labels and generous tap targets. Validation evidence and local saved history remain available without dominating the measurement task.

New photos are explicitly uploaded after review. Detected hardware remains an assumption until visually confirmed; checking an overlay does not turn its uncertainty into proven accuracy. The synthetic example is labelled throughout.


## Phone and waiting refinement

The user rejected the muted green treatment. The experimental app now uses white, neutral grey and black actions, with a small coral activity accent. It borrows the restraint and photo-first task rhythm of consumer resale apps, not their logos, feeds or brand palettes. Revisited the live [Vinted storefront](https://www.vinted.co.uk/) in the browser: product photos lead, short ordinary labels and clearly ranked actions do the work. App Store screenshot pages returned an error in this pass, so this revision does not claim a new native-app inspection. The earlier published Vinted screenshots and Depop's documented editable listing flow remain the reference evidence above.

On phones the capture/read action stays at the bottom within thumb reach, with safe-area padding and 52 px controls. Garment choice stays visible; scale, second-photo and focal-length settings share one disclosure. Native inputs remain 16 px to avoid unwanted iOS zoom. Photo tips remain accessible after selection. The result explains how to select a line and drag its endpoints.

Waiting shows the selected garment, quiet activity, three coarse steps, short actual server-stage messages, cancel and a delayed slow-service explanation. No fake percentage or timed "successful" detection claims. Reduced motion keeps a static activity indicator. Focus and live status labels support keyboard and assistive use. The header's unrelated actions, saved section and footer hide while waiting. Architecture and operational limits are recorded in [SYSTEM_DESIGN.md](SYSTEM_DESIGN.md).

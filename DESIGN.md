# Product design decisions

Before changing the interface, the existing live FitTag demo and recent repository history were inspected. Its useful identity was the warm paper/ink palette, yellow measuring-tape rule, photo-to-lines-to-results relationship and honest error bars. Those remain.

Reference study: [Linear's product hierarchy](https://linear.app/features), [Stripe's product presentation](https://stripe.com/payments), and [Apple's camera flow](https://support.apple.com/en-gb/guide/iphone/iph263472f78/ios). The borrowed principles are restrained typography, stable alignment, a single strong action, immediate preview, progressive disclosure and short recovery instructions. Brand colours and decorative styles were not copied.

FitTag has three focused states: capture, processing and result. The main screen puts the garment ahead of feature marketing. The phone action area stays within reach; the fallback reference settings live in a disclosure. Native camera capture reduces permission friction. Result rows highlight their corresponding line instead of relying on hover or unreadable labels baked into a photo. Confidence appears beside measurements, before save/compare actions.

Borders and spacing do the grouping. Corner radii are modest. There are no gradients, animated backgrounds or dashboard ornaments. Motion is limited to a processing indicator and respects reduced-motion preferences. Controls have visible keyboard focus, native labels and generous tap targets. Validation evidence and local saved history remain available without dominating the measurement task.

New photos are explicitly uploaded after review. Detected hardware remains an assumption until visually confirmed; checking an overlay does not turn its uncertainty into proven accuracy. The synthetic example is labelled throughout.

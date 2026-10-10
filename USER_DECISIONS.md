# Decisions from the FitTag conversation

This records Mohib's directions and preferences, separately from implementation choices made by the assistant. It is a working product brief, not a list of claims that have been validated. Updated 10 October 2026.

## Product and measurement

- Build a working installable PWA, not just a mockup. It should work well on a phone and be easy to demonstrate to a recruiter in under a minute.
- Keep the existing Python/OpenCV/FastAPI engine. Do not rewrite the technical core without a useful reason.
- Main-product jeans flow: ordinary phone photo, using standardized garment hardware such as a tack button where supported. Do not foreground the stale printed four-ArUco-sheet process. Keep older calibration modes documented as fallback/development paths.
- Experiment with no reference object at all. Mohib explicitly confirmed this means no button, paper, card or other reference in the image. Explore ML and other ideas creatively, while keeping confidence and correction honest.
- Protect personal jeans sizes and identifying garment details. Do not expose them in public demos, screenshots or docs.
- Keep evidence of independent real-garment photo agreement and the 17.0 mm tack-button recovery, without implying that evidence validates the reference-free experiment.

## Interaction and design

- Treat UI as product design. Study real interfaces and interactions, including Vinted, Depop, Otherwise, Apple camera flows and other excellent consumer apps. Otherwise is a reference for friendliness, not a requirement to copy its evidence-canvas/panel layout.
- Avoid generic AI/SaaS styling: gradients, glows, arbitrary purple/blue, excessive pills, oversized rounded cards, animated dashboards and long explanations.
- Mohib rejected the muted green treatment. Use a more intentional palette and continue improving spacing, hierarchy, empty/error/waiting states and phone ergonomics.
- Use normal, concise language. In particular, avoid repeatedly foregrounding technical language such as "simulated" in the main flow. Preserve truthful example provenance in clear everyday words.
- Keep the introduction focused on one photo. Support both taking a new photo and choosing an existing one.
- Also support choosing several photos/items, with parallel processing where resources make it useful. Do not confuse different items with the optional second capture of the same item used for a scale check.
- Catch obvious bad-photo problems promptly, before wasting time on slow inference. Do not claim a quick check guarantees measurement quality.
- Make waiting pleasant, but improve or remove unnecessary waiting where possible. The exact approach is up to the assistant.
- Include a demo of how to use the app, not just a technical counterexample.
- Continue iterating on small and larger problems; these examples are not an exhaustive feature checklist.

## Engineering, deployment and publication

- Deploy the full app as one straightforward Render service, with the Python backend serving the PWA. Include Dockerfile, root `render.yaml`, configuration and realistic deployment docs.
- Use normal Git commit/push through this computer's existing Git Credential Manager. Stop uploading files individually through the browser. Diagnose exact errors, request network access when needed, and never expose credentials or overwrite existing work.
- Earlier authorization permitted updates to the existing FitTag repo/main for the completed hardware PWA. For the reference-free experiment, create a new branch and **do not merge it yet**. Continue publishing improvements on `codex/fittag-button-free`.
- A strict one-photo processing limit is acceptable when Render cannot keep up. It is not a permanent product requirement: investigate threading/parallel techniques and measure the result, as with Otherwise. Do not silently upgrade to a paid plan or claim local speed as Render speed.
- Research and implement system-design techniques when they solve actual problems. Keep the service practical for constrained hosting.
- Run useful tests and local checks. Distinguish local/browser success from uncompleted container, production, camera/device and OS-install verification.
- Keep communicating about findings and exact blockers. Work autonomously within the authorized scope rather than repeatedly handing routine steps back to Mohib.

## Evidence and CV

- Prefer numbers that explain what users can do and the benefit to them. Do not turn test counts or arbitrary implementation statistics into supposed user impact.
- Do not invent users, time saved, returns avoided or real-garment accuracy. Separate generated-image experiments from real-garment evidence and actual user studies.
- Exclude the measurement supplied as a scale anchor from corrected-error scores; it is correct by construction. Report other measurements and material worst cases, not just a flattering median.

## Current assistant choices, open to revision

- Up to six photos in a browser-held selection, with individual checks/results and removal, stop and retry. This limit is an implementation choice, not a user-specified number.
- CPU thread count is configurable from one to four; measurement capacity from one to two. Free Render defaults stay at one/one. A better-resourced deployment can opt into tested parallel settings after checking memory and latency.
- Quick photo checks run on-device. Geometry still checks framing/outline before invoking the depth model. Ambiguous client checks warn or leave manual review available.
- The walkthrough uses a public computer-made example with a known size; no personal garment data. It teaches checking/editing lines and supplying a known measurement.

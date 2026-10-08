"""Phone orchestration over the existing calibration and silhouette engines.

Hardware-only capture is a conservative near-overhead estimate, not a full
homography. The experimental stitch scale field remains in markerless.py; a
single disc cannot determine a plane's complete perspective transformation.
"""
import cv2
import numpy as np

from core.flatlay import garment_mask, largest_contour, rotate, waistband_tilt
from core.markerless import find_button, refine_disc, scale_from_button
from core.measure import measure
from core.segment import contrast, contrast_check, touches_border


def hardware_measure(photo, diameter_mm=17.0, known_diameter=False):
    mask = garment_mask(photo)
    contour = largest_contour(mask) if mask is not None else None
    if contour is None or cv2.contourArea(contour) < photo.shape[0] * photo.shape[1] * .08:
        raise ValueError("Couldn't find the jeans. Use a plain contrasting background and even light.")
    if touches_border(contour, photo.shape):
        raise ValueError("The garment reaches the photo edge. Include the whole waistband and both hems.")
    status, message = contrast_check(contrast(photo, mask))
    if status == "refuse":
        raise ValueError(message)
    x, y, w, h = cv2.boundingRect(contour)
    # Restrict candidates to the waistband, not rivets at the hems or floor highlights.
    ellipse = find_button(photo, roi=(x, y, w, max(30, int(h * .18))),
                          px_band=(8, .045 * max(photo.shape[:2])))
    if ellipse is None:
        raise ValueError("No clear tack button found. Retake with the button visible and sharp, or choose a known-reference fallback.")
    ellipse = refine_disc(photo, ellipse)
    cx, cy = ellipse[0]
    # Metal is deliberately unlike fabric; colour segmentation may cut a notch
    # from the top edge at the button. Require nearby fabric rather than the
    # centre pixel itself to be foreground.
    radius = max(3, int(ellipse[1][1] * .75))
    nearby = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * radius + 1, 2 * radius + 1)))
    if not (0 <= cx < photo.shape[1] and 0 <= cy < photo.shape[0]) or nearby[int(cy), int(cx)] == 0:
        raise ValueError("The candidate button is outside the garment. Retake on a plain background.")
    scale = scale_from_button(ellipse, diameter_mm, .02 if known_diameter else .14)
    if scale.tilt_deg > 20:
        raise ValueError("The button looks too tilted for hardware-only scale. Hold the camera directly overhead, or use a paper reference for perspective correction.")
    angle = waistband_tilt(mask)
    if abs(angle) > 20:
        raise ValueError("Place the waistband at the top of the photo and straighten the jeans.")
    rect, mask = rotate(photo, angle, (255, 255, 255)), rotate(mask, angle)
    # Belt loops, shadows and rounded corners can create a few narrow rows above
    # the actual waistband. Start at the first sustained wide row, keeping the
    # existing core.measure rules for the rest of the garment.
    ys = np.flatnonzero(mask.any(axis=1))
    top, bottom = int(ys[0]), int(ys[-1])
    band_end = min(bottom, top + max(10, int((bottom - top) * .08)))
    widths = []
    for yy in range(top, band_end):
        xs = np.flatnonzero(mask[yy])
        widths.append(int(xs[-1] - xs[0]) if xs.size else 0)
    threshold = .85 * float(np.percentile(widths, 75))
    for offset in range(max(0, len(widths) - 3)):
        if all(value >= threshold for value in widths[offset:offset + 3]):
            mask[:top + offset] = 0
            break
    contour = largest_contour(mask)
    if contour is None or touches_border(contour, mask.shape):
        raise ValueError("Straightening cropped the garment. Leave more space around it and retake.")
    rows = measure(contour, "jeans", scale.mm_per_px)
    if len(rows) < 5:
        raise ValueError("Couldn't separate both legs. Lay them flat with a visible gap and retake.")
    by_name = {r.name: r for r in rows}
    if not .60 <= by_name["waist_flat"].value_cm / max(by_name["hip_flat"].value_cm, 1) <= 1.25:
        raise ValueError("The waistband outline looks unreliable. Smooth it flat and retake on a contrasting surface.")
    # Preserve core landmark geometry; don't claim overlap-crease precision from an
    # unrectified image. Prior uncertainty is systematic and never averaged away.
    for row in rows:
        row.tolerance_cm = round(max(row.tolerance_cm, row.value_cm * max(.10, scale.rel_error)), 1)
    notes = [scale.as_note, "Hardware estimate; single reference, unchecked. Confirm the highlighted disc is the tack button.",
             "Near-overhead scale only; no full perspective correction. Button sizes vary and errors can exceed the displayed uncertainty.",
             "Inseam follows the silhouette split. Overlapping legs can underestimate it; verify with a tape measure."]
    if status == "warn":
        notes.append(message)
    # Overlay the exact detected disc in the same rotated coordinate system.
    marked = photo.copy()
    cv2.ellipse(marked, ellipse, (0, 130, 255), 3, cv2.LINE_AA)
    marked = rotate(marked, angle, (255, 255, 255))
    return marked, rows, scale.mm_per_px, notes

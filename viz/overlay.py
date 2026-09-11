"""Draw measurements onto the rectified image — the seller/buyer sees exactly which
line each centimetre came from. This is the 'measured fit is auditable' visual.
"""

from __future__ import annotations

import cv2
import numpy as np

from core.contracts import GarmentMeasurement


def draw_measurements(rectified: np.ndarray, garment: GarmentMeasurement) -> np.ndarray:
    img = rectified.copy()
    for m in garment.measurements:
        p1 = tuple(map(int, m.p1)); p2 = tuple(map(int, m.p2))
        cv2.line(img, p1, p2, (0, 180, 0), 3)
        for p in (p1, p2):
            cv2.circle(img, p, 6, (0, 140, 255), -1)
        mid = ((p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2)
        label = f"{m.name}: {m.value_cm:.1f}+/-{m.tolerance_cm:.1f}cm"
        org = (mid[0] + 8, mid[1] - 8)
        cv2.putText(img, label, org, cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 5)
        cv2.putText(img, label, org, cv2.FONT_HERSHEY_SIMPLEX, 0.7, (20, 20, 20), 2)
    return img

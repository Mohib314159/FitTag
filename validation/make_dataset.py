"""Generate a validation dataset. For REAL validation, replace these synthetic photos
with real flat-lay photos of garments shot on the mat, and put your TAPE-MEASURED numbers
in ground_truth.csv. Here we seed it synthetically (known truth) to exercise the harness.

    python -m validation.make_dataset
"""

from __future__ import annotations

import csv
from pathlib import Path

import cv2

from tests.synth import make_tshirt_photo, make_jeans_photo

HERE = Path(__file__).resolve().parent
PHOTOS = HERE / "photos"
COLS = ["length", "pit_to_pit", "shoulder_width", "sleeve_length", "hem_width",
        "waist_flat", "hip_flat", "inseam", "thigh", "leg_opening"]


def main():
    PHOTOS.mkdir(exist_ok=True)
    rows = []
    specs = [
        ("tee_a", "t-shirt", lambda: make_tshirt_photo(tilt=0.08)),
        ("tee_b", "t-shirt", lambda: make_tshirt_photo(tilt=0.13, bw=480, bl=640, sw=190, sl=110)),
        ("tee_c", "t-shirt", lambda: make_tshirt_photo(tilt=0.05, bw=560, bl=740, sw=220, sl=130, taper=6)),
        ("jeans_a", "jeans", lambda: make_jeans_photo(tilt=0.08)),
        ("jeans_b", "jeans", lambda: make_jeans_photo(tilt=0.12, waist=360, inseam=540, leg_open=150)),
        ("jeans_c", "jeans", lambda: make_jeans_photo(tilt=0.06, waist=500, inseam=700, leg_open=220)),
    ]
    for name, gtype, fn in specs:
        photo, gt = fn()
        fp = PHOTOS / f"{name}.png"
        cv2.imwrite(str(fp), photo)
        row = {"photo": f"{name}.png", "garment_type": gtype}
        for c in COLS:
            row[c] = gt.get(c, "")
        rows.append(row)

    with open(HERE / "ground_truth.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["photo", "garment_type"] + COLS)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} photos + ground_truth.csv")


if __name__ == "__main__":
    main()

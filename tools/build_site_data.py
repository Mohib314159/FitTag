"""Run the real FitTag engine on the sample photos and write what the website shows.

The site (docs/) is static: nothing is faked in the browser. Every number on it comes from
this script running core/ on the photos in validation/scenes/.

    python -m validation.render_scene     # (re)make the simulated photos
    python -m tools.build_site_data       # -> docs/data/samples.json + images
"""
from __future__ import annotations

import json
from pathlib import Path

import cv2

from core.calibrate import calibrate
from core.segment import segment_auto, largest_contour
from core.classify import classify
from core.measure import measure
from core.sizing import estimate_size

ROOT = Path(__file__).resolve().parent.parent
SCENES = ROOT / "validation" / "scenes"
DOCS = ROOT / "docs"
IMG = DOCS / "img"
MM_PER_PX = 0.5
WEB_W = 700                     # width of images shipped to the site


def run(photo):
    cal = calibrate(photo, mm_per_px_out=MM_PER_PX)
    if not cal.ok:
        return None
    mask = segment_auto(cal.rectified, marker_size_mm=cal.marker_size_mm, mm_per_px=cal.mm_per_px)
    contour = largest_contour(mask)
    gtype, category, src = classify(image_bgr=cal.rectified, contour=contour)
    ms = measure(contour, gtype, cal.mm_per_px, tol_scale=cal.tol_scale)
    return cal, contour, gtype, category, src, ms


def main():
    IMG.mkdir(parents=True, exist_ok=True)
    meta = json.loads((SCENES / "scenes.json").read_text())
    out = []
    for m in meta:
        photo = cv2.imread(str(SCENES / f"{m['name']}.jpg"))
        res = run(photo)
        if res is None:
            print(m["name"], "calibration failed"); continue
        cal, contour, gtype, category, src, ms = res
        R = cal.rectified
        s = WEB_W / R.shape[1]
        # outline of what the engine thinks is the garment (for the "silhouette" view)
        eps = 0.002 * cv2.arcLength(contour, True)
        poly = cv2.approxPolyDP(contour, eps, True).reshape(-1, 2)
        ph = cv2.resize(photo, (WEB_W, int(photo.shape[0] * WEB_W / photo.shape[1])), interpolation=cv2.INTER_AREA)
        rc = cv2.resize(R, (WEB_W, int(R.shape[0] * s)), interpolation=cv2.INTER_AREA)
        cv2.imwrite(str(IMG / f"{m['name']}-photo.jpg"), ph, [cv2.IMWRITE_JPEG_QUALITY, 82])
        cv2.imwrite(str(IMG / f"{m['name']}-flat.jpg"), rc, [cv2.IMWRITE_JPEG_QUALITY, 82])
        gt = m["ground_truth_cm"]
        meas = []
        for x in ms:
            t = gt.get(x.name)
            meas.append({"name": x.name, "cm": round(float(x.value_cm), 1), "tol": float(x.tolerance_cm),
                         "truth": t, "err": None if t is None else round(float(x.value_cm) - t, 1),
                         "p1": [round(x.p1[0] * s, 1), round(x.p1[1] * s, 1)],
                         "p2": [round(x.p2[0] * s, 1), round(x.p2[1] * s, 1)]})
        out.append({
            "id": m["name"], "caption": m["caption"], "type": gtype, "category": category,
            "type_source": src, "mode": cal.mode, "markers": cal.n_markers,
            "photo": f"img/{m['name']}-photo.jpg", "flat": f"img/{m['name']}-flat.jpg",
            "flat_size": [rc.shape[1], rc.shape[0]], "photo_size": [ph.shape[1], ph.shape[0]],
            "outline": [[round(float(a) * s, 1), round(float(b) * s, 1)] for a, b in poly],
            "measurements": meas,
            "size": estimate_size(gtype, {x.name: x.value_cm for x in ms}),
            "camera": m["camera"],
        })
        print(m["name"], gtype, cal.mode, [(x["name"], x["cm"], x["truth"]) for x in meas])
    (DOCS / "data").mkdir(exist_ok=True)
    (DOCS / "data" / "samples.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()

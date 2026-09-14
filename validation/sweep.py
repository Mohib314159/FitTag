"""Stress test: how far can you push the photo before the measurements go wrong?

Renders simulated photos (validation/render_scene.py) while varying one thing at a time:
camera tilt, how carefully the sheets were placed, missing sheets, and backdrop colour.
Runs the full engine on each and records the error against the known true dimensions.

    python -m validation.sweep            # ~5 min on 2 cores -> docs/data/sweep.json
"""
from __future__ import annotations

import json
import time
from multiprocessing import Pool
from pathlib import Path

import cv2

from validation import render_scene as R
from core.calibrate import calibrate, calibrate_by_card
import numpy as np
from core.segment import segment_auto, largest_contour, contrast, contrast_check
from core.classify import classify
from core.measure import measure

ROOT = Path(__file__).resolve().parent.parent
BASE = {s["name"]: s for s in R.SCENES}


def case(group, label, base, seed, **over):
    spec = dict(BASE[base])
    cam = dict(spec["camera"])
    cam.update(over.pop("camera", {}))
    spec.update(over, camera=cam, seed=seed)
    return {"group": group, "label": label, "garment": base, "spec": spec}


def cases():
    out = []
    for pitch in (0, 10, 20, 30, 40, 50):
        for i, g in enumerate(("jeans-charcoal", "jeans-midwash", "tee-burgundy")):
            out.append(case("tilt", f"{pitch}°", g, 100 + pitch + i,
                            camera={"pitch_deg": pitch, "roll_deg": [3, -4, 2][i], "yaw_deg": [2, -3, 4][i]}))
    for j in (0, 5, 10, 20):
        out.append(case("placement", f"±{j} mm", "jeans-charcoal", 200 + j, jitter=float(j)))
    out.append(case("sheets", "3 of 4 sheets", "jeans-midwash", 301, missing=(2,)))
    out.append(case("sheets", "2 of 4 sheets", "jeans-midwash", 302, missing=(1, 3)))
    out.append(case("sheets", "1 of 4 sheets", "jeans-midwash", 303, missing=(1, 2, 3)))
    # (paper mode has its own harness — validation/paper_mode.py — because it needs the box
    # the user would drag, and faking that with a threshold tests the threshold, not the method)
    # markerless: a bank card is the only thing of known size in the picture
    for pitch in (8, 22):
        out.append(case("card", f"bank card only, {pitch}° tilt", "jeans-charcoal", 600 + pitch,
                        card=True, missing=(0, 1, 2, 3),
                        camera={"pitch_deg": pitch, "height_mm": 1250.0, "out_size": (2268, 3024)}))
    out.append(case("lens", "phone lens left uncorrected", "jeans-charcoal", 500,
                    camera={"k1": 0.06}))
    out.append(case("lens", "strong barrel distortion", "jeans-charcoal", 501,
                    camera={"k1": 0.14}))
    for name, rgb in (("light grey sheet", (214, 216, 219)), ("beige carpet", (150, 170, 190)),
                      ("mid-grey floor", (120, 118, 116)), ("dark floor", (70, 68, 66))):
        out.append(case("backdrop", name, "jeans-charcoal", 400 + len(out), backdrop=rgb))
    for i, c in enumerate(out):
        c["idx"] = i
    return out


def run_case(c):
    R.set_margin(350)
    t0 = time.time()
    photo, _, gt, _ = R.render(c["spec"])
    t1 = time.time()
    res = {k: c[k] for k in ("group", "label", "garment")}
    thumb = ROOT / "docs" / "img" / "sweep" / f'{c["idx"]:02d}.jpg'
    thumb.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(thumb), cv2.resize(photo, (270, 360), interpolation=cv2.INTER_AREA), [cv2.IMWRITE_JPEG_QUALITY, 72])
    res["thumb"] = f'img/sweep/{c["idx"]:02d}.jpg'
    res["truth"] = gt
    if c["spec"].get("paper"):
        from core.markerless import find_rectangle
        from core.calibrate import calibrate_by_paper
        g = cv2.cvtColor(photo, cv2.COLOR_BGR2GRAY)
        dark = cv2.morphologyEx((cv2.GaussianBlur(g, (0, 0), 3) < np.percentile(g, 22)).astype(np.uint8) * 255,
                                cv2.MORPH_OPEN, np.ones((25, 25), np.uint8))
        cs, _ = cv2.findContours(dark, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        box = cv2.boxPoints(cv2.minAreaRect(max(cs, key=cv2.contourArea))) if cs else None
        cal = calibrate_by_paper(photo, corners=find_rectangle(photo), garment_box_px=box)
    elif c["spec"].get("card"):
        cal = calibrate_by_card(photo)
    else:
        cal = calibrate(photo, mm_per_px_out=0.5)
    res["mode"], res["markers"] = cal.mode, cal.n_markers
    if not cal.ok:
        res.update(ok=False, why="no markers found")
        return res
    mask = segment_auto(cal.rectified, marker_size_mm=cal.marker_size_mm, mm_per_px=cal.mm_per_px,
                        prior=getattr(cal, "prior", None))
    contour = largest_contour(mask)
    if contour is None:
        res.update(ok=False, why="garment not found")
        return res
    filled = np.zeros_like(mask)
    cv2.drawContours(filled, [contour], -1, 255, cv2.FILLED)
    cval = contrast(cal.rectified, filled)
    status, _ = contrast_check(cval)
    res["contrast"], res["contrast_status"] = round(cval, 1), status
    # measure as the known type (the app lets the user pick jeans / t-shirt), and separately
    # record whether the automatic shape-based guess would have got it right
    true_type = "jeans" if c["spec"]["kind"] == "jeans" else "t-shirt"
    guess, _, _ = classify(image_bgr=cal.rectified, contour=contour)
    gtype = true_type
    res["type_guess_ok"] = (guess == true_type)
    ms = measure(contour, gtype, cal.mm_per_px, tol_scale=cal.tol_scale)
    errs = []
    for m in ms:
        if m.name in gt:
            errs.append({"name": m.name, "cm": round(float(m.value_cm), 1), "truth": gt[m.name],
                         "err": round(float(m.value_cm) - gt[m.name], 1), "tol": float(m.tolerance_cm)})
    res.update(ok=True, type=gtype, errors=errs,
               max_abs_err=max(abs(e["err"]) for e in errs) if errs else None,
               within=sum(abs(e["err"]) <= e["tol"] for e in errs), n=len(errs),
               engine_s=round(time.time() - t1, 1))
    print(f'{c["group"]:<9} {c["label"]:<16} {c["garment"]:<15} {res["mode"]:<6} '
          f'{res["within"]}/{res["n"]} max|err|={res["max_abs_err"]} guess_ok={res["type_guess_ok"]}', flush=True)
    return res


def main():
    cs = cases()
    with Pool(2) as p:
        results = p.map(run_case, cs, chunksize=1)
    out = ROOT / "docs" / "data" / "sweep.json"
    out.write_text(json.dumps(results, indent=1))
    ok = [r for r in results if r.get("ok")]
    print(f"\n{len(ok)}/{len(results)} photos measured; "
          f"{sum(r['within'] for r in ok)}/{sum(r['n'] for r in ok)} measurements inside their error bars")


if __name__ == "__main__":
    main()

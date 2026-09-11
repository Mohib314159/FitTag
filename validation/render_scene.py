"""Render realistic *simulated* phone photos of garments on the printed FitTag kit.

The older harness (tests/synth.py) draws a flat red polygon on white paper. That proves the
geometry but says nothing about real photos. This script builds a harder scene:

  - a light bedsheet with wrinkles and uneven lighting as the backdrop
  - the four real A4 corner sheets from print/ laid out as the placement guide says,
    each nudged by a few mm (people don't tape perfectly)
  - a garment with a curved silhouette, fabric texture, seams, fading and a drop shadow
  - a handheld camera: tilted, slightly rotated, lens vignetting, sensor noise, JPEG

Ground truth comes from the garment's design dimensions (in mm), measured the way a person
with a tape measure would. The pipeline only ever sees the photo.

It is still simulated — a real photo of a real garment is the test that matters.

    python -m validation.render_scene        # -> validation/scenes/*.jpg + scenes.json
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import cv2
import numpy as np

from core.calibrate import MAT_MM

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = HERE / "scenes"

PX = 0.5                                  # scene raster: mm per pixel
MARGIN = 700.0                            # backdrop around the mat (mm), wide enough that the camera never sees past it
SCENE_MM = (MAT_MM[0] + 2 * MARGIN, MAT_MM[1] + 2 * MARGIN)
A4 = (210.0, 297.0)
SHEET_ORIGIN = {0: (0.0, 0.0), 1: (MAT_MM[0] - A4[0], 0.0),
                2: (MAT_MM[0] - A4[0], MAT_MM[1] - A4[1]), 3: (0.0, MAT_MM[1] - A4[1])}
SHEET_FILES = {0: "mat_corner_0_top_left.png", 1: "mat_corner_1_top_right.png",
               2: "mat_corner_2_bottom_right.png", 3: "mat_corner_3_bottom_left.png"}


def px(v_mm: float) -> float:
    return v_mm / PX


def mat_to_scene(x_mm, y_mm):
    return px(x_mm + MARGIN), px(y_mm + MARGIN)


def set_margin(mm: float):
    """Smaller backdrop = faster renders (used by the robustness sweep)."""
    global MARGIN, SCENE_MM
    MARGIN = mm
    SCENE_MM = (MAT_MM[0] + 2 * MARGIN, MAT_MM[1] + 2 * MARGIN)


# ---------------------------------------------------------------------------- noise

def smooth_noise(shape, scale_px, rng, octaves=3):
    h, w = shape
    out = np.zeros(shape, np.float32)
    amp = 1.0
    for o in range(octaves):
        s = max(2, int(scale_px / (2 ** o)))
        small = rng.standard_normal((h // s + 2, w // s + 2)).astype(np.float32)
        out += amp * cv2.resize(small, (w, h), interpolation=cv2.INTER_CUBIC)
        amp *= 0.5
    out -= out.mean()
    return out / (out.std() + 1e-6)


# ---------------------------------------------------------------------------- backdrop

def backdrop(shape, rng, base=(214, 216, 219)):
    h, w = shape
    img = np.ones((h, w, 3), np.float32) * np.array(base, np.float32)
    # wrinkles: thin random ridges, blurred into soft light/dark folds
    ridge = np.zeros((h, w), np.float32)
    for _ in range(26):
        x0, y0 = rng.uniform(0, w), rng.uniform(0, h)
        ang = rng.uniform(0, math.pi)
        L = rng.uniform(0.15, 0.6) * max(h, w)
        x1, y1 = x0 + L * math.cos(ang), y0 + L * math.sin(ang)
        cv2.line(ridge, (int(x0), int(y0)), (int(x1), int(y1)), float(rng.uniform(-1, 1)),
                 int(rng.uniform(6, 22)))
    ridge = cv2.GaussianBlur(ridge, (0, 0), 18)
    ridge = ridge / (np.abs(ridge).max() + 1e-6)
    img += ridge[..., None] * 16
    img += smooth_noise((h, w), 80, rng)[..., None] * 3.0
    return img


def paste_sheets(img, rng, jitter_mm=2.5, missing=()):
    """Lay the real printed A4 sheets onto the backdrop, each slightly misplaced."""
    placed = {}
    for mid, fname in SHEET_FILES.items():
        if mid in missing:          # simulate a sheet that's covered or out of frame
            continue
        sheet = cv2.imread(str(ROOT / "print" / fname), cv2.IMREAD_COLOR)
        sw, sh = int(round(px(A4[0]))), int(round(px(A4[1])))
        sheet = cv2.resize(sheet, (sw, sh), interpolation=cv2.INTER_AREA).astype(np.float32)
        ox, oy = SHEET_ORIGIN[mid]
        dx, dy = rng.uniform(-jitter_mm, jitter_mm, 2)
        rot = math.radians(rng.uniform(-0.6, 0.6))
        cx, cy = mat_to_scene(ox + A4[0] / 2 + dx, oy + A4[1] / 2 + dy)
        M = cv2.getRotationMatrix2D((sw / 2, sh / 2), math.degrees(rot), 1.0)
        M[0, 2] += cx - sw / 2
        M[1, 2] += cy - sh / 2
        H, W = img.shape[:2]
        warped = cv2.warpAffine(sheet, M, (W, H), flags=cv2.INTER_LINEAR)
        mask = cv2.warpAffine(np.ones((sh, sw), np.float32), M, (W, H))
        # paper sits on the sheet: faint contact shadow
        shadow = cv2.GaussianBlur(mask, (0, 0), 5)
        img *= (1 - 0.10 * shadow[..., None] * (1 - mask[..., None]))
        paper_tint = np.array([242, 245, 247], np.float32) / 255.0
        img[:] = img * (1 - mask[..., None]) + warped * paper_tint * mask[..., None]
        placed[mid] = (float(dx), float(dy), float(math.degrees(rot)))
    return placed


# ---------------------------------------------------------------------------- garments

def _densify(pts, step=12.0):
    p = np.asarray(pts, np.float64)
    out = []
    for a, b in zip(p, np.roll(p, -1, 0)):
        n = max(1, int(np.linalg.norm(b - a) / step))
        out += [a + (b - a) * k / n for k in range(n)]
    return np.array(out)


def _smooth_poly(pts, iters=2):
    """Chaikin corner cutting on a densified outline: corners round off by a few mm
    (like real fabric) without eating whole hems or cuffs."""
    p = _densify(pts)
    for _ in range(iters):
        q = 0.75 * p + 0.25 * np.roll(p, -1, 0)
        r = 0.25 * p + 0.75 * np.roll(p, -1, 0)
        p = np.empty((2 * len(q), 2))
        p[0::2], p[1::2] = q, r
    return p


def jeans_shape(cx, top, waist, hip, rise, inseam, thigh, opening, band=40.0):
    """Five-pocket jeans laid flat, dimensions in mm (all flat measurements).

    Returns (outline pts in mat mm, detail lines, ground truth in cm)."""
    crotch_y = top + rise
    hem_y = crotch_y + inseam
    # legs splay slightly: inner edges part from the crotch point
    gap_hem = 2 * thigh - (hip)            # keeps outer edge roughly straight from hip
    gap_hem = max(40.0, gap_hem + 60.0)
    outer_hem = gap_hem / 2 + opening
    pts = [
        (cx - waist / 2, top), (cx + waist / 2, top),
        (cx + waist / 2 + 2, top + band),
        (cx + hip / 2, top + 0.62 * rise),
        (cx + hip / 2, crotch_y),
        (cx + outer_hem, hem_y), (cx + gap_hem / 2, hem_y),
        (cx + 3, crotch_y + 4), (cx, crotch_y), (cx - 3, crotch_y + 4),
        (cx - gap_hem / 2, hem_y), (cx - outer_hem, hem_y),
        (cx - hip / 2, crotch_y),
        (cx - hip / 2, top + 0.62 * rise),
        (cx - waist / 2 - 2, top + band),
    ]
    # keep waistband and hems crisp, soften the rest
    soft = _smooth_poly(pts, 1)
    # thigh by the usual tape-measure convention: one leg, 25 mm below the crotch
    d = 25.0 / inseam
    thigh_w = (hip / 2 + (outer_hem - hip / 2) * d) - (gap_hem / 2) * d
    gt = {"waist_flat": waist / 10, "hip_flat": hip / 10, "inseam": inseam / 10,
          "leg_opening": opening / 10, "thigh": round(thigh_w / 10, 1)}
    details = {
        "band": [(cx - waist / 2, top + band), (cx + waist / 2, top + band)],
        "fly": [(cx + 10, top + band), (cx + 38, top + band + 30), (cx + 40, top + 0.55 * rise),
                (cx + 12, top + 0.72 * rise), (cx, top + 0.74 * rise)],
        "pocket_l": [(cx - waist / 2 + 12, top + band + 5), (cx - waist / 2 + 70, top + band + 90),
                     (cx - waist / 2 + 140, top + band + 8)],
        "pocket_r": [(cx + waist / 2 - 12, top + band + 5), (cx + waist / 2 - 70, top + band + 90),
                     (cx + waist / 2 - 140, top + band + 8)],
        "seam_l": [(cx - hip / 2 + 8, top + 0.62 * rise), (cx - outer_hem + 8, hem_y - 5)],
        "seam_r": [(cx + hip / 2 - 8, top + 0.62 * rise), (cx + outer_hem - 8, hem_y - 5)],
        "hem_l": [(cx - outer_hem + 3, hem_y - 22), (cx - gap_hem / 2 - 3, hem_y - 22)],
        "hem_r": [(cx + gap_hem / 2 + 3, hem_y - 22), (cx + outer_hem - 3, hem_y - 22)],
    }
    return soft, details, gt, (crotch_y, hem_y, gap_hem)


def tee_shape(cx, top, chest, length, sleeve, sleeve_drop=35.0, neck=180.0):
    """T-shirt laid flat with slightly dropped sleeves."""
    half = chest / 2
    sh_y = top + 25                  # shoulder slope: the side seam top sits lower than the neck
    arm_y = top + 230
    pts = [
        (cx - neck / 2, top), (cx - neck / 4, top + 55), (cx + neck / 4, top + 55),
        (cx + neck / 2, top),
        (cx + half, sh_y),
        (cx + half + sleeve, sh_y + sleeve_drop),
        (cx + half + sleeve, sh_y + sleeve_drop + 175),
        (cx + half, arm_y),
        (cx + half - 6, top + length), (cx - half + 6, top + length),
        (cx - half, arm_y),
        (cx - half - sleeve, sh_y + sleeve_drop + 175),
        (cx - half - sleeve, sh_y + sleeve_drop),
        (cx - half, sh_y),
    ]
    soft = _smooth_poly(pts, 1)
    gt = {"length": length / 10, "pit_to_pit": chest / 10, "hem_width": (chest - 12) / 10,
          "sleeve_length": sleeve / 10}
    details = {
        "collar": [(cx - neck / 2 + 8, top + 4), (cx - neck / 4, top + 64), (cx + neck / 4, top + 64),
                   (cx + neck / 2 - 8, top + 4)],
        "hem": [(cx - half + 10, top + length - 22), (cx + half - 10, top + length - 22)],
        "cuff_l": [(cx - half - sleeve + 20, sh_y + sleeve_drop), (cx - half - sleeve + 20, sh_y + sleeve_drop + 175)],
        "cuff_r": [(cx + half + sleeve - 20, sh_y + sleeve_drop), (cx + half + sleeve - 20, sh_y + sleeve_drop + 175)],
    }
    return soft, details, gt, None


def render_fabric(img, outline_mm, details_mm, rng, base_bgr, kind="denim", fades=None):
    H, W = img.shape[:2]
    poly = np.array([mat_to_scene(x, y) for x, y in outline_mm], np.float32)
    mask = np.zeros((H, W), np.uint8)
    cv2.fillPoly(mask, [np.round(poly * 4).astype(np.int32)], 255, lineType=cv2.LINE_AA, shift=2)
    m = mask.astype(np.float32) / 255.0

    # drop shadow onto the backdrop (light from top-left)
    sh = cv2.GaussianBlur(np.roll(np.roll(m, 9, 0), 7, 1), (0, 0), 9)
    img *= (1 - 0.30 * sh[..., None] * (1 - m[..., None]))

    fab = np.ones((H, W, 3), np.float32) * np.array(base_bgr, np.float32)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    if kind == "denim":
        twill = np.sin((xx + yy * 0.55) * (2 * math.pi / 3.2))
        slub = cv2.resize(rng.standard_normal((H, W // 6)).astype(np.float32), (W, H))
        fab += (twill * 5 + slub * 6)[..., None]
        # fading on thighs/knees (wear), lighter and bluer
        if fades:
            wear = np.zeros((H, W), np.float32)
            for (fx, fy, r) in fades:
                sx, sy = mat_to_scene(fx, fy)
                wear += np.exp(-(((xx - sx) ** 2) / (2 * (px(r) * 0.7) ** 2) +
                                 ((yy - sy) ** 2) / (2 * px(r) ** 2)))
            wear = np.clip(wear, 0, 1) * (0.6 + 0.4 * smooth_noise((H, W), 30, rng).clip(-1, 1) * 0.5)
            fab += wear[..., None] * np.array([30, 22, 14], np.float32)
    else:  # jersey
        knit = smooth_noise((H, W), 2, rng, octaves=1)
        fab += knit[..., None] * 4
    # soft folds
    folds = smooth_noise((H, W), 120, rng, octaves=2)
    fab *= (1 + 0.07 * folds[..., None])
    # edges roll under: darker near the outline
    dist = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
    fab *= (0.78 + 0.22 * np.clip(dist / 26.0, 0, 1))[..., None]

    # seams + topstitching
    stitch_col = (60, 140, 200) if kind == "denim" else tuple(int(c * 0.8) for c in base_bgr)
    for name, pts in details_mm.items():
        p = np.array([mat_to_scene(x, y) for x, y in _smooth_poly(pts, 2) if True], np.int32) \
            if len(pts) > 2 else np.array([mat_to_scene(x, y) for x, y in pts], np.int32)
        cv2.polylines(fab, [p], False, tuple(float(c) * 0.72 for c in base_bgr), 5, cv2.LINE_AA)
        if kind == "denim":
            dash = p.astype(np.float32)
            for a, b in zip(dash[:-1], dash[1:]):
                n = int(np.linalg.norm(b - a) / 9)
                for k in range(0, n, 2):
                    s = a + (b - a) * k / max(n, 1)
                    e = a + (b - a) * (k + 1) / max(n, 1)
                    cv2.line(fab, tuple(np.int32(s + 4)), tuple(np.int32(e + 4)), stitch_col, 2, cv2.LINE_AA)
    img[:] = img * (1 - m[..., None]) + fab * m[..., None]
    return mask


# ---------------------------------------------------------------------------- camera

def handheld_photo(scene, rng, out_size=(1512, 2016), pitch_deg=16, roll_deg=3.0, yaw_deg=2.0,
                   height_mm=1650.0, f_px=1650.0):
    """Project the floor plane through a pinhole camera held at an angle."""
    Hs, Ws = scene.shape[:2]
    ow, oh = out_size
    K = np.array([[f_px, 0, ow / 2], [0, f_px, oh / 2], [0, 0, 1]], np.float64)

    def rot(ax, deg):
        a = math.radians(deg)
        c, s = math.cos(a), math.sin(a)
        if ax == "x": return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
        if ax == "y": return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
        return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])

    # camera looks straight down (+Z into the floor), then tilts
    R = rot("z", roll_deg) @ rot("x", -pitch_deg) @ rot("y", yaw_deg)
    centre = np.array([SCENE_MM[0] / 2, SCENE_MM[1] / 2, 0.0])
    # step back so the tilted optical axis still hits the scene centre
    axis = R.T @ np.array([0, 0, 1.0])
    cam = centre - axis * (height_mm / axis[2])
    t = -R @ cam
    Hplane = K @ np.column_stack([R[:, 0], R[:, 1], t])          # floor mm -> image
    S = np.diag([PX, PX, 1.0])                                    # scene px -> floor mm
    Himg = Hplane @ S
    photo = cv2.warpPerspective(scene, Himg, (ow, oh), flags=cv2.INTER_AREA,
                                borderMode=cv2.BORDER_REPLICATE)

    # lens + sensor
    yy, xx = np.mgrid[0:oh, 0:ow].astype(np.float32)
    r2 = ((xx - ow / 2) ** 2 + (yy - oh / 2) ** 2) / ((ow / 2) ** 2 + (oh / 2) ** 2)
    photo *= (1 - 0.28 * r2)[..., None]
    light = cv2.GaussianBlur(rng.standard_normal((6, 5)).astype(np.float32), (0, 0), 1)
    light = cv2.resize(light, (ow, oh), interpolation=cv2.INTER_CUBIC)
    photo *= (1 + 0.05 * light)[..., None]
    photo *= np.array([0.96, 1.0, 1.05], np.float32)            # warm indoor white balance
    photo = cv2.GaussianBlur(photo, (0, 0), 0.7)
    photo += rng.normal(0, 2.4, photo.shape).astype(np.float32)
    photo = np.clip(photo, 0, 255).astype(np.uint8)
    ok, jpg = cv2.imencode(".jpg", photo, [cv2.IMWRITE_JPEG_QUALITY, 86])
    return cv2.imdecode(jpg, cv2.IMREAD_COLOR), jpg


# ---------------------------------------------------------------------------- scenes

SCENES = [
    dict(name="jeans-charcoal", kind="jeans", seed=7, colour=(78, 74, 72),
         dims=dict(waist=410.0, hip=520.0, rise=300.0, inseam=760.0, thigh=300.0, opening=235.0),
         camera=dict(pitch_deg=17, roll_deg=3.5, yaw_deg=2.5),
         caption="Baggy charcoal jeans, shot handheld at an angle"),
    dict(name="jeans-midwash", kind="jeans", seed=11, colour=(140, 96, 58),
         dims=dict(waist=385.0, hip=490.0, rise=280.0, inseam=790.0, thigh=275.0, opening=205.0),
         camera=dict(pitch_deg=12, roll_deg=-4.0, yaw_deg=-3.0),
         caption="Mid-wash straight jeans, camera rotated the other way"),
    dict(name="tee-burgundy", kind="tee", seed=5, colour=(52, 36, 128),
         dims=dict(chest=540.0, length=720.0, sleeve=190.0),
         camera=dict(pitch_deg=14, roll_deg=2.0, yaw_deg=4.0),
         caption="Burgundy tee, sleeves angled down like a real flat-lay"),
]


def render(spec):
    rng = np.random.default_rng(spec["seed"])
    shape = (int(px(SCENE_MM[1])), int(px(SCENE_MM[0])))
    img = backdrop(shape, rng, base=spec.get("backdrop", (214, 216, 219)))
    placed = paste_sheets(img, rng, jitter_mm=spec.get("jitter", 2.5), missing=spec.get("missing", ()))
    cx = MAT_MM[0] / 2
    if spec["kind"] == "jeans":
        d = spec["dims"]
        top = (MAT_MM[1] - d["rise"] - d["inseam"]) / 2
        outline, details, gt, (crotch_y, hem_y, gap) = jeans_shape(cx, top, **d)
        fades = [(cx - d["hip"] / 4, crotch_y + 120, 90), (cx + d["hip"] / 4, crotch_y + 120, 90),
                 (cx - d["hip"] / 4 - 15, crotch_y + d["inseam"] * 0.45, 70),
                 (cx + d["hip"] / 4 + 15, crotch_y + d["inseam"] * 0.45, 70)]
        render_fabric(img, outline, details, rng, spec["colour"], "denim", fades)
    else:
        d = spec["dims"]
        top = (MAT_MM[1] - d["length"]) / 2
        outline, details, gt, _ = tee_shape(cx, top, **d)
        render_fabric(img, outline, details, rng, spec["colour"], "jersey")
    photo, jpg = handheld_photo(np.clip(img, 0, 255), rng, **spec["camera"])
    return photo, jpg, {k: round(v, 1) for k, v in gt.items()}, placed


def main():
    OUT.mkdir(exist_ok=True)
    meta = []
    for spec in SCENES:
        photo, jpg, gt, placed = render(spec)
        (OUT / f"{spec['name']}.jpg").write_bytes(jpg.tobytes())
        meta.append({"name": spec["name"], "kind": spec["kind"], "caption": spec["caption"],
                     "ground_truth_cm": gt, "camera": spec["camera"],
                     "sheet_misplacement": {str(k): {"dx_mm": round(v[0], 1), "dy_mm": round(v[1], 1),
                                                     "rot_deg": round(v[2], 2)} for k, v in placed.items()}})
        print(spec["name"], gt)
    (OUT / "scenes.json").write_text(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()

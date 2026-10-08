"""Reproduce the public synthetic hardware example, using the real phone route.

Rendering is a development step, never part of serving a Render request.
"""
import copy
import json
from pathlib import Path
from PIL import Image
from validation.render_scene import SCENES, render
from api.server import _phone_measure, OVERLAYS

ROOT = Path(__file__).resolve().parent.parent

def main():
    spec = copy.deepcopy(SCENES[0])
    spec["missing"] = (0, 1, 2, 3)
    spec["camera"].update(pitch_deg=0, roll_deg=0, yaw_deg=0, out_size=(1200, 1600))
    photo, encoded, truth, _ = render(spec)
    result = _phone_measure(photo, "hardware", "jeans", 17.0, False)
    if not result["ok"]:
        raise RuntimeError(result["error"])
    result["demo"] = True
    result["garment"].pop("item_id", None)
    result["garment"]["notes"].insert(0, "Simulated hardware-only photo, precomputed with the same phone endpoint; not a real-world accuracy result.")
    Image.open(OVERLAYS / result["overlay_url"].split("/")[-1]).convert("RGB").save(ROOT / "web/demo.jpg", quality=88)
    result["overlay_url"] = "./demo.jpg"
    (ROOT / "web/demo.json").write_text(json.dumps(result), encoding="utf-8")
    (ROOT / "web/example-photo.jpg").write_bytes(encoded.tobytes())
    (ROOT / "validation/phone_example_truth.json").write_text(json.dumps({"synthetic": True, "truth_cm": truth}, indent=2))
    from tools.build_pwa import main as build
    build()

if __name__ == "__main__":
    main()

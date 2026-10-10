"""Generate the public example input; never use a personal garment photograph."""
import copy
from pathlib import Path
from validation import render_scene as scene


def make():
    scene.set_margin(250.)
    scene.PX = 1.
    spec=copy.deepcopy(scene.SCENES[0])
    spec.update(missing=(0,1,2,3),hardware=False)
    spec['camera'].update(height_mm=1500,pitch_deg=0,roll_deg=0,yaw_deg=0,out_size=(800,1000),f_px=900)
    image, encoded, truth, _ = scene.render(spec)
    return image, encoded.tobytes(), truth


if __name__=='__main__':
    _, raw, _=make()
    (Path(__file__).resolve().parent.parent/'web/example-jeans.jpg').write_bytes(raw)

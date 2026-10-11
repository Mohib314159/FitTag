"""Known-plane control to separate geometry error from learned scale error.

Depth here comes from the generated scene's camera, not an actual LiDAR sensor.
This cannot validate an iPhone capture or the accuracy of sensor measurements.
"""
import json
import math
import argparse
from pathlib import Path
import numpy as np
from tools.probe_candidates import CASES,captures,score,summarize

def plane_depth(shape,height_mm,pitch_deg,focal_px=450.):
    h,w=shape[:2];yy,xx=np.indices((h,w),dtype=np.float32)
    pitch=math.radians(pitch_deg)
    # Ray centres account for the renderer's 2:1 pixel-centre resize.
    rays_y=(yy-(h/2-.25))/focal_px
    return (height_mm/1000)/(math.sin(pitch)*rays_y+math.cos(pitch))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--cache',type=Path);args=parser.parse_args()
    records=[]
    def inputs():
        if args.cache is None:
            yield from captures();return
        for index in range(len(CASES)):
            with np.load(args.cache/f'{index}-assumed.npz',allow_pickle=False) as data:
                yield index,data['image'],str(data['kind']),json.loads(str(data['truth']))
    for index,image,kind,truth in inputs():
        _,height,pitch=CASES[index]
        depth=plane_depth(image.shape,height,pitch)
        row={'case':index,'camera':'known','depth_source':'generated_ground_truth_plane'}
        try:row.update(score(image,kind,truth,depth,450.))
        except ValueError as exc:row.update(mode='refused',reason=str(exc))
        records.append(row);print(json.dumps(row),flush=True)
    output=Path(__file__).resolve().parents[1]/'validation/geometry_depth_control.json'
    output.write_text(json.dumps({'synthetic_only':True,'not_a_sensor_test':True,
                                 'summary':summarize(records),'records':records},indent=2),encoding='utf-8')
    print(json.dumps(summarize(records)),flush=True)

if __name__=='__main__':main()

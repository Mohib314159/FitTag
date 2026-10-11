"""Compare mask cleaning on cached generated cases with known plane depth.

Defaults remain unchanged. These cases select no production parameter and
cannot establish performance on a real garment photograph.
"""
import argparse
import json
from pathlib import Path
import numpy as np
from core import flatlay,free_capture
from tools.probe_candidates import CASES,score,summarize
from tools.probe_geometry_control import plane_depth

def main():
    parser=argparse.ArgumentParser();parser.add_argument('cache',type=Path);args=parser.parse_args()
    previous=free_capture.garment_mask;records=[]
    try:
        for label,sigma,kernel in [('original',3.,21),('gentler',1.,5),('unblurred',0.,3)]:
            free_capture.garment_mask=lambda im,s=sigma,k=kernel: flatlay.garment_mask(im,open_px=k,blur_sigma=s)
            for index,(_,height,pitch) in enumerate(CASES):
                with np.load(args.cache/f'{index}-assumed.npz',allow_pickle=False) as data:
                    image=data['image'];truth=json.loads(str(data['truth']));kind=str(data['kind'])
                row={'case':index,'camera':label,'sigma':sigma,'opening_pixels':kernel}
                try:row.update(score(image,kind,truth,plane_depth(image.shape,height,pitch),450.))
                except ValueError as exc:row.update(mode='refused',reason=str(exc))
                records.append(row);print(json.dumps(row),flush=True)
    finally:free_capture.garment_mask=previous
    output=Path(__file__).resolve().parents[1]/'validation/mask_cleaning_probe.json'
    output.write_text(json.dumps({'synthetic_only':True,'known_plane_control':True,
                                 'summary':summarize(records),'records':records},indent=2),encoding='utf-8')
    print(json.dumps(summarize(records)),flush=True)

if __name__=='__main__':main()

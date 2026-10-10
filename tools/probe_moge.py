"""Buttonless model comparison on controlled scenes; not real-user validation."""
import argparse
import copy
import json
import math
from pathlib import Path
import statistics
import time
import cv2
from core.moge_depth import Model,metric_maps
from core.free_capture import depth_measure,outline
from validation import render_scene as scene

def main():
    parser=argparse.ArgumentParser();parser.add_argument('model');parser.add_argument('--cases',type=int,default=6)
    parser.add_argument('--tokens',type=int,default=1200);args=parser.parse_args()
    model=Model(args.model);records=[];scene.set_margin(250.);scene.PX=1.
    for index,(kind,height,pitch) in enumerate([(0,1500,0),(0,1850,0),(0,1650,15),(1,1500,0),(1,1850,12),(2,1200,0)][:args.cases]):
        spec=copy.deepcopy(scene.SCENES[kind]);spec.update(missing=(0,1,2,3),hardware=False)
        spec['camera'].update(height_mm=height,pitch_deg=pitch,roll_deg=0,yaw_deg=0,out_size=(800,1000),f_px=900)
        image,_,truth,_=scene.render(spec);kind='t-shirt' if kind==2 else 'jeans'
        # Bound output arrays while preserving aspect ratio and the camera scale.
        image=cv2.resize(image,(400,500),interpolation=cv2.INTER_AREA)
        started=time.perf_counter();raw=model.raw(image,args.tokens);seconds=time.perf_counter()-started
        _,_,_,mask=outline(image,kind)
        for camera in ('estimated','known'):
            try:
                depth,fx,_=metric_maps(raw,None if camera=='estimated' else 450.)
                _,rows,diagnostics=depth_measure(image,kind,depth,fx,mask)
                errors={row.name:round(100*abs(float(row.value_cm)-truth[row.name])/truth[row.name],2) for row in rows if row.name in truth}
                record={'case':index,'camera':camera,'mode':'depth','absolute_errors_pct':errors,'diagnostics':diagnostics,'inferred_diagonal_fov_deg':round(math.degrees(2*math.atan(math.hypot(400,500)/(2*fx))),2)}
            except ValueError as exc:
                record={'case':index,'camera':camera,'mode':'refused','absolute_errors_pct':{},'reason':str(exc)}
            record.update(synthetic=True,inference_seconds=round(seconds,2));records.append(record)
            print(json.dumps(record),flush=True)
        output=Path(__file__).resolve().parents[1]/'validation/moge_buttonless_probe.json'
        summary=[]
        for camera in ('estimated','known'):
            group=[r for r in records if r['camera']==camera];errors=[e for r in group for e in r['absolute_errors_pct'].values()]
            summary.append({'camera':camera,'accepted':sum(r['mode']=='depth' for r in group),'total':len(group),'median_error_pct':round(statistics.median(errors),2) if errors else None,'max_error_pct':max(errors) if errors else None})
        output.write_text(json.dumps({'synthetic_only':True,'tokens':args.tokens,'summary':summary,'records':records},indent=2),encoding='utf-8')
    print(json.dumps(summary),flush=True)

if __name__=='__main__':main()

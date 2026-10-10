"""Reproducible preprocessing counterexamples; never overwrite the public demo."""
import copy
import json
import math
from pathlib import Path
import statistics
import time
from core import depth_model
from api import free_capture
from validation import render_scene as scene

def main():
    scene.set_margin(250.);scene.PX=1.
    records=[];predict=depth_model.predict
    for index,(kind,height,pitch) in enumerate([(0,1500,0),(0,1850,0),(0,1650,15),(1,1500,0),(1,1850,12),(2,1200,0)]):
        spec=copy.deepcopy(scene.SCENES[kind]);spec.update(missing=(0,1,2,3),hardware=False)
        spec['camera'].update(height_mm=height,pitch_deg=pitch,roll_deg=0,yaw_deg=0,out_size=(800,1000),f_px=900)
        image,encoded,truth,_=scene.render(spec)
        garment='t-shirt' if kind==2 else 'jeans'
        fov=math.degrees(2*math.atan(math.hypot(800,1000)/(2*900)))
        for mode in ('stretch','letterbox','reflect'):
            started=time.perf_counter();depth=predict(image,preprocessing=mode)
            inference=time.perf_counter()-started
            depth_model.predict=lambda _:depth
            try:
                for camera in ('assumed','known'):
                    _,result=free_capture.process(image,encoded.tobytes(),garment,0 if camera=='assumed' else fov)
                    errors={row['name']:round(100*abs(row['value_cm']-truth[row['name']])/truth[row['name']],2)
                            for row in result['rows'] if 'value_cm' in row and row['name'] in truth}
                    records.append({'case':index,'synthetic':True,'preprocessing':mode,'camera':camera,'mode':result['mode'],
                                    'absolute_errors_pct':errors,'inference_seconds':round(inference,2),'notes':result['notes']})
                    print(index,mode,camera,result['mode'],errors,flush=True)
            finally: depth_model.predict=predict
    summary=[]
    for mode in ('stretch','letterbox','reflect'):
        for camera in ('assumed','known'):
            group=[r for r in records if r['preprocessing']==mode and r['camera']==camera]
            errors=[error for record in group for error in record['absolute_errors_pct'].values()]
            summary.append({'preprocessing':mode,'camera':camera,'accepted':sum(r['mode']=='depth' for r in group),'total':len(group),
                            'median_absolute_error_pct':round(statistics.median(errors),2) if errors else None,
                            'maximum_absolute_error_pct':max(errors) if errors else None})
    path=Path(__file__).resolve().parents[1]/'validation/buttonless_preprocessing_audit.json'
    path.write_text(json.dumps({'synthetic_only':True,'model_sha256':depth_model.MODEL_SHA256,'summary':summary,'records':records},indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2),flush=True)

if __name__=='__main__':main()

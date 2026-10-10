"""Same 400x500 images as the MoGe comparison, using the existing metric model."""
import copy
import json
import math
from pathlib import Path
import statistics
import cv2
from core import depth_model
from api import free_capture
from validation import render_scene as scene

def main():
    scene.set_margin(250.);scene.PX=1.;records=[];predict=depth_model.predict
    for index,(kind,height,pitch) in enumerate([(0,1500,0),(0,1850,0),(0,1650,15),(1,1500,0),(1,1850,12),(2,1200,0)]):
        spec=copy.deepcopy(scene.SCENES[kind]);spec.update(missing=(0,1,2,3),hardware=False)
        spec['camera'].update(height_mm=height,pitch_deg=pitch,roll_deg=0,yaw_deg=0,out_size=(800,1000),f_px=900)
        photo,_,truth,_=scene.render(spec);photo=cv2.resize(photo,(400,500),interpolation=cv2.INTER_AREA)
        encoded=cv2.imencode('.jpg',photo)[1].tobytes();kind='t-shirt' if kind==2 else 'jeans';depth=predict(photo)
        depth_model.predict=lambda _:depth
        try:
            for camera in ('assumed','known'):
                fov=0 if camera=='assumed' else math.degrees(2*math.atan(math.hypot(400,500)/900))
                _,result=free_capture.process(photo,encoded,kind,fov)
                errors={row['name']:round(100*abs(float(row['value_cm'])-truth[row['name']])/truth[row['name']],2) for row in result['rows'] if 'value_cm' in row and row['name'] in truth}
                records.append({'case':index,'camera':camera,'mode':result['mode'],'absolute_errors_pct':errors})
                print(index,camera,result['mode'],errors,flush=True)
        finally: depth_model.predict=predict
    summary=[]
    for camera in ('assumed','known'):
        group=[r for r in records if r['camera']==camera];errors=[e for r in group for e in r['absolute_errors_pct'].values()]
        summary.append({'camera':camera,'accepted':sum(r['mode']=='depth' for r in group),'total':len(group),'median_error_pct':round(statistics.median(errors),2) if errors else None,'max_error_pct':max(errors) if errors else None})
    path=Path(__file__).resolve().parents[1]/'validation/buttonless_baseline_400.json'
    path.write_text(json.dumps({'synthetic_only':True,'geometry':'preserved_projected_mask','resolution':[400,500],'summary':summary,'records':records},indent=2),encoding='utf-8')
    print(json.dumps(summary),flush=True)

if __name__=='__main__':main()

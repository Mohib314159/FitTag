"""Synthetic counterexamples for model scale, never real-garment validation."""
import copy
import json
import math
import time
from dataclasses import asdict
from pathlib import Path
import cv2
from PIL import Image
from api.free_capture import process
from validation import render_scene as scene

ROOT=Path(__file__).resolve().parent.parent


def main():
    scene.set_margin(250.)
    scene.PX=1.0  # Smaller development renderer, not serving infrastructure.
    output=ROOT/'validation/button_free_probe.json'
    records=[]
    demo_done=False
    for index,(kind,height,pitch,colour) in enumerate([
        (0,1500,0,None),(0,1850,0,None),(0,1650,15,None),
        (1,1500,0,None),(1,1850,12,None),(2,1200,0,None)]):
        spec=copy.deepcopy(scene.SCENES[kind])
        spec.update(missing=(0,1,2,3),hardware=False)
        spec['camera'].update(height_mm=height,pitch_deg=pitch,roll_deg=0,yaw_deg=0,
                              out_size=(800,1000),f_px=900)
        image,encoded,truth,_=scene.render(spec)
        garment='jeans' if kind!=2 else 't-shirt'
        actual_fov=math.degrees(2*math.atan(math.hypot(800,1000)/(2*900)))
        for camera in ('assumed','known-synthetic-intrinsics'):
            rect,result=process(image,encoded.tobytes(),garment,0 if camera=='assumed' else actual_fov)
            rows=result['rows']
            errors={r['name']:round(100*(r['value_cm']-truth[r['name']])/truth[r['name']],1)
                    for r in rows if 'value_cm' in r and r['name'] in truth}
            record={'synthetic':True,'case':index,'garment':garment,'camera':camera,
                    'height_mm':height,'pitch_deg':pitch,'truth_cm':truth,'mode':result['mode'],
                    'relative_errors_pct':errors,'diagnostics':result['diagnostics'],'notes':result['notes']}
            if errors:
                anchor='waist_flat' if garment=='jeans' else 'pit_to_pit'
                values={r['name']:r['value_cm'] for r in rows}
                factor=truth[anchor]/values[anchor]
                record['known_length_corrected_errors_pct']={name:round(100*(value*factor-truth[name])/truth[name],1)
                                                            for name,value in values.items() if name in truth}
            records.append(record)
            print(index,camera,result['mode'],errors,flush=True)
            if not demo_done and camera=='assumed':
                (ROOT/'web/example-jeans.jpg').write_bytes(encoded.tobytes())
                # Model inputs contain no button, rivet, card, paper or mat.
                Image.fromarray(cv2.cvtColor(rect,cv2.COLOR_BGR2RGB)).save(ROOT/'web/free-demo.jpg',quality=88)
                result.update(demo=True,demo_truth_cm=truth,overlay_url='./free-demo.jpg',image_size=list(rect.shape[1::-1]))
                result['notes'].insert(0,'Simulated garment, with hardware and all reference objects removed. Actual pinned ONNX model inference, not invented numbers.')
                result['notes'].insert(1,f"Known synthetic flat waist: {truth.get('waist_flat')} cm. Compare it with the model guess. This demonstrates model scale error.")
                (ROOT/'web/free-demo.json').write_text(json.dumps(result),encoding='utf-8')
                demo_done=True
        output.write_text(json.dumps({'synthetic_only':True,'records':records},indent=2),encoding='utf-8')

if __name__=='__main__':main()

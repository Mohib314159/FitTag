"""Offline model comparison. Generated stress tests are not user validation.

Run one candidate per process in an isolated Torch environment. Author sources
and hash-verified checkpoints live outside this repository. No private uploads,
network inference, best-case filtering or serving-default changes.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import sys
import threading
import time

import cv2
import numpy as np

from core.free_capture import depth_measure, focal_from_diagonal_fov, outline
from validation import render_scene as scene

CASES=[(0,1500,0),(0,1850,0),(0,1650,15),(1,1500,0),(1,1850,12),(2,1200,0)]

def captures():
    scene.set_margin(250.);scene.PX=1.
    for index,(kind,height,pitch) in enumerate(CASES):
        spec=copy.deepcopy(scene.SCENES[kind]);spec.update(missing=(0,1,2,3),hardware=False)
        spec['camera'].update(height_mm=height,pitch_deg=pitch,roll_deg=0,yaw_deg=0,
                              out_size=(800,1000),f_px=900)
        image,_,truth,_=scene.render(spec)
        yield index,cv2.resize(image,(400,500),interpolation=cv2.INTER_AREA),('t-shirt' if kind==2 else 'jeans'),truth

def score(image,kind,truth,depth,fx):
    if depth.shape!=image.shape[:2]:
        depth=cv2.resize(depth,image.shape[1::-1],interpolation=cv2.INTER_LINEAR)
    _,_,_,mask=outline(image,kind)
    _,rows,diagnostics=depth_measure(image,kind,depth.astype(np.float32),fx,mask)
    measured={row.name:float(row.value_cm) for row in rows if row.name in truth}
    return {'mode':'depth','absolute_errors_pct':{
        name:round(100*abs(value-truth[name])/truth[name],2) for name,value in measured.items()},
        'absolute_errors_cm':{name:round(abs(value-truth[name]),3) for name,value in measured.items()},
        'measurements_cm':measured,'diagnostics':diagnostics}

def summarize(records):
    output=[]
    for camera in sorted({row['camera'] for row in records}):
        group=[r for r in records if r['camera']==camera]
        pct=[v for r in group for v in r.get('absolute_errors_pct',{}).values()]
        cm=[v for r in group for v in r.get('absolute_errors_cm',{}).values()]
        output.append({'camera':camera,'accepted':sum(r['mode']=='depth' for r in group),
                       'total':len(group),'scored_measurements':len(pct),
                       'median_error_pct':round(statistics.median(pct),2) if pct else None,
                       'max_error_pct':max(pct) if pct else None,
                       'median_error_cm':round(statistics.median(cm),3) if cm else None,
                       'p90_error_cm':round(float(np.percentile(cm,90)),3) if cm else None})
    return output

def load_candidate(name,root,precision='float32'):
    import torch
    from safetensors.torch import load_file
    folder=root/'research-models'/name
    manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    for entry in manifest['files']:
        if entry['file'].endswith(('.safetensors','.pt','.bin')):
            with (folder/entry['file']).open('rb') as source:
                if hashlib.file_digest(source,'sha256').hexdigest()!=entry['sha256']:
                    raise ValueError('Checkpoint checksum does not match recorded download.')
    if name=='unidepth':
        sys.path.insert(0,str(root/'unidepth-source'))
        from unidepth.models import UniDepthV2
        config=json.loads((folder/'config.json').read_text())
        model=UniDepthV2(config)
        model.load_state_dict(load_file(str(folder/'model.safetensors')),strict=True)
        model.eval();model.resolution_level=0
        def predict(image):
            rgb=torch.from_numpy(cv2.cvtColor(image,cv2.COLOR_BGR2RGB).copy()).permute(2,0,1)
            results=[]
            for camera in ('estimated','known'):
                K=None if camera=='estimated' else torch.tensor([[450.,0.,199.5],[0.,450.,249.5],[0.,0.,1.]])
                start=time.perf_counter()
                with torch.inference_mode(): result=model.infer(rgb,K)
                depth=result['depth'].squeeze().float().cpu().numpy()
                matrix=result['intrinsics'].squeeze().float().cpu().numpy()
                # infer() returns a camera-head prediction even when supplied
                # rays condition the points. Use the supplied K for that run.
                fx=450. if camera=='known' else float((matrix[0,0]+matrix[1,1])/2)
                results.append((camera,depth,fx,time.perf_counter()-start))
            return results
    elif name=='da3':
        sys.path.insert(0,str(root/'da3-source'/'src'))
        # Pinned upstream commit imports a moved utility from its old location.
        # Alias the author's unchanged module; do not replace model operations.
        import importlib
        sys.modules['depth_anything_3.model.utils.ray_utils']=importlib.import_module('depth_anything_3.utils.ray_utils')
        from depth_anything_3.cfg import create_object
        from depth_anything_3.utils.io.input_processor import InputProcessor
        from omegaconf import OmegaConf
        config=json.loads((folder/'config.json').read_text())
        # Meta construction and assign avoid a second full checkpoint allocation.
        # Upstream builds a dropout schedule with linspace().item(); that tiny
        # initializer needs CPU scalars even when parameter storage is meta.
        original_linspace=torch.linspace
        def cpu_linspace(*args,**kwargs):
            kwargs.setdefault('device','cpu')
            return original_linspace(*args,**kwargs)
        torch.linspace=cpu_linspace
        try:
            with torch.device('meta'): model=create_object(OmegaConf.create(config['config']))
        finally: torch.linspace=original_linspace
        state=load_file(str(folder/'model.safetensors'))
        state={key.removeprefix('model.'):value for key,value in state.items()}
        model.load_state_dict(state,strict=True,assign=True);model.eval()
        processor=InputProcessor()
        def predict(image):
            rgb=cv2.cvtColor(image,cv2.COLOR_BGR2RGB)
            tensor,_,_=processor([rgb],process_res=504,num_workers=1)
            start=time.perf_counter()
            with torch.inference_mode(): output=model(tensor.unsqueeze(0))
            canonical=output['depth'].squeeze().float().cpu().numpy()
            seconds=time.perf_counter()-start
            # Author metric conversion uses focal length in the processed pixels.
            scale=(tensor.shape[-1]/image.shape[1]+tensor.shape[-2]/image.shape[0])/2
            return [(camera,canonical*(fx*scale)/300.,fx,seconds)
                    for camera,fx in [('assumed',focal_from_diagonal_fov(image.shape)),('known',450.)]]
    elif name=='depthpro':
        sys.path.insert(0,str(root/'depthpro-source'/'src'))
        import dataclasses
        import depth_pro
        from depth_pro.depth_pro import DEFAULT_MONODEPTH_CONFIG_DICT
        config=dataclasses.replace(DEFAULT_MONODEPTH_CONFIG_DICT,checkpoint_uri=None)
        with torch.device('meta'):
            model,_=depth_pro.create_model_and_transforms(config,device=torch.device('meta'))
        if precision=='float32':
            cache_meta=json.loads((folder/'fp32-manifest.json').read_text())
            with (folder/'depth_pro_fp32.safetensors').open('rb') as source:
                if hashlib.file_digest(source,'sha256').hexdigest()!=cache_meta['sha256']:
                    raise ValueError('Converted checkpoint hash mismatch')
            state=load_file(str(folder/'depth_pro_fp32.safetensors'))
            manifest={**manifest,'fp32_cache':cache_meta}
        else:state=torch.load(folder/'depth_pro.pt',map_location='cpu',weights_only=True,mmap=True)
        model.load_state_dict(state,strict=True,assign=True);model.eval()
        def predict(image):
            rgb=torch.from_numpy(cv2.cvtColor(image,cv2.COLOR_BGR2RGB).copy()).permute(2,0,1).float()/255.
            rgb=((rgb-.5)/.5).to(dtype=next(model.parameters()).dtype)
            start=time.perf_counter()
            with torch.inference_mode(): output=model.infer(rgb)
            depth=output['depth'].squeeze().float().cpu().numpy()
            inferred=float(output['focallength_px'].item());seconds=time.perf_counter()-start
            # infer() applies f_px by scaling canonical inverse depth only.
            return [('estimated',depth,inferred,seconds),('known',depth*(450./inferred),450.,seconds)]
    else: raise ValueError('Unknown candidate')
    return predict,manifest

def main():
    parser=argparse.ArgumentParser();parser.add_argument('candidate',choices=['unidepth','da3','depthpro'])
    parser.add_argument('--work',type=Path,required=True);parser.add_argument('--cases',type=int,default=6)
    parser.add_argument('--threads',type=int,default=4)
    parser.add_argument('--precision',choices=['float32','checkpoint'],default='float32');args=parser.parse_args()
    os.environ['HF_HUB_OFFLINE']='1';os.environ['WANDB_MODE']='disabled'
    import psutil
    import torch
    torch.set_num_threads(args.threads);torch.set_num_interop_threads(1);torch.manual_seed(13)
    cv2.setNumThreads(1)
    output=Path(__file__).resolve().parents[1]/'validation'/f'{args.candidate}_buttonless_probe.json'
    records=[];report={'synthetic_only':True,'candidate':args.candidate,'torch':torch.__version__,
                       'device':'cpu','threads':args.threads,'input_resolution':[400,500],
                       'weight_dtype':'float16' if args.candidate=='depthpro' and args.precision=='checkpoint' else 'float32',
                       'records':records,'summary':[],'status':'loading'}
    process=psutil.Process();peak=[process.memory_info().rss];stop=threading.Event()
    def monitor():
        while not stop.wait(.25): peak[0]=max(peak[0],process.memory_info().rss)
    thread=threading.Thread(target=monitor,daemon=True);thread.start()
    def save():
        report['peak_rss_mb']=round(max(peak[0],process.memory_info().rss)/1e6,1)
        report['summary']=summarize(records)
        output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    save();print('loading',args.candidate,flush=True)
    try:
        started=time.perf_counter();predict,manifest=load_candidate(args.candidate,args.work.resolve(),args.precision)
        report['artifact']=manifest;report['load_seconds']=round(time.perf_counter()-started,2)
        report['status']='running';save();print('model loaded',flush=True)
        for index,image,kind,truth in list(captures())[:args.cases]:
            print('infer case',index,flush=True)
            for camera,depth,fx,seconds in predict(image):
                cached=args.work.resolve()/'candidate-maps'/args.candidate
                cached.mkdir(parents=True,exist_ok=True)
                np.savez_compressed(cached/f'{index}-{camera}.npz',depth=depth,focal_px=fx,
                                    seconds=seconds,image=image,truth=json.dumps(truth),kind=kind)
                record={'case':index,'camera':camera,'focal_px':round(fx,3),'inference_seconds':round(seconds,2)}
                try: record.update(score(image,kind,truth,depth,fx))
                except ValueError as exc: record.update(mode='refused',reason=str(exc))
                records.append(record);save();print(json.dumps(record),flush=True)
        report['status']='completed'
    except Exception as exc:
        report['status']='failed';report['failure']=type(exc).__name__+': '+str(exc)
        raise
    finally:
        stop.set();save();print(json.dumps(report['summary']),flush=True)

if __name__=='__main__':main()

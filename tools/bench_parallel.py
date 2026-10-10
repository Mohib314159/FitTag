"""Reproducible local CPU experiment; not a Render or human-task benchmark."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time


def worker(threads):
    os.environ['FITTAG_DEPTH_THREADS'] = str(threads)
    import cv2
    cv2.setNumThreads(1)
    from core.depth_model import predict
    from api.free_capture import process
    from core import free_capture
    import api.free_capture as api
    root = Path(__file__).resolve().parent.parent
    from tools.make_free_input import make
    image, raw, _ = make()
    predict(image)  # warm model, exclude initialization
    records=[]
    fast = free_capture.depth_measure
    def repeated(image, kind, depth, focal, mask=None):
        return fast(image,kind,depth,focal)  # emulate the previous duplicate outline
    for label,implementation,parallel in [('previous-outline',repeated,1),('reuse-outline',fast,1),('two-photos',fast,2)]:
        api.depth_measure = implementation
        times=[]
        for _ in range(3):
            started=time.perf_counter()
            with ThreadPoolExecutor(max_workers=parallel) as pool:
                outputs=list(pool.map(lambda _:process(image,raw,'jeans',0),range(parallel)))
            assert all(output[1]['mode']=='depth' for output in outputs)
            times.append(time.perf_counter()-started)
        records.append({'route':label,'concurrent_photos':parallel,'threads':threads,
                        'median_seconds':round(statistics.median(times),3),'samples_seconds':[round(v,3) for v in times]})
    import psutil
    memory=psutil.Process().memory_info()
    return {'threads':threads,'process_peak_working_set_mb':round(memory.peak_wset/1024**2,1) if hasattr(memory,'peak_wset') else None,'records':records}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--worker',type=int);args=parser.parse_args()
    if args.worker:
        print(json.dumps(worker(args.worker)),flush=True);return
    records=[];profiles=[]
    for threads in (1,2,4):
        reply=subprocess.run([sys.executable,'-m','tools.bench_parallel','--worker',str(threads)],capture_output=True,text=True)
        if reply.returncode:
            raise RuntimeError(reply.stderr)
        batch=json.loads(reply.stdout.strip());profiles.append(batch);records.extend(batch['records'])
        print(json.dumps(batch),flush=True)
    root=Path(__file__).resolve().parent.parent
    (root/'validation/parallel_latency.json').write_text(json.dumps({
        'scope':'Warm Windows CPU; three runs per configuration; one generated reference-free garment photo reused. Includes outline/model/geometry, excludes upload/polling/overlays and human capture. Not Render hardware.',
        'memory_scope':'Full Windows worker peak including generated input rendering, model warmup and all trials; not a live service memory measurement.',
        'profiles':profiles,'records':records},indent=2),encoding='utf-8')


if __name__=='__main__':main()

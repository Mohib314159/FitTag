"""Measure local API latency, not human task time or real-garment accuracy."""
import argparse
import json
import statistics
import time
import urllib.request
from pathlib import Path


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--url',default='http://127.0.0.1:8003')
    parser.add_argument('--samples',type=int,default=5)
    args=parser.parse_args()
    root=Path(__file__).resolve().parent.parent
    raw=(root/'web/free-demo.jpg').read_bytes()
    records=[]
    for label,fields in [('shape',{'estimate':'false'}),('depth',{'estimate':'true'}),
                         ('distance',{'camera_height_cm':'150','fov_deg':'84'})]:
        durations=[]
        for index in range(args.samples):
            boundary='fittag-public-synthetic-benchmark'
            body=b''
            for key,value in fields.items():
                body+=f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode()
            body+=f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="synthetic.jpg"\r\nContent-Type: image/jpeg\r\n\r\n'.encode()+raw+f'\r\n--{boundary}--\r\n'.encode()
            req=urllib.request.Request(args.url+'/measure-free',data=body,headers={'Content-Type':f'multipart/form-data; boundary={boundary}'})
            started=time.perf_counter()
            with urllib.request.urlopen(req,timeout=60) as response:result=json.load(response)
            elapsed=time.perf_counter()-started
            if not result['ok'] or result['mode']!=label:raise RuntimeError('Benchmark route did not produce its expected result mode.')
            durations.append(elapsed)
            print(label,index+1,round(elapsed,2),'seconds',flush=True)
        records.append({'mode':label,'samples':len(durations),'median_seconds':round(statistics.median(durations),2),
                        'range_seconds':[round(min(durations),2),round(max(durations),2)],
                        'raw_seconds':[round(v,3) for v in durations]})
    report={'scope':'Windows localhost, synthetic image; admitted requests on an already running server. Includes multipart decode, processing and overlay creation. Excludes human capture/setup and Internet/Render latency.',
            'real_users_measured':0,'records':records}
    (root/'validation/button_free_latency.json').write_text(json.dumps(report,indent=2),encoding='utf-8')

if __name__=='__main__':main()

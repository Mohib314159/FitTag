"""Stream the research checkpoint to memory-mappable FP32 safetensors.

Only dtype conversion; no inference, quantization, training or model rewrite.
The original research license still applies. Files must stay outside Git.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import numpy as np
import torch

def main():
    parser=argparse.ArgumentParser();parser.add_argument('folder',type=Path);folder=parser.parse_args().folder
    manifest=json.loads((folder/'manifest.json').read_text())
    source=folder/'depth_pro.pt'
    expected=next(x['sha256'] for x in manifest['files'] if x['file']=='depth_pro.pt')
    with source.open('rb') as f:
        if hashlib.file_digest(f,'sha256').hexdigest()!=expected:raise ValueError('Original hash mismatch')
    destination=folder/'depth_pro_fp32.safetensors';meta_path=folder/'fp32-manifest.json'
    if destination.exists() and meta_path.exists():
        meta=json.loads(meta_path.read_text())
        with destination.open('rb') as f:
            if hashlib.file_digest(f,'sha256').hexdigest()==meta['sha256']:
                print('FP32 cache already verified',flush=True);return
    state=torch.load(source,map_location='cpu',weights_only=True,mmap=True)
    header={};offset=0
    kinds={torch.int64:('I64',np.int64),torch.int32:('I32',np.int32),torch.bool:('BOOL',np.bool_)}
    arrays={}
    for name,tensor in state.items():
        dtype,np_dtype=('F32',np.float32) if tensor.is_floating_point() else kinds[tensor.dtype]
        size=tensor.numel()*np.dtype(np_dtype).itemsize
        header[name]={'dtype':dtype,'shape':list(tensor.shape),'data_offsets':[offset,offset+size]}
        arrays[name]=np_dtype;offset+=size
    encoded=json.dumps(header,separators=(',',':')).encode();encoded+=b' '*((-len(encoded))%8)
    temporary=destination.with_suffix('.download')
    try:
        with temporary.open('wb') as f:
            f.write(struct.pack('<Q',len(encoded)));f.write(encoded)
            for index,(name,tensor) in enumerate(state.items()):
                f.write(tensor.numpy().astype(arrays[name],copy=True).tobytes())
                if index%100==0:print('converted',index,'/',len(state),flush=True)
        with temporary.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
        temporary.replace(destination)
        meta={'source_sha256':expected,'sha256':digest,'bytes':destination.stat().st_size,
              'conversion':'floating tensors promoted to FP32; integer buffers preserved'}
        meta_path.write_text(json.dumps(meta,indent=2),encoding='utf-8')
        print(json.dumps(meta),flush=True)
    finally:temporary.unlink(missing_ok=True)

if __name__=='__main__':main()

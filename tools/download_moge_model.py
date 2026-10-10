"""Download the authors' small ONNX weights for an isolated, local comparison."""
import argparse
import hashlib
from pathlib import Path
import urllib.request

REVISION='e50ffda41565591092adea54c6ac83d6212e1e23'
SHA256='24eacb5dc7a2c54c7bc98f7de085ffbed79ad006ea5b664c2c2cdc02ff3a52f0'
URL=f'https://huggingface.co/Ruicheng/moge-2-vits-normal-onnx/resolve/{REVISION}/model.onnx'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('path');path=Path(parser.parse_args().path)
    path.parent.mkdir(parents=True,exist_ok=True);temporary=path.with_suffix('.download')
    digest=hashlib.sha256()
    try:
        with urllib.request.urlopen(URL,timeout=60) as response,temporary.open('wb') as output:
            for block in iter(lambda:response.read(1024*1024),b''):digest.update(block);output.write(block)
        if digest.hexdigest()!=SHA256: raise ValueError('MoGe checksum mismatch; weights were not installed.')
        temporary.replace(path);print(f'Verified {path.stat().st_size} bytes',flush=True)
    finally: temporary.unlink(missing_ok=True)

if __name__=='__main__':main()

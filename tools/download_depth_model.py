"""Download data, not executable code; verify before installing model weights."""
import argparse
import hashlib
from pathlib import Path
import urllib.request
from core.depth_model import MODEL_URL, MODEL_SHA256


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('path',nargs='?',default='models/metric-small.onnx')
    target=Path(parser.parse_args().path)
    target.parent.mkdir(parents=True,exist_ok=True)
    temporary=target.with_suffix('.download')
    digest=hashlib.sha256()
    try:
        with urllib.request.urlopen(MODEL_URL,timeout=120) as response,temporary.open('wb') as output:
            for chunk in iter(lambda:response.read(1024*1024),b''):
                digest.update(chunk);output.write(chunk)
        if digest.hexdigest()!=MODEL_SHA256:
            raise RuntimeError('Model checksum mismatch; download was not installed.')
        temporary.replace(target)
        print(f'Verified metric model: {target} ({target.stat().st_size} bytes)')
    finally:
        temporary.unlink(missing_ok=True)

if __name__=='__main__':main()

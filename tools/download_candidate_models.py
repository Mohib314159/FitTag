"""Pinned local research artifacts. Never used by a serving request."""
import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import subprocess
import urllib.request

CANDIDATES={
    'unidepth':{'repository':'lpiccinelli/unidepth-v2-vits14',
                'revision':'038c238f06c87b6c2f5b3749fd51fbf442b1f218',
                'source_commit':'8d8cfe4c7ee15297099983607febf0d4f32eb3d6',
                'source_folder':'unidepth-source',
                'files':{'model.safetensors':'93705cb3295dd7476b44911b8a55f5215bf74e8d5eccd27cecdb1b338270a648',
                         'config.json':'ecc1f898690debe387d10329cca5d9d66a0a447ce83c3a2a7ae3673c7ce43cfe'}},
    'da3':{'repository':'depth-anything/DA3METRIC-LARGE',
           'revision':'4010e39f3634a45bc60553321fb49fb760bd594e',
           'source_commit':'3d835ec1a5802d64a8b8b15f817a1ab54809bfe4','source_folder':'da3-source',
           'files':{'model.safetensors':'bbea5b0b3ee389849cffa7ddae89de064a90abd2b055fc5aa99aac68db324776',
                    'config.json':'a336f3e76fe375aaae17a9aed9130c9f2aa061535d317ec57dcb2f1f02e1dd53'}},
    'depthpro':{'repository':'apple/DepthPro',
                'revision':'ccd1350a774eb2248bcdfb3be430e38f1d3087ef',
                'source_commit':'9e65e4dbe9568d23c546fcec53302b10445e109e','source_folder':'depthpro-source',
                'files':{'depth_pro.pt':'3eb35ca68168ad3d14cb150f8947a4edf85589941661fdb2686259c80685c0ce',
                         'LICENSE':'d8f5d9dfbdb60dc81b8f1720421699e7811070f0b46f6668f90253d5ac8c0b20'}}}

def download(work,name):
    spec=CANDIDATES[name];source=work/spec['source_folder']
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()
    if commit!=spec['source_commit']:raise ValueError(f'{name}: check out the pinned author source commit first')
    folder=work/'research-models'/name;folder.mkdir(parents=True,exist_ok=True);entries=[]
    for filename,expected in spec['files'].items():
        path=folder/filename
        if path.exists():
            with path.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
            if digest!=expected:raise ValueError(f'{path}: existing artifact has another hash; leaving it untouched')
        else:
            temporary=path.with_suffix('.download');digest=hashlib.sha256();size=0
            url=f"https://huggingface.co/{spec['repository']}/resolve/{spec['revision']}/{filename}"
            try:
                with urllib.request.urlopen(url,timeout=60) as response,temporary.open('wb') as destination:
                    for block in iter(lambda:response.read(1024*1024),b''):
                        size+=len(block)
                        if size>4_000_000_000:raise ValueError('Artifact exceeds the download limit')
                        digest.update(block);destination.write(block)
                if digest.hexdigest()!=expected:raise ValueError('Downloaded hash mismatch')
                temporary.replace(path)
            finally:temporary.unlink(missing_ok=True)
        entries.append({'file':filename,'sha256':expected,'bytes':path.stat().st_size})
    manifest={'name':name,**{k:spec[k] for k in ['repository','revision','source_commit']},'files':entries}
    (folder/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(name,'verified',flush=True)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('work',type=Path)
    parser.add_argument('--candidate',choices=[*CANDIDATES,'all'],default='all');args=parser.parse_args()
    names=list(CANDIDATES) if args.candidate=='all' else [args.candidate]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda name:download(args.work.resolve(),name),names))

if __name__=='__main__':main()

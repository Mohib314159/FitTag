"""Private CLI inspection, never a claim that an auxiliary is calibrated metres."""
import argparse
import json
from pathlib import Path
from api.camera_evidence import inspect

KNOWN_AUX_TYPES={
    'urn:com:apple:photo:2020:aux:hdrgainmap':'hdr_gain_map',
    'urn:com:apple:photo:2018:aux:portraiteffectsmatte':'portrait_matte',
    'urn:com:apple:photo:2017:aux:disparity':'disparity_candidate',
}

def inspect_file(path):
    path=Path(path)
    if path.stat().st_size>12*1024*1024:raise ValueError('File exceeds the 12 MB inspection bound.')
    raw=path.read_bytes();result=inspect(raw)
    result.update(depth_layers=[],auxiliary_types=[],metric_depth_usable=False,
                  reason='No verified absolute depth, units and RGB alignment are available.')
    if path.suffix.lower() not in ('.heic','.heif'):return result
    import pillow_heif
    container=pillow_heif.open_heif(raw)
    for depth in (container.info.get('depth_images') or [])[:8]:
        # Do not dump layer metadata: it may include identifying fields or
        # undocumented values. Layer presence does not establish AVDepthData's
        # physical accuracy classification or its calibration to the RGB image.
        result['depth_layers'].append({'width':int(depth.size[0]),'height':int(depth.size[1])})
    for aux_type in list((container.info.get('aux') or {}).keys())[:16]:
        result['auxiliary_types'].append(KNOWN_AUX_TYPES.get(aux_type,'unclassified_auxiliary'))
    return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('photo',type=Path)
    result=inspect_file(parser.parse_args().photo)
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()

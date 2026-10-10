import io
from PIL import Image
from api.camera_evidence import inspect

def encoded(**tags):
    image=Image.new('RGB',(800,1000),'gray');exif=Image.Exif()
    for key,value in tags.items(): exif[int(key)]=value
    raw=io.BytesIO();image.save(raw,'JPEG',exif=exif);return raw.getvalue()

def test_numeric_metadata_is_observed_but_never_proves_absolute_scale():
    evidence=inspect(encoded(**{'41989':24,'37382':1.2,'41988':2.0,'315':'private owner name','270':'private description'}))
    assert evidence['focal_35mm']==24 and evidence['subject_distance_m']==1.2
    assert evidence['digital_zoom']==2 and not evidence['absolute_scale_verified']
    assert set(evidence)=={'focal_35mm','subject_distance_m','digital_zoom','embedded_depth_candidates','absolute_scale_verified'}
    assert 'private' not in str(evidence)

def test_missing_or_invalid_fields_are_unknown_not_fabricated_distances():
    evidence=inspect(encoded(**{'41989':0,'37382':0,'41988':0}))
    assert evidence['subject_distance_m'] is None and evidence['focal_35mm'] is None
    assert not inspect(b'broken image')['absolute_scale_verified']

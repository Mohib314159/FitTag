"""Evaluation must keep refusals visible and separate scale from contour error."""
import numpy as np
import pytest
from tools.probe_candidates import summarize
from tools.probe_geometry_control import plane_depth
from tools.inspect_photo_depth import inspect_file

def test_refused_inputs_remain_in_denominator():
    result=summarize([
        {'camera':'known','mode':'depth','absolute_errors_pct':{'waist_flat':10.},
         'absolute_errors_cm':{'waist_flat':4.}},
        {'camera':'known','mode':'refused','reason':'bad floor'},
    ])[0]
    assert result['accepted']==1 and result['total']==2
    assert result['scored_measurements']==1
    assert result['median_error_pct']==10.
    assert result['median_error_cm']==4.

def test_all_refused_is_unknown_accuracy_not_zero_error():
    result=summarize([{'camera':'estimated','mode':'refused'}])[0]
    assert result['median_error_pct'] is None
    assert result['p90_error_cm'] is None

def test_metric_plane_depth_accounts_for_tilt_and_height():
    depth=plane_depth((500,400),1500.,15.)
    normal=np.array([0.,np.sin(np.deg2rad(15)),np.cos(np.deg2rad(15))])
    y,x=np.indices(depth.shape)
    points=np.stack([(x-199.75)/450.,(y-249.75)/450.,np.ones_like(x)],axis=-1)*depth[...,None]
    assert np.allclose(points@normal,1.5,atol=1e-6)
    assert depth[0,200]>depth[-1,200]
    assert plane_depth((500,400),2000.,0.)[200,200]==pytest.approx(2.)

def test_heic_without_sensor_depth_is_not_a_metric_measurement(tmp_path):
    from PIL import Image
    from pillow_heif import register_heif_opener
    register_heif_opener(thumbnails=False)
    path=tmp_path/'plain.heic'
    Image.new('RGB',(80,100),(100,110,120)).save(path,format='HEIF')
    result=inspect_file(path)
    assert result['depth_layers']==[]
    assert result['metric_depth_usable'] is False
    assert result['absolute_scale_verified'] is False
    assert 'GPS' not in str(result)

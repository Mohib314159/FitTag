"""Independent geometry, safety and experimental contract checks."""
import io
import math
import cv2
import numpy as np
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from api import server,free_capture as api
from core import depth_model
from core.free_capture import floor_plane,focal_from_diagonal_fov,depth_measure,rectify_plane
from tests.test_phone_api import photo


@pytest.fixture
def client():
    with TestClient(server.app) as c:yield c


def request(client,raw=None,**data):
    return client.post('/measure-free',files={'file':('garment.jpg',raw or photo(False),'image/jpeg')},data=data)


def test_buttonless_shape_has_no_invented_centimetres(client,monkeypatch):
    monkeypatch.setattr(depth_model,'predict',lambda *_:pytest.fail('Shape mode must not load a model'))
    response=request(client,estimate='false')
    data=response.json()
    assert data['ok'] and data['mode']=='shape'
    assert len(data['rows'])>=5
    assert all('value_cm' not in r and 'tolerance_cm' not in r for r in data['rows'])
    assert next(r for r in data['rows'] if r['name']=='inseam')['ratio']==1
    assert response.headers['cache-control']=='no-store'
    assert client.get(data['overlay_url']).headers['cache-control']=='no-store'


def test_no_configured_model_falls_back_to_ratios(client,monkeypatch):
    monkeypatch.setattr(depth_model,'_session',None)
    monkeypatch.delenv('FITTAG_DEPTH_MODEL',raising=False)
    result=request(client).json()
    assert result['ok'] and result['mode']=='shape'
    assert 'not configured' in result['notes'][0]


def test_a_lying_consistent_model_is_not_called_validated(client,monkeypatch):
    monkeypatch.setattr(depth_model,'predict',lambda image:np.full(image.shape[:2],2.,np.float32))
    result=request(client).json()
    assert result['mode']=='depth'
    assert result['diagnostics']['floor_depth_m']==2.
    assert result['diagnostics']['focal_source']=='assumed'
    assert all('tolerance_cm' not in r for r in result['rows'])
    assert any('No error interval' in note for note in result['notes'])


def test_nonplanar_depth_keeps_shape(client,monkeypatch):
    def nonsense(image):
        y,x=np.indices(image.shape[:2]);return (1+(np.sin(x/20)+1)*.8).astype(np.float32)
    monkeypatch.setattr(depth_model,'predict',nonsense)
    result=request(client).json()
    assert result['ok'] and result['mode']=='shape'
    assert 'flat plane' in result['notes'][0]


@pytest.mark.parametrize('bad',[-1,np.nan,np.inf])
def test_invalid_depth_never_escapes_as_numbers(client,monkeypatch,bad):
    monkeypatch.setattr(depth_model,'predict',lambda image:np.full(image.shape[:2],bad,np.float32))
    result=request(client).json()
    assert result['mode']=='shape' and all('value_cm' not in r for r in result['rows'])


def test_geometric_projection_preserves_known_physical_distance():
    image=np.full((1200,900,3),235,np.uint8)
    mask=np.zeros(image.shape[:2],np.uint8)
    cv2.rectangle(mask,(250,80),(650,1120),255,-1)
    f=1000.
    # Known pinhole: 400-pixel waist at 1 metre with 1000-pixel focal = 40cm.
    _,rectified,scale=rectify_plane(image,mask,np.array([0.,0.,1.]),f)
    x,y,w,h=cv2.boundingRect(cv2.findContours(rectified,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)[0][0])
    assert abs((w-1)*scale/10-40)<.2


def test_known_tilted_plane_and_outliers_recover_plane():
    h,w=400,320;f=400.
    y,x=np.indices((h,w))
    normal=np.array([.05,.12,1/1.4])
    rays=np.stack(((x-(w-1)/2)/f,(y-(h-1)/2)/f,np.ones((h,w))),axis=-1)
    depth=(1/(rays@normal)).astype(np.float32)
    depth[30:45,30:45]*=1.3
    mask=np.zeros((h,w),np.uint8);mask[90:310,100:220]=255
    coef,diag=floor_plane(depth,mask,f)
    assert np.allclose(coef,normal,atol=.005)
    assert diag['plane_residual_pct']<1


def test_second_photo_disagreement_withholds_cm(client,monkeypatch):
    predictions=iter([1.,2.])
    monkeypatch.setattr(depth_model,'predict',lambda image:np.full(image.shape[:2],next(predictions),np.float32))
    raw=photo(False);img=Image.open(io.BytesIO(raw));buf=io.BytesIO();img.save(buf,'PNG')
    response=client.post('/measure-free',files={'file':('a.jpg',raw,'image/jpeg'),'second':('b.png',buf.getvalue(),'image/png')})
    result=response.json()
    assert result['ok'] and result['mode']=='shape' and not result['cross_check']['agreed']
    assert 'value_cm' not in result['rows'][0]


def test_identical_photo_is_not_independent(client):
    raw=photo(False)
    result=client.post('/measure-free',files={'file':('a.jpg',raw,'image/jpeg'),'second':('b.jpg',raw,'image/jpeg')}).json()
    assert not result['ok'] and 'identical' in result['error']


def test_only_numeric_focal_metadata_is_used():
    img=Image.new('RGB',(600,800),'white');exif=Image.Exif();exif[41989]=24
    buf=io.BytesIO();img.save(buf,'JPEG',exif=exif)
    assert 80<api.camera_fov(buf.getvalue())<90
    assert api.camera_fov(photo(False)) is None


@pytest.mark.parametrize('fov',['NaN','39','111'])
def test_invalid_field_of_view_refused(client,fov):
    assert request(client,fov_deg=fov).status_code==422


def test_cropped_buttonless_capture_is_refused(client):
    result=request(client,photo(False,crop=True),estimate='false').json()
    assert not result['ok'] and 'cropped' in result['error']


def test_pinned_model_hash_is_enforced(client,tmp_path,monkeypatch):
    path=tmp_path/'fake.onnx';path.write_bytes(b'not a model')
    monkeypatch.setenv('FITTAG_DEPTH_MODEL',str(path));monkeypatch.setattr(depth_model,'_session',None)
    result=request(client).json()
    assert result['mode']=='shape' and 'checksum' in result['notes'][0]


def test_supplied_camera_distance_does_not_need_a_model(client,monkeypatch):
    monkeypatch.setattr(depth_model,'predict',lambda *_:pytest.fail('Distance route must not invent depth'))
    fov=math.degrees(2*math.atan(math.hypot(900,1200)/(2*1000)))
    first=request(client,camera_height_cm=100,fov_deg=fov).json()
    second=request(client,camera_height_cm=150,fov_deg=fov).json()
    assert first['mode']==second['mode']=='distance'
    a=next(r['value_cm'] for r in first['rows'] if r['name']=='waist_flat')
    b=next(r['value_cm'] for r in second['rows'] if r['name']=='waist_flat')
    assert abs(a-41.2)<.5 and abs(b/a-1.5)<.01


@pytest.mark.parametrize('height',['NaN','10','351'])
def test_invalid_camera_distance_is_refused(client,height):
    assert request(client,camera_height_cm=height).status_code==422


def test_bad_framing_is_rejected_before_loading_depth(client,monkeypatch):
    monkeypatch.setattr(depth_model,'predict',lambda *_:pytest.fail('Bad framing must not invoke depth inference'))
    result=request(client,photo(False,crop=True)).json()
    assert not result['ok'] and 'cropped' in result['error']


def test_bad_second_photo_skips_both_depth_estimates(client,monkeypatch):
    monkeypatch.setattr(depth_model,'predict',lambda *_:pytest.fail('Validate the second outline before either model call'))
    result=client.post('/measure-free',files={
        'file':('first.jpg',photo(False),'image/jpeg'),
        'second':('second.jpg',photo(False,crop=True),'image/jpeg'),
    }).json()
    assert result['ok'] and result['mode']=='shape'
    assert 'cropped' in result['notes'][0]
    assert all('value_cm' not in row for row in result['rows'])

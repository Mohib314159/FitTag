import io
import json
import struct
import zipfile
import cv2
import numpy as np
import pytest
from core.free_capture import camera_inverse
from core.lidar_capture import fit_sensor_floor,process
from tools.import_record3d import decode,read_frame,declared_lzfse_bytes,camera
from tests.test_phone_api import photo

def archive(tmp_path,**changes):
    lib=pytest.importorskip('liblzfse')
    rgb=photo(False);image=cv2.imdecode(np.frombuffer(rgb,np.uint8),cv2.IMREAD_COLOR)
    h,w=image.shape[:2];dw,dh=75,100
    K=np.array([[1000.,0.,w/2-20],[0.,1100.,h/2+12],[0.,0.,1.]])
    meta={'w':w,'h':h,'dw':dw,'dh':dh,'K':K.T.ravel().tolist()}
    meta.update(changes.pop('metadata',{}))
    depth=np.full((dh,dw),1.2,np.float32);conf=np.full((dh,dw),2,np.uint8)
    members={'metadata':json.dumps(meta).encode(),'rgbd/0.jpg':rgb,
             'rgbd/0.depth':lib.compress(depth.tobytes()),'rgbd/0.conf':lib.compress(conf.tobytes())}
    members.update(changes)
    path=tmp_path/'capture.r3d'
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in members.items():z.writestr(name,data)
    return path,K

def test_compressed_record3d_round_trip_preserves_metres_and_camera(tmp_path):
    path,K=archive(tmp_path)
    image,depth,confidence,got=read_frame(path)
    assert depth.shape==(100,75) and np.allclose(depth,1.2)
    assert np.all(confidence==2) and np.allclose(got,K)
    rect,result=process(image,depth,confidence,K,'jeans')
    assert result['mode']=='lidar' and len(result['rows'])==5
    assert result['diagnostics']['floor_depth_m']==pytest.approx(1.2,abs=.001)
    assert rect.size>0

def test_lidar_geometry_uses_anisotropic_focal_and_offcentre_principal_point():
    K=np.array([[100.,0.,32.],[0.,120.,55.],[0.,0.,1.]])
    yy,xx=np.indices((100,80));rays=np.stack([xx,yy,np.ones_like(xx)],axis=-1)@np.linalg.inv(K).T
    coefficient=np.array([.1,.2,1/1.2]);depth=1/(rays@coefficient)
    mask=np.zeros((100,80),np.uint8);mask[30:70,25:55]=255
    got,_=fit_sensor_floor(depth,np.full(depth.shape,2,np.uint8),mask,K)
    assert np.allclose(got,coefficient,atol=1e-6)
    assert np.allclose(camera_inverse(depth.shape,K),np.linalg.inv(K))

def test_low_confidence_or_nonfinite_depth_is_refused():
    K=np.array([[100.,0.,40.],[0.,100.,50.],[0.,0.,1.]])
    mask=np.zeros((100,80),np.uint8)
    for depth,confidence in [(np.full(mask.shape,np.nan),np.full(mask.shape,2)),
                             (np.ones(mask.shape),np.zeros(mask.shape))]:
        with pytest.raises(ValueError,match='high-confidence'):fit_sensor_floor(depth,confidence,mask,K)

def test_unsafe_archive_is_not_extracted(tmp_path):
    path,_=archive(tmp_path,**{'../outside.txt':b'no'})
    with pytest.raises(ValueError,match='Unsafe'):read_frame(path)
    assert not (tmp_path.parent/'outside.txt').exists()

def test_image_camera_size_mismatch_is_refused(tmp_path):
    path,_=archive(tmp_path,metadata={'w':1200,'h':1600})
    with pytest.raises(ValueError,match='orientation or size'):read_frame(path)

def test_different_rgb_depth_crops_are_not_silently_resized(tmp_path):
    path,_=archive(tmp_path,metadata={'dw':80})
    with pytest.raises(ValueError,match='different crops'):read_frame(path)

def test_compressed_expansion_is_checked_before_native_decode():
    with pytest.raises(ValueError,match='expands'):declared_lzfse_bytes(b'bvx-'+struct.pack('<I',1000000000)+b'bvx$',16)
    with pytest.raises(ValueError,match='Truncated'):declared_lzfse_bytes(b'bvx-'+struct.pack('<I',16)+b'xx',16)

def test_per_frame_camera_replaces_static_camera():
    meta={'K':[1.,0,0,0,1.,0,0,0,1.], 'perFrameIntrinsicCoeffs':[[300.,310.,200.,250.]]}
    K=camera(meta,0)
    assert K[0,0]==300 and K[1,1]==310 and K[0,2]==200 and K[1,2]==250

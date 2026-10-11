import cv2
import numpy as np
import pytest
from core.measure import measure_jeans

@pytest.mark.parametrize('scale',[1.,2.])
def test_close_set_legs_do_not_shift_crotch_downward(scale):
    # Two long legs part through a narrow, persistent gap. Gap grows slowly;
    # merging six-pixel gaps used to lose several centimetres of inseam.
    points=np.array([(0,0),(400,0),(400,1000),(220,1000),(202,300),
                     (198,300),(180,1000),(0,1000)],np.int32).reshape(-1,1,2)
    rows={row.name:row for row in measure_jeans(points,scale,crotch_gap=1)}
    assert rows['inseam'].p1[1]==pytest.approx(300,abs=2)
    assert rows['inseam'].value_cm==pytest.approx(70.*scale,abs=.3*scale)

def test_contiguous_legs_do_not_invent_an_inseam():
    points=np.array([(0,0),(400,0),(400,1000),(0,1000)],np.int32).reshape(-1,1,2)
    assert 'inseam' not in {row.name for row in measure_jeans(points,1.)}

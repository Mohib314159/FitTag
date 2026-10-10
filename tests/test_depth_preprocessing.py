import numpy as np
import pytest
from core import depth_model

class Runtime:
    def __init__(self): self.tensor=None
    def get_inputs(self): return [type('Input',(),{'name':'input'})()]
    def run(self,_,feed):
        self.tensor=feed['input']
        # An input-space ramp proves unpadding, rather than returning a constant.
        return [np.broadcast_to(np.arange(392,dtype=np.float32)[:,None]+1,(392,392))[None]]

@pytest.mark.parametrize('shape',[(1000,800),(800,1000),(1200,600),(600,1200)])
def test_aspect_preserving_experiments_restore_the_original_depth_coordinates(monkeypatch,shape):
    runtime=Runtime();monkeypatch.setattr(depth_model,'session',lambda:runtime)
    photo=np.zeros((*shape,3),np.uint8)
    depth=depth_model.predict(photo,preprocessing='letterbox')
    assert depth.shape==shape and np.isfinite(depth).all()
    assert runtime.tensor.shape==(1,3,392,392)
    if shape[1]>shape[0]:
        assert depth[0,0]>1 and depth[-1,0]<392
    else:
        assert depth[0,0]==1 and depth[-1,0]==392

def test_unknown_preprocessing_does_not_silently_change_the_model(monkeypatch):
    monkeypatch.setattr(depth_model,'session',lambda:Runtime())
    with pytest.raises(ValueError,match='Unknown'):depth_model.predict(np.zeros((800,600,3),np.uint8),'unknown')

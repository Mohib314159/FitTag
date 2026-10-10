import asyncio
import threading
import httpx
import numpy as np

from api import server, free_capture
from api.capacity import ComputeGate, bounded_env
from core import depth_model
from tests.test_jobs import wait_for
from tests.test_phone_api import photo


def test_parallel_api_has_two_independent_slots_and_refuses_a_third(monkeypatch):
    gate=ComputeGate(2)
    monkeypatch.setattr(server,'MEASURE_LOCK',gate)
    released=threading.Event()
    def process(*args):
        args[-1]('depth')
        assert released.wait(5)
        return None,{'ok':True,'camera':args[3]}
    monkeypatch.setattr(free_capture,'process',process)
    monkeypatch.setattr(free_capture,'persist',lambda rect,result:result)
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app),base_url='http://test') as client:
            try:
                responses=[]
                for fov in (84,85):
                    reply=await client.post('/measure-free-jobs',data={'fov_deg':fov},files={'file':('a.jpg',photo(False),'image/jpeg')})
                    assert reply.status_code==202
                    responses.append(reply.json()['status_url'])
                assert gate.active==2 and responses[0]!=responses[1]
                assert (await client.get('/experiment')).json()['parallel_photos']==2
                assert (await client.post('/measure-free-jobs',files={'file':('a.jpg',photo(False),'image/jpeg')})).status_code==429
                assert (await client.get('/health')).status_code==200
            finally:
                released.set()
                await wait_for(lambda:gate.active==0)
            values=[(await client.get(url)).json()['result']['camera'] for url in responses]
            assert values==[84,85]
    asyncio.run(scenario())


def test_runtime_settings_are_bounded(monkeypatch):
    for value,expected in [('0',1),('20',4),('bad',1),('2',2)]:
        monkeypatch.setenv('TEST_FITTAG_THREADS',value)
        assert bounded_env('TEST_FITTAG_THREADS',1,4)==expected


def test_smaller_intermediate_rgb_arrays_preserve_model_input(monkeypatch):
    import cv2
    rng=np.random.default_rng(14);photo=rng.integers(0,256,(800,600,3),dtype=np.uint8)
    captured=[]
    class Runtime:
        def get_inputs(self):
            return [type('Input',(),{'name':'photo'})()]
        def run(self,_,values):
            captured.append(values['photo'])
            return [np.ones((1,392,392),np.float32)]
    monkeypatch.setattr(depth_model,'session',lambda:Runtime())
    depth_model.predict(photo)
    old=cv2.cvtColor(photo,cv2.COLOR_BGR2RGB).astype(np.float32)/255
    old=cv2.resize(old,(392,392),interpolation=cv2.INTER_CUBIC)
    old=(old-np.array([.485,.456,.406],np.float32))/np.array([.229,.224,.225],np.float32)
    assert np.allclose(captured[0],old.transpose(2,0,1)[None],atol=3e-6)

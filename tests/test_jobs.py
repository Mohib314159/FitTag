import asyncio
import threading
import time

import httpx
import pytest

from api import jobs
from api import free_capture
from api.server import app, MEASURE_LOCK
from tests.test_free_capture import photo


async def wait_for(predicate):
    for _ in range(200):
        if predicate():
            return
        await asyncio.sleep(.02)
    raise AssertionError('Worker did not reach the expected state')


def test_job_success_exposes_real_stages_and_private_result(monkeypatch):
    def process(*args):
        args[-1]('geometry')
        return None, {'ok': True, 'mode': 'shape', 'rows': []}
    monkeypatch.setattr(free_capture, 'process', process)
    monkeypatch.setattr(free_capture, 'persist', lambda rect, result: result)
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            accepted = await client.post('/measure-free-jobs', files={'file': ('a.jpg', photo(False), 'image/jpeg')})
            assert accepted.status_code == 202
            url = accepted.json()['status_url']
            assert accepted.headers['location'] == url and len(url.rsplit('/', 1)[1]) == 32
            await wait_for(lambda: not MEASURE_LOCK.locked())
            reply = await client.get(url)
            assert reply.headers['cache-control'] == 'no-store'
            assert reply.json()['status'] == 'succeeded'
            assert reply.json()['stage'] == 'finishing'
            assert reply.json()['result']['mode'] == 'shape'
            assert not any(key in reply.json() for key in ('raw', 'photo', 'exif'))
            assert (await client.get('/measurement-jobs/not-a-job')).status_code == 404
    asyncio.run(scenario())


def test_busy_cancel_and_health_keep_slot_until_native_work_finishes(monkeypatch):
    started, release = threading.Event(), threading.Event()
    def process(*args):
        args[-1]('depth')
        started.set()
        assert release.wait(5)
        return None, {'ok': True}
    monkeypatch.setattr(free_capture, 'process', process)
    monkeypatch.setattr(free_capture, 'persist', lambda *_: pytest.fail('Cancelled work must not persist an overlay'))
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            try:
                accepted = await client.post('/measure-free-jobs', files={'file': ('a.jpg', photo(False), 'image/jpeg')})
                url = accepted.json()['status_url']
                await wait_for(started.is_set)
                assert (await client.get(url)).json()['stage'] == 'depth'
                busy = await client.post('/measure-free-jobs', files={'file': ('a.jpg', photo(False), 'image/jpeg')})
                assert busy.status_code == 429 and busy.headers['retry-after'] == '5'
                assert (await client.get('/health')).status_code == 200
                assert (await client.delete(url)).json()['status'] == 'cancelled'
                assert (await client.get(url)).json()['status'] == 'cancelled'
                assert MEASURE_LOCK.locked()
            finally:
                release.set()
                await wait_for(lambda: not MEASURE_LOCK.locked())
            assert 'result' not in (await client.get(url)).json()
    asyncio.run(scenario())


def test_decode_failure_releases_slot_and_no_job_is_created():
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            count = len(jobs.jobs)
            reply = await client.post('/measure-free-jobs', files={'file': ('a.jpg', b'bad', 'image/jpeg')})
            assert reply.status_code == 400
            assert not MEASURE_LOCK.locked() and len(jobs.jobs) == count
            invalid = await client.post('/measure-free-jobs', data={'fov_deg': 'nan'}, files={'file': ('a.jpg', b'bad', 'image/jpeg')})
            assert invalid.status_code == 422
    asyncio.run(scenario())


def test_combined_upload_limit_is_enforced_before_creating_work():
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            raw = photo(False)
            padded = raw + b'x' * (int(6.2 * 1024 * 1024) - len(raw))
            count = len(jobs.jobs)
            reply = await client.post('/measure-free-jobs', files={
                'file': ('a.jpg', padded, 'image/jpeg'), 'second': ('b.jpg', padded, 'image/jpeg')})
            assert reply.status_code == 413 and 'combined' in reply.json()['detail']
            assert not MEASURE_LOCK.locked() and len(jobs.jobs) == count
    asyncio.run(scenario())


def test_worker_failure_is_recoverable_and_does_not_leak_internal_paths(monkeypatch):
    def broken(*_):
        raise RuntimeError('C:/private/model/path')
    monkeypatch.setattr(free_capture, 'process', broken)
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            reply = await client.post('/measure-free-jobs', files={'file': ('a.jpg', photo(False), 'image/jpeg')})
            await wait_for(lambda: not MEASURE_LOCK.locked())
            result = (await client.get(reply.json()['status_url'])).json()
            assert result['status'] == 'failed'
            assert 'private' not in result['error']
    asyncio.run(scenario())


def test_retention_is_bounded_and_active_jobs_are_not_evicted(monkeypatch):
    now = time.monotonic()
    state = {'active': jobs.Job()}
    state.update({str(i): jobs.Job(status='succeeded', finished=now-i) for i in range(30)})
    state['expired'] = jobs.Job(status='succeeded', finished=now-jobs.TTL_SECONDS-1)
    monkeypatch.setattr(jobs, 'jobs', state)
    jobs.prune(now)
    assert len(state) == jobs.MAX_JOBS
    assert 'active' in state and 'expired' not in state


def test_real_shape_job_returns_proportions_without_cm():
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            reply = await client.post('/measure-free-jobs', data={'estimate': 'false'}, files={'file': ('a.jpg', photo(False), 'image/jpeg')})
            await wait_for(lambda: not MEASURE_LOCK.locked())
            result = (await client.get(reply.json()['status_url'])).json()['result']
            assert result['mode'] == 'shape' and len(result['rows']) == 5
            assert all('value_cm' not in row for row in result['rows'])
    asyncio.run(scenario())

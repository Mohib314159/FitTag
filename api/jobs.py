"""Bounded, ephemeral HTTP jobs for a single-worker photo service.

No broker or disk persistence: a restart loses jobs, which the client explains.
All state mutations happen on the event loop. Worker progress is marshalled back.
"""
import asyncio
import time
import uuid
from dataclasses import dataclass, field

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

router = APIRouter()
TTL_SECONDS = 600
MAX_JOBS = 20
jobs = {}
tasks = set()


@dataclass
class Job:
    status: str = 'running'
    stage: str = 'outline'
    created: float = field(default_factory=time.monotonic)
    finished: float | None = None
    result: dict | None = None
    error: str | None = None
    cancelled: bool = False


def prune(now=None, reserve=0):
    now = time.monotonic() if now is None else now
    for key, job in list(jobs.items()):
        if job.finished is not None and now - job.finished > TTL_SECONDS:
            del jobs[key]
    # Active/cancelled-but-still-computing jobs must never be evicted.
    done = sorted(((key, job) for key, job in jobs.items() if job.finished is not None),
                  key=lambda item: item[1].finished)
    for key, _ in done[:max(0, len(jobs) - MAX_JOBS + reserve)]:
        del jobs[key]


def get_job(key):
    prune()
    if key not in jobs:
        raise HTTPException(404, 'This result expired or the server restarted. Your photo can be sent again.')
    return jobs[key]


@router.post('/measure-free-jobs')
async def submit(file: UploadFile = File(...), garment_type: str = Form('jeans'),
                 fov_deg: float = Form(0), second: UploadFile | None = File(None),
                 estimate: bool = Form(True), camera_height_cm: float = Form(0)):
    import numpy as np
    from api.server import MEASURE_LOCK, _decode
    if garment_type not in ('jeans', 't-shirt') or not np.isfinite(fov_deg) or (fov_deg != 0 and not 40 <= fov_deg <= 110):
        raise HTTPException(422, 'Choose a supported garment and a field of view between 40 and 110 degrees.')
    if not np.isfinite(camera_height_cm) or (camera_height_cm != 0 and not 35 <= camera_height_cm <= 350):
        raise HTTPException(422, 'Camera height must be a known lens-to-floor distance between 35 and 350 cm.')
    if MEASURE_LOCK.locked():
        return JSONResponse({'ok': False, 'error': 'Another photo is being measured. Try again in a few seconds.'},
                            429, headers={'Retry-After': '5'})
    # Admission happens before decoding. There is no unbounded work queue.
    await MEASURE_LOCK.acquire()
    admitted = False
    try:
        photo, raw = await _decode(file)
        other, other_raw = await _decode(second) if second else (None, None)
        if len(raw) + len(other_raw or b'') > 12 * 1024 * 1024:
            raise HTTPException(413, 'The combined photos must be smaller than 12 MB.')
        if other_raw is not None and other_raw == raw:
            raise HTTPException(422, 'The second photo is identical. Take a fresh photo.')
        prune(reserve=1)
        key = uuid.uuid4().hex
        job = Job()
        jobs[key] = job
        loop = asyncio.get_running_loop()

        def progress(stage):
            if job.cancelled:
                raise ValueError('Cancelled')
            loop.call_soon_threadsafe(set_stage, stage)

        def set_stage(stage):
            if not job.cancelled:
                job.stage = stage

        def work():
            from api.free_capture import process, persist
            rect, result = process(photo, raw, garment_type, fov_deg, other, other_raw,
                                   estimate, camera_height_cm, progress)
            progress('finishing')
            return persist(rect, result)

        async def execute():
            try:
                result = await run_in_threadpool(work)
                if not job.cancelled:
                    if result.get('ok'):
                        job.result, job.status = result, 'succeeded'
                    else:
                        job.error, job.status = result.get('error'), 'failed'
            except ValueError as exc:
                if not job.cancelled:
                    job.error, job.status = str(exc), 'failed'
            except Exception:
                if not job.cancelled:
                    job.error = 'Could not finish this photo. Try a smaller JPEG on a plain floor.'
                    job.status = 'failed'
            finally:
                job.finished = time.monotonic()
                MEASURE_LOCK.release()

        task = asyncio.create_task(execute())
        tasks.add(task)
        task.add_done_callback(tasks.discard)
        admitted = True
        location = '/measurement-jobs/' + key
        return JSONResponse({'ok': True, 'status_url': location}, 202,
                            headers={'Location': location, 'Retry-After': '1'})
    finally:
        if not admitted:
            MEASURE_LOCK.release()
        await file.close()
        if second:
            await second.close()


@router.get('/measurement-jobs/{key}')
async def status(key: str):
    job = get_job(key)
    body = {'ok': True, 'status': job.status, 'stage': job.stage,
            'elapsed_seconds': round((job.finished or time.monotonic()) - job.created, 1)}
    if job.result is not None:
        body['result'] = job.result
    if job.error:
        body['error'] = job.error
    return JSONResponse(body, headers={'Retry-After': '1'})


@router.delete('/measurement-jobs/{key}')
async def cancel(key: str):
    job = get_job(key)
    job.cancelled = True
    job.status, job.result, job.error = 'cancelled', None, None
    # Native inference may finish; its slot stays occupied until then.
    return {'ok': True, 'status': 'cancelled'}

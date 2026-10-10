"""Pinned CPU ONNX metric model. No remote calls or downloads during a request."""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import threading
import cv2
import numpy as np

MODEL_REVISION = '86f40563e7e87a0839be758988aa804930409a61'
MODEL_SHA256 = '50dbcac7a6d667e365a3ceffdf51cc497aa5e06b6d2c1d5824c252640fbf5bf3'
MODEL_URL = f'https://huggingface.co/kornia/depth-anything/resolve/{MODEL_REVISION}/depth-anything-v2-metric-small-indoor.onnx'
_session = None
_lock = threading.Lock()


def available():
    path = os.environ.get('FITTAG_DEPTH_MODEL','')
    return bool(path and Path(path).is_file())


def session():
    global _session
    with _lock:
        if _session is None:
            path = os.environ.get('FITTAG_DEPTH_MODEL','')
            if not path or not Path(path).is_file():
                raise ValueError('Depth model is not configured. Your outline still works; centimetres are unavailable.')
            digest = hashlib.sha256()
            with open(path,'rb') as f:
                for block in iter(lambda:f.read(1024*1024),b''): digest.update(block)
            if digest.hexdigest() != MODEL_SHA256:
                raise ValueError('Depth model checksum does not match the pinned metric model. Showing proportions only.')
            try:
                import onnxruntime as ort
                options = ort.SessionOptions()
                from api.capacity import bounded_env
                options.intra_op_num_threads = bounded_env('FITTAG_DEPTH_THREADS', 1, 4)
                options.inter_op_num_threads = 1
                options.add_session_config_entry('session.intra_op.allow_spinning', '0')
                options.add_session_config_entry('session.inter_op.allow_spinning', '0')
                options.enable_cpu_mem_arena = False
                options.enable_mem_pattern = False
                _session = ort.InferenceSession(path,sess_options=options,providers=['CPUExecutionProvider'])
            except ImportError:
                raise ValueError('The depth runtime is unavailable. Showing proportions only.') from None
            except Exception:
                raise ValueError('The depth model could not load. Showing proportions only.') from None
        return _session


def predict(photo):
    runtime = session()
    # Fixed 392-square export; training uses RGB ImageNet normalization.
    # Resize before allocating RGB float arrays: same per-channel interpolation.
    small = cv2.resize(photo.astype(np.float32),(392,392),interpolation=cv2.INTER_CUBIC)
    rgb = cv2.cvtColor(small,cv2.COLOR_BGR2RGB).astype(np.float32)/255.
    rgb = (rgb-np.array([.485,.456,.406],np.float32))/np.array([.229,.224,.225],np.float32)
    tensor = np.ascontiguousarray(rgb.transpose(2,0,1)[None])
    try:
        depth = runtime.run(None,{runtime.get_inputs()[0].name:tensor})[0].squeeze()
    except Exception:
        raise ValueError('Depth inference failed. Showing proportions only.') from None
    if depth.ndim != 2:
        raise ValueError('The metric model returned an unexpected output. Showing proportions only.')
    return cv2.resize(depth,photo.shape[1::-1],interpolation=cv2.INTER_LINEAR)

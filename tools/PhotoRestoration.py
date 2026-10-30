"""One GaterV3 1x pass after faces, before optional SR.

The session is request-local so DirectML allocations cannot survive into the
next Kobold diffusion request. PNG provenance prevents repeated restoration.
"""
from pathlib import Path
import hashlib
import json
import time
import threading
import re

from RuntimePaths import ROOT, asset

MARKER_KEY = 'kcpp_photo_restoration'
MODEL_SHA = '6653528b62fe763403e18fa33a21c28755b27006e15d6be4b2c2c56c7ca4d27b'
KIND = 'gater-v3-restore-1x-v1'
_VERIFIED={}
_LOCK=threading.RLock()


def expected_sha(options):
    value=options.get('model_sha256',MODEL_SHA)
    if not isinstance(value,str) or not re.fullmatch(r'[0-9a-f]{64}',value):raise ValueError('Pinned restoration model SHA256 required')
    return value

def verified_model(options):
    model=Path(asset(options.get('model',''),ROOT)).resolve()
    if not model.is_relative_to(ROOT.resolve()) or not model.is_file() or not expected_sha(options):
        raise ValueError('Validated portable Gater model is missing or mismatched')
    with _LOCK:
        stat=model.stat();identity=(stat.st_size,stat.st_mtime_ns,stat.st_ino,stat.st_dev)
        if _VERIFIED.get((str(model),expected_sha(options)))!=identity:
            digest=hashlib.sha256()
            with model.open('rb') as stream:
                for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
            after=model.stat()
            if (after.st_size,after.st_mtime_ns,after.st_ino,after.st_dev)!=identity or digest.hexdigest()!=expected_sha(options):
                raise ValueError('Gater model changed or fingerprint mismatch')
            _VERIFIED[(str(model),expected_sha(options))]=identity
    return model


def prewarm_model(options):
    if not options.get('enabled',False):return dict(enabled=False,ok=True)
    started=time.perf_counter();model=verified_model(options)
    return dict(enabled=True,ok=True,model_sha256=expected_sha(options),model_bytes=model.stat().st_size,
                seconds=time.perf_counter()-started,GPU_session_created=False)


def rgb_sha(image):
    return hashlib.sha256(image.convert('RGB').tobytes()).hexdigest()


def matching_marker(image, options):
    if not options.get('enabled', False):
        return None
    try:
        marker = json.loads(image.info.get(MARKER_KEY, ''))
        if (marker.get('kind') == KIND and marker.get('model_sha256') == expected_sha(options)
                and marker.get('passes') == 1 and marker.get('strength') == 1
                and marker.get('output_dimensions') == list(image.size)
                and marker.get('rgb_sha256') == rgb_sha(image)):
            return marker
    except (ValueError, TypeError, AttributeError):
        pass
    return None


def attach_marker(image, marker):
    """Bind provenance to the final pixels, including an optional subsequent SR."""
    if marker:
        marker = {**marker, 'rgb_sha256': rgb_sha(image), 'output_dimensions': list(image.size)}
        image.info[MARKER_KEY] = json.dumps(marker, separators=(',', ':'))
    return image


def restore_once(image, options, prior=None):
    if not options.get('enabled', False):
        return image, dict(enabled=False, applied=False, seconds=0), None
    if options.get('provider', 'directml') != 'directml' or float(options.get('strength', 1)) != 1:
        raise ValueError('The validated Gater profile requires DirectML FP32 at strength1')
    expected_sha(options)
    prior = prior or matching_marker(image, options)
    if prior:
        return image, dict(enabled=True, applied=False, already_processed=True,
                           model_sha256=expected_sha(options), seconds=0), prior
    started = time.perf_counter()
    model = verified_model(options)

    import numpy as np
    import onnxruntime as ort
    from PIL import Image
    from GpuAdapter import select_dml_adapter

    session = None
    try:
        adapter = select_dml_adapter()
        settings = ort.SessionOptions()
        settings.intra_op_num_threads = 1
        settings.inter_op_num_threads = 1
        settings.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        settings.enable_mem_pattern = False
        settings.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_BASIC
        session = ort.InferenceSession(str(model), sess_options=settings,
            providers=[('DmlExecutionProvider', {'device_id': str(adapter['index'])}), 'CPUExecutionProvider'])
        # ORT may retry a failed DML initialization with a CPU-only provider.
        if not session.get_providers() or session.get_providers()[0] != 'DmlExecutionProvider':
            raise RuntimeError('Gater DirectML initialization failed; CPU inference is disabled')
        session.disable_fallback()
        feeds, outputs = session.get_inputs(), session.get_outputs()
        if len(feeds) != 1 or len(outputs) != 1 or feeds[0].type != 'tensor(float)' or len(feeds[0].shape) != 4:
            raise RuntimeError('Unexpected Gater FP32 NCHW contract')
        ready_seconds = time.perf_counter() - started
        original = np.asarray(image.convert('RGB'), dtype=np.uint8)
        tensor = np.ascontiguousarray(original.transpose(2, 0, 1)[None].astype(np.float32) / 255.0)
        tick = time.perf_counter()
        raw = session.run(None, {feeds[0].name: tensor})[0]
        inference_seconds = time.perf_counter() - tick
        if raw.shape != tensor.shape or not np.isfinite(raw).all():
            raise RuntimeError('Gater changed geometry or produced non-finite pixels')
        pixels = np.rint(np.clip(raw[0].transpose(1, 2, 0), 0, 1) * 255).astype(np.uint8)
        result = Image.fromarray(pixels)
        result.info.update(image.info)
        marker = dict(kind=KIND, model_sha256=expected_sha(options), strength=1, passes=1,
                      restored_dimensions=list(image.size), input_rgb_sha256=rgb_sha(image))
        result = attach_marker(result, marker)
        marker = json.loads(result.info[MARKER_KEY])
        return result, dict(enabled=True, applied=True, already_processed=False, model_sha256=expected_sha(options),
                            provider='DirectML FP32', scale=1, whole_frame=True, adapter=adapter,
                            model_ready_seconds=ready_seconds, inference_seconds=inference_seconds,
                            seconds=time.perf_counter() - started), marker
    finally:
        # No persistent GPU allocation competes with the next diffusion request.
        if session is not None:
            del session

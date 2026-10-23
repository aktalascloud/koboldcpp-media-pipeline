"""Portable Helaman ATD FP32 worker. One request owns one GPU process."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import tempfile
import time

from PIL import Image
from RuntimePaths import ROOT, asset


def configured_output_scale(options):
    value = options.get('output_scale', 2)
    if type(value) is not int or value not in (2, 4):
        raise ValueError('Helaman output_scale must be2 or4')
    return value


class HelamanUpscaler:
    def __init__(self, options):
        self.options = dict(options)
        self.output_scale = configured_output_scale(options)
        self.worker = Path(asset(options['worker'], ROOT))
        self.model = Path(asset(options['model'], ROOT))
        for path in (self.worker, self.model, self.model.with_name(self.model.name+'.data')):
            if not path.is_relative_to(ROOT) or not path.is_file():
                raise ValueError('Missing portable Helaman asset: '+str(path))
        self.metadata = dict(model_sha256=hashlib.sha256(self.model.read_bytes()).hexdigest())
        expected = options.get('model_sha256')
        if expected and expected != self.metadata['model_sha256']:
            raise ValueError('Helaman model hash mismatch')

    def close(self):
        # Every call waits for its own worker to exit; no GPU session survives.
        pass

    def upscale(self, image):
        started = time.perf_counter()
        portable_root = ROOT.resolve()
        temporary = (portable_root/'runtime/tmp').resolve()
        if not temporary.is_relative_to(portable_root) or temporary == portable_root:
            raise ValueError('Helaman temporary parent must resolve inside portable ROOT')
        temporary.mkdir(parents=True, exist_ok=True)
        budget = max(30, min(1800, int(self.options.get('timeout_seconds', 1800))))
        with tempfile.TemporaryDirectory(prefix='helaman-', dir=temporary) as folder:
            folder = Path(folder).resolve()
            if folder.parent != temporary or not folder.name.startswith('helaman-'):
                raise RuntimeError('Helaman private temporary folder escaped its verified parent')
            incoming, output, proof = folder/'input.png', folder/'output.png', folder/'proof.json'
            image.convert('RGB').save(incoming)
            command = [str(ROOT/'runtime/python/python.exe'), '-I', '-B', str(self.worker),
                       '--input', str(incoming), '--output', str(output), '--proof', str(proof),
                       '--model', str(self.model), '--context', str(self.options.get('context',32)),
                       '--max-seconds', str(budget)]
            if self.output_scale == 4:
                command.extend(['--output-scale', '4'])
            environment = dict(os.environ, TMP=str(temporary), TEMP=str(temporary))
            completed = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True,
                                       text=True, encoding='utf-8', errors='replace',
                                       timeout=budget+60, creationflags=subprocess.CREATE_NO_WINDOW)
            report = json.loads(proof.read_text(encoding='utf-8')) if proof.exists() else {}
            if completed.returncode or report.get('status') != 'completed':
                raise RuntimeError('Helaman failed: '+str(report.get('error') or completed.stderr[-1500:]))
            if report.get('model_sha256') != self.metadata['model_sha256']:
                raise RuntimeError('Helaman worker used an unexpected model')
            reported_scale = report.get('output_scale', 2 if self.output_scale == 2 else None)
            if reported_scale != self.output_scale:
                raise RuntimeError('Helaman worker output_scale contract mismatch; no scale fallback')
            with Image.open(output) as opened:
                final = opened.convert('RGB')
                final.load()
            if final.size != (image.width*self.output_scale, image.height*self.output_scale):
                raise RuntimeError('Helaman output must be exactly'+str(self.output_scale)+'x; no scale fallback')
            # The transient per-node ORT profile and intermediate4x tensors are
            # intentionally removed with this request's verified private folder.
            information = dict(provider='DirectML FP32', native_scale=4, output_scale=self.output_scale, upscaling_resize=self.output_scale,
                               model=self.options.get('name','Helaman ATD'),
                               model_sha256=self.metadata['model_sha256'],
                               worker_seconds=report.get('seconds'),
                               inference_seconds=report.get('inference_seconds'),
                               tile_count=report.get('tile_count'),
                               tile_dimensions=report.get('tile_dimensions'),
                               adapter=report.get('adapter'),
                               experimental_tiling=True, whole_image_equivalence=False,
                               sort_policy=report.get('sort_policy'),
                               seconds=time.perf_counter()-started)
            return final, information

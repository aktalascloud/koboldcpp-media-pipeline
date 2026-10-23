"""Set local dependency/cache paths for Helaman experiments; no global settings."""
from pathlib import Path
import os
import sys
import tempfile

R=Path(__file__).resolve().parent
ROOT=R.parent.parent


def setup(threads=2,shared_ort=False):
    for folder in ('tmp','cache','proof','artifacts'):
        (R/folder).mkdir(exist_ok=True)
    tempfile.tempdir=str(R/'tmp')
    os.environ['TMP']=str(R/'tmp');os.environ['TEMP']=str(R/'tmp')
    os.environ['TORCH_HOME']=str(R/'cache/torch')
    os.environ['TORCHINDUCTOR_CACHE_DIR']=str(R/'cache/inductor')
    os.environ['OMP_NUM_THREADS']=str(threads);os.environ['MKL_NUM_THREADS']=str(threads)
    sys.path.insert(0,str(R/'deps'))
    if shared_ort:
        # Read-only use of the installed DirectML/OpenVINO runtimes. CPU provider
        # must be explicit until Root releases the GPU benchmark queue.
        sys.path.append(str(ROOT/'runtime/python/Lib/site-packages'))
    sys.stdout.reconfigure(encoding='utf-8',errors='backslashreplace')
    sys.stderr.reconfigure(encoding='utf-8',errors='backslashreplace')


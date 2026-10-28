"""Bounded, non-pickle Wan5B decoder input captured by the owned Native worker."""
from pathlib import Path
import hashlib,struct
import numpy as np
def read_wan_latents(path,root,expected_sha256=None):
    root=Path(root).resolve();path=Path(path).resolve()
    if not any(path.is_relative_to(root/p) for p in ['runtime/tmp','RESULTS/Video','OUTPUTS/video']):raise ValueError('Unexpected latent snapshot location')
    size=path.stat().st_size
    if not 60<size<=128*1024**2+60:raise ValueError('Wan snapshot exceeds bounds')
    raw=path.read_bytes();magic,dimensions,count=struct.unpack('<8sIQ',raw[:20]);shape=struct.unpack('<5q',raw[20:60])
    if magic!=b'KCPPWLAT' or dimensions!=5 or any(x<=0 for x in shape) or shape[3:]!=(48,1):raise ValueError('Unsupported Wan snapshot header')
    if int(np.prod(shape,dtype=np.int64))!=count or size!=60+count*4 or shape[2]>31 or shape[0]*shape[1]*256>2_000_000:raise ValueError('Invalid Wan snapshot geometry')
    digest=hashlib.sha256(raw).hexdigest()
    if expected_sha256 and digest!=expected_sha256:raise ValueError('Wan snapshot changed')
    tensor=np.frombuffer(raw,dtype='<f4',offset=60).reshape(tuple(reversed(shape))).copy()
    if not np.isfinite(tensor).all():raise ValueError('Wan latent contains nonfinite values')
    return tensor,dict(sha256=digest,bytes=size,shape=list(tensor.shape),frames=(shape[2]-1)*4+1,width=shape[0]*16,height=shape[1]*16,normalization='raw full-Wan posterior mean')

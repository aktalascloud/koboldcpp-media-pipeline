"""Very light, CPU-only chroma denoise; no diffusion or luminance smoothing."""
import hashlib
import json
import time
from RuntimePaths import dependencies
dependencies()
import cv2
import numpy as np
from PIL import Image


def denoise(image,options=None):
    options=options or {}
    if not options.get('enabled',False):return image,dict(enabled=False,seconds=0)
    mode=options.get('mode','chroma_bilateral')
    sigma=float(options.get('sigma',8));amount=float(options.get('amount',1))
    if mode!='chroma_bilateral' or not 2<=sigma<=32 or not 0<=amount<=1:raise ValueError('Invalid chroma denoise settings')
    signature=hashlib.sha256(json.dumps(dict(mode=mode,sigma=sigma,amount=amount),sort_keys=True).encode()).hexdigest()[:16]
    if image.info.get('kcpp_proxy_denoise')==signature:return image,dict(enabled=True,already_processed=True,seconds=0,applied=False)
    start=time.perf_counter()
    x=np.asarray(image.convert('RGB'),dtype=np.float32)
    rr,gg,bb=cv2.split(x)
    yy=.25*rr+.5*gg+.25*bb;co=rr-bb;cg=gg-.5*(rr+bb)
    smooth=cv2.bilateralFilter(cv2.merge((yy,co,cg)),3,sigma,1)
    co+=amount*(smooth[:,:,1]-co);cg+=amount*(smooth[:,:,2]-cg)
    temp=yy-.5*cg
    result=cv2.merge((temp+.5*co,yy+.5*cg,temp-.5*co))
    final=Image.fromarray(np.rint(result).clip(0,255).astype(np.uint8))
    if 'A' in image.getbands():final=final.convert('RGBA');final.putalpha(image.getchannel('A'))
    final.info.update(image.info);final.info['kcpp_proxy_denoise']=signature
    return final,dict(enabled=True,applied=True,mode=mode,sigma=sigma,amount=amount,diameter=3,sigma_space=1,
                      luma='YCoCg luminance retained before 8-bit rounding and clipping',
                      seconds=round(time.perf_counter()-start,4),dimensions=list(image.size),signature=signature)

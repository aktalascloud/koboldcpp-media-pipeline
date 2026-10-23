"""Preserve source low-frequency exposure and color while retaining SR detail."""
import time
from RuntimePaths import dependencies
dependencies()
import cv2
import numpy as np
from PIL import Image
def preserve_tones(source,final,sigma=20):
    start=time.perf_counter();reference=source.convert('RGB').resize(final.size,Image.Resampling.LANCZOS)
    values=np.arange(256,dtype=np.float32)/255
    lut=np.where(values<=.04045,values/12.92,((values+.055)/1.055)**2.4)
    la=lut[np.asarray(reference)];lb=lut[np.asarray(final.convert('RGB'))]
    factor=min(1,512/max(final.size));small=(max(8,round(final.width*factor)),max(8,round(final.height*factor)))
    aa=cv2.resize(la,small,interpolation=cv2.INTER_AREA);bb=cv2.resize(lb,small,interpolation=cv2.INTER_AREA)
    low=cv2.GaussianBlur(aa,(0,0),float(sigma)*factor)-cv2.GaussianBlur(bb,(0,0),float(sigma)*factor)
    delta=cv2.resize(low,final.size,interpolation=cv2.INTER_LINEAR)
    corrected=np.clip(lb+delta,0,1)
    scale=np.arange(65536,dtype=np.float32)/65535
    inverse=np.rint(np.clip(np.where(scale<=.0031308,scale*12.92,1.055*scale**(1/2.4)-.055),0,1)*255).astype(np.uint8)
    out=Image.fromarray(inverse[np.rint(corrected*65535).astype(np.uint16)])
    if 'A' in final.getbands():out=out.convert('RGBA');out.putalpha(final.getchannel('A'))
    return out,dict(seconds=round(time.perf_counter()-start,4),sigma=float(sigma),method='Source low-frequency linear-light RGB match;SR high-frequency detail retained')

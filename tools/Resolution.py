"""One native pixel budget while preserving common client aspect ratios."""
import math
def choose_resolution(width,height,budget=614400,max_edge=1280,alignment=32):
    width=int(width);height=int(height)
    if width<=0 or height<=0:raise ValueError('Positive image dimensions required')
    if isinstance(alignment,bool) or alignment not in (16,32,64):raise ValueError('Native alignment must be 16, 32 or 64')
    ratio=width/height;candidates=[]
    for w in range(256,int(max_edge)+1,alignment):
        for h in range(256,int(max_edge)+1,alignment):
            area=w*h
            if area<=budget:
                score=10*abs(math.log((w/h)/ratio))+(budget-area)/budget
                candidates.append((score,-area,w,h))
    if not candidates:raise ValueError('Native image budget is too small')
    _,_,w,h=min(candidates);return w,h

"""Arbitrary image geometry: fixed reflected 2D tiles, exact crop coverage."""
import numpy as np


def axis_jobs(length,tile,context):
    assert length>0 and tile>2*context and context>=0
    if length<=tile:
        before=(tile-length)//2
        spans=[(0,length,-before,before,'single-fit')]
    else:
        inner=tile-2*context
        spans=[(start,min(length,start+inner),start-context,context,'grid') for start in range(0,length,inner)]
    jobs=[]
    for start,end,logical_start,crop_before,mode in spans:
        logical=np.arange(logical_start,logical_start+tile,dtype=np.int64)
        if length==1:indices=np.zeros(tile,dtype=np.int64)
        else:
            period=2*(length-1);indices=logical%period;indices=np.where(indices>=length,period-indices,indices)
        jobs.append({'start':start,'end':end,'length':end-start,'logical_start':logical_start,'logical_end':logical_start+tile,
                     'crop_before':crop_before,'crop_end':crop_before+end-start,'mode':mode,'indices':indices,
                     'reflected_samples':int(((logical<0)|(logical>=length)).sum())})
    return jobs


def grid_jobs(width,height,tile_width,tile_height,context=32):
    xs=axis_jobs(width,tile_width,context);ys=axis_jobs(height,tile_height,context)
    rows=[]
    for yi,y in enumerate(ys):
        for xi,x in enumerate(xs):rows.append({'row':yi,'column':xi,'x':x,'y':y})
    return rows,xs,ys


def put_core(canvas,tile4x,job):
    assert tile4x.dtype==canvas.dtype==np.uint8
    x,y=job['x'],job['y']
    core=tile4x[y['crop_before']*4:y['crop_end']*4,x['crop_before']*4:x['crop_end']*4]
    dest=canvas[y['start']*4:y['end']*4,x['start']*4:x['end']*4]
    assert core.shape==dest.shape
    dest[:]=core

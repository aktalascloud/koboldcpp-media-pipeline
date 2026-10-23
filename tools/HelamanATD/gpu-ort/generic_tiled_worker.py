"""Experimental FP32 arbitrary-size2D ATD; Root owns face/tone stages."""
from pathlib import Path
from collections import Counter
import argparse,hashlib,json,os,sys,threading,time,traceback
R=Path(__file__).resolve().parent;H=R.parent;sys.path.insert(0,str(H));sys.path.insert(0,str(R))
from isolated_runtime import setup,ROOT


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def finalize_image(canvas,width,height,output_scale,Image):
    """Preserve native4x pixels, or perform the exact legacy Lanczos2x."""
    if output_scale not in (2,4):raise ValueError('Output scale must be2 or4')
    final=Image.fromarray(canvas)
    if output_scale==4:return final
    return final.resize((width*2,height*2),Image.Resampling.LANCZOS)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('input','output','proof','model'):p.add_argument('--'+name,required=True,type=Path)
    p.add_argument('--output-scale',type=int,choices=(2,4),default=2)
    p.add_argument('--context',type=int,choices=(32,64),default=32);p.add_argument('--max-seconds',type=int,default=360)
    args=p.parse_args();assert 30<=args.max_seconds<=1800
    setup(2,shared_ort=True);sys.path.append(str(ROOT/'tools'))
    args.output.parent.mkdir(parents=True,exist_ok=True);args.proof.parent.mkdir(parents=True,exist_ok=True)
    start=time.perf_counter();done=threading.Event();lock=threading.Lock()
    result={'status':'started','stage':'imports','scope':'Experimental pureSR2D tiles, not equivalent to original whole-image ATD. Root owns pre/post-face/denoise/tones.',
            'pid':os.getpid(),'input':str(args.input),'output':str(args.output),'model':str(args.model),'experimental_tiling':True,'whole_image_equivalence':False,
            'tiling_caveat':'Global token categories/groups are recomputed independently per reflected tile; identical weights/sort do not guarantee whole-image quality or seam-free output.',
            'native_scale':4,'output_scale':args.output_scale,'postresize':'per-tile4× float→rint/clip uint8, crop context, assemble whole4×uint8, one shared PIL Lanczos2×',
            'sort_policy':'OriginalTorchCPU stable=False','precision':'FP32','automatic_EP_fallback':False,'context':args.context,'budget_seconds':args.max_seconds,'tiles':[]}
    result['resize_applied']=args.output_scale==2
    if args.output_scale==4:result['postresize']='per-tile4× float→rint/clip uint8, crop context, assemble whole4×uint8, no resize'
    def save():
        with lock:args.proof.write_text(json.dumps(dict(result),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    def watchdog():
        if not done.wait(args.max_seconds):
            result.update(status='timeout',stage='own_budget_reached',seconds=time.perf_counter()-start,error='Own isolated stripe worker budget reached; no other process terminated and no automatic retry')
            save();os._exit(124)
    save();threading.Thread(target=watchdog,daemon=True).start()
    try:
        import numpy as np
        import torch
        import onnxruntime as ort
        from PIL import Image
        import atd_sort_op
        from tile_geometry_2d import grid_jobs,put_core
        from GpuAdapter import select_dml_adapter
        assert torch.version.cuda is None
        torch.set_num_threads(2);torch.set_num_interop_threads(1)
        result.update(torch_version=torch.__version__,ort_version=ort.__version__,model_sha256=sha(args.model),input_sha256=sha(args.input))
        data=args.model.with_name(args.model.name+'.data')
        if data.is_file():result['external_data']={'path':str(data),'bytes':data.stat().st_size,'sha256':sha(data)}
        with Image.open(args.input) as source:image=source.convert('RGB');image.load()
        width,height=image.size;pixels=np.asarray(image);result.update(input_dimensions=[width,height],input_rgb_sha256=hashlib.sha256(image.tobytes()).hexdigest())
        adapter=select_dml_adapter();result['adapter']=adapter
        options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1
        options.enable_mem_pattern=False;options.execution_mode=ort.ExecutionMode.ORT_SEQUENTIAL;options.graph_optimization_level=ort.GraphOptimizationLevel.ORT_ENABLE_BASIC
        options.enable_profiling=True;options.profile_file_prefix=str(args.proof.with_suffix(''))+'-profile';options.log_severity_level=2
        result['custom_library']=atd_sort_op.register_runtime(options)
        result['stage']='session_load';save();tick=time.perf_counter()
        session=ort.InferenceSession(str(args.model),sess_options=options,providers=[('DmlExecutionProvider',{'device_id':adapter['index']}),'CPUExecutionProvider'],enable_fallback=0)
        result.update(session_load_seconds=time.perf_counter()-tick,providers=session.get_providers());assert result['providers'][0]=='DmlExecutionProvider'
        input=session.get_inputs()[0];assert input.type=='tensor(float)' and input.shape[0:2]==[1,3]
        tile_height,tile_width=input.shape[2:4]
        assert isinstance(tile_height,int) and isinstance(tile_width,int) and min(tile_height,tile_width)>2*args.context
        assert tile_height%16==tile_width%16==0
        jobs,xjobs,yjobs=grid_jobs(width,height,tile_width,tile_height,args.context)
        canvas=np.empty((height*4,width*4,3),dtype=np.uint8)
        result.update(tiling_kind='2D reflected context; one group along any fitting axis',
                      tile_dimensions=[tile_width,tile_height],inner_dimensions=[tile_width-2*args.context,tile_height-2*args.context],
                      tile_count=len(jobs),grid_columns=len(xjobs),grid_rows=len(yjobs),
                      input_pixel_overhead_ratio=len(jobs)*tile_height*tile_width/(height*width),
                      seam_x_native=[row['start'] for row in xjobs[1:]],seam_y_native=[row['start'] for row in yjobs[1:]],
                      seam_x_output2x=[row['start']*2 for row in xjobs[1:]],seam_y_output2x=[row['start']*2 for row in yjobs[1:]])
        result.update(seam_x_output=[row['start']*args.output_scale for row in xjobs[1:]],seam_y_output=[row['start']*args.output_scale for row in yjobs[1:]])
        if args.output_scale==4:
            result.pop('seam_x_output2x',None);result.pop('seam_y_output2x',None)
            result.update(seam_x_output4x=result['seam_x_output'],seam_y_output4x=result['seam_y_output'])
        for number,job in enumerate(jobs):
            result['stage']='tile_run_'+str(number);save()
            stripe=pixels[job['y']['indices'][:,None],job['x']['indices'][None,:],:];array=np.ascontiguousarray(stripe.transpose(2,0,1)[None],dtype=np.float32)/255
            before=atd_sort_op.COUNTS['calls'];tick=time.perf_counter();output=session.run(None,{input.name:array})[0];elapsed=time.perf_counter()-tick
            assert output.shape==(1,3,tile_height*4,tile_width*4) and np.isfinite(output).all()
            tile=np.rint(np.clip(output[0].transpose(1,2,0),0,1)*255).astype(np.uint8);put_core(canvas,tile,job)
            calls=atd_sort_op.COUNTS['calls']-before;assert calls==36
            row={'row':job['row'],'column':job['column'],
                 'x':{key:value for key,value in job['x'].items() if key!='indices'},
                 'y':{key:value for key,value in job['y'].items() if key!='indices'}}
            row.update(index=number,seconds=elapsed,sort_callbacks=calls,input_rgb_sha256=hashlib.sha256(stripe.tobytes()).hexdigest(),
                       reflected_x_indices_sha256=hashlib.sha256(job['x']['indices'].tobytes()).hexdigest(),
                       reflected_y_indices_sha256=hashlib.sha256(job['y']['indices'].tobytes()).hexdigest())
            result['tiles'].append(row);result['seconds']=time.perf_counter()-start;save()
            print(json.dumps({'stage':'tile_complete','index':number,'count':len(jobs),'seconds':elapsed,'sort_callbacks':calls}),flush=True)
        result['stage']='whole_Lanczos2x' if args.output_scale==2 else 'whole_native4x_no_resize';save();tick=time.perf_counter()
        final=finalize_image(canvas,width,height,args.output_scale,Image);final.save(args.output)
        result.update(assembly_resize_save_seconds=time.perf_counter()-tick,output_dimensions=list(final.size),output_rgb_sha256=hashlib.sha256(final.tobytes()).hexdigest(),output_sha256=sha(args.output))
        profile=session.end_profiling();events=json.loads(Path(profile).read_text(encoding='utf-8'));histogram={}
        for event in events:
            attr=event.get('args',{});provider=attr.get('provider')
            if event.get('cat')!='Node' or not provider:continue
            bucket=histogram.setdefault(provider,{}).setdefault(attr.get('op_name','unknown'),{'calls':0,'summed_ORT_event_us':0.0})
            bucket['calls']+=1;bucket['summed_ORT_event_us']+=float(event.get('dur',0))
        providers=dict(Counter(event.get('args',{}).get('provider') for event in events if event.get('cat')=='Node' and event.get('args',{}).get('provider')))
        assert providers.get('DmlExecutionProvider',0)>0 and atd_sort_op.COUNTS['calls']==36*len(jobs)
        result.update(status='completed',stage='done',seconds=time.perf_counter()-start,inference_seconds=sum(row['seconds'] for row in result['tiles']),
                      sort_callbacks=atd_sort_op.COUNTS['calls'],provider_kernel_counts=providers,provider_op_histogram=histogram,profile=profile,
                      ORT_duration_scope='Summed ORT eventdur is diagnostic; copies synchronize GPU. Not pure hardware GPU time.')
    except Exception as error:
        text=repr(error);result.update(status='failed',error=text,traceback=traceback.format_exc(),seconds=time.perf_counter()-start,
                                       possible_oom=any(term in text.lower() for term in ('out of memory','e_outofmemory','8007000e','not enough memory')))
        traceback.print_exc()
    done.set();save();print(json.dumps({key:result.get(key) for key in ('status','seconds','inference_seconds','tile_count','sort_callbacks','output_dimensions','error')}),flush=True)
    return int(result['status']!='completed')


if __name__=='__main__':raise SystemExit(main())

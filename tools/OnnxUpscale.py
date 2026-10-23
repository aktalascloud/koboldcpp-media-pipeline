"""FP32 native 2x super-resolution on AMD via ONNX Runtime DirectML."""
import argparse
import gc
import hashlib
import json
from pathlib import Path
import sys
import time
from GpuAdapter import select_dml_adapter
from RuntimePaths import dependencies

HERE=Path(__file__).resolve().parent
dependencies()
import numpy as np
import onnxruntime as ort
from PIL import Image

class Upscaler:
    def __init__(self,model,provider='directml',tile=0,padding=32,profile_prefix=None):
        self.model=Path(model);self.provider=provider;self.tile=tile;self.padding=padding
        if tile and (tile<64 or tile%32):raise ValueError('Tile must be zero or a multiple of32, at least64')
        if padding<0 or padding%2:raise ValueError('Padding must be non-negative and even')
        options=ort.SessionOptions();options.enable_mem_pattern=False
        options.execution_mode=ort.ExecutionMode.ORT_SEQUENTIAL
        options.intra_op_num_threads=2;options.inter_op_num_threads=1
        options.graph_optimization_level=ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        if profile_prefix:options.enable_profiling=True;options.profile_file_prefix=str(profile_prefix)
        adapter=select_dml_adapter() if provider=='directml' else None
        providers=[('DmlExecutionProvider',{'device_id':adapter['index']}),'CPUExecutionProvider'] if adapter else ['CPUExecutionProvider']
        started=time.perf_counter();self.session=ort.InferenceSession(str(self.model),sess_options=options,providers=providers)
        self.load_seconds=round(time.perf_counter()-started,4)
        if provider=='directml' and self.session.get_providers()[0]!='DmlExecutionProvider':raise RuntimeError('DirectML provider not active')
        inp=self.session.get_inputs()[0];self.input_name=inp.name
        if inp.type!='tensor(float)':raise ValueError('This runtime deliberately uses FP32 models')
        self.metadata=dict(model=str(self.model),model_sha256=hashlib.sha256(self.model.read_bytes()).hexdigest(),ort_version=ort.__version__,providers=self.session.get_providers(),input_name=inp.name,input_shape=inp.shape,output_shapes=[o.shape for o in self.session.get_outputs()],load_seconds=self.load_seconds,tile=tile,padding=padding)
        self.metadata['adapter']=adapter
    def run_tensor(self,arr):
        # Input and output follow the released models' RGB/NCHW [0,1] convention.
        tensor=np.ascontiguousarray(arr.transpose(2,0,1)[None],dtype=np.float32)/255
        out=self.session.run(None,{self.input_name:tensor})[0]
        if out.shape!=(1,3,arr.shape[0]*2,arr.shape[1]*2):raise RuntimeError('Model did not produce native2x RGB output')
        if not np.isfinite(out).all():raise RuntimeError('Non-finite upscaler output')
        return np.rint(np.clip(out[0].transpose(1,2,0),0,1)*255).astype(np.uint8)
    def upscale(self,image):
        start=time.perf_counter();rgb=image.convert('RGB');arr=np.asarray(rgb)
        height,width=arr.shape[:2]
        # RRDB pixel-unshuffle needs even dimensions. Padding is removed afterwards.
        arr=np.pad(arr,((0,height%2),(0,width%2),(0,0)),mode='reflect')
        h,w=arr.shape[:2];tiles=0
        if not self.tile:
            result=self.run_tensor(arr);tiles=1
        else:
            result=np.empty((h*2,w*2,3),dtype=np.uint8)
            for top in range(0,h,self.tile):
                for left in range(0,w,self.tile):
                    right=min(w,left+self.tile);bottom=min(h,top+self.tile)
                    a=max(0,left-self.padding);b=max(0,top-self.padding);c=min(w,right+self.padding);d=min(h,bottom+self.padding)
                    piece=self.run_tensor(arr[b:d,a:c])
                    result[top*2:bottom*2,left*2:right*2]=piece[(top-b)*2:(bottom-b)*2,(left-a)*2:(right-a)*2]
                    tiles+=1
        final=Image.fromarray(result[:height*2,:width*2])
        if 'A' in image.getbands():
            final=final.convert('RGBA');final.putalpha(image.getchannel('A').resize(final.size,Image.Resampling.LANCZOS))
        return final,dict(inference_seconds=round(time.perf_counter()-start,4),input_dimensions=[width,height],output_dimensions=list(final.size),native_scale=2,tiles=tiles,provider=self.provider)
    def end_profile(self):
        return self.session.end_profiling() if self.session.get_session_options().enable_profiling else None
    def close(self):
        self.session=None;gc.collect()
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('image',type=Path);p.add_argument('--model',required=True,type=Path);p.add_argument('--out',required=True,type=Path);p.add_argument('--provider',choices=('directml','cpu'),default='directml');p.add_argument('--tile',type=int,default=0);a=p.parse_args()
    assert not a.out.exists(),'Output already exists'
    engine=Upscaler(a.model,a.provider,a.tile);image=Image.open(a.image)
    result,info=engine.upscale(image);result.save(a.out);print(json.dumps({**engine.metadata,**info,'output':str(a.out)},ensure_ascii=False));engine.close()

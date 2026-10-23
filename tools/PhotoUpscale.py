"""FP32 photo SR with native2x or4x models, always returning exact2x."""
import gc
import hashlib
from pathlib import Path
import sys
import time
from RuntimePaths import TOOLS,dependencies
dependencies()
from GpuAdapter import select_dml_adapter
import numpy as np
from PIL import Image
import onnxruntime as ort

class PhotoUpscaler:
    def __init__(self,model,scale=4,provider='directml',tile=256,padding=32,threads=10):
        self.model=Path(model);self.scale=int(scale);self.provider=provider;self.tile=int(tile);self.padding=int(padding);self.session=None;self.compiled=None
        assert self.scale in (2,4) and self.tile>=0
        start=time.perf_counter()
        if provider.startswith('openvino'):
            import openvino as ov
            self.core=ov.Core();self.devices=self.core.available_devices
            ov_model=self.core.read_model(str(self.model))
            device='GPU' if provider=='openvino_gpu' else 'CPU'
            config={'PERFORMANCE_HINT':'LATENCY','NUM_STREAMS':1,'INFERENCE_PRECISION_HINT':'f32'}
            if device=='CPU':config['INFERENCE_NUM_THREADS']=int(threads)
            else:config.pop('NUM_STREAMS')
            self.compiled=self.core.compile_model(ov_model,device,config)
            self.ov_device=self.core.get_property(device,'FULL_DEVICE_NAME')
            self.input_name=self.compiled.input(0).any_name
        else:
            options=ort.SessionOptions();options.enable_mem_pattern=False;options.execution_mode=ort.ExecutionMode.ORT_SEQUENTIAL;options.intra_op_num_threads=int(threads) if provider=='cpu' else 2;options.inter_op_num_threads=1
            self.adapter=select_dml_adapter() if provider=='directml' else None
            providers=[('DmlExecutionProvider',{'device_id':self.adapter['index']}),'CPUExecutionProvider'] if self.adapter else ['CPUExecutionProvider']
            self.session=ort.InferenceSession(str(self.model),sess_options=options,providers=providers)
            self.input_name=self.session.get_inputs()[0].name
            if provider=='directml':assert self.session.get_providers()[0]=='DmlExecutionProvider'
        self.load_seconds=round(time.perf_counter()-start,4)
        self.metadata=dict(model=str(self.model),model_sha256=hashlib.sha256(self.model.read_bytes()).hexdigest(),native_scale=self.scale,provider=provider,tile=self.tile,padding=self.padding,load_seconds=self.load_seconds)
        self.metadata['adapter']=getattr(self,'adapter',None)
        self.metadata['openvino_device']=getattr(self,'ov_device',None)
    def run_tensor(self,arr):
        tensor=np.ascontiguousarray(arr.transpose(2,0,1)[None],dtype=np.float32)/255
        if self.compiled is not None:out=self.compiled({self.input_name:tensor})[0]
        else:out=self.session.run(None,{self.input_name:tensor})[0]
        assert out.shape==(1,3,arr.shape[0]*self.scale,arr.shape[1]*self.scale),out.shape
        assert np.isfinite(out).all()
        return np.rint(np.clip(out[0].transpose(1,2,0),0,1)*255).astype(np.uint8)
    def upscale(self,image):
        start=time.perf_counter();rgb=image.convert('RGB');arr=np.asarray(rgb);height,width=arr.shape[:2];s=self.scale
        arr=np.pad(arr,((0,height%2),(0,width%2),(0,0)),mode='reflect');h,w=arr.shape[:2];tiles=0
        if not self.tile:result=self.run_tensor(arr);tiles=1
        else:
            result=np.empty((h*s,w*s,3),dtype=np.uint8)
            for top in range(0,h,self.tile):
                for left in range(0,w,self.tile):
                    right=min(w,left+self.tile);bottom=min(h,top+self.tile);a=max(0,left-self.padding);b=max(0,top-self.padding);c=min(w,right+self.padding);d=min(h,bottom+self.padding)
                    piece=self.run_tensor(arr[b:d,a:c]);result[top*s:bottom*s,left*s:right*s]=piece[(top-b)*s:(bottom-b)*s,(left-a)*s:(right-a)*s];tiles+=1
        final=Image.fromarray(result[:height*s,:width*s]);native_size=final.size
        if s!=2:final=final.resize((width*2,height*2),Image.Resampling.LANCZOS)
        if 'A' in image.getbands():final=final.convert('RGBA');final.putalpha(image.getchannel('A').resize(final.size,Image.Resampling.LANCZOS))
        return final,dict(inference_seconds=round(time.perf_counter()-start,4),input_dimensions=[width,height],native_dimensions=list(native_size),output_dimensions=list(final.size),tiles=tiles,provider=self.provider,native_scale=s,postresize='Lanczos4to2' if s==4 else 'none')
    def close(self):self.session=None;self.compiled=None;gc.collect()

class PhotoBlendUpscaler:
    """Two measured photo SR models, blended at identical final dimensions."""
    def __init__(self,model,detail_model,amount=.5,provider='directml',tile=384,padding=32,release_between=True):
        self.amount=float(amount)
        self.model=model;self.detail_model=detail_model;self.provider=provider;self.tile=tile;self.padding=padding;self.release_between=bool(release_between)
        if not 0<=self.amount<=1:raise ValueError('Photo blend must be between zero and one')
        self.primary=None;self.detail=None
        try:
            self.primary=PhotoUpscaler(model,4,provider,tile,padding)
            self.detail=PhotoUpscaler(detail_model,2,provider,0 if provider=='directml' else 256,padding)
        except Exception:
            self.close();raise
        self.metadata={**self.primary.metadata,'detail_model':self.detail.metadata,'blend_amount':self.amount}
    def upscale(self,image):
        start=time.perf_counter()
        if self.primary is None:self.primary=PhotoUpscaler(self.model,4,self.provider,self.tile,self.padding)
        if self.detail is None:self.detail=PhotoUpscaler(self.detail_model,2,self.provider,0 if self.provider=='directml' else 256,self.padding)
        primary,a=self.primary.upscale(image)
        if self.release_between:self.primary.close();self.primary=None
        detail,b=self.detail.upscale(image)
        if self.release_between:self.detail.close();self.detail=None
        if primary.size!=detail.size:raise RuntimeError('Photo SR models returned different dimensions')
        final=Image.blend(primary,detail,self.amount)
        return final,dict(provider=self.provider,native_scale=2,output_dimensions=list(final.size),
            inference_seconds=round(time.perf_counter()-start,4),primary=a,detail=b,blend_amount=self.amount,
            model_sha256=self.metadata['model_sha256'],detail_model_sha256=self.metadata['detail_model']['model_sha256'],release_between_models=self.release_between,
            method='Nomos photo SR and native2x RealESRGAN at identical output size')
    def close(self):
        for engine in (self.primary,self.detail):
            if engine:engine.close()
        self.primary=None;self.detail=None

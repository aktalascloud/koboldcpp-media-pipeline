"""Stream Artius Comfy INT8/packed W4A8 into standard GGUF Q8_0 for Kobold.

Original checkpoints are read-only. ConvRot is inverted with the regular H4
Kronecker transform. No model training or activation approximation is involved.
"""
from pathlib import Path
import argparse,collections,gc,hashlib,json,math,os,struct,sys,tempfile,time,types
os.environ.setdefault('OPENBLAS_NUM_THREADS','2')
import numpy as np
ROOT=Path(__file__).resolve().parent.parent;BASE=ROOT/'MODELS';OUT=BASE/'converted'
package=types.ModuleType('gguf');package.__path__=[str(ROOT/'tools/vendor/gguf')];sys.modules['gguf']=package
from gguf.gguf_writer import GGUFWriter
from gguf.constants import GGMLQuantizationType as QT
from gguf.quants import quantize,dequantize

def unrotate(x,size=256):
    assert x.shape[-1]%size==0
    y=np.array(x,dtype=np.float32,copy=True).reshape(-1,size)
    stride=1
    while stride<size:
        view=y.reshape(-1,size//(stride*4),4,stride)
        a,b,c,d=[view[:,:,j,:].copy() for j in range(4)]
        total=a+b+c+d
        view[:,:,0,:]=total-2*d;view[:,:,1,:]=total-2*c
        view[:,:,2,:]=total-2*b;view[:,:,3,:]=total-2*a
        stride*=4
    return (y/np.sqrt(np.float32(size))).reshape(x.shape)
def fp8_table():
    a=np.arange(256,dtype=np.uint16);e=(a>>3)&15;m=a&7
    value=np.where(e==0,(m/8)*2**-6,(1+m/8)*np.exp2(e.astype(np.int16)-7))
    value=np.where((e==15)&(m==7),np.nan,value);return (value*np.where(a&128,-1,1)).astype(np.float32)
FP8=fp8_table()
class SafeFile:
    def __init__(self,p):
        self.path=p
        with p.open('rb') as f:n=struct.unpack('<Q',f.read(8))[0];self.header=json.loads(f.read(n));self.offset=8+n
        self.data=np.memmap(p,mode='r',dtype=np.uint8)
    def array(self,name,rows=None):
        t=self.header[name];a,b=t['data_offsets'];dtype=t['dtype'];shape=t['shape']
        dt={'BF16':'<u2','F32':'<f4','F16':'<f2','I8':'i1','U8':'u1','F8_E4M3':'u1','I64':'<i8'}[dtype]
        arr=self.data[self.offset+a:self.offset+b].view(dt).reshape(shape)
        if rows is not None:arr=arr[rows]
        if dtype=='BF16':return (arr.astype(np.uint32)<<16).view(np.float32)
        if dtype=='F8_E4M3':return FP8[arr]
        return arr
    def config(self,base,meta):
        key=base+'.comfy_quant'
        if key in self.header:return json.loads(bytes(self.array(key)).decode('utf-8'))
        return meta.get('layers',{}).get(base,{})
def selftest():
    h=np.array([[1,1,1,-1],[1,1,-1,1],[1,-1,1,1],[-1,1,1,1]],np.float32)
    matrix=h
    while len(matrix)<256:matrix=np.kron(matrix,h)
    matrix/=16
    x=np.random.default_rng(123).integers(-127,128,size=(16,256)).astype(np.float32)
    assert np.max(np.abs(unrotate(x)-x@matrix))<1e-4
    assert np.max(np.abs(unrotate(unrotate(x))-x))<1e-4
    packed=np.array([[0x21,0xf0]],np.uint8);codes=np.empty((1,4),np.uint8);codes[:,0::2]=packed&15;codes[:,1::2]=packed>>4
    assert codes.tolist()==[[1,2,0,15]]
    print('Regular ConvRot transform and nibble packing verified against independent matrix reference.',flush=True)
def convert(path,role,output_name=None,model_name='Artius MOSS local compatible Q8_0',description='Decoded from verified original Comfy checkpoint; ConvRot inverted; standard Q8_0 matrices.'):
    dest=OUT/(output_name or role+'-q8_0.gguf');assert not dest.exists(),'Existing derived model preserved.'
    temporary=dest.with_suffix('.writing');assert not temporary.exists(),'Inspect previous partial conversion.'
    f=SafeFile(path);meta=json.loads(f.header.get('__metadata__',{}).get('_quantization_metadata','{}'))
    tempdir=OUT/'.tmp';tempdir.mkdir(exist_ok=True);tempfile.tempdir=str(tempdir)
    writer=GGUFWriter(temporary,arch='moss_image' if role=='image' else 'qwen35',use_temp_file=True)
    writer.add_name(model_name);writer.add_description(description)
    count=0;start=time.monotonic();errors=[];formats=collections.Counter()
    for name,t in f.header.items():
        if name=='__metadata__' or any(name.endswith(s) for s in ['.comfy_quant','.weight_scale','.scale_weight','.weight_s_rel','.weight_s_channel','.weight_codebook','.weight_correction']):continue
        shape=t['shape'];cfg=f.config(name[:-7],meta) if name.endswith('.weight') else {}
        fmt=cfg.get('format','');formats[fmt or t['dtype']]+=1
        if role=='image':tensor_name=name if name.startswith('model.diffusion_model.') else 'model.diffusion_model.'+name
        else:tensor_name=name.replace('model.language_model.','model.',1)
        if fmt=='asym_w4a8_int8':
            rows,half=shape;cols=half*2;shape=[rows,cols]
        quantized=len(shape)==2 and shape[-1]%32==0 and name.endswith('.weight')
        if quantized:
            rows,cols=shape;q=np.memmap(tempdir/'tensor.bin',mode='w+',dtype=np.uint8,shape=(rows,cols//32*34))
            for a in range(0,rows,256):
                b=min(rows,a+256);sl=slice(a,b);base=name[:-7]
                if fmt=='asym_w4a8_int8':
                    raw=f.array(name,sl).view(np.uint8);codes=np.empty((b-a,cols),np.uint8)
                    codes[:,0::2]=raw&15;codes[:,1::2]=raw>>4
                    codebook=f.array(base+'.weight_codebook').astype(np.float32)
                    rel=f.array(base+'.weight_s_rel',sl)
                    levels=codebook[codes].reshape(b-a,-1,int(cfg['group_size']))
                    grid=np.clip(np.rint(levels*rel[:,:,None]),-127,127).reshape(b-a,cols)
                    x=unrotate(grid,int(cfg.get('convrot_groupsize',256))) if cfg.get('convrot') else grid
                    x*=f.array(base+'.weight_s_channel',sl).reshape(-1,1)
                elif fmt=='int8_tensorwise' or t['dtype']=='I8':
                    assert fmt=='int8_tensorwise',(name,fmt)
                    x=f.array(name,sl).astype(np.float32)
                    if cfg.get('convrot'):x=unrotate(x,int(cfg.get('convrot_groupsize',256)))
                    scale=f.array(base+'.weight_scale')
                    x*=scale.reshape(-1,1)[sl] if scale.size>1 else float(scale.reshape(-1)[0])
                elif t['dtype']=='F8_E4M3':
                    x=f.array(name,sl).astype(np.float32)
                    scale_key=base+'.weight_scale'
                    if scale_key in f.header:
                        scale=f.array(scale_key)
                        x*=scale.reshape(-1,1)[sl] if scale.size>1 else float(scale.reshape(-1)[0])
                    if cfg.get('convrot'):x=unrotate(x,int(cfg.get('convrot_groupsize',256)))
                else:x=f.array(name,sl).astype(np.float32)
                assert np.isfinite(x).all(),name
                encoded=quantize(x,QT.Q8_0);q[a:b]=encoded
                if a==0:
                    decoded=dequantize(encoded,QT.Q8_0);error=float(np.linalg.norm(decoded-x)/(np.linalg.norm(x)+1e-20));errors.append(error)
                    assert error<.03,(name,error)
            writer.add_tensor(tensor_name,q,raw_dtype=QT.Q8_0);q._mmap.close();del q
            (tempdir/'tensor.bin').unlink()
        else:
            arr=np.array(f.array(name),copy=True)
            if arr.dtype not in (np.float32,np.float16,np.int64,np.int32):arr=arr.astype(np.float32)
            if arr.dtype==np.int64:arr=arr.astype(np.int32)
            writer.add_tensor(tensor_name,arr);del arr
        count+=1
        if count%20==0:print(json.dumps(dict(role=role,tensors=count,seconds=round(time.monotonic()-start,1))),flush=True)
    writer.write_header_to_file();writer.write_kv_data_to_file();writer.write_tensors_to_file(progress=False);writer.close()
    temporary.replace(dest)
    report=dict(source=path.name,output=dest.name,bytes=dest.stat().st_size,tensors=count,formats=dict(formats),max_sample_q8_relative_error=max(errors,default=0),seconds=time.monotonic()-start,
        caveat='Q8_0 is additional requantization; preserves the source merge, but is not bit-identical to original Comfy INT8/BF16 inference.')
    dest.with_suffix('.conversion.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source-dir',type=Path,required=True);p.add_argument('--source-file',type=Path);p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--role',choices=['image','text','both'],default='both');p.add_argument('--output-name');p.add_argument('--model-name',default='Artius MOSS local compatible Q8_0');p.add_argument('--description',default='Decoded from verified original Comfy checkpoint; ConvRot inverted; standard Q8_0 matrices.');a=p.parse_args();BASE=a.source_dir.resolve();OUT=a.output_dir.resolve();OUT.mkdir(parents=True,exist_ok=True);selftest()
    if a.source_file:
        if a.role=='both':raise ValueError('One source file requires one role.')
        convert(a.source_file.resolve(),a.role,a.output_name,a.model_name,a.description)
    else:
        if a.role in ['image','both']:convert(BASE/'img-artiusMoss_v10_3309287.safetensors','image')
        if a.role in ['text','both']:convert(BASE/'txt-artiusMoss_v10_3313824.safetensors','text')

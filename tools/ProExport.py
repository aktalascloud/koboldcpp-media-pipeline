"""Export stateful LightVAE without unrolling the complete clip into VRAM.

Pinned upstream Python is used only in this isolated conversion process.
Numerical comparison checks the first frame and four subsequent latent steps.
"""
from pathlib import Path
import argparse,sys,json,hashlib,time,gc
ROOT=Path(__file__).resolve().parent.parent;BASE=ROOT/'runtime/cache/pro-setup'
sys.path[:0]=[str(BASE/'torch'),str(BASE/'LightVAE')]
import torch,numpy as np
from lightvae.wan22_lightvae_decoder import Decoder
from lightvae.base_vae import wan22_vae_layers as native
class Stream(torch.nn.Module):
    def __init__(self,core,initial,slots):
        super().__init__();self.core=core;self.initial=initial;self.slots=list(slots)
    def forward(self,z,*caches):
        history=[None]*self.core.slots
        if not self.initial:
            for i,value in zip(self.slots,caches):history[i]=value
        component=self.core.component;decoder=component.decoder;slot=[0]
        x=self.core._apply_layer(decoder.conv1,component.conv2(z),history,slot)
        for layer in decoder.middle:x=self.core._apply_layer(layer,x,history,slot)
        for stage in decoder.upsamples:
            shortcut=x
            for layer in stage.upsamples:x=self.core._apply_layer(layer,x,history,slot)
            if stage.avg_shortcut is not None:x=x+stage.avg_shortcut(shortcut,first_chunk=self.initial)
        for layer in decoder.head:x=self.core._apply_layer(layer,x,history,slot)
        if self.initial and not self.slots:self.slots=[i for i,v in enumerate(history) if isinstance(v,torch.Tensor)]
        return (native.unpatchify(x,2),*[history[i] for i in self.slots])
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--variant',choices=['lite','pro'],default='pro');args=parser.parse_args()
    torch.set_num_threads(4);torch.set_num_interop_threads(1);torch.manual_seed(2026)
    folder=BASE/('lightvae-'+args.variant);folder.mkdir(parents=True,exist_ok=True);config=json.loads((BASE/f'LightVAE/lightvae/config/lightvae-{args.variant}-wan22.json').read_text())
    weight=ROOT/f'MODELS/vae/candidates/lightvae-{args.variant}-wan22-decoder.safetensors'
    core=Decoder(config,checkpoint=weight).float().eval()
    for layer in core.modules():
        if isinstance(layer,torch.nn.Upsample) and layer.mode=='nearest-exact':
            scale=layer.scale_factor;factors=scale if isinstance(scale,tuple) else (scale,scale)
            assert all(float(v).is_integer() and v>=1 for v in factors);layer.mode='nearest'
    sample=torch.randn(1,48,5,4,4)*.5
    with torch.inference_mode():reference=core(sample)
    original=core._apply_layer
    def apply(layer,x,history,slot):
        index=slot[0];result=original(layer,x,history,slot)
        if isinstance(layer,native.Resample) and layer.mode=='upsample3d' and isinstance(history[index],str):
            rank=layer.time_conv.rank
            assert rank>0
            history[index]=x.new_zeros(x.shape[0],2,2*rank,x.shape[-2],x.shape[-1])
        return result
    core._apply_layer=apply
    start=Stream(core,True,[])
    with torch.inference_mode():
        first=start(sample[:,:,:1]);step=Stream(core,False,start.slots);outputs=[first[0]];cache=first[1:]
        for i in range(1,5):
            values=step(sample[:,:,i:i+1],*cache);outputs.append(values[0]);cache=values[1:]
        result=torch.cat(outputs,dim=2);difference=(result-reference).abs()
        assert difference.max()<.001 and difference.mean()<.00001,(float(difference.max()),float(difference.mean()))
    state_specs=[]
    for i,v in enumerate(first[1:]):
        assert v.shape[3]%4==0 and v.shape[4]%4==0
        state_specs.append(dict(index=start.slots[i],channels=v.shape[2],history=v.shape[1],height_factor=v.shape[3]//4,width_factor=v.shape[4]//4))
    np.save(folder/'stream-fixture-latent.npy',sample.numpy());np.save(folder/'stream-fixture-reference.npy',reference.numpy())
    files=[]
    for name,module,inputs,output_prefix in [('start',start,(sample[:,:,:1],),'cache'),('step',step,(sample[:,:,1:2],*first[1:]),'next')]:
        path=ROOT/f'MODELS/vae/candidates/lightvae-{args.variant}-{name}.onnx'
        names=['latent']+([] if name=='start' else [f'cache{i}' for i in range(len(state_specs))])
        outputs=['pixels']+[f'{output_prefix}{i}' for i in range(len(state_specs))]
        dynamic={'latent':{3:'latent_h',4:'latent_w'},'pixels':{3:'pixel_h',4:'pixel_w'}}
        for i in range(len(state_specs)):
            dynamic[f'{output_prefix}{i}']={3:f'state{i}_h',4:f'state{i}_w'}
            if name=='step':dynamic[f'cache{i}']={3:f'state{i}_h',4:f'state{i}_w'}
        with torch.inference_mode():torch.onnx.export(module,inputs,str(path),opset_version=17,dynamo=False,input_names=names,output_names=outputs,dynamic_axes=dynamic,do_constant_folding=True)
        files.append(dict(role=name,path=str(path.relative_to(ROOT)).replace('\\','/'),bytes=path.stat().st_size,sha256=hashlib.file_digest(path.open('rb'),'sha256').hexdigest()))
        print('Exported '+name,flush=True)
    receipt=dict(ok=True,variant=args.variant,files=files,state_specs=state_specs,reference_max_abs=float(difference.max()),reference_mean_abs=float(difference.mean()),
        full_size_state_bytes=sum(1*s['history']*s['channels']*(52*s['height_factor'])*(30*s['width_factor'])*4 for s in state_specs),
        scope='Stateful decoder export;start returns1frame,each later latent returns4;GPU tests pending.')
    (folder/'stream-export.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt),flush=True)
if __name__=='__main__':main()

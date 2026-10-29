"""Deduplicate reviewed Pro start/step ONNX initializers into one weight file."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'runtime/cache/pro-setup/torch'))
import onnx,json,hashlib
ROOT=Path(__file__).resolve().parent.parent;META=ROOT/'runtime/cache/pro-setup/lightvae-pro/stream-export.json'
def main():
    source=json.loads(META.read_text());out=ROOT/'MODELS/vae/lightvae-pro-stream';out.mkdir(exist_ok=True)
    data=out/'weights.bin';seen={};files=[]
    with data.open('wb') as sink:
        for row in source['files']:
            p=ROOT/row['path']
            with p.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==row['sha256']
            model=onnx.load(str(p),load_external_data=False)
            for t in model.graph.initializer:
                raw=t.raw_data
                if len(raw)<1024:continue
                digest=hashlib.sha256(raw).digest()
                if digest not in seen:
                    offset=sink.tell();sink.write(raw);seen[digest]=(offset,len(raw))
                offset,size=seen[digest]
                onnx.external_data_helper.set_external_data(t,location='weights.bin',offset=offset,length=size)
                t.ClearField('raw_data');t.data_location=onnx.TensorProto.EXTERNAL
            target=out/(row['role']+'.onnx');onnx.save_model(model,str(target))
            files.append({'role':row['role'],'path':target.relative_to(ROOT).as_posix(),'bytes':target.stat().st_size,'sha256':hashlib.file_digest(target.open('rb'),'sha256').hexdigest()})
    files.append({'role':'weights','path':data.relative_to(ROOT).as_posix(),'bytes':data.stat().st_size,'sha256':hashlib.file_digest(data.open('rb'),'sha256').hexdigest()})
    for row in files:
        if row['role']!='weights':onnx.checker.check_model(str(ROOT/row['path']))
    result={'format':1,'checkpoint_sha256':'9985d3b90321f48109c3fed25b526f38d137a1a7a8f34e1afbe41ddfc27d2782','files':files,'state_specs':source['state_specs'],'reference_max_abs':source['reference_max_abs'],'spatial_scale':16,'latent_channels':48,'temporal_scale':4,'tile_pixels':320,'tile_threshold':576,'overlap_pixels':64,'source':'https://huggingface.co/lightx2v/LightVAE/tree/4925ea978147b9de492d7a5fd4f9c6d1854ca1cc','license_weights':'Apache-2.0','scope':'Shared-weight FP32 causal start/step graphs; actual GPU trial required before activation.'}
    (out/'manifest.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
if __name__=='__main__':main()

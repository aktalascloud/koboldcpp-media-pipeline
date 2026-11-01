"""Optional original-provider Wav2Lip download. Non-commercial/personal research only."""
from pathlib import Path
import hashlib,json,urllib.request
ROOT=Path(__file__).resolve().parent.parent
URL='https://github.com/facefusion/facefusion-assets/releases/download/models-3.0.0/wav2lip_gan_96.onnx'
SHA='8e804de2ae264fdfad607339846dabcc728d84191e2fc3433b156c40c83f906c'
def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--accept-noncommercial',action='store_true');a=p.parse_args()
    if not a.accept_noncommercial:raise SystemExit('Read https://github.com/Rudrabha/Wav2Lip#disclaimer and rerun with --accept-noncommercial. Weights are not MIT or licensed for commercial use.')
    folder=ROOT/'MODELS/detailers/lipsync';folder.mkdir(parents=True,exist_ok=True);target=folder/'wav2lip_gan_96.onnx'
    if not target.exists():
        part=target.with_suffix('.download');urllib.request.urlretrieve(URL,part)
        with part.open('rb') as f:actual=hashlib.file_digest(f,'sha256').hexdigest()
        if actual!=SHA:part.unlink();raise RuntimeError('Original model SHA mismatch')
        part.replace(target)
    with target.open('rb') as f:
        if hashlib.file_digest(f,'sha256').hexdigest()!=SHA:raise RuntimeError('Existing model differs; file preserved')
    manifest=folder/'manifest.json'
    if not manifest.exists():manifest.write_text(json.dumps({'file':target.name,'sha256':SHA,'source':URL,'original':'https://github.com/Rudrabha/Wav2Lip','license':'Non-commercial research/personal use only; original Wav2Lip/LRS2 restrictions; never mirror weights','validated':False},indent=2)+'\n',encoding='utf-8')
    print('Original-provider model ready. Real local lip-sync validation is still required.')
if __name__=='__main__':main()

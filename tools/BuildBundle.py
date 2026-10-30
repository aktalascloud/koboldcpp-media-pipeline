"""Build a local one-file media kit from the accepted installation; no model weights/cache.

Private runtime files are embedded for the owner's machine. Publishing this artifact
requires its separate third-party redistribution review; core/media code publication
does not implicitly upload this large local executable.
"""
from pathlib import Path
import hashlib,json,subprocess,zipfile,sys
ROOT=Path(__file__).resolve().parent.parent;BUILD=ROOT/'runtime/cache/bundle-build'
def digest(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    (BUILD/'results').mkdir(parents=True,exist_ok=True);(BUILD/'candidate').mkdir(parents=True,exist_ok=True)
    manifest=BUILD/'results/media-bundle-manifest.json';archive=BUILD/'candidate/media-payload.zip'
    forbidden={'__pycache__','cache','logs','tmp','backups','.git','tests','test'}
    files={}
    for folder in ['runtime/python','runtime/ffmpeg','runtime/rife']:
        for p in (ROOT/folder).rglob('*'):
            if p.is_file() and not forbidden.intersection(p.relative_to(ROOT).parts):files[p.relative_to(ROOT).as_posix()]=p
    for p in (ROOT/'profiles/api').rglob('*'):
        if p.is_file():files[p.relative_to(ROOT).as_posix()]=p
    for p in (ROOT/'tools').glob('*'):
        if p.suffix in ('.py','.ps1','.json','.cs'):files[p.relative_to(ROOT).as_posix()]=p
    for relative in ['Helper.kcpps','koboldcpp-nocuda.exe','runtime/native-environment.json','runtime/requirements.lock.txt','runtime/versions.json','profiles/moss-adapters.json','MODELS/manifest.json']:
        p=ROOT/relative
        if p.is_file():files[relative]=p
    # The one master config contains exact generated profiles; no separate
    # hand-maintained Native configs are required in a fresh extraction.
    h=json.loads((ROOT/'Helper.kcpps').read_text(encoding='utf-8'));gd=json.loads(h['gendefaults'])
    assert gd['kcpp_proxy']['backend_supervisor'].get('inline_profiles')
    license_root=ROOT/'licenses'
    if not license_root.is_dir():license_root=ROOT/'build/publishing/koboldcpp-media-pipeline/licenses'
    for p in license_root.rglob('*'):
        if p.is_file():files['licenses/'+p.relative_to(license_root).as_posix()]=p
    rows={}
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as z:
        for name,p in sorted(files.items()):
            if p.is_symlink() or not p.resolve().is_relative_to(ROOT):raise RuntimeError('Unsafe bundle input')
            if p.suffix.lower() in ('.gguf','.safetensors','.onnx') and not name.startswith('runtime/python/'):raise RuntimeError('Model weight in runtime bundle')
            rows[name]={'bytes':p.stat().st_size,'sha256':digest(p)};z.write(p,name)
    with zipfile.ZipFile(archive) as check:
        if check.testzip() is not None:raise RuntimeError('Corrupt media payload')
    proof={'format':1,'files':rows,'main_models_embedded':False,'generated_profiles_in_master':True,'local_owner_bundle':True,'redistribution_review_required':True}
    manifest.write_text(json.dumps(proof,separators=(',',':')),encoding='utf-8')
    csc=Path('C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe');output=ROOT/'KoboldCpp.exe'
    args=[str(csc),'/nologo','/target:winexe','/platform:x64','/optimize+', '/out:'+str(output),'/r:System.Windows.Forms.dll','/r:System.Web.Extensions.dll','/r:System.IO.Compression.dll','/r:System.IO.Compression.FileSystem.dll','/resource:'+str(manifest)+',media-manifest.json','/resource:'+str(archive)+',media-payload.zip',str(ROOT/'tools/MediaBundle.cs')]
    subprocess.run(args,cwd=ROOT,check=True)
    result={'ok':True,'file':'KoboldCpp.exe','bytes':output.stat().st_size,'sha256':digest(output),'payload_files':len(rows),'payload_bytes':archive.stat().st_size,'native_sha256':digest(ROOT/'koboldcpp-nocuda.exe'),'main_models_embedded':False,'private_local_runtime':True,'public_release_uploaded':False}
    (BUILD/'results/media-bundle.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))
if __name__=='__main__':main()

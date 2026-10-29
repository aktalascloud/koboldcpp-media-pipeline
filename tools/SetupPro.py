"""One-time CPU Pro conversion using original downloads; no second Python runtime."""
from pathlib import Path
import sys,json,hashlib,urllib.request,urllib.parse,subprocess,os,runpy,socket
ROOT=Path(__file__).resolve().parent.parent
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def fetch(row,target):
    address=urllib.parse.urlsplit(row['url'])
    if address.scheme!='https' or address.username or address.password:raise ValueError('Original setup downloads require HTTPS')
    if target.exists():
        if target.stat().st_size==row['bytes'] and sha(target)==row['sha256']:return
        raise RuntimeError('Existing setup asset differs; preserved:'+target.name)
    target.parent.mkdir(parents=True,exist_ok=True);partial=target.with_name(target.name+'.partial')
    request=urllib.request.Request(row['url'],headers={'User-Agent':'KoboldCpp-Media-Setup'})
    with urllib.request.urlopen(request,timeout=120) as response,partial.open('wb') as sink:
        if urllib.parse.urlsplit(response.geturl()).scheme!='https':raise ValueError('Insecure setup redirect refused')
        count=0
        while chunk:=response.read(1024*1024):
            count+=len(chunk)
            if count>row['bytes']:raise ValueError('Setup download exceeded its pinned size')
            sink.write(chunk)
    if partial.stat().st_size!=row['bytes'] or sha(partial)!=row['sha256']:raise RuntimeError('Original Pro setup download hash mismatch')
    partial.replace(target)
def ready(spec):
    manifest=ROOT/'MODELS/vae/lightvae-pro-stream/manifest.json'
    if not manifest.is_file() or sha(manifest)!=spec['expected_manifest_sha256']:return False
    from VideoPro import verify_assets
    verify_assets(ROOT,spec['expected_manifest_sha256']);return True
def prepare():
    spec=json.loads((ROOT/'tools/pro-setup-sources.json').read_text())
    if ready(spec):print('Pinned Pro graphs already ready; no model download/conversion.');return True
    for port in (5001,5003):
        with socket.socket() as probe:
            probe.settimeout(.3)
            if probe.connect_ex(('127.0.0.1',port))==0:raise RuntimeError('Stop the service before initial Pro setup; active installation preserved')
    output=ROOT/'MODELS/vae/lightvae-pro-stream'
    if output.exists() and any(output.iterdir()):raise RuntimeError('Partial/different Pro output preserved; review it before retrying setup')
    cache=ROOT/'runtime/cache/pro-setup';cache.mkdir(parents=True,exist_ok=True)
    for row in spec['source_files']:fetch(row,cache/'LightVAE'/row['path'])
    raw=ROOT/'MODELS/vae/candidates/lightvae-pro-wan22-decoder.safetensors';fetch(spec['checkpoint'],raw)
    pip=cache/spec['pip']['name'];fetch(spec['pip'],pip)
    env=os.environ.copy();env.update(TMP=str(ROOT/'runtime/tmp'),TEMP=str(ROOT/'runtime/tmp'),PYTHONDONTWRITEBYTECODE='1')
    command=[sys.executable,'-I','-B',str(Path(__file__).resolve()),'_pip',str(pip),'--isolated','install','--no-cache-dir','--no-compile','--target',str(cache/'torch'),'--index-url','https://download.pytorch.org/whl/cpu','--extra-index-url','https://pypi.org/simple',*spec['packages']]
    subprocess.run(command,cwd=ROOT,env=env,check=True)
    subprocess.run([sys.executable,'-I','-B',str(ROOT/'tools/ProExport.py'),'--variant','pro'],cwd=ROOT,env=env,check=True)
    subprocess.run([sys.executable,'-I','-B',str(ROOT/'tools/ProShare.py')],cwd=ROOT,env=env,check=True)
    if not ready(spec):raise RuntimeError('Converted Pro graphs differ from pinned reproducible build; not activated')
    print('Pro ready. PyTorch/source/checkpoint setup cache remains local and is never included in releases.')
    return True
if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='_pip':
        wheel=sys.argv[2];sys.path.insert(0,wheel);sys.argv=['pip',*sys.argv[3:]];runpy.run_module('pip',run_name='__main__')
    else:prepare()

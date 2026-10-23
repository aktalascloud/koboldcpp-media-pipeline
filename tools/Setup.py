"""Complete a single portable installation. No inference or registry changes."""
from pathlib import Path
import argparse, hashlib, json, os, urllib.request
ROOT=Path(__file__).resolve().parent.parent

def sha(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(8*1024*1024),b''):digest.update(block)
    return digest.hexdigest()

def download(row):
    path=(ROOT/row['path']).resolve()
    if not path.is_relative_to(ROOT):raise RuntimeError('Invalid model path')
    if path.is_file():
        if path.stat().st_size!=row['bytes'] or sha(path)!=row['sha256']:raise RuntimeError('Existing file differs; preserved: '+row['path'])
        return
    if not row.get('url'):raise RuntimeError('Extract the model release asset first: '+row['path'])
    if row['path'].endswith('gpen_bfr_512.onnx'):
        print('GPEN is Non-Commercial according to its converter. See licenses/GPEN-NOTICE.md.')
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.download')
    print('Downloading '+row['path'],flush=True)
    request=urllib.request.Request(row['url'],headers={'User-Agent':'KoboldCpp-Media-Setup'})
    try:
        with urllib.request.urlopen(request,timeout=180) as response,temporary.open('xb') as output:
            while block:=response.read(4*1024*1024):output.write(block)
        if temporary.stat().st_size!=row['bytes'] or sha(temporary)!=row['sha256']:raise RuntimeError('Download SHA/size mismatch; original target preserved')
        os.replace(temporary,path)
    except FileExistsError:
        raise RuntimeError('Previous incomplete download preserved. Inspect/remove: '+str(temporary)) from None

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--skip-model-downloads',action='store_true');args=parser.parse_args()
    catalog=json.loads((ROOT/'models.json').read_text())
    if not args.skip_model_downloads:
        for row in catalog['models']:download(row)
    exe=ROOT/'koboldcpp-nocuda.exe'
    if not exe.is_file():raise RuntimeError('The core Windows release is missing')
    helper_path=ROOT/'Helper.kcpps';helper=json.loads(helper_path.read_text(encoding='utf-8-sig'))
    defaults=json.loads(helper['gendefaults']);profiles=defaults['kcpp_proxy']['backend_supervisor']['profiles']
    exe_sha=sha(exe)
    for name,profile in profiles.items():
        profile['executable_sha256']=exe_sha
        profile['helper_sha256']=sha(ROOT/profile['helper'])
    helper['gendefaults']=json.dumps(defaults,ensure_ascii=False,separators=(',',':'))
    helper_path.write_text(json.dumps(helper,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    excluded={'logs','cache','tmp','__pycache__','.git','backups','outputs','proof','artifacts'}
    records=[]
    for path in sorted(ROOT.rglob('*')):
        rel=path.relative_to(ROOT)
        if not path.is_file() or excluded.intersection(rel.parts) or path.suffix.lower() in ('.zip','.log','.pid','.pyc','.download') or path.name=='portable-manifest.json':continue
        records.append({'path':rel.as_posix(),'bytes':path.stat().st_size,'sha256':sha(path)})
    manifest={'format':1,'production_root_is_relative':True,'file_count':len(records),'files':records}
    (ROOT/'portable-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    missing=[row['path'] for row in catalog['models'] if not (ROOT/row['path']).is_file()]
    print(json.dumps({'ready':not missing,'missing':missing,'native_exe_sha256':exe_sha,'registry_changed':False,'inference_started':False},indent=2))
    return 2 if missing else 0

if __name__=='__main__':raise SystemExit(main())

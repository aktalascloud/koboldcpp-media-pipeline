"""Install the hash-pinned Pillow security wheel with pip, without model downloads.

The caller must stop its owned idle service first. Fresh Setup runs before launch.
"""
from pathlib import Path
import base64,csv,hashlib,importlib.metadata,json,os,subprocess,sys,urllib.request,zipfile

ROOT=Path(__file__).resolve().parent.parent


def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def fetch(root,row):
    target=root/'runtime/cache/security-wheels'/row['filename']
    if not target.resolve().is_relative_to(root) or target.is_symlink():raise RuntimeError('Unsafe wheel cache path')
    if not target.exists():
        target.parent.mkdir(parents=True,exist_ok=True)
        temporary=target.with_suffix(target.suffix+'.download')
        with urllib.request.urlopen(row['url'],timeout=60) as response,temporary.open('wb') as output:
            while block:=response.read(1024*1024):output.write(block)
        if digest(temporary)!=row['sha256']:raise RuntimeError('Security wheel SHA256 mismatch')
        os.replace(temporary,target)
    if target.is_symlink() or digest(target)!=row['sha256']:raise RuntimeError('Security wheel differs; preserved')
    return target


def install(root=ROOT):
    root=Path(root).resolve();site=root/'runtime/python/Lib/site-packages'
    if not site.resolve().is_relative_to(root) or (site/'PIL').is_symlink() or (site/'PIL').is_junction():
        raise RuntimeError('Pillow package path escaped the portable installation')
    pin=json.loads((root/'tools/pillow-security.json').read_text(encoding='utf8'))
    distributions=[d for d in importlib.metadata.distributions(path=[str(site)]) if d.metadata['Name'].lower()=='pillow']
    if len(distributions)!=1:raise RuntimeError('Pillow distribution identity is ambiguous')
    current=distributions[0]
    if Path(current._path).is_symlink() or Path(current._path).is_junction():raise RuntimeError('Unsafe package metadata path')
    if current.version==pin['version']:
        return {'ok':True,'version':current.version,'changed':False}
    if current.version!='12.3.0':raise RuntimeError('Unexpected Pillow version preserved: '+current.version)
    # Preserve local source edits instead of letting pip uninstall them.
    record=Path(current._path)/'RECORD'
    owned=set()
    with record.open(encoding='utf8',newline='') as stream:
        for name,expected,_ in csv.reader(stream):
            if not expected:continue
            raw=site/name;path=raw.resolve()
            if not path.is_relative_to(site.resolve()) or raw.is_symlink():raise RuntimeError('Unsafe Pillow package record')
            owned.add(path)
            algorithm,value=expected.split('=',1)
            if algorithm!='sha256' or not path.is_file():raise RuntimeError('Pillow package record mismatch')
            actual=base64.urlsafe_b64encode(bytes.fromhex(digest(path))).decode().rstrip('=')
            if actual!=value and pin.get('accepted_baseline_sha256',{}).get(name)!=digest(path):
                raise RuntimeError('Modified Pillow file preserved: '+name)
    pip_wheel=fetch(root,pin['pip']);image_wheel=fetch(root,pin['wheel'])
    with zipfile.ZipFile(image_wheel) as wheel:
        for name in wheel.namelist():
            path=(site/name).resolve()
            if not path.is_relative_to(site.resolve()):raise RuntimeError('Unsafe wheel member')
            if path.is_file() and path not in owned and path.read_bytes()!=wheel.read(name):
                raise RuntimeError('Unowned package file collision preserved: '+name)
    code="import sys;sys.path.insert(0,sys.argv[1]);from pip._internal.cli.main import main;raise SystemExit(main(['install','--no-index','--no-deps','--disable-pip-version-check','--force-reinstall',sys.argv[2]]))"
    python=root/'runtime/python/python.exe'
    subprocess.run([str(python),'-I','-B','-c',code,str(pip_wheel),str(image_wheel)],check=True,cwd=root)
    subprocess.run([str(python),'-I','-B','-c',"import PIL;from PIL import Image;assert PIL.__version__=='13.0.0';Image.new('RGB',(2,2)).load()"],check=True,cwd=root)
    lock=root/'runtime/requirements.lock.txt'
    if lock.is_file():lock.write_text(lock.read_text(encoding='utf8').replace('pillow==12.3.0','pillow==13.0.0'),encoding='utf8',newline='\n')
    versions=root/'runtime/versions.json'
    if versions.is_file():
        data=json.loads(versions.read_text(encoding='utf8'));data.setdefault('packages',{})['pillow']=pin['version']
        versions.write_text(json.dumps(data,indent=2)+'\n',encoding='utf8',newline='\n')
    return {'ok':True,'version':pin['version'],'changed':True,'wheel_sha256':pin['wheel']['sha256']}


if __name__=='__main__':print(json.dumps(install()))

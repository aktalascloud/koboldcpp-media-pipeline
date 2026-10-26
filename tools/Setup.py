"""Install pinned MOSS/music assets. No inference or registry changes."""
from pathlib import Path
import argparse,hashlib,ipaddress,json,os,shutil,socket,subprocess,sys,urllib.error,urllib.parse,urllib.request
ROOT=Path(__file__).resolve().parent.parent
_HASHES={}
def sha(path):
    stat=path.stat();identity=(stat.st_size,stat.st_mtime_ns,stat.st_ino);cached=_HASHES.get(str(path))
    if cached and cached[0]==identity:return cached[1]
    with path.open('rb') as stream:value=hashlib.file_digest(stream,'sha256').hexdigest()
    _HASHES[str(path)]=(identity,value);return value
def inside(relative):
    path=(ROOT/relative).resolve()
    if not path.is_relative_to(ROOT) or path==ROOT:raise RuntimeError('Asset path escaped installation root.')
    return path
def verified(path,row):return path.is_file() and path.stat().st_size==row['bytes'] and sha(path)==row['sha256']
class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,request,fp,code,message,headers,url):
        result=super().redirect_request(request,fp,code,message,headers,url)
        if result and urllib.parse.urlsplit(request.full_url).netloc!=urllib.parse.urlsplit(url).netloc:result.remove_header('Authorization')
        return result
def download(row,target=None):
    path=target or inside(row['path'])
    if path.exists():
        if not verified(path,row):raise RuntimeError('Existing asset differs; preserved: '+row['path'])
        return path
    if not row.get('url'):raise RuntimeError('Missing verified release asset: '+row['path'])
    parsed=urllib.parse.urlsplit(row['url'])
    if parsed.scheme!='https' or parsed.username or parsed.password:raise RuntimeError('HTTPS asset URL required.')
    path.parent.mkdir(parents=True,exist_ok=True);partial=path.with_name(path.name+'.download');offset=partial.stat().st_size if partial.exists() else 0
    if offset>row['bytes']:raise RuntimeError('Incomplete asset is larger than expected; preserved for inspection.')
    if offset==row['bytes']:
        if not verified(partial,row):raise RuntimeError('Completed partial has the wrong fingerprint; preserved.')
        os.replace(partial,path);return path
    headers={'User-Agent':'KoboldCpp-Media-Setup','Accept-Encoding':'identity'}
    if offset:headers['Range']='bytes='+str(offset)+'-'
    token=os.environ.get('CIVITAI_API_KEY','') if parsed.hostname in ('civitai.com','civitai.red') else ''
    if token:headers['Authorization']='Bearer '+token
    print('Downloading '+row['path'],flush=True)
    try:
        with urllib.request.build_opener(SafeRedirect()).open(urllib.request.Request(row['url'],headers=headers),timeout=180) as response:
            append=bool(offset and response.status==206)
            if append and not str(response.headers.get('Content-Range','')).startswith('bytes '+str(offset)+'-'):raise RuntimeError('Unexpected resume range.')
            with partial.open('ab' if append else 'wb') as output:
                for block in iter(lambda:response.read(4*1024*1024),b''):output.write(block)
    except urllib.error.HTTPError as error:
        if error.code in (401,403) and row.get('requires_civitai_access'):
            raise RuntimeError('Exact W4 encoder requires Civitai access. Download file3313824 from the author page and use -MossSourceDirectory, or supply CIVITAI_API_KEY only in the process environment. No different encoder is substituted.') from None
        raise RuntimeError('Asset download failed with HTTP'+str(error.code)+': '+row['path']) from None
    if not verified(partial,row):raise RuntimeError('Download size/SHA256 mismatch; original target preserved: '+row['path'])
    if path.exists():raise RuntimeError('Asset appeared concurrently; both files preserved.')
    os.replace(partial,path);return path
def source_file(row,directory,temporary):
    destination=temporary/Path(row['path']).name
    if directory:
        candidates=[directory/name for name in dict.fromkeys([Path(row['path']).name,*row.get('aliases',[])])]
        candidates.extend(p for p in directory.glob('*.safetensors') if p.stat().st_size==row['bytes'])
        for path in dict.fromkeys(candidates):
            if verified(path,row):
                if not destination.exists():
                    try:os.link(path,destination)
                    except OSError:shutil.copyfile(path,destination)
                if not verified(destination,row):raise RuntimeError('Imported source differs; preserved for inspection.')
                return destination
    if row.get('required_user_file') and not row.get('url'):
        raise RuntimeError('Required original model not found in --moss-source-directory: '+Path(row['path']).name)
    return download(row,destination)
def prepare_moss(catalog,directory):
    pending=[]
    for row in catalog['models']:
        if not row.get('generated_role'):continue
        target=inside(row['path'])
        if target.exists():
            if not verified(target,row):raise RuntimeError('Existing derived model differs; preserved: '+row['path'])
        else:pending.append(row)
    if not pending:return
    # Fail gated encoder access before downloading/converting the public image.
    pending.sort(key=lambda row:row['generated_role']!='text')
    temporary=inside('runtime/tmp/moss-source');temporary.mkdir(parents=True,exist_ok=True);sources={r['role']:r for r in catalog['moss_sources']}
    # Require explicitly supplied checkpoints before any large gated download.
    imported={r['role']:source_file(sources[r['role']],directory,temporary) for r in pending if sources[r['role']].get('required_user_file')}
    for row in pending:
        role=row['generated_role'];source=imported.get(role) or source_file(sources[role],directory,temporary)
        command=[sys.executable,'-I','-B',str(ROOT/'tools/MossConvert.py'),'--source-dir',str(temporary),'--source-file',str(source),'--output-dir',str(ROOT/'MOSS/models'),'--output-name',Path(row['path']).name,'--role',role]
        for field in ['model_name','description']:
            if sources[role].get(field):command.extend(['--'+field.replace('_','-'),sources[role][field]])
        subprocess.run(command,cwd=ROOT,check=True)
        if not verified(inside(row['path']),row):raise RuntimeError('Derived model differs from measured Q8 output; no unverified model accepted.')
        source.unlink() # Only Setup's verified temporary download/link, never the user's source.
    for folder in [ROOT/'MOSS/models/.tmp',temporary]:
        if folder.is_dir() and not any(folder.iterdir()):folder.rmdir()
def inventory(catalog):return [dict(path=row['path'],ok=verified(inside(row['path']),row)) for row in catalog['models']]
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--skip-model-downloads',action='store_true');parser.add_argument('--check-only',action='store_true')
    parser.add_argument('--moss-source-directory',type=Path);parser.add_argument('--gpen-path',type=Path);parser.add_argument('--listen-host',default='127.0.0.1');args=parser.parse_args();ipaddress.ip_address(args.listen_host)
    catalog=json.loads((ROOT/'models.json').read_text(encoding='utf-8'))
    if args.check_only:
        rows=inventory(catalog);ready=all(r['ok'] for r in rows);print(json.dumps(dict(ready=ready,assets=rows,inference_started=False,registry_changed=False),indent=2));return 0 if ready else 2
    helper_path=ROOT/'Helper.kcpps';helper=json.loads(helper_path.read_text(encoding='utf-8-sig'));defaults=json.loads(helper['gendefaults'])
    for port in [int(helper['port']),int(defaults['kcpp_proxy']['port'])]:
        with socket.socket() as probe:
            probe.settimeout(.3)
            if probe.connect_ex(('127.0.0.1',port))==0:raise RuntimeError('Configured port is busy. Close the service before initial Setup; a running installation is never modified.')
    if args.gpen_path:
        row=next(r for r in catalog['models'] if r['path'].endswith('gpen_bfr_512.onnx'));source=args.gpen_path.resolve()
        if not verified(source,row):raise RuntimeError('Supplied GPEN fingerprint differs.')
        target=inside(row['path']);target.parent.mkdir(parents=True,exist_ok=True)
        if not target.exists():shutil.copyfile(source,target)
    if not args.skip_model_downloads:
        prepare_moss(catalog,args.moss_source_directory.resolve() if args.moss_source_directory else None)
        for row in catalog['models']:
            if not row.get('generated_role'):download(row)
    exe=ROOT/'koboldcpp-nocuda.exe'
    if not exe.is_file():raise RuntimeError('Pinned core Windows asset missing.')
    defaults['kcpp_proxy'].update(host=args.listen_host,autostart_enabled=False);exe_sha=sha(exe)
    for p in defaults['kcpp_proxy']['backend_supervisor']['profiles'].values():p.update(executable_sha256=exe_sha,helper_sha256=sha(inside(p['helper'])))
    helper['gendefaults']=json.dumps(defaults,ensure_ascii=False,separators=(',',':'));helper_path.write_text(json.dumps(helper,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    records=[]
    for path in sorted(ROOT.rglob('*')):
        rel=path.relative_to(ROOT)
        if not path.is_file() or {'__pycache__','.git','logs','backups','outputs','proof','artifacts','cache'}.intersection(rel.parts):continue
        if rel.parts[:2] in [('runtime','tmp'),('runtime','cache')] or path.suffix.lower() in ('.zip','.log','.pid','.pyc','.download') or path.name=='portable-manifest.json':continue
        records.append(dict(path=rel.as_posix(),bytes=path.stat().st_size,sha256=sha(path)))
    (ROOT/'portable-manifest.json').write_text(json.dumps(dict(format=1,production_root_is_relative=True,file_count=len(records),files=records),indent=2)+'\n',encoding='utf-8')
    missing=[r['path'] for r in inventory(catalog) if not r['ok']];print(json.dumps(dict(ready=not missing,missing=missing,native_exe_sha256=exe_sha,registry_changed=False,inference_started=False),indent=2));return 2 if missing else 0
if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as error:
        print('Setup stopped: network error; no credentials logged.' if isinstance(error,urllib.error.URLError) else 'Setup stopped: '+str(error),file=sys.stderr);raise SystemExit(2)

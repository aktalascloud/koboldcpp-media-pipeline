"""One-click portable Kobold launcher, with native backend and both public APIs."""
import argparse
import ctypes
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
import hashlib
import re
sys.stdout.reconfigure(encoding='utf-8',errors='backslashreplace');sys.stderr.reconfigure(encoding='utf-8',errors='backslashreplace')
from RuntimePaths import ROOT,asset
from GpuAdapter import adapters

def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def get(port,path):
    with urllib.request.urlopen(f'http://127.0.0.1:{port}'+path,timeout=2) as answer:return json.load(answer)
def managed_launch_with_retry(root,helper,arguments):
    """Repeat only transient inventory/frontend failures; keep all ownership checks."""
    from SupervisorLaunch import launch
    from BackendSupervisor import SupervisorError
    for attempt in range(1,4):
        try:return launch(root,helper,arguments)
        except SupervisorError as error:
            body=getattr(error,'body',None)
            detail=body.get('error') if isinstance(body,dict) else None
            code=detail.get('code') if isinstance(detail,dict) else None
            if code not in ('inventory_failed','frontend_start_failed') or attempt==3:raise
            print('Temporary managed launch error '+code+'; retry '+str(attempt+1)+'/3 in2s.',flush=True)
            time.sleep(2)
def preflight(helper):
    h=read(helper);gd=h['gendefaults'];gd=json.loads(gd) if isinstance(gd,str) else gd
    assert h.get('sdquant',0) in (0,1,2),'Kobold sdquant supports0=off,1=Q8,2=Q4'
    assert 1<=int(gd.get('steps',8))<=9,'This profile is limited to9steps'
    files={}
    for name in ('sdmodel','sdclip1','sdvae','musicdiffusion','musicllm','musicembeddings','musicvae'):
        path=Path(asset(h[name],ROOT));files[name]=dict(path=str(path),exists=path.is_file(),bytes=path.stat().st_size if path.is_file() else None)
    for index,value in enumerate(h.get('sdlora') or []):
        path=Path(asset(value,ROOT));files['sdlora_'+str(index)]=dict(path=str(path),exists=path.is_file(),bytes=path.stat().st_size if path.is_file() else None)
    if h.get('sdclip2'):
        path=Path(asset(h['sdclip2'],ROOT));files['sdclip2']=dict(path=str(path),exists=path.is_file(),bytes=path.stat().st_size if path.is_file() else None)
    for section,key in (('upscaler','model'),('upscaler','detail_model'),('detailer','model'),('detailer','feature_guard_model')):
        value=gd['kcpp_proxy'].get(section,{}).get(key)
        if value:
            path=Path(asset(value,ROOT));files[section+'_'+key]=dict(path=str(path),exists=path.is_file(),bytes=path.stat().st_size if path.is_file() else None)
    for name,relative in (('native_executable','koboldcpp-nocuda.exe'),('face_detector','tools/detailer_models/face_detection_yunet_2023mar.onnx')):
        path=ROOT/relative;files[name]=dict(path=str(path),exists=path.is_file(),bytes=path.stat().st_size if path.is_file() else None)
    import numpy,PIL,cv2,onnxruntime
    packages={name:dict(version=module.__version__,path=str(Path(module.__file__).resolve())) for name,module in [('numpy',numpy),('PIL',PIL),('cv2',cv2),('onnxruntime',onnxruntime)]}
    if gd['kcpp_proxy'].get('detailer',{}).get('provider')=='openvino':
        import openvino
        packages['openvino']=dict(version=openvino.__version__,path=str(Path(openvino.__file__).resolve()))
    assert all(Path(p['path']).is_relative_to(ROOT) for p in packages.values()),'A runtime dependency escaped the portable directory'
    ok=all(value['exists'] for value in files.values())
    row=dict(ok=ok,root=str(ROOT),python=sys.executable,python_version=sys.version,helper=str(helper),files=files,packages=packages,gpus=adapters(),native_port=h['port'],public_port=gd['kcpp_proxy']['port'])
    if gd['kcpp_proxy'].get('backend_supervisor',{}).get('enabled') is True:
        from BackendSupervisor import from_helper
        supervisor=from_helper(helper,root=ROOT)
        row['backend_supervisor']=supervisor.preflight()
        row['ok']=row['ok'] and row['backend_supervisor']['ok']
    return h,gd,row
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');parser.add_argument('--verify',action='store_true');parser.add_argument('--register-startup',action='store_true');parser.add_argument('--no-proxy',action='store_true');a=parser.parse_args()
    if (ROOT/'logs/deployment-in-progress.json').exists():
        print('Deployment is incomplete. Review the deployment journal before starting Native.');return 4
    os.chdir(ROOT);helper=ROOT/'Helper.kcpps';h,gd,check=preflight(helper)
    (ROOT/'logs').mkdir(exist_ok=True)
    (ROOT/'logs'/'portable-preflight.json').write_text(json.dumps(check,ensure_ascii=False,indent=2),encoding='utf-8')
    if a.verify:
        from Verify import verify
        return verify()
    if a.check:
        print(json.dumps(check,ensure_ascii=False));return 0 if check['ok'] else 2
    if not check['ok']:print('Missing model or runtime file. See logs/portable-preflight.json');return 2
    if a.register_startup or gd['kcpp_proxy'].get('autostart_enabled',False):
        from Startup import register
        startup=register()
        if a.register_startup:print(json.dumps(startup,ensure_ascii=False));return 0
    if gd['kcpp_proxy'].get('backend_supervisor',{}).get('enabled') is True:
        return managed_launch_with_retry(ROOT,helper,a)  # Do not enter the old Native/proxy starter.
    helper_hash=hashlib.sha256(helper.read_bytes()).hexdigest()
    child_environment=os.environ.copy();temporary=ROOT/'runtime'/'tmp';temporary.mkdir(exist_ok=True)
    child_environment['TMP']=str(temporary);child_environment['TEMP']=str(temporary)
    try:
        existing=get(h['port'],'/api/extra/version')
    except Exception:existing=None
    if existing:
        active_file=ROOT/'logs'/'native-active.json'
        if active_file.exists() and read(active_file).get('helper_sha256')!=helper_hash:
            print('Helper changed. Close the previous Kobold window before restarting to apply native model settings.');return 3
        if not a.no_proxy:
            try:running_proxy=get(gd['kcpp_proxy']['port'],'/health')
            except Exception:running_proxy=None
            if not running_proxy:
                subprocess.Popen([str(ROOT/'runtime'/'python'/'pythonw.exe'),'-I','-B',str(ROOT/'tools'/'KoboldProxy.py'),'--helper',str(helper),'--ensure'],cwd=ROOT,env=child_environment,creationflags=subprocess.CREATE_NO_WINDOW)
        print('Native backend already running. Existing process preserved;public proxy ensured.');return 0
    proxy=None;native=None
    try:
        if not a.no_proxy:
            proxy=subprocess.Popen([str(ROOT/'runtime'/'python'/'pythonw.exe'),'-I','-B',str(ROOT/'tools'/'KoboldProxy.py'),'--helper',str(helper),'--ensure'],cwd=ROOT,env=child_environment,creationflags=subprocess.CREATE_NO_WINDOW)
        stamp=time.strftime('%Y%m%d-%H%M%S');log_path=ROOT/'logs'/f'Kobold-portable-{stamp}-stdout.log'
        print('KoboldCpp / portable photo pipeline. Public API: http://127.0.0.1:'+str(gd['kcpp_proxy']['port']),flush=True)
        native=subprocess.Popen([str(ROOT/'koboldcpp-nocuda.exe'),'--config',str(helper),'--skiplauncher','--singleinstance'],cwd=ROOT,env=child_environment,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',bufsize=1)
        active=dict(pid=native.pid,helper=str(helper),helper_sha256=helper_hash,native_log=str(log_path),started=time.time(),python=sys.executable)
        if not h.get('sdquant',0):active['actual_image_quantization']='unquantized_checkpoint'
        active_file=ROOT/'logs'/'native-active.json';active_file.write_text(json.dumps(active,indent=2),encoding='utf-8')
        with log_path.open('w',encoding='utf-8') as log:
            for line in native.stdout:
                log.write(line);log.flush()
                if 'Diffusion Model quantized to ' in line:
                    match=re.search(r'Diffusion Model quantized to ([A-Za-z0-9_]+)',line)
                    if match:
                        active['actual_image_quantization']=match.group(1)
                        active_file.write_text(json.dumps(active,indent=2),encoding='utf-8')
                if not line.lstrip().startswith('Input:'):print(line,end='',flush=True)
        return native.wait()
    except KeyboardInterrupt:return 0
    finally:
        if native and native.poll() is None:
            subprocess.run(['taskkill','/PID',str(native.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        if proxy and proxy.poll() is None and not gd['kcpp_proxy'].get('keep_alive_without_backend',False):proxy.terminate()
if __name__=='__main__':raise SystemExit(main())

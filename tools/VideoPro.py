"""Full-encoder Wan48 latents to causal Pro RGB; no Tiny fallback."""
from pathlib import Path
import sys,json,time,hashlib,subprocess,gc,argparse

def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def verify_assets(root,manifest_sha):
    folder=root/'MODELS/vae/lightvae-pro-stream';path=folder/'manifest.json'
    if sha(path)!=manifest_sha:raise ValueError('Pinned Pro manifest changed')
    meta=json.loads(path.read_text());cache=root/'runtime/cache/video-pro-assets.json';old=json.loads(cache.read_text()).get('files',{}) if cache.is_file() else {};current={};files={}
    if {r['role'] for r in meta['files']}!={'start','step','weights'}:raise ValueError('Invalid Pro graph roles')
    for row in meta['files']:
        p=(root/row['path']).resolve()
        if not p.is_relative_to(folder.resolve()) or not p.is_file():raise ValueError('Invalid Pro asset path')
        stat=p.stat();fingerprint={'size':stat.st_size,'mtime_ns':stat.st_mtime_ns,'ctime_ns':stat.st_ctime_ns,'inode':stat.st_ino,'device':stat.st_dev,'sha256':row['sha256']}
        if stat.st_size!=row['bytes'] or (old.get(row['role'])!=fingerprint and sha(p)!=row['sha256']):raise ValueError('Pro asset identity changed')
        files[row['role']]=p;current[row['role']]=fingerprint
    cache.parent.mkdir(exist_ok=True);cache.write_text(json.dumps({'files':current})+'\n')
    return meta,files

def worker(root,capture,dest,manifest_sha):
    import numpy as np,onnxruntime as ort
    from PIL import Image
    from VideoLatents import read_wan_latents
    from GpuAdapter import select_dml_adapter
    meta,files=verify_assets(root,manifest_sha);z,capture_meta=read_wan_latents(capture,root)
    frames=capture_meta['frames'];height=capture_meta['height'];width=capture_meta['width']
    if (width,height) not in ((480,832),(832,480)) or frames>121:raise ValueError('Pro is bounded to native480p Wan clips')
    def positions(size):return [0] if size<=20 else sorted(set([*range(0,size-20+1,16),size-20]))
    tiles=[(x,y) for y in positions(z.shape[-2]) for x in positions(z.shape[-1])];histories=[[] for _ in tiles];states=[];times=[];loads=[];profiles=[];cache_names=['cache'+str(i) for i in range(len(meta['state_specs']))]
    def session(role):
        options=ort.SessionOptions();options.enable_mem_pattern=False;options.execution_mode=ort.ExecutionMode.ORT_SEQUENTIAL;options.intra_op_num_threads=1;options.inter_op_num_threads=1
        options.enable_profiling=True;options.profile_file_prefix=str(dest/('profile-'+role))
        began=time.perf_counter();s=ort.InferenceSession(str(files[role]),sess_options=options,providers=[('DmlExecutionProvider',{'device_id':select_dml_adapter()['index']}),'CPUExecutionProvider']);loads.append(time.perf_counter()-began)
        if s.get_providers()[0]!='DmlExecutionProvider':raise RuntimeError('Pro requires DirectML, no CPU fallback')
        return s
    s=session('start')
    for i,(x,y) in enumerate(tiles):
        began=time.perf_counter();values=s.run(None,{'latent':np.ascontiguousarray(z[:,:,:1,y:y+20,x:x+20])});times.append(time.perf_counter()-began)
        histories[i].append(values[0]);states.append(values[1:])
    profiles.append(Path(s.end_profiling()));del s;gc.collect()
    s=session('step')
    for t in range(1,z.shape[2]):
        for i,(x,y) in enumerate(tiles):
            feed={'latent':np.ascontiguousarray(z[:,:,t:t+1,y:y+20,x:x+20]),**dict(zip(cache_names,states[i]))}
            began=time.perf_counter();values=s.run(None,feed);times.append(time.perf_counter()-began)
            histories[i].append(values[0]);states[i]=values[1:]
    profiles.append(Path(s.end_profiling()));del s,states;gc.collect()
    sums=np.zeros((frames,height,width,3),np.float32);weights=np.zeros((height,width),np.float32);ramp=np.linspace(1/65,64/65,64,dtype=np.float32)
    for i,(x,y) in enumerate(tiles):
        p=np.concatenate(histories[i],axis=2)[0].transpose(1,2,3,0);ph,pw=p.shape[1:3]
        if p.shape[0]!=frames or not np.isfinite(p).all():raise RuntimeError('Invalid Pro temporal output')
        wx=np.ones(pw,np.float32);wy=np.ones(ph,np.float32)
        if x:wx[:64]=ramp
        if y:wy[:64]=ramp
        if x+20<z.shape[-1]:wx[-64:]=ramp[::-1]
        if y+20<z.shape[-2]:wy[-64:]=ramp[::-1]
        weight=wy[:,None]*wx[None,:];px,py=x*16,y*16
        sums[:,py:py+ph,px:px+pw]+=p*weight[None,:,:,None];weights[py:py+ph,px:px+pw]+=weight
    if not np.all(weights>0):raise RuntimeError('Uncovered Pro tile region')
    rgb=np.rint((np.clip(sums/weights[None,:,:,None],-1,1)+1)*127.5).astype(np.uint8)
    Image.fromarray(rgb[-1]).save(dest/'last-frame.png')
    if dest.is_relative_to(root/'RESULTS/Video'):np.save(dest/'decoded.npy',rgb)
    ffmpeg=str(root/'runtime/ffmpeg/ffmpeg.exe');avi=dest/'decoded.avi'
    enc=subprocess.Popen([ffmpeg,'-hide_banner','-loglevel','error','-nostdin','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{width}x{height}','-r','24','-i','pipe:0','-an','-c:v','ffv1',str(avi)],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    _,err=enc.communicate(rgb.tobytes(),timeout=60)
    if enc.returncode:raise RuntimeError('Pro AVI encoder failed:'+err.decode(errors='replace')[-300:])
    subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-nostdin','-y','-i',str(avi),'-c:v','libx264','-preset','veryfast','-crf','18','-pix_fmt','yuv420p','-threads','8',str(dest/'video.mp4')],check=True,timeout=60)
    cpu=[];gpu=0
    for path in profiles:
        events=json.loads(path.read_text());path.unlink();gpu+=sum(e.get('args',{}).get('provider')=='DmlExecutionProvider' for e in events)
        cpu +=[e.get('args',{}).get('op_name') for e in events if e.get('args',{}).get('provider')=='CPUExecutionProvider' and e.get('args',{}).get('op_name') in ('Conv','ConvTranspose','MatMul','Gemm')]
    if not gpu or cpu:raise RuntimeError('Unexpected Pro CPU heavy operation')
    result={'ok':True,'frames':frames,'dimensions':[width,height],'fps':24,'decoder':'LightVAE-Pro causal FP32/DirectML','manifest_sha256':manifest_sha,'tile_threshold':576,'tile_pixels':320,'overlap_pixels':64,'load_seconds':loads,'decode_seconds':sum(times),'dml_nodes':gpu,'cpu_core_nodes':cpu,'capture_sha256':capture_meta['sha256']}
    (dest/'result.json').write_text(json.dumps(result,indent=2)+'\n')

def decode_pro(capture,destination,root,manifest_sha,timeout=300):
    from OwnedMediaProcess import run_owned
    root=Path(root).resolve();capture=Path(capture).resolve();dest=Path(destination).resolve()
    if not any(dest.is_relative_to(root/p) for p in ('OUTPUTS/video','RESULTS/Video')) or dest.exists():raise ValueError('Invalid or existing Pro destination')
    meta,files=verify_assets(root,manifest_sha)
    command=[str(root/'runtime/python/python.exe'),'-I','-B',str(root/'tools/VideoPro.py'),'--worker','--root',str(root),'--capture',str(capture),'--dest',str(dest),'--manifest-sha',manifest_sha]
    process=run_owned(command,root,dest,timeout,memory_guard=True);result=json.loads((dest/'result.json').read_text());result.update(process)
    (dest/'result.json').write_text(json.dumps(result,indent=2)+'\n');return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--worker',action='store_true');p.add_argument('--root',type=Path,required=True);p.add_argument('--capture',type=Path,required=True);p.add_argument('--dest',type=Path,required=True);p.add_argument('--manifest-sha',required=True);a=p.parse_args()
    if not a.worker:raise SystemExit('This module is launched by the owned media controller')
    root=a.root.resolve();dest=a.dest.resolve()
    if not any(dest.is_relative_to(root/f) for f in ('OUTPUTS/video','RESULTS/Video')):raise ValueError('Invalid decoder worker destination')
    worker(root,a.capture.resolve(),dest,a.manifest_sha)

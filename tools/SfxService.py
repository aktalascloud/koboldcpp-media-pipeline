"""Portable SA3 CPU effects shared by the video timeline and standalone API."""
from pathlib import Path
import hashlib,json,math,os,subprocess,tempfile,time,uuid,wave


_SFX_BATCH_SHA256 = '55137f9fffded2c6a5bede0421cb086a892ed321428476184fc7472fca542fcc'

def validate(payload):
    if not isinstance(payload,dict) or set(payload)-{'prompt','duration','seed','response_format'}:raise ValueError('SFX: prompt, duration, seed, response_format')
    prompt=payload.get('prompt','');duration=payload.get('duration',5);seed=payload.get('seed',424242);fmt=payload.get('response_format','wav')
    if not isinstance(prompt,str) or not prompt.strip() or len(prompt)>2000:raise ValueError('SFX prompt:1..2000символов; описание звука по-английски')
    if type(duration) not in (int,float) or not math.isfinite(duration) or not .25<=duration<=60:raise ValueError('SFX duration:0.25..60секунд')
    if type(seed) is not int or not 0<=seed<2**31:raise ValueError('SFX seed:0..2147483647')
    if fmt not in ('wav','mp3'):raise ValueError('SFX response_format: wav либо mp3')
    return {'prompt':prompt.strip(),'duration':float(duration),'seed':seed,'response_format':fmt}

def _sa3_command(root,cfg,prompt):
    from AudioServices import services,sfx_assets
    opts=services(cfg)
    models, assets=sfx_assets(cfg,root)
    executable=root/'runtime/sa3/sa3-generate.exe'
    if not executable.is_file():raise ValueError('SA3 SFX не установлен полностью внутри комплекта')
    command = [str(executable), '--model', 'small-sfx', '--models-dir', str(models),
               '--encoding', 'q8_0', '--ae-encoding', 'q8_0', '--t5-encoding', 'f16']
    for role, path in assets.items():
        command.extend((f'--{role}', str(path)))
    command.extend(('--steps', '8', '--threads', str(opts['sfx_threads']), '--prompt', prompt))
    return command


def _run_sa3(command,root,log_dir,remaining):
    from OwnedMediaProcess import run_owned
    environment={**os.environ,'SA3_DEVICE':'cpu','SA3_GPU':'0'}
    environment.pop('SA3_T5_SHORT_CONTEXT',None)
    if _supports_batch(root):environment['SA3_T5_SHORT_CONTEXT']='1'
    run_owned(command,root,log_dir,min(900,remaining()),environment=environment)


def native_clip(root,cfg,prompt,duration,seed,target,remaining):
    root=Path(root).resolve();target=Path(target).resolve()
    if not target.is_relative_to(root):raise ValueError('SFX output must stay in the portable directory')
    command=_sa3_command(root,cfg,prompt)
    target.parent.mkdir(parents=True,exist_ok=True)
    command.extend(('--duration', str(max(.25, duration)), '--seed', str(seed), '--out', str(target)))
    _run_sa3(command,root,target.parent/(target.stem+'-worker'),remaining)
    if not target.is_file() or target.stat().st_size<44:raise RuntimeError('SA3 вернул пустой звук')


def _supports_batch(root):
    executable=root/'runtime/sa3/sa3-generate.exe'
    try:
        provenance=json.loads(executable.with_name('provenance.json').read_text(encoding='utf-8-sig'))
        if not isinstance(provenance,dict) or provenance.get('sfx_batch_sha256')!=_SFX_BATCH_SHA256:
            return False
        if not executable.resolve().is_relative_to(root):
            return False
        with executable.open('rb') as binary:
            return hashlib.file_digest(binary,'sha256').hexdigest()==_SFX_BATCH_SHA256
    except (OSError,ValueError):
        return False


def _native_batch(root,cfg,prompt,folder,chunks,remaining):
    from OwnedMediaProcess import OwnedMediaError
    command=_sa3_command(root,cfg,prompt)
    # The worker owns this temporary directory only. Legacy retries write the
    # regular part paths, which remain untouched until the whole batch validates.
    with tempfile.TemporaryDirectory(prefix='batch-parts-',dir=folder) as name:
        stage=Path(name)
        if stage.resolve().parent!=folder or stage.is_symlink():
            raise ValueError('Invalid SFX batch output directory')
        command.extend(('--sfx-batch',str(stage)))
        for _,duration,seed in chunks:
            command.extend(('--sfx-part',str(max(.25,duration)),str(seed)))
        staged=[stage/target.name for target,_,_ in chunks]
        try:
            _run_sa3(command,root,folder/'batch-worker',remaining)
            for part in staged:
                if part.is_symlink() or not part.is_file():
                    raise OSError('SA3 batch part is missing')
                with wave.open(str(part),'rb') as audio:
                    frames=audio.getnframes()
                    if frames<=0 or part.stat().st_size!=44+frames*audio.getnchannels()*audio.getsampwidth():
                        raise wave.Error('Incomplete SA3 batch WAV')
        except (OwnedMediaError,OSError,EOFError,wave.Error):
            remaining()
            return False
        remaining()
        for source,(target,_,_) in zip(staged,chunks):
            source.rename(target)
    return True

def generate(root,cfg,payload,remaining):
    from BackendSupervisor import write_json
    p=validate(payload);root=Path(root).resolve();job_id=uuid.uuid4().hex;folder=root/'RESULTS/generated/sfx'/job_id;folder.mkdir(parents=True)
    began=time.perf_counter();chunks=[];left=p['duration'];index=0
    # Short real generations bound CPU memory; extra20ms compensates each
    # crossfade. No repeated audio loop is used to simulate longer generation.
    while left>1e-7:
        length=min(5.,left);raw=folder/f'part-{index}.wav';duration=length+(.02 if index else 0)
        chunks.append((raw,duration,(p['seed']+index)%(2**31)));left-=length;index+=1
    if not (len(chunks)>1 and _supports_batch(root) and _native_batch(root,cfg,p['prompt'],folder,chunks,remaining)):
        for raw,duration,seed in chunks:
            native_clip(root,cfg,p['prompt'],duration,seed,raw,remaining)
    parts=[raw for raw,_,_ in chunks]
    command=[str(root/'runtime/ffmpeg/ffmpeg.exe'),'-hide_banner','-loglevel','error','-nostdin','-y']
    for path in parts:command+=['-i',str(path)]
    filters=[f'[{i}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[p{i}]' for i in range(len(parts))]
    label='p0'
    for i in range(1,len(parts)):
        next_label='m'+str(i);filters.append(f'[{label}][p{i}]acrossfade=d=0.02:c1=tri:c2=tri[{next_label}]');label=next_label
    filters.append(f'[{label}]atrim=duration={p["duration"]:.9f},asetpts=PTS-STARTPTS[out]')
    wav=folder/'audio.wav';command+=['-filter_complex',';'.join(filters),'-map','[out]','-c:a','pcm_s16le',str(wav)]
    subprocess.run(command,check=True,timeout=remaining(),stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    with wave.open(str(wav),'rb') as audio:actual=audio.getnframes()/audio.getframerate();channels=audio.getnchannels()
    if abs(actual-p['duration'])>.05 or channels!=2:raise RuntimeError('SA3 output duration/channels differ from the requested effect')
    output=wav
    if p['response_format']=='mp3':
        output=folder/'audio.mp3';subprocess.run([str(root/'runtime/ffmpeg/ffmpeg.exe'),'-v','error','-nostdin','-y','-i',str(wav),'-c:a','libmp3lame','-q:a','2',str(output)],check=True,timeout=remaining(),stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    remaining()
    meta={'id':job_id,'backend':'sa3.cpp CPU Haswell','requested_seconds':p['duration'],'actual_seconds':actual,'format':p['response_format'],'sample_rate':48000,'channels':2,'native_chunks':len(parts),'steps_per_chunk':8,'seed':p['seed'],'generation_seconds':time.perf_counter()-began,'bytes':output.stat().st_size,'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'gpu_model_switched':False}
    write_json(folder/'metadata.json',meta)
    for path in parts:path.unlink(missing_ok=True)
    return output,meta

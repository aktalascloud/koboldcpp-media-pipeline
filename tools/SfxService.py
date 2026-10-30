"""Portable SA3 CPU effects shared by the video timeline and standalone API."""
from pathlib import Path
import hashlib,json,math,os,subprocess,time,uuid,wave

def validate(payload):
    if not isinstance(payload,dict) or set(payload)-{'prompt','duration','seed','response_format'}:raise ValueError('SFX: prompt, duration, seed, response_format')
    prompt=payload.get('prompt','');duration=payload.get('duration',5);seed=payload.get('seed',424242);fmt=payload.get('response_format','wav')
    if not isinstance(prompt,str) or not prompt.strip() or len(prompt)>2000:raise ValueError('SFX prompt:1..2000символов; описание звука по-английски')
    if type(duration) not in (int,float) or not math.isfinite(duration) or not .25<=duration<=60:raise ValueError('SFX duration:0.25..60секунд')
    if type(seed) is not int or not 0<=seed<2**31:raise ValueError('SFX seed:0..2147483647')
    if fmt not in ('wav','mp3'):raise ValueError('SFX response_format: wav либо mp3')
    return {'prompt':prompt.strip(),'duration':float(duration),'seed':seed,'response_format':fmt}

def native_clip(root,cfg,prompt,duration,seed,target,remaining):
    from AudioServices import services,capabilities
    from OwnedMediaProcess import run_owned
    root=Path(root).resolve();target=Path(target).resolve()
    if not target.is_relative_to(root):raise ValueError('SFX output must stay in the portable directory')
    opts=services(cfg);models=Path(opts['sfx_model_dir']);models=(models if models.is_absolute() else root/models).resolve()
    if not models.is_relative_to(root) or not capabilities(cfg)['sfx']:raise ValueError('SA3 SFX не установлен полностью внутри комплекта')
    target.parent.mkdir(parents=True,exist_ok=True)
    command=[str(root/'runtime/sa3/sa3-generate.exe'),'--model','small-sfx','--models-dir',str(models),'--encoding','q8_0','--ae-encoding','q8_0','--t5-encoding','f16','--duration',str(max(.25,duration)),'--steps','8','--threads',str(opts['sfx_threads']),'--seed',str(seed),'--prompt',prompt,'--out',str(target)]
    run_owned(command,root,target.parent/(target.stem+'-worker'),min(900,remaining()),environment={**os.environ,'SA3_DEVICE':'cpu','SA3_GPU':'0'})
    if not target.is_file() or target.stat().st_size<44:raise RuntimeError('SA3 вернул пустой звук')

def generate(root,cfg,payload,remaining):
    from BackendSupervisor import write_json
    p=validate(payload);root=Path(root).resolve();job_id=uuid.uuid4().hex;folder=root/'OUTPUTS/sfx'/job_id;folder.mkdir(parents=True)
    began=time.perf_counter();parts=[];left=p['duration'];index=0
    # Short real generations bound CPU memory; extra20ms compensates each
    # crossfade. No repeated audio loop is used to simulate longer generation.
    while left>1e-7:
        length=min(5.,left);raw=folder/f'part-{index}.wav';duration=length+(.02 if index else 0)
        native_clip(root,cfg,p['prompt'],duration,(p['seed']+index)%(2**31),raw,remaining);parts.append(raw);left-=length;index+=1
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

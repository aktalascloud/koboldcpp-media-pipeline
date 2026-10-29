"""Separate YuE2 soundtrack and lossless video-stream MP4 mux. No lip-sync claim."""
from pathlib import Path
import json,math,subprocess,time,hashlib,cv2
from NativeVideo import request_audio_deadline
from MusicContract import prepare_music

def audio_options(value,default_enabled=True):
    if value is None:return {'enabled':bool(default_enabled),'style':'Gentle cinematic instrumental background, atmospheric, natural acoustic texture, no vocals','lyrics':'','volume':.7}
    if type(value) is bool:return {'enabled':value,'style':'Gentle cinematic instrumental background, no vocals','lyrics':'','volume':.7}
    if not isinstance(value,dict) or set(value)-{'enabled','style','lyrics','volume','seed'}:raise ValueError('audio accepts enabled/style/lyrics/volume/seed')
    result={'enabled':True,'style':'Gentle cinematic instrumental background, no vocals','lyrics':'','volume':.7,**value}
    if type(result['enabled']) is not bool or not isinstance(result['style'],str) or not result['style'].strip() or len(result['style'])>2000 or not isinstance(result['lyrics'],str) or len(result['lyrics'])>8000:raise ValueError('Invalid video audio text/enable flag')
    if isinstance(result['volume'],bool) or not isinstance(result['volume'],(int,float)) or not math.isfinite(result['volume']) or not 0<=result['volume']<=1:raise ValueError('Audio volume must be0..1')
    if 'seed' in result and (type(result['seed']) is not int or not 0<=result['seed']<2**63):raise ValueError('Invalid video audio seed')
    return result

def mux_audio(folder,root,metadata,volume,timeout):
    folder=Path(folder);root=Path(root);source=folder/'video.mp4';audio=folder/'audio.mp3';target=folder/'video-audio.work.mp4'
    frames=metadata['frames'];fps=metadata['fps'];duration=frames/fps;fade=min(.12,duration/3)
    command=[str(root/'runtime/ffmpeg/ffmpeg.exe'),'-hide_banner','-loglevel','error','-nostdin','-y','-i',str(source),'-i',str(audio),'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','192k','-af',f'volume={volume},apad,atrim=duration={duration:.9f},afade=t=out:st={max(0,duration-fade):.9f}:d={fade:.9f}','-t',f'{duration:.9f}','-movflags','+faststart',str(target)]
    began=time.perf_counter();subprocess.run(command,check=True,timeout=timeout,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    check=cv2.VideoCapture(str(target));actual=round(check.get(cv2.CAP_PROP_FRAME_COUNT));actual_fps=check.get(cv2.CAP_PROP_FPS);check.release()
    if actual!=frames or abs(actual_fps-fps)>.001:raise RuntimeError('Audio mux changed video frames/FPS')
    subprocess.run([str(root/'runtime/ffmpeg/ffmpeg.exe'),'-hide_banner','-loglevel','error','-nostdin','-i',str(target),'-map','0:a:0','-frames:a','1','-f','null','NUL'],check=True,timeout=max(1,timeout-(time.perf_counter()-began)),stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    silent=folder/'video-silent.mp4'
    if silent.exists():raise ValueError('Existing silent video is preserved')
    source.rename(silent);target.rename(source)
    return {'mux_seconds':time.perf_counter()-began,'video_stream':'copied without re-encoding','mp4_audio_codec':'AAC192k','source_audio_format':'MP3 stereo','duration_seconds':duration,'video_frames_preserved':True}

def generate_soundtrack(supervisor,root,folder,cfg,options,budget,metadata):
    if not options['enabled']:return {'enabled':False}
    root=Path(root).resolve();folder=Path(folder).resolve();cap=max(6,math.ceil(metadata['frames']/metadata['fps']))
    payload=prepare_music({k:v for k,v in options.items() if k in ('style','lyrics','seed')}|{'duration':cap},cfg)
    began=time.perf_counter()
    with supervisor.lock:
        previous=supervisor.readiness_seconds
        try:
            supervisor.readiness_seconds=min(float(previous),budget.remaining())
            with supervisor.lease('music',cfg) as active:
                body=request_audio_deadline(active['backend']+'/api/extra/music/generate',payload,timeout=budget.remaining())
                (folder/'audio.mp3').write_bytes(body)
            supervisor.stop_idle()
        finally:supervisor.readiness_seconds=previous
    seconds=time.perf_counter()-began
    mux=mux_audio(folder,root,metadata,options['volume'],budget.remaining())
    return {'enabled':True,'generator':'YuE2-3B Q8_0','generation_and_load_seconds':seconds,'requested_music_cap_seconds':cap,'source_bytes':len(body),'source_sha256':hashlib.sha256(body).hexdigest(),'conditioning':'Separate text-to-music; no video-conditioned Foley or lip synchronization','music_style':options['style'],**mux}

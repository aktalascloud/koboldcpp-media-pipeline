"""Stored-video import and audio-driven postprocessing; never a second Wan render."""
from pathlib import Path
import hashlib,json,re,subprocess,time,uuid,math
import cv2
from AudioServices import remote,services,voice_registry

class StoredVideoMissing(ValueError):pass

def saved(root,video_id):
    if not isinstance(video_id,str) or not re.fullmatch('[0-9a-f]{32}',video_id):raise ValueError('Invalid video_id')
    base=(Path(root)/'RESULTS/generated/video').resolve();path=(base/video_id).resolve()
    if not path.is_relative_to(base) or not (path/'service.json').is_file() or not (path/'video.mp4').is_file():raise StoredVideoMissing('Stored video not found')
    record=json.loads((path/'service.json').read_text(encoding='utf-8'))['metadata']
    if record.get('status')!='completed' or hashlib.file_digest((path/'video.mp4').open('rb'),'sha256').hexdigest()!=record.get('output_sha256'):raise ValueError('Stored video is incomplete or its SHA changed')
    return path

def inspect(path):
    cap=cv2.VideoCapture(str(path));fps=cap.get(cv2.CAP_PROP_FPS);frames=round(cap.get(cv2.CAP_PROP_FRAME_COUNT));w=round(cap.get(cv2.CAP_PROP_FRAME_WIDTH));h=round(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if fps not in (24,48,60) or not 1<=frames<=1800 or w*h>2_000_000 or min(w,h)<96 or frames/fps>30.000001:cap.release();raise ValueError('Video must be24/48/60FPS, up to30seconds/2MP')
    ok,frame=cap.read();cap.release()
    if not ok:raise ValueError('Video cannot be decoded')
    return dict(width=w,height=h,frames=frames,fps=fps,duration_seconds=frames/fps)

def receipt(folder,metadata,base):
    from BackendSupervisor import write_json
    identity=folder.name;url=base+'/api/extra/video/media/'+identity+'/video.mp4'
    metadata.update(id=identity,url=url,output_bytes=(folder/'video.mp4').stat().st_size,output_sha256=hashlib.file_digest((folder/'video.mp4').open('rb'),'sha256').hexdigest())
    metadata.update(status='completed');metadata.setdefault('model','stored-video')
    if (folder/'speech.wav').is_file():metadata['speech_audio_url']=base+'/api/extra/video/media/'+identity+'/speech.wav'
    record={'id':identity,'object':'video','created':int(time.time()),'url':url,'metadata':metadata,'data':[{'url':url,'mime_type':'video/mp4'}]}
    write_json(folder/'service.json',{'created':record['created'],'metadata':metadata});return record

def import_mp4(root,body,base=''):
    root=Path(root);identity=uuid.uuid4().hex;folder=root/'RESULTS/generated/video'/identity
    if not 32<=len(body)<=128*1024**2 or b'ftyp' not in body[:64]:raise ValueError('Expected MP4 upload, at most128MiB')
    folder.mkdir(parents=True);source=folder/'upload.mp4';source.write_bytes(body)
    metadata=inspect(source)
    # Validate the complete stream, not a container's declared frame count alone.
    ffmpeg=str(root/'runtime/ffmpeg/ffmpeg.exe')
    check=subprocess.run([ffmpeg,'-v','info','-xerror','-nostdin','-nostats','-i',str(source),'-map','0:v:0','-an','-vf','vfrdet','-progress','pipe:1','-f','null','NUL'],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=60)
    counts=re.findall(rb'(?m)^frame=(\d+)',check.stdout);vfr=re.findall(rb'VFR:([0-9.]+)',check.stderr)
    if not counts or int(counts[-1])!=metadata['frames'] or not vfr or float(vfr[-1])!=0:raise ValueError('Import requires a complete constant-frame-rate MP4 with matching frame count')
    subprocess.run([ffmpeg,'-v','error','-nostdin','-i',str(source),'-map','0:v:0','-map','0:a:0?','-c','copy','-movflags','+faststart',str(folder/'video.mp4')],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=30)
    source.unlink();metadata.update(operation='import',origin='client-owned MP4',native_generation=False)
    return receipt(folder,metadata,base)

def interpolate(root,cfg,payload,base='',timeout=300):
    if not isinstance(payload,dict) or set(payload)-{'video_id','fps'}:raise ValueError('Expected video_id,fps')
    fps=payload.get('fps',48)
    if type(fps) is not int or fps not in (48,60):raise ValueError('fps:48/60')
    source=saved(root,payload.get('video_id'));metadata=inspect(source/'video.mp4')
    if metadata['fps']!=24:raise ValueError('RIFE input must be24FPS; no repeated interpolation')
    folder=Path(root)/'RESULTS/generated/video'/uuid.uuid4().hex;folder.mkdir(parents=True)
    from VideoRife import interpolate_video
    report=interpolate_video(source/'video.mp4',folder/'rife',root,timeout=timeout,target_fps=fps,model_dir=cfg.get('proxy',{}).get('video',{}).get('rife_models'))
    Path(report['output']).replace(folder/'silent.mp4')
    subprocess.run([str(Path(root)/'runtime/ffmpeg/ffmpeg.exe'),'-v','error','-nostdin','-i',str(folder/'silent.mp4'),'-i',str(source/'video.mp4'),'-map','0:v:0','-map','1:a:0?','-c','copy','-t',str(report['output_duration_seconds']),'-movflags','+faststart',str(folder/'video.mp4')],check=True,timeout=30,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    (folder/'silent.mp4').unlink()
    metadata.update(fps=fps,frames=report['output_frames'],duration_seconds=report['output_duration_seconds'],operation='interpolate',source_video_id=source.name,frame_interpolation=report)
    cap=cv2.VideoCapture(str(folder/'video.mp4'));cap.set(cv2.CAP_PROP_POS_FRAMES,metadata['frames']-1);ok,last=cap.read();cap.release()
    if ok:cv2.imwrite(str(folder/'last-frame.png'),last)
    return receipt(folder,metadata,base)

def lipsync(root,cfg,payload,base='',timeout=300):
    allowed={'video_id','mode','target_box','speech'}
    if not isinstance(payload,dict) or set(payload)-allowed:raise ValueError('Expected video_id,mode,target_box,speech')
    mode=payload.get('mode')
    if mode not in ('onscreen','voiceover'):raise ValueError('mode: onscreen/voiceover')
    if mode=='onscreen':
        box=payload.get('target_box')
        if not isinstance(box,list) or len(box)!=4 or any(type(n) not in (int,float) or not math.isfinite(n) for n in box):raise ValueError('Explicit normalized target_box[x,y,w,h] required')
        x,y,w,h=box
        if not 0<=x<x+w<=1 or not 0<=y<y+h<=1:raise ValueError('Invalid normalized target_box')
        from VideoLipSync import assets
        assets(root)
    source=saved(root,payload.get('video_id'));speech=payload.get('speech')
    if not isinstance(speech,dict) or set(speech)-{'text','voice','language','start','voice_profile','speaker_id'} or not {'text','voice','language'}.issubset(speech):raise ValueError('speech requires text,voice,language')
    if not isinstance(speech['text'],str) or not 1<=len(speech['text'])<=1500 or speech['language'] not in ('ru','en'):raise ValueError('Invalid speech text/language')
    voices=voice_registry(services(cfg))[speech['language']]
    if speech['voice'] not in set().union(*voices.values()):raise ValueError('Voice is not registered for this language in the configured TTS connection')
    if mode=='onscreen' and speech.get('voice_profile') not in ('female','male'):raise ValueError('Onscreen speech requires explicit voice_profile female/male; gender is not inferred from an image')
    if 'voice_profile' in speech and (speech['voice_profile'] not in voices or speech['voice'] not in voices[speech['voice_profile']]):raise ValueError('Voice does not match the explicit profile/language')
    if 'speaker_id' in speech and (not isinstance(speech['speaker_id'],str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',speech['speaker_id'])):raise ValueError('Invalid speaker_id')
    metadata=inspect(source/'video.mp4');start=speech.get('start',0)
    if type(start) not in (int,float) or not math.isfinite(start) or not 0<=start<metadata['duration_seconds']:raise ValueError('Invalid speech start')
    identity=uuid.uuid4().hex;folder=Path(root)/'RESULTS/generated/video'/identity;folder.mkdir(parents=True)
    began=time.perf_counter();status,_,body=remote(cfg,'/v1/audio/speech',json.dumps({'model':'tts-1','input':speech['text'],'voice':speech['voice'],'language':speech['language'],'response_format':'wav'}).encode(),timeout=min(90,timeout))
    if status!=200 or not body or len(body)>32*1024**2:raise RuntimeError('TTS failed or returned invalid audio size')
    audio=folder/'speech.wav';audio.write_bytes(body)
    if mode=='onscreen':
        from VideoLipSync import process
        provider=cfg.get('proxy',{}).get('video',{}).get('lipsync_provider','cpu')
        if provider not in ('cpu','directml'):raise ValueError('Configured lipsync_provider must be cpu/directml')
        report=process(source/'video.mp4',audio,folder/'mouth',root,payload.get('target_box'),timeout=max(1,timeout-(time.perf_counter()-began)),start_seconds=start,provider=provider)
        (folder/'mouth/video.mp4').replace(folder/'video.mp4')
    else:
        import wave
        with wave.open(str(audio),'rb') as wav:duration=wav.getnframes()/wav.getframerate()
        if duration+start>metadata['duration_seconds']+1/16000:raise ValueError('Speech does not fit; no silent truncation')
        subprocess.run([str(Path(root)/'runtime/ffmpeg/ffmpeg.exe'),'-v','error','-nostdin','-i',str(source/'video.mp4'),'-i',str(audio),'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-af',f'adelay={round(start*1000)}:all=1,apad,atrim=duration={metadata["duration_seconds"]}','-t',str(metadata['duration_seconds']),str(folder/'video.mp4')],check=True,timeout=60,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        report={'mode':'voiceover','video_encoding':'copied','speech_seconds':duration}
    metadata.update(operation='lipsync' if mode=='onscreen' else 'voiceover',parent_video_id=source.name,lip_sync=mode=='onscreen',speech={'voice':speech['voice'],'language':speech['language'],'voice_profile':speech.get('voice_profile'),'speaker_id':speech.get('speaker_id'),'start':start,'audio_sha256':hashlib.file_digest(audio.open('rb'),'sha256').hexdigest()},mouth=report,post_seconds=time.perf_counter()-began)
    previous=json.loads((source/'service.json').read_text(encoding='utf-8'))['metadata']
    metadata['speech_segments']=[*previous.get('speech_segments',[]),{'video_id':identity,**metadata['speech']}] if mode=='onscreen' else []
    # A real last frame is available for downstream clients; no synthetic continuation.
    cap=cv2.VideoCapture(str(folder/'video.mp4'));cap.set(cv2.CAP_PROP_POS_FRAMES,metadata['frames']-1);ok,last=cap.read();cap.release()
    if ok:cv2.imwrite(str(folder/'last-frame.png'),last)
    return receipt(folder,metadata,base)

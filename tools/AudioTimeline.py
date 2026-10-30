"""Real timed audio stems: SA3 SFX, configured TTS, YuE2 music; no false Foley/lip-sync."""
from pathlib import Path
import json,math,re,hashlib,subprocess,time,os
from AudioServices import services,select_voice,remote,plan

def number(value):return type(value) in (int,float) and math.isfinite(value)

def validate(options,duration,cfg):
    if not number(duration) or not 0<duration<=360:raise ValueError('Неверная длительность видеоряда')
    if type(options.get('auto_plan',False)) is not bool:raise ValueError('auto_plan должен быть переключателем')
    speakers=options.get('speakers',[])
    if not isinstance(speakers,list) or len(speakers)>8:raise ValueError('Допустимы до8 персонажей')
    by_id={}
    for row in speakers:
        if not isinstance(row,dict) or not isinstance(row.get('id'),str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',row['id']) or row['id'] in by_id:raise ValueError('Неверный или повторный speaker_id')
        if row.get('voice_profile') not in ('female','male'):raise ValueError('Для персонажа задайте voice_profile female/male явно')
        by_id[row['id']]=row
    tracks=options.get('tracks')
    if options.get('auto_plan'):
        generated=plan(cfg,options.get('prompt',options.get('style','')),duration,speakers);tracks=generated.get('tracks')
    if not isinstance(tracks,list) or not 1<=len(tracks)<=8:raise ValueError('Укажите1..8 аудиодорожек')
    result=[];opts=services(cfg)
    for index,row in enumerate(tracks):
        if not isinstance(row,dict) or set(row)-{'kind','prompt','text','start','end','volume','speaker_id','seed','fit','language'}:raise ValueError('Неизвестные поля аудиодорожки')
        kind=row.get('kind');start=row.get('start');end=row.get('end');volume=row.get('volume',.7)
        if kind not in ('sfx','speech','music') or not number(start) or not number(end) or not 0<=start<end<=duration+.001 or not number(volume) or not 0<=volume<=1:raise ValueError('Проверьте kind/start/end/volume аудиодорожки')
        text=row.get('text','') if kind=='speech' else row.get('prompt','')
        if not isinstance(text,str) or not text.strip() or len(text)>2000:raise ValueError('Для дорожки нужен text речи либо prompt звука')
        item={**row,'start':float(start),'end':min(float(end),duration),'volume':float(volume),'index':index}
        if kind=='speech':
            if not opts['tts_enabled']:raise ValueError('TTS не подключён в Audio')
            speaker=by_id.get(row.get('speaker_id'))
            if speaker is None:raise ValueError('Дорожка речи должна ссылаться на описанного speaker_id')
            language=row.get('language',speaker.get('language',options.get('language','ru')))
            if not isinstance(language,str):raise ValueError('language: ru либо en')
            language=language.lower().split('-')[0]
            item['voice']=select_voice(opts,{**speaker,'language':language});item['language']=language
            if row.get('fit','natural') not in ('natural','stretch'):raise ValueError('fit: natural либо stretch')
        if kind=='sfx':
            from AudioServices import capabilities
            if not capabilities(cfg)['sfx']:raise ValueError('SA3 SFX не установлен полностью: нужны native runtime и пять файлов моделей')
        if 'seed' in row and (type(row['seed']) is not int or not 0<=row['seed']<2**31):raise ValueError('Некорректный seed дорожки')
        result.append(item)
    return {'tracks':result,'speakers':speakers,'duration_seconds':duration,'voice_map':{t['speaker_id']+':'+t['language']:t['voice'] for t in result if t['kind']=='speech'}}

def render(supervisor,root,folder,cfg,options,budget,metadata):
    from OwnedMediaProcess import run_owned
    from MusicContract import prepare_music
    from NativeVideo import request_audio_deadline
    root=Path(root).resolve();folder=Path(folder).resolve();duration=metadata['frames']/metadata['fps'];timeline=options.get('_validated_timeline') or validate(options,duration,cfg)
    stems=folder/'audio-tracks';stems.mkdir(exist_ok=True);reports=[];paths=[];began=time.perf_counter()
    for track in timeline['tracks']:
        budget.remaining();index=track['index'];length=track['end']-track['start'];kind=track['kind'];target=stems/(str(index)+('.mp3' if kind=='music' else '.wav'));tick=time.perf_counter()
        if kind=='speech':
            payload={'model':'tts-1','input':track['text'],'voice':track['voice'],'language':track['language'],'response_format':'wav','seed':track.get('seed',int(hashlib.sha256(track['speaker_id'].encode()).hexdigest()[:7],16))}
            status,headers,body=remote(cfg,'/v1/audio/speech',json.dumps(payload).encode(),timeout=budget.remaining())
            if status!=200 or not body:raise RuntimeError('TTS вернул ошибку или пустое аудио')
            target.write_bytes(body)
        elif kind=='music':
            payload=prepare_music({'style':track['prompt'],'lyrics':track.get('text',''),'duration':max(6,math.ceil(length))},cfg)
            with supervisor.lease('music',cfg) as active:target.write_bytes(request_audio_deadline(active['backend']+'/api/extra/music/generate',payload,timeout=budget.remaining()))
            supervisor.stop_idle()
        else:
            exe=root/'runtime/sa3/sa3-generate.exe';opts=services(cfg);models=Path(opts['sfx_model_dir']);models=(models if models.is_absolute() else root/models).resolve()
            if not models.is_relative_to(root):raise ValueError('Для портативности поместите SFX-модели в папку комплекта')
            if not exe.is_file() or not (models/'stable-audio-3-small-sfx-dit-0.5B-v1.0-Q8_0.gguf').is_file():raise ValueError('SA3 SFX не установлен')
            environment={**os.environ,'SA3_DEVICE':'cpu','SA3_GPU':'0'}
            command=[str(exe),'--model','small-sfx','--models-dir',str(models),'--encoding','q8_0','--ae-encoding','q8_0','--t5-encoding','f16','--duration',str(max(.25,length)),'--steps','8','--threads',str(opts['sfx_threads']),'--seed',str(track.get('seed',424242+index)),'--prompt',track['prompt'],'--out',str(target)]
            run_owned(command,root,stems/('worker-'+str(index)),min(900,budget.remaining()),environment=environment)
        if not target.is_file() or target.stat().st_size<44:raise RuntimeError('Пустой звук дорожки')
        probe=subprocess.run([str(root/'runtime/ffmpeg/ffmpeg.exe'),'-hide_banner','-i',str(target)],capture_output=True,text=True,errors='replace',timeout=min(30,budget.remaining()))
        match=re.search(r'Duration:\s*(\d+):(\d+):([0-9.]+)',probe.stderr)
        if not match:raise RuntimeError('Не удалось определить длительность аудиодорожки')
        actual=int(match[1])*3600+int(match[2])*60+float(match[3]);speed=1.
        if kind=='speech' and actual>length+.08:
            speed=actual/length
            if track.get('fit','natural')!='stretch' or not .5<=speed<=2:raise ValueError('Речь не помещается в таймкод. Увеличьте интервал или явно задайте fit=stretch (до2×); речь не обрезается молча.')
        paths.append((target,track,speed));reports.append({k:track.get(k) for k in ('kind','start','end','volume','speaker_id','voice')}|{'source_seconds':actual,'render_seconds':time.perf_counter()-tick,'sha256':hashlib.sha256(target.read_bytes()).hexdigest()})
    ffmpeg=str(root/'runtime/ffmpeg/ffmpeg.exe');command=[ffmpeg,'-hide_banner','-loglevel','error','-nostdin','-y','-i',str(folder/'video.mp4')];filters=[]
    for i,(path,track,speed) in enumerate(paths,1):
        command+=['-i',str(path)];length=track['end']-track['start'];delay=round(track['start']*1000)
        effect=f'atempo={speed},' if speed!=1 else ''
        filters.append(f'[{i}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,{effect}atrim=duration={length:.9f},asetpts=PTS-STARTPTS,volume={track["volume"]},afade=t=in:d={min(.01,length/4):.9f},afade=t=out:st={max(0,length-.025):.9f}:d={min(.025,length/3):.9f},adelay={delay}|{delay}[t{i}]')
    labels=''.join(f'[t{i}]' for i in range(1,len(paths)+1));filters.append(labels+f'amix=inputs={len(paths)}:duration=longest:normalize=0,alimiter=limit=0.95,apad,atrim=duration={duration:.9f},asplit=2[a_mux][a_mp3]')
    target=folder/'video-timeline.work.mp4';source_audio=folder/'audio.mp3'
    command+=['-filter_complex',';'.join(filters),'-map','0:v:0','-map','[a_mux]','-c:v','copy','-c:a','aac','-b:a','192k','-t',str(duration),'-movflags','+faststart',str(target),'-map','[a_mp3]','-c:a','libmp3lame','-q:a','2',str(source_audio)]
    subprocess.run(command,check=True,timeout=budget.remaining(),stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    import cv2
    check=cv2.VideoCapture(str(target));frames=round(check.get(cv2.CAP_PROP_FRAME_COUNT));fps=check.get(cv2.CAP_PROP_FPS);check.release()
    if frames!=metadata['frames'] or abs(fps-metadata['fps'])>.001:raise RuntimeError('Аудиомикс изменил число кадров или FPS')
    (folder/'video.mp4').rename(folder/'video-silent.mp4');target.rename(folder/'video.mp4')
    report={'enabled':True,'mode':'timed-multitrack','tracks':reports,'voice_map':timeline['voice_map'],'seconds':time.perf_counter()-began,'duration_seconds':duration,'source_audio_format':'MP3 stereo','mp4_audio_codec':'AAC192k','video_stream':'copied without re-encoding','lip_sync':False,'visual_event_alignment':'client/helper-provided timestamps, not automatic lip synchronization'}
    (stems/'timeline.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');return report

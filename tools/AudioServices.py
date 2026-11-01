"""Configured OpenAI-compatible helper/TTS/STT; URLs never come from generation requests."""
import functools,json,urllib.request,urllib.error,urllib.parse,math,re,threading,socket

def _bounded_read(response,limit,timeout):
    expired=threading.Event()
    def cancel():
        expired.set()
        sock=getattr(getattr(getattr(response,'fp',None),'raw',None),'_sock',None)
        if sock is not None:
            try:sock.shutdown(socket.SHUT_RDWR)
            except OSError:pass
    timer=threading.Timer(timeout,cancel);timer.daemon=True;timer.start()
    try:
        body=response.read(limit+1)
        if expired.is_set():raise TimeoutError('Audio provider response deadline exceeded')
        if len(body)>limit:raise ValueError('Audio provider response exceeds size limit')
        return body
    finally:timer.cancel()

def normalize(config):
    if not isinstance(config,dict):raise ValueError('Настройки аудиосервера должны быть объектом')
    allowed={'base_url','helper_model','helper_enabled','tts_enabled','stt_enabled','female_voice','secondary_female_voice','male_voice','english_female_voice','english_male_voice','voice_selection_verified','sfx_model_dir','sfx_threads'}
    if set(config)-allowed:raise ValueError('Неизвестные настройки подключения аудио')
    result={'base_url':'','helper_model':'','helper_enabled':False,'tts_enabled':False,'stt_enabled':False,'female_voice':'shimmer','secondary_female_voice':'sage','male_voice':'echo','english_female_voice':'shimmer','english_male_voice':'Ryan','voice_selection_verified':False,'sfx_model_dir':'MODELS/audio/sfx','sfx_threads':20,**config}
    base=result['base_url'].strip().rstrip('/')
    if base:
        u=urllib.parse.urlsplit(base)
        if u.scheme not in ('http','https') or not u.netloc or u.username or u.password or u.query or u.fragment or u.path not in ('','/v1'):raise ValueError('API URL: http(s)://сервер:порт/v1, без пароля и параметров')
        result['base_url']=base if u.path=='/v1' else base+'/v1'
    for key in ('helper_enabled','tts_enabled','stt_enabled','voice_selection_verified'):
        if type(result[key]) is not bool:raise ValueError('Ожидается переключатель '+key)
    for key in ('helper_model','female_voice','secondary_female_voice','male_voice','english_female_voice','english_male_voice'):
        if not isinstance(result[key],str) or len(result[key])>256:raise ValueError('Неверное значение '+key)
    if not isinstance(result['sfx_model_dir'],str) or type(result['sfx_threads']) is not int or not 1<=result['sfx_threads']<=36:raise ValueError('Укажите папку SFX и1..36 потоков CPU')
    if any(result[k] for k in ('helper_enabled','tts_enabled','stt_enabled')) and not base:raise ValueError('Укажите API URL аудиосервера')
    return result

def services(cfg):return normalize(cfg.get('proxy',{}).get('audio_services',{}))

def remote(cfg,path,body=None,content_type='application/json',timeout=180):
    opts=services(cfg);base=opts['base_url']
    if not base:raise ValueError('Внешний аудиосервер не подключён')
    if path.startswith('/v1/'):url=base+path[3:]
    elif path.startswith('/api/extra/'):
        parsed=urllib.parse.urlsplit(base);url=urllib.parse.urlunsplit((parsed.scheme,parsed.netloc,path,'',''))
    else:raise ValueError('Неподдерживаемый маршрут аудиосервера')
    req=urllib.request.Request(url,body,{'Content-Type':content_type,'Accept-Encoding':'identity'},method='POST' if body is not None else 'GET')
    try:
        with urllib.request.urlopen(req,timeout=timeout) as r:return r.status,dict(r.headers),_bounded_read(r,64*1024**2,timeout)
    except urllib.error.HTTPError as e:
        with e:return e.code,dict(e.headers),_bounded_read(e,256*1024,timeout)

def capabilities(cfg):
    opts=services(cfg)
    from pathlib import Path
    root=Path(__file__).resolve().parent.parent;models=Path(opts['sfx_model_dir']);models=models if models.is_absolute() else root/models
    names=['stable-audio-3-small-sfx-dit-0.5B-v1.0-Q8_0.gguf','stable-audio-3-small-sfx-same-s-v1.0-Q8_0.gguf','stable-audio-3-small-sfx-conditioner-v1.0-F32.gguf','t5gemma-b-b-ul2-encoder-0.3B-v1.0-F16.gguf','t5gemma-b-b-ul2-v1.0-vocab.gguf']
    sfx=(root/'runtime/sa3/sa3-generate.exe').is_file() and models.is_dir() and all((models/n).is_file() for n in names)
    return {'helper':opts['helper_enabled'],'tts':opts['tts_enabled'],'stt':opts['stt_enabled'],'sfx':sfx,'sfx_endpoint':'/v1/audio/sfx','sfx_max_seconds':60,'sfx_backend':'CPU Haswell','voice_selection_verified':opts['voice_selection_verified'],'helper_model':opts['helper_model'],'speaker_profiles':['female','male'],'languages':['ru','en'],'voices':{lang:[{'id':voice,'voice_profile':profile} for profile,voices in profiles.items() for voice in sorted(voices)] for lang,profiles in voice_registry(opts).items()},'url_configured':bool(opts['base_url'])}

def select_voice(opts,speaker):
    profile=speaker.get('voice_profile')
    if profile not in ('female','male'):raise ValueError('Укажите voice_profile female/male для каждого говорящего персонажа; сервер не угадывает его по лицу')
    if not opts['voice_selection_verified']:raise ValueError('Переключение голосов внешнего TTS ещё не подтверждено; речь не подменяется случайным голосом')
    language=speaker.get('language','ru')
    if not isinstance(language,str):raise ValueError('language должен быть строкой ru/en')
    language=language.lower().split('-')[0]
    if language not in ('ru','en'):raise ValueError('Для автоматического выбора голоса поддержаны ru/en; язык задаётся в API, отдельно от GUI')
    if 'voice' in speaker:
        voices=voice_registry(opts)
        if speaker['voice'] not in voices[language][profile]:raise ValueError('Голос не соответствует явному профилю и языку персонажа')
        return speaker['voice']
    key=('english_' if language=='en' else '')+('female_voice' if profile=='female' else 'male_voice')
    return opts[key]

def voice_registry(opts):
    return {'ru':{'female':{opts['female_voice'],opts.get('secondary_female_voice','sage')},'male':{opts['male_voice']}},'en':{'female':{opts['english_female_voice']},'male':{opts['english_male_voice']}}}

@functools.lru_cache(maxsize=32)
def _plan(base,model,scene,seconds,speakers_json):
    speakers=json.loads(speakers_json)
    prompt={'scene':scene,'duration_seconds':seconds,'speakers':speakers}
    payload={'model':model,'temperature':.1,'max_tokens':1800,'response_format':{'type':'json_object'},'messages':[{'role':'system','content':'Create a concise realistic audio timeline as JSON {"tracks":[...]}. Track fields: kind (sfx/music/speech), prompt (sound description) or text (speech), start, end in seconds, volume0..1, speaker_id for speech. Maximum6 tracks. Return an empty tracks array for a quiet scene without requested/confirmed audio. Do not invent constant wind/hiss/cloth noise. Use only given speaker IDs and explicit voice profiles. Never infer gender/identity from an image. Match timing to the supplied duration. No lip-sync guarantee. Describe environmental sounds in English; preserve spoken text language. Do not add music unless requested.'},{'role':'user','content':json.dumps(prompt,ensure_ascii=False)}]}
    variants=[]
    for kind in ('music','sfx',*(['speech'] if speakers else [])):
        properties={'kind':{'type':'string','enum':[kind]},'start':{'type':'number','minimum':0,'maximum':seconds},'end':{'type':'number','minimum':0,'maximum':seconds},'volume':{'type':'number','minimum':0,'maximum':1},'text' if kind=='speech' else 'prompt':{'type':'string','minLength':1,'maxLength':2000}}
        if kind=='speech':properties.update(speaker_id={'type':'string','enum':[s['id'] for s in speakers]},language={'type':'string','enum':['ru','en']})
        variants.append({'type':'object','additionalProperties':False,'required':list(properties),'properties':properties})
    schema={'type':'object','required':['tracks'],'additionalProperties':False,'properties':{'tracks':{'type':'array','maxItems':8,'items':{'anyOf':variants}}}}
    payload['response_format']={'type':'json_schema','json_schema':{'name':'audio_timeline','strict':True,'schema':schema}}
    req=urllib.request.Request(base+'/chat/completions',json.dumps(payload).encode('utf-8'),{'Content-Type':'application/json'})
    # One bounded repair only. Invalid plans never reach an audio renderer.
    failure='';content=''
    for attempt in range(2):
        if attempt:
            payload['messages'] += [{'role':'assistant','content':content[:12000]},
                {'role':'user','content':'Repair this JSON only, no reasoning or markdown. Required root: {"tracks":[...]}. Error: '+failure}]
        req=urllib.request.Request(base+'/chat/completions',json.dumps(payload).encode('utf-8'),{'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req,timeout=60) as r:result=json.loads(_bounded_read(r,256*1024,60))
        except urllib.error.HTTPError as error:
            if attempt==0 and error.code in (400,422):
                error.close();payload['response_format']={'type':'json_object'};failure='Provider rejected JSON Schema; use strict JSON object';continue
            raise
        content=result.get('choices',[{}])[0].get('message',{}).get('content','')
        try:return _validate_plan(content,seconds,{s['id'] for s in speakers})
        except (ValueError,TypeError,KeyError) as error:failure=str(error)
    raise ValueError('Хелпер не вернул допустимый tracks после одной коррекции: '+failure)

def _validate_plan(content,seconds,speaker_ids):
    if not isinstance(content,str) or len(content)>24000:raise ValueError('Invalid helper response length')
    content=re.sub(r'<think>.*?</think>','',content,flags=re.S).strip()
    if content.startswith('```') and content.endswith('```'):
        content=content.split('\n',1)[-1].rsplit('```',1)[0].strip()
    answer=json.loads(content)
    if not isinstance(answer,dict) or set(answer)!={'tracks'} or not isinstance(answer['tracks'],list) or not 0<=len(answer['tracks'])<=8:raise ValueError('Required tracks array with0..8 items')
    for track in answer['tracks']:
        if not isinstance(track,dict) or set(track)-{'kind','prompt','text','start','end','volume','speaker_id','language','seed','fit'}:raise ValueError('Unknown track fields')
        if track.get('kind') not in ('music','sfx','speech'):raise ValueError('Invalid kind')
        a,b,v=track.get('start'),track.get('end'),track.get('volume',.7)
        if any(type(n) not in (int,float) or not math.isfinite(n) for n in (a,b,v)) or not 0<=a<b<=seconds or not 0<=v<=1:raise ValueError('Invalid start/end/volume')
        speech=track['kind']=='speech'
        if speech and 'text' not in track and isinstance(track.get('prompt'),str):track['text']=track.pop('prompt')
        text=track.get('text' if speech else 'prompt')
        if not isinstance(text,str) or not text.strip() or len(text)>2000:raise ValueError('Missing text/prompt')
        if speech and track.get('speaker_id') not in speaker_ids:raise ValueError('Unknown speaker_id')
        if 'language' in track and track['language'] not in ('ru','en'):raise ValueError('language must be ru/en')
        if 'fit' in track and track['fit'] not in ('natural','stretch'):raise ValueError('Invalid fit')
        if 'seed' in track and (type(track['seed']) is not int or not 0<=track['seed']<2**31):raise ValueError('Invalid seed')
    return answer

def plan(cfg,scene,seconds,speakers):
    opts=services(cfg)
    if not opts['helper_enabled'] or not opts['helper_model']:raise ValueError('Хелпер не настроен в Audio')
    if not isinstance(scene,str) or not scene.strip() or len(scene)>6000 or type(seconds) not in (int,float) or not math.isfinite(seconds) or not 0<seconds<=360:raise ValueError('Неверное описание или длительность плана')
    if not isinstance(speakers,list) or len(speakers)>8:raise ValueError('Допустимы до8 персонажей')
    ids=set()
    for speaker in speakers:
        if not isinstance(speaker,dict) or not isinstance(speaker.get('id'),str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',speaker['id']) or speaker['id'] in ids or speaker.get('voice_profile') not in ('female','male') or speaker.get('language','ru') not in ('ru','en'):raise ValueError('Для персонажа нужны уникальный id,voice_profile female/male,language ru/en')
        ids.add(speaker['id'])
    return _plan(opts['base_url'],opts['helper_model'],scene,float(seconds),json.dumps(speakers,sort_keys=True))

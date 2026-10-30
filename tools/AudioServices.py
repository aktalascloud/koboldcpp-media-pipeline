"""Configured OpenAI-compatible helper/TTS/STT; URLs never come from generation requests."""
import functools,json,urllib.request,urllib.error,urllib.parse,math

def normalize(config):
    if not isinstance(config,dict):raise ValueError('Настройки аудиосервера должны быть объектом')
    allowed={'base_url','helper_model','helper_enabled','tts_enabled','stt_enabled','female_voice','male_voice','english_female_voice','english_male_voice','voice_selection_verified','sfx_model_dir','sfx_threads'}
    if set(config)-allowed:raise ValueError('Неизвестные настройки подключения аудио')
    result={'base_url':'','helper_model':'','helper_enabled':False,'tts_enabled':False,'stt_enabled':False,'female_voice':'shimmer','male_voice':'echo','english_female_voice':'shimmer','english_male_voice':'Ryan','voice_selection_verified':False,'sfx_model_dir':'MODELS/audio/sfx','sfx_threads':20,**config}
    base=result['base_url'].strip().rstrip('/')
    if base:
        u=urllib.parse.urlsplit(base)
        if u.scheme not in ('http','https') or not u.netloc or u.username or u.password or u.query or u.fragment or u.path not in ('','/v1'):raise ValueError('API URL: http(s)://сервер:порт/v1, без пароля и параметров')
        result['base_url']=base if u.path=='/v1' else base+'/v1'
    for key in ('helper_enabled','tts_enabled','stt_enabled','voice_selection_verified'):
        if type(result[key]) is not bool:raise ValueError('Ожидается переключатель '+key)
    for key in ('helper_model','female_voice','male_voice','english_female_voice','english_male_voice'):
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
        with urllib.request.urlopen(req,timeout=timeout) as r:return r.status,dict(r.headers),r.read()
    except urllib.error.HTTPError as e:return e.code,dict(e.headers),e.read()

def capabilities(cfg):
    opts=services(cfg)
    from pathlib import Path
    root=Path(__file__).resolve().parent.parent;models=Path(opts['sfx_model_dir']);models=models if models.is_absolute() else root/models
    names=['stable-audio-3-small-sfx-dit-0.5B-v1.0-Q8_0.gguf','stable-audio-3-small-sfx-same-s-v1.0-Q8_0.gguf','stable-audio-3-small-sfx-conditioner-v1.0-F32.gguf','t5gemma-b-b-ul2-encoder-0.3B-v1.0-F16.gguf','t5gemma-b-b-ul2-v1.0-vocab.gguf']
    sfx=(root/'runtime/sa3/sa3-generate.exe').is_file() and models.is_dir() and all((models/n).is_file() for n in names)
    return {'helper':opts['helper_enabled'],'tts':opts['tts_enabled'],'stt':opts['stt_enabled'],'sfx':sfx,'sfx_backend':'CPU Haswell','voice_selection_verified':opts['voice_selection_verified'],'helper_model':opts['helper_model'],'speaker_profiles':['female','male'],'languages':['ru','en'],'url_configured':bool(opts['base_url'])}

def select_voice(opts,speaker):
    profile=speaker.get('voice_profile')
    if profile not in ('female','male'):raise ValueError('Укажите voice_profile female/male для каждого говорящего персонажа; сервер не угадывает его по лицу')
    if not opts['voice_selection_verified']:raise ValueError('Переключение голосов внешнего TTS ещё не подтверждено; речь не подменяется случайным голосом')
    language=speaker.get('language','ru')
    if not isinstance(language,str):raise ValueError('language должен быть строкой ru/en')
    language=language.lower().split('-')[0]
    if language not in ('ru','en'):raise ValueError('Для автоматического выбора голоса поддержаны ru/en; язык задаётся в API, отдельно от GUI')
    key=('english_' if language=='en' else '')+('female_voice' if profile=='female' else 'male_voice')
    return opts[key]

@functools.lru_cache(maxsize=32)
def _plan(base,model,scene,seconds,speakers_json):
    speakers=json.loads(speakers_json)
    prompt={'scene':scene,'duration_seconds':seconds,'speakers':speakers}
    payload={'model':model,'temperature':.1,'max_tokens':1800,'response_format':{'type':'json_object'},'messages':[{'role':'system','content':'Create a concise realistic audio timeline as JSON {"tracks":[...]}. Track fields: kind (sfx/music/speech), prompt (sound description) or text (speech), start, end in seconds, volume0..1, speaker_id for speech. Maximum6 tracks. Use only given speaker IDs and explicit voice profiles. Never infer gender/identity from an image. Match timing to the supplied duration. No lip-sync guarantee. Describe environmental sounds in English; preserve spoken text language. Do not add music unless requested.'},{'role':'user','content':json.dumps(prompt,ensure_ascii=False)}]}
    req=urllib.request.Request(base+'/chat/completions',json.dumps(payload).encode('utf-8'),{'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=120) as r:result=json.load(r)
    answer=json.loads(result['choices'][0]['message']['content'])
    if not isinstance(answer,dict) or not isinstance(answer.get('tracks'),list):raise ValueError('Хелпер не вернул tracks')
    for track in answer['tracks']:
        if isinstance(track,dict) and track.get('kind')=='speech' and 'text' not in track and isinstance(track.get('prompt'),str):
            track['text']=track.pop('prompt')
    return answer

def plan(cfg,scene,seconds,speakers):
    opts=services(cfg)
    if not opts['helper_enabled'] or not opts['helper_model']:raise ValueError('Хелпер не настроен в Audio')
    if not isinstance(scene,str) or not scene.strip() or len(scene)>6000 or type(seconds) not in (int,float) or not math.isfinite(seconds) or not 0<seconds<=360:raise ValueError('Неверное описание или длительность плана')
    if not isinstance(speakers,list) or len(speakers)>8:raise ValueError('Допустимы до8 персонажей')
    return _plan(opts['base_url'],opts['helper_model'],scene,float(seconds),json.dumps(speakers,sort_keys=True))

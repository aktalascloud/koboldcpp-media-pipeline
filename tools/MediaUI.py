"""Offline media workbench and OpenAPI registry. No inference or process launch on import."""
import json
import re

from MusicContract import MAX_MUSIC_SECONDS, MAX_SEMANTIC_TOKENS

ROUTES = {
    'image': '/sdapi/v1/txt2img', 'music': '/api/extra/music/generate',
    'video': '/v1/videos/generations',
}

def dispatch(payload, upscale=False):
    if not isinstance(payload, dict) or set(payload)-{'type','parameters'}:
        raise ValueError('Expected type and parameters only')
    kind = payload.get('type')
    routes = {'image':'/sdapi/v1/extra-single-image','video':'/v1/videos/upscale'} if upscale else ROUTES
    if kind not in routes or not isinstance(payload.get('parameters'),dict):
        raise ValueError('Unsupported media type or missing parameters object')
    return routes[kind], payload['parameters']

def native_schema(html):
    """Decode the bundled Swagger object as data, without executing its script."""
    text = html.decode('utf-8-sig')
    marker = re.search(r'(?m)^[ \t]*(?:const|let|var) spec\s*=\s*', text)
    if marker is None:
        raise ValueError('Native API catalog not found')
    body = text[marker.end():text.index('</script>', marker.end())].strip().removesuffix(';')
    # Native emits trailing commas in an otherwise JSON object. Keep quoted strings intact.
    body = re.sub(r'"(?:[^"\\]|\\.)*"|,(?=\s*[\]}])', lambda m: '' if m[0] == ',' else m[0], body)
    spec = json.loads(body)
    if not isinstance(spec, dict) or spec.get('openapi') != '3.0.3' or not isinstance(spec.get('paths'), dict):
        raise ValueError('Unsupported Native API catalog')
    return spec


def schema(native=None):
    paths={}
    descriptions={
        '/v1/media/generations':('post','Unified image, music or video generation. type selects the task; parameters follow its specific contract.'),
        '/v1/media/upscale':('post','Unified image/video postprocessing. Video requires video_id and optional enhance_faces only.'),
        '/v1/media/capabilities':('get','Discover all media operations and automatic model switching.'),
        '/v1/media/audio-plan':('post','Создать план аудиодорожек с таймкодами выбранным хелпером.'),
        '/v1/audio/speech':('post','Речь через настроенный TTS. Язык и голос задаются в API.'),
        '/v1/audio/sfx':('post','Генерация звуковых эффектов SA3 CPU,0.25–60секунд; ответ WAV либо MP3, фото-модель остаётся вGPU.'),
        '/v1/audio/sfx/capabilities':('get','Доступность SFX, пределы длительности и форматы.'),
        '/v1/audio/transcriptions':('post','Распознавание аудио через настроенный STT.'),
        '/v1/audio/voices':('get','Список голосов подключённого сервера.'),
        '/v1/audio/capabilities':('get','Подключения хелпера/TTS/STT и проверка голосов.'),

        '/v1/media/settings':('get','Effective public settings; no credentials or private paths.'),
        '/sdapi/v1/txt2img':('post','Generate an image; faces/Gater, optional ClearReality4x.'),
        '/sdapi/v1/img2img':('post','Whole-frame redraw of one target. Not instruction editing or multiple references.'),
        '/sdapi/v1/extra-single-image':('post','Faces/Gater before ClearReality4x; preserve trusted processing markers.'),
        '/v1/images/generations':('post','OpenAI-compatible image generation.'),
        '/v1/images/edits':('post','Explicit operation=img2img; unsupported masks/references return422.'),
        '/v1/images/synthesize':('post','Text analyses supplied by a client vision model, not native image-reference conditioning.'),
        '/v1/images/capabilities':('get','Image operation contract.'),
        '/v1/images/synthesis-schema':('get','Contract for client-side visual analysis and text reference synthesis.'),
        '/api/extra/music/generate':('post','YuE2 MP3, caller-provided lyrics/style.'),
        '/api/extra/music/prepare':('post','Prepare the configured music model for the API.'),
        '/v1/music/capabilities':('get','YuE2 music contract.'),
        '/v1/videos/generations':('post','Wan480p/Pro, optional720p faces/RIFE; timed music, SFX and speech mixed into MP4. No lip-sync.'),
        '/v1/videos/upscale':('post','Postprocess a stored generated video.'),
        '/v1/videos/import':('post','Import a client-owned MP4, up to30seconds/2MP; binary video/mp4 body.'),
        '/v1/videos/interpolate':('post','RIFE48/60FPS for an owned imported/generated24FPS clip up to30seconds/2MP, without another Wan render.'),
        '/v1/videos/lipsync':('post','Postprocess a stored video with explicit speech and target_box; optional non-commercial Wav2Lip runtime required.'),
        '/v1/videos/jobs/{request_id}':('get','Persistent generation receipt; survives client disconnect and marks interrupted jobs unknown.'),
        '/v1/videos/jobs/{request_id}/cancel':('post','Cancel a queued request only; never globally abort Native.'),
        '/v1/videos/soundtrack':('post','Replace audio on a new copy of a completed video using reviewed event timestamps, without regenerating its frames.'),
        '/v1/videos/capabilities':('get','Frames, cache, optional RIFE and audio limits.'),
        '/api/extra/video/media/{video_id}/{asset}':('get','Download a stored video, audio track or frame. Byte ranges are supported.'),
        '/sdapi/v1/detail':('post','Run the configured photo detailer.'),
        '/sdapi/v1/upscalers':('get','Configured public image upscaler.'),
        '/sdapi/v1/progress':('get','Image progress, including facade postprocessing.'),
        '/api/extra/version':('get','Native version and media capability flags for this entry point.'),
        '/health':('get','Live service and queue state.'),
    }
    for route,(method,description) in descriptions.items():
        op={'summary':description,'responses':{'200':{'description':'Successful result; MP3 for music, JSON/MP4 URL for video.'},'422':{'description':'Unsupported operation or invalid parameters.'},'503':{'description':'Backend unavailable.'}}}
        if method=='post':op['requestBody']={'required':True,'content':{'application/json':{'schema':{'type':'object'}}}}
        paths[route]={method:op,'x-kobold-scope':'media'}
    paths['/v1/media/settings']['post']={'summary':'Save bounded settings from the local machine while idle; requires current revision and X-Kobold-Config:1.','parameters':[{'name':'X-Kobold-Config','in':'header','required':True,'schema':{'type':'string','enum':['1']}}],'requestBody':{'required':True,'content':{'application/json':{'schema':{'type':'object','required':['revision']}}}},'responses':{'200':{'description':'Saved without restarting the resident model'},'403':{'description':'Not local/same-origin'},'409':{'description':'Generation active'},'422':{'description':'Invalid setting or stale revision'}}}
    track={'type':'object','required':['kind','start','end'],'additionalProperties':False,'properties':{'kind':{'type':'string','enum':['music','sfx','speech']},'start':{'type':'number','minimum':0},'end':{'type':'number','minimum':0},'volume':{'type':'number','minimum':0,'maximum':1},'prompt':{'type':'string'},'text':{'type':'string'},'speaker_id':{'type':'string'},'language':{'type':'string','enum':['ru','en']},'fit':{'type':'string','enum':['natural','stretch']},'seed':{'type':'integer','minimum':0,'maximum':2147483647},'speech_video_id':{'type':'string','pattern':'^[0-9a-f]{32}$'}}}
    audio={'type':'object','properties':{'enabled':{'type':'boolean'},'auto_plan':{'type':'boolean'},'prompt':{'type':'string'},'language':{'type':'string','enum':['ru','en']},'speakers':{'type':'array','maxItems':8,'items':{'type':'object','required':['id','voice_profile'],'properties':{'id':{'type':'string'},'voice_profile':{'type':'string','enum':['female','male']},'language':{'type':'string','enum':['ru','en']},'voice':{'type':'string','minLength':1,'maxLength':256}}}},'tracks':{'type':'array','minItems':0,'maxItems':8,'items':track}}}
    paths['/v1/videos/generations']['post']['requestBody']['content']['application/json']['schema']={'type':'object','required':['prompt'],'properties':{'prompt':{'type':'string'},'frames':{'type':'integer','minimum':5,'maximum':121,'description':'4n+1 frames at24FPS'},'resolution':{'type':'string','enum':['480p']},'orientation':{'type':'string','enum':['portrait','landscape']},'deadline_seconds':{'type':'number','exclusiveMinimum':True,'minimum':0,'maximum':900},'audio':audio}}
    generation=paths['/v1/videos/generations']['post']
    generation['parameters']=[{'name':'Idempotency-Key','in':'header','schema':{'type':'string','pattern':'^[A-Za-z0-9_.:-]{8,128}$'}}]
    generation['responses'].update({'202':{'description':'Existing queued/running/unknown request; poll status URL, do not retry with a new key'},'409':{'description':'Same idempotency key with a different payload'},'504':{'description':'Request deadline exceeded; receipt retained'}})
    generation['requestBody']['content']['application/json']['schema']['properties']['interpolate_fps']={'type':'integer','enum':[24,48,60],'default':48}
    for route in ('/v1/videos/jobs/{request_id}','/v1/videos/jobs/{request_id}/cancel'):
        operation=paths[route]['get' if route.endswith('{request_id}') else 'post']
        operation['parameters']=[{'name':'request_id','in':'path','required':True,'schema':{'type':'string','pattern':'^[0-9a-f]{32}$'}}]
    paths['/v1/videos/import']['post']['requestBody']={'required':True,'content':{'video/mp4':{'schema':{'type':'string','format':'binary'}}}}
    paths['/v1/videos/interpolate']['post']['requestBody']['content']['application/json']['schema']={'type':'object','additionalProperties':False,'required':['video_id'],'properties':{'video_id':{'type':'string','pattern':'^[0-9a-f]{32}$'},'fps':{'type':'integer','enum':[48,60],'default':48}}}
    paths['/v1/videos/lipsync']['post']['requestBody']['content']['application/json']['schema']={'type':'object','additionalProperties':False,'required':['video_id','speech','mode'],'properties':{'video_id':{'type':'string','pattern':'^[0-9a-f]{32}$'},'mode':{'type':'string','enum':['voiceover','onscreen']},'target_box':{'type':'array','minItems':4,'maxItems':4,'items':{'type':'number','minimum':0,'maximum':1}},'speech':{'type':'object','required':['text','voice','language'],'additionalProperties':False,'properties':{'text':{'type':'string','minLength':1,'maxLength':1500},'voice':{'type':'string','minLength':1,'maxLength':256},'language':{'type':'string','enum':['ru','en']},'start':{'type':'number','minimum':0,'maximum':30},'voice_profile':{'type':'string','enum':['female','male']},'speaker_id':{'type':'string','maxLength':64}}}}}
    paths['/v1/videos/soundtrack']['post']['requestBody']['content']['application/json']['schema']={'type':'object','required':['video_id','audio'],'additionalProperties':False,'properties':{'video_id':{'type':'string','pattern':'^[0-9a-f]{32}$'},'audio':audio}}
    paths['/v1/audio/sfx']['post']['requestBody']['content']['application/json']['schema']={'type':'object','required':['prompt'],'additionalProperties':False,'properties':{'prompt':{'type':'string','minLength':1,'maxLength':2000},'duration':{'type':'number','minimum':.25,'maximum':60,'default':5},'seed':{'type':'integer','minimum':0,'maximum':2147483647},'response_format':{'type':'string','enum':['wav','mp3'],'default':'wav'}}}
    paths['/v1/audio/sfx']['post']['responses']['200']={'description':'Binary generated sound, not JSON','content':{'audio/wav':{'schema':{'type':'string','format':'binary'}},'audio/mpeg':{'schema':{'type':'string','format':'binary'}}}}
    paths['/v1/audio/transcriptions']['post']['requestBody']={'required':True,'content':{'multipart/form-data':{'schema':{
        'type':'object','required':['file'],'properties':{'file':{'type':'string','format':'binary'},'model':{'type':'string'},'language':{'type':'string'}}}}}}
    paths['/v1/images/edits']['post']['requestBody']['content']['multipart/form-data']={'schema':{'type':'object',
        'required':['image','operation','prompt'],'properties':{'image':{'type':'string','format':'binary'},'operation':{'type':'string','enum':['img2img']},'prompt':{'type':'string'}}}}
    paths['/v1/videos/jobs/{request_id}/cancel']['post'].pop('requestBody')
    download=paths['/api/extra/video/media/{video_id}/{asset}']['get']
    download['parameters']=[{'name':'video_id','in':'path','required':True,'schema':{'type':'string','pattern':'^[0-9a-f]{32}$'}},
        {'name':'asset','in':'path','required':True,'schema':{'type':'string','enum':['video.mp4','video-native480.mp4','video-24fps.mp4','audio.mp3','speech.wav','last-frame.png','native-last-frame.png']}},
        {'name':'Range','in':'header','schema':{'type':'string'}}]
    content={kind:{'schema':{'type':'string','format':'binary'}} for kind in ('video/mp4','audio/mpeg','audio/wav','image/png')}
    download['responses']={'200':{'description':'Stored asset','content':content},'206':{'description':'Partial asset','content':content},
        '404':{'description':'Asset unavailable'},'413':{'description':'Asset too large'},'416':{'description':'Invalid byte range'}}
    paths['/api/extra/music/generate']['post']['responses']['200']={'description':'YuE2 MP3','content':{'audio/mpeg':{'schema':{'type':'string','format':'binary'}}}}
    paths['/api/extra/music/generate']['post']['requestBody']['content']['application/json']['schema']={'type':'object',
        'properties':{'style':{'type':'string','minLength':1},'caption':{'type':'string','minLength':1},'lyrics':{'type':'string'},
        'duration':{'type':'number','minimum':1,'maximum':MAX_MUSIC_SECONDS},'semantic_max_tokens':{'type':'integer','minimum':1,'maximum':MAX_SEMANTIC_TOKENS}},
        'anyOf':[{'required':['style']},{'required':['caption']}]}
    paths['/v1/media/audio-plan']['post']['requestBody']['content']['application/json']['schema']={'type':'object',
        'additionalProperties':False,'required':['prompt','duration_seconds'],'properties':{'prompt':{'type':'string'},
        'duration_seconds':{'type':'number','exclusiveMinimum':True,'minimum':0,'maximum':360},'speakers':audio['properties']['speakers']}}
    paths['/v1/videos/upscale']['post']['requestBody']['content']['application/json']['schema']={'type':'object',
        'additionalProperties':False,'required':['video_id'],'properties':{
        'video_id':{'type':'string','pattern':'^[0-9a-f]{32}$'},'enhance_faces':{'type':'boolean'}}}
    aliases={
        '/images/generations':'/v1/images/generations','/images/edits':'/v1/images/edits','/images/synthesize':'/v1/images/synthesize',
        '/images/synthesis-schema':'/v1/images/synthesis-schema','/api/extra/image-capabilities':'/v1/images/capabilities',
        '/sdapi/v1/upscale':'/sdapi/v1/extra-single-image','/api/extra/tts':'/v1/audio/speech','/api/extra/transcribe':'/v1/audio/transcriptions',
        '/api/extra/music/capabilities':'/v1/music/capabilities','/api/extra/video/capabilities':'/v1/videos/capabilities',
        '/api/extra/video/generate':'/v1/videos/generations','/api/extra/video/upscale':'/v1/videos/upscale',
    }
    for alias,target in aliases.items():
        paths[alias]={'$ref':'#/paths/'+target.replace('/','~1'),'x-kobold-scope':'media'}
    for route,dispatches in (
        ('/v1/media/generations',ROUTES),
        ('/v1/media/upscale',{'image':'/sdapi/v1/extra-single-image','video':'/v1/videos/upscale'}),
    ):
        op=paths[route]['post']
        op['requestBody']['content']['application/json']['schema']={'type':'object','required':['type','parameters'],
            'additionalProperties':False,'properties':{'type':{'type':'string','enum':list(dispatches)},'parameters':{'type':'object'}},
            'oneOf':[{'properties':{'type':{'enum':[kind]},'parameters':{
                '$ref':'#/paths/'+target.replace('/','~1')+'/post/requestBody/content/application~1json/schema'}}}
                for kind,target in dispatches.items()]}
    spec={'openapi':'3.0.3','info':{'title':'KoboldCpp unified media API','version':'1.3'},
          'servers':[{'url':'/'}],'paths':paths}
    if native is not None:
        compatibility={path:{**item,'x-kobold-scope':'native'} for path,item in native['paths'].items()
                       if not path.startswith('/api/admin/') and path != '/api/extra/shutdown'}
        # An upstream alias outside the facade may still reach Native directly.
        for path,item in list(compatibility.items()):
            ref=item.get('$ref','')
            if ref.startswith('#/paths/'):
                target=ref[8:].replace('~1','/').replace('~0','~')
                if target in paths:
                    compatibility[path]={**native['paths'][target],'x-kobold-scope':'native'}
        # These client routes are implemented by Native outside its bundled catalog.
        extra={
            '/sdapi/v1/interrupt':('post','Interrupt the image request that owns the supplied genkey.'),
            '/sdapi/v1/recovery-status':('get','Read running, complete or unknown status for a genkey.'),
            '/api/version':('get','Ollama compatibility version.'),
            '/api/show':('post','Ollama compatibility model information.'),
            '/api/embed':('post','Ollama-compatible embeddings when enabled.'),
            '/sdcpp/v1/capabilities':('get','Native SDCPP compatibility capability flags.'),
            '/sdcpp/v1/model-files':('get','Native SDCPP list of available model descriptors.'),
            '/sdcpp/v1/recipes':('get','Native SDCPP compatibility recipes.'),
            '/sdcpp/v1/models':('get','Native SDCPP compatibility model list.'),
            '/sdcpp/v1/models/status':('get','Native SDCPP loaded model state.'),
            '/sdcpp/v1/jobs/{job_id}':('get','Read a Native SDCPP request record.'),
            '/sdcpp/v1/jobs/{job_id}/cancel':('post','Cancel a Native SDCPP request.'),
            '/sdcpp/v1/img_gen':('post','Native SDCPP image generation without Media postprocessing.'),
            '/system_stats':('get','ComfyUI compatibility metadata; values are placeholders.'),
            '/object_info':('get','Limited ComfyUI compatibility node descriptions.'),
            '/prompt':('post','Run the subset of ComfyUI image workflows accepted by Native.'),
            '/history':('get','ComfyUI compatibility record for the last image request.'),
            '/view':('get','PNG from the last ComfyUI-compatible image request.'),
            '/voice/check':('get','Legacy VITS voice capability metadata.'),
            '/voice/speakers':('get','Legacy VITS speakers metadata.'),
            '/voice/vits':('get','Legacy VITS query-text to WAV when enabled.'),
            '/speakers':('get','Legacy XTTS speakers metadata.'),
            '/get_tts_settings':('get','Legacy XTTS compatibility settings.'),
            '/tts_to_audio':('post','Legacy XTTS text-to-audio when enabled.'),
        }
        for path,(method,summary) in extra.items():
            operation={'summary':summary,'responses':{'200':{'description':'Native compatibility response'}}}
            if '{job_id}' in path:
                operation['parameters']=[{'name':'job_id','in':'path','required':True,'schema':{'type':'string'}}]
            compatibility.setdefault(path,{method:operation,'x-kobold-scope':'native'})
        compatibility['/sdapi/v1/recovery-status']['get']['parameters']=[{'name':'genkey','in':'query','schema':{'type':'string'}}]
        compatibility['/sdapi/v1/interrupt']['post']['requestBody']={'required':True,'content':{'application/json':{'schema':{
            'type':'object','required':['genkey'],'properties':{'genkey':{'type':'string','minLength':1}}}}}}
        spec['paths']={**compatibility,**paths}
        spec['components']=native.get('components',{})
        spec['tags']=native.get('tags',[])
        spec['info']['description']='Media operations and Native compatibility routes. Native capabilities depend on the loaded model and configuration. Administrative and shutdown routes are outside this client catalog.'
    return spec

def public_settings(cfg):
    proxy=cfg['proxy'];defaults=cfg['defaults'];video=proxy.get('video',{})
    return {'image':{k:defaults.get(k) for k in ('width','height','steps','cfg_scale','sampler_name','scheduler','eta','flow_shift','cache_mode','cache_options')},
        'modes':proxy.get('image_modes',{}),
        'faces':{k:proxy.get('detailer',{}).get(k) for k in ('enabled','visibility','minimum_feature_similarity','detector_resolution','max_faces')},
        'gater':proxy.get('photo_restoration',{}).get('enabled',False),
        'upscaler':{'name':proxy['upscaler'].get('name'),'scale':proxy['upscaler'].get('output_scale')},
        'video':{k:video.get(k) for k in ('enabled','scheduler','default_cache_mode','default_cache_options','default_frames','default_audio','default_interpolate_fps','vae_tiling_threshold','conv_workgroup')},
        'resident_model':'photo-normal','automatic_model_switching':True}

def page():
    return HTML.replace('__MAX_MUSIC_SECONDS__', str(MAX_MUSIC_SECONDS)).encode('utf-8')

HTML=r'''<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>KoboldCpp · Медиа</title><style>
:root{color-scheme:dark;font:15px system-ui;background:#10151e;color:#e8eef8}*{box-sizing:border-box}body{max-width:1160px;margin:32px auto;padding:0 22px}h1{font-size:28px;margin-bottom:7px}small,.muted{color:#a9b8cd}nav{display:flex;gap:8px;flex-wrap:wrap;margin:24px 0}button,select,input,textarea{font:inherit;color:inherit;background:#1c2839;border:1px solid #3a4d66;border-radius:8px;padding:10px}button{cursor:pointer}button.active,.primary{background:#325eaa;border-color:#699ce9}button:disabled{opacity:.5;cursor:wait}section{display:none}section.active{display:block}.card{background:#172130;border:1px solid #293b52;border-radius:14px;padding:20px;margin:14px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:16px}label{display:grid;gap:7px}textarea{width:100%;min-height:112px;resize:vertical}.row{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin:16px 0}label.check{display:flex;align-items:center}input[type=checkbox]{width:18px;height:18px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:12px ui-monospace;background:#0d1420;padding:14px;border-radius:8px}a{color:#99c0ff}#output img,#output video{max-width:100%;max-height:75vh;border-radius:12px}audio{width:100%}#status{white-space:pre-wrap}.bad{color:#ffafaf}.ok{color:#aadac2}details{margin:12px 0}table{border-collapse:collapse;width:100%}td,th{text-align:left;padding:10px;border-bottom:1px solid #314158}code{overflow-wrap:anywhere}
</style><h1>KoboldCpp · Медиа</h1><div class="muted">Фото, музыка и видео. Модели переключаются автоматически; после задания загружается фото-модель.</div>
<nav><button data-tab="image" class="active">Изображение</button><button data-tab="video">Видео</button><button data-tab="music">Музыка</button><button data-tab="upscale">Апскейл</button><button data-tab="api">API</button><button data-tab="settings">Настройки</button></nav>
<section id="image" class="active"><div class="card"><label>Описание изображения<textarea id="iprompt" placeholder="Опишите сцену, свет, композицию и материалы"></textarea></label><div class="grid"><label>Режим<select id="imode"><option value="normal">Обычный ·736×1104</option><option value="quality">High ·928×1392</option></select></label><label>Исходное фото (необязательно)<input id="iedit" type="file" accept="image/png,image/jpeg,image/webp"></label><label>Перерисовка<input id="idenoise" type="number" min="0" max="1" step="0.05" value="0.6"></label><label>Seed<input id="iseed" type="number" value="-1"></label><label>Шаги<input id="isteps" type="number" min="1" max="9" value="8"></label><label>Сэмплер<select id="isampler"><option value="euler">Euler</option><option value="dpm++2m_sde">DPM++2M SDE</option></select></label><label>Шедулер<select id="ischedule"><option>simple</option><option>beta</option><option>sgm_uniform</option></select></label><label>Порог Cache-DiT<input id="icache" type="number" min="0" max="0.08" step="0.01" value="0.08"></label></div><div class="row"><label class="check"><input id="isr" type="checkbox">ClearReality4×</label><button class="primary" onclick="generateImage()">Создать изображение</button></div><small>YuNet/GPEN/SFace и Gater применяются по настройкам сервера. High включает4×. С исходным фото выполняется целиковая перерисовка; точный перенос лица и маски не поддерживаются.</small></div></section>
<section id="video"><div class="card"><label>Сцена и движение<textarea id="vprompt" placeholder="Опишите движение, камеру и свет"></textarea></label><div class="grid"><label>Начальный кадр (необязательно)<input id="vstart" type="file" accept="image/png"></label><label>Ориентация<select id="vorient"><option value="portrait">Вертикальная</option><option value="landscape">Горизонтальная</option></select></label><label>Кадры<select id="vframes"><option>17</option><option>49</option><option>81</option><option>121</option></select></label><label>Шедулер<select id="vschedule"><option>beta</option><option>simple</option><option>normal</option><option>sgm_uniform</option></select></label><label>Порог Cache-DiT<input id="vcache" type="number" min="0" max="0.08" step="0.01" value="0.04"></label><label>FPS результата<select id="vfps"><option>24</option><option selected>48</option><option>60</option></select></label></div><div class="row"><label class="check"><input id="vsr" type="checkbox" checked>ClearReality720p</label><label class="check"><input id="vfaces" type="checkbox" checked>Лица</label><label class="check"><input id="vaudio" type="checkbox" checked>Музыка YuE2</label></div><label>Описание музыки<input id="vstyle" value="Gentle cinematic instrumental background, no vocals"></label><div class="row"><button class="primary" onclick="generateVideo()">Создать видео</button><small>Wan480p,4шага,Euler,Pro VAE,тайл576,WG512.17кадров≈0,71с;48FPS не увеличивает длительность. Длинные прогоны не подтверждены. Звук — музыкальный фон, без синхронизации губ.</small></div></div></section>
<section id="music"><div class="card"><label>Стиль<input id="mstyle" placeholder="Russian pop, warm vocals, acoustic guitar"></label><label>Текст песни<textarea id="mlyrics" placeholder="[Verse]&#10;Текст песни"></textarea></label><div class="row"><label>Длительность,с<input id="mduration" type="number" min="6" max="__MAX_MUSIC_SECONDS__" value="32"></label><button class="primary" onclick="generateMusic()">Создать MP3</button></div><small>Для инструментала оставьте текст пустым и добавьте no vocals в стиль.</small></div></section>
<section id="upscale"><div class="card"><label>Изображение<input id="ufile" type="file" accept="image/png,image/jpeg,image/webp"></label><div class="row"><button class="primary" onclick="upscaleImage()">ClearReality4× + улучшение деталей</button></div><small>Лица и Gater до апскейла; повторная обработка собственных PNG пропускается по проверенным маркерам.</small><hr><label>ID созданного видео<input id="uvid" placeholder="video_id из ответа API"></label><div class="row"><button onclick="upscaleVideo()">Видео до720p + лица</button></div></div></section>
<section id="api"><div class="card"><h2>Единый API</h2><p>Адрес <code id="base"></code>. Сервер переключает медиамодели по запросу. Совместимость с Native зависит от загруженной модели и настроек.</p><p><a href="/openapi.json" target="_blank">Общий OpenAPI JSON</a> · <a href="/v1/media/openapi.json" target="_blank">OpenAPI медиамаршрутов</a> · <a href="/api/native" target="_blank">Справка Native</a> · <a href="/v1/media/capabilities" target="_blank">Возможности</a></p><pre>POST /v1/media/generations
{"type":"video","parameters":{"prompt":"A cinematic scene","frames":17,"resolution":"480p","interpolate_fps":48,"audio":false}}</pre><label>Поиск по API<input id="routeSearch" type="search" placeholder="Метод, путь или описание"></label><p id="routeStatus" role="status"></p><div id="routes"></div></div></section>
<section id="settings"><div class="card"><h2>Параметры сервера</h2><p>Единый пользовательский конфиг: Helper.kcpps. Профили загрузки формируются из него; пути моделей не передаются в промпте.</p><div class="grid"><label>Cache-DiT фото<input id="scache" type="number" min="0" max="0.08" step="0.01" value="0.08"></label><label>Cache-DiT видео<input id="svcache" type="number" min="0" max="0.08" step="0.01" value="0.04"></label><label>GPEN,доля<input id="sgpen" type="number" min="0" max="0.35" step="0.05" value="0.2"></label><label>SFace,минимум<input id="ssface" type="number" min="0.97" max="1" step="0.01" value="0.97"></label><label>YuNet<input id="syunet" type="number" min="640" max="1280" step="32" value="960"></label></div><div class="row"><label class="check"><input id="sfaces" type="checkbox" checked>Лица</label><label class="check"><input id="sgater" type="checkbox" checked>Gater Restore</label><label class="check"><input id="saudio" type="checkbox" checked>Звук видео по умолчанию</label><button onclick="saveSettings()">Сохранить в Helper.kcpps</button></div><pre id="settingsView">Загрузка…</pre><p class="muted">Сохранение доступно локально, когда нет активной генерации. Пути моделей и системные параметры не принимаются через этот API. Служебные профили воспроизводятся из Helper.kcpps.</p></div></section>
<div class="card"><div id="status">Готово.</div><div id="output"></div><details><summary>Ответ API / время</summary><pre id="details"></pre></details></div>
<script>
const $=id=>document.getElementById(id);let busy=false;let blobURL=null;let settingsRevision=null;
document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>{document.querySelectorAll('section').forEach(s=>s.classList.toggle('active',s.id===b.dataset.tab));document.querySelectorAll('[data-tab]').forEach(x=>x.classList.toggle('active',x===b));});
const preferred=['/api','/docs'].includes(location.pathname)?'api':location.pathname==='/videoui'?'video':location.hash.slice(1);const initialTab=Array.from(document.querySelectorAll('[data-tab]')).find(b=>b.dataset.tab===preferred);if(initialTab)initialTab.click();
$('base').textContent=location.origin;$('imode').onchange=()=>{$('isr').checked=$('imode').value==='quality';};
async function file64(id){const f=$(id).files[0];if(!f)throw Error('Выберите изображение');if(f.size>32*1024*1024)throw Error('Изображение больше32МБ');return await new Promise((ok,no)=>{const r=new FileReader;r.onload=()=>ok(r.result);r.onerror=no;r.readAsDataURL(f);});}
async function call(path,data,kind){if(busy)return;busy=true;document.querySelectorAll('button').forEach(b=>b.disabled=true);$('status').className='';$('status').textContent='Выполняется… Не закрывайте вкладку.';$('output').replaceChildren();const started=performance.now();let timer=setInterval(()=>{$('status').textContent=`Выполняется… ${((performance.now()-started)/1000).toFixed(0)}с`;},1000);try{const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});if(!r.ok){let t=await r.text();throw Error(t.slice(0,3000));}let detail;
if((r.headers.get('content-type')||'').startsWith('audio/')){const blob=await r.blob();if(!blob.size)throw Error('Пустое аудио');if(blobURL)URL.revokeObjectURL(blobURL);blobURL=URL.createObjectURL(blob);const a=document.createElement('audio');a.controls=true;a.src=blobURL;$('output').append(a);detail={format:blob.type,bytes:blob.size};}
else {detail=await r.json();const raw=(detail.images||[])[0]||detail.image;if(raw){const im=document.createElement('img');im.alt='Результат';im.src=raw.startsWith('data:')?raw:'data:image/png;base64,'+raw;$('output').append(im);}const candidate=detail.url||detail.video_url||detail.data?.[0]?.url||detail.output?.url;if(candidate){const u=new URL(candidate,location.origin);if(u.origin!==location.origin)throw Error('Ссылка результата должна принадлежать этому серверу');const v=document.createElement('video');v.controls=true;v.src=u.href;$('output').append(v);const a=document.createElement('a');a.href=u.href;a.textContent='Открыть / скачать MP4';a.target='_blank';$('output').append(a);}if(detail.video_id||detail.id)$('uvid').value=detail.video_id||detail.id;detail=JSON.parse(JSON.stringify(detail,(k,v)=>['images','image','b64_json'].includes(k)?'[данные изображения]':v));}
$('details').textContent=JSON.stringify(detail,null,2);$('status').className='ok';$('status').textContent=`Готово за${((performance.now()-started)/1000).toFixed(2)}с`;}
catch(e){$('status').className='bad';$('status').textContent='Ошибка: '+e.message;}finally{clearInterval(timer);busy=false;document.querySelectorAll('button').forEach(b=>b.disabled=false);}}
function cache(value,warmup){return Number(value)>0?{cache_mode:'cache-dit',cache_options:`threshold=${Number(value)},warmup=${warmup},Fn=16,Bn=2`}:{cache_mode:'disabled',cache_options:''};}
async function generateImage(){const high=$('imode').value==='quality';const body={prompt:$('iprompt').value,width:high?928:736,height:high?1392:1104,kcpp_quality:high?'quality':'normal',steps:Number($('isteps').value),cfg_scale:1,sampler_name:$('isampler').value,scheduler:$('ischedule').value,eta:0,flow_shift:5,seed:Number($('iseed').value),enable_hr:$('isr').checked,...cache($('icache').value,4)};try{if($('iedit').files.length){body.init_images=[await file64('iedit')];body.denoising_strength=Number($('idenoise').value);return call('/sdapi/v1/img2img',body,'image');}return call('/sdapi/v1/txt2img',body,'image');}catch(e){$('status').textContent=e.message;}}
async function generateVideo(){let data={model:'kobold-wan22-turbo',prompt:$('vprompt').value,frames:Number($('vframes').value),resolution:'480p',orientation:$('vorient').value,sampler_name:'euler',scheduler:$('vschedule').value,steps:4,cfg_scale:1,eta:0,flow_shift:5,upscale_to:$('vsr').checked?'720p':null,enhance_faces:$('vfaces').checked,interpolate_fps:Number($('vfps').value),audio:{enabled:$('vaudio').checked,style:$('vstyle').value,lyrics:''},...cache($('vcache').value,1)};try{if($('vstart').files.length)data.image=await file64('vstart');return call('/v1/videos/generations',data,'video');}catch(e){$('status').textContent=e.message;}}
function generateMusic(){return call('/api/extra/music/generate',{lyrics:$('mlyrics').value,style:$('mstyle').value,duration:Number($('mduration').value),cot:'off',num_inference_steps:8,guidance_scale:1.01,use_mp3:true,stereo:true},'music');}
async function upscaleImage(){try{return call('/sdapi/v1/extra-single-image',{image:await file64('ufile'),upscaling_resize:4},'image');}catch(e){$('status').textContent=e.message;}}
function upscaleVideo(){return call('/v1/videos/upscale',{video_id:$('uvid').value,enhance_faces:true},'video');}
fetch('/v1/media/settings').then(r=>r.json()).then(v=>{$('settingsView').textContent=JSON.stringify(v,null,2);settingsRevision=v.revision;$('sfaces').checked=v.faces.enabled;$('sgater').checked=v.gater;$('sgpen').value=v.faces.visibility;$('ssface').value=v.faces.minimum_feature_similarity;$('syunet').value=v.faces.detector_resolution;$('saudio').checked=v.video.default_audio;const threshold=s=>Number((/threshold=([0-9.]+)/.exec(s||'')||[])[1]||0);$('scache').value=threshold(v.image.cache_options);$('svcache').value=threshold(v.video.default_cache_options);$('icache').value=$('scache').value;$('vcache').value=$('svcache').value;$('vaudio').checked=v.video.default_audio;$('vfps').value=String(v.video.default_interpolate_fps||48);}).catch(e=>{$('settingsView').textContent=e.message;});
fetch('/openapi.json').then(r=>{if(!r.ok)throw new Error(String(r.status));return r.json();}).then(doc=>{
  const table=document.createElement('table'), body=table.createTBody();
  const header=table.createTHead().insertRow();
  for(const label of ['Метод','Путь','Описание','Раздел']){const cell=document.createElement('th');cell.textContent=label;header.append(cell);}
  const resolve=(item,seen=new Set())=>{const ref=item.$ref;if(!ref?.startsWith('#/paths/')||seen.has(ref))return item;
    seen.add(ref);return resolve(doc.paths[ref.slice(8).replaceAll('~1','/').replaceAll('~0','~')]||{},seen);};
  const rows=[];
  for(const [path,item] of Object.entries(doc.paths))for(const [method,op] of Object.entries(resolve(item))){
    if(!['get','post','put','patch','delete','head','options'].includes(method))continue;
    const row=body.insertRow();
    for(const value of [method.toUpperCase(),path,op.summary||op.description||'',item['x-kobold-scope']==='native'?'Native':'Медиа'])row.insertCell().textContent=value;
    rows.push(row);
  }
  $('routes').append(table);
  const filter=()=>{const query=$('routeSearch').value.trim().toLowerCase();let shown=0;
    for(const row of rows){row.hidden=!row.textContent.toLowerCase().includes(query);if(!row.hidden)shown++;}
    $('routeStatus').textContent=`${shown} из ${rows.length} операций`+(doc['x-kobold-native-catalog']==='unavailable'?' · Справка Native временно недоступна.':'');};
  $('routeSearch').addEventListener('input',filter);filter();
}).catch(()=>{$('routeStatus').textContent='Не удалось загрузить список маршрутов.';});
async function saveSettings(){try{const r=await fetch('/v1/media/settings',{method:'POST',headers:{'Content-Type':'application/json','X-Kobold-Config':'1'},body:JSON.stringify({revision:settingsRevision,image:{cache_threshold:Number($('scache').value)},video:{cache_threshold:Number($('svcache').value),default_audio:$('saudio').checked},faces:{enabled:$('sfaces').checked,visibility:Number($('sgpen').value),minimum_feature_similarity:Number($('ssface').value),detector_resolution:Number($('syunet').value)},gater:$('sgater').checked})});const v=await r.json();if(!r.ok)throw Error(JSON.stringify(v));settingsRevision=v.revision;$('icache').value=$('scache').value;$('vcache').value=$('svcache').value;$('vaudio').checked=$('saudio').checked;$('status').textContent='Настройки сохранены. Следующие запросы используют новый конфиг.';}catch(e){$('status').textContent=e.message;}}
fetch('/v1/videos/capabilities').then(r=>r.json()).then(v=>{for(const op of $('vfps').options)if(!v.interpolate_fps.includes(Number(op.value)))op.disabled=true;if(!v.interpolate_fps.includes(Number($('vfps').value)))$('vfps').value='24';}).catch(()=>{});
</script></html>'''

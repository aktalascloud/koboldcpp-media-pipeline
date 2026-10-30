"""Native Kobold settings controls; one Helper, existing portable runtime and supervisor."""
from pathlib import Path
import hashlib,json,subprocess,sys,threading,time,urllib.request

ROOT=Path(__file__).resolve().parent.parent
# name, tab, label, type/choices, lower, upper
FIELDS=[
 ('photo_steps','Фото','Шаги',int,1,9),('photo_sampler','Фото','Сэмплер',('euler','dpm++2m_sde'),None,None),
 ('photo_scheduler','Фото','Шедулер',('simple','beta','sgm_uniform'),None,None),('photo_cfg','Фото','CFG',float,0,10),
 ('photo_shift','Фото','Flow shift',float,.1,10),('photo_cache','Фото','Cache-DiT, порог',float,0,.08),
 ('image_edit_enabled','Фото','Редактирование img2img',bool,None,None),
 ('video_frames','Видео','Кадры (4n+1)',int,5,121),('video_scheduler','Видео','Euler / шедулер',('beta','simple','normal','sgm_uniform'),None,None),
 ('video_cache','Видео','Cache-DiT, порог',float,0,.08),('video_vram','Видео','VRAM Native, МиБ',int,4096,7500),
 ('video_upscale','Видео','ClearReality до720p',bool,None,None),('video_faces','Видео','Улучшение лиц',bool,None,None),
 ('video_audio','Видео','Музыкальная дорожка',bool,None,None),('video_fps','Видео','FPS (RIFE)',('24','48'),None,None),
 ('music_duration','Музыка','Длительность, с',int,1,360),('music_steps','Музыка','Шаги YuE2',int,1,64),
 ('music_guidance','Музыка','Guidance',float,0,20),('music_cot','Музыка','CoT',('off','melody','full'),None,None),
 ('normal_sr','Апскейл','Авто4×: обычный режим',bool,None,None),('high_sr','Апскейл','Авто4×: High',bool,None,None),
 ('sr_tile','Апскейл','Тайл (0 = авто)',int,0,1024),('sr_padding','Апскейл','Перекрытие тайлов',int,8,64),
 ('face_enabled','Лица','YuNet / GPEN / SFace',bool,None,None),('face_percent','Лица','GPEN, %',float,0,35),
 ('face_similarity','Лица','SFace, минимум',float,.97,1),('face_resolution','Лица','YuNet, разрешение',int,640,1280),
 ('face_max','Лица','Максимум лиц',int,1,4),('gater','Лица','Gater Restore1×',bool,None,None),
 ('autostart','Система','Автозапуск при входе',bool,None,None),
]

def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def gd(h):return json.loads(h['gendefaults']) if isinstance(h['gendefaults'],str) else h['gendefaults']
def threshold(options,default):
    return next((float(p.split('=',1)[1]) for p in (options or '').split(',') if p.startswith('threshold=')),default)

def profile_data(h,root=ROOT):
    config=gd(h)['kcpp_proxy']['backend_supervisor'];inline=config.get('inline_profiles',{})
    return {n:json.loads(inline[n]) if n in inline else read(root/s['helper']) for n,s in config['profiles'].items()}

def load_values(root=ROOT,configuration=None):
    h=configuration or read(root/'Helper.kcpps');d=gd(h);p=d['kcpp_proxy'];v=p['video'];f=p['detailer'];m=p.get('music_defaults',{})
    vp=profile_data(h,root)['video']
    values=dict(photo_steps=d['steps'],photo_sampler=d['sampler_name'],photo_scheduler=d['scheduler'],photo_cfg=d['cfg_scale'],photo_shift=d['flow_shift'],photo_cache=threshold(d.get('cache_options'),0) if d.get('cache_mode')!='disabled' else 0,
        video_frames=v.get('default_frames',17),video_scheduler=v['scheduler'],video_cache=threshold(v.get('default_cache_options'),0) if v.get('default_cache_mode')!='disabled' else 0,video_vram=vp.get('sdvramlimit',6500),video_upscale=v.get('default_upscale_to')=='720p',video_faces=v.get('default_enhance_faces',True),video_audio=v.get('default_audio',True),video_fps=str(v.get('default_interpolate_fps',24)),
        music_duration=m.get('duration',32),music_steps=m.get('num_inference_steps',8),music_guidance=m.get('guidance_scale',1.01),music_cot=m.get('cot','off'),
        normal_sr=p['image_modes']['normal']['auto_upscale'],high_sr=p['image_modes']['quality']['auto_upscale'],sr_tile=p['upscaler'].get('tile',0),sr_padding=p['upscaler'].get('padding',32),
        face_enabled=f.get('enabled',True),face_percent=float(f.get('visibility',.2))*100,face_similarity=f.get('minimum_feature_similarity',.97),face_resolution=f.get('detector_resolution',960),face_max=f.get('max_faces',2),gater=p['photo_restoration']['enabled'],autostart=p.get('autostart_enabled',False),image_edit_enabled=p.get('image_edit_enabled',True))
    return values,hashlib.sha256((root/'Helper.kcpps').read_bytes()).hexdigest()

def validate(values):
    if set(values)!={r[0] for r in FIELDS}:raise ValueError('Неполный или неизвестный набор параметров.')
    out={}
    for key,tab,label,kind,low,high in FIELDS:
        value=values[key]
        if isinstance(kind,tuple):
            if value not in kind:raise ValueError(label+': неподдерживаемое значение')
        elif kind is bool:
            if type(value) is not bool:raise ValueError(label+': требуется переключатель')
        else:
            if type(value) not in (int,float) or (kind is int and type(value) is not int) or not low<=value<=high:raise ValueError(label+': значение вне диапазона')
        out[key]=value
    if out['video_frames']%4!=1:raise ValueError('Кадры видео:5,9,13,17…121 (4n+1).')
    if out['music_cot']=='melody':raise ValueError('CoT melody требует ABC-партитуру в запросе; используйте off или full по умолчанию.')
    if out['sr_tile'] and out['sr_tile']<64:raise ValueError('Тайл:0 или не меньше64.')
    return out

def save(payload,root=ROOT):
    from MediaControl import stop_services
    from BackendSupervisor import write_json
    from UnifiedConfig import consolidate
    from MediaConfig import _atomic,_encode
    values=validate(payload['values']);helper=root/'Helper.kcpps';active=read(helper);h=json.loads(json.dumps(payload.get('configuration') or active))
    if not payload.get('export_file') and payload.get('revision')!=hashlib.sha256(helper.read_bytes()).hexdigest():raise ValueError('Настройки уже изменились. Перезагрузите форму.')
    d=gd(h);p=d['kcpp_proxy'];profiles=profile_data(h,root)
    # Runtime identity is owned by this installation, not by a copied user file.
    current=gd(active)['kcpp_proxy']['backend_supervisor'];p['backend_supervisor']=json.loads(json.dumps(current))
    for name,profile in profiles.items():
        spec=p['backend_supervisor']['profiles'][name];profile['port']=profile['port_param']=int(spec['port']);profile['host']='127.0.0.1'
    mode='cache-dit' if values['photo_cache'] else 'disabled';cache=f"threshold={values['photo_cache']},warmup=4,Fn=16,Bn=2" if values['photo_cache'] else ''
    image=dict(steps=values['photo_steps'],sampler_name=values['photo_sampler'],scheduler=values['photo_scheduler'],cfg_scale=values['photo_cfg'],flow_shift=values['photo_shift'],cache_mode=mode,cache_options=cache,eta=0)
    d.update(image)
    for name in ('photo-normal','photo-quality'):
        g=gd(profiles[name]);g.update(image);profiles[name]['gendefaults']=json.dumps(g,separators=(',',':'))
    v=p['video'];v.update(default_frames=values['video_frames'],frames=values['video_frames'],scheduler=values['video_scheduler'],default_cache_mode='cache-dit' if values['video_cache'] else 'disabled',default_cache_options=f"threshold={values['video_cache']},warmup=1,Fn=16,Bn=2" if values['video_cache'] else '',default_upscale_to='720p' if values['video_upscale'] else None,default_enhance_faces=values['video_faces'],default_audio=values['video_audio'],default_interpolate_fps=int(values['video_fps']))
    vg=gd(profiles['video']);vg.update(scheduler=v['scheduler'],cache_mode=v['default_cache_mode'],cache_options=v['default_cache_options']);profiles['video'].update(sdvramlimit=values['video_vram'],gendefaults=json.dumps(vg,separators=(',',':')))
    p['music_defaults']=dict(duration=values['music_duration'],num_inference_steps=values['music_steps'],guidance_scale=values['music_guidance'],cot=values['music_cot'])
    mg=gd(profiles['music']);mg.update(num_inference_steps=values['music_steps'],guidance_scale=values['music_guidance'],cot=values['music_cot']);profiles['music']['gendefaults']=json.dumps(mg,separators=(',',':'))
    p['image_modes']['normal']['auto_upscale']=values['normal_sr'];p['image_modes']['quality']['auto_upscale']=values['high_sr'];p['upscaler'].update(tile=values['sr_tile'],padding=values['sr_padding'])
    p['detailer'].update(enabled=values['face_enabled'],visibility=values['face_percent']/100,minimum_feature_similarity=values['face_similarity'],detector_resolution=values['face_resolution'],max_faces=values['face_max']);p['photo_restoration']['enabled']=values['gater'];p['autostart_enabled']=values['autostart']
    p['image_edit_enabled']=values['image_edit_enabled']
    p['ui_language']=payload.get('language',p.get('ui_language','ru'))
    if payload.get('services') is not None:
        from AudioServices import normalize
        p['audio_services']=normalize(payload['services'])
    h['gendefaults']=json.dumps(d,ensure_ascii=False,separators=(',',':'))
    registry=None
    if payload.get('models') is not None:
        from MediaModelFiles import prepare
        registry=prepare(payload['models'],h,profiles,p,root)
        h['gendefaults']=json.dumps(d,ensure_ascii=False,separators=(',',':'))
    if registry is None:registry=read(root/'profiles/moss-adapters.json')
    p['embedded_adapter_registry']=registry
    if payload.get('export_file'):
        destination=Path(payload['export_file']).expanduser().resolve()
        if destination.suffix.lower()!='.kcpps':raise ValueError('Выберите файл .kcpps')
        if destination==helper.resolve():raise ValueError('Это служебный снимок. Сохраните конфигурацию под пользовательским именем.')
        destination.parent.mkdir(parents=True,exist_ok=True)
        for name,profile in profiles.items():
            raw=_encode(profile).decode('utf-8');spec=p['backend_supervisor']['profiles'][name];spec['helper_sha256']=hashlib.sha256(raw.encode('utf-8')).hexdigest();p['backend_supervisor'].setdefault('inline_profiles',{})[name]=raw
        h['gendefaults']=json.dumps(d,ensure_ascii=False,separators=(',',':'));_atomic(destination,_encode(h))
        return {'ok':True,'saved_file':str(destination),'configuration':h,'runtime_changed':False}
    h['gendefaults']=json.dumps(d,ensure_ascii=False,separators=(',',':'))
    paths=[helper,root/'portable-manifest.json',root/'profiles/moss-adapters.json',*[root/spec['helper'] for spec in p['backend_supervisor']['profiles'].values()]];backups={q:q.read_bytes() for q in paths if q.exists()}
    supervisor=None
    try:
        supervisor,_=stop_services(root)
        if registry is not None:write_json(root/'profiles/moss-adapters.json',registry)
        for name,profile in profiles.items():write_json(root/p['backend_supervisor']['profiles'][name]['helper'],profile)
        consolidate(h,root);write_json(helper,h)
        manifest=root/'portable-manifest.json'
        if manifest.exists():
            data=read(manifest);rows={r['path']:r for r in data['files']}
            for q in paths:
                if q==manifest or not q.exists():continue
                raw=q.read_bytes();name=q.relative_to(root).as_posix();rows[name]={'path':name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
            data.update(files=sorted(rows.values(),key=lambda r:r['path']),file_count=len(rows),total_bytes=sum(r['bytes'] for r in rows.values()));_atomic(manifest,_encode(data))
        from Startup import register,unregister
        if values['autostart']:register()
        else:unregister()
    except BaseException:
        for q,raw in backups.items():_atomic(q,raw)
        raise
    finally:
        if supervisor:supervisor.close()
        subprocess.Popen([str(root/'runtime/python/pythonw.exe'),'-I','-B',str(root/'tools/AutoStart.py')],cwd=root,creationflags=subprocess.CREATE_NO_WINDOW)
    port=int(p['port']);deadline=time.monotonic()+180
    while time.monotonic()<deadline:
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/health',timeout=2) as r:health=json.load(r)
            if health.get('helper_sha256')==hashlib.sha256(helper.read_bytes()).hexdigest() and health.get('backend_supervisor',{}).get('native_profile')=='photo-normal':return {'ok':True,'revision':health['helper_sha256']}
        except OSError:pass
        time.sleep(.5)
    raise RuntimeError('Настройки записаны; запуск ещё не подтверждён. Проверьте logs/autostart.log.')

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');sys.stderr.reconfigure(encoding='utf-8')
    try:print(json.dumps(save(json.load(sys.stdin))))
    except Exception as error:print(str(error),file=sys.stderr);raise SystemExit(1)

"""Bind stock Kobold file selectors to media profiles; import external files portably."""
from pathlib import Path
import hashlib,json,math

IMAGE_FIELDS=('sdmodel','sdllm','sdclip1','sdclip2','sdvae')
MUSIC_FIELDS=('musicllm','musicvae','musicdiffusion','musicembeddings')
POST_FIELDS=('upscaler','video_upscaler','rife','face','guard','detector','restoration')

def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def selection(h,profiles,proxy):
    result={name:{**{k:profiles[key].get(k,'') for k in IMAGE_FIELDS},'sdlora':profiles[key].get('sdlora') or [],'sdloramult':profiles[key].get('sdloramult') or []} for name,key in [('photo','photo-normal'),('video','video')]}
    result['music']={k:profiles['music'].get(k,'') for k in MUSIC_FIELDS}
    f=proxy['detailer'];result['post']={'upscaler':proxy['upscaler']['model'],'video_upscaler':proxy['video'].get('upscaler_model',proxy['upscaler']['model']),'rife':proxy['video'].get('rife_models','DETAILERS/interpolation/rife-v4.6'),'face':f['model'],'guard':f['feature_guard_model'],'detector':f.get('detector_model','DETAILERS/faces/face_detection_yunet_2023mar.onnx'),'restoration':proxy['photo_restoration']['model']}
    return result

def gguf_arch(path):
    from MossImageBudget import _read,_string,_value
    with path.open('rb') as f:
        if f.read(4)!=b'GGUF' or _read(f,'<I')!=3:raise ValueError('Ожидается GGUF v3: '+path.name)
        _read(f,'<Q');n=_read(f,'<Q')
        if n>10000:raise ValueError('Слишком большой GGUF-заголовок')
        for _ in range(n):
            key=_string(f);value=_value(f,_read(f,'<I'))
            if key=='general.architecture':return value
    raise ValueError('Архитектура GGUF не указана')

def portable_file(value,folder,root,convert_role=None):
    import shutil,subprocess,sys,uuid
    value=str(value).strip()
    if not value:return ''
    source=(Path(value) if Path(value).is_absolute() else root/value).resolve()
    if not source.is_file():raise ValueError('Файл не найден: '+str(source))
    if convert_role and source.suffix.lower()=='.safetensors':
        output=root/folder/(source.stem+'-'+sha(source)[:10]+'.gguf')
        if not output.exists():
            output.parent.mkdir(parents=True,exist_ok=True)
            subprocess.run([sys.executable,'-I','-B',str(root/'tools/MossConvert.py'),'--source-dir',str(source.parent),'--source-file',str(source),'--output-dir',str(output.parent),'--role',convert_role,'--output-name',output.name,'--model-name',source.stem],check=True,cwd=root,stdout=sys.stderr)
        return output.relative_to(root).as_posix()
    if source.is_relative_to(root):return source.relative_to(root).as_posix()
    digest=sha(source);destination=(root/folder/(source.stem+'-'+digest[:10])/source.name).resolve()
    if not destination.is_relative_to(root):raise ValueError('Небезопасный путь импорта')
    files=[(source,destination)]
    if source.suffix.lower()=='.onnx':
        import onnx
        model=onnx.load(str(source),load_external_data=False)
        for tensor in model.graph.initializer:
            for row in tensor.external_data:
                if row.key!='location':continue
                relative=Path(row.value);original=(source.parent/relative).resolve();target=(destination.parent/relative).resolve()
                if relative.is_absolute() or not original.is_relative_to(source.parent) or not target.is_relative_to(destination.parent):raise ValueError('ONNX external data выходит из папки модели')
                if not original.is_file():raise ValueError('Отсутствует ONNX external data: '+row.value)
                files.append((original,target))
    files=list({str(t):(s,t) for s,t in files}.values())
    missing=sum(s.stat().st_size for s,t in files if not t.exists())
    if shutil.disk_usage(root).free<missing+256*1024**2:raise ValueError('Недостаточно места для переносимого импорта')
    for original,target in files:
        if target.exists():
            if sha(target)!=sha(original):raise ValueError('Другой файл импорта сохранён: '+str(target))
            continue
        target.parent.mkdir(parents=True,exist_ok=True);temporary=target.with_name(target.name+'.import-'+uuid.uuid4().hex)
        shutil.copy2(original,temporary)
        if sha(temporary)!=sha(original):raise ValueError('Ошибка SHA256 при импорте')
        temporary.replace(target)
    return destination.relative_to(root).as_posix()

def prepare(chosen,h,profiles,proxy,root):
    root=Path(root).resolve();old=selection(h,profiles,proxy)
    if not isinstance(chosen,dict) or set(chosen)!=set(old):raise ValueError('Неверные группы файлов медиапрофиля')
    for group,keys in [('photo',(*IMAGE_FIELDS,'sdlora','sdloramult')),('video',(*IMAGE_FIELDS,'sdlora','sdloramult')),('music',MUSIC_FIELDS),('post',POST_FIELDS)]:
        if not isinstance(chosen[group],dict) or set(chosen[group])!=set(keys):raise ValueError('Неверные поля файлов: '+group)
    for group,key in [('photo','photo-normal'),('video','video')]:
        row=chosen[group];profile=profiles[key]
        for field in IMAGE_FIELDS:
            role='image' if group=='photo' and field=='sdmodel' else 'text' if group=='photo' and field in ('sdclip1','sdllm') else None
            folder='MODELS/images' if group=='photo' and field=='sdmodel' else 'MODELS/video' if field=='sdmodel' else 'MODELS/vae' if field=='sdvae' else 'MODELS/text'
            profile[field]=portable_file(row[field],folder,root,role)
        if group=='photo':
            from MossImageBudget import inspect_gguf
            if inspect_gguf(root/profile['sdmodel'])['architecture']!='moss_image':raise ValueError('Фото-профиль требует совместимую MOSS GGUF')
            if profile.get('sdllm'):
                if profile.get('sdclip1') and profile['sdclip1']!=profile['sdllm']:raise ValueError('Для MOSS выберите один текстовый энкодер: Clip-1 или Image LLM')
                profile['sdclip1']=profile.pop('sdllm');profile['sdllm']=''
            if inspect_gguf(root/profile['sdclip1'])['architecture']!='qwen35':raise ValueError('MOSS требует текстовый энкодер Qwen3.5')
            tokenizer=json.loads((root/profile['sdclip2']).read_text(encoding='utf-8'))
            if not isinstance(tokenizer.get('model'),dict):raise ValueError('Clip-2 для MOSS должен быть tokenizer.json')
        elif gguf_arch(root/profile['sdmodel'])!='wan':raise ValueError('Видеопрофиль требует совместимую Wan2.2 TI2V5B GGUF')
        paths=row['sdlora'];weights=row['sdloramult']
        if not isinstance(paths,list) or not isinstance(weights,list) or len(paths)>4:raise ValueError('Допустимы до4 статических LoRA')
        if not paths:weights=[]
        if paths and len(weights)==1:weights=weights*len(paths)
        if len(paths)!=len(weights) or any(type(w) not in (int,float) or not math.isfinite(w) or not -2<=w<=2 for w in weights):raise ValueError('Укажите по одному весу LoRA либо один общий вес')
        profile['sdlora']=[portable_file(p,'MODELS/loras',root) for p in paths];profile['sdloramult']=weights
        if any(Path(p).suffix.lower()!='.safetensors' for p in profile['sdlora']):raise ValueError('Для медиапрофиля LoRA должны быть safetensors')
        if group=='photo':
            for field in (*IMAGE_FIELDS,'sdlora','sdloramult'):h[field]=profile.get(field,'');profiles['photo-quality'][field]=profile.get(field,'')
    music=chosen['music']
    if music.get('musicdiffusion') or music.get('musicembeddings'):raise ValueError('YuE2 использует MusicLLM и MusicVAE; ACE-Step Diffuser/Embeds оставьте пустыми')
    for field in MUSIC_FIELDS:
        value=portable_file(music[field],'MODELS/music/user',root)
        if value and gguf_arch(root/value)!='audiocpp':raise ValueError('Музыкальный профиль требует совместимые YuE2 GGUF')
        profiles['music'][field]=h[field]=value
    if not h.get('musicllm') or not h.get('musicvae'):raise ValueError('Укажите оба файла YuE2: MusicLLM и MusicVAE')
    for name in POST_FIELDS:
        if name=='rife':
            import shutil
            source=Path(chosen['post'][name]);source=(source if source.is_absolute() else root/source).resolve()
            if not all((source/f).is_file() for f in ('flownet.bin','flownet.param')):raise ValueError('RIFE: выберите папку с flownet.bin и flownet.param')
            if not source.is_relative_to(root):
                target=root/'DETAILERS/interpolation'/(source.name+'-'+sha(source/'flownet.param')[:10]);target.mkdir(parents=True,exist_ok=True)
                for filename in ('flownet.bin','flownet.param'):
                    destination=target/filename
                    if destination.exists() and sha(destination)!=sha(source/filename):raise ValueError('Другие файлы RIFE сохранены')
                    if not destination.exists():shutil.copy2(source/filename,destination)
                source=target
            proxy['video']['rife_models']=source.relative_to(root).as_posix();continue
        path=portable_file(chosen['post'][name],'UPSCALERS/imported' if name in ('upscaler','video_upscaler') else 'DETAILERS/imported',root)
        if not path or Path(path).suffix.lower()!='.onnx':raise ValueError('Для '+name+' требуется совместимая ONNX-модель')
        import onnx
        graph=onnx.load(str(root/path),load_external_data=False);constants={t.name for t in graph.graph.initializer}
        feeds=[v for v in graph.graph.input if v.name not in constants]
        if not any(v.type.tensor_type.elem_type==onnx.TensorProto.FLOAT and len(v.type.tensor_type.shape.dim)==4 for v in feeds):raise ValueError(name+': требуется совместимая FP32 NCHW ONNX-модель')
        if name=='upscaler':
            changed=path!=proxy['upscaler']['model'];proxy['upscaler'].update(model=path,model_sha256=sha(root/path))
            if changed:proxy['upscaler']['name']=Path(path).stem+' FP32 DML4x'
        elif name=='video_upscaler':proxy['video'].update(upscaler_model=path,upscaler_model_sha256=sha(root/path))
        elif name=='restoration':proxy['photo_restoration'].update(model=path,model_sha256=sha(root/path))
        else:proxy['detailer'][{'face':'model','guard':'feature_guard_model','detector':'detector_model'}[name]]=path
    registry_path=root/'profiles/moss-adapters.json';registry=json.loads(registry_path.read_text(encoding='utf-8'));known={r['path']:r for m in registry.get('models',{}).values() for r in m.get('adapters',[])}
    model=h['sdmodel'];entry=registry.setdefault('models',{}).setdefault(model,{})
    entry['adapters']=[{**known.get(p,{'role':'user'}),'path':p,'weight':float(w),'sha256':sha(root/p)} for p,w in zip(h['sdlora'],h['sdloramult'])]
    proxy['video']['adapters']=[{'name':Path(p).name,'sha256':sha(root/p),'weight':float(w)} for p,w in zip(profiles['video']['sdlora'],profiles['video']['sdloramult'])]
    return registry

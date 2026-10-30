"""Native Image Gen / Audio / Video editor, using Kobold's own file picker helpers."""
from pathlib import Path
import json,hashlib,subprocess,threading,sys
from MediaNativeGUI import FIELDS,load_values,profile_data,read,gd,validate
from MediaModelFiles import IMAGE_FIELDS,MUSIC_FIELDS,selection

ROOT=Path(__file__).resolve().parent.parent
EN_LABELS={'photo_steps':'Steps','photo_sampler':'Sampler','photo_scheduler':'Scheduler','photo_cfg':'CFG','photo_shift':'Flow shift','photo_cache':'Cache-DiT threshold','image_edit_enabled':'Image editing (img2img)','video_frames':'Video frames (4n+1)','video_scheduler':'Euler scheduler','video_cache':'Video cache threshold','video_vram':'Native VRAM limit, MiB','video_upscale':'Upscale video to720p','video_faces':'Video face restoration','video_audio':'Video soundtrack','video_fps':'Output FPS (RIFE)','music_duration':'Music duration, seconds','music_steps':'YuE2 inference steps','music_guidance':'Music guidance','music_cot':'Music CoT','normal_sr':'Normal automatic4x upscale','high_sr':'High automatic4x upscale','sr_tile':'Upscaler tile (0=auto)','sr_padding':'Tile overlap','face_enabled':'YuNet / GPEN / SFace','face_percent':'GPEN blend, %','face_similarity':'SFace minimum similarity','face_resolution':'YuNet resolution','face_max':'Maximum faces','gater':'Gater Restore1x','autostart':'Start at Windows logon'}
TIPS={
 'photo_steps':('Количество шагов фото. Для текущей MOSS рекомендуется8; максимум9.','Image diffusion steps. Current MOSS preset uses8; maximum9.'),
 'photo_sampler':('Алгоритм семплирования фото. Файлы моделей выбираются штатными Browse.','Image sampler. Model files use the original Browse controls.'),
 'photo_scheduler':('Распределение шагов по уровню шума.','Noise schedule used by the image sampler.'),
 'photo_cfg':('Сила следования описанию; для Turbo обычно1.','Prompt guidance; Turbo usually uses1.'),
 'photo_shift':('Сдвиг временной шкалы diffusion; текущее значение5.','Diffusion timestep shift; current value5.'),
 'photo_cache':('Порог Cache-DiT для фото.0 выключает кэш.','Image Cache-DiT threshold.0 disables caching.'),
 'image_edit_enabled':('Включает наше img2img API: одна исходная картинка и целиковая перерисовка. Без масок и точного переноса лица.','Enable custom img2img API: one target and whole-frame redraw. No masks or exact identity transfer.'),
 'video_frames':('Число кадров4n+1.17 кадров≈0,71с при24FPS; длинные прогоны не подтверждены.','Frame count4n+1.17frames≈0.71s at24FPS; long clips are unverified.'),
 'video_scheduler':('Шедулер Euler для видео. Шаги4, CFG1 и eta0 сохраняются.','Video Euler scheduler.4steps,CFG1 and eta0 remain fixed.'),
 'video_cache':('Лёгкий Cache-DiT;0 выключает. Текущий порог0,04, warmup1; выигрыш не гарантирован.','Light Cache-DiT;0 disables it. Current threshold0.04/warmup1; no guaranteed gain.'),
 'video_vram':('Лимит Native в МиБ; Pro и постобработка получают GPU отдельно.','Native VRAM budget inMiB; Pro and postprocessing use the GPU separately.'),
 'video_upscale':('Финальный апскейл видео до720p выбранной ONNX-моделью.','Final video upscale to720p using the selected ONNX model.'),
 'video_faces':('YuNet, GPEN и проверка сходства SFace для кадров.','YuNet, GPEN and SFace identity guard for video frames.'),
 'video_audio':('Отдельная музыкальная дорожка YuE2. Это не синхронизация губ или шумы по видеоряду.','Separate YuE2 musical track, not lip-sync or video-conditioned Foley.'),
 'video_fps':('RIFE добавляет промежуточные кадры до48FPS, не меняя длительность.','RIFE interpolates to48FPS without extending duration.'),
 'music_duration':('Приблизительный предел YuE2 через25 semantic tokens/с, не точная длина.','Approximate YuE2 cap using25 semantic tokens/s, not an exact duration.'),
 'music_steps':('Шаги генерации YuE2 по умолчанию. Явные параметры API имеют приоритет.','Default YuE2 generation steps. Explicit API parameters override defaults.'),
 'music_guidance':('Guidance музыки; это не CFG изображения.','Music guidance, independent from image CFG.'),
 'music_cot':('Off быстрее. Melody требует ABC-партитуру в запросе.','Off is faster. Melody requires an ABC score in the request.'),
 'normal_sr':('Автоапскейл обычной генерации; отдельное API апскейла остаётся доступным.','Automatic Normal upscale; the separate upscale API stays available.'),
 'high_sr':('Автоапскейл режима High после обработки лиц и деталей.','Automatic High upscale after face/detail processing.'),
 'sr_tile':('0 означаетавто. Меньшие тайлы снижают VRAM, но могут замедлить работу.','0 meansauto. Smaller tiles reduce VRAM but may be slower.'),
 'sr_padding':('Перекрытие тайлов для уменьшения видимых стыков.','Tile overlap used to reduce visible seams.'),
 'face_enabled':('Детектор YuNet, GPEN и SFace до апскейла.','YuNet detection, GPEN and SFace before upscaling.'),
 'face_percent':('Доля результата GPEN. Текущее значение20%.','GPEN result blend. Current value20%.'),
 'face_similarity':('Минимальное сходство лица после улучшения; текущее0,97.','Minimum identity similarity after restoration; current0.97.'),
 'face_resolution':('Размер входа детектора YuNet; текущее960.','YuNet detector input size; current960.'),
 'face_max':('Максимум обрабатываемых лиц; размеры выбираются автоматически.','Maximum processed faces; size bounds scale automatically.'),
 'gater':('Один проход восстановления1x до апскейла, без дополнительного sharpen.','One1x restoration pass before upscaling; no extra sharpening.'),
 'autostart':('Автозапуск применённой конфигурации при входе в Windows. Модели меняются по API.','Start the applied configuration at Windows logon. Models switch on API demand.'),
}

class Editor:
    def __init__(self,ctk,parents,photo_vars,makefileentry,show_tooltip,hide_tooltip,dialogs,locale,root=ROOT):
        self.ctk=ctk;self.root=root;self.parents=parents;self.makefileentry=makefileentry;self.hover=show_tooltip;self.hide=hide_tooltip;self.dialogs=dialogs;self.locale=locale
        self.configuration=read(root/'Helper.kcpps');self.source=None;self.widgets={};self.photo_vars=photo_vars;self.video_vars={};self.post_vars={};self.status=ctk.StringVar(value='')
        state=root/'logs/active-user-config.json'
        if state.exists():
            previous=read(state).get('path')
            if previous and Path(previous).is_file():self.source=Path(previous)
        self.revision=hashlib.sha256((root/'Helper.kcpps').read_bytes()).hexdigest()
        for name,label,key,filters in [('Video model','Video model','sdmodel','*.gguf *.safetensors'),('Video encoder','Text encoder','sdclip1','*.gguf *.safetensors'),('Video VAE','Video VAE','sdvae','*.gguf *.safetensors'),('Video LoRAs','Video LoRAs','sdlora','*.safetensors')]:
            var=ctk.StringVar();self.video_vars[key]=var
            row=1+list(('sdmodel','sdclip1','sdvae','sdlora')).index(key)*3
            makefileentry(parents['Видео'],label,'Select '+name,var,row=row,width=290,filetypes=[('Model files',filters)],multiple=key=='sdlora',tooltiptxt='RU: Выберите совместимый файл для Wan2.2 TI2V5B.\nEN: Select a compatible Wan2.2 TI2V5B file.')
        for key in ('sdllm','sdclip2'):self.video_vars[key]=ctk.StringVar(value='')
        self.video_vars['sdloramult']=ctk.StringVar();ctk.CTkLabel(parents['Видео'],text='LoRA weights').grid(row=13,column=0,padx=8,sticky='w');ctk.CTkEntry(parents['Видео'],textvariable=self.video_vars['sdloramult'],width=180).grid(row=13,column=0,padx=(200,0),sticky='w')
        for _w in parents['Видео'].grid_slaves(row=13):
            _w.bind('<Enter>',lambda event:show_tooltip(event,'RU: Веса LoRA через пробел; один вес можно применить ко всем.\nEN: Space-separated LoRA weights; one weight can apply to all adapters.'));_w.bind('<Leave>',hide_tooltip)
        for group,name,label,row in [('Видео','video_upscaler','Video upscaler ONNX4x',16),('Видео','rife','RIFE model directory',19),('Фото','upscaler','Image upscaler ONNX4x',110),('Фото','face','GPEN model ONNX',113),('Фото','guard','SFace model ONNX',116),('Фото','detector','YuNet model ONNX',119),('Фото','restoration','Restore1x model ONNX',122)]:
            var=ctk.StringVar();self.post_vars[name]=var
            # Image upscaler uses the existing stock Upscaler field.
            if name=='upscaler':self.post_vars[name]=photo_vars['sdupscaler'];continue
            makefileentry(parents[group],label,'Select '+label,var,row=row,width=290,filetypes=[('ONNX','*.onnx')],dialog_type=2 if name=='rife' else 0,tooltiptxt='RU: Файлы вне комплекта импортируются внутрь; оригинал сохраняется. Только совместимые модели.\nEN: External files are imported into the kit; originals are preserved. Compatible models only.')
        rows={'Фото':140,'Видео':30,'Музыка':100,'Апскейл':160,'Лица':180,'Система':70}
        per_request={'photo_steps','photo_sampler','photo_scheduler','photo_cfg','photo_shift','video_frames','video_scheduler','video_upscale','video_faces','video_audio','video_fps','music_duration','music_steps','music_guidance','music_cot'}
        for key,group,label,kind,low,high in FIELDS:
            if key in per_request:continue
            parent=parents[group];row=rows[group];rows[group]+=1
            en=EN_LABELS[key];locale.catalog[en]=label;locale.reverse[label]=en
            if kind is bool:
                widget=ctk.CTkCheckBox(parent,text=en);widget.grid(row=row,column=0,columnspan=3,padx=8,pady=5,sticky='w')
            else:
                lab=ctk.CTkLabel(parent,text=en,wraplength=175,justify='left');lab.grid(row=row,column=0,padx=8,pady=4,sticky='w')
                widget=ctk.CTkOptionMenu(parent,values=list(kind),width=145) if isinstance(kind,tuple) else ctk.CTkEntry(parent,width=145)
                widget.grid(row=row,column=0,padx=(220,0),pady=4,sticky='w')
                self.tip(lab,key)
            self.widgets[key]=(widget,kind);self.tip(widget,key)
        ctk.CTkLabel(parents['Система'],textvariable=self.status,wraplength=370,justify='left').grid(row=80,column=0,columnspan=3,padx=8,pady=8,sticky='w')
        language=ctk.StringVar(value='Русский' if locale.language=='ru' else 'English');self.language=language
        ctk.CTkLabel(parents['Система'],text='Language').grid(row=72,column=0,padx=8,pady=6,sticky='w')
        choice=ctk.CTkOptionMenu(parents['Система'],values=['Русский','English'],variable=language,command=self.change_language);choice.grid(row=72,column=0,padx=(200,0),pady=6,sticky='w')
        choice.bind('<Enter>',lambda event:show_tooltip(event,'RU: Язык GUI и описаний API.\nEN: GUI and API-description language.'))
        self.service_vars={}
        for index,(key,label,boolean) in enumerate([('base_url','Helper / TTS / STT API',False),('helper_model','Helper model ID',False),('helper_enabled','Use helper model',True),('tts_enabled','Remote TTS',True),('stt_enabled','Remote STT',True),('female_voice','Female voice profile',False),('male_voice','Male voice profile',False),('english_female_voice','Female voice (EN)',False),('english_male_voice','Male voice (EN)',False),('voice_selection_verified','Voice profiles checked',True)]):
            parent=parents['Музыка'];row=70+index*3
            var=ctk.BooleanVar() if boolean else ctk.StringVar();self.service_vars[key]=var
            if boolean:w=ctk.CTkCheckBox(parent,text=label,variable=var);w.grid(row=row,column=0,padx=8,pady=5,sticky='w')
            else:
                ctk.CTkLabel(parent,text=label).grid(row=row,column=0,padx=8,pady=4,sticky='w');w=ctk.CTkEntry(parent,textvariable=var,width=235);w.grid(row=row+1,column=0,padx=8,pady=4,sticky='w')
            w.bind('<Enter>',lambda event:show_tooltip(event,'RU: Подключение общего сервера хелпера, речи и распознавания. Профили голоса закрепляются за персонажами; запрос задаёт speaker_id и таймкоды.\nEN: Shared helper/speech/transcription server. Voice profiles stay bound to speaker IDs; requests provide timestamps.'));w.bind('<Leave>',hide_tooltip)
            if key=='voice_selection_verified':w.bind('<Enter>',lambda event:show_tooltip(event,'RU: Подтвердите после прослушивания, что женский и мужской профили выбраны правильно. Смена адреса или имён голосов сбрасывает подтверждение.\nEN: Confirm after listening that female/male profiles are correct. Changing endpoint or voice names clears confirmation.'))
        for key in ('sfx_model_dir','sfx_threads'):self.service_vars[key]=ctk.StringVar()
        makefileentry(parents['Музыка'],'SFX model directory','Select SA3 SFX model directory',self.service_vars['sfx_model_dir'],row=105,width=290,dialog_type=2,tooltiptxt='RU: Папка комплекта SA3 Small-SFX GGUF: DiT, SAME, conditioner, T5Gemma и tokenizer.\nEN: SA3 Small-SFX GGUF directory containing DiT, SAME, conditioner, T5Gemma and tokenizer.')
        ctk.CTkLabel(parents['Музыка'],text='SFX CPU threads').grid(row=108,column=0,padx=8,sticky='w');ctk.CTkEntry(parents['Музыка'],textvariable=self.service_vars['sfx_threads'],width=70).grid(row=108,column=0,padx=(200,0),sticky='w')
        self.reset(self.configuration)
        for key in ('base_url','female_voice','male_voice','english_female_voice','english_male_voice'):self.service_vars[key].trace_add('write',lambda *_:self.service_vars['voice_selection_verified'].set(False))
        locale.apply()

    def tip(self,widget,key):
        ru,en=TIPS[key];widget.bind('<Enter>',lambda event:self.hover(event,'RU: '+ru+'\nEN: '+en));widget.bind('<Leave>',self.hide)
    def change_language(self,value):self.locale.set(value)
    def reset(self,configuration):
        self.configuration=configuration;values,_=load_values(self.root,configuration);p=gd(configuration)['kcpp_proxy'];models=selection(configuration,profile_data(configuration,self.root),p)
        for key,(w,kind) in self.widgets.items():
            if kind is bool:w.select() if values[key] else w.deselect()
            elif isinstance(kind,tuple):w.set(str(values[key]))
            else:w.delete(0,'end');w.insert(0,str(values[key]))
        self.seed_models=models
        from AudioServices import services
        self.audio_settings=services({'proxy':p})
        for key,var in self.service_vars.items():var.set(self.audio_settings[key])
        for key in IMAGE_FIELDS:self.photo_vars[key].set(models['photo'].get(key,''));self.video_vars[key].set(models['video'].get(key,''))
        for role,variables in [('photo',self.photo_vars),('video',self.video_vars)]:
            variables['sdlora'].set('|'.join(models[role]['sdlora']));variables['sdloramult'].set(' '.join(map(str,models[role]['sdloramult'])))
        for key in MUSIC_FIELDS:self.photo_vars[key].set(models['music'][key])
        for key,var in self.post_vars.items():var.set(models['post'][key])
        self.revision=hashlib.sha256((self.root/'Helper.kcpps').read_bytes()).hexdigest()
        self.status.set(str(self.source) if self.source else self.locale.text('Save a user .kcpps file or launch the current settings.'))
    def payload(self):
        values,_=load_values(self.root,self.configuration);values.update({key:bool(w.get()) if kind is bool else w.get() if isinstance(kind,tuple) else kind(w.get().replace(',','.')) for key,(w,kind) in self.widgets.items()});validate(values)
        models=json.loads(json.dumps(self.seed_models))
        for role,variables in [('photo',self.photo_vars),('video',self.video_vars)]:
            models[role]={**{k:variables[k].get().strip() for k in IMAGE_FIELDS},'sdlora':[s for s in variables['sdlora'].get().split('|') if s],'sdloramult':[float(v) for v in variables['sdloramult'].get().replace('|',' ').split()]}
        models['music']={k:self.photo_vars[k].get().strip() for k in MUSIC_FIELDS};models['post']={k:v.get().strip() for k,v in self.post_vars.items()}
        services={**self.audio_settings,**{key:var.get() for key,var in self.service_vars.items()}}
        services['sfx_threads']=int(services['sfx_threads'])
        return dict(values=values,models=models,revision=self.revision,configuration=self.configuration,language=self.locale.language,services=services)
    def run(self,payload):
        self.status.set(self.locale.text('Applying configuration…'))
        def worker():
            try:
                p=subprocess.run([str(self.root/'runtime/python/python.exe'),'-I','-B',str(self.root/'tools/MediaNativeGUI.py'),'--apply'],input=json.dumps(payload),capture_output=True,text=True,encoding='utf-8',cwd=self.root,timeout=900,creationflags=subprocess.CREATE_NO_WINDOW)
                if p.returncode:raise RuntimeError(p.stderr.strip()[-1400:] or p.stdout.strip()[-1400:])
                answer=json.loads(p.stdout.splitlines()[-1])
                def done():
                    if answer.get('saved_file'):
                        self.source=Path(answer['saved_file']);self.configuration=answer['configuration'];self.status.set(self.locale.text('Configuration saved: ')+str(self.source))
                    else:self.revision=answer['revision'];self.configuration=read(self.root/'Helper.kcpps');self.status.set(self.locale.text('Applied. Image model is GPU-resident.'))
                    state=self.root/'logs/active-user-config.json';state.parent.mkdir(exist_ok=True);state.write_text(json.dumps({'path':str(self.source) if self.source else None})+'\n',encoding='utf-8')
                self.parents['Система'].after(0,done)
            except Exception as error:
                message=str(error)
                def failed():
                    self.status.set(message)
                    from tkinter.messagebox import showerror
                    showerror('KoboldCpp',message)
                self.parents['Система'].after(0,failed)
        threading.Thread(target=worker,daemon=True).start()
    def launch(self):
        try:self.run(self.payload())
        except Exception as error:
            from tkinter.messagebox import showerror
            showerror('KoboldCpp',str(error))
    def save_dialog(self):
        path=self.dialogs['save'](title='Save configuration',filetypes=[('KoboldCpp','*.kcpps')],defaultextension='.kcpps',initialdir=str(self.source.parent if self.source else self.root),initialfile=self.source.name if self.source else 'my-media.kcpps')
        if path:
            try:payload=self.payload();payload['export_file']=path;self.run(payload)
            except Exception as error:
                from tkinter.messagebox import showerror
                showerror('KoboldCpp',str(error))
    def load_dialog(self):
        path=self.dialogs['open'](title='Load configuration',filetypes=[('KoboldCpp','*.kcpps')])
        if path:
            try:
                configuration=read(path);profile_data(configuration,self.root);self.source=Path(path);self.reset(configuration);self.locale.set(gd(configuration)['kcpp_proxy'].get('ui_language','ru'))
            except Exception as error:
                from tkinter.messagebox import showerror
                showerror('KoboldCpp',str(error))

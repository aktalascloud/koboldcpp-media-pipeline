"""RU/EN display localization; technical values and API keys are never translated."""
import json
from pathlib import Path

BASE=Path(__file__).resolve().parent
CORE={'Quick Launch':'Запуск','Hardware':'Оборудование','Context':'Контекст','Loaded Files':'Модели','Network':'Сеть','Horde Worker':'Horde','Image Gen':'Изображения','Audio':'Аудио','Video':'Видео','Agent':'Агент','Admin':'Управление','Extra':'Дополнительно','Launch':'Запустить','Save Config':'Сохранить','Load Config':'Загрузить','Get Help':'Справка','Update':'Обновить','Browse':'Выбрать','Language':'Язык','Model':'Модель','Settings':'Настройки'}

CORE.update({'Video model':'Модель видео','Text encoder':'Текстовый энкодер','Video VAE':'VAE видео','Video LoRAs':'LoRA видео','LoRA weights':'Веса LoRA','Video upscaler ONNX4x':'Апскейлер видео ONNX4×','RIFE model directory':'Папка модели RIFE','Image upscaler ONNX4x':'Апскейлер фото ONNX4×','GPEN model ONNX':'Модель GPEN ONNX','SFace model ONNX':'Модель SFace ONNX','YuNet model ONNX':'Модель YuNet ONNX','Restore1x model ONNX':'Восстановление1× ONNX','Image Model:':'Модель:','Image LLM:':'Энкодер:','Clip-1 File:':'CLIP-1:','Clip-2 File:':'CLIP-2:','Image VAE:':'VAE:','Audio VAE:':'Аудио VAE:','ImgThreads:':'Потоки:','ImgGPU:':'GPU:','Compress Weights:':'Сжатие:','Clamp Resolution (Hard):':'Лимит размера:','(Soft):':'Мягкий:','Runtime LoRAs':'LoRA по запросу','Multiplier:':'Веса:','Image LoRAs:':'LoRA:','Upscaler:':'Апскейлер:','SD Flash Attention':'Flash Attention SD','MusicLLM:':'Музыка LLM:','MusicVAE:':'Музыка VAE:','MusicEmbeds:':'Эмбеддинги:','MusicDiffuser:':'Диффузия:','Save configuration':'Сохранить конфигурацию','Load configuration':'Загрузить конфигурацию','Save a user .kcpps file or launch the current settings.':'Сохраните любой пользовательский.kcpps или запустите текущие настройки.','Applying configuration…':'Применение конфигурации…','Applied. Image model is GPU-resident.':'Применено. Фото-модель загружена в GPU.','Configuration saved: ':'Конфигурация сохранена: '})

CORE.update({'Video upscaler ONNX4x':'Апскейлер4× ONNX','RIFE model directory':'Модель RIFE (папка)','Text encoder':'Энкодер текста','Video LoRAs':'LoRA видео','LoRA weights':'Веса LoRA','GPEN model ONNX':'GPEN (ONNX)','SFace model ONNX':'SFace (ONNX)','YuNet model ONNX':'YuNet (ONNX)','Restore1x model ONNX':'Восст.1× (ONNX)','Cache-DiT threshold':'Кэш фото (порог)','Video cache threshold':'Кэш видео (порог)','Native VRAM limit, MiB':'VRAM, МиБ','GPEN blend, %':'GPEN, %','SFace minimum similarity':'Сходство SFace','YuNet resolution':'Размер YuNet','Maximum faces':'Макс. лиц','Normal automatic4x upscale':'Авто4×: обычный','High automatic4x upscale':'Авто4×: High','Upscaler tile (0=auto)':'Тайл (0=авто)','Tile overlap':'Перекрытие','Image editing (img2img)':'Редакт. img2img','Start at Windows logon':'Автозапуск Windows'})

CORE.update({'Helper / TTS / STT API':'Хелпер / TTS / STT API','Helper model ID':'ID модели хелпера','Use helper model':'Использовать хелпер','Remote TTS':'Внешний TTS','Remote STT':'Внешний STT','Female voice profile':'Женский голос (профиль)','Male voice profile':'Мужской голос (профиль)'})

CORE.update({'Female voice profile':'Голос Ж (RU)','Male voice profile':'Голос М (RU)','Female voice (EN)':'Голос Ж (EN)','Male voice (EN)':'Голос М (EN)'})

CORE.update({'Voice profiles checked':'Голоса проверены','Model Offload':'Выгрузка в RAM','VAE dev:':'VAE:','CLIP dev:':'CLIP:','Wan480p/Pro, optional720p faces/RIFE; timed music, SFX and speech mixed into MP4. No lip-sync.':'Wan480p/Pro, лица/RIFE и720p; музыка, эффекты и речь по таймкодам в MP4. Без синхронизации губ.'})

class Localizer:
    def __init__(self,root,language='ru'):
        self.root=root;self.language=language;self.catalog=dict(CORE)
        path=BASE/'gui-ru.json'
        if path.exists():self.catalog.update(json.loads(path.read_text(encoding='utf-8')))
        self.catalog.update(CORE)
        self.reverse={v:k for k,v in self.catalog.items()};self.originals={}
    def text(self,value,language=None):
        if not isinstance(value,str):return value
        language=language or self.language
        if language=='en':return self.reverse.get(value,value)
        if value.strip() in CORE:return CORE[value.strip()]
        if value in self.catalog:return self.catalog[value]
        stripped=value.strip()
        if stripped in self.catalog:return self.catalog[stripped]
        for key in sorted(self.catalog,key=len,reverse=True):
            if len(key)>18 and value.startswith(key):return self.catalog[key]+value[len(key):]
        return value
    def tooltip(self,value):
        if '\nEN: ' in value and value.startswith('RU: '):
            ru,en=value[4:].split('\nEN: ',1)
            return value if self.language=='ru' else 'EN: '+en+'\nRU: '+ru
        return 'RU: '+self.text(value,'ru')+'\nEN: '+self.text(value,'en')
    def apply(self,widget=None):
        widget=widget or self.root
        try:
            current=widget.cget('text')
            if isinstance(current,str) and current:
                previous=self.originals.get(widget)
                if previous is None or current not in (previous,self.text(previous,'ru'),self.text(previous,'en')):self.originals[widget]=current
                widget.configure(text=self.text(self.originals[widget]))
        except Exception:pass
        for child in widget.winfo_children():self.apply(child)
    def set(self,value):
        self.language='ru' if value in ('Русский','ru') else 'en';self.apply()
    def dialog(self,function):
        def wrapped(*args,**kwargs):
            args=tuple(self.text(v) if isinstance(v,str) else v for v in args)
            for key in ('title','message'):
                if key in kwargs:kwargs[key]=self.text(kwargs[key])
            return function(*args,**kwargs)
        return wrapped

def translate_api(value,language='ru'):
    if language!='ru':return value
    catalog=dict(CORE);path=BASE/'gui-ru.json'
    if path.exists():catalog.update(json.loads(path.read_text(encoding='utf-8')))
    def walk(item,key=''):
        if isinstance(item,dict):return {k:walk(v,k) for k,v in item.items()}
        if isinstance(item,list):return [walk(v,key) for v in item]
        if isinstance(item,str) and key in ('message','detail','description','summary','warning','hint','textinfo'):return catalog.get(item,item)
        return item
    return walk(value)

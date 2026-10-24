"""Single-Helper A1111/OpenAI photo pipeline: configured Helaman2x/4x SR, local faces and MP3.

Configuration lives in Helper.kcpps / gendefaults / kcpp_proxy. Native Kobold
continues to run Z-Image and music; this process supplies optional postprocessing.
"""
import argparse
from contextlib import nullcontext,contextmanager
import base64
from collections import deque
import gc
import gzip
import hashlib
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import io
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import os
import re
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from PIL import Image,PngImagePlugin
from RuntimePaths import ROOT,asset
from DetailerProxy import FaceDetailer
from OnnxUpscale import Upscaler
from PhotoUpscale import PhotoUpscaler,PhotoBlendUpscaler
from FastFaceRestore import Restorer,FeatureGuard
from FastDenoise import denoise
from ToneGuard import preserve_tones
from Resolution import choose_resolution
from ImageEdits import EDIT_PATHS,ImageEditError,prepare_edit
from ImageModes import ImageModeError,resolve_image_mode,fit_edit_pair
from HelamanUpscale import HelamanUpscaler,configured_output_scale as helaman_output_scale
from VideoService import VideoService,VideoServiceError,VIDEO_JSON_PATHS,VIDEO_MEDIA_PREFIX,is_video_request
from BackendSupervisor import SupervisorError
from FaceSizePolicy import scale_face_options
from PhotoRestoration import restore_once,matching_marker as matching_restoration_marker,attach_marker as attach_restoration_marker,prewarm_model as prewarm_restoration_model
from ImageBudget import ImageBudgetError,apply_image_gpu_budget,prewarm_image_budget
from NativeVideo import request_json_deadline
from PhotoCapture import capture_stage

VERSION='3.0-photo-video-portable'
IMAGE_FIELDS=('steps','cfg_scale','sampler_name','scheduler','eta','flow_shift','clip_skip','cache_mode','cache_options')
SR_PATHS=('/sdapi/v1/upscale','/sdapi/v1/extra-single-image')
IMAGE_PATHS=('/sdapi/v1/txt2img','/sdapi/v1/img2img')
OPENAI_IMAGE_PATHS=('/v1/images/generations','/images/generations')
MUSIC_PATHS=('/api/extra/music/generate','/api/extra/music/prepare')
LOG=logging.getLogger('KoboldProxy')

def upscale_api_scale(config):
    opts=config['proxy']['upscaler']
    return helaman_output_scale(opts) if opts.get('runtime')=='helaman_atd' else 2

def sr_api_response(final,report,config,requested_scale=None):
    opts=config['proxy']['upscaler'];scale=upscale_api_scale(config)
    name=opts.get('name',str(scale)+'x upscaler')
    answer=dict(image=image_encode(final,marker=report.get('detailer',{}).get('marker')),
                html_info=f'<p>Postprocess upscale by: {float(scale):.1f}, Postprocess upscaler: {name}</p>',kcpp_proxy=report)
    if opts.get('runtime')=='helaman_atd':
        report['upscaling_resize']=scale
        report['requested_upscaling_resize']=requested_scale
        answer['upscaling_resize']=scale
    return answer

def settings(path):
    data=path.read_bytes();helper=json.loads(data.decode('utf-8-sig'))
    defaults=helper.get('gendefaults',{});defaults=json.loads(defaults) if isinstance(defaults,str) else defaults
    proxy=defaults.get('kcpp_proxy')
    if not isinstance(proxy,dict) or not proxy.get('enabled'):raise ValueError('Helper does not enable kcpp_proxy')
    for section,key in (('upscaler','model'),('upscaler','detail_model'),('detailer','model'),('detailer','feature_guard_model'),('photo_restoration','model')):
        if proxy.get(section,{}).get(key):proxy[section][key]=asset(proxy[section][key],path.resolve().parent)
    front=int(proxy.get('port',5001));back=int(helper.get('port',helper.get('port_param',5003)))
    if not 1<=front<=65535 or not 1<=back<=65535 or front==back:raise ValueError('Proxy and native backend need different valid ports')
    mode=proxy.get('upscaler',{}).get('mode','onnx')
    if mode not in ('onnx','native'):raise ValueError('Unsupported upscaler mode')
    if mode=='onnx' and not Path(proxy['upscaler']['model']).is_file():raise ValueError('Configured ONNX upscaler is absent')
    if proxy['upscaler'].get('runtime')=='photo_blend' and not Path(proxy['upscaler'].get('detail_model','')).is_file():raise ValueError('Configured photo detail upscaler is absent')
    if proxy.get('photo_restoration',{}).get('enabled') and not Path(proxy['photo_restoration'].get('model','')).is_file():raise ValueError('Configured Gater restoration model is absent')
    return dict(helper=helper,defaults=defaults,proxy=proxy,port=front,backend='http://127.0.0.1:'+str(back),helper_sha256=hashlib.sha256(data).hexdigest())
def image_decode(value):
    im=Image.open(io.BytesIO(base64.b64decode(value.split(',')[-1])))
    return im.convert('RGBA' if 'A' in im.getbands() else 'RGB')
def image_encode(image,parameters=None,marker=None):
    out=io.BytesIO();tags=PngImagePlugin.PngInfo()
    for key,value in image.info.items():
        if key=='kcpp_proxy_detailer' and marker:continue
        if isinstance(value,str) and len(value)<32768:tags.add_text(key,value)
    if parameters:tags.add_text('parameters',parameters)
    if marker:
        marker={**marker,'version':VERSION,'rgb_sha256':hashlib.sha256(image.convert('RGB').tobytes()).hexdigest()}
        tags.add_text('kcpp_proxy_detailer',json.dumps(marker,separators=(',',':')))
    image.save(out,format='PNG',pnginfo=tags)
    return base64.b64encode(out.getvalue()).decode()
def face_signature(options,legacy=False,include_policy=False):
    canonical=dict(options)
    reference={key:canonical.pop('_reference_'+key,None) for key in ('minimum_face','maximum_face')}
    for key in ('auto_size','reference_dimensions'):canonical.pop(key,None)
    if not include_policy:canonical.pop('after_upscale',None)
    scale=float(canonical.pop('_pixel_scale',1))
    if scale<=0:raise ValueError('Invalid face pixel scale')
    for key,default in (('minimum_face',32),('maximum_face',160)):
        canonical[key]=round(float(reference[key] if reference[key] is not None else float(canonical.get(key,default))/scale),6)
    if not legacy:
        for key in ('model','feature_guard_model'):
            if canonical.get(key):
                path=Path(canonical[key]).resolve()
                canonical[key]=path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path.name
    return hashlib.sha256(json.dumps(canonical,sort_keys=True).encode()).hexdigest()[:16]
def matching_face_marker(image,options):
    try:
        marker=json.loads(image.info.get('kcpp_proxy_detailer',''))
        signatures={face_signature(candidate,legacy=legacy,include_policy=include_policy)
                    for candidate in (options,{**options,'after_upscale':False},{**options,'after_upscale':True})
                    for legacy in (False,True) for include_policy in (False,True)}
        if marker.get('signature') in signatures and int(marker.get('faces',0))>0 and marker.get('rgb_sha256')==hashlib.sha256(image.convert('RGB').tobytes()).hexdigest():return marker
    except (ValueError,TypeError,AttributeError):pass
    return None
def request(url,body=None,headers=None,method=None):
    headers={k:v for k,v in (headers or {}).items() if k.lower() not in ('host','content-length','connection','transfer-encoding')}
    headers['Accept-Encoding']='identity'
    req=urllib.request.Request(url,body,headers,method=method)
    try:
        with urllib.request.urlopen(req,timeout=7200) as response:return response.status,dict(response.headers),response.read()
    except urllib.error.HTTPError as error:return error.code,dict(error.headers),error.read()
def request_json(url,payload,headers=None):
    status,returned,body=request(url,json.dumps(payload).encode('utf-8'),{**(headers or {}),'Content-Type':'application/json'},'POST')
    if returned.get('Content-Encoding','').lower()=='gzip':body=gzip.decompress(body)
    answer=json.loads(body)
    if not 200<=status<300:raise RuntimeError('Native backend '+str(status)+': '+str(answer)[:300])
    return answer

class Pipeline:
    def __init__(self,helper,photo_backend_lease=None):
        self.helper=helper.resolve();self.lock=threading.RLock();self.state_lock=threading.Lock();self.active=None
        self.detailer=None;self.detailer_key=None;self.upscaler=None;self.upscaler_key=None;self.restorer=None;self.restorer_key=None;self.guard=None;self.started=time.time();self.completed=0
        self.recent_detail=deque(maxlen=16)
        self.face_prewarm=None
        self.image_budget_prewarm=None
        self.restoration_prewarm=None
        self.photo_backend_lease=photo_backend_lease
        self.upscale_vram_lease=None
    def config(self):return settings(self.helper)
    def update(self,**values):
        with self.state_lock:
            if self.active is not None:self.active.update(values)
    def state(self):
        with self.state_lock:return dict(self.active) if self.active else None
    def begin(self,key,kind):
        with self.state_lock:self.active=dict(request_key=key,kind=kind,stage='base',started=time.time())
    def finish(self):
        with self.state_lock:self.active=None;self.completed+=1
    def release_upscaler(self):
        existed=bool(self.upscaler)
        if existed:self.upscaler.close()
        self.upscaler=None;self.upscaler_key=None
    def face_engine(self,backend,options=None):
        options=options if options is not None else self.config()['proxy'].get('detailer',{})
        key=(int(options.get('detector_resolution',640)),float(options.get('detector_score_threshold',.82)),float(options.get('detector_nms_threshold',.3)),int(options.get('detector_top_k',5000)))
        if self.detailer is None or self.detailer_key!=key:
            self.detailer=FaceDetailer(backend,*key);self.detailer_key=key
        self.detailer.backend=backend;return self.detailer
    def release_restorer(self):
        if self.restorer:self.restorer.close()
        self.restorer=None;self.restorer_key=None
    def release_gpu(self):self.release_upscaler();self.release_restorer()
    def prewarm_cpu_faces(self,config):
        opts=config['proxy'].get('detailer',{})
        if not config['proxy'].get('prewarm_cpu_faces',False) or not opts.get('enabled') or opts.get('mode')!='gpen' or opts.get('provider')!='openvino':return
        start=time.perf_counter()
        try:
            detector=self.face_engine(config['backend'],opts)
            if opts.get('feature_guard',True) and not self.guard:self.guard=FeatureGuard(opts.get('feature_guard_model'))
            self.restorer=Restorer(opts['model'],'openvino',detector,self.guard);self.restorer_key=(opts['model'],'openvino')
            self.face_prewarm=dict(ok=True,seconds=round(time.perf_counter()-start,4),provider='OpenVINO CPU',compiled_cache_used=getattr(self.restorer.session,'loaded_from_cache',False),model_sha256=self.restorer.metadata['model_sha256'])
            LOG.info('CPU face model preloaded during native startup: %s',self.face_prewarm)
        except Exception as error:
            self.release_restorer();self.face_prewarm=dict(ok=False,error=str(error));LOG.exception('CPU face preload failed;lazy face stage remains available')
    def profile(self,payload,config):
        if config['proxy'].get('enforce_image_profile',True):
            for key in IMAGE_FIELDS:
                if key in config['defaults']:payload[key]=config['defaults'][key]
            nested=payload.get('kcpp_extra_args',{})
            if isinstance(nested,dict) and isinstance(nested.get('params'),dict):
                for key in IMAGE_FIELDS:
                    if key in nested['params'] and key in config['defaults']:nested['params'][key]=config['defaults'][key]
                for key in ('shifted_timestep','distilled_guidance','extra_sample_args'):nested['params'].pop(key,None)
            for key in ('shifted_timestep','distilled_guidance','extra_sample_args'):payload.pop(key,None)
        payload['eta']=0
        trigger=str(config['proxy'].get('lora_trigger') or '').strip()
        if trigger:
            prompt=str(payload.get('prompt') or '')
            pattern=r'(?<!\w)'+re.escape(trigger)+r'(?!\w)'
            if not re.search(pattern,prompt,flags=re.IGNORECASE):
                payload['prompt']=trigger+(', '+prompt if prompt else '')
        return payload
    def process_faces(self,image,options,base,config):
        if not options or not options.get('enabled',True):return image,dict(processed_faces=0,seconds=0,disabled=True)
        stage_start=time.perf_counter()
        options,face_size_policy=scale_face_options(options,image.size)
        signature=face_signature(options)
        original_marker=matching_face_marker(image,options)
        if original_marker:return image,dict(processed_faces=0,seconds=0,already_processed=True,outside_masks_exact=True,marker=original_marker,face_size_policy=face_size_policy)
        self.release_upscaler()
        mode=config['proxy'].get('detailer',{}).get('mode','diffusion')
        if mode=='diffusion':
            self.release_restorer();engine=self.face_engine(config['backend'],options)
        else:
            detector=self.face_engine(config['backend'],options)
            eligible=detector.detect(image,int(options.get('minimum_face',32)),int(options.get('maximum_face',160)))
            if not eligible:
                return image,dict(processed_faces=0,attempted_faces=0,seconds=0,
                    processing_seconds=round(time.perf_counter()-stage_start,4),
                    skipped='No eligible small faces',outside_masks_exact=True,face_size_policy=face_size_policy)
            selected=config['proxy']['detailer'];model=selected['model'];provider=selected.get('provider','directml');key=(model,provider)
            self.update(stage='face_restorer',face=0,total_faces=1)
            if selected.get('feature_guard',True) and not self.guard:self.guard=FeatureGuard(selected.get('feature_guard_model'))
            if self.restorer_key!=key:
                self.release_restorer();self.restorer=Restorer(model,provider,detector,self.guard);self.restorer_key=key
            engine=self.restorer
        kwargs={} if mode=='diffusion' else dict(detected_faces=eligible)
        final,report=engine.refine(image,options,base,progress=lambda event:self.update(**event),**kwargs);report['processing_seconds']=round(time.perf_counter()-stage_start,4);report['face_size_policy']=face_size_policy
        if report['processed_faces']:
            report['marker']=dict(version=VERSION,signature=signature,faces=report['processed_faces'],passes=1)
        return final,report
    def upscale(self,image,config):
        opts=config['proxy']['upscaler'];mode=opts.get('mode','onnx');started=time.perf_counter()
        if not config['proxy'].get('retain_face_session_for_images',False):self.release_restorer()
        self.update(stage='upscaler')
        if opts.get('runtime')=='helaman_atd':
            self.release_upscaler()
            engine=HelamanUpscaler(opts)
            try:final,info=engine.upscale(image)
            finally:engine.close()
        elif mode=='native':
            self.release_upscaler()
            answer=request_json(config['backend']+'/sdapi/v1/upscale',dict(image=image_encode(image),upscaling_resize=2))
            final=image_decode(answer['image']);native_dimensions=list(final.size)
            if final.width not in (image.width*2,image.width*4) or final.height*image.width!=final.width*image.height:
                raise RuntimeError('Native upscaler did not return a real2x/4x image')
            if final.size!=(image.width*2,image.height*2):final=final.resize((image.width*2,image.height*2),Image.Resampling.LANCZOS)
            info=dict(provider='native',native_dimensions=native_dimensions,model=opts.get('name','Native ESRGAN'))
        else:
            tile=int(opts.get('tile',0))
            if not tile and image.width*image.height>int(opts.get('max_whole_pixels',800000)):tile=512
            provider=opts.get('provider','directml');scale=int(opts.get('native_scale',2));padding=int(opts.get('padding',32));blend=opts.get('runtime')=='photo_blend';photo=opts.get('runtime')=='photo' or scale!=2 or blend;key=(str(opts['model']),provider,tile,scale,padding,photo,opts.get('detail_model'),float(opts.get('blend_amount',.5)),bool(opts.get('release_between_models',True)))
            def engine_for(selected_provider,selected_tile):
                if blend:return PhotoBlendUpscaler(opts['model'],opts['detail_model'],opts.get('blend_amount',.5),selected_provider,selected_tile,padding,opts.get('release_between_models',True))
                return PhotoUpscaler(opts['model'],scale,selected_provider,selected_tile,padding) if photo else Upscaler(opts['model'],selected_provider,selected_tile)
            try:
                if self.upscaler_key!=key:
                    self.release_upscaler()
                    self.upscaler=engine_for(provider,tile)
                    self.upscaler_key=key
                final,info=self.upscaler.upscale(image)
            except Exception:
                self.release_upscaler()
                if not opts.get('cpu_fallback',True):raise
                engine=engine_for('openvino',256) if photo and opts.get('cpu_fallback')=='openvino' else engine_for('cpu',256 if photo else 512)
                try:final,info=engine.upscale(image);info['fallback']=True
                finally:engine.close()
            info.update(model=opts.get('name',Path(opts['model']).stem),model_sha256=self.upscaler.metadata['model_sha256'] if self.upscaler else None)
        info['seconds']=round(time.perf_counter()-started,4)
        return final,info
    def finish_photo(self,image,options,base,config,upscale=False):
        options=dict(options or {})
        report=dict(base_rgb_sha256=hashlib.sha256(image.convert('RGB').tobytes()).hexdigest(),input_dimensions=list(image.size),native_dimensions=list(image.size))
        # A matching marker prevents repeating the same restoration before SR.
        # The selected profile skips restoration after the Helaman pass.
        prior=matching_face_marker(image,options) if options.get('enabled',True) else None
        before_upscale=bool(upscale and config['proxy'].get('faces_before_upscale',False))
        repeat_after_upscale=bool(upscale and config['proxy'].get('repeat_faces_after_upscale',False))
        first_marker=prior
        restoration_options=config['proxy'].get('photo_restoration',{})
        restoration_marker=matching_restoration_marker(image,restoration_options)
        final=image;scale=1
        if before_upscale:
            try:final,before=self.process_faces(final,options,base,config)
            except Exception as error:
                before=dict(error=str(error),fallback='original image',processed_faces=0)
                LOG.exception('Pre-upscale face stage failed; retained original')
            report['detailer_before_upscale']=before
            first_marker=before.get('marker',prior)
            capture_stage(config,base.get('genkey'),'faces',final)
        if upscale:
            if callable(self.upscale_vram_lease):
                with self.upscale_vram_lease(config) as placement:
                    final,restoration,restoration_marker=restore_once(final,restoration_options,restoration_marker)
                    report['restoration']=restoration
                    capture_stage(config,base.get('genkey'),'processed',final)
                    final,up=self.upscale(final,config)
                    placement['restoration_in_exclusive_gpu_lease']=True
                    up['vram_policy']=placement
            else:
                final,restoration,restoration_marker=restore_once(final,restoration_options,restoration_marker)
                report['restoration']=restoration
                capture_stage(config,base.get('genkey'),'processed',final)
                final,up=self.upscale(final,config)
            report['upscaler']=up
            scale=final.width/image.width
        local={**options,'minimum_face':round(int(options.get('minimum_face',32))*scale),'maximum_face':round(int(options.get('maximum_face',160))*scale),'_pixel_scale':scale}
        if upscale and not repeat_after_upscale:
            self.release_upscaler()
            detail=dict(processed_faces=0,attempted_faces=0,seconds=0,already_processed=True,
                        source_faces=int((first_marker or {}).get('faces',0)),outside_masks_exact=True,marker=first_marker,
                        skipped='Selected Helaman profile applies faces only before SR; no repeated GPEN after SR')
        else:
            try:final,detail=self.process_faces(final,local,base,config)
            except Exception as error:
                detail=dict(error=str(error),fallback='original image',processed_faces=0)
                LOG.exception('Face stage failed; retained original')
        if repeat_after_upscale:
            detail['repeat_after_upscale']=True
            detail['input_already_restored']=bool(prior)
            detail['pre_upscale_face_pass_available']=bool(first_marker)
            if detail.get('processed_faces'):
                detail['marker']['passes']=int(first_marker.get('passes',1))+1 if first_marker else 1
        report['detailer']=detail
        if not upscale:
            final,restoration,restoration_marker=restore_once(final,restoration_options,restoration_marker)
            report['restoration']=restoration
        if config['proxy'].get('denoise',{}).get('enabled',False):
            final,noise=denoise(final,config['proxy']['denoise']);report['denoise']=noise
        if config['proxy'].get('preserve_tones',False):
            final,tone=preserve_tones(image,final,float(config['proxy'].get('tone_sigma',20)));report['tone_guard']=tone
        final=attach_restoration_marker(final,restoration_marker)
        report['output_dimensions']=list(final.size)
        return final,report
    def generate(self,path,payload,headers,edit_context=None,request_mode=None):
        start=time.perf_counter()
        mode=request_mode or resolve_image_mode(payload,self.config(),'edit' if path=='/sdapi/v1/img2img' else 'generation')
        config=mode.config
        if request_mode is None:payload=mode.payload
        key=payload.get('genkey','')
        if path=='/sdapi/v1/img2img' and edit_context is None:
            initial=payload.get('init_images')
            if not isinstance(initial,list) or len(initial)!=1 or not isinstance(initial[0],str):
                raise ImageModeError('Provide exactly one init_images image.','init_images','single_image_required')
            image=image_decode(initial[0]);mask=image_decode(payload['mask']) if payload.get('mask') else None
            requested=(payload['width'],payload['height']) if 'width' in payload and 'height' in payload else None
            if ('width' in payload)!=('height' in payload):
                raise ImageModeError('Provide width and height together.','size','invalid_dimensions')
            prepared,prepared_mask,geometry=fit_edit_pair(image,mask,config,requested)
            payload.update(init_images=[image_encode(prepared)],width=prepared.width,height=prepared.height,resize_mode=0)
            if prepared_mask is not None:payload['mask']=image_encode(prepared_mask)
            mode.metadata['geometry']=geometry
        option=payload.pop('kcpp_detailer',None)
        requested_hr=config['proxy'].get('allow_generation_upscale',True) and (config['proxy'].get('always_upscale',False) or bool(payload.get('enable_hr',config['defaults'].get('enable_hr',False))))
        if edit_context:requested_hr=False
        payload.pop('kcpp_proxy',None);payload=self.profile(payload,config);payload['enable_hr']=False
        if edit_context:
            payload['steps']=edit_context['steps']
            edit_context['effective_prompt']=payload.get('prompt','')
        if path=='/sdapi/v1/txt2img' and not mode.metadata['geometry_applied'] and config['proxy'].get('fixed_native_resolution',False):
            width=int(payload.get('width',config['defaults'].get('width',704)));height=int(payload.get('height',config['defaults'].get('height',960)))
            if config['proxy'].get('native_pixel_budget'):
                width,height=choose_resolution(width,height,int(config['proxy']['native_pixel_budget']),int(config['proxy'].get('max_native_edge',1280)),alignment=int(config['proxy'].get('native_alignment',32)))
                payload.update(width=width,height=height)
            else:
                small=min(config['defaults']['width'],config['defaults']['height']);large=max(config['defaults']['width'],config['defaults']['height'])
                payload.update(width=large if width>height else small,height=small if width>height else large)
        elif path=='/sdapi/v1/img2img':payload.update(cache_mode='disabled',cache_options='')
        if payload.get('mask'):
            config['proxy']['photo_restoration']={**config['proxy'].get('photo_restoration',{}),'enabled':False}
            mode.metadata['restoration_skipped']='Masked edit preserves pixels outside the selected region'
        budget=apply_image_gpu_budget(payload,config,operation='edit' if path=='/sdapi/v1/img2img' else 'generation',
                                      image_prepared=path=='/sdapi/v1/img2img',root=ROOT)
        payload,config=budget.payload,budget.config
        mode.payload,mode.config=payload,config
        mode.metadata.update(native_dimensions=budget.report['actualDimensions'],gpu_budget=budget.report,
                             native_pixel_budget=int(payload['width'])*int(payload['height']),max_native_edge=max(int(payload['width']),int(payload['height'])))
        if config['proxy'].get('retain_face_session_for_images',False):self.release_upscaler()
        else:self.release_gpu()
        self.begin(key,'image')
        try:
            if not callable(self.photo_backend_lease):
                raise ImageModeError('Photo supervisor is not connected.','kcpp_quality','backend_profile_unavailable',503)
            # The supervisor holds its global Native/GPU lease through postprocessing.
            with self.photo_backend_lease(mode.native_profile,config) as active:
                if not isinstance(active,dict) or active.get('native_profile')!=mode.native_profile or not active.get('helper_sha256') or not active.get('backend'):
                    raise ImageModeError('Supervisor did not verify the requested photo profile.','kcpp_quality','backend_profile_unavailable',503)
                config['backend']=active['backend']
                tick=time.perf_counter();answer=request_json(config['backend']+path,payload,headers);base_seconds=time.perf_counter()-tick
                try:info=json.loads(answer.get('info','{}'))
                except (ValueError,TypeError):info={}
                detail_opts=dict(config['proxy'].get('detailer',{}))
                if option is False or (payload.get('mask') and option is None):detail_opts['enabled']=False
                elif isinstance(option,dict):detail_opts.update(option);detail_opts.setdefault('enabled',True)
                reports=[];images=[]
                for index,encoded in enumerate(answer.get('images',[])):
                    image=image_decode(encoded)
                    expected_size=(int(payload['width']),int(payload['height']))
                    if image.size!=expected_size:
                        raise RuntimeError('Native clamped the requested geometry: expected '+str(expected_size)+', received '+str(image.size))
                    actual_seed=info.get('all_seeds',[info.get('seed',payload.get('seed',104729))])
                    seed=actual_seed[min(index,len(actual_seed)-1)] if actual_seed else 104729
                    capture_stage(config,key,'raw',image)
                    final,report=self.finish_photo(image,detail_opts,{'seed':seed,'genkey':key},config,upscale=requested_hr)
                    changed=report.get('detailer',{}).get('processed_faces',0)>0 or requested_hr or report.get('denoise',{}).get('applied',False) or report.get('restoration',{}).get('applied',False)
                    parameters=(info.get('infotexts') or [''])[0]
                    images.append(image_encode(final,parameters,report.get('detailer',{}).get('marker')) if changed else encoded)
                    reports.append(report)
                answer['images']=images;answer['kcpp_proxy']=dict(version=VERSION,base_seconds=round(base_seconds,3),postprocessing=reports,total_seconds=round(time.perf_counter()-start,3),profile={k:payload.get(k) for k in IMAGE_FIELDS})
                answer['kcpp_proxy']['gpu_budget']=budget.report
                answer['kcpp_proxy']['image_mode']={**mode.metadata,'active_profile':active['native_profile'],'active_helper_sha256':active['helper_sha256'],**{key:active.get(key) for key in ('expected_image_quantization','actual_image_quantization','quantization_confirmed','quantization_confirmation')}}
                LOG.info(json.dumps(dict(kind='image',**answer['kcpp_proxy']),ensure_ascii=False))
                return answer
        finally:self.finish()

def serve(helper,photo_backend_lease=None,backend_supervisor=None):
    pipeline=Pipeline(helper,photo_backend_lease);initial=pipeline.config();stop=threading.Event()
    videos=VideoService(backend_supervisor,ROOT,request_json_deadline,before_native=pipeline.release_gpu,
        public_base_url=initial['proxy'].get('video_public_base_url',''),deadline_seconds=900) if backend_supervisor else None
    original_photo_lease=pipeline.photo_backend_lease
    music_request_serial = [0]
    @contextmanager
    def checked_photo_lease(profile,cfg):
        with backend_supervisor.lock:
            videos.require_unblocked()
            with original_photo_lease(profile,cfg) as active:yield active
    @contextmanager
    def checked_native_lease(profile,cfg=None):
        with backend_supervisor.lock:
            videos.require_unblocked()
            with backend_supervisor.lease(profile,cfg) as active:yield active
    @contextmanager
    def checked_gpu_lease():
        with backend_supervisor.lock:
            videos.require_unblocked()
            with backend_supervisor.gpu_lease() as active:yield active
    def restore_photo(cfg):
        try:
            with checked_native_lease('photo-normal',cfg): pass
        except Exception:
            LOG.exception('Photo reload after music failed; next photo lease will retry')
    def restore_photo_after_prepare(cfg, serial):
        # A prepare request is normally followed by generate. Give that pair
        # a shared music context, then restore photo if the caller stays idle.
        if stop.wait(30): return
        with pipeline.lock:
            if stop.is_set() or music_request_serial[0] != serial: return
            state=backend_supervisor.status()
            if (state.get('active') or {}).get('native_profile') == 'music':
                restore_photo(cfg)
    def restore_photo_after_upscale(cfg):
        with pipeline.lock:
            if stop.is_set(): return
            if not backend_supervisor.status().get('active'):
                restore_photo(cfg)
    @contextmanager
    def upscale_vram_lease(cfg):
        with backend_supervisor.lock:
            videos.require_unblocked()
            resident=cfg['proxy'].get('resident_photo',{}).get('enabled',False)
            result=backend_supervisor.stop_idle() if resident else dict(stopped=False)
            placement=dict(native_released=result.get('stopped',False),
                reason='Helaman owns VRAM exclusively; photo returns after the response')
            try:
                yield placement
            finally:
                pipeline.release_upscaler()
                if result.get('stopped'):
                    threading.Thread(target=restore_photo_after_upscale,args=(cfg,),daemon=True).start()
    if backend_supervisor is not None:
        pipeline.upscale_vram_lease=upscale_vram_lease
    if videos is not None and callable(original_photo_lease):pipeline.photo_backend_lease=checked_photo_lease
    def supervisor_status():
        if backend_supervisor is None:return None
        state=backend_supervisor.status();active=state.get('active') or {}
        return dict(phase=state.get('phase'),native_profile=active.get('native_profile'),
                    helper_sha256=active.get('helper_sha256'),run_id=active.get('run_id'),
                    live_checked=False,automatic_model_switching=True)

    forwarded_headers=('Content-Encoding','Content-Disposition','Cache-Control','ETag','Last-Modified','Vary','Location','Content-Range','Accept-Ranges')
    class Handler(BaseHTTPRequestHandler):
        protocol_version='HTTP/1.1'
        def reply(self,data,status=200,content_type='application/json',headers=None):
            if not isinstance(data,bytes):data=json.dumps(data,ensure_ascii=False).encode('utf-8')
            self.send_response(status);self.send_header('Content-Type',content_type)
            self.send_header('Content-Length',str(len(data)));self.send_header('Connection','close')
            self.send_header('Access-Control-Allow-Origin','*')
            for key,value in (headers or {}).items():
                if key.lower() in {h.lower() for h in forwarded_headers}:self.send_header(key,value)
            self.end_headers();self.close_connection=True
            if self.command!='HEAD':self.wfile.write(data)
        def raw_forward(self,body=None,config=None):
            cfg=config or pipeline.config()
            headers={k:v for k,v in self.headers.items() if k.lower() not in ('host','content-length','connection','transfer-encoding')}
            headers['Accept-Encoding']='identity'
            upstream=urllib.request.Request(cfg['backend']+self.path,body,headers,method=self.command)
            try:response=urllib.request.urlopen(upstream,timeout=600)
            except urllib.error.HTTPError as error:response=error
            with response:
                self.send_response(response.status)
                self.send_header('Content-Type',response.headers.get('Content-Type','application/json'))
                length=response.headers.get('Content-Length')
                if length is not None:self.send_header('Content-Length',length)
                self.send_header('Connection','close');self.send_header('Access-Control-Allow-Origin','*')
                for key in forwarded_headers:
                    if response.headers.get(key) is not None:self.send_header(key,response.headers[key])
                self.end_headers();self.close_connection=True
                if self.command!='HEAD':
                    while True:
                        chunk=response.read1(65536)
                        if not chunk:break
                        self.wfile.write(chunk);self.wfile.flush()
        def forward(self,body=None,config=None):
            cfg=config or pipeline.config()
            path=urllib.parse.urlsplit(self.path).path
            controls=('/sdapi/v1/interrupt','/sdapi/v1/skip','/api/extra/abort')
            if backend_supervisor is None or self.command in ('GET','HEAD') or path in controls:
                return self.raw_forward(body,cfg)
            # Text/music streams retain the same Native lease through EOF.
            with pipeline.lock:
                pipeline.release_gpu()
                demand_music = path in MUSIC_PATHS and backend_supervisor.music_on_demand
                profile = 'music' if demand_music else 'photo-normal'
                if demand_music: music_request_serial[0] += 1
                try:
                    with checked_native_lease(profile,cfg) as active:
                        cfg={**cfg,'backend':active['backend']}
                        self.raw_forward(body,cfg)
                finally:
                    # All music weights are gone before the photo model returns.
                    if demand_music and path == '/api/extra/music/generate':
                        restore_photo(cfg)
                    elif demand_music:
                        threading.Thread(target=restore_photo_after_prepare,
                            args=(cfg,music_request_serial[0]),daemon=True).start()
                return
        def media(self,path):
            if videos is None:raise VideoServiceError('Video supervisor unavailable.','video_backend_unavailable',503)
            result=videos.open_media(path,dict(self.headers))
            self.send_response(result.status)
            for key,value in result.headers.items():self.send_header(key,value)
            self.send_header('Access-Control-Allow-Origin','*');self.send_header('Connection','close')
            self.end_headers();self.close_connection=True
            if self.command!='HEAD':
                for block in result.chunks():self.wfile.write(block)
        def do_OPTIONS(self):
            self.send_response(204);self.send_header('Access-Control-Allow-Origin','*');self.send_header('Access-Control-Allow-Headers','*')
            self.send_header('Access-Control-Allow-Methods','GET, HEAD, POST, OPTIONS');self.send_header('Content-Length','0');self.end_headers()
        def do_HEAD(self):
            self.do_GET()
        def do_GET(self):
            try:
                cfg=pipeline.config();path=urllib.parse.urlsplit(self.path).path
                if path.startswith(VIDEO_MEDIA_PREFIX):self.media(path);return
                if path=='/api/extra/version' and backend_supervisor:
                    status,headers,raw=request(cfg['backend']+path)
                    if status==200:
                        version=json.loads(raw);version.update(music=True,musicllm=True,txt2img=True,kcpp_auto_switch=True,video=bool(cfg['proxy'].get('video',{}).get('enabled',False)))
                        self.reply(version);return
                if path=='/health':
                    self.reply(dict(service='KoboldProxy',version=VERSION,pid=os.getpid(),helper=str(pipeline.helper),helper_sha256=cfg['helper_sha256'],
                      backend=cfg['backend'],port=cfg['port'],profile={k:cfg['defaults'].get(k) for k in IMAGE_FIELDS},
                      resolution=dict(default_width=cfg['defaults'].get('width'),default_height=cfg['defaults'].get('height'),pixel_budget=cfg['proxy'].get('native_pixel_budget'),always_upscale=cfg['proxy'].get('always_upscale',False),allow_generation_upscale=cfg['proxy'].get('allow_generation_upscale',True)),
                      backend_supervisor=supervisor_status(),image_modes=cfg['proxy'].get('image_modes'),video=cfg['proxy'].get('video'),upscaler=cfg['proxy']['upscaler'],detailer=cfg['proxy'].get('detailer',{}),photo_restoration=cfg['proxy'].get('photo_restoration',{}),faces_before_upscale=cfg['proxy'].get('faces_before_upscale',False),repeat_faces_after_upscale=cfg['proxy'].get('repeat_faces_after_upscale',False),denoise=cfg['proxy'].get('denoise',{}),force_mp3=cfg['proxy'].get('force_mp3',True),completed=pipeline.completed,active=pipeline.state(),sr_session_loaded=bool(pipeline.upscaler),face_session_loaded=bool(pipeline.restorer),face_prewarm=pipeline.face_prewarm));return
                if path=='/sdapi/v1/upscalers':
                    opts=cfg['proxy']['upscaler'];self.reply([dict(name=opts.get('name','2x upscaler'),model_name=opts.get('name','2x upscaler'),model_path=opts.get('model','native'),model_url=opts.get('source',''),scale=upscale_api_scale(cfg))]);return
                if path=='/sdapi/v1/progress':
                    query=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);state=pipeline.state();key=query.get('genkey',[''])[0]
                    if state and state.get('request_key','')==key and state['stage'] in ('face_restorer','upscaler'):
                        self.reply(dict(progress=.95 if state['stage']=='face_restorer' else .99,eta_relative=0,state=dict(job_count=1,job_no=0,sampling_steps=1,sampling_step=0,interrupted=False,skipped=False),current_image=None,textinfo='Обработка деталей лица' if state['stage']=='face_restorer' else 'Апскейл'+str(upscale_api_scale(cfg))+'x'));return
                    if state and state.get('request_key','')==key and state['stage']=='detailer':
                        suffix=urllib.parse.urlencode(dict(skip_current_image='true',genkey=state['genkey']))
                        status,headers,raw=request(cfg['backend']+'/sdapi/v1/progress?'+suffix)
                        native=json.loads(raw);fraction=float(native.get('progress',0));count=max(1,state.get('total_faces',1))
                        native['progress']=min(.995,.85+.15*(state.get('face',1)-1+fraction)/count)
                        native['textinfo']=f'Face detailer {state.get("face",1)}/{count}'
                        native['current_image']=None;self.reply(native,status);return
                    if cfg['proxy'].get('final_only_preview',True):
                        query['skip_current_image']=['true']
                        target=path+'?'+urllib.parse.urlencode(query,doseq=True)
                        status,headers,raw=request(cfg['backend']+target);self.reply(raw,status,headers.get('Content-Type','application/json'),headers);return
                self.forward(config=cfg)
            except (BrokenPipeError,ConnectionResetError):pass
            except (SupervisorError,VideoServiceError) as error:self.reply(error.body,error.status,headers=getattr(error,'headers',None))
            except Exception as error:LOG.exception('GET failed');self.reply(dict(error=type(error).__name__,detail=str(error)),503)
        def do_POST(self):
            try:
                cfg=pipeline.config();path=urllib.parse.urlsplit(self.path).path
                if path in EDIT_PATHS:
                    if self.headers.get('Transfer-Encoding'):raise ImageEditError('Chunked image-edit uploads are unsupported; provide Content-Length.',code='content_length_required',status=411)
                    if self.headers.get('Content-Length') is None:raise ImageEditError('Content-Length is required.',code='content_length_required',status=411)
                    try:int(self.headers['Content-Length'])
                    except ValueError:raise ImageEditError('Invalid Content-Length.',code='invalid_content_length')
                length=int(self.headers.get('Content-Length','0'))
                maximum=int(cfg['helper'].get('maxrequestsize',32))*1024*1024
                if length<0 or length>maximum:self.reply(dict(error='Request exceeds configured size limit'),413);return
                body=self.rfile.read(length)
                if path in VIDEO_JSON_PATHS or path=='/sdapi/v1/txt2img':
                    video_payload=json.loads(body or b'{}')
                    if not isinstance(video_payload,dict):self.reply(dict(error='JSON object required'),400);return
                    if is_video_request(path,video_payload):
                        if videos is None:raise VideoServiceError('Video supervisor unavailable.','video_backend_unavailable',503)
                        if cfg['proxy'].get('video',{}).get('enabled',True) is False:
                            raise VideoServiceError('Видеогенерация отложена до завершения проверки качества. Фото и музыка доступны.','video_deferred',503)
                        try:
                            with videos.client_deadline(self.connection) as video_budget:
                                with pipeline.lock:
                                    pipeline.begin(video_payload.get('genkey',''),'video')
                                    try:self.reply(videos.generate(path,video_payload,dict(self.headers),cfg,budget=video_budget))
                                    finally:pipeline.finish()
                        except (BrokenPipeError,ConnectionResetError,OSError):
                            self.close_connection=True
                            LOG.info('Video client disconnected or reached its deadline')
                        except VideoServiceError as error:
                            if video_budget.cancelled.is_set() or video_budget.clock()>=video_budget.until:
                                self.close_connection=True
                                try:self.connection.shutdown(socket.SHUT_RDWR)
                                except OSError:pass
                                try:self.connection.close()
                                except OSError:pass
                                LOG.info('Video deadline expired; response socket closed after cleanup')
                            else:self.reply(error.body,error.status,headers=getattr(error,'headers',None))
                        return
                if path in EDIT_PATHS:
                    with pipeline.lock:
                        image_payload,edit_context=prepare_edit(body,self.headers.get('Content-Type',''),cfg,mode_resolver=resolve_image_mode)
                        request_mode=edit_context.pop('_resolved_image_mode')
                        answer=pipeline.generate('/sdapi/v1/img2img',image_payload,dict(self.headers),edit_context=edit_context,request_mode=request_mode)
                        images=answer.get('images',[])
                        if len(images)!=1:raise RuntimeError('Native image edit returned an unexpected image count')
                        decoded=image_decode(images[0]);report=answer.get('kcpp_proxy',{})
                        report['image_edit']=edit_context
                        self.reply(dict(created=int(time.time()),data=[dict(b64_json=images[0])],background='opaque',output_format='png',size=f'{decoded.width}x{decoded.height}',kcpp_proxy=report))
                    return
                if path not in (*IMAGE_PATHS,*OPENAI_IMAGE_PATHS,*EDIT_PATHS,*SR_PATHS,*MUSIC_PATHS,'/sdapi/v1/detail'):
                    self.forward(body,config=cfg);return
                payload=json.loads(body or b'{}')
                if not isinstance(payload,dict):self.reply(dict(error='JSON object required'),400);return
                with pipeline.lock, (checked_gpu_lease() if backend_supervisor else nullcontext()):
                    request_mode=None
                    if path in (*IMAGE_PATHS,*OPENAI_IMAGE_PATHS):
                        request_mode=resolve_image_mode(payload,cfg,'edit' if path=='/sdapi/v1/img2img' else 'generation')
                        payload=request_mode.payload
                    if path in OPENAI_IMAGE_PATHS:
                        image_payload=dict(payload)
                        size=str(image_payload.pop('size',''))
                        dimensions=size.lower().split('x')
                        if len(dimensions)==2 and all(part.isdigit() for part in dimensions):image_payload.update(width=int(dimensions[0]),height=int(dimensions[1]))
                        for field in ('model','response_format','quality','output_format','background'):image_payload.pop(field,None)
                        image_payload.pop('n',None)
                        image_payload['batch_size']=1;image_payload['n_iter']=1
                        answer=pipeline.generate('/sdapi/v1/txt2img',image_payload,dict(self.headers),request_mode=request_mode)
                        images=answer.get('images',[]);size=''
                        if images:
                            decoded=image_decode(images[0]);size=f'{decoded.width}x{decoded.height}'
                        self.reply(dict(created=int(time.time()),data=[dict(b64_json=value) for value in images],background='opaque',output_format='png',size=size,quality='medium',kcpp_proxy=answer.get('kcpp_proxy')));return
                    if path in IMAGE_PATHS:
                        self.reply(pipeline.generate(path,payload,dict(self.headers),request_mode=request_mode));return
                    pipeline.begin(payload.get('genkey',''), 'music' if path in MUSIC_PATHS else 'postprocess')
                    try:
                        if path in MUSIC_PATHS:
                            pipeline.release_gpu()
                            if cfg['proxy'].get('force_mp3',True):payload.update(use_mp3=True,response_format='mp3')
                            self.forward(json.dumps(payload).encode('utf-8'),cfg);return
                        image=image_decode(payload['image']);started=time.perf_counter()
                        if path=='/sdapi/v1/detail':
                            opts={**cfg['proxy'].get('detailer',{}),**payload.get('detailer',{}),'enabled':True}
                            final,detail=pipeline.process_faces(image,opts,payload,cfg)
                            self.reply(dict(image=image_encode(final,marker=detail.get('marker')),detailer=detail));return
                        requested_scale=payload.get('upscaling_resize')
                        if cfg['proxy']['upscaler'].get('runtime')=='helaman_atd':payload['upscaling_resize']=upscale_api_scale(cfg)
                        opts=dict(cfg['proxy'].get('detailer',{}));option=payload.get('kcpp_detailer')
                        if option is False:opts['enabled']=False
                        elif isinstance(option,dict):opts.update(option)
                        final,report=pipeline.finish_photo(image,opts,payload,cfg,upscale=True)
                        report['total_seconds']=round(time.perf_counter()-started,4)
                        name=cfg['proxy']['upscaler'].get('name','2x upscaler')
                        self.reply(sr_api_response(final,report,cfg,requested_scale))
                        LOG.info(json.dumps(dict(kind='upscale',**report),ensure_ascii=False))
                    finally:pipeline.finish()
            except (BrokenPipeError,ConnectionResetError):pass
            except (ImageEditError,ImageModeError,ImageBudgetError,SupervisorError,VideoServiceError) as error:self.reply(error.body,error.status,headers=getattr(error,'headers',None))
            except Exception as error:LOG.exception('POST failed');self.reply(dict(error=type(error).__name__,detail=str(error)),502)
        def log_message(self,format,*args):LOG.info(format,*args)
    host=initial['proxy'].get('host','127.0.0.1')
    if ':' in host:
        class Server(ThreadingHTTPServer):
            address_family=socket.AF_INET6
            def server_bind(self):
                self.socket.setsockopt(socket.IPPROTO_IPV6,socket.IPV6_V6ONLY,0)
                super().server_bind()
    else:Server=ThreadingHTTPServer
    server=Server((host,initial['port']),Handler)
    try:pipeline.image_budget_prewarm=prewarm_image_budget(root=ROOT,config=initial)
    except ImageBudgetError as error:
        pipeline.image_budget_prewarm=dict(ok=False,error=str(error))
        LOG.exception('SD tokenizer prewarm failed; image requests remain blocked until repaired')
    pipeline.prewarm_cpu_faces(initial)
    pipeline.restoration_prewarm=prewarm_restoration_model(initial['proxy'].get('photo_restoration',{}))
    pid_path=ROOT/'logs'/f'image-proxy-{initial["port"]}.pid.json'
    pid_path.write_text(json.dumps(dict(pid=os.getpid(),helper=str(helper),port=initial['port'],started=time.time()),indent=2),encoding='utf-8')
    def watchdog():
        misses=0;seen=False
        while not stop.wait(10):
            try:
                with urllib.request.urlopen(pipeline.config()['backend']+'/api/extra/version',timeout=2) as answer:healthy=answer.status==200
            except Exception:healthy=False
            seen=seen or healthy;misses=0 if healthy else misses+1
            if seen and misses>=3:
                if pipeline.config()['proxy'].get('keep_alive_without_backend',False):
                    if misses==3:
                        with pipeline.lock:pipeline.release_gpu()
                        LOG.info('Native backend stopped; GPU released, waiting for next Helper launch')
                    continue
                LOG.info('Native backend stopped; closing proxy and releasing GPU memory')
                server.shutdown();return
    if backend_supervisor is None:threading.Thread(target=watchdog,daemon=True).start()
    LOG.info('Started proxy on %s:%s, native backend %s',host,initial['port'],initial['backend'])
    try:server.serve_forever(poll_interval=.5)
    finally:
        stop.set();server.server_close()
        with pipeline.lock:pipeline.release_gpu()
        LOG.info('Proxy stopped')

def main():
    p=argparse.ArgumentParser();p.add_argument('--helper',type=Path,required=True);p.add_argument('--ensure',action='store_true');a=p.parse_args()
    cfg=settings(a.helper);folder=ROOT/'logs';folder.mkdir(exist_ok=True)
    handler=RotatingFileHandler(folder/'image-proxy.log',maxBytes=2*1024*1024,backupCount=2,encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'));LOG.addHandler(handler);LOG.setLevel(logging.INFO)
    if a.ensure:
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{cfg["port"]}/health',timeout=2) as response:existing=json.load(response)
            if existing.get('service')=='KoboldProxy' and Path(existing.get('helper','')).resolve()==a.helper.resolve():
                LOG.info('Existing proxy reused');return
            raise RuntimeError('Configured public port belongs to another service')
        except (urllib.error.URLError,TimeoutError,ConnectionError):pass
    serve(a.helper)
if __name__=='__main__':main()

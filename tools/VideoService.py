"""Shared Native video routing; no process launcher and no standalone SD CLI.

The shared supervisor owns Native identity/startup/unload. Its global lease is
held through the Native request and CPU finishing. Public media reads do not
load/switch models.
"""
from __future__ import annotations

import copy
from contextlib import contextmanager
from dataclasses import dataclass
import shutil
import json
import math
from pathlib import Path
import re
import socket
import threading
import time
import urllib.parse
import uuid

from NativeVideo import prepare_request, finish_native_video

VIDEO_JSON_PATHS=('/api/extra/video/generate','/v1/videos/generations')
VIDEO_MEDIA_PREFIX='/api/extra/video/media/'
MAX_VIDEO_SECONDS=900
SIZES={(640,352):('360p','landscape'),(352,640):('360p','portrait'),
       (832,480):('480p','landscape'),(480,832):('480p','portrait')}


class VideoServiceError(ValueError):
    def __init__(self,message,code='invalid_video_request',status=400,headers=None):
        super().__init__(message);self.status=status;self.headers=headers or {}
        self.body={'error':{'message':message,'type':code,'code':code}}


class VideoBudget:
    def __init__(self,seconds,clock):
        if isinstance(seconds,bool) or not isinstance(seconds,(int,float)) or not math.isfinite(seconds) or not 0<seconds<=MAX_VIDEO_SECONDS:
            raise ValueError('Total video budget must be finite and in(0,900]seconds')
        self.seconds=float(seconds);self.clock=clock;self.started=clock();self.until=self.started+self.seconds
        self.cancelled=threading.Event()
    def remaining(self):
        value=self.until-self.clock()
        if self.cancelled.is_set() or value<=0:raise TimeoutError('Total video request deadline exhausted')
        return value
    def elapsed(self):return self.clock()-self.started


def is_video_request(path,payload):
    path=urllib.parse.urlsplit(path).path
    if path in VIDEO_JSON_PATHS:return True
    if path!='/sdapi/v1/txt2img' or not isinstance(payload,dict):return False
    value=payload.get('frames',1)
    if isinstance(value,bool):return False
    try:return float(value)>1
    except (TypeError,ValueError):raise VideoServiceError('frames должно быть числом.')


@dataclass(frozen=True)
class MediaResponse:
    path:Path
    status:int
    headers:dict
    start:int
    length:int

    def chunks(self,size=65536):
        size=max(1024,min(int(size),65536))
        with self.path.open('rb') as stream:
            stream.seek(self.start);remaining=self.length
            while remaining:
                block=stream.read(min(size,remaining))
                if not block:raise OSError('Stored video shortened during read')
                remaining-=len(block);yield block


class VideoService:
    def __init__(self,supervisor,root,request_json,finisher=None,before_native=None,
                 public_base_url='',max_media_bytes=128*1024**2,deadline_seconds=MAX_VIDEO_SECONDS,clock=None):
        self.supervisor=supervisor;self.root=Path(root).resolve();self.request_json=request_json
        self.finisher=finisher or finish_native_video;self.before_native=before_native
        self.clock=clock or time.perf_counter
        VideoBudget(deadline_seconds,self.clock)
        self.deadline_seconds=float(deadline_seconds)
        self.outputs=(self.root/'OUTPUTS/video').resolve()
        self.blocker=(self.root/'logs/video-owned-unload-blocker.json').resolve()
        if not self.outputs.is_relative_to(self.root) or not self.blocker.is_relative_to(self.root):
            raise ValueError('Video managed paths must remain inside portable root')
        self.max_media_bytes=max(1024,min(int(max_media_bytes),256*1024**2))
        parsed=urllib.parse.urlsplit(public_base_url)
        if public_base_url and (parsed.scheme not in ('http','https') or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('','/')):
            raise VideoServiceError('Некорректный публичный базовый URL видео.')
        self.public_base_url=public_base_url.rstrip('/')

    @contextmanager
    def client_deadline(self,connection):
        """Root wraps the video route/reply, BEFORE waiting for pipeline.lock.

        This caps the client's own API connection even while existing bounded
        Supervisor startup/shutdown operations are returning. Cleanup may finish
        later under the lease; no successful result is returned after expiry.
        """
        budget=VideoBudget(self.deadline_seconds,self.clock)
        def cancel():
            budget.cancelled.set()
            try:connection.shutdown(socket.SHUT_RDWR)
            except OSError:pass
            try:connection.close()
            except OSError:pass
        timer=threading.Timer(budget.remaining(),cancel);timer.daemon=True;timer.start()
        try:yield budget
        finally:timer.cancel()

    def _blocker_data(self):
        if not self.blocker.is_file():return None
        try:
            data=json.loads(self.blocker.read_text(encoding='utf-8'))
            if not isinstance(data,dict):raise ValueError('blocker must be an object')
            return data
        except (OSError,ValueError) as error:
            raise VideoServiceError('Состояние предыдущего video-unload не читается; новые задания заблокированы.','video_unload_unconfirmed',503) from error

    def require_unblocked(self):
        """Root must also call this before every nonvideo Native/GPU lease."""
        data=self._blocker_data()
        if data and data.get('resolved') is not True:
            raise VideoServiceError('Предыдущий собственный Native ещё не подтверждён как выгруженный; новые задания заблокированы.','video_unload_unconfirmed',503)

    def _save_blocker(self,data):
        self.blocker.parent.mkdir(parents=True,exist_ok=True)
        temporary=self.blocker.with_name(self.blocker.name+'.writing')
        temporary.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');temporary.replace(self.blocker)

    @staticmethod
    def _identity(active):
        if not isinstance(active,dict):return None
        result={k:active.get(k) for k in ('run_id','native_profile','helper_sha256','executable_sha256','port')}
        if not result['run_id']:return None
        for key in ('worker','native'):
            record=active.get(key)
            if record:result[key]={k:record.get(k) for k in ('pid','created_ticks')}
        return result

    def _snapshot(self):
        if not callable(getattr(self.supervisor,'status',None)):
            raise RuntimeError('Supervisor identity snapshot is required for owned video cleanup')
        state=self.supervisor.status()
        if not isinstance(state,dict):raise RuntimeError('Invalid Supervisor snapshot')
        return state

    def _owned_video_identity(self,state):
        active=state.get('active');identity=self._identity(active)
        profile=self._profile()
        if not identity:return None
        if identity.get('native_profile')!='video' or identity.get('helper_sha256')!=profile['helper_sha256'] or identity.get('executable_sha256')!=profile['executable_sha256'] or identity.get('port')!=profile.get('port',5003):
            raise RuntimeError('Current context is not this verified video profile; preserved')
        return identity

    @staticmethod
    def _same_identity(current,expected):
        return bool(current and expected and all(current.get(k)==v for k,v in expected.items() if v is not None))

    def _unload_blocked_owned(self,data):
        """Only verified stop_idle, never PID kill or shutdown of a changed context."""
        expected=data.get('expected_identity');state=self._snapshot();current=self._owned_video_identity(state)
        if current is None:
            # Missing state alone is not evidence that the captured process died.
            history=state.get('history',[])
            confirmed=bool(expected and any(h.get('reason')=='stale_or_exited_preserved' and
                          self._same_identity(self._identity(h.get('active')),expected)
                          for h in history if isinstance(h,dict)))
            if not confirmed:raise RuntimeError('Captured owned unload is not confirmed; no context stopped')
            result={'retired':True,'reason':'captured_context_absent_in_verified_history' if expected else 'no_video_context_was_started','new_context_started':False}
        else:
            if expected and not self._same_identity(current,expected):raise RuntimeError('Video context identity changed; preserved')
            if not expected:
                data['expected_identity']=expected=current
            result=self.supervisor.stop_idle()
            confirmed=bool(result.get('stopped') and result.get('run_id')==expected['run_id'])
            if result.get('retired'):
                confirmed=not self._snapshot().get('active')
            if not confirmed:raise RuntimeError('Supervisor did not confirm unload of captured video context')
        data.update(resolved=True,owned_unload=result,confirmed_at=time.time());self._save_blocker(data)
        return result

    def recover_owned_unload(self):
        """Explicit recovery, no launch/generation. Root may expose an operator hook."""
        with self.supervisor.lock:
            data=self._blocker_data()
            if not data or data.get('resolved') is True:return {'resolved':True,'reason':'no_unresolved_video_blocker'}
            return self._unload_blocked_owned(data)

    def _failed_cleanup(self,job_id,expected,native_sent,error):
        data={'resolved':False,'video_id':job_id,'expected_identity':expected,'native_request_sent':native_sent,
              'reason':repr(error),'created':time.time(),'deadline_seconds':self.deadline_seconds}
        self._save_blocker(data);started=self.clock()
        try:result=self._unload_blocked_owned(data);confirmed=True
        except Exception as cleanup_error:
            data['owned_unload_error']=repr(cleanup_error);self._save_blocker(data);result=None;confirmed=False
        return {'owned_unload_confirmed':confirmed,'owned_unload':result,'next_jobs_blocked_until_owned_unload_confirmed':not confirmed,
                'cleanup_seconds_outside_request_budget':max(0,self.clock()-started)}

    def _known_preflight_without_start(self,before,error):
        """Recognize only unchanged, known file/config preflight failures.

        BackendSupervisor._ensure verifies files before switching. Its _start
        atomically saves a new launch intent BEFORE spawn_worker. Therefore an
        unchanged snapshot plus a known preflight code can certify no video was
        started. Mere missing state or an arbitrary exception cannot certify it.
        """
        body=getattr(error,'body',{})
        code=body.get('error',{}).get('code') if isinstance(body,dict) and isinstance(body.get('error'),dict) else None
        if code not in ('profile_file_changed','invalid_profile_config','invalid_profile','music_profile_changed') or not isinstance(before,dict):return False
        prior=before.get('active')
        if prior is not None and (not isinstance(prior,dict) or prior.get('native_profile')=='video'):return False
        try:return before==self._snapshot()
        except Exception:return False

    def _profile(self):
        if not self.supervisor or not callable(getattr(self.supervisor,'lease',None)) or not hasattr(self.supervisor,'lock'):
            raise VideoServiceError('Общий менеджер Native не подключён.','video_backend_unavailable',503)
        profile=getattr(self.supervisor,'profiles',{}).get('video',{})
        expected=(self.root/'koboldcpp-nocuda.exe').resolve()
        photo=self.supervisor.profiles.get('photo-normal',{})
        if Path(profile.get('executable','')).resolve()!=expected or profile.get('executable_sha256')!=photo.get('executable_sha256') or not re.fullmatch(r'[0-9a-f]{64}',str(profile.get('helper_sha256',''))) or profile.get('native_jpeg_quality')!=95:
            raise VideoServiceError('Менеджер не закрепил текущий общий Native с проверенным JPEG95 и видеопрофилем.','video_backend_unavailable',503)
        return profile

    def _job(self,payload):
        if not isinstance(payload,dict):raise VideoServiceError('Требуется объект JSON.')
        allowed={'prompt','frames','fps','seed','resolution','orientation','width','height','n','batch_size','n_iter','steps','cfg_scale','model','genkey','start_frame','video_start_frame','image','init_images','continue_from','sampler_name','scheduler','flow_shift','eta','negative_prompt','upscale_to','enhance_faces'}
        unknown=set(payload)-allowed
        if unknown:raise VideoServiceError('Неподдерживаемые поля видео: '+', '.join(sorted(unknown)),status=422)
        for key,expected in [('steps',4),('cfg_scale',1),('sampler_name','euler'),('scheduler','simple'),('flow_shift',5),('eta',0)]:
            if key in payload and payload[key]!=expected:raise VideoServiceError('Для выбранной Turbo-модели требуется '+key+'='+str(expected),status=422)
        if payload.get('model','kobold-video') not in ('kobold-video','kobold-wan22-turbo'):raise VideoServiceError('Неизвестная видео-модель; веса управляются сервером.',status=422)
        if payload.get('negative_prompt',''):raise VideoServiceError('CFG1 Turbo не использует negative_prompt; задайте позитивное описание.',status=422)
        if any(key in payload for key in ('seconds','duration','duration_seconds')):
            raise VideoServiceError('Пока задайте явное frames: 4n+1, от 5 до 121. Длинное видео ещё не измерено.')
        if payload.get('n',1)!=1 or payload.get('batch_size',1)!=1 or payload.get('n_iter',1)!=1:
            raise VideoServiceError('Один видеоклип на запрос.')
        job={key:payload[key] for key in ('prompt','frames','fps','seed','resolution','orientation') if key in payload}
        # Author4-step/CFG1 contract is explicit; legacy photo steps must not leak in.
        job.update(steps=4,cfg_scale=1)
        if 'width' in payload or 'height' in payload:
            width,height=payload.get('width'),payload.get('height')
            if type(width) is not int or type(height) is not int or (width,height) not in SIZES:
                raise VideoServiceError('Допустимы 640×352 или 832×480, также portrait с перестановкой сторон.')
            job['resolution'],job['orientation']=SIZES[(width,height)]
        if payload.get('start_frame'):
            raise VideoServiceError('Публичный запрос принимает PNG base64 или continue_from, без локального пути.')
        images=payload.get('init_images')
        if images is not None and (not isinstance(images,list) or len(images)>1):
            raise VideoServiceError('Для I2V допускается одно начальное PNG.')
        image_inputs=[value for value in (payload.get('video_start_frame'),payload.get('image'),images[0] if images else None) if value is not None and value!='']
        if len(image_inputs)>1:raise VideoServiceError('Укажите только один источник PNG: image, video_start_frame или init_images.',status=422)
        inline=image_inputs[0] if image_inputs else None
        continuation=payload.get('continue_from')
        if inline and continuation:raise VideoServiceError('Укажите одно начальное изображение.')
        if continuation:
            if not isinstance(continuation,str) or not re.fullmatch(r'[0-9a-f]{32}',continuation):
                raise VideoServiceError('Некорректный идентификатор предыдущего видео.')
            folder=self.outputs/continuation
            previous=(folder/('native-last-frame.png' if (folder/'native-last-frame.png').is_file() else 'last-frame.png')).resolve()
            if not previous.is_relative_to(self.outputs) or not previous.is_file():
                raise VideoServiceError('Последний кадр предыдущего видео отсутствует.','video_not_found',404)
            job['start_frame']=str(previous)
        elif inline:job['start_png_base64']=inline
        return job

    def generate(self,path,payload,headers=None,cfg=None,budget=None):
        if budget is None:budget=VideoBudget(self.deadline_seconds,self.clock)
        elif not isinstance(budget,VideoBudget) or budget.clock is not self.clock or budget.seconds>self.deadline_seconds:
            raise ValueError('Use this VideoService client_deadline budget')
        if not is_video_request(path,payload):raise VideoServiceError('Запрос не относится к видеогенерации.')
        self.require_unblocked();profile=self._profile();job=self._job(copy.deepcopy(payload))
        # Validate before acquiring a cold model. No photo defaults/triggers leak in.
        try:prepare_request(job,self.root,'http://127.0.0.1:'+str(profile.get('port',5003)),native_jpeg_quality=95)
        except ValueError as error:raise VideoServiceError(str(error)) from error
        created=int(time.time());job_id=uuid.uuid4().hex;destination=self.outputs/job_id
        acquired=False;lease_attempted=False;expected=None;native_sent=False;before_lease=None
        prior_readiness=None
        try:
            acquired=self.supervisor.lock.acquire(timeout=budget.remaining())
            if not acquired:raise TimeoutError('Total video deadline exhausted while waiting for shared GPUlock')
            self.require_unblocked();budget.remaining()
            prior_readiness=getattr(self.supervisor,'readiness_seconds',None)
            if self.before_native:self.before_native()
            budget.remaining()
            if prior_readiness is not None:self.supervisor.readiness_seconds=min(float(prior_readiness),budget.remaining())
            before_lease=copy.deepcopy(self._snapshot())
            lease_attempted=True
            with self.supervisor.lease('video',cfg) as active:
                if not isinstance(active,dict) or active.get('native_profile')!='video' or active.get('helper_sha256')!=profile['helper_sha256'] or not active.get('backend'):
                    raise VideoServiceError('Менеджер не подтвердил активный видеопрофиль.','video_backend_unavailable',503)
                expected=self._owned_video_identity(self._snapshot())
                if not expected or expected['run_id']!=active.get('run_id'):
                    raise VideoServiceError('Не подтверждена identity собственного видео-запроса.','video_backend_unavailable',503)
                ready_seconds=budget.elapsed();budget.remaining()
                try:plan=prepare_request(job,self.root,active['backend'],native_jpeg_quality=95)
                except ValueError as error:raise VideoServiceError(str(error)) from error
                native_started=self.clock();native_sent=True
                # Callback must implement an absolute socket watchdog, not an
                # unbounded/keepalive-resetting read timeout. Root wiring is separate.
                answer=self.request_json(plan['endpoint'],plan['payload'],headers or {},timeout=budget.remaining())
                native_seconds=self.clock()-native_started
                # A tiny remainder is still a valid bound. Native AVI/finalPNG are
                # preserved by the finisher even if its encoder budget expires.
                allowance=max(0.000001,budget.until-self.clock())
                finished=self.finisher(answer,plan,destination,self.root,timeout=allowance,
                                       deadline=budget.until,clock=self.clock,run_encoder=True)
                budget.remaining()
                if finished.get('status')!='completed':
                    raise VideoServiceError('Обработка MP4 не завершена.','video_postprocess_failed',502)
                try:info=json.loads(answer.get('info','{}')) if isinstance(answer.get('info'),str) else answer.get('info',{})
                except (ValueError,TypeError):info={}
                media_path=VIDEO_MEDIA_PREFIX+job_id+'/video.mp4'
                metadata=dict(id=job_id,model=plan['contract']['model'],backend='KoboldCpp Native',
                              native_profile='video',native_jpeg_quality=95,vae_decoder=(cfg or {}).get('proxy',{}).get('video',{}).get('codec'),output_format='mp4',mime_type='video/mp4',
                              width=plan['contract']['dimensions'][0],height=plan['contract']['dimensions'][1],
                              frames=finished.get('encoded_frames'),fps=plan['contract']['fps'],
                              duration_seconds=plan['contract']['seconds'],steps=4,cfg_scale=1,
                              requested_seed=plan['payload']['seed'],actual_seed=info.get('seed') if isinstance(info,dict) else None,
                              url=self.public_base_url+media_path,relative_url=media_path,
                              last_frame_url=self.public_base_url+VIDEO_MEDIA_PREFIX+job_id+'/last-frame.png',
                              output_sha256=finished.get('output_sha256'),output_bytes=finished.get('output_bytes'),
                              native_call_seconds=round(native_seconds,4),encoder_seconds=finished.get('encoder_seconds'),
                              profile_ready_seconds=round(ready_seconds,4),total_seconds=round(budget.elapsed(),4),
                              deadline_seconds=self.deadline_seconds,deadline_includes='queue,coldload,Native,MP4',
                              photo_processing=False,upscale=False,
                              temporal_processing='No stretching, duplication or interpolation; I2V continuation is not yet a validated seamless extension.')
                if not destination.is_dir():
                    raise VideoServiceError('Результат видео не сохранён.','video_postprocess_failed',502)
                (destination/'service.json').write_text(json.dumps(dict(created=created,metadata=metadata,active_profile=active),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
                budget.remaining()
                if urllib.parse.urlsplit(path).path=='/sdapi/v1/txt2img':
                    returned=dict(answer);returned['kcpp_video']=metadata;return returned
                return dict(id=job_id,object='video',created=created,url=metadata['url'],
                            data=[dict(url=metadata['url'],mime_type='video/mp4')],metadata=metadata)
        except Exception as error:
            cleanup={}
            # No cleanup/blocker for a queued request that never owned the slot.
            if acquired and lease_attempted:
                if expected is None and not native_sent and self._known_preflight_without_start(before_lease,error):
                    cleanup={'owned_unload_required':False,'failure_before_native_launch':True,
                             'next_jobs_blocked_until_owned_unload_confirmed':False}
                else:cleanup=self._failed_cleanup(job_id,expected,native_sent,error)
            if isinstance(error,VideoServiceError):failure=error
            else:
                timed_out=isinstance(error,TimeoutError) or self.clock()>=budget.until
                failure=VideoServiceError('Видео не завершено: '+str(error),
                    'video_deadline_exceeded' if timed_out else 'video_generation_failed',504 if timed_out else 502)
            failure.body['error'].update(video_id=job_id,deadline_seconds=self.deadline_seconds,
                request_seconds=round(budget.elapsed(),4),native_avi_preserved=(destination/'native.avi').is_file(),
                partial_encoder_output_preserved=(destination/'video.work.mp4').is_file(),**cleanup)
            if failure is error:raise
            raise failure from error
        finally:
            if acquired and prior_readiness is not None:self.supervisor.readiness_seconds=prior_readiness
            if acquired:self.supervisor.lock.release()

    def enhance(self,result,cfg,budget,upscale_to=None,faces=False):
        """Only saved generated media. Caller holds the global pipeline/GPU locks."""
        from VideoPost import process_video
        metadata=dict(result.get('metadata') or result.get('kcpp_video') or {})
        identity=metadata.get('id')
        if not isinstance(identity,str) or not re.fullmatch(r'[0-9a-f]{32}',identity):raise VideoServiceError('Некорректный video_id.',status=422)
        if upscale_to not in (None,'720p') or type(faces) is not bool:raise VideoServiceError('upscale_to:720p или null; enhance_faces:boolean.',status=422)
        if not(upscale_to or faces):return result
        folder=(self.outputs/identity).resolve();source=folder/'native.avi'
        if not folder.is_relative_to(self.outputs) or not source.is_file():raise VideoServiceError('Исходный Native AVI не найден.','video_not_found',404)
        options=cfg.get('proxy',{}).get('video',{})
        model=options.get('upscaler','clearreality') if upscale_to else 'lanczos'
        if model not in ('clearreality','paragon2x','lanczos'):raise VideoServiceError('Неизвестный проверенный видео-апскейлер.',status=422)
        report=process_video(source,folder/'enhanced',self.root,model=model,faces=faces,target_short_edge=720 if upscale_to else 480,
            face_provider=options.get('face_provider','directml'),face_visibility=.2,temporal_faces=.25,timeout=budget.remaining())
        (folder/'video.mp4').rename(folder/'video-native480.mp4')
        shutil.copy2(folder/'last-frame.png',folder/'native-last-frame.png')
        Path(report['output']).rename(folder/'video.mp4');shutil.copy2(folder/'enhanced/output-last.png',folder/'last-frame.png')
        metadata.update(width=report['dimensions'][0],height=report['dimensions'][1],native_dimensions=report['source_dimensions'],
            upscale=bool(upscale_to),face_processing=bool(report['processed_faces']),processed_faces=report['processed_faces'],
            output_sha256=report['output_sha256'],output_bytes=report['output_bytes'],enhancement_seconds=report['total_seconds'],
            total_seconds=round(budget.elapsed(),4),postprocessing={k:v for k,v in report.items() if k!='output'},source_native_preserved=True)
        metadata.update(native_video_url=self.public_base_url+VIDEO_MEDIA_PREFIX+identity+'/video-native480.mp4',native_last_frame_url=self.public_base_url+VIDEO_MEDIA_PREFIX+identity+'/native-last-frame.png')
        (folder/'enhancement.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        result=dict(result);result['metadata']=metadata;result['url']=metadata['url'];result['data']=[dict(url=metadata['url'],mime_type='video/mp4')]
        return result

    def upscale_saved(self,payload,cfg,budget):
        if not isinstance(payload,dict) or set(payload)-{'video_id','enhance_faces'}:raise VideoServiceError('Ожидаются video_id и необязательный enhance_faces.',status=422)
        identity=payload.get('video_id');faces=payload.get('enhance_faces',False)
        if not isinstance(identity,str) or not re.fullmatch(r'[0-9a-f]{32}',identity) or type(faces) is not bool:raise VideoServiceError('Некорректный video_id/enhance_faces.',status=422)
        original=(self.outputs/identity).resolve();service=original/'service.json'
        if not original.is_relative_to(self.outputs) or not service.is_file() or not (original/'native.avi').is_file():raise VideoServiceError('Исходное видео не найдено.','video_not_found',404)
        saved=json.loads(service.read_text(encoding='utf-8'));metadata=dict(saved['metadata']);new_id=uuid.uuid4().hex;target=self.outputs/new_id;target.mkdir()
        for name in ['native.avi','video.mp4']:
            source=original/('video-native480.mp4' if name=='video.mp4' and (original/'video-native480.mp4').is_file() else name)
            shutil.copy2(source,target/name)
        shutil.copy2(original/('native-last-frame.png' if (original/'native-last-frame.png').is_file() else 'last-frame.png'),target/'last-frame.png')
        metadata.update(id=new_id,url=self.public_base_url+VIDEO_MEDIA_PREFIX+new_id+'/video.mp4',relative_url=VIDEO_MEDIA_PREFIX+new_id+'/video.mp4',
            last_frame_url=self.public_base_url+VIDEO_MEDIA_PREFIX+new_id+'/last-frame.png',source_video_id=identity)
        result=dict(id=new_id,object='video',created=int(time.time()),metadata=metadata,url=metadata['url'])
        result=self.enhance(result,cfg,budget,upscale_to='720p',faces=faces)
        (target/'service.json').write_text(json.dumps(dict(created=result['created'],metadata=result['metadata']),indent=2)+'\n')
        return result

    def open_media(self,path,headers=None):
        decoded=urllib.parse.unquote(urllib.parse.urlsplit(path).path)
        match=re.fullmatch(re.escape(VIDEO_MEDIA_PREFIX)+r'([0-9a-f]{32})/(video\.mp4|video-native480\.mp4|last-frame\.png|native-last-frame\.png)',decoded)
        if not match:raise VideoServiceError('Видео не найдено.','video_not_found',404)
        file=(self.outputs/match[1]/match[2]).resolve()
        if not file.is_relative_to(self.outputs) or not file.is_file():
            raise VideoServiceError('Видео не найдено.','video_not_found',404)
        total=file.stat().st_size
        if not 0<total<=self.max_media_bytes:
            raise VideoServiceError('Размер сохранённого видео вне лимита.','video_media_size_limit',413)
        start,end,status=0,total-1,200
        value=(headers or {}).get('Range') or (headers or {}).get('range')
        if value:
            bound=re.fullmatch(r'bytes=(\d*)-(\d*)',str(value))
            error_headers={'Content-Range':f'bytes */{total}'}
            if not bound or not any(bound.groups()):raise VideoServiceError('Некорректный Range.','invalid_range',416,error_headers)
            if bound[1]:start=int(bound[1]);end=min(int(bound[2]) if bound[2] else total-1,total-1)
            else:
                suffix=int(bound[2])
                if suffix<=0:raise VideoServiceError('Некорректный Range.','invalid_range',416,error_headers)
                start=max(0,total-suffix)
            if start>=total or start>end:raise VideoServiceError('Range вне файла.','invalid_range',416,error_headers)
            status=206
        returned={'Content-Type':'video/mp4' if match[2].endswith('.mp4') else 'image/png',
                  'Content-Length':str(end-start+1),'Accept-Ranges':'bytes',
                  'X-Content-Type-Options':'nosniff','Cache-Control':'no-store'}
        if status==206:returned['Content-Range']=f'bytes {start}-{end}/{total}'
        return MediaResponse(file,status,returned,start,end-start+1)

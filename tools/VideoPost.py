"""Bounded CPU decode/encode + DirectML SR and optional guarded face restoration."""
from pathlib import Path
import hashlib,json,os,subprocess,time,gc
import cv2,numpy as np
from PIL import Image
from PhotoUpscale import PhotoUpscaler
from DetailerProxy import FaceDetailer
from FastFaceRestore import Restorer,FeatureGuard

MODELS={
    'clearreality':('ClearRealityV1-fp32.onnx',4,'bbce9d5a653281cfae07788d620bd4ec45712709bdf6349a06a893159efd97ce'),
    'paragon2x':('video/paragon2x/model.onnx',2,'02c21d316890651dc3d7ac3297b6c3e33ab42491fb18f657d56715974fbc8b22')}
PARAGON_DATA_SHA='c8ddb04cc7415390194206f38c9de9108a21d07724908f49c89127d887b791c6'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def process_video(source,destination,root,model='clearreality',faces=False,temporal_faces=.25,timeout=600,profile_gpu=False,target_short_edge=720,face_provider='openvino',face_visibility=.2,freeze_face_initializers=False,face_similarity=.97,detector_resolution=960,max_faces=2):
    root=Path(root).resolve();source=Path(source).resolve();destination=Path(destination).resolve()
    if not source.is_relative_to(root) or not source.is_file():raise ValueError('Video source must be inside Root')
    if not any(destination.is_relative_to(root/folder) for folder in ['OUTPUTS/video','RESULTS/Video']):raise ValueError('Unexpected video postprocess destination')
    if destination.exists():raise ValueError('Existing postprocess result is preserved')
    if model not in (*MODELS,'lanczos') or not 0<=temporal_faces<=.5 or target_short_edge not in (480,720) or face_provider not in ('openvino','directml') or not 0<face_visibility<=.5:raise ValueError('Invalid bounded video enhancement option')
    destination.mkdir(parents=True);started=time.perf_counter();deadline=started+float(timeout)
    capture=cv2.VideoCapture(str(source),cv2.CAP_FFMPEG)
    if not capture.isOpened():raise ValueError('Cannot decode source video')
    width=int(capture.get(cv2.CAP_PROP_FRAME_WIDTH));height=int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT));fps=float(capture.get(cv2.CAP_PROP_FPS));count=round(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    if not 1<=count<=121 or not 1<=fps<=60 or width*height>2_000_000:raise ValueError('Video exceeds tested postprocessing bounds')
    scale=target_short_edge/min(width,height);size=(2*round(width*scale/2),2*round(height*scale/2))
    upscaler=None;restorer=None;guard=None;encoder=None;stderr=None;rows=[];gpu_report=None;face_gpu_report=None;previous_gray=None;previous_delta=None
    try:
        if model!='lanczos':
            name,native_scale,digest=MODELS[model];path=root/'UPSCALERS'/name
            if sha(path)!=digest:raise ValueError('Video SR model SHA mismatch')
            if model=='paragon2x' and sha(path.with_name('net_g_75000_fused_op18_fp32.onnx.data'))!=PARAGON_DATA_SHA:raise ValueError('Video SR external data SHA mismatch')
            upscaler=PhotoUpscaler(path,scale=native_scale,provider='directml',tile=0,output_scale=native_scale,
                profile_prefix=str(destination/'ort-first-frame') if profile_gpu else None)
        if faces:
            guard=FeatureGuard(root/'DETAILERS/faces/face_recognition_sface_2021dec.onnx')
            if not .97<=face_similarity<=1 or type(detector_resolution) is not int or not 640<=detector_resolution<=1280 or type(max_faces) is not int or not 1<=max_faces<=4:raise ValueError('Invalid bounded face settings')
            detector=FaceDetailer(detector_resolution=detector_resolution)
            restorer=Restorer(root/'DETAILERS/faces/gpen_bfr_512.onnx',provider=face_provider,detector=detector,guard=guard,profile_prefix=str(destination/'ort-gpen') if profile_gpu and face_provider=='directml' else None,freeze_initializers=freeze_face_initializers)
        load_seconds=time.perf_counter()-started
        output=destination/'video.mp4';temporary=destination/'video.work.mp4'
        command=[str(root/'runtime/ffmpeg/ffmpeg.exe'),'-hide_banner','-nostdin','-n','-f','rawvideo','-pixel_format','rgb24','-video_size',f'{size[0]}x{size[1]}','-framerate',str(fps),'-i','pipe:0','-an','-c:v','libx264','-preset','veryfast','-crf','18','-pix_fmt','yuv420p','-threads','8','-fps_mode','passthrough','-movflags','+faststart',str(temporary)]
        stderr=(destination/'encode.log').open('wb')
        encoder=subprocess.Popen(command,cwd=root,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW,
            env={**os.environ,'TEMP':str(root/'runtime/tmp'),'TMP':str(root/'runtime/tmp')})
        index=0
        while True:
            ok,frame=capture.read()
            if not ok:break
            if index>=count or time.perf_counter()>=deadline:raise TimeoutError('Video enhancement frame/deadline bound exceeded')
            begin=time.perf_counter();original=Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB))
            if upscaler:
                enhanced,sr=upscaler.upscale(original);enhanced=enhanced.resize(size,Image.Resampling.LANCZOS)
            else:enhanced=original.resize(size,Image.Resampling.LANCZOS);sr={}
            sr_seconds=time.perf_counter()-begin
            if profile_gpu and upscaler and index==0:
                profile=Path(upscaler.session.end_profiling());events=json.loads(profile.read_text())
                core={'Conv','ConvTranspose','Gemm','MatMul','Mish','PRelu','DepthToSpace'}
                cpu_core=[e.get('args',{}).get('op_name') for e in events if e.get('args',{}).get('provider')=='CPUExecutionProvider' and e.get('args',{}).get('op_name') in core]
                gpu_nodes=sum(e.get('args',{}).get('provider')=='DmlExecutionProvider' for e in events)
                gpu_report=dict(dml_nodes=gpu_nodes,cpu_core_nodes=cpu_core)
                if not gpu_nodes or cpu_core:raise RuntimeError('Video SR core did not stay on DirectML: '+str(gpu_report))
                profile.unlink()
            before=enhanced;face_report={};face_seconds=0;temporal_reverted=False
            if restorer:
                # Keep the same native-face size policy before/after720p SR.
                # A fixed240px cap caused medium faces to toggle on/off after SR.
                face_min=round(32*target_short_edge/480);face_max=round(192*target_short_edge/480)
                begin=time.perf_counter();enhanced,face_report=restorer.refine(before,dict(visibility=face_visibility,fidelity=1.,minimum_face=face_min,maximum_face=face_max,max_faces=max_faces,minimum_feature_similarity=face_similarity,mask_mode='face'))
                if profile_gpu and face_provider=='directml' and index==0:
                    profile=Path(restorer.session.end_profiling());events=json.loads(profile.read_text());profile.unlink()
                    core={'Conv','ConvTranspose','Gemm','MatMul'}
                    face_gpu_report=dict(dml_nodes=sum(e.get('args',{}).get('provider')=='DmlExecutionProvider' for e in events),cpu_core_nodes=[e.get('args',{}).get('op_name') for e in events if e.get('args',{}).get('provider')=='CPUExecutionProvider' and e.get('args',{}).get('op_name') in core])
                    if face_report['attempted_faces'] and (not face_gpu_report['dml_nodes'] or face_gpu_report['cpu_core_nodes']):raise RuntimeError('Face core did not stay on DirectML: '+str(face_gpu_report))
                base=np.asarray(before).astype(np.float32);candidate=np.asarray(enhanced).astype(np.float32);delta=candidate-base
                gray=cv2.cvtColor(np.asarray(before),cv2.COLOR_RGB2GRAY);small=cv2.resize(gray,(max(16,size[0]//4),max(16,size[1]//4)))
                if previous_gray is not None and previous_delta is not None and face_report['processed_faces'] and temporal_faces:
                    if float(np.mean(cv2.absdiff(small,previous_gray)))<30:
                        flow=cv2.calcOpticalFlowFarneback(small,previous_gray,None,.5,3,15,3,5,1.2,0)
                        flow=cv2.resize(flow,size);flow[:,:,0]*=size[0]/small.shape[1];flow[:,:,1]*=size[1]/small.shape[0]
                        yy,xx=np.mgrid[:size[1],:size[0]].astype(np.float32)
                        warped=cv2.remap(previous_delta,xx+flow[:,:,0],yy+flow[:,:,1],cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT)
                        mask=np.max(np.abs(delta),axis=2)>0
                        smooth=delta.copy();smooth[mask]=(1-temporal_faces)*delta[mask]+temporal_faces*warped[mask]
                        proposed=Image.fromarray(np.rint(np.clip(base+smooth,0,255)).astype(np.uint8))
                        if all(guard.similarity(before,proposed,f)>=face_similarity for f in face_report['faces'] if f['applied']):enhanced=proposed
                        else:temporal_reverted=True
                previous_delta=np.asarray(enhanced).astype(np.float32)-base;previous_gray=small
                face_seconds=time.perf_counter()-begin
            if index==0:
                original.save(destination/'input-first.png');before.save(destination/'sr-first.png');enhanced.save(destination/'output-first.png')
            pixels=np.asarray(enhanced.convert('RGB'));encoder.stdin.write(pixels.tobytes())
            rows.append(dict(frame=index,sr_seconds=sr_seconds,faces_seconds=face_seconds,processed_faces=face_report.get('processed_faces',0),temporal_guard_reverted=temporal_reverted,
                face_similarities=[f['feature_similarity'] for f in face_report.get('faces',[])],luma_mean=float(cv2.cvtColor(pixels,cv2.COLOR_RGB2GRAY).mean())))
            index+=1
        if index!=count:raise RuntimeError('Source frame count changed during decode')
        encoder.stdin.close();encoder.wait(timeout=max(.1,deadline-time.perf_counter()))
        if encoder.returncode:raise RuntimeError('Video encoder failed')
        temporary.rename(output);original.save(destination/'input-last.png');before.save(destination/'sr-last.png');enhanced.save(destination/'output-last.png')
        check=cv2.VideoCapture(str(output),cv2.CAP_FFMPEG)
        actual=(round(check.get(cv2.CAP_PROP_FRAME_COUNT)),check.get(cv2.CAP_PROP_FPS),round(check.get(cv2.CAP_PROP_FRAME_WIDTH)),round(check.get(cv2.CAP_PROP_FRAME_HEIGHT)));check.release()
        if actual[0]!=count or abs(actual[1]-fps)>.001 or actual[2:]!=size:raise RuntimeError('Video SR changed frame count/FPS/size unexpectedly')
        receipt=dict(ok=True,model=model,faces=faces,face_provider=face_provider,face_visibility=face_visibility,face_size_policy=dict(minimum=round(32*target_short_edge/480),maximum=round(192*target_short_edge/480),reference_short_edge=480),face_gpu_profile=face_gpu_report,frozen_face_initializers=restorer.metadata.get('in_memory_frozen_initializers') if restorer else None,temporal_face_strength=temporal_faces,source_dimensions=[width,height],dimensions=list(size),frames=count,fps=fps,
            total_seconds=time.perf_counter()-started,load_seconds=load_seconds,sr_seconds=sum(r['sr_seconds'] for r in rows),face_seconds=sum(r['faces_seconds'] for r in rows),
            processed_faces=sum(r['processed_faces'] for r in rows),gpu_profile=gpu_report,frames_details=rows,output=str(output),output_sha256=sha(output),output_bytes=output.stat().st_size,
            geometry=f'Aspect ratio preserved; short edge{target_short_edge}, even dimensions; no stretching, interpolation, frame duplication or drop.',quality='Per-frame SR; no guarantee of recovering missing detail. Optional guarded face residual smoothing is motion-compensated.')
        (destination/'result.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');return receipt
    finally:
        capture.release()
        if encoder and encoder.poll() is None:encoder.kill();encoder.wait(timeout=10)
        if stderr:stderr.close()
        if restorer:restorer.close()
        if upscaler:upscaler.close()
        gc.collect()

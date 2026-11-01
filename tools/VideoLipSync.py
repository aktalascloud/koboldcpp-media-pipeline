"""Optional audio-driven mouth postprocessing. Wav2Lip weights are non-commercial.

Uses the original Wav2Lip mel/face input convention, implemented with NumPy.
Source specification: https://github.com/Rudrabha/Wav2Lip (audio.py/hparams.py).
No automatic speaker selection, video extension, face generation or audio stretching.
"""
from pathlib import Path
import hashlib,json,math,subprocess,time,wave
import cv2,numpy as np

def processor_fingerprint():
    import inspect
    return hashlib.sha256((inspect.getsource(mel_spectrogram)+inspect.getsource(process)).encode()).hexdigest()

def capabilities(root,provider='cpu'):
    root=Path(root)
    try:
        manifest=root/'MODELS/detailers/lipsync/manifest.json';data=json.loads(manifest.read_text(encoding='utf-8'))
        path=(manifest.parent/data['file']).resolve()
        installed=path.is_relative_to((root/'MODELS').resolve()) and path.is_file()
        validated=installed and data.get('validated') is True and data.get('processor_sha256')==processor_fingerprint()
    except (OSError,ValueError,KeyError):installed=validated=False
    return {'supported':validated,'installed':installed,'engine':'Wav2Lip GAN96 ONNX','provider':provider,'modes':['voiceover','onscreen'] if validated else ['voiceover'],'endpoint':'/v1/videos/lipsync','import_endpoint':'/v1/videos/import','interpolation_endpoint':'/v1/videos/interpolate','languages':['ru','en'],'fps':[24,48,60],'max_seconds':30,'max_pixels':2_000_000,'target':'explicit normalized target_box at speech start; reject missing/ambiguous track','identity_guaranteed':False,'audio_conditioning':'exact stored TTS WAV; reusable speech_video_id, no audio_id contract','license':'Original Wav2Lip non-commercial research/personal use only; optional original-provider weights, not mirrored','validation_scope':'Reference tests on Haswell/RX580; no speed claim for another machine'}

def assets(root):
    root=Path(root).resolve();manifest=root/'MODELS/detailers/lipsync/manifest.json'
    data=json.loads(manifest.read_text(encoding='utf-8'));path=(manifest.parent/data['file']).resolve()
    if not path.is_relative_to(root/'MODELS') or hashlib.file_digest(path.open('rb'),'sha256').hexdigest()!=data['sha256']:raise ValueError('Lip-sync model SHA mismatch')
    return path,data

def mel_spectrogram(audio):
    """16kHz, preemphasis .97, Slaney-normalized80mel, FFT800/hop200/Hann."""
    audio=np.asarray(audio,dtype=np.float32)
    audio=np.concatenate((audio[:1],audio[1:]-.97*audio[:-1]))
    padded=np.pad(audio,(400,400),mode='reflect')
    windows=np.lib.stride_tricks.sliding_window_view(padded,800)[::200]
    spectrum=np.abs(np.fft.rfft(windows*(.5-.5*np.cos(2*np.pi*np.arange(800)/800)),axis=1)).T
    def hz_to_mel(h):return np.where(h<1000,h/(200/3),15+np.log(np.maximum(h,1)/1000)/(np.log(6.4)/27))
    def mel_to_hz(m):return np.where(m<15,m*(200/3),1000*np.exp((m-15)*(np.log(6.4)/27)))
    frequencies=mel_to_hz(np.linspace(hz_to_mel(np.array(55.)),hz_to_mel(np.array(7600.)),82))
    fft=np.arange(401)*20;ramps=frequencies[:,None]-fft[None,:];widths=np.diff(frequencies)
    filters=np.maximum(0,np.minimum(-ramps[:-2]/widths[:-1,None],ramps[2:]/widths[1:,None]))
    filters*=2/(frequencies[2:]-frequencies[:-2])[:,None]
    db=20*np.log10(np.maximum(1e-5,filters@spectrum))-20
    return np.clip(8*((db+100)/100)-4,-4,4).astype(np.float32)

def process(source,audio,destination,root,target_box,timeout=180,provider='directml',profile_gpu=False,start_seconds=0):
    root=Path(root).resolve();source=Path(source).resolve();audio=Path(audio).resolve();dest=Path(destination).resolve()
    if any(not p.is_relative_to(root/'RESULTS') for p in (source,audio,dest)) or dest.exists():raise ValueError('Lip-sync uses stored owned artifacts only')
    if not isinstance(target_box,list) or len(target_box)!=4 or any(type(x) not in (float,int) or not math.isfinite(x) for x in target_box):raise ValueError('Explicit normalized target_box[x,y,w,h] required')
    x,y,w,h=target_box
    if not 0<=x<x+w<=1 or not 0<=y<y+h<=1 or min(w,h)<=0:raise ValueError('Invalid target_box')
    model,provenance=assets(root);dest.mkdir(parents=True);began=time.perf_counter()
    cap=cv2.VideoCapture(str(source));fps=cap.get(cv2.CAP_PROP_FPS);count=round(cap.get(cv2.CAP_PROP_FRAME_COUNT));width=round(cap.get(cv2.CAP_PROP_FRAME_WIDTH));height=round(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if not 1<=count<=1800 or not 1<=fps<=60 or width*height>2_000_000 or count/fps>30.000001:cap.release();raise ValueError('Lip-sync limit:30s/60FPS/2MP')
    ffmpeg=str(root/'runtime/ffmpeg/ffmpeg.exe');mono=dest/'speech-16k.wav'
    subprocess.run([ffmpeg,'-v','error','-nostdin','-i',str(audio),'-ac','1','-ar','16000','-c:a','pcm_s16le',str(mono)],check=True,timeout=min(30,timeout))
    with wave.open(str(mono),'rb') as wav:samples=np.frombuffer(wav.readframes(wav.getnframes()),dtype='<i2').astype(np.float32)/32768
    duration=len(samples)/16000
    if type(start_seconds) not in (int,float) or not math.isfinite(start_seconds) or not 0<=start_seconds<count/fps or start_seconds+duration>count/fps+1/16000:cap.release();raise ValueError('Speech timing exceeds video duration; no trimming or stretching')
    mel=mel_spectrogram(samples);mel=np.pad(mel,((0,0),(0,16)),constant_values=-4)
    import onnxruntime as ort
    options=ort.SessionOptions();options.intra_op_num_threads=8;options.inter_op_num_threads=1
    options.enable_mem_pattern=False;options.execution_mode=ort.ExecutionMode.ORT_SEQUENTIAL
    if profile_gpu:options.enable_profiling=True;options.profile_file_prefix=str(dest/'ort')
    providers=['DmlExecutionProvider'] if provider=='directml' else ['CPUExecutionProvider']
    session=ort.InferenceSession(str(model),sess_options=options,providers=providers)
    from DetailerProxy import FaceDetailer
    from PIL import Image
    detector=FaceDetailer(detector_resolution=960)
    recognizer=cv2.FaceRecognizerSF.create(str(root/'MODELS/detailers/faces/face_recognition_sface_2021dec.onnx'),'')
    reference_feature=None;track_similarities=[]
    target=np.array([x*width,y*height,w*width,h*height]);centroid=target[:2]+target[2:]/2
    encoder=None;stderr=None;reports=[];inference=0
    try:
        stderr=(dest/'encode.log').open('wb')
        encoder=subprocess.Popen([ffmpeg,'-v','error','-nostdin','-f','rawvideo','-pix_fmt','bgr24','-s',f'{width}x{height}','-r',str(fps),'-i','pipe:0','-an','-c:v','libx264','-preset','veryfast','-crf','18','-threads','16','-pix_fmt','yuv420p',str(dest/'silent.mp4')],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW)
        for index in range(count):
            if time.perf_counter()-began>=timeout:raise TimeoutError('Lip-sync deadline exceeded')
            ok,frame=cap.read()
            if not ok:raise ValueError('Truncated input video')
            if start_seconds<=index/fps<start_seconds+duration:
                found=detector.detect(Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)),minimum=24,maximum=max(width,height))
                ranked=sorted(found,key=lambda f:np.linalg.norm(np.array(f['box'][:2])+np.array(f['box'][2:])/2-centroid))
                if not ranked:raise ValueError('Target face is not detectable; no invented face')
                selected=ranked[0];box=np.array(selected['box']);center=box[:2]+box[2:]/2
                if np.linalg.norm(center-centroid)>max(target[2:])*.6:raise ValueError('Target face track lost')
                if len(ranked)>1:
                    second=np.array(ranked[1]['box']);distance=np.linalg.norm(second[:2]+second[2:]/2-centroid)
                    if distance-np.linalg.norm(center-centroid)<min(box[2:])*.3:raise ValueError('Ambiguous speaker face; provide a more precise target_box')
                face_row=np.array([*selected['box'],*selected['landmarks'],selected['confidence']],np.float32)
                feature=recognizer.feature(recognizer.alignCrop(frame,face_row)).reshape(-1).astype(np.float64)
                feature/=max(np.linalg.norm(feature),1e-10)
                if reference_feature is None:reference_feature=feature.copy()
                similarity=float(np.dot(reference_feature,feature));track_similarities.append(similarity)
                # SFace/LFW verification is not a calibrated hard threshold for
                # a small synthetic face changing pose. Keep it as a diagnostic;
                # explicit spatial continuity and ambiguity rejection own the slot.
                centroid=center
                a,b=max(0,int(box[0])),max(0,int(box[1]));c,d=min(width,int(box[0]+box[2])),min(height,int(box[1]+box[3]+10))
                crop=cv2.resize(frame[b:d,a:c],(96,96));masked=crop.copy();masked[48:]=0
                face=np.concatenate((masked,crop),axis=2).transpose(2,0,1)[None].astype(np.float32)/255
                offset=int((index/fps-start_seconds)*80);chunk=mel[:,offset:offset+16]
                if chunk.shape[1]<16:chunk=np.pad(chunk,((0,0),(0,16-chunk.shape[1])),constant_values=-4)
                tick=time.perf_counter();prediction=session.run(None,{'source':chunk[None,None],'target':face})[0];inference+=time.perf_counter()-tick
                if not np.isfinite(prediction).all():raise RuntimeError('Lip-sync model returned invalid pixels')
                prediction=np.clip(prediction[0].transpose(1,2,0)*255,0,255).astype(np.uint8)
                patch=cv2.resize(prediction,(c-a,d-b),interpolation=cv2.INTER_CUBIC)
                # Only the lower face; eyes, body and all pixels outside the ROI unchanged before encode.
                mask=np.zeros((d-b,c-a),np.float32);cv2.ellipse(mask,(mask.shape[1]//2,int(mask.shape[0]*.74)),(max(1,int(mask.shape[1]*.42)),max(1,int(mask.shape[0]*.25))),0,0,360,1,-1)
                mask=cv2.GaussianBlur(mask,(0,0),max(1,mask.shape[1]*.035))[:,:,None]
                frame[b:d,a:c]=np.rint(frame[b:d,a:c]*(1-mask)+patch*mask).astype(np.uint8)
                if index%max(1,round(fps/4))==0:cv2.imwrite(str(dest/f'frame-{index:04}.jpg'),frame[b:d,a:c])
                reports.append([a,b,c,d])
            encoder.stdin.write(frame.tobytes())
        encoder.stdin.close();encoder.wait(timeout=max(1,timeout-(time.perf_counter()-began)))
        if encoder.returncode:raise RuntimeError('Lip-sync encoder failed')
        delay=round(start_seconds*1000)
        subprocess.run([ffmpeg,'-v','error','-nostdin','-i',str(dest/'silent.mp4'),'-i',str(audio),'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','192k','-af',f'adelay={delay}:all=1,apad,atrim=duration={count/fps}','-t',str(count/fps),'-movflags','+faststart',str(dest/'video.mp4')],check=True,timeout=max(1,timeout-(time.perf_counter()-began)))
        gpu_report=None
        if profile_gpu:
            profile=Path(session.end_profiling());events=json.loads(profile.read_text());profile.unlink()
            gpu_report={'dml_nodes':sum(e.get('args',{}).get('provider')=='DmlExecutionProvider' for e in events),'cpu_core_nodes':[e.get('args',{}).get('op_name') for e in events if e.get('args',{}).get('provider')=='CPUExecutionProvider' and e.get('args',{}).get('op_name') in ('Conv','ConvTranspose','MatMul','Gemm')]}
            if provider=='directml' and (not gpu_report['dml_nodes'] or gpu_report['cpu_core_nodes']):raise RuntimeError('Lip-sync core did not remain on DirectML')
        report={'engine':'Wav2Lip GAN96 ONNX','model_sha256':provenance['sha256'],'license':'Non-commercial research/personal use only; original Wav2Lip terms','provider':provider,'gpu_profile':gpu_report,'input_fps':fps,'frames':count,'speech_seconds':duration,'duration_seconds':count/fps,'seconds':time.perf_counter()-began,'inference_seconds':inference,'processed_frames':len(reports),'audio_sha256':hashlib.file_digest(audio.open('rb'),'sha256').hexdigest(),'mouth_rois':reports,'video_encoding':'libx264 CRF18; only lower-face pixels modified before full-frame encoding','identity_guaranteed':False,'output':str(dest/'video.mp4')}
        report.update(track_guard='Explicit target_box + bounded spatial continuity; reject missing/ambiguous targets. SFace source-drift diagnostic, not an identity guarantee',minimum_track_similarity=min(track_similarities) if track_similarities else None,source_drift_frames=sum(s<.363 for s in track_similarities))
        report['processor_sha256']=processor_fingerprint()
        (dest/'report.json').write_text(json.dumps(report,indent=2)+'\n');return report
    finally:
        cap.release()
        if encoder and encoder.poll() is None:encoder.kill();encoder.wait(timeout=10)
        if stderr:stderr.close()
        del session

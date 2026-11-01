"""Optional Vulkan interpolation of a completed video; no duration extension."""
from pathlib import Path
import subprocess,json,time,math,shutil,cv2
from OwnedMediaProcess import run_owned

def available(root,model_dir=None):
    import os
    root=Path(root)
    model=Path(model_dir) if model_dir else root/'MODELS/detailers/interpolation/rife-v4.6';model=model if model.is_absolute() else root/model
    paths=[root/'runtime/rife/rife-ncnn-vulkan.exe',model/'flownet.bin',model/'flownet.param']
    vcomp=(root/'runtime/rife/vcomp140.dll').is_file() or (Path(os.environ.get('SystemRoot','C:/Windows'))/'System32/vcomp140.dll').is_file()
    return all(p.is_file() for p in paths) and vcomp

def interpolate_video(source,destination,root,timeout=180,model_dir=None,target_fps=48):
    if type(target_fps) is not int or target_fps not in (48,60):raise ValueError('RIFE target FPS must be48 or60')
    if not available(root,model_dir):raise ValueError('Optional RIFE/runtime dependency is not initialized')
    root=Path(root).resolve();source=Path(source).resolve();dest=Path(destination).resolve();began=time.perf_counter()
    if not any(dest.is_relative_to(root/p) for p in ('RESULTS/generated/video','RESULTS/checks')) or dest.exists():raise ValueError('Invalid RIFE destination')
    cap=cv2.VideoCapture(str(source));frames=round(cap.get(cv2.CAP_PROP_FRAME_COUNT));fps=cap.get(cv2.CAP_PROP_FPS);width=round(cap.get(cv2.CAP_PROP_FRAME_WIDTH));height=round(cap.get(cv2.CAP_PROP_FRAME_HEIGHT));cap.release()
    if not 5<=frames<=720 or width*height>2_000_000 or abs(fps-24)>.001:raise ValueError('RIFE expects24FPS, at most30seconds/2MP')
    dest.mkdir(parents=True);inp=dest/'input';out=dest/'output';inp.mkdir();out.mkdir();ffmpeg=str(root/'runtime/ffmpeg/ffmpeg.exe')
    def remaining():
        value=timeout-(time.perf_counter()-began)
        if value<=0:raise TimeoutError('RIFE exceeded shared video budget')
        return value
    subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-nostdin','-y','-i',str(source),str(inp/'%08d.png')],check=True,timeout=remaining())
    count=math.ceil(frames*target_fps/24)
    rife_count=count
    if target_fps==60 and frames%2:
        # ncnn maps i*input_count/output_count. Pad one endpoint for an exact
        # 24->60 time grid (4n+1 inputs), then encode only the requested duration.
        shutil.copy2(sorted(inp.glob('*.png'))[-1],inp/f'{frames+1:08d}.png')
        rife_count=(frames+1)*5//2
    command=[str(root/'runtime/rife/rife-ncnn-vulkan.exe'),'-i',str(inp),'-o',str(out),'-n',str(rife_count),'-m',str((Path(model_dir) if Path(model_dir).is_absolute() else root/Path(model_dir)) if model_dir else root/'MODELS/detailers/interpolation/rife-v4.6'),'-g','0','-j','1:1:1','-f','%08d.png']
    process=run_owned(command,root,dest,remaining());files=sorted(out.glob('*.png'))
    if len(files)!=rife_count:raise RuntimeError('RIFE frame count mismatch')
    target=dest/'video.mp4'
    subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-nostdin','-y','-framerate',str(target_fps),'-i',str(out/'%08d.png'),'-frames:v',str(count),'-c:v','libx264','-preset','veryfast','-crf','18','-pix_fmt','yuv420p','-threads','16','-movflags','+faststart',str(target)],check=True,timeout=remaining())
    cap=cv2.VideoCapture(str(target));actual=round(cap.get(cv2.CAP_PROP_FRAME_COUNT));actual_fps=cap.get(cv2.CAP_PROP_FPS);cap.release()
    if actual!=count or abs(actual_fps-target_fps)>.001:raise RuntimeError('Encoded RIFE FPS/frame count mismatch')
    # These folders are created exclusively by this call, never user-supplied.
    for temporary in (inp,out):
        if temporary.is_symlink() or not temporary.resolve().is_relative_to(dest):raise RuntimeError('Unexpected RIFE temporary path')
        shutil.rmtree(temporary)
    return {'input_frames':frames,'output_frames':count,'fps':target_fps,'dimensions':[width,height],'seconds':time.perf_counter()-began,'output':str(target),'native_motion_duration_seconds':frames/24,'output_duration_seconds':count/target_fps,'duration_rounding_seconds':count/target_fps-frames/24,'method':'RIFE4.6/ncnn Vulkan; motion interpolation, endpoint padding; CFR duration rounding less than one output frame','worker':process}

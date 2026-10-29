"""Optional Vulkan interpolation of a completed video; no duration extension."""
from pathlib import Path
import subprocess,json,time,cv2
from OwnedMediaProcess import run_owned

def available(root):
    import os
    root=Path(root)
    paths=[root/'runtime/rife/rife-ncnn-vulkan.exe',root/'DETAILERS/interpolation/rife-v4.6/flownet.bin',root/'DETAILERS/interpolation/rife-v4.6/flownet.param']
    vcomp=(root/'runtime/rife/vcomp140.dll').is_file() or (Path(os.environ.get('SystemRoot','C:/Windows'))/'System32/vcomp140.dll').is_file()
    return all(p.is_file() for p in paths) and vcomp

def interpolate_video(source,destination,root,timeout=180):
    if not available(root):raise ValueError('Optional RIFE/runtime dependency is not initialized')
    root=Path(root).resolve();source=Path(source).resolve();dest=Path(destination).resolve();began=time.perf_counter()
    if not any(dest.is_relative_to(root/p) for p in ('OUTPUTS/video','RESULTS/Video')) or dest.exists():raise ValueError('Invalid RIFE destination')
    cap=cv2.VideoCapture(str(source));frames=round(cap.get(cv2.CAP_PROP_FRAME_COUNT));fps=cap.get(cv2.CAP_PROP_FPS);width=round(cap.get(cv2.CAP_PROP_FRAME_WIDTH));height=round(cap.get(cv2.CAP_PROP_FRAME_HEIGHT));cap.release()
    if not 5<=frames<=121 or abs(fps-24)>.001:raise ValueError('RIFE expects a bounded24FPS clip')
    dest.mkdir(parents=True);inp=dest/'input';out=dest/'output';inp.mkdir();out.mkdir();ffmpeg=str(root/'runtime/ffmpeg/ffmpeg.exe')
    def remaining():
        value=timeout-(time.perf_counter()-began)
        if value<=0:raise TimeoutError('RIFE exceeded shared video budget')
        return value
    subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-nostdin','-y','-i',str(source),str(inp/'%08d.png')],check=True,timeout=remaining())
    command=[str(root/'runtime/rife/rife-ncnn-vulkan.exe'),'-i',str(inp),'-o',str(out),'-n',str(frames*2),'-m',str(root/'DETAILERS/interpolation/rife-v4.6'),'-g','0','-j','1:1:1','-f','%08d.png']
    process=run_owned(command,root,dest,remaining());files=sorted(out.glob('*.png'))
    if len(files)!=frames*2:raise RuntimeError('RIFE frame count mismatch')
    target=dest/'video.mp4'
    subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-nostdin','-y','-framerate','48','-i',str(out/'%08d.png'),'-c:v','libx264','-preset','veryfast','-crf','18','-pix_fmt','yuv420p','-threads','8','-movflags','+faststart',str(target)],check=True,timeout=remaining())
    return {'input_frames':frames,'output_frames':frames*2,'fps':48,'dimensions':[width,height],'seconds':time.perf_counter()-began,'output':str(target),'native_motion_duration_seconds':frames/24,'method':'RIFE4.6/ncnn Vulkan; original frames retained, interpolated intermediates and one endpoint repeat','worker':process}

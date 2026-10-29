"""Bounded owned Windows subprocesses; never terminate an unrelated PID."""
import ctypes,subprocess,time,json
from ctypes import wintypes as w
from pathlib import Path

def job_object():
    class Basic(ctypes.Structure):
        _fields_=[('user',ctypes.c_longlong),('job_user',ctypes.c_longlong),('flags',w.DWORD),('minimum',ctypes.c_size_t),('maximum',ctypes.c_size_t),('count',w.DWORD),('affinity',ctypes.c_size_t),('priority',w.DWORD),('scheduling',w.DWORD)]
    class IO(ctypes.Structure):_fields_=[(n,ctypes.c_ulonglong) for n in ['r','w','o','rb','wb','ob']]
    class Extended(ctypes.Structure):_fields_=[('basic',Basic),('io',IO),('process_mem',ctypes.c_size_t),('job_mem',ctypes.c_size_t),('peak_process',ctypes.c_size_t),('peak_job',ctypes.c_size_t)]
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    k.CreateJobObjectW.argtypes=[ctypes.c_void_p,w.LPCWSTR];k.CreateJobObjectW.restype=w.HANDLE
    k.SetInformationJobObject.argtypes=[w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD]
    k.AssignProcessToJobObject.argtypes=[w.HANDLE,w.HANDLE];k.CloseHandle.argtypes=[w.HANDLE]
    job=k.CreateJobObjectW(None,None);info=Extended();info.basic.flags=0x2000
    if not job or not k.SetInformationJobObject(job,9,ctypes.byref(info),ctypes.sizeof(info)):raise ctypes.WinError(ctypes.get_last_error())
    return k,job

def run_owned(command,root,destination,timeout,memory_guard=False):
    root=Path(root).resolve();destination=Path(destination).resolve()
    if not any(destination.is_relative_to(root/f) for f in ('OUTPUTS/video','RESULTS/Video')):raise ValueError('Unexpected owned media destination')
    destination.mkdir(parents=True,exist_ok=True);k,job=job_object();began=time.perf_counter();monitor=None
    if not 0<float(timeout)<=900:raise ValueError('Invalid media timeout')
    child=None
    try:
        with (destination/'worker.log').open('wb') as log:
            child=subprocess.Popen(command,cwd=root,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
            if not k.AssignProcessToJobObject(job,int(child._handle)):raise RuntimeError('Owned media job assignment failed')
            if memory_guard:
                monitor_log=(destination/'gpu-monitor.log').open('wb')
                monitor=subprocess.Popen(['powershell.exe','-NoProfile','-NonInteractive','-File',str(root/'tools/MediaGpuMonitor.ps1'),'-OutputPath',str(destination/'gpu.jsonl'),'-TargetPid',str(child.pid)],cwd=root,creationflags=subprocess.CREATE_NO_WINDOW,stdout=monitor_log,stderr=subprocess.STDOUT)
                monitor_log.close()
                if not k.AssignProcessToJobObject(job,int(monitor._handle)):raise RuntimeError('GPU monitor ownership failed')
            spill=None
            while child.poll() is None:
                if time.perf_counter()-began>timeout:raise TimeoutError('Owned media process exceeded request budget')
                if monitor is not None:
                    if monitor.poll() is not None:raise RuntimeError('GPU memory monitor unavailable; stopped owned decoder')
                    try:
                        row=json.loads((destination/'gpu.jsonl').read_text().splitlines()[-1]);excessive=row['dedicated']>6500*2**20 or row['shared']>1024*2**20
                        spill=(spill or time.monotonic()) if excessive else None
                        if spill and time.monotonic()-spill>=8:raise RuntimeError('Pro exceeded6500MiB dedicated/1024MiB shared policy')
                    except (OSError,ValueError,IndexError):pass
                time.sleep(.2)
            if child.returncode:raise RuntimeError('Owned media worker failed:'+str(child.returncode))
        peaks={}
        if memory_guard:
            rows=[json.loads(line) for line in (destination/'gpu.jsonl').read_text().splitlines()]
            peaks={key+'_mib':max(r[key] for r in rows)/2**20 for key in ('dedicated','shared')}
        return {'worker_pid':child.pid,'worker_wall_seconds':time.perf_counter()-began,'gpu_peak':peaks}
    finally:
        k.CloseHandle(job)
        if child:
            try:child.wait(timeout=10)
            except subprocess.TimeoutExpired:pass

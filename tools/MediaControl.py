"""Pause only the verified idle media service; shared by deployment and desktop settings."""
import ctypes
import time
from pathlib import Path
from BackendSupervisor import WindowsOperations,from_helper
from SupervisorLaunch import _verify_front

def stop_services(root):
    root=Path(root).resolve();ops=WindowsOperations();helper=root/'Helper.kcpps'
    import json
    data=json.loads(helper.read_text(encoding='utf-8'));gd=json.loads(data['gendefaults']);port=int(gd['kcpp_proxy']['port'])
    if ops.listeners(port):
        health,identity=_verify_front(ops,port,root,helper,root/'tools/SupervisorLaunch.py',root/'runtime/python/pythonw.exe')
        if health.get('active'):raise RuntimeError('Генерация выполняется. Примените настройки после её завершения.')
        active=health.get('backend_supervisor') or {}
        if active.get('native_profile'):
            native_port=int(gd['kcpp_proxy']['backend_supervisor']['profiles'][active['native_profile']]['port'])
            if not ops.api(native_port,'/api/extra/perf').get('idle',False):raise RuntimeError('Native занят; настройки сохранены без изменений.')
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.OpenProcess.argtypes=[ctypes.c_ulong,ctypes.c_int,ctypes.c_ulong];kernel.OpenProcess.restype=ctypes.c_void_p
        kernel.TerminateProcess.argtypes=[ctypes.c_void_p,ctypes.c_uint];kernel.CloseHandle.argtypes=[ctypes.c_void_p]
        handle=kernel.OpenProcess(0x100001,False,identity['pid'])
        if not handle:raise ctypes.WinError(ctypes.get_last_error())
        try:
            actual=ops.process(identity['pid'])
            if not actual or any(actual[k]!=identity[k] for k in ('created_ticks','executable')):raise RuntimeError('Владелец API изменился; процесс сохранён.')
            if ops.api(port,'/health').get('active'):raise RuntimeError('Генерация началась; процесс сохранён.')
            if not kernel.TerminateProcess(handle,0):raise ctypes.WinError(ctypes.get_last_error())
        finally:kernel.CloseHandle(handle)
        deadline=time.monotonic()+20
        while ops.listeners(port) and time.monotonic()<deadline:time.sleep(.2)
        if ops.listeners(port):raise RuntimeError('API не освободил порт.')
    supervisor=from_helper(helper,root=root)
    try:return supervisor,supervisor.stop_idle()
    except BaseException:supervisor.close();raise

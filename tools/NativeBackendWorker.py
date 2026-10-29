"""Visible Native console and lossless ownership/log records. No server forwarding."""
from __future__ import annotations
import argparse
import ctypes
import os
from pathlib import Path
import re
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from BackendSupervisor import (PROFILES, SupervisorError, WindowsOperations,
                               read_json, root_path, sha256, write_json)


def native_arguments(executable, helper):
    # Native's graceful loopback shutdown API requires this flag. The lifetime
    # named-port mutex and immediate prelaunch free-port check guard our races.
    return [str(executable), '--config', str(helper), '--skiplauncher', '--singleinstance']


def main():
    parser = argparse.ArgumentParser()
    for field in ('root', 'profile', 'executable', 'executable-sha256', 'helper',
                  'helper-sha256', 'run-id', 'active-file', 'log-file'):
        parser.add_argument('--'+field, required=True)
    parser.add_argument('--port', type=int, required=True)
    args = parser.parse_args()
    root = Path(args.root).resolve()
    if args.profile not in PROFILES or not re.fullmatch(r'[0-9a-f]{32}', args.run_id):
        raise SupervisorError('Invalid Native worker identity.', 'invalid_ownership')
    executable, helper = root_path(root, args.executable), root_path(root, args.helper)
    active_file, log_file = root_path(root, args.active_file), root_path(root, args.log_file)
    if sha256(executable) != args.executable_sha256 or sha256(helper) != args.helper_sha256:
        raise SupervisorError('Immutable worker executable/Helper changed.', 'profile_file_changed')
    h = read_json(helper)
    if h.get('host') not in ('127.0.0.1', 'localhost') or int(h.get('port', 0)) != args.port or int(h.get('port_param', args.port)) != args.port or h.get('onready') or h.get('launch') or h.get('singleinstance') is not True:
        raise SupervisorError('Unsafe Native worker Helper.', 'invalid_profile_config')
    temporary = root / 'runtime/tmp'
    temporary.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment.pop('KCPP_WAN_TAE_DECODER',None)
    environment.pop('KCPP_WAN_LATENT_SNAPSHOT',None)
    environment.pop('KCPP_WAN_LATENT_ONLY',None)
    capture=h.get('kcpp_video_capture_latents',False)
    if type(capture) is not bool or (capture and args.profile!='video'):
        raise SupervisorError('Latent capture is a video-only boolean.','invalid_profile_config')
    if capture:
        if not re.fullmatch(r'[0-9a-f]{32}',args.run_id):raise SupervisorError('Invalid capture run identity.','invalid_profile_config')
        capture_path=root_path(root,'runtime/tmp/wan-latents-'+args.run_id+'.bin')
        if capture_path.exists() or capture_path.with_suffix('.bin.partial').exists():raise SupervisorError('Capture target already exists.','profile_file_changed')
        environment['KCPP_WAN_LATENT_SNAPSHOT']=str(capture_path)
    latent_only=h.get('kcpp_video_latent_only',False)
    if type(latent_only) is not bool or (latent_only and (args.profile!='video' or not capture or h.get('kcpp_video_tae_decoder') is not None)):
        raise SupervisorError('Pro latent-only is video-only, requires capture and forbids Tiny.','invalid_profile_config')
    if latent_only:environment['KCPP_WAN_LATENT_ONLY']='1'
    decoder=h.get('kcpp_video_tae_decoder')
    if decoder is not None:
        if args.profile!='video' or not isinstance(decoder,dict) or set(decoder)!={'path','sha256'}:raise SupervisorError('Independent Tiny decoder is video-only and must be pinned.','invalid_profile_config')
        decoder_path=root_path(root,decoder['path'])
        if not decoder_path.is_file() or not 0<decoder_path.stat().st_size<64*1024**2 or sha256(decoder_path)!=decoder['sha256']:raise SupervisorError('Independent Tiny decoder identity mismatch.','profile_file_changed')
        environment['KCPP_WAN_TAE_DECODER']=str(decoder_path)
    environment['TMP'] = environment['TEMP'] = str(temporary)
    environment['PYTHONUNBUFFERED'] = '1'
    environment['PYTHONIOENCODING'] = 'utf-8'
    # The portable sidecar contains only measured Vulkan controls, never shell code.
    environment_file = root / 'runtime/native-environment.json'
    native_environment = read_json(environment_file) if environment_file.is_file() else {}
    allowed_environment = {'GGML_VK_ALLOW_GRAPHICS_QUEUE', 'GGML_VK_POLARIS_SAFE',
        'GGML_VK_MAX_NODES_PER_SUBMIT', 'GGML_VK_BATCHED_SUBMITS', 'GGML_VK_FORCE_MMVQ',
        'GGML_VK_DISABLE_MMVQ', 'GGML_VK_DISABLE_ASYNC', 'GGML_VK_GCN_TILE64',
        'GGML_VK_GCN_TILE_VARIANT', 'GGML_VK_IQ4_XS_ROWS', 'GGML_VK_IQ4_XS_WG', 'GGML_VK_GCN_CONV_WG'}
    profile_environment=h.get('kcpp_native_environment',{})
    if not isinstance(native_environment,dict) or not isinstance(profile_environment,dict):raise SupervisorError('Native environments must be objects.','invalid_profile_config')
    native_environment={**native_environment,**profile_environment}
    if not isinstance(native_environment, dict) or set(native_environment) - allowed_environment:
        raise SupervisorError('Unknown portable Vulkan environment option.', 'invalid_profile_config')
    for key, value in native_environment.items():
        valid = isinstance(value, str) and (value in {'k16','m32','n32'} if key == 'GGML_VK_GCN_TILE_VARIANT' else value in {'256','512'} if key=='GGML_VK_GCN_CONV_WG' else bool(re.fullmatch(r'[0-9]{1,4}', value)))
        if not valid:
            raise SupervisorError('Invalid portable Vulkan option value.', 'invalid_profile_config')
    if environment_file.is_file():
        for key in list(environment):
            if key.startswith('GGML_VK_'): environment.pop(key)
        environment.update(native_environment)
    print('Portable Vulkan environment: '+str(native_environment), flush=True)
    operations = WindowsOperations()
    with operations.native_port_lock(args.port) as port_ownership, operations.owner_lock(root / 'logs/native-worker.lock'):
        if operations.listeners(args.port):
            raise SupervisorError('Native slot is occupied; no process launched.', 'foreign_listener')
        kernel = ctypes.WinDLL('kernel32')
        kernel.SetConsoleTitleW.argtypes = [ctypes.wintypes.LPCWSTR]
        kernel.SetConsoleTitleW('Kobold Native | '+args.profile+' | '+str(args.port))
        kernel.GetConsoleWindow.restype = ctypes.wintypes.HWND
        console_window = kernel.GetConsoleWindow()
        user = ctypes.WinDLL('user32')
        user.IsWindowVisible.argtypes = [ctypes.wintypes.HWND]
        user.IsWindowVisible.restype = ctypes.wintypes.BOOL
        worker = operations.process(os.getpid())
        if not worker: raise SupervisorError('Visible worker identity unavailable.', 'invalid_ownership')
        active = dict(format=1, run_id=args.run_id, native_profile=args.profile,
                      helper=str(helper), helper_sha256=args.helper_sha256,
                      executable=str(executable), executable_sha256=args.executable_sha256,
                      port=args.port, worker=worker, worker_pid=os.getpid(), native_log=str(log_file),
                      started=time.time(), phase='worker_started', visible_console_requested=True,
                      visible_console=bool(console_window and user.IsWindowVisible(console_window)),
                      temporary_directory=str(temporary), native_environment=native_environment, python_unbuffered_requested=True,
                      native_c_stdio_unbuffered_proven=False, managed_port_mutex=port_ownership)
        if h.get('sdquant')==0 and str(h.get('sdmodel','')).lower().endswith('.gguf'):
            from MossImageBudget import inspect_gguf
            try:
                quant=inspect_gguf(root_path(root,h['sdmodel']))
                if quant['architecture']=='moss_image':
                    active.update(actual_image_quantization=quant['quantization'],
                        image_quantization_source=quant['quantization_confirmation'])
            except (OSError,ValueError):
                pass  # The generic worker also accepts non-MOSS GGUF models.
        write_json(active_file, active)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with log_file.open('w', encoding='utf-8', buffering=1) as output:
            arguments = native_arguments(executable, helper)
            if operations.listeners(args.port):
                active.update(phase='foreign_port_appeared_before_launch', native_not_launched=True)
                write_json(active_file, active)
                raise SupervisorError('Private port became occupied; Native not launched.', 'foreign_listener')
            # This child inherits the visible worker console. Its stdout is tee'd
            # back into that same console; a second hidden Native is never used.
            native = subprocess.Popen(arguments, cwd=root, env=environment,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding='utf-8', errors='replace', bufsize=1)
            deadline = time.monotonic() + 10
            identity = None
            while time.monotonic() < deadline and native.poll() is None:
                identity = operations.process(native.pid)
                if identity: break
                time.sleep(.1)
            if not identity:
                active.update(phase='identity_capture_failed_preserved', pid=native.pid)
                write_json(active_file, active)
                raise SupervisorError('Native started without captured identity; preserved, no second launch.', 'invalid_ownership')
            active.update(native=identity, pid=native.pid, phase='loading')
            console_pids = (ctypes.wintypes.DWORD * 256)()
            kernel.GetConsoleProcessList.argtypes = [ctypes.POINTER(ctypes.wintypes.DWORD), ctypes.wintypes.DWORD]
            count = kernel.GetConsoleProcessList(console_pids, len(console_pids))
            active['native_attached_to_worker_console'] = bool(count <= len(console_pids) and native.pid in console_pids[:count])
            active['requested_quantization_level'] = h.get('sdquant', 0)
            write_json(active_file, active)
            try:
                for line in native.stdout:
                    # Native's Input line may contain full image/base64 data.
                    safe_line = '[Input payload omitted]\n' if line.lstrip().startswith('Input:') else line
                    # Bound the current diagnostic file; console output remains complete.
                    if output.tell() > 512 * 1024:
                        output.seek(0); output.truncate()
                    output.write(safe_line); output.flush()
                    print(safe_line, end='', flush=True)
                    quant = re.search(r'Diffusion Model quantized to ([A-Za-z0-9_]+)', line)
                    if quant:
                        active['actual_image_quantization'] = quant.group(1).lower()
                        write_json(active_file, active)
                code = native.wait()
                active.update(phase='exited', exit_code=code, exited=time.time())
                write_json(active_file, active)
                return code
            except KeyboardInterrupt:
                active.update(phase='console_interrupted_preserved', interrupted=time.time())
                write_json(active_file, active)
                return 130


if __name__ == '__main__':
    raise SystemExit(main())

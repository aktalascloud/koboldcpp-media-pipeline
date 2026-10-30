"""One owned Native context. Import/construction never launch a process or call HTTP.

Only an explicit lease/start operation touches the host. Operations are injected
for CPU-only tests. Paths are relative to the supplied application root, never
to this module's staging directory.
"""
from __future__ import annotations

from contextlib import contextmanager
import copy
import ctypes
from ctypes import wintypes
import hashlib
import http.client
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request
import uuid
import re
import threading
import socket

PROFILES = ('photo-normal', 'photo-quality', 'music', 'video')
MUSIC_FIELDS = ('musicdiffusion', 'musicllm', 'musicembeddings', 'musicvae')


class SupervisorError(RuntimeError):
    def __init__(self, message, code='backend_unavailable', status=503):
        super().__init__(message)
        self.status = status
        self.body = {'error': {'message': message, 'type': 'backend_error', 'code': code}}


def music_asset_fields(helper):
    present={field for field in MUSIC_FIELDS if helper.get(field)}
    if present=={'musicllm','musicvae'}:return ('musicllm','musicvae')
    if present==set(MUSIC_FIELDS):return MUSIC_FIELDS
    raise SupervisorError('Music requires either YuE2 LLM+VAE or the complete ACE-Step asset set.', 'music_profile_changed')


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.writing')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    try:
        for attempt in range(20):
            try:
                os.replace(temporary, path)
                break
            except OSError as error:
                # Windows readers/AV may briefly deny DELETE sharing. Keep the
                # complete old record; never fall back to truncating it in place.
                if getattr(error, 'winerror', None) not in (5, 32, 33) or attempt == 19: raise
                time.sleep(min(.01 * 2**attempt, .25))
    finally:
        try: temporary.unlink(missing_ok=True)
        except OSError: pass


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(4 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def same_path(left, right):
    return bool(left and right) and os.path.normcase(str(Path(left).resolve())) == os.path.normcase(str(Path(right).resolve()))


def root_path(root, value):
    if not isinstance(value, (str, Path)) or not str(value):
        raise SupervisorError('A nonempty application-relative path is required.', 'invalid_profile_config')
    path = Path(value)
    path = (path if path.is_absolute() else root / path).resolve()
    if not path.is_relative_to(root):
        raise SupervisorError('Configured path escapes application root: ' + str(value), 'invalid_profile_config')
    return path


def helper_defaults(helper):
    value = helper.get('gendefaults', {})
    return json.loads(value) if isinstance(value, str) else copy.deepcopy(value)


class WindowsOperations:
    """Host operations, intentionally not used by the unit tests."""
    def monotonic(self): return time.monotonic()
    def sleep(self, seconds): time.sleep(seconds)

    def boot_started(self):
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.GetTickCount64.restype = ctypes.c_ulonglong
        return time.time() - kernel.GetTickCount64() / 1000

    def _powershell(self, script):
        shell = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
        try:
            result = subprocess.run([str(shell), '-NoProfile', '-NonInteractive', '-Command',
                "$ErrorActionPreference='Stop'; [Console]::OutputEncoding=[Text.UTF8Encoding]::new(); " + script],
                capture_output=True, encoding='utf-8-sig', errors='replace', timeout=12,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except subprocess.TimeoutExpired:
            raise SupervisorError('Process inventory timed out; no unsafe fallback.', 'inventory_failed') from None
        if result.returncode:
            raise SupervisorError('Process inventory failed; no unsafe fallback: ' + result.stderr[-800:], 'inventory_failed')
        return json.loads(result.stdout) if result.stdout.strip() else None

    def process(self, pid):
        pid = int(pid)
        if pid <= 0: raise SupervisorError('Invalid recorded PID.', 'invalid_ownership')
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        handle = kernel.OpenProcess(0x1000 | 0x0400 | 0x100000, False, pid)
        if not handle:
            error = ctypes.get_last_error()
            if error == 87: return None
            raise ctypes.WinError(error)
        try:
            kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
            exit_code = wintypes.DWORD()
            if not kernel.GetExitCodeProcess(handle, ctypes.byref(exit_code)): raise ctypes.WinError(ctypes.get_last_error())
            if exit_code.value != 259: return None
            kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
            name, size = ctypes.create_unicode_buffer(32768), wintypes.DWORD(32768)
            if not kernel.QueryFullProcessImageNameW(handle, 0, name, ctypes.byref(size)): raise ctypes.WinError(ctypes.get_last_error())
            kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
            created, exited, kt, ut = (wintypes.FILETIME() for _ in range(4))
            if not kernel.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(exited), ctypes.byref(kt), ctypes.byref(ut)): raise ctypes.WinError(ctypes.get_last_error())
            ticks = (created.dwHighDateTime << 32) | created.dwLowDateTime
            # Query the already pinned process handle. WMI/PowerShell startup
            # can block during cold model loading and must not govern identity.
            class Basic(ctypes.Structure):
                _fields_ = [('reserved1', ctypes.c_void_p), ('peb', ctypes.c_void_p),
                            ('reserved2', ctypes.c_void_p * 2), ('unique_pid', ctypes.c_size_t),
                            ('parent_pid', ctypes.c_size_t)]
            class Unicode(ctypes.Structure):
                _fields_ = [('length', wintypes.USHORT), ('maximum', wintypes.USHORT),
                            ('buffer', ctypes.c_void_p)]
            query = ctypes.WinDLL('ntdll').NtQueryInformationProcess
            query.argtypes = [wintypes.HANDLE, wintypes.ULONG, ctypes.c_void_p,
                              wintypes.ULONG, ctypes.POINTER(wintypes.ULONG)]
            query.restype = ctypes.c_long
            basic, returned = Basic(), wintypes.ULONG()
            status = query(handle, 0, ctypes.byref(basic), ctypes.sizeof(basic), ctypes.byref(returned))
            if status < 0 or basic.unique_pid != pid:
                raise SupervisorError('Pinned process basic identity query failed.', 'inventory_failed')
            needed = wintypes.ULONG()
            query(handle, 60, None, 0, ctypes.byref(needed))
            if not ctypes.sizeof(Unicode) <= needed.value <= 1024 * 1024:
                raise SupervisorError('Pinned process command-line size query failed.', 'inventory_failed')
            buffer = ctypes.create_string_buffer(needed.value)
            status = query(handle, 60, buffer, needed.value, ctypes.byref(returned))
            if status < 0:
                raise SupervisorError('Pinned process command-line query failed.', 'inventory_failed')
            text = Unicode.from_buffer(buffer)
            address = ctypes.addressof(buffer)
            if text.length % 2 or text.length > text.maximum or (text.length and
                    (not text.buffer or text.buffer < address or text.buffer + text.length > address + len(buffer))):
                raise SupervisorError('Pinned process returned an invalid command-line buffer.', 'inventory_failed')
            command = ctypes.wstring_at(text.buffer, text.length // 2) if text.length else ''
            if not kernel.GetExitCodeProcess(handle, ctypes.byref(exit_code)) or exit_code.value != 259:
                return None
            return dict(pid=pid, executable=name.value, created_ticks=ticks,
                        parent_pid=int(basic.parent_pid), command_line=command)
        finally:
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel.CloseHandle(handle)

    def arguments(self, record):
        shell = ctypes.WinDLL('shell32', use_last_error=True)
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        shell.CommandLineToArgvW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_int)]
        shell.CommandLineToArgvW.restype = ctypes.POINTER(wintypes.LPWSTR)
        count = ctypes.c_int()
        pointer = shell.CommandLineToArgvW(record['command_line'], ctypes.byref(count))
        if not pointer: raise ctypes.WinError(ctypes.get_last_error())
        try: return [pointer[i] for i in range(count.value)]
        finally:
            kernel.LocalFree.argtypes = [wintypes.HLOCAL]
            kernel.LocalFree(pointer)

    def listeners(self, port):
        port = int(port)
        if not 1 <= port <= 65535: raise ValueError('Invalid TCP port')
        class Row4(ctypes.Structure):
            _fields_ = [(key, wintypes.DWORD) for key in ('state', 'address', 'port', 'remote_address', 'remote_port', 'pid')]
        class Row6(ctypes.Structure):
            _fields_ = [('address', ctypes.c_ubyte * 16), ('scope', wintypes.DWORD), ('port', wintypes.DWORD),
                        ('remote_address', ctypes.c_ubyte * 16), ('remote_scope', wintypes.DWORD),
                        ('remote_port', wintypes.DWORD), ('state', wintypes.DWORD), ('pid', wintypes.DWORD)]
        query = ctypes.WinDLL('iphlpapi.dll').GetExtendedTcpTable
        query.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD), wintypes.BOOL,
                          wintypes.ULONG, ctypes.c_int, wintypes.ULONG]
        query.restype = wintypes.DWORD
        owners = set()
        for family, row_type in ((2, Row4), (23, Row6)):
            size = wintypes.DWORD()
            result = query(None, ctypes.byref(size), False, family, 3, 0)
            if result not in (0, 122): raise ctypes.WinError(result)
            for attempt in range(4):
                buffer = ctypes.create_string_buffer(max(4, size.value))
                size.value = len(buffer)
                result = query(buffer, ctypes.byref(size), False, family, 3, 0)
                if result == 122: continue
                if result: raise ctypes.WinError(result)
                count = wintypes.DWORD.from_buffer(buffer).value
                if 4 + count * ctypes.sizeof(row_type) > len(buffer):
                    raise SupervisorError('Invalid TCP owner table.', 'inventory_failed')
                for index in range(count):
                    row = row_type.from_buffer(buffer, 4 + index * ctypes.sizeof(row_type))
                    if row.state == 2 and socket.ntohs(row.port & 0xffff) == port:
                        owners.add(int(row.pid))
                break
            else: raise SupervisorError('TCP owner table kept changing; preserved.', 'inventory_failed')
        return sorted(owners)

    def api(self, port, path, payload=None, timeout=3):
        body = json.dumps(payload).encode('utf-8') if payload is not None else None
        request = urllib.request.Request(f'http://127.0.0.1:{int(port)}{path}', body,
                                         headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)

    def shutdown_verified(self, port, verify_connected_owner):
        # Pin the TCP connection before the final ownership check. A different
        # listener cannot inherit this already-connected socket between check
        # and POST; failures never trigger an automatic reconnect/retry.
        connection = http.client.HTTPConnection('127.0.0.1', int(port), timeout=6)
        try:
            connection.connect()
            verify_connected_owner()
            connection.request('POST', '/api/extra/shutdown', body=b'{}',
                               headers={'Content-Type': 'application/json', 'Connection': 'close'})
            response = connection.getresponse()
            if not 200 <= response.status < 300:
                raise SupervisorError('Owned Native shutdown HTTP request was refused.', 'shutdown_refused')
            return json.loads(response.read())
        finally: connection.close()

    @contextmanager
    def owner_lock(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        kernel.CreateFileW.restype = wintypes.HANDLE
        handle = kernel.CreateFileW(str(path), 0xC0000000, 0, None, 4, 0x80, None)
        if handle == ctypes.c_void_p(-1).value:
            error = ctypes.get_last_error()
            if error in (32, 33):
                raise SupervisorError('Another launcher/supervisor owns the application lock; preserved.', 'supervisor_already_running')
            raise SupervisorError('Cannot acquire application ownership lock, Windows error '+str(error)+'.', 'ownership_lock_failed')
        try: yield
        finally:
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel.CloseHandle(handle)

    @contextmanager
    def native_port_lock(self, port):
        """Cross-Root/Portable slot lock, held by the visible worker lifetime."""
        if type(port) is not int or not 1 <= port <= 65535:
            raise SupervisorError('Invalid managed Native port.', 'invalid_profile_config')
        name = 'Local\\KoboldCpp-Managed-Native-' + str(port)
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        kernel.CreateMutexW.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.ReleaseMutex.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.CreateMutexW(None, False, name)
        if not handle: raise SupervisorError('Cannot open the managed Native port mutex.', 'ownership_lock_failed')
        acquired = False
        try:
            result = kernel.WaitForSingleObject(handle, 5000)
            if result not in (0, 0x80):
                raise SupervisorError('Another managed Root owns this Native port; no model started.', 'native_port_busy', 409)
            acquired = True
            yield dict(name=name, acquired=True, abandoned=result == 0x80)
        finally:
            if acquired: kernel.ReleaseMutex(handle)
            kernel.CloseHandle(handle)

    def spawn_worker(self, root, worker, python, profile, active_file, log_file, run_id):
        temporary = root / 'runtime/tmp'
        temporary.mkdir(parents=True, exist_ok=True)
        environment = os.environ.copy()
        environment['TMP'] = environment['TEMP'] = str(temporary)
        environment['PYTHONUNBUFFERED'] = '1'
        environment['PYTHONIOENCODING'] = 'utf-8'
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 1
        arguments = [str(python), '-I', '-u', '-B', str(worker), '--root', str(root),
            '--profile', profile['name'], '--executable', str(profile['executable']),
            '--executable-sha256', profile['executable_sha256'], '--helper', str(profile['helper']),
            '--helper-sha256', profile['helper_sha256'], '--port', str(profile['port']),
            '--run-id', run_id, '--active-file', str(active_file), '--log-file', str(log_file)]
        child = subprocess.Popen(arguments, cwd=root, env=environment,
                                 creationflags=subprocess.CREATE_NEW_CONSOLE, startupinfo=startup)
        record = self.process(child.pid)
        if not record: raise SupervisorError('Fresh Native worker exited before identity capture.', 'worker_start_failed')
        return record


class BackendSupervisor:
    def __init__(self, config, root=None, operations=None):
        if root is None:
            from RuntimePaths import ROOT
            root = ROOT
        self.root = Path(root).resolve()
        self.config = copy.deepcopy(config)
        self.operations = operations if operations is not None else WindowsOperations()
        self.lock = threading.RLock()
        self._owner = None
        self.state_file = root_path(self.root, config.get('state_file', 'logs/backend-supervisor.json'))
        self.worker = root_path(self.root, config.get('worker', 'tools/NativeBackendWorker.py'))
        self.python = root_path(self.root, config.get('python', 'runtime/python/python.exe'))
        self.active_file = root_path(self.root, config.get('active_file', 'logs/native-active.json'))
        self.readiness_seconds = self._seconds(config.get('readiness_seconds', 900), 5, 1800)
        self.shutdown_seconds = self._seconds(config.get('shutdown_seconds', 60), 5, 180)
        self.version = str(config.get('native_version', '1.123.1'))
        profiles = config.get('profiles')
        allowed_sets = (set(PROFILES), set(PROFILES) - {'music'}, set(PROFILES) - {'video'})
        if not isinstance(profiles, dict) or set(profiles) not in allowed_sets:
            raise SupervisorError('Photo-normal/photo-quality/video and optional music profiles are required.', 'invalid_profile_config')
        self.music_on_demand = 'music' in profiles
        self.profiles = {name: self._profile(name, spec) for name, spec in profiles.items()}
        if len({p['port'] for p in self.profiles.values()}) != 1:
            raise SupervisorError('All profiles must use one private Native port.', 'invalid_profile_config')
        if not same_path(self.profiles['photo-normal']['executable'], self.profiles['photo-quality']['executable']):
            raise SupervisorError('Both photo profiles must use the same Root Native executable.', 'invalid_profile_config')
        if not same_path(self.profiles['photo-normal']['executable'], self.root / 'koboldcpp-nocuda.exe'):
            raise SupervisorError('Photo profiles must use the original Root koboldcpp-nocuda.exe.', 'invalid_profile_config')
        if self.music_on_demand and not same_path(self.profiles['music']['executable'], self.root / 'koboldcpp-nocuda.exe'):
            raise SupervisorError('Music must use the same Root Kobold executable.', 'invalid_profile_config')
        if 'video' in self.profiles:
            if not same_path(self.profiles['video']['executable'], self.root / 'koboldcpp-nocuda.exe') or self.profiles['video']['executable_sha256']!=self.profiles['photo-normal']['executable_sha256']:
                raise SupervisorError('Video must use the same pinned Root Kobold executable as photo/music.', 'invalid_profile_config')
        self.default_profile = config.get('default_profile', 'photo-normal')
        if self.default_profile != 'photo-normal':
            raise SupervisorError('Startup must restore the full photo-normal/music profile.', 'invalid_profile_config')

    @staticmethod
    def _seconds(value, lower, upper):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not lower <= value <= upper:
            raise SupervisorError('Invalid bounded lifecycle timeout.', 'invalid_profile_config')
        return float(value)

    def _profile(self, name, spec):
        if not isinstance(spec, dict): raise SupervisorError('Invalid profile.', 'invalid_profile_config')
        result = copy.deepcopy(spec)
        result['name'] = name
        for field in ('executable', 'helper'):
            result[field] = root_path(self.root, result.get(field))
            if not re.fullmatch(r'[0-9a-fA-F]{64}', str(result.get(field + '_sha256', ''))):
                raise SupervisorError('Exact executable/helper SHA256 required.', 'invalid_profile_config')
            result[field + '_sha256'] = result[field + '_sha256'].lower()
        port = result.get('port')
        if type(port) is not int or not 1 <= port <= 65535:
            raise SupervisorError('Invalid private Native port.', 'invalid_profile_config')
        capabilities = result.get('capabilities', ['txt2img'] if name.startswith('photo-') else [])
        if not isinstance(capabilities, list) or not capabilities or any(x not in ('txt2img', 'music', 'musicllm') for x in capabilities):
            raise SupervisorError('Explicit Native capabilities required.', 'invalid_profile_config')
        required = {'music', 'musicllm'} if name == 'music' else {'txt2img'}
        if name == 'photo-normal' and not self.music_on_demand:
            required.update({'music', 'musicllm'})
        if not required.issubset(capabilities):
            raise SupervisorError('Profile omits required Native capabilities.', 'invalid_profile_config')
        result['capabilities'] = capabilities
        return result

    def _verify_files(self, profile):
        for field in ('executable', 'helper'):
            if not profile[field].is_file() or sha256(profile[field]) != profile[field + '_sha256']:
                raise SupervisorError('Reviewed profile file missing or changed: ' + str(profile[field]), 'profile_file_changed')
        if not self.worker.is_file() or not self.python.is_file():
            raise SupervisorError('Portable Native worker/Python is missing.', 'profile_file_changed')
        helper = read_json(profile['helper'])
        if helper.get('host') not in ('127.0.0.1', 'localhost') or int(helper.get('port', 0)) != profile['port'] or int(helper.get('port_param', profile['port'])) != profile['port']:
            raise SupervisorError('Helper does not match the loopback private Native slot.', 'invalid_profile_config')
        if helper.get('onready') or helper.get('launch'):
            raise SupervisorError('Native profile must not launch additional helpers.', 'invalid_profile_config')
        if helper.get('singleinstance') is not True:
            raise SupervisorError('Managed Native requires singleinstance for verified graceful API shutdown.', 'invalid_profile_config')
        if profile['name'] == 'music' and helper.get('sdmodel'):
            raise SupervisorError('Demand-loaded music must not keep photo weights loaded.', 'invalid_profile_config')
        if profile['name'] != 'music' and not helper.get('sdmodel'):
            raise SupervisorError('Native image/video model is missing from the profile.', 'invalid_profile_config')
        for field in ('sdmodel', 'sdllm', 'sdt5xxl', 'sdclip1', 'sdclip2', 'sdclip3', 'sdvae', *MUSIC_FIELDS):
            if helper.get(field) and not root_path(self.root, helper[field]).is_file():
                raise SupervisorError('Profile asset missing or outside Root: '+field, 'profile_file_changed')
        for value in helper.get('sdlora') or []:
            if not root_path(self.root, value).is_file():
                raise SupervisorError('Static LoRA asset missing or outside Root.', 'profile_file_changed')
        if profile['name'] == 'music' or (profile['name'] == 'photo-normal' and not self.music_on_demand):
            master = read_json(self.root / 'Helper.kcpps')
            fields=music_asset_fields(helper)
            if set(fields)!=set(music_asset_fields(master)):
                raise SupervisorError('Music model family differs from the master Helper.', 'music_profile_changed')
            for field in fields:
                if not helper.get(field) or not master.get(field) or not same_path(root_path(self.root, helper[field]), root_path(self.root, master[field])):
                    raise SupervisorError('Original production music assets are not preserved.', 'music_profile_changed')
                if not root_path(self.root, helper[field]).is_file():
                    raise SupervisorError('Original music asset missing.', 'music_profile_changed')
        return helper

    def preflight(self):
        """Read only files/SHA/schema; no API, process inventory or launching."""
        rows = {}
        for name, profile in self.profiles.items():
            helper = self._verify_files(profile)
            rows[name] = dict(helper=str(profile['helper']), helper_sha256=profile['helper_sha256'],
                              executable=str(profile['executable']), executable_sha256=profile['executable_sha256'],
                              port=profile['port'], capabilities=profile['capabilities'],
                              sdflashattention=helper.get('sdflashattention'),
                              original_music=name == ('music' if self.music_on_demand else 'photo-normal'))
        return dict(ok=True, root=str(self.root), profiles=rows, host_checked=False)

    def _state(self, allow_relocation=False):
        if not self.state_file.exists(): return {'format': 1, 'root': str(self.root), 'phase': 'not_started', 'history': []}
        value = read_json(self.state_file)
        old_root = value.get('root')
        if value.get('format') != 1 or not isinstance(old_root, str) or not Path(old_root).is_absolute() or not isinstance(value.get('history'), list):
            raise SupervisorError('Supervisor ownership state is invalid; preserved.', 'invalid_ownership')
        # Compare old Root lexically: never probe a former disk/network path.
        if os.path.normcase(os.path.normpath(old_root)) != os.path.normcase(os.path.normpath(str(self.root))):
            if not allow_relocation:
                return dict(format=1, root=str(self.root), phase='relocated_state_pending',
                            previous_root=old_root, history=[], relocation_pending=True)
            if self._owner is None:
                raise SupervisorError('Relocation requires the application ownership lock.', 'invalid_ownership')
            ports = sorted({profile['port'] for profile in self.profiles.values()})
            if any(self.operations.listeners(port) for port in ports):
                raise SupervisorError('Relocated private port is occupied; copied state and all PIDs preserved.', 'foreign_listener')
            token = 'relocated-' + uuid.uuid4().hex
            archived_state = self.root / 'logs/native-history' / (token + '-state.json')
            archived_state.parent.mkdir(parents=True, exist_ok=True)
            raw_state = self.state_file.read_bytes()
            archived_state.write_bytes(raw_state)
            event = dict(reason='copied_state_relocated_without_pid_inspection', previous_root=old_root,
                         state_archive=archived_state.relative_to(self.root).as_posix(),
                         state_sha256=hashlib.sha256(raw_state).hexdigest(),
                         verified_free_ports=ports, stale_pid_actions='none; not inventoried', time=time.time())
            if self.active_file.exists():
                raw_active = self.active_file.read_bytes()
                archived_active = archived_state.with_name(token + '-active.json')
                archived_active.write_bytes(raw_active)
                event.update(active_archive=archived_active.relative_to(self.root).as_posix(),
                             active_sha256=hashlib.sha256(raw_active).hexdigest())
            fresh = dict(format=1, root=str(self.root), phase='relocated_reinitialized', history=[event])
            self._save(fresh)
            return fresh
        return value

    def _save(self, state):
        state['updated'] = time.time()
        write_json(self.state_file, state)

    def _identity_status(self, record):
        if not isinstance(record, dict) or not isinstance(record.get('pid'), int) or not isinstance(record.get('created_ticks'), int) or not record.get('executable'):
            raise SupervisorError('Recorded process has no creation identity; preserved.', 'invalid_ownership')
        current = self.operations.process(record['pid'])
        if current is None: return 'dead'
        if current['created_ticks'] == record['created_ticks'] and same_path(current['executable'], record['executable']): return 'owned'
        return 'reused'

    def _verify_arguments(self, record, expected_executable, expected_pairs):
        current = self.operations.process(record['pid'])
        if not current or current['created_ticks'] != record['created_ticks'] or not same_path(current['executable'], record['executable']) or not same_path(current['executable'], expected_executable):
            raise SupervisorError('Recorded process identity no longer matches; preserved.', 'identity_changed')
        args = self.operations.arguments(current)
        for switch, expected in expected_pairs.items():
            indexes = [i for i, value in enumerate(args) if value == switch]
            if len(indexes) != 1 or indexes[0]+1 >= len(args):
                raise SupervisorError('Owned process arguments mismatch; preserved.', 'identity_changed')
            actual = args[indexes[0]+1]
            if switch in ('--config', '--helper', '--root', '--executable', '--active-file'):
                match = same_path(actual, expected)
            else: match = actual == str(expected)
            if not match: raise SupervisorError('Owned process arguments mismatch; preserved.', 'identity_changed')

    def _refresh_active(self, state):
        active = state.get('active')
        if not active: return None
        profile = self.profiles.get(active.get('native_profile'))
        if not profile or not same_path(active.get('helper'), profile['helper']) or active.get('helper_sha256') != profile['helper_sha256'] or active.get('executable_sha256') != profile['executable_sha256']:
            raise SupervisorError('State is not owned by the configured immutable profile; preserved.', 'invalid_ownership')
        # A reboot can interrupt _start between saving intent and recording its
        # worker. No previous-boot worker can survive; current-boot ambiguity
        # remains fail-closed. Both worker locks and the port must also be free.
        boot = getattr(self.operations, 'boot_started', lambda: None)() if not active.get('worker') else None
        started = active.get('started')
        if not active.get('worker') and type(started) in (int, float) and boot is not None and 0 < started < boot - 5:
            with self.operations.native_port_lock(profile['port']), self.operations.owner_lock(self.root / 'logs/native-worker.lock'):
                self._retire_dead(state, active, reason='previous_boot_incomplete_launch_retired')
            return None
        if self.active_file.exists():
            candidate = read_json(self.active_file)
            if candidate.get('run_id') == active.get('run_id'):
                for field in ('native_profile', 'helper_sha256', 'executable_sha256', 'port'):
                    if candidate.get(field) != active.get(field): raise SupervisorError('Native worker record identity mismatch.', 'invalid_ownership')
                if not same_path(candidate.get('helper'), active['helper']) or not same_path(candidate.get('executable'), profile['executable']):
                    raise SupervisorError('Native worker paths mismatch.', 'invalid_ownership')
                if active.get('worker'):
                    if candidate.get('worker', {}).get('pid') != active['worker'].get('pid') or candidate.get('worker', {}).get('created_ticks') != active['worker'].get('created_ticks'):
                        raise SupervisorError('Native worker creation identity mismatch.', 'invalid_ownership')
                else:
                    # Recover only this recorded random launch intent, with a
                    # live verified worker and exact helper/run-id arguments.
                    self._verify_worker(candidate, profile)
                active = {**active, **candidate}
                state['active'] = active
        return active

    def _verify_worker(self, active, profile):
        record = active.get('worker')
        if not record: raise SupervisorError('Native worker identity has not been published; preserved.', 'native_not_ready')
        self._verify_arguments(record, self.python, {'--root': self.root, '--helper': profile['helper'], '--run-id': active['run_id']})
        current = self.operations.process(record['pid'])
        if not current or current['created_ticks'] != record['created_ticks']:
            raise SupervisorError('Worker identity changed; preserved.', 'identity_changed')
        arguments = self.operations.arguments(current)
        if sum(same_path(argument, self.worker) for argument in arguments if not argument.startswith('-')) != 1:
            raise SupervisorError('Worker script is not the reviewed Native worker.', 'identity_changed')

    def _assert_listener_tree(self, active, profile):
        native = active.get('native')
        if not native: raise SupervisorError('Native creation identity is not ready.', 'native_not_ready')
        self._verify_arguments(native, profile['executable'], {'--config': profile['helper']})
        self._verify_worker(active, profile)
        actual_native = self.operations.process(native['pid'])
        if not actual_native or actual_native['created_ticks'] != native['created_ticks'] or actual_native['parent_pid'] != active['worker']['pid']:
            raise SupervisorError('Native is not a child of its verified visible worker.', 'invalid_ownership')
        owners = self.operations.listeners(profile['port'])
        if not owners: raise SupervisorError('Owned Native listener is not ready.', 'native_not_ready')
        listeners = []
        for pid in owners:
            current = self.operations.process(pid)
            seen = set()
            leaf = copy.deepcopy(current)
            while current and current['pid'] != native['pid']:
                if current['pid'] in seen or len(seen) >= 32 or not same_path(current['executable'], profile['executable']) or current['created_ticks'] < native['created_ticks']:
                    raise SupervisorError('Native port belongs to a foreign process; preserved.', 'foreign_listener')
                seen.add(current['pid'])
                current = self.operations.process(current['parent_pid'])
            if not current or current['created_ticks'] != native['created_ticks']:
                raise SupervisorError('Native port is outside the verified process tree; preserved.', 'foreign_listener')
            listeners.append(leaf)
        active['listeners'] = listeners
        return listeners

    def _assert_listener(self, active, profile, require_capabilities=True):
        self._assert_listener_tree(active, profile)
        version = self.operations.api(profile['port'], '/api/extra/version')
        if version.get('result') != 'KoboldCpp' or str(version.get('version')) != self.version:
            raise SupervisorError('Native version does not match the requested profile.', 'wrong_native_profile')
        if require_capabilities and not all(version.get(key) for key in profile['capabilities']):
            raise SupervisorError('Requested Native capabilities are not ready.', 'native_not_ready')
        if not self.operations.api(profile['port'], '/api/extra/perf').get('idle', False):
            raise SupervisorError('Owned Native is busy; no context stopped.', 'backend_busy', 409)
        return version

    def _wait_ready(self, state, profile):
        deadline = self.operations.monotonic() + self.readiness_seconds
        last = ''
        while self.operations.monotonic() < deadline:
            active = self._refresh_active(state)
            if self._identity_status(active['worker']) != 'owned':
                state['phase'] = 'start_failed_preserved'; self._save(state)
                raise SupervisorError('Native worker exited or its PID was reused; records preserved.', 'worker_start_failed')
            try:
                version = self._assert_listener(active, profile)
                helper = read_json(profile['helper'])
                self._annotate_quantization(active, profile, helper)
                self._verify_files(profile)
                state.update(phase='ready', active=active, native_version=version)
                self._save(state)
                return active
            except SupervisorError as error:
                if error.body['error']['code'] in ('foreign_listener', 'identity_changed', 'invalid_ownership', 'wrong_native_profile', 'backend_busy', 'quantization_mismatch'):
                    state['phase'] = 'start_failed_preserved'; self._save(state); raise
                last = str(error)
            except (OSError, ValueError) as error: last = str(error)
            self.operations.sleep(.5)
        state.update(phase='readiness_timeout_preserved', last_error=last); self._save(state)
        raise SupervisorError('Native readiness timeout; owned process and logs preserved: ' + last, 'native_readiness_timeout')

    @staticmethod
    def _annotate_quantization(active, profile, helper):
        if profile['name'].startswith('photo-') and helper.get('sdquant')==0 and str(helper.get('sdmodel','')).lower().endswith('.gguf'):
            from MossImageBudget import inspect_gguf
            model=root_path(profile['executable'].parent,helper['sdmodel'])
            info=inspect_gguf(model)
            if info['architecture']=='moss_image':
                observed=active.get('actual_image_quantization')
                expected=info['quantization']
                active.update(expected_image_quantization=expected,
                    quantization_confirmed=observed==expected,
                    quantization_confirmation=active.get('image_quantization_source','pending_GGUF_tensor_directory'))
                if observed and observed!=expected:
                    raise SupervisorError('Observed MOSS GGUF quantization differs from reviewed profile.','quantization_mismatch')
                return
        if profile['name'].startswith('photo-') and helper.get('sdquant') in (1, 2):
            expected = 'q4_0' if helper['sdquant'] == 2 else 'q8_0'
            observed = active.get('actual_image_quantization')
            active.update(expected_image_quantization=expected,
                          quantization_confirmed=observed == expected,
                          quantization_confirmation='native_stdout' if observed else 'pending_native_stdout')
            if observed is not None and observed != expected:
                raise SupervisorError('Observed Native quantization differs from reviewed Helper.', 'quantization_mismatch')

    def _retire_dead(self, state, active, reason='stale_or_exited_preserved'):
        statuses = []
        for record in [active.get('worker'), active.get('native'), *active.get('listeners', [])]:
            if record:
                status = self._identity_status(record)
                if status == 'owned': raise SupervisorError('An owned context still exists; a second context is forbidden.', 'context_still_alive')
                if status == 'reused':
                    actual = self.operations.process(record['pid'])
                    if any(same_path(actual['executable'], p['executable']) for p in self.profiles.values()):
                        raise SupervisorError('Recorded PID now belongs to another Native; preserved.', 'foreign_native')
                statuses.append({'pid': record['pid'], 'status': status})
        if self.operations.listeners(active['port']):
            raise SupervisorError('Private Native port is occupied; preserved.', 'foreign_listener')
        state['history'].append({'reason': reason, 'active': copy.deepcopy(active), 'identity_status': statuses, 'time': time.time()})
        state.pop('active', None); state['phase'] = 'stopped'; self._save(state)

    def _stop(self, state, active):
        profile = self.profiles[active['native_profile']]
        self._verify_files(profile)
        self._assert_listener(active, profile, require_capabilities=False)
        state['phase'] = 'stopping'; self._save(state)
        answer = self.operations.shutdown_verified(profile['port'], lambda: self._assert_listener_tree(active, profile))
        if answer.get('success') is not True:
            state['phase'] = 'shutdown_refused_preserved'; self._save(state)
            raise SupervisorError('Owned Native refused graceful shutdown; no force kill.', 'shutdown_refused')
        deadline = self.operations.monotonic() + self.shutdown_seconds
        while self.operations.monotonic() < deadline:
            if not self.operations.listeners(profile['port']):
                records = [active.get('worker'), active.get('native'), *active.get('listeners', [])]
                if all(not record or self._identity_status(record) != 'owned' for record in records):
                    # Buffered Native stdout can appear only at shutdown. Preserve
                    # that late evidence without using an absent line as proof.
                    active = self._refresh_active(state)
                    mismatch = None
                    try: self._annotate_quantization(active, profile, read_json(profile['helper']))
                    except SupervisorError as error: mismatch = error
                    self._retire_dead(state, active)
                    if mismatch: raise mismatch
                    return
            self.operations.sleep(.5)
        state['phase'] = 'shutdown_timeout_preserved'; self._save(state)
        raise SupervisorError('Owned context did not fully exit; no second Native and no force kill.', 'shutdown_timeout')

    def _start(self, state, profile):
        if self.operations.listeners(profile['port']):
            raise SupervisorError('Private Native slot is occupied by an unowned process; preserved.', 'foreign_listener')
        run_id = uuid.uuid4().hex
        log_file = self.root / 'logs' / ('Native-' + profile['name'] + '-' + run_id + '.log')
        if self.active_file.exists():
            archive = self.root / 'logs/native-history' / (run_id + '-previous-active.json')
            archive.parent.mkdir(parents=True, exist_ok=True)
            archive.write_bytes(self.active_file.read_bytes())
        active = dict(run_id=run_id, native_profile=profile['name'], helper=str(profile['helper']),
                      helper_sha256=profile['helper_sha256'], executable=str(profile['executable']),
                      executable_sha256=profile['executable_sha256'], port=profile['port'],
                      native_log=str(log_file), started=time.time())
        state.update(phase='starting', active=active); self._save(state)
        worker = self.operations.spawn_worker(self.root, self.worker, self.python, profile,
                                              self.active_file, log_file, run_id)
        active['worker'] = worker
        self._verify_worker(active, profile)
        state['active'] = active; self._save(state)
        return self._wait_ready(state, profile)

    def _claim_owner(self):
        if self._owner is None:
            owner = self.operations.owner_lock(self.state_file.with_suffix('.lock'))
            owner.__enter__()
            self._owner = owner

    def _ensure(self, name):
        if name not in self.profiles: raise SupervisorError('Unknown Native profile.', 'invalid_profile', 400)
        profile = self.profiles[name]
        self._verify_files(profile)
        self._claim_owner()
        state = self._state(allow_relocation=True)
        active = self._refresh_active(state)
        if active:
            if not active.get('worker'):
                raise SupervisorError('An incomplete launch intent is preserved; inspect worker record before starting again.', 'incomplete_launch_preserved')
            records = [active.get('worker'), active.get('native'), *active.get('listeners', [])]
            owned = any(record and self._identity_status(record) == 'owned' for record in records)
            if not owned:
                self._retire_dead(state, active)
            elif active['native_profile'] == name:
                return self._wait_ready(state, profile)
            else:
                self._stop(state, active)
        return self._start(state, profile)

    @contextmanager
    def lease(self, profile, request_config=None):
        """Global RLock is held until Native AND the caller's postprocessing end."""
        with self.lock:
            active = self._ensure(profile)
            yield dict(native_profile=profile, backend=f"http://127.0.0.1:{active['port']}",
                       helper=str(active['helper']), helper_sha256=active['helper_sha256'],
                       native_pid=active['native']['pid'], run_id=active['run_id'],
                       native_log=active['native_log'],
                       expected_image_quantization=active.get('expected_image_quantization'),
                       actual_image_quantization=active.get('actual_image_quantization'),
                       quantization_confirmed=active.get('quantization_confirmed', False),
                       quantization_confirmation=active.get('quantization_confirmation', 'not_exposed'))

    def status(self):
        """File-only snapshot, not a claim of current host/API liveness."""
        # State writes use atomic replace. Health/progress must never wait for
        # an image/video lease that can last minutes.
        return {**copy.deepcopy(self._state()), 'live_checked': False}

    @contextmanager
    def gpu_lease(self):
        """Serialize local SR/face work without loading/switching Native."""
        with self.lock:
            active = self.status().get('active', {})
            yield dict(native_profile=active.get('native_profile'),
                       helper_sha256=active.get('helper_sha256'),
                       backend=f"http://127.0.0.1:{active['port']}" if active.get('port') else None,
                       native_switched=False)

    def stop_idle(self):
        """Unload only this owned idle Native. Never load a replacement profile."""
        with self.lock:
            self._claim_owner()
            state = self._state(allow_relocation=True)
            active = self._refresh_active(state)
            if not active:
                return dict(stopped=False, reason='no_owned_active_context', new_context_started=False)
            if not active.get('worker'):
                raise SupervisorError('Incomplete launch is preserved; no unverified unload.', 'incomplete_launch_preserved')
            records = [active.get('worker'), active.get('native'), *active.get('listeners', [])]
            owned = any(record and self._identity_status(record) == 'owned' for record in records)
            if not owned:
                self._retire_dead(state, active)
                return dict(stopped=False, retired=True, reason='owned_context_already_exited', new_context_started=False)
            self._stop(state, active)
            return dict(stopped=True, native_profile=active['native_profile'],
                        run_id=active['run_id'], new_context_started=False)

    unload_idle = stop_idle

    def close(self):
        """Release ownership lock only. Never kill a backend on proxy teardown."""
        with self.lock:
            if self._owner is not None:
                self._owner.__exit__(None, None, None)
                self._owner = None


def from_helper(helper, root=None, operations=None):
    if root is None:
        from RuntimePaths import ROOT
        root = ROOT
    data = read_json(helper)
    config = helper_defaults(data).get('kcpp_proxy', {}).get('backend_supervisor', {})
    if config.get('enabled') is not True:
        raise SupervisorError('Backend supervisor is disabled.', 'supervisor_disabled')
    from UnifiedConfig import materialize
    materialize(config,root,operations or WindowsOperations())
    return BackendSupervisor(config, root=root, operations=operations)

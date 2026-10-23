"""Opt-in launcher delegation; the old Launch never starts another Native.

Deploy only with the reviewed proxy API-routing integration. Import is inert.
"""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from BackendSupervisor import (SupervisorError, WindowsOperations, from_helper,
                               helper_defaults, read_json, root_path, same_path,
                               sha256, write_json)


def _verify_front(operations, port, root, helper, script, python):
    health = operations.api(port, '/health')
    if health.get('service') != 'KoboldProxy' or not same_path(health.get('helper'), helper) or health.get('helper_sha256') != sha256(helper):
        raise SupervisorError('Public API is not the expected master Helper; preserved.', 'foreign_listener')
    record = operations.process(int(health.get('pid', 0)))
    if not record or not same_path(record.get('executable'), python) or set(operations.listeners(port)) != {record['pid']}:
        raise SupervisorError('Public listener process identity mismatch; preserved.', 'foreign_listener')
    active_file = root / 'logs/proxy-supervisor-active.json'
    expected = read_json(active_file) if active_file.is_file() else {}
    if expected.get('pid') != record['pid'] or expected.get('created_ticks') != record['created_ticks'] or not same_path(expected.get('executable'), python) or not same_path(expected.get('helper'), helper) or expected.get('helper_sha256') != sha256(helper):
        raise SupervisorError('Public listener is not the recorded frontend creation identity; preserved.', 'foreign_listener')
    arguments = operations.arguments(record)
    if not any(same_path(value, script) for value in arguments if not value.startswith('-')) or '--proxy' not in arguments:
        raise SupervisorError('Existing frontend is outside this supervisor launcher; preserved.', 'foreign_listener')
    for field, value in (('--root', root), ('--helper', helper)):
        indexes = [i for i, part in enumerate(arguments) if part == field]
        if len(indexes) != 1 or indexes[0]+1 >= len(arguments) or not same_path(arguments[indexes[0]+1], value):
            raise SupervisorError('Existing frontend arguments differ; preserved.', 'foreign_listener')
    return health, record


def launch(root, helper, arguments):
    root, helper = Path(root).resolve(), Path(helper).resolve()
    h = read_json(helper)
    proxy = helper_defaults(h)['kcpp_proxy']
    supervisor = from_helper(helper, root=root)
    if arguments.no_proxy:
        try:
            with supervisor.lease('photo-normal') as active: print('Visible photo-normal/music Native ready:', active['native_pid'])
            return 0
        finally: supervisor.close()
    operations = WindowsOperations()
    port = int(proxy['port'])
    python = root_path(root, 'runtime/python/pythonw.exe')
    script = Path(__file__).resolve()
    temporary = root / 'runtime/tmp'
    temporary.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment['TMP'] = environment['TEMP'] = str(temporary)
    environment['PYTHONUNBUFFERED'] = '1'
    environment['PYTHONIOENCODING'] = 'utf-8'
    with operations.owner_lock(root / 'logs/supervisor-launch.lock'):
        if operations.listeners(port):
            _verify_front(operations, port, root, helper, script, python)
            print('Verified public supervisor already running; no duplicate launched.')
            return 0
        log_file = root / 'logs' / ('SupervisorProxy-'+time.strftime('%Y%m%d-%H%M%S')+'.log')
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with log_file.open('w', encoding='utf-8') as output:
            child = subprocess.Popen([str(python), '-I', '-u', '-B', str(script), '--proxy', '--root', str(root), '--helper', str(helper)],
                cwd=root, env=environment, stdout=output, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW)
        identity = operations.process(child.pid)
        if not identity: raise SupervisorError('Public supervisor exited before identity capture; inspect log.', 'frontend_start_failed')
        write_json(root / 'logs/proxy-supervisor-active.json',
                   dict(**identity, helper=str(helper), helper_sha256=sha256(helper), log=str(log_file)))
        deadline = time.monotonic() + supervisor.readiness_seconds + 30
        last = ''
        while time.monotonic() < deadline:
            if child.poll() is not None:
                raise SupervisorError('Public supervisor exited; no legacy launcher fallback. See '+str(log_file), 'frontend_start_failed')
            try:
                _verify_front(operations, port, root, helper, script, python)
                print('Public supervisor and visible photo-normal/music Native ready.')
                return 0
            except SupervisorError as error:
                if error.body['error']['code'] == 'foreign_listener': raise
                last = str(error)
            except (OSError, ValueError) as error: last = str(error)
            time.sleep(.5)
        raise SupervisorError('Public supervisor readiness timed out; owned records preserved: '+last, 'frontend_readiness_timeout')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--proxy', action='store_true', required=True)
    parser.add_argument('--root', required=True)
    parser.add_argument('--helper', required=True)
    args = parser.parse_args()
    root = Path(args.root).resolve()
    helper = root_path(root, args.helper)
    supervisor = from_helper(helper, root=root)
    try:
        with supervisor.lease('photo-normal'): pass
        import KoboldProxy
        KoboldProxy.serve(helper, photo_backend_lease=supervisor.lease, backend_supervisor=supervisor)
        return 0
    finally:
        # No force kill and no unverified teardown of a potentially busy Native.
        supervisor.close()


if __name__ == '__main__':
    raise SystemExit(main())

"""Portable Windows logon entry, with a persistent error log and visible Native."""
from pathlib import Path
import datetime
import os
import runpy
import sys
import traceback


def main():
    root=Path(__file__).resolve().parent.parent
    launch=root/'tools/Launch.py'
    if not (root/'Helper.kcpps').is_file() or not launch.is_file():
        return 2
    (root/'logs').mkdir(exist_ok=True)
    with (root/'logs/autostart.log').open('w',encoding='utf-8',buffering=1) as log:
        # pythonw has no console streams at logon. Launch expects real streams.
        sys.stdout=sys.stderr=log
        os.chdir(root)
        os.environ['PYTHONUNBUFFERED']='1'
        sys.argv=[str(launch)]
        print('Windows logon launch: '+datetime.datetime.now().isoformat(),flush=True)
        try:
            runpy.run_path(str(launch),run_name='__main__')
        except SystemExit as error:
            code=error.code if isinstance(error.code,int) else (0 if error.code is None else 1)
            print('Launcher exit code: '+str(code),flush=True)
            return code
        except BaseException:
            traceback.print_exc()
            return 1
        return 0


if __name__=='__main__':
    raise SystemExit(main())

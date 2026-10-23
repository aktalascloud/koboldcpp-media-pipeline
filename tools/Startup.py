"""Per-user Windows startup, always pointing at the current portable directory."""
import json,time,winreg
from RuntimePaths import ROOT
NAME='KoboldCppPortable'
KEY=r'Software\Microsoft\Windows\CurrentVersion\Run'
def register():
    command='"'+str(ROOT/'runtime/python/pythonw.exe')+'" -I -B "'+str(ROOT/'tools/AutoStart.py')+'"'
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER,KEY,0,winreg.KEY_READ|winreg.KEY_SET_VALUE) as key:
        try:previous,kind=winreg.QueryValueEx(key,NAME)
        except FileNotFoundError:previous=None
        if previous and not str(previous).lower().endswith(('\\start.exe"','\\tools\\autostart.py"')):
            raise RuntimeError('Startup name belongs to an unexpected command;preserved')
        if previous!=command:winreg.SetValueEx(key,NAME,0,winreg.REG_SZ,command)
        actual,kind=winreg.QueryValueEx(key,NAME)
    assert actual==command
    row=dict(enabled=True,name=NAME,key='HKCU\\'+KEY,command=actual,previous=previous,root=str(ROOT),verified_readback=True,updated=time.time(),scope='Full visible native Kobold and public API proxy;no installed Python/Codex dependency')
    (ROOT/'logs').mkdir(exist_ok=True);(ROOT/'logs'/'startup-registration.json').write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding='utf-8')
    return row

"""One user-facing Helper; exact derived Native profiles are reproducible cache files."""
import hashlib
import json
from pathlib import Path

def defaults(helper):
    value=helper.get('gendefaults',{})
    return json.loads(value) if isinstance(value,str) else value

def consolidate(helper,root):
    """Called only by setup/deployment while services are stopped."""
    root=Path(root).resolve();gd=defaults(helper);config=gd['kcpp_proxy']['backend_supervisor']
    raw={}
    for name,spec in config['profiles'].items():
        path=(root/spec['helper']).resolve()
        if not path.is_relative_to(root) or path.is_symlink():raise ValueError('Unsafe Native profile path')
        text=path.read_bytes().decode('utf-8');json.loads(text)
        raw[name]=text;spec['helper_sha256']=hashlib.sha256(text.encode('utf-8')).hexdigest()
    config['inline_profiles']=raw
    helper['gendefaults']=json.dumps(gd,ensure_ascii=False,separators=(',',':'))
    return helper

def materialize(config,root,operations):
    """Never replace a live profile. Unknown or modified user files fail closed."""
    inline=config.get('inline_profiles')
    if inline is None:return
    if not isinstance(inline,dict) or set(inline)!=set(config['profiles']):raise ValueError('Invalid unified Native profiles')
    root=Path(root).resolve()
    for name,text in inline.items():
        spec=config['profiles'][name];target=(root/spec['helper']).resolve()
        if not target.is_relative_to(root/'profiles') or target.is_symlink():raise ValueError('Unsafe derived profile target')
        if not isinstance(text,str) or len(text)>262144:raise ValueError('Invalid derived profile data')
        json.loads(text);raw=text.encode('utf-8');digest=hashlib.sha256(raw).hexdigest()
        if digest!=spec['helper_sha256']:raise ValueError('Unified profile fingerprint mismatch: '+name)
        if target.is_file():
            if hashlib.sha256(target.read_bytes()).hexdigest()==digest:continue
            raise ValueError('Modified derived profile preserved: '+name+'; close the service before reconciling Helper.kcpps')
        if operations.listeners(int(spec['port'])):raise ValueError('Cannot create a profile while Native is listening')
        target.parent.mkdir(parents=True,exist_ok=True)
        temp=target.with_name(target.name+'.writing');temp.write_bytes(raw);temp.replace(target)

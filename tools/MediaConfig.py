"""Bounded hot settings in the single master Helper. Model paths are never accepted over HTTP."""
import hashlib
import json
import os
import time
import ipaddress
from pathlib import Path

def loopback_peer(value):
    address=ipaddress.ip_address(value)
    mapped=getattr(address,'ipv4_mapped',None)
    return (mapped or address).is_loopback

def _encode(value):return (json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
def _atomic(path,raw):
    temp=path.with_name(path.name+'.writing');temp.write_bytes(raw);os.replace(temp,path)

def update(root,helper,payload,pid):
    root=Path(root).resolve();helper=Path(helper).resolve()
    if helper.parent!=root or helper.name!='Helper.kcpps':raise ValueError('Only the master Helper can be changed')
    if not isinstance(payload,dict) or set(payload)-{'revision','image','video','faces','gater'}:raise ValueError('Unknown settings section')
    old=helper.read_bytes();revision=hashlib.sha256(old).hexdigest()
    if payload.get('revision')!=revision:raise ValueError('Settings changed; reload them before saving')
    h=json.loads(old);gd=json.loads(h['gendefaults']) if isinstance(h['gendefaults'],str) else h['gendefaults'];proxy=gd['kcpp_proxy']
    def fields(section,allowed):
        row=payload.get(section,{})
        if not isinstance(row,dict) or set(row)-set(allowed):raise ValueError('Unknown '+section+' option')
        return row
    def number(value,low,high,integer=False):
        if type(value) not in (int,float) or not low<=value<=high or (integer and type(value) is not int):raise ValueError('Invalid numeric setting')
        return value
    image=fields('image',('cache_threshold',))
    if 'cache_threshold' in image:
        value=number(image['cache_threshold'],0,.08);gd.update(cache_mode='cache-dit' if value else 'disabled',cache_options=f'threshold={value},warmup=4,Fn=16,Bn=2' if value else '')
    video=fields('video',('cache_threshold','default_audio','default_interpolate_fps'))
    if 'cache_threshold' in video:
        value=number(video['cache_threshold'],0,.08);proxy['video'].update(default_cache_mode='cache-dit' if value else 'disabled',default_cache_options=f'threshold={value},warmup=1,Fn=16,Bn=2' if value else '')
    for key in ('default_audio',):
        if key in video:
            if type(video[key]) is not bool:raise ValueError('Boolean required')
            proxy['video'][key]=video[key]
    if 'default_interpolate_fps' in video:
        if type(video['default_interpolate_fps']) is not int or video['default_interpolate_fps'] not in (24,48):raise ValueError('FPS must be24 or48')
        proxy['video']['default_interpolate_fps']=video['default_interpolate_fps']
    faces=fields('faces',('enabled','visibility','minimum_feature_similarity','detector_resolution','max_faces'))
    for key,value in faces.items():
        if key=='enabled':
            if type(value) is not bool:raise ValueError('Boolean required')
        else:
            bounds={'visibility':(0,.35,False),'minimum_feature_similarity':(.97,1,False),'detector_resolution':(640,1280,True),'max_faces':(1,4,True)}[key]
            number(value,*bounds)
        proxy['detailer'][key]=value
    if 'gater' in payload:
        if type(payload['gater']) is not bool:raise ValueError('Boolean required')
        proxy['photo_restoration']['enabled']=payload['gater']
    h['gendefaults']=json.dumps(gd,ensure_ascii=False,separators=(',',':'));new=_encode(h);new_hash=hashlib.sha256(new).hexdigest()
    record=root/'logs/proxy-supervisor-active.json';manifest=root/'portable-manifest.json'
    backups={helper:old}
    for path in (record,manifest):
        if path.exists():backups[path]=path.read_bytes()
    if record.exists():
        identity=json.loads(backups[record])
        if identity.get('pid')!=pid or identity.get('helper_sha256')!=revision or Path(identity['helper']).resolve()!=helper:raise ValueError('Frontend identity changed; preserved')
        identity['helper_sha256']=new_hash
    try:
        _atomic(helper,new)
        if record.exists():_atomic(record,_encode(identity))
        if manifest.exists():
            data=json.loads(backups[manifest]);rows={r['path']:r for r in data['files']};rows['Helper.kcpps']={'path':'Helper.kcpps','bytes':len(new),'sha256':new_hash};data['files']=sorted(rows.values(),key=lambda r:r['path']);data.update(file_count=len(rows),total_bytes=sum(r['bytes'] for r in rows.values()),updated=time.time());_atomic(manifest,_encode(data))
    except BaseException:
        for path,raw in backups.items():_atomic(path,raw)
        raise
    return {'saved':True,'revision':new_hash,'reload_required':False,'inference_started':False}

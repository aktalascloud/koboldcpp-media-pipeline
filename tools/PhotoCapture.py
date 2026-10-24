"""Explicit local benchmark capture; disabled unless a configured key matches.

The API caller cannot choose a path. Regular image requests never save files.
"""
from pathlib import Path
from PIL import PngImagePlugin
from RuntimePaths import ROOT

def capture_stage(config,key,stage,image):
    options=config.get('proxy',{}).get('comparison_capture',{})
    if options.get('enabled') is not True or not key or key!=options.get('genkey'):return
    if stage not in {'raw','faces','processed'}:raise ValueError('Invalid capture stage.')
    parent=(ROOT/'MOSS/results').resolve();folder=(ROOT/str(options.get('directory',''))).resolve()
    if not folder.is_relative_to(parent) or folder==parent:raise ValueError('Benchmark capture escaped its private folder.')
    folder.mkdir(parents=True,exist_ok=True);target=folder/(stage+'.png')
    if target.exists():raise ValueError('Existing benchmark stage is preserved.')
    tags=PngImagePlugin.PngInfo()
    for name,value in image.info.items():
        if isinstance(value,str):tags.add_text(name,value)
    image.save(target,format='PNG',pnginfo=tags)

"""KoboldCpp ESRGAN API adapter with an exact requested output size."""
import argparse
import base64
import io
import json
from pathlib import Path
import time
import urllib.request
from PIL import Image

parser=argparse.ArgumentParser()
parser.add_argument('image',type=Path)
parser.add_argument('--scale',type=float,default=2)
parser.add_argument('--out',type=Path)
args=parser.parse_args()
if not 1 <= args.scale <= 4:
    parser.error('--scale must be between 1 and 4')
with Image.open(args.image) as im:
    original_size=im.size
    original_alpha=im.getchannel('A') if 'A' in im.getbands() else None
output=args.out or args.image.with_name(args.image.stem+f'-upscaled-{args.scale:g}x.png')
if output.resolve()==args.image.resolve():
    parser.error('Output must differ from original')
if output.exists():
    parser.error('Output already exists; choose a new --out path')
payload={'image':base64.b64encode(args.image.read_bytes()).decode(),'upscaling_resize':4}
req=urllib.request.Request('http://127.0.0.1:5001/sdapi/v1/upscale',json.dumps(payload).encode(),{'Content-Type':'application/json'})
start=time.perf_counter()
with urllib.request.urlopen(req,timeout=1800) as response:
    result=json.load(response)
if not result.get('image'):
    raise RuntimeError('Upscaler did not return an image')
im=Image.open(io.BytesIO(base64.b64decode(result['image'].split(',')[-1])))
target=(round(original_size[0]*args.scale),round(original_size[1]*args.scale))
if im.size!=target:
    im=im.resize(target,Image.Resampling.LANCZOS)
if original_alpha is not None:
    im=im.convert('RGBA')
    im.putalpha(original_alpha.resize(target,Image.Resampling.LANCZOS))
im.save(output)
print(json.dumps({'output':str(output.resolve()),'size':im.size,'seconds':round(time.perf_counter()-start,3)},ensure_ascii=False))

"""Local image API proxy with optional CPU face detection and Kobold crop inpainting.

Native ADetailer is an A1111 extension; this is a separate, lightweight equivalent.
Enable per request with kcpp_detailer=true, or POST an existing image to
/sdapi/v1/detail. The standard API remains unchanged when the option is absent.
"""
import argparse
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import sys
import threading
import time
import urllib.error
import urllib.request
from RuntimePaths import dependencies

HERE=Path(__file__).resolve().parent
dependencies()
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

FACE_PROMPT='A natural close-up photograph of the same adult person, consistent identity, age, expression, gaze, lighting and skin tone. Realistic eyes and eyelashes, subtle skin pores, no beauty retouching.'
def image_bytes(im):
    out=io.BytesIO();im.save(out,format='PNG');return out.getvalue()
def encode(im):return base64.b64encode(image_bytes(im)).decode()
def decode(value):return Image.open(io.BytesIO(base64.b64decode(value.split(',')[-1]))).convert('RGB')
def post(url,payload,timeout=600):
    req=urllib.request.Request(url,json.dumps(payload).encode(),{'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=timeout) as r:return json.load(r)

class FaceDetailer:
    def __init__(self,backend='http://127.0.0.1:5001',detector_resolution=640,score_threshold=.82,nms_threshold=.3,top_k=5000):
        self.backend=backend.rstrip('/')
        self.detector_resolution=int(detector_resolution)
        if not 320<=self.detector_resolution<=2048 or not 0<float(score_threshold)<1 or not 0<float(nms_threshold)<1 or not 1<=int(top_k)<=10000:raise ValueError('Invalid YuNet settings')
        self.detector=cv2.FaceDetectorYN.create(str(HERE/'detailer_models'/'face_detection_yunet_2023mar.onnx'),'',(self.detector_resolution,self.detector_resolution),float(score_threshold),float(nms_threshold),int(top_k))
        cv2.setNumThreads(2)
        self.lock=threading.Lock()
    def detect(self,im,minimum=32,maximum=160):
        ratio=min(1,self.detector_resolution/max(im.size));size=(max(32,round(im.width*ratio)),max(32,round(im.height*ratio)))
        bgr=np.asarray(im.resize(size,Image.Resampling.LANCZOS))[:,:,::-1].copy()
        self.detector.setInputSize(size);_,found=self.detector.detect(bgr)
        out=[]
        if found is None:return out
        for f in found:
            x,y,w,h=[float(v)/ratio for v in f[:4]]
            if min(w,h)<minimum or max(w,h)>maximum:continue
            out.append(dict(box=[x,y,w,h],landmarks=[float(v)/ratio for v in f[4:14]],confidence=float(f[-1])))
        return sorted(out,key=lambda f:f['box'][2]*f['box'][3],reverse=True)
    def refine(self,im,options=None,base_parameters=None,progress=None):
        options=options or {};base_parameters=base_parameters or {};started=time.perf_counter()
        strength=float(options.get('strength',.25));steps=int(options.get('steps',8));resolution=int(options.get('resolution',512));limit=int(options.get('max_faces',2))
        scheduler=options.get('scheduler','ltx2');visibility=float(options.get('visibility',1))
        if scheduler not in ('ltx2','beta') or not 0<visibility<=1:raise ValueError('Invalid refinement scheduler/visibility')
        if not 0<strength<=.6 or not 1<=steps<=9 or resolution not in (256,320,384,448,512,576,640,704,768) or not 1<=limit<=4:raise ValueError('Invalid bounded detailer parameters')
        minimum=int(options.get('minimum_face',32));maximum=int(options.get('maximum_face',160))
        if not 16<=minimum<=maximum<=2048:raise ValueError('Invalid face size range')
        original=im.convert('RGB');result=original.copy();report=dict(detector='OpenCV YuNet CPU',options=dict(strength=strength,steps=steps,resolution=resolution,max_faces=limit,minimum_face=minimum,maximum_face=maximum,scheduler=scheduler,visibility=visibility),faces=[])
        with self.lock:
            faces=self.detect(original,minimum,maximum)[:limit]
            for index,face in enumerate(faces):
                x,y,w,h=face['box'];edge=min(max(w,h)*2.6,im.width,im.height)
                left=max(0,min(im.width-edge,x+w/2-edge/2));top=max(0,min(im.height-edge,y+h/2-edge/2))
                box=(int(left),int(top),int(left+edge),int(top+edge));crop=original.crop(box)
                native_mask=Image.new('L',crop.size,0)
                ellipse=(x-left-.12*w,y-top-.13*h,x-left+1.12*w,y-top+1.12*h)
                ImageDraw.Draw(native_mask).ellipse(ellipse,fill=255)
                # Pillow's blur has finite support; pixels outside the stored mask remain exact.
                native_mask=native_mask.filter(ImageFilter.GaussianBlur(max(1,min(w,h)*.06)))
                request_mask=native_mask.resize((resolution,resolution),Image.Resampling.LANCZOS)
                crop=crop.resize((resolution,resolution),Image.Resampling.LANCZOS)
                seed=int(base_parameters.get('seed',104729));seed=104729 if seed<0 else seed
                p=dict(prompt=options.get('prompt',FACE_PROMPT),negative_prompt='',init_images=[encode(crop)],mask=encode(request_mask),inpainting_mask_invert=0,
                  width=resolution,height=resolution,steps=steps,cfg_scale=1,sampler_name='euler',scheduler=scheduler,eta=0,flow_shift=3,clip_skip=-1,
                  cache_mode='disabled',cache_options='',enable_hr=False,denoising_strength=strength,seed=(seed+1000003*(index+1))%2147483647,
                  batch_size=1,n_iter=1,genkey=f'detailer_{time.time_ns()}_{index}')
                if progress:progress(dict(stage='detailer',face=index+1,total_faces=len(faces),genkey=p['genkey']))
                before=time.perf_counter();answer=post(self.backend+'/sdapi/v1/img2img',p)
                if not answer.get('images') or not answer['images'][0]:raise RuntimeError('Kobold returned no detail crop')
                refined=decode(answer['images'][0])
                if refined.size!=(resolution,resolution):raise RuntimeError('Unexpected detail crop dimensions')
                refined=refined.resize((box[2]-box[0],box[3]-box[1]),Image.Resampling.LANCZOS)
                result.paste(refined,box[:2],native_mask)
                report['faces'].append(dict(**face,crop=list(box),seconds=round(time.perf_counter()-before,3),seed=p['seed'],actual_info=answer.get('info',''),mask_sha256=__import__('hashlib').sha256(native_mask.tobytes()).hexdigest()))
        report['seconds']=round(time.perf_counter()-started,3)
        report['image_dimensions']=list(result.size)
        report['processed_faces']=len(report['faces'])
        if visibility<1:result=Image.blend(original,result,visibility)
        if 'A' in im.getbands():
            result=result.convert('RGBA');result.putalpha(im.getchannel('A'))
        return result,report

def serve(port=5002,backend='http://127.0.0.1:5001'):
    engine=FaceDetailer(backend)
    class Handler(BaseHTTPRequestHandler):
        protocol_version='HTTP/1.1'
        def reply(self,data,status=200,content_type='application/json'):
            if not isinstance(data,bytes):data=json.dumps(data,ensure_ascii=False).encode('utf-8')
            self.send_response(status);self.send_header('Content-Type',content_type);self.send_header('Content-Length',str(len(data)));self.send_header('Access-Control-Allow-Origin','*');self.end_headers();self.wfile.write(data)
        def do_OPTIONS(self):
            self.send_response(204);self.send_header('Access-Control-Allow-Origin','*');self.send_header('Access-Control-Allow-Headers','Content-Type, Authorization');self.send_header('Access-Control-Allow-Methods','GET, POST, OPTIONS');self.send_header('Content-Length','0');self.end_headers()
        def do_GET(self):
            if self.path=='/health':self.reply(dict(status='ready',backend=backend,face_detection='CPU',enabled_by_default=False));return
            self.forward()
        def forward(self,body=None):
            headers={k:v for k,v in self.headers.items() if k.lower() not in ('host','content-length','connection','transfer-encoding')}
            req=urllib.request.Request(backend+self.path,body,headers,method=self.command)
            try:
                with urllib.request.urlopen(req,timeout=600) as answer:self.reply(answer.read(),answer.status,answer.headers.get('Content-Type','application/json'))
            except urllib.error.HTTPError as e:self.reply(e.read(),e.code,e.headers.get('Content-Type','application/json'))
        def do_POST(self):
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=32*1024*1024:self.reply({'error':'Invalid request size'},413);return
                body=self.rfile.read(length)
                if self.path.split('?')[0] not in ('/sdapi/v1/txt2img','/sdapi/v1/img2img','/sdapi/v1/detail'):self.forward(body);return
                payload=json.loads(body);option=payload.pop('kcpp_detailer',False)
                if self.path=='/sdapi/v1/detail':
                    im=decode(payload['image']);options=payload.get('detailer',{})
                    final,report=engine.refine(im,options,payload)
                    self.reply(dict(image=encode(final),detailer=report));return
                if not option:self.forward(json.dumps(payload).encode());return
                answer=post(backend+self.path,payload);reports=[];images=[]
                for encoded in answer.get('images',[]):
                    final,report=engine.refine(decode(encoded),option if isinstance(option,dict) else {},payload)
                    images.append(encode(final));reports.append(report)
                answer['images']=images;answer['kcpp_detailer_report']=reports;self.reply(answer)
            except Exception as e:self.reply(dict(error=type(e).__name__,detail=str(e)),502)
        def log_message(self,format,*args):print(time.strftime('%H:%M:%S'),format%args,flush=True)
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    print(f'Local detailer proxy http://127.0.0.1:{port}; backend {backend}; enabled only by explicit request',flush=True)
    server.serve_forever()
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=5002);parser.add_argument('--backend',default='http://127.0.0.1:5001');a=parser.parse_args();serve(a.port,a.backend)

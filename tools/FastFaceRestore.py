"""Local FP32 GFPGAN/CodeFormer restoration with conservative face-only compositing.

Model input conventions and FFHQ coordinates follow FaceFusion3.0.0's public
face-enhancer model specification. No FaceFusion application/content analyser is used.
"""
import gc
import hashlib
from pathlib import Path
import sys
import time
from RuntimePaths import dependencies

HERE=Path(__file__).resolve().parent
dependencies()
import cv2
import numpy as np
import onnxruntime as ort
from PIL import Image,ImageDraw,ImageFilter
from DetailerProxy import FaceDetailer
from GpuAdapter import select_dml_adapter
from OvSession import OvSession

FFHQ=np.array([[.37691676,.46864664],[.62285697,.46912813],[.50123859,.61331904],[.39308822,.72541100],[.61150205,.72490465]],np.float32)*512
class FeatureGuard:
    def __init__(self,path=None):
        self.path=Path(path or HERE/'detailer_models'/'face_recognition_sface_2021dec.onnx')
        self.model=cv2.FaceRecognizerSF.create(str(self.path),'')
    def feature(self,image,face):
        bgr=np.asarray(image.convert('RGB'))[:,:,::-1].copy()
        row=np.asarray([*face['box'],*face['landmarks'],face['confidence']],np.float32)
        aligned=self.model.alignCrop(bgr,row)
        feature=self.model.feature(aligned).reshape(-1).astype(np.float64)
        return feature/max(float(np.linalg.norm(feature)),1e-10)
    def similarity(self,a,b,face):return float(np.dot(self.feature(a,face),self.feature(b,face)))

class Restorer:
    def __init__(self,model,provider='directml',detector=None,guard=None,profile_prefix=None):
        self.path=Path(model);self.provider=provider;self.detector=detector or FaceDetailer();self.guard=guard
        options=ort.SessionOptions();options.enable_mem_pattern=False;options.execution_mode=ort.ExecutionMode.ORT_SEQUENTIAL
        options.intra_op_num_threads=2;options.inter_op_num_threads=1
        if profile_prefix:options.enable_profiling=True;options.profile_file_prefix=str(profile_prefix)
        adapter=select_dml_adapter() if provider=='directml' else None
        providers=[('DmlExecutionProvider',{'device_id':adapter['index']}),'CPUExecutionProvider'] if adapter else ['CPUExecutionProvider']
        start=time.perf_counter()
        if provider=='openvino':
            self.session=OvSession(self.path,threads=10)
        else:self.session=ort.InferenceSession(str(self.path),sess_options=options,providers=providers)
        if provider=='directml' and self.session.get_providers()[0]!='DmlExecutionProvider':raise RuntimeError('DirectML not active')
        self.inputs=self.session.get_inputs();self.output_name=self.session.get_outputs()[0].name;self.load_seconds=round(time.perf_counter()-start,4)
        self.metadata=dict(model=str(self.path),model_sha256=hashlib.sha256(self.path.read_bytes()).hexdigest(),provider=provider,ort_version=ort.__version__,load_seconds=self.load_seconds,inputs=[dict(name=i.name,type=i.type,shape=i.shape) for i in self.inputs])
        self.metadata['adapter']=adapter
    def restore_crop(self,crop,fidelity):
        tensor=np.ascontiguousarray((crop.astype(np.float32)/127.5-1).transpose(2,0,1)[None])
        feed={}
        for item in self.inputs:
            if item.name=='input':feed[item.name]=tensor
            elif item.name=='weight':feed[item.name]=np.asarray(fidelity if item.shape==[] else [fidelity],np.float64 if item.type=='tensor(double)' else np.float32)
            else:raise ValueError('Unknown restoration input '+item.name)
        out=self.session.run([self.output_name],feed)[0]
        if out.shape!=(1,3,512,512) or not np.isfinite(out).all():raise RuntimeError('Invalid restoration output')
        return np.rint((np.clip(out[0].transpose(1,2,0),-1,1)+1)*127.5).astype(np.uint8)
    def refine(self,image,options=None,base_parameters=None,progress=None,detected_faces=None):
        opts=options or {};start=time.perf_counter();visibility=float(opts.get('visibility',1));fidelity=float(opts.get('fidelity',.9));minimum=int(opts.get('minimum_face',32));maximum=int(opts.get('maximum_face',160));limit=int(opts.get('max_faces',2))
        if not 0<visibility<=1 or not 0<=fidelity<=1 or not 1<=limit<=4:raise ValueError('Invalid face-restoration options')
        original=image.convert('RGB');result=original.copy();union=Image.new('L',image.size,0)
        mask_mode=opts.get('mask_mode','face')
        if mask_mode not in ('face','eyes'):raise ValueError('Invalid restoration mask mode')
        report=dict(detector='OpenCV YuNet CPU',mode=self.path.stem,provider=self.provider,options=dict(visibility=visibility,fidelity=fidelity,minimum_face=minimum,maximum_face=maximum,max_faces=limit,resampling='lanczos_before_inverse_affine',mask_mode=mask_mode),model_load_seconds=self.load_seconds,compiled_cache_used=getattr(self.session,'loaded_from_cache',False),faces=[])
        faces=(self.detector.detect(original,minimum,maximum) if detected_faces is None else detected_faces)[:limit]
        for index,face in enumerate(faces):
            if progress:progress(dict(stage='face_restorer',face=index+1,total_faces=len(faces)))
            stamp=time.perf_counter();src=np.asarray(face['landmarks'],np.float32).reshape(5,2)
            matrix,_=cv2.estimateAffinePartial2D(src,FFHQ,method=cv2.LMEDS)
            if matrix is None:raise RuntimeError('Could not align detected face')
            crop=cv2.warpAffine(np.asarray(original),matrix,(512,512),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_REPLICATE)
            restored=self.restore_crop(crop,fidelity)
            # First antialias down to the source face's sampling density. A direct
            # linear inverse warp from512 pixels aliases skin detail on tiny faces.
            scale=float(np.sqrt(abs(np.linalg.det(matrix[:,:2]))))
            target=min(512,max(32,round(512/max(scale,1))))
            if target<512:
                restored=np.asarray(Image.fromarray(restored).resize((target,target),Image.Resampling.LANCZOS))
                factor=target/512
                matrix=matrix*factor
                matrix[:,2]+=(factor-1)*.5
            inverse=cv2.invertAffineTransform(matrix)
            restored=cv2.warpAffine(restored,inverse,image.size,flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_REPLICATE)
            x,y,w,h=face['box'];mask=Image.new('L',image.size,0)
            ImageDraw.Draw(mask).ellipse((x-.12*w,y-.13*h,x+1.12*w,y+1.12*h),fill=255)
            mask=mask.filter(ImageFilter.GaussianBlur(max(1,min(w,h)*.06)))
            if mask_mode=='eyes':
                eyes=Image.new('L',image.size,0);draw=ImageDraw.Draw(eyes)
                for ex,ey in np.asarray(face['landmarks']).reshape(5,2)[:2]:draw.ellipse((ex-.18*w,ey-.065*h,ex+.18*w,ey+.065*h),fill=255)
                eyes=eyes.filter(ImageFilter.GaussianBlur(max(1,min(w,h)*.025)))
                mask=Image.fromarray(((np.asarray(mask,dtype=np.uint16)*np.asarray(eyes,dtype=np.uint16)+127)//255).astype(np.uint8))
            alpha=np.asarray(mask,dtype=np.float32)[:,:,None]*(visibility/255)
            proposed=Image.fromarray(np.rint(np.asarray(result)*(1-alpha)+restored*alpha).clip(0,255).astype(np.uint8))
            similarity=self.guard.similarity(original,proposed,face) if self.guard else None
            accepted=similarity is None or similarity>=float(opts.get('minimum_feature_similarity',0))
            if accepted:
                result=proposed;union=Image.fromarray(np.maximum(np.asarray(union),np.asarray(mask)))
            report['faces'].append(dict(**face,seconds=round(time.perf_counter()-stamp,4),feature_similarity=similarity,applied=accepted,mask_sha256=hashlib.sha256(mask.tobytes()).hexdigest()))
        report.update(seconds=round(time.perf_counter()-start,4),processed_faces=sum(f['applied'] for f in report['faces']),attempted_faces=len(faces),image_dimensions=list(result.size),outside_masks_exact=bool(np.array_equal(np.asarray(original)[np.asarray(union)==0],np.asarray(result)[np.asarray(union)==0])))
        assert report['outside_masks_exact']
        if 'A' in image.getbands():result=result.convert('RGBA');result.putalpha(image.getchannel('A'))
        return result,report
    def close(self):self.session=None;gc.collect()

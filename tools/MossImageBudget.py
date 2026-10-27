"""MOSS FA profile guard. Uses measured geometry, never Z-Image's score formula.

The UTF-8 byte count is a conservative token upper bound, not an exact count.
GGUF tensor directories are checked without reading multi-gigabyte weights.
"""
from pathlib import Path
import functools,json,struct,unicodedata,hashlib,math

def _read(stream,fmt):
    size=struct.calcsize(fmt);data=stream.read(size)
    if len(data)!=size:raise ValueError('Truncated GGUF directory.')
    return struct.unpack(fmt,data)[0]
def _string(stream):
    size=_read(stream,'<Q')
    if size>1048576:raise ValueError('GGUF directory string too large.')
    return stream.read(size).decode('utf-8')
def _value(stream,kind):
    formats={0:'<B',1:'<b',2:'<H',3:'<h',4:'<I',5:'<i',6:'<f',7:'<?',10:'<Q',11:'<q',12:'<d'}
    if kind in formats:return _read(stream,formats[kind])
    if kind==8:return _string(stream)
    if kind==9:
        sub=_read(stream,'<I');count=_read(stream,'<Q')
        if count>1000000:raise ValueError('GGUF metadata array too large.')
        return [_value(stream,sub) for _ in range(count)]
    raise ValueError('Unknown GGUF metadata type.')
@functools.lru_cache(maxsize=8)
def _directory(path,identity):
    with Path(path).open('rb') as stream:
        if stream.read(4)!=b'GGUF' or _read(stream,'<I')!=3:raise ValueError('Expected GGUF v3.')
        count=_read(stream,'<Q');metadata_count=_read(stream,'<Q')
        if count>10000 or metadata_count>10000:raise ValueError('Unbounded GGUF directory.')
        metadata={}
        for _ in range(metadata_count):
            key=_string(stream);metadata[key]=_value(stream,_read(stream,'<I'))
        kinds={};names=set();signature={}
        for _ in range(count):
            name=_string(stream);dimensions=_read(stream,'<I')
            if not 0<=dimensions<=8:raise ValueError('Unexpected GGUF tensor rank: '+name)
            shape=tuple(_read(stream,'<Q') for _ in range(dimensions))
            short=name.removeprefix('model.diffusion_model.').removeprefix('diffusion_model.')
            if short in ('final_linear_video.weight','layers.0.proj.qkv.weight','layers.41.proj.o.weight'):signature[short]=shape
            kind=_read(stream,'<I');_read(stream,'<Q');names.add(name)
            kinds[kind]=kinds.get(kind,0)+1
    architecture=metadata.get('general.architecture');container_architecture=architecture
    if architecture=='qwen_image' and signature=={'final_linear_video.weight':(3072,128),'layers.0.proj.qkv.weight':(3072,9216),'layers.41.proj.o.weight':(3072,3072)}:architecture='moss_image'
    quant='q8_0' if 8 in kinds and 2 not in kinds else 'q4_0' if 2 in kinds and 8 not in kinds else None
    if quant is None or set(kinds)-{0,1,2,8,26}:raise ValueError('Expected reviewed Q8_0/Q4_0 matrices and unquantized small tensors.')
    return dict(architecture=architecture,container_architecture=container_architecture,tensor_signature_confirmation=signature if architecture!=container_architecture else {},tensor_count=count,types=kinds,
                quantization=quant,quantization_confirmation='GGUF_tensor_directory',names=names)
def inspect_gguf(path):
    path=Path(path).resolve();s=path.stat()
    return _directory(str(path),(s.st_size,s.st_mtime_ns,s.st_ino))

@functools.lru_cache(maxsize=16)
def _adapter_sha(path,identity):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def validate_static_adapters(helper,root):
    paths=helper.get('sdlora') or [];weights=helper.get('sdloramult') or []
    if not paths:return []
    if not isinstance(paths,list) or not isinstance(weights,list) or len(paths)!=len(weights) or len(paths)>4:raise ValueError('Explicit static MOSS adapter paths/weights required.')
    manifest=json.loads((root/'profiles/moss-adapters.json').read_text(encoding='utf-8-sig'));allowed={row['path']:row for row in manifest['adapters']};out=[];turbo=0
    if manifest.get('base_model_path') and (root/helper.get('sdmodel','')).resolve()!=(root/manifest['base_model_path']).resolve():raise ValueError('Static adapters were not reviewed for this model path.')
    for value,weight in zip(paths,weights):
        path=(root/value).resolve()
        if not path.is_relative_to(root) or path.suffix!='.safetensors' or not path.is_file():raise ValueError('Static adapter missing/outside portable Root.')
        relative=path.relative_to(root).as_posix();row=allowed.get(relative)
        if not row or not row.get('approved'):raise ValueError('Unreviewed MOSS adapter.')
        if isinstance(weight,bool) or not math.isfinite(float(weight)) or float(weight)!=float(row['weight']):raise ValueError('Static adapter weight differs from reviewed profile.')
        stat=path.stat();digest=_adapter_sha(str(path),(stat.st_size,stat.st_mtime_ns,stat.st_ino))
        if digest!=row['sha256']:raise ValueError('MOSS adapter SHA256 mismatch.')
        turbo+=row['role']=='turbo';out.append(dict(path=relative,weight=float(weight),sha256=digest,role=row['role']))
    if turbo>1:raise ValueError('Only one turbo/distillation adapter may be active.')
    return out
def validate_profile(helper,root):
    root=Path(root).resolve()
    if helper.get('sdflashattention') is not True or helper.get('sdquant')!=0:
        raise ValueError('MOSS requires FA and its already quantized GGUF; sdquant must be0.')
    if helper.get('sdclipdevice')!=-2 or helper.get('sdoffloadcpu') is not False:
        raise ValueError('MOSS requires CPU text encoding and GPU diffusion.')
    result={}
    adapters=validate_static_adapters(helper,root)
    if adapters:result['static_adapters']=adapters
    for field,architecture in [('sdmodel','moss_image'),('sdclip1','qwen35')]:
        path=(root/helper.get(field,'')).resolve()
        if not path.is_relative_to(root):raise ValueError('MOSS model escaped the portable root.')
        info=inspect_gguf(path)
        if info['architecture']!=architecture:raise ValueError('Wrong MOSS model/encoder architecture.')
        result[field]={key:value for key,value in info.items() if key!='names'}
    tokenizer=(root/helper.get('sdclip2','')).resolve()
    if not tokenizer.is_relative_to(root) or not tokenizer.is_file() or tokenizer.suffix.lower()!='.json':
        raise ValueError('Official MOSS Qwen3.5 tokenizer.json is required.')
    return result

def apply_moss_budget(payload,config,*,operation,image_prepared,root):
    from ImageBudget import ImageBudgetDecision,ImageBudgetError
    helper=config.get('helper',{})
    try:profiles=validate_profile(helper,root)
    except (OSError,ValueError,UnicodeError) as error:
        raise ImageBudgetError('MOSS profile validation failed: '+str(error),'imageBudget','unsupported_moss_profile',503) from error
    static_adapters=profiles.pop('static_adapters',[])
    width,height=payload['width'],payload['height']
    if width*height>2000000 or max(width,height)>1776:
        raise ImageBudgetError('MOSS geometry exceeds the measured RX580 FA envelope.','size','moss_geometry_exceeded',422)
    positive=payload.get('prompt','high quality');forced=payload.get('add_sd_prompt','')
    body=', '.join([positive,forced])
    if len(body.encode('utf-8'))>3000:
        raise ImageBudgetError('Use a caption up to3000 UTF-8 bytes; no silent prompt truncation.','prompt','moss_caption_too_long',422)
    template='<|im_start|>user\n'+body+'<|im_end|>\n<|im_start|>assistant\n<think>\n'
    upper=len(unicodedata.normalize('NFC',template).encode('utf-8'))
    if upper>4096:raise ImageBudgetError('MOSS caption exceeds its conservative4096-token upper bound.','prompt','moss_caption_too_long',422)
    report=dict(policy='moss_FA_measured_geometry',selectedDimensions=[width,height],actualDimensions=[width,height],
        captionTokens=None,paddedTokens=None,captionTokenUpperBound=upper,captionTokenLimit=4096,
        scoreBytes=None,limitBytes=None,paddedImageTokens=None,fallbackReason=None,resized=False,
        operation=operation,imagePrepared=bool(image_prepared),NativeExistingPromptByteCut=False,
        promptChanged=False,stepsChanged=False,cacheChanged=False,modelChanged=False,
        diffusionDevice='Vulkan',textEncoderDevice='CPU',prequantized=profiles,static_adapters=static_adapters,
        limitation='Selected FA envelope; acceptance is recorded separately. Byte upper bound is not an exact tokenizer count; Z-Image noFA formula is not used.')
    return ImageBudgetDecision(payload,config,report)

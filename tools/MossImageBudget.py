"""MOSS FA profile guard. Uses measured geometry, never Z-Image's score formula.

The UTF-8 byte count is a conservative token upper bound, not an exact count.
GGUF tensor directories are checked without reading multi-gigabyte weights.
"""
from pathlib import Path
import functools,json,struct,unicodedata

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
        kinds={};names=set()
        for _ in range(count):
            name=_string(stream);dimensions=_read(stream,'<I')
            if not 0<=dimensions<=8:raise ValueError('Unexpected GGUF tensor rank: '+name)
            for _ in range(dimensions):_read(stream,'<Q')
            kind=_read(stream,'<I');_read(stream,'<Q');names.add(name)
            kinds[kind]=kinds.get(kind,0)+1
    if 8 not in kinds or set(kinds)-{0,8,26}:raise ValueError('Expected Q8_0 matrices and unquantized small tensors.')
    return dict(architecture=metadata.get('general.architecture'),tensor_count=count,types=kinds,
                quantization='q8_0',quantization_confirmation='GGUF_tensor_directory',names=names)
def inspect_gguf(path):
    path=Path(path).resolve();s=path.stat()
    return _directory(str(path),(s.st_size,s.st_mtime_ns,s.st_ino))
def validate_profile(helper,root):
    root=Path(root).resolve()
    if helper.get('sdflashattention') is not True or helper.get('sdquant')!=0:
        raise ValueError('MOSS requires FA and its already quantized GGUF; sdquant must be0.')
    if helper.get('sdclipdevice')!=-2 or helper.get('sdoffloadcpu') is not False or helper.get('sdlora'):
        raise ValueError('MOSS requires the CPU text encoder, GPU diffusion, and no Z-Image LoRA.')
    result={}
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
        diffusionDevice='Vulkan',textEncoderDevice='CPU',prequantized=profiles,
        limitation='Selected FA envelope; acceptance is recorded separately. Byte upper bound is not an exact tokenizer count; Z-Image noFA formula is not used.')
    return ImageBudgetDecision(payload,config,report)

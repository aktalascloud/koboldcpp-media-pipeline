"""Exact Native SD-Qwen caption budget for the selected ZImage/noFA profile.

Pure CPU/string work. No Native, network, process, model or image inference.
Generation may select a smaller exact author ratio; prepared edits never resize.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import copy
import hashlib
import importlib.util
import json
import re
import sys
import threading
import time

TENSOR_LIMIT_BYTES=2147483648
HEADS=30
ASSET_RELATIVE='tools/SDTokenizer'
EXPECTED={
    'native_counter.py':'202a2bf3d704624ac593be0955d0791b7012c8ef125189546abd642cad214751',
    'qwen2-merges.native.txt':'0de0bc38a29ea38eef099b677fa1ff52edd181e573529af26c4cd2136e233777',
    'native-qwen-spec.json':'3113adb80b9ed125d4577ab978ced08505ab9924b9e50c04a76528abe9ceb8d6',
    'dependency-install.json':'7539e63b25cfabffbcca800f7ca75dbd37f2c3d122f4579e356049043d87a5c2',
}
_LOCK=threading.RLock()
_COUNTERS={}


class ImageBudgetError(ValueError):
    def __init__(self,message,field='prompt',code='image_gpu_budget_error',status=400,report=None):
        super().__init__(message)
        self.status=status
        self.body=dict(error=dict(message=message,type='invalid_request_error',param=field,code=code))
        if report is not None:self.body['imageBudget']=report


@dataclass
class ImageBudgetDecision:
    payload:dict
    config:dict
    report:dict


def _sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def _asset_directory(root=None,assets=None):
    if assets is not None:return Path(assets).resolve()
    if root is None:
        from RuntimePaths import ROOT
        root=ROOT
    return (Path(root).resolve()/ASSET_RELATIVE).resolve()


def _counter(root=None,assets=None):
    directory=_asset_directory(root,assets)
    with _LOCK:
        key=str(directory)
        if key in _COUNTERS:return _COUNTERS[key]
        try:
            manifest=json.loads((directory/'asset-manifest.json').read_text(encoding='utf-8'))
            files=manifest['files']
            actual={p.relative_to(directory).as_posix() for p in directory.rglob('*')
                    if p.is_file() and '__pycache__' not in p.relative_to(directory).parts}
            if actual!=set(files)|{'asset-manifest.json'}:
                raise ValueError('Unexpected/missing tokenizer package files.')
            for relative,item in files.items():
                part=PurePosixPath(relative)
                if part.is_absolute() or '..' in part.parts:raise ValueError('Invalid package path.')
                path=(directory/relative).resolve()
                if not path.is_relative_to(directory) or path.stat().st_size!=item['bytes'] or _sha(path)!=item['sha256']:
                    raise ValueError('Tokenizer package file changed: '+relative)
            for relative,digest in EXPECTED.items():
                if files.get(relative,{}).get('sha256')!=digest or _sha(directory/relative)!=digest:
                    raise ValueError('Validated Native tokenizer input mismatch: '+relative)
            proof=json.loads((directory/'validation.json').read_text(encoding='utf-8'))
            if proof['validated_counter_sha256']!=EXPECTED['native_counter.py'] or len(proof['golden_cases'])!=4 or not all(row['exact_strings_count_padding'] for row in proof['golden_cases']):
                raise ValueError('Native golden parity proof is missing.')
            name='_kcpp_validated_sd_counter_'+hashlib.sha256(key.encode()).hexdigest()[:16]
            spec=importlib.util.spec_from_file_location(name,directory/'native_counter.py')
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            # Another CPU module may already have loaded byte-identical regex.
            # Accept that copy only when every loaded package module matches.
            if module.regex.__version__!='2026.9.29':raise ValueError('Wrong Unicode regex version.')
            for loaded_name,loaded in tuple(sys.modules.items()):
                if loaded_name=='regex' or loaded_name.startswith('regex.'):
                    filename=getattr(loaded,'__file__',None)
                    if not filename:continue
                    path=Path(filename)
                    relative='deps/regex/'+path.name
                    if relative not in files or _sha(path)!=files[relative]['sha256']:
                        raise ValueError('An incompatible regex module is already loaded.')
            counter=module.NativeQwenCounter()
            _COUNTERS[key]=counter
            return counter
        except ImageBudgetError:raise
        except Exception as error:
            raise ImageBudgetError('The validated SD tokenizer package is unavailable; image generation is blocked until repaired: '+str(error),
                                   'imageBudget','image_tokenizer_unavailable',503) from error


def prewarm_image_budget(root=None,assets=None):
    started=time.perf_counter();_counter(root,assets)
    return dict(ok=True,seconds=time.perf_counter()-started,policy='Native_SD_Qwen_exact_counter',weights_loaded=False)


def score_bytes(width,height,padded_caption_tokens):
    image=(width//16)*(height//16);padded_image=(image+31)//32*32
    return 4*HEADS*(padded_image+padded_caption_tokens)**2,padded_image


def apply_image_gpu_budget(payload,config,*,operation='generation',image_prepared=False,root=None,assets=None):
    """Call after self.profile/trigger handling and final Native geometry.

    The input prompt is never replaced/trimmed. Runtime LoRA directives receive
    an explicit400 until their local Native-removal path is parity-validated.
    Missing counter data fails closed, with503, before entering the Native lease.
    """
    if not isinstance(payload,dict) or not isinstance(config,dict):raise ImageBudgetError('Image payload/config must be objects.')
    if operation not in ('generation','edit'):raise ImageBudgetError('Unsupported image budget operation.','operation')
    local=copy.deepcopy(payload);cfg=copy.deepcopy(config)
    for field in ('add_sd_cfg_limit','add_sd_step_limit'):
        if field in local:
            raise ImageBudgetError('Native limit overrides cannot change the fixed CFG1/eight-step image profile.',field,'unsupported_profile_override')
    extra=local.get('kcpp_extra_args')
    if extra is not None:
        if not isinstance(extra,dict) or not isinstance(extra.get('params',{}),dict):
            raise ImageBudgetError('Malformed nested Native parameters.','kcpp_extra_args','unsupported_nested_budget')
        allowed={'steps','cfg_scale','sampler_name','scheduler','eta','flow_shift','clip_skip','cache_mode','cache_options'}
        if any(key not in allowed or key not in local or value!=local[key] for key,value in extra.get('params',{}).items()):
            raise ImageBudgetError('Nested Native parameters cannot override the resolved image geometry, prompt or fixed profile.','kcpp_extra_args','unsupported_nested_budget')
    if isinstance(local.get('cfg_scale'),bool) or local.get('cfg_scale')!=1:
        raise ImageBudgetError('The validated image profile requires CFG1.','cfg_scale','unsupported_gpu_budget_profile')
    if cfg.get('helper',{}).get('sdflashattention') is not False:
        raise ImageBudgetError('The GPU budget is validated for the selected NoFA image context only.','sdflashattention','unsupported_gpu_budget_profile')
    for field in ('batch_size','n_iter','frames'):
        if local.get(field,1)!=1:raise ImageBudgetError('The validated image budget supports one image at a time.',field,'unsupported_gpu_budget_profile')
    if (local.get('extra_images') or local.get('ref_images') or local.get('video_start_frame') or local.get('video_end_frame') or local.get('send_as_refimg')):
        raise ImageBudgetError('Reference-image/video conditioning is outside the validated caption budget.','extra_images','unsupported_reference_budget')
    if local.get('lora') or local.get('lora_weights'):
        raise ImageBudgetError('Runtime LoRA requests are outside the validated static-profile counter.','lora','unsupported_lora_budget')
    positive=local.get('prompt','high quality');forced=local.get('add_sd_prompt','')
    if not isinstance(positive,str) or not isinstance(forced,str):raise ImageBudgetError('prompt and add_sd_prompt must be strings.')
    if '<lora:' in (positive+forced).lower():
        raise ImageBudgetError('Runtime LoRA prompt directives are not yet parity-validated; the prompt was not changed.','prompt','unsupported_lora_budget')
    width,height=local.get('width'),local.get('height')
    if any(type(value)is not int or value<256 or value>2048 or value%16 for value in (width,height)):
        raise ImageBudgetError('Resolved aligned16 dimensions256..2048 are required.','size','invalid_budget_geometry')
    if operation=='generation' and (local.get('init_images') or local.get('mask')):
        raise ImageBudgetError('Prepared image/mask input must use the edit budget path.','init_images','prepared_image_geometry_required')
    if local.get('enable_hr'):
        raise ImageBudgetError('Automatic high-resolution passes are outside the selected no-autoSR image profile.','enable_hr','unsupported_gpu_budget_profile')
    try:count=_counter(root,assets).native_request(local)
    except ImageBudgetError:raise
    except (ValueError,TypeError,UnicodeError) as error:raise ImageBudgetError('The exact Native prompt cannot be counted: '+str(error),'prompt','unsupported_prompt_budget') from error
    except Exception as error:raise ImageBudgetError('The exact SD tokenizer failed; Native generation was not attempted.','imageBudget','image_tokenizer_unavailable',503) from error
    caption=count['caption_tokens'];padded=count['padded_caption_tokens']
    initial_score,padded_image=score_bytes(width,height,padded)
    report=dict(policy='zimage_noFA_Native_Qwen',selectedDimensions=[width,height],actualDimensions=[width,height],
        captionTokens=caption,paddedTokens=padded,scoreBytes=initial_score,limitBytes=TENSOR_LIMIT_BYTES,
        paddedImageTokens=padded_image,fallbackReason=None,resized=False,operation=operation,imagePrepared=bool(image_prepared),
        NativeExistingPromptByteCut=len(positive.encode('utf-8'))>3000,
        promptChanged=False,stepsChanged=False,cacheChanged=False,modelChanged=False,
        limitation='Single F32 attention-tensor bound, not totalVRAM or weight residency; text encoding remains onCPU, parameter placement is verified separately.')
    if initial_score<=TENSOR_LIMIT_BYTES:return ImageBudgetDecision(local,cfg,report)
    if operation=='edit' or image_prepared:
        raise ImageBudgetError('This prepared image/mask geometry exceeds the GPU caption budget. Use a shorter prompt or explicitly prepare a smaller edit; no automatic mask/image resize was applied.',
                               'prompt','prepared_edit_gpu_budget_exceeded',422,report)
    if not (width*3==height*2 or width*2==height*3):
        raise ImageBudgetError('Generation fallback requires the resolved exact author2:3/3:2 geometry.','size','invalid_budget_geometry',400,report)
    proxy=cfg.get('proxy',{});alignment=proxy.get('native_alignment',16)
    if type(alignment)is not int or alignment not in (16,32,64):raise ImageBudgetError('Invalid Native alignment.','native_alignment')
    budget=min(width*height,int(proxy.get('native_pixel_budget',width*height)))
    edge=min(max(width,height),int(proxy.get('max_native_edge',max(width,height))))
    landscape=width>height;best=None
    for unit in range(alignment,edge//3+1,alignment):
        short,long=2*unit,3*unit
        if short<256 or short*long>budget:continue
        candidate=(long,short) if landscape else (short,long)
        score,padded_img=score_bytes(*candidate,padded)
        if score<=TENSOR_LIMIT_BYTES:best=(candidate,score,padded_img)
    if best is None:
        report['fallbackReason']='caption_exceeds_all_supported_native_resolutions'
        raise ImageBudgetError('The caption exceeds the GPU attention budget even at the minimum supported image size. The prompt, model and sampling parameters were not changed.',
                               'prompt','image_gpu_budget_exceeded',422,report)
    actual,score,padded_img=best
    local.update(width=actual[0],height=actual[1])
    cfg.setdefault('defaults',{}).update(width=actual[0],height=actual[1])
    cfg.setdefault('proxy',{}).update(native_pixel_budget=actual[0]*actual[1],max_native_edge=max(actual),fixed_native_resolution=True)
    report.update(actualDimensions=list(actual),scoreBytes=score,paddedImageTokens=padded_img,
                  fallbackReason='caption_requires_smaller_native_resolution',resized=True)
    return ImageBudgetDecision(local,cfg,report)

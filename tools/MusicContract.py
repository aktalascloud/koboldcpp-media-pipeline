"""YuE2 request contract; the caller's LLM composes lyrics, Native renders music."""
from __future__ import annotations
import math

class MusicRequestError(ValueError):
    status=422
    def __init__(self,message,code='invalid_music_request'):
        super().__init__(message);self.body={'error':{'code':code,'message':message}}

def music_family(config):
    return config.get('proxy',{}).get('music',{}).get('family','ace-step')

def capabilities(config):
    family=music_family(config)
    return dict(family=family,backend='KoboldCpp Native',composer='client-selected LLM',
        generate_endpoint='/api/extra/music/generate',prepare_endpoint='/api/extra/music/prepare',
        output_format='mp3',stereo=True,default_steps=8,
        duration_control='semantic_max_tokens / 25 is an approximate upper bound' if family=='yue2' else 'duration',
        locally_tested_seconds=32 if family=='yue2' else None,
        russian_vocals='user-confirmed on the saved short trial' if family=='yue2' else 'previous configuration',
        official_yue2_language_tags=['Chinese','English'] if family=='yue2' else None)

def prepare_music(payload,config):
    if music_family(config)!='yue2':return dict(payload)
    result=dict(payload)
    obsolete={'inference_steps','shift','vocal_language','gen_codes','rewrite_caption','music_reference_audio_data'}
    found=obsolete.intersection(result)
    if found:raise MusicRequestError('YuE2 does not accept ACE-Step fields: '+', '.join(sorted(found))+'. Use lyrics/style, num_inference_steps and semantic_max_tokens.')
    allowed={'lyrics','style','caption','cot','seed','num_inference_steps','guidance_scale','cfg_scale','use_mp3','response_format','stereo','duration',
             'semantic_prefix','abc','genkey'}
    for prefix in ('semantic','abc'):
        allowed.update(prefix+'_'+s for s in ('temperature','top_p','top_k','repetition_penalty','penalty_window','min_tokens','max_tokens'))
    unknown=set(result)-allowed
    if unknown:raise MusicRequestError('Unsupported YuE2 fields: '+', '.join(sorted(unknown)))
    if 'style' in result and 'caption' in result and result['style']!=result['caption']:raise MusicRequestError('style and caption conflict.')
    if 'caption' in result:result['style']=result.pop('caption')
    if not isinstance(result.get('style'),str) or not result['style'].strip():raise MusicRequestError('A nonempty style string is required.')
    if not isinstance(result.get('lyrics',''),str):raise MusicRequestError('lyrics must be a string.')
    result.setdefault('lyrics','');result.setdefault('cot','off');result.setdefault('num_inference_steps',8)
    if result['cot'] not in ('off','melody','full'):raise MusicRequestError('cot must be off, melody or full.')
    if result['cot']=='melody' and not result.get('abc'):raise MusicRequestError('cot=melody requires an explicit ABC score.')
    if 'guidance_scale' in result and 'cfg_scale' in result and result['guidance_scale']!=result['cfg_scale']:raise MusicRequestError('guidance_scale and cfg_scale conflict.')
    if 'cfg_scale' in result:result['guidance_scale']=result.pop('cfg_scale')
    result.setdefault('guidance_scale',1.01 if result['cot']=='off' else 1.)
    duration=result.pop('duration',None)
    if duration is not None:
        if isinstance(duration,bool) or not isinstance(duration,(int,float)) or not math.isfinite(duration) or not 1<=duration<=360:raise MusicRequestError('duration must be 1..360 seconds; it is an approximate cap, not an exact duration.')
        tokens=math.ceil(duration*25)
        if 'semantic_max_tokens' in result and result['semantic_max_tokens']!=tokens:raise MusicRequestError('duration and semantic_max_tokens conflict.')
        result['semantic_max_tokens']=tokens
    result.setdefault('semantic_max_tokens',750)
    result.setdefault('semantic_min_tokens',min(200,result['semantic_max_tokens']) if isinstance(result['semantic_max_tokens'],int) else 0)
    for key,value in result.items():
        if isinstance(value,float) and not math.isfinite(value):raise MusicRequestError('Non-finite music parameter: '+key)
        if key.endswith(('_min_tokens','_max_tokens','_top_k','_penalty_window')) or key in ('num_inference_steps','seed'):
            if isinstance(value,bool) or not isinstance(value,int) or value<0:raise MusicRequestError(key+' must be a nonnegative integer.')
    if not 1<=result['num_inference_steps']<=64:raise MusicRequestError('num_inference_steps must be 1..64.')
    if not 1<=result['semantic_max_tokens']<=9000 or result['semantic_min_tokens']>result['semantic_max_tokens']:raise MusicRequestError('Invalid semantic token range (maximum 9000).')
    if isinstance(result['guidance_scale'],bool) or not isinstance(result['guidance_scale'],(int,float)) or not 0<=result['guidance_scale']<=20:raise MusicRequestError('guidance_scale must be 0..20.')
    if 'seed' in result and result['seed']>=2**63:raise MusicRequestError('seed must be below 2**63.')
    for prefix in ('semantic','abc'):
        for suffix,minimum,maximum in [('temperature',0,5),('top_p',0,1),('repetition_penalty',0,None)]:
            key=prefix+'_'+suffix
            if key not in result:continue
            value=result[key]
            if isinstance(value,bool) or not isinstance(value,(float,int)) or value<minimum or (suffix!='temperature' and value==0) or (maximum is not None and value>maximum):raise MusicRequestError('Invalid sampling parameter: '+key)
        for suffix in ('top_k','penalty_window'):
            key=prefix+'_'+suffix
            if key in result and result[key]<1:raise MusicRequestError(key+' must be positive.')
        low,high=prefix+'_min_tokens',prefix+'_max_tokens'
        if low in result and high in result and result[low]>result[high]:raise MusicRequestError('Invalid '+prefix+' token range.')
    if isinstance(result.get('abc',''),str) is False:raise MusicRequestError('abc must be a string.')
    if 'semantic_prefix' in result:
        prefix=result['semantic_prefix']
        if not isinstance(prefix,list) or len(prefix)>result['semantic_max_tokens'] or any(isinstance(x,bool) or not isinstance(x,int) or not 0<=x<32768 for x in prefix):raise MusicRequestError('semantic_prefix must be codec indices 0..32767 within the token budget.')
    result.update(use_mp3=True,response_format='mp3',stereo=True)
    result.pop('genkey',None)
    return result

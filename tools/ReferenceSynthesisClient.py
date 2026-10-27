"""Provider/model-agnostic OWUI bridge. vision_call is supplied by the caller.

One vision call analyzes all source images and composes a final caption. No
provider URL, API key, model name, downloads or inference dependency is fixed.
"""
import base64,hashlib,json,inspect
PROFILE_FIELDS=('steps','cfg_scale','sampler_name','scheduler','eta','flow_shift','clip_skip','cache_mode','cache_options')

async def build_synthesis_payload(sources,user_request,vision_call,*,analysis_prompt,analysis_model=None,generation_options=None):
    if not isinstance(analysis_prompt,str) or not analysis_prompt:raise ValueError('Fetch vision_system_prompt from the synthesis schema endpoint.')
    if not isinstance(sources,list) or not 2<=len(sources)<=4:raise ValueError('Provide2–4 source images with explicit roles.')
    if sum(s.get('role')=='base' for s in sources)!=1:raise ValueError('Exactly one base image is required.')
    if any(s.get('role') not in ('base','reference') for s in sources):raise ValueError('Invalid source role.')
    bindings=[];content=[dict(type='text',text='User request: '+user_request)]
    for index,source in enumerate(sources):
        raw=source['image_bytes'];sid=source.get('id','image'+str(index+1));role=source['role'];uses=source['use_for']
        if not isinstance(raw,bytes) or not raw or len(raw)>32*1024*1024:raise ValueError('Bounded original image bytes required.')
        mime='image/png' if raw.startswith(b'\x89PNG\r\n\x1a\n') else 'image/jpeg' if raw.startswith(b'\xff\xd8') else 'image/webp' if raw[:4]==b'RIFF' and raw[8:12]==b'WEBP' else None
        if mime is None:raise ValueError('PNG/JPEG/WebP required.')
        binding=dict(id=sid,role=role,image_sha256=hashlib.sha256(raw).hexdigest(),use_for=uses);bindings.append(binding)
        content.extend([dict(type='text',text=json.dumps(binding)),dict(type='image_url',image_url=dict(url='data:'+mime+';base64,'+base64.b64encode(raw).decode()))])
    messages=[dict(role='system',content=analysis_prompt),dict(role='user',content=content)]
    result=vision_call(messages)
    if inspect.isawaitable(result):result=await result
    if isinstance(result,str):
        text=result.strip()
        if text.startswith('```') and text.endswith('```'):text='\n'.join(text.splitlines()[1:-1])
        result=json.loads(text)
    if not isinstance(result,dict) or not isinstance(result.get('sources'),list):raise ValueError('Vision provider must return the requested structured analysis; no fallback synthesis.')
    described={r['id']:r for r in result['sources']}
    if len(result['sources'])!=len(bindings) or len({b['id'] for b in bindings})!=len(bindings) or set(described)!={b['id'] for b in bindings}:raise ValueError('Vision response does not match all source IDs exactly once.')
    final=[]
    for binding in bindings:
        description=described[binding['id']].get('description')
        if not isinstance(description,str) or not description.strip():raise ValueError('Missing visual analysis; synthesis not started.')
        # Role/hash/request come from trusted caller inputs, not model guesses.
        final.append({**binding,'description':description})
    options=generation_options or {}
    permitted={'model','width','height','size','kcpp_quality','enable_hr','seed','n','response_format','output_format','background','quality',*PROFILE_FIELDS}
    if set(options)-permitted:raise ValueError('Unsupported generation options.')
    return {**options,'operation':'reference_synthesis','sources':final,'user_request':user_request,'generation_prompt':result.get('generation_prompt'),'analysis_model':analysis_model}

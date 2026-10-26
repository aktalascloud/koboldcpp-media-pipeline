"""Bounded OpenAI image-edit input translated to the existing A1111 img2img path.

Only Pillow and the Python standard library are used. This module never fetches
image URLs, loads an inference model, writes uploaded files, or changes settings.
"""
import base64
import binascii
from email import policy
from email.parser import BytesParser
import io
import json
import math
import re

from PIL import Image, ImageOps, UnidentifiedImageError
from Resolution import choose_resolution

EDIT_PATHS = ('/v1/images/edits', '/images/edits')
MAX_IMAGE_PIXELS = 67_108_864
MAX_FORM_PARTS = 24
REFERENCE_FIELDS=('reference_images','reference_images[]','reference_image','reference_image[]','references','extra_images','ref_images','send_as_refimg')
TARGET_FIELDS=('image','image[]','target_image')
CAPABILITIES_PATH='/v1/images/capabilities'


class ImageEditError(ValueError):
    def __init__(self, message, param=None, code='invalid_request', status=400):
        super().__init__(message)
        self.status = status
        self.body = {'error': {'message': message, 'type': 'invalid_request_error', 'param': param, 'code': code}}


def fail(message, param=None, code='invalid_request', status=400):
    raise ImageEditError(message, param, code, status)


def unsupported(message,param,code,**details):
    error=ImageEditError(message,param,code,422)
    error.body['error'].update(capabilities_url=CAPABILITIES_PATH,**details)
    raise error


def model_contract(config,requested=None):
    checkpoint=str(config['helper'].get('sdmodel','')).replace('\\','/').rsplit('/',1)[-1]
    aliases=['default','koboldcpp','kobold-moss','kobold-moss-img2img',checkpoint,checkpoint.rsplit('.',1)[0]]
    if requested is not None and (not isinstance(requested,str) or requested not in aliases):
        unsupported('The image model is server-managed; the requested model is not available.','model','unsupported_image_model',supported_models=aliases)
    return dict(requested=requested,resolved=checkpoint,server_managed=True,aliases=aliases)


def image_capabilities(config):
    return dict(schema_version=2,model_family=config['proxy'].get('image_model_family','moss'),model=model_contract(config),
        operations=dict(txt2img=dict(supported=True,model_alias='kobold-moss',endpoints=['/sdapi/v1/txt2img','/v1/images/generations']),img2img=dict(supported=True,model_alias='kobold-moss-img2img',endpoints=['/sdapi/v1/img2img','/v1/images/edits'],semantics='whole_frame_redraw',prompt_semantics='complete_descriptive_caption',target_images=dict(min=1,max=1),reference_images=dict(max=0),multiple_images=False,masks=False,instruction_edit=False,semantic_success_evaluated=False,default_strength=config['proxy'].get('image_edit_denoising_strength',.6),strength_range=[.05,1.0],steps_range=[1,9],cache_mode='disabled',automatic_upscale=False),instruction_edit=dict(supported=False),reference_guided_edit=dict(supported=False),inpaint=dict(supported=False),upscale=dict(supported=True,scale=config['proxy']['upscaler'].get('output_scale',4))),
        inputs=dict(target_fields=list(TARGET_FIELDS),reference_fields=list(REFERENCE_FIELDS),formats=['png','jpeg','webp'],remote_urls=False,min_dimension=256,max_decoded_pixels=MAX_IMAGE_PIXELS,alpha_masks=False,animated_images=False,max_multipart_parts=MAX_FORM_PARTS,max_upload_bytes=int(config['helper'].get('maxrequestsize',32))*1024*1024),
        openai_edits_default_operation='instruction_edit',requires_explicit_redraw_operation=True,redraw_model_alias='kobold-moss-img2img',capabilities_url=CAPABILITIES_PATH)


def reject_references(fields):
    for name in REFERENCE_FIELDS:
        if fields.get(name):unsupported('Reference conditioning is unsupported by this model/backend; no references were used.',name,'reference_images_unsupported',max_reference_images=0)


def validate_edit_contract(fields,config,*,default_operation='instruction_edit'):
    reject_references(fields)
    operation=fields.get('operation')
    if operation is None:operation=default_operation
    if operation=='instruction_edit' or fields.get('instruction'):
        unsupported('This checkpoint has no instruction-edit mode. Explicit img2img is whole-frame redraw from a descriptive caption, not a precise editing command.','operation','instruction_edit_unsupported',requested_operation=operation,supported_operations=['img2img'])
    if operation!='img2img':
        unsupported('This edit operation is unsupported by the configured checkpoint/backend.','operation','unsupported_image_operation',requested_operation=operation,supported_operations=['img2img'])
    if fields.get('mask') is not None:
        unsupported('Masked editing is not supported by this MOSS proxy.','mask','mask_unsupported')
    if fields.get('enable_hr') is True:
        unsupported('Automatic upscale of an edit is unsupported; upscale the returned PNG through the separate API.','enable_hr','edit_upscale_unsupported')
    if fields.get('quality') not in (None,'','auto'):
        unsupported('quality is not an editing control; select kcpp_quality for the geometry budget.','quality','edit_quality_unsupported')
    return model_contract(config,fields.get('model'))


def validate_generation_contract(fields,config):
    reject_references(fields)
    if fields.get('model')=='kobold-moss-img2img':
        unsupported('Use the edits/img2img endpoint for the redraw model alias.','model','target_requires_img2img')
    if fields.get('operation') not in (None,'txt2img'):
        unsupported('Use a supported image operation and its endpoint.','operation','unsupported_image_operation',supported_operations=['txt2img'])
    if any(fields.get(k) for k in (*TARGET_FIELDS,'init_images','mask')):
        unsupported('Image inputs must use the explicit img2img redraw endpoint.','image','target_requires_img2img')
    if fields.get('override_settings'):
        unsupported('Runtime checkpoint overrides are unsupported; the server owns the model/profile.','override_settings','runtime_override_unsupported')
    if integer(fields.get('n',1),'n')!=1:
        unsupported('Only one output is supported.','n','multiple_outputs_unsupported',max_output_images=1)
    if fields.get('response_format') not in (None,'','b64_json'):
        unsupported('This proxy returns base64 PNG, not hosted result URLs.','response_format','response_format_unsupported')
    if fields.get('output_format') not in (None,'','png'):
        unsupported('This image pipeline returns PNG.','output_format','output_format_unsupported')
    if fields.get('background') not in (None,'','auto','opaque'):
        unsupported('Transparent-background generation is unsupported.','background','background_unsupported')
    if fields.get('quality') not in (None,'','auto'):
        unsupported('Use kcpp_quality for the actual profile; OpenAI quality presets are unsupported.','quality','image_quality_unsupported')
    return model_contract(config,fields.get('model'))


def integer(value, param):
    if isinstance(value, bool) or not re.fullmatch(r'[+-]?\d+', str(value).strip()):
        fail(param + ' must be an integer.', param)
    return int(value)


def parse_fields(body, content_type):
    if '\r' in content_type or '\n' in content_type:
        fail('Invalid Content-Type header.', code='invalid_content_type')
    media = content_type.split(';', 1)[0].strip().lower()
    if media == 'application/json':
        try:
            fields = json.loads(body.decode('utf-8'))
        except (UnicodeError, ValueError):
            fail('Expected a valid UTF-8 JSON object.', code='invalid_json')
        if not isinstance(fields, dict):
            fail('Expected a JSON object.', code='invalid_json')
        reject_references(fields)
        images = []
        for name in TARGET_FIELDS:
            value = fields.pop(name, None)
            if value is not None:
                images.extend(value if isinstance(value, list) else [value])
        if len(images)>1:
            unsupported('Exactly one target is supported; multiple images are not treated as references.','image','multiple_images_unsupported',max_target_images=1,max_reference_images=0)
        if len(images) != 1:
            fail('Provide exactly one image; multiple-image edits are unsupported.', 'image', 'single_image_required')
        value = images[0]
        if not isinstance(value, str):
            fail('JSON image must be base64 or an image data URI.', 'image')
        value = value.strip()
        if value.lower().startswith(('http:', 'https:', 'file:')):
            fail('Image URLs are unsupported; upload the original image bytes.', 'image', 'image_url_unsupported')
        if value.startswith('data:'):
            match = re.fullmatch(r'data:image/(?:png|jpe?g|webp);base64,(.+)', value, re.I | re.S)
            if not match:
                fail('Expected a PNG, JPEG or WebP base64 data URI.', 'image')
            value = match.group(1)
        try:
            image = base64.b64decode(value, validate=True)
        except (ValueError, binascii.Error):
            fail('Invalid base64 image.', 'image')
        return fields, image
    if media != 'multipart/form-data':
        fail('Use multipart/form-data or application/json.', code='unsupported_content_type', status=415)
    try:
        message = BytesParser(policy=policy.default).parsebytes(
            b'MIME-Version: 1.0\r\nContent-Type: ' + content_type.encode('ascii') + b'\r\n\r\n' + body)
    except (UnicodeError, ValueError):
        fail('Malformed multipart request.', code='invalid_multipart')
    boundary = message.get_boundary()
    if not boundary or len(boundary) > 200 or not message.is_multipart() or message.defects:
        fail('Missing or malformed multipart boundary.', code='invalid_multipart')
    fields, images = {}, []
    for index, part in enumerate(message.iter_parts()):
        if index >= MAX_FORM_PARTS:
            fail('Too many multipart fields.', code='too_many_fields', status=413)
        if part.is_multipart() or part.defects or part.get_content_disposition() != 'form-data':
            fail('Malformed multipart field.', code='invalid_multipart')
        name = part.get_param('name', header='content-disposition')
        if not name or len(name) > 128:
            fail('Multipart field has no name.', code='invalid_multipart')
        data = part.get_payload(decode=True)
        if data is None:
            fail('Invalid multipart field data.', name, 'invalid_multipart')
        if name in REFERENCE_FIELDS and (data or part.get_filename() is not None):
            unsupported('Reference conditioning is unsupported; no references were used.',name,'reference_images_unsupported',max_reference_images=0)
        if name in TARGET_FIELDS:
            images.append(data)
            continue
        if name == 'mask':
            fail('Masked edits are not enabled for this image pipeline.', 'mask', 'mask_unsupported', 422)
        if part.get_filename() is not None:
            fail('Unexpected uploaded file field: ' + name, name)
        if name in fields:
            fail('Duplicate multipart field: ' + name, name)
        try:
            fields[name] = data.decode('utf-8')
        except UnicodeError:
            fail('Text fields must be UTF-8.', name)
    if len(images)>1:
        unsupported('Exactly one target image is supported.','image','multiple_images_unsupported',max_target_images=1,max_reference_images=0)
    if len(images) != 1:
        fail('Provide exactly one image; multiple-image edits are unsupported.', 'image', 'single_image_required')
    return fields, images[0]


def load_image(raw):
    try:
        with Image.open(io.BytesIO(raw)) as source:
            if source.format not in ('PNG', 'JPEG', 'WEBP'):
                fail('Only PNG, JPEG and WebP images are supported.', 'image', 'unsupported_image_format', 415)
            if source.width * source.height > MAX_IMAGE_PIXELS:
                fail('Input image exceeds the 64-megapixel decoding limit.', 'image', 'image_too_large', 413)
            if min(source.size) < 256:
                fail('Both source-image dimensions must be at least 256 pixels.', 'image', 'image_too_small')
            if getattr(source, 'n_frames', 1) != 1:
                fail('Animated or multiple-frame uploads are unsupported.', 'image')
            original_size = list(source.size)
            orientation = source.getexif().get(274, 1)
            image = ImageOps.exif_transpose(source).convert('RGBA')
            if image.getchannel('A').getextrema()[0] < 255:
                fail('Transparent-image masks are unsupported; provide an opaque source image.', 'image', 'mask_unsupported', 422)
            return image.convert('RGB'), dict(upload_dimensions=original_size, exif_orientation_applied=orientation not in (None, 1))
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, ValueError) as error:
        if isinstance(error, ImageEditError):
            raise
        fail('The image cannot be decoded as PNG, JPEG or WebP.', 'image', 'invalid_image')


def fit_with_edge_padding(image, target):
    # Uniform fit preserves object geometry. Edge replication avoids invented
    # colored borders when alignment requires a slightly different canvas ratio.
    scale = min(1.0, target[0] / image.width, target[1] / image.height)
    size = (max(1, min(target[0], round(image.width * scale))),
            max(1, min(target[1], round(image.height * scale))))
    resized = image.resize(size, Image.Resampling.LANCZOS) if size != image.size else image.copy()
    left, top = (target[0] - size[0]) // 2, (target[1] - size[1]) // 2
    canvas = Image.new('RGB', target)
    canvas.paste(resized, (left, top))
    if left:
        canvas.paste(resized.crop((0, 0, 1, size[1])).resize((left, size[1])), (0, top))
    right = target[0] - left - size[0]
    if right:
        canvas.paste(resized.crop((size[0]-1, 0, size[0], size[1])).resize((right, size[1])), (left+size[0], top))
    if top:
        canvas.paste(canvas.crop((0, top, target[0], top+1)).resize((target[0], top)), (0, 0))
    bottom = target[1] - top - size[1]
    if bottom:
        canvas.paste(canvas.crop((0, top+size[1]-1, target[0], top+size[1])).resize((target[0], bottom)), (0, top+size[1]))
    return canvas, dict(source_dimensions=list(image.size), native_dimensions=list(target),
                        content_dimensions=list(size), content_box=[left, top, left+size[0], top+size[1]],
                        scale=scale, resize_mode='uniform_fit_edge_padding', crop=False, stretch=False)


def prepare_edit(body, content_type, config, mode_resolver=None):
    maximum = int(config['helper'].get('maxrequestsize', 32)) * 1024 * 1024
    if len(body) > maximum:
        fail('Request exceeds the configured size limit.', code='request_too_large', status=413)
    fields, raw = parse_fields(body, content_type)
    model=validate_edit_contract(fields,config)
    fields.pop('mask',None)  # Only None reaches this point; real masks were rejected.
    allowed={'operation','model','prompt','negative_prompt','n','size','width','height','background','output_format','response_format','steps','denoising_strength','seed','genkey','enable_hr','kcpp_quality','quality',*REFERENCE_FIELDS}
    unknown=sorted(set(fields)-allowed)
    if unknown:unsupported('Unsupported edit parameter; it was not silently ignored.',unknown[0],'unsupported_edit_parameter')
    request_mode = mode_resolver(fields, config, 'edit') if mode_resolver else None
    if request_mode is not None:
        fields, config = request_mode.payload, request_mode.config
    if 'mask' in fields:
        fail('Masked edits are not enabled for this MOSS pipeline.', 'mask', 'mask_unsupported', 422)
    prompt = fields.get('prompt')
    if not isinstance(prompt, str) or not prompt.strip():
        fail('A nonempty prompt is required.', 'prompt')
    if len(prompt.encode('utf-8')) > 2998:
        fail('Prompt exceeds 2998 UTF-8 bytes; shorten it before editing.', 'prompt', 'prompt_too_long')
    response_format = fields.get('response_format') or 'b64_json'
    if response_format != 'b64_json':
        fail('Use response_format=b64_json; this proxy does not host result URLs.', 'response_format', 'response_format_unsupported')
    if integer(fields.get('n', 1), 'n') != 1:
        unsupported('Only one output image is supported.','n','multiple_outputs_unsupported',max_output_images=1)
    if fields.get('background') not in (None, '', 'auto', 'opaque'):
        fail('This photographic pipeline returns opaque PNG images.', 'background', 'background_unsupported')
    if fields.get('output_format') not in (None, '', 'png'):
        fail('This pipeline returns PNG; use output_format=png.', 'output_format')
    steps = integer(fields.get('steps', config['defaults'].get('steps', 8)), 'steps')
    if not 1 <= steps <= 9:
        fail('steps must be between 1 and 9.', 'steps')
    strength_value = fields.get('denoising_strength', config['proxy'].get('image_edit_denoising_strength', 0.4))
    if isinstance(strength_value, bool):
        fail('denoising_strength must be a number from 0.05 to 1.', 'denoising_strength')
    try:
        strength = float(strength_value)
    except (TypeError, ValueError):
        fail('denoising_strength must be a number from 0.05 to 1.', 'denoising_strength')
    if not math.isfinite(strength) or not 0.05 <= strength <= 1:
        fail('denoising_strength must be a number from 0.05 to 1.', 'denoising_strength')
    seed = integer(fields.get('seed', -1), 'seed')
    if not -1 <= seed <= 2147483647:
        fail('seed must be -1 or a nonnegative 32-bit signed integer.', 'seed')
    image, orientation = load_image(raw)
    budget = min(int(config['proxy'].get('native_pixel_budget', config['defaults'].get('width', 704) * config['defaults'].get('height', 960))), image.width * image.height)
    max_edge = min(int(config['proxy'].get('max_native_edge', 1280)), max(image.size))
    requested_size = fields.get('size') or 'auto'
    if 'width' in fields or 'height' in fields:
        if 'width' not in fields or 'height' not in fields:fail('Provide width and height together.','size','invalid_dimensions')
        if requested_size!='auto':fail('Use size or width/height, not both.','size','ambiguous_size')
        requested_size=str(integer(fields['width'],'width'))+'x'+str(integer(fields['height'],'height'))
    if requested_size != 'auto':
        match = re.fullmatch(r'(\d+)x(\d+)', str(requested_size).lower())
        if not match:
            fail('size must be auto or WIDTHxHEIGHT.', 'size')
        requested = tuple(int(value) for value in match.groups())
        if not all(256 <= value <= 16384 for value in requested):
            fail('Requested size dimensions must be between 256 and 16384.', 'size')
        budget = min(budget, requested[0] * requested[1])
        max_edge = min(max_edge, max(requested))
    alignment = int(config['proxy'].get('native_alignment', 32))
    try:
        target = choose_resolution(image.width, image.height, budget, max_edge, alignment=alignment)
    except (ValueError, TypeError):
        fail('Image dimensions cannot fit the configured native budget.', 'size')
    prepared, geometry = fit_with_edge_padding(image, target)
    encoded = io.BytesIO()
    prepared.save(encoded, format='PNG')  # Deliberately drop old face-pass markers.
    payload = dict(prompt=prompt, negative_prompt=str(fields.get('negative_prompt') or ''),
                   init_images=[base64.b64encode(encoded.getvalue()).decode('ascii')],
                   width=target[0], height=target[1], denoising_strength=strength, steps=steps,
                   seed=seed, batch_size=1, n_iter=1, enable_hr=False, cache_mode='disabled', cache_options='')
    if fields.get('genkey'):
        payload['genkey'] = str(fields['genkey'])[:128]
    context = dict(operation='img2img', response_format='b64_json', steps=steps,
                   denoising_strength=strength, requested_size=requested_size,
                   requested_size_policy='area cap; input aspect has priority', geometry={**orientation, **geometry},
                   semantics='whole_frame_redraw',model=model,target_images=1,reference_images=0,multiple_images_supported=False,instruction_edit_supported=False,semantic_success_evaluated=False,
                   auto_upscale=False, cache_mode='disabled', masked_edit_supported=False,
                   limitation='Whole-frame img2img; this model is not an instruction-edit model and cannot guarantee unchanged source pixels or identity.')
    if request_mode is not None:
        context['_resolved_image_mode'] = request_mode  # Handler removes this private object before JSON.
    return payload, context


def prepare_a1111_edit(payload,config):
    """A1111 explicitly means redraw; share upload/strength/geometry validation."""
    model=validate_edit_contract(payload,config,default_operation='img2img')
    images=payload.get('init_images')
    if not isinstance(images,list) or len(images)!=1:
        unsupported('Exactly one init_images target is supported.','init_images','multiple_images_unsupported',max_target_images=1,max_reference_images=0)
    for field in ['batch_size','n_iter']:
        if integer(payload.get(field,1),field)!=1:unsupported('Only one output is supported.',field,'multiple_outputs_unsupported',max_output_images=1)
    if payload.get('resize_mode',0)!=0:unsupported('Only uniform fit with edge padding is supported.','resize_mode','unsupported_resize_mode')
    sampling=('cfg_scale','sampler_name','scheduler','flow_shift','clip_skip','eta','cache_mode','cache_options')
    allowed={'init_images','operation','model','mask','instruction','prompt','negative_prompt','n','size','width','height','background','output_format','response_format','steps','denoising_strength','seed','genkey','enable_hr','kcpp_quality','quality','batch_size','n_iter','resize_mode','kcpp_detailer',*sampling,*REFERENCE_FIELDS}
    unknown=set(payload)-allowed
    if unknown:unsupported('Unsupported img2img parameter; it was not ignored.',sorted(unknown)[0],'unsupported_edit_parameter')
    fields={k:v for k,v in payload.items() if k not in {'init_images','batch_size','n_iter','resize_mode','kcpp_detailer',*sampling}}
    fields.update(operation='img2img',image=images[0])
    prepared,context=prepare_edit(json.dumps(fields).encode('utf-8'),'application/json',config)
    for field in sampling:
        if field in payload and field not in ('cache_mode','cache_options'):prepared[field]=payload[field]
    if 'kcpp_detailer' in payload:prepared['kcpp_detailer']=payload['kcpp_detailer']
    prepared['resize_mode']=0;context.update(model=model,requested_sampling={k:payload[k] for k in sampling if k in payload},sampling_profile_enforced=True)
    return prepared,context

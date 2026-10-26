"""Pure request-local photo modes; no model, network or process operations.

High uses exact author2:3/3:2; Normal may use the closest Native grid within1%. Edits retain source aspect;
image and mask share geometry. Normal's150s target excludes optional SR.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
import re

from Resolution import choose_resolution

FIELD = 'kcpp_quality'
DEFAULT_MODES = {
    'normal': dict(native_profile='photo-normal', default_width=592, default_height=896,
                   native_pixel_budget=530432, max_native_edge=896, native_alignment=16,
                   generation_face_target_seconds=150, provisional=False, auto_upscale=False),
    'quality': dict(native_profile='photo-quality', default_width=1152, default_height=768,
                    native_pixel_budget=884736, max_native_edge=1152, native_alignment=16,
                    generation_face_target_seconds=None, provisional=False, auto_upscale=True),
}
MODE_KEYS = set(DEFAULT_MODES['normal']) | {'fallback_reason'}


class ImageModeError(ValueError):
    def __init__(self, message, field=FIELD, code='invalid_image_mode', status=400):
        super().__init__(message)
        self.status = status
        self.body = dict(error=dict(message=message, type='invalid_request_error', param=field, code=code))


@dataclass
class ResolvedImageMode:
    payload: dict
    config: dict
    mode: str
    native_profile: str
    metadata: dict

    @property
    def nativeProfile(self):
        return self.native_profile


def default_image_modes():
    return copy.deepcopy(DEFAULT_MODES)


def _integer(value, field, minimum=1, maximum=16384, status=400):
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ImageModeError('A positive integer is required.', field, 'invalid_dimensions', status)
    if isinstance(value, str) and not re.fullmatch(r'[0-9]+', value):
        raise ImageModeError('A positive integer is required.', field, 'invalid_dimensions', status)
    value = int(value)
    if not minimum <= value <= maximum:
        raise ImageModeError(f'Expected {minimum}..{maximum}.', field, 'invalid_dimensions', status)
    return value


def _mode_spec(config, mode):
    table = config.get('proxy', {}).get('image_modes', {})
    if not isinstance(table, dict) or set(table) - set(DEFAULT_MODES):
        raise ImageModeError('Invalid image_modes configuration.', 'image_modes', 'invalid_mode_config', 500)
    override = table.get(mode, {})
    if not isinstance(override, dict) or set(override) - MODE_KEYS:
        raise ImageModeError('Unknown mode configuration field.', 'image_modes', 'invalid_mode_config', 500)
    spec = {**DEFAULT_MODES[mode], **copy.deepcopy(override)}
    if spec['native_profile'] != 'photo-' + mode:
        raise ImageModeError('Mode must map to its approved photo profile.', 'native_profile', 'invalid_mode_config', 500)
    for key in ('default_width', 'default_height', 'max_native_edge'):
        spec[key] = _integer(spec[key], key, 256, 4096, 500)
    spec['native_pixel_budget'] = _integer(spec['native_pixel_budget'], 'native_pixel_budget', 1, 2048**2, 500)
    alignment = spec['native_alignment']
    if type(alignment) is not int or alignment not in (16, 32, 64):
        raise ImageModeError('Alignment must be16/32/64.', 'native_alignment', 'invalid_mode_config', 500)
    w, h = spec['default_width'], spec['default_height']
    ratio_ok = w*3 == h*2 or w*2 == h*3
    ratio_error = abs(min(w,h)*3-max(w,h)*2)/(max(w,h)*2)
    if (not ratio_ok and not (mode == 'normal' and ratio_error <= .01)) or w % alignment or h % alignment:
        raise ImageModeError('Photo geometry must meet its mode aspect and Native alignment.', 'image_modes', 'invalid_mode_config', 500)
    if mode == 'quality' and (w*h > spec['native_pixel_budget'] or max(w,h) > spec['max_native_edge']):
        raise ImageModeError('Selected Quality geometry exceeds its own budget; refusing a silent reduction.', 'image_modes', 'invalid_mode_config', 500)
    if type(spec['provisional']) is not bool:
        raise ImageModeError('provisional must be boolean.', 'provisional', 'invalid_mode_config', 500)
    if type(spec['auto_upscale']) is not bool:
        raise ImageModeError('auto_upscale must be boolean.', 'auto_upscale', 'invalid_mode_config', 500)
    return spec


def _requested_dimensions(payload, spec):
    if 'width' in payload or 'height' in payload:
        if 'width' not in payload or 'height' not in payload:
            raise ImageModeError('Provide width and height together.', 'size', 'invalid_dimensions')
        return (_integer(payload['width'], 'width'), _integer(payload['height'], 'height'))
    size = payload.get('size')
    if size not in (None, '', 'auto'):
        match = re.fullmatch(r'([0-9]+)x([0-9]+)', str(size))
        if not match:
            raise ImageModeError('size must be WIDTHxHEIGHT or auto.', 'size', 'invalid_dimensions')
        return tuple(_integer(value, 'size') for value in match.groups())
    return spec['default_width'], spec['default_height']


def author_resolution(landscape, budget, max_edge, alignment=16):
    """Largest exact author ratio within the trusted mode's effective limits."""
    if type(alignment) is not int or alignment not in (16, 32, 64):
        raise ImageModeError('Invalid alignment.', 'native_alignment', 'invalid_mode_config', 500)
    # Exact2:3 requires both sides to be aligned, hence ratio unit%alignment==0.
    sizes = [(2*unit, 3*unit) for unit in range(alignment, max_edge//3 + 1, alignment)
             if 2*unit >= 256 and 6*unit*unit <= budget]
    if not sizes:
        raise ImageModeError('Mode budget cannot fit an author-ratio image.', 'image_modes', 'invalid_mode_config', 500)
    width, height = sizes[-1]
    return (height, width) if landscape else (width, height)


def resolve_image_mode(payload, config, operation='generation'):
    """Consume kcpp_quality once; caller forwards only result.payload to Native.

    The returned native_profile is for the external supervisor. This function
    neither switches Native nor claims the selected profile is loaded.
    """
    if not isinstance(payload, dict) or not isinstance(config, dict):
        raise ImageModeError('JSON object/config required.', code='invalid_payload')
    if operation not in ('generation', 'edit'):
        raise ImageModeError('Unsupported image operation.', 'operation', 'invalid_operation')
    clean = copy.deepcopy(payload)
    mode = clean.pop(FIELD, 'normal')
    if not isinstance(mode, str) or mode not in DEFAULT_MODES:
        raise ImageModeError('kcpp_quality must be normal or quality.')
    local = copy.deepcopy(config)
    spec = _mode_spec(local, mode)
    defaults, proxy = local.setdefault('defaults', {}), local.setdefault('proxy', {})
    # Sampling follows the reviewed Helper defaults for both photo modes.
    # Do not silently disable cache or replace the configured step count in High.
    # Mode defaults are an explicit selected/fallback size, never silently enlarged.
    budget = min(spec['native_pixel_budget'], spec['default_width']*spec['default_height'])
    edge = min(spec['max_native_edge'], max(spec['default_width'], spec['default_height']))
    # High defaults to SR; Normal may explicitly request it. Native receives
    # enable_hr=False: the proxy runs the configured SR after faces/restoration.
    if 'enable_hr' in clean and type(clean['enable_hr']) is not bool:
        raise ImageModeError('enable_hr must be boolean.', 'enable_hr', 'invalid_upscale_flag')
    auto_upscale = operation == 'generation' and (spec['auto_upscale'] or clean.get('enable_hr') is True)
    proxy.update(native_pixel_budget=budget, max_native_edge=edge,
                 native_alignment=spec['native_alignment'], fixed_native_resolution=True,
                 always_upscale=auto_upscale, allow_generation_upscale=auto_upscale,
                 faces_before_upscale=True, repeat_faces_after_upscale=False)
    defaults.update(width=spec['default_width'], height=spec['default_height'], enable_hr=auto_upscale)
    clean['enable_hr'] = auto_upscale
    meta = dict(kcpp_quality=mode, native_profile=spec['native_profile'], operation=operation,
                native_pixel_budget=budget, max_native_edge=edge, native_alignment=spec['native_alignment'],
                auto_upscale=auto_upscale, provisional=spec['provisional'],
                generation_face_target_seconds=spec['generation_face_target_seconds'], generation_face_speed_proven=False,
                timing_scope=('generation_including_loras_faces_restoration_and_upscale' if auto_upscale
                              else 'generation_including_loras_and_first_face_without_upscale'),
                comparison_targets_seconds=[150] if mode == 'normal' else [], repeat_faces_after_upscale=False,
                fallback_reason=spec.get('fallback_reason'), geometry_applied=False)
    if operation == 'generation':
        requested = _requested_dimensions(clean, spec)
        if mode == 'quality':
            short, long = sorted((spec['default_width'],spec['default_height']))
            actual = (long,short) if requested[0] > requested[1] else (short,long)
        else:
            if spec['default_width']*3 != spec['default_height']*2:
                short,long=sorted((spec['default_width'],spec['default_height']))
                actual=(long,short) if requested[0]>requested[1] else (short,long)
            else:
                actual = author_resolution(requested[0] > requested[1], budget, edge, spec['native_alignment'])
        rw, rh = requested
        exact_author = rw*3 == rh*2 or rw*2 == rh*3
        requested_fits = (min(requested) >= 256 and rw % spec['native_alignment'] == 0 and
                          rh % spec['native_alignment'] == 0 and rw*rh <= budget and max(requested) <= edge)
        use_smaller = mode == 'normal' and exact_author and requested_fits and rw*rh < actual[0]*actual[1]
        if use_smaller:
            actual = requested
        clean.update(width=actual[0], height=actual[1])
        # OpenAI's size must not overwrite the resolved pair in a later translator.
        clean.pop('size', None)
        meta.update(requested_dimensions=list(requested), native_dimensions=list(actual),
                    aspect_policy=('normal selected Native grid within1% of author2:3; explicit smaller aligned author sizes respected'
                                   if mode == 'normal' else 'quality exact selected author2:3/3:2 geometry by orientation; client smaller size ignored; square defaults portrait'),
                    author_aspect_relative_error=abs(min(actual)*3-max(actual)*2)/(max(actual)*2),
                    requested_smaller_author_size_used=use_smaller,
                    geometry_applied=True, native_fullhd_long_edge1920=max(actual) == 1920)
    else:
        meta.update(aspect_policy='source aspect; uniform fit within budget, never author-ratio crop',
                    mask_policy='same content box/scale as image; caller retains existing mask-support validation')
    return ResolvedImageMode(clean, local, mode, spec['native_profile'], meta)


def edit_resolution(width, height, config, requested_dimensions=None):
    """Reuse the existing generic aspect resolver only for source-aware edits."""
    width = _integer(width, 'source_width', 256)
    height = _integer(height, 'source_height', 256)
    proxy = config['proxy']
    budget = min(int(proxy['native_pixel_budget']), width*height)
    edge = min(int(proxy['max_native_edge']), max(width, height))
    if requested_dimensions is not None:
        if not isinstance(requested_dimensions, (list, tuple)) or len(requested_dimensions) != 2:
            raise ImageModeError('Expected two requested dimensions.', 'size', 'invalid_dimensions')
        rw, rh = (_integer(value, 'size', 256) for value in requested_dimensions)
        budget, edge = min(budget, rw*rh), min(edge, max(rw, rh))
    short,long=sorted((int(config['defaults']['width']),int(config['defaults']['height'])))
    candidate=(long,short) if width>height else (short,long)
    source_error=abs(min(width,height)*3-max(width,height)*2)/(max(width,height)*2)
    if source_error<=.01 and candidate[0]*candidate[1]<=budget and max(candidate)<=edge:
        return candidate
    return choose_resolution(width, height, budget, edge, alignment=int(proxy['native_alignment']))


def fit_edit_pair(image, mask, config, requested_dimensions=None):
    """CPU pixel geometry only. Inputs must already share orientation/coordinates.

    Mask rejection remains the caller's policy. For an
    allowed A1111 mask this preserves soft/binary levels with NEAREST and puts
    the same scaled mask in the image content box; padded pixels stay maskedoff.
    """
    from PIL import Image
    from ImageEdits import fit_with_edge_padding
    if mask is not None and mask.size != image.size:
        raise ImageModeError('Mask dimensions must match source image.', 'mask', 'invalid_mask_dimensions')
    if 'A' in image.getbands() and image.getchannel('A').getextrema()[0] < 255:
        raise ImageModeError('Transparent source masks are unsupported.', 'image', 'mask_unsupported', 422)
    target = edit_resolution(image.width, image.height, config, requested_dimensions)
    prepared, geometry = fit_with_edge_padding(image.convert('RGB'), target)
    prepared_mask = None
    if mask is not None:
        prepared_mask = Image.new('L', target, 0)
        resized = mask.convert('L').resize(tuple(geometry['content_dimensions']), Image.Resampling.NEAREST)
        prepared_mask.paste(resized, tuple(geometry['content_box'][:2]))
    return prepared, prepared_mask, geometry

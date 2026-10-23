"""Pure resolution-relative face-size policy. No detector/model imports."""
from math import isfinite,sqrt

REFERENCE_DIMENSIONS=(640,864)
REFERENCE_MINIMUM_FACE=32
REFERENCE_MAXIMUM_FACE=128


def _dimensions(value,name):
    if not isinstance(value,(tuple,list)) or len(value)!=2:
        raise ValueError(name+' must contain width and height')
    result=[]
    for item in value:
        if isinstance(item,bool):raise ValueError(name+' must contain positive integers')
        number=int(item)
        if number<=0 or float(item)!=number:raise ValueError(name+' must contain positive integers')
        result.append(number)
    return tuple(result)


def _number(value,name):
    if isinstance(value,bool):raise ValueError(name+' must be a positive number')
    number=float(value)
    if not isfinite(number) or number<=0:raise ValueError(name+' must be a positive number')
    return number


def scale_face_options(options,image_size):
    """Return copied options and metadata; never compound an earlier SR scale.

    Explicit reference bounds win. Legacy post-SR callers may provide only
    effective bounds and _pixel_scale; division restores their reference base.
    auto_size=False leaves those effective legacy bounds unchanged.
    """
    local=dict(options or {})
    width,height=_dimensions(image_size,'image_size')
    reference=_dimensions(local.get('reference_dimensions',REFERENCE_DIMENSIONS),'reference_dimensions')
    enabled=local.get('auto_size',True)
    if not isinstance(enabled,bool):raise ValueError('auto_size must be boolean')
    incoming_scale=_number(local.get('_pixel_scale',1),'_pixel_scale')
    minimum=_number(local.get('minimum_face',REFERENCE_MINIMUM_FACE),'minimum_face')
    maximum=_number(local.get('maximum_face',REFERENCE_MAXIMUM_FACE),'maximum_face')
    base_minimum=_number(local.get('_reference_minimum_face',minimum/incoming_scale),'_reference_minimum_face')
    base_maximum=_number(local.get('_reference_maximum_face',maximum/incoming_scale),'_reference_maximum_face')
    if minimum>maximum or base_minimum>base_maximum:raise ValueError('Invalid face-size range')
    geometric_scale=sqrt((width*height)/(reference[0]*reference[1]))
    scale=geometric_scale if enabled else incoming_scale
    if enabled:
        raw_minimum=round(base_minimum*scale)
        raw_maximum=round(base_maximum*scale)
        selected_minimum=min(2048,max(16,raw_minimum))
        selected_maximum=min(2048,max(selected_minimum,raw_maximum))
    else:
        if not minimum.is_integer() or not maximum.is_integer() or not 16<=minimum<=maximum<=2048:
            raise ValueError('Invalid unscaled face-size range')
        selected_minimum,selected_maximum=int(minimum),int(maximum)
        raw_minimum,raw_maximum=selected_minimum,selected_maximum
    local.update(minimum_face=selected_minimum,maximum_face=selected_maximum,
                 _reference_minimum_face=base_minimum,_reference_maximum_face=base_maximum,
                 _pixel_scale=scale)
    metadata=dict(policy='reference_image_area' if enabled else 'legacy_unscaled',auto_size=enabled,
                  reference_dimensions=list(reference),input_dimensions=[width,height],scale=scale,
                  geometric_scale=geometric_scale,reference_minimum_face=base_minimum,
                  reference_maximum_face=base_maximum,minimum_face=selected_minimum,maximum_face=selected_maximum,
                  clamped=(selected_minimum,selected_maximum)!=(raw_minimum,raw_maximum),
                  detector_resolution_unchanged=True,
                  eligibility='min(box_width,box_height)>=minimum_face and max(box_width,box_height)<=maximum_face')
    return local,metadata

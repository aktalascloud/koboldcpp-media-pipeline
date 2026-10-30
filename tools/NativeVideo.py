"""Native Kobold request builder and CPU-only AVI-to-MP4 finishing.

One bounded loopback HTTP request is available for the video service. No model
loader, SD CLI, profile switch or GPU call; Supervisor owns startup/unload.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import http.client
import json
import os
from pathlib import Path
import struct
import subprocess
import math
import socket
import threading
import time
from urllib.parse import urlparse
import zlib

SIZES = {'360p': (640, 352), '480p': (832, 480)}
FPS = 24
MAX_FRAMES = 121
MAX_RESPONSE_BYTES = 256 * 1024**2
MAX_START_BYTES = 16 * 1024**2
MAX_VIDEO_SECONDS = 900


def request_json_deadline(url, payload=None, headers=None, timeout=MAX_VIDEO_SECONDS, _binary_audio=False):
    """Absolute watchdog closes only this request's loopback socket.

    Based on the separately tested pilot watchdog. A socket read timeout alone
    is insufficient when a peer keeps sending data. This is not a process kill.
    """
    if isinstance(timeout,bool) or not isinstance(timeout,(int,float)) or not math.isfinite(timeout) or not 0<timeout<=MAX_VIDEO_SECONDS:
        raise ValueError('Video HTTP timeout must be finite and in(0,900]seconds')
    address=urlparse(url)
    if (address.scheme!='http' or address.hostname not in ('127.0.0.1','localhost') or address.port not in (5003,5005,5013)
            or address.username or address.password or address.query or address.fragment):
        raise ValueError('Video HTTP targets only the owned loopback Native slot')
    data=json.dumps(payload).encode('utf-8') if payload is not None else None
    returned={k:v for k,v in (headers or {}).items() if k.lower() not in ('host','content-length','connection','transfer-encoding')}
    returned.update({'Content-Type':'application/json','Accept-Encoding':'identity'})
    connection=http.client.HTTPConnection(address.hostname,address.port,timeout=float(timeout))
    # The watchdog may close the socket between the expiry check and send().
    # Never let HTTPConnection silently reconnect after that absolute deadline.
    connection.auto_open=0
    expired=threading.Event();sockets=[];started=time.perf_counter()
    def cancel():
        expired.set();sock=sockets[0] if sockets else connection.sock
        if sock is not None:
            try:sock.shutdown(socket.SHUT_RDWR)
            except OSError:pass
        connection.close()
    timer=threading.Timer(float(timeout),cancel);timer.daemon=True;timer.start()
    try:
        connection.connect()
        if connection.sock is not None:sockets.append(connection.sock)
        if expired.is_set() or time.perf_counter()-started>=timeout:raise TimeoutError('Absolute video Native HTTP deadline exceeded')
        connection.request('POST' if payload is not None else 'GET',address.path or '/',data,returned)
        response=connection.getresponse();body=response.read(MAX_RESPONSE_BYTES+1)
        if expired.is_set() or time.perf_counter()-started>=timeout:raise TimeoutError('Absolute video Native HTTP deadline exceeded')
        if len(body)>MAX_RESPONSE_BYTES:raise ValueError('Native video JSON exceeds bounded response limit')
        if not 200<=response.status<300:raise RuntimeError('Native HTTP'+str(response.status)+': '+body[:1000].decode('utf-8','replace'))
        if _binary_audio:
            if len(body)<128 or not (body.startswith(b'ID3') or (body[0]==255 and body[1]&224==224)):
                raise ValueError('Native returned no valid MP3 audio')
            answer=body
        else:answer=json.loads(body)
        if expired.is_set() or time.perf_counter()-started>=timeout:raise TimeoutError('Absolute video Native HTTP deadline exceeded')
        return answer
    except (OSError,http.client.HTTPException) as error:
        if expired.is_set() or time.perf_counter()-started>=timeout:raise TimeoutError('Absolute video Native HTTP deadline exceeded') from error
        raise
    finally:timer.cancel();connection.close()


def request_audio_deadline(url,payload,headers=None,timeout=MAX_VIDEO_SECONDS):
    return request_json_deadline(url,payload,headers,timeout,_binary_audio=True)


def project_root(value: str | Path | None = None) -> Path:
    if value is None:
        from RuntimePaths import ROOT
        root = Path(ROOT).resolve()
    else:
        root = Path(value).resolve()
    if not (root / 'Helper.kcpps').is_file():
        raise ValueError('Portable root must contain Helper.kcpps')
    return root


def decode_base64(value: str, maximum: int) -> bytes:
    if not isinstance(value, str):
        raise ValueError('Expected base64 string')
    if value.startswith('data:'):
        value = value.split(',', 1)[1]
    if len(value) > (maximum + 2) // 3 * 4 + 4:
        raise ValueError('Encoded media exceeds size limit')
    try:
        result = base64.b64decode(value, validate=True)
    except (ValueError, TypeError) as error:
        raise ValueError('Invalid media base64') from error
    if len(result) > maximum:
        raise ValueError('Decoded media exceeds size limit')
    return result


def png_dimensions(data: bytes) -> tuple[int, int]:
    if not data.startswith(b'\x89PNG\r\n\x1a\n'):
        raise ValueError('Expected PNG start/final frame')
    cursor, dimensions, ended = 8, None, False
    while cursor + 12 <= len(data):
        size = struct.unpack_from('>I', data, cursor)[0]
        kind = data[cursor + 4:cursor + 8]
        end = cursor + 12 + size
        if end > len(data):
            raise ValueError('Truncated PNG chunk')
        if zlib.crc32(data[cursor + 4:end - 4]) & 0xffffffff != struct.unpack_from('>I', data, end - 4)[0]:
            raise ValueError('PNG CRC mismatch')
        if kind == b'IHDR':
            if dimensions is not None or size != 13:
                raise ValueError('Invalid PNG header')
            dimensions = struct.unpack_from('>II', data, cursor + 8)
        if kind == b'IEND':
            ended = True
            break
        cursor = end
    if not dimensions or not ended:
        raise ValueError('PNG header/end missing')
    return dimensions


def video_cache_settings(job):
    mode=job.get('cache_mode','disabled')
    if mode not in ('disabled','cache-dit','easycache'):
        raise ValueError('Video cache_mode must be disabled, cache-dit or easycache')
    defaults={'disabled':'','cache-dit':'threshold=0.08,warmup=2,Fn=16,Bn=2','easycache':'threshold=0.2,start=0.15,end=0.85'}
    options=job.get('cache_options',defaults[mode])
    if mode!='disabled' and options=='':options=defaults[mode]
    if not isinstance(options,str) or len(options)>160:raise ValueError('Bounded video cache_options string required')
    if mode=='disabled':
        if options:raise ValueError('Disabled video cache must have empty options')
        return mode,''
    allowed={'threshold','warmup','Fn','Bn'} if mode=='cache-dit' else {'threshold','start','end'}
    values={}
    for field in options.split(','):
        key,sep,value=field.partition('=');key=key.strip();value=value.strip()
        if not sep or key not in allowed or key in values:raise ValueError('Unknown or duplicate video cache option')
        try:number=float(value)
        except ValueError:raise ValueError('Video cache options must be numeric') from None
        if not math.isfinite(number):raise ValueError('Video cache options must be finite')
        if key in ('warmup','Fn','Bn'):
            if not value.isdecimal() or not 0<=number<=40:raise ValueError('Invalid video cache block/warmup count')
            if key=='warmup' and not 1<=number<=3:raise ValueError('Four-step video cache warmup must be1..3')
        elif key=='threshold':
            if not 0<=number<=.3:raise ValueError('Video cache threshold must be0..0.3')
        elif not 0<=number<=1:raise ValueError('Video cache fractions must be0..1')
        values[key]=number
    if mode=='easycache' and not values.get('start',.15)<values.get('end',.85):raise ValueError('Video cache start must precede end')
    return mode,options


def prepare_request(job: dict, root: str | Path | None = None,
                    backend: str = 'http://127.0.0.1:5013',
                    native_jpeg_quality: int = 95) -> dict:
    """Build only. Do not send this request through the ordinary photo pipeline."""
    root = project_root(root)
    if native_jpeg_quality not in (40, 90, 95):
        raise ValueError('Manager must identify the actual verified Native JPEG quality; this is metadata, not an API override')
    address = urlparse(backend)
    if address.scheme != 'http' or address.hostname not in ('127.0.0.1', 'localhost') or address.port not in (5003,5005,5013) or address.path not in ('', '/') or address.query or address.fragment or address.username:
        raise ValueError('Expected local Native manager backend on5005 (legacy5003, manual5013)')
    resolution = job.get('resolution', '480p')
    if resolution not in SIZES:
        raise ValueError('Resolution must be360p or480p')
    width, height = SIZES[resolution]
    if job.get('orientation', 'landscape') not in ('portrait','landscape'):
        raise ValueError('Orientation must be portrait or landscape')
    if job.get('orientation', 'landscape') == 'portrait':
        width, height = height, width
    elif job.get('orientation', 'landscape') != 'landscape':
        raise ValueError('Orientation must be landscape or portrait')
    frames = job.get('frames', 17)
    if isinstance(frames, bool) or not isinstance(frames, int) or not 5 <= frames <= MAX_FRAMES or frames % 4 != 1:
        raise ValueError('Frames must be4n+1, from5 through121')
    if job.get('fps', FPS) != FPS or job.get('steps', 4) != 4 or job.get('cfg_scale', 1) != 1:
        raise ValueError('Video usesFPS24,4steps,CFG1')
    prompt = str(job.get('prompt', '')).strip()
    if not prompt or len(prompt.encode('utf-8')) > 2400:
        raise ValueError('Prompt must contain1..2400UTF8bytes')
    if '<lora:' in prompt.lower():
        raise ValueError('Photo LoRA tags must not be inherited by Wan')
    seed = job.get('seed', 20261020)
    if isinstance(seed, bool) or not isinstance(seed, int) or not -1 <= seed <= 2147483647:
        raise ValueError('Seed must fit signed32-bit integer or-1')
    payload = dict(prompt=prompt, negative_prompt='', width=width, height=height,
                   frames=frames, fps=FPS, steps=4, cfg_scale=1, sampler_name='euler',
                   scheduler='simple', flow_shift=5, eta=0, clip_skip=-1,
                   cache_mode='disabled', cache_options='', enable_hr=False,
                   video_output_type=1, seed=seed, lora=[])
    payload['kcpp_extra_args']=dict(keep_image_gen_on_disconnect=False)
    requested_scheduler=job.get('scheduler','simple')
    if requested_scheduler not in ('simple','normal','discrete','beta','sgm_uniform'):raise ValueError('Unsupported video Euler scheduler')
    payload['scheduler']='discrete' if requested_scheduler=='normal' else requested_scheduler
    payload['cache_mode'],payload['cache_options']=video_cache_settings(job)
    start = job.get('start_frame')
    start_encoded = job.get('start_png_base64')
    if start and start_encoded:
        raise ValueError('Choose one initialPNG source')
    if start_encoded:
        image=decode_base64(start_encoded,MAX_START_BYTES)
        source_size=png_dimensions(image)
        payload['video_start_frame']=base64.b64encode(image).decode('ascii')
        start_metadata=dict(source='inlinePNG',dimensions=list(source_size),sha256=hashlib.sha256(image).hexdigest(),
                            native_preprocessing='Native center-crops to targetaspect and BOX-resizes if dimensions differ; manager may prepare a matchingPNG first.')
    elif start:
        path = Path(start)
        if not path.is_absolute():
            path = root / path
        path = path.resolve()
        if not path.is_relative_to(root) or not path.is_file() or path.stat().st_size > MAX_START_BYTES:
            raise ValueError('Start frame must be a local PNG inside portable root, at most16MiB')
        image = path.read_bytes()
        source_size = png_dimensions(image)
        payload['video_start_frame'] = base64.b64encode(image).decode('ascii')
        start_metadata = dict(path=str(path), dimensions=list(source_size), sha256=hashlib.sha256(image).hexdigest(),
                              native_preprocessing='Native center-crops to targetaspect and BOX-resizes if dimensions differ; manager may prepare a matchingPNG first.')
    else:
        start_metadata = None
    return dict(endpoint=backend.rstrip('/') + '/sdapi/v1/txt2img', payload=payload,
                contract=dict(backend='Native KoboldCpp1.123.1', dimensions=[width, height],
                              frames=frames, fps=FPS, seconds=frames/FPS,
                              model='Wan2.2-TI2V-5B-Turbo-Q4_0', start_frame=start_metadata,
                              automatic_photo_details=False, automatic_upscale=False,
                              source_container='MJPEG AVI', source_jpeg_quality=native_jpeg_quality,
                              lossless_native_frames_available=False,
                              continuation='Pass returned last_frame_path as nextjob.start_frame; continuity is unverified. No stretching, frame duplication or interpolation is performed.'))


def avi_header(data: bytes) -> dict:
    if len(data) < 12 or data[:4] != b'RIFF' or data[8:12] != b'AVI ':
        raise ValueError('Native response is not AVI; GIF is not silently substituted')
    end = struct.unpack_from('<I', data, 4)[0] + 8
    if end > len(data):
        raise ValueError('Truncated AVI container')
    header = None
    video_stream = None
    def walk(start: int, stop: int, depth: int = 0):
        nonlocal header, video_stream
        if depth > 4:
            raise ValueError('Excessive AVI header nesting')
        position = start
        while position + 8 <= stop:
            kind = data[position:position + 4]
            size = struct.unpack_from('<I', data, position + 4)[0]
            content, finish = position + 8, position + 8 + size
            if finish > stop:
                raise ValueError('Truncated AVI chunk')
            if kind == b'LIST' and size >= 4 and data[content:content + 4] in (b'hdrl', b'strl'):
                walk(content + 4, finish, depth + 1)
            elif kind == b'avih' and size >= 56:
                values = struct.unpack_from('<14I', data, content)
                header = dict(microseconds_per_frame=values[0], frames=values[4], width=values[8], height=values[9])
            elif kind == b'strh' and size >= 48 and data[content:content + 4] == b'vids':
                scale, rate = struct.unpack_from('<II', data, content + 20)
                video_stream = dict(codec=data[content + 4:content + 8].decode('ascii', 'replace'), scale=scale, rate=rate)
            position = finish + size % 2
    walk(12, end)
    if not header or not video_stream or not video_stream['scale'] or not video_stream['rate']:
        raise ValueError('AVI video headers missing')
    header.update(video_stream)
    header['fps'] = video_stream['rate'] / video_stream['scale']
    if video_stream['codec'].upper() not in ('MJPG', 'JPEG'):
        raise ValueError('Unexpected Native AVI codec')
    return header


def finish_native_video(answer: dict, plan: dict, output_dir: str | Path,
                        root: str | Path | None = None, timeout: float = 180,
                        run_encoder: bool = False, deadline: float | None = None,
                        clock=None) -> dict:
    """Preserve Native AVI/finalPNG, optionally run bundled CPU FFmpeg explicitly."""
    clock=clock or time.perf_counter
    if isinstance(timeout,bool) or not isinstance(timeout,(int,float)) or not math.isfinite(timeout) or timeout<=0:
        raise ValueError('Encoder timeout must be finite and positive')
    if deadline is not None and (isinstance(deadline,bool) or not isinstance(deadline,(int,float)) or not math.isfinite(deadline)):
        raise ValueError('Video deadline must be finite')
    root = project_root(root)
    destination = Path(output_dir)
    if not destination.is_absolute():destination=root/destination
    destination=destination.resolve()
    allowed = [root/'OUTPUTS/video', root/'RESULTS/Video']
    if not any(destination.is_relative_to(path.resolve()) for path in allowed):
        raise ValueError('Output must stay within managed VIDEO outputs or benchmark artifacts')
    if not answer.get('animated'):
        raise ValueError('Native did not return an animated video result')
    encoded = list(answer.get('images', [])[:1]) + [answer.get('extra_data', '')]
    media = None
    for value in encoded:
        if not value:
            continue
        decoded = decode_base64(value, MAX_RESPONSE_BYTES)
        if decoded.startswith(b'RIFF'):
            media = decoded
            break
    if media is None:
        raise ValueError('Native AVI payload missing')
    metadata = avi_header(media)
    contract = plan['contract']
    if [metadata['width'], metadata['height']] != contract['dimensions'] or metadata['frames'] != contract['frames'] or abs(metadata['fps'] - contract['fps']) > .0001:
        raise ValueError('Native AVI dimensions/framecount/FPS differ from requested contract')
    final = decode_base64(answer.get('final_frame', ''), MAX_START_BYTES)
    if list(png_dimensions(final)) != contract['dimensions']:
        raise ValueError('Native finalPNG dimensions differ from AVI')
    ffmpeg = root/'runtime/ffmpeg/ffmpeg.exe'
    if not ffmpeg.is_file():
        raise ValueError('Bundled FFmpeg missing')
    native_file, last_frame = destination/'native.avi', destination/'last-frame.png'
    temporary, final_file = destination/'video.work.mp4', destination/'video.mp4'
    command = [str(ffmpeg), '-hide_banner', '-nostdin', '-n', '-hwaccel', 'none',
               '-i', str(native_file), '-map', '0:v:0', '-an', '-c:v', 'libx264',
               '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p', '-threads', '8',
               '-fps_mode', 'passthrough', '-movflags', '+faststart', '-progress', 'pipe:1',
               '-nostats', '-f', 'mp4', str(temporary)]
    report = dict(status='prepared_not_executed', native_header=metadata,
                  source_avi_sha256=hashlib.sha256(media).hexdigest(),
                  source_avi_bytes=len(media), last_frame_path=str(last_frame),
                  last_frame_sha256=hashlib.sha256(final).hexdigest(),
                  ffmpeg_command=command, output=str(final_file),
                  source_jpeg_quality=contract['source_jpeg_quality'],
                  source_quality_note=f'Native JPEG{contract["source_jpeg_quality"]} loss is already present; CRF18 MP4 does not restore lost detail.',
                  temporal_processing='No-r, scale, fps, setpts, duplicate, interpolation or duration-stretch filter.',
                  video_post_detailer=False, video_upscale=False)
    if not run_encoder:
        return report
    if any(path.exists() for path in [native_file, last_frame, temporary, final_file, destination/'postprocess.json', destination/'ffmpeg-progress.txt', destination/'ffmpeg.log']):
        raise ValueError('Refusing to overwrite existing video stage outputs')
    destination.mkdir(parents=True, exist_ok=True)
    native_file.write_bytes(media)
    last_frame.write_bytes(final)
    env = os.environ.copy()
    env['TMP'] = env['TEMP'] = str(root/'runtime/tmp')
    Path(env['TMP']).mkdir(parents=True, exist_ok=True)
    started = clock()
    def remaining_encoder():
        allowance=min(float(timeout),600.0)
        if deadline is not None:allowance=min(allowance,deadline-clock())
        return allowance
    def fail_deadline(message):
        report.update(status='failed_total_video_deadline',encoder_seconds=clock()-started,
                      total_deadline=deadline,native_artifacts_preserved=True)
        (destination/'postprocess.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        raise TimeoutError(message)
    allowance=remaining_encoder()
    if allowance<=0:fail_deadline('Total video deadline exhausted before MP4 encoding; Native artifacts retained')
    report['encoder_timeout_seconds']=allowance
    try:
        completed = subprocess.run(command, cwd=str(root), env=env, timeout=allowance, capture_output=True, text=True, encoding='utf-8', errors='replace')
    except subprocess.TimeoutExpired as error:
        for value, name in [(error.stdout, 'ffmpeg-progress.txt'), (error.stderr, 'ffmpeg.log')]:
            if isinstance(value, bytes):value=value.decode('utf-8', 'replace')
            (destination/name).write_text(value or '', encoding='utf-8')
        report.update(status='failed_encoder_timeout', encoder_seconds=clock()-started,
                      encoder_timeout_seconds=allowance,native_artifacts_preserved=True)
        (destination/'postprocess.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        raise TimeoutError('FFmpeg timeout; NativeAVI/finalPNG/logs retained') from error
    (destination/'ffmpeg-progress.txt').write_text(completed.stdout, encoding='utf-8')
    (destination/'ffmpeg.log').write_text(completed.stderr, encoding='utf-8')
    if completed.returncode:
        raise RuntimeError('FFmpeg failed; nativeAVI/finalPNG/logs retained')
    if deadline is not None and clock()>=deadline:fail_deadline('Total video deadline exhausted during MP4 encoding; work file retained')
    progress = {}
    for line in completed.stdout.splitlines():
        if '=' in line:
            key, value = line.split('=', 1)
            progress[key] = value.strip()
    if int(progress.get('frame', '-1')) != metadata['frames'] or int(progress.get('dup_frames', '0')) or int(progress.get('drop_frames', '0')):
        raise RuntimeError('Encoded framecount differs or frames were duplicated/dropped; logs retained')
    if not temporary.is_file() or temporary.stat().st_size == 0:
        raise RuntimeError('Empty MP4 output')
    output_bytes=temporary.stat().st_size
    output_sha256=hashlib.sha256(temporary.read_bytes()).hexdigest()
    if deadline is not None and clock()>=deadline:fail_deadline('Total video deadline exhausted before MP4 publication; work file retained')
    os.replace(temporary, final_file)
    report.update(status='completed', encoder_seconds=clock()-started,
                  encoded_frames=metadata['frames'], output_bytes=output_bytes,
                  output_sha256=output_sha256, progress=progress)
    (destination/'postprocess.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    if deadline is not None and clock()>=deadline:fail_deadline('Total video deadline exhausted after MP4 publication; saved output retained')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['build', 'postprocess'])
    parser.add_argument('--root')
    parser.add_argument('--job', required=True)
    parser.add_argument('--backend', default='http://127.0.0.1:5013')
    parser.add_argument('--response')
    parser.add_argument('--output-dir')
    parser.add_argument('--run-encoder', action='store_true')
    args = parser.parse_args()
    job = json.loads(Path(args.job).read_text(encoding='utf-8-sig'))
    plan = prepare_request(job, args.root, args.backend)
    if args.mode == 'postprocess':
        if not args.response or not args.output_dir:
            parser.error('postprocess requires--response and--output-dir')
        answer = json.loads(Path(args.response).read_text(encoding='utf-8-sig'))
        result = finish_native_video(answer, plan, args.output_dir, args.root, run_encoder=args.run_encoder)
    else:
        result = plan
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

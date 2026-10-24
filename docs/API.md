# API and OpenWebUI

AUTOMATIC1111 image base URL: `http://YOUR_KOBOLD_HOST:5001`. The private Native port5003 is not an OWUI endpoint. OpenAI Images uses the same public server with `/v1`. Defaults are loopback; network exposure is explicit and no cloud/API credential is shipped.

## Normal
Works without a mode field. Normal uses736×1104; landscape1104×736. Generation and edits receive YuNet/GPEN/SFace/Gater; no automatic SR.

```json
{"width":736,"height":1104,"steps":8,"cfg_scale":1,"sampler_name":"euler","scheduler":"simple","eta":0,"flow_shift":5,"clip_skip":-1,"cache_mode":"cache-dit","cache_options":"threshold=0.08,warmup=4,Fn=16,Bn=2","enable_hr":false}
```

## High
Use exactly `kcpp_quality:"quality"`; `high` is a UI label, not an API alias. This selects928×1392 and automatic Helaman4×, returning3712×5568. Both native orientations are exact2:3. The saved complete request took861.79s; a15min target is not a guarantee for all scenes.

```json
{"kcpp_quality":"quality","width":928,"height":1392,"steps":8,"cfg_scale":1,"sampler_name":"euler","scheduler":"simple","eta":0,"flow_shift":5,"clip_skip":-1,"cache_mode":"cache-dit","cache_options":"threshold=0.08,warmup=4,Fn=16,Bn=2","enable_hr":true}
```

Apply the selected preset after common filter parameters and remove a conflicting `size`. High determines orientation and ignores stale smaller dimensions. Normal respects an explicit smaller aligned2:3 request; remove old576×864 values if the new Normal is wanted. Sampling comes from Helper: the proxy does not force9steps or disable High cache. MOSS requests above2,000,000 native pixels are rejected by the guard.

`enable_hr` selects proxy SR; it does not switch face refinement. Before forwarding to Native the proxy sets it false, so no expensive native hires/img2img pass runs. High faces and Gater run before4×, with no repeat afterward. Automatic face bounds are39–155px Normal and49–196px High; the model's512 GPEN input and dimensionless20%/SFace0.97 settings remain fixed.

Use an HTTP timeout that covers the complete image request, e.g.3600–7200s in the actual filter client/reverse proxy. There is no universal OWUI environment-variable name assumed here.

## Routes
- `POST /sdapi/v1/txt2img`: generation.
- `POST /sdapi/v1/img2img`: `init_images`, prompt and `denoising_strength`.
- `POST /v1/images/generations`: OpenAI Images-compatible generation.
- `POST /v1/images/edits`: one PNG/JPEG/WebP file or supported base64 JSON; alias `kobold-moss-img2img` is accepted. Ordinary redraw, not an instruction-edit-trained model. Default strength0.6. The input is uniformly fit to the Normal/edit budget; final faces/Gater run, autoSR off. Masks remain unsupported on the OpenAI edit route.
- `POST /sdapi/v1/extra-single-image` with `{"image":"BASE64_PNG","upscaling_resize":4}`: standalone SR. `/sdapi/v1/upscale` is also accepted. Faces/Gater run first unless valid pixel-bound PNG markers prove prior processing. Preserve returned original PNG bytes, not a thumbnail or metadata-stripped re-encode.
- Music: `/api/extra/music/prepare`, `/api/extra/music/generate`, original Kobold schema; MP3 forced. Photo is restored afterward. Public capabilities aggregate supported profiles; private Native reports the currently loaded module.

For long jobs a `genkey` can identify progress requests; poll `/sdapi/v1/progress?genkey=THE_SAME_KEY`. Do not confuse Native's LLM abort queue with image cancellation. This backend version has no standard A1111 image-interrupt route; direct forwarding is not a tested cancellation mechanism.

## Prompt filter
Use one rewrite, cache the finished caption by original request/options/model version, and normally aim for120–180 coherent English words. No `physioshade`, Z-Image LoRA tags, negative-prompt lists or repeated quality tags. Describe subject/action/framing/light/materials/colors and requested visible text. Exact counts, clocks and anatomy remain generative limitations. The proxy accepts up to3000 UTF-8 caption bytes without silent truncation. [Official prompt skill](https://github.com/OpenMOSS/MOSS-Image/blob/main/skills/moss-image-prompt-enhancer/SKILL.md).

Model loading: Normal stays GPU-resident; music loads on demand. High and standalone SR release only the supervisor-owned idle Native for exclusive Gater/Helaman VRAM, then restore Normal. Do not start a second GPU backend on the same card while expecting the measured timings.
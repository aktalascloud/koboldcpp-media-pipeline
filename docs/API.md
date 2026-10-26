# API and OpenWebUI
Public AUTOMATIC1111 URL: `http://YOUR_KOBOLD_HOST:5001`; OpenAI Images uses `/v1`. Private Native 5003 is not an OWUI endpoint. Default bind is loopback; expose it explicitly during Setup if needed.

## Normal with immediate4×
Works without a mode field.736×1104 generates2944×4416, landscape swaps dimensions. `enable_hr:true` selects the proxy SR pass, not native hires/img2img.
```json
{
  "steps": 8,
  "cfg_scale": 1,
  "sampler_name": "dpm++2m_sde",
  "scheduler": "sgm_uniform",
  "eta": 0,
  "flow_shift": 5,
  "clip_skip": -1,
  "cache_mode": "cache-dit",
  "cache_options": "threshold=0.08,warmup=4,Fn=16,Bn=2",
  "width": 736,
  "height": 1104,
  "enable_hr": true
}
```
Set `enable_hr:false` or omit it for ordinary Normal without SR. Faces/Gater still apply. The selected model is controlled by the backend profile; no LoRA trigger or client checkpoint override is needed.

## High
Use `kcpp_quality:"quality"`.928×1392 produces3712×5568. The selected Refined High profile is not yet measured end-to-end; do not apply old Artius/Helaman timing to it.
```json
{
  "width": 928,
  "height": 1392,
  "steps": 8,
  "cfg_scale": 1,
  "sampler_name": "dpm++2m_sde",
  "scheduler": "sgm_uniform",
  "eta": 0,
  "flow_shift": 5,
  "clip_skip": -1,
  "cache_mode": "cache-dit",
  "cache_options": "threshold=0.08,warmup=4,Fn=16,Bn=2",
  "kcpp_quality": "quality",
  "enable_hr": true
}
```
Apply the selected preset after common filter parameters; remove a conflicting `size`. High owns its orientation/size and defaults to SR. Sampling follows Helper defaults. Max2MP guard remains; sdclampedsoft=2048 prevents silent1MP clamping.

## Processing and routes
- `POST /sdapi/v1/txt2img`: generation; `/v1/images/generations` is OpenAI Images-compatible.
- `POST /sdapi/v1/img2img`: init_images/prompt/denoising_strength; final faces/Gater, no automatic SR on edits.
- `POST /v1/images/edits`: PNG/JPEG/WebP or supported base64 JSON. Ordinary redraw, not an instruction-edit-trained model; default strength0.6. Source aspect is retained; OpenAI edit masks remain unsupported.
- `POST /sdapi/v1/extra-single-image` or `/sdapi/v1/upscale`: `{"image":"BASE64_PNG","upscaling_resize":4}`. Applies faces/Gater first, unless valid pixel-bound markers prove they already ran. Returns exact4×; no repeated face pass afterward. Preserve returned PNG bytes, not a metadata-stripped thumbnail.
- Music `/api/extra/music/prepare` and `/api/extra/music/generate`: original schema, MP3, demand loading and photo return.
- Progress `/sdapi/v1/progress?genkey=YOUR_JOB_KEY`. Native LLM abort is not an image-cancel API.

YuNet960, GPEN512/OpenVINOCPU at20%, SFace≥0.97, max2; face bounds39–155 px Normal/49–196 px High. Larger faces can skip GPEN. Gater1× and ClearReality4× use FP32 DirectML with owned VRAM handoff, then photo returns to GPU. No driver or TDR changes.

Use a client/proxy timeout covering the full job, e.g.3600 s. Prompt rewriting: one pass, cache the result, normally120–180 coherent English words. Describe subject/action/framing/light/materials/colors; no Z-Image LoRA/physioshade tags. Exact anatomy, clocks and small writing are not guaranteed. [Official MOSS prompt skill](https://github.com/OpenMOSS/MOSS-Image/blob/main/skills/moss-image-prompt-enhancer/SKILL.md).

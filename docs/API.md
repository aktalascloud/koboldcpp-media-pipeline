# API / OpenWebUI
AUTOMATIC1111 base: `http://YOUR_KOBOLD_HOST:5001`; OpenAI Images uses `/v1`. Private Native5003 is not OWUI's endpoint. Setup binds loopback by default; use `-ListenHost 0.0.0.0` to expose your LAN service explicitly.

## Normal
No explicit mode needed. Extra JSON:
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
  "enable_hr": false
}
```
The server owns the selected image model, static Afterlight0.25 and sampling profile. No LoRA tags/triggers. `enable_hr:true` requests proxy4×, not Native hires/img2img. Default Normal returns736×1104 with faces/Gater;4× returns2944×4416.

## High through a filter
Apply after common filter parameters; remove conflicting `size` overrides:
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
High selects928×1392 and defaults to4× (3712×5568). Selected Ray High generation/full-cycle is not measured; historical times do not apply.

## Processing / routes
- Generation: `/sdapi/v1/txt2img`, `/v1/images/generations`.
- Redraw: `/sdapi/v1/img2img`; `/v1/images/edits` requires explicit `operation=img2img`. Final faces/Gater; no autoSR. [Limitations](EDITING.md).
- Upscale: `/sdapi/v1/extra-single-image` or `/sdapi/v1/upscale`, `{"image":"BASE64_PNG","upscaling_resize":4}`. Faces/Gater before SR unless valid pixel-bound markers prove they ran already. No repeated pass after SR; preserve returned PNG/metadata.
- YuNet960 detects; GPEN512 blends20%; SFace>=0.97 guards features, max2faces. Bounds scale by image area; large faces may be skipped. Gater Restore1× then optional ClearReality FP32 DirectML4×. Separate denoise/Gater Sharpen/Helaman disabled.
- `/v1/images/capabilities`: instruction-edit/masks/raw references/multi-image are explicitly unsupported, not replaced by successful PNG generation.
- [Reference synthesis](REFERENCE-SYNTHESIS.md): client-selected vision analysis/caption, text-only conditioning, no exact identity guarantee.
- MusicMP3/API-only; returns to GPU-resident Normal. Video deferred.

Use a timeout covering the full job, e.g.3600s. Rewrite captions once and cache them; normally120–180 coherent English words. Numeric timing scope: benchmarks/results.json.


YuE2 music supersedes previous ACE-Step references: Q8_0 main + F16 VAE, no Gemma, client-side helper, MP3. See [music contract](MUSIC.md). Original pinned weights download only; CC-BY-NC-4.0 and upstream attribution apply. No song-generation claims beyond the saved short trials.

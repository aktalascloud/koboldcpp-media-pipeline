# OpenWebUI and API

A1111 image generation base URL: `http://YOUR_KOBOLD_HOST:5001`. Authentication is blank only if you configured no authentication. This is the proxy, not private Native5003. OpenAI-compatible routes also exist; keep the existing OpenWebUI image-generation provider unchanged.

Normal additional parameters (works without explicitly specifying normal):

```json
{"width":592,"height":896,"steps":8,"cfg_scale":1,"sampler_name":"euler","scheduler":"beta","eta":0,"flow_shift":3,"clip_skip":-1,"cache_mode":"cache-dit","cache_options":"threshold=0.08,warmup=4,Fn=16,Bn=2","enable_hr":false}
```

High additional parameters:

```json
{"kcpp_quality":"quality","width":1152,"height":768,"steps":8,"cfg_scale":1,"sampler_name":"euler","scheduler":"beta","eta":0,"flow_shift":3,"clip_skip":-1,"cache_mode":"cache-dit","cache_options":"threshold=0.08,warmup=4,Fn=16,Bn=2","enable_hr":true}
```

Use exactly `kcpp_quality: "quality"`; `high` is the UI name, not an API alias; the public API preset files are authoritative. Normal faces/Gater always run; enable_hr is not a switch for face refinement. High selects its own native profile and optional SR policy.

POST `/sdapi/v1/txt2img` for generation. POST `/sdapi/v1/img2img` with `init_images` and `denoising_strength` for ordinary Turbo redraw. This is not an instruction-trained image-edit model; exact identity/structure preservation is not guaranteed. Final edits receive YuNet/GPEN/SFace/Gater, with the Normal pixel budget.

POST `/sdapi/v1/extra-single-image` with `{"image":"BASE64_PNG","upscaling_resize":4}` for existing images. `/sdapi/v1/upscale` is also accepted. It preprocesses faces/Gater unless valid markers match, then Helaman4x, without a second refinement pass. Preserve original returned PNG bytes in the OpenWebUI filter so the pixel-bound markers survive. Decode/re-encode may lose metadata and require processing again.

LoRA weights are static in Helper and profiles. Send only the scene prompt: the proxy prefixes `physioshade` once. Never add duplicate `<lora:...>` tags. Prompt enhancement should run once, target up to180 natural English words, and cache the finished prompt keyed by original text/options/model version; do not change the model or inference parameters.

Music: POST `/api/extra/music/prepare` or `/api/extra/music/generate` using the existing Kobold music schema. MP3 is forced by this profile. The public service aggregates photo/music capabilities even while private Native reports only the currently loaded model. No external cloud API key is shipped.

# Video API

Public API: port5001 or5003. Native5005 is private. `/media#video` is the shared workbench; `/api` and `/openapi.json` list every operation.

POST `/v1/videos/generations` (JSON), or POST `/v1/media/generations` with `{"type":"video","parameters":{...}}`.

```json
{"prompt":"A cinematic scene with subtle natural motion","frames":17,"resolution":"480p","orientation":"portrait","steps":4,"sampler_name":"euler","scheduler":"beta","cfg_scale":1,"eta":0,"flow_shift":5,"cache_mode":"cache-dit","cache_options":"threshold=0.04,warmup=1,Fn=16,Bn=2","upscale_to":"720p","enhance_faces":true,"interpolate_fps":48,"audio":{"enabled":true,"style":"Cinematic instrumental, no vocals"}}
```

Wan5B full encoder/diffusion, causal Pro FP32 DirectML, threshold576/actual320px tiles, WG512; no Tiny. ClearReality720p, guarded GPEN/SFace, optional RIFE48 and separate YuE2 track.17 native frames are about0.71s, not17seconds; interpolation preserves duration. No Foley/lip-sync claim. Check `/v1/videos/capabilities` before requesting48FPS. Source PNG base64 uses `image`, not a local start_frame path.

Models switch automatically; Native unloads before GPU postprocessing and photo residency returns. Relative result URLs resolve against this server. GET returned MP4 URL; support Range playback. Limit450s; only17-frame full Pro jobs validated. Long continuous video unverified.

Cache0.04/warmup1 is the user's30October selection. Historical29October cache probes did not establish a consistent speed gain; their original EXE SHA and all negatives remain in benchmarks/video.json. No new generation/speed benchmark for this GUI/API update. Public kit does not enable the private user video adapter.

One Helper.kcpps holds exact derived profiles. Settings writes are local/same-origin/revision-guarded and idle-only. Owner-local KoboldCpp.exe bundles code/runtime; models stay external. Public code kit uses original downloads and does not mirror the large local runtime EXE.

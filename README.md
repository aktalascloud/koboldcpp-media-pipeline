# KoboldCpp media server · MOSS / YuE2 / Wan

[Русский](README.ru.md) · [Windows kit](https://github.com/aktalascloud/koboldcpp-media-pipeline/releases/latest) · [API](docs/API.md) · [OWUI filter instructions](docs/MEDIA.ru.md) · [Models/licenses](docs/LICENSES.md)

One portable Windows media server built around [our Haswell AVX2 / RX580 Polaris/gfx803 KoboldCpp fork](https://github.com/aktalascloud/koboldcpp-avx2-vulkan-numa) and [original KoboldCpp](https://github.com/LostRuins/koboldcpp). One shared Native slot; the image model stays GPU-resident when idle. Models unload/load automatically. Run **Start.exe**; **Setup.ps1** is initial setup/update only.

| Task | Selected configuration | Public API |
|---|---|---|
| Images | Ray Artshoot Q8, Afterlight0.25 + RealismEnhancer1.0, Euler/simple8, CFG1, eta0, shift5, Cache-DiT0.08 | `/sdapi/v1/txt2img`, `/v1/images/generations` |
| Music | YuE2-3B Q8 + F16 VAE, caller-provided lyrics/style, MP3 stereo | `/api/extra/music/generate` |
| Video + soundtrack | Wan5B Turbo Q4, full encoder + Pro FP32 DirectML, Euler/beta4, CFG1, eta0, shift5 | `/v1/videos/generations` |

Normal/edit: **736×1104**, YuNet/GPEN20%/SFace0.97/Gater, no automatic SR. Explicit `enable_hr:true` adds ClearReality4×. High: **928×1392**, defaults to4×; the new High adapter combination has not been generated/measured. Native hires is off.

Video: native **480p**, Pro threshold576/actual320px tiles, WG512; ClearReality720p and guarded faces. Tiny/Super-Tiny are not used. Timed YuE2 music, SA3 effects and external TTS speech can be mixed into one MP4 without re-encoding video. Event timing is supplied by the client/helper; this is not joint AV inference or lip-sync. [Audio timeline and optional SFX installation](docs/AUDIO-TIMELINE.md). Optional RIFE48FPS preserves duration. The public kit has no private user video adapter enabled; local video measurements explicitly include one.

## Current saved example

| Actual Normal | Actual4× output (lossless full image linked) |
|---|---|
|![Normal](examples/ray-realism-normal.png)|[![4x preview](examples/ray-realism-4x-preview.webp)](examples/ray-realism-4x.webp)|

![Exact4× eye pixels](examples/ray-realism-eyes.png)

Other scenes from the earlier28October recipe: [night](examples/night-processed.png), [watchmaker](examples/watchmaker-processed.png). They are historical examples, not measurements of the new adapters. [RGB provenance](examples/gallery.json).

## Measured scope

29October2026, Xeon E5-2696v3 / RX5802048SP8GB, EXE `ff7d4d0b`:

- Images29October2026, Nativeff7d4d0b: real public Normal, without explicit mode/size: **163.85s**. Ordinary4× API on that saved PNG: **6.04s**. These are two requests. [Image battle, all arms and cold/warm caveats](benchmarks/image-current.json).
- Video30October2026, Native0986410a: **3.04s/73frames**, I2V→Pro/Clear720/faces + music/SFX/RU speech: **552.57s**. Reviewed audio revision without regenerating frames: **57.96s**. A5.04s T2V clip passed854.78s but failed visual selection. [Exact stages and limits](benchmarks/audio-video-20261030.json).
- Light cache0.04/0.08 matched control latents in the tested scene;0.08 did not establish a consistent speed benefit. The current default is Cache-DiT0.04/warmup1 by user choice30October; no new gain is claimed. No universal speedup/long-clip claim.

## Setup

Download the code kit and run `Setup.ps1 -ListenHost 0.0.0.0` once for LAN use, then launch **Start.exe**. Main MOSS/Qwen weights and adapters come from original distributors/user imports; no main weights, keys, logs or caches are in this repository.

Pro is built once on CPU by `tools/SetupPro.py`: pinned original safetensors/source and temporary CPU PyTorch, using the same bundled Python. Serving afterwards needs only the three Pro graph/weight files and existing DirectML runtime. Optional RIFE is an original-download component; no Microsoft DLL is mirrored. [Video API/limits](docs/VIDEO.md) · [Original-download models](docs/MODELS.md).

## Desktop and API

Native **Image Gen** contains image models, faces/restoration/upscaling and img2img; **Audio** contains audio models and helper/TTS/STT connections; **Video** contains Wan/VAE/LoRA/upscaler/RIFE/cache settings. **Extra** has RU/EN and logon startup. Original file selectors are reused. Save/Load supports any user-selected `.kcpps`; duration, speech, frames and other request parameters belong in API calls.

Stable APIs5001/5003 share one queue, private Native5005 switches models. `/api` and `/openapi.json` document the routes; optional browser workbench `/media`. `POST /v1/media/generations` accepts `{"type":"video","parameters":{...}}`, also image/music. Photo returns GPU-resident after processing.

Owner-local `KoboldCpp.exe` (~371MiB) embeds code/runtime, not weights. Normal launch opens the native GUI; `--background` supports logon. The source builder is `tools/BuildBundle.py`. This complete local artifact is not publicly mirrored pending runtime redistribution review; the minimal public code kit uses **Start.exe** and separately installed dependencies. Fresh-machine end-to-end generation has not been tested.

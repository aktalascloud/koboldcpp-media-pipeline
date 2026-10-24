# KoboldCpp MOSS media pipeline
[Русский](README.ru.md) · **[Download Windows kit](https://github.com/aktalascloud/koboldcpp-media-pipeline/releases/latest)** · [API / OpenWebUI](docs/API.md) · [Model setup](docs/MODELS.md) · [Licenses](docs/LICENSES.md)

Portable Windows photo/music integration for **[our optimized KoboldCpp fork](https://github.com/aktalascloud/koboldcpp-avx2-vulkan-numa)** and [original KoboldCpp](https://github.com/LostRuins/koboldcpp). Tested on Haswell AVX2 and AMD RX 580 Polaris/gfx803 8 GB. Kobold remains the backend; the proxy provides AUTOMATIC1111/OpenAI Images APIs, model switching, face refinement, restoration and Helaman 4×.

## Current MOSS results
All images below were saved during existing tests. No new inference or AI retouching was performed for publication. [Pixel provenance](examples/gallery.json).

| Normal, faces + Gater | Watchmaker, saved 704×1056 | Night, saved 704×1056 |
|---|---|---|
| [![Normal](examples/normal-moss.png)](examples/normal-moss.png) | [![Watchmaker](examples/watchmaker-moss.png)](examples/watchmaker-moss.png) | [![Night](examples/night-moss.png)](examples/night-moss.png) |
| ![Face](examples/normal-moss-face.png) | ![Face](examples/watchmaker-moss-face.png) | ![Face](examples/night-moss-face.png) |

### Exact High source and full 4× cycle
The source RGB matches the native base of the measured High request. The right image includes faces, Gater and Helaman; this is a full-chain comparison, not an SR-only comparison. Crops contain unscaled saved pixels. The right overview is a labeled web preview; click it for the original 3712×5568 PNG.

| Native 928×1392, raw | Faces + Gater + Helaman 4× |
|---|---|
| [![Native](examples/high-native-moss.png)](examples/high-native-moss.png) | [![4× preview](examples/high-4x-preview.png)](examples/high-4x-moss.png) |
| ![Eyes](examples/high-native-moss-eyes.png) | ![Eyes](examples/high-4x-moss-eyes.png) |
| ![Face](examples/high-native-moss-face.png) | ![Face](examples/high-4x-moss-face.png) |

## Measured settings and time
| Mode | Native, exact 2:3 | Steps / cache | Output | Complete request |
|---|---|---|---|---:|
| Normal / edit budget | 736×1104 | 8 / Cache-DiT 0.08 | Faces + Gater, no autoSR | **141.47 s** |
| High | 928×1392, 1.29 MP | 8 / Cache-DiT 0.08 | Faces + Gater + 4×, 3712×5568 | **861.79 s — 14 min 22 s** |

High is one complete API request, including profile switching. Native 245.676 s; faces 1.597 s; Gater 4.608 s; Helaman 588.394 s; the remainder is switching/transport. No OOM occurred. This is one saved complex scene/seed, not a guarantee for every caption. Captions/cache hits/background load affect time. [Exact scope and proof](benchmarks/results.json). These are media-profile timings, not an attribution of gains to native compiler patches; see the linked core fork for stock-versus-latest native comparisons.

## Pipeline
1. **Artius MOSS compatible Q8_0** image/text GGUF, official Qwen3.5 tokenizer and FLUX2 VAE. No Z-Image LoRA or `physioshade` trigger. Original custom INT8/packed W4A8 files require the included local converter; converted weights are not uploaded here.
2. Euler/simple, **8 steps**, CFG 1, flow shift 5, clip skip −1, eta 0. Flash Attention on. Cache-DiT `threshold=0.08,warmup=4,Fn=16,Bn=2`; the control scene skipped two of eight model evaluations.
3. Text encoder on CPU, 20 threads; diffusion/VAE on Vulkan. High has a 6500 MiB budget and can segment if required. The selected size used a monolithic GPU graph.
4. YuNet 960, score 0.82; GPEN 512/OpenVINO CPU blended 20%; SFace minimum 0.97, at most two faces. Automatic bounds: Normal 39–155 px, High 49–196 px. Large faces may intentionally skip GPEN.
5. Gater Restore 1× FP32 DirectML, full native frame. No sharpen. High/standalone SR releases the owned idle Native before Gater and Helaman, then restores photo after the response. No repeated face/Gater pass after 4×. Pixel-bound PNG markers prevent duplicate processing.
6. Music loads on API demand, returns MP3, then restores the GPU-resident Normal photo model. Video remains deferred.

Sharpened eyes do not guarantee flawless anatomy or exact clock hands. The restorer/upscaler can smooth skin or fabric; native originals are provided. This Kobold adaptation does not include the author's TemporalScoreRescaling. Q8 conversion adds rounding; do not claim bit-identical ComfyUI inference.

## Install once, then run the EXE
1. Extract **media-pipeline-code.zip** from the latest release. Run **Setup.ps1 once**. It downloads SHA-pinned runtime/postprocessing assets and primary-host main weights, converts MOSS locally and creates the local manifest.
2. **Exact W4 encoder access is required.** Civitai file **3313824**, SHA256 starting `b0a6c1ab29`, requires the user's own account/access. Download it from the [author page](https://civitai.com/models/3010191?modelVersionId=3416029), then run `Setup.ps1 -MossSourceDirectory <your-download-folder>`. Alternatively use the process-only `CIVITAI_API_KEY` environment variable; the installer never saves or prints its value. Current HF v2 INT8 is a different file and is not silently substituted. [Details](docs/MODELS.md).
3. Launch **Start.exe directly**; no PowerShell launcher is needed afterward. **Start.exe --check** checks the installation. The registered Native window is separate and visible. One runtime copy; user-supplied source files are preserved. Allow roughly 60 GB free during initial download/conversion.

GPEN is downloaded from its original ONNX distributor, or supplied with `-GPENPath`; it is not mirrored in the new code release. Its terms are **Non-Commercial**, with unresolved original redistribution details. Main MOSS/Qwen/AceStep weights are never in Git or our release.

Defaults are loopback public 5001/private 5003. For another OWUI machine, explicitly pass `-ListenHost 0.0.0.0` during Setup and configure access on your network. Startup is opt-in: **Start.exe --register-startup**. No driver, BIOS, TDR, clock or voltage changes. Existing large runtime/postprocessing assets are hash-pinned and reused; unused Z-Image LoRAs/token resources are not extracted.

Original wrapper code: AGPL-3.0. GGUF writer subset: MIT. Model/runtime licenses are independent and retained. No credentials, private addresses, caches, logs, PID/state or benchmark counters are shipped. [Component notices](docs/LICENSES.md).
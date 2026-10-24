# KoboldCpp media pipeline
[Русский](README.ru.md) · **[Download](https://github.com/aktalascloud/koboldcpp-media-pipeline/releases/latest)** · [API / OpenWebUI](docs/API.md) · [Licenses](docs/LICENSES.md)

Portable Windows photo/music integration for **[our optimized KoboldCpp fork](https://github.com/aktalascloud/koboldcpp-avx2-vulkan-numa)**. Haswell/AVX2 and RX 580 Polaris/gfx803. Kobold stays the backend; the proxy adds model switching, face refinement, restoration and Helaman 4×.

## Selected results
Saved images from earlier tests; no new generation or retouching for publication. Different scenes use different saved stages; [provenance](examples/historical-scenes.json).

| Window portrait, Helaman 2× | Watchmaker, 2× | Tailoring studio, native |
|---|---|---|
| [![Portrait](examples/portrait-window-helaman-2x.png)](examples/portrait-window-helaman-2x.png) | [![Watchmaker](examples/watchmaker-workbench-2x.png)](examples/watchmaker-workbench-2x.png) | [![Studio](examples/tailoring-studio-native.png)](examples/tailoring-studio-native.png) |
| ![Eyes](examples/portrait-window-helaman-2x-eyes.png) | ![Hands](examples/watchmaker-workbench-2x-hands.png) | ![Eyes](examples/tailoring-studio-native-eyes.png) |

### Full body, face and eyes
The saved 608×912 source already includes three LoRAs, faces and Gater. Helaman produces 2432×3648 without another face pass. Crops preserve saved pixels.

| Refined source | Helaman 4× |
|---|---|
| [![Source](examples/normal-608x912-final.png)](examples/normal-608x912-final.png) | [![4×](examples/resident-normal-4x.png)](examples/resident-normal-4x.png) |
| ![Face](examples/sr-input-face.png) | ![Face](examples/helaman-4x-face.png) |
| ![Eyes](examples/sr-input-eyes.png) | ![Eyes](examples/helaman-4x-eyes.png) |

## Measured time
Same 576×864 scene, seed, three LoRAs, faces and Gater; no SR:

| Original stock | Latest measured optimized result |
|---:|---:|
| 163.15 s | 138.35 s first / **131.83 s warm** |

Warm elapsed time is **19.20% lower**. This saved 23 October test is separate from later native compiler builds. [Raw proof](benchmarks/results.json).

Current Normal is larger: **592×896, about 140 s warm**, without SR. Saved Helaman 608×912 to 2432×3648: **194.90 s**, exclusive VRAM, about 7.41 GB dedicated memory. Photo generation/reload is outside SR time. Full High+4× was not timed again after the memory-policy fix. Refinement does not guarantee correct clock geometry.

## Pipeline
1. GPU-resident Moody photo model; protected Qwen encoder on CPU, 20 threads. Music loads only on API demand, outputs MP3, then restores photo.
2. PhysioShade **0.15**, FlowDPO **0.35**, MaskedDPOFull **0.25**. Trigger **physioshade** is inserted once. Do not load the same LoRAs again in requests.
3. Euler/beta, **8 steps**, eta 0, CFG 1, shift 3, clip skip−1, Cache-DiT 0.08/warmup4/Fn16/Bn2; SD flash attention off.
4. YuNet 960, score 0.82; GPEN 512/OpenVINO CPU blended 20%; SFace minimum 0.97; max 2 faces. Face-size bounds scale with resolution.
5. Gater Restore 1× FP32 DirectML, strength 1, after faces. No sharpen.
6. Normal/edit **592×896**, no autoSR. High **1152×768** or portrait768×1152, auto Helaman native **4×**, no downsize/repeated face pass.

Standalone SR applies faces/Gater before Helaman unless pixel-bound markers prove prior processing. The supervisor releases its owned idle Native for exclusive SR VRAM, then restores photo. Video is deferred and its weights/runtime are excluded.

## Install
Extract **media-pipeline-code.zip**, run **Setup.ps1 once**, then launch **Start.exe directly**. Setup downloads hash-pinned components; large Moody/Qwen/AceStep weights come from their original hosts. One runtime copy. Start.exe --check validates installation.

Windows startup is opt-in: runtime/python/python.exe -I -B tools/Launch.py --register-startup. Kobold opens in a separate visible window. Public API 5001/private Native 5003 default to loopback; network exposure is explicit.

Code: AGPL-3.0; third-party terms retained. GPEN is a separate **Non-Commercial** asset. No credentials, private addresses, cache or logs in the public kit. [Component licenses](docs/LICENSES.md) · [Original KoboldCpp](https://github.com/LostRuins/koboldcpp).

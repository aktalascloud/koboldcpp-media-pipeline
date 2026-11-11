# KoboldCpp media pipeline
[Русский](README.ru.md) · [Release](https://github.com/aktalascloud/koboldcpp-media-pipeline/releases/latest) · [Install/build](docs/BUILD.md) · [API / OWUI](docs/API.md) · [Licenses](docs/LICENSES.md)

Portable Windows media around [our Haswell/AVX2 RX 580 Polaris/gfx803 fork](https://github.com/aktalascloud/koboldcpp-avx2-vulkan-numa) of [original KoboldCpp](https://github.com/LostRuins/koboldcpp). Run **Start.exe → KoboldCpp.exe**. Models switch exclusively; image stays GPU-resident when idle. Setup.ps1 is initial installation/update, not the launcher. No main weights are mirrored.

Goal: one portable KoboldCpp.exe with one runtime and a common on-demand API for photo, audio, video, effects and their combinations. The experimental core tracks official updates and selected security/model/performance patches for AVX2/Polaris; user-selected models and settings stay configurable.

- Default image recipe: Ray Q8, Afterlight0.25 + RealismEnhancer1, Euler/simple8, eta0, Cache-DiT0.08. Normal736×1104 without automatic SR; High928×1392 with ClearReality4x, supplemental High controls saved in the photo evidence. YuNet/GPEN20%/SFace0.97/Gater before SR, no repeat afterwards. Models/presets are configurable.
- Music: YuE2 MP3. SFX: SA3 CPU WAV/MP3,0.25–60s. Speech/helper/STT use a configurable provider and explicit RU/EN voices.
- Video: Wan5B Turbo, full encoder + Pro FP32, Euler/beta4, WG512, threshold576, ClearReality720p/faces, RIFE48FPS default/60 optional. Audio-driven lip-sync is a separate optional stage; this is not joint AV inference. Native limit121 frames; conservative tested clip73. Client project15 s default/30 s maximum.

**Core 1.125 · 2026-11-11 · Native `fdc3d11d`.** Official base `f49df57`. [77 patches](https://github.com/aktalascloud/koboldcpp-avx2-vulkan-numa/tree/concedo_experimental/performance/patches/series).

## Text, music and photo · November 11

| Workload | Before → after | Change |
|---|---:|---:|
| CPU · prompt | 72.313 → 73.305 tok/s | ≈+1.37% |
| CPU · decode | 17.251 → 17.148 tok/s | ≈-0.60% |
| RX 580 · prompt | 312.988 → 313.767 tok/s | ≈+0.25% |
| RX 580 · decode | 34.261 → 34.381 tok/s | +0.35% |
| YuE2 · 32 s | 43.900 → 43.910 s | +0.02% |
| ABDM Normal | 150.809 → 151.281 s | +0.31% |
| ABDM 4× | 2.712 → 2.639 s | ≈-2.70% |

Same Qwen3-4B IQ4_XS control, YuE2 profile and ABDM Normal profile. Text, semantic codes, MP3, PCM and RGB matched. The ≈ marker indicates overlapping ranges. Whole YuE2 timing uses one warm sample per executable.

[Repeats and hashes](results/performance-2026-11-11-multimodal.json) · [Operations](results/operations-2026-11-11-multimodal.json) · [PR diffs](results/pr-review-2026-11-11-multimodal.json)

## Ray Artshoot examples · November 7

| Actual Normal | Actual4x, full lossless image linked |
|---|---|
|![Normal](results/photo-normal.png)|[![4x](results/photo-preview.webp)](results/photo-4x.webp)|
![Unscaled4x eye pixels](results/photo-eyes.png)

Only necessary code/config/licenses and current results. Models/detailers/upscalers under MODELS, one runtime; all evidence under results. [Local-model build rules](AGENTS.md). Full owner-local EXE is built locally, not mirrored without runtime redistribution review. Fresh-machine full inference has not been tested.

## 1 November: verified changes
| Manual check | Result | Scope |
|---|---:|---|
| Native image, prior / fresh warm | 147.91 /147.60 s | same8-step736x1104 scene;12 RGB-identical outputs across flags |
| I2V73 → Pro/Clear720/faces/RIFE48 | 583.63 s |146 frames,3.04s; Native6053MiB VRAM, no OOM |
| Stored-video lip-sync at60FPS | 29.12 s API |183 frames; CPU, photo process unchanged |
| Music + SFX + exact speech | 57.37 s API | decoded video identical; exact WAV reused |

Pro502 after relocation was caused by an obsolete PowerShell monitor path. Audio mixing now uses finite sequential mix/mux/MP3 steps, avoiding a reproduced FFmpeg dual-output hang. Generations have persistent idempotent job receipts. Optional Wav2Lip is non-commercial, original-provider only; no perfect identity/articulation guarantee.73 frames are the conservative measured clip size;15/30 s remains client orchestration, not a measured long AI movie. Models/settings/context are configurable; API aliases do not select arbitrary weight files.

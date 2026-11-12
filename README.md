# KoboldCpp media pipeline
[Русский](README.ru.md) · [Release](https://github.com/aktalascloud/koboldcpp-media-pipeline/releases/latest) · [Install/build](docs/BUILD.md) · [API / OWUI](docs/API.md) · [Licenses](docs/LICENSES.md)

Portable Windows media around [our Haswell/AVX2 RX 580 Polaris/gfx803 fork](https://github.com/aktalascloud/koboldcpp-avx2-vulkan-numa) of [original KoboldCpp](https://github.com/LostRuins/koboldcpp). Run **Start.exe → KoboldCpp.exe**. Models switch exclusively; image stays GPU-resident when idle. Setup.ps1 is initial installation/update, not the launcher. No main weights are mirrored.

Goal: one portable KoboldCpp.exe with one runtime and a common on-demand API for photo, audio, video, effects and their combinations. The experimental core tracks official updates and selected security/model/performance patches for AVX2/Polaris; user-selected models and settings stay configurable.

- Default image recipe: Ray Q8, Afterlight0.25 + RealismEnhancer1, Euler/simple8, eta0, Cache-DiT0.08. Normal736×1104 without automatic SR; High928×1392 with ClearReality4x, supplemental High controls saved in the photo evidence. YuNet/GPEN20%/SFace0.97/Gater before SR, no repeat afterwards. Models/presets are configurable.
- Music: YuE2 MP3. SFX: SA3 CPU WAV/MP3,0.25–60s. Speech/helper/STT use a configurable provider and explicit RU/EN voices.
- Video: Wan5B Turbo, full encoder + Pro FP32, Euler/beta4, WG512, threshold576, ClearReality720p/faces, RIFE48FPS default/60 optional. Audio-driven lip-sync is a separate optional stage; this is not joint AV inference. Native limit121 frames; conservative tested clip73. Client project15 s default/30 s maximum.

**Core 1.125 · 2026-11-12 · Native 743938b2.** Official base d7331295. [81 patches](https://github.com/aktalascloud/koboldcpp-avx2-vulkan-numa/tree/concedo_experimental/performance/patches/series).

YuE2 accepts up to 300 seconds or 7,500 semantic tokens through the public music API. [Duration patch](patches/media-music-five-minute-limit/README.md).

## FlashAttention, decode and render · November 11

This table reports the November 11 Native 5f103234 build.

| Workload | Before → after | Change |
|---|---:|---:|
| CPU · prompt | 74.224 → 73.158 tok/s | ≈-1.44% |
| CPU · decode | 17.436 → 17.317 tok/s | ≈-0.69% |
| RX 580 · prompt | 305.191 → 311.772 tok/s | +2.16% |
| RX 580 · decode | 33.118 → 34.034 tok/s | +2.77% |
| YuE2 Vulkan · render from plan | 28.820 → 25.213 s | -12.52% |
| YuE2 CPU · render from plan | 289.237 → 288.529 s | -0.24% |
| YuE2 Vulkan · whole request | 43.729 → 40.155 s | -8.17% |
| ABDM Normal | 151.281 → 129.601 s | -14.33% |
| Separate 4× | 2.639 → 2.688 s | ≈+1.85% |

Text, semantic codes, MP3, PCM and RGB matched. YuE2 phase comparisons use one sample per build. CPU decode uses eight counterbalanced samples per build. The ≈ marker means the ranges overlap. The operation report retains every tested Q8_0 variant.

[Repeats and SHA](results/performance-2026-11-11-kernels.json) · [Operations](results/operations-2026-11-11-kernels.json) · [PR diffs](results/pr-review-2026-11-11-kernels.json)

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

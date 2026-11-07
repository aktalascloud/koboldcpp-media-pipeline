# KoboldCpp media pipeline
[Русский](README.ru.md) · [Release](https://github.com/aktalascloud/koboldcpp-media-pipeline/releases/latest) · [Install/build](docs/BUILD.md) · [API / OWUI](docs/API.md) · [Licenses](docs/LICENSES.md)

Portable Windows media around [our Haswell/AVX2 RX 580 Polaris/gfx803 fork](https://github.com/aktalascloud/koboldcpp-avx2-vulkan-numa) of [original KoboldCpp](https://github.com/LostRuins/koboldcpp). Run **Start.exe → KoboldCpp.exe**. Models switch exclusively; image stays GPU-resident when idle. Setup.ps1 is initial installation/update, not the launcher. No main weights are mirrored.

Goal: one portable KoboldCpp.exe with one runtime and a common on-demand API for photo, audio, video, effects and their combinations. The experimental core tracks official updates and selected security/model/performance patches for AVX2/Polaris; user-selected models and settings stay configurable.

- Default image recipe: Ray Q8, Afterlight0.25 + RealismEnhancer1, Euler/simple8, eta0, Cache-DiT0.08. Normal736×1104 without automatic SR; High928×1392 with ClearReality4x, supplemental High controls saved in the photo evidence. YuNet/GPEN20%/SFace0.97/Gater before SR, no repeat afterwards. Models/presets are configurable.
- Music: YuE2 MP3. SFX: SA3 CPU WAV/MP3,0.25–60s. Speech/helper/STT use a configurable provider and explicit RU/EN voices.
- Video: Wan5B Turbo, full encoder + Pro FP32, Euler/beta4, WG512, threshold576, ClearReality720p/faces, RIFE48FPS default/60 optional. Audio-driven lip-sync is a separate optional stage; this is not joint AV inference. Native limit121 frames; conservative tested clip73. Client project15 s default/30 s maximum.

**Core1.125 · 2026-11-07 · `efddce0e`.** 65 Native patches,7 new adaptations;Pillow13.0.0. [Catalog and PR review](https://github.com/aktalascloud/koboldcpp-avx2-vulkan-numa/blob/concedo_experimental/performance/review-2026-11-07-r5.md) · [Separate media patch](patches/pillow13-security/README.md).

## Manual Normal+4× · 2026-11-07

Latest available official rolling1.125 `db00fc38`,updated November3 → `efddce0e`. Three arms:stock,previous0519dcbf,new EXE;the same current models,settings,prompt and seed424242,no High.3 Normal/arm,first separate,warm median of two;2 separate4×/arm with photo resident before every call.

| Stage | Official1.125 | Fork efddce0e | Less time |
|---|---:|---:|---:|
| Native | 176.810 s | 143.500 s | 33.310 s / 18.84% |
| Normal ready | 185.187 s | 152.333 s | 32.854 s / 17.74% |
| Separate4× | 2.838 s | 2.772 s | 0.066 s / 2.33% |
| Normal+4×* | 188.025 s | 155.105 s | 32.920 s / 17.51% |

*Sum of independently measured phase medians,not one joint API request. Production Pipeline/private Native HTTP includes PNG/base64/JSON;public5001 queue/transport,model loading and photo return are excluded. All9 raw/finished RGB and6 SR outputs match. Against previous0519dcbf,the sum saves **2.745s / 1.74%**;separate4× takes **33.5ms longer**. SR shares identical media code;this is not an upscaler-kernel gain. [Every repeat,range,load,hash and limit](results/performance-2026-11-07-r4.json). Arm order is fixed,sample size small.

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

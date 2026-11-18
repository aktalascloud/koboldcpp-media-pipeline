# KoboldCpp media pipeline

[Русский](README.ru.md) · [Release](https://github.com/aktalascloud/koboldcpp-media-pipeline/releases/latest) · [Install](docs/BUILD.md) · [API](docs/API.md) · [Licenses](docs/LICENSES.md)

Portable Windows service for images, video, music and sound effects. Run `Start.exe`. Setup installs the [Windows AVX2/Vulkan core](https://github.com/aktalascloud/koboldcpp-avx2-vulkan-numa/releases/latest). The active image model stays resident while idle. Video and music load on demand. Pick weights and presets in the native GUI.

- Images use MOSS with optional face restoration and 4× upscaling.
- Wan video supports up to 121 native frames at 24 FPS per pass. RIFE provides 48 or 60 FPS.
- YuE2 accepts up to 300 seconds. SA3 produces sound effects on CPU.
- Open **System → GGUF Converter** for quantization and calibration. [Converter](https://github.com/aktalascloud/gguf-converter)

**Core 1.125 · 2026-11-17 · d9b2e6b5** · [Patched source](https://github.com/aktalascloud/koboldcpp-avx2-vulkan-numa/tree/concedo_experimental/performance/patches/series) · [Media patches](patches/)

[Verified examples and dated tests](https://github.com/aktalascloud/koboldcpp-media-pipeline/blob/v2026.11.17-r5/results/measurements.json).

[Gater on RX 580](patches/gater-directml-graph/README.md) · [Video post-processing](patches/media-video-post-fast/README.md) · [RIFE input](patches/rife-fast-png/README.md)

[LightVAE-Pro profiling](patches/video-pro-profile/README.md) · [RIFE CPU workers](patches/rife-cpu-workers/README.md) · [November 18 runs](results/video-post-ab-20261118.json)

[RX 580/Haswell measurements](results/lowlevel-media-20261118.json) · [LightVAE-Pro](patches/lightvae-pro-gpu-state/) · [SA3](patches/sa3-media-dispatch/)

# KoboldCpp media pipeline

[Русский](README.ru.md) · [Release](https://github.com/aktalascloud/koboldcpp-media-pipeline/releases/latest) · [Install](docs/BUILD.md) · [Unified API](docs/UNIFIED-API.md) · [Licenses](docs/LICENSES.md)

Portable Windows service for images, video, music and sound effects. After setup, run `KoboldCpp.exe`. Use `Start-Local.cmd` when the project is next to an existing KoboldCpp installation. Setup installs the [Windows AVX2/Vulkan core](https://github.com/aktalascloud/koboldcpp-avx2-vulkan-numa/releases/tag/v1.125-20261117-d9b2e6b5). The image model stays resident while idle. Video and music load on demand.

- Images use MOSS with optional face restoration and 4× upscaling.
- Wan video supports up to 121 native frames at 24 FPS per pass. RIFE provides 48 or 60 FPS.
- YuE2 accepts up to 300 seconds. SA3 produces sound effects on CPU.
- Open **System → GGUF Converter** for quantization and calibration. [Converter](https://github.com/aktalascloud/gguf-converter) · [Installer patch](patches/portable-gguf-converter/)

**Core 1.125 · 2026-11-17 · d9b2e6b5** · [Patched source](https://github.com/aktalascloud/koboldcpp-avx2-vulkan-numa/tree/concedo_experimental/performance/patches/series) · [Media patches](patches/)

[Measurements and example gallery](docs/evidence/) · [Release notes](RELEASE.md)

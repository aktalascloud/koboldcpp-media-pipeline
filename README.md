# KoboldCpp Media Pipeline

[Русский](README.ru.md) · [Release / Скачать](https://github.com/aktalascloud/koboldcpp-media-pipeline/releases/latest) · [Guide / Документация](docs/UNIFIED-API.md) · [Evidence / Данные](https://github.com/aktalascloud/koboldcpp-media-pipeline/blob/24a912c4c35ee6ad38deea62a46a58730fa3ee84/docs/evidence/lowlevel-media-20261118.json)

Run local image, video, music and sound-effect generation behind one Windows API. The image model stays resident when idle. Wan video and YuE2 music load on demand. SA3 runs sound effects on the CPU.

**Quick start.** Follow [setup](docs/BUILD.md) and launch `KoboldCpp.exe`. If you already have KoboldCpp in the adjacent folder, use `Start-Local.cmd`. See [model packages](release-assets.json) and the [Hugging Face catalog](https://huggingface.co/TalasCloud).

**Evidence.** November 18, 2026, RX 580 / Haswell worker A/B: LightVAE-Pro saved 17 Wan frames in 30.53 s vs 33.04 s. The SA3 CPU worker processed three chunks of a 15-second effect in 21.57 s vs 26.53 s. Outputs matched byte for byte. The code archive uses the compatible pinned installer runtime.

## Capabilities

- MOSS images with optional face restoration and 4× upscaling.
- Wan generates up to 121 native frames at 24 FPS per pass. RIFE interpolates to 48 or 60 FPS.
- YuE2 accepts up to 300 seconds. Open **System → GGUF Converter** to quantize and calibrate weights.

[All measurements and examples / Все замеры и примеры](docs/evidence/) · [Patches / Патчи](patches/) · [GGUF Converter](https://github.com/aktalascloud/gguf-converter) · [Core AVX2/Vulkan](https://github.com/aktalascloud/koboldcpp-avx2-vulkan-numa)

[All projects / Все проекты](https://github.com/aktalascloud)

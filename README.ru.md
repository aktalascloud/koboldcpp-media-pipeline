# Медиакомплект KoboldCpp

[English](README.md) · [Релиз](https://github.com/aktalascloud/koboldcpp-media-pipeline/releases/latest) · [Установка](docs/BUILD.md) · [Единый API](docs/UNIFIED-API.md) · [Лицензии](docs/LICENSES.md)

Переносимый Windows-сервер для фото, видео, музыки и звуковых эффектов. После установки запускайте `KoboldCpp.exe`. Если проект лежит рядом с готовой установкой KoboldCpp, используйте `Start-Local.cmd`. Установщик подключает [движок AVX2/Vulkan](https://github.com/aktalascloud/koboldcpp-avx2-vulkan-numa/releases/tag/v1.125-20261117-d9b2e6b5). Фото остаётся в памяти при простое. Видео и музыка загружаются по запросу.

- MOSS для изображений с опциональным улучшением лиц и апскейлом 4×.
- Wan даёт до 121 кадра за проход при 24 FPS. RIFE интерполирует до 48 или 60 FPS.
- YuE2 принимает запросы до 300 секунд. SA3 генерирует эффекты на CPU.
- **Система → Конвертер GGUF** открывает квантование и калибровку. [Конвертер](https://github.com/aktalascloud/gguf-converter) · [Патч установщика](patches/portable-gguf-converter/)

**Core 1.125 · 17 ноября 2026 · d9b2e6b5** · [Патчи движка](https://github.com/aktalascloud/koboldcpp-avx2-vulkan-numa/tree/concedo_experimental/performance/patches/series) · [Патчи медиакомплекта](patches/)

[Замеры и галерея примеров](docs/evidence/) · [Заметки к релизу](RELEASE.md)

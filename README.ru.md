# Медиакомплект KoboldCpp

[English](README.md) · [Релиз](https://github.com/aktalascloud/koboldcpp-media-pipeline/releases/latest) · [Установка](docs/BUILD.md) · [API](docs/API.ru.md) · [Лицензии](docs/LICENSES.md)

Переносимый Windows-сервер для фото, видео, музыки и звуковых эффектов. Запускайте `Start.exe`. Установщик подключает [движок AVX2/Vulkan](https://github.com/aktalascloud/koboldcpp-avx2-vulkan-numa/releases/latest). Фото остаётся в памяти при простое. Видео и музыка загружаются по запросу. Модели и параметры выбираются в GUI.

- MOSS для изображений с опциональным улучшением лиц и апскейлом 4×.
- Wan даёт до 121 кадра за проход при 24 FPS. RIFE интерполирует до 48 или 60 FPS.
- YuE2 принимает запросы до 300 секунд. SA3 генерирует эффекты на CPU.
- **Система → Конвертер GGUF** открывает квантование и калибровку. [Конвертер](https://github.com/aktalascloud/gguf-converter)

**Core 1.125 · 17 ноября 2026 · d9b2e6b5** · [Патчи движка](https://github.com/aktalascloud/koboldcpp-avx2-vulkan-numa/tree/concedo_experimental/performance/patches/series) · [Патчи медиакомплекта](patches/)

[Проверенные примеры и замеры](https://github.com/aktalascloud/koboldcpp-media-pipeline/blob/v2026.11.17-r5/results/measurements.json).

[Gater на RX 580](patches/gater-directml-graph/README.md) · [Постобработка видео](patches/media-video-post-fast/README.md) · [Кадры для RIFE](patches/rife-fast-png/README.md)

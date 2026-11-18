# KoboldCpp Media Pipeline

[English](README.md) · [Скачать](https://github.com/aktalascloud/koboldcpp-media-pipeline/releases/tag/v2026.11.18-r1) · [Документация](docs/UNIFIED-API.md) · [Данные](https://github.com/aktalascloud/koboldcpp-media-pipeline/blob/24a912c4c35ee6ad38deea62a46a58730fa3ee84/docs/evidence/lowlevel-media-20261118.json)

Локальный Windows API для изображений, видео, музыки и звуковых эффектов. Модель изображений остаётся в памяти при простое. Wan и YuE2 загружаются по запросу. Звуковые эффекты SA3 работают на CPU.

**Запуск.** Следуйте [инструкции установки](docs/BUILD.md) и запустите `KoboldCpp.exe`. Если KoboldCpp уже лежит в соседней папке, используйте `Start-Local.cmd`. Пакеты указаны в [манифесте](release-assets.json) и [каталоге Hugging Face](https://huggingface.co/TalasCloud).

**Проверка.** В A/B от 18 ноября 2026 года на RX 580 / Haswell воркер LightVAE-Pro сохранил 17 кадров Wan за 30,53 с вместо 33,04 с. CPU-воркер SA3 обработал три чанка 15-секундного эффекта за 21,57 с вместо 26,53 с. Результаты совпали побайтно. В архиве кода используется совместимый рантайм установщика.

## Возможности

- MOSS для изображений, восстановление лиц и апскейл 4× по выбору.
- Wan генерирует до 121 исходного кадра за проход при 24 FPS. RIFE интерполирует до 48 или 60 FPS.
- YuE2 принимает длительность до 300 секунд. Квантование и калибровка доступны в **System → GGUF Converter**.

[All measurements and examples / Все замеры и примеры](docs/evidence/) · [Patches / Патчи](patches/) · [GGUF Converter](https://github.com/aktalascloud/gguf-converter) · [Core AVX2/Vulkan](https://github.com/aktalascloud/koboldcpp-avx2-vulkan-numa)

[Все проекты](https://github.com/aktalascloud)

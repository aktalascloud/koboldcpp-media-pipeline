# Медиакомплект KoboldCpp
[English](README.md) · [Установка/сборка](docs/BUILD.md) · [API и ТЗ OWUI](docs/API.ru.md) · [Лицензии](docs/LICENSES.md)

Один переносимый Windows-сервер на [оптимизированном форке Haswell/AVX2/RX580Polaris/gfx803](https://github.com/aktalascloud/koboldcpp-avx2-vulkan-numa). Запуск **Start.exe → KoboldCpp.exe**. Setup.ps1 нужен при установке/обновлении. Фото вGPU при простое; музыка/видео загружаются по требованию. Главные веса не зеркалируются.

Фото: RayQ8/Afterlight.25/RealismEnhancer1,Euler/simple8,eta0,CacheDiT.08;Normal736×1104 безautoSR,High928×1392 сClear4x(новыйHigh не измерен). YuNet/GPEN20/SFace.97/Gater доSR, после него повторов нет. МузыкаYuE2MP3; SFXSA3CPU WAV/MP3 до60с. TTS/helper/STT настраиваются, голосаRU/EN явные.

ВидеоWan5BTurbo/fullencoder/ProFP32/Euler-beta4,WG512,порог576,Clear720/лица/optionalRIFE. БезTiny/Helaman. Звук — отдельные генераторы и монтаж, безlip-sync. Native-проход<=121кадра/5.04с;20сdefault/60сmax — ТЗ оркестрации фильтром, не проверенная длинная Native-генерация.

| Saved test | Actual wall time | Scope |
|---|---:|---|
| PhotoNormal | 163.85s |29Oct, ff7d4d0b, one API |
| Separate photo4x | 6.04s |saved PNG, separate API |
| Video3.04s | 552.57s |30Oct,0986410a,I2V/Pro/Clear720/faces/all3audio |
| Audio revision | 57.96s |73RGB frames unchanged, no video rerun |
| Music32sMP3 | 57.01s |28Oct,6c03b583, photo return61.07s |
| SFX2sWAV /6sMP3 |10.57s /17.17s |30Oct CPU, photo stayed resident |


[Все последние измерения/ограничения в одном файле](results/measurements.json). **Для текущей1.124.1/ed587d0b только проверка запуска, новых скоростей нет.** Видеозамеры включали частный пользовательский адаптер, в публичном комплекте его нет.

![Последний обычный результат](results/photo-normal.png)
[Полный4x](results/photo-4x.webp) · [Глаза4x](results/photo-eyes.png). Последние примеры и данные только в results; модели/улучшалки/апскейлеры — MODELS, runtime один. [Правила локальной модели](AGENTS.md). Полный локальный EXE собирается на машине владельца; публично не зеркалируется без проверки прав на сторонний runtime. Полная генерация на чистой машине не тестировалась.

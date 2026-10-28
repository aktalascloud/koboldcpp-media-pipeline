# KoboldCpp media pipeline · Ray MOSS
[English](README.md) · [Windows-комплект](https://github.com/aktalascloud/koboldcpp-media-pipeline/releases/latest) · [API/OWUI](docs/API.md)

**Ray Q8 + Afterlight0,25 · DPM++2M SDE/sgm_uniform · 8 шагов · CFG1 · eta0 · shift5.** Дополнительной turbo нет: модель уже SFT Turbo. Слова-активаторы не нужны. Cache-DiT0,08/warmup4/Fn16/Bn2, FA, энкодерCPU20.

Normal/edit736×1104: YuNet960/GPEN20%/SFace0,97/Gater1×, без автоSR. `enable_hr:true` добавляет ClearReality4×. High928×1392 по умолчанию с4×, новый полный High не измерялся. МузыкаAceStep/MP3 и возврат фото сохранены.

**Полный реальный Normal4×: 175.14с**,2944×4416. Один запрос на EXE `6c03b583f7a2`,28октября2026. БазаAPI163,08с, лица1,36с, Gater3,87с, SR1,02с; остальное — кодирование, передача и переключение. Не переносить старые Dirty/Refined цифры или эти значения на другойSHA. [Доказательства](benchmarks/results.json).

![Обычный режим с улучшалками](examples/fullbody-processed.png)

**MODELS** — модели/LoRA/музыка; **DETAILERS** — лица/Gater; **UPSCALERS** — ClearReality. Dirty — необязательный запасной комплект (`-IncludeDirtyBackup`). Разово `Setup.ps1 -MossSourceDirectory <оригиналы>`, затем **Start.exe**. Проверенные старые пути переносятся поSHA; незнакомые файлы не удаляются. Основные веса/LoRA/ключи/кэши/логи не выкладываются. [Источники](docs/MODELS.md), [лицензии](docs/LICENSES.md), [оптимизированный KoboldCpp](https://github.com/aktalascloud/koboldcpp-avx2-vulkan-numa), [оригинал](https://github.com/LostRuins/koboldcpp).

## Музыка

**YuE2 Q8 + F16 VAE**, helper NeoHorse на стороне OWUI, MP3 stereo. 32с музыки через API: **57,01с** с переключением; фото снова в GPU к61,07с. Русская короткая проба одобрена пользователем; длинные песни не измерены. [Правила фильтра](docs/MUSIC.ru.md), [MP3](examples/yue2-russian-32s.mp3), [замеры](benchmarks/music.json). ACE-Step удалён. Веса CC-BY-NC-4.0 скачиваются у оригинального распространителя.

## Video

[480p Native generation,720p enhancement and API](docs/VIDEO.md) · [Русская инструкция OWUI](docs/VIDEO.ru.md) · [Measured timings](benchmarks/video.json). Models download from their original distributors.

<!-- video-research -->

[Restorers, alternative VAEs and factory sampler comparisons](docs/VIDEO_RESEARCH.md). No candidate VAE is silently enabled; the selected fast Super-Tiny pipeline remains the default.

# Медиасервер KoboldCpp · MOSS / YuE2 / Wan

[English](README.md) · [Комплект Windows](https://github.com/aktalascloud/koboldcpp-media-pipeline/releases/latest) · [ТЗ для фильтра OWUI](docs/MEDIA.ru.md) · [Лицензии](docs/LICENSES.md)

Один переносимый сервер на базе [оптимизированного KoboldCpp для Haswell/AVX2 и RX580 Polaris/gfx803](https://github.com/aktalascloud/koboldcpp-avx2-vulkan-numa). Изображения, музыка и видео используют общий Native-слот. По умолчанию фото-модель находится в GPU; переключение и возврат автоматические. Запуск: **Start.exe**, Setup.ps1 только для установки/обновления.

- Фото: Ray Q8 + Afterlight0.25 + RealismEnhancer1.0, Euler/simple8, CFG1, eta0, shift5, Cache-DiT0.08. Normal/edit736×1104 без авто-SR; явный enable_hr включает ClearReality4×. High928×1392 с4× настроен, новый набор High заново не измерен.
- Музыка: YuE2-3B Q8/F16 VAE, MP3 stereo; текст и стиль готовит клиентская helper-LLM.
- Видео: Wan5B Turbo Q4, полный энкодер и Pro FP32/DirectML, Euler/beta4, WG512, порогVAE576/тайл320. Генерация480p, ClearReality720p, лица; Tiny/Super-Tiny не используются. YuE2 добавляет музыкальную дорожку в тот же MP4-запрос. Это не синхронный Foley/речь/губы. RIFE48FPS опционален и не удлиняет ролик.

[Готовый API](docs/VIDEO.ru.md) · [Все фото-замеры](benchmarks/image-current.json) · [Все видео-замеры](benchmarks/video.json)

Реальные публичные запросы29октября2026 на EXE ff7d4d0b: Normal163.85с и отдельный4×6.04с. Видео с Pro, локальным пользовательским адаптером,720p,лицами,RIFE и музыкой —190.76с и258.05с для17исходных кадров (0.71с видео). Последняя цифра включает очередь/готовность профиля82.55с. Публичный комплект не распространяет и не включает приватный видеоадаптер. Лёгкий кэш0.04/0.08 совпал с контрольными латентами; устойчивого выигрыша0.08 нет.

![Обычная генерация](examples/ray-realism-normal.png)

[Полный4× без потерь](examples/ray-realism-4x.webp) · [Глаза4×](examples/ray-realism-eyes.png) · [Прежняя ночная сцена](examples/night-processed.png) · [Прежний часовщик](examples/watchmaker-processed.png)

Крупные модели и LoRA не зеркалируются: оригинальные загрузки/импорт пользователя, SHA и лицензии сохранены. Pro один раз конвертируется на CPU тем же комплектным Python; при работе PyTorch не нужен. Нет второй runtime-копии, ключей, кешей, логов и PID-файлов в Git/релизе. [Оригинальный KoboldCpp](https://github.com/LostRuins/koboldcpp).

## Единый интерфейс

`/media` и `/api`: фото/перерисовка, музыка, видео, лица, апскейл, Pro VAE, RIFE и звук. Общие API5001/5003; Native5005. Один Helper.kcpps содержит все служебные профили. Видеокэш Cache-DiT0.04/warmup1 включён по выбору пользователя, новых замеров нет.

Локальный KoboldCpp.exe (~356МиБ) содержит код/runtime; веса находятся отдельно. Автозапуск: `--background`, нативный GUI: `--native-gui`. Этот локальный EXE не зеркалируется в GitHub без отдельной проверки прав на сторонний runtime; публичный минимальный комплект по-прежнему запускается Start.exe.

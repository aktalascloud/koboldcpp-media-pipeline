# Медиапайплайн KoboldCpp · Refined Realism
[English](README.md) · [Windows-комплект](https://github.com/aktalascloud/koboldcpp-media-pipeline/releases/latest) · [API/OWUI](docs/API.md) · [Модели](docs/MODELS.md) · [Лицензии](docs/LICENSES.md)

Бэкенд — [наш оптимизированный KoboldCpp](https://github.com/aktalascloud/koboldcpp-avx2-vulkan-numa), форк [оригинала](https://github.com/LostRuins/koboldcpp). Проверено: Haswell AVX2, RX580 Polaris/gfx803, 8 ГБ.

**Refined Realism Q8 · DPM++ 2M SDE/sgm_uniform ·8шагов ·eta0.** Normal 736×1104, High 928×1392. Без LoRA. YuNet960/GPEN20%/SFace0,97, Gater1×, затем необязательный ClearReality Normal 4×. Helaman и повторные лица после SR отключены. Кэш0,08/warmup4/Fn16/Bn2; CFG1,shift5,FA; энкодерCPU20.

Один настоящий Normal-запрос сразу с4×: **161.96с**,2944×4416, включая PNG/API. Native 150.259с, лица1.183с, Gater3.694с, SR0.962с. Фото-модель уже была в GPU; после ответа снова загружена. Полный High Refined не измерялся. [Точные замеры и scope](benchmarks/results.json).

Выбран DPM по предпочтению пользователя. Не заявляем выигрыш над Euler/simple по самому самплингу: часть разницы запросов связана с отдельным кэшем Qwen. Сравнение ускорений native со стоком — в репозитории core.

Галерея трёх сцен, крупные глаза и точная пара Native/4× — в [основном README](README.md#current-moss-results). Это сохранённые тестовые результаты; заново для публикации ничего не генерировалось. Ошибки стрелок, пальцев и мелких деталей возможны.

Установка: распаковать код, предоставить точные исходники Refined BF16 и Artius W4-энкодера, один раз выполнить `Setup.ps1 -MossSourceDirectory <папка>`, затем запускать **Start.exe** напрямую. Для Refined проверенный URL загрузки не установлен: требуется пользовательский файл. Либо заранее положить проверенные GGUF по `models.json`. GPEN скачивается у исходного распространителя; Non-Commercial, не зеркалируется.

Normal без параметров работает без SR; `enable_hr:true` включает4×. High через `kcpp_quality:"quality"` автоматически включает4×. МузыкаMP3 загружается по API, затем возвращается фото. Видео отложено. Один runtime; отдельное видимое окно, автозапуск по желанию. Ключи, личные пути, кэши и логи не публикуются. Основные веса не загружаются в GitHub.

**Редактирование:** [контракт и правила фильтра OWUI](docs/EDITING.md). Instruction-edit, референсы и маски возвращают422. Поддерживается только явная перерисовка img2img; одного alias модели для выбора операции недостаточно.

**Новый кадр по нескольким фото:** [reference_synthesis](docs/REFERENCE-SYNTHESIS.md). Любая выбранная vision-модель клиента анализирует фото и составляет caption; MOSS получает только текст. Точная идентичность лица не гарантируется, новых весов нет.

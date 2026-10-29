# Единый медиасервер: контракт для фильтра OWUI

Один настраиваемый `KOBOLD_BASE_URL`: `http://<AI_HOST>:5001`. Порт5003 является внутренним Native. Ключ и helper-модель хранить в настройках OWUI, не в коде. Сервер не привязан к NeoHorse или другому провайдеру LLM.

`GET /v1/media/capabilities` возвращает маршруты; подробности: `/v1/images/capabilities`, `/v1/music/capabilities`, `/v1/videos/capabilities`.

## Изображения

AUTOMATIC1111: `POST /sdapi/v1/txt2img`. [Доппараметры Normal](image-api-preset.json). Normal работает без явного `normal`:736×1104,8шагов,Euler/simple,CFG1,shift5,eta0,Cache-DiT0.08. Статические адаптеры RayQ8: Afterlight0.25 и RealismEnhancer1.0. Не добавлять LoRAпути/веса в запрос. Спецтриггеров в официальных карточках этих LoRA нет.

Один проход улучшения prompt до180английских слов. Кэшировать готовый prompt по исходному запросу/режиму/версии шаблона. Обычное описание Caption; Layout только при необходимости точной разметки. Не переписывать уже улучшенный prompt повторно.

High: `kcpp_quality:"quality"`, `enable_hr:true`; [пресет](image-api-high-preset.json).928×1392 с4×SR настроены, текущая полная High-цепочка с новым набором LoRA заново не измерялась. Обычный режим автоматически не масштабируется. `enable_hr:true` включает прокси4×; Native hires выключен.

Готовый PNG: `POST /sdapi/v1/extra-single-image`, поля `image:PNGbase64`, `upscaling_resize:4`. Лица/Gater применяются до ClearReality; собственные уже обработанные PNG узнаются по маркерам.

OpenAIсовместимая генерация: `/v1/images/generations`. MOSSредактирование — явный `operation:img2img`, один target, целиковая перерисовка. Instruction-edit,маски и сырые multi-image references возвращают ошибку. `/v1/images/synthesize` принимает текстовые анализы клиентской vision-LLM; точный перенос лица не гарантируется.

## Музыка

`POST /api/extra/music/generate`, ответ — MP3 stereo. Helper в OWUI готовит оригинальные `lyrics` и `style`; сервер рендерит YuE2:

```json
{"lyrics":"[Verse]\nОригинальный русский текст","style":"Russian pop, clear warm vocals, acoustic instruments","duration":32,"cot":"off","num_inference_steps":8,"guidance_scale":1.01,"use_mp3":true,"stereo":true}
```

`duration` — приблизительный верхний предел через25semantic tokens/с. Для инструментала оставить `lyrics` пустым и указать `no vocals`. Не передавать ACE-Stepполя `inference_steps/shift/vocal_language`; не смешивать imageCFG с музыкальным `guidance_scale`. Русский вокал подтверждён пользователем на прежней32с пробе, не на каждом новом билде.

## Видео и звук

Отдельный `POST /v1/videos/generations`; [JSON](video-api-preset.json) и [подробности](video-owui-instructions.ru.md). Не отправлять видео через фото-редактор или порт5003. Prompt описывает движения и камеру; `audio.style` — отдельный музыкальный фон.

`frames:17` означает0,71с при24FPS. RIFE48FPS не увеличивает длительность. Звук YuE2 — музыкальная дорожка, не синхронные шумы/речь/губы. Перед48FPS проверить capabilities; без установленного RIFE использовать24.

## Ответы, ошибки и переключение

Относительные URL объединять с `KOBOLD_BASE_URL`, не с адресом OWUI. Скачивать PNG/MP3/MP4 только с настроенного сервера, загружать в файлы OWUI и возвращать настоящие mediaссылки. Не подменять ошибки или пустое аудио успешной картинкой. Не логировать ключи и полные base64.

Модели переключает сервер, один GPUконтекст за раз. По умолчанию в GPU фото-модель. Во время видео Native освобождает GPU для Pro/ClearReality/лиц, затем при необходимости загружается YuE2 и возвращается фото-модель. Фильтру не нужны команды запуска/убийства процессов или доступ к файлам сервера.

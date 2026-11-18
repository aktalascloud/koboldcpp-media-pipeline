# Единый API KoboldCpp

Клиент подключается к одному адресу. Порты 5001 и 5003 используют одну очередь. Порт Native 5005 служебный. [Договоры медиаопераций](API.md) · [ТЗ OWUI](API.ru.md) · [Снимок OpenAPI](unified-openapi.json).

| GET | Что открывает |
|---|---|
| `/api`, `/docs` | Поиск по маршрутам обоих разделов |
| `/openapi.json` | Схема с текущим каталогом Native и расширениями Media |
| `/v1/media/openapi.json` | Схема медиасервиса, доступная при переключении Native |
| `/api/native` | Встроенная справка KoboldCpp |
| `/media`, `/videoui` | Интерфейс медиасервиса |

Медиамаршруты используют профиль сервера. Видео, фото и музыка переключаются автоматически. Маршруты совместимости зависят от возможностей загруженной модели и конфигурации. Общий каталог клиента исключает административные и служебные команды остановки. Сохранение `/v1/media/settings` возможно с локальной машины в состоянии простоя с текущей ревизией и заголовком `X-Kobold-Config: 1`.

`POST /v1/media/generations` принимает `type: image | video | music` и объект `parameters`. Речь и эффекты вызываются через `/v1/audio/speech` и `/v1/audio/sfx`. Используйте `GET /v1/media/capabilities`, `/v1/audio/capabilities` и профильные capabilities перед запросом. Для видео сохраняйте `Idempotency-Key` и исходные параметры. При 202 получайте состояние по `/v1/videos/jobs/{request_id}`.

## Выбор маршрута

Каталог и форматы запросов: `/docs` на работающем сервере или [снимок OpenAPI](unified-openapi.json) для работы офлайн. Источник медиасхемы — [MediaUI.py](../tools/MediaUI.py).

| Задача | Маршрут |
|---|---|
| Создать фото, видео или музыку | `POST /v1/media/generations` |
| Улучшить фото или сохранённое видео | `POST /v1/media/upscale` |
| Проверить квитанцию видео или отменить задачу в очереди | `GET /v1/videos/jobs/{request_id}`, `POST /v1/videos/jobs/{request_id}/cancel` |
| Импортировать MP4, повысить FPS, заменить звук | `POST /v1/videos/import`, `/v1/videos/interpolate`, `/v1/videos/soundtrack` |
| Озвучить, распознать речь или создать эффект | `POST /v1/audio/speech`, `/v1/audio/transcriptions`, `/v1/audio/sfx` |

Для совместимых клиентов используйте тот же адрес сервера. В полном каталоге есть маршруты KoboldAI, OpenAI, Ollama, Anthropic, Stable Diffusion и ограниченный набор ComfyUI. Проверяйте возможности выбранной модели перед запросом.

### Псевдонимы вне OpenAPI

| Группа | Маршруты |
|---|---|
| Возможности медиа | `GET /api/extra/image-capabilities`, `GET /api/extra/music/capabilities`, `GET /api/extra/video/capabilities` |
| Фото | `POST /images/generations`, `POST /images/edits`, `POST /images/synthesize`, `GET /images/synthesis-schema`, `POST /sdapi/v1/upscale` |
| Видео и речь | `POST /api/extra/video/generate`, `POST /api/extra/video/upscale`, `POST /api/extra/tts`, `POST /api/extra/transcribe` |
| KoboldAI | `POST /api/latest/generate`, `GET /api/latest/info/version`, `GET /api/latest/model`, `GET /api/latest/config/max_context_length`, `GET /api/latest/config/max_length`, `POST /api/extra/tokenize` |
| Другие клиенты | `GET /api/ps`, `GET /models`, `POST /chat/completions`, `POST /completions`, `POST /v1/completion`, `POST /messages`, `POST /responses` |

При обновлении снимка сохраните ответ `GET /openapi.json` с порта 5003, когда `x-kobold-native-catalog` равен `available`. Сверьте его с ответом на порту 5001 и с `GET /v1/media/openapi.json` для медиамаршрутов.

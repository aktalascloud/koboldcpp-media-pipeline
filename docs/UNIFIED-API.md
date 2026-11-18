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

## Медиа

| Метод | Маршрут | Назначение |
|---|---|---|
| GET | `/api/extra/image-capabilities` | Image operation contract. |
| GET | `/api/extra/music/capabilities` | YuE2 music contract. |
| POST | `/api/extra/music/generate` | YuE2 MP3, caller-provided lyrics/style. |
| POST | `/api/extra/music/prepare` | Prepare the configured music model for the API. |
| POST | `/api/extra/transcribe` | Распознавание аудио через настроенный STT. |
| POST | `/api/extra/tts` | Речь через настроенный TTS. Язык и голос задаются в API. |
| GET | `/api/extra/version` | Native version and media capability flags for this entry point. |
| GET | `/api/extra/video/capabilities` | Frames, cache, optional RIFE and audio limits. |
| POST | `/api/extra/video/generate` | Wan480p/Pro, optional720p faces/RIFE; timed music, SFX and speech mixed into MP4. No lip-sync. |
| GET | `/api/extra/video/media/{video_id}/{asset}` | Download a stored video, audio track or frame. Byte ranges are supported. |
| POST | `/api/extra/video/upscale` | Postprocess a stored generated video. |
| GET | `/health` | Live service and queue state. |
| POST | `/images/edits` | Explicit operation=img2img; unsupported masks/references return422. |
| POST | `/images/generations` | OpenAI-compatible image generation. |
| GET | `/images/synthesis-schema` | Contract for client-side visual analysis and text reference synthesis. |
| POST | `/images/synthesize` | Text analyses supplied by a client vision model, not native image-reference conditioning. |
| POST | `/sdapi/v1/detail` | Run the configured photo detailer. |
| POST | `/sdapi/v1/extra-single-image` | Faces/Gater before ClearReality4x; preserve trusted processing markers. |
| POST | `/sdapi/v1/img2img` | Whole-frame redraw of one target. Not instruction editing or multiple references. |
| GET | `/sdapi/v1/progress` | Image progress, including facade postprocessing. |
| POST | `/sdapi/v1/txt2img` | Generate an image; faces/Gater, optional ClearReality4x. |
| POST | `/sdapi/v1/upscale` | Faces/Gater before ClearReality4x; preserve trusted processing markers. |
| GET | `/sdapi/v1/upscalers` | Configured public image upscaler. |
| GET | `/v1/audio/capabilities` | Подключения хелпера/TTS/STT и проверка голосов. |
| POST | `/v1/audio/sfx` | Генерация звуковых эффектов SA3 CPU,0.25–60секунд; ответ WAV либо MP3, фото-модель остаётся вGPU. |
| GET | `/v1/audio/sfx/capabilities` | Доступность SFX, пределы длительности и форматы. |
| POST | `/v1/audio/speech` | Речь через настроенный TTS. Язык и голос задаются в API. |
| POST | `/v1/audio/transcriptions` | Распознавание аудио через настроенный STT. |
| GET | `/v1/audio/voices` | Список голосов подключённого сервера. |
| GET | `/v1/images/capabilities` | Image operation contract. |
| POST | `/v1/images/edits` | Explicit operation=img2img; unsupported masks/references return422. |
| POST | `/v1/images/generations` | OpenAI-compatible image generation. |
| GET | `/v1/images/synthesis-schema` | Contract for client-side visual analysis and text reference synthesis. |
| POST | `/v1/images/synthesize` | Text analyses supplied by a client vision model, not native image-reference conditioning. |
| POST | `/v1/media/audio-plan` | Создать план аудиодорожек с таймкодами выбранным хелпером. |
| GET | `/v1/media/capabilities` | Discover all media operations and automatic model switching. |
| POST | `/v1/media/generations` | Unified image, music or video generation. type selects the task; parameters follow its specific contract. |
| GET | `/v1/media/settings` | Effective public settings; no credentials or private paths. |
| POST | `/v1/media/settings` | Save bounded settings from the local machine while idle; requires current revision and X-Kobold-Config:1. |
| POST | `/v1/media/upscale` | Unified image/video postprocessing. Video requires video_id and optional enhance_faces only. |
| GET | `/v1/music/capabilities` | YuE2 music contract. |
| GET | `/v1/videos/capabilities` | Frames, cache, optional RIFE and audio limits. |
| POST | `/v1/videos/generations` | Wan480p/Pro, optional720p faces/RIFE; timed music, SFX and speech mixed into MP4. No lip-sync. |
| POST | `/v1/videos/import` | Import a client-owned MP4, up to30seconds/2MP; binary video/mp4 body. |
| POST | `/v1/videos/interpolate` | RIFE48/60FPS for an owned imported/generated24FPS clip up to30seconds/2MP, without another Wan render. |
| GET | `/v1/videos/jobs/{request_id}` | Persistent generation receipt; survives client disconnect and marks interrupted jobs unknown. |
| POST | `/v1/videos/jobs/{request_id}/cancel` | Cancel a queued request only; never globally abort Native. |
| POST | `/v1/videos/lipsync` | Postprocess a stored video with explicit speech and target_box; optional non-commercial Wav2Lip runtime required. |
| POST | `/v1/videos/soundtrack` | Replace audio on a new copy of a completed video using reviewed event timestamps, without regenerating its frames. |
| POST | `/v1/videos/upscale` | Postprocess a stored generated video. |

## Совместимость Native

| Метод | Маршрут | Назначение |
|---|---|---|
| GET | `/.well-known/serviceinfo` | Retrieve the common API identity provider |
| POST | `/api/chat` | Generate a chat response using the Ollama API format |
| POST | `/api/embed` | Ollama-compatible embeddings when enabled. |
| POST | `/api/extra/abort` | Aborts the currently ongoing text generation. |
| POST | `/api/extra/data/list` | List available saved slots from the KoboldCpp server. |
| POST | `/api/extra/data/load` | Loads data from a save slot in the database file in the KoboldCpp server. |
| POST | `/api/extra/data/save` | Saves data to a slot in a database file in the KoboldCpp server. |
| POST | `/api/extra/detokenize` | Converts an array of token IDs into a string. |
| POST | `/api/extra/embeddings` | Creates an embedding vector representing the input text. Please refer to OpenAI documentation |
| GET | `/api/extra/generate/check` | Poll the incomplete results of the currently ongoing text generation. |
| POST | `/api/extra/generate/check` | Poll the incomplete results of the currently ongoing text generation. Supports multiuser mode. |
| POST | `/api/extra/generate/stream` | Generate text with a specified prompt. SSE streamed results. |
| POST | `/api/extra/json_to_grammar` | Converts a provided JSON schema into GBNF grammar. |
| GET | `/api/extra/last_logprobs` | Obtains the most recent token logprobs. |
| POST | `/api/extra/last_logprobs` | Obtains the token logprobs of the most recent request. |
| POST | `/api/extra/multiplayer/getstory` | Fetches the current multiplayer story data, LZMA compressed encoded base64 |
| POST | `/api/extra/multiplayer/setstory` | Sets the current multiplayer story and increments the turn. |
| POST | `/api/extra/multiplayer/status` | Fetches the current multiplayer turn information. |
| POST | `/api/extra/music/transcribe` | Transcribes music or audio to text and ABC notation |
| GET | `/api/extra/perf` | Retrieve the KoboldCpp recent performance information |
| GET | `/api/extra/preloadstory` | Retrieves the KoboldCpp preloaded story |
| GET | `/api/extra/speakers_list` | Get a list of available TTS speakers. |
| POST | `/api/extra/tokencount` | Counts the number of tokens in a string. |
| POST | `/api/extra/tokenize` | Counts the number of tokens in a string. |
| GET | `/api/extra/true_max_context_length` | Retrieve the actual max context length setting value set from the launcher |
| POST | `/api/extra/websearch` | Searches the web using DuckDuckGo and returns the top 3 results. |
| POST | `/api/generate` | Generate text using the Ollama API format |
| GET | `/api/latest/config/max_context_length` | Retrieve the current max context length setting value that public backends see |
| GET | `/api/latest/config/max_length` | Retrieve the current max length (amount to generate) setting value |
| POST | `/api/latest/generate` | Generate text with a specified prompt |
| GET | `/api/latest/info/version` | Current KoboldAI United API version |
| GET | `/api/latest/model` | Retrieve the current model string. |
| GET | `/api/ps` | List the active model in Ollama format |
| POST | `/api/show` | Ollama compatibility model information. |
| GET | `/api/tags` | List the active model in Ollama format |
| GET | `/api/v1/config/max_context_length` | Retrieve the current max context length setting value that public backends see |
| GET | `/api/v1/config/max_length` | Retrieve the current max length (amount to generate) setting value |
| POST | `/api/v1/generate` | Generate text with a specified prompt |
| GET | `/api/v1/info/version` | Current KoboldAI United API version |
| GET | `/api/v1/model` | Retrieve the current model string. |
| GET | `/api/version` | Ollama compatibility version. |
| POST | `/audio/speech` | Generates Text-To-Speech audio from input text. Please refer to OpenAI documentation |
| POST | `/audio/transcriptions` | Create an OpenAI-compatible audio transcription |
| GET | `/audio/voices` | List voices available to the OpenAI-compatible speech endpoint |
| POST | `/chat/completions` | Generates a response from a list of messages. Please refer to OpenAI documentation |
| POST | `/completions` | Generates text continuations given a prompt. Please refer to OpenAI documentation |
| GET | `/get_tts_settings` | Legacy XTTS compatibility settings. |
| GET | `/history` | ComfyUI compatibility record for the last image request. |
| POST | `/mcp` | Call tools exposed by configured MCP servers |
| POST | `/messages` | Creates a message using the Anthropic Messages API format |
| GET | `/models` | List and describe the various models available in the API. Please refer to OpenAI documentation |
| GET | `/object_info` | Limited ComfyUI compatibility node descriptions. |
| POST | `/prompt` | Run the subset of ComfyUI image workflows accepted by Native. |
| GET | `/props` | Returns the Jinja template stored in the GGUF model, if found. |
| POST | `/responses` | Emulates OpenAI Responses API. Very experimental, not recommended (use chat completions instead). Please refer to OpenAI documentation |
| GET | `/sdapi/v1/get_last.json` | Retrieve the cached result of an image generation |
| POST | `/sdapi/v1/interrogate` | Generates a short text caption describing an image |
| POST | `/sdapi/v1/interrupt` | Interrupt the image request that owns the supplied genkey. |
| GET | `/sdapi/v1/latent-upscale-modes` | List latent upscale modes |
| GET | `/sdapi/v1/loras` | List available image LoRAs |
| GET | `/sdapi/v1/options` | Gets configuration info for image generation |
| GET | `/sdapi/v1/recovery-status` | Read running, complete or unknown status for a genkey. |
| GET | `/sdapi/v1/samplers` | Gets a list of supported samplers |
| GET | `/sdapi/v1/schedulers` | List supported image schedulers |
| GET | `/sdapi/v1/sd-models` | Gets a list of image generation models |
| GET | `/sdcpp/v1/capabilities` | Native SDCPP compatibility capability flags. |
| POST | `/sdcpp/v1/img_gen` | Native SDCPP image generation without Media postprocessing. |
| GET | `/sdcpp/v1/jobs/{job_id}` | Read a Native SDCPP request record. |
| POST | `/sdcpp/v1/jobs/{job_id}/cancel` | Cancel a Native SDCPP request. |
| GET | `/sdcpp/v1/model-files` | Native SDCPP list of available model descriptors. |
| GET | `/sdcpp/v1/models` | Native SDCPP compatibility model list. |
| GET | `/sdcpp/v1/models/status` | Native SDCPP loaded model state. |
| GET | `/sdcpp/v1/recipes` | Native SDCPP compatibility recipes. |
| GET | `/speakers` | Legacy XTTS speakers metadata. |
| GET | `/system_stats` | ComfyUI compatibility metadata; values are placeholders. |
| POST | `/tts_to_audio` | Legacy XTTS text-to-audio when enabled. |
| POST | `/v1/chat/completions` | Generates a response from a list of messages. Please refer to OpenAI documentation |
| POST | `/v1/completion` | Generates text continuations given a prompt. Please refer to OpenAI documentation |
| POST | `/v1/completions` | Generates text continuations given a prompt. Please refer to OpenAI documentation |
| POST | `/v1/embeddings` | Creates an embedding vector representing the input text. Please refer to OpenAI documentation |
| POST | `/v1/messages` | Creates a message using the Anthropic Messages API format |
| GET | `/v1/models` | List and describe the various models available in the API. Please refer to OpenAI documentation |
| POST | `/v1/responses` | Emulates OpenAI Responses API. Very experimental, not recommended (use chat completions instead). Please refer to OpenAI documentation |
| GET | `/view` | PNG from the last ComfyUI-compatible image request. |
| GET | `/voice/check` | Legacy VITS voice capability metadata. |
| GET | `/voice/speakers` | Legacy VITS speakers metadata. |
| GET | `/voice/vits` | Legacy VITS query-text to WAV when enabled. |

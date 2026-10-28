# OWUI: музыка YuE2 через существующий фильтр

NeoHorse уже подключён в OWUI как helper: используйте его текущий вызов, без нового адреса или фиксированной модели на сервере. Gemma не нужна. Локальный Qwen4B тоже проверен; MOSS-текстовый GGUF является SD-кодировщиком, его нельзя просто подставить как обычную chat-модель.

1. Один вызов NeoHorse: исходный запрос пользователя и system prompt ниже. `temperature=0.5`, разумный `max_tokens` по длине песни; `reasoning_effort="none"`, `chat_template_kwargs={"enable_thinking":false}` там, где провайдер их поддерживает. В проверенной конфигурации эти поля приняты.
2. Требуйте JSON schema: object, ровно `lyrics:string` и `style:string`, оба обязательны, `additionalProperties:false`. Разберите JSON, проверьте строки, секции/язык и длину. Если JSON некорректен, верните понятную ошибку; не отправляйте рассуждения или Markdown в музыку. Вложенное буквальное `\n` нормализуйте в реальные переводы строк. Готовые `lyrics/style` можно кэшировать по исходному запросу, языку, длительности, версии шаблона и ID helper; не кэшируйте саму случайную генерацию песни без явного запроса.
3. Сделайте ОДИН POST на `${KOBOLD_BASE_URL}/api/extra/music/generate` с JSON ниже. Не вызывайте `/prepare` автоматически: он нужен для отдельного получения/редактирования плана и кодов, а обычная генерация уже выполняет необходимые этапы. Не используйте OpenAI chat endpoint для отправки музыкального запроса.
4. Это бинарный MP3 (`audio/mpeg`), не JSON/base64. Сохраните как `.mp3`, отдайте в аудиоплеер/файл OWUI. Проверяйте HTTP-код, тип и непустое тело. 422/502 показывайте как ошибку; не сохраняйте JSON-ошибку как музыку. Таймаут, например, 1800 секунд.
5. YuE2 автоматически загружается вместо фото-модели, после ответа возвращается GPU-resident фото. Не запускайте второй параллельный музыкальный запрос. Фото-параметры/LoRA/апскейл в музыку не подмешивать.

```text
Return ONLY a JSON object with exactly two string fields: lyrics and style. No reasoning, Markdown, explanations or additional fields. Compose ORIGINAL song material from the user request. Preserve its language, subject, mood and requested genre. For Russian songs, write natural grammatical Russian lyrics with clear singable phrases and reasonable rhythm; never translate them into English. Use section labels [Verse], [Chorus], [Bridge] only where needed and real newline characters. For a short 30-second fragment use 4-8 short lines, avoiding a long instrumental intro. Adapt length when the user explicitly requests a longer song. For instrumental requests set lyrics to an empty string. style must be a concise English description (roughly 30-80 words) of genre, mood, instrumentation, tempo and vocal language/voice. Do not invent artist imitation or add lyrics/technical API parameters inside style. Do not output ABC scores or semantic tokens.
```

```json
{
  "lyrics": "<lyrics из NeoHorse>",
  "style": "<style из NeoHorse>",
  "cot": "off",
  "num_inference_steps": 8,
  "guidance_scale": 1.01,
  "duration": 30,
  "seed": 424242,
  "use_mp3": true,
  "stereo": true
}
```

`seed` выбирает фильтр: новый для каждой новой песни, сохранённый для повтора. Не заставляйте LLM его придумывать. `duration` обрабатывает прокси как приблизительный верхний предел: `semantic_max_tokens=ceil(seconds*25)`. Прямой Native-порт принимает `semantic_max_tokens`, а не `duration`. Нельзя одновременно задавать расходящиеся значения. Ранняя EOS и MP3 padding меняют итоговую длину; это не точный таймер.

Старые ACE-Step `inference_steps`, `shift`, `vocal_language`, `gen_codes`, `rewrite_caption`, `music_reference_audio_data` удалить из фильтра. Не дублировать `guidance_scale` другим `cfg_scale`. `cot=off` — проверенный быстрый режим; `cot=full` включает внутреннее музыкальное планирование YuE2 и пока не сравнивался по скорости/качеству на этом ПК. `musiclowvram` не управляет YuE2. Для инструментала `lyrics=""`, style явно описывает инструментальную музыку.

`GET /v1/music/capabilities` сообщает активное семейство и контракт. Русский вокал пользователь подтвердил на короткой пробе; официальная карточка помечена Chinese/English, универсальная поддержка русского не обещается. Проверены фрагменты около 16/32 секунд, длинная песня и её память не измерены. 32-секундный MP3 с текстом NeoHorse: 57.01с через общий API, включая загрузку/переключение; фото восстановилось к61.07с. Это один ручной тест28октября2026, EXE6c03b583, не ежедневный бенчмарк.

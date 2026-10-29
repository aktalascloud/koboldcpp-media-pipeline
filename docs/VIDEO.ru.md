# Видео для фильтра OWUI

Базовый URL: http://<AI_HOST>:5001. Порт5003 внутренний. Возможности: GET /v1/videos/capabilities. Вызов: POST /v1/videos/generations, JSON; готовый файл video-api-preset.json.

```json
{
  "model": "kobold-wan22-turbo",
  "prompt": "An adult woman naturally blinks and turns her head, subtle fabric movement, realistic eyes, steady camera",
  "frames": 17,
  "resolution": "480p",
  "orientation": "portrait",
  "seed": 424242,
  "sampler_name": "euler",
  "scheduler": "beta",
  "steps": 4,
  "cfg_scale": 1,
  "eta": 0,
  "flow_shift": 5,
  "cache_mode": "disabled",
  "upscale_to": "720p",
  "enhance_faces": true,
  "interpolate_fps": 48,
  "audio": {"enabled":true,"style":"Gentle cinematic instrumental background, quiet warm piano and soft strings, no vocals","lyrics":"","volume":0.7}
}
```

Для I2V добавить image с PNGbase64. Для продолжения — continue_from с ID клипа; длинная непрерывность не подтверждена. Локальные пути и произвольные URL запрещены. Модель и статические адаптеры выбирает сервер. Локально используется пользовательская Wan5BLoRA1.0; публичный комплект её не распространяет и автоматически не включает.

Полный Wan-энкодер и диффузия работают в Kobold;48-канальные латенты декодирует ProFP32/DirectML. Tiny/Super-Tiny не используются. Порог VAE576 соответствует тайлу320, перекрытие64. Native VRAM6500MiB, у Pro дополнительно контролируется фактическая память. Native выгружается перед Pro/SR.

Генерация:832×480 или480×832. После ClearReality:1248×720 или720×1248, без растягивания. YuNet960/GPEN20%/SFace0.97 применяются после масштабирования. Gater и повторное сильное восстановление видео выключены.

frames — исходные кадры24FPS,4n+1. Проверенные17кадров — около0,71с, не17секунд.49кадров —2,04с. Длинные клипы экспериментальны. RIFE48FPS удваивает кадры, сохраняя длительность; один конечный кадр повторяется. Если capabilities не содержит48, использовать24.

Звук — отдельная музыка YuE2 и сборка дорожки в MP4. Это не совместная аудиовидеомодель, не синхронный Foley и не липсинк. audio:false отключает звук. Исходная музыка сохраняется MP3; MP4 содержит AAC, видео копируется без дополнительного перекодирования. Клиент может передать style/lyrics; сервер не привязан к конкретной helper-LLM.

Кэш необязателен: cache-dit с threshold=0.04,warmup=1,Fn=16,Bn=2 или threshold=0.08,warmup=2,Fn=16,Bn=2. На проверенной сцене латенты совпали с контролем; устойчивого ускорения0,08 нет. Основной пресет без кэша. Фото-параметры автоматически в видео не переносить.

Ответ: id,url,data[0].url,metadata с фактическими размерами, кадрами,FPS,звуком и временами. Относительный URL объединить с адресом Kobold, не OWUI. Фильтр скачивает MP4, загружает в файлы OWUI и возвращает видео в чат. MediaURL поддерживает Range; MP3 доступен через metadata.audio_source_url.

Таймаут клиента не менее500с; общий серверный бюджет450с включает очередь, загрузки, Native,Pro,пост и звук. Латенты или незавершённый результат не выдаются за успешный MP4. При ошибке показать JSONошибку. После успешного запроса metadata.resident_photo_ready подтверждает возврат фото-модели в GPU.

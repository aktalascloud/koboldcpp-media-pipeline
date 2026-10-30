# Задание другой LLM: подключить настоящий SFX API к существующему фильтру OWUI

Public template: configure YOUR_KOBOLD_HOST in the existing OWUI filter. No personal endpoint is included.

## Адрес

**Kobold base URL: `http://YOUR_KOBOLD_HOST:5001`**. Публичный alias5003 также работает. Частный Native5005 не использовать. С машины OWUI localhost обозначает сам OWUI, а не этот Kobold.

```text
GET  http://YOUR_KOBOLD_HOST:5001/v1/audio/sfx/capabilities
POST http://YOUR_KOBOLD_HOST:5001/v1/audio/sfx
GET  http://YOUR_KOBOLD_HOST:5001/openapi.json
```

## Запрос и ответ

```json
{
  "prompt": "Soft natural wind and gentle fabric rustling, no voices, no music",
  "duration": 5,
  "seed": 424242,
  "response_format": "wav"
}
```

`prompt`:1–2000символов, описание нужного звука по-английски. `duration`:0.25–60секунд, default5. `seed`:0..2147483647. `response_format`:wav либо mp3. Остальные поля не передавать: ни voice, ни image-model, ни sampler/LoRA. Шагов8, SA3 Small SFX работает на CPU Haswell; фото-модель остаётся вGPU. Для длинного звука сервер делает несколько настоящих коротких генераций и соединяет их20мс кроссфейдами; не зацикливает один кусок. Сшивка не гарантирует идеально стабильную семантику длительного эффекта.

**HTTP200 содержит бинарный WAV/MP3, а не JSON или URL.** Content-Type audio/wav либо audio/mpeg. Заголовки:

- `X-SFX-Id` — ID задания, не URL скачивания;
- `X-SFX-Seconds` — длительность исходного PCM;
- `X-SFX-Generation-Seconds` — фактическое время звуковой стадии;
- `Content-Disposition` — имя файла.

WAV —48kHz stereo PCM16. У MP3 возможна обычная кодековая задержка/padding. Ошибки422 — параметры;503 — нет моделей/runtime или очередь;504 — превышение бюджета;502 — ошибка генератора. Ошибка не является успешным звуком. Общий серверный бюджет450секунд включает ожидание очереди; клиентский timeout разумно ставить470–480секунд.

```python
import httpx

async def make_sfx(prompt: str, seconds: float) -> bytes:
    timeout = httpx.Timeout(480, connect=10)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            "http://YOUR_KOBOLD_HOST:5001/v1/audio/sfx",
            json={"prompt": prompt, "duration": seconds,
                  "seed": 424242, "response_format": "wav"},
        )
        response.raise_for_status()
        if response.headers.get("content-type", "").split(";")[0] != "audio/wav":
            raise RuntimeError("Kobold returned something other than WAV")
        if len(response.content) < 44:
            raise RuntimeError("Empty SFX response")
        return response.content
```

В реальном фильтре переиспользуй существующий async-клиент/Valves, не зашивай этот адрес в нескольких местах. Не создавай новую отдельную службу/модель. Итоговый фильтр — один Python-файл.

## Автоматический звук для видео

1. Сначала сгенерировать/собрать **реальное** немое видео. Итоговая длительность по умолчанию20секунд, максимум60; текущий video-endpoint остаётся ограниченным короткими сегментами, поэтому длинный монтаж выполняет фильтр последовательными I2V-продолжениями. SFX duration60 — предел звука, а не обещание одного60-секундного video-прохода.
2. Извлечь кадры с глобальными таймкодами и проанализировать выбранной vision-моделью OWUI. Helper получает наблюдения, а не выдумывает события по исходному описанию.
3. Составить музыку/SFX/речь на общей шкале. Для каждого эффекта вызвать новый `/v1/audio/sfx` с duration=end−start. Сохранить полученные байты в принадлежащий заданию WAV и разместить его в start через FFmpeg.
4. Прежний обходной путь — создавать звуковые копии короткого видео через `/v1/videos/soundtrack` только ради SFX — теперь не нужен, если capabilities нового endpoint подтверждают доступность.
5. Музыка отдельно: `POST http://YOUR_KOBOLD_HOST:5001/api/extra/music/generate`, JSON `{"style":"Quiet cinematic instrumental, no vocals","lyrics":"","duration":20,"response_format":"mp3"}`; ответ бинарный MP3. YuE2 duration — приблизительный верхний предел, измерить настоящую длину.
6. Речь отдельно: `POST http://YOUR_KOBOLD_HOST:5001/v1/audio/speech`, JSON `{"model":"tts-1","input":"Мгновение тишины.","voice":"sage","language":"ru","response_format":"wav"}`. Реальные голоса: ru/shimmer=Маша, ru/sage=Света, ru/echo=Дима; en/shimmer=Heart, en/Ryan=Michael. Aliases одного голоса не считать разными тембрами. `speaker_id -> language -> voice` сохранять стабильно. Язык задавать явно; русский по умолчанию. Не менять глобальные профили сервера ради одного персонажа.
7. Свести WAV/MP3 на OWUI:48kHz stereo, задержки по таймкодам, громкости, короткие fades и limiter. В финальной аудиостадии видео `-c:v copy`, AAC192k/faststart; не запускать Wan/VAE/SR повторно. Музыка тише речи. Не обрезать пользовательскую реплику молча и не угадывать пол персонажа по лицу.

Для точного удара в SFX может понадобиться анализ начала реального звука и перенос атаки в таймкод; SA3 не гарантирует позицию каждого удара внутри сгенерированного окна. Закадровая речь не является lip-sync. Не обещать полное равенство совместной AV-модели LTX.

Кэшировать по prompt/duration/seed/format/backend, исключить повторный POST из inlet/outlet одного сообщения. После сетевого timeout не повторять дорогой POST вслепую. При недоступном SFX сохранить видео и вернуть понятную ошибку, не подменять звук музыкой/тишиной под видом успеха. Файлы хранить штатным способом OWUI с доступом только владельца. Не логировать токены или Base64.
